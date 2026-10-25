"""Facebook Page post insights for the metric snapshots (C-131; FR-ANL-01). The adapter's
``get_media_insights`` delegates here.

A Page post's figures, read with the Page token and the ``read_insights`` permission (asked for
only when FB_REQUEST_INSIGHTS_SCOPE is on; the adapter drops Capability.POST_INSIGHTS without it):

- ``GET /{post_id}/insights?metric=post_media_view,post_total_media_view_unique,post_clicks`` with
  ``period=lifetime``: views, reach and clicks. Meta replaced the older impressions metrics
  (``post_impressions`` and friends) with these "media view" ones, so the old names are not asked
  for.
- ``GET /{post_id}?fields=shares``: how many times the post was shared (Meta puts shares on the
  post, not in insights).

Likes (reactions) and comments come from the live counts, as for every other post. A value
Facebook does not give is a known unknown (None), never an error that stops the snapshot job: the
shared helpers of the Instagram insights module treat a refusal that way and still raise
retryable failures and a dead token.

Unverified until a real Page returns them (docs/verification.md, C-131): the three metric names and
that they take ``period=lifetime``; that ``values[0].value`` is a plain number for each; that a
Page post (an id with ``_``) and a video id both answer; ``shares.count``; how soon after posting
the figures exist.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from socialhood.platforms.base import MediaInsights
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram.insights import _get, _int, _metrics, _value
from socialhood.platforms.instagram.reads import GRAPH_ID

# Facebook's post metric -> the MediaInsights field (PostMetric key) it fills.
POST_METRIC_KEYS: dict[str, str] = {
    "post_media_view": "views",
    "post_total_media_view_unique": "reach",
    "post_clicks": "clicks",
}


def _post_id(media_ref: str) -> str:
    if not GRAPH_ID.match(media_ref):
        raise PlatformError("platform_rejected", message="Not a Facebook post id")
    return media_ref


async def media_insights(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str
) -> MediaInsights:
    """The post's lifetime figures now: views, reach, clicks and shares."""
    post = _post_id(media_ref)
    items = await _metrics(
        http,
        graph(f"{post}/insights"),
        POST_METRIC_KEYS,
        endpoint="post.insights",
        token=token,
        params={"period": "lifetime"},
    )
    values: dict[str, int | None] = {
        key: _value(items.get(name)) for name, key in POST_METRIC_KEYS.items()
    }
    body = await _get(
        http, graph(post), endpoint="post.shares", token=token, params={"fields": "shares"}
    )
    values["shares"] = _shares(body)
    return MediaInsights(**values)


def _shares(body: Any) -> int | None:
    """``shares.count``; a post nobody shared has no ``shares`` field, which is zero."""
    if not isinstance(body, dict):
        return None
    shares = body.get("shares")
    if isinstance(shares, dict):
        return _int(shares.get("count"))
    return 0 if "shares" not in body else None
