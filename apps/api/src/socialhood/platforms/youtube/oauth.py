"""Google OAuth for YouTube (C-195): the same OAuth client as Clerk's Google sign-in, one scope.

- ``youtube.force-ssl`` only: uploads, and editing or deleting what was uploaded
  (``youtube.upload`` alone can't edit or cancel).
- Authorise with ``access_type=offline`` and ``prompt=consent`` so Google always returns a refresh
  token, and ``include_granted_scopes=false`` so the grant holds this scope alone.
- The refresh token is the stored credential (``access_token_enc``, no expiry); a short-lived
  access token is minted from it for each use. ``invalid_grant`` while minting means the access was
  removed: ``account_needs_reconnect``.

``youtube_for`` picks the client: the real one, or the fake with ``YOUTUBE_PROVIDER=fake`` (never in
production); tests swap it with ``use_youtube`` (tests/support/youtube.py does for every test).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode

from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.client import Channel, google_http, list_channels

SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
SCOPES = (SCOPE,)
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 (an address, not a secret)
REVOKE_URL = "https://oauth2.googleapis.com/revoke"


@dataclass(frozen=True)
class Grant:
    """What a finished authorisation gives: the refresh token (the stored credential), an access
    token for the calls that follow right away, and the scopes Google granted."""

    refresh_token: str
    access_token: str
    scopes: tuple[str, ...]


class YouTubeOAuth(Protocol):
    def authorize_url(self, state: str) -> str: ...

    async def exchange_code(self, code: str) -> Grant: ...

    async def access_token(self, refresh_token: str) -> str: ...

    async def revoke(self, refresh_token: str) -> None: ...

    async def channels(self, access_token: str) -> list[Channel]: ...


class HttpYouTubeOAuth:
    def __init__(self, deps: PlatformDeps) -> None:
        self.settings = deps.settings
        self.http = google_http(deps.http)

    def authorize_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self.settings.youtube_client_id or "",
                "redirect_uri": self.settings.youtube_redirect_uri or "",
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "false",
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def _token(self, endpoint: str, data: dict[str, str]) -> dict[str, Any]:
        secret = self.settings.youtube_client_secret
        body = await self.http.request(
            "POST",
            TOKEN_URL,
            endpoint=endpoint,
            data={
                **data,
                "client_id": self.settings.youtube_client_id or "",
                "client_secret": secret.get_secret_value() if secret else "",
            },
        )
        return body if isinstance(body, dict) else {}

    async def exchange_code(self, code: str) -> Grant:
        body = await self._token(
            "oauth.exchange",
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.youtube_redirect_uri or "",
            },
        )
        refresh = body.get("refresh_token")
        if not refresh:  # Google returns it only on a consented offline grant
            raise PlatformError("platform_rejected", message="Google didn't give lasting access")
        return Grant(
            refresh_token=str(refresh),
            access_token=str(body.get("access_token") or ""),
            scopes=tuple(str(body.get("scope") or "").split()),
        )

    async def access_token(self, refresh_token: str) -> str:
        body = await self._token(
            "oauth.refresh", {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )
        return str(body["access_token"])

    async def revoke(self, refresh_token: str) -> None:
        await self.http.request(
            "POST", REVOKE_URL, endpoint="oauth.revoke", data={"token": refresh_token}
        )

    async def channels(self, access_token: str) -> list[Channel]:
        return await list_channels(self.http, access_token)


_override: list[YouTubeOAuth] = []


def youtube_for(deps: PlatformDeps) -> YouTubeOAuth:
    """The client for this call: a test's override, else what the settings say."""
    if _override:
        return _override[-1]
    if deps.settings.youtube_provider == "fake":
        from socialhood.platforms.youtube.fake import process_fake

        return process_fake(deps.settings)
    return HttpYouTubeOAuth(deps)


def configured(deps: PlatformDeps) -> bool:
    """Whether Connect can work: the fake always, the real client with its OAuth client set up."""
    s = deps.settings
    if _override or s.youtube_provider == "fake":
        return True
    return bool(s.youtube_client_id and s.youtube_client_secret and s.youtube_redirect_uri)


@contextmanager
def use_youtube(client: YouTubeOAuth) -> Iterator[YouTubeOAuth]:
    """Tests: every youtube_for() in the block returns ``client``."""
    _override.append(client)
    try:
        yield client
    finally:
        _override.pop()
