"""Which Razorpay client this process uses: the real one over the shared httpx client, or the
sandbox with ``RAZORPAY_PROVIDER=fake`` (never in production). Tests swap it with
``use_razorpay`` (tests/support/razorpay.py does for every test, so no test reaches Razorpay).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import httpx

from socialhood.razorpay.client import RazorpayClient
from socialhood.razorpay.fake import FakeRazorpay
from socialhood.settings import Settings

_override: list[RazorpayClient] = []
_process: list[FakeRazorpay] = []


def get_razorpay(http: httpx.AsyncClient, settings: Settings) -> RazorpayClient:
    """The client for this call: a test's override, else what the settings say."""
    if _override:
        return _override[-1]
    if settings.razorpay_provider == "fake":
        if not _process:
            _process.append(FakeRazorpay())
        return _process[0]
    from socialhood.razorpay.http import HttpRazorpayClient

    return HttpRazorpayClient(http)


@contextmanager
def use_razorpay(client: RazorpayClient) -> Iterator[RazorpayClient]:
    """Tests: every get_razorpay() in the block returns ``client``."""
    _override.append(client)
    try:
        yield client
    finally:
        _override.pop()
