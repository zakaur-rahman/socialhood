"""FR-BIL-07 at send time: after a downgrade, accounts past the plan's accounts_per_platform are
read-only (each platform's earliest connected accounts keep the slots). Nothing sends from them:
replies and retries, comment replies and scheduled messages are refused with the 402's entitlement
and limit, and the automation runtime records a skipped run instead of sending. Reading and
moderation stay allowed (C-052). Scheduling and activation are in test_entitlements.py."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.tasks.scheduled import dispatch_due_messages, send_one
from socialhood.platforms.sandbox import outbox
from socialhood.services.automations.queue import HOLD_RETRY_S
from socialhood.services.automations.runtime import Outcome
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.automation_api import make_outbound, set_plan
from tests.support.automations import make_automation, make_comment, make_media_item
from tests.support.inbox import make_account, make_scheduled, make_thread
from tests.support.publishing_api import Shop, open_shop
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


def read_only(username: str) -> str:
    return (
        f"Your plan includes 1 Instagram account. @{username} is read-only until you upgrade or "
        "disconnect another."
    )


async def connected(engine: AsyncEngine, account_id: uuid.UUID, shift: timedelta) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET connected_at = now() + :shift WHERE id = :a"),
            {"a": account_id, "shift": shift},
        )


def assert_read_only(response: httpx.Response, username: str = "maple.cakes") -> None:
    assert response.status_code == 402, response.text
    body = response.json()
    assert (body["code"], body["entitlement"], body["limit"]) == (
        "quota_exceeded",
        "accounts_per_platform",
        1,
    )
    assert body["detail"] == read_only(username)


# ---------------------------------------------------------------- what a person sends


@pytest.fixture
async def shop(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> Shop:
    """A Free workspace's owner with one Instagram account (maple.bakery)."""
    return await open_shop(app, client, clerk, engine)


@pytest.fixture
async def extra(shop: Shop) -> uuid.UUID:
    """A second Instagram account, connected after the first: past Free's one slot."""
    account = await shop.account("maple.cakes")
    await connected(shop.engine, account, timedelta(minutes=1))
    return account


async def send(shop: Shop, conversation_id: uuid.UUID) -> httpx.Response:
    return await shop.client.post(
        shop.url(f"/conversations/{conversation_id}/messages"),
        json={"client_id": str(uuid.uuid4()), "text": "Your order ships today"},
        headers={**shop.headers, "Idempotency-Key": uuid.uuid4().hex},
    )


async def test_replies_and_retries_from_a_read_only_account_are_402(
    shop: Shop, extra: uuid.UUID
) -> None:
    thread = await make_thread(shop.engine, workspace_id=shop.wid, account_id=extra)
    assert_read_only(await send(shop, thread.conversation_id))
    assert await shop.rows("SELECT id FROM messages WHERE direction = 'outbound'") == []

    failed = await make_outbound(
        shop.engine,
        workspace_id=shop.wid,
        account_id=str(extra),
        conversation_id=thread.conversation_id,
        status="failed",
    )
    assert_read_only(await shop.call("POST", f"/messages/{failed}/retry"))
    assert (await shop.one("SELECT status FROM messages WHERE id = :id", id=failed)) == {
        "status": "failed"
    }

    # Reading stays allowed; the account that keeps the slot sends; Pro lifts the limit.
    opened = await shop.call("GET", f"/conversations/{thread.conversation_id}/messages")
    assert opened.status_code == 200, opened.text
    first = await make_thread(shop.engine, workspace_id=shop.wid, account_id=shop.account_id)
    assert (await send(shop, first.conversation_id)).status_code == 202
    await set_plan(shop.engine, shop.wid, "pro")
    assert (await send(shop, thread.conversation_id)).status_code == 202


async def test_comment_replies_from_a_read_only_account_are_402(
    shop: Shop, extra: uuid.UUID
) -> None:
    post = await make_media_item(shop.engine, workspace_id=shop.wid, account_id=extra)
    comment = await make_comment(
        shop.engine, workspace_id=shop.wid, account_id=extra, media_item_id=post, text="Price?"
    )
    for action in ("reply", "private-reply"):
        response = await shop.client.post(
            shop.url(f"/comments/{comment}/{action}"),
            json={"text": "Sent you the price!"},
            headers={**shop.headers, "Idempotency-Key": uuid.uuid4().hex},
        )
        assert_read_only(response)
    assert not outbox.COMMENT_REPLIES
    assert await shop.rows("SELECT id FROM messages") == []

    # Hiding sends nothing, so it stays allowed.
    hidden = await shop.call("POST", f"/comments/{comment}/hide")
    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["hidden"] is True


