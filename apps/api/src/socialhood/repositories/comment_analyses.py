"""Comment intelligence rows (T6.2; TR-AI-11, FR-CMT-02, FR-CMT-03, FR-CMT-05): the analysis batch,
stored analyses, each post's comment stats (``media_items.comment_stats``) and the figures a post
summary is built from. Tenant-scoped: reads are filtered by the session's workspace, writes use
``scoped_update`` or stamp the current workspace. ``accounts_with_pending`` and
``stale_summaries`` look across workspaces: jobs/ calls them inside ``tenant_bypass_scope``.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Integer, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.analytics import CommentAnalysis
from socialhood.models.automations import AnalysisStatus, Comment
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.media import MediaItem, MediaType
from socialhood.repositories.base import scoped_update

_FRESH = {"populate_existing": True}
STAT_NAMES = ("total", "analysed", "positive", "neutral", "negative", "spam")


# ---------------------------------------------------------------- the batch (analyze_comments)


async def pending_batch(
    session: AsyncSession, social_account_id: uuid.UUID, limit: int
) -> list[tuple[Comment, str | None]]:
    """The account's oldest pending comments (arrival order, ix_comments_pending_analysis) with
    their post's caption."""
    comments = list(
        (
            await session.scalars(
                select(Comment)
                .where(
                    Comment.social_account_id == social_account_id,
                    Comment.analysis_status == AnalysisStatus.PENDING,
                )
                .order_by(Comment.created_at, Comment.id)
                .limit(limit),
                execution_options=_FRESH,
            )
        ).all()
    )
    post_ids = {c.media_item_id for c in comments}
    captions: dict[uuid.UUID, str | None] = {}
    if post_ids:
        rows = await session.execute(
            select(MediaItem.id, MediaItem.caption).where(MediaItem.id.in_(post_ids))
        )
        captions = {post_id: caption for post_id, caption in rows.all()}
    return [(c, captions.get(c.media_item_id)) for c in comments]


async def has_pending(session: AsyncSession, social_account_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(
                exists().where(
                    Comment.social_account_id == social_account_id,
                    Comment.analysis_status == AnalysisStatus.PENDING,
                )
            )
        )
    )


async def recent_post_ids(
    session: AsyncSession, social_account_id: uuid.UUID, limit: int
) -> list[uuid.UUID]:
    """The account's most recent posts (stories take no comments)."""
    result = await session.scalars(
        select(MediaItem.id)
        .where(
            MediaItem.social_account_id == social_account_id,
            MediaItem.media_type != MediaType.STORY,
        )
        .order_by(MediaItem.posted_at.desc(), MediaItem.id.desc())
        .limit(limit)
    )
    return list(result.all())


async def skip_pending(
    session: AsyncSession,
    social_account_id: uuid.UUID,
    *,
    comment_ids: Collection[uuid.UUID] | None = None,
    except_posts: Collection[uuid.UUID] | None = None,
) -> set[uuid.UUID]:
    """Pending comments of the account become ``skipped`` (all of them, the given ones, or those
    not on ``except_posts``); returns the posts they are on."""
    statement = scoped_update(Comment).where(
        Comment.social_account_id == social_account_id,
        Comment.analysis_status == AnalysisStatus.PENDING,
    )
    if comment_ids is not None:
        if not comment_ids:
            return set()
        statement = statement.where(Comment.id.in_(list(comment_ids)))
    if except_posts is not None:
        statement = statement.where(Comment.media_item_id.not_in(list(except_posts)))
    result = await session.execute(
        statement.values(analysis_status=AnalysisStatus.SKIPPED).returning(Comment.media_item_id)
    )
    return set(result.scalars().all())


async def insert_analyses(session: AsyncSession, rows: Sequence[dict[str, Any]]) -> set[uuid.UUID]:
    """Store analyses once per comment; returns the comments stored now."""
    if not rows:
        return set()
    workspace_id = require_workspace()
    statement = (
        insert(CommentAnalysis)
        .on_conflict_do_nothing(index_elements=[CommentAnalysis.comment_id])
        .returning(CommentAnalysis.comment_id)
    )
    result = await session.execute(
        statement, [{"workspace_id": workspace_id, **row} for row in rows]
    )
    return set(result.scalars().all())


async def mark_done(session: AsyncSession, comment_ids: Collection[uuid.UUID]) -> None:
    if comment_ids:
        await session.execute(
            scoped_update(Comment)
            .where(Comment.id.in_(list(comment_ids)))
            .values(analysis_status=AnalysisStatus.DONE)
        )


async def mark_hidden(session: AsyncSession, comment_ids: Collection[uuid.UUID]) -> None:
    """Auto-hidden spam (FR-CMT-05)."""
    if comment_ids:
        await session.execute(
            scoped_update(Comment).where(Comment.id.in_(list(comment_ids))).values(hidden=True)
        )


