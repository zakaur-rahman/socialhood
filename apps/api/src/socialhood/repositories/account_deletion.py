"""Account data deletion rows (C-067; FR-CON-06, F-16).

Marking (in the workspace's scope, like any tenant write): the account is disconnected (its tokens
destroyed) and records who asked and when; its scheduled messages and pending post targets are
cancelled, so nothing goes out for it before the purge.

Purging: every table holding the account's rows is emptied in batches, children before parents,
so each statement is short and a purge that stops half-way resumes where it was. The tables come
from the schema, not a list: those reachable from social_accounts through ON DELETE CASCADE
foreign keys, which is exactly what deleting the account row would take with it
(``account_tables``). A row is the account's when one of those foreign keys names the account or
one of the account's rows (``owned_by``). A new table joins the purge by having such a key;
tests/unit/test_account_purge_tables.py fails for an account column without one.

The deletes name the workspace and the account explicitly (the purge job runs outside any
request), so no other account's or workspace's rows can match.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from typing import Any

from sqlalchemy import (
    Column,
    ColumnElement,
    Select,
    Table,
    Text,
    cast,
    delete,
    exists,
    func,
    not_,
    or_,
    select,
    true,
    union,
)
from sqlalchemy.ext.asyncio import AsyncSession

import socialhood.models  # noqa: F401  (registers every table before the schema is read)
from socialhood.db.base import Base
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.inbox import Conversation, ScheduledMessage, ScheduledStatus
from socialhood.models.media import AssetPurpose, MediaAsset
from socialhood.models.platform import WebhookEvent
from socialhood.models.publishing import (
    ScheduledPost,
    ScheduledPostStatus,
    ScheduledPostTarget,
    TargetStatus,
)
from socialhood.repositories.base import scoped_delete, scoped_update

ACCOUNTS: Table = SocialAccount.__table__  # type: ignore[assignment]
MESSAGES: Table = Base.metadata.tables["messages"]
SCHEDULED_MESSAGES: Table = Base.metadata.tables["scheduled_messages"]
ASSETS: Table = MediaAsset.__table__  # type: ignore[assignment]

# Files a message owns: uploaded to send in a message, or copied from one (TR-MED-03). Library
# uploads (posts) and knowledge files are the workspace's and are never deleted here.
MESSAGE_FILE_PURPOSES = (AssetPurpose.MESSAGE, AssetPurpose.INBOUND)


# ---------------------------------------------------------------- the tables, from the schema


def _cascades(column: Column[Any], parent: Table) -> bool:
    return any(
        fk.column.table is parent and (fk.ondelete or "").upper() == "CASCADE"
        for fk in column.foreign_keys
    )


@cache
def _owned_names() -> frozenset[str]:
    """Every table whose rows go when an account row is deleted (the cascade's closure)."""
    owned: set[str] = set()
    parents = {ACCOUNTS.name}
    changed = True
    while changed:
        changed = False
        for table in Base.metadata.sorted_tables:
            if table.name in owned or table is ACCOUNTS:
                continue
            if any(
                (fk.ondelete or "").upper() == "CASCADE" and fk.column.table.name in parents
                for fk in table.foreign_keys
            ):
                owned.add(table.name)
                parents.add(table.name)
                changed = True
    return frozenset(owned)


def account_tables() -> list[Table]:
    """Every table holding an account's rows, children before parents (reverse dependency
    order), so no foreign key refuses a delete and the cascades find nothing left. The account
    row itself is not among them: it goes last."""
    owned = _owned_names()
    return [table for table in reversed(Base.metadata.sorted_tables) if table.name in owned]


def owner_links(table: Table) -> list[tuple[Column[Any], Table]]:
    """The cascading foreign keys that make ``table``'s rows the account's: to social_accounts
    itself when the table has one (the others then lead to the same account), else to each
    owned parent."""
    owned = _owned_names()
    direct: list[tuple[Column[Any], Table]] = []
    through: list[tuple[Column[Any], Table]] = []
    for column in table.columns:
        for fk in column.foreign_keys:
            parent = fk.column.table
            if not _cascades(column, parent):
                continue
            if parent is ACCOUNTS:
                direct.append((column, parent))
            elif parent.name in owned:
                through.append((column, parent))
    return direct or through


def owned_by(table: Table, account_id: uuid.UUID, workspace_id: uuid.UUID) -> ColumnElement[bool]:
    """``table``'s rows that belong to the account (see the module docstring)."""
    clauses: list[ColumnElement[bool]] = []
    for column, parent in owner_links(table):
        if parent is ACCOUNTS:
            clauses.append(column == account_id)
        else:
            parents = select(parent.c.id).where(
                parent.c.workspace_id == workspace_id, owned_by(parent, account_id, workspace_id)
            )
            clauses.append(column.in_(parents))
    return or_(*clauses)


async def delete_batch(
    session: AsyncSession,
    table: Table,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    limit: int,
) -> int:
    """Delete up to ``limit`` of the account's rows from ``table``; returns how many went."""
    batch = (
        select(table.c.id)
        .where(table.c.workspace_id == workspace_id, owned_by(table, account_id, workspace_id))
        .limit(limit)
    )
    result = await session.execute(delete(table).where(table.c.id.in_(batch)).returning(table.c.id))
    return len(result.all())


# ---------------------------------------------------------------- marking (workspace scope)


async def mark_deleting(
    session: AsyncSession,
    account_id: uuid.UUID,
    *,
    requested_by: uuid.UUID | None,
    at: datetime,
) -> bool:
    """Disconnect the account (tokens destroyed now) and mark it deleting; the first request's
    time is kept. False when it isn't in this workspace."""
    result = await session.execute(
        scoped_update(SocialAccount, id=account_id)
        .values(
            access_token_enc=None,
            whatsapp_pin_enc=None,
            status=AccountStatus.DISCONNECTED,
            disconnected_at=func.coalesce(SocialAccount.disconnected_at, at),
            last_error=None,
            deletion_requested_at=func.coalesce(SocialAccount.deletion_requested_at, at),
            deletion_requested_by_user_id=func.coalesce(
                SocialAccount.deletion_requested_by_user_id, requested_by
            ),
        )
        .returning(SocialAccount.id)
    )
    return result.scalar_one_or_none() is not None


async def cancel_scheduled_messages(session: AsyncSession, account_id: uuid.UUID) -> int:
    """Scheduled messages in the account's conversations that haven't started."""
    conversations = select(Conversation.id).where(Conversation.social_account_id == account_id)
    result = await session.execute(
        scoped_update(ScheduledMessage, status=ScheduledStatus.SCHEDULED)
        .where(ScheduledMessage.conversation_id.in_(conversations))
        .values(status=ScheduledStatus.CANCELED)
        .returning(ScheduledMessage.id)
    )
    return len(result.all())


async def cancel_pending_targets(session: AsyncSession, account_id: uuid.UUID) -> list[uuid.UUID]:
    """The account's post targets that haven't started; returns their posts' ids."""
    result = await session.execute(
        scoped_update(
            ScheduledPostTarget, social_account_id=account_id, status=TargetStatus.PENDING
        )
        .values(status=TargetStatus.CANCELED)
        .returning(ScheduledPostTarget.scheduled_post_id)
    )
    return sorted(set(result.scalars().all()))


# ---------------------------------------------------------------- files the messages own


@dataclass(frozen=True)
class OwnedFile:
    asset_id: uuid.UUID
    public_id: str
    resource_type: str


def _attachment_refs(workspace_id: uuid.UUID) -> tuple[Select[Any], ColumnElement[str]]:
    """``SELECT <asset id> FROM messages, jsonb_array_elements(attachments)``: one row per
    attachment that names a stored asset; the caller adds which messages."""
    element = func.jsonb_array_elements(MESSAGES.c.attachments).table_valued(
        "value", joins_implicitly=True
    )
    ref = element.c.value.op("->>", return_type=Text)("asset_id")
    query = (
        select(ref)
        .select_from(MESSAGES)
        .join(element, true())
        .where(MESSAGES.c.workspace_id == workspace_id, ref.is_not(None))
    )
    return query, ref


async def message_files(
    session: AsyncSession, workspace_id: uuid.UUID, account_id: uuid.UUID
) -> list[OwnedFile]:
    """Stored files named by the account's messages or scheduled messages (attachments, and
    copies of inbound media), whatever else names them: ``shared_files`` says which to keep."""
    attachments, _ = _attachment_refs(workspace_id)
    named = union(
        attachments.where(owned_by(MESSAGES, account_id, workspace_id)),
        select(cast(func.unnest(SCHEDULED_MESSAGES.c.attachment_asset_ids), Text)).where(
            SCHEDULED_MESSAGES.c.workspace_id == workspace_id,
            owned_by(SCHEDULED_MESSAGES, account_id, workspace_id),
        ),
    ).subquery()
    rows = await session.execute(
        select(ASSETS.c.id, ASSETS.c.public_id, ASSETS.c.resource_type)
        .where(
            ASSETS.c.workspace_id == workspace_id,
            ASSETS.c.purpose.in_(MESSAGE_FILE_PURPOSES),
            cast(ASSETS.c.id, Text).in_(select(named.c[0])),
        )
        .order_by(ASSETS.c.id)
    )
    return [OwnedFile(asset_id=r[0], public_id=r[1], resource_type=r[2]) for r in rows.all()]


async def shared_files(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    asset_ids: Sequence[uuid.UUID],
) -> set[uuid.UUID]:
    """Of ``asset_ids``, those something outside the account still names: another account's
    message or scheduled message, or any row with a foreign key to media_assets that isn't the
    account's (a post in the library, a knowledge file, another account's automation)."""
    if not asset_ids:
        return set()
    ids = list(asset_ids)
    texts = [str(i) for i in ids]
    attachments, ref = _attachment_refs(workspace_id)
    queries: list[Select[Any]] = [
        attachments.where(not_(owned_by(MESSAGES, account_id, workspace_id)), ref.in_(texts)),
        select(cast(func.unnest(SCHEDULED_MESSAGES.c.attachment_asset_ids), Text)).where(
            SCHEDULED_MESSAGES.c.workspace_id == workspace_id,
            not_(owned_by(SCHEDULED_MESSAGES, account_id, workspace_id)),
            SCHEDULED_MESSAGES.c.attachment_asset_ids.overlap(ids),
        ),
    ]
    owned = _owned_names()
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if not any(fk.column.table is ASSETS for fk in column.foreign_keys):
                continue
            where: list[ColumnElement[bool]] = [column.in_(ids)]
            if "workspace_id" in table.c:
                where.append(table.c.workspace_id == workspace_id)
            if table.name in owned:
                where.append(not_(owned_by(table, account_id, workspace_id)))
            queries.append(select(cast(column, Text)).where(*where))
    rows = await session.execute(union(*queries))
    return {uuid.UUID(str(row[0])) for row in rows.all() if row[0]}


async def delete_assets(
    session: AsyncSession, workspace_id: uuid.UUID, asset_ids: Sequence[uuid.UUID]
) -> int:
    if not asset_ids:
        return 0
    result = await session.execute(
        delete(ASSETS)
        .where(ASSETS.c.workspace_id == workspace_id, ASSETS.c.id.in_(list(asset_ids)))
        .returning(ASSETS.c.id)
    )
    return len(result.all())


# ---------------------------------------------------------------- the rest of the purge


async def delete_webhook_events(
    session: AsyncSession, workspace_id: uuid.UUID, platform_account_id: str, limit: int
) -> int:
    """Stored webhook payloads routed to this workspace for the account (not a tenant table)."""
    batch = (
        select(WebhookEvent.id)
        .where(
            WebhookEvent.workspace_id == workspace_id,
            WebhookEvent.platform_account_id == platform_account_id,
        )
        .limit(limit)
    )
    result = await session.execute(
        delete(WebhookEvent)
        .where(WebhookEvent.id.in_(batch))
        .returning(WebhookEvent.id)
        .execution_options(synchronize_session=False)
    )
    return len(result.all())


PUBLISHED = (ScheduledPostStatus.PUBLISHED, ScheduledPostStatus.PARTIALLY_PUBLISHED)
UNFINISHED = (ScheduledPostStatus.SCHEDULED, ScheduledPostStatus.PUBLISHING)


async def settle_posts_without_accounts(session: AsyncSession) -> dict[str, int]:
    """Scheduled posts whose only accounts were deleted (a post past draft always had one): one
    that published there goes with that account's posts; one still waiting or publishing is
    canceled (F-13: every target canceled). Drafts keep their caption and media."""
    no_target = ~exists().where(ScheduledPostTarget.scheduled_post_id == ScheduledPost.id)
    published = await session.execute(
        scoped_delete(ScheduledPost)
        .where(ScheduledPost.status.in_(PUBLISHED), no_target)
        .returning(ScheduledPost.id)
        .execution_options(synchronize_session=False)
    )
    canceled = await session.execute(
        scoped_update(ScheduledPost)
        .where(ScheduledPost.status.in_(UNFINISHED), no_target)
        .values(status=ScheduledPostStatus.CANCELED)
        .returning(ScheduledPost.id)
        .execution_options(synchronize_session=False)
    )
    return {"posts_deleted": len(published.all()), "posts_canceled": len(canceled.all())}


async def delete_account(
    session: AsyncSession, workspace_id: uuid.UUID, account_id: uuid.UUID
) -> bool:
    """The last step: the account row itself (only one being deleted). Its cascade takes any row
    written since the batches ran."""
    result = await session.execute(
        delete(ACCOUNTS)
        .where(
            ACCOUNTS.c.id == account_id,
            ACCOUNTS.c.workspace_id == workspace_id,
            ACCOUNTS.c.deletion_requested_at.is_not(None),
        )
        .returning(ACCOUNTS.c.id)
    )
    return result.scalar_one_or_none() is not None


async def deleting_accounts(
    session: AsyncSession,
) -> list[tuple[uuid.UUID, uuid.UUID, datetime]]:
    """(account, workspace, requested at) of every account being deleted, oldest first. Across
    workspaces: the caller (the sweeper, in jobs/) runs it in the tenant bypass."""
    result = await session.execute(
        select(SocialAccount.id, SocialAccount.workspace_id, SocialAccount.deletion_requested_at)
        .where(SocialAccount.deletion_requested_at.is_not(None))
        .order_by(SocialAccount.deletion_requested_at, SocialAccount.id)
    )
    return [(row[0], row[1], row[2]) for row in result.all() if row[2] is not None]
