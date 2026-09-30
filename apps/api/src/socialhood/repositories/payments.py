"""Dodo payments (§5.8; TR-BIL-02): one row per Dodo payment id, upserted from payment.* events.
A payment never goes back to ``pending``, and a settled one only moves forward (succeeded after a
failed retry, refunded after succeeded), so a late or repeated event can't undo a newer one."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, DateTime, Uuid, case, func, literal, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.billing import Payment, PaymentStatus

RANK = {
    PaymentStatus.PENDING: 0,
    PaymentStatus.FAILED: 1,
    PaymentStatus.SUCCEEDED: 2,
    PaymentStatus.REFUNDED: 3,
}


def _rank(column: Any) -> ColumnElement[int]:
    return case(*((column == status.value, rank) for status, rank in RANK.items()), else_=0)


async def upsert(
    session: AsyncSession,
    *,
    dodo_payment_id: str,
    dodo_subscription_id: str | None,
    status: PaymentStatus,
    amount_minor: int,
    currency: str,
    occurred_at: datetime,
    invoice_url: str | None,
    failure_reason: str | None,
) -> bool:
    """Insert the payment, or update it unless the stored status is further along. True when a
    row was written."""
    workspace_id = require_workspace()
    row = insert(Payment).values(
        workspace_id=workspace_id,
        dodo_payment_id=dodo_payment_id,
        dodo_subscription_id=dodo_subscription_id,
        status=status.value,
        amount_minor=amount_minor,
        currency=currency,
        occurred_at=occurred_at,
        invoice_url=invoice_url,
        failure_reason=failure_reason,
    )
    new = row.excluded
    statement = row.on_conflict_do_update(
        index_elements=[Payment.dodo_payment_id],
        set_={
            "dodo_subscription_id": func.coalesce(
                new.dodo_subscription_id, Payment.dodo_subscription_id
            ),
            "status": new.status,
            "amount_minor": new.amount_minor,
            "currency": new.currency,
            "occurred_at": new.occurred_at,
            "invoice_url": func.coalesce(new.invoice_url, Payment.invoice_url),
            "failure_reason": new.failure_reason,
            "updated_at": func.now(),
        },
        where=(Payment.workspace_id == workspace_id) & (_rank(new.status) >= _rank(Payment.status)),
    ).returning(Payment.id)
    return (await session.execute(statement)).scalar_one_or_none() is not None


async def page(
    session: AsyncSession, *, before: tuple[datetime, uuid.UUID] | None, limit: int
) -> list[Payment]:
    """The workspace's payments, newest first, one more than ``limit`` (the caller pages)."""
    statement = select(Payment).order_by(Payment.occurred_at.desc(), Payment.id.desc())
    if before is not None:
        statement = statement.where(
            tuple_(Payment.occurred_at, Payment.id)
            < tuple_(literal(before[0], DateTime(timezone=True)), literal(before[1], Uuid()))
        )
    return list((await session.scalars(statement.limit(limit + 1))).all())


async def recent(session: AsyncSession, *, limit: int = 20) -> list[Payment]:
    result = await session.scalars(
        select(Payment).order_by(Payment.occurred_at.desc()).limit(limit)
    )
    return list(result.all())
