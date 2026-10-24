"""Which Meta catalogue client a call uses: the real one over the shared httpx client, or the
sandbox for a sandbox WhatsApp number (those exist only where ``SANDBOX_PLATFORM_ENABLED`` is on,
so the fake can't be reached in production). Tests swap it with ``use_catalogue``
(tests/support/catalogue.py does for every test, so no test reaches Meta).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import httpx

from socialhood.metacatalog.client import CatalogueClient
from socialhood.metacatalog.fake import FakeCatalogue
from socialhood.models.connections import SocialAccount
from socialhood.settings import Settings

SANDBOX_PREFIX = "sandbox_"

_override: list[CatalogueClient] = []
_process: list[FakeCatalogue] = []


def is_sandbox(acct: SocialAccount) -> bool:
    return acct.platform_account_id.startswith(SANDBOX_PREFIX)


def get_catalogue(
    http: httpx.AsyncClient, settings: Settings, acct: SocialAccount
) -> CatalogueClient:
    """The client for this account: a test's override, the sandbox catalogue for a sandbox
    number, else Meta's."""
    if _override:
        return _override[-1]
    if is_sandbox(acct):
        if not _process:
            _process.append(FakeCatalogue())
        return _process[0]
    from socialhood.metacatalog.http import HttpCatalogueClient

    return HttpCatalogueClient(http, settings)


@contextmanager
def use_catalogue(client: CatalogueClient) -> Iterator[CatalogueClient]:
    """Tests: every get_catalogue() in the block returns ``client``."""
    _override.append(client)
    try:
        yield client
    finally:
        _override.pop()
