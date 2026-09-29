"""Message analyses (T5.2; TR-AI-05, FR-AI-04) and the conversation signals they cache, plus the
cross-workspace lookup of follow-up reminders that are due (T5.11; F-18). Tenant-scoped unless a
function says otherwise (TR-TEN-04)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.ai import MessageAnalysis
from socialhood.models.inbox import (
    Conversation,
    ConversationStatus,
    Direction,
    Message,
    MessageSource,
)
from socialhood.repositories.base import scoped_update

_FRESH = {"populate_existing": True}


async def insert_analysis(session: AsyncSession, values: dict[str, Any]) -> MessageAnalysis | None:
    """Store a message's analysis once; None when the message already has one."""
    statement = (
        insert(MessageAnalysis)
        .values(workspace_id=require_workspace(), **values)
        .on_conflict_do_nothing(index_elements=[MessageAnalysis.message_id])
        .returning(MessageAnalysis)
    )
    return (await session.scalars(statement, execution_options=_FRESH)).one_or_none()


async def get(session: AsyncSession, analysis_id: uuid.UUID) -> MessageAnalysis | None:
    return (
        await session.scalars(select(MessageAnalysis).where(MessageAnalysis.id == analysis_id))
    ).one_or_none()


async def exists_for_message(session: AsyncSession, message_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(MessageAnalysis.id).where(MessageAnalysis.message_id == message_id)
    )
    return found is not None


async def latest(session: AsyncSession, conversation_id: uuid.UUID) -> MessageAnalysis | None:
    """The conversation's newest analysis (its newest analysed customer message)."""
    return (
        await session.scalars(
            select(MessageAnalysis)
            .join(Message, Message.id == MessageAnalysis.message_id)
            .where(MessageAnalysis.conversation_id == conversation_id)
            .order_by(Message.occurred_at.desc(), MessageAnalysis.created_at.desc())
            .limit(1)
        )
    ).first()


async def correct(
    session: AsyncSession, analysis_id: uuid.UUID, values: dict[str, Any]
) -> MessageAnalysis | None:
    """FR-AI-04: store a member's correction; the updated row."""
    statement = (
        scoped_update(MessageAnalysis, id=analysis_id)
        .values(**values, updated_at=func.now())
        .returning(MessageAnalysis)
    )
    return (await session.scalars(statement, execution_options=_FRESH)).one_or_none()


async def recent_messages(
    session: AsyncSession, conversation_id: uuid.UUID, limit: int
) -> list[Message]:
    """The conversation's last ``limit`` customer and business messages, oldest first (system
    notes are not part of the conversation the model reads)."""
    rows = (
        await session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id, Message.direction != Direction.SYSTEM
            )
            .order_by(Message.occurred_at.desc(), Message.id.desc())
            .limit(limit)
        )
    ).all()
    return list(reversed(rows))


async def newest_customer_message_id(
    session: AsyncSession, conversation_id: uuid.UUID
) -> uuid.UUID | None:
    """The newest message the customer wrote (and did not unsend)."""
    return await session.scalar(
        select(Message.id)
        .where(
            Message.conversation_id == conversation_id,
            Message.direction == Direction.INBOUND,
            Message.source == MessageSource.CUSTOMER,
            Message.deleted_at.is_(None),
        )
        .order_by(Message.occurred_at.desc(), Message.id.desc())
        .limit(1)
    )


async def messages_since(
    session: AsyncSession, conversation_id: uuid.UUID, since: datetime | None
) -> int:
    """Customer and business messages after ``since`` (all of them when None): the summary
    trigger (FR-AI-03). System notes do not count."""
    query = (
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == conversation_id, Message.direction != Direction.SYSTEM)
    )
    if since is not None:
        query = query.where(Message.occurred_at > since)
    return int(await session.scalar(query) or 0)


async def lock_due_reminders(
    session: AsyncSession,
    *,
    now: datetime,
    lead_score: int,
    wrote_between: tuple[timedelta, timedelta],
    quiet_for: timedelta,
    limit: int,
) -> list[Conversation]:
    """F-18: open conversations with a lead whose customer last wrote between
    ``wrote_between`` ago, not yet reminded for that message, and no business message for
    ``quiet_for``; locked so two runs never remind twice. Across workspaces: the caller opens
    tenant_bypass_scope (jobs/ only)."""
    newest, oldest = wrote_between
    statement = (
        select(Conversation)
        .where(
            Conversation.status == ConversationStatus.OPEN,
            Conversation.lead_score >= lead_score,
            Conversation.last_inbound_at <= now - newest,
            Conversation.last_inbound_at >= now - oldest,
            Conversation.window_reminder_for.is_distinct_from(Conversation.last_inbound_at),
            or_(
                Conversation.last_outbound_at.is_(None),
                Conversation.last_outbound_at < now - quiet_for,
            ),
        )
        .order_by(Conversation.last_inbound_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list((await session.scalars(statement, execution_options=_FRESH)).all())
