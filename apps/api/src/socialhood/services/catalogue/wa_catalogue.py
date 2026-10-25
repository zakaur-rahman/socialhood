"""The WhatsApp catalogue sync (GR-33): copy the workspace's products to a Meta commerce catalogue
so WhatsApp product and product-list messages can show them.

Built like Facebook (GR-29) and Shopify (GR-31): **nothing here has run against a real catalogue**.
It works against a sandbox catalogue for sandbox WhatsApp numbers (metacatalog/fake.py) and is
listed as unverified in docs/CONFLICTS.md (C-121).

- **What is copied.** Every active product: one catalogue item per variant, or one for a product
  without variants. The item's retailer id (Meta's ``product_retailer_id``) is our variant id or
  product id, so a message names exactly the row the customer sees. An item carries the title
  ("Cotton kurta - Blue / M"), description, availability (out of stock only when stock is recorded
  as 0), price ("799.00 INR"), the product's link, its picture and the brand. Meta requires a link
  and a picture: a product without them is not sent and says so on the card.
- **How it stays in step.** The ``sync_whatsapp_catalogue`` job compares what the catalogue should
  hold with what was last sent (a hash per item in ``catalogue_items``) and sends only what changed:
  new and changed items as upserts, and items whose product or variant is gone, or switched off, as
  deletes. It runs a moment after a product is added, changed, deleted or imported, after a Shopify
  sync, when Sync is pressed, and every few minutes as a safety net, so a missed trigger heals.
- **Access.** The WhatsApp number's own business token makes the calls (it is the account's, so
  nothing new is stored). Meta wants ``catalog_management`` (and ``business_management``) and the
  catalogue connected to the WhatsApp Business Account in WhatsApp Manager; both are unverified, so
  the connect step reports whatever Meta says in plain words.
- **Plan.** Connecting needs ``commerce`` (PD-8: Pro and Max). A downgrade stops the sync; what is
  in the catalogue stays.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.billing.entitlements import allows, check_entitlement
from socialhood.billing.plans import current_plan
from socialhood.errors import ApiError
from socialhood.metacatalog.client import (
    BATCH_SIZE,
    BatchItem,
    CatalogueClient,
    CatalogueError,
)
from socialhood.metacatalog.registry import get_catalogue
from socialhood.models.catalogue import (
    CatalogueConnection,
    CatalogueItem,
    CatalogueState,
    Product,
    ProductVariant,
)
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.identity import Workspace
from socialhood.observability.logging import get_logger
from socialhood.repositories import catalogue as repo
from socialhood.repositories import social_accounts as accounts
from socialhood.schemas.wa_catalogue import (
    WaCatalogueConnect,
    WaCatalogueProblem,
    WaCatalogueStatus,
)
from socialhood.security.crypto import TokenCipher
from socialhood.services.catalogue import money, products
from socialhood.settings import Settings

log = get_logger(__name__)

SYNC_STALE = timedelta(minutes=15)  # a sync that started longer ago is not still running
TITLE_MAX = 150  # Meta's title limit
DESCRIPTION_MAX = 5000
PROBLEMS_SHOWN = 5
TRIGGER_DELAY_S = 8.0  # after a change: the request that made it has committed by then

NOT_CONNECTED = "Connect a WhatsApp catalogue first."
NEEDS_ATTENTION = (
    "Meta no longer lets this number use the catalogue. Check the catalogue is connected to your "
    "WhatsApp Business Account and that Amplychat has catalogue access, then connect again."
)
CATALOGUE_NOT_FOUND = "Meta can't find that catalogue. Check the id in Commerce Manager."
CATALOGUE_DENIED = (
    "Meta doesn't let this number use that catalogue. Connect the catalogue to your WhatsApp "
    "Business Account in WhatsApp Manager, and allow catalogue access when you connect the number."
)
META_DOWN = "Meta didn't respond. Try again."
NOT_WHATSAPP = "Choose a WhatsApp number."
PLAN_STOPPED = "The catalogue is part of Pro, so the sync stopped."
NO_LINK = "Add a link to this product. Meta needs one for every catalogue item."
NO_PICTURE = "Add a picture to this product. Meta needs one for every catalogue item."


@dataclass
class Wanted:
    retailer_id: str
    product_id: uuid.UUID
    variant_id: uuid.UUID | None
    name: str
    data: dict[str, Any] | None  # None: it can't be sent as it is (``error`` says why)
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
    name = title
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
        return Wanted(rid, product.id, variant.id if variant else None, name, None, error)
    stock = variant.stock if variant is not None else product.stock
    description = (product.description or title)[:DESCRIPTION_MAX]
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
    }
    return Wanted(rid, product.id, variant.id if variant else None, name, data)


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


def syncing(conn: CatalogueConnection, now: datetime) -> bool:
    return conn.sync_started_at is not None and now - conn.sync_started_at < SYNC_STALE


async def status(session: AsyncSession, *, now: datetime | None = None) -> WaCatalogueStatus:
    now = now or datetime.now(UTC)
    entitled = allows(await current_plan(session), products.KEY)
    conn = await get(session)
    if conn is None:
        return WaCatalogueStatus(entitled=entitled, connected=False)
    counts = dict(
        (
            await session.execute(
                select(CatalogueItem.state, func.count()).group_by(CatalogueItem.state)
            )
        ).all()
    )
    broken = (
        await session.execute(
            select(CatalogueItem.retailer_id, CatalogueItem.error, Product.name)
            .outerjoin(Product, Product.id == CatalogueItem.product_id)
            .where(CatalogueItem.state == CatalogueState.ERROR)
            .order_by(CatalogueItem.updated_at.desc())
            .limit(PROBLEMS_SHOWN)
        )
    ).all()
    acct = await accounts.get(session, conn.social_account_id)
    label = None
    if acct is not None:
        label = acct.display_name or acct.phone_number or acct.username
    return WaCatalogueStatus(
        entitled=entitled,
        connected=True,
        status=conn.status,
        social_account_id=conn.social_account_id,
        account_label=label,
        catalog_id=conn.catalog_id,
        catalog_name=conn.catalog_name,
        brand=conn.brand,
        syncing=syncing(conn, now),
        synced_at=conn.synced_at,
        sync_error=conn.sync_error,
        last_error=conn.last_error,
        items_synced=int(counts.get(CatalogueState.SYNCED, 0)),
        items_pending=int(counts.get(CatalogueState.PENDING, 0)),
        items_error=int(counts.get(CatalogueState.ERROR, 0)),
        problems=[
            WaCatalogueProblem(name=name or retailer, message=error or "Meta refused this item.")
            for retailer, error, name in broken
        ],
    )


# ---------------------------------------------------------------- connecting


def token_of(acct: SocialAccount, cipher: TokenCipher) -> str:
    if not acct.access_token_enc:
        raise ApiError("account_needs_reconnect")
    return cipher.decrypt(acct.access_token_enc)


async def connect(
    session: AsyncSession,
    http: httpx.AsyncClient,
    settings: Settings,
    cipher: TokenCipher,
    body: WaCatalogueConnect,
    *,
    user_id: uuid.UUID,
) -> None:
    """Check the catalogue is visible to the number's token, then save the connection and mark
    every item as not yet sent. 402 without commerce on the plan, 404 for an account that isn't
    this workspace's, 422 for a number that isn't WhatsApp, 409 for a catalogue Meta won't show,
    502 when Meta doesn't answer."""
    acct = await accounts.get(session, body.social_account_id)
    if acct is None:
        raise ApiError("not_found")
    await check_entitlement(session, products.KEY, detail="The WhatsApp catalogue is part of Pro.")
    if acct.platform != "whatsapp" or acct.status == AccountStatus.DISCONNECTED:
        raise ApiError("validation_error", NOT_WHATSAPP)
    client = get_catalogue(http, settings, acct)
    try:
        info = await client.get_catalog(token_of(acct, cipher), body.catalog_id)
    except CatalogueError as error:
        raise _api_error(error) from error
    workspace = await session.get(Workspace, acct.workspace_id)
    brand = (body.brand or (workspace.name if workspace else "") or "Shop").strip()
    conn = await get(session, lock=True)
    if conn is None:
        conn = CatalogueConnection(social_account_id=acct.id, catalog_id=info.id, brand=brand)
        session.add(conn)
    conn.social_account_id = acct.id
    conn.catalog_id = info.id
    conn.catalog_name = info.name
    conn.brand = brand
    conn.status = "active"
    conn.last_error = conn.sync_error = None
    conn.connected_by_user_id = user_id
    conn.synced_at = None
    await session.flush()
    # A different catalogue holds none of what was sent before: send everything again.
    for item in (await session.scalars(select(CatalogueItem))).all():
        item.state, item.content_hash, item.error = CatalogueState.PENDING, None, None


