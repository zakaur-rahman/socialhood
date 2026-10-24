"""What Razorpay tells us about a payment link (GR-32), applied by the webhook job
(services/webhook_handlers/razorpay.py) in the workspace the webhook address belongs to.

The post was already checked against the workspace's webhook secret (webhooks/razorpay.py) and
stored once per Razorpay event id, so a re-delivery adds nothing; this is idempotent as well: an
order that is already paid stays as it is.

- ``payment_link.paid``: the order is paid when the amount paid is the order's total (a payment
  link takes no partial payments; anything else is left alone and logged). A payment that comes
  for an order that was cancelled or expired still marks it paid, because the money has arrived.
- ``payment_link.expired``: an order still waiting becomes ``expired``.
- ``payment_link.cancelled``: nothing changes here; a cancel we asked for already did it.
- ``payment_link.partially_paid`` and every other event: ignored.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.orders import Order, OrderStatus, PaymentConnection
from socialhood.observability.logging import get_logger
from socialhood.services.orders import orders

log = get_logger(__name__)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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
    link = _dict(_dict(payload.get("payment_link")).get("entity"))
    if event not in ("payment_link.paid", "payment_link.expired"):
        return "ignored", "not an event we act on"
    order = await _order_for(session, link)
    if order is None:
        return "ignored", "unknown order"
    if event == "payment_link.expired":
        if order.status == OrderStatus.AWAITING_PAYMENT:
            order.status = OrderStatus.EXPIRED
            return "processed", None
        return "ignored", "the order was not waiting"
    payment = _dict(_dict(payload.get("payment")).get("entity"))
    paid = link.get("amount_paid", payment.get("amount"))
    currency = str(link.get("currency") or payment.get("currency") or order.currency)
    if paid != order.total_minor or currency != order.currency:
        log.warning("razorpay_amount_differs", order_id=str(order.id))
        return "ignored", "the amount paid differs from the order"
    changed = await orders.apply_paid(
        session, order, reference=str(payment.get("id") or "") or None, user_id=None, now=now
    )
    return ("processed", None) if changed else ("ignored", "already paid")
