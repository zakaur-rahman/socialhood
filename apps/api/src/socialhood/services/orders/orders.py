"""Orders (GR-32): made in a conversation from the catalogue, asked for payment, paid, cancelled.

- **Totals are computed here**, from the catalogue's prices when the order is made, and the lines
  are a snapshot (name, variant, SKU, unit price), so a later price change never alters an order.
  A request carries product ids and quantities, never a price. Every line is in one currency.
- **Stock** is checked when it is recorded (more than is left is refused) but is not reduced:
  the catalogue's stock is a number the business keeps (C-120).
- **Status.** ``draft`` when made, ``awaiting_payment`` once a payment link or UPI request is
  out, then ``paid``, ``cancelled`` or ``expired`` (Razorpay's link ran out). A paid order is
  final. A payment that arrives for a cancelled or expired order still marks it paid, because the
  money has arrived.
- **Paying.** Razorpay: a Payment Link on the business's own keys; Razorpay's signed webhook marks
  the order paid (webhook.py). UPI: a ``upi://pay`` link and the VPA in the message; there is no
  webhook for it, so a member marks the order paid and the audit trail says who and when.
- **Plan.** Making an order, asking for payment and marking paid need ``commerce`` (PD-8: Pro and
  Max) and room under ``orders_monthly``; reading orders is never refused.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlencode

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import allows, check_entitlement, quota_error
from socialhood.billing.plans import current_plan, entitlement
from socialhood.db.tenancy import require_workspace
from socialhood.errors import ApiError, FieldError
from socialhood.models.catalogue import Product, ProductVariant
from socialhood.models.inbox import Contact, Conversation
from socialhood.models.orders import (
    Order,
    OrderItem,
    OrderSource,
    OrderStatus,
    PaymentConnection,
    PaymentMethod,
)
from socialhood.observability.logging import get_logger
from socialhood.razorpay.client import MIN_EXPIRY_S, RazorpayClient, RazorpayError
from socialhood.repositories import catalogue as catalogue_repo
from socialhood.schemas.orders import (
    AddressOut,
    OrderContact,
    OrderCreate,
    OrderLimits,
    OrderLineOut,
    OrderList,
    OrderOut,
)
from socialhood.security.crypto import TokenCipher
from socialhood.services import leads
from socialhood.services.catalogue import money
from socialhood.services.orders import payments

log = get_logger(__name__)

KEY = "commerce"
LINK_TTL = timedelta(days=3)  # how long a Razorpay link can be paid
MAX_LISTED_LINES = 5  # lines named in the payment message
UPI_CURRENCY = "INR"

COPY = {
    "plan": "Orders are part of Pro.",
    "cap": "Your plan includes {limit:,} orders a month.",
    "product_gone": "That product doesn't exist any more.",
    "product_off": "{name} is switched off. Turn it on, or choose another.",
    "variant_needed": "Choose a variant of {name}.",
    "variant_gone": "That variant of {name} doesn't exist.",
    "no_variants": "{name} has no variants.",
    "no_price": "{name} has no price. Add one in Products first.",
    "currency": "All the products in an order must be priced in the same currency.",
    "stock": "Only {left} left of {name}.",
    "total": "That total is too large.",
    "state": "This order is {status}, so that can't be done.",
    "paid": "This order is already paid.",
    "upi_currency": "UPI payments are in rupees. This order is in {currency}.",
    "no_conversation": "That conversation's customer can't be reached.",
}
STATUS_WORDS: dict[str, str] = {
    OrderStatus.DRAFT: "a draft",
    OrderStatus.AWAITING_PAYMENT: "waiting for payment",
    OrderStatus.PAID: "paid",
    OrderStatus.CANCELLED: "cancelled",
    OrderStatus.EXPIRED: "expired",
}


@dataclass
class Line:
    product: Product
    variant: ProductVariant | None
    quantity: int
    unit_minor: int


# ---------------------------------------------------------------- reading


async def get(session: AsyncSession, order_id: uuid.UUID, *, lock: bool = False) -> Order:
    query = select(Order).where(Order.id == order_id)
    if lock:
        query = query.with_for_update()
    order = (await session.scalars(query)).one_or_none()
    if order is None:
        raise ApiError("not_found", "That order wasn't found.")
    return order


async def items_of(
    session: AsyncSession, order_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[OrderItem]]:
    if not order_ids:
        return {}
    rows = await session.scalars(
        select(OrderItem)
        .where(OrderItem.order_id.in_(list(order_ids)))
        .order_by(OrderItem.position, OrderItem.created_at, OrderItem.id)
    )
    grouped: dict[uuid.UUID, list[OrderItem]] = {}
    for item in rows.all():
        grouped.setdefault(item.order_id, []).append(item)
    return grouped


async def views(session: AsyncSession, orders: Sequence[Order]) -> list[OrderOut]:
    """The orders as the API shows them (one query each for lines, contacts and names)."""
    if not orders:
        return []
    items = await items_of(session, [o.id for o in orders])
    contacts = {
        c.id: c
        for c in (
            await session.scalars(
                select(Contact).where(Contact.id.in_({o.contact_id for o in orders}))
            )
        ).all()
    }
    user_ids = {
        u for o in orders for u in (o.paid_by_user_id, o.created_by_user_id) if u is not None
    }
    names = await leads.user_names(session, list(user_ids))
    return [_out(o, items.get(o.id, []), contacts[o.contact_id], names) for o in orders]


async def view(session: AsyncSession, order: Order) -> OrderOut:
    return (await views(session, [order]))[0]


def _out(
    order: Order, items: Sequence[OrderItem], contact: Contact, names: dict[uuid.UUID, str]
) -> OrderOut:
    cur = order.currency
    return OrderOut(
        id=order.id,
        number=order.number,
        status=order.status,
        source=order.source,
        currency=cur,
        total_minor=order.total_minor,
        total=money.plain(order.total_minor, cur),
        items=[
            OrderLineOut(
                id=i.id,
                product_id=i.product_id,
                variant_id=i.variant_id,
                name=i.name,
                variant_title=i.variant_title,
                sku=i.sku,
                quantity=i.quantity,
                unit_price_minor=i.unit_price_minor,
                unit_price=money.plain(i.unit_price_minor, cur),
                line_total_minor=i.line_total_minor,
                line_total=money.plain(i.line_total_minor, cur),
            )
            for i in items
        ],
        address=AddressOut(**order.address) if order.address else None,
        note=order.note,
        contact=OrderContact(
            id=contact.id, display_name=contact.display_name, username=contact.username
        ),
        conversation_id=order.conversation_id,
        payment_method=order.payment_method,
        payment_link_url=order.payment_link_url,
        payment_reference=order.payment_reference,
        link_expires_at=order.link_expires_at,
        paid_at=order.paid_at,
        paid_by_name=names.get(order.paid_by_user_id) if order.paid_by_user_id else None,
        cancelled_at=order.cancelled_at,
        created_by_name=names.get(order.created_by_user_id) if order.created_by_user_id else None,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


async def list_orders(
    session: AsyncSession,
    *,
    status: str | None,
    contact_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> OrderList:
    where = []
    if status:
        where.append(Order.status == status)
    if contact_id is not None:
        where.append(Order.contact_id == contact_id)
    total = int(await session.scalar(select(func.count()).select_from(Order).where(*where)) or 0)
    rows = await session.scalars(
        select(Order)
        .where(*where)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)
        .offset(offset)
    )
    conn = await payments.get(session)
    plan = await current_plan(session)
    return OrderList(
        items=await views(session, list(rows.all())),
        total=total,
        limits=OrderLimits(
            entitled=allows(plan, KEY),
            razorpay_ready=bool(conn and conn.razorpay_key_id and conn.razorpay_secret_enc),
            upi_ready=bool(conn and conn.upi_vpa),
        ),
    )


# ---------------------------------------------------------------- making an order


def _field(index: int, name: str, message: str) -> FieldError:
    return FieldError(f"items.{index}.{name}", message)


async def resolve_lines(
    session: AsyncSession, wanted: Sequence[tuple[uuid.UUID, uuid.UUID | None, int]]
) -> list[Line]:
    """The catalogue's products and prices for ``(product, variant, quantity)`` requests.
    A product or variant that isn't this workspace's is a 404 (nothing reveals what exists);
    a product that is off, has no price or is out of stock is a 422 on that line."""
    product_ids = {p for p, _, _ in wanted}
    products = {
        p.id: p
        for p in (await session.scalars(select(Product).where(Product.id.in_(product_ids)))).all()
    }
    if len(products) != len(product_ids):
        raise ApiError("not_found", COPY["product_gone"])
    variants = await catalogue_repo.variants_of(session, list(product_ids))
    lines: list[Line] = []
    errors: list[FieldError] = []
    wanted_by_variant: dict[uuid.UUID | None, int] = {}
    for index, (product_id, variant_id, quantity) in enumerate(wanted):
        product = products[product_id]
        own = variants.get(product_id, [])
        variant: ProductVariant | None = None
        if variant_id is not None:
            variant = next((v for v in own if v.id == variant_id), None)
            if variant is None and own:
                errors.append(
                    _field(index, "variant_id", COPY["variant_gone"].format(name=product.name))
                )
                continue
            if variant is None:
                errors.append(
                    _field(index, "variant_id", COPY["no_variants"].format(name=product.name))
                )
                continue
        elif own:
            errors.append(
                _field(index, "variant_id", COPY["variant_needed"].format(name=product.name))
            )
            continue
        if not product.active:
            errors.append(
                _field(index, "product_id", COPY["product_off"].format(name=product.name))
            )
            continue
        unit = variant.price_minor if variant is not None else product.price_minor
        if unit is None:
            errors.append(_field(index, "product_id", COPY["no_price"].format(name=product.name)))
            continue
        stock = variant.stock if variant is not None else product.stock
        key = variant.id if variant is not None else product.id
        total_asked = wanted_by_variant.get(key, 0) + quantity
        wanted_by_variant[key] = total_asked
        if stock is not None and total_asked > stock:
            errors.append(
                _field(
                    index, "quantity", COPY["stock"].format(left=max(stock, 0), name=product.name)
                )
            )
            continue
        lines.append(Line(product, variant, quantity, unit))
    if errors:
        raise ApiError("validation_error", errors=errors)
    if len({line.product.currency for line in lines}) > 1:
        raise ApiError("validation_error", errors=[FieldError("items", COPY["currency"])])
    return lines


def total_of(lines: Sequence[Line]) -> int:
    total = sum(line.unit_minor * line.quantity for line in lines)
    if total > money.MAX_MINOR:
        raise ApiError("validation_error", errors=[FieldError("items", COPY["total"])])
    return total


async def _next_number(session: AsyncSession) -> int:
    # One order is numbered at a time per workspace, so two at once can't take the same number.
    await session.execute(
        select(
            func.pg_advisory_xact_lock(func.hashtextextended(f"orders:{require_workspace()}", 0))
        )
    )
    last = await session.scalar(select(func.max(Order.number)))
    return int(last or 0) + 1


async def _check_month(session: AsyncSession, now: datetime) -> None:
    limit = entitlement(await current_plan(session), "orders_monthly")
    if limit is None:
        return
    start = now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = int(
        await session.scalar(
            select(func.count()).select_from(Order).where(Order.created_at >= start)
        )
        or 0
    )
    if used + 1 > limit:
        raise quota_error("orders_monthly", int(limit), COPY["cap"].format(limit=int(limit)))


async def add(
    session: AsyncSession,
    *,
    conv: Conversation,
    lines: Sequence[Line],
    address: dict[str, Any] | None,
    note: str | None,
    source: str,
    user_id: uuid.UUID | None,
    status: str = OrderStatus.DRAFT,
    now: datetime,
) -> tuple[Order, list[OrderItem]]:
    """Save an order for the conversation's contact (the lines already resolved and priced)."""
    contact = await session.get(Contact, conv.contact_id)
    if contact is None:
        raise ApiError("not_found", COPY["no_conversation"])
    order = Order(
        number=await _next_number(session),
        contact_id=contact.id,
        conversation_id=conv.id,
        status=status,
        source=source,
        currency=lines[0].product.currency,
        total_minor=total_of(lines),
        address=address or None,
        note=note.strip() if note and note.strip() else None,
        created_by_user_id=user_id,
    )
    session.add(order)
    await session.flush()
    items = [
        OrderItem(
            order_id=order.id,
            product_id=line.product.id,
            variant_id=line.variant.id if line.variant is not None else None,
            name=line.product.name,
            variant_title=line.variant.title if line.variant is not None else None,
            sku=(line.variant.sku if line.variant is not None else None) or line.product.sku,
            quantity=line.quantity,
            unit_price_minor=line.unit_minor,
            line_total_minor=line.unit_minor * line.quantity,
            position=position,
        )
        for position, line in enumerate(lines)
    ]
    session.add_all(items)
    await session.flush()
    from socialhood.services.webhooks import events

    await events.order_event(session, "order.created", order, items, contact)
    return order, items


