"""TR-API-07 rate limits (T9.2): the sliding window, and each limit class through the API.

Windows are filled directly in Valkey (every request at "now"), so a test needs one request to
reach the limit instead of hundreds.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from redis.asyncio import Redis

from socialhood.api.ratelimit import LIMIT_DEPENDENCIES
from socialhood.auth.deps import current_user
from socialhood.security.ratelimit import LIMITS, Limit, hit, window_key
from tests.support.api import Clerk, sign_in

CLIENT_IP = "127.0.0.1"  # httpx's ASGITransport


async def fill(redis: Redis, name: str, subject: str) -> None:
    """Put a full window of requests, all made now, in front of ``subject``."""
    limit = LIMITS[name]
    now_ms = int(time.time() * 1000)
    await redis.zadd(
        window_key(limit, subject), {f"fill-{i}": now_ms for i in range(limit.max_requests)}
    )
    await redis.expire(window_key(limit, subject), limit.window_s)


def assert_limited(response: httpx.Response) -> None:
    assert response.status_code == 429, response.text
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "rate_limited"
    assert 1 <= int(response.headers["retry-after"]) <= 60


async def workspace_of(client: httpx.AsyncClient, clerk: Clerk) -> tuple[str, str]:
    """A new user (their own email, so their own account) and their workspace id."""
    clerk_id, me = await sign_in(client, clerk, email=f"{uuid.uuid4().hex[:10]}@example.com")
    return clerk_id, me["workspaces"][0]["id"]


# ---------------------------------------------------------------- the window


async def test_the_window_admits_the_limit_then_waits_for_the_oldest(redis: Redis) -> None:
    limit, subject = Limit("t", 3, 60), uuid.uuid4().hex
    assert await hit(redis, limit, subject, now=1000.0) == 0
    assert await hit(redis, limit, subject, now=1010.0) == 0
    assert await hit(redis, limit, subject, now=1020.0) == 0
    # Full: the next request is admitted when the one at 1000 leaves, 30 s later.
    assert await hit(redis, limit, subject, now=1030.0) == pytest.approx(30.0)
    # A refused request isn't recorded, so the window slides as soon as the oldest leaves.
    assert await hit(redis, limit, subject, now=1060.5) == 0
    assert await hit(redis, limit, subject, now=1061.0) == pytest.approx(9.0)


async def test_each_subject_has_its_own_window(redis: Redis) -> None:
    limit = Limit("t", 1, 60)
    assert await hit(redis, limit, "a", now=1000.0) == 0
    assert await hit(redis, limit, "a", now=1001.0) > 0
    assert await hit(redis, limit, "b", now=1001.0) == 0


# ---------------------------------------------------------------- per user


async def test_a_user_over_300_a_minute_gets_429(
    client: httpx.AsyncClient, clerk: Clerk, redis: Redis
) -> None:
    clerk_id, _ = await workspace_of(client, clerk)
    other, _ = await workspace_of(client, clerk)
    await fill(redis, "user", clerk_id)

    assert_limited(await client.get("/v1/me", headers=clerk.headers(clerk_id)))
    assert (await client.get("/v1/me", headers=clerk.headers(other))).status_code == 200


async def test_an_invalid_token_is_401_and_spends_nothing(
    client: httpx.AsyncClient, clerk: Clerk, redis: Redis
) -> None:
    response = await client.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert [key async for key in redis.scan_iter("rl:user:*")] == []


# ---------------------------------------------------------------- per workspace

NIL = "00000000-0000-0000-0000-000000000001"

SEND_ROUTES = [
    f"/conversations/{NIL}/messages",
    f"/messages/{NIL}/retry",
    f"/comments/{NIL}/reply",
    f"/comments/{NIL}/private-reply",
    f"/conversations/{NIL}/scheduled-messages",
    f"/scheduled-posts/{NIL}/publish-now",
]
AI_ROUTES = [
    f"/conversations/{NIL}/suggestions",
    f"/conversations/{NIL}/summary",
    f"/conversations/{NIL}/polish",
    "/ai/caption",
    "/ai/hashtags",
    "/knowledge/test",
    "/agent/runs",
    f"/posts/{NIL}/summary",
]


@pytest.mark.parametrize(
    ("name", "path"),
    [("sends", path) for path in SEND_ROUTES] + [("ai", path) for path in AI_ROUTES],
)
async def test_sends_and_ai_requests_are_limited_per_workspace(
    client: httpx.AsyncClient, clerk: Clerk, redis: Redis, name: str, path: str
) -> None:
    clerk_id, wid = await workspace_of(client, clerk)
    await fill(redis, name, wid)
    response = await client.post(f"/v1/w/{wid}{path}", json={}, headers=clerk.headers(clerk_id))
    assert_limited(response)


async def test_the_send_and_ai_budgets_are_separate(
    client: httpx.AsyncClient, clerk: Clerk, redis: Redis
) -> None:
    clerk_id, wid = await workspace_of(client, clerk)
    headers = clerk.headers(clerk_id)
    await fill(redis, "sends", wid)
    assert_limited(await client.post(f"/v1/w/{wid}/messages/{NIL}/retry", headers=headers))
    # The AI budget is untouched: the route runs and finds no such conversation.
    response = await client.post(f"/v1/w/{wid}/conversations/{NIL}/suggestions", headers=headers)
    assert response.status_code == 404


async def test_another_workspace_is_unaffected_and_outsiders_spend_nothing(
    client: httpx.AsyncClient, clerk: Clerk, redis: Redis
) -> None:
    owner, wid = await workspace_of(client, clerk)
    outsider, other_wid = await workspace_of(client, clerk)
    await fill(redis, "sends", other_wid)

    # The outsider's own workspace is full; the owner's isn't.
    retry = f"/messages/{NIL}/retry"
    assert (await client.post(f"/v1/w/{wid}{retry}", headers=clerk.headers(owner))).status_code == (
        404
    )
    # A request for a workspace the caller isn't in is 404 before it counts (TR-API-03).
    for _ in range(3):
        response = await client.post(f"/v1/w/{wid}{retry}", headers=clerk.headers(outsider))
        assert response.status_code == 404
    assert await redis.zcard(window_key(LIMITS["sends"], wid)) == 1  # the owner's one request


# ---------------------------------------------------------------- per IP


async def test_the_oauth_callback_allows_30_a_minute_per_ip(client: httpx.AsyncClient) -> None:
    for _ in range(30):
        response = await client.get("/v1/oauth/instagram/callback", params={"state": "forged"})
        assert response.status_code == 303
    assert_limited(await client.get("/v1/oauth/instagram/callback", params={"state": "forged"}))


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/v1/digest/unsubscribe?token=forged"),
        ("GET", "/v1/billing/plans"),
        ("GET", "/v1/data-deletion/forged-code"),
    ],
)
async def test_public_routes_are_limited_per_ip(
    client: httpx.AsyncClient, redis: Redis, method: str, path: str
) -> None:
    await fill(redis, "public", CLIENT_IP)
    assert_limited(await client.request(method, path))


async def test_the_client_ip_comes_from_the_configured_edge_header(
    app: FastAPI, client: httpx.AsyncClient, redis: Redis
) -> None:
    app.state.settings.client_ip_header = "true-client-ip"
    await fill(redis, "public", "203.0.113.7")
    path = "/v1/data-deletion/forged-code"

    assert_limited(await client.get(path, headers={"True-Client-IP": "203.0.113.7"}))
    # X-Forwarded-For's first entry is the client's own claim and changes nothing.
    spoofed = {"True-Client-IP": "203.0.113.7", "X-Forwarded-For": "198.51.100.1"}
    assert_limited(await client.get(path, headers=spoofed))
    other = await client.get(path, headers={"True-Client-IP": "203.0.113.8"})
    assert other.status_code == 404, other.text


async def test_behind_render_the_client_ip_is_the_rightmost_untrusted_hop(
    app: FastAPI, client: httpx.AsyncClient, redis: Redis
) -> None:
    """Production: CLIENT_IP_HEADER=x-forwarded-for. Cloudflare and Render's load balancer
    append; a client's own X-Forwarded-For stays on the left and can't pick its bucket."""
    app.state.settings.client_ip_header = "X-Forwarded-For"
    await fill(redis, "public", "203.0.113.7")
    path = "/v1/data-deletion/forged-code"
    edge = "162.158.12.34, 10.204.1.9"  # Cloudflare, then Render's load balancer

    assert_limited(await client.get(path, headers={"X-Forwarded-For": f"203.0.113.7, {edge}"}))
    for forged in ("198.51.100.1", "203.0.113.8, 10.0.0.1"):
        spoofed = {"X-Forwarded-For": f"{forged}, 203.0.113.7, {edge}"}
        assert_limited(await client.get(path, headers=spoofed))
    other = await client.get(path, headers={"X-Forwarded-For": f"203.0.113.8, {edge}"})
    assert other.status_code == 404, other.text


async def test_webhooks_are_not_limited_by_ip(client: httpx.AsyncClient) -> None:
    # TR-API-07: Meta delivers from shared IPs; only the body size is capped.
    for _ in range(LIMITS["public"].max_requests + 5):
        response = await client.post("/webhooks/instagram", content=b"{}")
        assert response.status_code == 401


def _calls(dependant: Dependant) -> Iterator[Callable[..., Any]]:
    for sub in dependant.dependencies:
        if sub.call is not None:
            yield sub.call
        yield from _calls(sub)


async def test_every_v1_route_is_behind_a_limit(app: FastAPI) -> None:
    """A new route without sign-in must get a per-IP limit (api/ratelimit.PUBLIC); every route
    with sign-in has the per-user one."""
    unlimited = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/v1/"):
            continue
        calls = list(_calls(route.dependant))
        if current_user not in calls and not LIMIT_DEPENDENCIES.intersection(calls):
            unlimited.append(f"{sorted(route.methods)} {route.path}")
    assert unlimited == []


# ---------------------------------------------------------------- switches and outages


async def test_limits_can_be_switched_off_outside_production(
    app: FastAPI, client: httpx.AsyncClient, redis: Redis
) -> None:
    app.state.settings.rate_limits_enabled = False
    await fill(redis, "public", CLIENT_IP)
    assert (await client.get("/v1/data-deletion/forged-code")).status_code == 404


async def test_a_valkey_outage_lets_requests_through(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    working = app.state.redis
    app.state.redis = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    try:
        assert (await client.get("/v1/data-deletion/forged-code")).status_code == 404
    finally:
        await app.state.redis.aclose()
        app.state.redis = working
