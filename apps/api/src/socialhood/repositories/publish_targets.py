"""Queries for the publish jobs (T7.3; F-13, FR-PUB-05, TR-JOB-03).

Tenant-scoped like every repository. The dispatcher and the sweeper look across workspaces: they
call ``lock_due_posts``, ``pending_targets_of``, ``stuck_publishing`` and ``idle_containers``
inside a ``tenant_bypass_scope`` opened in jobs/ (TR-TEN-04); the rest run in the post's
workspace scope.

Locks are always taken post first, then target (the dispatcher, the publish steps, the sweeper),
so two of them never wait on each other in opposite orders; a post's status is derived from its
targets while its row is locked, so two targets finishing at once can't both miss the other.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.automations import Automation, AutomationPost
from socialhood.models.media import MediaAsset, MediaItem
from socialhood.models.publishing import (
    ScheduledPost,
    ScheduledPostAsset,
    ScheduledPostStatus,
    ScheduledPostTarget,
    TargetStatus,
)
from socialhood.platforms.base import PlatformMedia

DUE_STATUSES = (ScheduledPostStatus.SCHEDULED, ScheduledPostStatus.PUBLISHING)


# ---------------------------------------------------------------- across workspaces (jobs/)


async def lock_due_posts(session: AsyncSession, now: datetime, limit: int) -> list[ScheduledPost]:
    """Posts whose time has come with a target still pending, soonest first, locked; a post
    another dispatcher (or a publish step) holds is skipped (TR-JOB-03)."""
    waiting = exists().where(
        ScheduledPostTarget.scheduled_post_id == ScheduledPost.id,
        ScheduledPostTarget.status == TargetStatus.PENDING,
    )
    statement = (
        select(ScheduledPost)
        .where(
            ScheduledPost.status.in_(DUE_STATUSES),
            ScheduledPost.publish_at <= now,
            waiting,
        )
        .order_by(ScheduledPost.publish_at, ScheduledPost.id)
        .limit(limit)
        .with_for_update(of=ScheduledPost, skip_locked=True)
    )
    return list((await session.scalars(statement)).all())


async def pending_targets_of(
    session: AsyncSession, post_ids: Sequence[uuid.UUID]
) -> list[ScheduledPostTarget]:
    """The pending targets of posts the caller has locked, locked too."""
    if not post_ids:
        return []
    statement = (
        select(ScheduledPostTarget)
        .where(
            ScheduledPostTarget.scheduled_post_id.in_(post_ids),
            ScheduledPostTarget.status == TargetStatus.PENDING,
        )
        .order_by(ScheduledPostTarget.scheduled_post_id, ScheduledPostTarget.id)
        .with_for_update(of=ScheduledPostTarget)
    )
    return list((await session.scalars(statement)).all())


async def stuck_publishing(
    session: AsyncSession, claimed_before: datetime, limit: int
) -> list[ScheduledPostTarget]:
    """Targets claimed before ``claimed_before`` that never got their containers (a lost
    publish_target, or a worker that died). Not locked: the sweeper locks each in order."""
    statement = (
        select(ScheduledPostTarget)
        .where(
            ScheduledPostTarget.status == TargetStatus.PUBLISHING,
            ScheduledPostTarget.claimed_at < claimed_before,
        )
        .order_by(ScheduledPostTarget.claimed_at)
        .limit(limit)
    )
    return list((await session.scalars(statement)).all())


async def idle_containers(
    session: AsyncSession, updated_before: datetime, limit: int
) -> list[ScheduledPostTarget]:
    """Targets waiting for Instagram whose last poll is older than ``updated_before``: their
    poll chain may be lost (every poll touches the row)."""
    statement = (
        select(ScheduledPostTarget)
        .where(
            ScheduledPostTarget.status == TargetStatus.CONTAINER_CREATED,
            ScheduledPostTarget.updated_at < updated_before,
        )
        .order_by(ScheduledPostTarget.updated_at)
        .limit(limit)
    )
    return list((await session.scalars(statement)).all())


# ---------------------------------------------------------------- one workspace


async def get_target(session: AsyncSession, target_id: uuid.UUID) -> ScheduledPostTarget | None:
    return await session.get(ScheduledPostTarget, target_id)


async def lock_post(session: AsyncSession, post_id: uuid.UUID) -> ScheduledPost | None:
    statement = select(ScheduledPost).where(ScheduledPost.id == post_id).with_for_update()
    return (await session.scalars(statement)).one_or_none()


async def lock_target(
    session: AsyncSession, target_id: uuid.UUID, *, skip_locked: bool = False
) -> ScheduledPostTarget | None:
    """The target, locked (after its post). ``skip_locked``: None when another job holds it."""
    statement = (
        select(ScheduledPostTarget)
        .where(ScheduledPostTarget.id == target_id)
        .with_for_update(skip_locked=skip_locked)
        .execution_options(populate_existing=True)
    )
    return (await session.scalars(statement)).one_or_none()


async def lock_post_and_target(
    session: AsyncSession, target_id: uuid.UUID
) -> tuple[ScheduledPost, ScheduledPostTarget] | None:
    """The target and its post, locked in that order (post first)."""
    target = await get_target(session, target_id)
    if target is None:
        return None
    post = await lock_post(session, target.scheduled_post_id)
    locked = await lock_target(session, target_id)
    if post is None or locked is None:
        return None
    return post, locked


async def targets_of(session: AsyncSession, post_id: uuid.UUID) -> list[ScheduledPostTarget]:
    statement = (
        select(ScheduledPostTarget)
        .where(ScheduledPostTarget.scheduled_post_id == post_id)
        .order_by(ScheduledPostTarget.created_at, ScheduledPostTarget.id)
        .execution_options(populate_existing=True)
    )
    return list((await session.scalars(statement)).all())


async def assets_of(session: AsyncSession, post_id: uuid.UUID) -> list[MediaAsset]:
    """The post's images and videos in order."""
    statement = (
        select(MediaAsset)
        .join(ScheduledPostAsset, ScheduledPostAsset.media_asset_id == MediaAsset.id)
        .where(ScheduledPostAsset.scheduled_post_id == post_id)
        .order_by(ScheduledPostAsset.position)
    )
    return list((await session.scalars(statement)).all())


