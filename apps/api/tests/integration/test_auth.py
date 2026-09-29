"""T1.1 (TR-AUTH-01, TR-AUTH-02) and T1.2 provisioning (TR-AUTH-03, FR-ACC-02)."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.auth.clerk import InvalidToken, verify_session_token
from socialhood.models.identity import User
from socialhood.settings import Settings
from tests.support.api import Clerk, sign_in
from tests.support.identity import ISSUER, Keys, make_keys, make_token

# ---------------------------------------------------------------- token verification (T1.1)


def test_a_valid_token_yields_the_clerk_user_id(keys: Keys, api_settings: Settings) -> None:
    assert verify_session_token(make_token(keys, "user_abc"), api_settings) == "user_abc"


def test_an_expired_token_is_rejected(keys: Keys, api_settings: Settings) -> None:
    with pytest.raises(InvalidToken):
        verify_session_token(make_token(keys, "user_abc", expires_in=-60), api_settings)


def test_a_token_signed_with_another_key_is_rejected(api_settings: Settings) -> None:
    other = make_keys()
    with pytest.raises(InvalidToken):
        verify_session_token(make_token(other, "user_abc"), api_settings)


def test_a_wrong_authorized_party_is_rejected(keys: Keys, api_settings: Settings) -> None:
    token = make_token(keys, "user_abc", azp="https://evil.example")
    with pytest.raises(InvalidToken, match="invalid_azp"):
        verify_session_token(token, api_settings)


def test_a_token_without_azp_is_accepted(keys: Keys, api_settings: Settings) -> None:
    assert verify_session_token(make_token(keys, "user_abc", azp=None), api_settings) == "user_abc"


def test_a_wrong_issuer_or_missing_claim_is_rejected(keys: Keys, api_settings: Settings) -> None:
    with pytest.raises(InvalidToken):
        verify_session_token(make_token(keys, "u", issuer="https://other"), api_settings)
    with pytest.raises(InvalidToken):
        verify_session_token(make_token(keys, "u", omit=("nbf",)), api_settings)
    assert api_settings.clerk_issuer == ISSUER


async def test_missing_or_bad_authorization_is_401(client: httpx.AsyncClient) -> None:
    for headers in ({}, {"Authorization": "Bearer"}, {"Authorization": "Basic abc"}):
        response = await client.get("/v1/me", headers=headers)
        assert response.status_code == 401
        assert response.json()["code"] == "unauthorized"
    response = await client.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


# ---------------------------------------------------------------- provisioning (T1.2)


async def test_first_request_creates_user_workspace_and_defaults(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    _, me = await sign_in(client, clerk, first_name="Priya")
    assert me["email"] == "priya@example.com"
    assert me["name"] == "Priya Nair"
    [workspace] = me["workspaces"]
    assert workspace["name"] == "Priya's workspace"
    assert workspace["slug"] == "priyas-workspace"
    assert workspace["role"] == "owner"
    assert workspace["plan"] == "free"
    assert me["last_workspace_id"] == workspace["id"]

    async with engine.connect() as conn:
        counts = (
            await conn.execute(
                text(
                    "SELECT (SELECT count(*) FROM workspace_members),"
                    " (SELECT count(*) FROM subscriptions WHERE status = 'free'),"
                    " (SELECT count(*) FROM ai_settings),"
                    " (SELECT count(*) FROM agent_policies WHERE mode = 'read_only')"
                )
            )
        ).one()
    assert tuple(counts) == (1, 1, 1, 1)


async def test_a_user_without_a_name_gets_my_workspace(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    _, me = await sign_in(client, clerk, first_name=None, last_name=None)
    assert me["workspaces"][0]["name"] == "My workspace"
    assert me["name"] is None


async def test_slugs_stay_unique(client: httpx.AsyncClient, clerk: Clerk) -> None:
    _, first = await sign_in(client, clerk, email="a@example.com", first_name="Sam")
    _, second = await sign_in(client, clerk, email="b@example.com", first_name="Sam")
    assert first["workspaces"][0]["slug"] == "sams-workspace"
    assert second["workspaces"][0]["slug"].startswith("sams-workspace-")


async def test_ten_concurrent_first_requests_create_one_user_and_one_workspace(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id = clerk.add()
    headers = clerk.headers(clerk_id)
    responses = await asyncio.gather(*(client.get("/v1/me", headers=headers) for _ in range(10)))
    assert [r.status_code for r in responses] == [200] * 10
    assert len({r.json()["id"] for r in responses}) == 1
    async with engine.connect() as conn:
        users = await conn.scalar(select(func.count()).select_from(User))
        workspaces = await conn.scalar(text("SELECT count(*) FROM workspaces"))
    assert (users, workspaces) == (1, 1)


async def test_a_verified_email_links_to_the_existing_account(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    _, original = await sign_in(client, clerk, email="owner@example.com")
    # Same person, new Clerk id (for example after moving to the production Clerk instance).
    _, linked = await sign_in(client, clerk, email="OWNER@example.com", verified=True)
    assert linked["id"] == original["id"]
    assert linked["workspaces"] == original["workspaces"]


async def test_an_unverified_email_is_never_linked(client: httpx.AsyncClient, clerk: Clerk) -> None:
    _, original = await sign_in(client, clerk, email="owner@example.com")
    _, other = await sign_in(client, clerk, email="owner@example.com", verified=False)
    assert other["id"] != original["id"]
    assert other["workspaces"][0]["id"] != original["workspaces"][0]["id"]


async def test_clerk_being_down_is_a_clear_503(client: httpx.AsyncClient, clerk: Clerk) -> None:
    response = await client.get("/v1/me", headers=clerk.headers("user_not_in_clerk"))
    assert response.status_code == 503
    assert response.json()["code"] == "service_unavailable"


async def test_last_seen_is_written_at_most_once_per_window(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, _ = await sign_in(client, clerk)
    async with engine.connect() as conn:
        first = await conn.scalar(text("SELECT last_seen_at FROM users"))
    await client.get("/v1/me", headers=clerk.headers(clerk_id))
    async with engine.connect() as conn:
        second = await conn.scalar(text("SELECT last_seen_at FROM users"))
    assert first is not None
    assert second == first
