"""T2.2-T2.4: connecting Instagram (F-03), account settings and disconnect (FR-CON-01...06)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.security.crypto import TokenCipher
from socialhood.services.connections import CONNECT_EXPIRED, CONNECT_NOT_YOURS, SUBSCRIBE_FAILED
from tests.support.api import TOKEN_KEY, WEB, Clerk, sign_in
from tests.support.automations import make_automation
from tests.support.instagram import (
    FakeInstagram,
    callback,
    complete,
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
    state = await start_connect(client, clerk, clerk_id, ws["id"])
    response = await client.get(
        "/v1/oauth/instagram/callback", params={"code": "code-1", "state": state}
    )
    query = redirect_query(response)
    assert query["_path"] == f"/w/{ws['slug']}/settings/connections"
    assert set(query) == {"instagram", "_path"}
    assert response.headers["location"].startswith(WEB)
    assert instagram.calls == []  # X-1: the callback connects nothing
    assert await rows(engine) == []

    done = await complete(client, clerk, clerk_id, ws["id"], query["instagram"])
    assert done.status_code == 200, done.text
    assert done.json()["username"] == "maple.bakery"

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
    assert "instagram" in redirect_query(first)
    assert redirect_query(again) == {"error": "state_invalid", "_path": "/app"}
    assert again.headers["location"].startswith(WEB)


# ---------------------------------------------------------------- X-1: login CSRF


async def test_a_victim_cannot_finish_an_attackers_connect(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    """The attacker starts a connect and sends the authorize link to a victim, who approves it.
    The victim's browser lands on the attacker's workspace page with the nonce; neither the
    victim's workspace nor the attacker's gets the victim's Instagram account."""
    attacker, ws_attacker = await owner(client, clerk, "attacker@example.com")
    victim, ws_victim = await owner(client, clerk, "victim@example.com")
    state = await start_connect(client, clerk, attacker, ws_attacker["id"])
    nonce = await callback(client, state)  # in the victim's browser

    # The page the victim lands on is the attacker's workspace: not theirs.
    outsider = await complete(client, clerk, victim, ws_attacker["id"], nonce)
    assert outsider.status_code == 404
    # Posted to the victim's own workspace, it is refused and used up.
    refused = await complete(client, clerk, victim, ws_victim["id"], nonce)
    assert (refused.status_code, refused.json()["code"]) == (403, "forbidden")
    assert refused.json()["detail"] == CONNECT_NOT_YOURS
    assert (await complete(client, clerk, attacker, ws_attacker["id"], nonce)).status_code == 404

    assert instagram.calls == []  # the code was never exchanged
    assert await rows(engine) == []


async def test_a_nonce_for_another_workspace_of_the_same_member_is_refused(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk, "a@example.com")
    _, other = await owner(client, clerk, "b@example.com")
    async with engine.begin() as conn:  # a is also an admin of b's workspace
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " SELECT :other, owner_user_id, 'admin' FROM workspaces WHERE id = :mine"
            ),
            {"other": other["id"], "mine": ws["id"]},
        )
    nonce = await callback(client, await start_connect(client, clerk, clerk_id, ws["id"]))
    refused = await complete(client, clerk, clerk_id, other["id"], nonce)
    assert (refused.status_code, refused.json()["code"]) == (403, "forbidden")
    assert await rows(engine) == []


