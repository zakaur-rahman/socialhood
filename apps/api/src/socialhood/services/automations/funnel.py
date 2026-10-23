"""Flow analytics (GR-15): the per-step funnel and the A/B split results of one automation.

Built from what is already recorded, with nothing new on the send path:

- **reached / failed / taps / captures / skipped / consents** come from the step log
  (``automation_run_steps``): one row per step a run reached, whose ``detail`` holds the tapped
  option, the saved answer, the skip and the consent answer;
- **sent / delivered / read** from the status of the step's message (``messages``);
- **link clicks** from ``link_clicks`` (counted clicks only, links.is_bot);
- **a Split's branches**: each run's split row says the path it took; the branch's figures are the
  rows of the steps reachable from that path, for the runs that took it.

Runs of an automation still on its message settings have no step log: its message step is built
from the run itself (the run's DM). Steps come in the order a walk meets them, then any the
current flow can't reach.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import Integer, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from socialhood.models.automations import (
    Automation,
    AutomationRun,
    AutomationRunStep,
    LinkClick,
    RunResult,
)
from socialhood.models.contacts import Tag
from socialhood.models.inbox import Message
from socialhood.schemas.flows import AskStep, FlowDefinition, RandomizeStep, SendStep, Step
from socialhood.schemas.funnel import (
    AutomationFunnel,
    FunnelStep,
    SplitBranch,
    SplitResult,
)
from socialhood.services.automations import flow_preview, flow_store, flows

SENT = ("sent", "delivered", "read")
DELIVERED = ("delivered", "read")
SKIPPED_RUNS = (RunResult.SKIPPED_COOLDOWN, RunResult.SKIPPED_EXPIRED)
NO_FIGURES = (0,) * 9


def order(definition: FlowDefinition) -> list[Step]:
    """The steps in the order a walk meets them (depth first, each exit in turn), then the rest."""
    by_id = {s.id: s for s in definition.steps}
    seen: list[str] = []
    stack = [definition.start]
    while stack:
        step_id = stack.pop()
        if step_id in seen or step_id not in by_id:
            continue
        seen.append(step_id)
        exits = [t for t in flows.successors(by_id[step_id]) if t is not None]
        stack.extend(reversed(exits))
    rest = [s.id for s in definition.steps if s.id not in seen]
    return [by_id[i] for i in [*seen, *rest]]


def reachable(definition: FlowDefinition, start: str | None) -> set[str]:
    """Every step a run can meet from ``start`` on (including it)."""
    by_id = {s.id: s for s in definition.steps}
    found: set[str] = set()
    stack: list[str | None] = [start] if start else []
    while stack:
        step_id = stack.pop()
        if step_id is None or step_id in found or step_id not in by_id:
            continue
        found.add(step_id)
        stack.extend(flows.successors(by_id[step_id]))
    return found


def rate(part: int, whole: int) -> float:
    """Part of whole as a share between 0 and 1; 0 when nothing reached it."""
    return round(part / whole, 4) if whole > 0 else 0.0


def _excerpt(step: Step) -> str | None:
    if isinstance(step, SendStep | AskStep) and step.text.strip():
        flat = " ".join(step.text.split())
        return flat if len(flat) <= 80 else flat[:79].rstrip() + "..."
    return None


async def _step_figures(
    session: AsyncSession, automation_id: uuid.UUID, since: datetime
) -> dict[str, tuple[int, ...]]:
    row = AutomationRunStep
    runs = select(AutomationRun.id).where(AutomationRun.automation_id == automation_id)
    found = await session.execute(
        select(
            row.step_id,
            func.count(),
            func.count().filter(Message.status.in_(SENT)),
            func.count().filter(Message.status.in_(DELIVERED)),
            func.count().filter(Message.status == "read"),
            func.count().filter(row.status == "failed"),
            func.count().filter(row.kind == "send", func.jsonb_exists(row.detail, "option")),
            func.count().filter(row.kind == "ask", func.jsonb_exists(row.detail, "answer")),
            func.count().filter(row.kind == "ask", func.jsonb_exists(row.detail, "skipped")),
            func.count().filter(row.detail["consent"].astext == "granted"),
        )
        .select_from(row)
        .outerjoin(Message, Message.id == row.message_id)
        .where(row.run_id.in_(runs), row.created_at >= since)
        .group_by(row.step_id)
    )
    return {r[0]: tuple(int(v or 0) for v in r[1:]) for r in found.all()}


async def _legacy_figures(
    session: AsyncSession, automation_id: uuid.UUID, since: datetime
) -> tuple[int, ...]:
    """The "message" step of runs on the message settings: every run that wasn't skipped reached
    it; the run's DM says whether it was sent, delivered and read."""
    run = AutomationRun
    found = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(Message.status.in_(SENT)),
                func.count().filter(Message.status.in_(DELIVERED)),
                func.count().filter(Message.status == "read"),
                func.count().filter(run.result.in_((RunResult.FAILED, RunResult.PARTIAL))),
            )
            .select_from(run)
            .outerjoin(Message, Message.id == run.private_reply_message_id)
            .where(
                run.automation_id == automation_id,
                run.flow_version.is_(None),
                run.created_at >= since,
                run.result.not_in(SKIPPED_RUNS),
            )
        )
    ).one()
    return (*(int(v or 0) for v in found), 0, 0, 0, 0)


