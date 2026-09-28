"""T3.2: Instagram webhook events through the worker's path (store, process_event, ingest).

F-06, TR-WH-06 (a replay creates and triggers nothing), FR-INB-05 (archive), FR-INB-09 (native
app replies), TR-JOB-05 (echo reconciliation), reactions, read receipts and edits.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import Message
from socialhood.models.platform import WebhookStatus
from socialhood.platforms.events import DeliveryStatus
from socialhood.platforms.instagram.parse import epoch_time
from socialhood.services.ingest import ingest
from tests.support.inbox import make_account, make_thread, make_workspace
from tests.support.ingest import (
    ACCOUNT_REF,
    CUSTOMER,
    deliver,
    jobs,
    replay_all,
    rows,
    sessions,
    stream,
    webhook_rows,
)
from tests.support.instagram import fixture

PROCESSED = [WebhookStatus.PROCESSED]
IGNORED = [WebhookStatus.IGNORED]


@pytest.fixture
async def workspace(engine: AsyncEngine, clean_db: None, queue: None) -> uuid.UUID:
    wid = await make_workspace(engine)
    await make_account(engine, wid, platform_account_id=ACCOUNT_REF)
    return wid


def mid(name: str) -> str:
    """The platform message id in a fixture delivery."""
    item = fixture(name)["entry"][0]["messaging"][0]
    return str(item["message"]["mid"])


def at(name: str) -> datetime:
    return epoch_time(fixture(name)["entry"][0]["messaging"][0]["timestamp"])


async def messages(engine: AsyncEngine) -> list[dict[str, Any]]:
    return await rows(
        engine,
        "SELECT id, direction, source, kind, text, attachments, status, platform_message_id,"
        " reactions, read_at, edited_at, sent_at, error_code, reply_to_platform_message_id"
        " FROM messages ORDER BY occurred_at",
    )


async def conversation(engine: AsyncEngine) -> dict[str, Any]:
    [conv] = await rows(engine, "SELECT * FROM conversations")
    return conv


@pytest.mark.parametrize(
    ("name", "kind", "attachments", "copies"),
    [
        ("webhook_message_text.json", "text", [], 0),
        ("webhook_message_reply.json", "text", [], 0),
        ("webhook_message_image.json", "image", ["image"], 1),
        ("webhook_message_video.json", "video", ["video"], 1),
        ("webhook_message_audio.json", "audio", ["audio"], 1),
        ("webhook_message_file.json", "file", ["file"], 1),
        ("webhook_message_sticker.json", "sticker", ["sticker"], 1),
        ("webhook_story_mention.json", "story_mention", ["story"], 0),  # never copied
        ("webhook_story_reply.json", "story_reply", ["story"], 0),
        ("webhook_share.json", "share", ["share"], 0),
        ("webhook_share_reel.json", "share", ["share"], 0),
        ("webhook_message_unsupported.json", "unsupported", [], 0),
        ("webhook_postback.json", "text", [], 0),
    ],
)
async def test_each_customer_message_type_is_stored(
    engine: AsyncEngine,
    redis: Redis,
    workspace: uuid.UUID,
    name: str,
    kind: str,
    attachments: list[str],
    copies: int,
) -> None:
    assert await deliver(sessions(engine), redis, name) == PROCESSED
    [msg] = await messages(engine)
    assert (msg["direction"], msg["source"], msg["kind"], msg["status"]) == (
        "inbound",
        "customer",
        kind,
        "received",
    )
    item = fixture(name)["entry"][0]["messaging"][0]
    assert msg["platform_message_id"] == (item.get("message") or item.get("postback"))["mid"]
    assert [a["type"] for a in msg["attachments"]] == attachments
    for attachment in msg["attachments"]:
        assert attachment["url"] == attachment["platform_url"]  # until ingest_media copies it
    copy_jobs = await jobs("ingest_media")
    assert len(copy_jobs) == copies
    assert all(j["deferred"] and j["queue_name"] == "interactive" for j in copy_jobs)


async def test_a_new_inbound_message_updates_the_conversation(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    await deliver(sessions(engine), redis, "webhook_message_text.json")
    conv = await conversation(engine)
    sent = at("webhook_message_text.json")
    assert (conv["unread_count"], conv["awaiting_reply"], conv["status"]) == (1, True, "open")
    assert conv["last_inbound_at"] == conv["last_message_at"] == sent
    assert conv["last_message_preview"] == "Hi! Is the sourdough available today?"
    assert (conv["last_message_direction"], conv["last_message_source"]) == ("inbound", "customer")
    [contact] = await rows(engine, "SELECT * FROM contacts")
    assert (contact["platform_user_id"], contact["first_seen_at"]) == (CUSTOMER, sent)
    assert contact["last_seen_at"] == sent

    published = await stream(redis, workspace)
    assert [t for t, _ in published] == ["message.created", "conversation.updated"]
    assert published[0][1]["message"]["text"] == "Hi! Is the sourdough available today?"
    assert published[1][1]["conversation"]["unread_count"] == 1

    [profile] = await jobs("fetch_contact_profile")
    assert profile["queueing_lock"] == f"profile:{contact['id']}"
    assert profile["deferred"]  # after the caller's commit


async def test_a_replayed_event_creates_nothing_and_triggers_nothing(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    maker = sessions(engine)
    await deliver(maker, redis, "webhook_message_image.json")

    async def snapshot() -> tuple[Any, ...]:
        counts = await rows(
            engine,
            "SELECT (SELECT count(*) FROM messages) AS m, (SELECT count(*) FROM contacts) AS c,"
            " (SELECT count(*) FROM conversations) AS v,"
            " (SELECT unread_count FROM conversations) AS unread",
        )
        return (counts[0], len(await jobs()), len(await stream(redis, workspace)))

    before = await snapshot()
    assert before[1:] == (2, 2)  # profile + media jobs; message.created + conversation.updated

    assert await replay_all(engine, maker, redis) == PROCESSED
    assert await deliver(maker, redis, "webhook_message_image.json", copy=":again") == PROCESSED
    assert await snapshot() == before


async def test_an_archived_conversation_returns_when_the_contact_writes(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    maker = sessions(engine)
    await deliver(maker, redis, "webhook_message_text.json")
    async with engine.begin() as conn:
        await conn.execute(sql("UPDATE conversations SET status = 'archived', unread_count = 0"))
    await deliver(maker, redis, "webhook_message_reply.json")
    conv = await conversation(engine)
    assert (conv["status"], conv["unread_count"]) == ("open", 1)
    [_, reply] = await messages(engine)
    assert reply["reply_to_platform_message_id"] == mid("webhook_message_text.json")


async def test_an_older_message_arriving_late_keeps_the_latest_preview(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    maker = sessions(engine)
    await deliver(maker, redis, "webhook_message_reply.json")
    await deliver(maker, redis, "webhook_message_text.json")  # sent a millisecond earlier
    conv = await conversation(engine)
    assert conv["last_message_preview"] == "This one please"
    assert conv["last_message_at"] == at("webhook_message_reply.json")
    assert conv["unread_count"] == 2


# ---------------------------------------------------------------- echoes (FR-INB-09, TR-JOB-05)


async def test_an_echo_is_an_outbound_message_from_the_instagram_app(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    maker = sessions(engine)
    await deliver(maker, redis, "webhook_message_text.json")
    await deliver(maker, redis, "webhook_echo.json")
    [_, echo] = await messages(engine)
    assert (echo["direction"], echo["source"], echo["status"]) == ("outbound", "native_app", "sent")
    assert echo["sent_at"] == at("webhook_echo.json")
    conv = await conversation(engine)
    assert conv["awaiting_reply"] is False
    assert conv["last_outbound_at"] == at("webhook_echo.json")
    assert (conv["last_message_direction"], conv["last_message_source"]) == (
        "outbound",
        "native_app",
    )
    assert [t for t, _ in await stream(redis, workspace)][-2:] == [
        "message.created",
        "conversation.updated",
    ]
    assert len(await jobs("fetch_contact_profile")) == 1  # the contact already existed


async def _outbound(
    engine: AsyncEngine,
    workspace: uuid.UUID,
    *,
    text: str,
    occurred_at: datetime,
    status: str,
    platform_message_id: str | None = None,
    error_code: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> uuid.UUID:
    """An outbound message from Social Hood in the customer's conversation."""
    [account] = await rows(engine, "SELECT id FROM social_accounts")
    thread = await make_thread(
        engine,
        workspace_id=workspace,
        account_id=account["id"],
        contact_ref=CUSTOMER,
        texts=(),
    )
    with workspace_scope(workspace):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            msg = Message(
                conversation_id=thread.conversation_id,
                social_account_id=account["id"],
                direction="outbound",
                source="human",
                kind="image" if attachments and not text else "text",
                text=text or None,
                attachments=attachments or [],
                occurred_at=occurred_at,
                updated_at=occurred_at,
                platform_message_id=platform_message_id,
                status=status,
                error_code=error_code,
                error_message="We couldn't confirm delivery" if error_code else None,
            )
            session.add(msg)
            await session.commit()
            return msg.id


