"""GR-29: connecting Facebook Pages through Facebook Login - the single-use state, the Page picker,
encrypted Page tokens, the webhook subscription, the plan's limit, who may finish a connect (X-1)
and Meta's deauthorize callback for a Page."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.app import app as jobs_app
from socialhood.security.crypto import TokenCipher
from socialhood.security.signatures import sign_request
from socialhood.services.facebook_connect import (
    CONNECT_EXPIRED,
    CONNECT_NOT_YOURS,
    NO_MESSAGING,
)
from socialhood.settings import Settings
from tests.support.api import META_APP_SECRET, TOKEN_KEY, WEB, Clerk, sign_in
from tests.support.facebook import (
    LONG_TOKEN,
    OTHER_PAGE_ID,
    OTHER_PAGE_TOKEN,
    PAGE_ID,
    PAGE_TOKEN,
    USER_ID,
    FakeFacebook,
    callback,
    connect,
    connect_pages,
    list_pages,
    start_connect,
    with_facebook,
)
from tests.support.instagram import FakeInstagram, redirect_query, state_from

MODS_PAGE_ID = "109876543210003"


@pytest.fixture
def api_settings(api_settings: Settings) -> Settings:
    return with_facebook(api_settings)


async def owner(
    client: httpx.AsyncClient, clerk: Clerk, email: str = "o@example.com"
) -> tuple[str, dict[str, Any]]:
    clerk_id, me = await sign_in(client, clerk, email=email)
    return clerk_id, me["workspaces"][0]


async def accounts(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT * FROM social_accounts ORDER BY created_at"))
        return [dict(r._mapping) for r in result]


async def nonce_for(
    client: httpx.AsyncClient, clerk: Clerk, clerk_id: str, wid: str, code: str = "code-1"
) -> str:
    started = await start_connect(client, clerk, clerk_id, wid)
    assert started.status_code == 200, started.text
    return await callback(client, state_from(started.json()["authorize_url"]), code)


async def test_connect_is_off_until_facebook_is_configured(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, ws = await owner(client, clerk)
    app.state.settings = app.state.settings.model_copy(update={"fb_redirect_uri": None})
    response = await start_connect(client, clerk, clerk_id, ws["id"])
    assert (response.status_code, response.json()["code"]) == (503, "service_unavailable")


async def test_start_stores_a_single_use_state_and_asks_for_the_page_permissions(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook, redis: Redis
) -> None:
    clerk_id, ws = await owner(client, clerk)
    started = await start_connect(client, clerk, clerk_id, ws["id"])
    url = started.json()["authorize_url"]
    assert url.startswith("https://www.facebook.com/")
    assert "pages_messaging" in url
    assert "pages_manage_engagement" in url
    assert 0 < await redis.ttl(f"oauth:{state_from(url)}") <= 600


async def test_the_callback_connects_nothing_and_a_state_works_once(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    started = await start_connect(client, clerk, clerk_id, ws["id"])
    state = state_from(started.json()["authorize_url"])
    first = await client.get("/v1/oauth/facebook/callback", params={"code": "c", "state": state})
    query = redirect_query(first)
    assert query["_path"] == f"/w/{ws['slug']}/settings/connections"
    assert set(query) == {"facebook", "_path"}
    assert first.headers["location"].startswith(WEB)
    assert facebook.calls == []  # X-1: the callback exchanges nothing
    assert await accounts(engine) == []
    again = await client.get("/v1/oauth/facebook/callback", params={"code": "c", "state": state})
    assert redirect_query(again) == {"error": "state_invalid", "_path": "/app"}


async def test_a_declined_login_goes_back_with_the_reason(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook
) -> None:
    clerk_id, ws = await owner(client, clerk)
    state = state_from(
        (await start_connect(client, clerk, clerk_id, ws["id"])).json()["authorize_url"]
    )
    response = await client.get(
        "/v1/oauth/facebook/callback", params={"error": "access_denied", "state": state}
    )
    assert redirect_query(response)["error"] == "access_denied"


async def test_the_page_list_shows_which_pages_the_person_can_connect(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    listed = await list_pages(client, clerk, clerk_id, ws["id"], nonce)
    assert listed.status_code == 200, listed.text
    items = {p["id"]: p for p in listed.json()["items"]}
    assert set(items) == {PAGE_ID, OTHER_PAGE_ID, MODS_PAGE_ID}
    assert (items[PAGE_ID]["name"], items[PAGE_ID]["username"]) == ("Maple Bakery", "maplebakery")
    assert items[PAGE_ID]["can_connect"] is True
    assert (items[MODS_PAGE_ID]["can_connect"], items[MODS_PAGE_ID]["problem"]) == (
        False,
        NO_MESSAGING,
    )
    assert "token" not in str(listed.json()).lower()
    assert facebook.calls == ["exchange", "long_lived", "me", "accounts"]
    # Asking again returns the same list without spending the code again.
    again = await list_pages(client, clerk, clerk_id, ws["id"], nonce)
    assert again.json() == listed.json()
    assert facebook.calls.count("exchange") == 1
    assert await accounts(engine) == []


async def test_a_connected_page_has_an_encrypted_token_and_a_subscription(
    client: httpx.AsyncClient,
    clerk: Clerk,
    facebook: FakeFacebook,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    done = await connect(client, clerk, clerk_id, ws["id"])
    assert done.status_code == 201, done.text
    [account] = done.json()["items"]
    assert (account["platform"], account["username"]) == ("facebook", "maplebakery")
    assert account["display_name"] == "Maple Bakery"
    assert account["token_expires_at"] is None
    assert {"dm_send", "comments", "private_reply", "read_receipts"} <= set(account["capabilities"])
    assert "publish" in account["capabilities"]  # GR-30: pages_manage_posts is requested
    assert not {"post_insights", "templates"} & set(account["capabilities"])

    [row] = await accounts(engine)
    assert (row["platform"], row["platform_account_id"]) == ("facebook", PAGE_ID)
    assert row["app_scoped_id"] == USER_ID
    assert (row["status"], row["token_expires_at"]) == ("active", None)
    assert row["webhooks_subscribed_at"] is not None
    assert PAGE_TOKEN.encode() not in bytes(row["access_token_enc"])
    assert TokenCipher([TOKEN_KEY]).decrypt(row["access_token_enc"]) == PAGE_TOKEN
    assert LONG_TOKEN not in str(row)  # the person's own token is never stored
    assert facebook.tokens_seen[-1] == PAGE_TOKEN  # the Page subscribes with its own token
    assert "messages" in facebook.subscribed_fields[0].split(",")
    assert "feed" in facebook.subscribed_fields[0].split(",")

    listed = (
        await client.get(f"/v1/w/{ws['id']}/social-accounts", headers=clerk.headers(clerk_id))
    ).json()["items"]
    assert [a["platform"] for a in listed] == ["facebook"]
    jobs = await jobs_app.connector.execute_query_all_async(
        "SELECT task_name FROM procrastinate_jobs ORDER BY task_name"
    )
    assert [j["task_name"] for j in jobs] == ["backfill_account", "sync_media"]


async def test_the_nonce_is_spent_when_the_pages_are_connected(
    client: httpx.AsyncClient,
    clerk: Clerk,
    facebook: FakeFacebook,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    await list_pages(client, clerk, clerk_id, ws["id"], nonce)
    assert (
        await connect_pages(client, clerk, clerk_id, ws["id"], nonce, [PAGE_ID])
    ).status_code == 201
    replayed = await connect_pages(client, clerk, clerk_id, ws["id"], nonce, [PAGE_ID])
    assert (replayed.status_code, replayed.json()["detail"]) == (404, CONNECT_EXPIRED)
    assert len(await accounts(engine)) == 1


async def test_connecting_before_listing_asks_to_list_first(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    response = await connect_pages(client, clerk, clerk_id, ws["id"], nonce, [PAGE_ID])
    assert (response.status_code, response.json()["code"]) == (409, "conflict")
    assert await accounts(engine) == []


async def test_a_page_the_person_cannot_message_for_is_refused(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    response = await connect(client, clerk, clerk_id, ws["id"], [MODS_PAGE_ID])
    assert response.status_code == 422
    [error] = response.json()["errors"]
    assert error["field"] == "page_ids"
    assert NO_MESSAGING in error["message"]
    assert await accounts(engine) == []


async def test_a_page_that_was_not_listed_is_refused(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook, engine: AsyncEngine
) -> None:
    clerk_id, ws = await owner(client, clerk)
    response = await connect(client, clerk, clerk_id, ws["id"], ["999"])
    assert (response.status_code, response.json()["errors"][0]["field"]) == (422, "page_ids")
    assert await accounts(engine) == []


async def test_a_login_that_lists_no_pages_says_so(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook
) -> None:
    clerk_id, ws = await owner(client, clerk)
    facebook.pages = []
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    response = await list_pages(client, clerk, clerk_id, ws["id"], nonce)
    assert response.status_code == 422


async def test_an_expired_code_is_a_platform_error(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook
) -> None:
    clerk_id, ws = await owner(client, clerk)
    facebook.exchange_status = 400
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    response = await list_pages(client, clerk, clerk_id, ws["id"], nonce)
    assert (response.status_code, response.json()["code"]) == (502, "platform_error")


async def test_the_free_plan_allows_one_page_and_a_refusal_keeps_the_nonce(
    client: httpx.AsyncClient,
    clerk: Clerk,
    facebook: FakeFacebook,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    await list_pages(client, clerk, clerk_id, ws["id"], nonce)
    over = await connect_pages(client, clerk, clerk_id, ws["id"], nonce, [PAGE_ID, OTHER_PAGE_ID])
    assert over.status_code == 402, over.text
    body = over.json()
    assert (body["code"], body["entitlement"], body["limit"]) == (
        "quota_exceeded",
        "accounts_per_platform",
        1,
    )
    assert body["detail"] == "Your plan includes 1 Facebook account."
    assert await accounts(engine) == []
    # Nothing was added and the nonce still works for one Page.
    one = await connect_pages(client, clerk, clerk_id, ws["id"], nonce, [PAGE_ID])
    assert one.status_code == 201, one.text


async def test_a_second_connect_is_refused_when_the_plan_is_full(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook, queue: None
) -> None:
    clerk_id, ws = await owner(client, clerk)
    assert (await connect(client, clerk, clerk_id, ws["id"])).status_code == 201
    second = await start_connect(client, clerk, clerk_id, ws["id"])
    assert (second.status_code, second.json()["entitlement"]) == (402, "accounts_per_platform")


async def test_reconnecting_a_page_updates_it_in_place(
    client: httpx.AsyncClient,
    clerk: Clerk,
    facebook: FakeFacebook,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    assert (await connect(client, clerk, clerk_id, ws["id"])).status_code == 201
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET status = 'needs_reconnect', access_token_enc = NULL")
        )
    facebook.pages[0]["access_token"] = "EAAGpage-token-renewed"
    assert (await connect(client, clerk, clerk_id, ws["id"])).status_code == 201
    [row] = await accounts(engine)
    assert row["status"] == "active"
    assert TokenCipher([TOKEN_KEY]).decrypt(row["access_token_enc"]) == "EAAGpage-token-renewed"


async def test_a_page_connected_in_another_workspace_is_in_use(
    client: httpx.AsyncClient,
    clerk: Clerk,
    facebook: FakeFacebook,
    engine: AsyncEngine,
    queue: None,
) -> None:
    first, ws_first = await owner(client, clerk, "first@example.com")
    second, ws_second = await owner(client, clerk, "second@example.com")
    assert (await connect(client, clerk, first, ws_first["id"])).status_code == 201
    response = await connect(client, clerk, second, ws_second["id"])
    assert (response.status_code, response.json()["code"]) == (409, "account_in_use")
    assert len(await accounts(engine)) == 1


async def test_a_failed_subscription_leaves_the_page_with_a_retry(
    client: httpx.AsyncClient,
    clerk: Clerk,
    facebook: FakeFacebook,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    facebook.subscribe = (400, {"error": {"code": 100, "message": "No permission"}})
    done = await connect(client, clerk, clerk_id, ws["id"])
    assert done.status_code == 201, done.text
    [account] = done.json()["items"]
    assert (account["status"], account["last_error"]) == (
        "error",
        "Couldn't subscribe to messages. Try again.",
    )
    facebook.subscribe = (200, {"success": True})
    again = await client.post(
        f"/v1/w/{ws['id']}/social-accounts/{account['id']}/resubscribe",
        headers=clerk.headers(clerk_id),
    )
    assert (again.status_code, again.json()["status"]) == (200, "active")


# ---------------------------------------------------------------- X-1: login CSRF


async def test_a_victim_cannot_finish_an_attackers_connect(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook, engine: AsyncEngine
) -> None:
    attacker, ws_attacker = await owner(client, clerk, "attacker@example.com")
    victim, ws_victim = await owner(client, clerk, "victim@example.com")
    nonce = await nonce_for(client, clerk, attacker, ws_attacker["id"])  # in the victim's browser
    outsider = await list_pages(client, clerk, victim, ws_attacker["id"], nonce)
    assert outsider.status_code == 404  # the victim is not a member of that workspace
    refused = await list_pages(client, clerk, victim, ws_victim["id"], nonce)
    assert (refused.status_code, refused.json()["detail"]) == (403, CONNECT_NOT_YOURS)
    pick = await connect_pages(client, clerk, victim, ws_victim["id"], nonce, [PAGE_ID])
    assert pick.status_code == 403
    assert facebook.calls == []  # the code was never exchanged
    assert await accounts(engine) == []


async def test_an_expired_nonce_fails(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook, redis: Redis
) -> None:
    clerk_id, ws = await owner(client, clerk)
    code = "plaintext-oauth-code"
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"], code)
    key = f"oauth:held:{nonce}"
    held = await redis.get(key)
    assert held is not None
    assert code not in held  # the code is kept encrypted
    await redis.pexpire(key, 1)
    await asyncio.sleep(0.05)
    expired = await list_pages(client, clerk, clerk_id, ws["id"], nonce)
    assert (expired.status_code, expired.json()["detail"]) == (404, CONNECT_EXPIRED)


async def test_page_tokens_are_kept_encrypted_while_the_person_picks(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook, redis: Redis
) -> None:
    clerk_id, ws = await owner(client, clerk)
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    await list_pages(client, clerk, clerk_id, ws["id"], nonce)
    held = await redis.get(f"oauth:held:{nonce}")
    assert held is not None
    assert PAGE_TOKEN not in held
    assert OTHER_PAGE_TOKEN not in held
    assert 0 < await redis.ttl(f"oauth:held:{nonce}") <= 600


async def test_the_two_platforms_do_not_share_connect_state(
    client: httpx.AsyncClient, clerk: Clerk, facebook: FakeFacebook, instagram: FakeInstagram
) -> None:
    clerk_id, ws = await owner(client, clerk)
    nonce = await nonce_for(client, clerk, clerk_id, ws["id"])
    wrong = await client.post(
        f"/v1/w/{ws['id']}/social-accounts/instagram/complete",
        json={"nonce": nonce},
        headers=clerk.headers(clerk_id),
    )
    assert wrong.status_code == 404
    assert instagram.calls == []
    # A Facebook state sent to Instagram's callback is a forged one.
    state = state_from(
        (await start_connect(client, clerk, clerk_id, ws["id"])).json()["authorize_url"]
    )
    ig = await client.get("/v1/oauth/instagram/callback", params={"code": "c", "state": state})
    assert redirect_query(ig) == {"error": "state_invalid", "_path": "/app"}


# ---------------------------------------------------------------- Meta's privacy callbacks


async def test_deauthorize_disconnects_every_page_the_person_connected(
    client: httpx.AsyncClient,
    clerk: Clerk,
    facebook: FakeFacebook,
    engine: AsyncEngine,
    queue: None,
) -> None:
    clerk_id, ws = await owner(client, clerk)
    assert (await connect(client, clerk, clerk_id, ws["id"])).status_code == 201
    payload = {"algorithm": "HMAC-SHA256", "user_id": USER_ID, "issued_at": 1790000000}
    response = await client.post(
        "/webhooks/meta/deauthorize",
        data={"signed_request": sign_request(payload, META_APP_SECRET)},
    )
    assert response.status_code == 200
    [row] = await accounts(engine)
    assert (row["status"], row["access_token_enc"]) == ("disconnected", None)
    [note] = (
        await client.get(f"/v1/w/{ws['id']}/notifications", headers=clerk.headers(clerk_id))
    ).json()["items"]
    assert note["type"] == "account_disconnected"
    assert "Facebook" in note["body"]
