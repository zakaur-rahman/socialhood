"""The action gateway for Ask Social Hood's writes (GR-36; FR-AGT-08, FR-AGT-09, TR-AGT-04;
agent-architecture.html §4, §8). Every write the agent proposes goes through here, and nothing
else saves what the agent asked for. Nothing here commits: the caller does.

The agent only ever *proposes* (``propose``):
1. the action must exist (``agent.actions``) and not be one of the unavailable ones (broadcasts);
2. the principal's role must allow it (``required_role``), as it would by hand;
3. the arguments are checked with the same service-layer validation the screens use
   (``spec.check``), so a proposal that would be refused is refused now, in the model's turn;
4. a pending approval is stored with an idempotency key (the proposing step's key): a retried
   step finds its approval instead of adding another. It expires after ``APPROVAL_TTL``
   (24 hours, recorded in C-107), and the step is marked ``approval``;
5. the audit trail gets ``proposed``.

Only a member's explicit approval executes (``approve``): the approval row is locked, must still
be pending and unexpired, the approver's role must allow the action (403 ``forbidden``), the
arguments (as shown, or edited) are checked again, and the normal service function runs inside a
savepoint in the same transaction that marks the approval ``approved`` and records the outcome.
If the service refuses (a name taken since, a plan limit), nothing is saved, the approval stays
pending with the reason in its ``outcome`` (``ok`` false) so the member can edit or reject it, and
the trail gets ``failed``. A second approval of the same row is 409, so a write never runs twice.

Rejection and expiry are recorded the same way (``reject``, ``expire_due``). The audit trail is
the agent's own table (agent_approval_events), shown in the run trace; GR-19's general
``audit_events`` can mirror it with one call in ``_record``.

Who sees what: owners and admins see every approval, a member those of their own runs. An approval
that isn't visible is 404, and ``can_decide`` tells the web whether to enable Approve.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.agent import actions
from socialhood.agent.actions import ActionEnv, ActionSpec, Outcome, Summary
from socialhood.agent.planner import current_tools
from socialhood.agent.registry import ToolContext
from socialhood.auth.deps import ROLE_RANK, WorkspaceContext
from socialhood.errors import ERROR_CODES, ApiError
from socialhood.models.agent import (
    APPROVAL_TTL,
    AgentApproval,
    AgentApprovalEvent,
    AgentApprovalEventKind,
    AgentStep,
    ApprovalStatus,
    GatewayDecision,
    RiskTier,
)
from socialhood.models.identity import Role
from socialhood.observability.logging import get_logger
from socialhood.repositories import agent as repo
from socialhood.schemas import agent as schemas
from socialhood.schemas.inbox import Actor
from socialhood.services.conversations import decode_cursor, encode_cursor

log = get_logger(__name__)

ROLE_WORDS = "Only owners and admins can approve this, as in the app."
STATUS_WORDS = {
    ApprovalStatus.APPROVED: "This was already approved.",
    ApprovalStatus.REJECTED: "This was already rejected.",
    ApprovalStatus.EXPIRED: "This expired before anyone approved it. Ask again to get it back.",
    ApprovalStatus.SUPERSEDED: "This was replaced by a newer proposal.",
}


def _sees_every(ctx: WorkspaceContext) -> bool:
    """Owners and admins see every approval, as they see every run (FR-AGT-07)."""
    return ROLE_RANK[ctx.role] >= ROLE_RANK[Role.ADMIN]


def _allows(role: Role, spec: ActionSpec[Any]) -> bool:
    return ROLE_RANK[role] >= ROLE_RANK[actions.required_role(spec)]


def _record(
    session: AsyncSession,
    approval_id: uuid.UUID,
    event: AgentApprovalEventKind,
    *,
    actor_user_id: uuid.UUID | None,
    **detail: Any,
) -> None:
    """One line of the audit trail. GR-19: also write the general ``audit_events`` row here."""
    repo.add_approval_event(
        session, approval_id, event.value, actor_user_id=actor_user_id, detail=detail
    )
    log.info(
        "agent_approval",
        approval_id=str(approval_id),
        event=event.value,
        actor=str(actor_user_id) if actor_user_id else None,
    )


# ---------------------------------------------------------------- propose (the agent)


def _env_of(ctx: ToolContext) -> ActionEnv:
    return ActionEnv(
        session=ctx.session,
        workspace_id=ctx.workspace_id,
        user_id=ctx.principal.user_id,
        role=ctx.principal.role,
        now=ctx.now,
    )


async def propose(
    ctx: ToolContext, spec: ActionSpec[Any], args: BaseModel, *, now: datetime | None = None
) -> tuple[AgentApproval, Summary]:
    """File ``args`` as a pending approval for the step that is running (module docstring).
    Writes nothing to the workspace. Returns the approval and what it says in plain words."""
    reason = actions.UNAVAILABLE.get(spec.tool)
    if reason is not None:
        raise ApiError("conflict", reason)
    if ctx.step_id is None or ctx.step_key is None:
        raise RuntimeError("a proposal needs the step that makes it")
    if ROLE_RANK[ctx.principal.role] < ROLE_RANK[actions.required_role(spec)]:
        raise ApiError(
            "forbidden", f"Only owners and admins can add this {spec.noun}, as in the app."
        )
    env = _env_of(ctx)
    valid = spec.args_model.model_validate(args.model_dump(mode="json"))
    await spec.check(env, valid)
    summary = await spec.summarize(env, valid)
    session = ctx.session
    found = await repo.approval_for_key(session, ctx.step_key)
    if found is not None:  # the step ran before: its approval stands
        return found, summary
    created = now or ctx.now
    approval = repo.add_approval(
        session,
        id=uuid.uuid4(),
        run_id=ctx.run_id,
        step_id=ctx.step_id,
        summary=summary.title[: actions.APPROVAL_SUMMARY_CHARS],
        payload=_payload(spec, valid, summary),
        status=ApprovalStatus.PENDING,
        expires_at=created + APPROVAL_TTL,
        idempotency_key=ctx.step_key,
    )
    await session.flush()
    await repo.update_step(session, ctx.step_id, decision=GatewayDecision.APPROVAL.value)
    _record(
        session,
        approval.id,
        AgentApprovalEventKind.PROPOSED,
        actor_user_id=ctx.principal.user_id,
        tool=spec.tool,
        summary=summary.title,
    )
    return approval, summary


# ---------------------------------------------------------------- decide (a member)


async def visible_approval(
    session: AsyncSession,
    ctx: WorkspaceContext,
    approval_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> AgentApproval:
    """The approval, if the caller may see it: one of their own runs', or any for owners and
    admins. Anything else is 404, so another member's approval can't be probed."""
    row = await repo.get_approval(session, approval_id, for_update=for_update)
    if row is None:
        raise ApiError("not_found")
    if not _sees_every(ctx):
        run = await repo.get_run(session, row.run_id)
        if run is None or run.requested_by_user_id != ctx.user.id:
            raise ApiError("not_found")
    return row


def _spec_of(row: AgentApproval) -> ActionSpec[Any]:
    spec = actions.action_for(str((row.payload or {}).get("tool")))
    if spec is None:
        raise ApiError("conflict", "This kind of proposal isn't available any more.")
    return spec


def _payload(spec: ActionSpec[Any], args: BaseModel, summary: Summary) -> dict[str, Any]:
    """What an approval stores: the exact call, and what it said when it was shown (``preview``)."""
    return {
        "tool": spec.tool,
        "args": args.model_dump(mode="json"),
        "preview": {
            "lines": summary.lines,
            "match_count": summary.match_count,
            "step_count": summary.step_count,
        },
    }


def _outcome_json(outcome: Outcome) -> dict[str, Any]:
    return {
        "ok": True,
        "summary": outcome.summary,
        "resource_kind": outcome.resource_kind,
        "resource_id": str(outcome.resource_id),
        "route": outcome.route,
        "error_code": None,
    }


def _failure_json(error: ApiError) -> dict[str, Any]:
    first = error.errors[0].message if error.errors else None
    message = first or error.detail or ERROR_CODES[error.code].title
    return {
        "ok": False,
        "summary": f"Nothing was saved. {message}",
        "resource_kind": None,
        "resource_id": None,
        "route": None,
        "error_code": error.code,
    }


async def approve(
    session: AsyncSession,
    ctx: WorkspaceContext,
    approval_id: uuid.UUID,
    edited: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> AgentApproval:
    """Run the write as proposed, or with ``edited`` arguments (module docstring). 403 for a role
    that can't do it by hand, 409 when it isn't pending, 422 for edited arguments that don't
    fit. The caller commits, then returns the approval; ``outcome.ok`` false means the service
    refused it and the approval is still pending."""
    now = now or datetime.now(UTC)
    row = await visible_approval(session, ctx, approval_id, for_update=True)
    spec = _spec_of(row)
    if not _allows(ctx.role, spec):
        raise ApiError("forbidden", ROLE_WORDS)
    if row.status != ApprovalStatus.PENDING:
        raise ApiError("conflict", STATUS_WORDS.get(ApprovalStatus(row.status), "Already decided."))
    if row.expires_at <= now:  # the route saves expiries before it decides (expire_due)
        raise ApiError("conflict", STATUS_WORDS[ApprovalStatus.EXPIRED])
    raw = edited if edited is not None else (row.payload or {}).get("args", {})
    try:
        args = spec.args_model.model_validate(raw)
    except ValidationError as error:
        raise ApiError("validation_error", "Those changes don't fit this proposal.") from error

    env = ActionEnv(
        session=session, workspace_id=ctx.workspace_id, user_id=ctx.user.id, role=ctx.role, now=now
    )
    run_id = row.run_id
    try:
        async with session.begin_nested():  # a refusal leaves no half-saved rows
            await spec.check(env, args)
            outcome = await spec.execute(env, args)
    except ApiError as error:
        row.outcome = _failure_json(error)
        _record(
            session,
            row.id,
            AgentApprovalEventKind.FAILED,
            actor_user_id=ctx.user.id,
            error_code=error.code,
            summary=row.outcome["summary"],
        )
        log.info(
            "agent_approval_refused", run_id=str(run_id), tool=spec.tool, http_status=error.status
        )
        return row

    summary = await spec.summarize(env, args)
    row.payload = _payload(spec, args, summary)
    row.summary = summary.title[: actions.APPROVAL_SUMMARY_CHARS]
    row.status = ApprovalStatus.APPROVED
    row.decided_by_user_id = ctx.user.id
    row.decided_at = now
    row.executed_at = now
    row.outcome = _outcome_json(outcome)
    _record(
        session,
        row.id,
        AgentApprovalEventKind.APPROVED,
        actor_user_id=ctx.user.id,
        edited=edited is not None,
    )
    _record(
        session,
        row.id,
        AgentApprovalEventKind.EXECUTED,
        actor_user_id=ctx.user.id,
        resource_kind=outcome.resource_kind,
        resource_id=str(outcome.resource_id),
        summary=outcome.summary,
    )
    await session.flush()
    return row


async def reject(
    session: AsyncSession,
    ctx: WorkspaceContext,
    approval_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> AgentApproval:
    """Say no: nothing is saved. Anyone who can see it may reject it (rejecting changes nothing);
    409 when it isn't pending."""
    now = now or datetime.now(UTC)
    row = await visible_approval(session, ctx, approval_id, for_update=True)
    if row.status != ApprovalStatus.PENDING:
        raise ApiError("conflict", STATUS_WORDS.get(ApprovalStatus(row.status), "Already decided."))
    if row.expires_at <= now:
        raise ApiError("conflict", STATUS_WORDS[ApprovalStatus.EXPIRED])
    row.status = ApprovalStatus.REJECTED
    row.decided_by_user_id = ctx.user.id
    row.decided_at = now
    _record(session, row.id, AgentApprovalEventKind.REJECTED, actor_user_id=ctx.user.id)
    await session.flush()
    return row


