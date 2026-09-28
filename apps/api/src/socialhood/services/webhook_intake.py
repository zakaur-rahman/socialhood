"""Store split webhook events once and queue their processing (TR-WH-03).

Shared by the provider routes and the sandbox, so both follow exactly the same path.
"""

from __future__ import annotations

import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.jobs.enqueue import enqueue
from socialhood.observability.logging import get_logger
from socialhood.platforms.events import RawEvent
from socialhood.repositories import webhook_events

log = get_logger(__name__)


async def store_and_enqueue(
    session: AsyncSession, provider: str, events: list[RawEvent]
) -> list[uuid.UUID]:
    """Insert each event (re-deliveries insert nothing), commit, then enqueue the new ones.

    An enqueue failure is logged, not raised: the row is safe, and sweep_stuck re-enqueues
    events still ``received`` after 60 seconds.
    """
    inserted: list[uuid.UUID] = []
    for event in events:
        event_id = await webhook_events.store(
            session,
            provider=provider,
            dedupe_key=event.dedupe_key,
            event_type=event.event_type,
            payload=dict(event.payload),
            platform_account_id=event.account_ref,
        )
        if event_id is not None:
            inserted.append(event_id)
    await session.commit()
    for event_id in inserted:
        await enqueue_processing(event_id)
    return inserted


async def enqueue_processing(event_id: uuid.UUID) -> bool:
    from socialhood.jobs.tasks.webhooks import process_webhook_event

    try:
        return await enqueue(
            process_webhook_event, key=f"wh:{event_id}", webhook_event_id=str(event_id)
        )
    except Exception:
        log.warning("webhook_enqueue_failed", event_id=str(event_id))
        return False


async def record_delivery(redis: Redis, provider: str, ok: bool, *, minute: int) -> None:
    """Per-minute delivery counters for the webhook health check (TR-WH-08)."""
    try:
        key = f"wh:{provider}:{minute}:{'ok' if ok else 'fail'}"
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 3600)
        if ok:
            pipe.set(f"wh:{provider}:last", minute, ex=7 * 24 * 3600)
        await pipe.execute()
    except Exception:
        log.warning("webhook_counter_failed", provider=provider)