def _api_error(error: CatalogueError) -> ApiError:
    if error.kind == "not_found":
        return ApiError("conflict", CATALOGUE_NOT_FOUND)
    if error.kind == "auth":
        return ApiError("conflict", CATALOGUE_DENIED)
    if error.kind == "rejected":
        return ApiError("conflict", CATALOGUE_DENIED)
    return ApiError("platform_error", META_DOWN)


async def disconnect(session: AsyncSession) -> None:
    """Forget the connection and what was sent. The catalogue itself is left as it is in Meta."""
    from socialhood.repositories.base import scoped_delete

    await session.execute(scoped_delete(CatalogueItem))
    await session.execute(scoped_delete(CatalogueConnection))


# ---------------------------------------------------------------- triggering


async def enqueue_sync(workspace_id: uuid.UUID, *, delay_s: float = 0) -> None:
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.catalogue import sync_whatsapp_catalogue

    try:
        await enqueue(
            sync_whatsapp_catalogue,
            key=f"wa-catalogue-sync:{workspace_id}",
            delay_s=delay_s,
            workspace_id=str(workspace_id),
        )
    except Exception:  # never fail what asked for it; the periodic sweep picks it up
        log.warning("wa_catalogue_sync_enqueue_failed")


async def touch(session: AsyncSession, workspace_id: uuid.UUID) -> None:
    """Products changed: queue a sync shortly, when a catalogue is connected. Call it after the
    commit that changed them. Cheap when nothing is connected."""
    if await get(session) is not None:
        await enqueue_sync(workspace_id, delay_s=TRIGGER_DELAY_S)


