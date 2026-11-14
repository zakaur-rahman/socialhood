"""An in-memory Google for YouTube, for tests and for running without Google
(``YOUTUBE_PROVIDER=fake``; refused in production).

- ``authorize_url`` points straight back at the redirect address with a fake code, so a browser
  "signs in" without leaving the app; ``exchange_code`` accepts that code.
- ``channels`` lists ``self.channel_list`` (one channel unless a test changes it).
- ``revoke`` (and ``revoke_access``) make minting with that refresh token fail as ``invalid_grant``
  (``account_needs_reconnect``); ``fail_next(error)`` raises ``error`` on the next call. Every call
  is recorded in ``calls``.

shortcut: state lives in this process only (unlike google/fake.py's Redis mode), enough while
only the API calls YouTube; give it Redis when the worker publishes (Phase 2).
"""

from __future__ import annotations

import secrets
from collections import deque
from typing import Any
from urllib.parse import urlencode

from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.client import Channel
from socialhood.platforms.youtube.oauth import SCOPES, Grant
from socialhood.settings import Settings

CODE = "fake-youtube-code"
REFRESH_PREFIX = "fake-yt-refresh:"
ACCESS_PREFIX = "fake-yt-access:"
CHANNEL = Channel(
    id="UCfakeChannel0000000000001",
    title="Maple Bakery",
    handle="maplebakery",
    avatar_url="https://yt.test/maple.jpg",
)


def _invalid_grant() -> PlatformError:
    return PlatformError(
        "account_needs_reconnect", platform_code="invalid_grant", message="Token has been revoked"
    )


class FakeYouTube:
    def __init__(
        self, redirect_uri: str = "http://localhost:8000/v1/oauth/youtube/callback"
    ) -> None:
        self.redirect_uri = redirect_uri
        self.channel_list: list[Channel] = [CHANNEL]
        self.scopes: tuple[str, ...] = SCOPES
        self.revoked: set[str] = set()
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._failures: deque[PlatformError] = deque()

    def fail_next(self, error: PlatformError) -> None:
        self._failures.append(error)

    def revoke_access(self, refresh_token: str) -> None:
        self.revoked.add(refresh_token)

    def _enter(self, name: str, **args: Any) -> None:
        self.calls.append((name, args))
        if self._failures:
            raise self._failures.popleft()

    def authorize_url(self, state: str) -> str:
        return f"{self.redirect_uri}?{urlencode({'code': CODE, 'state': state})}"

    async def exchange_code(self, code: str) -> Grant:
        self._enter("exchange_code", code=code)
        if code != CODE:
            raise _invalid_grant()
        refresh = f"{REFRESH_PREFIX}{secrets.token_hex(4)}"
        return Grant(
            refresh_token=refresh, access_token=ACCESS_PREFIX + refresh, scopes=self.scopes
        )

    async def access_token(self, refresh_token: str) -> str:
        self._enter("access_token")
        if not refresh_token.startswith(REFRESH_PREFIX) or refresh_token in self.revoked:
            raise _invalid_grant()
        return ACCESS_PREFIX + refresh_token

    async def revoke(self, refresh_token: str) -> None:
        self._enter("revoke", token=refresh_token)
        self.revoke_access(refresh_token)

    async def channels(self, access_token: str) -> list[Channel]:
        self._enter("channels")
        if not access_token.startswith(ACCESS_PREFIX):
            raise PlatformError("account_needs_reconnect", platform_code="401")
        return list(self.channel_list)


_process: list[FakeYouTube] = []


def process_fake(settings: Settings) -> FakeYouTube:
    if not _process:
        redirect = settings.youtube_redirect_uri
        _process.append(FakeYouTube(redirect) if redirect else FakeYouTube())
    return _process[0]
