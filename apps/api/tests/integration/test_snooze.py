"""GR-45: snooze a conversation. PATCH snoozed_until / unsnooze (future, at most 90 days, not for
an archived conversation), the "snoozed" view and every other view, the counts and the priority
queue leaving snoozed conversations out, the wake_snoozed job (unread, the assignee told,
conversation.updated), and a new customer message waking one early."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks.snooze import wake_due_conversations
from socialhood.services import priority_queue
from tests.support.analysis import Inbox, make_inbox
from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace
from tests.support.inbox import make_thread
from tests.support.ingest import sessions, stream

CUSTOMER = "igsid_priya"


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None) -> Ws:
    return await workspace(client, clerk)


@pytest.fixture
async def inbox(engine: AsyncEngine, redis: Redis, clean_db: None, queue: None) -> Inbox:
    return await make_inbox(engine, redis)


async def thread(ws: Ws, engine: AsyncEngine, name: str = "Priya Shah") -> str:
    made = await make_thread(
        engine,
        workspace_id=ws.wid,
        account_id=ws.account_id,
        display_name=name,
        username=None,
        unread=1,
    )
    return str(made.conversation_id)


async def ids(ws: Ws, view: str) -> list[str]:
    page = await ws.ok("GET", f"/conversations?view={view}")
    return [item["id"] for item in page["items"]]


def later(**delta: float) -> str:
    return (datetime.now(UTC) + timedelta(**delta)).isoformat()


# ---------------------------------------------------------------- the API


async def test_a_snoozed_conversation_leaves_every_view_but_snoozed(
    ws: Ws, engine: AsyncEngine
) -> None:
    conv = await thread(ws, engine)
    for view in ("all", "unread", "needs_reply"):
        assert await ids(ws, view) == [conv]
    assert (await ws.ok("GET", "/conversations/counts"))["unread"] == 1

    until = later(hours=3)
    detail = await ws.ok("PATCH", f"/conversations/{conv}", json={"snoozed_until": until})
    assert datetime.fromisoformat(detail["snoozed_until"]) == datetime.fromisoformat(until)
    assert detail["status"] == "open"

    for view in ("all", "unread", "needs_reply", "needs_you", "leads", "mine", "unassigned"):
        assert await ids(ws, view) == []
    [item] = (await ws.ok("GET", "/conversations?view=snoozed"))["items"]
    assert (item["id"], item["snoozed_until"] is not None) == (conv, True)
    counts = await ws.ok("GET", "/conversations/counts")
    assert (counts["unread"], counts["needs_reply"]) == (0, 0)

    back = await ws.ok("PATCH", f"/conversations/{conv}", json={"unsnooze": True})
    assert back["snoozed_until"] is None
    assert await ids(ws, "snoozed") == []
    assert await ids(ws, "all") == [conv]
    assert (await ws.ok("GET", "/conversations/counts"))["unread"] == 1


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"snoozed_until": "2020-01-01T00:00:00Z"}, "Pick a time in the future."),
        ({"snoozed_until": "2099-01-01T00:00:00Z"}, "at most 90 days"),
    ],
    ids=["past", "too_far"],
)
async def test_a_snooze_must_be_in_the_next_90_days(
    ws: Ws, engine: AsyncEngine, change: dict[str, Any], message: str
) -> None:
    conv = await thread(ws, engine)
    response = await ws.call("PATCH", f"/conversations/{conv}", json=change)
    assert response.status_code == 422, response.text
    [error] = response.json()["errors"]
    assert error["field"] == "snoozed_until"
    assert message in error["message"]
    assert await ids(ws, "snoozed") == []


async def test_snooze_and_unsnooze_together_are_refused(ws: Ws, engine: AsyncEngine) -> None:
    conv = await thread(ws, engine)
    response = await ws.call(
        "PATCH", f"/conversations/{conv}", json={"snoozed_until": later(hours=1), "unsnooze": True}
    )
    assert response.status_code == 422, response.text


async def test_an_archived_conversation_cannot_be_snoozed_and_archiving_ends_a_snooze(
    ws: Ws, engine: AsyncEngine
) -> None:
    conv = await thread(ws, engine)
    await ws.ok("PATCH", f"/conversations/{conv}", json={"snoozed_until": later(hours=1)})
    archived = await ws.ok("PATCH", f"/conversations/{conv}", json={"status": "archived"})
    assert archived["snoozed_until"] is None
    assert await ids(ws, "snoozed") == []
    assert await ids(ws, "archived") == [conv]

    response = await ws.call(
        "PATCH", f"/conversations/{conv}", json={"snoozed_until": later(hours=1)}
    )
    assert response.status_code == 422, response.text


async def test_the_priority_queue_leaves_snoozed_conversations_out(
    ws: Ws, engine: AsyncEngine
) -> None:
    conv = await thread(ws, engine)

    async def queued() -> list[uuid.UUID]:
        with workspace_scope(uuid.UUID(ws.wid)):
            async with sessions(engine)() as session:
                found = await priority_queue.priority_queue(
                    session, now=datetime.now(UTC), human_agent=False
                )
        return [item.id for item in found]

    assert await queued() == [uuid.UUID(conv)]
    await ws.ok("PATCH", f"/conversations/{conv}", json={"snoozed_until": later(hours=1)})
    assert await queued() == []


# ---------------------------------------------------------------- waking


async def test_the_wake_job_brings_a_conversation_back_unread_and_tells_the_assignee(
    inbox: Inbox, redis: Redis
) -> None:
    t0 = datetime.now(UTC)
    await inbox.dm(CUSTOMER, "Is the gold one still available?", at=t0 - timedelta(hours=2))
    conv_id = await inbox.conversation_id(CUSTOMER)
    [owner] = await inbox.rows("SELECT owner_user_id FROM workspaces WHERE id = :w", w=inbox.wid)
    await inbox.set(
        "conversations",
        conv_id,
        unread_count=0,
        assignee_user_id=owner["owner_user_id"],
        snoozed_until=t0 + timedelta(minutes=1),
    )
    await redis.flushdb()

    assert await wake_due_conversations(inbox.maker, redis, inbox.settings, now=t0) == []
    assert (await inbox.conversation(conv_id))["snoozed_until"] is not None

    woken_at = t0 + timedelta(minutes=2)
    assert await wake_due_conversations(inbox.maker, redis, inbox.settings, now=woken_at) == [
        conv_id
    ]
    conv = await inbox.conversation(conv_id)
    assert (conv["snoozed_until"], conv["unread_count"]) == (None, 1)
    [note] = await inbox.rows(
        "SELECT * FROM notifications WHERE type = 'conversation_snooze_ended'"
    )
    assert note["user_id"] == owner["owner_user_id"]
    assert note["link"] == f"/inbox/{conv_id}"
    [(kind, payload)] = await stream(redis, inbox.wid)
    assert kind == "conversation.updated"
    assert payload["conversation"]["snoozed_until"] is None
    assert payload["conversation"]["unread_count"] == 1

    # Once only.
    assert await wake_due_conversations(inbox.maker, redis, inbox.settings, now=woken_at) == []
    assert len(await inbox.rows("SELECT id FROM notifications")) == 1


async def test_a_snoozed_conversation_nobody_has_wakes_without_a_notification(
    inbox: Inbox, redis: Redis
) -> None:
    t0 = datetime.now(UTC)
    await inbox.dm(CUSTOMER, "hello", at=t0 - timedelta(hours=1))
    conv_id = await inbox.conversation_id(CUSTOMER)
    await inbox.set("conversations", conv_id, snoozed_until=t0 - timedelta(seconds=5))

    assert await wake_due_conversations(inbox.maker, redis, inbox.settings, now=t0) == [conv_id]

    assert await inbox.rows("SELECT id FROM notifications") == []


async def test_a_new_customer_message_wakes_a_snoozed_conversation_early(inbox: Inbox) -> None:
    t0 = datetime.now(UTC)
    await inbox.dm(CUSTOMER, "hello", at=t0 - timedelta(hours=1))
    conv_id = await inbox.conversation_id(CUSTOMER)
    await inbox.set("conversations", conv_id, unread_count=0, snoozed_until=t0 + timedelta(days=2))

    await inbox.dm(CUSTOMER, "anyone there?", at=t0)

    conv = await inbox.conversation(conv_id)
    assert (conv["snoozed_until"], conv["unread_count"], conv["status"]) == (None, 1, "open")


async def test_our_own_reply_does_not_wake_a_snoozed_conversation(inbox: Inbox) -> None:
    t0 = datetime.now(UTC)
    await inbox.dm(CUSTOMER, "hello", at=t0 - timedelta(hours=1))
    conv_id = await inbox.conversation_id(CUSTOMER)
    await inbox.set("conversations", conv_id, snoozed_until=t0 + timedelta(days=1))

    await inbox.business(conv_id, "Let me check and come back.", at=t0)

    assert (await inbox.conversation(conv_id))["snoozed_until"] is not None