async def create(
    session: AsyncSession, body: OrderCreate, *, user_id: uuid.UUID, now: datetime | None = None
) -> Order:
    """An order made by a member in a conversation. 402 without commerce on the plan or over the
    month's orders, 404 for a conversation or product that isn't this workspace's, 422 on the
    lines."""
    now = now or datetime.now(UTC)
    from socialhood.repositories import inbox

    conv = await inbox.get_conversation(session, body.conversation_id)
    if conv is None:
        raise ApiError("not_found", "That conversation wasn't found.")
    lines = await resolve_lines(
        session, [(i.product_id, i.variant_id, i.quantity) for i in body.items]
    )
    await check_entitlement(session, KEY, detail=COPY["plan"])
    await _check_month(session, now)
    address = (
        {k: v.strip() for k, v in body.address.model_dump().items() if v and v.strip()}
        if body.address
        else None
    )
    order, _ = await add(
        session,
        conv=conv,
        lines=lines,
        address=address,
        note=body.note,
        source=OrderSource.INBOX,
        user_id=user_id,
        now=now,
    )
    return order


# ---------------------------------------------------------------- asking for payment


def upi_link(vpa: str, name: str, order: Order) -> str:
    query = urlencode(
        {
            "pa": vpa,
            "pn": name,
            "am": money.plain(order.total_minor, order.currency),
            "cu": order.currency,
            "tn": f"Order {order.number}",
        },
        quote_via=quote,
    )
    return f"upi://pay?{query}"


