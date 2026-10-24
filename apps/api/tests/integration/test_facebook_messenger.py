"""GR-29: Messenger on a Facebook Page - the Page webhook (verification, signature, batches), the
inbox (messages, echoes, deliveries, reads, postbacks, referrals), replying within the window,
and what a Page cannot send. The sandbox serves the Page, so no Meta call is made."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.tasks import send as send_tasks
from socialhood.models.platform import WebhookStatus
from socialhood.platforms.deps import deps_from
from socialhood.platforms.sandbox import outbox
from socialhood.services.webhook_handlers import instagram as instagram_handler
from socialhood.services.webhook_processing import process_event
from socialhood.settings import Settings
from tests.support.api import Clerk, sign_in
from tests.support.facebook import (
    FB_VERIFY_TOKEN,
    PERSON,
    deliver_page,
    hub_signature,
    page_delivery,
    page_message,
    signed_delivery,
    with_facebook,
)
from tests.support.inbox import make_asset, make_thread
from tests.support.ingest import sessions
from tests.support.instagram import hub_signature as ig_signature
from tests.support.sending import (
    Setup,
    clean_outbox,
    context,
    conversation_row,
    outbound_rows,
    post_message,
    use_app_runtime,
)

URL = "/webhooks/facebook"
CONTACT = "7001234567890999"


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return with_facebook(api_settings)


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture(autouse=True)
def _deps(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Webhook events are processed with the test app's HTTP client and settings."""
    deps = deps_from(app.state.http, app.state.settings)
    monkeypatch.setattr(instagram_handler, "platform_deps", lambda: deps)