async def analyses_for(
    session: AsyncSession, comment_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, CommentAnalysis]:
    if not comment_ids:
        return {}
    result = await session.scalars(
        select(CommentAnalysis).where(CommentAnalysis.comment_id.in_(list(comment_ids)))
    )
    return {row.comment_id: row for row in result.all()}


# ---------------------------------------------------------------- post stats (FR-CMT-03)


async def bump_total(session: AsyncSession, media_item_id: uuid.UUID) -> MediaItem | None:
    """One more comment on the post (webhook intake); returns the post as it now is. Atomic, so
    it never loses a concurrent count; ``recount`` later recomputes every figure under the row
    lock."""
    total = func.coalesce(MediaItem.comment_stats["total"].astext.cast(Integer), 0) + 1
    result = await session.scalars(
        scoped_update(MediaItem, id=media_item_id)
        .values(
            comment_stats=func.coalesce(MediaItem.comment_stats, func.jsonb_build_object()).op(
                "||"
            )(func.jsonb_build_object("total", total))
        )
        .returning(MediaItem),
        execution_options=_FRESH,
    )
    return result.one_or_none()


async def count_stats(session: AsyncSession, media_item_id: uuid.UUID) -> dict[str, int]:
    """CommentStats for the post, from the rows: deleted comments are left out; ``analysed`` is
    every comment no longer pending (skipped ones too, so progress completes); positive, neutral
    and negative count analysed comments that are not spam. Each query reads one table, so a
    viral post's plan never depends on join estimates."""
    live = Comment.deleted_at.is_(None)
    total, analysed, deleted = (
        await session.execute(
            select(
                func.count().filter(live),
                func.count().filter(live, Comment.analysis_status != AnalysisStatus.PENDING),
                func.array_agg(Comment.id).filter(Comment.deleted_at.is_not(None)),
            ).where(Comment.media_item_id == media_item_id)
        )
    ).one()
    stats = dict.fromkeys(STAT_NAMES, 0) | {"total": int(total), "analysed": int(analysed)}
    readings = await session.execute(
        select(CommentAnalysis.sentiment, CommentAnalysis.is_spam, func.count())
        .where(CommentAnalysis.media_item_id == media_item_id, *_not_deleted(deleted))
        .group_by(CommentAnalysis.sentiment, CommentAnalysis.is_spam)
    )
    for sentiment, is_spam, n in readings.all():
        stats["spam" if is_spam else str(sentiment)] += int(n)
    return stats


def _not_deleted(deleted: Sequence[uuid.UUID] | None) -> list[ColumnElement[bool]]:
    """Leave out the analyses of deleted comments (few: a post's deleted ones, by id)."""
    return [CommentAnalysis.comment_id.not_in(list(deleted))] if deleted else []


async def _deleted_ids(session: AsyncSession, media_item_id: uuid.UUID) -> list[uuid.UUID]:
    result = await session.scalars(
        select(Comment.id).where(
            Comment.media_item_id == media_item_id, Comment.deleted_at.is_not(None)
        )
    )
    return list(result.all())


async def recount(session: AsyncSession, media_item_ids: Collection[uuid.UUID]) -> list[MediaItem]:
    """Recompute ``comment_stats`` of the posts under their row locks (taken in id order) and
    return them fresh. Counting after the lock sees every committed comment, so this and
    ``bump_total`` never lose one."""
    if not media_item_ids:
        return []
    items = list(
        (
            await session.scalars(
                select(MediaItem)
                .where(MediaItem.id.in_(list(media_item_ids)))
                .order_by(MediaItem.id)
                .with_for_update(),
                execution_options=_FRESH,
            )
        ).all()
    )
    for item in items:
        item.comment_stats = await count_stats(session, item.id)
    await session.flush()
    return items


async def stored_counts(
    session: AsyncSession, social_account_id: uuid.UUID, limit: int
) -> list[tuple[MediaItem, int]]:
    """The account's most recent posts with the comments stored for each (TR-WH-08's gap check
    against Instagram's ``comments_count``)."""
    stored = (
        select(func.count())
        .where(Comment.media_item_id == MediaItem.id)
        .correlate(MediaItem)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(MediaItem, stored)
        .where(
            MediaItem.social_account_id == social_account_id,
            MediaItem.media_type != MediaType.STORY,
        )
        .order_by(MediaItem.posted_at.desc(), MediaItem.id.desc())
        .limit(limit)
    )
    return [(item, int(count or 0)) for item, count in rows.all()]


# ---------------------------------------------------------------- post summaries (TR-AI-11)


async def has_analyses(session: AsyncSession, media_item_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(select(exists().where(CommentAnalysis.media_item_id == media_item_id)))
    )


