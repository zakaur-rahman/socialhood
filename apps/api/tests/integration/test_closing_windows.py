"""T5.11: follow-up reminders before a reply window closes (FR-INB-14, F-18).

Done when (with time-machine): one reminder per window; none after a recent business reply. Plus:
the notification, the "Closing soon" signal and view, and conversations that never qualify.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.services.conversations import ListFilters, list_conversations
from tests.support.analysis import Inbox, make_inbox
from tests.support.ingest import stream

T0 = datetime(2026, 9, 28, 9, 0, tzinfo=UTC)
CUSTOMER = "igsid_priya"


@pytest.fixture
async def inbox(engine: AsyncEngine, redis: Redis, clean_db: None, queue: None) -> Inbox:
    return await make_inbox(engine, redis)


async def lead(inbox: Inbox, *, at: datetime = T0, score: int = 70) -> uuid.UUID:
    """Priya wrote at ``at``; her conversation's lead score is ``score``."""
    with time_machine.travel(at, tick=False):
        await inbox.dm(CUSTOMER, "Is the gold one still available?", at=at, name="Priya")
    conv_id = await inbox.conversation_id(CUSTOMER)
    await inbox.set("conversations", conv_id, lead_score=score)
    return conv_id


async def check(inbox: Inbox, at: datetime) -> list[uuid.UUID]:
    with time_machine.travel(at, tick=False):
        return await inbox.check_windows()


async def closing_soon_ids(inbox: Inbox, at: datetime) -> list[uuid.UUID]:
    with workspace_scope(inbox.wid):
        async with inbox.maker() as session:
            page = await list_conversations(
                session,
                ListFilters(view="closing_soon"),
                cursor=None,
                limit=30,
                ig_human_agent_enabled=False,
                now=at,
            )
    return [item.id for item in page.items]


async def test_one_reminder_per_window(inbox: Inbox, redis: Redis) -> None:
    conv_id = await lead(inbox)
    await redis.flushdb()

    assert await check(inbox, T0 + timedelta(hours=17, minutes=45)) == []
    assert await check(inbox, T0 + timedelta(hours=18, minutes=5)) == [conv_id]

    [note] = await inbox.rows("SELECT * FROM notifications")
    assert (note["type"], note["severity"], note["title"]) == (
        "window_closing",
        "warning",
        "Follow up with Priya",
    )
    assert note["body"] == "Follow up with Priya: the reply window closes in 6 h."
    assert note["link"] == f"/inbox/{conv_id}?schedule=1"
    assert note["channels"] == ["in_app", "push"]
    conv = await inbox.conversation(conv_id)
    assert conv["window_reminder_for"] == conv["last_inbound_at"] == T0
    [(kind, payload)] = await stream(redis, inbox.wid)
    assert kind == "conversation.updated"
    assert payload["conversation"]["signal"] == "closing_soon"
    assert await closing_soon_ids(inbox, T0 + timedelta(hours=19)) == [conv_id]

    # Later runs in the same window remind no one again.
    for hours in (18.5, 20, 21.9):
        assert await check(inbox, T0 + timedelta(hours=hours)) == []
    assert len(await inbox.rows("SELECT id FROM notifications")) == 1

    # A new customer message starts a new window and clears the signal.
    wrote_again = T0 + timedelta(hours=21)
    with time_machine.travel(wrote_again, tick=False):
        await inbox.dm(CUSTOMER, "Still thinking about it", at=wrote_again)
    assert await closing_soon_ids(inbox, wrote_again + timedelta(minutes=1)) == []
    assert await check(inbox, wrote_again + timedelta(hours=18, minutes=10)) == [conv_id]
    assert len(await inbox.rows("SELECT id FROM notifications")) == 2


async def test_no_reminder_after_a_recent_business_reply(inbox: Inbox) -> None:
    conv_id = await lead(inbox)
    await inbox.business(conv_id, "Yes! Want me to hold it for you?", at=T0 + timedelta(hours=17))

    assert await check(inbox, T0 + timedelta(hours=18, minutes=5)) == []
    assert await check(inbox, T0 + timedelta(hours=18, minutes=55)) == []
    assert await inbox.rows("SELECT id FROM notifications") == []
    # Two quiet hours later the lead has gone quiet after the reply: remind (F-18).
    assert await check(inbox, T0 + timedelta(hours=19, minutes=5)) == [conv_id]


async def test_a_reply_after_the_reminder_clears_closing_soon(inbox: Inbox) -> None:
    conv_id = await lead(inbox)
    assert await check(inbox, T0 + timedelta(hours=18, minutes=5)) == [conv_id]

    await inbox.business(conv_id, "Holding it for you until 6 pm.", at=T0 + timedelta(hours=19))

    assert await closing_soon_ids(inbox, T0 + timedelta(hours=19, minutes=1)) == []
    assert await check(inbox, T0 + timedelta(hours=21, minutes=30)) == []


@pytest.mark.parametrize(
    ("score", "status", "at"),
    [
        (59, "open", T0 + timedelta(hours=19)),  # not a lead
        (None, "open", T0 + timedelta(hours=19)),  # never analysed
        (80, "archived", T0 + timedelta(hours=19)),
        (80, "open", T0 + timedelta(hours=22, minutes=30)),  # too late: first run after 22 h
    ],
)
async def test_conversations_that_are_not_reminded(
    inbox: Inbox, score: int | None, status: str, at: datetime
) -> None:
    conv_id = await lead(inbox)
    await inbox.set("conversations", conv_id, lead_score=score, status=status)

    assert await check(inbox, at) == []
    assert await inbox.rows("SELECT id FROM notifications") == []