async def request_sync(session: AsyncSession, now: datetime) -> bool:
    """Sync now (the button): False when one is already running. The caller commits, then queues
    the job."""
    await check_entitlement(session, products.KEY, detail="The WhatsApp catalogue is part of Pro.")
    conn = await get(session, lock=True)
    if conn is None:
        raise ApiError("conflict", NOT_CONNECTED)
    if conn.status != "active":
        raise ApiError("conflict", NEEDS_ATTENTION)
    if syncing(conn, now):
        return False
    conn.sync_started_at = now
    conn.sync_error = None
    return True


# ---------------------------------------------------------------- the sync


async def run_sync(
    sessionmaker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
    settings: Settings,
    cipher: TokenCipher,
    *,
    now: datetime,
    will_retry: bool = False,
) -> str:
    """One pass (the sync_whatsapp_catalogue job; the caller has the workspace in scope): send
    what changed and delete what is gone. Returns ``missing``, ``plan``, ``reconnect``,
    ``failed`` or ``done``. A retryable Meta error is raised while the job has tries left."""
    async with sessionmaker() as session:
        conn = await get(session, lock=True)
        if conn is None:
            return "missing"
        if conn.status != "active":
            conn.sync_started_at = None
            await session.commit()
            return "reconnect"
        if not allows(await current_plan(session), products.KEY):
            conn.sync_started_at, conn.sync_error = None, PLAN_STOPPED
            await session.commit()
            return "plan"
        acct = await accounts.get(session, conn.social_account_id)
        if acct is None or acct.status in (
            AccountStatus.DISCONNECTED,
            AccountStatus.NEEDS_RECONNECT,
        ):
            conn.sync_started_at, conn.sync_error = None, NEEDS_ATTENTION
            await session.commit()
            return "reconnect"
        conn.sync_started_at = now
        client = get_catalogue(http, settings, acct)
        token, catalog_id, brand = token_of(acct, cipher), conn.catalog_id, conn.brand
        wanted = await wanted_items(session, brand)
        existing = {
            row.retailer_id: row for row in (await session.scalars(select(CatalogueItem))).all()
        }
        await session.commit()

    send: list[Wanted] = []
    local_errors: list[Wanted] = []
    for item in wanted:
        row = existing.get(item.retailer_id)
        if item.data is None:
            local_errors.append(item)
        elif row is None or row.content_hash != item.digest or row.state == CatalogueState.PENDING:
            send.append(item)
    wanted_ids = {item.retailer_id for item in wanted}
    gone = [rid for rid, row in existing.items() if rid not in wanted_ids]

    try:
        results = await _push(client, token, catalog_id, send, gone, existing)
    except CatalogueError as error:
        if error.retryable and will_retry:
            raise
        log.warning("wa_catalogue_sync_failed", error_kind=error.kind)
        auth = error.kind in ("auth", "not_found")
        await _stop(
            sessionmaker,
            error=NEEDS_ATTENTION if auth else "Meta didn't respond. Press Sync to try again.",
            reconnect=auth,
        )
        return "reconnect" if auth else "failed"

    async with sessionmaker() as session:
        conn = await get(session, lock=True)
        if conn is None:
            return "missing"
        await _record(session, send, local_errors, gone, results)
        conn.synced_at = now
        conn.sync_started_at = None
        conn.sync_error = None
        conn.last_error = None
        await session.commit()
    log.info("wa_catalogue_synced", sent=len(send), deleted=len(gone), unsendable=len(local_errors))
    return "done"


