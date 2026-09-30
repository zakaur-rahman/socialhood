"""Workspace deletion rows (T9.6; FR-ACC-05, F-16, §5.9).

Marking: the workspace goes to ``deleting`` (who and when), its accounts lose their tokens at once
and stop routing webhooks (routing ignores disconnected accounts), and its scheduled work and
queued emails stop. These run in the workspace's scope, like any tenant write.

Purging: every table that holds the workspace's rows is emptied in batches, children before
parents, so each statement is short and a purge that stops half-way resumes where it was. The
tables come from the TenantScoped registry (db/tenancy.py) plus any other table with a
``workspace_id`` foreign key to workspaces, so a new tenant table is purged without a change here.
These deletes name the workspace explicitly (the purge job runs outside any request).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Table, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import socialhood.models  # noqa: F401  (registers every table before the registry is read)
from socialhood.db.base import Base
from socialhood.db.tenancy import _tenant_tables
from socialhood.models.billing import Subscription
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.identity import Workspace, WorkspaceStatus
from socialhood.models.inbox import ScheduledMessage, ScheduledStatus
from socialhood.models.notifications import EmailDelivery, EmailStatus
from socialhood.models.platform import WebhookEvent
from socialhood.models.publishing import (
    ScheduledPost,
    ScheduledPostStatus,
    ScheduledPostTarget,
    TargetStatus,
)
from socialhood.repositories.base import scoped_update

WORKSPACE_DELETED = "The workspace was deleted."


# ---------------------------------------------------------------- marking (in the workspace scope)


async def mark_deleting(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    requested_by: uuid.UUID | None,
    at: datetime,
) -> bool:
    """active -> deleting; False when the workspace isn't active (gone, or already deleting)."""
    result = await session.execute(
        update(Workspace)
        .where(Workspace.id == workspace_id, Workspace.status == WorkspaceStatus.ACTIVE)
        .values(
            status=WorkspaceStatus.DELETING,
            deletion_requested_at=at,
            deletion_requested_by_user_id=requested_by,
        )
        .returning(Workspace.id)
    )
    return result.scalar_one_or_none() is not None


async def disconnect_accounts(session: AsyncSession, *, at: datetime) -> list[uuid.UUID]:
    """Destroy every account's tokens now and mark it disconnected (FR-ACC-05); returns the ids."""
    result = await session.execute(
        scoped_update(SocialAccount)
        .values(
            access_token_enc=None,
            whatsapp_pin_enc=None,
            status=AccountStatus.DISCONNECTED,
            disconnected_at=func.coalesce(SocialAccount.disconnected_at, at),
            last_error=None,
        )
        .returning(SocialAccount.id)
    )
    return list(result.scalars().all())


async def stop_scheduled_work(session: AsyncSession) -> dict[str, int]:
    """Scheduled messages and posts that haven't started are cancelled, so no dispatcher picks
    them up before the purge; queued emails are skipped."""
    messages = await session.execute(
        scoped_update(ScheduledMessage, status=ScheduledStatus.SCHEDULED)
        .values(status=ScheduledStatus.CANCELED)
        .returning(ScheduledMessage.id)
    )
    targets = await session.execute(
        scoped_update(ScheduledPostTarget, status=TargetStatus.PENDING)
        .values(status=TargetStatus.CANCELED)
        .returning(ScheduledPostTarget.id)
    )
    posts = await session.execute(
        scoped_update(ScheduledPost, status=ScheduledPostStatus.SCHEDULED)
        .values(status=ScheduledPostStatus.CANCELED)
        .returning(ScheduledPost.id)
    )
    emails = await session.execute(
        scoped_update(EmailDelivery, status=EmailStatus.QUEUED)
        .values(status=EmailStatus.SKIPPED, error=WORKSPACE_DELETED)
        .returning(EmailDelivery.id)
    )
    return {
        "scheduled_messages": len(messages.all()),
        "post_targets": len(targets.all()),
        "scheduled_posts": len(posts.all()),
        "emails": len(emails.all()),
    }


# ---------------------------------------------------------------- the purge (across workspaces)


def _references_workspaces(table: Table) -> bool:
    return any(
        fk.parent.name == "workspace_id" and fk.column.table.name == Workspace.__tablename__
        for fk in table.foreign_keys
    )


def workspace_tables() -> list[Table]:
    """Every table holding a workspace's rows, children before parents (reverse dependency
    order), so a restrictive foreign key never blocks a delete and cascades find nothing left."""
    registry = _tenant_tables()
    return [
        table
        for table in reversed(Base.metadata.sorted_tables)
        if table in registry or _references_workspaces(table)
    ]


# Kept until Dodo has confirmed the subscription is cancelled (C-052): deleted with the workspace.
BILLING_TABLES = frozenset({Subscription.__tablename__})


async def deleting_workspaces(session: AsyncSession) -> list[tuple[uuid.UUID, datetime | None]]:
    """Workspaces waiting to be purged, oldest request first (workspaces aren't tenant rows)."""
    result = await session.execute(
        select(Workspace.id, Workspace.deletion_requested_at)
        .where(Workspace.status == WorkspaceStatus.DELETING)
        .order_by(Workspace.deletion_requested_at.nulls_first(), Workspace.id)
    )
    return [(row[0], row[1]) for row in result.all()]


async def workspace_status(session: AsyncSession, workspace_id: uuid.UUID) -> str | None:
    status: str | None = await session.scalar(
        select(Workspace.status).where(Workspace.id == workspace_id)
    )
    return status


async def account_ids(session: AsyncSession, workspace_id: uuid.UUID) -> list[uuid.UUID]:
    result = await session.scalars(
        select(SocialAccount.id).where(SocialAccount.workspace_id == workspace_id)
    )
    return list(result.all())


async def delete_batch(
    session: AsyncSession, table: Table, workspace_id: uuid.UUID, limit: int
) -> int:
    """Delete up to ``limit`` of the workspace's rows from ``table``; returns how many went."""
    batch = select(table.c.id).where(table.c.workspace_id == workspace_id).limit(limit)
    result = await session.execute(delete(table).where(table.c.id.in_(batch)).returning(table.c.id))
    return len(result.all())


async def delete_webhook_events(session: AsyncSession, workspace_id: uuid.UUID, limit: int) -> int:
    """Stored webhook payloads routed to the workspace (not a tenant table: a plain column)."""
    batch = select(WebhookEvent.id).where(WebhookEvent.workspace_id == workspace_id).limit(limit)
    result = await session.execute(
        delete(WebhookEvent)
        .where(WebhookEvent.id.in_(batch))
        .returning(WebhookEvent.id)
        .execution_options(synchronize_session=False)
    )
    return len(result.all())


async def delete_workspace(session: AsyncSession, workspace_id: uuid.UUID) -> bool:
    """The last step: the workspace row itself (only one still deleting)."""
    result = await session.execute(
        delete(Workspace)
        .where(Workspace.id == workspace_id, Workspace.status == WorkspaceStatus.DELETING)
        .returning(Workspace.id)
        .execution_options(synchronize_session=False)
    )
    return result.scalar_one_or_none() is not None
