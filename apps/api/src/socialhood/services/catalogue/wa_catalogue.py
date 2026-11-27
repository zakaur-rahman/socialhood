"""The WhatsApp catalogue (GR-33, C-215): the workspace's products in a Meta commerce catalogue, so
WhatsApp product and product-list messages can show them.

**By scheduled feed (C-215).** Meta's WhatsApp sign-up never gives an app access to a catalogue,
so Amplychat can't push items to it. Instead it publishes the products at a secret link
(``GET /v1/feeds/whatsapp-catalogue/{token}.csv``, api/v1/catalogue_feed.py), and the business
adds that link in Commerce Manager as a scheduled data feed (Data sources, Data file, Upload via
URL, hourly). Each fetch replaces the catalogue's items with the feed's.

- **What is in the feed.** Every active product: one item per variant (grouped by
  ``item_group_id``), or one for a product without variants. The item's id is Meta's
  ``product_retailer_id``: our variant id or product id, so a message or a customer's cart names
  exactly the row the customer sees. An item carries the title ("Cotton kurta - Blue / M"),
  description, availability (out of stock only when stock is recorded as 0), condition, price
  ("799.00 INR"), the product's link, its picture and the brand. Meta requires a link and a
  picture: a product without them is left out and says so on the card.
- **What Meta has.** Each fetch records what it was given: ``catalogue_items`` holds one row per
  item in the last fetch, with the hash of its content. Product messages offer only those items.
  Any fetch counts, also someone opening the link in a browser (C-215: Meta's fetcher can't be
  told apart reliably).
- **The link.** A random token; New link replaces it and the old one stops working. Unknown
  tokens, and a workspace whose plan no longer has commerce, get 404, so Meta keeps the items it
  has (PD-8: Creator and Business).
- **Connecting** saves the WhatsApp number and the catalogue id without asking Meta (it won't
  show the catalogue to the app); the id is what product messages name.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import allows, check_entitlement
from socialhood.billing.plans import current_plan
from socialhood.errors import ApiError
from socialhood.models.catalogue import (
    CatalogueConnection,
    CatalogueItem,
    CatalogueState,
    Product,
    ProductVariant,
)
from socialhood.models.connections import AccountStatus
from socialhood.models.identity import Workspace
from socialhood.repositories import catalogue as repo
from socialhood.repositories import social_accounts as accounts
from socialhood.repositories.base import scoped_delete
from socialhood.schemas.wa_catalogue import (
    WaCatalogueConnect,
    WaCatalogueProblem,
    WaCatalogueStatus,
)
from socialhood.services.catalogue import money, products

TITLE_MAX = 150  # Meta's title limit
DESCRIPTION_MAX = 5000
PROBLEMS_SHOWN = 5
FEED_PATH = "/v1/feeds/whatsapp-catalogue/{token}.csv"
FEED_COLUMNS = (
    "id",
    "title",
    "description",
    "availability",
    "condition",
    "price",
    "link",
    "image_link",
    "brand",
    "item_group_id",
)

NOT_CONNECTED = "Connect a WhatsApp catalogue first."
NOT_WHATSAPP = "Choose a WhatsApp number."
PLAN_STOPPED = "The catalogue is part of Creator and Business, so Meta can no longer fetch it."
PLAN_DETAIL = "The WhatsApp catalogue is part of Creator and Business."
NO_LINK = "Add a link to this product. Meta needs one for every catalogue item."
NO_PICTURE = "Add a picture to this product. Meta needs one for every catalogue item."


@dataclass
class Wanted:
    retailer_id: str
    product_id: uuid.UUID
    variant_id: uuid.UUID | None
    name: str
    data: dict[str, Any] | None  # None: it can't be in the feed as it is (``error`` says why)
    error: str | None = None

    @property
    def digest(self) -> str | None:
        if self.data is None:
            return None
        return hashlib.sha256(json.dumps(self.data, sort_keys=True).encode()).hexdigest()


def retailer_id(product: Product, variant: ProductVariant | None) -> str:
    return str(variant.id if variant is not None else product.id)


def _availability(stock: int | None) -> str:
    return "out of stock" if stock is not None and stock <= 0 else "in stock"


def wanted_item(
    product: Product,
    variant: ProductVariant | None,
    *,
    brand: str,
    image_url: str | None,
) -> Wanted:
    """What the catalogue should hold for one variant, or for a product without variants."""
    title = f"{product.name} - {variant.title}" if variant is not None else product.name
    price = variant.price_minor if variant is not None else product.price_minor
    rid = retailer_id(product, variant)
    link = product.url
    picture = image_url or product.image_url
    error = None
    if price is None:
        error = "Add a price to this product."
    elif not link:
        error = NO_LINK
    elif not picture:
        error = NO_PICTURE
    if error is not None or price is None or link is None or picture is None:
        return Wanted(rid, product.id, variant.id if variant else None, title, None, error)
    stock = variant.stock if variant is not None else product.stock
    description = " ".join((product.description or title).split())[:DESCRIPTION_MAX]
    data = {
        "id": rid,
        "title": title[:TITLE_MAX],
        "description": description,
        "availability": _availability(stock),
        "condition": "new",
        "price": f"{money.plain(price, product.currency)} {product.currency}",
        "link": link,
        "image_link": picture,
        "brand": brand[:100],
        "item_group_id": str(product.id) if variant is not None else "",
    }
    return Wanted(rid, product.id, variant.id if variant else None, title, data)


async def wanted_items(session: AsyncSession, brand: str) -> list[Wanted]:
    """Every active product's items, in a stable order."""
    rows = list(
        (
            await session.scalars(
                select(Product)
                .where(Product.active.is_(True))
                .order_by(Product.created_at, Product.id)
            )
        ).all()
    )
    variants = await repo.variants_of(session, [p.id for p in rows])
    pictures = await repo.image_urls(session, [p.image_asset_id for p in rows if p.image_asset_id])
    found: list[Wanted] = []
    for product in rows:
        own = variants.get(product.id, [])
        picture = pictures.get(product.image_asset_id) if product.image_asset_id else None
        if own:
            found += [wanted_item(product, v, brand=brand, image_url=picture) for v in own]
        else:
            found.append(wanted_item(product, None, brand=brand, image_url=picture))
    return found


