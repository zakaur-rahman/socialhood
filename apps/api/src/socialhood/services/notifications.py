"""Notifications (FR-NOT-01…03): in-app rows, and the email and push they lead to (T8.5, T8.6).

Producers pass only the type and the words (``notify_admins`` for the owners and admins,
``notify_members`` for everyone who answers conversations); this module decides the channels,
per recipient (C-049):

- ``in_app``: always (FR-NOT-01).
- ``email``: types in EMAIL_TYPES (account needs reconnecting, payment problem, plan activated,
  plan downgraded, post failed), to owners and admins only, whoever the notification went to:
  account, billing and publishing are theirs to fix. Not optional (FR-NOT-02).
- ``push``: types in PUSH_EVENT_OF_TYPE (Needs you, new lead, window closing, account needs
  reconnecting or disconnected), when the member's switch for that event is on (FR-NOT-03).

In the same transaction each new notification with ``email`` queues its email in the outbox
(dedupe ``notification:{id}``), and one with ``push`` records deliver_push when the member has an
enabled device; both jobs are deferred when the caller commits (notify/dispatch.py), so a
notification that rolls back sends nothing. A repeated dedupe_key inserts nothing and so sends
nothing again.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.identity import Role, User, Workspace, WorkspaceMember
from socialhood.models.notifications import (
    EMAIL_TYPES,
    PUSH_EVENT_OF_TYPE,
    Notification,
    NotificationChannel,
)
from socialhood.notify import dispatch, preferences
from socialhood.notify.outbox import queue_email
from socialhood.repositories import push_subscriptions
from socialhood.repositories.base import scoped_update

ADMIN_ROLES = frozenset({Role.OWNER, Role.ADMIN})
EMAIL_ROLES = ADMIN_ROLES  # who receives the FR-NOT-02 emails


def channels_for(
    type: str, *, role: str, prefs: Mapping[str, Any] | None, has_email: bool = True
) -> list[str]:
    """The channels of one recipient's notification of ``type``."""
    channels = [NotificationChannel.IN_APP.value]
    if type in EMAIL_TYPES and role in EMAIL_ROLES and has_email:
        channels.append(NotificationChannel.EMAIL.value)
    event = PUSH_EVENT_OF_TYPE.get(type)
    if event is not None and preferences.pushes(prefs, event):
        channels.append(NotificationChannel.PUSH.value)
    return channels


async def notify_admins(
    session: AsyncSession,
    *,
    type: str,
    severity: str,
    title: str,
    body: str,
    link: str | None = None,
    dedupe_key: str | None = None,
    data: Mapping[str, Any] | None = None,
) -> int:
    """Notify the current workspace's owners and admins; a repeated dedupe_key is a no-op.
    Returns the number of notifications created. ``data`` adds fields to the email's data."""
    return await _notify(
        session,
        roles=ADMIN_ROLES,
        type=type,
        severity=severity,
        title=title,
        body=body,
        link=link,
        dedupe_key=dedupe_key,
        data=data,
    )


async def notify_members(
    session: AsyncSession,
    *,
    type: str,
    severity: str,
    title: str,
    body: str,
    link: str | None = None,
    dedupe_key: str | None = None,
    data: Mapping[str, Any] | None = None,
) -> int:
    """Notify every member of the current workspace (inbox events anyone answering
    conversations needs, e.g. a closing reply window, F-18, or a new lead); a repeated
    dedupe_key is a no-op."""
    return await _notify(
        session,
        roles=None,
        type=type,
        severity=severity,
        title=title,
        body=body,
        link=link,
        dedupe_key=dedupe_key,
        data=data,
    )


async def _notify(
    session: AsyncSession,
    *,
    roles: frozenset[Role] | None,
    type: str,
    severity: str,
    title: str,
    body: str,
    link: str | None,
    dedupe_key: str | None,
    data: Mapping[str, Any] | None,
) -> int:
    workspace_id = require_workspace()
    query = select(
        WorkspaceMember.user_id,
        WorkspaceMember.role,
        WorkspaceMember.notification_prefs,
        User.email,
    ).join(User, User.id == WorkspaceMember.user_id)
    if roles is not None:
        query = query.where(WorkspaceMember.role.in_(roles))
    recipients = {row.user_id: row for row in (await session.execute(query)).all()}
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
                    "channels": channels_for(
                        type,
                        role=row.role,
                        prefs=row.notification_prefs,
                        has_email=bool(row.email),
                    ),
                }
                for user_id, row in recipients.items()
            ]
        )
        .on_conflict_do_nothing(
            index_elements=[Notification.user_id, Notification.dedupe_key],
            index_where=text("dedupe_key IS NOT NULL"),
        )
        .returning(Notification.id, Notification.user_id, Notification.channels)
    )
    created = (await session.execute(statement)).all()
    await _deliver(
        session,
        workspace_id,
        created,
        recipients=recipients,
        email_data={"title": title, "body": body, "link": link, **(data or {})},
        type=type,
    )
    return len(created)


async def _deliver(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    created: Sequence[Any],
    *,
    recipients: Mapping[uuid.UUID, Any],
    email_data: dict[str, Any],
    type: str,
) -> None:
    """Queue the email and record the push of each new notification (sent after commit)."""
    emailed = [row for row in created if NotificationChannel.EMAIL in row.channels]
    pushed = [row for row in created if NotificationChannel.PUSH in row.channels]
    if emailed:
        workspace = await session.get(Workspace, workspace_id)
        data = {
            **email_data,
            "workspace_name": workspace.name if workspace else "",
            "workspace_slug": workspace.slug if workspace else "",
        }
        for row in emailed:
            await queue_email(
                session,
                template=type,
                to_email=recipients[row.user_id].email,
                dedupe_key=f"notification:{row.id}",
                data=data,
                user_id=row.user_id,
                notification_id=row.id,
            )
    if pushed:
        with_devices = await push_subscriptions.users_with_devices(
            session, {row.user_id for row in pushed}
        )
        for row in pushed:
            if row.user_id in with_devices:
                dispatch.after_commit(session, "deliver_push", row.id, workspace_id)


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
