"""T3.3: fetch_contact_profile (TR-PL-06) and ingest_media (TR-MED-03) against the test database,
with Instagram's Graph and CDN and Cloudinary mocked."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.models.connections import SocialAccount
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.events import InboundMediaRef, InboundMessage
from socialhood.services.ingest import ingest
from socialhood.services.ingest_followups import (
    copy_inbound_media,
    profile_cache_key,
    refresh_contact_profile,
)
from socialhood.settings import Settings
from tests.support.inbox import make_account, make_workspace
from tests.support.ingest import ACCOUNT_REF, CUSTOMER, rows, sessions, stream
from tests.support.instagram import GRAPH, fixture

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)
CDN = "https://lookaside.fbsbx.com/ig_messaging_cdn/?asset_id=77"
UPLOAD = "https://api.cloudinary.com/v1_1/demo/auto/upload"


@dataclass
class Setup:
    workspace_id: uuid.UUID
    account_id: uuid.UUID
    account_ref: str
    deps: PlatformDeps


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def storage_settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(
        update={
            "cloudinary_cloud_name": "demo",
            "cloudinary_api_key": "123",
            "cloudinary_api_secret": SecretStr("shh"),
        }
    )


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as router:
        yield router


async def _setup(
    engine: AsyncEngine, http: httpx.AsyncClient, settings: Settings, *, sandbox: bool
) -> Setup:
    wid = await make_workspace(engine)
    ref = f"sandbox_{uuid.uuid4().hex[:8]}" if sandbox else ACCOUNT_REF
    account_id = await make_account(engine, wid, platform_account_id=ref)
    deps = deps_from(http, settings)
    async with engine.begin() as conn:
        await conn.execute(
            sql("UPDATE social_accounts SET access_token_enc = :t WHERE id = :i"),
            {"t": deps.cipher.encrypt("IGQVJtoken"), "i": account_id},
        )
    return Setup(wid, account_id, ref, deps)


@pytest.fixture
async def sandbox(
    engine: AsyncEngine,
    http: httpx.AsyncClient,
    storage_settings: Settings,
    clean_db: None,
    queue: None,
) -> Setup:
    return await _setup(engine, http, storage_settings, sandbox=True)


@pytest.fixture
async def instagram_account(
    engine: AsyncEngine,
    http: httpx.AsyncClient,
    storage_settings: Settings,
    clean_db: None,
    queue: None,
) -> Setup:
    return await _setup(engine, http, storage_settings, sandbox=False)


async def inbound(
    engine: AsyncEngine, setup: Setup, *, kind: Any = "image", contact_ref: str = CUSTOMER
) -> tuple[uuid.UUID, str]:
    """An inbound message with one attachment, through ingest: (message id, attachment id)."""
    event = InboundMessage(
        account_ref=setup.account_ref,
        occurred_at=NOW,
        contact_ref=contact_ref,
        contact_name=None,
        platform_message_id=f"mid_{uuid.uuid4().hex}",
        kind="story_mention" if kind == "story" else kind,
        text=None,
        attachments=(InboundMediaRef(kind=kind, url=CDN),),
    )
    with workspace_scope(setup.workspace_id):
        async with sessions(engine)() as session:
            acct = await session.get(SocialAccount, setup.account_id)
            assert acct is not None
            result = await ingest(session, acct, [event], now=NOW)
            await session.commit()
    [message_id] = result.created_message_ids
    [row] = await rows(engine, "SELECT attachments FROM messages WHERE id = :i", i=message_id)
    return message_id, row["attachments"][0]["id"]


def uploaded(setup: Setup, attachment_id: str) -> dict[str, Any]:
    public_id = f"ws/{setup.workspace_id}/inbound/2026/09/{attachment_id}"
    return {
        "public_id": public_id,
        "resource_type": "image",
        "format": "png",
        "secure_url": f"https://res.cloudinary.com/demo/image/upload/v1/{public_id}.png",
        "bytes": 68,
        "width": 1,
        "height": 1,
    }


async def attachment(engine: AsyncEngine, message_id: uuid.UUID) -> dict[str, Any]:
    [row] = await rows(engine, "SELECT attachments FROM messages WHERE id = :i", i=message_id)
    return dict(row["attachments"][0])


# ---------------------------------------------------------------- ingest_media


async def test_the_attachment_switches_to_the_stored_copy(
    engine: AsyncEngine, redis: Redis, sandbox: Setup, mock: respx.MockRouter
) -> None:
    message_id, attachment_id = await inbound(engine, sandbox)
    route = mock.post(UPLOAD).respond(200, json=uploaded(sandbox, attachment_id))

    copy = copy_inbound_media(
        sessions(engine),
        redis,
        sandbox.deps,
        workspace_id=sandbox.workspace_id,
        message_id=message_id,
        attachment_id=attachment_id,
        now=NOW,
    )
    assert await copy is True

    stored = await attachment(engine, message_id)
    body = uploaded(sandbox, attachment_id)
    assert stored["url"] == body["secure_url"]
    assert stored["platform_url"] == CDN  # kept, private
    assert (stored["mime_type"], stored["size_bytes"], stored["width"]) == ("image/png", 68, 1)
    [asset] = await rows(engine, "SELECT * FROM media_assets")
    assert str(asset["id"]) == stored["asset_id"]
    assert (asset["purpose"], asset["public_id"]) == ("inbound", body["public_id"])

    sent = route.calls.last.request.content.decode(errors="replace")
    assert f"ws/{sandbox.workspace_id}/inbound/2026/09" in sent
    [(kind, payload)] = await stream(redis, sandbox.workspace_id)
    assert kind == "message.updated"
    assert payload["message"]["attachments"][0]["url"] == body["secure_url"]
    assert "platform_url" not in payload["message"]["attachments"][0]

    again = await copy_inbound_media(
        sessions(engine),
        redis,
        sandbox.deps,
        workspace_id=sandbox.workspace_id,
        message_id=message_id,
        attachment_id=attachment_id,
    )
    assert again is False
    assert route.call_count == 1


async def test_without_storage_the_platform_url_stays(
    engine: AsyncEngine, redis: Redis, sandbox: Setup, api_settings: Settings
) -> None:
    message_id, attachment_id = await inbound(engine, sandbox)
    unconfigured = PlatformDeps(sandbox.deps.http, sandbox.deps.cipher, api_settings)
    assert not await copy_inbound_media(
        sessions(engine),
        redis,
        unconfigured,
        workspace_id=sandbox.workspace_id,
        message_id=message_id,
        attachment_id=attachment_id,
    )
    assert (await attachment(engine, message_id))["url"] == CDN


async def test_story_media_is_never_copied(
    engine: AsyncEngine, redis: Redis, sandbox: Setup, mock: respx.MockRouter
) -> None:
    message_id, attachment_id = await inbound(engine, sandbox, kind="story")
    route = mock.post(UPLOAD).respond(200, json=uploaded(sandbox, attachment_id))
    assert not await copy_inbound_media(
        sessions(engine),
        redis,
        sandbox.deps,
        workspace_id=sandbox.workspace_id,
        message_id=message_id,
        attachment_id=attachment_id,
    )
    assert route.call_count == 0


async def test_instagram_media_is_downloaded_then_stored(
    engine: AsyncEngine, redis: Redis, instagram_account: Setup, mock: respx.MockRouter
) -> None:
    setup = instagram_account
    message_id, attachment_id = await inbound(engine, setup)
    cdn = mock.get(CDN).respond(
        200, content=b"\xff\xd8jpeg", headers={"content-type": "image/jpeg"}
    )
    mock.post(UPLOAD).respond(200, json=uploaded(setup, attachment_id))
    assert await copy_inbound_media(
        sessions(engine),
        redis,
        setup.deps,
        workspace_id=setup.workspace_id,
        message_id=message_id,
        attachment_id=attachment_id,
        now=NOW,
    )
    assert cdn.call_count == 1
    assert (await attachment(engine, message_id))["mime_type"] == "image/jpeg"


async def test_expired_media_is_dropped_and_an_outage_retries(
    engine: AsyncEngine, redis: Redis, instagram_account: Setup, mock: respx.MockRouter
) -> None:
    setup = instagram_account
    message_id, attachment_id = await inbound(engine, setup)
    route = mock.get(CDN)

    async def run() -> bool:
        return await copy_inbound_media(
            sessions(engine),
            redis,
            setup.deps,
            workspace_id=setup.workspace_id,
            message_id=message_id,
            attachment_id=attachment_id,
        )

    route.respond(404)
    assert await run() is False
    route.respond(503)
    with pytest.raises(PlatformError) as caught:
        await run()
    assert caught.value.retryable
    assert (await attachment(engine, message_id))["url"] == CDN


# ---------------------------------------------------------------- fetch_contact_profile


async def test_the_sandbox_profile_fills_the_contact(
    engine: AsyncEngine, redis: Redis, sandbox: Setup
) -> None:
    await inbound(engine, sandbox, contact_ref="sandbox_user_ab12")
    [contact] = await rows(engine, "SELECT id FROM contacts")
    assert await stream(redis, sandbox.workspace_id) == []  # ingest's events were not published

    assert await refresh_contact_profile(
        sessions(engine),
        redis,
        sandbox.deps,
        workspace_id=sandbox.workspace_id,
        contact_id=contact["id"],
        now=NOW,
    )
    [row] = await rows(engine, "SELECT * FROM contacts")
    assert (row["display_name"], row["username"]) == ("Sandbox customer ab12", "customer_ab12")
    assert row["profile_fetched_at"] == NOW
    [(kind, payload)] = await stream(redis, sandbox.workspace_id)
    assert kind == "conversation.updated"
    assert payload["conversation"]["contact"]["username"] == "customer_ab12"
    assert await redis.ttl(profile_cache_key(sandbox.account_id, "sandbox_user_ab12")) > 0


async def test_an_instagram_profile_is_fetched_once_a_day(
    engine: AsyncEngine, redis: Redis, instagram_account: Setup, mock: respx.MockRouter
) -> None:
    setup = instagram_account
    await inbound(engine, setup)
    [contact] = await rows(engine, "SELECT id FROM contacts")
    route = mock.get(f"{GRAPH}/{setup.deps.settings.ig_graph_version}/{CUSTOMER}").respond(
        200, json=fixture("user_profile.json")
    )
    for _ in range(2):
        await refresh_contact_profile(
            sessions(engine),
            redis,
            setup.deps,
            workspace_id=setup.workspace_id,
            contact_id=contact["id"],
        )
    assert route.call_count == 1  # the second run reads the 24 h cache (TR-PL-06)
    [row] = await rows(engine, "SELECT * FROM contacts")
    assert (row["display_name"], row["username"]) == ("Priya Shah", "priya.shah")
    assert row["profile_picture_url"] == "https://scontent.cdninstagram.com/v/priya.jpg"


async def test_a_refused_profile_waits_a_week_and_an_outage_retries(
    engine: AsyncEngine, redis: Redis, instagram_account: Setup, mock: respx.MockRouter
) -> None:
    setup = instagram_account
    await inbound(engine, setup)
    [contact] = await rows(engine, "SELECT id FROM contacts")
    route = mock.get(f"{GRAPH}/{setup.deps.settings.ig_graph_version}/{CUSTOMER}")

    async def run() -> bool:
        return await refresh_contact_profile(
            sessions(engine),
            redis,
            setup.deps,
            workspace_id=setup.workspace_id,
            contact_id=contact["id"],
            now=NOW,
        )

    route.respond(500, json={"error": {"code": 2, "message": "Service temporarily unavailable"}})
    with pytest.raises(PlatformError):
        await run()
    [row] = await rows(engine, "SELECT * FROM contacts")
    assert row["profile_fetched_at"] is None  # nothing written before a retry (TR-JOB-04)

    route.respond(400, json={"error": {"code": 230, "message": "User consent is required"}})
    assert await run() is True
    [row] = await rows(engine, "SELECT * FROM contacts")
    assert (row["profile_fetched_at"], row["display_name"]) == (NOW, None)
