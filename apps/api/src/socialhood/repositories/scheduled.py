"""Scheduled-message queries (T3.13; F-10, FR-SMS-02, TR-JOB-03).

Tenant-scoped like every repository. The dispatcher and the sweeper look across workspaces: they
call ``lock_due`` and ``lock_stuck`` inside a ``tenant_bypass_scope`` opened in jobs/ (TR-TEN-04).
Rows come back with their conversation's platform and contact, which the API shape needs.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.inbox import Contact, Conversation, Message, ScheduledMessage
from socialhood.models.inbox import ScheduledStatus as S
from socialhood.models.media import MediaAsset

PENDING = (S.SCHEDULED, S.SENDING)
DONE = (S.SENT, S.FAILED, S.EXPIRED)


class ScheduledRow(NamedTuple):
    scheduled: ScheduledMessage
    platform: str
    contact: Contact


def _with_context() -> Select[ScheduledMessage, str, Contact]:
    return (
        select(ScheduledMessage, Conversation.platform, Contact)
        .join(Conversation, Conversation.id == ScheduledMessage.conversation_id)
        .join(Contact, Contact.id == Conversation.contact_id)
    )


async def _fetch(
    session: AsyncSession, statement: Select[ScheduledMessage, str, Contact]
) -> list[ScheduledRow]:
    result = await session.execute(statement)
    return [ScheduledRow(s, p, c) for s, p, c in result.all()]


async def get(
    session: AsyncSession, scheduled_message_id: uuid.UUID, *, for_update: bool = False
) -> ScheduledRow | None:
    """One row; ``for_update`` locks it (not its conversation) until the transaction ends."""
    statement = _with_context().where(ScheduledMessage.id == scheduled_message_id)
    if for_update:
        statement = statement.with_for_update(of=ScheduledMessage)
    rows = await _fetch(session, statement)
    return rows[0] if rows else None


async def lock_sending(
    session: AsyncSession, scheduled_message_id: uuid.UUID
) -> ScheduledRow | None:
    """A claimed row nobody else is sending right now, or None (TR-JOB-03: sends once)."""
    statement = (
        _with_context()
        .where(
            ScheduledMessage.id == scheduled_message_id,
            ScheduledMessage.status == S.SENDING,
            ScheduledMessage.message_id.is_(None),
        )
        .with_for_update(of=ScheduledMessage, skip_locked=True)
    )
    rows = await _fetch(session, statement)
    return rows[0] if rows else None


async def list_pending(
    session: AsyncSession,
    *,
    limit: int,
    after: tuple[datetime, uuid.UUID] | None = None,
    conversation_id: uuid.UUID | None = None,
) -> list[ScheduledRow]:
    """Scheduled and sending rows, soonest first."""
    statement = _with_context().where(ScheduledMessage.status.in_(PENDING))
    if conversation_id is not None:
        statement = statement.where(ScheduledMessage.conversation_id == conversation_id)
    if after is not None:
        statement = statement.where(
            tuple_(ScheduledMessage.send_at, ScheduledMessage.id) > tuple_(*after)
        )
    statement = statement.order_by(ScheduledMessage.send_at, ScheduledMessage.id).limit(limit)
    return await _fetch(session, statement)


async def list_done(
    session: AsyncSession,
    *,
    since: datetime,
    limit: int,
    before: tuple[datetime, uuid.UUID] | None = None,
) -> list[ScheduledRow]:
    """Sent, failed and expired rows due since ``since``, most recent first."""
    statement = _with_context().where(
        ScheduledMessage.status.in_(DONE), ScheduledMessage.send_at >= since
    )
    if before is not None:
        statement = statement.where(
            tuple_(ScheduledMessage.send_at, ScheduledMessage.id) < tuple_(*before)
        )
    statement = statement.order_by(
        ScheduledMessage.send_at.desc(), ScheduledMessage.id.desc()
    ).limit(limit)
    return await _fetch(session, statement)


async def count_pending(session: AsyncSession) -> int:
    """For the pending_scheduled_messages limit (counted live, §5.8)."""
    count = await session.scalar(
        select(func.count())
        .select_from(ScheduledMessage)
        .where(ScheduledMessage.status.in_(PENDING))
    )
    return int(count or 0)


async def existing_asset_ids(
    session: AsyncSession, asset_ids: Sequence[uuid.UUID]
) -> set[uuid.UUID]:
    """The ids among ``asset_ids`` that are media assets of the current workspace."""
    if not asset_ids:
        return set()
    result = await session.scalars(select(MediaAsset.id).where(MediaAsset.id.in_(asset_ids)))
    return set(result.all())


async def find_sent_message(
    session: AsyncSession, conversation_id: uuid.UUID, client_id: uuid.UUID
) -> Message | None:
    """The message an earlier attempt already created for this scheduled message, if any."""
    result = await session.scalars(
        select(Message).where(
            Message.conversation_id == conversation_id, Message.client_id == client_id
        )
    )
    return result.one_or_none()


# ---- across workspaces (the caller in jobs/ opens tenant_bypass_scope)


async def lock_due(session: AsyncSession, now: datetime, limit: int) -> list[ScheduledRow]:
    """TR-JOB-03: due rows, locked so two dispatchers never claim the same one."""
    statement = (
        _with_context()
        .where(ScheduledMessage.status == S.SCHEDULED, ScheduledMessage.send_at <= now)
        .order_by(ScheduledMessage.send_at)
        .limit(limit)
        .with_for_update(of=ScheduledMessage, skip_locked=True)
    )
    return await _fetch(session, statement)


async def lock_stuck(
    session: AsyncSession, claimed_before: datetime, limit: int
) -> list[ScheduledRow]:
    """Rows claimed before ``claimed_before`` that never produced a message. A row a running
    send_scheduled holds is skipped."""
    statement = (
        _with_context()
        .where(
            ScheduledMessage.status == S.SENDING,
            ScheduledMessage.message_id.is_(None),
            ScheduledMessage.claimed_at < claimed_before,
        )
        .order_by(ScheduledMessage.claimed_at)
        .limit(limit)
        .with_for_update(of=ScheduledMessage, skip_locked=True)
    )
    return await _fetch(session, statement)
