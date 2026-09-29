"""API projections of posts and comments (schemas/posts.py; FR-CMT-03, FR-CMT-04) and the events
that carry them (TR-RT-03): comment.created and comment.updated carry ``{comment: Comment}``,
post.updated carries ``{post: PostDetail}``, so open pages patch their caches without a refetch.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.analytics import CommentAnalysis
from socialhood.models.automations import Comment
from socialhood.models.media import MediaItem
from socialhood.realtime import events
from socialhood.repositories import comments as comments_repo
from socialhood.repositories.comments import CommentRow
from socialhood.schemas.posts import Comment as CommentOut
from socialhood.schemas.posts import CommentAnalysis as CommentAnalysisOut
from socialhood.schemas.posts import (
    CommentPrivateReply,
    CommentPublicReply,
    CommentStats,
    PostDetail,
    PostSummary,
    PostTopic,
)


def post_summary(item: MediaItem) -> PostSummary:
    return PostSummary(
        id=item.id,
        social_account_id=item.social_account_id,
        platform_media_id=item.platform_media_id,
        media_type=item.media_type,
        caption=item.caption,
        media_url=item.media_url,
        thumbnail_url=item.thumbnail_url,
        permalink=item.permalink,
        posted_at=item.posted_at,
        like_count=item.like_count,
        comments_count=item.comments_count,
        stats=CommentStats.from_stored(item.comment_stats),
    )


def topics_of(raw: Sequence[Any] | None) -> list[PostTopic]:
    """The stored topic labels, largest first; a malformed entry is left out."""
    topics: list[PostTopic] = []
    for entry in raw or []:
        try:
            topics.append(PostTopic.model_validate(entry))
        except ValidationError:
            continue
    return sorted(topics, key=lambda t: (-t.count, t.label))


def post_detail(item: MediaItem) -> PostDetail:
    return PostDetail(
        **post_summary(item).model_dump(),
        summary=item.summary,
        summary_updated_at=item.summary_updated_at,
        topics=topics_of(item.topics),
    )


def analysis_out(row: CommentAnalysis | None) -> CommentAnalysisOut | None:
    if row is None:
        return None
    return CommentAnalysisOut.model_validate(
        {
            "sentiment": row.sentiment,
            "sentiment_score": row.sentiment_score,
            "intent": row.intent,
            "is_spam": row.is_spam,
            "topic": row.topic,
        }
    )


def comment_out(
    comment: Comment,
    analysis: CommentAnalysis | None,
    *,
    profile_picture_url: str | None = None,
    private_reply_conversation_id: uuid.UUID | None = None,
) -> CommentOut:
    public_reply = None
    if comment.our_reply_text and comment.our_replied_at:
        public_reply = CommentPublicReply(
            text=comment.our_reply_text,
            platform_id=comment.our_reply_platform_id,
            replied_at=comment.our_replied_at,
        )
    private_reply = None
    if comment.private_reply_message_id and private_reply_conversation_id:
        private_reply = CommentPrivateReply(
            message_id=comment.private_reply_message_id,
            conversation_id=private_reply_conversation_id,
        )
    return CommentOut.model_validate(
        {
            "id": comment.id,
            "post_id": comment.media_item_id,
            "social_account_id": comment.social_account_id,
            "contact_id": comment.contact_id,
            "platform_comment_id": comment.platform_comment_id,
            "parent_platform_comment_id": comment.parent_platform_comment_id,
            "author_username": comment.author_username,
            "author_profile_picture_url": profile_picture_url,
            "text": comment.text,
            "like_count": comment.like_count,
            "hidden": comment.hidden,
            "commented_at": comment.commented_at,
            "deleted_at": comment.deleted_at,
            "analysis_status": comment.analysis_status,
            "analysis": analysis_out(analysis) if comment.analysis_status == "done" else None,
            "public_reply": public_reply,
            "private_reply": private_reply,
        }
    )


def row_out(row: CommentRow) -> CommentOut:
    return comment_out(
        row.comment,
        row.analysis,
        profile_picture_url=row.profile_picture_url,
        private_reply_conversation_id=row.private_reply_conversation_id,
    )


async def comments_out(
    session: AsyncSession, comment_ids: Collection[uuid.UUID]
) -> list[CommentOut]:
    """Fresh projections of the comments, read after the caller's changes were flushed."""
    return [row_out(row) for row in await comments_repo.rows_for(session, comment_ids)]


# ---------------------------------------------------------------- events (TR-RT-03)


def queue_comment(
    session: AsyncSession, workspace_id: uuid.UUID, out: CommentOut, *, created: bool = False
) -> None:
    events.queue(
        session,
        workspace_id,
        "comment.created" if created else "comment.updated",
        {"comment": out.model_dump(mode="json")},
    )


async def queue_comments(
    session: AsyncSession, comment_ids: Collection[uuid.UUID], *, created: bool = False
) -> list[CommentOut]:
    """Queue comment.updated (or created) for each comment as it now is; returns them."""
    outs: list[CommentOut] = []
    for row in await comments_repo.rows_for(session, comment_ids):
        out = row_out(row)
        queue_comment(session, row.comment.workspace_id, out, created=created)
        outs.append(out)
    return outs


def queue_post(session: AsyncSession, item: MediaItem) -> PostDetail:
    detail = post_detail(item)
    events.queue(
        session, item.workspace_id, "post.updated", {"post": detail.model_dump(mode="json")}
    )
    return detail
