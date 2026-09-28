"""T3.5: the inbox read APIs (FR-INB-01, 02, 04, 05; TR-PL-04; TR-API-04).

Views, filters and search run in SQL before the page is cut; cursors never skip or repeat rows,
even on ties; the detail shows the reply window at its boundaries; read, unread, archive and the
AI override emit conversation.updated.
"""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import time_machine
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.models.inbox import Conversation
from socialhood.realtime.events import stream_key
from socialhood.services import read_receipts
from tests.support.api import Clerk, sign_in
from tests.support.inbox import (
    Thread,
    make_account,
    make_scheduled,
    make_thread,
    make_workspace,
)

NOW = datetime.now(UTC).replace(microsecond=0)


@dataclass
class Owner:
    client: httpx.AsyncClient
    clerk: Clerk
    clerk_id: str
    user_id: str
    wid: str
    account_id: uuid.UUID

    async def call(
        self, method: str, path: str, *, json: Any = None, **params: Any
    ) -> httpx.Response:
        return await self.client.request(
            method,
            f"/v1/w/{self.wid}{path}",
            json=json,
            params={k: v for k, v in params.items() if v is not None},
            headers=self.clerk.headers(self.clerk_id),
        )

    async def ids(self, **params: Any) -> list[str]:
        response = await self.call("GET", "/conversations", **params)
        assert response.status_code == 200, response.text
        return [item["id"] for item in response.json()["items"]]

    async def detail(self, conversation_id: uuid.UUID) -> dict[str, Any]:
        response = await self.call("GET", f"/conversations/{conversation_id}")
        assert response.status_code == 200, response.text
        return response.json()  # type: ignore[no-any-return]