async def sandbox_page(
    client: httpx.AsyncClient, clerk: Clerk, *, email: str = "owner@example.com"
) -> tuple[str, str, str, str]:
    """(clerk id, workspace id, account id, the Page's id) of a signed-in owner's sandbox Page."""
    clerk_id, me = await sign_in(client, clerk, email=email, first_name="Asha")
    wid = me["workspaces"][0]["id"]
    created = await client.post(
        f"/v1/w/{wid}/dev/sandbox/accounts",
        json={"platform": "facebook"},
        headers=clerk.headers(clerk_id),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    return clerk_id, wid, body["id"], f"sandbox_{body['username'].split('.')[-1]}"


async def page_ref(engine: AsyncEngine, account_id: str) -> str:
    async with engine.connect() as conn:
        row = await conn.execute(
            text("SELECT platform_account_id FROM social_accounts WHERE id = :id"),
            {"id": account_id},
        )
        return str(row.scalar_one())


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


@pytest.fixture
async def page(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Setup:
    """An owner, a sandbox Facebook Page and a Messenger conversation whose customer just wrote."""
    clerk_id, wid, account_id, _ = await sandbox_page(client, clerk)
    thread = await make_thread(
        engine,
        workspace_id=wid,
        account_id=account_id,
        platform="facebook",
        last_inbound_at=None,
    )
    return Setup(clerk_id, wid, account_id, thread, clerk.headers(clerk_id))


# ---------------------------------------------------------------- the Page webhook route


async def test_the_page_webhook_answers_the_verification_challenge(
    client: httpx.AsyncClient,
) -> None:
    params = {"hub.mode": "subscribe", "hub.verify_token": FB_VERIFY_TOKEN, "hub.challenge": "42"}
    ok = await client.get(URL, params=params)
    assert (ok.status_code, ok.text) == (200, "42")
    wrong = await client.get(URL, params={**params, "hub.verify_token": "nope"})
    assert wrong.status_code == 403


async def test_a_signed_batch_is_stored_once_per_event_and_queued(
    client: httpx.AsyncClient, engine: AsyncEngine, queue: None
) -> None:
    body = page_delivery(
        "109876543210001",
        messaging=[
            {
                "sender": {"id": PERSON},
                "recipient": {"id": "109876543210001"},
                "timestamp": int(time.time() * 1000),
                "message": {"mid": "m_1", "text": "hi"},
            },
            {
                "sender": {"id": PERSON},
                "recipient": {"id": "109876543210001"},
                "timestamp": int(time.time() * 1000),
                "delivery": {"mids": ["m_a", "m_b"], "watermark": int(time.time() * 1000)},
            },
        ],
    )
    raw, headers = signed_delivery(body)
    first = await client.post(URL, content=raw, headers=headers)
    again = await client.post(URL, content=raw, headers=headers)  # Meta re-delivers
    assert (first.status_code, again.status_code) == (200, 200)
    stored = await rows(
        engine, "SELECT provider, event_type, platform_account_id FROM webhook_events"
    )
    assert sorted(e["event_type"] for e in stored) == ["delivery", "delivery", "message"]
    assert {(e["provider"], e["platform_account_id"]) for e in stored} == {
        ("facebook", "109876543210001")
    }
    count = await jobs_app.connector.execute_query_one_async(
        "SELECT count(*) AS n FROM procrastinate_jobs WHERE task_name = 'process_webhook_event'"
    )
    assert count["n"] == 3


@pytest.mark.parametrize(
    "signature",
    [None, "sha256=" + "0" * 64, ig_signature(b"{}")],
    ids=["missing", "wrong", "instagram-secret"],
)
async def test_an_unsigned_or_wrongly_signed_delivery_is_refused(
    client: httpx.AsyncClient, engine: AsyncEngine, signature: str | None
) -> None:
    raw = b"{}"
    headers = {"content-type": "application/json"}
    if signature:
        headers["x-hub-signature-256"] = signature
    response = await client.post(URL, content=raw, headers=headers)
    assert response.status_code == 401
    assert await rows(engine, "SELECT id FROM webhook_events") == []


async def test_unreadable_but_signed_bodies_are_kept_and_acknowledged(
    client: httpx.AsyncClient, engine: AsyncEngine, queue: None
) -> None:
    raw = b"not json"
    headers = {"x-hub-signature-256": hub_signature(raw)}
    assert (await client.post(URL, content=raw, headers=headers)).status_code == 200
    [event] = await rows(engine, "SELECT event_type FROM webhook_events")
    assert event["event_type"] == "invalid"


async def test_an_event_for_an_unknown_page_is_ignored(
    client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    statuses = await deliver_page(sessions(engine), redis, page_message("111122223333"))
    assert statuses == [WebhookStatus.IGNORED]
    assert await rows(engine, "SELECT id FROM conversations") == []


# ---------------------------------------------------------------- the inbox


async def test_a_message_to_the_page_starts_a_facebook_conversation(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    clerk_id, wid, account_id, _ = await sandbox_page(client, clerk)
    ref = await page_ref(engine, account_id)
    maker = sessions(engine)

    assert await deliver_page(maker, redis, page_message(ref, sender=CONTACT, mid="m_1")) == [
        WebhookStatus.PROCESSED
    ]
    [contact] = await rows(engine, "SELECT * FROM contacts")
    assert contact["platform_user_id"] == CONTACT
    [conv] = await rows(engine, "SELECT * FROM conversations")
    assert (conv["platform"], conv["social_account_id"]) == ("facebook", uuid.UUID(account_id))
    assert conv["awaiting_reply"] is True
    [message] = await rows(engine, "SELECT * FROM messages")
    assert (message["direction"], message["text"], message["platform_message_id"]) == (
        "inbound",
        "Do you deliver on Sundays?",
        "m_1",
    )

    # A re-delivery stores nothing new.
    again = await deliver_page(maker, redis, page_message(ref, sender=CONTACT, mid="m_1"), copy="x")
    assert again == [WebhookStatus.IGNORED]
    assert len(await rows(engine, "SELECT id FROM messages")) == 1

    headers = clerk.headers(clerk_id)
    listed = await client.get(f"/v1/w/{wid}/conversations?platform=facebook", headers=headers)
    assert [c["platform"] for c in listed.json()["items"]] == ["facebook"]
    other = await client.get(f"/v1/w/{wid}/conversations?platform=instagram", headers=headers)
    assert other.json()["items"] == []


async def test_the_sandbox_injects_page_events_through_the_same_intake(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    clerk_id, wid, account_id, _ = await sandbox_page(client, clerk)
    injected = await client.post(
        f"/v1/w/{wid}/dev/sandbox/inbound",
        json={"account_id": account_id, "kind": "dm", "text": "Price?", "from_id": CONTACT},
        headers=clerk.headers(clerk_id),
    )
    assert (injected.status_code, injected.json()) == (200, {"stored": 1})
    [event] = await rows(engine, "SELECT id, provider FROM webhook_events")
    assert event["provider"] == "facebook"
    assert await process_event(sessions(engine), event["id"], redis) == WebhookStatus.PROCESSED
    [message] = await rows(engine, "SELECT text, direction FROM messages")
    assert (message["text"], message["direction"]) == ("Price?", "inbound")


async def test_the_sandbox_refuses_the_kinds_a_page_does_not_have(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, wid, account_id, _ = await sandbox_page(client, clerk)
    for kind in ("story_reply", "story_like", "story_mention", "live_comment"):
        response = await client.post(
            f"/v1/w/{wid}/dev/sandbox/inbound",
            json={"account_id": account_id, "kind": kind, "text": "x"},
            headers=clerk.headers(clerk_id),
        )
        assert response.status_code == 422, kind
        assert response.json()["errors"][0]["field"] == "kind"


async def test_echoes_deliveries_and_reads_follow_the_pages_own_messages(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    _, _, account_id, _ = await sandbox_page(client, clerk)
    ref = await page_ref(engine, account_id)
    maker = sessions(engine)
    now = int(time.time() * 1000)
    await deliver_page(maker, redis, page_message(ref, sender=CONTACT, mid="m_in"))

    # A reply typed in the Facebook app comes back as an echo: stored as the Page's own message.
    echo = page_delivery(
        ref,
        messaging=[
            {
                "sender": {"id": ref},
                "recipient": {"id": CONTACT},
                "timestamp": now,
                "message": {"mid": "m_native", "text": "Yes, we do!", "is_echo": True},
            }
        ],
    )
    assert await deliver_page(maker, redis, echo) == [WebhookStatus.PROCESSED]
    [native] = await rows(engine, "SELECT * FROM messages WHERE platform_message_id = 'm_native'")
    assert (native["direction"], native["source"]) == ("outbound", "native_app")

    delivered = page_delivery(
        ref,
        messaging=[
            {
                "sender": {"id": CONTACT},
                "recipient": {"id": ref},
                "timestamp": now + 1000,
                "delivery": {"mids": ["m_native"], "watermark": now + 1000},
            }
        ],
    )
    assert await deliver_page(maker, redis, delivered) == [WebhookStatus.PROCESSED]
    [row] = await rows(engine, "SELECT status FROM messages WHERE platform_message_id = 'm_native'")
    assert row["status"] == "delivered"

    seen = page_delivery(
        ref,
        messaging=[
            {
                "sender": {"id": CONTACT},
                "recipient": {"id": ref},
                "timestamp": now + 5000,
                "read": {"watermark": now + 5000},
            }
        ],
    )
    assert await deliver_page(maker, redis, seen) == [WebhookStatus.PROCESSED]
    [row] = await rows(engine, "SELECT status FROM messages WHERE platform_message_id = 'm_native'")
    assert row["status"] == "read"


async def test_a_tapped_get_started_or_ice_breaker_is_the_persons_message(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    _, _, account_id, _ = await sandbox_page(client, clerk)
    ref = await page_ref(engine, account_id)
    body = page_delivery(
        ref,
        messaging=[
            {
                "sender": {"id": CONTACT},
                "recipient": {"id": ref},
                "timestamp": int(time.time() * 1000),
                "postback": {"title": "Opening hours?", "payload": "ib:abc"},
            }
        ],
    )
    assert await deliver_page(sessions(engine), redis, body) == [WebhookStatus.PROCESSED]
    [message] = await rows(engine, "SELECT text, direction FROM messages")
    assert (message["text"], message["direction"]) == ("Opening hours?", "inbound")


async def test_an_m_me_link_opens_the_conversation_with_its_ref(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    _, _, account_id, _ = await sandbox_page(client, clerk)
    ref = await page_ref(engine, account_id)
    maker = sessions(engine)
    opened = page_delivery(
        ref,
        messaging=[
            {
                "sender": {"id": CONTACT},
                "recipient": {"id": ref},
                "timestamp": int(time.time() * 1000),
                "referral": {"ref": "spring", "source": "SHORTLINK", "type": "OPEN_THREAD"},
            }
        ],
    )
    await deliver_page(maker, redis, opened)
    await deliver_page(maker, redis, page_message(ref, "Hi", sender=CONTACT, mid="m_ref"))
    [conv] = await rows(engine, "SELECT entry_source, entry_ref FROM conversations")
    assert (conv["entry_source"], conv["entry_ref"]) == ("link", "spring")


async def test_a_first_message_from_a_click_to_messenger_ad_names_the_ad(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    _, _, account_id, _ = await sandbox_page(client, clerk)
    ref = await page_ref(engine, account_id)
    body = page_message(
        ref,
        "Is this in stock?",
        sender=CONTACT,
        mid="m_ad",
        referral={"source": "ADS", "type": "OPEN_THREAD", "ad_id": "ad_77"},
    )
    await deliver_page(sessions(engine), redis, body)
    [conv] = await rows(engine, "SELECT entry_source, entry_ad_id FROM conversations")
    assert (conv["entry_source"], conv["entry_ad_id"]) == ("ad", "ad_77")


# ---------------------------------------------------------------- replying


async def test_a_reply_is_sent_to_the_person_through_the_pages_adapter(
    client: httpx.AsyncClient,
    clerk: Clerk,
    page: Setup,
    engine: AsyncEngine,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    queue: None,
) -> None:
    use_app_runtime(app, monkeypatch)
    response = await post_message(client, page, text="Yes, we deliver on Sundays")
    assert response.status_code == 202, response.text
    message = response.json()
    await send_tasks.send_message(
        context(),
        message_id=str(message["id"]),
        conversation_id=str(message["conversation_id"]),
        workspace_id=page.wid,
    )
    [sent] = outbox.SENT
    assert sent.message.text == "Yes, we deliver on Sundays"
    [contact] = await rows(engine, "SELECT platform_user_id FROM contacts")
    assert sent.recipient_ref == contact["platform_user_id"]
    [row] = await outbound_rows(engine, page)
    assert (row["status"], row["platform_message_id"]) == ("sent", sent.platform_message_id)


async def test_the_window_is_24_hours_and_the_refusal_says_facebook(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> None:
    clerk_id, wid, account_id, _ = await sandbox_page(client, clerk)
    thread = await make_thread(
        engine,
        workspace_id=wid,
        account_id=account_id,
        platform="facebook",
        last_inbound_at=None,
    )
    old = Setup(clerk_id, wid, account_id, thread, clerk.headers(clerk_id))
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE conversations SET last_inbound_at = now() - interval '8 days'")
        )
    response = await post_message(client, old)
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "reply_window_closed"
    assert response.json()["detail"] == (
        "Facebook allows replies for 24 hours after the customer's last message."
    )
    assert await outbound_rows(engine, old) == []


async def test_human_agent_extends_a_human_reply_to_seven_days(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None, page: Setup
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE conversations SET last_inbound_at = now() - interval '3 days'")
        )
    response = await post_message(client, page)
    assert response.status_code == 202, response.text
    assert response.json()["human_agent_tag"] is True


async def test_a_page_message_may_be_2000_characters(
    client: httpx.AsyncClient, page: Setup, queue: None
) -> None:
    assert (await post_message(client, page, text="a" * 2000)).status_code == 202
    over = await post_message(client, page, text="a" * 2001)
    assert over.status_code == 422
    assert over.json()["errors"] == [
        {
            "field": "text",
            "message": "Facebook messages can be up to 2,000 characters; this one is 2,001.",
        }
    ]
    # Characters, not bytes: 1,500 two-byte characters would be over Instagram's limit.
    assert (await post_message(client, page, text="é" * 1500)).status_code == 202


async def test_the_heart_sticker_is_instagrams_only(
    client: httpx.AsyncClient, page: Setup, queue: None
) -> None:
    response = await post_message(client, page, text=None, sticker="like_heart")
    assert response.status_code == 415, response.text
    assert response.json()["code"] == "unsupported_media"
    assert response.json()["detail"] == "Facebook has no heart sticker."


async def test_an_image_is_sent_as_an_attachment_and_a_template_is_refused(
    client: httpx.AsyncClient, page: Setup, engine: AsyncEngine, queue: None
) -> None:
    image = await make_asset(engine, workspace_id=page.wid)
    ok = await post_message(client, page, text=None, attachment_asset_ids=[str(image)])
    assert ok.status_code == 202, ok.text
    template = await post_message(
        client, page, text=None, template={"name": "hello", "language": "en", "params": []}
    )
    assert template.status_code == 409
    assert template.json()["code"] == "capability_unavailable"


async def test_the_conversation_shows_the_open_window_for_a_page(
    client: httpx.AsyncClient, clerk: Clerk, page: Setup, engine: AsyncEngine
) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE conversations SET last_inbound_at = now()"))
    conv = await conversation_row(engine, page)
    assert conv["platform"] == "facebook"
    detail = await client.get(
        f"/v1/w/{page.wid}/conversations/{page.conversation_id}", headers=page.headers
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["platform"] == "facebook"
    assert body["reply_window"]["state"] == "open"
    assert json.dumps(body).count("Instagram") == 0
