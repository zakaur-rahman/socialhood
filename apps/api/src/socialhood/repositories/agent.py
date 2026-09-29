"""Ask Social Hood's runs, steps and policy (TA.1, TA.2, TA.6; FR-AGT-01, FR-AGT-07, TR-AGT-07,
TR-AGT-08).

Tenant-scoped like every repository: reads go through the ORM's workspace filter and writes
through ``scoped_update`` (TR-TEN-04). Status changes are conditional (``WHERE status IN …``), so
a member's cancel and the job never overwrite each other: whoever changes an unfinished run first
wins, and the other sees 0 rows. ``stuck_runs`` looks across workspaces for the sweeper: jobs/
calls it inside a ``tenant_bypass_scope`` (TR-TEN-04).

A run's credits and tokens are the sums of its ``ai_usage_events`` (ref_type ``agent_run``): its
model turns (agent_turn) and any AI-calling tool that meters against the run.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import DateTime, Text, Uuid, exists, func, literal, select, tuple_
from sqlalchemy.dialects.postgresql import ARRAY, aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.agent import (
    FINAL_RUN_STATUSES,
    AgentPolicy,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    RiskTier,
    StepStatus,
)
from socialhood.models.billing import AiFeature, AiUsageEvent
from socialhood.models.identity import User, WorkspaceMember
from socialhood.repositories.base import scoped_update

REF_TYPE = "agent_run"  # ai_usage_events.ref_type of a run's AI calls
UNFINISHED = tuple(s.value for s in AgentRunStatus if s not in FINAL_RUN_STATUSES)
# What the sweeper resumes: a run waiting for an approval (R2) waits for a person, not a job.
IN_FLIGHT = (AgentRunStatus.QUEUED, AgentRunStatus.PLANNING, AgentRunStatus.RUNNING)
_TIMESTAMP = DateTime(timezone=True)
_UUID = Uuid()


# ---------------------------------------------------------------- runs


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> AgentRun | None:
    return await session.scalar(select(AgentRun).where(AgentRun.id == run_id))


async def run_status(session: AsyncSession, run_id: uuid.UUID) -> str | None:
    """The run's stored status, read fresh (the job checks it before every step and turn)."""
    return await session.scalar(select(AgentRun.status).where(AgentRun.id == run_id))


async def owns_thread(session: AsyncSession, thread_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Whether ``thread_id`` is one of the user's threads in this workspace."""
    found = await session.scalar(
        select(
            exists().where(
                AgentRun.thread_id == thread_id, AgentRun.requested_by_user_id == user_id
            )
        )
    )
    return bool(found)


async def list_runs(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    thread_id: uuid.UUID | None,
    before: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[AgentRun]:
    """Newest first, one more than ``limit`` (the caller pages); ``user_id`` keeps one member's
    runs, ``thread_id`` one thread's."""
    statement = select(AgentRun).order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
    if user_id is not None:
        statement = statement.where(AgentRun.requested_by_user_id == user_id)
    if thread_id is not None:
        statement = statement.where(AgentRun.thread_id == thread_id)
    if before is not None:
        statement = statement.where(
            tuple_(AgentRun.created_at, AgentRun.id)
            < tuple_(literal(before[0], _TIMESTAMP), literal(before[1], _UUID))
        )
    return list((await session.scalars(statement.limit(limit + 1))).all())


async def thread_history(session: AsyncSession, run: AgentRun, *, limit: int) -> list[AgentRun]:
    """The thread's runs before ``run``, oldest first, at most ``limit`` (the latest ones)."""
    rows = await session.scalars(
        select(AgentRun)
        .where(
            AgentRun.thread_id == run.thread_id,
            AgentRun.id != run.id,
            AgentRun.created_at <= run.created_at,
        )
        .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
        .limit(limit)
    )
    return list(reversed(rows.all()))


class ThreadRow(NamedTuple):
    thread_id: uuid.UUID
    run_count: int
    created_at: datetime
    last_run_at: datetime
    first_request: str
    last_status: str


async def list_threads(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    before: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[ThreadRow]:
    """The user's threads, most recent activity first, one more than ``limit``."""
    last_at = func.max(AgentRun.created_at)
    statement = (
        select(
            AgentRun.thread_id,
            func.count(),
            func.min(AgentRun.created_at),
            last_at,
            func.array_agg(
                aggregate_order_by(AgentRun.request, AgentRun.created_at.asc()), type_=ARRAY(Text)
            )[1],
            func.array_agg(
                aggregate_order_by(AgentRun.status, AgentRun.created_at.desc()), type_=ARRAY(Text)
            )[1],
        )
        .where(AgentRun.requested_by_user_id == user_id)
        .group_by(AgentRun.thread_id)
        .order_by(last_at.desc(), AgentRun.thread_id.desc())
        .limit(limit + 1)
    )
    if before is not None:
        statement = statement.having(
            tuple_(last_at, AgentRun.thread_id)
            < tuple_(literal(before[0], _TIMESTAMP), literal(before[1], _UUID))
        )
    return [ThreadRow(*row) for row in (await session.execute(statement)).all()]


async def user_names(
    session: AsyncSession, user_ids: Collection[uuid.UUID | None]
) -> dict[uuid.UUID, str | None]:
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return {}
    rows = await session.execute(select(User.id, User.name).where(User.id.in_(ids)))
    return {row[0]: row[1] for row in rows.all()}


async def member_role(session: AsyncSession, user_id: uuid.UUID) -> str | None:
    """The user's role in the current workspace, or None when they aren't a member."""
    return await session.scalar(
        select(WorkspaceMember.role).where(WorkspaceMember.user_id == user_id)
    )


async def set_status(
    session: AsyncSession,
    run_id: uuid.UUID,
    status: str,
    *,
    unless_final: bool = True,
    **values: Any,
) -> bool:
    """Move an unfinished run to ``status`` with ``values``; False when it is already final (a
    member cancelled it, or another job finished it)."""
    statement = scoped_update(AgentRun, id=run_id).values(status=status, **values)
    if unless_final:
        statement = statement.where(AgentRun.status.in_(UNFINISHED))
    result = await session.execute(statement)
    return bool(getattr(result, "rowcount", 0))


async def touch(session: AsyncSession, run_id: uuid.UUID, **values: Any) -> None:
    """Store ``values`` on the run whatever its status (usage, model); updated_at moves too."""
    await session.execute(scoped_update(AgentRun, id=run_id).values(**values))


class RunUsage(NamedTuple):
    credits: int
    input_tokens: int
    output_tokens: int
    turns: int  # agent_turn calls that were charged (failed calls are refunded: 0 credits)


async def run_usage(session: AsyncSession, run_id: uuid.UUID) -> RunUsage:
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(AiUsageEvent.credits), 0),
                func.coalesce(func.sum(AiUsageEvent.input_tokens), 0),
                func.coalesce(func.sum(AiUsageEvent.output_tokens), 0),
                func.count().filter(
                    AiUsageEvent.feature == AiFeature.AGENT_TURN, AiUsageEvent.credits > 0
                ),
            ).where(AiUsageEvent.ref_type == REF_TYPE, AiUsageEvent.ref_id == run_id)
        )
    ).one()
    return RunUsage(int(row[0]), int(row[1]), int(row[2]), int(row[3]))


