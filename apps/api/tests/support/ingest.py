"""Helpers for the ingest, follow-up and sync tests: store fixture deliveries as webhook events
and process them the way the worker does, then look at rows, jobs and the real-time stream."""

from __future__ import annotations

import json
import uuid
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from socialhood.db.engine import make_sessionmaker
from socialhood.jobs.app import app as jobs_app
from socialhood.models.platform import WebhookStatus
from socialhood.platforms.instagram.webhooks import split_payload
from socialhood.realtime import events
from socialhood.repositories import webhook_events
from socialhood.services.webhook_processing import process_event
from tests.support.instagram import fixture

ACCOUNT_REF = "17841400000000001"  # the fixtures' entry.id
CUSTOMER = "990000000000001"  # the fixtures' customer IGSID


def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Sessions configured like the worker's."""
    return make_sessionmaker(engine)


async def deliver(
    maker: async_sessionmaker[AsyncSession],
    redis: Redis,
    body: str | dict[str, Any],
    *,
    copy: str = "",
) -> list[WebhookStatus | None]:
    """Store a delivery's events (``copy`` makes new dedupe keys, as an ops replay of another
    copy would) and process each like process_webhook_event does."""
    payload = fixture(body) if isinstance(body, str) else body
    ids: list[uuid.UUID] = []
    async with maker() as session:
        for raw in split_payload(payload):
            event_id = await webhook_events.store(
                session,
                provider="instagram",
                dedupe_key=raw.dedupe_key + copy,
                event_type=raw.event_type,
                payload=dict(raw.payload),
                platform_account_id=raw.account_ref,
            )
            assert event_id is not None, "already stored: pass copy=..."
            ids.append(event_id)
        await session.commit()
    return [await process_event(maker, event_id, redis) for event_id in ids]


async def replay_all(
    engine: AsyncEngine, maker: async_sessionmaker[AsyncSession], redis: Redis
) -> list[WebhookStatus | None]:
    """TR-OPS-04's replay: every stored event back to received, processed again."""
    async with engine.begin() as conn:
        ids = (
            await conn.execute(
                text("UPDATE webhook_events SET status = 'received', attempts = 0 RETURNING id")
            )
        ).scalars()
        event_ids = list(ids)
    return [await process_event(maker, event_id, redis) for event_id in event_ids]


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def webhook_rows(engine: AsyncEngine) -> list[dict[str, Any]]:
    return await rows(
        engine,
        "SELECT event_type, status, last_error FROM webhook_events"
        " ORDER BY received_at, dedupe_key",
    )


async def stream(redis: Redis, workspace_id: uuid.UUID | str) -> list[tuple[str, dict[str, Any]]]:
    entries = await redis.xrange(events.stream_key(uuid.UUID(str(workspace_id))))
    return [(e[1]["type"], json.loads(e[1]["data"])) for e in entries]


async def jobs(task_name: str | None = None) -> list[dict[str, Any]]:
    query = (
        "SELECT task_name, queue_name, queueing_lock, args,"
        " scheduled_at > now() AS deferred FROM procrastinate_jobs"
    )
    if task_name:
        return list(
            await jobs_app.connector.execute_query_all_async(
                query + " WHERE task_name = %(t)s ORDER BY id", t=task_name
            )
        )
    return list(await jobs_app.connector.execute_query_all_async(query + " ORDER BY id"))
