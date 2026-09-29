"""Comments and the posts they are on, for comment intake and comment automations (F-12, T4.4), and
the post detail's comment list and comment actions (T6.3; FR-CMT-04, UX-SCR-05). Tenant-scoped:
reads are filtered by the session's workspace and inserts are stamped with it."""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import ColumnElement, DateTime, Uuid, and_, exists, literal, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.analytics import CommentAnalysis
from socialhood.models.automations import AutomationRun, Comment, RunResult
from socialhood.models.inbox import Contact, Message
from socialhood.models.media import MediaItem
from socialhood.platforms.base import PlatformMedia

_FRESH = {"populate_existing": True}


class CommentRow(NamedTuple):
    """A comment with what its API projection needs (schemas/posts.py Comment)."""

    comment: Comment
    analysis: CommentAnalysis | None
    profile_picture_url: str | None
    private_reply_conversation_id: uuid.UUID | None


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


async def _rows(session: AsyncSession, comments: Sequence[Comment]) -> list[CommentRow]:
    """Each comment with its analysis, the commenter's picture and its private reply's
    conversation, read by id (one small query each, whatever the join estimates)."""
    ids = [c.id for c in comments]
    analyses = {
        a.comment_id: a
        for a in (
            await session.scalars(
                select(CommentAnalysis).where(CommentAnalysis.comment_id.in_(ids)),
                execution_options=_FRESH,
            )
        ).all()
    }
    contact_ids = {c.contact_id for c in comments if c.contact_id}
    pictures: dict[uuid.UUID, str | None] = {}
    if contact_ids:
        rows = await session.execute(
            select(Contact.id, Contact.profile_picture_url).where(Contact.id.in_(contact_ids))
        )
        pictures = {contact_id: picture for contact_id, picture in rows.all()}
    message_ids = {c.private_reply_message_id for c in comments if c.private_reply_message_id}
    conversations: dict[uuid.UUID, uuid.UUID] = {}
    if message_ids:
        linked = await session.execute(
            select(Message.id, Message.conversation_id).where(Message.id.in_(message_ids))
        )
        conversations = {message_id: conv for message_id, conv in linked.all()}
    return [
        CommentRow(
            c,
            analyses.get(c.id),
            pictures.get(c.contact_id) if c.contact_id else None,
            conversations.get(c.private_reply_message_id) if c.private_reply_message_id else None,
        )
        for c in comments
    ]


async def rows_for(session: AsyncSession, comment_ids: Collection[uuid.UUID]) -> list[CommentRow]:
    """Fresh rows for the comments' API projection (events after a change)."""
    if not comment_ids:
        return []
    result = await session.scalars(
        select(Comment).where(Comment.id.in_(list(comment_ids))).order_by(Comment.id),
        execution_options=_FRESH,
    )
    return await _rows(session, list(result.all()))


async def list_for_post(
    session: AsyncSession,
    media_item_id: uuid.UUID,
    *,
    condition: ColumnElement[bool] | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[CommentRow]:
    """The post's comments that are not deleted, newest first (ix_comments_media_commented),
    narrowed by ``condition`` (on Comment and its outer-joined CommentAnalysis); ``after`` is the
    last row of the previous page. Returns up to ``limit`` rows."""
    statement = select(Comment).where(
        Comment.media_item_id == media_item_id, Comment.deleted_at.is_(None)
    )
    if condition is not None:
        statement = statement.outerjoin(
            CommentAnalysis, CommentAnalysis.comment_id == Comment.id
        ).where(condition)
    if after is not None:
        statement = statement.where(
            tuple_(Comment.commented_at, Comment.id)
            < tuple_(literal(after[0], DateTime(timezone=True)), literal(after[1], Uuid()))
        )
    result = await session.scalars(
        statement.order_by(Comment.commented_at.desc(), Comment.id.desc()).limit(limit)
    )
    return await _rows(session, list(result.all()))


async def automation_reply_queued(session: AsyncSession, comment_id: uuid.UUID) -> bool:
    """An automation run for the comment is waiting to send its private reply (TR-JOB-07)."""
    return bool(
        await session.scalar(
            select(
                exists().where(
                    and_(
                        AutomationRun.trigger_comment_id == comment_id,
                        AutomationRun.result == RunResult.QUEUED,
                    )
                )
            )
        )
    )


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
