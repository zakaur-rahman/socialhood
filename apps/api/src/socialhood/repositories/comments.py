"""Comments and the posts they are on, for comment intake and comment automations (F-12, T4.4).
Tenant-scoped: reads are filtered by the session's workspace and inserts are stamped with it."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.automations import Comment
from socialhood.models.media import MediaItem
from socialhood.platforms.base import PlatformMedia

_FRESH = {"populate_existing": True}


async def get(session: AsyncSession, comment_id: uuid.UUID) -> Comment | None:
    return (await session.scalars(select(Comment).where(Comment.id == comment_id))).one_or_none()


async def lock(session: AsyncSession, comment_id: uuid.UUID) -> Comment | None:
    return (
        await session.scalars(
            select(Comment).where(Comment.id == comment_id).with_for_update(),
            execution_options=_FRESH,
        )
    ).one_or_none()


async def get_many(session: AsyncSession, comment_ids: Sequence[uuid.UUID]) -> list[Comment]:
    if not comment_ids:
        return []
    result = await session.scalars(select(Comment).where(Comment.id.in_(list(comment_ids))))
    return list(result.all())


async def lock_many(session: AsyncSession, comment_ids: Sequence[uuid.UUID]) -> list[Comment]:
    if not comment_ids:
        return []
    result = await session.scalars(
        select(Comment)
        .where(Comment.id.in_(list(comment_ids)))
        .order_by(Comment.id)
        .with_for_update(),
        execution_options=_FRESH,
    )
    return list(result.all())


async def insert_comment(session: AsyncSession, values: dict[str, Any]) -> Comment | None:
    """Insert once per (account, platform comment id); None when it is already stored."""
    statement = (
        insert(Comment)
        .values(workspace_id=require_workspace(), **values)
        .on_conflict_do_nothing(
            index_elements=[Comment.social_account_id, Comment.platform_comment_id]
        )
        .returning(Comment)
    )
    return (await session.scalars(statement, execution_options=_FRESH)).one_or_none()


async def find_media_item(
    session: AsyncSession, social_account_id: uuid.UUID, platform_media_id: str
) -> MediaItem | None:
    return (
        await session.scalars(
            select(MediaItem).where(
                MediaItem.social_account_id == social_account_id,
                MediaItem.platform_media_id == platform_media_id,
            )
        )
    ).one_or_none()


async def get_media_item(session: AsyncSession, media_item_id: uuid.UUID) -> MediaItem | None:
    return (
        await session.scalars(select(MediaItem).where(MediaItem.id == media_item_id))
    ).one_or_none()


async def insert_media_item(
    session: AsyncSession,
    *,
    social_account_id: uuid.UUID,
    media: PlatformMedia,
    synced_at: datetime | None,
) -> MediaItem | None:
    """Insert a post we have not stored; None when it is already there (post sync won)."""
    statement = (
        insert(MediaItem)
        .values(
            workspace_id=require_workspace(),
            social_account_id=social_account_id,
            platform_media_id=media.platform_media_id,
            media_type=media.media_type,
            caption=media.caption,
            media_url=media.media_url,
            thumbnail_url=media.thumbnail_url,
            permalink=media.permalink,
            posted_at=media.posted_at,
            like_count=media.like_count,
            comments_count=media.comments_count,
            synced_at=synced_at,
        )
        .on_conflict_do_nothing(
            index_elements=[MediaItem.social_account_id, MediaItem.platform_media_id]
        )
        .returning(MediaItem)
    )
    return (await session.scalars(statement, execution_options=_FRESH)).one_or_none()
