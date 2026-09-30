"""A fake Instagram Graph API on the shared respx router, plus helpers to connect accounts and
sign webhook deliveries."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from tests.support.api import IG_APP_SECRET, Clerk

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "meta"
GRAPH = "https://graph.instagram.com"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def hub_signature(raw: bytes, secret: str = IG_APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def signed_delivery(body: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(body).encode()
    return raw, {"x-hub-signature-256": hub_signature(raw), "content-type": "application/json"}


@dataclass
class FakeInstagram:
    """Behaviour is plain attributes, so a test changes one and the next call follows it."""

    profile: dict[str, Any] = field(default_factory=lambda: fixture("me_business.json"))
    exchange: tuple[int, dict[str, Any]] = (200, fixture("oauth_access_token.json"))
    subscribe: tuple[int, dict[str, Any]] = (200, fixture("subscribed_apps_success.json"))
    refresh: tuple[int, dict[str, Any]] = (200, fixture("refresh_access_token.json"))
    tokens_seen: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    def use_account(self, user_id: str, username: str, app_scoped_id: str | None = None) -> None:
        self.profile = {
            **self.profile,
            "user_id": user_id,
            "username": username,
            "id": app_scoped_id or f"26{user_id[-15:]}",
        }

    def _auth(self, request: httpx.Request) -> None:
        header = request.headers.get("authorization", "")
        if header.startswith("Bearer "):
            self.tokens_seen.append(header.removeprefix("Bearer "))

    def _exchange(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("exchange")
        return httpx.Response(self.exchange[0], json=self.exchange[1])

    def _long_lived(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("long_lived")
        return httpx.Response(200, json=fixture("long_lived_token.json"))

    def _me(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("me")
        self._auth(request)
        return httpx.Response(200, json=self.profile)

    def _subscribe(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("subscribe")
        self._auth(request)
        return httpx.Response(self.subscribe[0], json=self.subscribe[1])

    def _refresh(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("refresh")
        return httpx.Response(self.refresh[0], json=self.refresh[1])


@pytest.fixture
def instagram(clerk: Clerk) -> FakeInstagram:
    """Routes on the same respx router as the fake Clerk, so both work in one test."""
    fake = FakeInstagram()
    router = clerk.router
    router.post(TOKEN_URL).mock(side_effect=fake._exchange)
    router.get(f"{GRAPH}/access_token").mock(side_effect=fake._long_lived)
    router.get(f"{GRAPH}/refresh_access_token").mock(side_effect=fake._refresh)
    router.post(url__regex=rf"{GRAPH}/v[\d.]+/me/subscribed_apps").mock(side_effect=fake._subscribe)
    router.get(url__regex=rf"{GRAPH}/v[\d.]+/me(\?.*)?$").mock(side_effect=fake._me)
    return fake


def state_from(authorize_url: str) -> str:
    return parse_qs(urlparse(authorize_url).query)["state"][0]


async def start_connect(client: httpx.AsyncClient, clerk: Clerk, clerk_id: str, wid: str) -> str:
    response = await client.post(
        f"/v1/w/{wid}/social-accounts/instagram/connect", headers=clerk.headers(clerk_id)
    )
    assert response.status_code == 200, response.text
    return state_from(response.json()["authorize_url"])


async def callback(client: httpx.AsyncClient, state: str, code: str = "code-1") -> str:
    """Instagram sends the browser back; returns the nonce the callback redirected with (X-1)."""
    response = await client.get(
        "/v1/oauth/instagram/callback", params={"code": code, "state": state}
    )
    query = redirect_query(response)
    assert "instagram" in query, query
    return query["instagram"]


async def complete(
    client: httpx.AsyncClient, clerk: Clerk, clerk_id: str, wid: str, nonce: str
) -> httpx.Response:
    """The signed-in Connections page finishes the connect with the nonce."""
    return await client.post(
        f"/v1/w/{wid}/social-accounts/instagram/complete",
        json={"nonce": nonce},
        headers=clerk.headers(clerk_id),
    )


async def connect(
    client: httpx.AsyncClient, clerk: Clerk, clerk_id: str, wid: str, *, code: str = "code-1"
) -> httpx.Response:
    """Run the whole connect flow (start, Instagram's callback, the page's complete) and return
    the complete response: 200 with the account, or the problem."""
    state = await start_connect(client, clerk, clerk_id, wid)
    nonce = await callback(client, state, code)
    return await complete(client, clerk, clerk_id, wid, nonce)


def redirect_query(response: httpx.Response) -> dict[str, str]:
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    return {k: v[0] for k, v in parse_qs(urlparse(location).query).items()} | {
        "_path": urlparse(location).path
    }
