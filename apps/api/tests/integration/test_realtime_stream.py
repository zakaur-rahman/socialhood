"""T3.4: the real-time stream over Server-Sent Events (TR-RT-01...03).

The stream generator is driven directly (httpx's ASGI transport buffers streaming bodies); the
end-to-end tests run the app under uvicorn on a free port and read it with real HTTP clients.
"""

from __future__ import annotations

import asyncio
import json
import socket
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from redis.asyncio import Redis

from socialhood.realtime import stream
from socialhood.realtime.events import publish, stream_key
from socialhood.settings import get_settings
from tests.support.api import Clerk, sign_in
from tests.support.inbox import make_account, make_thread, make_workspace

TIMEOUT_S = 10


def never() -> Any:
    async def is_disconnected() -> bool:
        return False

    return is_disconnected


async def published(
    redis: Redis, wid: uuid.UUID, n: int, kind: Any = "notification.created"
) -> list[str]:
    ids = []
    for i in range(n):
        event_id = await publish(redis, wid, kind, {"n": i})
        assert event_id is not None
        ids.append(event_id)
    return ids


async def sse_clients(redis: Redis, wid: uuid.UUID) -> int:
    """Open stream connections for the workspace (each stream names its own connection)."""
    return sum(1 for c in await redis.client_list() if c.get("name") == f"sse:{wid}")


async def eventually(check: Callable[[], Awaitable[bool]]) -> None:
    for _ in range(TIMEOUT_S * 20):
        if await check():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition not met in time")


async def until_closed(redis: Redis, wid: uuid.UUID) -> None:
    async def closed() -> bool:
        return await sse_clients(redis, wid) == 0

    await eventually(closed)


# ---------------------------------------------------------------- where a stream starts


async def test_a_new_stream_starts_after_the_newest_entry(redis: Redis) -> None:
    wid = uuid.uuid4()
    key = stream_key(wid)
    assert await stream.start_position(redis, key, None) == stream.Start(stream.ORIGIN, False)
    ids = await published(redis, wid, 3)
    assert await stream.start_position(redis, key, None) == stream.Start(ids[-1], False)
    assert await stream.start_position(redis, key, "") == stream.Start(ids[-1], False)


async def test_last_event_id_resumes_while_it_is_in_the_stream(redis: Redis) -> None:
    wid = uuid.uuid4()
    key = stream_key(wid)
    ids = await published(redis, wid, 5)
    assert await stream.start_position(redis, key, ids[1]) == stream.Start(ids[1], False)

    await redis.xtrim(key, maxlen=2, approximate=False)  # ids[0..2] are gone
    assert await stream.start_position(redis, key, ids[2]) == stream.Start(ids[-1], True)
    assert await stream.start_position(redis, key, ids[3]) == stream.Start(ids[3], False)


@pytest.mark.parametrize("requested", ["garbage", "1-2-3", "99999999999999-0", "1-0"])
async def test_an_unknown_id_resyncs(redis: Redis, requested: str) -> None:
    wid = uuid.uuid4()
    ids = await published(redis, wid, 2)
    assert await stream.start_position(redis, stream_key(wid), requested) == stream.Start(
        ids[-1], True
    )


async def test_the_origin_replays_everything_until_the_stream_is_trimmed(redis: Redis) -> None:
    wid = uuid.uuid4()
    key = stream_key(wid)
    assert await stream.start_position(redis, key, stream.ORIGIN) == stream.Start("0-0", False)
    ids = await published(redis, wid, 3)
    assert await stream.start_position(redis, key, stream.ORIGIN) == stream.Start("0-0", False)
    await redis.xtrim(key, maxlen=1, approximate=False)
    assert await stream.start_position(redis, key, stream.ORIGIN) == stream.Start(ids[-1], True)


# ---------------------------------------------------------------- the stream body


