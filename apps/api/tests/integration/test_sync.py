"""T3.14 (FR-CON-01): connecting an account queues sync_media and backfill_account, and running
them stores its recent posts and conversations, for the sandbox and for (mocked) Instagram."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.instagram import reads
from socialhood.services.sync import backfill_account, sync_account_media
from tests.support.api import Clerk, sign_in
from tests.support.ingest import CUSTOMER, jobs, rows, sessions, stream
from tests.support.instagram import GRAPH, FakeInstagram, connect, fixture

THREAD_ID = fixture("conversations_list.json")["data"][0]["id"]


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reads, "CONVERSATIONS_PACE_S", 0)


def deps(app: FastAPI) -> PlatformDeps:
    return deps_from(app.state.http, app.state.settings)


async def run_both(
    app: FastAPI, engine: AsyncEngine, redis: Redis, wid: str, account_id: str
) -> tuple[int | None, int | None]:
    ids = {"workspace_id": uuid.UUID(wid), "account_id": uuid.UUID(account_id)}
    posts = await sync_account_media(sessions(engine), deps(app), **ids)
    created = await backfill_account(sessions(engine), redis, deps(app), **ids)
    return posts, created


async def conversations(engine: AsyncEngine) -> list[dict[str, Any]]:
    return await rows(
        engine,
        "SELECT c.platform_conversation_id, c.unread_count, c.awaiting_reply, c.status,"
        " c.last_message_preview, t.username, t.platform_user_id,"
        " (SELECT array_agg(m.direction || ':' || m.source ORDER BY m.occurred_at)"
        "  FROM messages m WHERE m.conversation_id = c.id) AS thread"
        " FROM conversations c JOIN contacts t ON t.id = c.contact_id"
        " ORDER BY c.platform_conversation_id",
    )


async def test_a_sandbox_account_shows_posts_and_conversations_after_connecting(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    created = await client.post(
        f"/v1/w/{wid}/dev/sandbox/accounts", headers=clerk.headers(clerk_id)
    )
    account_id = created.json()["id"]

    queued = {j["task_name"]: j for j in await jobs() if j["task_name"] != "ping"}
    assert queued.keys() == {"sync_media", "backfill_account"}
    assert queued["sync_media"]["queueing_lock"] == f"mediasync:{account_id}"
    assert queued["backfill_account"]["queueing_lock"] == f"backfill:{account_id}"
    assert {j["queue_name"] for j in queued.values()} == {"bulk"}

    assert await run_both(app, engine, redis, wid, account_id) == (3, 6)

    posts = await rows(
        engine, "SELECT media_type, caption FROM media_items ORDER BY posted_at DESC"
    )
    assert [p["media_type"] for p in posts] == ["image", "carousel", "reel"]
    threads = await conversations(engine)
    assert [t["thread"] for t in threads] == [
        ["inbound:customer", "outbound:native_app", "inbound:customer"],
        ["inbound:customer"],
        ["inbound:customer", "outbound:native_app"],
    ]
    # History is not new: nothing unread; still waiting where the customer wrote last.
    assert [(t["unread_count"], t["awaiting_reply"]) for t in threads] == [
        (0, True),
        (0, True),
        (0, False),
    ]
    assert all(t["platform_conversation_id"] and t["username"] for t in threads)
    [account] = await rows(engine, "SELECT media_synced_at, backfilled_at FROM social_accounts")
    assert account["media_synced_at"] is not None
    assert account["backfilled_at"] is not None

    published = await stream(redis, wid)
    assert {t for t, _ in published} == {"conversation.updated"}  # no event per old message
    assert len(await jobs("fetch_contact_profile")) == 3

    # Running both again (the 6-hourly sync, a reconnect) duplicates nothing.
    assert await run_both(app, engine, redis, wid, account_id) == (3, 0)
    assert len(await conversations(engine)) == 3
    assert len(await rows(engine, "SELECT id FROM media_items")) == 3


def mock_graph(clerk: Clerk) -> dict[str, Any]:
    router = clerk.router
    return {
        "media": router.get(url__regex=rf"{GRAPH}/v[\d.]+/me/media").respond(
            200, json=fixture("media_list.json")
        ),
        "conversations": router.get(url__regex=rf"{GRAPH}/v[\d.]+/me/conversations").respond(
            200, json=fixture("conversations_list.json")
        ),
        "thread": router.get(url__regex=rf"{GRAPH}/v[\d.]+/{THREAD_ID}").respond(
            200, json=fixture("conversation_messages.json")
        ),
    }


async def test_an_instagram_account_shows_posts_and_conversations_after_connecting(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    routes = mock_graph(clerk)
    await connect(client, clerk, clerk_id, wid)
    [account] = await rows(engine, "SELECT id FROM social_accounts")
    account_id = str(account["id"])
    assert {j["task_name"] for j in await jobs()} >= {"sync_media", "backfill_account"}

    assert await run_both(app, engine, redis, wid, account_id) == (3, 3)
    assert routes["media"].calls.last.request.url.params["limit"] == "25"

    posts = await rows(engine, "SELECT platform_media_id, media_type, like_count FROM media_items")
    assert {(p["platform_media_id"], p["media_type"]) for p in posts} == {
        ("18100000000000003", "image"),
        ("18100000000000002", "carousel"),
        ("18100000000000001", "reel"),
    }
    [thread] = await conversations(engine)
    assert thread["platform_conversation_id"] == THREAD_ID
    assert (thread["platform_user_id"], thread["username"]) == (CUSTOMER, "priya.shah")
    assert thread["thread"] == ["inbound:customer", "outbound:native_app", "inbound:customer"]
    assert thread["last_message_preview"] == "Photo"
    assert len(await jobs("ingest_media")) == 1  # the photo in the history
    assert len(await jobs("fetch_contact_profile")) == 1


async def test_a_refusal_ends_the_backfill_and_an_outage_retries(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    instagram: FakeInstagram,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    await connect(client, clerk, clerk_id, wid)
    [account] = await rows(engine, "SELECT id FROM social_accounts")
    route = clerk.router.get(url__regex=rf"{GRAPH}/v[\d.]+/me/conversations")
    ids = {"workspace_id": uuid.UUID(wid), "account_id": account["id"]}

    route.respond(400, json={"error": {"code": 10, "message": "Permission denied"}})
    assert await backfill_account(sessions(engine), redis, deps(app), **ids) is None
    route.respond(503, json={"error": {"code": 2, "message": "Service unavailable"}})
    with pytest.raises(PlatformError):
        await backfill_account(sessions(engine), redis, deps(app), **ids)
    [row] = await rows(engine, "SELECT backfilled_at FROM social_accounts")
    assert row["backfilled_at"] is None
