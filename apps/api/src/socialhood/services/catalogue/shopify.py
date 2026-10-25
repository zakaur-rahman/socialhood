"""Shopify import (GR-31): connect a store, copy its products, and keep them in step.

Built like Facebook (GR-29) and Google Sheets (GR-27): it waits for the owner's Shopify Partner
account and app listing (O-10), so it is **off until the app's credentials are set** (connecting
answers 503 "not configured"), runs against a built-in store in development and the end-to-end
stack (shopify/fake.py), and **nothing here has run against a real store**: every Shopify
behaviour is listed as unverified in docs/CONFLICTS.md (C-116).

- **Access.** Shopify's offline access token, encrypted like platform tokens (SEC-03) and never
  returned. The plan must include the catalogue (``commerce``, PD-8). Owners and admins.
- **Connecting.** Like Instagram (X-1) the public callback never connects anything: it checks
  Shopify's signature, parks the code under a one-time nonce bound to the member and workspace
  that started it, and the signed-in Products page finishes with POST …/complete. A store belongs
  to one workspace at a time.
- **Sync** (the ``sync_shopify_products`` job): every product is read page by page and saved as a
  product with ``source = shopify`` and its Shopify id; a product no longer in the store is
  removed after a pass that read them all. Variants carry their own price, SKU and stock; a
  product with one "Default Title" variant is a product without variants. Stock is recorded only
  when Shopify tracks it. A product beyond the plan's ``catalogue_products`` is skipped and
  counted. Prices are in the store's currency.
- **Webhooks** (``products/create``, ``products/update``, ``products/delete``, ``app/uninstalled``
  and the privacy topics a listed app answers) arrive at POST /webhooks/shopify, are stored, and
  are applied by a job (services/webhook_handlers/shopify.py): the same save the sync uses.
  ``app/uninstalled`` marks the store as needing a reconnect; ``shop/redact`` removes the store
  and its products. We hold no customer data, so the customer topics change nothing.
- **Disconnecting** revokes the token as far as Shopify answers and removes the connection and,
  unless asked to keep them, the products it made: a price that is no longer kept in step must
  not be quoted to customers.
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.billing.entitlements import allows, check_capacity, check_entitlement
from socialhood.billing.plans import current_plan
from socialhood.errors import ApiError
from socialhood.models.catalogue import Product, ProductSource, ShopifyConnection, ShopifyStatus
from socialhood.observability.logging import get_logger
from socialhood.repositories import catalogue as repo
from socialhood.schemas.catalogue import ShopifyStatus as ShopifyStatusOut
from socialhood.security.crypto import TokenCipher
from socialhood.services.catalogue import money, products
from socialhood.services.catalogue.products import ProductData, VariantData
from socialhood.shopify.client import (
    PRIVACY_TOPICS,
    PRODUCT_TOPICS,
    ShopifyClient,
    ShopifyError,
    ShopifyProduct,
    normalize_shop,
)
from socialhood.webhooks.routing import shopify_owner

log = get_logger(__name__)

STATE_TTL_S = 600
HELD_TTL_S = 600
SYNC_STALE = timedelta(minutes=15)  # a sync that started longer ago is not still running
MAX_VARIANTS = 100
DEFAULT_TITLE = "Default Title"

NOT_CONFIGURED = "Shopify isn't set up on this server."
NOT_CONNECTED = "Connect Shopify first."
NEEDS_RECONNECT = "Reconnect Shopify first: access was removed."
CONNECT_EXPIRED = "That connection link expired. Connect Shopify again."
CONNECT_NOT_YOURS = (
    "This Shopify connection was started by someone else, so it wasn't added. To connect your "
    "own store, use Connect Shopify."
)
CONNECT_FAILED = "Shopify didn't respond. Try again."
SHOP_INVALID = "Enter your store's address, like my-store.myshopify.com."
SHOP_IN_USE = "This store is connected to another Amplychat workspace. Disconnect it there first."
UNINSTALLED = "Access was removed in Shopify. Reconnect to keep your products in step."
PLAN_STOPPED = "The catalogue is part of Pro, so the sync stopped."
CAP_STOPPED = "Some products weren't added: your plan includes {limit:,} products."

Applied = Literal["created", "updated", "skipped"]
SyncOutcome = Literal["missing", "reconnect", "plan", "done", "failed"]


# ---------------------------------------------------------------- reading


def syncing(conn: ShopifyConnection, now: datetime) -> bool:
    return conn.sync_started_at is not None and now - conn.sync_started_at < SYNC_STALE


async def get_status(
    session: AsyncSession, *, configured: bool, now: datetime | None = None
) -> ShopifyStatusOut:
    plan = await current_plan(session)
    entitled = allows(plan, products.KEY)
    conn = await repo.get_shopify(session)
    if conn is None:
        return ShopifyStatusOut(available=configured, entitled=entitled, connected=False)
    return ShopifyStatusOut(
        available=configured,
        entitled=entitled,
        connected=True,
        status=conn.status,
        shop_domain=conn.shop_domain,
        shop_name=conn.shop_name,
        currency=conn.currency,
        syncing=syncing(conn, now or datetime.now(UTC)),
        synced_at=conn.synced_at,
        sync_error=conn.sync_error,
        products_synced=conn.products_synced,
        products_skipped=conn.products_skipped,
        last_error=conn.last_error,
    )


# ---------------------------------------------------------------- connecting


def _held_key(nonce: str) -> str:
    return f"oauth:held:shopify:{nonce}"


async def start_connect(
    session: AsyncSession,
    redis: Redis,
    client: ShopifyClient,
    *,
    configured: bool,
    shop_text: str,
    workspace_id: uuid.UUID,
    slug: str,
    user_id: uuid.UUID,
) -> str:
    """Store a single-use OAuth state and return Shopify's install address. A store another
    workspace holds is refused (409)."""
    await check_entitlement(session, products.KEY)
    if not configured:
        raise ApiError("service_unavailable", NOT_CONFIGURED)
    shop = normalize_shop(shop_text)
    if shop is None:
        raise products.invalid("shop", SHOP_INVALID)
    owner = await shopify_owner(session, shop)
    if owner is not None and owner != workspace_id:
        raise ApiError("account_in_use", SHOP_IN_USE)
    state = secrets.token_urlsafe(32)
    await redis.set(
        f"oauth:{state}",
        json.dumps(
            {
                "user_id": str(user_id),
                "workspace_id": str(workspace_id),
                "slug": slug,
                "platform": "shopify",
                "shop": shop,
            }
        ),
        ex=STATE_TTL_S,
    )
    return client.authorize_url(shop, state)


async def hold_code(redis: Redis, cipher: TokenCipher, state: dict[str, str], code: str) -> str:
    """Park the code (encrypted) for the signed-in page; returns the nonce the callback sends."""
    nonce = secrets.token_urlsafe(32)
    held = {
        "user_id": state["user_id"],
        "workspace_id": state["workspace_id"],
        "shop": state["shop"],
        "code": cipher.encrypt(code).decode(),
    }
    await redis.set(_held_key(nonce), json.dumps(held), ex=HELD_TTL_S)
    return nonce


async def finish_connect(
    session: AsyncSession,
    redis: Redis,
    client: ShopifyClient,
    cipher: TokenCipher,
    *,
    nonce: str,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    webhook_address: str,
    now: datetime,
) -> ShopifyConnection:
    """POST …/complete: take the held code (once, whatever happens next), exchange it and save the
    connection; only the member and workspace that started it can."""
    raw = await redis.getdel(_held_key(nonce))
    if raw is None:
        raise ApiError("not_found", CONNECT_EXPIRED)
    held = json.loads(raw)
    if held["user_id"] != str(user_id) or held["workspace_id"] != str(workspace_id):
        log.warning("shopify_connect_refused", reason="not_the_starter")
        raise ApiError("forbidden", CONNECT_NOT_YOURS)
    await check_entitlement(session, products.KEY)
    shop = str(held["shop"])
    owner = await shopify_owner(session, shop)
    if owner is not None and owner != workspace_id:
        raise ApiError("account_in_use", SHOP_IN_USE)
    try:
        grant = await client.exchange_code(shop, cipher.decrypt(held["code"].encode()))
        info = await client.shop_info(shop, grant.access_token)
    except ShopifyError as error:
        log.warning("shopify_connect_failed", error_kind=error.kind)
        raise ApiError("platform_error", CONNECT_FAILED) from error
    conn = await repo.get_shopify(session, lock=True)
    token = cipher.encrypt(grant.access_token)
    if conn is None:
        conn = ShopifyConnection(shop_domain=shop, token_enc=token, connected_at=now)
        session.add(conn)
    conn.shop_domain = shop
    conn.shop_name = info.name
    conn.storefront_domain = info.storefront_domain
    conn.currency = (info.currency or "").upper() or None
    conn.token_enc = token
    conn.scopes = list(grant.scopes)
    conn.status = ShopifyStatus.ACTIVE
    conn.last_error = None
    conn.connected_by_user_id = user_id
    conn.connected_at = now
    await session.flush()
    await _subscribe(conn, client, grant.access_token, webhook_address)
    await session.flush()
    await session.refresh(conn)  # server-side defaults, read by the status
    return conn


async def _subscribe(
    conn: ShopifyConnection, client: ShopifyClient, token: str, address: str
) -> None:
    """Ask Shopify for the webhooks. A failure leaves the store connected, the topics it didn't
    confirm empty, and says so on the card: the sync still works, only live updates don't."""
    topics = (*PRODUCT_TOPICS, *PRIVACY_TOPICS)
    try:
        conn.webhook_topics = await client.register_webhooks(
            conn.shop_domain, token, topics, address
        )
    except ShopifyError as error:
        log.warning("shopify_webhooks_failed", error_kind=error.kind)
        conn.webhook_topics = []
        conn.last_error = (
            "Shopify wouldn't send live updates. Products are synced when you press Sync."
        )


