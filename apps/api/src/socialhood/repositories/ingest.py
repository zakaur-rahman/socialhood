"""Writes and row locks for ingest, profiles, inbound media, sync and backfill (T3.2, T3.3,
T3.14). Tenant-scoped: reads are filtered by the session's workspace and inserts are stamped
with it, so every function runs inside ``workspace_scope``."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.inbox import Contact, Conversation, Direction, Message, MessageStatus
from socialhood.models.media import MediaAsset, MediaItem
from socialhood.platforms.base import PlatformMedia
from socialhood.repositories.base import scoped_delete

_FRESH = {"populate_existing": True}


# ---------------------------------------------------------------- contacts


async def find_contact(
    session: AsyncSession, social_account_id: uuid.UUID, platform_user_id: str
) -> Contact | None:
    return (
        await session.scalars(
            select(Contact).where(
                Contact.social_account_id == social_account_id,
                Contact.platform_user_id == platform_user_id,
            )
        )
    ).one_or_none()


async def get_or_create_contact(
    session: AsyncSession,
    *,
    social_account_id: uuid.UUID,
    platform_user_id: str,
    first_seen_at: datetime,
    display_name: str | None = None,
) -> tuple[Contact, bool]:
    """The contact for (account, platform user), inserted if new; True when this call created it.
    Concurrent first messages from one person insert once (ON CONFLICT DO NOTHING)."""
    existing = await find_contact(session, social_account_id, platform_user_id)
    if existing is not None:
        return existing, False
    statement = (
        insert(Contact)
        .values(
            workspace_id=require_workspace(),
            social_account_id=social_account_id,
            platform_user_id=platform_user_id,
            display_name=display_name,
            first_seen_at=first_seen_at,
        )
        .on_conflict_do_nothing(
            index_elements=[Contact.social_account_id, Contact.platform_user_id]
        )
        .returning(Contact)
    )
    created = (await session.scalars(statement, execution_options=_FRESH)).one_or_none()
    if created is not None:
        return created, True
    raced = await find_contact(session, social_account_id, platform_user_id)
    assert raced is not None  # the conflicting row is committed, or we would have waited on it
    return raced, False


# ---------------------------------------------------------------- conversations


async def lock_conversation(
    session: AsyncSession, conversation_id: uuid.UUID
) -> Conversation | None:
    """The conversation, locked until commit so counters are never lost to a concurrent update."""
    return (
        await session.scalars(
            select(Conversation).where(Conversation.id == conversation_id).with_for_update(),
            execution_options=_FRESH,
        )
    ).one_or_none()


async def _lock_for_contact(
    session: AsyncSession, social_account_id: uuid.UUID, contact_id: uuid.UUID
) -> Conversation | None:
    return (
        await session.scalars(
            select(Conversation)
            .where(
                Conversation.social_account_id == social_account_id,
                Conversation.contact_id == contact_id,
            )
            .with_for_update(),
            execution_options=_FRESH,
        )
    ).one_or_none()


async def get_or_create_conversation(
    session: AsyncSession,
    *,
    social_account_id: uuid.UUID,
    contact_id: uuid.UUID,
    platform: str,
) -> tuple[Conversation, bool]:
    """The (account, contact) conversation, locked; True when this call created it."""
    existing = await _lock_for_contact(session, social_account_id, contact_id)
    if existing is not None:
        return existing, False
    statement = (
        insert(Conversation)
        .values(
            workspace_id=require_workspace(),
            social_account_id=social_account_id,
            contact_id=contact_id,
            platform=platform,
        )
        .on_conflict_do_nothing(
            index_elements=[Conversation.social_account_id, Conversation.contact_id]
        )
        .returning(Conversation)
    )
    created = (await session.scalars(statement, execution_options=_FRESH)).one_or_none()
    if created is not None:
        return created, True
    raced = await _lock_for_contact(session, social_account_id, contact_id)
    assert raced is not None
    return raced, False


async def conversation_for_contact_ref(
    session: AsyncSession, social_account_id: uuid.UUID, platform_user_id: str
) -> tuple[Conversation, Contact] | None:
    contact = await find_contact(session, social_account_id, platform_user_id)
    if contact is None:
        return None
    conv = await _lock_for_contact(session, social_account_id, contact.id)
    return None if conv is None else (conv, contact)


async def conversations_for_contact(
    session: AsyncSession, contact_id: uuid.UUID
) -> list[Conversation]:
    result = await session.scalars(
        select(Conversation).where(Conversation.contact_id == contact_id)
    )
    return list(result.all())


# ---------------------------------------------------------------- messages


async def insert_message(session: AsyncSession, values: dict[str, Any]) -> Message | None:
    """Insert once per (account, platform message id); None when it is already stored."""
    statement = (
        insert(Message)
        .values(workspace_id=require_workspace(), **values)
        .on_conflict_do_nothing(
            index_elements=[Message.social_account_id, Message.platform_message_id]
        )
        .returning(Message)
    )
    return (await session.scalars(statement, execution_options=_FRESH)).one_or_none()


async def lock_message(session: AsyncSession, message_id: uuid.UUID) -> Message | None:
    return (
        await session.scalars(
            select(Message).where(Message.id == message_id).with_for_update(),
            execution_options=_FRESH,
        )
    ).one_or_none()


async def lock_message_by_platform_id(
    session: AsyncSession, social_account_id: uuid.UUID, platform_message_id: str
) -> Message | None:
    return (
        await session.scalars(
            select(Message)
            .where(
                Message.social_account_id == social_account_id,
                Message.platform_message_id == platform_message_id,
            )
            .with_for_update(),
            execution_options=_FRESH,
        )
    ).one_or_none()


OUR_SOURCES = ("human", "ai_auto", "automation")


async def own_send_for_echo(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    platform_message_id: str,
    text: str | None,
    has_attachments: bool,
    around: datetime,
    window: timedelta,
) -> Message | None:
    """The outbound message of ours an echo belongs to, if any (T3.6 / TR-JOB-05 race):
    an attachment part whose id the send job already recorded in ``attachments``, or a send
    being sent whose text matches (a text echo) or that has attachments (an attachment echo). The
    oldest in-flight send wins, since sends in a conversation go out in order."""
    part = (
        await session.scalars(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.direction == Direction.OUTBOUND,
                Message.attachments.contains([{"platform_message_id": platform_message_id}]),
            ),
            execution_options=_FRESH,
        )
    ).first()
    if part is not None:
        return part
    content = (
        Message.text == text
        if text
        else func.jsonb_array_length(Message.attachments) > 0
        if has_attachments
        else None
    )
    if content is None:
        return None
    return (
        await session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.direction == Direction.OUTBOUND,
                Message.source.in_(OUR_SOURCES),
                # Only a send already on its way can have an echo; a queued one is not ours.
                Message.status == MessageStatus.SENDING,
                Message.platform_message_id.is_(None),
                Message.occurred_at.between(around - window, around + window),
                content,
            )
            .order_by(Message.occurred_at)
            .limit(1)
            .with_for_update(),
            execution_options=_FRESH,
        )
    ).one_or_none()


async def unknown_delivery_candidate(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    text: str,
    around: datetime,
    window: timedelta,
) -> Message | None:
    """TR-JOB-05: an outbound message whose send timed out (failed, delivery_unknown), with this
    exact text, queued or marked failed within ``window`` of ``around``; the newest one wins."""
    near_queue = Message.occurred_at.between(around - window, around + window)
    near_failure = Message.updated_at.between(around - window, around + window)
    return (
        await session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.direction == Direction.OUTBOUND,
                Message.status == MessageStatus.FAILED,
                Message.error_code == "delivery_unknown",
                Message.platform_message_id.is_(None),
                Message.text == text,
                near_queue | near_failure,
            )
            .order_by(Message.occurred_at.desc())
            .limit(1)
            .with_for_update(),
            execution_options=_FRESH,
        )
    ).one_or_none()


async def outbound_unread(
    session: AsyncSession, conversation_id: uuid.UUID, *, up_to: datetime
) -> Sequence[Message]:
    """Sent or delivered outbound messages up to ``up_to``, locked: a read receipt covers them."""
    result = await session.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.direction == Direction.OUTBOUND,
            Message.status.in_([MessageStatus.SENT, MessageStatus.DELIVERED]),
            Message.occurred_at <= up_to,
        )
        .order_by(Message.occurred_at)
        .with_for_update(),
        execution_options=_FRESH,
    )
    return result.all()


# ---------------------------------------------------------------- media items (sync_media)


async def upsert_media_item(
    session: AsyncSession,
    *,
    social_account_id: uuid.UUID,
    media: PlatformMedia,
    synced_at: datetime,
) -> None:
    """Insert a post or refresh what the platform may have changed (caption, URLs, counts)."""
    changing = {
        "media_type": media.media_type,
        "caption": media.caption,
        "media_url": media.media_url,
        "thumbnail_url": media.thumbnail_url,
        "permalink": media.permalink,
        "like_count": media.like_count,
        "comments_count": media.comments_count,
        "synced_at": synced_at,
    }
    statement = insert(MediaItem).values(
        workspace_id=require_workspace(),
        social_account_id=social_account_id,
        platform_media_id=media.platform_media_id,
        posted_at=media.posted_at,
        **changing,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[MediaItem.social_account_id, MediaItem.platform_media_id],
        set_={**{k: statement.excluded[k] for k in changing}, "updated_at": synced_at},
    )
    await session.execute(statement)


async def assets_by_id(session: AsyncSession, asset_ids: Sequence[uuid.UUID]) -> list[MediaAsset]:
    if not asset_ids:
        return []
    result = await session.scalars(select(MediaAsset).where(MediaAsset.id.in_(asset_ids)))
    return list(result.all())


async def delete_asset(session: AsyncSession, asset_id: uuid.UUID) -> None:
    await session.execute(scoped_delete(MediaAsset, id=asset_id))
