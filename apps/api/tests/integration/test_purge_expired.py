"""T9.6: purge_expired, §5.9's retention rules. Each rule deletes what is past its retention and
keeps what isn't; batches of 2 make every rule loop."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from socialhood.db.engine import make_sessionmaker
from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.tasks.purge import delete_finished_jobs, months_before, purge_expired_rows
from tests.support.agent import make_agent_run
from tests.support.ai import make_analysis
from tests.support.inbox import make_account, make_thread, make_workspace
from tests.support.notify import make_notification

NOW = datetime(2026, 9, 30, 4, 0, tzinfo=UTC)


@pytest.fixture
def maker(engine: AsyncEngine, clean_db: None) -> async_sessionmaker[Any]:
    return make_sessionmaker(engine)


async def ids(engine: AsyncEngine, sql: str, **params: Any) -> set[str]:
    async with engine.connect() as conn:
        return {str(v) for v in (await conn.execute(text(sql), params)).scalars()}


async def run(maker: async_sessionmaker[Any]) -> dict[str, int]:
    return await purge_expired_rows(maker, now=NOW, batch=2)


async def _owner(engine: AsyncEngine, wid: uuid.UUID) -> uuid.UUID:
    async with engine.connect() as conn:
        owner: uuid.UUID = (
            await conn.execute(
                text("SELECT owner_user_id FROM workspaces WHERE id = :w"), {"w": wid}
            )
        ).scalar_one()
    return owner


async def test_webhook_events_are_kept_30_days(
    engine: AsyncEngine, maker: async_sessionmaker[Any]
) -> None:
    async with engine.begin() as conn:
        for key, age, status in (
            ("old-1", 31, "processed"),
            ("old-2", 40, "failed"),  # the dead-letter set goes too (TR-OPS-04)
            ("old-3", 30.1, "ignored"),
            ("new-1", 29, "processed"),
            ("new-2", 1, "failed"),
        ):
            await conn.execute(
                text(
                    "INSERT INTO webhook_events (provider, dedupe_key, event_type, payload,"
                    " status, received_at) VALUES ('instagram', :k, 'message', '{}', :s, :at)"
                ),
                {"k": key, "s": status, "at": NOW - timedelta(days=age)},
            )
    counts = await run(maker)
    assert counts["webhook_events"] == 3
    assert await ids(engine, "SELECT dedupe_key FROM webhook_events") == {"new-1", "new-2"}


async def test_notifications_are_kept_90_days(
    engine: AsyncEngine, maker: async_sessionmaker[Any]
) -> None:
    wid = await make_workspace(engine)
    user = await _owner(engine, wid)
    old = [
        await make_notification(
            engine, workspace_id=wid, user_id=user, created_at=NOW - timedelta(days=days)
        )
        for days in (91, 120, 365)
    ]
    kept = await make_notification(
        engine, workspace_id=wid, user_id=user, created_at=NOW - timedelta(days=89)
    )
    counts = await run(maker)
    assert counts["notifications"] == len(old)
    assert await ids(engine, "SELECT id FROM notifications") == {str(kept)}


async def test_ai_usage_events_are_kept_13_months(
    engine: AsyncEngine, maker: async_sessionmaker[Any]
) -> None:
    wid = await make_workspace(engine)
    cutoff = months_before(NOW, 13)  # 2025-08-30 04:00
    async with engine.begin() as conn:
        for ref, at in (
            ("old", cutoff - timedelta(seconds=1)),
            ("older", cutoff - timedelta(days=60)),
            ("kept", cutoff + timedelta(seconds=1)),
        ):
            await conn.execute(
                text(
                    "INSERT INTO ai_usage_events (workspace_id, feature, model, credits, outcome,"
                    " ref_type, created_at) VALUES (:w, 'message_analysis', 'fake', 1, 'ok', :r,"
                    " :at)"
                ),
                {"w": wid, "r": ref, "at": at},
            )
    counts = await run(maker)
    assert counts["ai_usage_events"] == 2
    assert await ids(engine, "SELECT ref_type FROM ai_usage_events") == {"kept"}


async def test_finished_agent_runs_are_kept_180_days(
    engine: AsyncEngine, maker: async_sessionmaker[Any]
) -> None:
    wid = await make_workspace(engine)
    old = NOW - timedelta(days=181)
    finished = await make_agent_run(engine, workspace_id=wid, created_at=old)
    failed = await make_agent_run(engine, workspace_id=wid, created_at=old, status="failed")
    running = await make_agent_run(
        engine, workspace_id=wid, created_at=old, status="running", completed_at=None
    )
    recent = await make_agent_run(engine, workspace_id=wid, created_at=NOW - timedelta(days=179))
    counts = await run(maker)
    assert counts["agent_runs"] == 2
    assert await ids(engine, "SELECT id FROM agent_runs") == {str(running.id), str(recent.id)}
    steps = await ids(engine, "SELECT run_id FROM agent_steps")
    assert steps.isdisjoint({str(finished.id), str(failed.id)})  # cascaded


async def _age_messages(engine: AsyncEngine, message_ids: list[uuid.UUID], days: int) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE messages SET occurred_at = :at WHERE id = ANY(:ids)"),
            {"at": NOW - timedelta(days=days), "ids": message_ids},
        )


async def _age_conversation(engine: AsyncEngine, conversation_id: uuid.UUID, days: int) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE conversations SET last_message_at = :at WHERE id = :c"),
            {"at": NOW - timedelta(days=days), "c": conversation_id},
        )


async def test_free_message_history_is_90_days_and_empty_conversations_go(
    engine: AsyncEngine, maker: async_sessionmaker[Any]
) -> None:
    """§5.9 and OQ-7: on Free, messages older than 90 days go with their analyses, and so does a
    conversation left without messages; a paid workspace keeps everything."""
    free = await make_workspace(engine)
    account = await make_account(engine, free)
    stale = await make_thread(
        engine, workspace_id=free, account_id=account, texts=("hi", "price?", "thanks")
    )
    mixed = await make_thread(
        engine, workspace_id=free, account_id=account, texts=("old", "new"), contact_ref="c2"
    )
    await _age_messages(engine, stale.message_ids, 91)
    await _age_conversation(engine, stale.conversation_id, 91)
    await _age_messages(engine, mixed.message_ids[:1], 120)
    analysis = await make_analysis(
        engine,
        workspace_id=free,
        conversation_id=stale.conversation_id,
        message_id=stale.message_ids[0],
    )

    paid = await make_workspace(engine)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO subscriptions (workspace_id, plan, status, billing_anchor_day)"
                " VALUES (:w, 'pro', 'active', 1)"
            ),
            {"w": paid},
        )
    paid_account = await make_account(engine, paid)
    paid_thread = await make_thread(engine, workspace_id=paid, account_id=paid_account)
    await _age_messages(engine, paid_thread.message_ids, 400)

    counts = await run(maker)
    assert counts["messages"] == 4
    assert counts["conversations"] == 1
    assert await ids(engine, "SELECT id FROM messages WHERE workspace_id = :w", w=free) == {
        str(mixed.message_ids[1])
    }
    assert await ids(engine, "SELECT id FROM conversations WHERE workspace_id = :w", w=free) == {
        str(mixed.conversation_id)
    }
    assert await ids(engine, "SELECT id FROM message_analyses WHERE id = :a", a=analysis) == set()
    assert await ids(engine, "SELECT id FROM messages WHERE workspace_id = :w", w=paid) == {
        str(m) for m in paid_thread.message_ids
    }


async def test_a_new_conversation_without_messages_is_kept(
    engine: AsyncEngine, maker: async_sessionmaker[Any]
) -> None:
    free = await make_workspace(engine)
    account = await make_account(engine, free)
    thread = await make_thread(engine, workspace_id=free, account_id=account, texts=())
    await run(maker)
    assert await ids(engine, "SELECT id FROM conversations") == {str(thread.conversation_id)}


async def test_a_deleting_workspace_is_left_to_its_purge(
    engine: AsyncEngine, maker: async_sessionmaker[Any]
) -> None:
    wid = await make_workspace(engine)
    account = await make_account(engine, wid)
    thread = await make_thread(engine, workspace_id=wid, account_id=account)
    await _age_messages(engine, thread.message_ids, 200)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET status = 'deleting' WHERE id = :w"), {"w": wid}
        )
    counts = await run(maker)
    assert "messages" not in counts


async def test_nothing_expired_deletes_nothing(
    engine: AsyncEngine, maker: async_sessionmaker[Any]
) -> None:
    wid = await make_workspace(engine)
    account = await make_account(engine, wid)
    await make_thread(engine, workspace_id=wid, account_id=account)
    assert await run(maker) == {}


async def test_finished_queue_jobs_are_kept_30_days(engine: AsyncEngine, queue: None) -> None:
    connector = jobs_app.connector
    made = []
    for _ in range(3):
        job = await jobs_app.configure_task("purge_workspace", queue="bulk").defer_async(
            workspace_id=str(uuid.uuid4())
        )
        made.append(job)
    old_done, old_failed, recent_done = made
    await connector.execute_query_async(
        "UPDATE procrastinate_jobs SET status = 'succeeded' WHERE id = ANY(%(ids)s)",
        ids=[old_done, recent_done],
    )
    await connector.execute_query_async(
        "UPDATE procrastinate_jobs SET status = 'failed' WHERE id = %(id)s", id=old_failed
    )
    await connector.execute_query_async(
        "UPDATE procrastinate_events SET at = now() - interval '31 days'"
        " WHERE job_id = ANY(%(ids)s)",
        ids=[old_done, old_failed],
    )
    await delete_finished_jobs()
    left = await connector.execute_query_all_async("SELECT id FROM procrastinate_jobs")
    assert [row["id"] for row in left] == [recent_done]


def test_months_before_keeps_the_day_or_the_months_last() -> None:
    assert months_before(NOW, 13) == datetime(2025, 8, 30, 4, 0, tzinfo=UTC)
    assert months_before(datetime(2026, 3, 31, tzinfo=UTC), 1) == datetime(2026, 2, 28, tzinfo=UTC)
    assert months_before(datetime(2026, 1, 15, tzinfo=UTC), 13) == datetime(
        2024, 12, 15, tzinfo=UTC
    )