async def disconnect(
    session: AsyncSession, client: ShopifyClient, cipher: TokenCipher, *, keep_products: bool
) -> None:
    conn = await repo.get_shopify(session, lock=True)
    if conn is None:
        return
    try:
        await client.revoke(conn.shop_domain, cipher.decrypt(conn.token_enc))
    except (ShopifyError, ValueError):
        log.warning("shopify_revoke_failed")
    await session.delete(conn)
    if not keep_products:
        await repo.delete_source(session, ProductSource.SHOPIFY)
    await session.flush()


# ---------------------------------------------------------------- mapping and saving


def _trim_sku(sku: str | None) -> str | None:
    return sku.strip()[:80] or None if sku else None


def to_data(
    shopify: ShopifyProduct, *, currency: str, storefront: str | None
) -> tuple[ProductData | None, int]:
    """The product as the catalogue holds it, and how many variants didn't fit. None when no
    price in it is readable (nothing to quote)."""
    variants = list(shopify.variants)
    cut = max(len(variants) - MAX_VARIANTS, 0)
    variants = variants[:MAX_VARIANTS]
    url = shopify.url or (
        f"https://{storefront}/products/{shopify.handle}" if storefront and shopify.handle else None
    )
    data = ProductData(
        name=shopify.title,
        currency=currency,
        description=shopify.description,
        url=products.quiet_https(url),
        image_url=products.quiet_https(shopify.image_url),
        active=shopify.status == "active",
        external_id=shopify.id,
    )
    plain = len(variants) == 1 and (variants[0].title == DEFAULT_TITLE or not variants[0].options)
    if plain:
        only = variants[0]
        price = money.from_decimal(only.price, currency) if only.price is not None else None
        if price is None:
            return None, cut
        data.price_minor, data.stock, data.sku = price, only.inventory, _trim_sku(only.sku)
        return data, cut
    seen: set[str] = set()
    for item in variants:
        price = money.from_decimal(item.price, currency) if item.price is not None else None
        if price is None:
            continue
        title = item.title if item.title.casefold() not in seen else f"{item.title} ({item.id})"
        seen.add(title.casefold())
        data.variants.append(
            VariantData(
                title=title[:120],
                price_minor=price,
                options=dict(list(item.options.items())[:3]),
                sku=_trim_sku(item.sku),
                stock=item.inventory,
                external_id=item.id,
            )
        )
    return (data, cut) if data.variants else (None, cut)