async def media_items_of(
    session: AsyncSession, target_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    """Target id -> the media item it published."""
    if not target_ids:
        return {}
    result = await session.execute(
        select(MediaItem.published_target_id, MediaItem.id).where(
            MediaItem.published_target_id.in_(target_ids)
        )
    )
    return {target_id: item_id for target_id, item_id in result.all() if target_id is not None}


async def linked_automations(session: AsyncSession, post_id: uuid.UUID) -> list[Automation]:
    """Automations scoped to the post (FR-AUT-18), by name."""
    statement = (
        select(Automation)
        .join(AutomationPost, AutomationPost.automation_id == Automation.id)
        .where(AutomationPost.scheduled_post_id == post_id)
        .order_by(Automation.name, Automation.id)
        .distinct()
    )
    return list((await session.scalars(statement)).all())


async def media_item_owner(
    session: AsyncSession, social_account_id: uuid.UUID, platform_media_id: str
) -> uuid.UUID | None:
    """The target that already published this post, if one did."""
    return await session.scalar(
        select(MediaItem.published_target_id).where(
            MediaItem.social_account_id == social_account_id,
            MediaItem.platform_media_id == platform_media_id,
        )
    )


async def upsert_published_item(
    session: AsyncSession,
    *,
    social_account_id: uuid.UUID,
    target_id: uuid.UUID,
    media: PlatformMedia,
    synced_at: datetime,
) -> MediaItem:
    """The published post in media_items (§5.6), linked to its target. A row that sync or a
    comment webhook stored first is updated and linked instead."""
    statement = insert(MediaItem).values(
        workspace_id=require_workspace(),
        social_account_id=social_account_id,
        platform_media_id=media.platform_media_id,
        posted_at=media.posted_at,
        media_type=media.media_type,
        caption=media.caption,
        media_url=media.media_url,
        thumbnail_url=media.thumbnail_url,
        permalink=media.permalink,
        like_count=media.like_count,
        comments_count=media.comments_count,
        synced_at=synced_at,
        published_target_id=target_id,
    )
    excluded = statement.excluded
    upsert = statement.on_conflict_do_update(
        index_elements=[MediaItem.social_account_id, MediaItem.platform_media_id],
        set_={
            # A read-back that failed has no URLs or counts: keep what sync stored.
            "caption": func.coalesce(excluded.caption, MediaItem.caption),
            "media_url": func.coalesce(excluded.media_url, MediaItem.media_url),
            "thumbnail_url": func.coalesce(excluded.thumbnail_url, MediaItem.thumbnail_url),
            "permalink": func.coalesce(excluded.permalink, MediaItem.permalink),
            "published_target_id": excluded.published_target_id,
            "synced_at": excluded.synced_at,
            "updated_at": synced_at,
        },
    ).returning(MediaItem.id)
    item_id: uuid.UUID = (await session.execute(upsert)).scalar_one()
    item = await session.get(MediaItem, item_id, populate_existing=True)
    if item is None:  # pragma: no cover - just written in this transaction
        raise LookupError("media item vanished")
    return item
