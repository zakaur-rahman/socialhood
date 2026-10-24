"""A customer's WhatsApp cart becomes an order (GR-33).

A customer who opens a product or product-list message, adds items and sends the cart makes an
``order`` message. Here it becomes a GR-32 order for that contact in that conversation, **awaiting
payment**, with its lines; a member then sends the payment link from the Orders page or the inbox.

- **Priced from the catalogue.** The retailer ids in the cart are our variant and product ids
  (services/catalogue/wa_catalogue.py), so each is matched to a catalogue row and priced from it
  now, like any order; the price the customer saw is not trusted. If it differs from the catalogue's
  the order's note says so.
- **Tolerant.** A cart is something the customer already did, so it is not refused for stock: items
  that are gone, switched off, unpriced or in another currency than the first are left out, and the
  note names how many. No usable item means no order (the message is still in the thread).
- **Plan.** Orders are part of Pro (PD-8) and capped per month; a workspace without room gets the
  message and no order.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import allows
from socialhood.billing.plans import current_plan
from socialhood.errors import ApiError
from socialhood.models.catalogue import Product, ProductVariant
from socialhood.models.inbox import Contact, Conversation, Message
from socialhood.models.orders import Order, OrderSource, OrderStatus
from socialhood.observability.logging import get_logger
from socialhood.platforms.events import CartOrder
from socialhood.services import audit
from socialhood.services.catalogue import money
from socialhood.services.orders import orders

log = get_logger(__name__)


def _uuid(text: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(text)
    except ValueError:
        return None


async def _lines(session: AsyncSession, cart: CartOrder) -> tuple[list[orders.Line], list[str]]:
    """The cart's lines priced from the catalogue, and the notes about what was left out or
    differs."""
    ids = {rid: _uuid(rid) for rid in {item.retailer_id for item in cart.items}}
    wanted = [i for i in ids.values() if i is not None]
    variants = {
        v.id: v
        for v in (
            await session.scalars(select(ProductVariant).where(ProductVariant.id.in_(wanted)))
        ).all()
    }
    product_ids = {v.product_id for v in variants.values()} | set(wanted)
    products = {
        p.id: p
        for p in (await session.scalars(select(Product).where(Product.id.in_(product_ids)))).all()
    }
    lines: list[orders.Line] = []
    notes: list[str] = []
    left_out = 0
    differs = 0
    for item in cart.items:
        key = ids.get(item.retailer_id)
        variant = variants.get(key) if key else None
        product = (
            products.get(variant.product_id) if variant else products.get(key) if key else None
        )
        if variant is None and product is not None and product.price_minor is None:
            product = None  # a product with variants must be named by its variant
        unit = variant.price_minor if variant else product.price_minor if product else None
        if product is None or not product.active or unit is None:
            left_out += 1
            continue
        if lines and lines[0].product.currency != product.currency:
            left_out += 1
            continue
        if item.price is not None and (item.currency or product.currency) == product.currency:
            seen = money.from_decimal(item.price, product.currency)
            if seen is not None and seen != unit:
                differs += 1
        lines.append(orders.Line(product, variant, item.quantity, unit))
    if left_out:
        which = "item in the cart wasn't" if left_out == 1 else "items in the cart weren't"
        notes.append(f"{left_out} {which} available.")
    if differs:
        notes.append("Some prices changed since the customer added them. This order uses today's.")
    return lines, notes


async def from_cart(
    session: AsyncSession,
    conv: Conversation,
    contact: Contact,
    msg: Message,
    cart: CartOrder,
    *,
    now: datetime,
) -> Order | None:
    """Make the order for a cart. None when the plan has no room or nothing in it can be ordered."""
    if not allows(await current_plan(session), orders.KEY):
        return None
    lines, notes = await _lines(session, cart)
    if not lines:
        log.info("whatsapp_cart_unusable", items=len(cart.items))
        return None
    try:
        await orders.check_month(session, now)
    except ApiError:
        log.info("whatsapp_cart_over_plan")
        return None
    note = " ".join(([cart.note.strip()] if cart.note and cart.note.strip() else []) + notes)
    order, _ = await orders.add(
        session,
        conv=conv,
        lines=lines,
        address=None,
        note=note[:500] or None,
        source=OrderSource.WHATSAPP,
        user_id=None,
        status=OrderStatus.AWAITING_PAYMENT,
        now=now,
    )
    audit.record_system(
        session,
        "WhatsApp cart",
        "order.created",
        "order",
        order.id,
        number=order.number,
        source="whatsapp",
    )
    count = sum(line.quantity for line in lines)
    msg.text = (
        f"Sent an order of {count} {'item' if count == 1 else 'items'} "
        f"({money.label(order.total_minor, order.currency)}). Order #{order.number}."
    )
    return order
