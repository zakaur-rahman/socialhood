"""The workspace's real-time stream as Server-Sent Events (T3.4, TR-RT-02).

``GET /v1/w/{wid}/events`` follows the Redis Stream ``events:{workspace_id}`` that
``realtime.events`` appends to after each commit (TR-RT-01):

- it starts after the Last-Event-ID header, else after the newest entry ("$": new events only);
- each entry goes out as ``id: <stream id>``, ``event: <type>``, ``data: <json>``;
- ``retry: 3000`` is sent once, and ``: ping`` after each 15 s without events;
- when the requested id is no longer in the stream (trimmed by MAXLEN, or never there), one
  ``event: resync`` tells the client to refetch, and the stream continues from the newest entry.
  The resync carries that entry's id, so a client that drops again resumes without a gap.

Every open stream blocks in XREAD on its own Redis connection, so long reads never take
connections from the shared pool, and the connection is closed when the client goes away. A stream
ends after ``MAX_STREAM_S``; the client reconnects with Last-Event-ID and a fresh token, which
rechecks its membership.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import anyio
from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

from socialhood.observability.logging import get_logger
from socialhood.realtime.events import stream_key

log = get_logger(__name__)

BLOCK_MS = 15_000  # one XREAD; a read that returns nothing is followed by a ping
BATCH = 100
RETRY_MS = 3_000
MAX_STREAM_S = 30 * 60
ORIGIN = "0-0"  # before every stream entry
PING = ": ping\n\n"
# Cache-Control no-transform keeps proxies from compressing the stream ("never compressed").
HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}

_STREAM_ID = re.compile(r"\d{1,20}-\d{1,20}")

Entry = tuple[str, dict[str, str]]


@dataclass(frozen=True)
class Start:
    """Where a stream begins: entries after ``cursor``, preceded by a resync when ``resync``."""

    cursor: str
    resync: bool


def connect(redis_url: str, workspace_id: uuid.UUID) -> Redis:
    """A dedicated connection for one stream's blocking reads (named for CLIENT LIST)."""
    return Redis.from_url(
        redis_url,
        decode_responses=True,
        single_connection_client=True,
        client_name=f"sse:{workspace_id}",
    )


async def start_position(redis: Redis, key: str, last_event_id: str | None) -> Start:
    """Resume after ``last_event_id`` while it is still in the stream; otherwise resync."""
    requested = (last_event_id or "").strip()
    if requested and await _replayable(redis, key, requested):
        return Start(cursor=requested, resync=False)
    newest = await redis.xrevrange(key, "+", "-", count=1)
    cursor = str(newest[0][0]) if newest else ORIGIN
    return Start(cursor=cursor, resync=bool(requested))


async def _replayable(redis: Redis, key: str, requested: str) -> bool:
    if not _STREAM_ID.fullmatch(requested):
        return False
    if requested == ORIGIN:
        # Sent in a resync while the stream was empty: everything after it is still there unless
        # the stream has been trimmed since.
        return await _never_trimmed(redis, key)
    return bool(await redis.xrange(key, requested, requested, count=1))


async def _never_trimmed(redis: Redis, key: str) -> bool:
    try:
        info: dict[str, Any] = await redis.xinfo_stream(key)
    except ResponseError:  # no such key: nothing was ever published
        return True
    return int(info["entries-added"]) == int(info["length"])


def format_event(event_id: str, event_type: str, data: str) -> str:
    lines = "".join(f"data: {line}\n" for line in data.split("\n"))
    return f"id: {event_id}\nevent: {event_type}\n{lines}\n"


def _entries(response: Any) -> list[Entry]:
    """XREAD's RESP2 reply, ``[[key, [(id, fields), ...]]]`` or empty on timeout."""
    return [
        (str(entry_id), dict(fields or {}))
        for _key, rows in response or []
        for entry_id, fields in rows
    ]


async def event_stream(
    reader: Redis,
    workspace_id: uuid.UUID,
    start: Start,
    *,
    is_disconnected: Callable[[], Awaitable[bool]],
    block_ms: int = BLOCK_MS,
    max_duration_s: float = MAX_STREAM_S,
) -> AsyncIterator[str]:
    """The response body. Reads with ``reader`` (see ``connect``) and closes it when done."""
    key = stream_key(workspace_id)
    deadline = time.monotonic() + max_duration_s
    cursor = start.cursor
    try:
        yield f"retry: {RETRY_MS}\n\n"
        if start.resync:
            yield format_event(cursor, "resync", "{}")
        while time.monotonic() < deadline:
            response = await reader.xread({key: cursor}, count=BATCH, block=block_ms)
            if await is_disconnected():
                return
            entries = _entries(response)
            if not entries:
                yield PING
                continue
            for entry_id, fields in entries:
                cursor = entry_id
                yield format_event(
                    entry_id, fields.get("type", "message"), fields.get("data", "{}")
                )
    except RedisError as error:
        # The client reconnects after RETRY_MS with the last id it received.
        log.warning("realtime_stream_failed", error=type(error).__name__)
    finally:
        with anyio.CancelScope(shield=True):
            await reader.aclose()
