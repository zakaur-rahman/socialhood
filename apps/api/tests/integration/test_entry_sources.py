"""GR-01: entry sources, referrals, postback payloads, opt-ins and Live comments through the
worker's path (store, process_event, ingest or comment intake)."""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.models.platform import WebhookStatus
from socialhood.platforms.instagram.parse import epoch_time
from tests.support.automations import make_automation, make_media_item
from tests.support.inbox import make_account, make_workspace
from tests.support.ingest import ACCOUNT_REF, CUSTOMER, deliver, jobs, rows, sessions
from tests.support.instagram import fixture

PROCESSED = [WebhookStatus.PROCESSED]
IGNORED = [WebhookStatus.IGNORED]


@pytest.fixture
async def account(engine: AsyncEngine, clean_db: None, queue: None) -> tuple[uuid.UUID, uuid.UUID]:
    wid = await make_workspace(engine)
    return wid, await make_account(engine, wid, platform_account_id=ACCOUNT_REF)


@pytest.fixture
async def workspace(account: tuple[uuid.UUID, uuid.UUID]) -> uuid.UUID:
    return account[0]


def _ms(at: datetime) -> int:
    return int(at.timestamp() * 1000)


def text_dm(at: datetime, mid: str = "m_text", text: str = "Hi there") -> dict[str, Any]:
    body = copy.deepcopy(fixture("webhook_message_text.json"))
    item = body["entry"][0]["messaging"][0]
    item["timestamp"] = _ms(at)
    item["message"] = {"mid": mid, "text": text}
    return body


def link_referral(at: datetime, ref: str = "spring-sale") -> dict[str, Any]:
    body = copy.deepcopy(fixture("webhook_referral_link.json"))
    item = body["entry"][0]["messaging"][0]
    item["timestamp"] = _ms(at)
    item["referral"]["ref"] = ref
    return body


async def conversations(engine: AsyncEngine) -> list[dict[str, Any]]:
    return await rows(
        engine,
        "SELECT entry_source, entry_ref, entry_ad_id, entry_at, last_referral FROM conversations",
    )


async def contact(engine: AsyncEngine) -> dict[str, Any]:
    [row] = await rows(engine, "SELECT last_referral, first_entry_source FROM contacts")
    return row


