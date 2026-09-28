"""Process one stored webhook event (TR-WH-05).

Lock the row if it still needs work, route it to its workspace, dispatch it to its provider's
handler, and record the outcome: processed, ignored (with the reason), or failed with the error
(replayable, TR-OPS-04).
"""

from __future__ import annotations

import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.models.platform import WebhookEvent, WebhookProvider, WebhookStatus
from socialhood.observability.logging import get_logger
from socialhood.realtime import events
from socialhood.repositories import webhook_events
from socialhood.services import clerk_sync
from socialhood.services.webhook_handlers import Handler, Outcome, instagram, whatsapp

__all__ = ["HANDLERS", "Outcome", "process_event"]

log = get_logger(__name__)


async def _clerk(session: AsyncSession, event: WebhookEvent) -> Outcome:
    result = await clerk_sync.apply_event(session, event.payload)
    return Outcome(result, None if result == "processed" else "not a user change we act on")


HANDLERS: dict[str, Handler] = {
    WebhookProvider.CLERK: _clerk,
    WebhookProvider.INSTAGRAM: instagram.handle,
    WebhookProvider.WHATSAPP: whatsapp.handle,
}


async def process_event(
    sessionmaker: async_sessionmaker[AsyncSession],
    event_id: uuid.UUID,
    redis: Redis | None = None,
) -> WebhookStatus | None:
    """Return the final status, or None when there was nothing to do.

    A failure with attempts left puts the row back to ``received`` and re-raises, so the job
    retries with backoff; the last attempt marks it ``failed`` and returns (TR-JOB-04).
    """
    async with sessionmaker() as session:
        claimed = await webhook_events.claim(session, event_id)
        if claimed is None:
            return None
        event, attempt = claimed
        handler = HANDLERS.get(event.provider)
        if handler is None:
            await webhook_events.finish(
                session, event_id, WebhookStatus.IGNORED, error="no handler", attempts=attempt
            )
            await session.commit()
            return WebhookStatus.IGNORED
        provider = event.provider
        try:
            outcome = await handler(session, event)
        except Exception as error:
            await session.rollback()
            events.discard(session)
            final = attempt >= webhook_events.MAX_ATTEMPTS
            log.exception(
                "webhook_event_failed",
                event_id=str(event_id),
                provider=provider,
                attempt=attempt,
                final=final,
            )
            async with sessionmaker() as failed:
                await webhook_events.record_failure(
                    failed,
                    event_id,
                    attempt=attempt,
                    error=f"{type(error).__name__}: {error}",
                    final=final,
                )
                await failed.commit()
            if final:
                return WebhookStatus.FAILED
            raise
        status = WebhookStatus.PROCESSED if outcome.status == "processed" else WebhookStatus.IGNORED
        await webhook_events.finish(
            session,
            event_id,
            status,
            error=outcome.reason if status is WebhookStatus.IGNORED else None,
            workspace_id=outcome.workspace_id,
            attempts=attempt,
        )
        # Real-time events the handler queued go out only now that the rows are committed.
        if redis is not None:
            await events.commit_and_publish(session, redis)
        else:
            await session.commit()
            events.discard(session)
        return status
