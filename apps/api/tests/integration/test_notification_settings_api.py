"""Notification settings through the API (T8.6, T8.7; FR-NOT-03, FR-NOT-04, F-19, C-049): the
member's preferences, push subscriptions per user, and the digest's one-click unsubscribe."""

from __future__ import annotations

import base64
import os
import uuid
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.models.identity import DEFAULT_NOTIFICATION_PREFS
from socialhood.notify.unsubscribe import make_token
from socialhood.security.crypto import new_key
from tests.support.api import TOKEN_KEY, Clerk, sign_in
from tests.support.notify import AUTH, P256DH, push_endpoint

# A browser that subscribed again gets a new auth secret (base64url, as PushManager gives it).
NEW_AUTH = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()

QUIET = {
    "email_digest": False,
    "push": {"needs_you": True, "new_lead": False, "window_closing": True, "account": False},
}


async def _rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


def subscription(endpoint: str | None = None, **values: Any) -> dict[str, Any]:
    return {
        "endpoint": endpoint or push_endpoint(),
        "keys": {"p256dh": P256DH, "auth": AUTH},
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0) Mobile/15E148",
        **values,
    }


# ---------------------------------------------------------------- preferences


async def test_preferences_start_on_and_are_replaced_whole(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid, headers = me["workspaces"][0]["id"], clerk.headers(clerk_id)
    url = f"/v1/w/{wid}/notification-preferences"

    first = await client.get(url, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json() == DEFAULT_NOTIFICATION_PREFS

    saved = await client.put(url, headers=headers, json=QUIET)
    assert saved.status_code == 200, saved.text
    assert saved.json() == QUIET
    assert (await client.get(url, headers=headers)).json() == QUIET
    [row] = await _rows(
        engine,
        "SELECT notification_prefs FROM workspace_members WHERE user_id = :u",
        u=me["id"],
    )
    assert row["notification_prefs"] == QUIET


async def test_a_partial_or_unknown_body_is_refused(
    client: httpx.AsyncClient, clerk: Clerk
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    url = f"/v1/w/{me['workspaces'][0]['id']}/notification-preferences"
    for body in (
        {"email_digest": False},
        {**QUIET, "push": {"needs_you": True}},
        {**QUIET, "sms": True},
    ):
        response = await client.put(url, headers=clerk.headers(clerk_id), json=body)
        assert response.status_code == 422, body


async def test_stored_preferences_missing_a_switch_read_as_on(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE workspace_members SET notification_prefs ="
                ' \'{"push": {"needs_you": false}}\'::jsonb WHERE user_id = :u'
            ),
            {"u": me["id"]},
        )
    url = f"/v1/w/{me['workspaces'][0]['id']}/notification-preferences"
    body = (await client.get(url, headers=clerk.headers(clerk_id))).json()
    assert body == {
        "email_digest": True,
        "push": {"needs_you": False, "new_lead": True, "window_closing": True, "account": True},
    }


# ---------------------------------------------------------------- push subscriptions


async def test_a_browser_is_registered_and_removed(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    headers = clerk.headers(clerk_id)
    body = subscription()

    created = await client.post("/v1/me/push-subscriptions", headers=headers, json=body)
    assert created.status_code == 201, created.text
    device = created.json()
    assert set(device) == {"id", "user_agent", "created_at", "last_used_at"}
    assert device["user_agent"] == body["user_agent"]
    [row] = await _rows(engine, "SELECT * FROM push_subscriptions WHERE id = :d", d=device["id"])
    assert (str(row["user_id"]), row["endpoint"], row["p256dh"], row["auth"]) == (
        me["id"],
        body["endpoint"],
        P256DH,
        AUTH,
    )

    removed = await client.delete(
        "/v1/me/push-subscriptions", headers=headers, params={"endpoint": body["endpoint"]}
    )
    assert removed.status_code == 204
    assert await _rows(engine, "SELECT id FROM push_subscriptions") == []
    again = await client.delete(
        "/v1/me/push-subscriptions", headers=headers, params={"endpoint": body["endpoint"]}
    )
    assert again.status_code == 204


async def test_registering_again_refreshes_the_browser_and_moves_it_to_the_caller(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    first_id, first = await sign_in(client, clerk, email="first@example.com")
    second_id, second = await sign_in(client, clerk, email="second@example.com")
    body = subscription()
    created = await client.post(
        "/v1/me/push-subscriptions", headers=clerk.headers(first_id), json=body
    )
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE push_subscriptions SET failure_count = 5, disabled_at = now() WHERE id = :d"
            ),
            {"d": created.json()["id"]},
        )

    moved = await client.post(
        "/v1/me/push-subscriptions",
        headers=clerk.headers(second_id),
        json={**body, "keys": {"p256dh": P256DH, "auth": NEW_AUTH}},
    )

    assert moved.status_code == 201, moved.text
    assert moved.json()["id"] == created.json()["id"]
    [row] = await _rows(engine, "SELECT * FROM push_subscriptions")
    assert str(row["user_id"]) == second["id"] != first["id"]
    assert (row["auth"], row["failure_count"], row["disabled_at"]) == (
        NEW_AUTH,
        0,
        None,
    )


async def test_only_browser_push_services_are_accepted(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, _ = await sign_in(client, clerk)
    for endpoint in (
        "https://169.254.169.254/latest/meta-data/iam",
        "https://hooks.attacker.example/collect",
        "http://fcm.googleapis.com/fcm/send/abc",
    ):
        response = await client.post(
            "/v1/me/push-subscriptions",
            headers=clerk.headers(clerk_id),
            json=subscription(endpoint),
        )
        assert response.status_code == 422, endpoint
        assert {error["field"] for error in response.json()["errors"]} == {"endpoint"}
    assert await _rows(engine, "SELECT id FROM push_subscriptions") == []


async def test_a_user_keeps_their_ten_most_recent_browsers(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, _ = await sign_in(client, clerk)
    endpoints = [push_endpoint() for _ in range(11)]
    for endpoint in endpoints:
        response = await client.post(
            "/v1/me/push-subscriptions",
            headers=clerk.headers(clerk_id),
            json=subscription(endpoint),
        )
        assert response.status_code == 201

    kept = {
        row["endpoint"] for row in await _rows(engine, "SELECT endpoint FROM push_subscriptions")
    }
    assert kept == set(endpoints[1:])


# ---------------------------------------------------------------- digest unsubscribe


async def test_one_click_turns_the_digest_off_and_nothing_else(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    await client.put(
        f"/v1/w/{wid}/notification-preferences",
        headers=clerk.headers(clerk_id),
        json={**QUIET, "email_digest": True},
    )
    token = make_token(uuid.UUID(wid), uuid.UUID(me["id"]), [TOKEN_KEY])

    # A mail client's RFC 8058 one-click POST: no sign-in, a form body that is ignored.
    response = await client.post(
        "/v1/digest/unsubscribe",
        params={"token": token},
        content="List-Unsubscribe=One-Click",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"workspace_name": me["workspaces"][0]["name"], "email_digest": False}
    prefs = (
        await client.get(f"/v1/w/{wid}/notification-preferences", headers=clerk.headers(clerk_id))
    ).json()
    assert prefs == QUIET  # the push switches are as they were
    again = await client.post("/v1/digest/unsubscribe", params={"token": token})
    assert again.status_code == 200


async def test_an_unsubscribe_link_that_isnt_ours_is_404(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    _, me = await sign_in(client, clerk)
    wid, user = uuid.UUID(me["workspaces"][0]["id"]), uuid.UUID(me["id"])
    other_key = new_key()  # a valid key, but not one the API holds
    for token in (
        "not-a-token",
        make_token(wid, user, [other_key]),
        make_token(wid, uuid.uuid4(), [TOKEN_KEY]),
    ):
        response = await client.post("/v1/digest/unsubscribe", params={"token": token})
        assert response.status_code == 404, token
        assert response.json()["code"] == "not_found"
    assert (await client.get("/v1/digest/unsubscribe", params={"token": "x"})).status_code == 405
    [row] = await _rows(
        engine, "SELECT notification_prefs FROM workspace_members WHERE user_id = :u", u=user
    )
    assert row["notification_prefs"]["email_digest"] is True
