"""Facebook Login for Pages: the connect steps (GR-29).

authorize URL -> code -> user token -> long-lived user token (~60 days) -> ``/me/accounts``, which
lists the Pages the person manages, each with its own Page access token. A Page token made from a
long-lived user token does not expire, so a connected Page needs no refresh (unverified until a
real Page confirms it, docs/verification.md). The person picks the Pages to connect; only those
tokens are stored, encrypted like every platform credential.

Field names follow Meta's Graph API docs and are unverified until a real account confirms them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.settings import Settings

DIALOG = "https://www.facebook.com"
GRAPH = "https://graph.facebook.com"

# pages_manage_metadata lets us subscribe a Page to webhooks; pages_read_user_content reads the
# comments on its posts. pages_manage_posts (GR-30) lets us publish; read_insights (C-131) lets
# us read post insights and is asked for only with FB_REQUEST_INSIGHTS_SCOPE (docs/app-review).
PUBLISH_SCOPE = "pages_manage_posts"
INSIGHTS_SCOPE = "read_insights"
SCOPES = (
    "pages_show_list",
    "pages_messaging",
    "pages_manage_metadata",
    "pages_manage_engagement",
    "pages_read_engagement",
    "pages_read_user_content",
    "pages_manage_posts",
)


def scopes(settings: Settings) -> tuple[str, ...]:
    """The permissions to ask for: the fixed ones, plus read_insights when it is switched on."""
    return SCOPES + ((INSIGHTS_SCOPE,) if settings.fb_request_insights_scope else ())


# A Page task that lets a person answer messages as the Page.
MESSAGING_TASK = "MESSAGING"
PAGE_FIELDS = "id,name,username,picture.type(large){url},access_token,tasks"
PAGES_LIMIT = 100


@dataclass(frozen=True)
class LongToken:
    access_token: str
    expires_at: datetime | None


@dataclass(frozen=True)
class FacebookUser:
    id: str
    name: str | None


@dataclass(frozen=True)
class FacebookPage:
    id: str
    name: str | None
    username: str | None
    picture_url: str | None
    access_token: str
    tasks: tuple[str, ...]

    @property
    def can_message(self) -> bool:
        """The person can answer messages as this Page. A listing without tasks is taken as yes
        (Meta only omits them for tokens that predate the field)."""
        return not self.tasks or MESSAGING_TASK in self.tasks


def authorize_url(settings: Settings, state: str) -> str:
    query = {
        "client_id": settings.meta_app_id or "",
        "redirect_uri": settings.fb_redirect_uri or "",
        "response_type": "code",
        "scope": ",".join(scopes(settings)),
        "state": state,
    }
    return f"{DIALOG}/{settings.meta_graph_version}/dialog/oauth?{urlencode(query)}"


def _graph(settings: Settings, path: str) -> str:
    return f"{GRAPH}/{settings.meta_graph_version}/{path}"


def _secret(settings: Settings) -> str:
    return settings.meta_app_secret.get_secret_value() if settings.meta_app_secret else ""


def _expiry(expires_in: Any) -> datetime | None:
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None
    return datetime.now(UTC) + timedelta(seconds=seconds)


async def exchange_code(http: PlatformHttp, settings: Settings, code: str) -> str:
    body = await http.request(
        "GET",
        _graph(settings, "oauth/access_token"),
        endpoint="oauth.access_token",
        params={
            "client_id": settings.meta_app_id or "",
            "client_secret": _secret(settings),
            "redirect_uri": settings.fb_redirect_uri or "",
            "code": code,
        },
    )
    if not isinstance(body, dict) or not body.get("access_token"):
        raise PlatformError("platform_rejected", message="Facebook returned no access token")
    return str(body["access_token"])


async def long_lived(http: PlatformHttp, settings: Settings, short_token: str) -> LongToken:
    body = await http.request(
        "GET",
        _graph(settings, "oauth/access_token"),
        endpoint="oauth.long_lived",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.meta_app_id or "",
            "client_secret": _secret(settings),
            "fb_exchange_token": short_token,
        },
    )
    if not isinstance(body, dict) or not body.get("access_token"):
        raise PlatformError("platform_rejected", message="Facebook returned no access token")
    return LongToken(str(body["access_token"]), _expiry(body.get("expires_in")))


async def me(http: PlatformHttp, settings: Settings, token: str) -> FacebookUser:
    body = await http.request(
        "GET", _graph(settings, "me"), endpoint="me", token=token, params={"fields": "id,name"}
    )
    if not isinstance(body, dict) or not body.get("id"):
        raise PlatformError("platform_rejected", message="Facebook did not say who this is")
    return FacebookUser(id=str(body["id"]), name=body.get("name"))


def parse_pages(body: Any) -> list[FacebookPage]:
    """The Pages from a ``/me/accounts`` body; one without an id or a Page token is left out."""
    rows = body.get("data") if isinstance(body, dict) else None
    pages: list[FacebookPage] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or not row.get("id") or not row.get("access_token"):
            continue
        picture = row.get("picture")
        data = picture.get("data") if isinstance(picture, dict) else None
        tasks = row.get("tasks")
        pages.append(
            FacebookPage(
                id=str(row["id"]),
                name=row.get("name"),
                username=row.get("username"),
                picture_url=data.get("url") if isinstance(data, dict) else None,
                access_token=str(row["access_token"]),
                tasks=tuple(str(t) for t in tasks) if isinstance(tasks, list) else (),
            )
        )
    return pages


async def pages(http: PlatformHttp, settings: Settings, token: str) -> list[FacebookPage]:
    """The Pages the person manages (first 100)."""
    body = await http.request(
        "GET",
        _graph(settings, "me/accounts"),
        endpoint="me.accounts",
        token=token,
        params={"fields": PAGE_FIELDS, "limit": PAGES_LIMIT},
    )
    return parse_pages(body)