@pytest.fixture
async def owner(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Owner:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    account_id = await make_account(engine, wid)
    return Owner(client, clerk, clerk_id, me["id"], wid, account_id)


async def set_conversation(engine: AsyncEngine, conversation_id: uuid.UUID, **values: Any) -> None:
    assignments = ", ".join(f"{name} = :{name}" for name in values)
    async with engine.begin() as conn:
        await conn.execute(
            text(f"UPDATE conversations SET {assignments} WHERE id = :id"),  # noqa: S608
            {**values, "id": conversation_id},
        )


async def add_message(
    engine: AsyncEngine,
    owner: Owner,
    thread: Thread,
    *,
    body: str,
    at: datetime,
    source: str = "customer",
    sent_by: str | None = None,
    account_id: uuid.UUID | None = None,
) -> uuid.UUID:
    direction = "inbound" if source == "customer" else "outbound"
    async with engine.begin() as conn:
        return (  # type: ignore[no-any-return]
            await conn.execute(
                text(
                    "INSERT INTO messages (workspace_id, conversation_id, social_account_id,"
                    " direction, source, kind, text, occurred_at, status, sent_by_user_id)"
                    " VALUES (:w, :c, :a, :d, :s, 'text', :t, :at, :st, :u) RETURNING id"
                ),
                {
                    "w": owner.wid,
                    "c": thread.conversation_id,
                    "a": account_id or owner.account_id,
                    "d": direction,
                    "s": source,
                    "t": body,
                    "at": at,
                    "st": "received" if direction == "inbound" else "sent",
                    "u": sent_by,
                },
            )
        ).scalar_one()


async def thread_at(
    engine: AsyncEngine,
    owner: Owner,
    minutes_ago: float,
    *,
    account_id: uuid.UUID | None = None,
    platform: str = "instagram",
    **state: Any,
) -> Thread:
    """A conversation whose last message was ``minutes_ago``, with conversation ``state``."""
    names = {k: state.pop(k) for k in ("username", "display_name", "texts") if k in state}
    thread = await make_thread(
        engine,
        workspace_id=owner.wid,
        account_id=account_id or owner.account_id,
        platform=platform,
        **names,
    )
    await set_conversation(
        engine,
        thread.conversation_id,
        last_message_at=NOW - timedelta(minutes=minutes_ago),
        **state,
    )
    return thread


def ids_of(*threads: Thread) -> list[str]:
    return [str(t.conversation_id) for t in threads]


async def stream_events(redis: Redis, wid: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (fields["type"], json.loads(fields["data"]))
        for _, fields in await redis.xrange(stream_key(uuid.UUID(wid)))
    ]


# ---------------------------------------------------------------- list: views and filters


async def test_views(owner: Owner, engine: AsyncEngine) -> None:
    quiet = await thread_at(engine, owner, 1, unread_count=0, awaiting_reply=False)
    unread = await thread_at(engine, owner, 2, unread_count=2, awaiting_reply=True)
    lead = await thread_at(engine, owner, 3, unread_count=0, awaiting_reply=False, lead_score=60)
    cold = await thread_at(engine, owner, 4, unread_count=0, awaiting_reply=False, lead_score=59)
    archived = await thread_at(engine, owner, 5, unread_count=1, status="archived")
    by_ai = await thread_at(engine, owner, 6, unread_count=0, awaiting_reply=False)
    escalated = await thread_at(engine, owner, 7, unread_count=0, needs_human=True)
    for thread in (by_ai, escalated):
        await add_message(
            engine, owner, thread, body="Yes!", at=NOW - timedelta(hours=1), source="ai_auto"
        )

    assert await owner.ids() == ids_of(quiet, unread, lead, cold, by_ai, escalated)
    assert await owner.ids(view="unread") == ids_of(unread)
    assert await owner.ids(view="needs_reply") == ids_of(unread, escalated)
    assert await owner.ids(view="leads") == ids_of(lead)
    assert await owner.ids(view="ai_handled") == ids_of(by_ai)
    assert await owner.ids(view="archived") == ids_of(archived)

    item = (await owner.call("GET", "/conversations", view="unread")).json()["items"][0]
    assert item["contact"]["username"] == "priya.shah"
    assert item["unread_count"] == 2
    assert item["last_message_preview"] == "Do you ship to Pune?"
    assert item["signal"] is None


async def test_unknown_view_is_a_validation_error(owner: Owner) -> None:
    response = await owner.call("GET", "/conversations", view="spam")
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_a_busy_account_never_hides_another(owner: Owner, engine: AsyncEngine) -> None:
    whatsapp = await make_account(engine, owner.wid, platform="whatsapp", username="maple.wa")
    busy = [await thread_at(engine, owner, i) for i in range(35)]
    quiet = await thread_at(engine, owner, 600, account_id=whatsapp, platform="whatsapp")

    first = (await owner.call("GET", "/conversations", limit=30)).json()
    assert first["items"][0]["id"] == str(busy[0].conversation_id)
    assert str(quiet.conversation_id) not in [i["id"] for i in first["items"]]
    assert first["next_cursor"] is not None

    assert await owner.ids(platform="whatsapp", limit=30) == ids_of(quiet)
    assert await owner.ids(account_id=str(whatsapp), limit=30) == ids_of(quiet)
    assert await owner.ids(view="unread", platform="whatsapp", limit=30) == ids_of(quiet)
    assert await owner.ids(platform="instagram", account_id=str(whatsapp)) == []
    assert len(await owner.ids(platform="instagram", limit=100)) == 35


async def test_other_workspaces_are_never_listed_or_counted(
    owner: Owner, engine: AsyncEngine
) -> None:
    mine = await thread_at(engine, owner, 1)
    other = await make_workspace(engine)
    await make_thread(engine, workspace_id=other, account_id=await make_account(engine, other))

    assert await owner.ids() == ids_of(mine)
    assert await owner.ids(q="priya") == ids_of(mine)
    counts = (await owner.call("GET", "/conversations/counts")).json()
    assert counts == {"unread": 1, "needs_reply": 1, "needs_you": 0}


async def test_counts(owner: Owner, engine: AsyncEngine) -> None:
    await thread_at(engine, owner, 1, unread_count=2, awaiting_reply=True)
    await thread_at(engine, owner, 2, unread_count=0, awaiting_reply=True, needs_human=True)
    await thread_at(engine, owner, 3, unread_count=1, awaiting_reply=False)
    await thread_at(engine, owner, 4, unread_count=5, awaiting_reply=True, status="archived")

    response = await owner.call("GET", "/conversations/counts")
    assert response.status_code == 200
    assert response.json() == {"unread": 2, "needs_reply": 2, "needs_you": 1}


# ---------------------------------------------------------------- list: cursor (TR-API-04)


async def page_through(owner: Owner, path: str, limit: int, **params: Any) -> list[list[str]]:
    pages: list[list[str]] = []
    cursor: str | None = None
    while True:
        response = await owner.call("GET", path, cursor=cursor, limit=limit, **params)
        assert response.status_code == 200, response.text
        body = response.json()
        pages.append([item["id"] for item in body["items"]])
        cursor = body["next_cursor"]
        if cursor is None:
            return pages


async def test_cursor_pages_never_skip_or_repeat_ties(owner: Owner, engine: AsyncEngine) -> None:
    newest = await thread_at(engine, owner, 1)
    tied = [await thread_at(engine, owner, 5) for _ in range(6)]
    oldest = await thread_at(engine, owner, 9)

    pages = await page_through(owner, "/conversations", limit=3)
    tied_order = sorted((str(t.conversation_id) for t in tied), key=uuid.UUID, reverse=True)
    expected = [str(newest.conversation_id), *tied_order, str(oldest.conversation_id)]
    assert [len(p) for p in pages] == [3, 3, 2]
    assert [i for page in pages for i in page] == expected


def b64(value: Any) -> str:
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "cursor",
    [
        "nope",
        b64([1]),
        b64({"at": 1}),
        b64(["2026-09-28T12:00:00+00:00", "not-a-uuid"]),
        b64(["2026-09-28T12:00:00", str(uuid.uuid4())]),  # no time zone
    ],
)
async def test_a_bad_cursor_is_a_validation_error(
    owner: Owner, engine: AsyncEngine, cursor: str
) -> None:
    thread = await thread_at(engine, owner, 1)
    for path in ("/conversations", f"/conversations/{thread.conversation_id}/messages"):
        response = await owner.call("GET", path, cursor=cursor)
        assert response.status_code == 422, path
        assert response.json()["errors"][0]["field"] == "cursor"


