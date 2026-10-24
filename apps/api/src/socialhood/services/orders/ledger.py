"""What has been paid on an order and what has been given back (GR-32 follow-up, C-125).

Money is kept as rows, not as a status: ``order_payments`` (each payment toward the order) and
``order_refunds`` (each refund of part of a payment), with the two totals on the order
(``amount_paid_minor``, ``amount_refunded_minor``) kept equal to their sums by the functions here.
The status follows the totals:

- some paid, less than the total: ``partially_paid``; the whole total: ``paid``;
- everything paid has been refunded: ``refunded``. A part refund leaves the status alone (the
  order is still paid, it just shows what came back).

Rules:
- **A Razorpay payment counts once.** Its id is unique per order, so a webhook re-delivered, or the
  ``paid`` event that follows a ``partially_paid`` one, never adds it twice.
- **A refund goes back where the money came from.** A refund is taken from the newest payments
  first. A Razorpay payment is refunded through the business's own keys (``pending`` until Razorpay
  says it is processed, or failed); a UPI payment can't be refunded by us, so a member records that
  they paid it back and it counts at once. A refund can't be more than what is paid and not yet
  refunded, counting refunds still pending.
- **Only a processed refund counts.** A refund Razorpay later fails is shown as failed and the
  money is refundable again. A refund made in the Razorpay dashboard arrives as a webhook and is
  recorded as an outside refund of that payment.
- Every change is audited by the caller (a member) or here (a webhook).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError
from socialhood.models.inbox import Contact
from socialhood.models.orders import (
    Order,
    OrderPayment,
    OrderRefund,
    OrderStatus,
    PaymentConnection,
    PaymentMethod,
    RefundMethod,
    RefundStatus,
)
from socialhood.observability.logging import get_logger
from socialhood.razorpay.client import RazorpayClient, RazorpayError
from socialhood.security.crypto import TokenCipher
from socialhood.services.catalogue import money
from socialhood.services.orders import payments

log = get_logger(__name__)

COPY = {
    "nothing_paid": "Only an order with a payment can be refunded.",
    "all_refunded": "Everything paid on this order has been refunded.",
    "too_much": "You can refund up to {left} on this order.",
    "reason": "Say why you are refunding this order.",
    "over": "That payment is more than what is left to pay.",
    "amount": "Enter an amount more than zero.",
    "razorpay_refused": "Razorpay refused this refund.",
    "razorpay_failed": "Razorpay could not make this refund.",
}
PAYABLE = (
    OrderStatus.DRAFT,
    OrderStatus.AWAITING_PAYMENT,
    OrderStatus.PARTIALLY_PAID,
    OrderStatus.EXPIRED,
)
PAID_STATES = (OrderStatus.PARTIALLY_PAID, OrderStatus.PAID, OrderStatus.FULFILLED)


def remaining(order: Order) -> int:
    """What is still to pay (never negative)."""
    return max(0, order.total_minor - (order.amount_paid_minor or 0))


async def payments_of(session: AsyncSession, order_ids: Sequence[uuid.UUID]) -> list[OrderPayment]:
    if not order_ids:
        return []
    rows = await session.scalars(
        select(OrderPayment)
        .where(OrderPayment.order_id.in_(list(order_ids)))
        .order_by(OrderPayment.paid_at, OrderPayment.created_at, OrderPayment.id)
    )
    return list(rows.all())


async def refunds_of(session: AsyncSession, order_ids: Sequence[uuid.UUID]) -> list[OrderRefund]:
    if not order_ids:
        return []
    rows = await session.scalars(
        select(OrderRefund)
        .where(OrderRefund.order_id.in_(list(order_ids)))
        .order_by(OrderRefund.created_at, OrderRefund.id)
    )
    return list(rows.all())


def pending_minor(refunds: Sequence[OrderRefund]) -> int:
    return sum(r.amount_minor for r in refunds if r.status == RefundStatus.PENDING)


def refundable(order: Order, refunds: Sequence[OrderRefund]) -> int:
    """Paid, not yet refunded and not on its way back."""
    return max(
        0,
        (order.amount_paid_minor or 0)
        - (order.amount_refunded_minor or 0)
        - pending_minor(refunds),
    )


# ---------------------------------------------------------------- payments


async def record_payment(
    session: AsyncSession,
    order: Order,
    *,
    amount: int,
    method: str,
    reference: str | None,
    razorpay_payment_id: str | None,
    user_id: uuid.UUID | None,
    now: datetime,
) -> OrderPayment | None:
    """Add a payment and move the order: partially paid, or paid once the total is reached (and
    ``order.paid`` is emitted then). None when this Razorpay payment is already recorded. 422 for
    an amount that is more than what is left to pay."""
    if amount <= 0:
        raise ApiError("validation_error", COPY["amount"])
    if amount > remaining(order):
        raise ApiError("validation_error", COPY["over"])
    row = OrderPayment(
        order_id=order.id,
        amount_minor=amount,
        method=method,
        reference=reference.strip()[:200] if reference and reference.strip() else None,
        razorpay_payment_id=razorpay_payment_id,
        recorded_by_user_id=user_id,
        paid_at=now,
    )
    try:
        async with session.begin_nested():  # the unique (order, Razorpay payment id)
            session.add(row)
            await session.flush()
    except IntegrityError:
        return None
    order.amount_paid_minor += amount
    order.payment_reference = row.reference or order.payment_reference
    order.paid_by_user_id = user_id
    if order.amount_paid_minor >= order.total_minor:
        order.status = OrderStatus.PAID
        order.paid_at = now
        await _emit(session, order, "order.paid")
    else:
        order.status = OrderStatus.PARTIALLY_PAID
    return row


async def _emit(session: AsyncSession, order: Order, event: str, **extra: object) -> None:
    from socialhood.services.orders import orders
    from socialhood.services.webhooks import events

    contact = await session.get(Contact, order.contact_id)
    if contact is None:
        return
    items = (await orders.items_of(session, [order.id])).get(order.id, [])
    await events.order_event(session, event, order, items, contact, **extra)


# ---------------------------------------------------------------- refunds


@dataclass
class RefundResult:
    made: list[OrderRefund]
    failed: OrderRefund | None = None  # a part Razorpay refused after an earlier part went through


def _allocate(
    payments_list: Sequence[OrderPayment],
    refunds: Sequence[OrderRefund],
    amount: int,
) -> list[tuple[OrderPayment, int]]:
    """Split ``amount`` over the payments, newest first, by what is left of each."""
    taken: dict[uuid.UUID, int] = {}
    for refund in refunds:
        if refund.payment_id is not None and refund.status != RefundStatus.FAILED:
            taken[refund.payment_id] = taken.get(refund.payment_id, 0) + refund.amount_minor
    parts: list[tuple[OrderPayment, int]] = []
    need = amount
    for payment in sorted(payments_list, key=lambda p: (p.paid_at, p.created_at), reverse=True):
        if need <= 0:
            break
        room = payment.amount_minor - taken.get(payment.id, 0)
        take = min(room, need)
        if take > 0:
            parts.append((payment, take))
            need -= take
    return parts


async def refund(
    session: AsyncSession,
    order: Order,
    *,
    amount: int | None,
    reason: str,
    client: RazorpayClient,
    cipher: TokenCipher,
    user_id: uuid.UUID,
    now: datetime,
) -> RefundResult:
    """Refund ``amount`` (None: everything refundable) of an order that has payments. 422 for an
    order without payments, a missing reason or too large an amount; 409 when a Razorpay payment
    needs refunding and Razorpay isn't set up; a Razorpay failure on the first part is raised
    (nothing is recorded); on a later part it is recorded as a failed refund."""
    if not reason.strip():
        raise ApiError("validation_error", COPY["reason"])
    if order.status == OrderStatus.REFUNDED:
        raise ApiError("validation_error", COPY["all_refunded"])
    if order.status not in PAID_STATES or order.amount_paid_minor <= 0:
        raise ApiError("validation_error", COPY["nothing_paid"])
    paid = await payments_of(session, [order.id])
    done = await refunds_of(session, [order.id])
    left = refundable(order, done)
    want = left if amount is None else amount
    if want <= 0:
        raise ApiError(
            "validation_error", COPY["amount"] if amount is not None else COPY["all_refunded"]
        )
    if want > left:
        raise ApiError(
            "validation_error", COPY["too_much"].format(left=money.label(left, order.currency))
        )
    parts = _allocate(paid, done, want)
    conn: PaymentConnection | None = await payments.get(session)
    creds = (
        payments.credentials(conn, cipher)
        if any(p.method == PaymentMethod.RAZORPAY and p.razorpay_payment_id for p, _ in parts)
        else None
    )
    result = RefundResult(made=[])
    for payment, part in parts:
        row = OrderRefund(
            order_id=order.id,
            payment_id=payment.id,
            amount_minor=part,
            reason=reason.strip()[:200],
            method=RefundMethod.MANUAL,
            status=RefundStatus.PROCESSED,
            created_by_user_id=user_id,
            processed_at=now,
        )
        if payment.method == PaymentMethod.RAZORPAY and payment.razorpay_payment_id and creds:
            row.method = RefundMethod.RAZORPAY
            try:
                sent = await client.refund_payment(
                    creds,
                    payment.razorpay_payment_id,
                    amount_minor=part,
                    reason=row.reason,
                    receipt=f"order{order.number}",
                )
            except RazorpayError as error:
                if not result.made:
                    raise _api_error(error, conn) from error
                row.status, row.processed_at = RefundStatus.FAILED, None
                row.failure = _failure(error)
                session.add(row)
                result.failed = row
                break
            row.razorpay_refund_id = sent.id
            row.status = RefundStatus(sent.status)
            row.processed_at = now if row.status == RefundStatus.PROCESSED else None
            row.failure = COPY["razorpay_failed"] if row.status == RefundStatus.FAILED else None
        session.add(row)
        result.made.append(row)
    await session.flush()
    for row in result.made:
        if row.status == RefundStatus.PROCESSED:
            await settle(session, order, row, now=now)
    return result


def _failure(error: RazorpayError) -> str:
    if error.kind == "rejected":
        return COPY["razorpay_refused"]
    return payments.RAZORPAY_DOWN


def _api_error(error: RazorpayError, conn: PaymentConnection | None) -> ApiError:
    if error.kind == "auth":
        if conn is not None:
            conn.razorpay_last_error = payments.KEYS_REFUSED
        return ApiError("conflict", payments.KEYS_REFUSED)
    if error.kind == "rejected":
        return ApiError("validation_error", COPY["razorpay_refused"])
    return ApiError("platform_error", payments.RAZORPAY_DOWN)


async def settle(
    session: AsyncSession, order: Order, refund_row: OrderRefund, *, now: datetime
) -> None:
    """A refund just became processed: add it to the order's refunded total, mark the order
    ``refunded`` when everything paid is back, and emit ``order.refunded`` once."""
    order.amount_refunded_minor += refund_row.amount_minor
    if order.amount_refunded_minor >= order.amount_paid_minor > 0:
        order.status = OrderStatus.REFUNDED
    await _emit(
        session,
        order,
        "order.refunded",
        refund={
            "id": str(refund_row.id),
            "amount_minor": refund_row.amount_minor,
            "amount": money.plain(refund_row.amount_minor, order.currency),
            "reason": refund_row.reason,
            "method": refund_row.method,
            "full": order.status == OrderStatus.REFUNDED,
        },
    )


async def apply_refund_event(
    session: AsyncSession,
    order: Order,
    payment_row: OrderPayment | None,
    refund_row: OrderRefund | None,
    *,
    refund_id: str,
    amount: int,
    state: str,
    now: datetime,
) -> tuple[str, str | None]:
    """A Razorpay refund event for this order (``refund.processed`` or ``refund.failed``):
    finish the refund we made, or record one made in the Razorpay dashboard. Idempotent."""
    if refund_row is None:
        if payment_row is None or state != RefundStatus.PROCESSED:
            return "ignored", "an unknown refund"
        if amount > order.amount_paid_minor - order.amount_refunded_minor:
            return "ignored", "more than was paid"
        refund_row = OrderRefund(
            order_id=order.id,
            payment_id=payment_row.id,
            amount_minor=amount,
            reason="Refunded in the Razorpay dashboard",
            method=RefundMethod.RAZORPAY,
            status=RefundStatus.PENDING,
            razorpay_refund_id=refund_id,
        )
        session.add(refund_row)
        await session.flush()
    if refund_row.status == RefundStatus.PROCESSED:
        return "ignored", "already processed"
    if state == RefundStatus.FAILED:
        refund_row.status, refund_row.failure = RefundStatus.FAILED, COPY["razorpay_failed"]
        return "processed", None
    if state != RefundStatus.PROCESSED:
        return "ignored", "not finished"
    refund_row.status, refund_row.processed_at = RefundStatus.PROCESSED, now
    await settle(session, order, refund_row, now=now)
    return "processed", None
