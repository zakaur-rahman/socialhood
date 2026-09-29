"""Ask Social Hood's runs, threads and policy for the API (TA.1; FR-AGT-01, FR-AGT-03,
FR-AGT-07, FR-AGT-10, TR-AGT-08; agent-architecture.html §11).

Runs belong to the member who asked. A member sees and cancels their own runs; owners and admins
see and cancel every run in the run history (FR-AGT-07). Threads are personal for everyone: the
Ask panel lists the caller's own threads, a run can only continue one of the caller's threads,
and ``thread_id`` on the run history keeps the caller's runs only. Anything else is 404
not_found, never 403, so another member's run can't be probed (TR-API-03).

A run's action cards come from its succeeded draft steps, in step order (FR-AGT-03); its steps
show the tool in plain words (agent/progress.py).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.agent import progress
from socialhood.agent.planner import current_tools
from socialhood.ai.metering import quota
from socialhood.auth.deps import ROLE_RANK, WorkspaceContext
from socialhood.billing.plans import CREDIT_COSTS
from socialhood.errors import ApiError
from socialhood.models.agent import (
    DEFAULT_LIMITS,
    DEFAULT_PERMISSIONS,
    AgentPolicy,
    AgentRun,
    AgentRunSource,
    AgentRunStatus,
    AgentStep,
)
from socialhood.models.billing import AiFeature
from socialhood.models.identity import Role
from socialhood.repositories import agent as repo
from socialhood.schemas import agent as schemas
from socialhood.schemas.inbox import Actor
from socialhood.services.conversations import decode_cursor, encode_cursor

THREAD_TITLE_CHARS = 80
NO_CREDITS = "Your workspace has used its AI credits for this period."


def sees_every_run(ctx: WorkspaceContext) -> bool:
    """Owners and admins open any run (FR-AGT-07)."""
    return ROLE_RANK[ctx.role] >= ROLE_RANK[Role.ADMIN]


# ---------------------------------------------------------------- projections


def _cards(results: list[dict[str, Any]]) -> list[Any]:
    return [r["action_card"] for r in results if isinstance(r.get("action_card"), dict)]


def run_out(
    row: AgentRun,
    *,
    names: dict[uuid.UUID, str | None],
    drafts: dict[uuid.UUID, list[dict[str, Any]]],
) -> schemas.AgentRun:
    requester = row.requested_by_user_id
    return schemas.AgentRun.model_validate(
        {
            "id": row.id,
            "thread_id": row.thread_id,
            "request": row.request,
            "source": row.source,
            "mode": row.mode,
            "status": row.status,
            "requested_by": (
                Actor(id=requester, name=names.get(requester)) if requester is not None else None
            ),
            "answer": row.answer,
            "answer_refs": row.answer_refs or [],
            "action_cards": _cards(drafts.get(row.id, [])),
            "credits": row.credits or 0,
            "error": progress.error_info(row.error_code, row.error_message),
            "created_at": row.created_at,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
        }
    )


def step_out(step: AgentStep) -> schemas.AgentStep:
    return schemas.AgentStep.model_validate(
        {
            "id": step.id,
            "ordinal": step.ordinal,
            "kind": step.kind,
            "tool": step.tool,
            "label": progress.step_label(current_tools(), step.kind, step.tool),
            "tier": step.tier,
            "status": step.status,
            "args": step.args or {},
            "summary": progress.step_summary(step.result),
            "result": step.result,
            "decision": step.decision,
            "verification": step.verification,
            "attempts": step.attempts or 0,
            "latency_ms": step.latency_ms or 0,
            "error": progress.error_info(step.error_code, step.error_message),
            "started_at": step.started_at,
            "completed_at": step.completed_at,
        }
    )


async def runs_out(session: AsyncSession, rows: list[AgentRun]) -> list[schemas.AgentRun]:
    names = await repo.user_names(session, [r.requested_by_user_id for r in rows])
    drafts = await repo.draft_results(session, [r.id for r in rows])
    return [run_out(r, names=names, drafts=drafts) for r in rows]


async def detail_out(session: AsyncSession, row: AgentRun) -> schemas.AgentRunDetail:
    [base] = await runs_out(session, [row])
    steps = await repo.steps_of(session, row.id)
    return schemas.AgentRunDetail.model_validate(
        {
            **base.model_dump(),
            "steps": [step_out(s) for s in steps],
            "plan": row.plan,
            "model": row.model,
            "prompt_version": row.prompt_version,
        }
    )


# ---------------------------------------------------------------- runs


async def visible_run(session: AsyncSession, ctx: WorkspaceContext, run_id: uuid.UUID) -> AgentRun:
    """The run, if the caller may open it: their own, or any for owners and admins."""
    row = await repo.get_run(session, run_id)
    if row is None or not (sees_every_run(ctx) or row.requested_by_user_id == ctx.user.id):
        raise ApiError("not_found")
    return row


async def create(
    session: AsyncSession, ctx: WorkspaceContext, body: schemas.AgentRunCreate
) -> AgentRun:
    """A queued run (agent.run.updated queued on the session). 404 for a thread that isn't the
    caller's; 402 quota_exceeded without a credit left. The caller commits, then enqueues."""
    if body.thread_id is not None and not await repo.owns_thread(
        session, body.thread_id, ctx.user.id
    ):
        raise ApiError("not_found")
    credits = await quota(session, now=datetime.now(UTC))
    if not credits.allows(CREDIT_COSTS[AiFeature.AGENT_TURN]):
        raise ApiError("quota_exceeded", NO_CREDITS)
    policy = await load_policy(session)
    run_id = uuid.uuid4()
    row = AgentRun(
        id=run_id,
        thread_id=body.thread_id or run_id,
        requested_by_user_id=ctx.user.id,
        source=AgentRunSource.ASK,
        request=body.request,
        mode=policy.mode,
        status=AgentRunStatus.QUEUED,
        answer_refs=[],
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    progress.queue_run(session, row, 0)
    return row


async def list_runs(
    session: AsyncSession,
    ctx: WorkspaceContext,
    *,
    thread_id: uuid.UUID | None,
    cursor: str | None,
    limit: int,
) -> schemas.AgentRunList:
    """Newest first. A thread is always the caller's own; without one, owners and admins see
    every run."""
    mine_only = thread_id is not None or not sees_every_run(ctx)
    rows = await repo.list_runs(
        session,
        user_id=ctx.user.id if mine_only else None,
        thread_id=thread_id,
        before=decode_cursor(cursor) if cursor else None,
        limit=limit,
    )
    page = rows[:limit]
    return schemas.AgentRunList(
        items=await runs_out(session, page),
        next_cursor=(
            encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        ),
    )


async def cancel(session: AsyncSession, ctx: WorkspaceContext, run_id: uuid.UUID) -> AgentRun:
    """Stop at the next step (§9): an unfinished run becomes cancelled now (events queued); a
    finished one is returned as it is."""
    row = await visible_run(session, ctx, run_id)
    now = datetime.now(UTC)
    cancelled = await repo.set_status(session, row.id, AgentRunStatus.CANCELLED, completed_at=now)
    await session.refresh(row)  # as stored now, whoever finished it
    if cancelled:
        counts = await repo.step_counts(session, [row.id])
        progress.queue_run(session, row, counts.get(row.id, 0))
    return row


async def list_threads(
    session: AsyncSession, ctx: WorkspaceContext, *, cursor: str | None, limit: int
) -> schemas.AgentThreadList:
    rows = await repo.list_threads(
        session,
        user_id=ctx.user.id,
        before=decode_cursor(cursor) if cursor else None,
        limit=limit,
    )
    page = rows[:limit]
    items = [
        schemas.AgentThread.model_validate(
            {
                "id": r.thread_id,
                "title": _title(r.first_request),
                "run_count": r.run_count,
                "last_status": r.last_status,
                "created_at": r.created_at,
                "last_run_at": r.last_run_at,
            }
        )
        for r in page
    ]
    return schemas.AgentThreadList(
        items=items,
        next_cursor=(
            encode_cursor(page[-1].last_run_at, page[-1].thread_id) if len(rows) > limit else None
        ),
    )


def _title(request: str) -> str:
    title = " ".join(request.split())
    if len(title) <= THREAD_TITLE_CHARS:
        return title
    return title[: THREAD_TITLE_CHARS - 1].rstrip() + "…"


# ---------------------------------------------------------------- policy (FR-AGT-10)


async def load_policy(session: AsyncSession) -> AgentPolicy:
    """The workspace's policy; created with the defaults when a workspace has none yet."""
    row = await repo.policy(session)
    if row is None:
        row = repo.add_policy(session)
        await session.flush()
        await session.refresh(row)
    return row


async def policy_out(session: AsyncSession, row: AgentPolicy) -> schemas.AgentPolicy:
    names = await repo.user_names(session, [row.updated_by_user_id])
    editor = row.updated_by_user_id
    return schemas.AgentPolicy.model_validate(
        {
            "mode": row.mode,
            "permissions": {**DEFAULT_PERMISSIONS, **(row.permissions or {})},
            "limits": {**DEFAULT_LIMITS, **(row.limits or {})},
            "updated_by": Actor(id=editor, name=names.get(editor)) if editor else None,
            "updated_at": row.updated_at,
        }
    )
