"""The OAuth flow against the app under test (C-165 phase C): register a client, authorize,
consent as the signed-in member (the Clerk test user's session, as the dashboard page would),
exchange the code, refresh. Everything runs in-process against ``mcp_app``."""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI

from tests.support.mcp import BASE, http_client
from tests.support.sending import Setup

RESOURCE = f"{BASE}/mcp"
LOOPBACK = "http://127.0.0.1:33418/callback"
CHATGPT = "https://chatgpt.com/connector_platform_oauth_redirect"
FORM = {"Content-Type": "application/x-www-form-urlencoded"}


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def query(location: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}


@dataclass
class Flow:
    app: FastAPI
    client_id: str
    redirect_uri: str = LOOPBACK
    secret: str | None = None
    verifier: str = ""
    challenge: str = ""
    state: str = field(default_factory=lambda: secrets.token_urlsafe(8))

    def __post_init__(self) -> None:
        if not self.verifier:
            self.verifier, self.challenge = pkce()

    def authorize_params(self, **overrides: Any) -> dict[str, str]:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code_challenge": self.challenge,
            "code_challenge_method": "S256",
            "state": self.state,
            "resource": RESOURCE,
            "scope": "posts:read conversations:read offline_access",
        }
        params.update(overrides)
        return {k: v for k, v in params.items() if v is not None}

    async def authorize(self, **overrides: Any) -> Any:
        async with http_client(self.app, None) as http:
            return await http.get("/oauth/authorize", params=self.authorize_params(**overrides))

    async def request_id(self, **overrides: Any) -> str:
        response = await self.authorize(**overrides)
        assert response.status_code == 302, response.text
        location = response.headers["location"]
        assert "/connect/authorize?request=" in location
        return query(location)["request"]

    async def consent(self, setup: Setup, request_id: str) -> Any:
        async with http_client(self.app, None, **setup.headers) as http:
            return await http.get(f"/v1/connect/requests/{request_id}")

    async def approve(
        self,
        setup: Setup,
        request_id: str,
        *,
        scopes: list[str] | None = None,
        workspace_id: str | None = None,
    ) -> Any:
        body = {
            "workspace_id": workspace_id or setup.wid,
            "scopes": scopes if scopes is not None else ["posts:read", "conversations:read"],
        }
        async with http_client(self.app, None, **setup.headers) as http:
            return await http.post(f"/v1/connect/requests/{request_id}/approve", json=body)

    async def code(self, setup: Setup, **kwargs: Any) -> str:
        approved = await self.approve(setup, await self.request_id(), **kwargs)
        assert approved.status_code == 200, approved.text
        back = query(approved.json()["redirect_to"])
        assert back["state"] == self.state
        assert back["iss"] == BASE
        return back["code"]

    def _auth(self, form: dict[str, str]) -> dict[str, str]:
        form = {"client_id": self.client_id, **form}
        if self.secret is not None:
            form["client_secret"] = self.secret
        return form

    async def token(self, form: dict[str, str]) -> Any:
        async with http_client(self.app, None) as http:
            return await http.post("/oauth/token", data=self._auth(form), headers=FORM)

    async def exchange(self, code: str, **overrides: str) -> Any:
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": self.verifier,
            "resource": RESOURCE,
            **overrides,
        }
        return await self.token({k: v for k, v in form.items() if v is not None})

    async def tokens(self, setup: Setup, **kwargs: Any) -> dict[str, Any]:
        response = await self.exchange(await self.code(setup, **kwargs))
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    async def refresh(self, refresh_token: str, **extra: str) -> Any:
        return await self.token(
            {"grant_type": "refresh_token", "refresh_token": refresh_token, **extra}
        )

    async def revoke(self, token: str) -> Any:
        async with http_client(self.app, None) as http:
            return await http.post("/oauth/revoke", data=self._auth({"token": token}), headers=FORM)


async def register(app: FastAPI, *, redirect_uris: list[str] | None = None, **extra: Any) -> Any:
    body = {
        "client_name": "Inspector",
        "redirect_uris": [LOOPBACK] if redirect_uris is None else redirect_uris,
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        **extra,
    }
    async with http_client(app, None) as http:
        return await http.post("/oauth/register", json=body)


async def public_flow(app: FastAPI, redirect_uri: str = LOOPBACK) -> Flow:
    response = await register(app, redirect_uris=[redirect_uri])
    assert response.status_code == 201, response.text
    return Flow(app=app, client_id=response.json()["client_id"], redirect_uri=redirect_uri)
