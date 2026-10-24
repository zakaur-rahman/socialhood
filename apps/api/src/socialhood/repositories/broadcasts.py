"""Broadcast reads (GR-23): the recipients' status, the counts, the quota and the pacing.

A recipient's status is read from the message it carries, so WhatsApp's delivery statuses
(services/whatsapp_status) are the only place that moves it: ``status_expr`` is the one definition
of what a recipient shows (queued, sent, delivered, read, failed or skipped). The session's tenant
filter limits every query to the current workspace; ``due`` and ``sending`` are the two lookups
the job runs across workspaces (inside tenant_bypass_scope, jobs/ only).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.broadcasts import (
    Broadcast,
    BroadcastRecipient,
    BroadcastStatus,
    RecipientState,
)
from socialhood.models.inbox import Message, MessageStatus
from socialhood.repositories.base import scoped_delete, scoped_update

# What a recipient with a message shows, from the message's status (a message still queued or
# being sent is "queued": it has not reached WhatsApp yet).
_FROM_MESSAGE = case(
    (Message.status == MessageStatus.READ, "read"),
    (Message.status == MessageStatus.DELIVERED, "delivered"),
    (Message.status == MessageStatus.SENT, "sent"),
    (Message.status == MessageStatus.FAILED, "failed"),
    else_="queued",
)
status_expr = case(
    (BroadcastRecipient.state == RecipientState.SKIPPED, "skipped"),
    (BroadcastRecipient.state == RecipientState.FAILED, "failed"),
    (BroadcastRecipient.message_id.is_(None), "queued"),
    else_=_FROM_MESSAGE,
)

STATUSES = ("queued", "sent", "delivered", "read", "failed", "skipped")


def _joined(query: Any) -> Any:
    return query.select_from(BroadcastRecipient).outerjoin(
        Message, Message.id == BroadcastRecipient.message_id
    )


async def counts(session: AsyncSession, broadcast_id: uuid.UUID) -> dict[str, int]:
    """Recipients by status, plus ``replied`` and ``stopped``, for one broadcast."""
    rows = (
        await session.execute(
            _joined(select(status_expr, func.count()))
            .where(BroadcastRecipient.broadcast_id == broadcast_id)
            .group_by(status_expr)
        )
    ).all()
    out = {status: 0 for status in STATUSES}
    for status, count in rows:
        out[status] = int(count)
    replied, stopped = (
        await session.execute(
            select(
                func.count(BroadcastRecipient.replied_at),
                func.count(BroadcastRecipient.stopped_at),
            ).where(BroadcastRecipient.broadcast_id == broadcast_id)
        )
    ).one()
    out["replied"] = int(replied)
    out["stopped"] = int(stopped)
    out["total"] = sum(out[status] for status in STATUSES)
    return out


async def counts_for(
    session: AsyncSession, broadcast_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    """``counts`` for several broadcasts (the list page), two queries in all."""
    out = {
        b: {**{status: 0 for status in STATUSES}, "replied": 0, "stopped": 0, "total": 0}
        for b in broadcast_ids
    }
    if not broadcast_ids:
        return out
    rows = (
        await session.execute(
            _joined(select(BroadcastRecipient.broadcast_id, status_expr, func.count()))
            .where(BroadcastRecipient.broadcast_id.in_(broadcast_ids))
            .group_by(BroadcastRecipient.broadcast_id, status_expr)
        )
    ).all()
    for broadcast_id, status, count in rows:
        out[broadcast_id][status] = int(count)
        out[broadcast_id]["total"] += int(count)
    extra = (
        await session.execute(
            select(
                BroadcastRecipient.broadcast_id,
                func.count(BroadcastRecipient.replied_at),
                func.count(BroadcastRecipient.stopped_at),
            )
            .where(BroadcastRecipient.broadcast_id.in_(broadcast_ids))
            .group_by(BroadcastRecipient.broadcast_id)
        )
    ).all()
    for broadcast_id, replied, stopped in extra:
        out[broadcast_id]["replied"] = int(replied)
        out[broadcast_id]["stopped"] = int(stopped)
    return out


async def recipient_page(
    session: AsyncSession,
    broadcast_id: uuid.UUID,
    *,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Any], int]:
    """(rows, total): each row is (recipient, status, message), by position."""
    base = _joined(select(BroadcastRecipient, status_expr.label("shown"), Message)).where(
        BroadcastRecipient.broadcast_id == broadcast_id
    )
    total_query = _joined(select(func.count())).where(
        BroadcastRecipient.broadcast_id == broadcast_id
    )
    if status is not None:
        base = base.where(status_expr == status)
        total_query = total_query.where(status_expr == status)
    rows = (
        await session.execute(
            base.order_by(BroadcastRecipient.position).limit(limit).offset(offset)
        )
    ).all()
    total = int(await session.scalar(total_query) or 0)
    return list(rows), total


async def dispatched_since(
    session: AsyncSession, since: datetime, until: datetime | None = None
) -> int:
    """Recipients handed to the send queue in [since, until): the quota's count."""
    query = select(func.count()).where(BroadcastRecipient.dispatched_at >= since)
    if until is not None:
        query = query.where(BroadcastRecipient.dispatched_at < until)
    return int(await session.scalar(query) or 0)