async def analysed_since(
    session: AsyncSession, media_item_id: uuid.UUID, since: datetime | None
) -> int:
    """Analyses stored for the post after ``since`` (all of them when None)."""
    statement = select(func.count()).where(CommentAnalysis.media_item_id == media_item_id)
    if since is not None:
        statement = statement.where(CommentAnalysis.created_at > since)
    return int(await session.scalar(statement) or 0)


async def top_topics(
    session: AsyncSession, media_item_id: uuid.UUID, limit: int
) -> list[tuple[str, int]]:
    """The post's most frequent topics among analysed comments that are not spam (deleted ones
    left out), most frequent first."""
    count = func.count().label("n")
    rows = await session.execute(
        select(CommentAnalysis.topic, count)
        .where(
            CommentAnalysis.media_item_id == media_item_id,
            CommentAnalysis.is_spam.is_(False),
            CommentAnalysis.topic.is_not(None),
            *_not_deleted(await _deleted_ids(session, media_item_id)),
        )
        .group_by(CommentAnalysis.topic)
        .order_by(count.desc(), CommentAnalysis.topic)
        .limit(limit)
    )
    return [(str(topic), int(n)) for topic, n in rows.all()]


async def topic_sentiments(
    session: AsyncSession, media_item_id: uuid.UUID, topics: Collection[str]
) -> dict[str, dict[str, int]]:
    """For each topic: its analysed, non-spam, not deleted comments by sentiment."""
    if not topics:
        return {}
    rows = await session.execute(
        select(CommentAnalysis.topic, CommentAnalysis.sentiment, func.count())
        .where(
            CommentAnalysis.media_item_id == media_item_id,
            CommentAnalysis.is_spam.is_(False),
            CommentAnalysis.topic.in_(list(topics)),
            *_not_deleted(await _deleted_ids(session, media_item_id)),
        )
        .group_by(CommentAnalysis.topic, CommentAnalysis.sentiment)
    )
    counts: dict[str, dict[str, int]] = {}
    for topic, sentiment, n in rows.all():
        counts.setdefault(str(topic), {})[str(sentiment)] = int(n)
    return counts


async def sample_comments(session: AsyncSession, media_item_id: uuid.UUID, limit: int) -> list[str]:
    """Texts of analysed, non-spam comments for the summary's context: most liked, then
    newest."""
    rows = (
        await session.execute(
            select(Comment.id, Comment.text)
            .where(
                Comment.media_item_id == media_item_id,
                Comment.deleted_at.is_(None),
                Comment.analysis_status == AnalysisStatus.DONE,
            )
            .order_by(Comment.like_count.desc(), Comment.commented_at.desc())
            .limit(limit * 3)
        )
    ).all()
    spam = set(
        (
            await session.scalars(
                select(CommentAnalysis.comment_id).where(
                    CommentAnalysis.comment_id.in_([comment_id for comment_id, _ in rows]),
                    CommentAnalysis.is_spam.is_(True),
                )
            )
        ).all()
    )
    return [text for comment_id, text in rows if text and comment_id not in spam][:limit]


async def lock_post(session: AsyncSession, media_item_id: uuid.UUID) -> MediaItem | None:
    return (
        await session.scalars(
            select(MediaItem).where(MediaItem.id == media_item_id).with_for_update(),
            execution_options=_FRESH,
        )
    ).one_or_none()


# ---------------------------------------------------------------- dispatch (jobs/, all workspaces)


async def accounts_with_pending(
    session: AsyncSession, limit: int = 1000
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(account id, workspace id) of live accounts with pending comments."""
    rows = await session.execute(
        select(SocialAccount.id, SocialAccount.workspace_id)
        .where(
            SocialAccount.status.in_([AccountStatus.ACTIVE, AccountStatus.ERROR]),
            exists().where(
                Comment.social_account_id == SocialAccount.id,
                Comment.analysis_status == AnalysisStatus.PENDING,
            ),
        )
        .limit(limit)
    )
    return [(account_id, workspace_id) for account_id, workspace_id in rows.all()]


async def stale_summaries(
    session: AsyncSession, *, analysed_before: datetime, limit: int = 500
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(post id, workspace id) of posts whose summary is behind by an analysis older than
    ``analysed_before``: never summarised, or summarised before it (TR-AI-11's 24 h rule)."""
    newer = exists().where(
        CommentAnalysis.media_item_id == MediaItem.id,
        CommentAnalysis.created_at <= analysed_before,
        or_(
            MediaItem.summary_updated_at.is_(None),
            CommentAnalysis.created_at > MediaItem.summary_updated_at,
        ),
    )
    rows = await session.execute(
        select(MediaItem.id, MediaItem.workspace_id)
        .where(
            or_(
                MediaItem.summary_updated_at.is_(None),
                MediaItem.summary_updated_at <= analysed_before,
            ),
            newer,
        )
        .limit(limit)
    )
    return [(post_id, workspace_id) for post_id, workspace_id in rows.all()]