# ---------------------------------------------------------------- list: search


async def test_search_by_name_username_and_message_text(owner: Owner, engine: AsyncEngine) -> None:
    priya = await thread_at(
        engine,
        owner,
        1,
        display_name="Priya Shah",
        username="priya.shah",
        texts=("Do you ship to Pune?",),
    )
    rohan = await thread_at(
        engine,
        owner,
        2,
        display_name="Rohan K",
        username="rohan_k",
        texts=("My order #4821 hasn't arrived",),
    )
    hindi = await thread_at(
        engine,
        owner,
        3,
        display_name=None,
        username="100%_real",
        texts=("क्या आप दिल्ली में डिलीवर करते हैं?",),
    )

    cases = {
        "priya": [priya],
        "SHAH": [priya],
        "@rohan": [rohan],
        "pun": [priya],  # a word prefix, for search as you type
        "ship pune": [priya],
        "order 4821": [rohan],
        "दिल्ली": [hindi],
        "100%": [hindi],  # LIKE wildcards are literal
        "_": [rohan, hindi],
        "   ": [priya, rohan, hindi],
        "zanzibar": [],
    }
    for q, expected in cases.items():
        assert await owner.ids(q=q) == ids_of(*expected), q

    await set_conversation(engine, priya.conversation_id, status="archived")
    assert await owner.ids(q="priya") == []
    assert await owner.ids(q="priya", view="archived") == ids_of(priya)


# ---------------------------------------------------------------- detail (§5.10, TR-PL-04)

T0 = datetime(2026, 9, 28, 12, tzinfo=UTC)
JUST = timedelta(seconds=1)