async def store_usage(session: AsyncSession, run_id: uuid.UUID) -> RunUsage:
    """Copy the run's usage sums onto the run (credits, input and output tokens)."""
    usage = await run_usage(session, run_id)
    await touch(
        session,
        run_id,
        credits=usage.credits,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )
    return usage


# ---------------------------------------------------------------- steps


async def steps_of(session: AsyncSession, run_id: uuid.UUID) -> list[AgentStep]:
    rows = await session.scalars(
        select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.ordinal)
    )
    return list(rows.all())


async def step_counts(
    session: AsyncSession, run_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not run_ids:
        return {}
    rows = await session.execute(
        select(AgentStep.run_id, func.count())
        .where(AgentStep.run_id.in_(run_ids))
        .group_by(AgentStep.run_id)
    )
    return {row[0]: int(row[1]) for row in rows.all()}


async def draft_results(
    session: AsyncSession, run_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    """Each run's succeeded draft steps' results, in step order (their action cards)."""
    if not run_ids:
        return {}
    rows = await session.execute(
        select(AgentStep.run_id, AgentStep.result)
        .where(
            AgentStep.run_id.in_(run_ids),
            AgentStep.tier == RiskTier.DRAFT,
            AgentStep.status == StepStatus.SUCCEEDED,
            AgentStep.result.is_not(None),
        )
        .order_by(AgentStep.run_id, AgentStep.ordinal)
    )
    found: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for run_id, result in rows.all():
        found.setdefault(run_id, []).append(result)
    return found


def add_step(session: AsyncSession, run_id: uuid.UUID, ordinal: int, **values: Any) -> AgentStep:
    """A new step (flushed by the caller's commit); its idempotency key is ``{run_id}:{ordinal}``
    (TR-AGT-07)."""
    step = AgentStep(
        run_id=run_id, ordinal=ordinal, idempotency_key=f"{run_id}:{ordinal}", **values
    )
    session.add(step)
    return step


async def update_step(session: AsyncSession, step_id: uuid.UUID, **values: Any) -> None:
    await session.execute(scoped_update(AgentStep, id=step_id).values(**values))


async def fail_running_steps(
    session: AsyncSession, run_id: uuid.UUID, *, code: str, message: str, at: datetime
) -> int:
    """Steps a crash, a cancel or the wall-time cap left ``running`` become failed."""
    result = await session.execute(
        scoped_update(AgentStep, run_id=run_id, status=StepStatus.RUNNING).values(
            status=StepStatus.FAILED, error_code=code, error_message=message, completed_at=at
        )
    )
    return int(getattr(result, "rowcount", 0))


# ---------------------------------------------------------------- policy


async def policy(session: AsyncSession) -> AgentPolicy | None:
    return await session.scalar(select(AgentPolicy))


def add_policy(session: AsyncSession) -> AgentPolicy:
    row = AgentPolicy(workspace_id=require_workspace())
    session.add(row)
    return row


# ---------------------------------------------------------------- across workspaces (jobs/)


async def stuck_runs(
    session: AsyncSession, idle_before: datetime, limit: int
) -> Sequence[AgentRun]:
    """Unfinished runs with no progress since ``idle_before``: neither the run nor any of its
    steps changed (every step write and model turn moves one of them). Oldest first."""
    recent_step = exists().where(
        AgentStep.run_id == AgentRun.id, AgentStep.updated_at >= idle_before
    )
    rows = await session.scalars(
        select(AgentRun)
        .where(
            AgentRun.status.in_(IN_FLIGHT),
            AgentRun.updated_at < idle_before,
            ~recent_step,
        )
        .order_by(AgentRun.updated_at)
        .limit(limit)
    )
    return rows.all()
