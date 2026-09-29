"""Scheduled posts, posting times, hashtag groups and the media library (T7.1; §5.7,
FR-PUB-01, FR-PUB-04, FR-PUB-08…14, F-13).

Tenant-scoped like every repository: reads go through the ORM's workspace filter and writes
through ``scoped_update`` / ``scoped_delete`` (TR-TEN-04). A post's targets come back in the order
of its accounts (the accounts' connection order, as the composer's Accounts chips list them),
its assets by position.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, time
from typing import Any, NamedTuple

from sqlalchemy import DateTime, Uuid, exists, func, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from socialhood.models.automations import Automation, AutomationPost
from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import Contact, Conversation, ScheduledMessage
from socialhood.models.inbox import ScheduledStatus as MessageStatus
from socialhood.models.media import AssetPurpose, MediaAsset, MediaItem
from socialhood.models.publishing import (
    HashtagGroup,
    PostingSlot,
    ScheduledPost,
    ScheduledPostAsset,
    ScheduledPostStatus,
    ScheduledPostTarget,
    TargetStatus,
)
from socialhood.repositories.base import scoped_delete, scoped_update

P = ScheduledPostStatus
T = TargetStatus
_TIMESTAMP = DateTime(timezone=True)
_UUID = Uuid()

# The List view's tabs (schemas/publishing.py ScheduledPostView).
VIEW_STATUSES: dict[str, tuple[str, ...]] = {
    "scheduled": (P.SCHEDULED, P.PUBLISHING),
    "drafts": (P.DRAFT,),
    "published": (P.PUBLISHED, P.PARTIALLY_PUBLISHED),
    "failed": (P.FAILED, P.CANCELED),
}
# Targets that will publish, are publishing or have published: they take an account's posting
# time (FR-PUB-09) and a place in its 24-hour publishing limit (FR-PUB-10).
_LIVE_TARGETS = (T.PENDING, T.PUBLISHING, T.CONTAINER_CREATED, T.PUBLISHED)


class Planned(NamedTuple):
    """A target that takes a time on an account: ``at`` is when it published, or its post's
    time while it waits or publishes."""

    social_account_id: uuid.UUID
    scheduled_post_id: uuid.UUID
    at: datetime
    published: bool


# ---------------------------------------------------------------- posts


async def get(
    session: AsyncSession, scheduled_post_id: uuid.UUID, *, for_update: bool = False
) -> ScheduledPost | None:
    """One post; ``for_update`` locks it, so an edit and the dispatcher's claim never
    interleave (F-13 Edits)."""
    statement = select(ScheduledPost).where(ScheduledPost.id == scheduled_post_id)
    if for_update:
        statement = statement.with_for_update()
    return (await session.scalars(statement)).one_or_none()


async def lock_many(session: AsyncSession, ids: Sequence[uuid.UUID]) -> list[ScheduledPost]:
    """The workspace's posts among ``ids``, locked in id order (no deadlock between two bulk
    actions)."""
    if not ids:
        return []
    statement = (
        select(ScheduledPost)
        .where(ScheduledPost.id.in_(set(ids)))
        .order_by(ScheduledPost.id)
        .with_for_update()
    )
    return list((await session.scalars(statement)).all())


async def assets_for(
    session: AsyncSession, post_ids: Sequence[uuid.UUID]
) -> list[tuple[ScheduledPostAsset, MediaAsset]]:
    """The posts' assets with their uploads, by post and position."""
    if not post_ids:
        return []
    result = await session.execute(
        select(ScheduledPostAsset, MediaAsset)
        .join(MediaAsset, MediaAsset.id == ScheduledPostAsset.media_asset_id)
        .where(ScheduledPostAsset.scheduled_post_id.in_(set(post_ids)))
        .order_by(ScheduledPostAsset.scheduled_post_id, ScheduledPostAsset.position)
    )
    return [(row[0], row[1]) for row in result.all()]


async def targets_for(
    session: AsyncSession, post_ids: Sequence[uuid.UUID]
) -> list[tuple[ScheduledPostTarget, SocialAccount]]:
    """The posts' targets with their accounts, by post, then in account order."""
    if not post_ids:
        return []
    result = await session.execute(
        select(ScheduledPostTarget, SocialAccount)
        .join(SocialAccount, SocialAccount.id == ScheduledPostTarget.social_account_id)
        .where(ScheduledPostTarget.scheduled_post_id.in_(set(post_ids)))
        .order_by(ScheduledPostTarget.scheduled_post_id, SocialAccount.created_at, SocialAccount.id)
    )
    return [(row[0], row[1]) for row in result.all()]