async def test_a_nonce_works_once(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    nonce = await callback(client, await start_connect(client, clerk, clerk_id, ws["id"]))
    assert (await complete(client, clerk, clerk_id, ws["id"], nonce)).status_code == 200
    replayed = await complete(client, clerk, clerk_id, ws["id"], nonce)
    assert (replayed.status_code, replayed.json()["detail"]) == (404, CONNECT_EXPIRED)
    assert instagram.calls.count("exchange") == 1
    assert len(await rows(engine)) == 1


async def test_an_expired_nonce_fails(
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
    redis: Redis,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    nonce = await callback(client, await start_connect(client, clerk, clerk_id, ws["id"]), "c-9")
    key = f"oauth:held:{nonce}"
    assert 0 < await redis.ttl(key) <= 600
    held = await redis.get(key)
    assert held is not None
    assert "c-9" not in held  # the code is kept encrypted
    await redis.pexpire(key, 1)
    await asyncio.sleep(0.05)

    expired = await complete(client, clerk, clerk_id, ws["id"], nonce)
    assert (expired.status_code, expired.json()["detail"]) == (404, CONNECT_EXPIRED)
    assert instagram.calls == []
    assert await rows(engine) == []


async def test_no_connect_for_a_workspace_being_deleted(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    """T9.6 follow-up: a deletion that starts mid-connect stops both the callback and complete."""
    clerk_id, ws = await owner(client, clerk)
    state = await start_connect(client, clerk, clerk_id, ws["id"])
    nonce = await callback(client, await start_connect(client, clerk, clerk_id, ws["id"]))
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET status = 'deleting' WHERE id = :w"), {"w": ws["id"]}
        )

    landed = await client.get("/v1/oauth/instagram/callback", params={"code": "c", "state": state})
    assert redirect_query(landed) == {"error": "state_invalid", "_path": "/app"}
    assert (await complete(client, clerk, clerk_id, ws["id"], nonce)).status_code == 404
    assert (
        await client.post(
            f"/v1/w/{ws['id']}/social-accounts/instagram/connect", headers=clerk.headers(clerk_id)
        )
    ).status_code == 404
    assert instagram.calls == []
    assert await rows(engine) == []


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
    response = await connect(client, clerk, clerk_id, ws["id"])
    assert (response.status_code, response.json()["code"]) == (502, "platform_error")
    assert response.json()["detail"] == "Instagram didn't respond. Try again."
    assert await rows(engine) == []


async def test_a_personal_account_cannot_connect(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    instagram.profile = fixture("me_personal.json")
    clerk_id, ws = await owner(client, clerk)
    response = await connect(client, clerk, clerk_id, ws["id"])
    assert (response.status_code, response.json()["code"]) == (422, "ig_not_professional")
    assert await rows(engine) == []


async def test_an_account_live_in_another_workspace_is_refused(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    a, ws_a = await owner(client, clerk, "a@example.com")
    b, ws_b = await owner(client, clerk, "b@example.com")
    assert (await connect(client, clerk, a, ws_a["id"])).status_code == 200
    refused = await connect(client, clerk, b, ws_b["id"])
    assert (refused.status_code, refused.json()["code"]) == (409, "account_in_use")
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
    assert (await connect(client, clerk, b, ws_b["id"])).status_code == 200


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
    assert (await connect(client, clerk, clerk_id, ws["id"])).status_code == 200
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
    response = await connect(client, clerk, clerk_id, ws["id"])
    assert response.status_code == 402
    problem = response.json()
    assert (problem["code"], problem["entitlement"], problem["limit"]) == (
        "quota_exceeded",
        "accounts_per_platform",
        1,
    )
    assert problem["detail"] == "Your plan includes 1 Instagram account."
    assert [r["username"] for r in await rows(engine)] == ["maple.bakery"]


async def test_a_failed_subscription_shows_an_error_and_can_be_retried(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram
) -> None:
    instagram.subscribe = (
        500,
        {"error": {"code": 2, "message": "Service temporarily unavailable"}},
    )
    clerk_id, ws = await owner(client, clerk)
    done = await connect(client, clerk, clerk_id, ws["id"])
    assert (done.status_code, done.json()["status"]) == (200, "error")
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


async def test_last_synced_is_the_later_of_the_media_sync_and_the_backfill(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    """Settings → Connections' "Last synced" (C-066): when posts or history were last pulled."""
    clerk_id, ws = await owner(client, clerk)
    await connect(client, clerk, clerk_id, ws["id"])
    url = f"/v1/w/{ws['id']}/social-accounts"

    async def synced(media: datetime | None, backfill: datetime | None) -> str | None:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE social_accounts SET media_synced_at = :m, backfilled_at = :b"),
                {"m": media, "b": backfill},
            )
        [acct] = (await client.get(url, headers=clerk.headers(clerk_id))).json()["items"]
        value: str | None = acct["last_synced_at"]
        return value

    earlier = datetime(2026, 9, 29, 6, 0, tzinfo=UTC)
    later = datetime(2026, 9, 30, 6, 0, tzinfo=UTC)
    assert await synced(None, None) is None
    assert await synced(later, earlier) == "2026-09-30T06:00:00Z"
    assert await synced(earlier, later) == "2026-09-30T06:00:00Z"
    assert await synced(None, earlier) == "2026-09-29T06:00:00Z"


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
    await make_automation(engine, workspace_id=ws["id"], account_id=row["id"])
    await make_automation(engine, workspace_id=ws["id"], account_id=row["id"], status="draft")

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
    async with engine.connect() as conn:  # F-15: its automations stop; drafts stay drafts
        statuses = (await conn.execute(text("SELECT status FROM automations"))).scalars().all()
    assert sorted(statuses) == ["draft", "paused"]
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