@pytest.mark.parametrize(
    ("platform", "human_agent", "elapsed", "state", "closes_after"),
    [
        ("instagram", False, timedelta(hours=24) - JUST, "open", timedelta(hours=24)),
        ("instagram", False, timedelta(hours=24), "closed", None),
        ("instagram", True, timedelta(hours=24), "human_agent", timedelta(days=7)),
        ("instagram", True, timedelta(days=7) - JUST, "human_agent", timedelta(days=7)),
        ("instagram", True, timedelta(days=7), "closed", None),
        ("whatsapp", True, timedelta(hours=24) - JUST, "open", timedelta(hours=24)),
        ("whatsapp", True, timedelta(hours=24), "template_only", None),
    ],
)
async def test_reply_window_at_the_boundaries(
    owner: Owner,
    engine: AsyncEngine,
    app: FastAPI,
    platform: str,
    human_agent: bool,
    elapsed: timedelta,
    state: str,
    closes_after: timedelta | None,
) -> None:
    app.state.settings.ig_human_agent_enabled = human_agent
    account = (
        owner.account_id
        if platform == "instagram"
        else await make_account(engine, owner.wid, platform="whatsapp", username="maple.wa")
    )
    thread = await make_thread(
        engine, workspace_id=owner.wid, account_id=account, platform=platform, last_inbound_at=T0
    )
    with time_machine.travel(T0 + elapsed, tick=False):
        body = await owner.detail(thread.conversation_id)
        listed = (await owner.call("GET", "/conversations")).json()["items"]

    assert [i["reply_window_closes_at"] for i in listed] == [body["reply_window_closes_at"]]
    closes_at = body["reply_window"]["closes_at"]
    assert body["reply_window"]["state"] == state
    assert (datetime.fromisoformat(closes_at) if closes_at else None) == (
        T0 + closes_after if closes_after else None
    )
    # The list's "Closing in 3h" chip only counts the standard window.
    expected_chip = T0 + timedelta(hours=24) if state == "open" else None
    chip = body["reply_window_closes_at"]
    assert (datetime.fromisoformat(chip) if chip else None) == expected_chip


async def test_a_conversation_without_an_inbound_message_is_closed(
    owner: Owner, engine: AsyncEngine
) -> None:
    thread = await make_thread(
        engine, workspace_id=owner.wid, account_id=owner.account_id, direction="outbound"
    )
    assert (await owner.detail(thread.conversation_id))["reply_window"] == {
        "state": "closed",
        "closes_at": None,
    }


async def test_closing_soon_signal(owner: Owner, engine: AsyncEngine) -> None:
    thread = await make_thread(
        engine, workspace_id=owner.wid, account_id=owner.account_id, last_inbound_at=T0
    )
    with time_machine.travel(T0 + timedelta(hours=22), tick=False):
        assert (await owner.detail(thread.conversation_id))["signal"] == "closing_soon"


async def test_conversation_detail(owner: Owner, engine: AsyncEngine) -> None:
    thread = await make_thread(engine, workspace_id=owner.wid, account_id=owner.account_id)
    conv = thread.conversation_id
    await make_scheduled(engine, workspace_id=owner.wid, conversation_id=conv)
    await make_scheduled(engine, workspace_id=owner.wid, conversation_id=conv, status="canceled")
    await make_scheduled(engine, workspace_id=owner.wid, conversation_id=conv, status="sent")

    body = await owner.detail(conv)
    assert body["id"] == str(conv)
    assert body["platform"] == "instagram"
    assert body["contact"]["id"] == str(thread.contact_id)
    assert body["contact"]["platform_user_id"].startswith("igsid_")
    assert body["contact"]["first_seen_at"] is not None
    assert body["social_account"] == {
        "id": str(owner.account_id),
        "username": "maple.bakery",
        "display_name": None,
        "status": "active",
    }
    assert body["ai"] == {"effective_mode": "suggest", "override": None, "paused_until": None}
    assert body["scheduled_count"] == 1
    assert body["latest_analysis"] is None
    assert body["pending_suggestion"] is None
    assert body["summary"] is None
    assert body["last_inbound_at"] is not None  # the reply window's anchor (Q-022)

    paused = datetime.now(UTC) + timedelta(hours=1)
    await set_conversation(engine, conv, ai_mode_override="off", ai_paused_until=paused)
    ai = (await owner.detail(conv))["ai"]
    assert ai["effective_mode"] == "off"
    assert ai["override"] == "off"
    assert datetime.fromisoformat(ai["paused_until"]) == paused

    await set_conversation(engine, conv, ai_paused_until=datetime.now(UTC) - timedelta(minutes=1))
    assert (await owner.detail(conv))["ai"]["paused_until"] is None


