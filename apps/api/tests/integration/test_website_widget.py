"""GR-28: the website chat widget. The settings routes and who may use them, the plan rule for
"Powered by Amplychat", the public widget API (session, send, receive, email, limits), the chat
as an inbox conversation of platform "web", an AI answer from knowledge and an inbox reply reaching
the visitor, and the files the embed serves."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing import plans
from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.platforms.deps import deps_from
from socialhood.security import widget_tokens as tokens
from socialhood.security.ratelimit import LIMITS, window_key
from socialhood.security.widget_tokens import visitor_id
from socialhood.services.suggestions import auto, service
from socialhood.services.widget import chat
from tests.support.ai import make_analysis, make_source
from tests.support.api import TOKEN_KEY, Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.ingest import stream
from tests.support.sending import clean_outbox, run_send, use_app_runtime
from tests.support.suggestions import SHIPPING_A, SHIPPING_Q, SHIPPING_REPLY, answer

HOST = "example.com"
CLIENT_IP = "127.0.0.1"  # httpx's ASGITransport


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@dataclass
class Site:
    """A signed-in owner whose widget allows ``example.com``, and the visitors who use it."""

    ws: Ws
    app: FastAPI
    engine: AsyncEngine
    widget_id: str

    @property
    def client(self) -> httpx.AsyncClient:
        return self.ws.client

    async def settings(self, **values: Any) -> dict[str, Any]:
        return await self.ws.ok("PUT", "/widget", json=values)

    async def session(
        self, *, host: str = HOST, key: str | None = None, widget_id: str | None = None
    ) -> httpx.Response:
        return await self.client.post(
            "/v1/widget/session",
            json={"widget_id": widget_id or self.widget_id, "host": host, "visitor_key": key},
        )

    async def visit(self, *, host: str = HOST, key: str | None = None) -> Visitor:
        response = await self.session(host=host, key=key)
        assert response.status_code == 200, response.text
        return Visitor(self, response.json())

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


@dataclass
class Visitor:
    site: Site
    opened: dict[str, Any]

    @property
    def key(self) -> str:
        return str(self.opened["visitor_key"])

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.opened['session_key']}"}

    @property
    def id(self) -> str:
        return visitor_id(self.key)

    async def send(self, body: str = "How much is shipping?", **extra: Any) -> httpx.Response:
        payload = {"text": body, "client_id": str(uuid.uuid4()), **extra}
        return await self.site.client.post(
            "/v1/widget/messages", json=payload, headers=self.headers
        )

    async def thread(self, **params: Any) -> httpx.Response:
        return await self.site.client.get(
            "/v1/widget/messages", params=params, headers=self.headers
        )

    async def messages(self) -> list[dict[str, Any]]:
        response = await self.thread()
        assert response.status_code == 200, response.text
        return list(response.json()["messages"])

    async def email(self, email: str = "pat@shop.example", **extra: Any) -> httpx.Response:
        return await self.site.client.post(
            "/v1/widget/email", json={"email": email, **extra}, headers=self.headers
        )


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, queue: None) -> Ws:
    return await workspace(client, clerk)


@pytest.fixture
async def site(app: FastAPI, engine: AsyncEngine, ws: Ws) -> Site:
    made = await ws.ok("GET", "/widget")
    await ws.ok("PUT", "/widget", json={"allowed_domains": [HOST]})
    return Site(ws, app, engine, made["widget_id"])


@pytest.fixture
def worker(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Any:
    return use_app_runtime(app, monkeypatch)


# ---------------------------------------------------------------- the settings routes


async def test_the_first_visit_makes_the_widget_and_the_embed_code(
    ws: Ws, site: Site, engine: AsyncEngine
) -> None:
    again = await ws.ok("GET", "/widget")
    assert again["widget_id"] == site.widget_id
    assert site.widget_id.startswith("wgt_")
    assert again["allowed_domains"] == [HOST]
    assert again["enabled"] is True
    assert again["script_url"].endswith("/widget.js")
    assert again["embed_snippet"] == (
        f'<script src="{again["script_url"]}" data-widget="{site.widget_id}" async></script>'
    )
    assert (again["email_capture"], again["position"], again["accent_color"]) == (
        "optional",
        "right",
        "#4467E6",
    )
    assert (again["conversations_today"], again["conversations_daily_limit"]) == (0, 50)
    rows = await site.rows(
        "SELECT platform, status, platform_account_id FROM social_accounts WHERE platform = 'web'"
    )
    assert rows == [
        {"platform": "web", "status": "active", "platform_account_id": site.widget_id}
    ]  # opening it again made nothing more


async def test_the_widget_account_is_listed_with_the_others(ws: Ws, site: Site) -> None:
    listed = await ws.ok("GET", "/social-accounts")
    web = [a for a in listed["items"] if a["platform"] == "web"]
    assert [(a["display_name"], a["ai_mode"], a["capabilities"]) for a in web] == [
        ("Website chat", "suggest", ["dm_send"])
    ]


async def test_changes_are_kept_and_domains_are_cleaned(ws: Ws, site: Site) -> None:
    saved = await site.settings(
        allowed_domains=["https://Shop.Example.com/page", "*.example.org", "shop.example.com"],
        accent_color="#0f766e",
        title="Ask Maple",
        greeting="Hello!",
        position="left",
        email_capture="required",
    )
    assert saved["allowed_domains"] == ["shop.example.com", "*.example.org"]
    assert (saved["accent_color"], saved["title"], saved["position"]) == (
        "#0F766E",
        "Ask Maple",
        "left",
    )
    assert (await ws.ok("GET", "/widget"))["email_capture"] == "required"


async def test_a_bad_domain_or_colour_names_the_field(ws: Ws, site: Site) -> None:
    bad = await ws.call("PUT", "/widget", json={"allowed_domains": ["ok.com", "not a domain"]})
    assert bad.status_code == 422, bad.text
    assert [e["field"] for e in bad.json()["errors"]] == ["allowed_domains.1"]
    assert (await ws.call("PUT", "/widget", json={"accent_color": "blue"})).status_code == 422
    assert (await ws.call("PUT", "/widget", json={"title": ""})).status_code == 422
    assert (await ws.call("PUT", "/widget", json={"enabled": None})).status_code == 422
    too_many = [f"site{i}.example.com" for i in range(21)]
    assert (await ws.call("PUT", "/widget", json={"allowed_domains": too_many})).status_code == 422
    assert (await ws.ok("GET", "/widget"))["allowed_domains"] == [HOST]  # nothing was saved


async def test_agents_cannot_read_or_change_the_settings(
    ws: Ws, site: Site, engine: AsyncEngine
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": ws.wid},
        )
    assert (await ws.call("GET", "/widget")).status_code == 403
    assert (await ws.call("PUT", "/widget", json={"title": "Mine"})).status_code == 403


# ---------------------------------------------------------------- "Powered by Amplychat" (PD-7)


async def test_free_shows_the_branding_and_pro_can_turn_it_off(
    ws: Ws, site: Site, engine: AsyncEngine
) -> None:
    free = await ws.ok("GET", "/widget")
    assert (free["show_branding"], free["can_remove_branding"]) == (True, False)
    refused = await ws.call("PUT", "/widget", json={"show_branding": False})
    assert refused.status_code == 402, refused.text
    assert refused.json()["code"] == "entitlement_required"
    assert refused.json()["entitlement"] == "widget_remove_branding"
    assert (await site.session()).json()["config"]["show_branding"] is True

    await set_plan(engine, ws.wid, "pro")
    pro = await site.settings(show_branding=False)
    assert (pro["show_branding"], pro["can_remove_branding"]) == (False, True)
    assert (await site.session()).json()["config"]["show_branding"] is False

    await set_plan(engine, ws.wid, "free")  # a downgrade keeps the choice but shows the link again
    assert (await site.session()).json()["config"]["show_branding"] is True
    assert (await ws.ok("GET", "/widget"))["show_branding"] is True
    await set_plan(engine, ws.wid, "max")
    assert (await site.session()).json()["config"]["show_branding"] is False


async def test_every_plan_has_the_widget(ws: Ws, site: Site, engine: AsyncEngine) -> None:
    for plan in ("free", "pro", "max"):
        await set_plan(engine, ws.wid, plan)
        assert (await site.session()).status_code == 200


# ---------------------------------------------------------------- sessions and sites


async def test_a_session_gives_the_config_and_a_new_visitor_key(site: Site) -> None:
    opened = (await site.session()).json()
    assert opened["expires_in"] > 3600
    assert opened["messages"] == []
    assert opened["version"] == "0.0"
    assert opened["config"]["greeting"] == "Hi! How can we help?"
    assert opened["config"]["email_known"] is False
    assert opened["visitor_key"]
    assert opened["session_key"]
    again = (await site.session(key=opened["visitor_key"])).json()
    assert again["visitor_key"] == opened["visitor_key"]  # the visitor keeps their key
    assert again["session_key"] != ""
    junk = (await site.session(key="short")).json()
    assert junk["visitor_key"] != "short"  # a malformed key is replaced, not trusted
    assert await site.rows("SELECT id FROM contacts") == []  # nothing is stored for a lurker


async def test_the_site_must_be_on_the_allowed_list(ws: Ws, site: Site) -> None:
    for host in ("evil.example", "example.com.evil.net", "shop.example.com", ""):
        response = await site.session(host=host or "x y")
        assert response.status_code in (403, 422), (host, response.text)
        if response.status_code == 403:
            assert response.json()["code"] == "forbidden"
    assert (await site.session(host="www.example.com")).status_code == 200  # www is the same site
    assert (await site.session(host="EXAMPLE.com")).status_code == 200
    await site.settings(allowed_domains=["*.example.com"])
    assert (await site.session(host="shop.example.com")).status_code == 200
    assert (await site.session(host="example.com")).status_code == 403
    await site.settings(allowed_domains=[])
    assert (await site.session()).status_code == 403  # no domain, no widget


async def test_an_unknown_or_switched_off_widget_is_not_found(ws: Ws, site: Site) -> None:
    assert (await site.session(widget_id="wgt_doesnotexist0000")).status_code == 404
    visitor = await site.visit()
    await site.settings(enabled=False)
    assert (await site.session()).status_code == 404
    assert (await visitor.send()).status_code == 404  # a live session stops with it
    assert (await visitor.thread()).status_code == 404


async def test_removing_a_domain_stops_a_live_session(site: Site) -> None:
    visitor = await site.visit()
    assert (await visitor.send()).status_code == 200
    await site.settings(allowed_domains=["other.example"])
    assert (await visitor.send("Still there?")).status_code == 403
    assert (await visitor.thread()).status_code == 403


async def test_a_browser_call_from_another_site_is_refused(site: Site) -> None:
    visitor = await site.visit()
    foreign = {"Origin": "https://evil.example"}
    sent = await site.client.post(
        "/v1/widget/messages",
        json={"text": "hi", "client_id": str(uuid.uuid4())},
        headers={**visitor.headers, **foreign},
    )
    assert sent.status_code == 403, sent.text
    assert (
        await site.client.get("/v1/widget/messages", headers={**visitor.headers, **foreign})
    ).status_code == 403
    assert (
        await site.client.post(
            "/v1/widget/session",
            json={"widget_id": site.widget_id, "host": HOST},
            headers=foreign,
        )
    ).status_code == 403
    own = {"Origin": "http://api.test"}  # the frame's own origin (the test client's host)
    ok = await site.client.get("/v1/widget/messages", headers={**visitor.headers, **own})
    assert ok.status_code == 200


async def test_a_missing_forged_or_expired_session_is_unauthorized(site: Site) -> None:
    visitor = await site.visit()
    for headers in ({}, {"Authorization": "Bearer nope"}, {"Authorization": "Basic abc"}):
        response = await site.client.get("/v1/widget/messages", headers=headers)
        assert response.status_code == 401, headers
        assert response.json()["code"] == "unauthorized"
    forged = visitor.headers["Authorization"][:-3] + "AAA"
    assert (
        await site.client.get("/v1/widget/messages", headers={"Authorization": forged})
    ).status_code == 401
    [account] = await site.rows(
        "SELECT id, workspace_id FROM social_accounts WHERE platform = 'web'"
    )
    expired, _ = tokens.issue(
        account_id=account["id"],
        workspace_id=account["workspace_id"],
        visitor=visitor.id,
        host=HOST,
        keys=[TOKEN_KEY],
        now=1.0,
    )
    stale = await site.client.get(
        "/v1/widget/messages", headers={"Authorization": f"Bearer {expired}"}
    )
    assert stale.status_code == 401
    assert stale.json()["code"] == "unauthorized"
    fresh, _ = tokens.issue(
        account_id=account["id"],
        workspace_id=account["workspace_id"],
        visitor=visitor.id,
        host=HOST,
        keys=[TOKEN_KEY],
    )
    live = await site.client.get(
        "/v1/widget/messages", headers={"Authorization": f"Bearer {fresh}"}
    )
    assert live.status_code == 200  # the same claim, not expired, is accepted


# ---------------------------------------------------------------- the chat is an inbox conversation


async def test_a_visitors_message_is_an_inbox_conversation_on_the_web_platform(
    ws: Ws, site: Site, redis: Redis
) -> None:
    visitor = await site.visit()
    sent = await visitor.send("Do you ship to Pune?")
    assert sent.status_code == 200, sent.text
    [mine] = sent.json()["messages"]
    assert (mine["author"], mine["text"]) == ("visitor", "Do you ship to Pune?")
    assert sent.json()["version"] != "0.0"

    [contact] = await site.rows("SELECT * FROM contacts")
    assert contact["platform_user_id"] == visitor.id
    assert visitor.key not in str(contact)
    assert contact["display_name"] == f"Visitor {visitor.id[-4:]}"
    [conv] = await site.rows("SELECT * FROM conversations")
    assert (conv["platform"], conv["awaiting_reply"], conv["unread_count"]) == ("web", True, 1)
    assert conv["entry_source"] == "organic"
    [message] = await site.rows("SELECT * FROM messages")
    assert (message["direction"], message["source"], message["status"]) == (
        "inbound",
        "customer",
        "received",
    )

    listed = await ws.ok("GET", "/conversations")
    [item] = [c for c in listed["items"] if c["platform"] == "web"]
    assert item["last_message_preview"] == "Do you ship to Pune?"
    assert item["reply_window_closes_at"] is None  # a website chat's window never closes
    kinds = [kind for kind, _ in await stream(redis, uuid.UUID(ws.wid))]
    assert {"message.created", "conversation.updated"} <= set(kinds)


async def test_the_same_client_id_stores_one_message(site: Site) -> None:
    visitor = await site.visit()
    body = {"text": "Hello", "client_id": str(uuid.uuid4())}
    first = await site.client.post("/v1/widget/messages", json=body, headers=visitor.headers)
    again = await site.client.post("/v1/widget/messages", json=body, headers=visitor.headers)
    assert first.status_code == again.status_code == 200
    assert first.json()["messages"] == again.json()["messages"]
    assert len(await site.rows("SELECT id FROM messages")) == 1


async def test_a_returning_visitor_sees_their_chat_and_keeps_one_conversation(site: Site) -> None:
    first = await site.visit()
    await first.send("One")
    await first.send("Two")
    back = await site.visit(key=first.key)
    assert [m["text"] for m in back.opened["messages"]] == ["One", "Two"]
    assert back.opened["version"] == (await first.thread()).json()["version"]
    await back.send("Three")
    assert len(await site.rows("SELECT id FROM conversations")) == 1
    other = await site.visit()
    await other.send("Different person")
    assert len(await site.rows("SELECT id FROM conversations")) == 2
    assert [m["text"] for m in await other.messages()] == ["Different person"]


# ---------------------------------------------------------------- email and consent


async def test_an_email_identifies_the_visitor_and_qualifies_the_lead(site: Site) -> None:
    visitor = await site.visit()
    await visitor.send("Hello")
    done = await visitor.email("  Pat@Shop.Example ", name="Pat Doe")
    assert done.status_code == 200, done.text
    assert done.json() == {"email_known": True}
    [contact] = await site.rows("SELECT * FROM contacts")
    assert (contact["email"], contact["email_source"], contact["email_verified"]) == (
        "pat@shop.example",
        "widget",
        False,
    )
    assert (contact["display_name"], contact["lead_stage"]) == ("Pat Doe", "qualified")
    assert await site.rows("SELECT id FROM contact_consents") == []  # no box ticked, nothing kept
    assert (await site.session(key=visitor.key)).json()["config"]["email_known"] is True
    wrong = await visitor.email("not-an-email")
    assert wrong.status_code == 422
    assert [e["field"] for e in wrong.json()["errors"]] == ["email"]


async def test_marketing_consent_is_recorded_with_the_words_shown(ws: Ws, site: Site) -> None:
    await site.settings(marketing_consent_enabled=True, marketing_consent_text="Email me offers.")
    visitor = await site.visit()
    assert (await visitor.email(marketing_consent=True)).status_code == 200
    [consent] = await site.rows("SELECT * FROM contact_consents")
    assert (consent["channel"], consent["status"], consent["source"]) == (
        "email",
        "granted",
        "widget",
    )
    evidence = consent["evidence"]
    assert evidence["text"] == "Email me offers."
    assert (evidence["host"], evidence["email"]) == (HOST, "pat@shop.example")
    assert evidence["widget_account_id"]
    datetime.fromisoformat(evidence["at"])
    [contact] = await site.rows("SELECT id FROM contacts")
    shown = await ws.ok("GET", f"/contacts/{contact['id']}")
    assert any(c["channel"] == "email" and c["status"] == "granted" for c in shown["consents"])


async def test_a_ticked_box_with_consent_switched_off_records_nothing(site: Site) -> None:
    visitor = await site.visit()
    assert (await visitor.email(marketing_consent=True)).status_code == 200
    assert await site.rows("SELECT id FROM contact_consents") == []


async def test_a_required_email_comes_before_the_first_message(site: Site) -> None:
    await site.settings(email_capture="required")
    visitor = await site.visit()
    blocked = await visitor.send("Hello")
    assert blocked.status_code == 422
    assert [e["field"] for e in blocked.json()["errors"]] == ["email"]
    assert await site.rows("SELECT id FROM messages") == []
    assert (await visitor.email()).status_code == 200  # the contact is made by the form
    assert (await visitor.send("Hello")).status_code == 200
    [contact] = await site.rows("SELECT * FROM contacts")
    assert contact["email"] == "pat@shop.example"
    assert len(await site.rows("SELECT id FROM conversations")) == 1


async def test_no_email_form_when_capture_is_off(site: Site) -> None:
    await site.settings(email_capture="off")
    visitor = await site.visit()
    assert (await visitor.email()).status_code == 404


# ---------------------------------------------------------------- abuse limits


async def test_spam_and_long_messages_are_refused_with_a_sentence(site: Site) -> None:
    visitor = await site.visit()
    for body in ("x" * 1500, "http://a.co http://b.co http://c.co", "a" * 40, "hi\x00there"):
        refused = await visitor.send(body)
        assert refused.status_code == 422, body
        assert [e["field"] for e in refused.json()["errors"]] == ["text"]
    assert (await visitor.send("")).status_code == 422
    assert (await visitor.send("x" * 2500)).status_code == 422  # over the schema's own cap
    assert await site.rows("SELECT id FROM messages") == []
    for _ in range(3):
        assert (await visitor.send("Buy now")).status_code == 200
    again = await visitor.send("buy now")
    assert again.status_code == 422
    assert "already sent" in again.json()["detail"]


async def test_new_chats_are_capped_per_plan_each_day(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(plans.ENTITLEMENTS["widget_conversations_daily"], "free", 2)
    first, second, third = await site.visit(), await site.visit(), await site.visit()
    assert (await first.send()).status_code == 200
    assert (await second.send()).status_code == 200
    capped = await third.send("Me too")
    assert capped.status_code == 429, capped.text
    assert capped.json()["code"] == "rate_limited"
    assert 60 <= int(capped.headers["retry-after"]) <= 86_400
    assert (await first.send("A second message")).status_code == 200  # open chats carry on
    assert (await site.ws.ok("GET", "/widget"))["conversations_today"] == 2


async def fill(redis: Redis, name: str, subject: str) -> None:
    limit = LIMITS[name]
    now_ms = int(time.time() * 1000)
    await redis.zadd(
        window_key(limit, subject), {f"fill-{i}": now_ms for i in range(limit.max_requests)}
    )
    await redis.expire(window_key(limit, subject), limit.window_s)


async def test_each_visitor_is_limited_on_their_own(site: Site, redis: Redis) -> None:
    busy, calm = await site.visit(), await site.visit()
    await fill(redis, "widget_send_visitor", busy.id)
    limited = await busy.send()
    assert limited.status_code == 429
    assert limited.json()["code"] == "rate_limited"
    assert 1 <= int(limited.headers["retry-after"]) <= 60
    assert (await calm.send()).status_code == 200
    await fill(redis, "widget_poll_visitor", busy.id)
    assert (await busy.thread()).status_code == 429


async def test_a_visitor_has_a_daily_message_cap(site: Site, redis: Redis) -> None:
    visitor = await site.visit()
    await fill(redis, "widget_send_day", visitor.id)
    assert (await visitor.send()).status_code == 429


async def test_each_ip_is_limited(site: Site, redis: Redis) -> None:
    visitor = await site.visit()
    for name, call in (
        ("widget_send_ip", visitor.send),
        ("widget_poll_ip", visitor.thread),
        ("widget_email_ip", visitor.email),
    ):
        await fill(redis, name, CLIENT_IP)
        assert (await call()).status_code == 429, name
    await fill(redis, "widget_session", CLIENT_IP)
    assert (await site.session()).status_code == 429
    await fill(redis, "widget_frame", CLIENT_IP)
    frame = await site.client.get("/widget/frame", params={"w": site.widget_id, "h": HOST})
    assert frame.status_code == 429


# ---------------------------------------------------------------- replies reach the widget


async def reply_from_inbox(site: Site, worker: Any, conversation_id: str, body: str) -> None:
    posted = await site.client.post(
        f"/v1/w/{site.ws.wid}/conversations/{conversation_id}/messages",
        json={"client_id": str(uuid.uuid4()), "text": body},
        headers={**site.ws.headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert posted.status_code in (200, 201, 202), posted.text
    message = posted.json()
    assert message["status"] == "queued"
    await run_send(site.ws, message)  # the send job, as the worker runs it


async def test_a_reply_from_the_inbox_reaches_the_widget(site: Site, worker: Any) -> None:
    visitor = await site.visit()
    await visitor.send("Do you ship to Pune?")
    [conv] = await site.rows("SELECT id FROM conversations")
    before = (await visitor.thread()).json()["version"]

    await reply_from_inbox(site, worker, str(conv["id"]), "Yes, we ship to Pune.")

    after = (await visitor.thread()).json()
    assert after["version"] != before
    assert [(m["author"], m["text"]) for m in after["messages"]] == [
        ("visitor", "Do you ship to Pune?"),
        ("team", "Yes, we ship to Pune."),
    ]
    [sent] = await site.rows("SELECT * FROM messages WHERE direction = 'outbound'")
    assert sent["status"] == "sent"
    assert sent["platform_message_id"].startswith("web_")


async def test_a_queued_or_failed_reply_is_not_shown(site: Site) -> None:
    visitor = await site.visit()
    await visitor.send("Hello")
    [conv] = await site.rows("SELECT id, social_account_id, workspace_id FROM conversations")
    for status in ("queued", "failed"):
        async with site.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO messages (workspace_id, conversation_id, social_account_id,"
                    " direction, source, kind, text, occurred_at, status)"
                    " VALUES (:w, :c, :a, 'outbound', 'human', 'text', :t, now(), :s)"
                ),
                {
                    "w": conv["workspace_id"],
                    "c": conv["id"],
                    "a": conv["social_account_id"],
                    "t": f"{status} reply",
                    "s": status,
                },
            )
    assert [m["author"] for m in await visitor.messages()] == ["visitor"]


async def test_a_waiting_poll_returns_as_soon_as_a_reply_is_sent(
    site: Site, worker: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(chat, "POLL_EVERY_S", 0.05)
    visitor = await site.visit()
    version = (await visitor.send("Anyone there?")).json()["version"]
    [conv] = await site.rows("SELECT id FROM conversations")

    waiting = asyncio.create_task(visitor.thread(version=version, wait=15))
    await asyncio.sleep(0.3)
    assert not waiting.done()  # nothing has changed, so the poll holds
    started = time.monotonic()
    await reply_from_inbox(site, worker, str(conv["id"]), "Right here.")
    response = await asyncio.wait_for(waiting, timeout=10)

    assert time.monotonic() - started < 5
    assert [m["text"] for m in response.json()["messages"]][-1] == "Right here."
    assert response.json()["version"] != version


async def test_a_poll_with_the_current_version_ends_empty_after_the_wait(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(chat, "POLL_EVERY_S", 0.05)
    visitor = await site.visit()
    version = (await visitor.send("Hello")).json()["version"]
    started = time.monotonic()
    response = await visitor.thread(version=version, wait=1)
    assert response.status_code == 200
    assert response.json()["version"] == version
    assert 0.8 <= time.monotonic() - started < 5
    assert (await visitor.thread(wait=21)).status_code == 422  # the wait is capped by the schema


# ---------------------------------------------------------------- AI answers from knowledge


async def test_the_ai_answers_a_website_visitor_from_knowledge(
    ws: Ws,
    site: Site,
    engine: AsyncEngine,
    redis: Redis,
    app: FastAPI,
    worker: Any,
    fake_ai: Any,
) -> None:
    await set_plan(engine, ws.wid, "pro")
    web = await site.rows("SELECT id FROM social_accounts WHERE platform = 'web'")
    await ws.ok("PATCH", f"/social-accounts/{web[0]['id']}", json={"ai_mode": "auto"})
    wid = uuid.UUID(ws.wid)
    await make_source(engine, workspace_id=wid, question=SHIPPING_Q, body=SHIPPING_A)
    visitor = await site.visit()
    await visitor.send(SHIPPING_Q)
    [conv] = await site.rows("SELECT id FROM conversations")
    [message] = await site.rows("SELECT id FROM messages")
    await make_analysis(
        engine,
        workspace_id=wid,
        conversation_id=conv["id"],
        message_id=message["id"],
        intent="shipping",
    )
    fake_ai.respond("suggest", answer())
    maker = make_sessionmaker(engine)
    with workspace_scope(wid):
        await service.generate(
            maker,
            redis,
            workspace_id=wid,
            conversation_id=conv["id"],
            message_id=message["id"],
            regeneration=0,
        )
    [suggestion] = await site.rows("SELECT id FROM reply_suggestions")
    deps = deps_from(app.state.http, app.state.settings)
    with workspace_scope(wid):
        decision = await auto.decide(maker, redis, deps, suggestion_id=suggestion["id"])
    assert decision is not None
    assert decision.outcome == "auto_sent"
    [ai_message] = await site.rows("SELECT * FROM messages WHERE source = 'ai_auto'")
    await run_send(ws, {"id": ai_message["id"], "conversation_id": conv["id"]})

    thread = await visitor.messages()
    assert [(m["author"], m["text"]) for m in thread] == [
        ("visitor", SHIPPING_Q),
        ("assistant", SHIPPING_REPLY),
    ]


async def test_an_escalation_flags_the_chat_as_needing_a_person(
    ws: Ws, site: Site, engine: AsyncEngine, redis: Redis, app: FastAPI, fake_ai: Any
) -> None:
    await set_plan(engine, ws.wid, "pro")
    web = await site.rows("SELECT id FROM social_accounts WHERE platform = 'web'")
    await ws.ok("PATCH", f"/social-accounts/{web[0]['id']}", json={"ai_mode": "auto"})
    wid = uuid.UUID(ws.wid)
    await make_source(engine, workspace_id=wid, question=SHIPPING_Q, body=SHIPPING_A)
    visitor = await site.visit()
    await visitor.send("I want a refund for my order")
    [conv] = await site.rows("SELECT id FROM conversations")
    [message] = await site.rows("SELECT id FROM messages")
    await make_analysis(
        engine,
        workspace_id=wid,
        conversation_id=conv["id"],
        message_id=message["id"],
        needs_human=True,
        needs_human_reason="refund",
    )
    fake_ai.respond("suggest", answer())
    maker = make_sessionmaker(engine)
    deps = deps_from(app.state.http, app.state.settings)
    with workspace_scope(wid):
        await service.generate(
            maker,
            redis,
            workspace_id=wid,
            conversation_id=conv["id"],
            message_id=message["id"],
            regeneration=0,
        )
        [suggestion] = await site.rows("SELECT id FROM reply_suggestions")
        decision = await auto.decide(maker, redis, deps, suggestion_id=suggestion["id"])
    assert decision is not None
    assert decision.outcome == "escalated"
    [flagged] = await site.rows("SELECT needs_human, needs_human_reason FROM conversations")
    assert flagged == {"needs_human": True, "needs_human_reason": "refund"}
    assert [m["author"] for m in await visitor.messages()] == ["visitor"]  # nothing was sent


# ---------------------------------------------------------------- the files the embed serves


async def test_the_embed_script_and_frame_files_are_served(site: Site) -> None:
    script = await site.client.get("/widget.js")
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert "max-age" in script.headers["cache-control"]
    assert len(script.content) < 8_000  # the embed itself stays tiny
    assert "data-widget" in script.text
    for path, kind in (("/widget/frame.js", "javascript"), ("/widget/frame.css", "css")):
        file = await site.client.get(path)
        assert file.status_code == 200
        assert kind in file.headers["content-type"]
    assert (await site.client.get("/widget/frame.js")).headers[
        "x-content-type-options"
    ] == "nosniff"


async def test_the_frame_is_served_only_to_an_allowed_site_and_names_it_in_its_policy(
    site: Site,
) -> None:
    ok = await site.client.get("/widget/frame", params={"w": site.widget_id, "h": HOST})
    assert ok.status_code == 200, ok.text
    policy = ok.headers["content-security-policy"]
    assert "frame-ancestors https://example.com https://www.example.com" in policy
    assert "script-src 'self'" in policy
    assert "default-src 'none'" in policy
    assert "x-frame-options" not in ok.headers
    assert f'data-widget="{site.widget_id}"' in ok.text
    assert 'data-host="example.com"' in ok.text
    assert '<script src="/widget/frame.js">' in ok.text
    assert ok.headers["cache-control"] == "no-store"

    for params, status in (
        ({"w": site.widget_id, "h": "evil.example"}, 403),
        ({"w": "wgt_doesnotexist0000", "h": HOST}, 404),
        ({"w": site.widget_id, "h": "exa mple"}, 404),
    ):
        refused = await site.client.get("/widget/frame", params=params)
        assert refused.status_code == status, params
        assert "frame-ancestors 'none'" in refused.headers["content-security-policy"]
        assert site.widget_id not in refused.text
    assert (await site.client.get("/widget/frame", params={"w": "x"})).status_code == 422


async def test_a_switched_off_widget_has_no_frame(site: Site) -> None:
    await site.settings(enabled=False)
    refused = await site.client.get("/widget/frame", params={"w": site.widget_id, "h": HOST})
    assert refused.status_code == 404


async def test_the_frame_ancestors_follow_the_domain_list(site: Site) -> None:
    await site.settings(allowed_domains=["*.example.org", "localhost"])
    ok = await site.client.get("/widget/frame", params={"w": site.widget_id, "h": "localhost"})
    policy = ok.headers["content-security-policy"]
    assert "https://*.example.org" in policy
    assert "http://localhost:*" in policy
    assert "example.com" not in policy


async def test_the_widget_routes_are_not_in_the_api_description(app: FastAPI) -> None:
    paths = app.openapi()["paths"]
    assert not [p for p in paths if p.startswith("/v1/widget") or p.startswith("/widget")]
    assert "/v1/w/{wid}/widget" in paths


async def test_the_settings_say_when_they_changed(site: Site) -> None:
    """The settings carry an updated_at the page can show."""
    saved = await site.settings(title="Updated")
    assert (
        abs((datetime.now(UTC) - datetime.fromisoformat(saved["updated_at"])).total_seconds()) < 60
    )
