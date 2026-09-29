"""Automation rows (T4.3, T4.7; §5.6): automations, their keywords and posts.

Tenant-scoped like every repository; deletes go through ``scoped_delete`` (TR-TEN-04). The
run-window job looks across workspaces: it calls ``lock_past_end`` inside a
``tenant_bypass_scope`` opened in jobs/.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import NamedTuple

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import (
    Automation,
    AutomationKeyword,
    AutomationPost,
    AutomationStatus,
    PostScope,
)
from socialhood.models.connections import AccountStatus, Platform, SocialAccount
from socialhood.models.media import MediaAsset, MediaItem, MediaType
from socialhood.repositories.base import scoped_delete

ACTIVE = AutomationStatus.ACTIVE


class Keyword(NamedTuple):
    keyword: str  # as typed
    normalized: str


class PostRow(NamedTuple):
    """An automation's post: a synced media item, or a scheduled post not yet published."""

    link: AutomationPost
    item: MediaItem | None


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------- automations


async def get(
    session: AsyncSession,
    automation_id: uuid.UUID,
    *,
    for_update: bool = False,
    fresh: bool = False,
) -> Automation | None:
    """``fresh`` reloads every column (after a write, whose server-side values such as
    updated_at the session does not have)."""
    statement = select(Automation).where(Automation.id == automation_id)
    if for_update:
        statement = statement.with_for_update()
    if fresh:
        statement = statement.execution_options(populate_existing=True)
    return (await session.scalars(statement)).one_or_none()


async def get_many(
    session: AsyncSession, ids: Sequence[uuid.UUID], *, for_update: bool = False
) -> list[Automation]:
    if not ids:
        return []
    statement = select(Automation).where(Automation.id.in_(ids)).order_by(Automation.id)
    if for_update:
        statement = statement.with_for_update()
    return list((await session.scalars(statement)).all())


async def list_filtered(
    session: AsyncSession,
    *,
    account_id: uuid.UUID | None = None,
    status: str | None = None,
    trigger: str | None = None,
    q: str | None = None,
    q_normalized: str | None = None,
) -> list[Automation]:
    """The list's filters (FR-AUT-19); ``q`` matches the name, ``q_normalized`` (the same
    search, normalised like keywords) a keyword."""
    statement = select(Automation)
    if account_id is not None:
        statement = statement.where(Automation.social_account_id == account_id)
    if status is not None:
        statement = statement.where(Automation.status == status)
    if trigger is not None:
        statement = statement.where(Automation.trigger == trigger)
    if q:
        name_pattern = f"%{escape_like(q)}%"
        keyword_pattern = f"%{escape_like(q_normalized or q)}%"
        statement = statement.where(
            or_(
                Automation.name.ilike(name_pattern, escape="\\"),
                exists().where(
                    AutomationKeyword.automation_id == Automation.id,
                    AutomationKeyword.keyword_normalized.like(keyword_pattern, escape="\\"),
                ),
            )
        )
    statement = statement.order_by(Automation.priority, Automation.created_at, Automation.id)
    return list((await session.scalars(statement)).all())


async def for_account(
    session: AsyncSession, social_account_id: uuid.UUID, *, for_update: bool = False
) -> list[Automation]:
    """The account's automations in runtime order (priority, then the oldest)."""
    statement = (
        select(Automation)
        .where(Automation.social_account_id == social_account_id)
        .order_by(Automation.priority, Automation.created_at, Automation.id)
    )
    if for_update:
        statement = statement.with_for_update()
    return list((await session.scalars(statement)).all())


async def active_for_accounts(
    session: AsyncSession, account_ids: Sequence[uuid.UUID]
) -> list[Automation]:
    if not account_ids:
        return []
    statement = select(Automation).where(
        Automation.status == ACTIVE, Automation.social_account_id.in_(account_ids)
    )
    return list((await session.scalars(statement)).all())


async def count_active(session: AsyncSession, *, excluding: uuid.UUID | None = None) -> int:
    """For the active_automations limit (counted live, §5.8)."""
    statement = select(func.count()).select_from(Automation).where(Automation.status == ACTIVE)
    if excluding is not None:
        statement = statement.where(Automation.id != excluding)
    return int(await session.scalar(statement) or 0)


async def any_activated(session: AsyncSession) -> bool:
    """Whether an automation of the workspace has ever been activated (FR-ACC-04). A count
    over the entity (not EXISTS), so the tenant filter applies as it does to any_live."""
    statement = (
        select(func.count()).select_from(Automation).where(Automation.activated_at.is_not(None))
    )
    return bool(await session.scalar(statement))


async def delete(session: AsyncSession, automation_id: uuid.UUID) -> None:
    """Keywords, posts and runs go with it (ON DELETE CASCADE)."""
    await session.execute(scoped_delete(Automation, id=automation_id))


# ---------------------------------------------------------------- keywords


async def keywords_for(
    session: AsyncSession, automation_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[Keyword]]:
    """Each automation's keywords in the order they were entered."""
    found: dict[uuid.UUID, list[Keyword]] = {i: [] for i in automation_ids}
    if not automation_ids:
        return found
    rows = await session.execute(
        select(
            AutomationKeyword.automation_id,
            AutomationKeyword.keyword,
            AutomationKeyword.keyword_normalized,
        )
        .where(AutomationKeyword.automation_id.in_(automation_ids))
        .order_by(AutomationKeyword.created_at, AutomationKeyword.id)
    )
    for automation_id, keyword, normalized in rows.all():
        found[automation_id].append(Keyword(keyword, normalized))
    return found


