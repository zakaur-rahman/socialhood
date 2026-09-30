"""Outbound message rows for the send pipeline (T3.6). Tenant-scoped: every write is limited to the
current workspace, and status changes are conditional so two workers never both own a send."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from sqlalchemy import and_, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import Comment
from socialhood.models.inbox import Message, MessageSource, MessageStatus
from socialhood.repositories.base import scoped_update

IN_FLIGHT = (MessageStatus.QUEUED, MessageStatus.SENDING)
# A late platform confirmation may still move these to sent; delivered and read never go back.
NOT_YET_SENT = (MessageStatus.QUEUED, MessageStatus.SENDING, MessageStatus.FAILED)


async def get(session: AsyncSession, message_id: uuid.UUID) -> Message | None:
    return (await session.scalars(select(Message).where(Message.id == message_id))).one_or_none()


async def find_by_client_id(
    session: AsyncSession, conversation_id: uuid.UUID, client_id: uuid.UUID
) -> Message | None:
    return (
        await session.scalars(
            select(Message).where(
                Message.conversation_id == conversation_id, Message.client_id == client_id
            )
        )
    ).one_or_none()


async def claim(
    session: AsyncSession, message_id: uuid.UUID, *, from_status: str, **values: Any
) -> bool:
    """Move a message to ``sending`` if it is still in ``from_status``; False if someone else
    changed it first."""
    result = await session.execute(
        scoped_update(Message, id=message_id)
        .where(Message.status == from_status)
        .values(status=MessageStatus.SENDING, error_code=None, error_message=None, **values)
        .returning(Message.id)
    )
    return result.first() is not None


async def update(session: AsyncSession, message_id: uuid.UUID, **values: Any) -> None:
    await session.execute(scoped_update(Message, id=message_id).values(**values))


async def mark_sent(
    session: AsyncSession, message_id: uuid.UUID, *, platform_message_id: str | None, at: datetime
) -> bool:
    """Record the platform's confirmation. Echo reconciliation may have done it already, and a
    confirmation after the sweeper gave up still wins: the platform has the message."""
    values: dict[str, Any] = {
        "status": MessageStatus.SENT,
        "sent_at": at,
        "error_code": None,
        "error_message": None,
    }
    if platform_message_id:
        values["platform_message_id"] = platform_message_id
    result = await session.execute(
        scoped_update(Message, id=message_id)
        .where(Message.status.in_(NOT_YET_SENT))
        .values(**values)
        .returning(Message.id)
    )
    return result.first() is not None


async def mark_failed(
    session: AsyncSession,
    message_id: uuid.UUID,
    *,
    code: str,
    message: str,
    only_from: Sequence[str] = IN_FLIGHT,
) -> bool:
    result = await session.execute(
        scoped_update(Message, id=message_id)
        .where(Message.status.in_(only_from))
        .values(status=MessageStatus.FAILED, error_code=code, error_message=message)
        .returning(Message.id)
    )
    return result.first() is not None


async def requeue_failed(session: AsyncSession, message_id: uuid.UUID) -> bool:
    """Retry (F-07): ``failed`` back to ``queued``; False when it is no longer failed."""
    result = await session.execute(
        scoped_update(Message, id=message_id)
        .where(Message.status == MessageStatus.FAILED)
        .values(status=MessageStatus.QUEUED, error_code=None, error_message=None)
        .returning(Message.id)
    )
    return result.first() is not None


class InFlight(NamedTuple):
    id: uuid.UUID
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID
    status: str
    # A queued row that is a member's private reply (T6.3): the comment it answers. Only
    # send_private_reply sends it; send_message would send it as a plain DM.
    comment_id: uuid.UUID | None = None


async def in_flight(
    session: AsyncSession,
    *,
    queued_before: datetime,
    sending_before: datetime,
    limit: int = 500,
    replies_within: timedelta = timedelta(days=7),
) -> list[InFlight]:
    """Outbound rows that have not moved for a while (ix_messages_in_flight). Callers in jobs/
    run this across workspaces.

    A queued private reply is a member's (source human; the automations' are stored ``sending``,
    services/automations/queue) linked from ``comments.private_reply_message_id``. Its comment is
    looked up among the workspace's comments made within ``replies_within`` (Instagram's 7 days)
    before the message, since none is queued for an older comment: ix_comments_workspace_commented
    finds it without reading every comment."""
    reply_to = (
        select(Comment.id)
        .where(
            Comment.workspace_id == Message.workspace_id,
            Comment.commented_at >= Message.occurred_at - replies_within,
            Comment.private_reply_message_id == Message.id,
        )
        .limit(1)
        .scalar_subquery()
    )
    private_reply = and_(
        Message.status == MessageStatus.QUEUED, Message.source == MessageSource.HUMAN
    )
    rows = await session.execute(
        select(
            Message.id,
            Message.workspace_id,
            Message.conversation_id,
            Message.status,
            case((private_reply, reply_to), else_=None),
        )
        .where(
            or_(
                (Message.status == MessageStatus.QUEUED) & (Message.updated_at < queued_before),
                (Message.status == MessageStatus.SENDING) & (Message.updated_at < sending_before),
            )
        )
        .order_by(Message.updated_at)
        .limit(limit)
    )
    return [InFlight(r[0], r[1], r[2], str(r[3]), r[4]) for r in rows.all()]
