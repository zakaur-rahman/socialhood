"""Best posting times (GR-30, "Best times" in R2; C-115): a suggested posting hour per weekday from
an account's own posts. Plain arithmetic, cached; no AI model is involved.

Method (``METHOD``): take the account's last ``MAX_POSTS`` posts from the last ``WINDOW_DAYS`` days
(stories left out) that have a known engagement. A post's engagement is its latest snapshot's
likes + comments + shares + saves, else its live like and comment counts (so a Facebook Page,
which has no insights yet, works too). Each post is scored against the account's median post
(score 1.0 is typical). Posts are grouped by weekday and hour in the workspace time zone; an hour
needs ``MIN_BUCKET`` posts to count, and a weekday's suggestion is the hour whose posts have the
best median score (the earlier hour on a tie). Fewer than ``MIN_POSTS`` scored posts: "not enough
history", and no day gets a suggestion. A weekday with no hour of ``MIN_BUCKET`` posts has none.

The answer is cached in Valkey for ``CACHE_TTL_S`` seconds per account; a cache that can't be read
or written is skipped.
"""

from __future__ import annotations

import json
import statistics
import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.media import MediaItem, MediaType
from socialhood.observability.logging import get_logger
from socialhood.schemas.publishing import BestTimeDay, BestTimes
from socialhood.services.analytics.queries import figures_at, snapshots_for
from socialhood.services.scheduled_posts import slots

log = get_logger(__name__)

MAX_POSTS = 90
WINDOW_DAYS = 180
MIN_POSTS = 10
MIN_BUCKET = 2
CACHE_TTL_S = 6 * 3600
INTERACTIONS = ("likes", "comments", "shares", "saves")
METHOD = (
    f"The hour whose posts did best on each weekday, from the last {MAX_POSTS} posts in "
    f"{WINDOW_DAYS} days (an hour needs {MIN_BUCKET} posts, and {MIN_POSTS} posts are needed in "
    "all). Best means the median of likes, comments, shares and saves against the account's "
    "median post."
)


def cache_key(account_id: uuid.UUID) -> str:
    return f"besttimes:{require_workspace()}:{account_id}"


def suggest(posts: Sequence[tuple[datetime, int]], tz_name: str) -> tuple[list[BestTimeDay], bool]:
    """(the seven days, enough history) from (posted_at, interactions) pairs."""
    tz = slots.zone(tz_name)
    empty = [BestTimeDay(weekday=day) for day in range(7)]
    if len(posts) < MIN_POSTS:
        return empty, False
    median = statistics.median(count for _, count in posts)
    typical = median or 1  # a median of 0: scores are the counts themselves, with no lift
    buckets: dict[tuple[int, int], list[float]] = defaultdict(list)
    for posted_at, count in posts:
        local = posted_at.astimezone(tz)
        buckets[(local.weekday(), local.hour)].append(count / typical)
    days: list[BestTimeDay] = []
    for weekday in range(7):
        hours = [
            (statistics.median(scores), hour, len(scores))
            for (day, hour), scores in buckets.items()
            if day == weekday and len(scores) >= MIN_BUCKET
        ]
        if not hours:
            days.append(BestTimeDay(weekday=weekday))
            continue
        score, hour, count = max(hours, key=lambda row: (row[0], -row[1]))
        days.append(
            BestTimeDay(
                weekday=weekday,
                local_time=time(hour, 0),
                posts=count,
                lift_percent=round((score - 1) * 100) if median else None,
            )
        )
    return days, True


async def scored_posts(
    session: AsyncSession, account_id: uuid.UUID, *, now: datetime
) -> list[tuple[datetime, int]]:
    """The account's recent posts with a known engagement, newest first."""
    rows = list(
        (
            await session.scalars(
                select(MediaItem)
                .where(
                    MediaItem.social_account_id == account_id,
                    MediaItem.media_type != MediaType.STORY,
                    MediaItem.posted_at >= now - timedelta(days=WINDOW_DAYS),
                )
                .order_by(MediaItem.posted_at.desc())
                .limit(MAX_POSTS)
            )
        ).all()
    )
    snaps = await snapshots_for(session, [row.id for row in rows])
    scored: list[tuple[datetime, int]] = []
    for row in rows:
        figures = figures_at(row, snaps.get(row.id, {}), "lifetime")
        if figures is None:
            continue
        known = [figures.values[key] for key in INTERACTIONS if key in figures.values]
        if known:
            scored.append((row.posted_at, sum(known)))
    return scored


async def best_times(
    session: AsyncSession,
    redis: Redis,
    account_id: uuid.UUID,
    *,
    timezone: str,
    now: datetime,
) -> BestTimes:
    """GET …/best-times. 404 not_found for an account that isn't this workspace's."""
    await slots.account_or_404(session, account_id)
    key = cache_key(account_id)
    try:
        cached = await redis.get(key)
        if cached:
            return BestTimes.model_validate_json(cached)
    except Exception:
        log.warning("best_times_cache_unreadable", account_id=str(account_id))
    scored = await scored_posts(session, account_id, now=now.astimezone(UTC))
    days, enough = suggest(scored, timezone)
    out = BestTimes(
        social_account_id=account_id,
        timezone=slots.zone(timezone).key,
        enough_history=enough,
        sample_size=len(scored),
        min_posts=MIN_POSTS,
        method=METHOD,
        days=days,
        computed_at=now,
    )
    try:
        await redis.set(key, json.dumps(out.model_dump(mode="json")), ex=CACHE_TTL_S)
    except Exception:
        log.warning("best_times_cache_unwritable", account_id=str(account_id))
    return out
