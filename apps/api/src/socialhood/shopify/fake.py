"""A built-in Shopify store for tests, development and the end-to-end stack
(``SHOPIFY_PROVIDER=fake``; never in production).

- ``authorize_url`` points straight back at the redirect address with ``code=fake-code:<shop>``,
  so a browser "installs the app" without leaving Amplychat; ``exchange_code`` accepts that
  code and gives ``fake-token:<shop>``.
- Every store starts with the same three products (a kurta with colour and size variants, a scarf
  without variants and an untracked stock, a draft jacket). ``set_products`` replaces them, so a
  test can change a price and then send the matching webhook.
- ``revoke_access`` makes every call with that token fail as ``auth`` (the app was uninstalled);
  ``fail_next(error)`` raises on the next call; ``pages`` is how many products one page holds, so
  a test can walk several pages. Every call is recorded in ``calls`` (memory mode only).
- With a Redis client the products and revoked tokens live there, so the API and the worker
  (separate processes in the end-to-end stack) see one store. Without one, it is all in memory.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict
from typing import Any
from urllib.parse import urlencode

from redis.asyncio import Redis

from socialhood.shopify.client import (
    Grant,
    ProductPage,
    ShopifyError,
    ShopifyProduct,
    ShopifyVariant,
    ShopInfo,
)

CODE_PREFIX = "fake-code:"
TOKEN_PREFIX = "fake-token:"  # noqa: S105 (a test marker, not a secret)
_PREFIX = "fakeshopify"


def seed_products(shop: str) -> list[ShopifyProduct]:
    def variant(vid: str, colour: str, size: str, price: str, stock: int | None) -> ShopifyVariant:
        return ShopifyVariant(
            id=vid,
            title=f"{colour} / {size}",
            sku=f"KUR-{colour[:2].upper()}-{size}",
            price=price,
            inventory=stock,
            options={"Colour": colour, "Size": size},
        )

    return [
        ShopifyProduct(
            id="9001",
            title="Cotton kurta",
            description="Soft cotton kurta, straight cut.",
            handle="cotton-kurta",
            url=f"https://{shop}/products/cotton-kurta",
            status="active",
            image_url="https://cdn.shopify.test/kurta.jpg",
            variants=(
                variant("9101", "Blue", "S", "799.00", 4),
                variant("9102", "Blue", "M", "799.00", 12),
                variant("9103", "Blue", "L", "849.00", 0),
                variant("9104", "Red", "M", "799.00", 7),
            ),
        ),
        ShopifyProduct(
            id="9002",
            title="Silk scarf",
            description="Hand-dyed silk scarf.",
            handle="silk-scarf",
            url=f"https://{shop}/products/silk-scarf",
            status="active",
            image_url=None,
            variants=(
                ShopifyVariant(
                    id="9201", title="Default Title", sku="SCARF-1", price="499.00", inventory=None
                ),
            ),
        ),
        ShopifyProduct(
            id="9003",
            title="Draft jacket",
            description=None,
            handle="draft-jacket",
            url=None,
            status="draft",
            image_url=None,
            variants=(
                ShopifyVariant(
                    id="9301", title="Default Title", sku=None, price="2999.00", inventory=0
                ),
            ),
        ),
    ]


def _dump(products: list[ShopifyProduct]) -> str:
    return json.dumps([asdict(p) for p in products])


def _load(raw: str) -> list[ShopifyProduct]:
    out = []
    for item in json.loads(raw):
        variants = tuple(ShopifyVariant(**v) for v in item.pop("variants"))
        out.append(ShopifyProduct(variants=variants, **item))
    return out


class FakeShopify:
    def __init__(
        self,
        redirect_uri: str = "http://localhost:8000/v1/oauth/shopify/callback",
        *,
        redis: Redis | None = None,
        pages: int = 2,
    ) -> None:
        self.redirect_uri = redirect_uri
        self.pages = pages
        self._redis = redis
        self._products: dict[str, list[ShopifyProduct]] = {}
        self._revoked: set[str] = set()
        self._failures: deque[ShopifyError] = deque()
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.webhooks: dict[str, list[str]] = {}

    # ---------------------------------------------------------------- test setup

    def fail_next(self, error: ShopifyError) -> None:
        self._failures.append(error)

    async def set_products(self, shop: str, products: list[ShopifyProduct]) -> None:
        if self._redis is not None:
            await self._redis.set(f"{_PREFIX}:{shop}:products", _dump(products))
        else:
            self._products[shop] = list(products)

    async def products(self, shop: str) -> list[ShopifyProduct]:
        if self._redis is not None:
            raw = await self._redis.get(f"{_PREFIX}:{shop}:products")
            return (
                _load(raw if isinstance(raw, str) else raw.decode()) if raw else seed_products(shop)
            )
        return list(self._products.get(shop) or seed_products(shop))

    async def revoke_access(self, token: str) -> None:
        if self._redis is not None:
            await self._redis.sadd(f"{_PREFIX}:revoked", token)
        else:
            self._revoked.add(token)

    async def _reinstate(self, token: str) -> None:
        if self._redis is not None:
            await self._redis.srem(f"{_PREFIX}:revoked", token)
        else:
            self._revoked.discard(token)

    async def _is_revoked(self, token: str) -> bool:
        if self._redis is not None:
            return bool(await self._redis.sismember(f"{_PREFIX}:revoked", token))
        return token in self._revoked

    async def _enter(self, name: str, **args: Any) -> None:
        self.calls.append((name, args))
        if self._failures:
            raise self._failures.popleft()

    async def _checked(self, token: str) -> None:
        if not token.startswith(TOKEN_PREFIX) or await self._is_revoked(token):
            raise ShopifyError("auth", "Shopify no longer accepts the access.", status=401)

    # ---------------------------------------------------------------- the client

    def authorize_url(self, shop: str, state: str) -> str:
        query = urlencode({"code": f"{CODE_PREFIX}{shop}", "state": state, "shop": shop})
        return f"{self.redirect_uri}?{query}"

    async def exchange_code(self, shop: str, code: str) -> Grant:
        await self._enter("exchange_code", shop=shop)
        if code != f"{CODE_PREFIX}{shop}":
            raise ShopifyError("auth", "Shopify no longer accepts the access.", status=400)
        token = f"{TOKEN_PREFIX}{shop}"
        await self._reinstate(token)  # installing again gives a working token, as on Shopify
        return Grant(token, ("read_products",))

    async def shop_info(self, shop: str, token: str) -> ShopInfo:
        await self._enter("shop_info", shop=shop)
        await self._checked(token)
        name = shop.removesuffix(".myshopify.com").replace("-", " ").title()
        return ShopInfo(name=name, domain=shop, storefront_domain=None, currency="INR")

    async def list_products(self, shop: str, token: str, cursor: str | None) -> ProductPage:
        await self._enter("list_products", shop=shop, cursor=cursor)
        await self._checked(token)
        every = await self.products(shop)
        start = int(cursor or 0)
        chunk = every[start : start + self.pages]
        more = start + self.pages < len(every)
        return ProductPage(chunk, str(start + self.pages) if more else None)

    async def register_webhooks(
        self, shop: str, token: str, topics: tuple[str, ...], address: str
    ) -> list[str]:
        await self._enter("register_webhooks", shop=shop, topics=topics, address=address)
        await self._checked(token)
        self.webhooks[shop] = list(topics)
        return list(topics)

    async def revoke(self, shop: str, token: str) -> None:
        await self._enter("revoke", shop=shop)
        await self.revoke_access(token)
