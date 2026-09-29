"""T4.4: DM automations at runtime (F-11 runtime; FR-AUT-05…07, FR-AUT-11, FR-AUT-13, FR-AUT-16,
FR-AUT-17): matching per account, priority, cooldown, run window, the DM through the send
pipeline, automation_handled, run idempotency, and contact_replied_at."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.models.inbox import Conversation
from socialhood.platforms.events import InboundMessage
from socialhood.platforms.sandbox import outbox
from socialhood.repositories import social_accounts as accounts
from socialhood.services.automations.runtime import Outcome
from socialhood.services.conversations import list_messages
from socialhood.services.ingest import ingest
from socialhood.services.sending import Delivery
from socialhood.settings import Settings
from tests.support.automations import make_automation
from tests.support.inbox import Thread, make_account, make_asset, make_thread, make_workspace
from tests.support.ingest import ACCOUNT_REF, deliver, jobs, sessions, stream
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox


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


async def dm_thread(world: World, *texts: str, **values: Any) -> Thread:
    return await make_thread(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        texts=texts or ("What's the PRICE?",),
        **values,
    )


async def outbound(world: World) -> list[dict[str, Any]]:
    return await world.rows(
        "SELECT * FROM messages WHERE direction = 'outbound' ORDER BY occurred_at, created_at"
    )


async def test_a_dm_keyword_sends_the_message_once(world: World) -> None:
    automation_id = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("price",),
        message_text="Hi {first_name}! Prices are on maple.example",
    )
    thread = await dm_thread(world)
    [trigger] = thread.message_ids

    assert await world.run("dm", trigger) is Outcome.FIRED

    run = await world.run_row()
    assert (run["automation_id"], run["result"], run["matched_keyword"]) == (
        automation_id,
        "sent",
        "price",
    )
    assert (run["trigger_message_id"], run["contact_id"], run["conversation_id"]) == (
        trigger,
        thread.contact_id,
        thread.conversation_id,
    )
    [dm] = await outbound(world)
    assert (dm["source"], dm["status"], dm["text"]) == (
        "automation",
        "queued",
        "Hi Priya! Prices are on maple.example",
    )
    assert dm["automation_run_id"] == run["id"]
    assert run["private_reply_message_id"] == dm["id"]
    # The bubble says "Automation · Send the link", live and when the conversation loads.
    named = {"id": str(automation_id), "name": "Send the link"}
    [created] = [
        data
        for kind, data in await stream(world.redis, world.wid)
        if kind == "message.created" and data["message"]["id"] == str(dm["id"])
    ]
    assert created["message"]["automation"] == named
    assert "_automation_run_id" not in created
    with workspace_scope(world.wid):
        async with world.maker() as session:
            conv = await session.get(Conversation, thread.conversation_id)
            assert conv is not None
            page = await list_messages(session, conv, cursor=None, limit=50)
    by_id = {str(m.id): m for m in page.items}
    assert by_id[str(dm["id"])].automation is not None
    assert by_id[str(dm["id"])].automation.model_dump(mode="json") == named
    assert by_id[str(trigger)].automation is None
    [handled] = await world.rows(
        "SELECT automation_handled FROM messages WHERE id = :id", id=trigger
    )
    assert handled["automation_handled"] is True  # FR-AUT-07: the AI leaves this message alone
    [send_job] = await jobs("send_message")
    assert send_job["queueing_lock"] == f"send:{dm['id']}"
    [automation] = await world.rows("SELECT last_run_at FROM automations")
    assert automation["last_run_at"] is not None

    assert await world.send(dm["id"]) is Delivery.SENT
    [sent] = outbox.SENT
    assert sent.message.text == "Hi Priya! Prices are on maple.example"
    assert (await world.run_row())["result"] == "sent"

    # Re-running the same event sends nothing.
    assert await world.run("dm", trigger) is Outcome.ALREADY_RAN
    assert len(await outbound(world)) == 1
    assert len(await world.rows("SELECT id FROM automation_runs")) == 1
    assert len(outbox.SENT) == 1


async def test_the_dm_carries_its_image_buttons_and_the_disclosure_line(world: World) -> None:
    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET automation_disclosure = 'Sent automatically'")
        )
    asset_id = await make_asset(world.engine, workspace_id=world.wid)
    await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("catalogue",),
        message_text="Here you go, {username|friend}",
        message_media_asset_id=asset_id,
        message_buttons=[{"title": "Catalogue", "url": "https://maple.example/catalogue"}],
    )
    thread = await dm_thread(world, "catalogue please", username=None)
    assert await world.run("dm", thread.message_ids[0]) is Outcome.FIRED

    [dm] = await outbound(world)
    assert dm["text"] == "Here you go, friend\n\nSent automatically"
    assert dm["buttons"] == [{"title": "Catalogue", "url": "https://maple.example/catalogue"}]
    assert [a["type"] for a in dm["attachments"]] == ["image"]

    assert await world.send(dm["id"]) is Delivery.SENT
    image, text_part = outbox.SENT
    assert image.message.attachment is not None
    assert text_part.message.text == "Here you go, friend\n\nSent automatically"
    assert [(b.title, b.url) for b in text_part.message.buttons] == [
        ("Catalogue", "https://maple.example/catalogue")
    ]


async def test_paused_and_other_accounts_automations_never_fire(
    world: World, engine: AsyncEngine
) -> None:
    await make_automation(
        engine, workspace_id=world.wid, account_id=world.account_id, status="paused"
    )
    await make_automation(
        engine, workspace_id=world.wid, account_id=world.account_id, status="draft"
    )
    # The same keyword on another account of this workspace, and in another workspace.
    other_account = await make_account(engine, world.wid)
    await make_automation(engine, workspace_id=world.wid, account_id=other_account)
    other_wid = await make_workspace(engine)
    await make_automation(
        engine, workspace_id=other_wid, account_id=await make_account(engine, other_wid)
    )

    thread = await dm_thread(world, "Send me the link")
    assert await world.run("dm", thread.message_ids[0]) is Outcome.NO_MATCH
    assert await outbound(world) == []
    assert await world.rows("SELECT id FROM automation_runs") == []


async def test_priority_then_cooldown(world: World) -> None:
    first = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("price",),
        priority=1,
        message_text="First",
    )
    second = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("price",),
        priority=2,
        message_text="Second",
    )
    thread = await dm_thread(world, "price?", "price again?", "and the price?")
    one, two, three = thread.message_ids

    assert await world.run("dm", one) is Outcome.FIRED
    # The first automation is cooling down for this contact: it records the skip and the
    # next matching automation answers.
    assert await world.run("dm", two) is Outcome.FIRED
    assert await world.run("dm", three) is Outcome.SKIPPED

    rows = await world.rows(
        "SELECT automation_id, trigger_message_id, result FROM automation_runs"
        " ORDER BY created_at, result"
    )
    assert {(r["automation_id"], r["trigger_message_id"], r["result"]) for r in rows} == {
        (first, one, "sent"),
        (first, two, "skipped_cooldown"),
        (second, two, "sent"),
        (first, three, "skipped_cooldown"),
        (second, three, "skipped_cooldown"),
    }
    assert [m["text"] for m in await outbound(world)] == ["First", "Second"]


async def test_no_cooldown_answers_every_time(world: World) -> None:
    await make_automation(
        world.engine, workspace_id=world.wid, account_id=world.account_id, cooldown_hours=0
    )
    thread = await dm_thread(world, "link", "link")
    for message_id in thread.message_ids:
        assert await world.run("dm", message_id) is Outcome.FIRED
    assert len(await outbound(world)) == 2


async def test_cooldown_ends(world: World) -> None:
    await make_automation(
        world.engine, workspace_id=world.wid, account_id=world.account_id, cooldown_hours=1
    )
    thread = await dm_thread(world, "link", "link")
    now = datetime.now(UTC)
    assert await world.run("dm", thread.message_ids[0], now=now - timedelta(minutes=61)) is (
        Outcome.FIRED
    )
    assert await world.run("dm", thread.message_ids[1], now=now) is Outcome.FIRED


async def test_the_run_window(world: World) -> None:
    now = datetime.now(UTC)
    later = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        starts_at=now + timedelta(hours=1),
    )
    thread = await dm_thread(world, "link", "link", "link")
    assert await world.run("dm", thread.message_ids[0], now=now) is Outcome.NO_MATCH
    assert await world.run("dm", thread.message_ids[1], now=now + timedelta(hours=2)) is (
        Outcome.FIRED
    )
    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE automations SET ends_at = :t, cooldown_hours = 0 WHERE id = :id"),
            {"t": now + timedelta(hours=3), "id": later},
        )
    assert await world.run("dm", thread.message_ids[2], now=now + timedelta(hours=4)) is (
        Outcome.NO_MATCH
    )


async def test_an_ai_reply_automation_sends_nothing_yet(world: World) -> None:
    await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        action="ai_reply",
        message_text=None,
        ai_instructions="Answer from the price list",
    )
    thread = await dm_thread(world, "link?")
    assert await world.run("dm", thread.message_ids[0]) is Outcome.FIRED
    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("failed", "ai_reply_unavailable")
    assert await outbound(world) == []
    [msg] = await world.rows("SELECT automation_handled FROM messages")
    assert msg["automation_handled"] is False


async def test_a_failed_send_fails_the_run_and_a_retry_restores_it(world: World) -> None:
    await make_automation(world.engine, workspace_id=world.wid, account_id=world.account_id)
    thread = await dm_thread(world, "link")
    await world.run("dm", thread.message_ids[0])
    [dm] = await outbound(world)

    outbox.fail_next("platform_rejected", kind="send")
    assert await world.send(dm["id"]) is Delivery.FAILED
    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("failed", "platform_rejected")
    assert run["error_message"].startswith("Instagram rejected this")

    async with world.engine.begin() as conn:
        await conn.execute(
            text("UPDATE messages SET status = 'queued' WHERE id = :id"), {"id": dm["id"]}
        )
    assert await world.send(dm["id"]) is Delivery.SENT
    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("sent", None)


async def test_a_refused_dm_is_a_failed_run(world: World) -> None:
    """The send pipeline's rules apply (TR-PL-10): the run says why nothing was sent."""
    await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        message_text="x" * 700,
        message_buttons=[{"title": "Shop", "url": "https://maple.example"}],
    )
    thread = await dm_thread(world, "link")
    assert await world.run("dm", thread.message_ids[0]) is Outcome.FIRED
    run = await world.run_row()
    assert (run["result"], run["error_code"]) == ("failed", "validation_error")
    assert "640 characters" in run["error_message"]
    assert await outbound(world) == []


