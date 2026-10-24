"""Shopify's product JSON as ``ShopifyProduct`` (GR-31), from the two shapes it comes in:

- the Admin GraphQL ``products`` list the sync reads (``from_graphql``);
- a product webhook's body (``from_webhook``), the REST-shaped JSON Shopify posts for
  ``products/create`` and ``products/update``.

Both are read defensively: a missing field is None, an unreadable product is None (skipped and
counted), and nothing is trusted for length. *Unverified* against a live store: the field names
follow Shopify's published schemas.
"""

from __future__ import annotations

import html
import re
from typing import Any

from socialhood.shopify.client import ShopifyProduct, ShopifyVariant, numeric_id

_TAGS = re.compile(r"<[^>]*>")
_BREAKS = re.compile(r"(?i)<br\s*/?>|</p>|</li>")
DEFAULT_TITLE = "Default Title"  # what Shopify calls the one variant of a product without options
MAX_TEXT = 2000


def plain_text(markup: object) -> str | None:
    """The product description without HTML, in one paragraph's worth of lines."""
    if not isinstance(markup, str) or not markup.strip():
        return None
    text = html.unescape(_TAGS.sub("", _BREAKS.sub("\n", markup)))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    out = "\n".join(line for line in lines if line)
    return out[:MAX_TEXT] or None


def _int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _text(value: object, limit: int) -> str | None:
    return value.strip()[:limit] or None if isinstance(value, str) else None


def _price(value: object) -> str | None:
    return (
        str(value) if isinstance(value, str | int | float) and not isinstance(value, bool) else None
    )


def from_graphql(node: dict[str, Any]) -> ShopifyProduct | None:
    product_id = numeric_id(node.get("id", ""))
    title = _text(node.get("title"), 200)
    if product_id is None or title is None:
        return None
    variants = []
    for item in (node.get("variants") or {}).get("nodes") or []:
        variant_id = numeric_id(item.get("id", ""))
        if variant_id is None:
            continue
        options = {
            str(o["name"])[:40]: str(o["value"])[:80]
            for o in (item.get("selectedOptions") or [])
            if isinstance(o, dict) and o.get("name") and o.get("value")
        }
        variants.append(
            ShopifyVariant(
                id=variant_id,
                title=_text(item.get("title"), 120) or variant_id,
                sku=_text(item.get("sku"), 80),
                price=_price(item.get("price")),
                inventory=(
                    _int(item.get("inventoryQuantity"))
                    if (item.get("inventoryItem") or {}).get("tracked")
                    else None  # an untracked variant has no stock to report, not 0
                ),
                options=options,
            )
        )
    image = node.get("featuredImage") or {}
    return ShopifyProduct(
        id=product_id,
        title=title,
        description=plain_text(node.get("descriptionHtml")),
        handle=_text(node.get("handle"), 255),
        url=_text(node.get("onlineStoreUrl"), 2000),
        status=str(node.get("status") or "ACTIVE").casefold(),
        image_url=_text(image.get("url") if isinstance(image, dict) else None, 2000),
        variants=tuple(variants),
    )


def from_webhook(body: dict[str, Any]) -> ShopifyProduct | None:
    product_id = numeric_id(body.get("id", ""))
    title = _text(body.get("title"), 200)
    if product_id is None or title is None:
        return None
    names = [
        str(o.get("name") or "")[:40] for o in (body.get("options") or []) if isinstance(o, dict)
    ]
    variants = []
    for item in body.get("variants") or []:
        if not isinstance(item, dict):
            continue
        variant_id = numeric_id(item.get("id", ""))
        if variant_id is None:
            continue
        options = {}
        for position, name in enumerate(names, start=1):
            value = item.get(f"option{position}")
            if name and isinstance(value, str) and value.strip():
                options[name] = value.strip()[:80]
        inventory = item.get("inventory_quantity")
        variants.append(
            ShopifyVariant(
                id=variant_id,
                title=_text(item.get("title"), 120) or variant_id,
                sku=_text(item.get("sku"), 80),
                price=_price(item.get("price")),
                inventory=_int(inventory) if item.get("inventory_management") else None,
                options=options,
            )
        )
    image = body.get("image") if isinstance(body.get("image"), dict) else {}
    return ShopifyProduct(
        id=product_id,
        title=title,
        description=plain_text(body.get("body_html")),
        handle=_text(body.get("handle"), 255),
        url=None,  # a webhook has no storefront address; the handle builds one
        status=str(body.get("status") or "active").casefold(),
        image_url=_text(image.get("src") if isinstance(image, dict) else None, 2000),
        variants=tuple(variants),
    )
