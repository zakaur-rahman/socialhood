"""T3.12: WhatsApp webhook intake (TR-WH-01…05) and processing: messages and reactions go to
ingest, delivery statuses move our outbound messages (F-06, F-07)."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.jobs.app import app as jobs_app
from socialhood.models.connections import SocialAccount
from socialhood.models.platform import WebhookStatus
from socialhood.platforms.events import InboundEvent, InboundMessage, Reaction
from socialhood.realtime.events import stream_key
from socialhood.repositories.webhook_events import MAX_ATTEMPTS
from socialhood.services import ingest
from socialhood.services.ingest import IngestResult
from socialhood.services.webhook_handlers.whatsapp import StatusNotMatched
from socialhood.services.webhook_processing import process_event
from socialhood.settings import Settings
from tests.support.api import IG_APP_SECRET, IG_VERIFY_TOKEN, META_APP_SECRET
from tests.support.inbox import make_account, make_thread, make_workspace
from tests.support.instagram import fixture, hub_signature
from tests.support.whatsapp import (
    CUSTOMER,
    PHONE_NUMBER_ID,
    WA_VERIFY_TOKEN,
    signed_delivery,
    with_whatsapp,
)

URL = "/webhooks/whatsapp"
SENT = "wamid.OUTBOUND000000000000000000000000000000001"
FAILED = "wamid.OUTBOUND000000000000000000000000000000002"


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return with_whatsapp(api_settings)


class FakeIngest:
    """Stands in for services/ingest.ingest (T3.2) and records what it was given."""

    def __init__(self) -> None:
        self.calls: list[tuple[SocialAccount, list[InboundEvent]]] = []
        self.result = IngestResult(created_message_ids=[uuid.uuid4()])

    async def __call__(
        self,
        session: AsyncSession,
        acct: SocialAccount,
        events: Sequence[InboundEvent],
        *,
        now: datetime | None = None,
    ) -> IngestResult:
        self.calls.append((acct, list(events)))
        return self.result


@pytest.fixture
def fake_ingest(monkeypatch: pytest.MonkeyPatch) -> FakeIngest:
    fake = FakeIngest()
    monkeypatch.setattr(ingest, "ingest", fake)
    return fake


async def stored(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT id, provider, dedupe_key, event_type, status, attempts, last_error,"
                " workspace_id, platform_account_id FROM webhook_events"
                " ORDER BY received_at, dedupe_key"
            )
        )
        return [dict(r._mapping) for r in result]


async def event_for(engine: AsyncEngine, key_part: str) -> dict[str, Any]:
    return next(e for e in await stored(engine) if key_part in e["dedupe_key"])


async def job_count() -> int:
    row = await jobs_app.connector.execute_query_one_async(
        "SELECT count(*) AS n FROM procrastinate_jobs WHERE task_name = 'process_webhook_event'"
    )
    return int(row["n"])


async def deliver(client: httpx.AsyncClient, body: dict[str, Any]) -> httpx.Response:
    raw, headers = signed_delivery(body)
    return await client.post(URL, content=raw, headers=headers)


async def connected_number(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID]:
    wid = await make_workspace(engine)
    aid = await make_account(engine, wid, platform="whatsapp", platform_account_id=PHONE_NUMBER_ID)
    return wid, aid


async def outbound_messages(engine: AsyncEngine, wid: uuid.UUID, aid: uuid.UUID) -> list[uuid.UUID]:
    """Two messages we sent, with the wamids the statuses fixture names."""
    thread = await make_thread(
        engine,
        workspace_id=wid,
        account_id=aid,
        platform="whatsapp",
        contact_ref=CUSTOMER,
        direction="outbound",
        texts=("Your cake is ready", "Pick it up by 6?"),
    )
    async with engine.begin() as conn:
        for message_id, wamid in zip(thread.message_ids, (SENT, FAILED), strict=True):
            await conn.execute(
                text(
                    "UPDATE messages SET platform_message_id = :w, status = 'sent',"
                    " sent_at = :at WHERE id = :id"
                ),
                {"w": wamid, "at": datetime(2025, 9, 28, 7, 59, tzinfo=UTC), "id": message_id},
            )
    return thread.message_ids


async def message_row(engine: AsyncEngine, message_id: uuid.UUID) -> dict[str, Any]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT status, sent_at, delivered_at, read_at, error_code, error_message"
                " FROM messages WHERE id = :id"
            ),
            {"id": message_id},
        )
        return dict(result.one()._mapping)


def at(seconds: int) -> datetime:
    return datetime.fromtimestamp(seconds, UTC)


# ---------------------------------------------------------------- intake


async def test_verification_echoes_the_challenge(client: httpx.AsyncClient) -> None:
    params = {"hub.mode": "subscribe", "hub.verify_token": WA_VERIFY_TOKEN, "hub.challenge": "42"}
    response = await client.get(URL, params=params)
    assert (response.status_code, response.text) == (200, "42")
    for token in ("nope", IG_VERIFY_TOKEN):
        wrong = await client.get(URL, params={**params, "hub.verify_token": token})
        assert wrong.status_code == 403


async def test_a_delivery_is_stored_once_per_event_and_queued(
    client: httpx.AsyncClient, engine: AsyncEngine, queue: None
) -> None:
    first = await deliver(client, fixture("whatsapp_webhook_statuses.json"))
    again = await deliver(client, fixture("whatsapp_webhook_statuses.json"))  # Meta retries
    assert (first.status_code, again.status_code) == (200, 200)

    rows = await stored(engine)
    assert len(rows) == 4
    assert {(r["provider"], r["event_type"], r["platform_account_id"]) for r in rows} == {
        ("whatsapp", "status", PHONE_NUMBER_ID)
    }
    assert await job_count() == 4


@pytest.mark.parametrize(
    "signature",
    [None, "sha256=" + "0" * 64, "instagram"],
    ids=["missing", "wrong", "instagram-secret"],
)
async def test_an_unsigned_delivery_is_refused_and_not_stored(
    client: httpx.AsyncClient, engine: AsyncEngine, signature: str | None
) -> None:
    raw = json.dumps(fixture("whatsapp_webhook_text.json")).encode()
    headers = {"content-type": "application/json"}
    if signature == "instagram":
        headers["x-hub-signature-256"] = hub_signature(raw, IG_APP_SECRET)
    elif signature:
        headers["x-hub-signature-256"] = signature
    response = await client.post(URL, content=raw, headers=headers)
    assert response.status_code == 401
    assert await stored(engine) == []


async def test_a_signed_but_unreadable_body_is_kept_and_acknowledged(
    app: FastAPI, client: httpx.AsyncClient, engine: AsyncEngine, queue: None
) -> None:
    raw = b"{not json"
    response = await client.post(
        URL, content=raw, headers={"x-hub-signature-256": hub_signature(raw, META_APP_SECRET)}
    )
    assert response.status_code == 200
    [row] = await stored(engine)
    assert (row["event_type"], row["dedupe_key"][:11]) == ("invalid", "wa:invalid:")
    assert await process_event(app.state.sessionmaker, row["id"]) is WebhookStatus.IGNORED


# ---------------------------------------------------------------- messages


async def test_a_message_goes_to_ingest_for_its_number(
    app: FastAPI,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    queue: None,
    fake_ingest: FakeIngest,
) -> None:
    wid, aid = await connected_number(engine)
    await deliver(client, fixture("whatsapp_webhook_text.json"))
    [row] = await stored(engine)

    assert await process_event(app.state.sessionmaker, row["id"]) is WebhookStatus.PROCESSED
    [(acct, events)] = fake_ingest.calls
    assert acct.id == aid
    [event] = events
    assert isinstance(event, InboundMessage)
    assert (event.contact_ref, event.contact_name, event.text) == (
        CUSTOMER,
        "Priya Shah",
        "Do you ship to Pune?",
    )
    [row] = await stored(engine)
    assert (row["status"], row["workspace_id"]) == ("processed", wid)


async def test_reactions_go_to_ingest_and_system_messages_are_ignored(
    app: FastAPI,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    queue: None,
    fake_ingest: FakeIngest,
) -> None:
    await connected_number(engine)
    await deliver(client, fixture("whatsapp_webhook_other.json"))
    reaction = await event_for(engine, "REACTION00000000000000000000000000000004")
    system = await event_for(engine, "SYSTEM")

    assert await process_event(app.state.sessionmaker, reaction["id"]) is WebhookStatus.PROCESSED
    assert await process_event(app.state.sessionmaker, system["id"]) is WebhookStatus.IGNORED
    [(_, [event])] = fake_ingest.calls
    assert isinstance(event, Reaction)
    assert (event.platform_message_id, event.emoji) == (SENT, "❤️")
    system = await event_for(engine, "SYSTEM")
    assert system["last_error"] == "system message"


async def test_what_ingest_ignores_marks_the_event_ignored(
    app: FastAPI,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    queue: None,
    fake_ingest: FakeIngest,
) -> None:
    await connected_number(engine)
    fake_ingest.result = IngestResult(ignored=["reaction to an unknown message"])
    await deliver(client, fixture("whatsapp_webhook_text.json"))
    [row] = await stored(engine)
    assert await process_event(app.state.sessionmaker, row["id"]) is WebhookStatus.IGNORED
    [row] = await stored(engine)
    assert row["last_error"] == "reaction to an unknown message"


async def test_other_fields_and_unknown_numbers_are_ignored(
    app: FastAPI,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    queue: None,
    fake_ingest: FakeIngest,
) -> None:
    await deliver(client, fixture("whatsapp_webhook_template_status.json"))
    await deliver(client, fixture("whatsapp_webhook_text.json"))
    for row in await stored(engine):
        assert await process_event(app.state.sessionmaker, row["id"]) is WebhookStatus.IGNORED
    reasons = {r["event_type"]: r["last_error"] for r in await stored(engine)}
    assert reasons == {
        "message_template_status_update": "message_template_status_update events are not used",
        "message": "unknown or disconnected account",
    }
    assert fake_ingest.calls == []


# ---------------------------------------------------------------- delivery statuses


async def test_statuses_move_our_messages_forward_and_publish(
    app: FastAPI,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    wid, aid = await connected_number(engine)
    sent_id, failed_id = await outbound_messages(engine, wid, aid)
    await deliver(client, fixture("whatsapp_webhook_statuses.json"))

    for part in (f"{SENT}:sent", f"{SENT}:delivered", f"{SENT}:read", f"{FAILED}:failed"):
        row = await event_for(engine, part)
        await process_event(app.state.sessionmaker, row["id"], redis)

    assert await message_row(engine, sent_id) == {
        "status": "read",
        "sent_at": datetime(2025, 9, 28, 7, 59, tzinfo=UTC),  # the send job's, kept
        "delivered_at": at(1759046502),
        "read_at": at(1759046530),
        "error_code": None,
        "error_message": None,
    }
    failed = await message_row(engine, failed_id)
    assert (failed["status"], failed["error_code"]) == ("failed", "reply_window_closed")
    assert failed["error_message"].startswith("Message failed to send because more than 24 hours")

    outcomes = {r["dedupe_key"].rsplit(":", 1)[1]: r for r in await stored(engine)}
    assert (outcomes["sent"]["status"], outcomes["sent"]["last_error"]) == (
        "ignored",
        "sent is not newer",
    )
    assert {outcomes[s]["status"] for s in ("delivered", "read", "failed")} == {"processed"}

    published = [
        (entry["type"], json.loads(entry["data"])["message"])
        for _, entry in await redis.xrange(stream_key(wid))
    ]
    assert [(kind, m["id"], m["status"]) for kind, m in published] == [
        ("message.updated", str(sent_id), "delivered"),
        ("message.updated", str(sent_id), "read"),
        ("message.updated", str(failed_id), "failed"),
    ]
    assert published[2][1]["error"]["code"] == "reply_window_closed"


async def test_a_late_status_changes_nothing(
    app: FastAPI, client: httpx.AsyncClient, engine: AsyncEngine, queue: None
) -> None:
    wid, aid = await connected_number(engine)
    sent_id, _ = await outbound_messages(engine, wid, aid)
    await deliver(client, fixture("whatsapp_webhook_statuses.json"))
    for part in (f"{SENT}:read", f"{SENT}:delivered"):
        await process_event(app.state.sessionmaker, (await event_for(engine, part))["id"])

    row = await message_row(engine, sent_id)
    assert (row["status"], row["delivered_at"], row["read_at"]) == (
        "read",
        at(1759046530),
        at(1759046530),
    )
    late = await event_for(engine, f"{SENT}:delivered")
    assert (late["status"], late["last_error"]) == ("ignored", "delivered is not newer")


def one_recent_status(wamid: str, status: str = "delivered") -> dict[str, Any]:
    body = fixture("whatsapp_webhook_statuses.json")
    value = body["entry"][0]["changes"][0]["value"]
    value["statuses"] = [
        {**value["statuses"][1], "id": wamid, "status": status, "timestamp": str(int(time.time()))}
    ]
    return body


async def test_a_status_that_beats_the_send_job_is_retried(
    app: FastAPI, client: httpx.AsyncClient, engine: AsyncEngine, queue: None
) -> None:
    """Meta can report a status before the send job has stored the wamid."""
    wid, aid = await connected_number(engine)
    sent_id, _ = await outbound_messages(engine, wid, aid)
    await deliver(client, one_recent_status("wamid.NOTSTOREDYET"))
    [row] = await stored(engine)

    with pytest.raises(StatusNotMatched):
        await process_event(app.state.sessionmaker, row["id"])
    [row] = await stored(engine)
    assert (row["status"], row["attempts"]) == ("received", 1)

    async with engine.begin() as conn:  # the send job commits
        await conn.execute(
            text("UPDATE messages SET platform_message_id = 'wamid.NOTSTOREDYET' WHERE id = :id"),
            {"id": sent_id},
        )
    assert await process_event(app.state.sessionmaker, row["id"]) is WebhookStatus.PROCESSED
    assert (await message_row(engine, sent_id))["status"] == "delivered"


async def test_a_status_for_a_message_we_never_sent_is_ignored(
    app: FastAPI, client: httpx.AsyncClient, engine: AsyncEngine, queue: None
) -> None:
    await connected_number(engine)
    await deliver(client, fixture("whatsapp_webhook_statuses.json"))  # old: no retry
    await deliver(client, one_recent_status("wamid.SENTBYANOTHERTOOL"))
    recent = await event_for(engine, "SENTBYANOTHERTOOL")
    async with engine.begin() as conn:  # the last attempt gives up instead of failing
        await conn.execute(
            text("UPDATE webhook_events SET attempts = :n WHERE id = :id"),
            {"n": MAX_ATTEMPTS - 1, "id": recent["id"]},
        )
    for row in await stored(engine):
        assert await process_event(app.state.sessionmaker, row["id"]) is WebhookStatus.IGNORED
    assert {r["last_error"] for r in await stored(engine)} == {"no outbound message with this id"}
