"""T3.13: scheduled messages (F-10, FR-SMS-01...03, TR-JOB-03, UX-INB-10).

The send pipeline's ``queue_outbound`` is replaced by a fake that inserts the outbound message, so
these tests cover scheduling, the dispatcher and send_scheduled, not the platform send.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import time_machine
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.jobs.app import app as jobs_app
from socialhood.jobs.tasks.scheduled import (
    dispatch_due_messages,
    send_one,
    sweep_stuck_messages,
)
from socialhood.models.inbox import Conversation, Message
from socialhood.realtime import events
from socialhood.services import scheduled as scheduled_service
from socialhood.services import sending
from socialhood.services.scheduled import client_id_for
from tests.support.api import Clerk, sign_in
from tests.support.inbox import make_asset, make_scheduled, make_thread

# ---- helpers


@dataclass
class FakeOutbound:
    """Stands in for services.sending.queue_outbound (T3.6): inserts the queued message."""

    calls: list[dict[str, Any]] = field(default_factory=list)
    error: ApiError | None = None
    delay_s: float = 0

    async def __call__(
        self,
        session: AsyncSession,
        conv: Conversation,
        *,
        source: str,
        client_id: uuid.UUID,
        text: str | None = None,
        attachment_asset_ids: Sequence[uuid.UUID] = (),
        template: object = None,
        sent_by_user_id: uuid.UUID | None = None,
        scheduled_message_id: uuid.UUID | None = None,
        suggestion_id: uuid.UUID | None = None,
    ) -> Message:
        self.calls.append(
            {
                "source": source,
                "client_id": client_id,
                "text": text,
                "attachment_asset_ids": list(attachment_asset_ids),
                "sent_by_user_id": sent_by_user_id,
                "scheduled_message_id": scheduled_message_id,
            }
        )
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        msg = Message(
            conversation_id=conv.id,
            social_account_id=conv.social_account_id,
            direction="outbound",
            source=source,
            kind="text",
            text=text,
            attachments=[],
            reactions=[],
            occurred_at=datetime.now(UTC),
            client_id=client_id,
            status="queued",
            human_agent_tag=False,
            sent_by_user_id=sent_by_user_id,
            scheduled_message_id=scheduled_message_id,
        )
        session.add(msg)
        await session.flush()
        events.queue(session, conv.workspace_id, "message.created", {"message_id": str(msg.id)})
        if self.error is not None:
            raise self.error
        return msg


@pytest.fixture
def outbound(monkeypatch: pytest.MonkeyPatch) -> FakeOutbound:
    fake = FakeOutbound()
    monkeypatch.setattr(sending, "queue_outbound", fake)
    return fake


@dataclass
class Ws:
    headers: dict[str, str]
    wid: str
    user_id: str
    conversation_id: uuid.UUID

    @property
    def base(self) -> str:
        return f"/v1/w/{self.wid}"


async def workspace(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    *,
    email: str = "owner@example.com",
    last_inbound_ago: timedelta = timedelta(minutes=1),
) -> Ws:
    """A signed-in owner with a sandbox account and one conversation."""
    clerk_id, me = await sign_in(client, clerk, email=email)
    wid = me["workspaces"][0]["id"]
    headers = clerk.headers(clerk_id)
    account = await client.post(f"/v1/w/{wid}/dev/sandbox/accounts", headers=headers)
    assert account.status_code == 201, account.text
    thread = await make_thread(
        engine,
        workspace_id=wid,
        account_id=account.json()["id"],
        last_inbound_at=datetime.now(UTC) - last_inbound_ago,
    )
    return Ws(headers, wid, me["id"], thread.conversation_id)


def iso(at: datetime) -> str:
    return at.isoformat().replace("+00:00", "Z")


async def schedule(
    client: httpx.AsyncClient, ws: Ws, *, in_: timedelta = timedelta(minutes=10), **body: Any
) -> httpx.Response:
    payload = {"text": "Your order ships today", "send_at": iso(datetime.now(UTC) + in_), **body}
    return await client.post(
        f"{ws.base}/conversations/{ws.conversation_id}/scheduled-messages",
        json=payload,
        headers=ws.headers,
    )


async def row(engine: AsyncEngine, scheduled_id: str | uuid.UUID) -> dict[str, Any]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT * FROM scheduled_messages WHERE id = :i"), {"i": str(scheduled_id)}
        )
        return dict(result.one()._mapping)


async def messages_for(engine: AsyncEngine, scheduled_id: str | uuid.UUID) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT * FROM messages WHERE scheduled_message_id = :i"), {"i": str(scheduled_id)}
        )
        return [dict(r._mapping) for r in result]


async def set_row(engine: AsyncEngine, scheduled_id: str | uuid.UUID, **values: Any) -> None:
    assignments = ", ".join(f"{k} = :{k}" for k in values)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"UPDATE scheduled_messages SET {assignments} WHERE id = :id"),  # noqa: S608
            {**values, "id": str(scheduled_id)},
        )


async def published(redis: Redis, wid: str) -> list[tuple[str, dict[str, Any]]]:
    entries = await redis.xrange(events.stream_key(uuid.UUID(wid)))
    return [(e[1]["type"], json.loads(e[1]["data"])) for e in entries]


def statuses(entries: list[tuple[str, dict[str, Any]]], scheduled_id: str) -> list[str]:
    return [
        data["scheduled_message"]["status"]
        for kind, data in entries
        if kind == "scheduled_message.updated" and data["scheduled_message"]["id"] == scheduled_id
    ]


async def send_jobs() -> list[dict[str, Any]]:
    return list(
        await jobs_app.connector.execute_query_all_async(
            "SELECT args, queueing_lock FROM procrastinate_jobs WHERE task_name = 'send_scheduled'"
        )
    )


# ---- scheduling (F-10, FR-SMS-01)


async def test_scheduling_returns_the_message_and_publishes_it(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis
) -> None:
    ws = await workspace(client, clerk, engine)
    asset = await make_asset(engine, workspace_id=ws.wid)
    send_at = (datetime.now(UTC) + timedelta(hours=2)).replace(microsecond=0)

    response = await client.post(
        f"{ws.base}/conversations/{ws.conversation_id}/scheduled-messages",
        json={
            "text": "  Your order ships today  ",
            "send_at": iso(send_at),
            "attachment_asset_ids": [str(asset)],
        },
        headers=ws.headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body == {
        "id": body["id"],
        "conversation_id": str(ws.conversation_id),
        "text": "Your order ships today",
        "attachment_asset_ids": [str(asset)],
        "send_at": iso(send_at),
        "status": "scheduled",
        "error": None,
        "contact": {
            "display_name": "Priya Shah",
            "username": "priya.shah",
            "profile_picture_url": None,
        },
        "platform": "instagram",
    }
    stored = await row(engine, body["id"])
    assert stored["created_by_user_id"] == uuid.UUID(ws.user_id)
    assert stored["attempts"] == 0
    assert statuses(await published(redis, ws.wid), body["id"]) == ["scheduled"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"send_at": "past"}, "send_at"),
        ({"send_at": "in_30s"}, "send_at"),
        ({"send_at": "after_window"}, "send_at"),
        ({"text": "   "}, "text"),
        ({"text": "x" * 2001}, "text"),
        ({"attachment_asset_ids": [str(uuid.uuid4())]}, "attachment_asset_ids"),
    ],
)
async def test_invalid_schedules_are_rejected(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    body: dict[str, Any],
    field: str,
) -> None:
    ws = await workspace(client, clerk, engine)  # the window closes in 23 h 59 min
    now = datetime.now(UTC)
    times = {
        "past": now - timedelta(minutes=5),
        "in_30s": now + timedelta(seconds=30),
        "after_window": now + timedelta(hours=23, minutes=56),
    }
    if "send_at" in body:
        body = {"send_at": iso(times[body["send_at"]])}

    response = await schedule(client, ws, **body)

    assert response.status_code == 422, response.text
    problem = response.json()
    assert problem["code"] == "validation_error"
    assert [e["field"] for e in problem["errors"]] == [field]


async def test_the_latest_time_is_five_minutes_before_the_window_closes(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    ws = await workspace(client, clerk, engine, last_inbound_ago=timedelta(hours=20))
    assert (await schedule(client, ws, in_=timedelta(hours=3, minutes=54))).status_code == 201
    assert (await schedule(client, ws, in_=timedelta(hours=3, minutes=56))).status_code == 422


async def test_a_closed_window_cannot_be_scheduled_into(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    ws = await workspace(client, clerk, engine, last_inbound_ago=timedelta(hours=25))
    response = await schedule(client, ws)
    assert response.status_code == 409
    assert response.json()["code"] == "reply_window_closed"


async def test_another_workspaces_attachment_is_rejected(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    ws = await workspace(client, clerk, engine)
    other = await workspace(client, clerk, engine, email="other@example.com")
    foreign = await make_asset(engine, workspace_id=other.wid)
    response = await schedule(client, ws, attachment_asset_ids=[str(foreign)])
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "attachment_asset_ids"


async def test_the_plan_limits_pending_messages(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    ws = await workspace(client, clerk, engine)  # Free: 20 pending (billing/plans.py)
    for i in range(20):
        await make_scheduled(
            engine,
            workspace_id=ws.wid,
            conversation_id=ws.conversation_id,
            status="sending" if i == 0 else "scheduled",
        )
    for status in ("sent", "canceled", "failed", "expired"):
        await make_scheduled(
            engine, workspace_id=ws.wid, conversation_id=ws.conversation_id, status=status
        )

    refused = await schedule(client, ws)
    assert refused.status_code == 402
    assert refused.json()["code"] == "quota_exceeded"
    assert refused.json()["detail"] == "Your plan includes 20 scheduled messages."

    listed = (await client.get(f"{ws.base}/scheduled-messages", headers=ws.headers)).json()
    one = next(i["id"] for i in listed["items"] if i["status"] == "scheduled")
    canceled = await client.delete(f"{ws.base}/scheduled-messages/{one}", headers=ws.headers)
    assert canceled.status_code == 204
    assert (await schedule(client, ws)).status_code == 201


# ---- edit and cancel (FR-SMS-02)


async def test_editing_text_and_time(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis
) -> None:
    ws = await workspace(client, clerk, engine)
    created = (await schedule(client, ws)).json()
    url = f"{ws.base}/scheduled-messages/{created['id']}"
    later = (datetime.now(UTC) + timedelta(hours=5)).replace(microsecond=0)

    edited = await client.patch(
        url, json={"text": "Ships tomorrow instead", "send_at": iso(later)}, headers=ws.headers
    )

    assert edited.status_code == 200, edited.text
    assert (edited.json()["text"], edited.json()["send_at"]) == (
        "Ships tomorrow instead",
        iso(later),
    )
    stored = await row(engine, created["id"])
    assert (stored["text"], stored["send_at"]) == ("Ships tomorrow instead", later)
    assert statuses(await published(redis, ws.wid), created["id"]) == ["scheduled", "scheduled"]

    too_late = await client.patch(
        url, json={"send_at": iso(datetime.now(UTC) + timedelta(days=2))}, headers=ws.headers
    )
    assert too_late.status_code == 422
    assert (await client.patch(url, json={"text": ""}, headers=ws.headers)).status_code == 422


async def test_cancel_only_while_scheduled(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis
) -> None:
    ws = await workspace(client, clerk, engine)
    created = (await schedule(client, ws)).json()
    url = f"{ws.base}/scheduled-messages/{created['id']}"

    assert (await client.delete(url, headers=ws.headers)).status_code == 204
    assert (await row(engine, created["id"]))["status"] == "canceled"
    assert statuses(await published(redis, ws.wid), created["id"]) == ["scheduled", "canceled"]
    assert (await client.delete(url, headers=ws.headers)).status_code == 204  # already canceled
    edit = await client.patch(url, json={"text": "Changed"}, headers=ws.headers)
    assert edit.status_code == 409
    assert edit.json()["code"] == "conflict"


@pytest.mark.parametrize("status", ["sending", "sent", "failed", "expired"])
async def test_a_claimed_or_finished_message_cannot_be_changed(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, status: str
) -> None:
    ws = await workspace(client, clerk, engine)
    scheduled_id = await make_scheduled(
        engine, workspace_id=ws.wid, conversation_id=ws.conversation_id, status=status
    )
    url = f"{ws.base}/scheduled-messages/{scheduled_id}"
    for response in (
        await client.patch(url, json={"text": "Changed"}, headers=ws.headers),
        await client.delete(url, headers=ws.headers),
    ):
        assert response.status_code == 409
        assert response.json()["code"] == "conflict"
    assert (await row(engine, scheduled_id))["status"] == status


# ---- lists (FR-SMS-02, UX-INB-10)


async def test_the_scheduled_tab_lists_pending_first_then_recent(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    ws = await workspace(client, clerk, engine)
    now = datetime.now(UTC)

    async def add(status: str, at: timedelta) -> str:
        return str(
            await make_scheduled(
                engine,
                workspace_id=ws.wid,
                conversation_id=ws.conversation_id,
                status=status,
                send_at=now + at,
            )
        )

    later = await add("scheduled", timedelta(hours=3))
    soon = await add("scheduled", timedelta(hours=1))
    sending = await add("sending", timedelta(minutes=-1))
    sent = await add("sent", timedelta(hours=-1))
    expired = await add("expired", timedelta(hours=-2))
    failed = await add("failed", timedelta(days=-3))
    await add("sent", timedelta(days=-10))  # too old for the tab
    await add("canceled", timedelta(hours=2))

    pages: list[list[str]] = []
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = (
            await client.get(f"{ws.base}/scheduled-messages", params=params, headers=ws.headers)
        ).json()
        pages.append([item["id"] for item in page["items"]])
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert pages == [[sending, soon], [later, sent], [expired, failed]]

    whole = (await client.get(f"{ws.base}/scheduled-messages", headers=ws.headers)).json()
    assert [i["status"] for i in whole["items"]] == [
        "sending",
        "scheduled",
        "scheduled",
        "sent",
        "expired",
        "failed",
    ]
    assert whole["next_cursor"] is None

    thread = (
        await client.get(
            f"{ws.base}/conversations/{ws.conversation_id}/scheduled-messages", headers=ws.headers
        )
    ).json()
    assert [i["id"] for i in thread["items"]] == [sending, soon, later]

    bad = await client.get(f"{ws.base}/scheduled-messages?cursor=nonsense", headers=ws.headers)
    assert bad.status_code == 422
    assert bad.json()["errors"][0]["field"] == "cursor"


async def test_a_pending_page_that_fills_exactly_still_leads_to_the_rest(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    ws = await workspace(client, clerk, engine)
    now = datetime.now(UTC)
    pending = str(
        await make_scheduled(
            engine,
            workspace_id=ws.wid,
            conversation_id=ws.conversation_id,
            send_at=now + timedelta(hours=1),
        )
    )
    sent = str(
        await make_scheduled(
            engine,
            workspace_id=ws.wid,
            conversation_id=ws.conversation_id,
            status="sent",
            send_at=now - timedelta(hours=1),
        )
    )
    url = f"{ws.base}/scheduled-messages"
    first = (await client.get(url, params={"limit": 1}, headers=ws.headers)).json()
    assert [i["id"] for i in first["items"]] == [pending]
    second = (
        await client.get(
            url, params={"limit": 1, "cursor": first["next_cursor"]}, headers=ws.headers
        )
    ).json()
    assert [i["id"] for i in second["items"]] == [sent]
    assert second["next_cursor"] is None


# ---- tenancy (TR-TEN-03)


async def test_other_workspaces_messages_are_invisible(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    ws = await workspace(client, clerk, engine)
    other = await workspace(client, clerk, engine, email="other@example.com")
    theirs = (await schedule(client, other)).json()["id"]
    url = f"{ws.base}/scheduled-messages/{theirs}"

    responses = [
        await client.patch(url, json={"text": "Mine now"}, headers=ws.headers),
        await client.delete(url, headers=ws.headers),
        await client.get(
            f"{ws.base}/conversations/{other.conversation_id}/scheduled-messages",
            headers=ws.headers,
        ),
        await schedule(client, Ws(ws.headers, ws.wid, ws.user_id, other.conversation_id)),
    ]
    assert [(r.status_code, r.json()["code"]) for r in responses] == [(404, "not_found")] * 4
    assert (await client.get(f"{ws.base}/scheduled-messages", headers=ws.headers)).json()[
        "items"
    ] == []
    assert (await row(engine, theirs))["status"] == "scheduled"


# ---- sending at the due time (FR-SMS-03, TR-JOB-03)


async def test_a_due_message_is_sent_once(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
    outbound: FakeOutbound,
) -> None:
    ws = await workspace(client, clerk, engine)
    asset = await make_asset(engine, workspace_id=ws.wid)
    created = (
        await schedule(client, ws, in_=timedelta(minutes=10), attachment_asset_ids=[str(asset)])
    ).json()
    scheduled_id = uuid.UUID(created["id"])
    sessions = app.state.sessionmaker

    assert await dispatch_due_messages(sessions, redis) == []  # not due yet

    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=10, seconds=20)):
        # Two dispatchers at once, then another tick: one claim, one job.
        first, second = await asyncio.gather(
            dispatch_due_messages(sessions, redis), dispatch_due_messages(sessions, redis)
        )
        assert sorted([first, second], key=len) == [[], [scheduled_id]]
        assert await dispatch_due_messages(sessions, redis) == []
        jobs = await send_jobs()
        assert len(jobs) == 1
        assert jobs[0]["queueing_lock"] == f"smsg:{scheduled_id}"
        assert jobs[0]["args"] == {
            "scheduled_message_id": str(scheduled_id),
            "workspace_id": ws.wid,
        }
        claimed = await row(engine, scheduled_id)
        assert (claimed["status"], claimed["attempts"]) == ("sending", 1)
        assert claimed["claimed_at"] is not None

        # Two workers run the job at the same time: one sends, the other finds it taken.
        outbound.delay_s = 0.3
        outcomes = await asyncio.gather(
            send_one(sessions, redis, scheduled_id, uuid.UUID(ws.wid), human_agent_enabled=False),
            send_one(sessions, redis, scheduled_id, uuid.UUID(ws.wid), human_agent_enabled=False),
        )
        assert sorted(outcomes) == ["sent", "skipped"]
        # A late repeat does nothing either.
        again = await send_one(
            sessions, redis, scheduled_id, uuid.UUID(ws.wid), human_agent_enabled=False
        )
        assert again == "skipped"

    assert outbound.calls == [
        {
            "source": "human",
            "client_id": client_id_for(scheduled_id),
            "text": "Your order ships today",
            "attachment_asset_ids": [asset],
            "sent_by_user_id": uuid.UUID(ws.user_id),
            "scheduled_message_id": scheduled_id,
        }
    ]
    [message] = await messages_for(engine, scheduled_id)
    done = await row(engine, scheduled_id)
    assert (done["status"], done["message_id"], done["error_code"]) == ("sent", message["id"], None)
    entries = await published(redis, ws.wid)
    assert statuses(entries, str(scheduled_id)) == ["scheduled", "sending", "sent"]
    assert [k for k, _ in entries].count("message.created") == 1


async def test_a_message_that_already_exists_is_not_sent_again(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
    outbound: FakeOutbound,
) -> None:
    """A row reset by the sweeper after its message was created never produces a second one."""
    ws = await workspace(client, clerk, engine)
    scheduled_id = uuid.UUID((await schedule(client, ws)).json()["id"])
    sessions = app.state.sessionmaker
    wid = uuid.UUID(ws.wid)
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        await dispatch_due_messages(sessions, redis)
        assert (
            await send_one(sessions, redis, scheduled_id, wid, human_agent_enabled=False) == "sent"
        )
        await set_row(engine, scheduled_id, status="sending", message_id=None)
        assert (
            await send_one(sessions, redis, scheduled_id, wid, human_agent_enabled=False) == "sent"
        )
    assert len(outbound.calls) == 1
    [message] = await messages_for(engine, scheduled_id)
    assert (await row(engine, scheduled_id))["message_id"] == message["id"]


async def test_a_closed_window_expires_the_message_and_tells_the_owner(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
    outbound: FakeOutbound,
) -> None:
    ws = await workspace(client, clerk, engine, last_inbound_ago=timedelta(hours=23))
    scheduled_id = uuid.UUID((await schedule(client, ws, in_=timedelta(minutes=30))).json()["id"])
    sessions = app.state.sessionmaker

    # The worker was down: the dispatcher next runs after the window has closed.
    with time_machine.travel(datetime.now(UTC) + timedelta(hours=2)):
        assert await dispatch_due_messages(sessions, redis) == [scheduled_id]
        outcome = await send_one(
            sessions, redis, scheduled_id, uuid.UUID(ws.wid), human_agent_enabled=False
        )

    assert outcome == "expired"
    assert outbound.calls == []
    assert await messages_for(engine, scheduled_id) == []
    expired = await row(engine, scheduled_id)
    assert (expired["status"], expired["error_code"]) == ("expired", "reply_window_closed")
    entries = await published(redis, ws.wid)
    assert statuses(entries, str(scheduled_id)) == ["scheduled", "sending", "expired"]
    last = next(d for k, d in reversed(entries) if k == "scheduled_message.updated")
    assert last["scheduled_message"]["error"] == {
        "code": "reply_window_closed",
        "message": "The reply window closed before the send time.",
    }

    notes = (await client.get(f"{ws.base}/notifications", headers=ws.headers)).json()
    [note] = notes["items"]
    assert (note["type"], note["severity"], note["title"], note["body"], note["link"]) == (
        "scheduled_message_expired",
        "warning",
        "Scheduled message not sent",
        "Scheduled message to Priya Shah wasn't sent: the reply window closed.",
        f"/inbox/{ws.conversation_id}",
    )


async def test_a_human_agent_window_still_allows_the_send(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
    outbound: FakeOutbound,
) -> None:
    """Instagram's 7-day Human Agent window, once approved (IG_HUMAN_AGENT_ENABLED)."""
    ws = await workspace(client, clerk, engine, last_inbound_ago=timedelta(hours=23))
    scheduled_id = uuid.UUID((await schedule(client, ws, in_=timedelta(minutes=30))).json()["id"])
    sessions = app.state.sessionmaker
    with time_machine.travel(datetime.now(UTC) + timedelta(hours=2)):
        await dispatch_due_messages(sessions, redis)
        outcome = await send_one(
            sessions, redis, scheduled_id, uuid.UUID(ws.wid), human_agent_enabled=True
        )
    assert outcome == "sent"


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (
            ApiError(
                "account_needs_reconnect",
                "@maple.bakery needs reconnecting before you can send from it.",
            ),
            "failed",
        ),
        (ApiError("capability_unavailable"), "failed"),
        (ApiError("reply_window_closed"), "expired"),
    ],
)
async def test_a_refused_send_is_recorded_not_retried(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
    outbound: FakeOutbound,
    error: ApiError,
    status: str,
) -> None:
    ws = await workspace(client, clerk, engine)
    scheduled_id = uuid.UUID((await schedule(client, ws)).json()["id"])
    outbound.error = error
    sessions = app.state.sessionmaker
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        await dispatch_due_messages(sessions, redis)
        outcome = await send_one(
            sessions, redis, scheduled_id, uuid.UUID(ws.wid), human_agent_enabled=False
        )

    assert outcome == status
    stored = await row(engine, scheduled_id)
    assert (stored["status"], stored["error_code"], stored["message_id"]) == (
        status,
        error.code,
        None,
    )
    if status == "failed":
        assert stored["error_message"] == (error.detail or "This account can't do that")
    # The pipeline's writes and events were rolled back with its savepoint.
    assert await messages_for(engine, scheduled_id) == []
    entries = await published(redis, ws.wid)
    assert "message.created" not in [k for k, _ in entries]
    assert statuses(entries, str(scheduled_id))[-1] == status