async def test_a_pause_until_resumed_reads_back(owner: Owner, engine: AsyncEngine) -> None:
    """A takeover of 0 minutes stores 'infinity' (§5.4); it must read back and compare."""
    conv = (
        await make_thread(engine, workspace_id=owner.wid, account_id=owner.account_id)
    ).conversation_id
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE conversations SET ai_paused_until = 'infinity' WHERE id = :id"),
            {"id": conv},
        )
    paused_until = (await owner.detail(conv))["ai"]["paused_until"]
    assert paused_until is not None
    assert paused_until.startswith("9999-12-31")


async def test_an_unknown_conversation_is_not_found(owner: Owner) -> None:
    missing = uuid.uuid4()
    for method, path in [
        ("GET", f"/conversations/{missing}"),
        ("GET", f"/conversations/{missing}/messages"),
        ("POST", f"/conversations/{missing}/read"),
        ("POST", f"/conversations/{missing}/unread"),
    ]:
        response = await owner.call(method, path)
        assert response.status_code == 404, path
        assert response.json()["code"] == "not_found"


# ---------------------------------------------------------------- changes (FR-INB-04, 05)


async def test_archive_and_unarchive(owner: Owner, engine: AsyncEngine, redis: Redis) -> None:
    thread = await thread_at(engine, owner, 1)
    conv = thread.conversation_id

    response = await owner.call("PATCH", f"/conversations/{conv}", json={"status": "archived"})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "archived"
    assert await owner.ids() == []
    assert await owner.ids(view="archived") == ids_of(thread)

    again = await owner.call("PATCH", f"/conversations/{conv}", json={"status": "archived"})
    assert again.status_code == 200
    reopened = await owner.call("PATCH", f"/conversations/{conv}", json={"status": "open"})
    assert reopened.json()["status"] == "open"

    published = await stream_events(redis, owner.wid)
    assert [(kind, p["conversation"]["status"]) for kind, p in published] == [
        ("conversation.updated", "archived"),
        ("conversation.updated", "open"),
    ]
    assert published[0][1]["conversation"]["id"] == str(conv)


async def test_ai_mode_override(owner: Owner, engine: AsyncEngine, redis: Redis) -> None:
    thread = await thread_at(engine, owner, 1)
    path = f"/conversations/{thread.conversation_id}"

    off = await owner.call("PATCH", path, json={"ai_mode_override": "off"})
    assert off.status_code == 200, off.text
    assert off.json()["ai"] == {"effective_mode": "off", "override": "off", "paused_until": None}

    auto = await owner.call("PATCH", path, json={"ai_mode_override": "auto"})
    assert auto.status_code == 402
    assert auto.json()["code"] == "entitlement_required"

    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE subscriptions SET plan = 'pro' WHERE workspace_id = :w"), {"w": owner.wid}
        )
    auto = await owner.call("PATCH", path, json={"ai_mode_override": "auto"})
    assert auto.json()["ai"]["effective_mode"] == "auto"

    cleared = await owner.call("PATCH", path, json={"clear_ai_mode_override": True})
    assert cleared.json()["ai"] == {
        "effective_mode": "suggest",
        "override": None,
        "paused_until": None,
    }

    both = await owner.call(
        "PATCH", path, json={"ai_mode_override": "off", "clear_ai_mode_override": True}
    )
    assert both.status_code == 422
    unknown = await owner.call("PATCH", path, json={"assigned_to": "someone"})
    assert unknown.status_code == 422

    assert [kind for kind, _ in await stream_events(redis, owner.wid)] == [
        "conversation.updated"
    ] * 3


