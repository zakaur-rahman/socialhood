"""Post detail and a post's comments (T6.3; FR-CMT-03, FR-CMT-04, UX-SCR-05).

The comment list is newest first (commented_at, then id), paged with the inbox's cursor format, and
narrowed by one filter chip (schemas/posts.py ``CommentFilter``): the sentiment chips and the
intent chips count analysed comments that are not spam, spam counts analysed spam, hidden counts
comments hidden on Instagram. Deleted comments are never listed.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError
from socialhood.models.analytics import CommentAnalysis
from socialhood.models.automations import AnalysisStatus, Comment
from socialhood.models.media import MediaItem
from socialhood.repositories import comments as comments_repo
from socialhood.schemas.posts import (
    COMMENT_FILTER_INTENTS,
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
