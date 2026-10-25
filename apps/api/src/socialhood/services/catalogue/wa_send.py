"""WhatsApp product and product-list messages (GR-33): a member sends them from the inbox, and the
flow step "send product" uses them when the conversation is on WhatsApp and a catalogue is
connected.

- **What goes out.** A ``product`` message shows one catalogue item (name, price and picture come
  from Meta's catalogue, not from the text); a ``product_list`` shows up to 30 items in up to 10
  titled sections under a header. The text typed is the message body; it is also what the thread
  shows. Meta delivers these only inside the 24-hour window, like any free-form message, and a
  customer on an old WhatsApp version sees a delivery failure.
- **Only synced items.** A message names retailer ids (our variant or product ids); every one must
  be in the catalogue as last synced, active and without an error. Otherwise nothing is sent and
  the reason names the product ("... isn't in the WhatsApp catalogue yet").
- **The catalogue belongs to a number.** The conversation must be on the WhatsApp number the
  catalogue was connected through (its business account owns the catalogue).
- **Flow fallback.** ``native_for_step`` answers None whenever a native message can't be sent (not
  WhatsApp, no catalogue, another number, the item not synced yet), and the step then sends the
  text and link it always did (services/catalogue/message.py).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import check_entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.catalogue import (
    CatalogueConnection,
    CatalogueItem,
    CatalogueState,
    Product,
    ProductVariant,
)
from socialhood.models.inbox import Conversation, Message
from socialhood.platforms.deps import PlatformDeps
from socialhood.repositories import catalogue as repo
from socialhood.schemas.wa_catalogue import MAX_ITEMS, ItemRef, ProductMessageSend
from socialhood.services.catalogue import products, wa_catalogue

NOT_WHATSAPP = "Product messages are for WhatsApp conversations."
NOT_CONNECTED = "Connect a WhatsApp catalogue on the Products page first."
OTHER_NUMBER = "This catalogue is connected to a different WhatsApp number."
PLAN = "The WhatsApp catalogue is part of Pro."
NEEDS_HEADER = "A product list needs a header."
NEEDS_ITEM = "Choose a product."
NEEDS_SECTIONS = "Add at least one section with products."
TOO_MANY = f"A product list holds up to {MAX_ITEMS} products."
LIST_MAX_VARIANTS = MAX_ITEMS


@dataclass(frozen=True)
class Resolved:
    retailer_id: str
    label: str


def _not_synced(label: str) -> str:
    return f"{label} isn't in the WhatsApp catalogue yet. Wait for the sync, or press Sync now."


async def _connection_for(session: AsyncSession, conv: Conversation) -> CatalogueConnection:
    if conv.platform != "whatsapp":
        raise ApiError("validation_error", NOT_WHATSAPP)
    conn = await wa_catalogue.get(session)
    if conn is None:
        raise ApiError("conflict", NOT_CONNECTED)
    if conn.status != "active":
        raise ApiError("conflict", wa_catalogue.NEEDS_ATTENTION)
    if conn.social_account_id != conv.social_account_id:
        raise ApiError("conflict", OTHER_NUMBER)
    return conn


async def resolve(session: AsyncSession, refs: list[ItemRef], *, field: str) -> list[Resolved]:
    """The retailer id of each item and a label for it. 404 for a product that isn't this
    workspace's, 422 for a variant missing or wrong, a product switched off or not synced."""
    ids = {ref.product_id for ref in refs}
    found = {
        p.id: p for p in (await session.scalars(select(Product).where(Product.id.in_(ids)))).all()
    }
    if len(found) != len(ids):
        raise ApiError("not_found", "That product doesn't exist any more.")
    variants = await repo.variants_of(session, list(ids))
    wanted: list[Resolved] = []
    errors: list[FieldError] = []
    for index, ref in enumerate(refs):
        product = found[ref.product_id]
        own = variants.get(product.id, [])
        path = f"{field}.{index}" if field else str(index)
        variant: ProductVariant | None = None
        if own:
            variant = next((v for v in own if v.id == ref.variant_id), None)
            if variant is None:
                errors.append(
                    FieldError(f"{path}.variant_id", f"Choose a variant of {product.name}.")
                )
                continue
        elif ref.variant_id is not None:
            errors.append(FieldError(f"{path}.variant_id", f"{product.name} has no variants."))
            continue
        if not product.active:
            errors.append(FieldError(f"{path}.product_id", f"{product.name} is switched off."))
            continue
        label = f"{product.name} - {variant.title}" if variant else product.name
        wanted.append(Resolved(wa_catalogue.retailer_id(product, variant), label))
    if errors:
        raise ApiError("validation_error", errors=errors)
    rows = {
        row.retailer_id: row
        for row in (
            await session.scalars(
                select(CatalogueItem).where(
                    CatalogueItem.retailer_id.in_([w.retailer_id for w in wanted])
                )
            )
        ).all()
    }
    for item in wanted:
        row = rows.get(item.retailer_id)
        if row is None or row.state != CatalogueState.SYNCED:
            raise ApiError("validation_error", _not_synced(item.label))
    return wanted