async def _clicks(
    session: AsyncSession, automation_id: uuid.UUID, since: datetime
) -> dict[str, tuple[int, int]]:
    found = await session.execute(
        select(LinkClick.step_id, func.count(), func.count(distinct(LinkClick.contact_id)))
        .where(LinkClick.automation_id == automation_id, LinkClick.created_at >= since)
        .group_by(LinkClick.step_id)
    )
    return {step: (int(n), int(people)) for step, n, people in found.all()}


async def _branch(
    session: AsyncSession,
    automation_id: uuid.UUID,
    split_id: str,
    path: int,
    steps: set[str],
    since: datetime,
) -> tuple[int, int, int, int, int, int]:
    """(runs, delivered, read, taps, link clicks, captures) for the runs that took ``path``."""
    split = aliased(AutomationRunStep)
    after = aliased(AutomationRunStep)
    runs = select(AutomationRun.id).where(AutomationRun.automation_id == automation_id)
    took = (
        split.run_id.in_(runs),
        split.step_id == split_id,
        split.created_at >= since,
        cast(split.detail["path"].astext, Integer) == path,
    )
    count = await session.scalar(select(func.count()).select_from(split).where(*took))
    figures = (
        await session.execute(
            select(
                func.count().filter(Message.status.in_(DELIVERED)),
                func.count().filter(Message.status == "read"),
                func.count().filter(
                    after.kind == "send", func.jsonb_exists(after.detail, "option")
                ),
                func.count().filter(after.kind == "ask", func.jsonb_exists(after.detail, "answer")),
            )
            .select_from(split)
            .join(after, after.run_id == split.run_id)
            .outerjoin(Message, Message.id == after.message_id)
            .where(*took, after.step_id.in_(steps))
        )
    ).one()
    clicks = await session.scalar(
        select(func.count())
        .select_from(LinkClick)
        .where(
            LinkClick.run_id.in_(select(split.run_id).where(*took)),
            LinkClick.step_id.in_(steps),
            LinkClick.created_at >= since,
        )
    )
    delivered, read, taps, captures = (int(v or 0) for v in figures)
    return int(count or 0), delivered, read, taps, int(clicks or 0), captures


async def automation_funnel(
    session: AsyncSession,
    automation: Automation,
    *,
    days: Literal[7, 30, 90],
    now: datetime,
) -> AutomationFunnel:
    since = now - timedelta(days=days)
    definition, _, source = await flow_store.current(session, automation)
    names = {
        tag_id: name for tag_id, name in (await session.execute(select(Tag.id, Tag.name))).all()
    }
    figures = await _step_figures(session, automation.id, since)
    if source == "legacy":
        figures["message"] = await _legacy_figures(session, automation.id, since)
    clicks = await _clicks(session, automation.id, since)
    steps: list[FunnelStep] = []
    for step in order(definition):
        reached, sent, delivered, read, failed, taps, captures, skipped, consents = figures.get(
            step.id, NO_FIGURES
        )
        link_clicks, clickers = clicks.get(step.id, (0, 0))
        steps.append(
            FunnelStep(
                step_id=step.id,
                kind=step.type,
                title=flow_preview.title(step, names),
                text=_excerpt(step),
                link_buttons=(
                    sum(1 for b in step.buttons if b.url and not b.profile)
                    if isinstance(step, SendStep)
                    else 0
                ),
                quick_replies=len(step.quick_replies) if isinstance(step, SendStep) else 0,
                reached=reached,
                sent=sent,
                delivered=delivered,
                read=read,
                failed=failed,
                taps=taps,
                link_clicks=link_clicks,
                link_clickers=clickers,
                captures=captures,
                skipped=skipped,
                consents=consents,
            )
        )
    splits: list[SplitResult] = []
    for step in definition.steps:
        if not isinstance(step, RandomizeStep):
            continue
        branches = []
        for index, path in enumerate(step.paths):
            runs, delivered, read, taps, link_clicks, captures = await _branch(
                session, automation.id, step.id, index, reachable(definition, path.next), since
            )
            branches.append(
                SplitBranch(
                    path=index,
                    label=f"Path {chr(65 + index)}",
                    weight=path.weight,
                    runs=runs,
                    delivered=delivered,
                    read=read,
                    taps=taps,
                    link_clicks=link_clicks,
                    captures=captures,
                )
            )
        splits.append(SplitResult(step_id=step.id, branches=branches))
    total = await session.scalar(
        select(func.count())
        .select_from(AutomationRun)
        .where(
            AutomationRun.automation_id == automation.id,
            AutomationRun.created_at >= since,
            AutomationRun.result.not_in(SKIPPED_RUNS),
        )
    )
    return AutomationFunnel(
        days=days,
        runs=int(total or 0),
        links_tracked=automation.track_links,
        steps=steps,
        splits=splits,
    )