async def published_items(
    session: AsyncSession, target_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    """Target id -> the media item (the post in Posts) it published, when there is one."""
    if not target_ids:
        return {}
    result = await session.execute(
        select(MediaItem.published_target_id, MediaItem.id).where(
            MediaItem.published_target_id.in_(set(target_ids))
        )
    )
    return {row[0]: row[1] for row in result.all() if row[0] is not None}


async def linked_automations(
    session: AsyncSession, post_ids: Sequence[uuid.UUID]
) -> list[tuple[uuid.UUID, Automation]]:
    """(scheduled post id, automation) for the comment automations scoped to the posts
    (FR-AUT-18), by name."""
    if not post_ids:
        return []
    result = await session.execute(
        select(AutomationPost.scheduled_post_id, Automation)
        .join(Automation, Automation.id == AutomationPost.automation_id)
        .where(AutomationPost.scheduled_post_id.in_(set(post_ids)))
        .order_by(Automation.name, Automation.id)
    )
    return [(row[0], row[1]) for row in result.all() if row[0] is not None]


async def accounts_by_id(
    session: AsyncSession, ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, SocialAccount]:
    """This workspace's accounts among ``ids``."""
    if not ids:
        return {}
    rows = await session.scalars(select(SocialAccount).where(SocialAccount.id.in_(set(ids))))
    return {row.id: row for row in rows.all()}


async def assets_by_id(
    session: AsyncSession, ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, MediaAsset]:
    """This workspace's uploads among ``ids``."""
    if not ids:
        return {}
    rows = await session.scalars(select(MediaAsset).where(MediaAsset.id.in_(set(ids))))
    return {row.id: row for row in rows.all()}


async def replace_assets(
    session: AsyncSession, scheduled_post_id: uuid.UUID, asset_ids: Sequence[uuid.UUID]
) -> None:
    """The post's assets become ``asset_ids`` in that order."""
    await session.execute(scoped_delete(ScheduledPostAsset, scheduled_post_id=scheduled_post_id))
    session.add_all(
        ScheduledPostAsset(scheduled_post_id=scheduled_post_id, media_asset_id=a, position=i)
        for i, a in enumerate(asset_ids)
    )
    await session.flush()


async def delete_targets(session: AsyncSession, target_ids: Sequence[uuid.UUID]) -> None:
    if target_ids:
        await session.execute(
            scoped_delete(ScheduledPostTarget).where(ScheduledPostTarget.id.in_(set(target_ids)))
        )


async def keep_published_links(session: AsyncSession, scheduled_post_id: uuid.UUID) -> int:
    """Before a post is deleted: automation links that already have their media item stop
    naming the post, so the delete's cascade leaves them (C-043). Returns how many."""
    result = await session.execute(
        scoped_update(AutomationPost, scheduled_post_id=scheduled_post_id)
        .where(AutomationPost.media_item_id.is_not(None))
        .values(scheduled_post_id=None)
        .returning(AutomationPost.id)
    )
    return len(result.all())


async def delete_posts(session: AsyncSession, post_ids: Sequence[uuid.UUID]) -> None:
    """Delete posts; their assets, targets and waiting automation links go with them."""
    if post_ids:
        await session.execute(
            scoped_delete(ScheduledPost).where(ScheduledPost.id.in_(set(post_ids)))
        )


def _on_accounts(account_ids: Sequence[uuid.UUID] | None) -> ColumnElement[bool] | None:
    if not account_ids:
        return None
    return exists().where(
        ScheduledPostTarget.scheduled_post_id == ScheduledPost.id,
        ScheduledPostTarget.social_account_id.in_(set(account_ids)),
    )


def view_key(view: str) -> Any:
    """The time a view orders by (the cursor's first part)."""
    if view == "drafts":
        return ScheduledPost.updated_at
    if view == "published":
        return func.coalesce(ScheduledPost.published_at, ScheduledPost.publish_at)
    return ScheduledPost.publish_at


def view_time(view: str, post: ScheduledPost) -> datetime:
    """``view_key`` for one loaded post."""
    if view == "drafts":
        return post.updated_at
    at = (post.published_at if view == "published" else None) or post.publish_at
    assert at is not None  # the schedulable check: every post past draft has a time
    return at


async def list_view(
    session: AsyncSession,
    *,
    view: str,
    account_ids: Sequence[uuid.UUID] | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[ScheduledPost]:
    """A page of the List view: scheduled soonest first, the others newest first."""
    key = view_key(view)
    statement = select(ScheduledPost).where(ScheduledPost.status.in_(VIEW_STATUSES[view]))
    on_accounts = _on_accounts(account_ids)
    if on_accounts is not None:
        statement = statement.where(on_accounts)
    ascending = view == "scheduled"
    if after is not None:
        cursor = tuple_(literal(after[0], _TIMESTAMP), literal(after[1], _UUID))
        row = tuple_(key, ScheduledPost.id)
        statement = statement.where(row > cursor if ascending else row < cursor)
    if ascending:
        statement = statement.order_by(key, ScheduledPost.id)
    else:
        statement = statement.order_by(key.desc(), ScheduledPost.id.desc())
    return list((await session.scalars(statement.limit(limit))).all())


async def in_range(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    account_ids: Sequence[uuid.UUID] | None,
    limit: int,
) -> list[ScheduledPost]:
    """Posts with a time in [start, end), drafts included, by time (the calendar)."""
    statement = select(ScheduledPost).where(
        ScheduledPost.publish_at >= start, ScheduledPost.publish_at < end
    )
    on_accounts = _on_accounts(account_ids)
    if on_accounts is not None:
        statement = statement.where(on_accounts)
    statement = statement.order_by(ScheduledPost.publish_at, ScheduledPost.id).limit(limit)
    return list((await session.scalars(statement)).all())


async def planned(
    session: AsyncSession,
    account_ids: Sequence[uuid.UUID],
    *,
    start: datetime,
    end: datetime,
) -> list[Planned]:
    """Targets of the accounts that publish, are publishing or published at a time in
    [start, end]: pending targets of scheduled posts, claimed ones, and published ones (at
    their publish time)."""
    if not account_ids:
        return []
    at = func.coalesce(ScheduledPostTarget.published_at, ScheduledPost.publish_at)
    result = await session.execute(
        select(
            ScheduledPostTarget.social_account_id,
            ScheduledPostTarget.scheduled_post_id,
            at,
            ScheduledPostTarget.status,
        )
        .join(ScheduledPost, ScheduledPost.id == ScheduledPostTarget.scheduled_post_id)
        .where(
            ScheduledPostTarget.social_account_id.in_(set(account_ids)),
            ScheduledPostTarget.status.in_(_LIVE_TARGETS),
            or_(
                ScheduledPostTarget.status != T.PENDING,
                ScheduledPost.status.in_((P.SCHEDULED, P.PUBLISHING)),
            ),
            at >= start,
            at <= end,
        )
    )
    return [
        Planned(row[0], row[1], row[2], row[3] == T.PUBLISHED)
        for row in result.all()
        if row[2] is not None
    ]


async def published_counts(
    session: AsyncSession, account_ids: Sequence[uuid.UUID], *, since: datetime
) -> dict[uuid.UUID, int]:
    """Posts each account published since ``since`` (the right rail's last 24 hours)."""
    if not account_ids:
        return {}
    result = await session.execute(
        select(ScheduledPostTarget.social_account_id, func.count())
        .where(
            ScheduledPostTarget.social_account_id.in_(set(account_ids)),
            ScheduledPostTarget.status == T.PUBLISHED,
            ScheduledPostTarget.published_at > since,
        )
        .group_by(ScheduledPostTarget.social_account_id)
    )
    return {row[0]: int(row[1]) for row in result.all()}


# ---------------------------------------------------------------- posting times (FR-PUB-09)


async def slots_for(session: AsyncSession, account_ids: Sequence[uuid.UUID]) -> list[PostingSlot]:
    """The accounts' weekly times, by account, weekday and time."""
    if not account_ids:
        return []
    rows = await session.scalars(
        select(PostingSlot)
        .where(PostingSlot.social_account_id.in_(set(account_ids)))
        .order_by(PostingSlot.social_account_id, PostingSlot.weekday, PostingSlot.local_time)
    )
    return list(rows.all())


async def replace_slots(
    session: AsyncSession, account_id: uuid.UUID, slots: Sequence[tuple[int, time]]
) -> None:
    """The account's weekly times become ``slots`` (weekday, local time), without duplicates."""
    await session.execute(scoped_delete(PostingSlot, social_account_id=account_id))
    session.add_all(
        PostingSlot(social_account_id=account_id, weekday=weekday, local_time=at)
        for weekday, at in dict.fromkeys(slots)
    )
    await session.flush()


# ---------------------------------------------------------------- hashtag groups (FR-PUB-12)


async def hashtag_groups(session: AsyncSession) -> list[HashtagGroup]:
    rows = await session.scalars(
        select(HashtagGroup).order_by(func.lower(HashtagGroup.name), HashtagGroup.id)
    )
    return list(rows.all())


async def hashtag_group(
    session: AsyncSession, hashtag_group_id: uuid.UUID, *, for_update: bool = False
) -> HashtagGroup | None:
    statement = select(HashtagGroup).where(HashtagGroup.id == hashtag_group_id)
    if for_update:
        statement = statement.with_for_update()
    return (await session.scalars(statement)).one_or_none()


async def hashtag_group_name_taken(
    session: AsyncSession, name: str, *, except_id: uuid.UUID | None = None
) -> bool:
    """Whether another group of the workspace has this name, ignoring case."""
    statement = select(HashtagGroup.id).where(func.lower(HashtagGroup.name) == name.lower())
    if except_id is not None:
        statement = statement.where(HashtagGroup.id != except_id)
    return (await session.scalars(statement.limit(1))).first() is not None


async def delete_hashtag_group(session: AsyncSession, hashtag_group_id: uuid.UUID) -> bool:
    result = await session.execute(
        scoped_delete(HashtagGroup, id=hashtag_group_id).returning(HashtagGroup.id)
    )
    return result.first() is not None


# ---------------------------------------------------------------- media library (FR-PUB-13)


async def post_uploads(
    session: AsyncSession,
    *,
    resource_type: str | None,
    start: datetime | None,
    end: datetime | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[MediaAsset]:
    """Images and videos uploaded for posts, newest first, created in [start, end)."""
    statement = select(MediaAsset).where(
        MediaAsset.purpose == AssetPurpose.POST,
        MediaAsset.resource_type.in_((resource_type,) if resource_type else ("image", "video")),
    )
    if start is not None:
        statement = statement.where(MediaAsset.created_at >= start)
    if end is not None:
        statement = statement.where(MediaAsset.created_at < end)
    if after is not None:
        statement = statement.where(
            tuple_(MediaAsset.created_at, MediaAsset.id)
            < tuple_(literal(after[0], _TIMESTAMP), literal(after[1], _UUID))
        )
    statement = statement.order_by(MediaAsset.created_at.desc(), MediaAsset.id.desc())
    return list((await session.scalars(statement.limit(limit))).all())


# ---------------------------------------------------------------- the calendar's Messages layer


class CalendarMessageRow(NamedTuple):
    scheduled: ScheduledMessage
    platform: str
    contact: Contact
    social_account_id: uuid.UUID


async def scheduled_messages(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
    account_ids: Sequence[uuid.UUID] | None,
    limit: int,
) -> list[CalendarMessageRow]:
    """Scheduled DMs sending in [start, end), canceled ones left out, by send time
    (FR-SMS-02 on the calendar)."""
    statement = (
        select(ScheduledMessage, Conversation.platform, Contact, Conversation.social_account_id)
        .join(Conversation, Conversation.id == ScheduledMessage.conversation_id)
        .join(Contact, Contact.id == Conversation.contact_id)
        .where(
            ScheduledMessage.send_at >= start,
            ScheduledMessage.send_at < end,
            ScheduledMessage.status != MessageStatus.CANCELED,
        )
    )
    if account_ids:
        statement = statement.where(Conversation.social_account_id.in_(set(account_ids)))
    statement = statement.order_by(ScheduledMessage.send_at, ScheduledMessage.id).limit(limit)
    result = await session.execute(statement)
    return [CalendarMessageRow(row[0], row[1], row[2], row[3]) for row in result.all()]
