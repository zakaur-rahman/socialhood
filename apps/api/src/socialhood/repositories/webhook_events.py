"""Stored webhook events (TR-WH-03, TR-WH-05). Not tenant-scoped."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.platform import WebhookEvent, WebhookStatus

MAX_ATTEMPTS = 5


async def store(
    session: AsyncSession,
    *,
    provider: str,
    dedupe_key: str,
    event_type: str,
    payload: dict[str, Any],
    platform_account_id: str | None = None,
) -> uuid.UUID | None:
    """Insert once per (provider, dedupe_key); return the new id, or None for a re-delivery."""
    statement = (
        insert(WebhookEvent)
        .values(
            provider=provider,
            dedupe_key=dedupe_key,
            event_type=event_type,
            payload=payload,
            platform_account_id=platform_account_id,
        )
        .on_conflict_do_nothing(index_elements=[WebhookEvent.provider, WebhookEvent.dedupe_key])
        .returning(WebhookEvent.id)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def claim(session: AsyncSession, event_id: uuid.UUID) -> WebhookEvent | None:
    """Lock an event that still needs work, or return None (done, taken, or out of attempts)."""
    statement = (
        select(WebhookEvent)
        .where(
            WebhookEvent.id == event_id,
            WebhookEvent.status.in_([WebhookStatus.RECEIVED, WebhookStatus.FAILED]),
            WebhookEvent.attempts < MAX_ATTEMPTS,
        )
        .with_for_update(skip_locked=True)
    )
    event = (await session.scalars(statement)).one_or_none()
    if event is not None:
        await session.execute(
            update(WebhookEvent)
            .where(WebhookEvent.id == event_id)
            .values(status=WebhookStatus.PROCESSING, attempts=WebhookEvent.attempts + 1)
        )
    return event


async def finish(
    session: AsyncSession,
    event_id: uuid.UUID,
    status: WebhookStatus,
    *,
    error: str | None = None,
    workspace_id: uuid.UUID | None = None,
) -> None:
    values: dict[str, Any] = {"status": status, "last_error": error}
    if status in (WebhookStatus.PROCESSED, WebhookStatus.IGNORED):
        values["processed_at"] = datetime.now(UTC)
    if workspace_id is not None:
        values["workspace_id"] = workspace_id
    await session.execute(update(WebhookEvent).where(WebhookEvent.id == event_id).values(**values))
