"""Product catalogue API (GR-31): products with variants, CSV import, and the Shopify store.

The rules are in services/catalogue/: products.py (create, change, delete, the plan), csv_import.py
(the header row, the preview, the save), shopify.py (connect, sync, webhooks) and facts.py (how the
AI reads products). Reading what exists is never refused (owners and admins, like Knowledge);
writing needs ``knowledge.manage`` and the catalogue on the plan (PD-8: Pro and Max, 402
``entitlement_required`` on Free), connecting Shopify needs ``integrations.manage``.

A request that names another workspace's picture or product is a 404 before any plan check, so
nothing reveals what exists.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from socialhood.auth.deps import Admin, CanManageIntegrations, CanManageKnowledge, Session
from socialhood.schemas.catalogue import (
    CsvImport,
    ImportPreview,
    ImportResult,
    ProductCreate,
    ProductList,
    ProductOut,
    ProductPatch,
    ShopifyConnectComplete,
    ShopifyConnectRequest,
    ShopifyConnectStart,
    ShopifyStatus,
)
from socialhood.security.crypto import TokenCipher, cipher_for
from socialhood.services import audit
from socialhood.services.catalogue import csv_import, products
from socialhood.services.catalogue import shopify as shopify_service
from socialhood.settings import Settings
from socialhood.shopify.client import ShopifyClient
from socialhood.shopify.registry import configured, get_shopify

router = APIRouter(prefix="/v1/w/{wid}", tags=["catalogue"])


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _cipher(request: Request) -> TokenCipher:
    return cipher_for(tuple(_settings(request).token_encryption_keys))


def _client(request: Request) -> ShopifyClient:
    return get_shopify(request.app.state.http, _settings(request), request.app.state.redis)


# ---------------------------------------------------------------- products


@router.get("/products", operation_id="list_products")
async def list_products(
    ctx: Admin,
    session: Session,
    q: Annotated[str | None, Query(max_length=100)] = None,
    active: bool | None = None,
    source: Annotated[str | None, Query(pattern="^(manual|csv|shopify)$", max_length=8)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> ProductList:
    """Newest first, with the plan's limits. ``q`` matches names, SKUs and variant words."""
    return await products.list_products(
        session, q=q, active=active, source=source, limit=limit, offset=offset
    )


@router.post("/products", status_code=201, operation_id="create_product")
async def create_product(
    body: ProductCreate, ctx: CanManageKnowledge, session: Session
) -> ProductOut:
    """Name, price (or variants that each have one), stock, picture and link. 402
    ``entitlement_required`` without the catalogue on the plan, 402 ``quota_exceeded`` over its
    products, 422 on the fields, 404 for a picture that isn't this workspace's."""
    product = await products.create(session, body)
    out = await products.view(session, product)
    await audit.record(session, ctx, "product.created", "product", product.id, source="manual")
    await session.commit()
    return out


@router.get("/products/{product_id}", operation_id="get_product")
async def get_product(product_id: uuid.UUID, ctx: Admin, session: Session) -> ProductOut:
    return await products.view(session, await products.get(session, product_id))


@router.patch("/products/{product_id}", operation_id="update_product")
async def update_product(
    product_id: uuid.UUID, body: ProductPatch, ctx: CanManageKnowledge, session: Session
) -> ProductOut:
    """Only the fields sent change; ``variants`` replaces the list (a variant is kept by its id)."""
    product = await products.update(session, product_id, body)
    out = await products.view(session, product)
    await audit.record(session, ctx, "product.updated", "product", product_id)
    await session.commit()
    return out


@router.delete("/products/{product_id}", status_code=204, operation_id="delete_product")
async def delete_product(
    product_id: uuid.UUID, ctx: CanManageKnowledge, session: Session
) -> Response:
    await products.delete(session, product_id)
    await audit.record(session, ctx, "product.deleted", "product", product_id)
    await session.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------- CSV import


@router.post("/products/import/preview", operation_id="preview_product_import")
async def preview_product_import(
    body: CsvImport, ctx: CanManageKnowledge, session: Session
) -> ImportPreview:
    """Read the file and say, line by line, what would be created, updated or left out and why.
    Saves nothing. 402 over the plan's rows, 422 for a file with no header row."""
    return csv_import.preview(await csv_import.plan(session, body.csv))


