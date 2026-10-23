"""Entry links (GR-08) and the counts behind their stats. Tenant-scoped: reads are filtered by the
session's workspace, inserts are stamped with it, and writes go through ``scoped_update`` and
``scoped_delete``."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.automations import Automation, AutomationRun, EntryLink
from socialhood.models.inbox import Conversation, Direction, Message, MessageSource
from socialhood.repositories.base import scoped_delete, scoped_update

_FRESH = {"populate_existing": True}


async def insert_link(session: AsyncSession, values: dict[str, Any]) -> EntryLink | None:
    """None when the account already has a link with this code."""
    statement = (
        insert(EntryLink)
        .values(workspace_id=require_workspace(), **values)
        .on_conflict_do_nothing(index_elements=["social_account_id", "code"])
        .returning(EntryLink)
    )
    return (await session.scalars(statement, execution_options=_FRESH)).one_or_none()


async def get(session: AsyncSession, link_id: uuid.UUID) -> EntryLink | None:
    return await session.get(EntryLink, link_id)


async def get_by_code(
    session: AsyncSession, social_account_id: uuid.UUID, code: str
) -> EntryLink | None:
    return await session.scalar(
        select(EntryLink).where(
            EntryLink.social_account_id == social_account_id, EntryLink.code == code
        )
    )


async def list_links(
    session: AsyncSession, *, account_id: uuid.UUID | None = None
) -> list[EntryLink]:
    statement = select(EntryLink).order_by(EntryLink.created_at.desc(), EntryLink.id.desc())
    if account_id is not None:
        statement = statement.where(EntryLink.social_account_id == account_id)
    return list((await session.scalars(statement)).all())


async def update_link(session: AsyncSession, link_id: uuid.UUID, **values: Any) -> None:
    await session.execute(scoped_update(EntryLink, id=link_id).values(**values))


async def delete_link(session: AsyncSession, link_id: uuid.UUID) -> None:
    await session.execute(scoped_delete(EntryLink, id=link_id))


async def has_inbound_since(
    session: AsyncSession, conversation_id: uuid.UUID, *, since: datetime, before: Message
) -> bool:
    """Whether the conversation has a customer message from ``since`` up to (not including)
    ``before``: they had already written after the referral."""
    found = await session.scalar(
        select(Message.id)
        .where(
            Message.conversation_id == conversation_id,
            Message.direction == Direction.INBOUND,
            Message.source == MessageSource.CUSTOMER,
            Message.occurred_at >= since,
            Message.occurred_at < before.occurred_at,
            Message.id != before.id,
        )
        .limit(1)
    )
    return found is not None


async def opened_counts(
    session: AsyncSession, account_id: uuid.UUID, codes: Sequence[str]
) -> dict[str, int]:
    """Conversations that began from each link: the entry source is a link and the entry ref is
    the link's code."""
    if not codes:
        return {}
    rows = await session.execute(
        select(Conversation.entry_ref, func.count())
        .where(
            Conversation.social_account_id == account_id,
            Conversation.entry_source == "link",
            Conversation.entry_ref.in_(list(codes)),
        )
        .group_by(Conversation.entry_ref)
    )
    return {str(ref): int(count) for ref, count in rows.all()}


async def run_counts(
    session: AsyncSession, account_id: uuid.UUID, codes: Sequence[str]
) -> dict[str, int]:
    """Runs that began from each link: runs of entry link automations on conversations whose entry
    is the link."""
    if not codes:
        return {}
    rows = await session.execute(
        select(Conversation.entry_ref, func.count(AutomationRun.id))
        .join(Conversation, Conversation.id == AutomationRun.conversation_id)
        .join(Automation, Automation.id == AutomationRun.automation_id)
        .where(
            Conversation.social_account_id == account_id,
            Conversation.entry_source == "link",
            Conversation.entry_ref.in_(list(codes)),
            Automation.trigger == "entry_link",
        )
        .group_by(Conversation.entry_ref)
    )
    return {str(ref): int(count) for ref, count in rows.all()}


async def automation_names(
    session: AsyncSession, automation_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not automation_ids:
        return {}
    rows = await session.execute(
        select(Automation.id, Automation.name).where(Automation.id.in_(list(automation_ids)))
    )
    return {automation_id: name for automation_id, name in rows.all()}