async def _free_skus(session: AsyncSession, data: ProductData, product: Product | None) -> None:
    """Shopify lets two products share a SKU; the catalogue doesn't. A SKU already used by
    another product is dropped here (the product is still found by name and its variants)."""
    named = [s for s in [data.sku, *(v.sku for v in data.variants)] if s]
    taken = await products.sku_conflicts(session, named, product_id=product.id if product else None)
    if data.sku in taken:
        data.sku = None
    seen: set[str] = set()
    for variant in data.variants:
        if variant.sku and (variant.sku in taken or variant.sku in seen):
            variant.sku = None
        elif variant.sku:
            seen.add(variant.sku)
    if data.sku and data.sku in seen:
        data.sku = None


async def apply_product(
    session: AsyncSession, conn: ShopifyConnection, shopify: ShopifyProduct
) -> Applied:
    """Create or update the catalogue's copy of one Shopify product."""
    data, _ = to_data(
        shopify,
        currency=conn.currency or money.DEFAULT_CURRENCY,
        storefront=conn.storefront_domain or conn.shop_domain,
    )
    if data is None:
        return "skipped"
    existing = await repo.by_external_id(session, shopify.id)
    if existing is None:
        plan = await current_plan(session)
        try:
            await check_capacity(session, "catalogue_products", plan=plan)
        except ApiError:
            return "skipped"
    else:
        data.image_asset_id = existing.image_asset_id  # a picture uploaded here is kept
    await _free_skus(session, data, existing)
    await products.save(session, data, source=ProductSource.SHOPIFY, product=existing)
    return "created" if existing is None else "updated"


