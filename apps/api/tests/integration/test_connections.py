"""T2.2-T2.4: connecting Instagram (F-03), account settings and disconnect (FR-CON-01...06)."""

from __future__ import annotations

from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.security.crypto import TokenCipher
from socialhood.services.connections import SUBSCRIBE_FAILED
from tests.support.api import TOKEN_KEY, WEB, Clerk, sign_in
from tests.support.instagram import (
    FakeInstagram,
    connect,
    fixture,
    redirect_query,
    start_connect,
)


async def owner(
    client: httpx.AsyncClient, clerk: Clerk, email: str = "o@example.com"
) -> tuple[str, dict[str, Any]]:
    clerk_id, me = await sign_in(client, clerk, email=email)
    return clerk_id, me["workspaces"][0]


async def rows(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT * FROM social_accounts ORDER BY created_at"))
        return [dict(r._mapping) for r in result]


async def test_start_stores_a_single_use_state(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, redis: Redis
) -> None:
    clerk_id, ws = await owner(client, clerk)
    state = await start_connect(client, clerk, clerk_id, ws["id"])
    ttl = await redis.ttl(f"oauth:{state}")
    assert 0 < ttl <= 600


async def test_a_successful_connect_stores_an_encrypted_token_and_subscribes(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    query = redirect_query(await connect(client, clerk, clerk_id, ws["id"]))
    assert query == {
        "connected": "instagram",
        "_path": f"/w/{ws['slug']}/settings/connections",
    }

    [row] = await rows(engine)
    assert row["platform_account_id"] == "17841400000000001"
    assert row["app_scoped_id"] == "26000000000000001"
    assert row["status"] == "active"
    assert row["webhooks_subscribed_at"] is not None
    assert b"IGQVJ" not in bytes(row["access_token_enc"])
    assert TokenCipher([TOKEN_KEY]).decrypt(row["access_token_enc"]) == "IGQVJlong-lived-token"
    assert instagram.tokens_seen == ["IGQVJlong-lived-token", "IGQVJlong-lived-token"]

    listed = (
        await client.get(f"/v1/w/{ws['id']}/social-accounts", headers=clerk.headers(clerk_id))
    ).json()["items"]
    assert [a["username"] for a in listed] == ["maple.bakery"]
    assert "post_insights" not in listed[0]["capabilities"]
    assert "dm_send" in listed[0]["capabilities"]
    assert listed[0]["sandbox"] is False

    overview = (
        await client.get(f"/v1/w/{ws['id']}/overview", headers=clerk.headers(clerk_id))
    ).json()
    steps = {s["key"]: s["done"] for s in overview["checklist"]["steps"]}
    assert steps["connect_account"] is True


async def test_a_state_works_once(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram
) -> None:
    clerk_id, ws = await owner(client, clerk)
    state = await start_connect(client, clerk, clerk_id, ws["id"])
    params = {"code": "c", "state": state}
    first = await client.get("/v1/oauth/instagram/callback", params=params)
    again = await client.get("/v1/oauth/instagram/callback", params=params)
    assert redirect_query(first)["connected"] == "instagram"
    assert redirect_query(again) == {"error": "state_invalid", "_path": "/app"}
    assert again.headers["location"].startswith(WEB)


async def test_an_unknown_state_is_refused(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/v1/oauth/instagram/callback", params={"code": "c", "state": "forged"}
    )
    assert redirect_query(response) == {"error": "state_invalid", "_path": "/app"}


async def test_cancelling_on_instagram(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    state = await start_connect(client, clerk, clerk_id, ws["id"])
    response = await client.get(
        "/v1/oauth/instagram/callback",
        params={"state": state, "error": "access_denied", "error_reason": "user_denied"},
    )
    assert redirect_query(response)["error"] == "access_denied"
    assert instagram.calls == []
    assert await rows(engine) == []


async def test_a_failed_exchange(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    instagram.exchange = (400, {"error_type": "OAuthException", "code": 400, "error_message": "x"})
    clerk_id, ws = await owner(client, clerk)
    assert redirect_query(await connect(client, clerk, clerk_id, ws["id"]))["error"] == (
        "connect_failed"
    )
    assert await rows(engine) == []


async def test_a_personal_account_cannot_connect(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    instagram.profile = fixture("me_personal.json")
    clerk_id, ws = await owner(client, clerk)
    assert redirect_query(await connect(client, clerk, clerk_id, ws["id"]))["error"] == (
        "ig_not_professional"
    )
    assert await rows(engine) == []


async def test_an_account_live_in_another_workspace_is_refused(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    a, ws_a = await owner(client, clerk, "a@example.com")
    b, ws_b = await owner(client, clerk, "b@example.com")
    assert redirect_query(await connect(client, clerk, a, ws_a["id"]))["connected"] == "instagram"
    assert redirect_query(await connect(client, clerk, b, ws_b["id"]))["error"] == (
        "account_in_use"
    )
    assert [str(r["workspace_id"]) for r in await rows(engine)] == [ws_a["id"]]


async def test_after_a_disconnect_another_workspace_may_connect_it(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    a, ws_a = await owner(client, clerk, "a@example.com")
    b, ws_b = await owner(client, clerk, "b@example.com")
    await connect(client, clerk, a, ws_a["id"])
    [first] = await rows(engine)
    await client.delete(
        f"/v1/w/{ws_a['id']}/social-accounts/{first['id']}", headers=clerk.headers(a)
    )
    assert redirect_query(await connect(client, clerk, b, ws_b["id"]))["connected"] == "instagram"


async def test_reconnecting_updates_the_same_row(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    await connect(client, clerk, clerk_id, ws["id"])
    [before] = await rows(engine)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET status = 'needs_reconnect', last_error = 'x'")
        )
    assert redirect_query(await connect(client, clerk, clerk_id, ws["id"]))["connected"] == (
        "instagram"
    )
    [after] = await rows(engine)
    assert after["id"] == before["id"]
    assert (after["status"], after["last_error"]) == ("active", None)


async def test_the_free_plan_allows_one_instagram_account(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram
) -> None:
    clerk_id, ws = await owner(client, clerk)
    await connect(client, clerk, clerk_id, ws["id"])
    response = await client.post(
        f"/v1/w/{ws['id']}/social-accounts/instagram/connect", headers=clerk.headers(clerk_id)
    )
    assert response.status_code == 402
    assert response.json()["code"] == "quota_exceeded"
    assert response.json()["detail"] == "Your plan includes 1 Instagram account."


async def test_a_reconnect_slot_cannot_be_used_for_a_different_account(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    await connect(client, clerk, clerk_id, ws["id"])
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE social_accounts SET status = 'needs_reconnect'"))

    instagram.use_account("17841400000000009", "other.shop")
    query = redirect_query(await connect(client, clerk, clerk_id, ws["id"]))
    assert (query["error"], query["limit"]) == ("quota_exceeded", "1")
    assert [r["username"] for r in await rows(engine)] == ["maple.bakery"]


async def test_a_failed_subscription_shows_an_error_and_can_be_retried(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram
) -> None:
    instagram.subscribe = (
        500,
        {"error": {"code": 2, "message": "Service temporarily unavailable"}},
    )
    clerk_id, ws = await owner(client, clerk)
    assert redirect_query(await connect(client, clerk, clerk_id, ws["id"]))["connected"] == (
        "instagram"
    )
    url = f"/v1/w/{ws['id']}/social-accounts"
    [acct] = (await client.get(url, headers=clerk.headers(clerk_id))).json()["items"]
    assert (acct["status"], acct["last_error"]) == ("error", SUBSCRIBE_FAILED)

    instagram.subscribe = (200, {"success": True})
    retried = await client.post(f"{url}/{acct['id']}/resubscribe", headers=clerk.headers(clerk_id))
    assert retried.status_code == 200
    assert (retried.json()["status"], retried.json()["last_error"]) == ("active", None)


async def test_account_settings(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram
) -> None:
    clerk_id, ws = await owner(client, clerk)
    await connect(client, clerk, clerk_id, ws["id"])
    url = f"/v1/w/{ws['id']}/social-accounts"
    [acct] = (await client.get(url, headers=clerk.headers(clerk_id))).json()["items"]
    assert acct["ai_mode"] == "suggest"

    changed = await client.patch(
        f"{url}/{acct['id']}",
        json={"ai_analysis_enabled": False, "auto_hide_spam": True},
        headers=clerk.headers(clerk_id),
    )
    assert changed.status_code == 200
    assert (changed.json()["ai_analysis_enabled"], changed.json()["auto_hide_spam"]) == (
        False,
        True,
    )

    auto = await client.patch(
        f"{url}/{acct['id']}", json={"ai_mode": "auto"}, headers=clerk.headers(clerk_id)
    )
    assert auto.status_code == 402
    assert auto.json()["code"] == "entitlement_required"


async def test_disconnect_deletes_the_token_and_clears_caches(
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
    redis: Redis,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    await connect(client, clerk, clerk_id, ws["id"])
    [row] = await rows(engine)
    await redis.set(f"profile:{row['id']}:990000000000001", "{}")

    url = f"/v1/w/{ws['id']}/social-accounts/{row['id']}"
    response = await client.delete(
        url, params={"delete_data": "true"}, headers=clerk.headers(clerk_id)
    )
    assert response.status_code == 204

    [row] = await rows(engine)
    assert row["access_token_enc"] is None
    assert row["status"] == "disconnected"
    assert row["disconnected_at"] is not None
    assert await redis.keys("profile:*") == []
    [listed] = (
        await client.get(f"/v1/w/{ws['id']}/social-accounts", headers=clerk.headers(clerk_id))
    ).json()["items"]
    assert (listed["status"], listed["capabilities"]) == ("disconnected", [])
    blocked = await client.patch(
        url, json={"auto_hide_spam": True}, headers=clerk.headers(clerk_id)
    )
    assert blocked.status_code == 409


async def test_connect_needs_instagram_configured(
    app: Any, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"ig_app_id": None})
    clerk_id, ws = await owner(client, clerk)
    response = await client.post(
        f"/v1/w/{ws['id']}/social-accounts/instagram/connect", headers=clerk.headers(clerk_id)
    )
    assert response.status_code == 503
