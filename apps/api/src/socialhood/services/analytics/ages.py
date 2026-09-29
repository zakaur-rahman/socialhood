"""Snapshot windows, post ages and formats (FR-ANL-01; TR-AGT-05; agent-architecture §6 "Fair
comparison"). Pure functions shared by the snapshot jobs and the analytics queries.

- A window is due from ``posted_at + age`` until its grace ends: a quarter of the age, at least
  30 minutes (1 h until 1 h 30, 24 h until 30 h, 30 d until 37.5 d). The grace covers a slow
  worker; after it the window is skipped for good, because figures read later would be at the
  wrong age. So posts synced after they were published (before the account was connected) only
  get the windows still ahead of them, and "they join baselines only at ages they have".
- Windows do not overlap, so a post has at most one window due at a time.
- Formats: Reels are compared with Reels, feed posts (images, carousels, feed videos) with feed
  posts, stories with stories.
"""

from __future__ import annotations

import math
from collections.abc import Collection
from datetime import datetime, timedelta
from typing import Literal

from socialhood.models.analytics import LIVE_COUNT_WINDOWS, WINDOW_AGES, SnapshotWindow
from socialhood.models.media import MediaType
from socialhood.schemas.analytics import AgeName

WINDOWS: tuple[SnapshotWindow, ...] = tuple(sorted(WINDOW_AGES, key=WINDOW_AGES.__getitem__))
MIN_GRACE = timedelta(minutes=30)
# The 72 h run and every later one marks the post's earlier snapshots final (FR-ANL-01): by then
# Instagram's lag (up to 48 h) has passed for everything read at 24 h.
FINAL_FROM = SnapshotWindow.H72
FINAL_WINDOWS = frozenset(w for w in WINDOWS if WINDOW_AGES[w] >= WINDOW_AGES[FINAL_FROM])
PROVISIONAL_WINDOWS = frozenset(WINDOWS) - FINAL_WINDOWS
INSIGHT_WINDOWS = frozenset(WINDOWS) - LIVE_COUNT_WINDOWS

FormatName = Literal["feed", "reel", "story"]
FORMATS: dict[FormatName, tuple[str, ...]] = {
    "feed": (MediaType.IMAGE, MediaType.CAROUSEL, MediaType.VIDEO),
    "reel": (MediaType.REEL,),
    "story": (MediaType.STORY,),
}


def grace(window: SnapshotWindow) -> timedelta:
    """How long after it is due a window may still be captured."""
    return max(MIN_GRACE, WINDOW_AGES[window] / 4)


# Posts older than this have no window left to capture.
SNAPSHOT_HORIZON = max(WINDOW_AGES[w] + grace(w) for w in WINDOWS)


def due_window(posted_at: datetime, taken: Collection[str], now: datetime) -> SnapshotWindow | None:
    """The window to capture for a post now, if any: due, inside its grace, not taken yet."""
    for window in WINDOWS:
        due = posted_at + WINDOW_AGES[window]
        if due <= now < due + grace(window) and window not in taken:
            return window
    return None


def reached(posted_at: datetime, now: datetime) -> list[SnapshotWindow]:
    """The windows a post is old enough for, youngest first."""
    return [w for w in WINDOWS if posted_at + WINDOW_AGES[w] <= now]


def closest(taken: Collection[str], target: SnapshotWindow) -> SnapshotWindow | None:
    """Of the windows a post has, the one nearest ``target`` (by ratio of ages; the younger one
    on a tie), or None when it has none."""
    have = [w for w in WINDOWS if w in taken]
    if not have:
        return None
    goal = WINDOW_AGES[target].total_seconds()
    return min(have, key=lambda w: abs(math.log(WINDOW_AGES[w].total_seconds() / goal)))


def shown_age(
    posted_at: datetime, taken: Collection[str], requested: AgeName | None, now: datetime
) -> AgeName:
    """The age a post's own figures are shown (and compared) at.

    - ``lifetime``: its latest known values.
    - A window it has reached: that window, or the snapshot closest to it when it has none there
      (for example a post published before the account was connected).
    - A window it is younger than, or no age: the latest window it has reached (its current
      age), or the snapshot closest to that while that window is still being captured.
    - Younger than 1 h: 1 h, with no figures yet.
    """
    if requested == "lifetime":
        return "lifetime"
    old_enough = reached(posted_at, now)
    if not old_enough:
        return SnapshotWindow.H1.value
    target = SnapshotWindow(requested) if requested in old_enough else old_enough[-1]
    if target in taken:
        return target.value
    near = closest(taken, target)
    return (near or target).value


def exact_age(
    posted_at: datetime, taken: Collection[str], requested: AgeName, now: datetime
) -> AgeName | None:
    """The age a post joins a ranking at: ``requested`` when it has a snapshot there; when it is
    younger than that, its latest snapshot; otherwise None (it is left out)."""
    if requested == "lifetime":
        return "lifetime"
    window = SnapshotWindow(requested)
    if window in taken:
        return window.value
    if posted_at + WINDOW_AGES[window] <= now:
        return None
    younger = [w for w in WINDOWS if w in taken and WINDOW_AGES[w] < WINDOW_AGES[window]]
    return younger[-1].value if younger else None


def format_of(media_type: str) -> FormatName:
    for name, types in FORMATS.items():
        if media_type in types:
            return name
    return "feed"


def same_format(media_type: str) -> tuple[str, ...]:
    """The media types a post of ``media_type`` is compared with by default."""
    return FORMATS[format_of(media_type)]