async def remove_product(session: AsyncSession, external_id: str) -> bool:
    existing = await repo.by_external_id(session, external_id)
    if existing is None:
        return False
    await repo.delete_product(session, existing.id)
    return True


# ---------------------------------------------------------------- sync


def webhook_address(api_base_url: str | None) -> str:
    return f"{(api_base_url or '').rstrip('/')}/webhooks/shopify"


async def request_sync(session: AsyncSession, now: datetime) -> bool:
    """Mark a sync as started; False when one is already running. The caller commits, then
    queues the job (``enqueue_sync``)."""
    await check_entitlement(session, products.KEY)
    conn = await repo.get_shopify(session, lock=True)
    if conn is None:
        raise ApiError("conflict", NOT_CONNECTED)
    if conn.status != ShopifyStatus.ACTIVE:
        raise ApiError("conflict", NEEDS_RECONNECT)
    if syncing(conn, now):
        return False
    conn.sync_started_at = now
    conn.sync_error = None
    return True


async def enqueue_sync(workspace_id: uuid.UUID, *, delay_s: float = 0) -> None:
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.catalogue import sync_shopify_products

    try:
        await enqueue(
            sync_shopify_products,
            key=f"shopify-sync:{workspace_id}",
            delay_s=delay_s,
            workspace_id=str(workspace_id),
        )
    except Exception:  # never fail what asked for it; the card shows the sync as started
        log.warning("shopify_sync_enqueue_failed")


async def _stop(
    sessionmaker: async_sessionmaker[AsyncSession], *, error: str | None, reconnect: bool = False
) -> None:
    async with sessionmaker() as session:
        conn = await repo.get_shopify(session, lock=True)
        if conn is None:
            return
        conn.sync_started_at = None
        conn.sync_error = error
        if reconnect:
            conn.status = ShopifyStatus.NEEDS_RECONNECT
            conn.last_error = UNINSTALLED
        await session.commit()