def payment_text(order: Order, items: Sequence[OrderItem], *, pay_url: str, vpa: str | None) -> str:
    """The message that carries the link: the order, its lines, the total and how to pay."""
    lines = [f"Order #{order.number}"]
    for item in items[:MAX_LISTED_LINES]:
        name = f"{item.name} - {item.variant_title}" if item.variant_title else item.name
        lines.append(
            f"{item.quantity} x {name}: {money.label(item.line_total_minor, order.currency)}"
        )
    if len(items) > MAX_LISTED_LINES:
        lines.append(f"and {len(items) - MAX_LISTED_LINES} more")
    lines.append(f"Total: {money.label(order.total_minor, order.currency)}")
    lines.append("")
    if vpa is None:
        lines.append(f"Pay here: {pay_url}")
    else:
        lines.append(f"Pay with any UPI app: {pay_url}")
        lines.append(f"Or send it to {vpa} and tell us when it's done.")
    return "\n".join(lines)


async def request_payment(
    session: AsyncSession,
    order: Order,
    method: str,
    *,
    client: RazorpayClient,
    cipher: TokenCipher,
    now: datetime | None = None,
) -> str:
    """Make the payment link (Razorpay) or UPI request and record it on the order, which is
    then awaiting payment. Returns the text to send. 409 when the method isn't set up, 422 for
    an order in a state that can't be paid or a UPI order that isn't in rupees. A link that was
    out for the order is cancelled first (best effort)."""
    now = now or datetime.now(UTC)
    await check_entitlement(session, KEY, detail=COPY["plan"])
    if order.status not in (OrderStatus.DRAFT, OrderStatus.AWAITING_PAYMENT, OrderStatus.EXPIRED):
        raise ApiError(
            "validation_error",
            COPY["paid"]
            if order.status == OrderStatus.PAID
            else COPY["state"].format(status=STATUS_WORDS.get(order.status, order.status)),
        )
    conn: PaymentConnection | None = await payments.get(session)
    items = (await items_of(session, [order.id])).get(order.id, [])
    contact = await session.get(Contact, order.contact_id)
    if method == PaymentMethod.RAZORPAY:
        creds = payments.credentials(conn, cipher)
        await _cancel_link(order, client, creds)
        expires = now + LINK_TTL
        try:
            link = await client.create_payment_link(
                creds,
                amount_minor=order.total_minor,
                currency=order.currency,
                reference_id=str(order.id),
                description=f"Order #{order.number}",
                customer_name=contact.display_name if contact else None,
                customer_phone=contact.phone if contact else None,
                expire_by=max(int(expires.timestamp()), int(now.timestamp()) + MIN_EXPIRY_S),
            )
        except RazorpayError as error:
            if error.kind == "auth":
                assert conn is not None
                conn.razorpay_last_error = payments.KEYS_REFUSED
                await session.commit()  # remember it for the card; the request still fails
                raise ApiError("conflict", payments.KEYS_REFUSED) from error
            if error.kind == "rejected":
                raise ApiError(
                    "validation_error", "Razorpay refused this payment request."
                ) from error
            raise ApiError("platform_error", payments.RAZORPAY_DOWN) from error
        order.payment_link_id = link.id
        order.payment_link_url = link.short_url
        order.link_expires_at = expires
        text = payment_text(order, items, pay_url=link.short_url, vpa=None)
    elif method == PaymentMethod.UPI:
        if conn is None or not conn.upi_vpa:
            raise ApiError("conflict", payments.UPI_MISSING)
        if order.currency != UPI_CURRENCY:
            raise ApiError("validation_error", COPY["upi_currency"].format(currency=order.currency))
        link_url = upi_link(conn.upi_vpa, conn.upi_name or conn.upi_vpa, order)
        order.payment_link_id = None
        order.payment_link_url = link_url
        order.link_expires_at = None
        text = payment_text(order, items, pay_url=link_url, vpa=conn.upi_vpa)
    else:  # pragma: no cover - the schema allows only the two
        raise ApiError("validation_error", "Choose Razorpay or UPI.")
    order.payment_method = method
    order.status = OrderStatus.AWAITING_PAYMENT
    return text


