"""T9.2 security pass: the obvious attacks, tried against the running app.

Tenant isolation has its own suite (tests/tenancy); SSRF is in tests/unit/test_ssrf.py and
tests/integration/test_knowledge.py; each webhook's own tests cover valid, invalid and replayed
signatures. These add the attacks that had no test of their own.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
from fastapi import FastAPI

from socialhood.auth.clerk import InvalidToken, verify_session_token
from socialhood.main import create_app
from socialhood.settings import Settings
from tests.support.api import WEB, Clerk, sign_in
from tests.support.identity import ISSUER, PARTY, Keys, make_token

# ---------------------------------------------------------------- session tokens (TR-AUTH-02)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _claims(sub: str = "user_abc") -> dict[str, Any]:
    now = int(time.time())
    return {"sub": sub, "iss": ISSUER, "azp": PARTY, "iat": now, "nbf": now, "exp": now + 60}


def test_an_unsigned_token_is_rejected(api_settings: Settings) -> None:
    token = jwt.encode(_claims(), key=None, algorithm="none")
    with pytest.raises(InvalidToken):
        verify_session_token(token, api_settings)


def test_a_token_signed_with_the_public_key_as_an_hmac_secret_is_rejected(
    keys: Keys, api_settings: Settings
) -> None:
    # Algorithm confusion: only RS256 is accepted, so the public key is never an HMAC secret.
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps(_claims()).encode())
    digest = hmac.new(keys.public_pem.encode(), f"{header}.{payload}".encode(), hashlib.sha256)
    token = f"{header}.{payload}.{_b64(digest.digest())}"
    with pytest.raises(InvalidToken):
        verify_session_token(token, api_settings)


@pytest.mark.parametrize(
    "overrides",
    [{"issuer": "https://clerk.attacker.example"}, {"azp": "https://attacker.example"}],
    ids=["wrong-issuer", "wrong-azp"],
)
async def test_the_api_refuses_a_token_for_another_issuer_or_party(
    client: httpx.AsyncClient, clerk: Clerk, keys: Keys, overrides: dict[str, str]
) -> None:
    clerk_id = clerk.add()
    token = make_token(keys, clerk_id, **overrides)
    response = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


# ---------------------------------------------------------------- bodies (SEC-08, TR-WH-01)


async def test_a_chunked_body_over_the_limit_is_refused(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    # No Content-Length: the middleware counts the streamed bytes instead.
    clerk_id, me = await sign_in(client, clerk)

    async def chunks() -> AsyncIterator[bytes]:
        yield b'{"name": "'
        for _ in range(17):
            yield b"x" * 65536
        yield b'"}'

    response = await client.patch(
        f"/v1/w/{me['workspaces'][0]['id']}",
        content=chunks(),
        headers={**clerk.headers(clerk_id), "content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


# ---------------------------------------------------------------- webhooks (SEC-04)


@pytest.mark.parametrize(
    ("path", "headers"),
    [
        ("/webhooks/instagram", {}),
        ("/webhooks/instagram", {"x-hub-signature-256": "sha256=" + "0" * 64}),
        ("/webhooks/whatsapp", {}),
        ("/webhooks/whatsapp", {"x-hub-signature-256": "sha256=" + "0" * 64}),
        ("/webhooks/clerk", {}),
        (
            "/webhooks/clerk",
            {"svix-id": "msg_1", "svix-timestamp": str(int(time.time())), "svix-signature": "v1,x"},
        ),
        ("/webhooks/dodo", {}),
        (
            "/webhooks/dodo",
            {
                "webhook-id": "msg_1",
                "webhook-timestamp": str(int(time.time())),
                "webhook-signature": "v1,AAAA",
            },
        ),
    ],
)
async def test_every_webhook_refuses_an_unsigned_or_forged_delivery(
    client: httpx.AsyncClient, path: str, headers: dict[str, str]
) -> None:
    body = b'{"object": "instagram", "type": "subscription.active", "data": {}}'
    response = await client.post(path, content=body, headers=headers)
    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/webhooks/instagram", "/webhooks/whatsapp"])
async def test_the_subscription_challenge_needs_the_verify_token(
    client: httpx.AsyncClient, path: str
) -> None:
    params = {"hub.mode": "subscribe", "hub.verify_token": "guess", "hub.challenge": "<script>"}
    response = await client.get(path, params=params)
    assert response.status_code == 403
    assert "<script>" not in response.text


# ---------------------------------------------------------------- redirects


@pytest.mark.parametrize(
    "params",
    [
        {"state": "forged", "code": "abc"},
        {"state": "forged", "error": "https://attacker.example"},
        {"code": "abc"},
    ],
)
async def test_the_oauth_callback_only_redirects_to_the_web_app(
    client: httpx.AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get("/v1/oauth/instagram/callback", params=params)
    assert response.status_code == 303
    assert response.headers["location"] == f"{WEB}/app?error=state_invalid"


# ---------------------------------------------------------------- CORS (SEC-05)


@pytest.fixture
async def cors_client(api_settings: Settings, clean_db: None) -> AsyncIterator[httpx.AsyncClient]:
    settings = api_settings.model_copy(update={"cors_allowed_origins": [WEB]})
    app: FastAPI = create_app(settings)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as c:
            yield c
    finally:
        await app.state.http.aclose()
        await app.state.redis.aclose()
        await app.state.engine.dispose()


async def test_cors_allows_only_the_configured_origin_without_credentials(
    cors_client: httpx.AsyncClient,
) -> None:
    preflight = {"Access-Control-Request-Method": "POST"}
    allowed = await cors_client.options("/v1/me", headers={"Origin": WEB, **preflight})
    assert allowed.headers["access-control-allow-origin"] == WEB
    assert "access-control-allow-credentials" not in allowed.headers

    for origin in ("https://attacker.example", f"{WEB}.attacker.example", "null"):
        refused = await cors_client.options("/v1/me", headers={"Origin": origin, **preflight})
        assert "access-control-allow-origin" not in refused.headers
        simple = await cors_client.get("/healthz", headers={"Origin": origin})
        assert "access-control-allow-origin" not in simple.headers