async def _push(
    client: CatalogueClient,
    token: str,
    catalog_id: str,
    send: list[Wanted],
    gone: list[str],
    existing: dict[str, CatalogueItem],
) -> dict[str, str]:
    """Send the upserts and the deletes in batches; the retailer ids Meta refused, with why."""
    refused: dict[str, str] = {}
    batch: list[BatchItem] = []

    async def flush() -> None:
        if batch:
            refused.update((await client.push(token, catalog_id, list(batch))).errors)
            batch.clear()

    for item in send:
        assert item.data is not None
        batch.append(BatchItem("UPDATE", item.retailer_id, item.data))
        if len(batch) >= BATCH_SIZE:
            await flush()
    for rid in gone:
        if existing[rid].content_hash is not None:  # never sent: nothing to delete in Meta
            batch.append(BatchItem("DELETE", rid))
            if len(batch) >= BATCH_SIZE:
                await flush()
    await flush()
    return refused


async def _record(
    session: AsyncSession,
    send: list[Wanted],
    local_errors: list[Wanted],
    gone: list[str],
    refused: dict[str, str],
) -> None:
    """Write down what happened to each item."""
    from socialhood.repositories.base import scoped_delete

    now = datetime.now(UTC)
    rows = {row.retailer_id: row for row in (await session.scalars(select(CatalogueItem))).all()}

    def row_for(item: Wanted) -> CatalogueItem:
        row = rows.get(item.retailer_id)
        if row is None:
            row = CatalogueItem(retailer_id=item.retailer_id)
            session.add(row)
            rows[item.retailer_id] = row
        row.product_id, row.variant_id = item.product_id, item.variant_id
        return row

    for item in send:
        row = row_for(item)
        if item.retailer_id in refused:
            row.state, row.error, row.content_hash = (
                CatalogueState.ERROR,
                refused[item.retailer_id],
                item.digest,  # not sent again until it changes
            )
        else:
            row.state, row.error, row.content_hash, row.synced_at = (
                CatalogueState.SYNCED,
                None,
                item.digest,
                now,
            )
    for item in local_errors:
        row = row_for(item)
        row.state, row.error = CatalogueState.ERROR, item.error
    for rid in gone:
        await session.execute(scoped_delete(CatalogueItem, retailer_id=rid))
    await session.flush()


async def _stop(
    sessionmaker: async_sessionmaker[AsyncSession], *, error: str, reconnect: bool
) -> None:
    async with sessionmaker() as session:
        conn = await get(session, lock=True)
        if conn is None:
            return
        conn.sync_started_at = None
        conn.sync_error = error
        if reconnect:
            conn.status = "needs_reconnect"
        await session.commit()
