"""Shared inbox lookups (tenant-scoped). Area-specific queries live in their own modules
(repositories/conversations.py, messages.py, scheduled.py, …)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.inbox import Contact, Conversation, Message, ScheduledMessage


async def get_conversation(
    session: AsyncSession, conversation_id: uuid.UUID
) -> Conversation | None:
    return (
        await session.scalars(select(Conversation).where(Conversation.id == conversation_id))
    ).one_or_none()


async def get_message(session: AsyncSession, message_id: uuid.UUID) -> Message | None:
    return (await session.scalars(select(Message).where(Message.id == message_id))).one_or_none()


async def get_contact(session: AsyncSession, contact_id: uuid.UUID) -> Contact | None:
    return (await session.scalars(select(Contact).where(Contact.id == contact_id))).one_or_none()


async def get_scheduled(
    session: AsyncSession, scheduled_message_id: uuid.UUID
) -> ScheduledMessage | None:
    return (
        await session.scalars(
            select(ScheduledMessage).where(ScheduledMessage.id == scheduled_message_id)
        )
    ).one_or_none()


async def find_message_by_platform_id(
    session: AsyncSession, social_account_id: uuid.UUID, platform_message_id: str
) -> Message | None:
    return (
        await session.scalars(
            select(Message).where(
                Message.social_account_id == social_account_id,
                Message.platform_message_id == platform_message_id,
            )
        )
    ).one_or_none()


async def latest_inbound_platform_id(
    session: AsyncSession, conversation_id: uuid.UUID
) -> str | None:
    """The newest customer message's platform id (WhatsApp marks read by message)."""
    return await session.scalar(
        select(Message.platform_message_id)
        .where(
            Message.conversation_id == conversation_id,
            Message.direction == "inbound",
            Message.platform_message_id.is_not(None),
        )
        .order_by(Message.occurred_at.desc(), Message.id.desc())
        .limit(1)
    )
