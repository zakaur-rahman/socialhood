"""P3 foundation: projections (§5.10), signals (UX-INB-04) and publish-after-commit (TR-RT-01)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.inbox import Contact, Conversation, Message
from socialhood.realtime import events
from socialhood.repositories import inbox
from socialhood.services.inbox_views import list_item, message_out, preview_text, signal_for
from tests.support.inbox import make_account, make_thread, make_workspace

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


def conversation(**values: object) -> Conversation:
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "workspace_id": uuid.uuid4(),
        "social_account_id": uuid.uuid4(),
        "contact_id": uuid.uuid4(),
        "platform": "instagram",
        "status": "open",
        "unread_count": 1,
        "awaiting_reply": True,
        "needs_human": False,
        "last_inbound_at": NOW - timedelta(hours=1),
    }
    return Conversation(**{**base, **values})


@pytest.mark.parametrize(
    ("values", "signal"),
    [
        ({"needs_human": True, "last_intent": "complaint"}, "needs_you"),
        ({"last_intent": "complaint", "lead_score": 90}, "complaint"),
        ({"last_inbound_at": NOW - timedelta(hours=22), "lead_score": 90}, "closing_soon"),
        ({"lead_score": 60}, "lead"),
        ({"last_sentiment": "negative"}, "negative"),
        ({}, None),
    ],
)
def test_one_signal_in_priority_order(values: dict[str, object], signal: str | None) -> None:
    conv = conversation(**values)
    contact = Contact(id=conv.contact_id, username="priya")
    assert list_item(conv, contact, now=NOW).signal == signal


def test_closing_soon_needs_an_unanswered_conversation() -> None:
    conv = conversation(awaiting_reply=False, last_inbound_at=NOW - timedelta(hours=22))
    assert signal_for(conv, now=NOW, window_closes_at=NOW + timedelta(hours=2)) is None


def test_previews() -> None:
    assert preview_text("text", "  Do you\n  ship?  ") == "Do you ship?"
    assert preview_text("text", "x" * 300) == "x" * 200
    assert preview_text("image", None) == "Photo"
    assert preview_text("story_reply", None) == "Story reply"


def test_message_projection_hides_internals() -> None:
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        direction="outbound",
        source="human",
        kind="image",
        text=None,
        attachments=[{"id": "a1", "type": "image", "url": "https://x/y.jpg", "public_id": "ws/x"}],
        occurred_at=NOW,
        status="failed",
        error_code="platform_rejected",
        error_message="Instagram rejected this",
        human_agent_tag=False,
        reactions=[],
    )
    out = message_out(msg).model_dump(mode="json")
    assert out["error"] == {"code": "platform_rejected", "message": "Instagram rejected this"}
    assert out["attachments"] == [
        {
            "id": "a1",
            "type": "image",
            "url": "https://x/y.jpg",
            "mime_type": None,
            "size_bytes": None,
            "width": None,
            "height": None,
            "duration_s": None,
            "filename": None,
            "thumbnail_url": None,
            "permalink": None,
            "expired": None,
        }
    ]


async def test_events_publish_only_after_commit(
    engine: AsyncEngine, redis: Redis, clean_db: None
) -> None:
    wid = await make_workspace(engine)
    async with AsyncSession(engine) as session:
        events.queue(session, wid, "notification.created", {"n": 1})
        await session.rollback()
        events.discard(session)
        events.queue(session, wid, "notification.created", {"n": 2})
        await events.commit_and_publish(session, redis)

    entries = await redis.xrange(events.stream_key(wid))
    assert [(e[1]["type"], json.loads(e[1]["data"])) for e in entries] == [
        ("notification.created", {"n": 2})
    ]


async def test_shared_lookups_are_tenant_scoped(engine: AsyncEngine, clean_db: None) -> None:
    wid, other = await make_workspace(engine), await make_workspace(engine)
    account = await make_account(engine, wid)
    thread = await make_thread(engine, workspace_id=wid, account_id=account)
    async with AsyncSession(engine) as session:
        with workspace_scope(wid):
            assert await inbox.get_conversation(session, thread.conversation_id) is not None
        with workspace_scope(other):
            assert await inbox.get_conversation(session, thread.conversation_id) is None
