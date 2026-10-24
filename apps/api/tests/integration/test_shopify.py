"""GR-31: Shopify import on the built-in store. The OAuth round trip and its nonce, the plan, the
sync (products, variants, prices, stock, removal, the plan's cap), the signed webhooks that keep
products in step, and disconnecting. Nothing here proves a real Shopify store behaves this way:
see docs/CONFLICTS.md, C-116."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing import plans
from socialhood.db.tenancy import workspace_scope
from socialhood.models.platform import WebhookStatus
from socialhood.security.crypto import cipher_for
from socialhood.services.catalogue import shopify
from socialhood.services.webhook_processing import process_event
from socialhood.shopify.fake import FakeShopify, seed_products
from socialhood.shopify.signatures import sign_webhook
from tests.support.api import SHOPIFY_SECRET, Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.ingest import jobs, sessions

BASE = "/integrations/shopify"
SHOP = "my-store.myshopify.com"


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None) -> Ws:
    made = await workspace(client, clerk)
    await set_plan(engine, made.wid, "pro")
    return made


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def connect(ws: Ws, client: httpx.AsyncClient, shop: str = "my-store") -> dict[str, Any]:
    """The whole round trip on the built-in store: connect, the callback, complete."""
    started = await ws.ok("POST", f"{BASE}/connect", json={"shop": shop})
    query = parse_qs(urlsplit(started["authorize_url"]).query)
    callback = await client.get(
        "/v1/oauth/shopify/callback",
        params={k: v[0] for k, v in query.items()},
    )
    assert callback.status_code == 303, callback.text
    target = urlsplit(callback.headers["location"])
    assert target.path.endswith("/products")
    nonce = parse_qs(target.query)["shopify"][0]
    return await ws.ok("POST", f"{BASE}/complete", json={"nonce": nonce}, status=200)


async def sync(app: FastAPI, engine: AsyncEngine, ws: Ws, fake: FakeShopify) -> str:
    settings = app.state.settings
    with workspace_scope(uuid.UUID(ws.wid)):
        return await shopify.run_sync(
            sessions(engine),
            fake,
            cipher_for(tuple(settings.token_encryption_keys)),
            now=datetime.now(UTC),
        )


async def products(ws: Ws) -> dict[str, dict[str, Any]]:
    listing = await ws.ok("GET", "/products", params={"limit": 200})
    return {p["name"]: p for p in listing["items"]}


# ---------------------------------------------------------------- connecting


async def test_free_is_told_to_upgrade_and_an_unset_app_says_so(
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    queue: None,
    monkeypatch: pytest.MonkeyPatch,
    app: FastAPI,
) -> None:
    free = await workspace(client, clerk)
    status = await free.ok("GET", BASE)
    assert (status["available"], status["entitled"], status["connected"]) == (True, False, False)
    refused = await free.call("POST", f"{BASE}/connect", json={"shop": "my-store"})
    assert (refused.status_code, refused.json()["entitlement"]) == (402, "commerce")

    await set_plan(engine, free.wid, "pro")
    monkeypatch.setattr("socialhood.shopify.registry._override", [])  # the real client's setup
    monkeypatch.setattr(app.state.settings, "shopify_provider", "shopify")
    unset = await free.call("POST", f"{BASE}/connect", json={"shop": "my-store"})
    assert (unset.status_code, unset.json()["detail"]) == (503, shopify.NOT_CONFIGURED)
    assert (await free.ok("GET", BASE))["available"] is False


async def test_the_store_address_is_checked(ws: Ws) -> None:
    for bad in ("evil.example.com", "my store", "x"):
        response = await ws.call("POST", f"{BASE}/connect", json={"shop": bad})
        assert response.status_code == 422, bad
        assert response.json()["errors"][0] == {"field": "shop", "message": shopify.SHOP_INVALID}


async def test_connect_stores_the_token_encrypted_and_queues_the_first_sync(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, fake_shopify: FakeShopify
) -> None:
    status = await connect(ws, client)

    assert (status["connected"], status["status"], status["shop_domain"]) == (True, "active", SHOP)
    assert (status["shop_name"], status["currency"], status["syncing"]) == ("My Store", "INR", True)
    assert "fake-token" not in json.dumps(status)
    [stored] = await rows(
        engine, "SELECT token_enc, scopes, webhook_topics FROM shopify_connections"
    )
    assert b"fake-token" not in bytes(stored["token_enc"])
    assert stored["scopes"] == ["read_products"]
    assert "products/update" in stored["webhook_topics"]
    assert "shop/redact" in stored["webhook_topics"]
    assert fake_shopify.webhooks[SHOP] == stored["webhook_topics"]
    [job] = await jobs("sync_shopify_products")
    assert job["queueing_lock"] == f"shopify-sync:{ws.wid}"


async def test_the_nonce_works_once_and_only_for_the_member_who_started_it(
    ws: Ws, client: httpx.AsyncClient
) -> None:
    started = await ws.ok("POST", f"{BASE}/connect", json={"shop": SHOP})
    query = {k: v[0] for k, v in parse_qs(urlsplit(started["authorize_url"]).query).items()}
    callback = await client.get("/v1/oauth/shopify/callback", params=query)
    nonce = parse_qs(urlsplit(callback.headers["location"]).query)["shopify"][0]
    await ws.ok("POST", f"{BASE}/complete", json={"nonce": nonce})
    again = await ws.call("POST", f"{BASE}/complete", json={"nonce": nonce})
    assert (again.status_code, again.json()["detail"]) == (404, shopify.CONNECT_EXPIRED)
    replay = await client.get("/v1/oauth/shopify/callback", params=query)  # the state is single-use
    assert replay.headers["location"].endswith("/app?error=state_invalid")


async def test_a_forged_or_mismatched_callback_connects_nothing(
    ws: Ws, client: httpx.AsyncClient
) -> None:
    forged = await client.get(
        "/v1/oauth/shopify/callback", params={"code": "x", "state": "nope", "shop": SHOP}
    )
    assert forged.headers["location"].endswith("/app?error=state_invalid")
    started = await ws.ok("POST", f"{BASE}/connect", json={"shop": SHOP})
    query = {k: v[0] for k, v in parse_qs(urlsplit(started["authorize_url"]).query).items()}
    other_shop = await client.get(
        "/v1/oauth/shopify/callback", params={**query, "shop": "other.myshopify.com"}
    )
    assert other_shop.headers["location"].endswith("/app?error=state_invalid")
    denied = await ws.ok("POST", f"{BASE}/connect", json={"shop": SHOP})
    query = {k: v[0] for k, v in parse_qs(urlsplit(denied["authorize_url"]).query).items()}
    refused = await client.get(
        "/v1/oauth/shopify/callback",
        params={"state": query["state"], "shop": SHOP, "error": "access_denied"},
    )
    assert refused.headers["location"].endswith("/products?error=access_denied")


async def test_a_real_install_redirect_must_be_signed(
    ws: Ws, client: httpx.AsyncClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    from socialhood.shopify.signatures import sign_query

    started = await ws.ok("POST", f"{BASE}/connect", json={"shop": SHOP})
    query = {k: v[0] for k, v in parse_qs(urlsplit(started["authorize_url"]).query).items()}
    monkeypatch.setattr(app.state.settings, "shopify_provider", "shopify")
    unsigned = await client.get("/v1/oauth/shopify/callback", params=query)
    assert unsigned.headers["location"].endswith("/app?error=state_invalid")
    signed = {**query, "hmac": sign_query(query, SHOPIFY_SECRET)}
    ok = await client.get("/v1/oauth/shopify/callback", params=signed)
    assert "?shopify=" in ok.headers["location"]


async def test_a_store_belongs_to_one_workspace(
    ws: Ws, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    await connect(ws, client)
    other = await workspace(client, clerk, email="other@example.com")
    await set_plan(engine, other.wid, "pro")
    taken = await other.call("POST", f"{BASE}/connect", json={"shop": SHOP})
    assert (taken.status_code, taken.json()["code"]) == (409, "account_in_use")


# ---------------------------------------------------------------- the sync


async def test_the_sync_copies_products_with_variants_prices_and_stock(
    app: FastAPI,
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    fake_shopify: FakeShopify,
) -> None:
    await connect(ws, client)
    assert await sync(app, engine, ws, fake_shopify) == "done"

    found = await products(ws)
    assert set(found) == {"Cotton kurta", "Silk scarf", "Draft jacket"}
    kurta, scarf, jacket = found["Cotton kurta"], found["Silk scarf"], found["Draft jacket"]
    assert (kurta["source"], kurta["currency"], kurta["active"]) == ("shopify", "INR", True)
    assert kurta["url"] == f"https://{SHOP}/products/cotton-kurta"
    assert [(v["title"], v["price_minor"], v["stock"]) for v in kurta["variants"]] == [
        ("Blue / S", 79900, 4),
        ("Blue / M", 79900, 12),
        ("Blue / L", 84900, 0),
        ("Red / M", 79900, 7),
    ]
    assert kurta["variants"][1]["options"] == {"Colour": "Blue", "Size": "M"}
    assert (scarf["price_minor"], scarf["stock"], scarf["sku"], scarf["variants"]) == (
        49900,
        None,  # untracked: not recorded, never 0
        "SCARF-1",
        [],
    )
    assert jacket["active"] is False
    status = await ws.ok("GET", BASE)
    assert (status["syncing"], status["products_synced"], status["sync_error"]) == (False, 3, None)
    assert status["synced_at"] is not None


async def test_a_second_sync_updates_in_place_and_removes_what_the_store_dropped(
    app: FastAPI,
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    fake_shopify: FakeShopify,
) -> None:
    await connect(ws, client)
    await sync(app, engine, ws, fake_shopify)
    before = await products(ws)

    store = seed_products(SHOP)
    store[0] = type(store[0])(
        **{
            **store[0].__dict__,
            "variants": tuple(
                type(v)(**{**v.__dict__, "price": "899.00"}) if v.id == "9102" else v
                for v in store[0].variants
            ),
        }
    )
    await fake_shopify.set_products(SHOP, store[:2])  # the jacket is gone
    assert await sync(app, engine, ws, fake_shopify) == "done"

    after = await products(ws)
    assert set(after) == {"Cotton kurta", "Silk scarf"}
    assert after["Cotton kurta"]["id"] == before["Cotton kurta"]["id"]  # updated, not duplicated
    prices = {v["title"]: v["price_minor"] for v in after["Cotton kurta"]["variants"]}
    assert prices["Blue / M"] == 89900
    ids_before = {v["title"]: v["id"] for v in before["Cotton kurta"]["variants"]}
    ids_after = {v["title"]: v["id"] for v in after["Cotton kurta"]["variants"]}
    assert ids_before == ids_after  # a flow step that names a variant keeps working


async def test_a_picture_uploaded_here_survives_the_sync(
    app: FastAPI, ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, fake_shopify: FakeShopify
) -> None:
    from tests.support.inbox import make_asset

    await connect(ws, client)
    await sync(app, engine, ws, fake_shopify)
    asset = await make_asset(engine, workspace_id=ws.wid)
    scarf = (await products(ws))["Silk scarf"]
    await ws.ok("PATCH", f"/products/{scarf['id']}", json={"image_asset_id": str(asset)})
    await sync(app, engine, ws, fake_shopify)
    assert (await products(ws))["Silk scarf"]["image_asset_id"] == str(asset)


async def test_the_sync_stops_at_the_plans_product_cap_and_says_so(
    app: FastAPI,
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    fake_shopify: FakeShopify,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(plans.ENTITLEMENTS["catalogue_products"], "pro", 2)
    await connect(ws, client)
    assert await sync(app, engine, ws, fake_shopify) == "done"
    assert len(await products(ws)) == 2
    status = await ws.ok("GET", BASE)
    assert (status["products_synced"], status["products_skipped"]) == (2, 1)
    assert status["sync_error"] == "Some products weren't added: your plan includes 2 products."


async def test_removed_access_asks_for_a_reconnect(
    app: FastAPI,
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    fake_shopify: FakeShopify,
) -> None:
    await connect(ws, client)
    await fake_shopify.revoke_access(f"fake-token:{SHOP}")
    assert await sync(app, engine, ws, fake_shopify) == "reconnect"
    status = await ws.ok("GET", BASE)
    assert (status["status"], status["syncing"]) == ("needs_reconnect", False)
    assert status["sync_error"] == shopify.UNINSTALLED
    refused = await ws.call("POST", f"{BASE}/sync")
    assert (refused.status_code, refused.json()["detail"]) == (409, shopify.NEEDS_RECONNECT)


async def test_pressing_sync_queues_one_job_at_a_time(ws: Ws, client: httpx.AsyncClient) -> None:
    await connect(ws, client)  # the first sync is already running
    again = await ws.call("POST", f"{BASE}/sync")
    assert (again.status_code, again.json()["syncing"]) == (202, True)
    assert len(await jobs("sync_shopify_products")) == 1


# ---------------------------------------------------------------- webhooks


def signed(
    body: dict[str, Any], topic: str, *, shop: str = SHOP, webhook_id: str = "w1"
) -> dict[str, Any]:
    raw = json.dumps(body).encode()
    return {
        "content": raw,
        "headers": {
            "X-Shopify-Hmac-Sha256": sign_webhook(raw, SHOPIFY_SECRET),
            "X-Shopify-Topic": topic,
            "X-Shopify-Shop-Domain": shop,
            "X-Shopify-Webhook-Id": webhook_id,
            "Content-Type": "application/json",
        },
    }


async def deliver(
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    redis: Redis,
    body: dict[str, Any],
    topic: str,
    **kw: Any,
) -> WebhookStatus | None:
    response = await client.post("/webhooks/shopify", **signed(body, topic, **kw))
    assert response.status_code == 200, response.text
    [event] = await rows(
        engine,
        "SELECT id FROM webhook_events WHERE provider = 'shopify'"
        " ORDER BY received_at DESC LIMIT 1",
    )
    return await process_event(sessions(engine), event["id"], redis)


async def test_unsigned_and_unconfigured_webhooks_are_refused(
    client: httpx.AsyncClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch, engine: AsyncEngine
) -> None:
    good = signed({"id": 1}, "products/update")
    assert (await client.post("/webhooks/shopify", content=good["content"])).status_code == 401
    forged = {**good["headers"], "X-Shopify-Hmac-Sha256": sign_webhook(good["content"], "other")}
    assert (
        await client.post("/webhooks/shopify", content=good["content"], headers=forged)
    ).status_code == 401
    assert await rows(engine, "SELECT id FROM webhook_events") == []
    monkeypatch.setattr(app.state.settings, "shopify_api_secret", None)
    unset = await client.post("/webhooks/shopify", **good)
    assert unset.status_code == 503


async def test_a_product_webhook_updates_the_catalogue_once(
    app: FastAPI,
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    redis: Redis,
    fake_shopify: FakeShopify,
) -> None:
    await connect(ws, client)
    await sync(app, engine, ws, fake_shopify)
    body = {
        "id": 9002,
        "title": "Silk scarf",
        "body_html": "<p>Hand-dyed silk.</p>",
        "handle": "silk-scarf",
        "status": "active",
        "options": [{"name": "Title"}],
        "variants": [
            {
                "id": 9201,
                "title": "Default Title",
                "sku": "SCARF-1",
                "price": "549.00",
                "inventory_quantity": 6,
                "inventory_management": "shopify",
                "option1": "Default Title",
            }
        ],
    }
    assert await deliver(client, engine, redis, body, "products/update") == WebhookStatus.PROCESSED
    scarf = (await products(ws))["Silk scarf"]
    assert (scarf["price_minor"], scarf["stock"]) == (54900, 6)
    assert scarf["url"] == f"https://{SHOP}/products/silk-scarf"
    # Shopify sends the same webhook again: stored once.
    again = await client.post("/webhooks/shopify", **signed(body, "products/update"))
    assert again.status_code == 200
    assert len(await rows(engine, "SELECT id FROM webhook_events WHERE provider = 'shopify'")) == 1


async def test_a_new_product_webhook_adds_it_and_a_delete_removes_it(
    app: FastAPI,
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    redis: Redis,
    fake_shopify: FakeShopify,
) -> None:
    await connect(ws, client)
    new = {
        "id": 9500,
        "title": "Linen shirt",
        "handle": "linen-shirt",
        "status": "active",
        "options": [{"name": "Size"}],
        "variants": [
            {
                "id": 1,
                "title": "M",
                "sku": "LS-M",
                "price": "1299.00",
                "option1": "M",
                "inventory_quantity": 2,
                "inventory_management": "shopify",
            }
        ],
    }
    assert await deliver(client, engine, redis, new, "products/create", webhook_id="c1") == (
        WebhookStatus.PROCESSED
    )
    shirt = (await products(ws))["Linen shirt"]
    assert [(v["title"], v["price_minor"], v["stock"]) for v in shirt["variants"]] == [
        ("M", 129900, 2)
    ]
    gone = await deliver(client, engine, redis, {"id": 9500}, "products/delete", webhook_id="d1")
    assert gone == WebhookStatus.PROCESSED
    assert "Linen shirt" not in await products(ws)


async def test_uninstalling_the_app_asks_for_a_reconnect_and_redaction_removes_the_store(
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    redis: Redis,
    app: FastAPI,
    fake_shopify: FakeShopify,
) -> None:
    await connect(ws, client)
    await sync(app, engine, ws, fake_shopify)
    assert await deliver(client, engine, redis, {}, "app/uninstalled", webhook_id="u1") == (
        WebhookStatus.PROCESSED
    )
    assert (await ws.ok("GET", BASE))["status"] == "needs_reconnect"
    assert len(await products(ws)) == 3  # kept until the store is redacted
    assert await deliver(
        client, engine, redis, {"shop_domain": SHOP}, "shop/redact", webhook_id="r1"
    ) == (WebhookStatus.PROCESSED)
    assert (await ws.ok("GET", BASE))["connected"] is False
    assert await products(ws) == {}


async def test_webhooks_for_unknown_stores_and_customer_topics_change_nothing(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    unknown = await deliver(
        client,
        engine,
        redis,
        {"id": 1, "title": "X"},
        "products/create",
        shop="nobody.myshopify.com",
    )
    assert unknown == WebhookStatus.IGNORED
    await connect(ws, client)
    customers = await deliver(
        client, engine, redis, {"customer": {}}, "customers/redact", webhook_id="k1"
    )
    assert customers == WebhookStatus.IGNORED
    assert await products(ws) == {}


async def test_a_downgraded_workspace_ignores_product_webhooks(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    await connect(ws, client)
    await set_plan(engine, ws.wid, "free")
    new = {
        "id": 9500,
        "title": "Linen shirt",
        "handle": "l",
        "status": "active",
        "variants": [{"id": 1, "title": "Default Title", "price": "10.00"}],
    }
    assert await deliver(client, engine, redis, new, "products/create") == WebhookStatus.IGNORED
    assert await products(ws) == {}


# ---------------------------------------------------------------- disconnecting


async def test_disconnecting_removes_the_store_and_its_products_unless_kept(
    app: FastAPI,
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    fake_shopify: FakeShopify,
) -> None:
    await connect(ws, client)
    await sync(app, engine, ws, fake_shopify)
    manual = await ws.ok("POST", "/products", 201, json={"name": "Hand made", "price": "10"})

    assert (await ws.call("DELETE", BASE, params={"keep_products": True})).status_code == 204
    assert (await ws.ok("GET", BASE))["connected"] is False
    assert len(await products(ws)) == 4

    await connect(ws, client)
    await sync(app, engine, ws, fake_shopify)
    assert (await ws.call("DELETE", BASE)).status_code == 204
    assert set(await products(ws)) == {"Hand made"}
    assert (await products(ws))["Hand made"]["id"] == manual["id"]
    assert (await ws.call("DELETE", BASE)).status_code == 204  # nothing to do is not an error