@router.post("/products/import", operation_id="import_products")
async def import_products(
    body: CsvImport, ctx: CanManageKnowledge, session: Session
) -> ImportResult:
    """Save the file's valid lines (the same reading as the preview); lines with problems are
    skipped and counted."""
    planned = await csv_import.plan(session, body.csv)
    result = await csv_import.apply(session, planned)
    await audit.record(
        session,
        ctx,
        "product.imported",
        "product",
        None,
        created=result.created,
        updated=result.updated,
        skipped=result.skipped,
    )
    await session.commit()
    return result


# ---------------------------------------------------------------- Shopify


@router.get("/integrations/shopify", operation_id="get_shopify")
async def get_shopify_status(request: Request, ctx: Admin, session: Session) -> ShopifyStatus:
    """The store connection, its last sync, and whether Shopify is set up on this server."""
    return await shopify_service.get_status(session, configured=configured(_settings(request)))


@router.post("/integrations/shopify/connect", operation_id="start_shopify_connect")
async def start_shopify_connect(
    request: Request, body: ShopifyConnectRequest, ctx: CanManageIntegrations, session: Session
) -> ShopifyConnectStart:
    """Shopify's install address for the store. 402 without the catalogue on the plan, 503 when
    the Shopify app isn't set up on this server, 409 for a store another workspace holds."""
    url = await shopify_service.start_connect(
        session,
        request.app.state.redis,
        _client(request),
        configured=configured(_settings(request)),
        shop_text=body.shop,
        workspace_id=ctx.workspace_id,
        slug=ctx.workspace.slug,
        user_id=ctx.user.id,
    )
    return ShopifyConnectStart(authorize_url=url)


@router.post("/integrations/shopify/complete", operation_id="complete_shopify_connect")
async def complete_shopify_connect(
    request: Request, body: ShopifyConnectComplete, ctx: CanManageIntegrations, session: Session
) -> ShopifyStatus:
    """Finish a connect with the nonce the OAuth callback redirected with. Only the member who
    started it, in the workspace they started it in, can finish it; the nonce works once and for 10
    minutes. 404 when it expired or was used, 403 when someone else started it, 502 when Shopify
    fails. The first sync starts at once."""
    settings = _settings(request)
    await shopify_service.finish_connect(
        session,
        request.app.state.redis,
        _client(request),
        _cipher(request),
        nonce=body.nonce,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
        webhook_address=shopify_service.webhook_address(settings.api_base_url),
        now=datetime.now(UTC),
    )
    await shopify_service.request_sync(session, datetime.now(UTC))
    await audit.record(session, ctx, "shopify.connected", "shopify")
    out = await shopify_service.get_status(session, configured=configured(settings))
    await session.commit()
    await shopify_service.enqueue_sync(ctx.workspace_id)
    return out


@router.post("/integrations/shopify/sync", status_code=202, operation_id="sync_shopify")
async def sync_shopify(
    request: Request, ctx: CanManageIntegrations, session: Session
) -> ShopifyStatus:
    """Copy the store's products again now. While one sync runs this changes nothing."""
    queued = await shopify_service.request_sync(session, datetime.now(UTC))
    out = await shopify_service.get_status(session, configured=configured(_settings(request)))
    await session.commit()
    if queued:
        await shopify_service.enqueue_sync(ctx.workspace_id)
    return out


@router.delete("/integrations/shopify", status_code=204, operation_id="disconnect_shopify")
async def disconnect_shopify(
    request: Request,
    ctx: CanManageIntegrations,
    session: Session,
    keep_products: bool = False,
) -> Response:
    """Revoke Shopify's access and remove the connection and, unless ``keep_products``, the
    products it made (they would no longer be kept in step)."""
    await shopify_service.disconnect(
        session, _client(request), _cipher(request), keep_products=keep_products
    )
    await audit.record(
        session, ctx, "shopify.disconnected", "shopify", None, kept_products=keep_products
    )
    await session.commit()
    return Response(status_code=204)
