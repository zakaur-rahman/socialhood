"""Post detail and a post's comments (T6.3; FR-CMT-03, FR-CMT-04, UX-SCR-05).

The comment list is newest first (commented_at, then id), paged with the inbox's cursor format, and
narrowed by one filter chip (schemas/posts.py ``CommentFilter``): the sentiment chips and the
intent chips count analysed comments that are not spam, spam counts analysed spam, hidden counts
comments hidden on Instagram. Deleted comments are never listed.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError
from socialhood.models.analytics import CommentAnalysis
from socialhood.models.automations import AnalysisStatus, Comment
from socialhood.models.media import MediaItem, MediaType
from socialhood.repositories import comments as comments_repo
from socialhood.repositories.automations import escape_like
from socialhood.repositories.comments import CommentRow
from socialhood.schemas.posts import (
    COMMENT_FILTER_INTENTS,
    CommentCounts,
    CommentFilter,
    CommentList,
    PostDetail,
)
from socialhood.services.comments import views
from socialhood.services.conversations import decode_cursor, encode_cursor


async def post_or_404(session: AsyncSession, post_id: uuid.UUID) -> MediaItem:
    item = await comments_repo.get_media_item(session, post_id)
    if item is None:
        raise ApiError("not_found")
    return item


async def get_post(session: AsyncSession, post_id: uuid.UUID) -> PostDetail:
    return views.post_detail(await post_or_404(session, post_id))


def filter_condition(name: CommentFilter) -> ColumnElement[bool] | None:
    """The chip as a condition on Comment and its (outer-joined) CommentAnalysis."""
    analysed = Comment.analysis_status == AnalysisStatus.DONE
    if name == "all":
        return None
    if name == "hidden":
        return Comment.hidden.is_(True)
    if name == "spam":
        return analysed & CommentAnalysis.is_spam.is_(True)
    not_spam = analysed & CommentAnalysis.is_spam.is_(False)
    if name in ("positive", "neutral", "negative"):
        return not_spam & (CommentAnalysis.sentiment == name)
    return not_spam & CommentAnalysis.intent.in_(COMMENT_FILTER_INTENTS[name])


@dataclass(frozen=True)
class CommentQuery:
    """Ask Social Hood's comment filters (get_post_comments, search_comments; TA.4). Every field
    narrows; None leaves it open. Deleted comments are never included. Sentiment, intents and
    topic match analysed comments only (TR-AI-11), spam apart unless ``spam`` says otherwise."""

    post_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None  # the commenter, once known as a contact
    start: datetime | None = None  # commented_at in [start, end)
    end: datetime | None = None
    q: str | None = None  # the comment's text contains it
    sentiment: str | None = None
    intents: tuple[str, ...] = ()
    topic: str | None = None  # the analysis topic contains it
    spam: bool | None = False  # False: not spam (unanalysed included); True: spam only
    replied: bool | None = None  # a public or private reply from the account


@dataclass(frozen=True)
class FoundComments:
    rows: list[CommentRow]  # newest first, at most the limit
    total: int  # comments matching
    in_scope: int  # comments in the scope (post, account, range, text), analysis filters aside
    pending: int  # of those, still waiting for analysis
    skipped: int  # of those, not analysed (AI analysis off, credits used up, beyond the plan)


def _scope(query: CommentQuery) -> list[ColumnElement[bool]]:
    where: list[ColumnElement[bool]] = [Comment.deleted_at.is_(None)]
    if query.post_id is not None:
        where.append(Comment.media_item_id == query.post_id)
    if query.account_id is not None:
        where.append(Comment.social_account_id == query.account_id)
    if query.contact_id is not None:
        where.append(Comment.contact_id == query.contact_id)
    if query.start is not None:
        where.append(Comment.commented_at >= query.start)
    if query.end is not None:
        where.append(Comment.commented_at < query.end)
    if query.q and query.q.strip():
        where.append(Comment.text.ilike(f"%{escape_like(query.q.strip())}%", escape="\\"))
    if query.replied is not None:
        replied = Comment.our_replied_at.is_not(None) | Comment.private_reply_message_id.is_not(
            None
        )
        where.append(replied if query.replied else ~replied)
    return where


def _analysis_filters(query: CommentQuery) -> list[ColumnElement[bool]]:
    where: list[ColumnElement[bool]] = []
    if query.sentiment is not None:
        where.append(CommentAnalysis.sentiment == query.sentiment)
    if query.intents:
        where.append(CommentAnalysis.intent.in_(query.intents))
    if query.topic and query.topic.strip():
        pattern = f"%{escape_like(query.topic.strip().casefold())}%"
        where.append(func.lower(CommentAnalysis.topic).like(pattern, escape="\\"))
    analysed = bool(where) or query.spam is True
    if query.spam is True:
        where.append(CommentAnalysis.is_spam.is_(True))
    elif query.spam is False:
        # Not spam: analysed as not spam, or (without analysis filters) not analysed yet.
        not_spam = CommentAnalysis.is_spam.is_not(True)
        where.append(not_spam)
    if analysed:
        where.append(Comment.analysis_status == AnalysisStatus.DONE)
    return where


async def find_comments(session: AsyncSession, query: CommentQuery, *, limit: int) -> FoundComments:
    """Comments matching ``query``, newest first, with the counts an answer states (FR-AGT-04,
    FR-AGT-06): how many match, how many are in scope and how many of those aren't analysed."""
    scope = _scope(query)
    joined = (
        select(Comment.id)
        .outerjoin(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
        .where(*scope, *_analysis_filters(query))
    )
    total = await session.scalar(select(func.count()).select_from(joined.subquery()))
    counts = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(Comment.analysis_status == AnalysisStatus.PENDING),
                func.count().filter(Comment.analysis_status == AnalysisStatus.SKIPPED),
            )
            .select_from(Comment)
            .where(*scope)
        )
    ).one()
    ids = (
        await session.scalars(
            joined.order_by(Comment.commented_at.desc(), Comment.id.desc()).limit(limit)
        )
    ).all()
    rows = {row.comment.id: row for row in await comments_repo.rows_for(session, ids)}
    return FoundComments(
        rows=[rows[i] for i in ids if i in rows],
        total=int(total or 0),
        in_scope=int(counts[0] or 0),
        pending=int(counts[1] or 0),
        skipped=int(counts[2] or 0),
    )