async def test_a_reply_within_24_hours_is_counted_once(world: World) -> None:
    await make_automation(world.engine, workspace_id=world.wid, account_id=world.account_id)
    ref = f"igsid_{uuid.uuid4().hex[:10]}"
    thread = await dm_thread(world, "link", contact_ref=ref)
    await world.run("dm", thread.message_ids[0])
    [dm] = await outbound(world)
    await world.send(dm["id"])

    async def customer_writes(text_: str, at: datetime) -> None:
        event = InboundMessage(
            account_ref="sandbox",
            occurred_at=at,
            contact_ref=ref,
            contact_name=None,
            platform_message_id=f"mid_{uuid.uuid4().hex}",
            kind="text",
            text=text_,
        )
        with workspace_scope(world.wid):
            async with world.maker() as session:
                acct = await accounts.get(session, world.account_id)
                assert acct is not None
                await ingest(session, acct, [event])
                await session.commit()

    first_reply = datetime.now(UTC) + timedelta(minutes=5)
    await customer_writes("Thanks!", first_reply)
    await customer_writes("One more question", first_reply + timedelta(minutes=5))
    run = await world.run_row()
    assert run["contact_replied_at"] == first_reply


async def test_a_reply_after_24_hours_is_not_counted(world: World) -> None:
    await make_automation(world.engine, workspace_id=world.wid, account_id=world.account_id)
    ref = f"igsid_{uuid.uuid4().hex[:10]}"
    thread = await dm_thread(world, "link", contact_ref=ref)
    await world.run("dm", thread.message_ids[0], now=datetime.now(UTC) - timedelta(hours=25))
    [dm] = await outbound(world)
    await world.send(dm["id"])
    event = InboundMessage(
        account_ref="sandbox",
        occurred_at=datetime.now(UTC),
        contact_ref=ref,
        contact_name=None,
        platform_message_id=f"mid_{uuid.uuid4().hex}",
        kind="text",
        text="Thanks",
    )
    with workspace_scope(world.wid):
        async with world.maker() as session:
            acct = await accounts.get(session, world.account_id)
            assert acct is not None
            await ingest(session, acct, [event])
            await session.commit()
    assert (await world.run_row())["contact_replied_at"] is None


async def test_ingest_enqueues_a_run_for_new_customer_dms_only(
    world: World, engine: AsyncEngine, redis: Redis
) -> None:
    ig = await make_account(engine, world.wid, platform_account_id=ACCOUNT_REF)
    maker = sessions(engine)

    # No active DM automation on the account: no job.
    await deliver(maker, redis, "webhook_message_text.json")
    assert await jobs("run_automation") == []

    await make_automation(engine, workspace_id=world.wid, account_id=ig, keywords=("sourdough",))
    await deliver(maker, redis, "webhook_message_reply.json")
    [job] = await jobs("run_automation")
    [msg] = await world.rows(
        "SELECT id FROM messages WHERE direction = 'inbound' ORDER BY created_at DESC LIMIT 1"
    )
    assert job["queueing_lock"] == f"automation:dm:{msg['id']}"
    assert job["args"]["kind"] == "dm"
    assert job["queue_name"] == "interactive"

    await deliver(maker, redis, "webhook_echo.json")  # the business's own reply
    assert len(await jobs("run_automation")) == 1
