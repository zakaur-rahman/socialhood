"""Which Google client this process uses: the real one over the shared httpx client, or the fake
with ``GOOGLE_PROVIDER=fake`` (never in production). Tests swap it with ``use_google``
(tests/support/google.py does for every test, so no test reaches Google).

The process fake keeps its sheets in Redis when it is given a client, so the API and the worker
(separate processes in the end-to-end stack) see the same sheets.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from redis.asyncio import Redis

from socialhood.google.client import GoogleClient
from socialhood.google.fake import FakeGoogle
from socialhood.settings import Settings

_override: list[GoogleClient] = []
_process: list[FakeGoogle] = []


def process_fake(settings: Settings, redis: Redis | None = None) -> FakeGoogle:
    if not _process:
        redirect = settings.google_redirect_uri
        _process.append(FakeGoogle(redirect, redis=redis) if redirect else FakeGoogle(redis=redis))
    return _process[0]


def get_google(
    http: httpx.AsyncClient, settings: Settings, redis: Redis | None = None
) -> GoogleClient:
    """The client for this call: a test's override, else what the settings say."""
    if _override:
        return _override[-1]
    if settings.google_provider == "fake":
        return process_fake(settings, redis)
    from socialhood.google.http import HttpGoogleClient

    return HttpGoogleClient(http, settings)


def configured(settings: Settings) -> bool:
    """Whether Connect can work: the fake always, the real client with its OAuth client set up."""
    if _override or settings.google_provider == "fake":
        return True
    return bool(
        settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri
    )


@contextmanager
def use_google(client: GoogleClient) -> Iterator[GoogleClient]:
    """Tests: every get_google() in the block returns ``client``."""
    _override.append(client)
    try:
        yield client
    finally:
        _override.pop()