def parse(chunk: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in chunk.strip("\n").split("\n"):
        name, _, value = line.partition(": ")
        fields[name] = value
    return fields


async def test_the_stream_sends_retry_then_entries_in_order(redis: Redis) -> None:
    wid = uuid.uuid4()
    start = await stream.start_position(redis, stream_key(wid), None)
    reader = stream.connect(get_settings().redis_url, wid)
    body = stream.event_stream(reader, wid, start, is_disconnected=never(), block_ms=5_000)

    async with asyncio.timeout(TIMEOUT_S):
        assert await anext(body) == "retry: 3000\n\n"
        pending = asyncio.ensure_future(anext(body))
        await asyncio.sleep(0.2)  # blocked in XREAD
        ids = await published(redis, wid, 3, "message.created")
        chunks = [await pending, await anext(body), await anext(body)]
        await body.aclose()

    assert [parse(c) for c in chunks] == [
        {
            "id": event_id,
            "event": "message.created",
            "data": json.dumps({"n": i}, separators=(",", ":")),
        }
        for i, event_id in enumerate(ids)
    ]
    assert chunks[0].endswith("\n\n")
    await until_closed(redis, wid)


async def test_an_idle_stream_pings_and_ends_when_the_client_leaves(redis: Redis) -> None:
    wid = uuid.uuid4()
    left = asyncio.Event()

    async def is_disconnected() -> bool:
        return left.is_set()

    start = await stream.start_position(redis, stream_key(wid), None)
    reader = stream.connect(get_settings().redis_url, wid)
    body = stream.event_stream(reader, wid, start, is_disconnected=is_disconnected, block_ms=100)
    async with asyncio.timeout(TIMEOUT_S):
        assert await anext(body) == "retry: 3000\n\n"
        assert await anext(body) == ": ping\n\n"
        assert await sse_clients(redis, wid) == 1  # its own connection, not the shared pool's
        left.set()
        assert [chunk async for chunk in body] == []
    await until_closed(redis, wid)


async def test_a_resync_carries_the_id_the_stream_continues_from(redis: Redis) -> None:
    wid = uuid.uuid4()
    ids = await published(redis, wid, 3)
    await redis.xtrim(stream_key(wid), maxlen=1, approximate=False)
    start = await stream.start_position(redis, stream_key(wid), ids[0])
    reader = stream.connect(get_settings().redis_url, wid)
    body = stream.event_stream(reader, wid, start, is_disconnected=never(), block_ms=100)
    async with asyncio.timeout(TIMEOUT_S):
        assert await anext(body) == "retry: 3000\n\n"
        assert parse(await anext(body)) == {"id": ids[-1], "event": "resync", "data": "{}"}
        new = await published(redis, wid, 1)
        assert parse(await anext(body))["id"] == new[0]
        await body.aclose()


async def test_a_stream_ends_after_its_lifetime(redis: Redis) -> None:
    wid = uuid.uuid4()
    reader = stream.connect(get_settings().redis_url, wid)
    body = stream.event_stream(
        reader,
        wid,
        stream.Start(stream.ORIGIN, False),
        is_disconnected=never(),
        block_ms=50,
        max_duration_s=0.3,
    )
    async with asyncio.timeout(TIMEOUT_S):
        chunks = [chunk async for chunk in body]
    assert chunks[0] == "retry: 3000\n\n"
    assert set(chunks[1:]) == {": ping\n\n"}


def test_multi_line_data_stays_one_event() -> None:
    assert stream.format_event("1-0", "x", "a\nb") == "id: 1-0\nevent: x\ndata: a\ndata: b\n\n"


# ---------------------------------------------------------------- end to end, over HTTP


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
async def live(app: FastAPI, clerk: Clerk) -> AsyncIterator[str]:
    """The app under uvicorn on a free port (the job queue's lifespan is not needed)."""
    port = free_port()
    clerk.router.route(host="127.0.0.1").pass_through()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            lifespan="off",
            log_level="warning",
            timeout_graceful_shutdown=2,
        )
    )
    task = asyncio.create_task(server.serve())

    async def started() -> bool:
        return bool(server.started)

    await eventually(started)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    await task