async def _cancel_link(order: Order, client: RazorpayClient, creds: Any) -> None:
    """Cancel the Razorpay link the order has, if any. A failure is logged, never raised: the
    link would only expire on its own."""
    if order.payment_method != PaymentMethod.RAZORPAY or not order.payment_link_id:
        return
    try:
        await client.cancel_payment_link(creds, order.payment_link_id)
    except RazorpayError as error:
        log.warning("razorpay_cancel_failed", order_id=str(order.id), http_status=error.status)


# ---------------------------------------------------------------- paid, cancelled


async def apply_paid(
    session: AsyncSession,
    order: Order,
    *,
    reference: str | None,
    user_id: uuid.UUID | None,
    now: datetime,
) -> bool:
    """Mark the order paid and emit ``order.paid``. False (nothing changed) when it already is."""
    if order.status == OrderStatus.PAID:
        return False
    order.status = OrderStatus.PAID
    order.paid_at = now
    order.paid_by_user_id = user_id
    order.payment_reference = reference.strip() if reference and reference.strip() else None
    contact = await session.get(Contact, order.contact_id)
    items = (await items_of(session, [order.id])).get(order.id, [])
    if contact is not None:
        from socialhood.services.webhooks import events

        await events.order_event(session, "order.paid", order, items, contact)
    return True


