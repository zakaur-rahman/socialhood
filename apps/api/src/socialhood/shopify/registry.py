"""Which Shopify client this process uses: the real one over the shared httpx client, or the fake
with ``SHOPIFY_PROVIDER=fake`` (never in production). Tests swap it with ``use_shopify``
(tests/support/shopify.py does for every test, so no test reaches Shopify).

The process fake keeps its store in Redis when it is given a client, so the API and the worker
(separate processes in the end-to-end stack) see the same products.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from redis.asyncio import Redis

from socialhood.settings import Settings
from socialhood.shopify.client import ShopifyClient
from socialhood.shopify.fake import FakeShopify

_override: list[ShopifyClient] = []
_process: list[FakeShopify] = []


def process_fake(settings: Settings, redis: Redis | None = None) -> FakeShopify:
    if not _process:
        redirect = settings.shopify_redirect_uri
        _process.append(
            FakeShopify(redirect, redis=redis) if redirect else FakeShopify(redis=redis)
        )
    return _process[0]


def get_shopify(
    http: httpx.AsyncClient, settings: Settings, redis: Redis | None = None
) -> ShopifyClient:
    """The client for this call: a test's override, else what the settings say."""
    if _override:
        return _override[-1]
    if settings.shopify_provider == "fake":
        return process_fake(settings, redis)
    from socialhood.shopify.http import HttpShopifyClient

    return HttpShopifyClient(http, settings)


def configured(settings: Settings) -> bool:
    """Whether Connect can work: the fake always, the real client with its app credentials set."""
    if _override or settings.shopify_provider == "fake":
        return True
    return bool(
        settings.shopify_api_key
        and settings.shopify_api_secret
        and settings.shopify_redirect_uri
        and settings.api_base_url
    )


def webhook_secret(settings: Settings) -> str:
    """The secret Shopify signs webhooks with: the app's client secret (empty when unset)."""
    secret = settings.shopify_api_secret
    return secret.get_secret_value() if secret else ""


@contextmanager
def use_shopify(client: ShopifyClient) -> Iterator[ShopifyClient]:
    """Tests: every get_shopify() in the block returns ``client``."""
    _override.append(client)
    try:
        yield client
    finally:
        _override.pop()