@dataclass
class Sse:
    """Reads one SSE response: comments skipped, one dict per event."""

    response: httpx.Response
    lines: AsyncIterator[str] = field(init=False)

    def __post_init__(self) -> None:
        self.lines = self.response.aiter_lines()

    async def next(self) -> dict[str, str]:
        fields: dict[str, str] = {}
        async with asyncio.timeout(TIMEOUT_S):
            async for line in self.lines:
                if line == "":
                    if "event" in fields:
                        return fields
                    fields = {}
                    continue
                if line.startswith(":"):
                    continue
                name, _, value = line.partition(": ")
                fields[name] = value
        raise AssertionError("stream ended")


async def test_two_clients_get_the_same_events_and_a_reconnect_replays(
    live: str, app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: Any, redis: Redis
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = me["workspaces"][0]["id"]
    account = await make_account(engine, wid)
    thread = await make_thread(engine, workspace_id=wid, account_id=account, unread=2)
    path = f"/v1/w/{wid}/events"
    conv = f"/v1/w/{wid}/conversations/{thread.conversation_id}"

    async def change(body: dict[str, Any]) -> None:
        response = await client.patch(conv, json=body, headers=clerk.headers(clerk_id))
        assert response.status_code == 200, response.text

    async with httpx.AsyncClient(base_url=live, timeout=TIMEOUT_S) as http:
        async with (
            http.stream("GET", path, headers=clerk.headers(clerk_id)) as first,
            http.stream("GET", path, headers=clerk.headers(clerk_id)) as second,
        ):
            assert first.status_code == 200
            assert first.headers["content-type"].startswith("text/event-stream")
            assert first.headers["cache-control"].startswith("no-cache")
            assert first.headers["x-accel-buffering"] == "no"
            assert "content-encoding" not in first.headers
            assert app.state.engine.pool.checkedout() == 0  # open streams hold no DB connection
            a, b = Sse(first), Sse(second)

            await change({"status": "archived"})
            seen_a, seen_b = await a.next(), await b.next()
            assert seen_a == seen_b
            assert seen_a["event"] == "conversation.updated"
            assert json.loads(seen_a["data"])["conversation"]["status"] == "archived"
            assert await sse_clients(redis, uuid.UUID(wid)) == 2

        # Both clients left: their stream connections close.
        await until_closed(redis, uuid.UUID(wid))

        # Missed while disconnected, replayed on reconnect.
        await change({"status": "open"})
        await change({"ai_mode_override": "off"})
        headers = {**clerk.headers(clerk_id), "Last-Event-ID": seen_a["id"]}
        async with http.stream("GET", path, headers=headers) as again:
            replay = Sse(again)
            missed = [await replay.next(), await replay.next()]
            assert [json.loads(e["data"])["conversation"]["status"] for e in missed] == [
                "open",
                "open",
            ]
            assert missed[0]["id"] > seen_a["id"]
            last_id = missed[1]["id"]

        # Trimmed past the client's id: one resync, then new events.
        await redis.xadd(stream_key(uuid.UUID(wid)), {"type": "usage.updated", "data": "{}"})
        await redis.xtrim(stream_key(uuid.UUID(wid)), maxlen=1, approximate=False)
        headers = {**clerk.headers(clerk_id), "Last-Event-ID": last_id}
        async with http.stream("GET", path, headers=headers) as late:
            events = Sse(late)
            resync = await events.next()
            assert resync["event"] == "resync"
            await change({"clear_ai_mode_override": True})
            assert (await events.next())["event"] == "conversation.updated"


async def test_the_stream_needs_a_member(
    client: httpx.AsyncClient, clerk: Clerk, engine: Any
) -> None:
    clerk_id, _ = await sign_in(client, clerk)
    other = await make_workspace(engine)
    response = await client.get(f"/v1/w/{other}/events", headers=clerk.headers(clerk_id))
    assert response.status_code == 404
    assert (await client.get(f"/v1/w/{other}/events")).status_code == 401
