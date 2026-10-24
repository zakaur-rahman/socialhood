"""A fake Facebook Graph API on the shared respx router (Facebook Login, the Pages a person
manages, the webhook subscription), plus helpers to connect Pages and to sign Page webhook
deliveries with the Meta app secret (GR-29)."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.models.platform import WebhookStatus
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.facebook.webhooks import split_payload
from socialhood.repositories import webhook_events
from socialhood.services.webhook_processing import process_event
from socialhood.settings import Settings
from tests.support.api import META_APP_SECRET, Clerk
from tests.support.inbox import make_account, make_workspace
from tests.support.instagram import redirect_query, state_from
from tests.support.runtime import World

GRAPH = "https://graph.facebook.com"
META_APP_ID = "9876543210"
FB_REDIRECT = "http://api.test/v1/oauth/facebook/callback"
FB_VERIFY_TOKEN = "fake-facebook-verify-token"
USER_ID = "10161234567890123"
PAGE_ID = "109876543210001"
OTHER_PAGE_ID = "109876543210002"
PERSON = "7001234567890123"  # a customer's Page-scoped id
SHORT_TOKEN = "EAAGshort-user-token"
LONG_TOKEN = "EAAGlong-user-token"
PAGE_TOKEN = "EAAGpage-token-maple"
OTHER_PAGE_TOKEN = "EAAGpage-token-other"


def with_facebook(settings: Settings) -> Settings:
    """The API test settings plus what Facebook Pages need."""
    return settings.model_copy(
        update={
            "meta_app_id": META_APP_ID,
            "fb_redirect_uri": FB_REDIRECT,
            "fb_webhook_verify_token": SecretStr(FB_VERIFY_TOKEN),
        }
    )


def hub_signature(raw: bytes, secret: str = META_APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def signed_delivery(body: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode()
    return raw, {"x-hub-signature-256": hub_signature(raw), "content-type": "application/json"}


def page(
    page_id: str = PAGE_ID,
    name: str = "Maple Bakery",
    username: str | None = "maplebakery",
    token: str = PAGE_TOKEN,
    tasks: tuple[str, ...] = ("MANAGE", "MESSAGING", "MODERATE"),
) -> dict[str, Any]:
    return {
        "id": page_id,
        "name": name,
        "username": username,
        "access_token": token,
        "tasks": list(tasks),
        "picture": {"data": {"url": f"https://cdn.test/{page_id}.jpg"}},
    }


def _graph(path: str) -> str:
    return rf"^{GRAPH}/v[\d.]+/{path}(\?.*)?$"


@dataclass
class FakeFacebook:
    """Behaviour is plain attributes, so a test changes one and the next call follows it."""

    pages: list[dict[str, Any]] = field(
        default_factory=lambda: [
            page(),
            page(OTHER_PAGE_ID, "Maple Cafe", None, OTHER_PAGE_TOKEN),
            page("109876543210003", "Moderators only", "mods", "EAAGmods", ("ANALYZE",)),
        ]
    )
    subscribe: tuple[int, dict[str, Any]] = (200, {"success": True})
    exchange_status: int = 200
    calls: list[str] = field(default_factory=list)
    tokens_seen: list[str] = field(default_factory=list)
    subscribed_fields: list[str] = field(default_factory=list)

    def install(self, router: Any) -> None:
        router.get(url__regex=_graph("oauth/access_token")).mock(side_effect=self._token)
        router.get(url__regex=_graph("me/accounts")).mock(side_effect=self._accounts)
        router.post(url__regex=_graph("me/subscribed_apps")).mock(side_effect=self._subscribe)
        router.get(url__regex=_graph("me")).mock(side_effect=self._me)

    def _auth(self, request: httpx.Request) -> None:
        header = request.headers.get("authorization", "")
        if header.startswith("Bearer "):
            self.tokens_seen.append(header.removeprefix("Bearer "))

    def _token(self, request: httpx.Request) -> httpx.Response:
        query = {k: v[0] for k, v in parse_qs(urlparse(str(request.url)).query).items()}
        if query.get("grant_type") == "fb_exchange_token":
            self.calls.append("long_lived")
            assert query["fb_exchange_token"] == SHORT_TOKEN
            return httpx.Response(200, json={"access_token": LONG_TOKEN, "expires_in": 5183944})
        self.calls.append("exchange")
        if self.exchange_status != 200:
            return httpx.Response(
                self.exchange_status,
                json={"error": {"code": 100, "message": "This authorization code has expired."}},
            )
        return httpx.Response(200, json={"access_token": SHORT_TOKEN, "expires_in": 3600})

    def _me(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("me")
        self._auth(request)
        return httpx.Response(200, json={"id": USER_ID, "name": "Priya Shah"})

    def _accounts(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("accounts")
        self._auth(request)
        return httpx.Response(200, json={"data": self.pages})

    def _subscribe(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("subscribe")
        self._auth(request)
        query = {k: v[0] for k, v in parse_qs(urlparse(str(request.url)).query).items()}
        self.subscribed_fields.append(query.get("subscribed_fields", ""))
        return httpx.Response(self.subscribe[0], json=self.subscribe[1])


@pytest.fixture
def facebook(clerk: Clerk) -> FakeFacebook:
    """Routes on the same respx router as the fake Clerk, so both work in one test."""
    fake = FakeFacebook()
    fake.install(clerk.router)
    return fake


async def start_connect(
    client: httpx.AsyncClient, clerk: Clerk, clerk_id: str, wid: str
) -> httpx.Response:
    return await client.post(
        f"/v1/w/{wid}/social-accounts/facebook/connect", headers=clerk.headers(clerk_id)
    )


async def callback(client: httpx.AsyncClient, state: str, code: str = "code-1") -> str:
    """Facebook sends the browser back; returns the nonce the callback redirected with."""
    response = await client.get(
        "/v1/oauth/facebook/callback", params={"code": code, "state": state}
    )
    query = redirect_query(response)
    assert "facebook" in query, query
    return query["facebook"]


async def list_pages(
    client: httpx.AsyncClient, clerk: Clerk, clerk_id: str, wid: str, nonce: str
) -> httpx.Response:
    return await client.post(
        f"/v1/w/{wid}/social-accounts/facebook/pages",
        json={"nonce": nonce},
        headers=clerk.headers(clerk_id),
    )


async def connect_pages(
    client: httpx.AsyncClient,
    clerk: Clerk,
    clerk_id: str,
    wid: str,
    nonce: str,
    page_ids: list[str],
) -> httpx.Response:
    return await client.post(
        f"/v1/w/{wid}/social-accounts/facebook/connect-pages",
        json={"nonce": nonce, "page_ids": page_ids},
        headers=clerk.headers(clerk_id),
    )


async def connect(
    client: httpx.AsyncClient,
    clerk: Clerk,
    clerk_id: str,
    wid: str,
    page_ids: list[str] | None = None,
) -> httpx.Response:
    """Run the whole connect (start, Facebook's callback, the Page list, the pick) and return
    the connect-pages response."""
    started = await start_connect(client, clerk, clerk_id, wid)
    assert started.status_code == 200, started.text
    nonce = await callback(client, state_from(started.json()["authorize_url"]))
    listed = await list_pages(client, clerk, clerk_id, wid, nonce)
    assert listed.status_code == 200, listed.text
    return await connect_pages(client, clerk, clerk_id, wid, nonce, page_ids or [PAGE_ID])


# ---------------------------------------------------------------- Page events and sandbox Pages


async def deliver_page(
    maker: async_sessionmaker[AsyncSession],
    redis: Redis,
    body: dict[str, Any],
    *,
    copy: str = "",
) -> list[WebhookStatus | None]:
    """Store a Page delivery's events (``copy`` makes new dedupe keys) and process each like
    process_webhook_event does."""
    ids: list[uuid.UUID] = []
    async with maker() as session:
        for raw in split_payload(body):
            event_id = await webhook_events.store(
                session,
                provider="facebook",
                dedupe_key=raw.dedupe_key + copy,
                event_type=raw.event_type,
                payload=dict(raw.payload),
                platform_account_id=raw.account_ref,
            )
            assert event_id is not None, "already stored: pass copy=..."
            ids.append(event_id)
        await session.commit()
    return [await process_event(maker, event_id, redis) for event_id in ids]


def page_message(
    page_ref: str,
    text: str = "Do you deliver on Sundays?",
    *,
    mid: str = "m_in_1",
    sender: str = PERSON,
    **message: Any,
) -> dict[str, Any]:
    """A Messenger delivery: one message from ``sender`` to the Page."""
    return page_delivery(
        page_ref,
        messaging=[
            {
                "sender": {"id": sender},
                "recipient": {"id": page_ref},
                "timestamp": int(time.time() * 1000),
                "message": {"mid": mid, "text": text, **message},
            }
        ],
    )


def page_delivery(
    page_ref: str,
    *,
    messaging: list[dict[str, Any]] | None = None,
    changes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"id": page_ref, "time": int(time.time() * 1000)}
    if messaging is not None:
        entry["messaging"] = messaging
    if changes is not None:
        entry["changes"] = changes
    return {"object": "page", "entry": [entry]}


def page_comment(
    page_ref: str,
    comment_id: str,
    text: str = "LINK please",
    *,
    post_id: str | None = None,
    sender: str = PERSON,
    name: str = "Asha Rao",
    **value: Any,
) -> dict[str, Any]:
    """A new comment on a post of the Page (the ``feed`` field)."""
    post = post_id or f"{page_ref}_post_0"
    return page_delivery(
        page_ref,
        changes=[
            {
                "field": "feed",
                "value": {
                    "item": "comment",
                    "verb": "add",
                    "comment_id": comment_id,
                    "post_id": post,
                    "parent_id": post,
                    "from": {"id": sender, "name": name},
                    "message": text,
                    "created_time": int(time.time()),
                    **value,
                },
            }
        ],
    )


async def make_page_world(engine: AsyncEngine, redis: Redis, deps: PlatformDeps) -> World:
    """A workspace with one sandbox Facebook Page (the sandbox adapter serves it)."""
    wid = await make_workspace(engine)
    account_id = await make_account(engine, wid, platform="facebook", username="maplebakery")
    return World(engine, redis, deps, wid, account_id)