async def run_sync(
    sessionmaker: async_sessionmaker[AsyncSession],
    client: ShopifyClient,
    cipher: TokenCipher,
    *,
    now: datetime,
    will_retry: bool = False,
) -> SyncOutcome:
    """One full pass over the store's products (the sync_shopify_products job; the caller has the
    workspace in scope). A retryable Shopify error is raised while the job has tries left."""
    async with sessionmaker() as session:
        conn = await repo.get_shopify(session, lock=True)
        if conn is None:
            return "missing"
        if conn.status != ShopifyStatus.ACTIVE:
            conn.sync_started_at = None
            await session.commit()
            return "reconnect"
        if not allows(await current_plan(session), products.KEY):
            conn.sync_started_at, conn.sync_error = None, PLAN_STOPPED
            await session.commit()
            return "plan"
        conn.sync_started_at, conn.sync_error = now, None
        shop, token = conn.shop_domain, cipher.decrypt(conn.token_enc)
        await session.commit()

    cursor: str | None = None
    seen: set[str] = set()
    created = updated = skipped = 0
    try:
        while True:
            page = await client.list_products(shop, token, cursor)
            async with sessionmaker() as session:
                conn = await repo.get_shopify(session)
                if conn is None:
                    return "missing"
                for item in page.products:
                    seen.add(item.id)
                    outcome = await apply_product(session, conn, item)
                    created += outcome == "created"
                    updated += outcome == "updated"
                    skipped += outcome == "skipped"
                await session.commit()
            cursor = page.next_cursor
            if cursor is None:
                break
    except ShopifyError as error:
        if error.retryable and will_retry:
            raise
        log.warning("shopify_sync_failed", error_kind=error.kind)
        auth = error.kind == "auth"
        await _stop(
            sessionmaker,
            error=UNINSTALLED if auth else "Shopify didn't respond. Press Sync to try again.",
            reconnect=auth,
        )
        return "reconnect" if auth else "failed"

    async with sessionmaker() as session:
        conn = await repo.get_shopify(session, lock=True)
        if conn is None:
            return "missing"
        gone = [
            pid
            for ext, pid in (await repo.external_ids(session, "shopify")).items()
            if ext not in seen
        ]
        await repo.delete_products(session, gone)
        cap = await _cap(session)
        conn.synced_at = now
        conn.sync_started_at = None
        conn.products_synced = created + updated
        conn.products_skipped = skipped
        conn.sync_error = CAP_STOPPED.format(limit=cap) if skipped and cap is not None else None
        await session.commit()
    log.info("shopify_synced", created=created, updated=updated, skipped=skipped, removed=len(gone))
    return "done"


async def _cap(session: AsyncSession) -> int | None:
    from socialhood.billing.plans import entitlement

    limit = entitlement(await current_plan(session), "catalogue_products")
    return None if limit is None else int(limit)


# ---------------------------------------------------------------- webhooks


async def handle_webhook(
    session: AsyncSession, conn: ShopifyConnection, topic: str, body: dict[str, Any]
) -> tuple[Literal["processed", "ignored"], str | None]:
    """Apply one verified webhook for ``conn`` (the caller has the workspace in scope)."""
    from socialhood.shopify.parse import from_webhook

    if topic == "app/uninstalled":
        conn.status = ShopifyStatus.NEEDS_RECONNECT
        conn.last_error = UNINSTALLED
        return "processed", None
    if topic == "shop/redact":
        await session.delete(conn)
        await repo.delete_source(session, ProductSource.SHOPIFY)
        return "processed", None
    if topic in ("customers/data_request", "customers/redact"):
        return "ignored", "no customer data is held"
    if topic not in ("products/create", "products/update", "products/delete"):
        return "ignored", "not a topic we use"
    if not allows(await current_plan(session), products.KEY):
        return "ignored", "the plan doesn't include the catalogue"
    if topic == "products/delete":
        from socialhood.shopify.client import numeric_id

        external = numeric_id(body.get("id", ""))
        if external is None:
            return "ignored", "no product id"
        removed = await remove_product(session, external)
        return ("processed", None) if removed else ("ignored", "an unknown product")
    parsed = from_webhook(body)
    if parsed is None:
        return "ignored", "unreadable product"
    outcome = await apply_product(session, conn, parsed)
    return ("ignored", "not saved") if outcome == "skipped" else ("processed", None)