async def expire_due(session: AsyncSession, now: datetime) -> int:
    """Pending approvals past their time become ``expired`` (a record for each); the current
    workspace's. Run before a list or a decision, and by the 15-minute sweep (jobs/tasks/agent)."""
    due = await repo.due_approvals(session, now)
    for row in due:
        row.status = ApprovalStatus.EXPIRED
        row.decided_at = now
        _record(session, row.id, AgentApprovalEventKind.EXPIRED, actor_user_id=None)
    if due:
        await session.flush()
    return len(due)


# ---------------------------------------------------------------- reading


def _actor(user_id: uuid.UUID | None, names: dict[uuid.UUID, str | None]) -> Actor | None:
    return Actor(id=user_id, name=names.get(user_id)) if user_id is not None else None


async def approvals_out(
    session: AsyncSession, role: Role | None, rows: list[AgentApproval]
) -> list[schemas.AgentApproval]:
    if not rows:
        return []
    runs = {
        r.id: r for r in [await repo.get_run(session, i) for i in {a.run_id for a in rows}] if r
    }
    steps = {s.id: s for s in await _steps(session, rows)}
    events = await repo.approval_events(session, [a.id for a in rows])
    user_ids = [r.requested_by_user_id for r in runs.values()]
    user_ids += [a.decided_by_user_id for a in rows]
    user_ids += [e.actor_user_id for evs in events.values() for e in evs]
    names = await repo.user_names(session, user_ids)
    tools = current_tools()
    out = []
    for a in rows:
        run, step = runs.get(a.run_id), steps.get(a.step_id)
        spec = actions.action_for(str((a.payload or {}).get("tool")))
        tool = str((a.payload or {}).get("tool"))
        preview = (a.payload or {}).get("preview") or {}
        registered = tools.get(tool)
        out.append(
            schemas.AgentApproval(
                id=a.id,
                run_id=a.run_id,
                step_id=a.step_id,
                request=run.request if run else "",
                tool=tool,
                label=registered.label if registered else tool.replace("_", " ").capitalize(),
                tier=RiskTier(step.tier).value if step and step.tier else RiskTier.DRAFT.value,
                summary=a.summary,
                payload=a.payload,
                lines=list(preview.get("lines") or []),
                match_count=preview.get("match_count"),
                step_count=preview.get("step_count"),
                status=a.status,
                expires_at=a.expires_at,
                can_decide=(
                    a.status == ApprovalStatus.PENDING
                    and spec is not None
                    and role is not None
                    and _allows(role, spec)
                ),
                requested_by=_actor(run.requested_by_user_id if run else None, names),
                decided_by=_actor(a.decided_by_user_id, names),
                decided_at=a.decided_at,
                outcome=schemas.ApprovalOutcome.model_validate(a.outcome) if a.outcome else None,
                events=[_event_out(e, names) for e in events.get(a.id, [])],
                created_at=a.created_at,
            )
        )
    return out


