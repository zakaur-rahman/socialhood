"""PA foundation (§5.5 Agent; FR-AGT-07, FR-AGT-09, FR-AGT-10, TR-AGT-07, TR-AGT-08): the keys,
checks and cascades of agent_runs, agent_steps, agent_approvals and agent_policies, and the
agent_turn credit feature, through the factories every PA test uses."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.models.agent import DEFAULT_LIMITS, DEFAULT_PERMISSIONS
from tests.support.agent import make_agent_approval, make_agent_policy, make_agent_run
from tests.support.inbox import make_workspace


@pytest.fixture
async def wid(engine: AsyncEngine, clean_db: None) -> uuid.UUID:
    return await make_workspace(engine)


async def _scalar(engine: AsyncEngine, sql: str, **params: Any) -> Any:
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar_one()


async def _execute(engine: AsyncEngine, sql: str, **params: Any) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), params)


async def _member(engine: AsyncEngine) -> uuid.UUID:
    """A user who can be deleted (the workspace's owner can't)."""
    suffix = uuid.uuid4().hex[:10]
    async with engine.begin() as conn:
        user: uuid.UUID = (
            await conn.execute(
                text("INSERT INTO users (clerk_user_id, email) VALUES (:c, :e) RETURNING id"),
                {"c": f"user_{suffix}", "e": f"{suffix}@example.com"},
            )
        ).scalar_one()
    return user


async def test_a_run_is_stored_with_its_steps_in_order(engine: AsyncEngine, wid: uuid.UUID) -> None:
    member = await _member(engine)
    run = await make_agent_run(engine, workspace_id=wid, requested_by_user_id=member)
    assert run.thread_id == run.id  # a new thread's id is its first run's id
    rows = await _scalar(
        engine,
        "SELECT array_agg(kind || ':' || coalesce(tool, '-') || ':' || idempotency_key"
        " ORDER BY ordinal) FROM agent_steps WHERE run_id = :r",
        r=run.id,
    )
    assert rows == [f"tool:get_latest_post:{run.id}:0", f"report:-:{run.id}:1"]
    assert await _scalar(
        engine, "SELECT answer_refs -> 0 ->> 'kind' FROM agent_runs WHERE id = :r", r=run.id
    ) == ("post")

    follow_up = await make_agent_run(
        engine, workspace_id=wid, thread_id=run.thread_id, request="And the one before?"
    )
    assert follow_up.thread_id == run.thread_id

    with pytest.raises(IntegrityError, match="uq_agent_steps_run_id_ordinal"):
        await _execute(
            engine,
            "INSERT INTO agent_steps (workspace_id, run_id, ordinal, kind, args, idempotency_key)"
            " VALUES (:w, :r, 1, 'report', '{}', 'k')",
            w=wid,
            r=run.id,
        )

    # Deleting the member keeps their runs (history); deleting the run takes its steps.
    await _execute(engine, "DELETE FROM users WHERE id = :u", u=member)
    assert (
        await _scalar(engine, "SELECT requested_by_user_id FROM agent_runs WHERE id = :r", r=run.id)
        is None
    )
    await _execute(engine, "DELETE FROM agent_runs WHERE id = :r", r=run.id)
    assert (
        await _scalar(engine, "SELECT count(*) FROM agent_steps WHERE run_id = :r", r=run.id) == 0
    )


@pytest.mark.parametrize(
    ("values", "check"),
    [
        ({"status": "done"}, "status"),
        ({"mode": "auto"}, "mode"),
        ({"source": "cron"}, "source"),
        ({"request": ""}, "request_length"),
        ({"request": "x" * 2001}, "request_length"),
        ({"answer_refs": {"kind": "post"}}, "answer_refs"),
    ],
)
async def test_run_checks(
    engine: AsyncEngine, wid: uuid.UUID, values: dict[str, Any], check: str
) -> None:
    with pytest.raises(IntegrityError, match=f"ck_agent_runs_{check}"):
        await make_agent_run(engine, workspace_id=wid, steps=[], **values)


@pytest.mark.parametrize(
    ("step", "check"),
    [
        ({"kind": "thought"}, "kind"),
        ({"tool": "get_posts", "tier": "risky"}, "tier"),
        ({"tool": "get_posts", "tier": "read", "status": "done"}, "status"),
        ({"tool": "get_posts", "tier": "read", "decision": "maybe"}, "decision"),
        ({"tool": "get_posts", "tier": "read", "decision": "refuse:"}, "decision"),
        ({"tool": None, "tier": "read"}, "tool"),
        ({"tool": "get_posts", "tier": None}, "tool"),
        ({"tool": "get_posts", "tier": "read", "attempts": -1}, "attempts"),
    ],
)
async def test_step_checks(
    engine: AsyncEngine, wid: uuid.UUID, step: dict[str, Any], check: str
) -> None:
    with pytest.raises(IntegrityError, match=f"ck_agent_steps_{check}"):
        await make_agent_run(engine, workspace_id=wid, steps=[step])


async def test_gateway_decisions_are_stored_as_words(engine: AsyncEngine, wid: uuid.UUID) -> None:
    steps = [
        {"tool": "send_message", "tier": "high", "decision": decision, "status": "blocked"}
        for decision in ("execute", "approval", "refuse:agent_permission_off")
    ]
    run = await make_agent_run(engine, workspace_id=wid, steps=steps)
    assert len(run.step_ids) == 3


async def test_one_pending_approval_per_step_and_cascades(
    engine: AsyncEngine, wid: uuid.UUID
) -> None:
    run = await make_agent_run(
        engine,
        workspace_id=wid,
        status="awaiting_approval",
        steps=[
            {
                "tool": "reply_to_comments",
                "tier": "high",
                "status": "awaiting_approval",
                "decision": "approval",
            }
        ],
    )
    on = {"workspace_id": wid, "run_id": run.id, "step_id": run.step_ids[0]}
    first = await make_agent_approval(engine, **on)
    with pytest.raises(IntegrityError, match="uq_agent_approvals_pending"):
        await make_agent_approval(engine, **on)
    # An edit supersedes the pending approval and asks again.
    await _execute(
        engine, "UPDATE agent_approvals SET status = 'superseded' WHERE id = :a", a=first
    )
    await make_agent_approval(engine, **on)
    with pytest.raises(IntegrityError, match="ck_agent_approvals_status"):
        await make_agent_approval(engine, status="maybe", **on)

    await _execute(engine, "DELETE FROM agent_steps WHERE id = :s", s=run.step_ids[0])
    assert (
        await _scalar(engine, "SELECT count(*) FROM agent_approvals WHERE run_id = :r", r=run.id)
        == 0
    )


async def test_one_policy_per_workspace_with_everything_off(
    engine: AsyncEngine, wid: uuid.UUID
) -> None:
    policy = await make_agent_policy(engine, workspace_id=wid)
    row = await _scalar(
        engine,
        "SELECT jsonb_build_array(mode, permissions, limits) FROM agent_policies WHERE id = :p",
        p=policy,
    )
    assert row == ["read_only", DEFAULT_PERMISSIONS, DEFAULT_LIMITS]
    assert await make_agent_policy(engine, workspace_id=wid, mode="copilot") == policy
    with pytest.raises(IntegrityError, match="uq_agent_policies_workspace_id"):
        await _execute(engine, "INSERT INTO agent_policies (workspace_id) VALUES (:w)", w=wid)
    with pytest.raises(IntegrityError, match="ck_agent_policies_mode"):
        await make_agent_policy(engine, workspace_id=wid, mode="yolo")

    other = await make_workspace(engine)
    await make_agent_policy(engine, workspace_id=other)
    await make_agent_run(engine, workspace_id=other)
    await _execute(engine, "DELETE FROM workspaces WHERE id = :w", w=other)
    for table in ("agent_policies", "agent_runs", "agent_steps"):
        assert (
            await _scalar(engine, f"SELECT count(*) FROM {table} WHERE workspace_id = :w", w=other)  # noqa: S608
            == 0
        )


async def test_agent_turns_are_a_credit_feature(engine: AsyncEngine, wid: uuid.UUID) -> None:
    await _execute(
        engine,
        "INSERT INTO ai_usage_events (workspace_id, feature, model, credits, outcome, ref_type,"
        " ref_id) VALUES (:w, 'agent_turn', 'fake-model', 1, 'ok', 'agent_run', :r)",
        w=wid,
        r=uuid.uuid4(),
    )
    with pytest.raises(IntegrityError, match="ck_ai_usage_events_feature"):
        await _execute(
            engine,
            "INSERT INTO ai_usage_events (workspace_id, feature, model, credits, outcome)"
            " VALUES (:w, 'agent_thought', 'fake-model', 1, 'ok')",
            w=wid,
        )
