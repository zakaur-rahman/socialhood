"""GR-44: "Automatic replies" off for one contact. Each automatic send stops at its own entry
point (the inbox's automations, the away message, comment automations, the follow nudge); the
setting is read and written through PATCH /contacts/{id}. AI Auto and sequence steps are covered
in test_auto_reply.py and unit/test_sequence_rules.py."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.platforms.sandbox import outbox
from socialhood.services.automations.runtime import Outcome
from socialhood.services.sending import Delivery
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace
from tests.support.automations import make_automation
from tests.support.inbox import make_account, make_thread
from tests.support.ingest import ACCOUNT_REF, deliver, jobs, sessions
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

WEEKDAYS = [{"day": d, "ranges": [{"start": "09:00", "end": "17:00"}]} for d in range(5)]


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


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


async def switch_off(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE contacts SET auto_replies_off = true"))


async def outbound(world: World) -> list[dict[str, Any]]:
    return await world.rows("SELECT * FROM messages WHERE direction = 'outbound'")


# ---------------------------------------------------------------- the setting


async def test_the_switch_is_saved_and_shown_on_the_contact_and_the_conversation(
    engine: AsyncEngine, ws: Ws
) -> None:
    thread = await make_thread(
        engine, workspace_id=ws.wid, account_id=ws.account_id, contact_ref="vip", texts=("Hi",)
    )
    start = await ws.ok("GET", f"/contacts/{thread.contact_id}")
    assert start["auto_replies_off"] is False

    off = await ws.ok("PATCH", f"/contacts/{thread.contact_id}", json={"auto_replies_off": True})
    assert off["auto_replies_off"] is True
    detail = await ws.ok("GET", f"/conversations/{thread.conversation_id}")
    assert detail["contact"]["auto_replies_off"] is True

    # A patch that does not mention it leaves it alone; false turns it back on.
    kept = await ws.ok("PATCH", f"/contacts/{thread.contact_id}", json={"name": "VIP"})
    assert kept["auto_replies_off"] is True
    on = await ws.ok("PATCH", f"/contacts/{thread.contact_id}", json={"auto_replies_off": False})
    assert on["auto_replies_off"] is False


# ---------------------------------------------------------------- the entry points


async def test_ingest_starts_no_automation_run_for_a_contact_with_replies_off(
    world: World, engine: AsyncEngine, redis: Redis
) -> None:
    ig = await make_account(engine, world.wid, platform_account_id=ACCOUNT_REF)
    await make_automation(engine, workspace_id=world.wid, account_id=ig, keywords=("sourdough",))
    maker = sessions(engine)

    await deliver(maker, redis, "webhook_message_text.json")
    assert len(await jobs("run_automation")) == 1  # a person who has it on: a run is queued

    await switch_off(engine)
    await deliver(maker, redis, "webhook_message_reply.json")
    assert len(await jobs("run_automation")) == 1  # the second message queued nothing


async def test_a_keyword_run_that_was_already_queued_still_sends_nothing_when_the_away_applies(
    world: World, engine: AsyncEngine
) -> None:
    """The away message (GR-22) checks the contact itself, for a run queued before the switch."""
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET timezone = 'UTC' WHERE id = :w"), {"w": world.wid}
        )
        await conn.execute(
            text(
                "INSERT INTO business_hours (workspace_id, social_account_id, enabled, schedule,"
                " away_enabled, away_message, auto_mode) VALUES (:w, NULL, true,"
                " CAST(:s AS jsonb), true, 'We are closed.', 'always')"
            ),
            {"w": world.wid, "s": json.dumps(WEEKDAYS)},
        )
    at = datetime(2026, 10, 19, 23, 0, tzinfo=UTC)  # a Monday, after closing
    dm = await world.dm("igsid_night", "hello?", at=at)
    assert dm is not None
    await switch_off(engine)

    assert await world.run("dm", dm, now=at) is Outcome.NO_MATCH

    assert await outbound(world) == []


async def test_a_comment_from_a_contact_with_replies_off_gets_no_public_reply_and_no_dm(
    world: World, engine: AsyncEngine
) -> None:
    await make_automation(
        engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        trigger="comment_keyword",
        message_text="Here's the link, {username}!",
        public_reply_texts=["Check your inbox!"],
    )
    first = await world.comment("link", author="990000000000042")
    assert first is not None
    await switch_off(engine)
    second = await world.comment("link please", author="990000000000042")
    assert second is not None

    assert await world.run("comment", second) is Outcome.SKIPPED

    assert not outbox.COMMENT_REPLIES
    assert await world.rows("SELECT id FROM automation_runs") == []
    assert (await world.drain()).sent == 0
    assert not outbox.PRIVATE_REPLIES


async def test_the_follow_nudge_is_not_queued_for_a_contact_with_replies_off(
    world: World, engine: AsyncEngine
) -> None:
    await make_automation(
        engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        trigger="dm_keyword",
        keywords=("price",),
        message_text="Prices start at 499.",
        follow_nudge=True,
        follow_nudge_text="Follow us for more!",
    )
    dm = await world.dm("igsid_vip", "price?")
    assert dm is not None
    outbox.set_follows("igsid_vip", False)
    assert await world.run("dm", dm) is Outcome.FIRED
    [message] = await outbound(world)
    await switch_off(engine)  # turned off after the keyword reply went out

    assert await world.send(message["id"]) is Delivery.SENT

    nudges = [j for j in await jobs("run_automation") if j["args"]["kind"] == "nudge"]
    assert nudges == []