# Instagram's private-reply window (actions.PRIVATE_REPLY_LIMIT): the badge counts what can still be
# answered in every way.
NEEDS_REPLY_WINDOW = timedelta(days=7)


async def comment_counts(session: AsyncSession, *, now: datetime) -> CommentCounts:
    """The Comments nav badge. A comment needs a reply when the account has not replied to it,
    publicly or privately (``CommentQuery.replied``), it is not spam (unanalysed included, as
    ``CommentQuery.spam=False``), it is neither hidden nor deleted, and it came in the last 7 days
    (Instagram's private-reply window). The window keeps the count to what can still be answered:
    the backfill on connect brings in older comments, and replies made in the Instagram app are
    never stored, so those would otherwise wait forever."""
    query = CommentQuery(start=now - NEEDS_REPLY_WINDOW, replied=False)
    needs_reply = await session.scalar(
        select(func.count())
        .select_from(Comment)
        .outerjoin(CommentAnalysis, CommentAnalysis.comment_id == Comment.id)
        .where(*_scope(query), *_analysis_filters(query), Comment.hidden.is_(False))
    )
    return CommentCounts(needs_reply=int(needs_reply or 0))


@dataclass(frozen=True)
class FoundPosts:
    items: list[MediaItem]  # newest first, at most the limit
    total: int


async def find_posts(
    session: AsyncSession,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    media_types: Sequence[str] | None = None,
    account_id: uuid.UUID | None = None,
    q: str | None = None,
    limit: int,
) -> FoundPosts:
    """Posts published in [start, end), of these media types (stories only when asked for),
    on one account, whose caption contains ``q``; newest first, and how many match (Ask Social
    Hood's get_posts, get_latest_post and search_posts, TA.4)."""
    where: list[ColumnElement[bool]] = []
    if media_types:
        where.append(MediaItem.media_type.in_(list(media_types)))
    else:
        where.append(MediaItem.media_type != MediaType.STORY)
    if start is not None:
        where.append(MediaItem.posted_at >= start)
    if end is not None:
        where.append(MediaItem.posted_at < end)
    if account_id is not None:
        where.append(MediaItem.social_account_id == account_id)
    if q and q.strip():
        where.append(MediaItem.caption.ilike(f"%{escape_like(q.strip())}%", escape="\\"))
    total = await session.scalar(select(func.count()).select_from(MediaItem).where(*where))
    items = await session.scalars(
        select(MediaItem)
        .where(*where)
        .order_by(MediaItem.posted_at.desc(), MediaItem.id.desc())
        .limit(limit)
    )
    return FoundPosts(items=list(items.all()), total=int(total or 0))


async def list_comments(
    session: AsyncSession,
    post_id: uuid.UUID,
    *,
    comment_filter: CommentFilter,
    cursor: str | None,
    limit: int,
) -> CommentList:
    item = await post_or_404(session, post_id)
    rows = await comments_repo.list_for_post(
        session,
        item.id,
        condition=filter_condition(comment_filter),
        after=decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )
    page = rows[:limit]
    last = page[-1].comment if page else None
    return CommentList(
        items=[views.row_out(row) for row in page],
        next_cursor=(
            encode_cursor(last.commented_at, last.id) if len(rows) > limit and last else None
        ),
    )
