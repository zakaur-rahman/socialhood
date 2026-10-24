"""Shopify test support (GR-31): every test runs with a FakeShopify (never Shopify); request
``fake_shopify`` to change the store's products, revoke access or queue a failure."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from socialhood.shopify.fake import FakeShopify
from socialhood.shopify.registry import use_shopify


@pytest.fixture(autouse=True)
def fake_shopify() -> Iterator[FakeShopify]:
    fake = FakeShopify()
    with use_shopify(fake):
        yield fake
