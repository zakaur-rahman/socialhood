"""The email outbox (email_deliveries; T8.5, T8.7). Reads and writes run in the current
workspace's scope, except the sweeper's, which jobs/ runs across workspaces."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.notifications import EmailDelivery, EmailStatus, Notification
from socialhood.repositories.base import scoped_update


async def insert_queued(session: AsyncSession, values: Mapping[str, Any]) -> uuid.UUID | None:
    """A queued row, unless (workspace, dedupe_key) exists: then None."""
    statement = (
        insert(EmailDelivery)
        .values({**values, "workspace_id": require_workspace()})
        .on_conflict_do_nothing(
            index_elements=[EmailDelivery.workspace_id, EmailDelivery.dedupe_key]
        )
        .returning(EmailDelivery.id)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def lock_for_send(session: AsyncSession, delivery_id: uuid.UUID) -> EmailDelivery | None:
    """The row, locked for this transaction; None when missing or another sender holds it."""
    return (
        await session.scalars(
            select(EmailDelivery)
            .where(EmailDelivery.id == delivery_id)
            .with_for_update(skip_locked=True)
        )
    ).one_or_none()


async def get(session: AsyncSession, delivery_id: uuid.UUID) -> EmailDelivery | None:
    return (
        await session.scalars(select(EmailDelivery).where(EmailDelivery.id == delivery_id))
    ).one_or_none()


async def mark_notification_emailed(
    session: AsyncSession, notification_id: uuid.UUID, at: datetime
) -> None:
    await session.execute(
        scoped_update(Notification, id=notification_id)
        .where(Notification.emailed_at.is_(None))
        .values(emailed_at=at)
    )


# ---------------------------------------------------------------- the sweeper (across workspaces)


async def queued_between(
    session: AsyncSession, *, created_after: datetime, created_before: datetime, limit: int
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(id, workspace_id) of rows still queued, created in the span, oldest first."""
    rows = await session.execute(
        select(EmailDelivery.id, EmailDelivery.workspace_id)
        .where(
            EmailDelivery.status == EmailStatus.QUEUED,
            EmailDelivery.created_at > created_after,
            EmailDelivery.created_at < created_before,
        )
        .order_by(EmailDelivery.created_at)
        .limit(limit)
    )
    return [(row.id, row.workspace_id) for row in rows]


async def expire_queued(session: AsyncSession, *, created_before: datetime, error: str) -> int:
    """Rows still queued long after they were created: failed, never sent late."""
    result = await session.execute(
        update(EmailDelivery)
        .where(
            EmailDelivery.status == EmailStatus.QUEUED,
            EmailDelivery.created_at < created_before,
        )
        .values(status=EmailStatus.FAILED, error=error)
        .returning(EmailDelivery.id)
    )
    return len(result.all())
