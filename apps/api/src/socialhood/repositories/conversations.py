"""Conversation writes from the inbox (T3.5; FR-INB-04, FR-INB-05): read state, archive and the
AI mode override. Scoped to the current workspace (TR-TEN-04). Each returns whether a row
changed, so callers only announce real changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.inbox import Conversation, ConversationStatus
from socialhood.repositories.base import scoped_update


async def update(session: AsyncSession, conversation_id: uuid.UUID, **values: Any) -> bool:
    statement = (
        scoped_update(Conversation, id=conversation_id).values(**values).returning(Conversation.id)
    )
    return (await session.execute(statement)).first() is not None


async def mark_read(session: AsyncSession, conversation_id: uuid.UUID) -> bool:
    """unread_count = 0; False when it already was."""
    statement = (
        scoped_update(Conversation, id=conversation_id)
        .where(Conversation.unread_count > 0)
        .values(unread_count=0)
        .returning(Conversation.id)
    )
    return (await session.execute(statement)).first() is not None


async def mark_unread(session: AsyncSession, conversation_id: uuid.UUID) -> bool:
    """unread_count = max(1, unread_count); False when it was already unread."""
    statement = (
        scoped_update(Conversation, id=conversation_id)
        .where(Conversation.unread_count < 1)
        .values(unread_count=1)
        .returning(Conversation.id)
    )
    return (await session.execute(statement)).first() is not None


async def lock_due_snoozed(session: AsyncSession, now: datetime, limit: int) -> list[Conversation]:
    """GR-45: open conversations whose snooze has ended, locked so two runs never wake one twice.
    Across workspaces: the caller opens tenant_bypass_scope (jobs/ only, TR-TEN-04)."""
    statement = (
        select(Conversation)
        .where(
            Conversation.snoozed_until.is_not(None),
            Conversation.snoozed_until <= now,
            Conversation.status == ConversationStatus.OPEN,
        )
        .order_by(Conversation.snoozed_until)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(
        (await session.scalars(statement, execution_options={"populate_existing": True})).all()
    )
