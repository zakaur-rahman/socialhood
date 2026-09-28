"""T2.7: token refresh (FR-CON-05, F-05), notifications (FR-NOT-01) and rate buckets (TR-PL-09)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.tasks.accounts import refresh_due_tokens, resubscribe_all
from socialhood.platforms.buckets import Bucket, TokenBuckets
from socialhood.platforms.deps import deps_from
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.security.rotate import rotate_all
from socialhood.settings import get_settings
from tests.support.api import TOKEN_KEY, Clerk, sign_in
from tests.support.instagram import FakeInstagram, connect, fixture


async def connected(client: httpx.AsyncClient, clerk: Clerk) -> tuple[str, str]:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    await connect(client, clerk, clerk_id, wid)
    return clerk_id, wid


async def age_token(
    engine: AsyncEngine, *, expires_in: timedelta, refreshed_ago: timedelta
) -> None:
    now = datetime.now(UTC)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE social_accounts SET token_expires_at = :e, token_refreshed_at = :r"),
            {"e": now + expires_in, "r": now - refreshed_ago},
        )


async def account(engine: AsyncEngine) -> dict[str, Any]:
    async with engine.connect() as conn:
        return dict((await conn.execute(text("SELECT * FROM social_accounts"))).one()._mapping)


async def test_a_token_with_19_days_left_is_refreshed(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
) -> None:
    await connected(client, clerk)
    await age_token(engine, expires_in=timedelta(days=19), refreshed_ago=timedelta(days=41))

    deps = deps_from(app.state.http, app.state.settings)
    counts = await refresh_due_tokens(app.state.sessionmaker, deps)

    assert counts == {"refreshed": 1, "failed": 0, "skipped": 0}
    row = await account(engine)
    assert TokenCipher([TOKEN_KEY]).decrypt(row["access_token_enc"]) == "IGQVJrefreshed-token"
    assert row["token_expires_at"] > datetime.now(UTC) + timedelta(days=59)


async def test_tokens_with_time_left_or_too_young_are_skipped(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
) -> None:
    await connected(client, clerk)
    deps = deps_from(app.state.http, app.state.settings)

    await age_token(engine, expires_in=timedelta(days=30), refreshed_ago=timedelta(days=30))
    assert (await refresh_due_tokens(app.state.sessionmaker, deps))["skipped"] == 1
    # Instagram refuses to refresh a token younger than 24 hours.
    await age_token(engine, expires_in=timedelta(days=10), refreshed_ago=timedelta(hours=2))
    assert (await refresh_due_tokens(app.state.sessionmaker, deps))["skipped"] == 1
    assert "refresh" not in instagram.calls


async def test_a_refused_refresh_asks_the_owner_to_reconnect_once(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
) -> None:
    clerk_id, wid = await connected(client, clerk)
    await age_token(engine, expires_in=timedelta(days=5), refreshed_ago=timedelta(days=55))
    instagram.refresh = (400, fixture("error_190_expired.json"))
    deps = deps_from(app.state.http, app.state.settings)

    assert (await refresh_due_tokens(app.state.sessionmaker, deps))["failed"] == 1
    row = await account(engine)
    assert row["status"] == "needs_reconnect"
    assert row["last_error"] == "Instagram stopped accepting this connection."

    await refresh_due_tokens(app.state.sessionmaker, deps)  # tomorrow's run: not due any more
    listed = (
        await client.get(f"/v1/w/{wid}/notifications", headers=clerk.headers(clerk_id))
    ).json()
    assert listed["unread_count"] == 1
    [note] = listed["items"]
    assert (note["type"], note["severity"], note["title"]) == (
        "account_needs_reconnect",
        "critical",
        "Reconnect @maple.bakery",
    )
    assert note["link"] == "/settings/connections"


async def test_a_platform_outage_leaves_the_account_alone(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
) -> None:
    await connected(client, clerk)
    await age_token(engine, expires_in=timedelta(days=5), refreshed_ago=timedelta(days=55))
    instagram.refresh = (503, {"error": {"code": 2, "message": "down"}})
    deps = deps_from(app.state.http, app.state.settings)

    assert (await refresh_due_tokens(app.state.sessionmaker, deps))["failed"] == 1
    assert (await account(engine))["status"] == "active"


async def test_reconciling_subscriptions(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram
) -> None:
    await connected(client, clerk)
    deps = deps_from(app.state.http, app.state.settings)
    assert await resubscribe_all(app.state.sessionmaker, deps) == 1
    assert instagram.calls.count("subscribe") == 2  # connect, then the reconcile


async def test_notifications_can_be_marked_read(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
) -> None:
    clerk_id, wid = await connected(client, clerk)
    await age_token(engine, expires_in=timedelta(days=5), refreshed_ago=timedelta(days=55))
    instagram.refresh = (400, fixture("error_190_expired.json"))
    await refresh_due_tokens(app.state.sessionmaker, deps_from(app.state.http, app.state.settings))

    url = f"/v1/w/{wid}/notifications"
    headers = clerk.headers(clerk_id)
    [note] = (await client.get(url, headers=headers)).json()["items"]
    marked = await client.post(f"{url}/read", json={"ids": [note["id"]]}, headers=headers)
    assert marked.status_code == 204
    listed = (await client.get(url, headers=headers)).json()
    assert listed["unread_count"] == 0
    assert listed["items"][0]["read_at"] is not None


async def test_buckets_never_grant_more_than_the_rate(redis: Redis) -> None:
    buckets = TokenBuckets(redis)
    now = 1_000_000.0
    waits = [await buckets.take(Bucket.IG_SEND, "acct-1", now=now) for _ in range(300)]
    assert sum(1 for w in waits if w == 0) == 100
    assert all(w > 0 for w in waits[100:])

    later = [await buckets.take(Bucket.IG_SEND, "acct-1", now=now + 1) for _ in range(150)]
    assert sum(1 for w in later if w == 0) == 100
    # Each account has its own bucket.
    assert await buckets.take(Bucket.IG_SEND, "acct-2", now=now) == 0


async def test_private_replies_refill_slowly(redis: Redis) -> None:
    buckets = TokenBuckets(redis)
    now = 2_000_000.0
    for _ in range(750):
        assert await buckets.take(Bucket.IG_PRIVATE_REPLY, "a", now=now) == 0
    wait = await buckets.take(Bucket.IG_PRIVATE_REPLY, "a", now=now)
    assert 4.7 < wait < 4.9  # one token per 3600 / 750 = 4.8 seconds


async def test_key_rotation_re_encrypts_every_token(
    client: httpx.AsyncClient, clerk: Clerk, instagram: FakeInstagram, engine: AsyncEngine
) -> None:
    await connected(client, clerk)
    newest = new_key()
    rotated = await rotate_all(get_settings().database_url, TokenCipher([newest, TOKEN_KEY]))
    assert rotated == 1
    row = await account(engine)
    assert TokenCipher([newest]).decrypt(row["access_token_enc"]) == "IGQVJlong-lived-token"
