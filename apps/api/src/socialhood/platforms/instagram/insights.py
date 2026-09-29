"""Instagram live counts and insights for the metric snapshots (T6.5; FR-ANL-01). The adapter's
``get_media_counts``, ``get_media_insights`` and ``get_account_insights`` delegate here.

Insight calls need the ``instagram_business_manage_insights`` scope, requested only when
IG_REQUEST_INSIGHTS_SCOPE is on (the adapter's capabilities drop POST_INSIGHTS and
ACCOUNT_INSIGHTS without it). ``GET /{media_id}?fields=like_count,comments_count`` gives the live
counts; ``GET /{media_id}/insights`` and ``GET /{ig_user_id}/insights`` the insights.

A value Instagram does not give is a known unknown (None), never an error that stops the
snapshot job: a refused call (permission missing, metric not offered for the format, media
posted before the account became professional) leaves its values None. Retryable failures (rate
limits, outages) and a dead token still raise, so the job's retry strategy and the connection
checks see them (TR-PL-03).

Metric names per format follow Meta's Media Insights and Account Insights references (checked
2026-09-29); what a real account returns is confirmed at T0.9 (docs/verification.md).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from socialhood.models.connections import SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import AccountInsights, MediaCounts, MediaInsights
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram.reads import GRAPH_ID

log = get_logger("socialhood.platforms")

COUNT_FIELDS = "like_count,comments_count"

# Instagram's media metric -> the MediaInsights field (PostMetric key) it fills.
MEDIA_METRIC_KEYS: dict[str, str] = {
    "reach": "reach",
    "views": "views",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
    "saved": "saves",
    "total_interactions": "total_interactions",
    "profile_visits": "profile_visits",
    "follows": "follows",
}
# Which of them Meta offers per media product type. Feed posts (images, carousels, feed videos)
# have them all; Reels have no profile_visits or follows; stories have no likes, comments or
# saved. ``impressions`` and ``plays`` are gone for media created since July 2024 (use views).
FEED_METRICS = tuple(MEDIA_METRIC_KEYS)
REELS_METRICS = ("reach", "views", "likes", "comments", "shares", "saved", "total_interactions")
STORY_METRICS = ("reach", "views", "shares", "total_interactions", "follows", "profile_visits")
METRICS_BY_MEDIA_TYPE: dict[str, tuple[str, ...]] = {
    "image": FEED_METRICS,
    "video": FEED_METRICS,
    "carousel": FEED_METRICS,
    "reel": REELS_METRICS,
    "story": STORY_METRICS,
}

# Account insights for one day (period=day, metric_type=total_value). follows_and_unfollows needs
# the follow_type breakdown, which the other metrics refuse, so it is asked for on its own; Meta
# leaves it out for accounts under 100 followers.
ACCOUNT_METRICS = ("reach", "views", "accounts_engaged", "total_interactions", "profile_links_taps")
FOLLOWS_METRIC = "follows_and_unfollows"
FOLLOW_TYPES = {"FOLLOWER": "follows", "NON_FOLLOWER": "unfollows"}

# Graph error 100 without a subcode: one of the metrics asked for is not offered for this media
# ("Incompatible metric"), which fails the whole request. Each metric is then asked for alone.
INCOMPATIBLE_METRIC = "100"


# ---------------------------------------------------------------- reading


async def _get(
    http: PlatformHttp, url: str, *, endpoint: str, token: str, params: dict[str, Any]
) -> Any | None:
    """A read whose refusal is a known unknown: None when Instagram refuses it for good."""
    try:
        return await http.request("GET", url, endpoint=endpoint, token=token, params=params)
    except PlatformError as error:
        if error.retryable or error.code == "account_needs_reconnect":
            raise
        log.info("insights_unavailable", endpoint=endpoint, platform_code=error.platform_code)
        return None


async def _metrics(
    http: PlatformHttp,
    url: str,
    metrics: Iterable[str],
    *,
    endpoint: str,
    token: str,
    params: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """``{metric: insight item}`` for the metrics Instagram returns. When it refuses the batch
    because one metric is incompatible, each metric is read alone and the refused ones are left
    out."""
    names = list(metrics)
    extra = dict(params or {})
    try:
        body = await http.request(
            "GET",
            url,
            endpoint=endpoint,
            token=token,
            params={**extra, "metric": ",".join(names)},
        )
        return _by_name(body)
    except PlatformError as error:
        if error.retryable or error.code == "account_needs_reconnect":
            raise
        if error.platform_code != INCOMPATIBLE_METRIC or len(names) == 1:
            log.info("insights_unavailable", endpoint=endpoint, platform_code=error.platform_code)
            return {}
    found: dict[str, Any] = {}
    for name in names:
        body = await _get(
            http, url, endpoint=endpoint, token=token, params={**extra, "metric": name}
        )
        found.update(_by_name(body))
    return found


def _by_name(body: Any) -> dict[str, Any]:
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        return {}
    return {
        item["name"]: item
        for item in data
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _value(item: Mapping[str, Any] | None) -> int | None:
    """An insight item's number: ``total_value.value`` (metric_type=total_value) or the last of
    ``values[].value`` (lifetime media metrics)."""
    if not isinstance(item, Mapping):
        return None
    total = item.get("total_value")
    if isinstance(total, Mapping) and _int(total.get("value")) is not None:
        return _int(total.get("value"))
    values = item.get("values")
    if isinstance(values, list) and values and isinstance(values[-1], Mapping):
        return _int(values[-1].get("value"))
    return None


def _breakdown(item: Mapping[str, Any] | None) -> dict[str, int]:
    """``{dimension value: number}`` from the first breakdown of a total_value item."""
    total = item.get("total_value") if isinstance(item, Mapping) else None
    breakdowns = total.get("breakdowns") if isinstance(total, Mapping) else None
    if not isinstance(breakdowns, list) or not breakdowns:
        return {}
    first = breakdowns[0]
    results = first.get("results") if isinstance(first, Mapping) else None
    found: dict[str, int] = {}
    for result in results if isinstance(results, list) else []:
        if not isinstance(result, Mapping):
            continue
        dims = result.get("dimension_values")
        value = _int(result.get("value"))
        if isinstance(dims, list) and dims and isinstance(dims[0], str) and value is not None:
            found[dims[0]] = value
    return found


def _media_id(media_ref: str) -> str:
    if not GRAPH_ID.match(media_ref):
        raise PlatformError("platform_rejected", message="Not an Instagram media id")
    return media_ref


# ---------------------------------------------------------------- posts


async def media_counts(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str
) -> MediaCounts | None:
    """The post's like and comment counts now; None when Instagram no longer gives the post
    (deleted, or refused). A count the owner hides is left None."""
    body = await _get(
        http,
        graph(_media_id(media_ref)),
        endpoint="media.counts",
        token=token,
        params={"fields": COUNT_FIELDS},
    )
    if not isinstance(body, dict):
        return None
    return MediaCounts(
        like_count=_int(body.get("like_count")), comments_count=_int(body.get("comments_count"))
    )


async def media_insights(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str, *, media_type: str
) -> MediaInsights:
    """The post's lifetime insights now, asking only for the metrics its format offers."""
    wanted = METRICS_BY_MEDIA_TYPE.get(media_type, FEED_METRICS)
    items = await _metrics(
        http,
        graph(f"{_media_id(media_ref)}/insights"),
        wanted,
        endpoint="media.insights",
        token=token,
    )
    values = {MEDIA_METRIC_KEYS[name]: _value(items.get(name)) for name in wanted}
    return MediaInsights(**values)