async def replace_keywords(
    session: AsyncSession, automation_id: uuid.UUID, keywords: Sequence[Keyword], now: datetime
) -> None:
    """Store ``keywords`` (already normalised and deduplicated) in their order: created_at
    grows by a microsecond per keyword, since rows inserted together share the clock."""
    await session.execute(scoped_delete(AutomationKeyword, automation_id=automation_id))
    session.add_all(
        AutomationKeyword(
            automation_id=automation_id,
            keyword=k.keyword,
            keyword_normalized=k.normalized,
            created_at=now + timedelta(microseconds=i),
        )
        for i, k in enumerate(keywords)
    )


# ---------------------------------------------------------------- posts


async def posts_for(
    session: AsyncSession, automation_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[PostRow]]:
    """Each automation's posts, newest first; scheduled posts not yet published come last."""
    found: dict[uuid.UUID, list[PostRow]] = {i: [] for i in automation_ids}
    if not automation_ids:
        return found
    rows = await session.execute(
        select(AutomationPost, MediaItem)
        .outerjoin(MediaItem, MediaItem.id == AutomationPost.media_item_id)
        .where(AutomationPost.automation_id.in_(automation_ids))
        .order_by(
            MediaItem.posted_at.desc().nulls_last(),
            AutomationPost.created_at,
            AutomationPost.id,
        )
    )
    for link, item in rows.all():
        found[link.automation_id].append(PostRow(link, item))
    return found


async def delete_posts(
    session: AsyncSession, automation_id: uuid.UUID, *, keep: Sequence[uuid.UUID] = ()
) -> None:
    """Remove the automation's post links, except the rows whose ids are in ``keep``."""
    statement = scoped_delete(AutomationPost, automation_id=automation_id)
    if keep:
        statement = statement.where(AutomationPost.id.not_in(keep))
    await session.execute(statement)


async def media_items(session: AsyncSession, ids: Sequence[uuid.UUID]) -> list[MediaItem]:
    if not ids:
        return []
    return list((await session.scalars(select(MediaItem).where(MediaItem.id.in_(ids)))).all())


async def get_media_item(session: AsyncSession, media_item_id: uuid.UUID) -> MediaItem | None:
    return (
        await session.scalars(select(MediaItem).where(MediaItem.id == media_item_id))
    ).one_or_none()


async def get_asset(session: AsyncSession, asset_id: uuid.UUID) -> MediaAsset | None:
    return (
        await session.scalars(select(MediaAsset).where(MediaAsset.id == asset_id))
    ).one_or_none()


async def asset_urls(session: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = await session.execute(
        select(MediaAsset.id, MediaAsset.secure_url).where(MediaAsset.id.in_(ids))
    )
    return {asset_id: url for asset_id, url in rows.all() if url}


# ---------------------------------------------------------------- upcoming posts (FR-AUT-18)


async def lock_waiting_for_next_post(
    session: AsyncSession, social_account_id: uuid.UUID
) -> list[Automation]:
    """The account's active next-post automations, locked so two callers never link one twice.
    The caller checks that each has no post yet (a fresh statement sees a concurrent link)."""
    statement = (
        select(Automation)
        .where(
            Automation.social_account_id == social_account_id,
            Automation.status == ACTIVE,
            Automation.post_scope == PostScope.NEXT_POST,
            Automation.activated_at.is_not(None),
        )
        .order_by(Automation.id)
        .with_for_update()
    )
    return list((await session.scalars(statement)).all())


async def has_posts(session: AsyncSession, automation_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(select(exists().where(AutomationPost.automation_id == automation_id)))
    )


async def first_post_since(
    session: AsyncSession, social_account_id: uuid.UUID, since: datetime
) -> MediaItem | None:
    """The account's earliest post (not a story) published at or after ``since``."""
    statement = (
        select(MediaItem)
        .where(
            MediaItem.social_account_id == social_account_id,
            MediaItem.media_type != MediaType.STORY,
            MediaItem.posted_at >= since,
        )
        .order_by(MediaItem.posted_at, MediaItem.id)
        .limit(1)
    )
    return (await session.scalars(statement)).one_or_none()


async def unlinked_scheduled_posts(
    session: AsyncSession, scheduled_post_id: uuid.UUID, social_account_id: uuid.UUID
) -> list[AutomationPost]:
    """Links to a scheduled post that has not published yet, for automations of the account
    the post just published on."""
    statement = (
        select(AutomationPost)
        .join(Automation, Automation.id == AutomationPost.automation_id)
        .where(
            AutomationPost.scheduled_post_id == scheduled_post_id,
            AutomationPost.media_item_id.is_(None),
            Automation.social_account_id == social_account_id,
        )
        .with_for_update(of=AutomationPost)
    )
    return list((await session.scalars(statement)).all())


# ---------------------------------------------------------------- accounts and posts


async def accounts(session: AsyncSession) -> dict[uuid.UUID, SocialAccount]:
    result = await session.scalars(select(SocialAccount))
    return {acct.id: acct for acct in result.all()}


async def live_instagram_accounts(session: AsyncSession) -> list[SocialAccount]:
    result = await session.scalars(
        select(SocialAccount)
        .where(
            SocialAccount.platform == Platform.INSTAGRAM,
            SocialAccount.status != AccountStatus.DISCONNECTED,
        )
        .order_by(SocialAccount.created_at)
    )
    return list(result.all())


# ---------------------------------------------------------------- across workspaces


async def lock_past_end(session: AsyncSession, now: datetime, limit: int) -> list[Automation]:
    """FR-AUT-17: active automations whose run window has ended, locked so two job runs never
    end (and announce) the same one. The caller opens tenant_bypass_scope."""
    statement = (
        select(Automation)
        .where(Automation.status == ACTIVE, Automation.ends_at <= now)
        .order_by(Automation.ends_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list((await session.scalars(statement)).all())