async def test_a_first_message_from_an_ad_records_the_ad(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    assert await deliver(sessions(engine), redis, "webhook_message_from_ad.json") == PROCESSED
    [conv] = await conversations(engine)
    assert (conv["entry_source"], conv["entry_ref"], conv["entry_ad_id"]) == (
        "ad",
        "diwali",
        "120210000000000001",
    )
    assert conv["last_referral"]["ad_title"] == "Diwali hampers"
    person = await contact(engine)
    assert person["first_entry_source"] == "ad"
    assert person["last_referral"]["ad_id"] == "120210000000000001"


async def test_a_plain_first_message_is_organic(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    assert await deliver(sessions(engine), redis, "webhook_message_text.json") == PROCESSED
    [conv] = await conversations(engine)
    assert (conv["entry_source"], conv["entry_ref"], conv["last_referral"]) == (
        "organic",
        None,
        None,
    )
    assert conv["entry_at"] == epoch_time(
        fixture("webhook_message_text.json")["entry"][0]["messaging"][0]["timestamp"]
    )
    assert (await contact(engine))["first_entry_source"] == "organic"


async def test_a_link_opened_then_a_message_starts_from_the_link(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    opened = epoch_time(
        fixture("webhook_referral_link.json")["entry"][0]["messaging"][0]["timestamp"]
    )
    maker = sessions(engine)
    assert await deliver(maker, redis, link_referral(opened)) == PROCESSED
    # A referral alone starts no conversation (no empty threads in the inbox).
    assert await conversations(engine) == []
    assert (await contact(engine))["last_referral"]["ref"] == "spring-sale"

    assert await deliver(maker, redis, text_dm(opened + timedelta(minutes=10))) == PROCESSED
    [conv] = await conversations(engine)
    assert (conv["entry_source"], conv["entry_ref"]) == ("link", "spring-sale")
    assert (await contact(engine))["first_entry_source"] == "link"


async def test_a_link_opened_long_before_the_message_doesnt_count(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    opened = epoch_time(
        fixture("webhook_referral_link.json")["entry"][0]["messaging"][0]["timestamp"]
    )
    maker = sessions(engine)
    await deliver(maker, redis, link_referral(opened))
    await deliver(maker, redis, text_dm(opened + timedelta(hours=2)))
    [conv] = await conversations(engine)
    assert conv["entry_source"] == "organic"


async def test_a_referral_just_after_the_first_message_upgrades_the_entry(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    """Meta may deliver the referral after the message that followed it."""
    first = epoch_time(
        fixture("webhook_message_text.json")["entry"][0]["messaging"][0]["timestamp"]
    )
    maker = sessions(engine)
    await deliver(maker, redis, text_dm(first))
    assert await deliver(maker, redis, link_referral(first + timedelta(seconds=20))) == PROCESSED
    [conv] = await conversations(engine)
    assert (conv["entry_source"], conv["entry_ref"]) == ("link", "spring-sale")
    assert conv["last_referral"]["ref"] == "spring-sale"
    assert (await contact(engine))["first_entry_source"] == "link"


async def test_a_later_referral_in_an_old_conversation_keeps_the_entry(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    first = epoch_time(
        fixture("webhook_message_text.json")["entry"][0]["messaging"][0]["timestamp"]
    )
    maker = sessions(engine)
    await deliver(maker, redis, text_dm(first))
    await deliver(maker, redis, link_referral(first + timedelta(days=3), ref="newsletter"))
    [conv] = await conversations(engine)
    assert conv["entry_source"] == "organic"
    assert conv["last_referral"]["ref"] == "newsletter"


async def test_a_postback_keeps_its_payload(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    assert await deliver(sessions(engine), redis, "webhook_postback.json") == PROCESSED
    [msg] = await rows(engine, "SELECT text, postback_payload FROM messages")
    assert (msg["text"], msg["postback_payload"]) == (
        "What are your opening hours?",
        "ICE_BREAKER_HOURS",
    )


async def test_an_opt_in_records_marketing_consent(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    """GR-02: Instagram's messaging_optins becomes a consent record, with Meta's words as
    evidence; it starts no conversation."""
    assert await deliver(sessions(engine), redis, "webhook_optin.json") == PROCESSED
    [consent] = await rows(
        engine, "SELECT channel, purpose, status, source, evidence FROM contact_consents"
    )
    assert consent == {
        "channel": "instagram",
        "purpose": "marketing",
        "status": "granted",
        "source": "platform_optin",
        "evidence": {"platform_event": "messaging_optins", "topic": "Offers", "status": "resume"},
    }
    assert await rows(engine, "SELECT id FROM conversations") == []


async def test_an_opt_in_that_stops_revokes_consent(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    body = copy.deepcopy(fixture("webhook_optin.json"))
    body["entry"][0]["messaging"][0]["optin"]["notification_messages_status"] = "stop"
    assert await deliver(sessions(engine), redis, body) == PROCESSED
    [consent] = await rows(engine, "SELECT status FROM contact_consents")
    assert consent["status"] == "revoked"


async def any_comment_automation(engine: AsyncEngine, account: tuple[uuid.UUID, uuid.UUID]) -> None:
    """An active "any comment" automation on all posts, with the fixtures' posts already stored
    (so intake doesn't fetch them from Instagram)."""
    wid, account_id = account
    for media_id in ("18100000000000001", "18020000000000005"):  # the post's, the Live's
        await make_media_item(
            engine, workspace_id=wid, account_id=account_id, platform_media_id=media_id
        )
    await make_automation(
        engine,
        workspace_id=wid,
        account_id=account_id,
        keywords=(),
        trigger="comment_any",
        post_scope="all",
    )


async def test_a_live_comment_is_stored_live_and_a_posts_automation_passes_it_over(
    engine: AsyncEngine, redis: Redis, account: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """GR-10: the automation is on posts only, so the job it queues finds no match on the Live
    (tests/integration/test_live_comments.py covers the Live scope)."""
    await any_comment_automation(engine, account)
    assert await deliver(sessions(engine), redis, "webhook_live_comment.json") == PROCESSED
    [comment] = await rows(engine, "SELECT platform_comment_id, text, is_live FROM comments")
    assert comment == {"platform_comment_id": "18030000000000009", "text": "PRICE", "is_live": True}
    assert len(await jobs("run_automation")) == 1


async def test_a_post_comment_is_not_live_and_runs_the_automation(
    engine: AsyncEngine, redis: Redis, account: tuple[uuid.UUID, uuid.UUID]
) -> None:
    await any_comment_automation(engine, account)
    assert await deliver(sessions(engine), redis, "webhook_comment_changes.json") == PROCESSED
    [comment] = await rows(engine, "SELECT is_live FROM comments")
    assert comment["is_live"] is False
    assert len(await jobs("run_automation")) == 1


async def test_a_referral_from_the_account_itself_is_ignored(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    body = link_referral(epoch_time(1790000600019))
    body["entry"][0]["messaging"][0]["sender"] = {"id": ACCOUNT_REF}
    assert await deliver(sessions(engine), redis, body) == IGNORED
    assert await rows(engine, "SELECT id FROM contacts") == []


def test_the_fixture_customer_is_the_one_ingest_expects() -> None:
    sender = fixture("webhook_referral_link.json")["entry"][0]["messaging"][0]["sender"]["id"]
    assert sender == CUSTOMER
