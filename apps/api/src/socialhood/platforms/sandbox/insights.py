"""Sandbox live counts and insights (T6.5; TR-PL-07, FR-ANL-01): deterministic made-up figures that
grow with a post's age, so snapshots and comparisons can be developed without Meta. The adapter's
``get_media_counts``, ``get_media_insights`` and ``get_account_insights`` delegate here.

The adapter is not told when a post was published, so a post's age counts from the first time the
sandbox is asked about it (the posts ``history.posts`` makes up count from their made-up publish
time). Each post reaches its own final reach, derived from its id; formats get Instagram's metrics
for them (no likes, comments or saves on stories; no profile visits or follows on Reels).
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import UTC, date, datetime, timedelta

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import AccountInsights, MediaCounts, MediaInsights

HISTORY_POST = re.compile(r"_post_(\d+)$")  # history.posts: post i was published 2i + 1 days ago
GROWTH_HOURS = 20.0  # most of a post's reach arrives in its first day or two
FOLLOWERS_EPOCH = date(2026, 1, 1)

_first_seen: dict[str, datetime] = {}


def _seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:12], 16)


def _age_hours(media_ref: str, now: datetime) -> float:
    match = HISTORY_POST.search(media_ref)
    published = now - timedelta(days=2 * int(match.group(1)) + 1) if match else now
    first = _first_seen.setdefault(media_ref, published)
    return max(0.0, (now - first).total_seconds() / 3600)


def _figures(acct: SocialAccount, media_ref: str, now: datetime) -> dict[str, int]:
    seed = _seed(acct.platform_account_id, media_ref)
    grown = 1 - math.exp(-_age_hours(media_ref, now) / GROWTH_HOURS)
    reach = round((400 + seed % 1600) * grown)
    likes = round(reach * (4 + seed % 7) / 100)
    return {
        "reach": reach,
        "views": round(reach * 1.4),
        "likes": likes,
        "comments": round(likes * 0.12),
        "shares": round(likes * 0.08),
        "saves": round(likes * 0.15),
        "profile_visits": round(reach * 0.02),
        "follows": round(reach * 0.004),
    }


def media_counts(acct: SocialAccount, media_ref: str) -> MediaCounts | None:
    figures = _figures(acct, media_ref, datetime.now(UTC))
    return MediaCounts(like_count=figures["likes"], comments_count=figures["comments"])


def media_insights(acct: SocialAccount, media_ref: str, *, media_type: str) -> MediaInsights:
    figures = _figures(acct, media_ref, datetime.now(UTC))
    if media_type == "story":
        for name in ("likes", "comments", "saves"):
            figures[name] = 0
    interactions = sum(figures[n] for n in ("likes", "comments", "shares", "saves"))
    if media_type == "story":
        return MediaInsights(
            reach=figures["reach"],
            views=figures["views"],
            shares=figures["shares"],
            total_interactions=interactions,
            profile_visits=figures["profile_visits"],
            follows=figures["follows"],
        )
    feed = media_type != "reel"
    return MediaInsights(
        reach=figures["reach"],
        views=figures["views"],
        likes=figures["likes"],
        comments=figures["comments"],
        shares=figures["shares"],
        saves=figures["saves"],
        total_interactions=interactions,
        profile_visits=figures["profile_visits"] if feed else None,
        follows=figures["follows"] if feed else None,
    )


def account_insights(acct: SocialAccount, day: date, *, tz: str) -> AccountInsights:
    """A made-up day for the account: followers grow by a few a day, the rest vary by day."""
    ref = acct.platform_account_id
    seed = _seed(ref, day.isoformat())
    reach = 800 + seed % 2400
    follows = 2 + seed % 15
    return AccountInsights(
        followers_count=1000 + _seed(ref) % 500 + 3 * (day - FOLLOWERS_EPOCH).days,
        reach=reach,
        views=round(reach * 1.7),
        accounts_engaged=round(reach * 0.06),
        total_interactions=round(reach * 0.09),
        follows=follows,
        unfollows=seed % 5,
        profile_links_taps=seed % 30,
    )