# ---------------------------------------------------------------- accounts


def day_bounds(day: date, tz: str) -> tuple[int, int]:
    """``day`` in the IANA zone ``tz`` as Unix seconds [start, end): the since and until of a
    one-day account insights read."""
    zone = ZoneInfo(tz)
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return int(start.timestamp()), int(end.timestamp())


async def account_insights(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    day: date,
    *,
    tz: str,
    with_insights: bool,
) -> AccountInsights:
    """Followers now (``GET /me?fields=followers_count``) and, with the insights scope, the
    account's insights for ``day`` in the workspace time zone."""
    profile = await _get(
        http,
        graph("me"),
        endpoint="me.followers",
        token=token,
        params={"fields": "followers_count"},
    )
    followers = _int(profile.get("followers_count")) if isinstance(profile, dict) else None
    if not with_insights:
        return AccountInsights(followers_count=followers)
    user_id = acct.platform_account_id
    if not GRAPH_ID.match(user_id):
        raise PlatformError("platform_rejected", message="Not an Instagram account id")
    since, until = day_bounds(day, tz)
    window = {"period": "day", "metric_type": "total_value", "since": since, "until": until}
    url = graph(f"{user_id}/insights")
    items = await _metrics(
        http, url, ACCOUNT_METRICS, endpoint="user.insights", token=token, params=window
    )
    follows = await _metrics(
        http,
        url,
        (FOLLOWS_METRIC,),
        endpoint="user.insights.follows",
        token=token,
        params={**window, "breakdown": "follow_type"},
    )
    return AccountInsights(
        followers_count=followers,
        reach=_value(items.get("reach")),
        views=_value(items.get("views")),
        accounts_engaged=_value(items.get("accounts_engaged")),
        total_interactions=_value(items.get("total_interactions")),
        profile_links_taps=_value(items.get("profile_links_taps")),
        **_follows(follows.get(FOLLOWS_METRIC)),
    )


def _follows(item: Mapping[str, Any] | None) -> dict[str, int | None]:
    """follows and unfollows from the follow_type breakdown. A breakdown without a row for one
    side means none of that side that day; a total of 0 comes without any breakdown."""
    split = _breakdown(item)
    if not split and not (item is not None and _value(item) == 0):
        return {"follows": None, "unfollows": None}
    return {key: split.get(dimension, 0) for dimension, key in FOLLOW_TYPES.items()}
