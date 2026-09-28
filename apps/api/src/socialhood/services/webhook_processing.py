"""Process one stored webhook event (TR-WH-05).

Lock the row if it still needs work, dispatch it to its provider's handler, and record the
outcome: processed, ignored, or failed with the error (replayable later, TR-OPS-04).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.models.platform import WebhookProvider, WebhookStatus
from socialhood.observability.logging import get_logger
from socialhood.repositories import webhook_events
from socialhood.services import clerk_sync

log = get_logger(__name__)

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[Literal["processed", "ignored"]]]

HANDLERS: dict[str, Handler] = {
    WebhookProvider.CLERK: clerk_sync.apply_event,
}


async def process_event(
    sessionmaker: async_sessionmaker[AsyncSession], event_id: uuid.UUID
) -> WebhookStatus | None:
    """Return the final status, or None when there was nothing to do."""
    async with sessionmaker() as session:
        event = await webhook_events.claim(session, event_id)
        if event is None:
            return None
        handler = HANDLERS.get(event.provider)
        if handler is None:
            await webhook_events.finish(
                session, event_id, WebhookStatus.IGNORED, error="no handler"
            )
            await session.commit()
            return WebhookStatus.IGNORED
        payload = event.payload
        provider = event.provider
        try:
            outcome = await handler(session, payload)
        except Exception as error:
            await session.rollback()
            log.exception("webhook_event_failed", event_id=str(event_id), provider=provider)
            async with sessionmaker() as failed:
                await webhook_events.finish(
                    failed, event_id, WebhookStatus.FAILED, error=f"{type(error).__name__}: {error}"
                )
                await failed.commit()
            raise
        status = WebhookStatus.PROCESSED if outcome == "processed" else WebhookStatus.IGNORED
        await webhook_events.finish(session, event_id, status)
        await session.commit()
        return status
