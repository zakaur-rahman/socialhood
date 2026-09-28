"""Instagram API with Instagram Login: the connect steps (F-03, TR-PL table).

authorize URL -> code -> short-lived token -> long-lived token (~60 days) -> /me.
Field names follow Meta's docs; T0.9 confirms them against a real account.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.settings import Settings

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"  # noqa: S105 - an endpoint, not a secret
GRAPH = "https://graph.instagram.com"

BASE_SCOPES = (
    "instagram_business_basic",
    "instagram_business_manage_messages",
    "instagram_business_manage_comments",
    "instagram_business_content_publish",
)
INSIGHTS_SCOPE = "instagram_business_manage_insights"
PROFESSIONAL_TYPES = frozenset({"BUSINESS", "MEDIA_CREATOR"})
PROFILE_FIELDS = (
    "user_id,username,name,account_type,profile_picture_url,followers_count,media_count"
)


@dataclass(frozen=True)
class ShortToken:
    access_token: str
    user_id: str
    permissions: tuple[str, ...]


@dataclass(frozen=True)
class LongToken:
    access_token: str
    expires_at: datetime | None


@dataclass(frozen=True)
class InstagramProfile:
    user_id: str  # professional account id = webhook entry.id
    app_scoped_id: str | None  # /me.id
    username: str | None
    name: str | None
    account_type: str | None
    profile_picture_url: str | None

    @property
    def is_professional(self) -> bool:
        return (self.account_type or "").upper() in PROFESSIONAL_TYPES


def scopes(settings: Settings) -> tuple[str, ...]:
    return BASE_SCOPES + ((INSIGHTS_SCOPE,) if settings.ig_request_insights_scope else ())


def authorize_url(settings: Settings, state: str) -> str:
    query = {
        "client_id": settings.ig_app_id or "",
        "redirect_uri": settings.ig_redirect_uri or "",
        "response_type": "code",
        "scope": ",".join(scopes(settings)),
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(query)}"


def _expiry(expires_in: Any) -> datetime | None:
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _secret(settings: Settings) -> str:
    return settings.ig_app_secret.get_secret_value() if settings.ig_app_secret else ""


async def exchange_code(http: PlatformHttp, settings: Settings, code: str) -> ShortToken:
    body = await http.request(
        "POST",
        TOKEN_URL,
        endpoint="oauth.access_token",
        data={
            "client_id": settings.ig_app_id or "",
            "client_secret": _secret(settings),
            "grant_type": "authorization_code",
            "redirect_uri": settings.ig_redirect_uri or "",
            "code": code,
        },
    )
    # Documented as {"data": [{...}]}; older responses were flat. Accept both.
    item = (
        body["data"][0] if isinstance(body, dict) and isinstance(body.get("data"), list) else body
    )
    if not isinstance(item, dict) or not item.get("access_token"):
        raise PlatformError("platform_rejected", message="Instagram returned no access token")
    raw = item.get("permissions") or ()
    permissions = tuple(p.strip() for p in raw.split(",")) if isinstance(raw, str) else tuple(raw)
    return ShortToken(str(item["access_token"]), str(item.get("user_id", "")), permissions)


async def long_lived(http: PlatformHttp, settings: Settings, short_token: str) -> LongToken:
    body = await http.request(
        "GET",
        f"{GRAPH}/access_token",
        endpoint="oauth.long_lived",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": _secret(settings),
            "access_token": short_token,
        },
    )
    return LongToken(str(body["access_token"]), _expiry(body.get("expires_in")))


async def refresh(http: PlatformHttp, token: str) -> LongToken:
    """Extend a long-lived token that is at least 24 hours old (another ~60 days)."""
    body = await http.request(
        "GET",
        f"{GRAPH}/refresh_access_token",
        endpoint="oauth.refresh",
        params={"grant_type": "ig_refresh_token", "access_token": token},
    )
    return LongToken(str(body["access_token"]), _expiry(body.get("expires_in")))


async def me(http: PlatformHttp, settings: Settings, token: str) -> InstagramProfile:
    body = await http.request(
        "GET",
        f"{GRAPH}/{settings.ig_graph_version}/me",
        endpoint="me",
        token=token,
        params={"fields": PROFILE_FIELDS},
    )
    return InstagramProfile(
        user_id=str(body.get("user_id") or body.get("id")),
        app_scoped_id=str(body["id"]) if body.get("id") else None,
        username=body.get("username"),
        name=body.get("name"),
        account_type=body.get("account_type"),
        profile_picture_url=body.get("profile_picture_url"),
    )