async def dispatch_times(
    session: AsyncSession, account_id: uuid.UUID, since: datetime
) -> list[datetime]:
    """When people were messaged by broadcasts on one number since ``since``: the daily limit's
    count. (Replies inside the 24-hour window are not counted; WhatsApp counts conversations
    started with a template.)"""
    rows = await session.scalars(
        select(BroadcastRecipient.dispatched_at)
        .join(Broadcast, Broadcast.id == BroadcastRecipient.broadcast_id)
        .where(
            Broadcast.social_account_id == account_id,
            BroadcastRecipient.dispatched_at >= since,
        )
    )
    return [t for t in rows.all() if t is not None]


async def pending_batch(
    session: AsyncSession, broadcast_id: uuid.UUID, limit: int
) -> list[BroadcastRecipient]:
    """The next recipients to hand over, in order, locked so two runs never take the same ones."""
    rows = await session.scalars(
        select(BroadcastRecipient)
        .where(
            BroadcastRecipient.broadcast_id == broadcast_id,
            BroadcastRecipient.state == RecipientState.PENDING,
        )
        .order_by(BroadcastRecipient.position)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(rows.all())


async def waiting(session: AsyncSession, broadcast_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count()).where(
                BroadcastRecipient.broadcast_id == broadcast_id,
                BroadcastRecipient.state == RecipientState.PENDING,
            )
        )
        or 0
    )


async def due(session: AsyncSession, *, now: datetime, limit: int) -> list[Broadcast]:
    """Scheduled broadcasts whose time has come, across workspaces (tenant_bypass_scope), locked."""
    rows = await session.scalars(
        select(Broadcast)
        .where(Broadcast.status == BroadcastStatus.SCHEDULED, Broadcast.scheduled_at <= now)
        .order_by(Broadcast.scheduled_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(rows.all())


async def sending(session: AsyncSession, *, limit: int) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """(workspace, broadcast) of broadcasts that are sending, across workspaces."""
    rows = await session.execute(
        select(Broadcast.workspace_id, Broadcast.id)
        .where(Broadcast.status == BroadcastStatus.SENDING)
        .order_by(Broadcast.started_at)
        .limit(limit)
    )
    return [(w, b) for w, b in rows.all()]


async def skip_pending(session: AsyncSession, broadcast_id: uuid.UUID, reason: str) -> int:
    """Everyone still waiting is skipped with ``reason`` (a cancelled broadcast)."""
    result = await session.execute(
        scoped_update(BroadcastRecipient, broadcast_id=broadcast_id, state=RecipientState.PENDING)
        .values(state=RecipientState.SKIPPED, skip_reason=reason)
        .returning(BroadcastRecipient.id)
    )
    return len(result.all())


async def delete_broadcast(session: AsyncSession, broadcast_id: uuid.UUID) -> None:
    await session.execute(scoped_delete(Broadcast, id=broadcast_id))
