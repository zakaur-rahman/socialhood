"""Process one stored webhook event (TR-WH-05).

Lock the row if it still needs work, route it to its workspace, dispatch it to its provider's
handler, and record the outcome: processed, ignored (with the reason), or failed with the error
(replayable, TR-OPS-04).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.models.platform import WebhookEvent, WebhookProvider, WebhookStatus
from socialhood.observability.logging import get_logger
from socialhood.repositories import webhook_events
from socialhood.services import clerk_sync
from socialhood.webhooks.routing import resolve_account

log = get_logger(__name__)


@dataclass(frozen=True)
class Outcome:
    status: Literal["processed", "ignored"]
    reason: str | None = None
    workspace_id: uuid.UUID | None = None


Handler = Callable[[AsyncSession, WebhookEvent], Awaitable[Outcome]]


async def _clerk(session: AsyncSession, event: WebhookEvent) -> Outcome:
    result = await clerk_sync.apply_event(session, event.payload)
    return Outcome(result, None if result == "processed" else "not a user change we act on")


async def _instagram(session: AsyncSession, event: WebhookEvent) -> Outcome:
    if event.event_type == "invalid":
        return Outcome("ignored", "unreadable payload")
    routed = await resolve_account(session, "instagram", event.platform_account_id or "")
    if routed is None:
        return Outcome("ignored", "unknown or disconnected account")
    with workspace_scope(routed.workspace_id):
        # Messages, reactions and reads become inbox data in P3 (services/ingest.py, T3.2);
        # comments in P6. Until then routed events are kept and can be replayed (TR-OPS-04).
        return Outcome(
            "ignored", f"{event.event_type} handling arrives with the inbox", routed.workspace_id
        )


HANDLERS: dict[str, Handler] = {
    WebhookProvider.CLERK: _clerk,
    WebhookProvider.INSTAGRAM: _instagram,
}


async def process_event(
    sessionmaker: async_sessionmaker[AsyncSession], event_id: uuid.UUID
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
        await session.commit()
        return status