# ---------------------------------------------------------------- reading


async def get(session: AsyncSession, *, lock: bool = False) -> CatalogueConnection | None:
    query = select(CatalogueConnection)
    if lock:
        query = query.with_for_update()
    return (await session.scalars(query)).one_or_none()


def feed_url(base: str, token: str) -> str:
    return base.rstrip("/") + FEED_PATH.format(token=token)


async def status(session: AsyncSession, *, feed_base: str | None = None) -> WaCatalogueStatus:
    """The connection and, item by item, how the feed stands against Meta's last fetch.
    ``feed_base`` (the API's public address) is given only to owners and admins, who see the
    link."""
    entitled = allows(await current_plan(session), products.KEY)
    conn = await get(session)
    if conn is None:
        return WaCatalogueStatus(entitled=entitled, connected=False)
    wanted = await wanted_items(session, conn.brand)
    fetched = {
        row.retailer_id: row.content_hash
        for row in (await session.scalars(select(CatalogueItem))).all()
    }
    broken = [w for w in wanted if w.data is None]
    acct = await accounts.get(session, conn.social_account_id)
    label = None
    if acct is not None:
        label = acct.display_name or acct.phone_number or acct.username
    return WaCatalogueStatus(
        entitled=entitled,
        connected=True,
        social_account_id=conn.social_account_id,
        account_label=label,
        catalog_id=conn.catalog_id,
        brand=conn.brand,
        feed_url=feed_url(feed_base, conn.feed_token) if feed_base and conn.feed_token else None,
        feed_fetched_at=conn.feed_fetched_at,
        last_error=None if entitled else PLAN_STOPPED,
        items_synced=len(fetched),
        items_pending=sum(
            1 for w in wanted if w.data is not None and fetched.get(w.retailer_id) != w.digest
        ),
        items_error=len(broken),
        problems=[
            WaCatalogueProblem(name=w.name, message=w.error or "") for w in broken[:PROBLEMS_SHOWN]
        ],
    )