async def test_a_due_scheduled_message_of_a_read_only_account_fails(
    app: FastAPI, shop: Shop, extra: uuid.UUID
) -> None:
    """Scheduled before the downgrade, due after it: failed with the 402's code and reason."""
    thread = await make_thread(shop.engine, workspace_id=shop.wid, account_id=extra)
    scheduled_id = await make_scheduled(
        shop.engine,
        workspace_id=shop.wid,
        conversation_id=thread.conversation_id,
        send_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    sessions = app.state.sessionmaker
    assert await dispatch_due_messages(sessions, shop.redis) == [scheduled_id]
    outcome = await send_one(
        sessions, shop.redis, scheduled_id, uuid.UUID(shop.wid), human_agent_enabled=False
    )
    assert outcome == "failed"
    row = await shop.one(
        "SELECT status, error_code, error_message, message_id FROM scheduled_messages"
        " WHERE id = :id",
        id=scheduled_id,
    )
    assert row == {
        "status": "failed",
        "error_code": "quota_exceeded",
        "error_message": read_only("maple.cakes"),
        "message_id": None,
    }
    assert await shop.rows("SELECT id FROM messages WHERE direction = 'outbound'") == []


# ---------------------------------------------------------------- the automation runtime


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


async def take_the_slot(world: World) -> None:
    """Another Instagram account, connected earlier, keeps Free's one slot: the world's account
    (maple.bakery) is read-only."""
    first = await make_account(world.engine, world.wid, username="maple.first")
    await connected(world.engine, first, timedelta(days=-1))


async def test_a_dm_automation_of_a_read_only_account_records_a_skipped_run(world: World) -> None:
    automation_id = await make_automation(
        world.engine, workspace_id=world.wid, account_id=world.account_id, keywords=("price",)
    )
    await take_the_slot(world)
    thread = await make_thread(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        texts=("What's the PRICE?",),
    )
    [trigger] = thread.message_ids

    assert await world.run("dm", trigger) is Outcome.SKIPPED
    [run] = await world.rows("SELECT * FROM automation_runs")
    assert (run["automation_id"], run["result"], run["error_code"], run["error_message"]) == (
        automation_id,
        "skipped_read_only",
        "read_only",
        read_only("maple.bakery"),
    )
    assert run["trigger_message_id"] == trigger
    assert await world.rows("SELECT id FROM messages WHERE direction = 'outbound'") == []
    [handled] = await world.rows(
        "SELECT automation_handled FROM messages WHERE id = :id", id=trigger
    )
    assert handled["automation_handled"] is False  # the inbox AI may still suggest a reply
    assert await world.run("dm", trigger) is Outcome.ALREADY_RAN


async def test_a_comment_automation_of_a_read_only_account_records_a_skipped_run(
    world: World,
) -> None:
    await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        trigger="comment_keyword",
        message_text="Here's the link!",
        public_reply_texts=["Check your inbox!"],
    )
    await take_the_slot(world)
    comment_id = await world.comment("LINK please")
    assert comment_id is not None

    assert await world.run("comment", comment_id) is Outcome.SKIPPED
    [run] = await world.rows("SELECT * FROM automation_runs")
    assert (run["result"], run["error_code"], run["error_message"]) == (
        "skipped_read_only",
        "read_only",
        read_only("maple.bakery"),
    )
    assert run["trigger_comment_id"] == comment_id
    assert not outbox.COMMENT_REPLIES  # no public reply either
    assert not outbox.PRIVATE_REPLIES


async def test_the_private_reply_queue_holds_for_a_read_only_account(world: World) -> None:
    """A run queued before the downgrade waits (and still expires after 7 days); nothing is
    sent while the account is read-only."""
    await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        trigger="comment_keyword",
        message_text="Here's the link!",
    )
    comment_id = await world.comment("link")
    assert comment_id is not None
    assert await world.run("comment", comment_id) is Outcome.FIRED
    await take_the_slot(world)

    result = await world.drain()
    assert (result.sent, result.failed, result.remaining, result.next_in_s) == (
        0,
        0,
        1,
        HOLD_RETRY_S,
    )
    assert not outbox.PRIVATE_REPLIES
    assert (await world.run_row())["result"] == "queued"