def _event_out(
    row: AgentApprovalEvent, names: dict[uuid.UUID, str | None]
) -> schemas.ApprovalEvent:
    return schemas.ApprovalEvent(
        id=row.id,
        event=row.event,
        actor=_actor(row.actor_user_id, names),
        detail=row.detail or {},
        created_at=row.created_at,
    )


async def _steps(session: AsyncSession, rows: list[AgentApproval]) -> list[AgentStep]:
    ids = {a.step_id for a in rows}
    return list((await session.scalars(select(AgentStep).where(AgentStep.id.in_(ids)))).all())


async def list_approvals(
    session: AsyncSession,
    ctx: WorkspaceContext,
    *,
    status: str,
    run_id: uuid.UUID | None,
    cursor: str | None,
    limit: int,
) -> schemas.AgentApprovalList:
    """Soonest to expire first. Owners and admins see every approval, a member those of their own
    runs."""
    rows = await repo.list_approvals(
        session,
        requested_by=None if _sees_every(ctx) else ctx.user.id,
        status=None if status == "all" else status,
        run_id=run_id,
        after=decode_cursor(cursor) if cursor else None,
        limit=limit,
    )
    page = rows[:limit]
    return schemas.AgentApprovalList(
        items=await approvals_out(session, ctx.role, page),
        next_cursor=(
            encode_cursor(page[-1].expires_at, page[-1].id) if len(rows) > limit else None
        ),
    )
