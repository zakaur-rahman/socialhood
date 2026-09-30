"""T4.6: the private-reply queue (FR-AUT-10, TR-JOB-07). A sandbox surge of 5,000 matches never
sends more than 750 private replies in any hour, finishes within 10% of its ETA, skips expired
matches with the reason, and never delays a DM on another account. Surge orders, public reply
only, a paused automation, temporary errors and the job's re-defer. Time is simulated: the drain
takes ``now`` (which also drives the token bucket) under time-machine."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import time_machine
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.platforms.sandbox import outbox
from socialhood.repositories import inbox
from socialhood.services import sending
from socialhood.services.automations import queue as prq
from socialhood.services.automations.runtime import Outcome
from socialhood.services.sending import Delivery
from socialhood.settings import Settings
from tests.support.automations import make_automation, make_media_item
from tests.support.inbox import make_account, make_thread
from tests.support.ingest import jobs
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

HOUR = timedelta(hours=1)


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def world(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    clean_db: None,
    queue: None,
) -> AsyncIterator[World]:
    async with platform_deps(api_settings, monkeypatch) as deps:
        yield await make_world(engine, redis, deps)


async def comment_automation(world: World, **values: Any) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "trigger": "comment_keyword",
        "message_text": "Here's the link, {username}!",
        "cooldown_hours": 0,
    }
    return await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        **{**defaults, **values},
    )


async def queued_runs(
    world: World,
    automation_id: uuid.UUID,
    *,
    count: int,
    commented_at: datetime,
    contacts: int = 250,
    prefix: str = "c",
    step: timedelta = timedelta(milliseconds=10),
) -> None:
    """``count`` matched comments waiting in the queue, written in bulk (a surge)."""
    media_item_id = await make_media_item(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        platform_media_id=f"post_{prefix}",
    )
    params = {
        "ws": world.wid,
        "acct": world.account_id,
        "media": media_item_id,
        "auto": automation_id,
        "n": count,
        "k": contacts,
        "t": commented_at,
        "step": step,
        "prefix": prefix,
    }
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO contacts (workspace_id, social_account_id, platform_user_id, username,"
                " first_seen_at)"
                " SELECT CAST(:ws AS uuid), CAST(:acct AS uuid), 'igsid_' || g, 'fan_' || g,"
                " CAST(:t AS timestamptz) FROM generate_series(1, CAST(:k AS integer)) g"
                " ON CONFLICT DO NOTHING"
            ),
            params,
        )
        await conn.execute(
            text(
                "INSERT INTO comments (workspace_id, social_account_id, media_item_id, contact_id,"
                " platform_comment_id, author_platform_user_id, author_username, text,"
                " commented_at)"
                " SELECT CAST(:ws AS uuid), CAST(:acct AS uuid), CAST(:media AS uuid), c.id,"
                " CAST(:prefix AS text) || '_' || g, c.platform_user_id, c.username, 'LINK',"
                " CAST(:t AS timestamptz) + g * CAST(:step AS interval)"
                " FROM generate_series(1, CAST(:n AS integer)) g"
                " JOIN contacts c ON c.social_account_id = CAST(:acct AS uuid)"
                " AND c.platform_user_id = 'igsid_' || (1 + g % CAST(:k AS integer))"
            ),
            params,
        )
        await conn.execute(
            text(
                "INSERT INTO automation_runs (workspace_id, automation_id, contact_id,"
                " trigger_comment_id, matched_keyword, result, created_at)"
                " SELECT CAST(:ws AS uuid), CAST(:auto AS uuid), contact_id, id, 'link', 'queued',"
                " commented_at FROM comments WHERE media_item_id = CAST(:media AS uuid)"
            ),
            params,
        )
    # As in a running database, where autovacuum keeps the planner's statistics current.
    async with world.engine.begin() as conn:
        await conn.execute(text("ANALYZE contacts, comments, automation_runs, conversations"))


async def send_times(world: World, account_id: uuid.UUID) -> list[datetime]:
    rows = await world.rows(
        "SELECT occurred_at FROM messages WHERE social_account_id = :a AND source = 'automation'"
        " AND status = 'sent' ORDER BY occurred_at",
        a=account_id,
    )
    return [r["occurred_at"] for r in rows]


def most_in_any_hour(times: list[datetime]) -> int:
    """The largest number of sends in any window [t, t + 1 h)."""
    most, start = 0, 0
    for end, at in enumerate(times):
        while at - times[start] >= HOUR:
            start += 1
        most = max(most, end - start + 1)
    return most


async def test_a_surge_of_5000_keeps_to_750_an_hour_and_its_eta(world: World) -> None:
    t0 = datetime.now(UTC).replace(microsecond=0)
    automation_id = await comment_automation(world)
    await queued_runs(world, automation_id, count=5000, commented_at=t0 - timedelta(minutes=5))
    await queued_runs(
        world, automation_id, count=40, commented_at=t0 - timedelta(days=8), prefix="old"
    )

    # Another account in the workspace, with a DM automation and a customer who just wrote
    # (on Pro: Free's one Instagram slot would leave it read-only, FR-BIL-07).
    await world.plan("pro")
    other = await make_account(world.engine, world.wid)
    await make_automation(world.engine, workspace_id=world.wid, account_id=other)

    waiting, eta_minutes = await world.queue_info(now=t0)
    assert waiting == 5000  # the expired ones will not be sent
    assert eta_minutes is not None

    now, drains, other_checked = t0, 0, False
    while True:
        with time_machine.travel(now, tick=False):
            result = await world.drain(now=now)
            if result.sent and not other_checked:
                await dm_on_another_account_is_not_delayed(world, other, now)
                other_checked = True
        drains += 1
        if result.next_in_s is None:
            break
        assert result.next_in_s >= 0
        now += timedelta(seconds=result.next_in_s)
        assert drains < 5000, "the queue never emptied"

    times = await send_times(world, world.account_id)
    assert len(times) == 5000
    assert most_in_any_hour(times) <= 750
    actual_minutes = (times[-1] - t0).total_seconds() / 60
    assert abs(eta_minutes - actual_minutes) <= 0.10 * actual_minutes

    counts = {
        r["result"]: r["n"]
        for r in await world.rows(
            "SELECT result, count(*) AS n FROM automation_runs WHERE automation_id = :a"
            " GROUP BY result",
            a=automation_id,
        )
    }
    assert counts == {"sent": 5000, "skipped_expired": 40}
    expired = await world.rows(
        "SELECT DISTINCT error_message FROM automation_runs WHERE result = 'skipped_expired'"
    )
    assert expired == [{"error_message": "Instagram's 7-day limit passed"}]
    assert await world.queue_info(now=now) == (0, None)


async def dm_on_another_account_is_not_delayed(
    world: World, account_id: uuid.UUID, now: datetime
) -> None:
    thread = await make_thread(
        world.engine,
        workspace_id=world.wid,
        account_id=account_id,
        texts=("Can I get the link?",),
        last_inbound_at=now - timedelta(minutes=1),
    )
    assert await world.run("dm", thread.message_ids[0], now=now) is Outcome.FIRED
    [dm] = await world.rows(
        "SELECT id FROM messages WHERE conversation_id = :c AND direction = 'outbound'",
        c=thread.conversation_id,
    )
    assert await world.send(dm["id"], now=now) is Delivery.SENT  # at once, not deferred
    # The surging account's own DMs use their own bucket too.
    mine = await make_thread(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        texts=("Hello?",),
        last_inbound_at=now - timedelta(minutes=1),
    )
    with workspace_scope(world.wid):
        async with world.maker() as session:
            conv = await inbox.get_conversation(session, mine.conversation_id)
            assert conv is not None
            msg = await sending.queue_outbound(
                session,
                conv,
                source="human",
                client_id=uuid.uuid4(),
                text="Hi! How can we help?",
                deps=world.deps,
                now=now,
            )
            await session.commit()
    assert await world.send(msg.id, now=now) is Delivery.SENT


@pytest.mark.parametrize(("order", "expected"), [("oldest_first", "abc"), ("newest_first", "cba")])
async def test_surge_orders(world: World, order: str, expected: str) -> None:
    automation_id = await comment_automation(world, surge_order=order)
    t0 = datetime.now(UTC) - timedelta(minutes=10)
    for i, name in enumerate("abc"):
        await queued_runs(
            world, automation_id, count=1, commented_at=t0 + timedelta(minutes=i), prefix=name
        )
    assert (await world.drain()).sent == 3
    assert [p.recipient_ref.split("_")[0] for p in outbox.PRIVATE_REPLIES] == list(expected)


async def test_automations_share_the_queue_in_turn(world: World) -> None:
    first = await comment_automation(world, priority=1)
    second = await comment_automation(world, priority=2, message_text="Second")
    t0 = datetime.now(UTC) - timedelta(minutes=10)
    await queued_runs(world, first, count=30, commented_at=t0, prefix="first")
    await queued_runs(world, second, count=30, commented_at=t0, prefix="second")
    result = await world.drain()
    assert result.sent == 20  # the bucket's burst
    refs = [p.recipient_ref.split("_")[0] for p in outbox.PRIVATE_REPLIES]
    assert refs == ["first", "second"] * 10
    assert result.remaining == 40
    assert result.next_in_s is not None
    assert 95 < result.next_in_s < 100  # a batch of 20 tokens at 730 an hour


async def test_public_reply_only_settles_the_queue_without_dms(world: World) -> None:
    automation_id = await comment_automation(world)
    await queued_runs(world, automation_id, count=5, commented_at=datetime.now(UTC))
    async with world.engine.begin() as conn:
        await conn.execute(text("UPDATE automations SET surge_order = 'public_only'"))
    assert await world.queue_info() == (0, None)
    result = await world.drain()
    assert (result.sent, result.settled, result.next_in_s) == (0, 5, None)
    assert not outbox.PRIVATE_REPLIES
    rows = await world.rows("SELECT result, error_code FROM automation_runs")
    assert {(r["result"], r["error_code"]) for r in rows} == {("failed", "nothing_sent")}


async def test_a_paused_automation_holds_its_queue(world: World) -> None:
    automation_id = await comment_automation(world)
    await queued_runs(world, automation_id, count=3, commented_at=datetime.now(UTC))
    async with world.engine.begin() as conn:
        await conn.execute(text("UPDATE automations SET status = 'paused'"))
    result = await world.drain()
    assert (result.sent, result.next_in_s) == (0, prq.HOLD_RETRY_S)
    async with world.engine.begin() as conn:
        await conn.execute(text("UPDATE automations SET status = 'active'"))
    assert (await world.drain()).sent == 3


async def test_an_ended_run_window_still_sends_what_matched(world: World) -> None:
    automation_id = await comment_automation(world)
    await queued_runs(world, automation_id, count=2, commented_at=datetime.now(UTC))
    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE automations SET status = 'paused', ends_at = now() - interval '1 minute'")
        )
    assert (await world.drain()).sent == 2


async def test_a_temporary_error_puts_the_reply_back_in_the_queue(world: World) -> None:
    automation_id = await comment_automation(world)
    await queued_runs(world, automation_id, count=1, commented_at=datetime.now(UTC))
    outbox.fail_next("platform_unavailable", kind="private_reply")
    result = await world.drain()
    assert (result.sent, result.remaining, result.next_in_s) == (0, 1, prq.RETRY_AFTER_S)
    assert await world.rows("SELECT id FROM messages") == []
    [run] = await world.rows("SELECT result, private_reply_message_id FROM automation_runs")
    assert run == {"result": "queued", "private_reply_message_id": None}
    assert (await world.drain()).sent == 1


async def test_an_account_to_reconnect_holds_the_queue(world: World) -> None:
    automation_id = await comment_automation(world)
    await queued_runs(world, automation_id, count=2, commented_at=datetime.now(UTC))
    outbox.fail_next("account_needs_reconnect", kind="private_reply")
    result = await world.drain()
    assert (result.failed, result.sent) == (1, 0)
    [acct] = await world.rows(
        "SELECT status FROM social_accounts WHERE id = :id", id=world.account_id
    )
    assert acct["status"] == "needs_reconnect"
    held = await world.drain()
    assert (held.sent, held.remaining, held.next_in_s) == (0, 1, prq.HOLD_RETRY_S)


async def test_the_eta(world: World) -> None:
    automation_id = await comment_automation(world)
    await queued_runs(world, automation_id, count=1460, commented_at=datetime.now(UTC))
    assert await world.queue_info() == (1460, 120)  # 730 an hour
    with workspace_scope(world.wid):
        async with world.maker() as session:
            assert await prq.automation_waiting(session, automation_id) == 1460


async def test_the_drain_job_re_defers_itself_while_runs_wait(world: World) -> None:
    automation_id = await comment_automation(world)
    await queued_runs(world, automation_id, count=25, commented_at=datetime.now(UTC))
    with workspace_scope(world.wid):
        result = await prq.run_drain(
            world.maker,
            world.redis,
            world.deps,
            workspace_id=world.wid,
            account_id=world.account_id,
        )
    assert (result.sent, result.remaining) == (20, 5)
    [job] = await jobs("drain_private_replies")
    assert job["queueing_lock"] == f"prq:{world.account_id}"
    assert job["deferred"] is True
