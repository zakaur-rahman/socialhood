"""Website chat widget rows and the queries behind its poll (GR-28). Tenant-scoped: callers run
inside the widget's workspace (``workspace_scope``)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import Conversation, Direction, Message, MessageStatus
from socialhood.models.widget import WidgetSettings
from socialhood.repositories.base import scoped_update

# An outbound message is shown to the visitor once it is sent; a queued or failed one is not.
VISIBLE_OUTBOUND = (MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ)
HISTORY_LIMIT = 100


async def find_account(session: AsyncSession) -> SocialAccount | None:
    """The workspace's web account (the earliest if a disconnected one was replaced)."""
    return (
        await session.scalars(
            select(SocialAccount)
            .where(SocialAccount.platform == "web")
            .order_by(SocialAccount.created_at)
            .limit(1)
        )
    ).one_or_none()


async def get_settings(session: AsyncSession, account_id: uuid.UUID) -> WidgetSettings | None:
    return (
        await session.scalars(
            select(WidgetSettings).where(WidgetSettings.social_account_id == account_id)
        )
    ).one_or_none()


async def update_settings(session: AsyncSession, settings_id: uuid.UUID, **values: object) -> None:
    await session.execute(scoped_update(WidgetSettings, id=settings_id).values(**values))


async def count_conversations_since(
    session: AsyncSession, account_id: uuid.UUID, since: datetime
) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.social_account_id == account_id, Conversation.created_at >= since)
    )
    return int(count or 0)


async def find_conversation(
    session: AsyncSession, account_id: uuid.UUID, contact_id: uuid.UUID
) -> Conversation | None:
    return (
        await session.scalars(
            select(Conversation).where(
                Conversation.social_account_id == account_id,
                Conversation.contact_id == contact_id,
            )
        )
    ).one_or_none()


async def recent_visitor_texts(
    session: AsyncSession, conversation_id: uuid.UUID, *, limit: int
) -> list[str]:
    """The visitor's latest messages, newest first (for the repeated-message rule)."""
    rows = await session.scalars(
        select(Message.text)
        .where(
            Message.conversation_id == conversation_id,
            Message.direction == Direction.INBOUND,
            Message.text.is_not(None),
        )
        .order_by(Message.occurred_at.desc(), Message.id.desc())
        .limit(limit)
    )
    return [text for text in rows.all() if text]


def _visible(conversation_id: uuid.UUID) -> tuple[object, ...]:
    return (
        Message.conversation_id == conversation_id,
        Message.deleted_at.is_(None),
        Message.text.is_not(None),
        (Message.direction == Direction.INBOUND)
        | ((Message.direction == Direction.OUTBOUND) & Message.status.in_(VISIBLE_OUTBOUND)),
    )


async def visible_messages(session: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    """What the visitor sees: their messages and the sent replies, oldest first, the latest
    ``HISTORY_LIMIT``."""
    rows = await session.scalars(
        select(Message)
        .where(*_visible(conversation_id))  # type: ignore[arg-type]
        .order_by(Message.occurred_at.desc(), Message.id.desc())
        .limit(HISTORY_LIMIT)
    )
    return list(reversed(rows.all()))


async def fingerprint(session: AsyncSession, conversation_id: uuid.UUID) -> str:
    """A string that changes when a visible message appears or changes; the poll's ``version``."""
    count, newest = (
        await session.execute(
            select(func.count(), func.max(Message.updated_at)).where(
                *_visible(conversation_id)  # type: ignore[arg-type]
            )
        )
    ).one()
    stamp = int(newest.timestamp() * 1_000_000) if newest is not None else 0
    return f"{count}.{stamp}"
