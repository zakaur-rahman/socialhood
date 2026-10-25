"""The message a flow's "send product" step sends (GR-31): name, price, stock when it is recorded,
and the link, read from the catalogue when the step runs, so a price or stock changed since the
flow was saved is what goes out.

    Here's the one you asked about:

    Cotton kurta - Blue / M
    INR 799.00
    In stock
    https://shop.example/kurta

A step that names a variant sends that variant. A step without one sends the product: its price
when it has no variants, else a list of up to six variants with their prices. Stock is said only
when it is recorded ("In stock", "Out of stock"); never guessed. The picture goes as the message's
attachment when the product has an uploaded one (an address elsewhere can't be attached, so the
link in the text stands in). A product that is gone, switched off, or a variant that is gone, is a
plain reason and the step fails, like a deleted saved reply.

Instagram allows 1,000 bytes of text, so the message is cut to ``MAX_BYTES``: variants are dropped
from the end first, then the intro.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.catalogue import Product, ProductVariant
from socialhood.repositories import catalogue as repo
from socialhood.services.catalogue import money

MAX_BYTES = 900
MAX_LISTED = 6
GONE = ("product_gone", "The product was deleted or switched off, so nothing was sent.")
VARIANT_GONE = ("variant_gone", "The product's variant was deleted, so nothing was sent.")


@dataclass(frozen=True)
class ProductMessage:
    text: str
    image_asset_id: uuid.UUID | None = None


class Unavailable(Exception):
    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def stock_line(stock: int | None) -> str | None:
    if stock is None:
        return None
    return "Out of stock" if stock <= 0 else "In stock"


def _one(product: Product, variant: ProductVariant | None) -> list[str]:
    if variant is None:
        title, price, stock = product.name, product.price_minor, product.stock
    else:
        title, price, stock = (
            f"{product.name} - {variant.title}",
            variant.price_minor,
            variant.stock,
        )
    lines = [title]
    if price is not None:
        lines.append(money.label(price, product.currency))
    if line := stock_line(stock):
        lines.append(line)
    return lines


def _listed(product: Product, variants: list[ProductVariant]) -> list[str]:
    lines = [product.name]
    for variant in variants[:MAX_LISTED]:
        suffix = ", out of stock" if variant.stock is not None and variant.stock <= 0 else ""
        lines.append(
            f"{variant.title}: {money.label(variant.price_minor, product.currency)}{suffix}"
        )
    return lines


def _fit(intro: str, body: list[str], link: str | None) -> str:
    """The text within MAX_BYTES: lines after the first are dropped from the end, then the intro."""
    keep = list(body)
    while True:
        parts = [*([intro, ""] if intro else []), "\n".join(keep), *([link] if link else [])]
        text = "\n".join(parts).strip()
        if len(text.encode()) <= MAX_BYTES:
            return text
        if len(keep) > 1:
            keep.pop()
        elif intro:
            intro = ""
        else:
            return keep[0].encode()[:MAX_BYTES].decode(errors="ignore")


async def build(
    session: AsyncSession,
    product_id: uuid.UUID,
    variant_id: uuid.UUID | None,
    intro: str = "",
) -> ProductMessage:
    """Raises ``Unavailable`` when the product or the variant is gone, or the product is off."""
    product = await repo.get(session, product_id)
    if product is None or not product.active:
        raise Unavailable(*GONE)
    variants = (await repo.variants_of(session, [product.id])).get(product.id, [])
    if variant_id is not None:
        chosen = next((v for v in variants if v.id == variant_id), None)
        if chosen is None:
            raise Unavailable(*VARIANT_GONE)
        body = _one(product, chosen)
    elif variants:
        body = _listed(product, variants)
    else:
        body = _one(product, None)
    text = _fit(intro.strip(), body, product.url)
    return ProductMessage(text=text, image_asset_id=product.image_asset_id)