async def test_the_echo_of_our_own_send_changes_nothing(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    await _outbound(
        engine,
        workspace,
        text="Yes, until 6 pm!",
        occurred_at=at("webhook_echo.json") - timedelta(seconds=2),
        status="sent",
        platform_message_id=mid("webhook_echo.json"),
    )
    assert await deliver(sessions(engine), redis, "webhook_echo.json") == PROCESSED
    [msg] = await messages(engine)
    assert msg["source"] == "human"
    assert await stream(redis, workspace) == []
    assert await jobs() == []


async def test_an_echo_completes_a_send_whose_outcome_was_unknown(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    pending = await _outbound(
        engine,
        workspace,
        text="Yes, until 6 pm!",
        occurred_at=at("webhook_echo.json") - timedelta(seconds=30),
        status="failed",
        error_code="delivery_unknown",
    )
    assert await deliver(sessions(engine), redis, "webhook_echo.json") == PROCESSED
    [msg] = await messages(engine)
    assert msg["id"] == pending
    assert (msg["status"], msg["error_code"]) == ("sent", None)
    assert msg["platform_message_id"] == mid("webhook_echo.json")
    published = await stream(redis, workspace)
    assert [t for t, _ in published] == ["message.updated"]
    assert published[0][1]["message"]["status"] == "sent"


async def test_an_echo_that_beats_our_send_job_completes_it(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    """The echo can arrive before the send job stores the id; it must not become a second
    message, and it proves the send was delivered."""
    ours = await _outbound(
        engine,
        workspace,
        text="Yes, until 6 pm!",
        occurred_at=at("webhook_echo.json") - timedelta(seconds=1),
        status="sending",
    )
    assert await deliver(sessions(engine), redis, "webhook_echo.json") == PROCESSED
    [msg] = await messages(engine)
    assert msg["id"] == ours
    assert (msg["status"], msg["platform_message_id"]) == ("sent", mid("webhook_echo.json"))
    assert [t for t, _ in await stream(redis, workspace)] == ["message.updated"]


async def test_an_echo_is_not_matched_to_a_send_that_has_not_started(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    await _outbound(
        engine,
        workspace,
        text="Yes, until 6 pm!",
        occurred_at=at("webhook_echo.json") - timedelta(seconds=1),
        status="queued",
    )
    await deliver(sessions(engine), redis, "webhook_echo.json")
    stored = await messages(engine)
    assert [(m["source"], m["status"]) for m in stored] == [
        ("human", "queued"),
        ("native_app", "sent"),
    ]


@pytest.mark.parametrize("recorded", [True, False], ids=["part-recorded", "part-in-flight"])
async def test_the_echo_of_one_of_our_attachment_parts_is_not_stored_again(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID, recorded: bool
) -> None:
    part: dict[str, Any] = {"id": "a1", "type": "image", "url": "https://res.cloudinary.com/x.jpg"}
    if recorded:
        part |= {"sent": True, "platform_message_id": mid("webhook_echo_image.json")}
    await _outbound(
        engine,
        workspace,
        text="",
        occurred_at=at("webhook_echo_image.json") - timedelta(seconds=1),
        status="sending",
        attachments=[part],
    )
    await deliver(sessions(engine), redis, "webhook_echo_image.json")
    [msg] = await messages(engine)
    assert (msg["source"], msg["status"]) == ("human", "sending")  # the send job finishes it
    assert await stream(redis, workspace) == []


@pytest.mark.parametrize(
    ("text", "age", "error_code"),
    [
        ("Yes, until 7 pm!", timedelta(seconds=30), "delivery_unknown"),  # different text
        ("Yes, until 6 pm!", timedelta(minutes=5), "delivery_unknown"),  # too long ago
        ("Yes, until 6 pm!", timedelta(seconds=30), "platform_rejected"),  # a known failure
    ],
)
async def test_an_echo_does_not_complete_another_send(
    engine: AsyncEngine,
    redis: Redis,
    workspace: uuid.UUID,
    text: str,
    age: timedelta,
    error_code: str,
) -> None:
    await _outbound(
        engine,
        workspace,
        text=text,
        occurred_at=at("webhook_echo.json") - age,
        status="failed",
        error_code=error_code,
    )
    await deliver(sessions(engine), redis, "webhook_echo.json")
    stored = await messages(engine)
    assert [(m["source"], m["status"]) for m in stored] == [
        ("human", "failed"),
        ("native_app", "sent"),
    ]


# ---------------------------------------------------------------- reactions, seen, edits


async def test_a_reaction_is_added_once_and_removed(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    maker = sessions(engine)
    await deliver(maker, redis, "webhook_echo.json")
    events_before = len(await stream(redis, workspace))

    assert await deliver(maker, redis, "webhook_reaction.json") == PROCESSED
    [msg] = await messages(engine)
    assert [(r["emoji"], r["by"]) for r in msg["reactions"]] == [("❤️", "customer")]
    published = await stream(redis, workspace)
    assert [t for t, _ in published[events_before:]] == ["message.updated"]
    assert published[-1][1]["message"]["reactions"][0]["by"] == "customer"

    await deliver(maker, redis, "webhook_reaction.json", copy=":again")
    assert len(await stream(redis, workspace)) == len(published)  # nothing changed, nothing sent

    await deliver(maker, redis, "webhook_unreact.json")
    [msg] = await messages(engine)
    assert msg["reactions"] == []


async def test_a_read_receipt_marks_the_accounts_messages_read(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    maker = sessions(engine)
    await deliver(maker, redis, "webhook_message_text.json")
    await deliver(maker, redis, "webhook_echo.json")
    assert await deliver(maker, redis, "webhook_seen.json") == PROCESSED
    inbound, echo = await messages(engine)
    assert (echo["status"], echo["read_at"]) == ("read", at("webhook_seen.json"))
    assert inbound["status"] == "received"
    assert [t for t, _ in await stream(redis, workspace)][-1] == "message.updated"


async def test_an_edit_replaces_the_text_and_the_preview(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    maker = sessions(engine)
    await deliver(maker, redis, "webhook_message_text.json")
    assert await deliver(maker, redis, "webhook_message_edit.json") == PROCESSED
    [msg] = await messages(engine)
    assert msg["text"] == "Hi! Is the rye sourdough available today?"
    assert msg["edited_at"] == at("webhook_message_edit.json")
    conv = await conversation(engine)
    assert conv["last_message_preview"] == "Hi! Is the rye sourdough available today?"
    assert [t for t, _ in await stream(redis, workspace)][-2:] == [
        "message.updated",
        "conversation.updated",
    ]


async def test_events_we_do_not_act_on_are_ignored_with_the_reason(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    maker = sessions(engine)
    assert await deliver(maker, redis, "webhook_reaction.json") == IGNORED
    assert await deliver(maker, redis, "webhook_message_deleted.json") == IGNORED
    assert await deliver(maker, redis, "webhook_seen.json") == IGNORED
    assert await deliver(maker, redis, "webhook_comment_changes.json") == IGNORED
    assert [r["last_error"] for r in await webhook_rows(engine)] == [
        "reaction to a message we don't have",
        "message deleted",
        "read receipt from an unknown contact",
        "comments arrive in P6",
    ]
    assert await messages(engine) == []


# ---------------------------------------------------------------- delivery statuses (WhatsApp)


async def test_delivery_statuses_only_move_a_message_forward(
    engine: AsyncEngine, redis: Redis, workspace: uuid.UUID
) -> None:
    message_id = await _outbound(
        engine,
        workspace,
        text="Your order is on its way",
        occurred_at=datetime.now(UTC),
        status="sent",
        platform_message_id="wamid.1",
    )
    now = datetime.now(UTC)

    async def status(value: Any, error_code: str | None = None) -> str:
        with workspace_scope(workspace):
            async with sessions(engine)() as session:
                acct = (await rows(engine, "SELECT id FROM social_accounts"))[0]
                account = await session.get(SocialAccount, acct["id"])
                assert account is not None
                event = DeliveryStatus(
                    account_ref=ACCOUNT_REF,
                    occurred_at=now,
                    platform_message_id="wamid.1",
                    status=value,
                    error_code=error_code,
                )
                await ingest(session, account, [event])
                await session.commit()
        [row] = await rows(engine, "SELECT status FROM messages WHERE id = :i", i=message_id)
        return str(row["status"])

    assert await status("delivered") == "delivered"
    assert await status("sent") == "delivered"
    assert await status("failed", "recipient_unavailable") == "delivered"
    assert await status("read") == "read"
    [row] = await rows(engine, "SELECT delivered_at, read_at FROM messages")
    assert row["delivered_at"] == row["read_at"] == now