async def mark_paid(
    session: AsyncSession,
    order: Order,
    *,
    reference: str | None,
    user_id: uuid.UUID,
    now: datetime | None = None,
) -> None:
    """A member says the order was paid (UPI has no webhook). 422 when it is already paid or
    cancelled."""
    await check_entitlement(session, KEY, detail=COPY["plan"])
    if order.status == OrderStatus.PAID:
        raise ApiError("validation_error", COPY["paid"])
    if order.status == OrderStatus.CANCELLED:
        raise ApiError("validation_error", COPY["state"].format(status="cancelled"))
    await apply_paid(
        session, order, reference=reference, user_id=user_id, now=now or datetime.now(UTC)
    )


async def cancel(
    session: AsyncSession,
    order: Order,
    *,
    client: RazorpayClient,
    cipher: TokenCipher,
    now: datetime | None = None,
) -> None:
    """Cancel an order that isn't paid, and its Razorpay link."""
    if order.status == OrderStatus.CANCELLED:
        return
    if order.status == OrderStatus.PAID:
        raise ApiError("validation_error", COPY["paid"])
    conn = await payments.get(session)
    if conn is not None and conn.razorpay_key_id and conn.razorpay_secret_enc:
        await _cancel_link(order, client, payments.credentials(conn, cipher))
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = now or datetime.now(UTC)
