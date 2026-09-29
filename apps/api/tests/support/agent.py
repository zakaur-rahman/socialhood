"""PA rows for tests: agent runs with their steps, approvals and the agent policy (written through
the ORM in the workspace's scope, committed, returned as ids). Nothing here calls a model."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.agent import APPROVAL_TTL, AgentApproval, AgentPolicy, AgentRun, AgentStep


def _uuid(value: uuid.UUID | str) -> uuid.UUID:
    return uuid.UUID(str(value))


@dataclass(frozen=True)
class MadeRun:
    id: uuid.UUID
    thread_id: uuid.UUID
    step_ids: tuple[uuid.UUID, ...]  # in ordinal order


# A finished R1 answer: one read tool call, then the report.
DEFAULT_STEPS: tuple[Mapping[str, Any], ...] = (
    {
        "kind": "tool",
        "tool": "get_latest_post",
        "tier": "read",
        "args": {"account": None},
        "result": {
            "summary": "Found your latest post, a reel published 26 hours ago",
            "refs": [],
            "caveats": [],
        },
    },
    {"kind": "report", "args": {}, "result": {"summary": "Wrote the answer"}},
)


async def make_agent_run(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    requested_by_user_id: uuid.UUID | str | None = None,
    thread_id: uuid.UUID | str | None = None,
    steps: Sequence[Mapping[str, Any]] = DEFAULT_STEPS,
    **values: Any,
) -> MadeRun:
    """A run with its steps (ordinals 0, 1, … in the order given).

    By default a succeeded read-only answer in a new thread (thread id = run id), with the steps
    in ``DEFAULT_STEPS``. Each step takes AgentStep columns; missing ones default to a succeeded
    step with one attempt. Other AgentRun columns go in ``values``.
    """
    wid = _uuid(workspace_id)
    now = datetime.now(UTC)
    run_id = uuid.uuid4()
    defaults: dict[str, Any] = {
        "request": "How did my latest post do?",
        "mode": "read_only",
        "status": "succeeded",
        "answer": "Your latest reel reached **4,120** people at 24 hours [1].",
        "answer_refs": [{"kind": "post", "id": str(uuid.uuid4()), "label": "Reel of 26 Sep"}],
        "model": "fake-model",
        "prompt_version": "agent.v1",
        "credits": 2,
        "input_tokens": 1200,
        "output_tokens": 180,
        "started_at": now - timedelta(seconds=4),
        "completed_at": now,
    }
    with workspace_scope(wid):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            run = AgentRun(
                id=run_id,
                thread_id=_uuid(thread_id) if thread_id is not None else run_id,
                requested_by_user_id=(
                    _uuid(requested_by_user_id) if requested_by_user_id is not None else None
                ),
                **{**defaults, **values},
            )
            session.add(run)
            await session.flush()
            rows = []
            for ordinal, step in enumerate(steps):
                step_defaults: dict[str, Any] = {
                    "kind": "tool",
                    "args": {},
                    "status": "succeeded",
                    "attempts": 1,
                    "latency_ms": 40,
                    "started_at": now - timedelta(seconds=3),
                    "completed_at": now - timedelta(seconds=2),
                }
                row = AgentStep(
                    run_id=run.id,
                    ordinal=ordinal,
                    idempotency_key=f"{run.id}:{ordinal}",
                    **{**step_defaults, **step},
                )
                session.add(row)
                rows.append(row)
            await session.flush()
            made = MadeRun(run.id, run.thread_id, tuple(row.id for row in rows))
            await session.commit()
            return made


async def make_agent_approval(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    run_id: uuid.UUID | str,
    step_id: uuid.UUID | str,
    **values: Any,
) -> uuid.UUID:
    """An R2 approval for a step, pending and expiring 24 hours from now unless ``values`` say
    otherwise."""
    defaults: dict[str, Any] = {
        "summary": "Reply “Thank you!” to 12 positive comments on your latest post",
        "payload": {"tool": "reply_to_comments", "args": {"text": "Thank you!", "max": 12}},
        "status": "pending",
        "expires_at": datetime.now(UTC) + APPROVAL_TTL,
    }
    with workspace_scope(_uuid(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = AgentApproval(
                run_id=_uuid(run_id), step_id=_uuid(step_id), **{**defaults, **values}
            )
            session.add(row)
            await session.commit()
            return row.id


async def make_agent_policy(
    engine: AsyncEngine, *, workspace_id: uuid.UUID | str, **values: Any
) -> uuid.UUID:
    """The workspace's policy: the one it has, updated with ``values``, or a new one (bare
    workspaces from make_workspace have none; provisioning creates it)."""
    with workspace_scope(_uuid(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = (await session.scalars(select(AgentPolicy))).one_or_none()
            if row is None:
                row = AgentPolicy(**values)
                session.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            await session.commit()
            return row.id