def interactive_of(
    kind: str,
    conn: CatalogueConnection,
    *,
    retailer_id: str | None = None,
    footer: str | None = None,
    header: str | None = None,
    sections: list[tuple[str, list[str]]] | None = None,
) -> dict[str, Any]:
    """What a ``messages.interactive`` column holds (read back by ``sending.pending_parts``)."""
    payload: dict[str, Any] = {"type": kind, "catalog_id": conn.catalog_id}
    if footer:
        payload["footer"] = footer.strip()
    if kind == "product":
        payload["retailer_id"] = retailer_id
    else:
        payload["header"] = (header or "").strip()
        payload["sections"] = [
            {"title": title, "retailer_ids": ids} for title, ids in sections or []
        ]
    return payload


async def build(
    session: AsyncSession, conv: Conversation, body: ProductMessageSend
) -> tuple[str, dict[str, Any]]:
    """Check the request and make the message: its body text and its ``interactive`` JSON."""
    conn = await _connection_for(session, conv)
    text = body.body.strip()
    if not text:
        raise ApiError("validation_error", errors=[FieldError("body", "Write the message.")])
    if body.kind == "product":
        if body.item is None:
            raise ApiError("validation_error", errors=[FieldError("item", NEEDS_ITEM)])
        [one] = await resolve(session, [body.item], field="item")
        return text, interactive_of(
            "product", conn, retailer_id=one.retailer_id, footer=body.footer
        )
    if not (body.header and body.header.strip()):
        raise ApiError("validation_error", errors=[FieldError("header", NEEDS_HEADER)])
    if not body.sections:
        raise ApiError("validation_error", errors=[FieldError("sections", NEEDS_SECTIONS)])
    if sum(len(s.items) for s in body.sections) > MAX_ITEMS:
        raise ApiError("validation_error", errors=[FieldError("sections", TOO_MANY)])
    sections: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for index, section in enumerate(body.sections):
        resolved = await resolve(session, section.items, field=f"sections.{index}.items")
        ids = []
        for r in resolved:
            if r.retailer_id not in seen:  # an item appears once in a message
                seen.add(r.retailer_id)
                ids.append(r.retailer_id)
        if ids:
            sections.append((section.title.strip(), ids))
    return text, interactive_of(
        "product_list", conn, footer=body.footer, header=body.header, sections=sections
    )


async def send(
    session: AsyncSession,
    conv: Conversation,
    body: ProductMessageSend,
    *,
    user_id: uuid.UUID,
    deps: PlatformDeps,
) -> Message:
    """Queue the message through the ordinary send pipeline (window, takeover and read-only rules
    apply). 402 without commerce on the plan."""
    from socialhood.services import sending

    await check_entitlement(session, products.KEY, detail=PLAN)
    text, interactive = await build(session, conv, body)
    return await sending.queue_outbound(
        session,
        conv,
        source="human",
        client_id=uuid.uuid4(),
        text=text,
        interactive=interactive,
        sent_by_user_id=user_id,
        deps=deps,
    )


# ---------------------------------------------------------------- the flow step


@dataclass(frozen=True)
class Native:
    text: str
    interactive: dict[str, Any]


async def native_for_step(
    session: AsyncSession,
    conv: Conversation,
    product_id: uuid.UUID,
    variant_id: uuid.UUID | None,
    intro: str,
) -> Native | None:
    """The product step as a native WhatsApp message, or None when it can't be one (the step then
    sends its text and link). A named variant is a product message; a product with variants and
    none named is a list of up to 30 of them; a product without variants is a product message."""
    if conv.platform != "whatsapp":
        return None
    conn = await wa_catalogue.get(session)
    if conn is None or conn.status != "active" or conn.social_account_id != conv.social_account_id:
        return None
    product = await repo.get(session, product_id)
    if product is None or not product.active:
        return None
    own = (await repo.variants_of(session, [product.id])).get(product.id, [])
    if variant_id is not None:
        chosen = next((v for v in own if v.id == variant_id), None)
        if chosen is None:
            return None
        rids = [wa_catalogue.retailer_id(product, chosen)]
    elif own:
        rids = [wa_catalogue.retailer_id(product, v) for v in own[:LIST_MAX_VARIANTS]]
    else:
        rids = [wa_catalogue.retailer_id(product, None)]
    synced = {
        row.retailer_id
        for row in (
            await session.scalars(
                select(CatalogueItem).where(
                    CatalogueItem.retailer_id.in_(rids),
                    CatalogueItem.state == CatalogueState.SYNCED,
                )
            )
        ).all()
    }
    if len(synced) != len(rids):
        return None
    text = (intro.strip() or product.name)[:1024]
    if len(rids) == 1:
        return Native(text, interactive_of("product", conn, retailer_id=rids[0]))
    return Native(
        text,
        interactive_of(
            "product_list", conn, header=product.name[:60], sections=[(product.name[:24], rids)]
        ),
    )
