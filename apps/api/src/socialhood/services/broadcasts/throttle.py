"""Pacing a broadcast to the number's limits (GR-23). Pure: no I/O and no clock.

WhatsApp limits how many different people a number may start a conversation with in 24 hours,
by its messaging tier (250, 1,000, 10,000, 100,000 or unlimited), and lowers or raises the tier
with the number's quality. This module turns the number's last known tier into a daily limit, and
the people already messaged in the last 24 hours into the room left now.

*Unverified against Meta:* the tier names, the figures and that the limit counts people in a rolling
24 hours (Meta's documentation of messaging limits, read 2026-10-24, not tested against a live
number). When the tier is not known the conservative default is used, the smallest tier a verified
business starts on.
"""

from __future__ import annotations

from datetime import datetime, timedelta

# WhatsApp's messaging tiers: people a number may start a conversation with per rolling 24 hours.
# None is unlimited.
TIER_LIMITS: dict[str, int | None] = {
    "TIER_50": 50,
    "TIER_250": 250,
    "TIER_1K": 1_000,
    "TIER_10K": 10_000,
    "TIER_100K": 100_000,
    "TIER_UNLIMITED": None,
}
DEFAULT_DAILY_LIMIT = 250  # when the tier is unknown
WINDOW = timedelta(hours=24)

# However high the limit, a batch is this many messages and the next one is a minute later, so a
# 2,500-person broadcast takes about 40 minutes and the send queue's own rate limits are never
# the thing that decides the pace.
BATCH_SIZE = 60
BATCH_EVERY = timedelta(minutes=1)
# A day's limit is not used up to the last person: some room is left for replies to customers who
# were not messaged by a broadcast but are new that day (WhatsApp counts every first message).
HEADROOM = 0.9


def limit_for_tier(tier: str | None) -> int | None:
    """People a day for a tier name; the default for an unknown name; None for unlimited."""
    if tier is None or tier not in TIER_LIMITS:
        return DEFAULT_DAILY_LIMIT
    return TIER_LIMITS[tier]


def usable(daily_limit: int | None) -> int | None:
    """What a broadcast may use of the daily limit (None: no limit)."""
    if daily_limit is None:
        return None
    return max(1, int(daily_limit * HEADROOM))


def room(daily_limit: int | None, messaged_last_24h: int) -> int | None:
    """How many more people may be messaged now (None: no limit)."""
    cap = usable(daily_limit)
    if cap is None:
        return None
    return max(0, cap - messaged_last_24h)


def batch_size(
    *, room_now: int | None, waiting: int, quota_left: int | None, size: int = BATCH_SIZE
) -> int:
    """How many recipients to hand over this time: the batch size, cut to the room under the
    daily limit, the plan's monthly quota and the people still waiting."""
    n = min(size, waiting)
    if room_now is not None:
        n = min(n, room_now)
    if quota_left is not None:
        n = min(n, quota_left)
    return max(0, n)


def next_room_at(
    dispatched_at: list[datetime], daily_limit: int | None, now: datetime
) -> datetime | None:
    """When the 24-hour window frees a place, for a number that is at its limit; None when there
    is room now or no limit. ``dispatched_at`` are the times people were messaged in the last 24
    hours."""
    cap = usable(daily_limit)
    if cap is None:
        return None
    recent = sorted(t for t in dispatched_at if t > now - WINDOW)
    if len(recent) < cap:
        return None
    # The (len - cap + 1)th oldest message leaves the window first to make room for one more.
    leaving = recent[len(recent) - cap]
    return leaving + WINDOW
