"""Stored webhook events (TR-WH-03, TR-WH-05). Not tenant-scoped."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, NamedTuple

from sqlalchemy import delete, select, update
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
    occurred_at: datetime | None = None,
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
            occurred_at=occurred_at,
        )
        .on_conflict_do_nothing(index_elements=[WebhookEvent.provider, WebhookEvent.dedupe_key])
        .returning(WebhookEvent.id)
    )
    return (await session.execute(statement)).scalar_one_or_none()


class Claim(NamedTuple):
    event: WebhookEvent
    attempt: int


async def claim(session: AsyncSession, event_id: uuid.UUID) -> Claim | None:
    """Lock an event that still needs work, or return None (done, taken, or out of attempts).

    The row lock lasts for the caller's transaction, so a worker that dies mid-way leaves the row
    ``received`` for the sweep; ``processing`` is never committed.
    """
    statement = (
        select(WebhookEvent)
        .where(
            WebhookEvent.id == event_id,
            WebhookEvent.status == WebhookStatus.RECEIVED,
            WebhookEvent.attempts < MAX_ATTEMPTS,
        )
        .with_for_update(skip_locked=True)
    )
    event = (await session.scalars(statement)).one_or_none()
    return None if event is None else Claim(event, event.attempts + 1)


async def record_failure(
    session: AsyncSession, event_id: uuid.UUID, *, attempt: int, error: str, final: bool
) -> None:
    """TR-JOB-04: back to ``received`` while retries remain; ``failed`` only on the last one."""
    await session.execute(
        update(WebhookEvent)
        .where(WebhookEvent.id == event_id)
        .values(
            status=WebhookStatus.FAILED if final else WebhookStatus.RECEIVED,
            attempts=attempt,
            last_error=error,
        )
    )


async def finish(
    session: AsyncSession,
    event_id: uuid.UUID,
    status: WebhookStatus,
    *,
    error: str | None = None,
    workspace_id: uuid.UUID | None = None,
    attempts: int | None = None,
) -> None:
    values: dict[str, Any] = {"status": status, "last_error": error}
    if attempts is not None:
        values["attempts"] = attempts
    if status in (WebhookStatus.PROCESSED, WebhookStatus.IGNORED):
        values["processed_at"] = datetime.now(UTC)
    if workspace_id is not None:
        values["workspace_id"] = workspace_id
    await session.execute(update(WebhookEvent).where(WebhookEvent.id == event_id).values(**values))


async def stuck_received(
    session: AsyncSession, before: datetime, limit: int = 1000
) -> list[uuid.UUID]:
    """Events still waiting after the grace period: their enqueue was probably lost."""
    result = await session.scalars(
        select(WebhookEvent.id)
        .where(WebhookEvent.status == WebhookStatus.RECEIVED, WebhookEvent.received_at < before)
        .order_by(WebhookEvent.received_at)
        .limit(limit)
    )
    return list(result.all())


async def list_failed(
    session: AsyncSession,
    *,
    ids: list[uuid.UUID] | None = None,
    provider: str | None = None,
    since: datetime | None = None,
    error_contains: str | None = None,
    limit: int = 500,
) -> list[WebhookEvent]:
    """The dead-letter set (TR-OPS-04), newest first."""
    statement = select(WebhookEvent).where(WebhookEvent.status == WebhookStatus.FAILED)
    if ids:
        statement = statement.where(WebhookEvent.id.in_(ids))
    if provider:
        statement = statement.where(WebhookEvent.provider == provider)
    if since is not None:
        statement = statement.where(WebhookEvent.received_at >= since)
    if error_contains:
        statement = statement.where(WebhookEvent.last_error.icontains(error_contains))
    statement = statement.order_by(WebhookEvent.received_at.desc()).limit(limit)
    return list((await session.scalars(statement)).all())


async def delete_for_account(session: AsyncSession, platform_account_id: str) -> None:
    await session.execute(
        delete(WebhookEvent).where(WebhookEvent.platform_account_id == platform_account_id)
    )


async def reset_for_replay(session: AsyncSession, event_ids: list[uuid.UUID]) -> int:
    """TR-OPS-04: back to ``received`` with attempts reset, so the pipeline processes them again."""
    result = await session.execute(
        update(WebhookEvent)
        .where(WebhookEvent.id.in_(event_ids), WebhookEvent.status == WebhookStatus.FAILED)
        .values(status=WebhookStatus.RECEIVED, attempts=0, last_error=None)
    )
    return int(result.rowcount)  # type: ignore[attr-defined]
