"""In-app notifications (FR-NOT-01). Email and push channels arrive in P8 (T8.5, T8.6)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.identity import Role, WorkspaceMember
from socialhood.models.notifications import Notification
from socialhood.repositories.base import scoped_update


async def notify_admins(
    session: AsyncSession,
    *,
    type: str,
    severity: str,
    title: str,
    body: str,
    link: str | None = None,
    dedupe_key: str | None = None,
) -> int:
    """Notify the current workspace's owners and admins; a repeated dedupe_key is a no-op."""
    workspace_id = require_workspace()
    recipients = (
        await session.scalars(
            select(WorkspaceMember.user_id).where(
                WorkspaceMember.role.in_([Role.OWNER, Role.ADMIN])
            )
        )
    ).all()
    if not recipients:
        return 0
    statement = (
        insert(Notification)
        .values(
            [
                {
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                    "type": type,
                    "severity": severity,
                    "title": title,
                    "body": body,
                    "link": link,
                    "dedupe_key": dedupe_key,
                }
                for user_id in recipients
            ]
        )
        .on_conflict_do_nothing(
            index_elements=[Notification.user_id, Notification.dedupe_key],
            index_where=text("dedupe_key IS NOT NULL"),
        )
        .returning(Notification.id)
    )
    return len((await session.execute(statement)).all())


async def notify_members(
    session: AsyncSession,
    *,
    type: str,
    severity: str,
    title: str,
    body: str,
    link: str | None = None,
    dedupe_key: str | None = None,
    channels: tuple[str, ...] = ("in_app",),
) -> int:
    """Notify every member of the current workspace (inbox events anyone answering conversations
    needs, e.g. a closing reply window, F-18); a repeated dedupe_key is a no-op. ``push`` in
    ``channels`` marks it for push delivery (T8.6)."""
    workspace_id = require_workspace()
    recipients = (await session.scalars(select(WorkspaceMember.user_id))).all()
    if not recipients:
        return 0
    statement = (
        insert(Notification)
        .values(
            [
                {
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                    "type": type,
                    "severity": severity,
                    "title": title,
                    "body": body,
                    "link": link,
                    "dedupe_key": dedupe_key,
                    "channels": list(channels),
                }
                for user_id in recipients
            ]
        )
        .on_conflict_do_nothing(
            index_elements=[Notification.user_id, Notification.dedupe_key],
            index_where=text("dedupe_key IS NOT NULL"),
        )
        .returning(Notification.id)
    )
    return len((await session.execute(statement)).all())


async def list_for(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int, before: datetime | None
) -> tuple[list[Notification], int]:
    query = select(Notification).where(Notification.user_id == user_id)
    if before is not None:
        query = query.where(Notification.created_at < before)
    items = list(
        (
            await session.scalars(query.order_by(Notification.created_at.desc()).limit(limit + 1))
        ).all()
    )
    unread = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return items, int(unread or 0)


async def mark_read(session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID] | None) -> None:
    statement = scoped_update(Notification, user_id=user_id).where(Notification.read_at.is_(None))
    if ids is not None:
        statement = statement.where(Notification.id.in_(ids))
    await session.execute(statement.values(read_at=datetime.now(UTC)))