# ---- the sweeper (TR-JOB-03)


async def test_the_sweeper_resets_stuck_claims_and_fails_them_after_five(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    ws = await workspace(client, clerk, engine)
    now = datetime.now(UTC)

    async def stuck(claimed_ago: timedelta, attempts: int) -> uuid.UUID:
        scheduled_id = await make_scheduled(
            engine,
            workspace_id=ws.wid,
            conversation_id=ws.conversation_id,
            status="sending",
            send_at=now - timedelta(minutes=30),
        )
        await set_row(engine, scheduled_id, claimed_at=now - claimed_ago, attempts=attempts)
        return scheduled_id

    lost = await stuck(timedelta(minutes=11), attempts=1)
    hopeless = await stuck(timedelta(minutes=11), attempts=5)
    recent = await stuck(timedelta(minutes=2), attempts=1)

    counts = await sweep_stuck_messages(app.state.sessionmaker, redis, now=now)

    assert counts == {"reset": 1, "failed": 1}
    assert (await row(engine, lost))["status"] == "scheduled"
    failed = await row(engine, hopeless)
    assert (failed["status"], failed["error_code"]) == ("failed", "internal")
    assert (await row(engine, recent))["status"] == "sending"
    entries = await published(redis, ws.wid)
    assert statuses(entries, str(lost)) == ["scheduled"]
    assert statuses(entries, str(hopeless)) == ["failed"]

    # The reset row is due again, so the next dispatcher tick claims it.
    assert await dispatch_due_messages(app.state.sessionmaker, redis, now=now) == [lost]


# ---- idempotency (TR-API-05) and following the message (Q-015)


async def test_the_same_idempotency_key_schedules_once(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis
) -> None:
    ws = await workspace(client, clerk, engine)
    at = iso(datetime.now(UTC) + timedelta(minutes=30))
    key = {"Idempotency-Key": "schedule-key-1"}
    url = f"{ws.base}/conversations/{ws.conversation_id}/scheduled-messages"
    body = {"text": "Your order ships today", "send_at": at}
    first = await client.post(url, json=body, headers={**ws.headers, **key})
    again = await client.post(url, json=body, headers={**ws.headers, **key})
    assert (first.status_code, again.status_code) == (201, 201)
    assert first.json()["id"] == again.json()["id"]
    changed = await client.post(url, json={**body, "text": "Other"}, headers={**ws.headers, **key})
    assert changed.status_code == 409
    assert changed.json()["code"] == "idempotency_conflict"
    async with engine.connect() as conn:
        count = (await conn.execute(text("SELECT count(*) FROM scheduled_messages"))).scalar_one()
    assert count == 1


async def _message_for(engine: AsyncEngine, ws: Ws, scheduled_id: str, **values: Any) -> uuid.UUID:
    async with engine.begin() as conn:
        account_id = (
            await conn.execute(
                text("SELECT social_account_id FROM conversations WHERE id = :c"),
                {"c": ws.conversation_id},
            )
        ).scalar_one()
        return uuid.UUID(
            str(
                (
                    await conn.execute(
                        text(
                            "INSERT INTO messages (workspace_id, conversation_id,"
                            " social_account_id, direction, source, kind, text, occurred_at,"
                            " status, error_code, error_message, scheduled_message_id)"
                            " VALUES (:w, :c, :a, 'outbound', 'human', 'text', 'x', now(),"
                            " :status, :code, :reason, :s) RETURNING id"
                        ),
                        {
                            "w": ws.wid,
                            "c": ws.conversation_id,
                            "a": account_id,
                            "s": scheduled_id,
                            "status": values.get("status", "failed"),
                            "code": values.get("code"),
                            "reason": values.get("reason"),
                        },
                    )
                ).scalar_one()
            )
        )


async def _follow(engine: AsyncEngine, ws: Ws, message_id: uuid.UUID, redis: Redis) -> None:
    with workspace_scope(uuid.UUID(ws.wid)):
        async with AsyncSession(engine) as session:
            msg = await session.get(Message, message_id)
            assert msg is not None
            await scheduled_service.follow_message(session, msg)
            await events.commit_and_publish(session, redis)


async def test_a_scheduled_message_shows_its_sends_result(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis
) -> None:
    """Q-015: sent at hand-over; failed if the send then fails; sent again after a retry."""
    ws = await workspace(client, clerk, engine)
    scheduled_id = (await schedule(client, ws)).json()["id"]
    await set_row(engine, scheduled_id, status="sent")
    message_id = await _message_for(
        engine, ws, scheduled_id, code="platform_rejected", reason="Instagram rejected this"
    )

    await _follow(engine, ws, message_id, redis)
    failed = await row(engine, scheduled_id)
    assert (failed["status"], failed["error_code"], failed["error_message"]) == (
        "failed",
        "platform_rejected",
        "Instagram rejected this",
    )
    assert failed["message_id"] == message_id

    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE messages SET status = 'sent', error_code = NULL WHERE id = :m"),
            {"m": message_id},
        )
    await _follow(engine, ws, message_id, redis)
    sent = await row(engine, scheduled_id)
    assert (sent["status"], sent["error_code"]) == ("sent", None)
    assert statuses(await published(redis, ws.wid), scheduled_id)[-2:] == ["failed", "sent"]


async def test_an_expired_or_canceled_row_is_left_alone(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis
) -> None:
    ws = await workspace(client, clerk, engine)
    scheduled_id = (await schedule(client, ws)).json()["id"]
    await set_row(engine, scheduled_id, status="canceled")
    message_id = await _message_for(engine, ws, scheduled_id, code="platform_rejected")
    await _follow(engine, ws, message_id, redis)
    assert (await row(engine, scheduled_id))["status"] == "canceled"
