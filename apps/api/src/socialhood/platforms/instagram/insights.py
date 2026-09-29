"""Instagram live counts and insights for the metric snapshots (T6.5; FR-ANL-01). The adapter's
``get_media_counts``, ``get_media_insights`` and ``get_account_insights`` delegate here.

Insight calls need the ``instagram_business_manage_insights`` scope, requested only when
IG_REQUEST_INSIGHTS_SCOPE is on (the adapter's capabilities drop POST_INSIGHTS and
ACCOUNT_INSIGHTS without it). ``GET /{media_id}?fields=like_count,comments_count`` gives the live
counts; ``GET /{media_id}/insights`` and ``GET /{ig_user_id}/insights`` the insights.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import AccountInsights, MediaCounts, MediaInsights
from socialhood.platforms.http import PlatformHttp


async def media_counts(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str
) -> MediaCounts | None:
    raise NotImplementedError("T6.5")


async def media_insights(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str, *, media_type: str
) -> MediaInsights:
    raise NotImplementedError("T6.5")


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
    raise NotImplementedError("T6.5")
