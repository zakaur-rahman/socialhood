"""What Razorpay tells us about a payment link and its refunds (GR-32), applied by the webhook job
(services/webhook_handlers/razorpay.py) in the workspace the webhook address belongs to.

The post was already checked against the workspace's webhook secret (webhooks/razorpay.py) and
stored once per Razorpay event id, so a re-delivery adds nothing; this is idempotent as well: a
Razorpay payment or refund is recorded once (ledger.py keys them by Razorpay's ids).

- ``payment_link.paid`` and ``payment_link.partially_paid``: a payment is recorded for the order
  (ledger.record_payment): the payment entity's amount, so a link that takes part payments
  records each part and the order becomes ``partially_paid`` and then ``paid``. A link that
  doesn't take part payments is paid in one go; an amount other than what was left is ignored and
  logged. A payment that comes for an order that was cancelled or expired still counts, because
  the money has arrived.
- ``payment_link.expired``: an order still waiting becomes ``expired``.
- ``payment_link.cancelled``: nothing changes here; a cancel we asked for already did it.
- ``refund.processed`` and ``refund.failed``: finish the refund we made, or record one the
  business made in its Razorpay dashboard (ledger.apply_refund_event).
- Every other event is ignored.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.orders import (
    Order,
    OrderPayment,
    OrderRefund,
    OrderStatus,
    PaymentConnection,
    PaymentMethod,
)
from socialhood.observability.logging import get_logger
from socialhood.services import audit
from socialhood.services.orders import ledger

log = get_logger(__name__)

PAYMENT_EVENTS = ("payment_link.paid", "payment_link.partially_paid")
REFUND_EVENTS = ("refund.processed", "refund.failed")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


async def _order_for(session: AsyncSession, link: dict[str, Any]) -> Order | None:
    link_id = str(link.get("id") or "")
    if link_id:
        found = (
            await session.scalars(
                select(Order).where(Order.payment_link_id == link_id).with_for_update()
            )
        ).first()
        if found is not None:
            return found
    reference = str(link.get("reference_id") or "")
    try:
        order_id = uuid.UUID(reference)
    except ValueError:
        return None
    return (
        await session.scalars(select(Order).where(Order.id == order_id).with_for_update())
    ).first()


async def apply(
    session: AsyncSession,
    conn: PaymentConnection,
    event: str,
    body: dict[str, Any],
    *,
    now: datetime | None = None,
) -> tuple[str, str | None]:
    """(``processed`` or ``ignored``, why). The caller commits."""
    now = now or datetime.now(UTC)
    conn.webhook_seen_at = now
    payload = _dict(body.get("payload"))
    if event in REFUND_EVENTS:
        return await _refund(session, event, payload, now)
    if event == "payment_link.expired":
        order = await _order_for(session, _dict(_dict(payload.get("payment_link")).get("entity")))
        if order is None:
            return "ignored", "unknown order"
        if order.status == OrderStatus.AWAITING_PAYMENT:
            order.status = OrderStatus.EXPIRED
            return "processed", None
        return "ignored", "the order was not waiting"
    if event not in PAYMENT_EVENTS:
        return "ignored", "not an event we act on"
    link = _dict(_dict(payload.get("payment_link")).get("entity"))
    order = await _order_for(session, link)
    if order is None:
        return "ignored", "unknown order"
    return await _payment(
        session, order, link, _dict(_dict(payload.get("payment")).get("entity")), now
    )


async def _payment(
    session: AsyncSession,
    order: Order,
    link: dict[str, Any],
    payment: dict[str, Any],
    now: datetime,
) -> tuple[str, str | None]:
    payment_id = str(payment.get("id") or "") or None
    currency = str(link.get("currency") or payment.get("currency") or order.currency)
    if currency != order.currency:
        log.warning("razorpay_amount_differs", order_id=str(order.id))
        return "ignored", "the amount paid differs from the order"
    left = ledger.remaining(order)
    # This payment's own amount; the link's running total less what we have recorded is the
    # fallback when the payment entity is missing.
    amount = _int(payment.get("amount"))
    if amount is None:
        total_paid = _int(link.get("amount_paid"))
        amount = None if total_paid is None else total_paid - order.amount_paid_minor
    if not order.accept_partial and amount != left:
        log.warning("razorpay_amount_differs", order_id=str(order.id))
        return "ignored", "the amount paid differs from the order"
    if amount is None or amount <= 0 or amount > left:
        log.warning("razorpay_amount_differs", order_id=str(order.id))
        return "ignored", "the amount paid differs from the order"
    row = await ledger.record_payment(
        session,
        order,
        amount=amount,
        method=PaymentMethod.RAZORPAY,
        reference=payment_id,
        razorpay_payment_id=payment_id,
        user_id=None,
        now=now,
    )
    if row is None:
        return "ignored", "already recorded"
    audit.record_system(
        session,
        "Razorpay",
        "order.payment_recorded",
        "order",
        order.id,
        number=order.number,
        amount_minor=amount,
        status=order.status,
    )
    return "processed", None


async def _refund(
    session: AsyncSession, event: str, payload: dict[str, Any], now: datetime
) -> tuple[str, str | None]:
    refund = _dict(_dict(payload.get("refund")).get("entity"))
    refund_id = str(refund.get("id") or "")
    payment_id = str(
        refund.get("payment_id")
        or _dict(_dict(payload.get("payment")).get("entity")).get("id")
        or ""
    )
    amount = _int(refund.get("amount"))
    if not refund_id or amount is None:
        return "ignored", "an unreadable refund"
    ours = (
        await session.scalars(
            select(OrderRefund).where(OrderRefund.razorpay_refund_id == refund_id).with_for_update()
        )
    ).first()
    paid: OrderPayment | None = None
    if ours is not None:
        order_id = ours.order_id
    else:
        paid = (
            (
                await session.scalars(
                    select(OrderPayment).where(OrderPayment.razorpay_payment_id == payment_id)
                )
            ).first()
            if payment_id
            else None
        )
        if paid is None:
            return "ignored", "an unknown payment"
        order_id = paid.order_id
    order = (
        await session.scalars(select(Order).where(Order.id == order_id).with_for_update())
    ).first()
    if order is None:
        return "ignored", "unknown order"
    state = "processed" if event == "refund.processed" else "failed"
    result = await ledger.apply_refund_event(
        session, order, paid, ours, refund_id=refund_id, amount=amount, state=state, now=now
    )
    if result[0] == "processed":
        audit.record_system(
            session,
            "Razorpay",
            "order.refund_updated",
            "order",
            order.id,
            number=order.number,
            refund=state,
            amount_minor=amount,
        )
    return result
