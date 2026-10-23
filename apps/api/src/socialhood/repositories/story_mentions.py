"""Story mentions (GR-07). Tenant-scoped: reads are filtered by the session's workspace and inserts
are stamped with it."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Uuid, func, literal, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.automations import StoryMention
from socialhood.models.inbox import Contact, Message


@dataclass(frozen=True)
class MentionRow:
    mention: StoryMention
    contact: Contact
    conversation_id: uuid.UUID


async def insert_mention(session: AsyncSession, values: dict[str, Any]) -> bool:
    """One row per mention message; False when the message already has one (a replay)."""
    statement = (
        insert(StoryMention)
        .values(workspace_id=require_workspace(), **values)
        .on_conflict_do_nothing(index_elements=["message_id"])
        .returning(StoryMention.id)
    )
    return (await session.scalars(statement)).one_or_none() is not None


async def list_page(
    session: AsyncSession,
    *,
    account_id: uuid.UUID | None,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[MentionRow]:
    """Newest first, ``limit`` rows (the caller asks for one more to know whether a next page
    exists)."""
    statement = (
        select(StoryMention, Contact, Message.conversation_id)
        .join(Contact, Contact.id == StoryMention.contact_id)
        .join(Message, Message.id == StoryMention.message_id)
        .order_by(StoryMention.mentioned_at.desc(), StoryMention.id.desc())
        .limit(limit)
    )
    if account_id is not None:
        statement = statement.where(StoryMention.social_account_id == account_id)
    if after is not None:
        statement = statement.where(
            tuple_(StoryMention.mentioned_at, StoryMention.id)
            < tuple_(literal(after[0], DateTime(timezone=True)), literal(after[1], Uuid()))
        )
    rows = await session.execute(statement)
    return [MentionRow(m, c, conversation_id) for m, c, conversation_id in rows.all()]


async def count_since(
    session: AsyncSession, since: datetime, *, account_id: uuid.UUID | None = None
) -> int:
    statement = (
        select(func.count()).select_from(StoryMention).where(StoryMention.mentioned_at >= since)
    )
    if account_id is not None:
        statement = statement.where(StoryMention.social_account_id == account_id)
    return int(await session.scalar(statement) or 0)


async def count_between(session: AsyncSession, since: datetime, until: datetime) -> int:
    """Mentions in [since, until), for the Home overview."""
    return int(
        await session.scalar(
            select(func.count())
            .select_from(StoryMention)
            .where(StoryMention.mentioned_at >= since, StoryMention.mentioned_at < until)
        )
        or 0
    )