async def test_read_and_unread(
    owner: Owner, engine: AsyncEngine, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipts: list[tuple[uuid.UUID, int]] = []

    async def after_marked_read(session: object, conv: Conversation) -> None:
        receipts.append((conv.id, conv.unread_count))

    monkeypatch.setattr(read_receipts, "after_marked_read", after_marked_read)
    thread = await thread_at(engine, owner, 1, unread_count=3)
    conv = thread.conversation_id

    assert (await owner.call("POST", f"/conversations/{conv}/read")).status_code == 204
    assert (await owner.detail(conv))["unread_count"] == 0
    assert receipts == [(conv, 0)]
    assert (await owner.call("GET", "/conversations/counts")).json()["unread"] == 0

    assert (await owner.call("POST", f"/conversations/{conv}/read")).status_code == 204
    assert receipts == [(conv, 0)]  # nothing changed: no receipt, no event

    assert (await owner.call("POST", f"/conversations/{conv}/unread")).status_code == 204
    assert (await owner.detail(conv))["unread_count"] == 1
    assert (await owner.call("POST", f"/conversations/{conv}/unread")).status_code == 204
    await set_conversation(engine, conv, unread_count=3)
    assert (await owner.call("POST", f"/conversations/{conv}/unread")).status_code == 204
    assert (await owner.detail(conv))["unread_count"] == 3  # max(1, unread_count)

    published = await stream_events(redis, owner.wid)
    assert [(kind, p["conversation"]["unread_count"]) for kind, p in published] == [
        ("conversation.updated", 0),
        ("conversation.updated", 1),
    ]


# ---------------------------------------------------------------- messages (FR-INB-02)


async def test_messages_newest_first_with_older_pages(owner: Owner, engine: AsyncEngine) -> None:
    thread = await make_thread(
        engine,
        workspace_id=owner.wid,
        account_id=owner.account_id,
        texts=("one", "two", "three", "four", "five"),
    )
    reply = await add_message(
        engine,
        owner,
        thread,
        body="six",
        at=datetime.now(UTC),
        source="human",
        sent_by=owner.user_id,
    )
    path = f"/conversations/{thread.conversation_id}/messages"

    first = (await owner.call("GET", path, limit=2)).json()
    assert [m["text"] for m in first["items"]] == ["six", "five"]
    assert first["items"][0]["id"] == str(reply)
    assert first["items"][0]["sent_by"] == {"id": owner.user_id, "name": "Priya Nair"}
    assert first["items"][1]["sent_by"] is None
    assert first["items"][1]["direction"] == "inbound"

    second = (await owner.call("GET", path, limit=2, cursor=first["next_cursor"])).json()
    third = (await owner.call("GET", path, limit=2, cursor=second["next_cursor"])).json()
    assert [m["text"] for m in second["items"]] == ["four", "three"]
    assert [m["text"] for m in third["items"]] == ["two", "one"]
    assert third["next_cursor"] is None


async def test_message_pages_never_skip_or_repeat_ties(owner: Owner, engine: AsyncEngine) -> None:
    thread = await make_thread(engine, workspace_id=owner.wid, account_id=owner.account_id)
    at = datetime.now(UTC) + timedelta(minutes=5)
    tied = [str(await add_message(engine, owner, thread, body=f"t{i}", at=at)) for i in range(6)]

    pages = await page_through(owner, f"/conversations/{thread.conversation_id}/messages", 4)
    expected = [*sorted(tied, key=uuid.UUID, reverse=True), str(thread.message_ids[0])]
    assert [i for page in pages for i in page] == expected
