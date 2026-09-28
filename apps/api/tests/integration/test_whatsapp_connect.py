"""T3.12: connecting WhatsApp through Embedded Signup (F-04, FR-CON-02) and the template picker's
list (FR-INB-10), against a fake Graph API."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.security.crypto import TokenCipher
from socialhood.services.connections import SUBSCRIBE_FAILED
from socialhood.services.whatsapp_templates import cache_key
from socialhood.settings import Settings
from tests.support.api import META_APP_SECRET, TOKEN_KEY, Clerk, sign_in
from tests.support.instagram import fixture
from tests.support.whatsapp import (
    BUSINESS_TOKEN,
    META_APP_ID,
    PHONE_NUMBER_ID,
    WABA_ID,
    FakeWhatsApp,
    install,
    signup,
    with_whatsapp,
)


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return with_whatsapp(api_settings)


@pytest.fixture
def whatsapp(clerk: Clerk) -> FakeWhatsApp:
    return install(clerk)


async def owner(
    client: httpx.AsyncClient, clerk: Clerk, email: str = "o@example.com"
) -> tuple[str, dict[str, Any]]:
    clerk_id, me = await sign_in(client, clerk, email=email)
    return clerk_id, me["workspaces"][0]


async def rows(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT * FROM social_accounts ORDER BY created_at"))
        return [dict(r._mapping) for r in result]


async def test_signup_stores_the_number_and_subscribes_its_business_account(
    client: httpx.AsyncClient, clerk: Clerk, whatsapp: FakeWhatsApp, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    response = await signup(client, clerk, clerk_id, ws["id"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["platform"], body["display_name"], body["phone_number"], body["status"]) == (
        "whatsapp",
        "Maple Bakery",
        "+91 98765 43210",
        "active",
    )
    assert body["capabilities"] == ["dm_attachments", "dm_send", "read_receipts", "templates"]
    assert body["token_expires_at"] is None

    assert whatsapp.calls == ["exchange", "number", "subscribe"]
    assert whatsapp.exchange_params == [
        {"client_id": META_APP_ID, "client_secret": META_APP_SECRET, "code": "wa-code-1"}
    ]
    assert whatsapp.tokens_seen == [BUSINESS_TOKEN, BUSINESS_TOKEN]

    [row] = await rows(engine)
    assert (row["platform"], row["platform_account_id"], row["waba_id"]) == (
        "whatsapp",
        PHONE_NUMBER_ID,
        WABA_ID,
    )
    assert row["webhooks_subscribed_at"] is not None
    assert row["connected_by_user_id"] is not None
    assert BUSINESS_TOKEN.encode() not in bytes(row["access_token_enc"])
    assert TokenCipher([TOKEN_KEY]).decrypt(row["access_token_enc"]) == BUSINESS_TOKEN

    listed = (
        await client.get(f"/v1/w/{ws['id']}/social-accounts", headers=clerk.headers(clerk_id))
    ).json()["items"]
    assert [(a["platform"], a["id"]) for a in listed] == [("whatsapp", body["id"])]


async def test_a_number_live_in_another_workspace_is_refused(
    client: httpx.AsyncClient, clerk: Clerk, whatsapp: FakeWhatsApp, engine: AsyncEngine
) -> None:
    a, ws_a = await owner(client, clerk, "a@example.com")
    b, ws_b = await owner(client, clerk, "b@example.com")
    assert (await signup(client, clerk, a, ws_a["id"])).status_code == 201
    refused = await signup(client, clerk, b, ws_b["id"])
    assert refused.status_code == 409
    assert refused.json()["code"] == "account_in_use"
    assert [str(r["workspace_id"]) for r in await rows(engine)] == [ws_a["id"]]


async def test_reconnecting_updates_the_same_row(
    client: httpx.AsyncClient, clerk: Clerk, whatsapp: FakeWhatsApp, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    await signup(client, clerk, clerk_id, ws["id"])
    [before] = await rows(engine)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET status = 'needs_reconnect', last_error = 'x'")
        )
    again = await signup(client, clerk, clerk_id, ws["id"], code="wa-code-2")
    assert again.status_code == 201
    [after] = await rows(engine)
    assert after["id"] == before["id"]
    assert (after["status"], after["last_error"]) == ("active", None)


async def test_the_free_plan_allows_one_whatsapp_number(
    client: httpx.AsyncClient, clerk: Clerk, whatsapp: FakeWhatsApp, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    await signup(client, clerk, clerk_id, ws["id"])
    whatsapp.calls.clear()
    second = await signup(client, clerk, clerk_id, ws["id"], phone_number_id="106540352240000")
    assert second.status_code == 402
    assert second.json()["code"] == "quota_exceeded"
    assert second.json()["detail"] == "Your plan includes 1 WhatsApp account."
    assert whatsapp.calls == []  # refused before the code was spent
    assert len(await rows(engine)) == 1


async def test_a_failed_exchange_stores_nothing(
    client: httpx.AsyncClient, clerk: Clerk, whatsapp: FakeWhatsApp, engine: AsyncEngine
) -> None:
    whatsapp.exchange = (400, {"error": {"message": "Invalid code", "code": 100}})
    clerk_id, ws = await owner(client, clerk)
    response = await signup(client, clerk, clerk_id, ws["id"])
    assert response.status_code == 502
    assert response.json()["code"] == "platform_error"
    assert "Invalid code" not in response.text  # provider bodies stay in the log
    assert await rows(engine) == []


async def test_a_failed_subscription_keeps_the_number_with_retry(
    client: httpx.AsyncClient, clerk: Clerk, whatsapp: FakeWhatsApp
) -> None:
    whatsapp.subscribe = (400, {"error": {"message": "Unsupported post request", "code": 100}})
    clerk_id, ws = await owner(client, clerk)
    response = await signup(client, clerk, clerk_id, ws["id"])
    assert response.status_code == 201
    assert (response.json()["status"], response.json()["last_error"]) == (
        "error",
        SUBSCRIBE_FAILED,
    )

    whatsapp.subscribe = (200, fixture("whatsapp_subscribed_apps_success.json"))
    retried = await client.post(
        f"/v1/w/{ws['id']}/social-accounts/{response.json()['id']}/resubscribe",
        headers=clerk.headers(clerk_id),
    )
    assert (retried.json()["status"], retried.json()["last_error"]) == ("active", None)


@pytest.mark.parametrize("field", ["waba_id", "phone_number_id"])
async def test_ids_must_be_metas_numeric_ids(
    client: httpx.AsyncClient, clerk: Clerk, whatsapp: FakeWhatsApp, field: str
) -> None:
    clerk_id, ws = await owner(client, clerk)
    response = await signup(client, clerk, clerk_id, ws["id"], **{field: "me/subscribed_apps"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == field
    assert whatsapp.calls == []


async def test_signup_needs_the_meta_app(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, whatsapp: FakeWhatsApp
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"meta_app_id": None})
    clerk_id, ws = await owner(client, clerk)
    response = await signup(client, clerk, clerk_id, ws["id"])
    assert response.status_code == 503
    assert whatsapp.calls == []


# ---------------------------------------------------------------- templates


async def test_the_picker_lists_approved_sendable_templates_from_a_short_cache(
    client: httpx.AsyncClient, clerk: Clerk, whatsapp: FakeWhatsApp, redis: Redis
) -> None:
    clerk_id, ws = await owner(client, clerk)
    account = (await signup(client, clerk, clerk_id, ws["id"])).json()
    url = f"/v1/w/{ws['id']}/social-accounts/{account['id']}/templates"

    response = await client.get(url, headers=clerk.headers(clerk_id))
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert [(t["name"], t["language"], t["param_count"]) for t in items] == [
        ("hello_again", "en_US", 0),
        ("order_update", "en", 2),
        ("order_update", "hi", 2),
    ]
    assert items[1] == {
        "name": "order_update",
        "language": "en",
        "category": "utility",
        "status": "approved",
        "body": "Hi {{1}}, your order {{2}} is on its way.",
        "param_count": 2,
    }
    assert whatsapp.calls.count("templates") == 2  # two pages

    again = await client.get(url, headers=clerk.headers(clerk_id))
    assert again.json() == response.json()
    assert whatsapp.calls.count("templates") == 2  # served from the cache
    assert 0 < await redis.ttl(cache_key(account["id"])) <= 300


async def test_instagram_accounts_have_no_templates(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, ws = await owner(client, clerk)
    sandbox = await client.post(
        f"/v1/w/{ws['id']}/dev/sandbox/accounts", headers=clerk.headers(clerk_id)
    )
    response = await client.get(
        f"/v1/w/{ws['id']}/social-accounts/{sandbox.json()['id']}/templates",
        headers=clerk.headers(clerk_id),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "capability_unavailable"


async def test_a_refused_token_asks_for_reconnect(
    client: httpx.AsyncClient, clerk: Clerk, whatsapp: FakeWhatsApp, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    account = (await signup(client, clerk, clerk_id, ws["id"])).json()
    whatsapp.templates = (401, fixture("error_190_expired.json"))
    url = f"/v1/w/{ws['id']}/social-accounts/{account['id']}/templates"

    response = await client.get(url, headers=clerk.headers(clerk_id))
    assert response.status_code == 409
    assert response.json()["code"] == "account_needs_reconnect"
    [row] = await rows(engine)
    assert row["status"] == "needs_reconnect"

    calls = whatsapp.calls.count("templates")
    again = await client.get(url, headers=clerk.headers(clerk_id))
    assert again.json()["code"] == "account_needs_reconnect"
    assert whatsapp.calls.count("templates") == calls  # no call with a known-bad token


async def test_a_platform_failure_is_a_502(
    client: httpx.AsyncClient, clerk: Clerk, whatsapp: FakeWhatsApp
) -> None:
    clerk_id, ws = await owner(client, clerk)
    account = (await signup(client, clerk, clerk_id, ws["id"])).json()
    whatsapp.templates = (500, {"error": {"message": "Service unavailable", "code": 2}})
    response = await client.get(
        f"/v1/w/{ws['id']}/social-accounts/{account['id']}/templates",
        headers=clerk.headers(clerk_id),
    )
    assert response.status_code == 502
    assert response.json()["code"] == "platform_error"