# ---------------------------------------------------------------- connecting


def new_token() -> str:
    return secrets.token_urlsafe(32)


async def connect(session: AsyncSession, body: WaCatalogueConnect, *, user_id: uuid.UUID) -> None:
    """Save the number and the catalogue id, and make the feed link if there is none. 402 without
    commerce on the plan, 404 for an account that isn't this workspace's, 422 for a number that
    isn't WhatsApp. Meta isn't asked: it doesn't show catalogues to the app (C-215)."""
    acct = await accounts.get(session, body.social_account_id)
    if acct is None:
        raise ApiError("not_found")
    await check_entitlement(session, products.KEY, detail=PLAN_DETAIL)
    if acct.platform != "whatsapp" or acct.status == AccountStatus.DISCONNECTED:
        raise ApiError("validation_error", NOT_WHATSAPP)
    workspace = await session.get(Workspace, acct.workspace_id)
    brand = (body.brand or (workspace.name if workspace else "") or "Shop").strip()
    conn = await get(session, lock=True)
    if conn is None:
        conn = CatalogueConnection(
            social_account_id=acct.id, catalog_id=body.catalog_id, brand=brand
        )
        session.add(conn)
    elif conn.catalog_id != body.catalog_id:
        # Another catalogue holds none of what Meta fetched into the old one.
        await session.execute(scoped_delete(CatalogueItem))
        conn.feed_fetched_at = None
    conn.social_account_id = acct.id
    conn.catalog_id = body.catalog_id
    conn.catalog_name = None
    conn.brand = brand
    conn.status = "active"
    conn.last_error = conn.sync_error = None
    conn.connected_by_user_id = user_id
    conn.feed_token = conn.feed_token or new_token()
    await session.flush()


async def new_link(session: AsyncSession) -> None:
    """Replace the feed link; the old one stops working at once."""
    conn = await get(session, lock=True)
    if conn is None:
        raise ApiError("conflict", NOT_CONNECTED)
    conn.feed_token = new_token()
    await session.flush()


async def disconnect(session: AsyncSession) -> None:
    """Forget the connection, its link and what Meta fetched. The catalogue itself is left as it
    is in Meta."""
    await session.execute(scoped_delete(CatalogueItem))
    await session.execute(scoped_delete(CatalogueConnection))


# ---------------------------------------------------------------- the feed


def render(items: list[Wanted]) -> str:
    """Meta's data-file format: a header row, then one row per item."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FEED_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for item in items:
        assert item.data is not None
        writer.writerow(item.data)
    return out.getvalue()


async def fetch(session: AsyncSession, *, now: datetime | None = None) -> str | None:
    """Meta's fetch of the feed (the caller has the workspace in scope and commits): the CSV, and
    what it held recorded as Meta's. None when nothing may be served (no connection, or the plan
    lost commerce)."""
    now = now or datetime.now(UTC)
    conn = await get(session, lock=True)  # one fetch at a time records
    if conn is None or not allows(await current_plan(session), products.KEY):
        return None
    served = [w for w in await wanted_items(session, conn.brand) if w.data is not None]
    rows = {row.retailer_id: row for row in (await session.scalars(select(CatalogueItem))).all()}
    for item in served:
        row = rows.pop(item.retailer_id, None)
        if row is None:
            row = CatalogueItem(retailer_id=item.retailer_id)
            session.add(row)
        row.product_id, row.variant_id = item.product_id, item.variant_id
        row.state, row.error = CatalogueState.SYNCED, None
        row.content_hash, row.synced_at = item.digest, now
    for gone in rows:  # not in this fetch: Meta removes it from the catalogue
        await session.execute(scoped_delete(CatalogueItem, retailer_id=gone))
    conn.feed_fetched_at = now
    await session.flush()
    return render(served)
