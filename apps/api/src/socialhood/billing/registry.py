"""Which Dodo client this process uses: the real one over the shared httpx client, or the fake
with ``DODO_PROVIDER=fake`` (never in production). Tests swap it with ``use_dodo``
(tests/support/billing.py does for every test, so no test reaches Dodo)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

import httpx

from socialhood.billing.dodo import DodoClient
from socialhood.billing.dodo_fake import FakeDodo
from socialhood.settings import Settings

_override: list[DodoClient] = []


@lru_cache
def _process_fake() -> FakeDodo:
    return FakeDodo()


def get_dodo(http: httpx.AsyncClient, settings: Settings) -> DodoClient:
    """The client for this call: a test's override, else what the settings say."""
    if _override:
        return _override[-1]
    if settings.dodo_provider == "fake":
        return _process_fake()
    from socialhood.billing.dodo_http import HttpDodoClient

    return HttpDodoClient(http, settings)


@contextmanager
def use_dodo(client: DodoClient) -> Iterator[DodoClient]:
    """Tests: every get_dodo() in the block returns ``client``."""
    _override.append(client)
    try:
        yield client
    finally:
        _override.pop()
