"""The YouTube Data API calls (C-195) and Google's error mapping.

Google's API errors look like ``{"error": {"code": 403, "errors": [{"reason": "quotaExceeded"}],
"message": ...}}``; its OAuth token endpoint answers ``{"error": "invalid_grant", ...}``. Neither is
a Meta Graph error, so YouTube calls use ``map_google_error``, never ``map_graph_error``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp

API = "https://www.googleapis.com/youtube/v3"
RATE_REASONS = frozenset({"quotaExceeded", "rateLimitExceeded", "userRateLimitExceeded"})
UPLOAD_LIMIT = (
    "This channel reached YouTube's daily upload limit. Try again tomorrow, or verify the "
    "channel on YouTube to upload more."
)


def map_google_error(
    status: int, body: Any, headers: dict[str, str] | None = None
) -> PlatformError:
    """Turn a failed Google response into the PlatformError services understand."""
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, str):  # the OAuth token endpoint
        reasons = [error]
        message = str(body.get("error_description") or error)
    else:
        error = error if isinstance(error, dict) else {}
        reasons = [str(e.get("reason")) for e in error.get("errors") or [] if isinstance(e, dict)]
        message = str(error.get("message") or f"HTTP {status}")
    platform_code = reasons[0] if reasons else str(status)

    def build(ours: str, text: str = message) -> PlatformError:
        return PlatformError(ours, platform_code=platform_code, message=text)

    if status == 401 or "invalid_grant" in reasons:
        return build("account_needs_reconnect")
    if status == 429 or RATE_REASONS & set(reasons):
        return build("platform_rate_limited")
    if "uploadLimitExceeded" in reasons:
        return build("platform_rejected", UPLOAD_LIMIT)
    if status >= 500:
        return build("platform_unavailable")
    return build("platform_rejected")


def google_http(client: httpx.AsyncClient) -> PlatformHttp:
    """The shared client with Google's error mapping."""
    return PlatformHttp(client, "youtube", mapper=map_google_error)


@dataclass(frozen=True)
class Channel:
    id: str
    title: str
    handle: str | None  # without the "@"
    avatar_url: str | None


def _channel(item: dict[str, Any]) -> Channel:
    snippet = item.get("snippet") or {}
    thumbs = snippet.get("thumbnails") or {}
    thumb = thumbs.get("default") or thumbs.get("medium") or thumbs.get("high") or {}
    handle = str(snippet.get("customUrl") or "").removeprefix("@") or None
    return Channel(
        id=str(item["id"]),
        title=str(snippet.get("title") or item["id"]),
        handle=handle,
        avatar_url=thumb.get("url"),
    )


async def list_channels(http: PlatformHttp, access_token: str) -> list[Channel]:
    """The channels of the signed-in Google account (channels.list, part=snippet, mine=true)."""
    body = await http.request(
        "GET",
        f"{API}/channels",
        endpoint="channels.list",
        token=access_token,
        params={"part": "snippet", "mine": "true", "maxResults": 50},
    )
    return [_channel(item) for item in (body or {}).get("items") or []]
