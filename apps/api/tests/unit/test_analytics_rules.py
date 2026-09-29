"""T6.5 (FR-ANL-01, FR-ANL-02, TR-AGT-05; agent-architecture §6): the pure rules behind the
snapshots and the analytics service: when a window is due, which age a figure is shown at,
formats, engagement rate, the comparison numbers, date ranges and the account day."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from itertools import pairwise

import pytest

from socialhood.errors import ApiError
from socialhood.models.analytics import WINDOW_AGES, SnapshotWindow
from socialhood.platforms.base import MediaCounts, MediaInsights
from socialhood.services.analytics import ages, stats
from socialhood.services.analytics.account_daily import due_day
from socialhood.services.analytics.common import date_range
from socialhood.services.analytics.snapshots import snapshot_metrics

POSTED = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def at(**delta: float) -> datetime:
    return POSTED + timedelta(**delta)


# ---------------------------------------------------------------- windows


@pytest.mark.parametrize(
    ("after", "window"),
    [
        (timedelta(minutes=59), None),
        (timedelta(hours=1), "1h"),
        (timedelta(hours=1, minutes=29), "1h"),
        (timedelta(hours=1, minutes=30), None),  # grace over: skipped for good
        (timedelta(hours=6), "6h"),
        (timedelta(hours=29, minutes=59), "24h"),
        (timedelta(hours=30), None),
        (timedelta(hours=89), "72h"),
        (timedelta(days=8, hours=18) - timedelta(seconds=1), "7d"),
        (timedelta(days=37, hours=11), "30d"),
        (timedelta(days=37, hours=12), None),
    ],
)
def test_a_window_is_due_until_its_grace_ends(after: timedelta, window: str | None) -> None:
    assert ages.due_window(POSTED, set(), POSTED + after) == window


def test_a_captured_window_is_not_due_again() -> None:
    assert ages.due_window(POSTED, {"24h"}, at(hours=25)) is None
    assert ages.due_window(POSTED, {"24h"}, at(hours=72)) == "72h"


def test_windows_and_their_graces_never_overlap() -> None:
    spans = [(WINDOW_AGES[w], WINDOW_AGES[w] + ages.grace(w)) for w in ages.WINDOWS]
    for (_, end), (start, _) in pairwise(spans):
        assert end <= start
    assert max(end for _, end in spans) == timedelta(days=37, hours=12) == ages.SNAPSHOT_HORIZON


def test_final_and_provisional_windows() -> None:
    assert set(ages.PROVISIONAL_WINDOWS) == {"1h", "6h", "24h"}
    assert set(ages.FINAL_WINDOWS) == {"72h", "7d", "30d"}
    assert set(ages.INSIGHT_WINDOWS) == {"24h", "72h", "7d", "30d"}


# ---------------------------------------------------------------- ages shown


@pytest.mark.parametrize(
    ("taken", "requested", "now", "shown"),
    [
        ({"1h", "6h", "24h"}, "24h", at(days=2), "24h"),
        ({"1h", "6h", "24h"}, None, at(days=2), "24h"),  # the latest window reached
        ({"1h", "6h", "24h"}, "7d", at(days=2), "24h"),  # younger: its current age
        ({"1h", "6h"}, "7d", at(hours=25), "6h"),  # 24 h still being captured
        ({"7d", "30d"}, "24h", at(days=40), "7d"),  # connected late: the closest it has
        ({"1h", "30d"}, "72h", at(days=40), "30d"),  # nearer 72 h than 1 h is, by ratio
        ({"1h", "7d"}, "24h", at(days=10), "7d"),
        (set(), "24h", at(days=2), "24h"),  # nothing captured: the age, no figures
        (set(), None, at(minutes=20), "1h"),  # younger than the first window
        ({"1h"}, "lifetime", at(hours=2), "lifetime"),
    ],
)
def test_the_age_a_post_is_shown_at(
    taken: set[str], requested: str | None, now: datetime, shown: str
) -> None:
    assert ages.shown_age(POSTED, taken, requested, now) == shown  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("taken", "requested", "now", "joined"),
    [
        ({"24h", "72h"}, "24h", at(days=5), "24h"),
        ({"72h"}, "24h", at(days=5), None),  # has no 24 h snapshot: left out
        ({"1h", "6h"}, "24h", at(hours=12), "6h"),  # younger: its latest snapshot
        (set(), "24h", at(hours=12), None),
        (set(), "lifetime", at(hours=12), "lifetime"),
    ],
)
def test_the_age_a_post_joins_a_ranking_at(
    taken: set[str], requested: str, now: datetime, joined: str | None
) -> None:
    assert ages.exact_age(POSTED, taken, requested, now) == joined  # type: ignore[arg-type]


def test_formats() -> None:
    assert ages.same_format("reel") == ("reel",)
    assert set(ages.same_format("image")) == {"image", "carousel", "video"}
    assert ages.same_format("carousel") == ages.same_format("video")
    assert ages.format_of("story") == "story"


# ---------------------------------------------------------------- snapshot contents


def test_live_counts_win_over_insight_likes_and_comments() -> None:
    counts = MediaCounts(like_count=60, comments_count=None)
    read = MediaInsights(reach=1000, likes=55, comments=4, saves=0)
    assert snapshot_metrics(counts, read) == {"reach": 1000, "likes": 60, "comments": 4, "saves": 0}
    assert snapshot_metrics(counts, None) == {"likes": 60}
    assert snapshot_metrics(None, None) == {}


# ---------------------------------------------------------------- numbers


def test_engagement_rate_needs_reach_and_every_interaction() -> None:
    full = {"reach": 2000, "likes": 100, "comments": 10, "shares": 5, "saves": 25}
    assert stats.engagement_rate(full) == 7.0
    assert stats.engagement_rate({**full, "reach": 0}) is None
    assert stats.engagement_rate({k: v for k, v in full.items() if k != "reach"}) is None
    assert stats.engagement_rate({k: v for k, v in full.items() if k != "saves"}) is None
    assert stats.engagement_rate({"likes": 10, "comments": 1}) is None  # a 1 h snapshot


def test_a_comparison_against_a_baseline() -> None:
    got = stats.compare("reach", 3000, [1000, 2000, 2000, 3000])
    assert (got.baseline_median, got.baseline_mean, got.sample_size) == (2000, 2000, 4)
    assert got.diff_pct == 50.0
    assert got.z_score == pytest.approx(1000 / 816.5, abs=0.01)


def test_too_small_a_baseline_gives_no_difference() -> None:
    got = stats.compare("likes", 90, [40, 60])
    assert (got.baseline_median, got.sample_size) == (50, 2)
    assert (got.diff_pct, got.z_score) == (None, None)
    empty = stats.compare("likes", 90, [])
    assert (empty.baseline_median, empty.baseline_mean, empty.sample_size) == (None, None, 0)


def test_no_difference_against_zero_or_without_spread() -> None:
    got = stats.compare("shares", 4, [0, 0, 0])
    assert (got.diff_pct, got.z_score) == (None, None)
    unknown = stats.compare("shares", None, [1, 2, 3])
    assert (unknown.baseline_median, unknown.diff_pct) == (2, None)


# ---------------------------------------------------------------- days


def test_ranges_are_the_workspace_days() -> None:
    now = datetime(2026, 9, 29, 20, 0, tzinfo=UTC)  # already 30 Sep in Kolkata
    span = date_range("Asia/Kolkata", now, None, None)
    assert (span.since, span.until) == (date(2026, 9, 1), date(2026, 9, 30))
    assert span.start == datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
    assert span.end == datetime(2026, 9, 30, 18, 30, tzinfo=UTC)
    only_until = date_range("UTC", now, None, date(2026, 6, 30))
    assert only_until.since == date(2026, 6, 1)
    only_since = date_range("UTC", now, date(2026, 9, 20), None)
    assert only_since.until == date(2026, 9, 29)
    assert date_range("Not/AZone", now, None, None).until == date(2026, 9, 29)
    with pytest.raises(ApiError) as caught:
        date_range("UTC", now, date(2026, 9, 2), date(2026, 9, 1))
    assert caught.value.code == "validation_error"


@pytest.mark.parametrize(
    ("timezone", "now", "day"),
    [
        ("UTC", datetime(2026, 9, 29, 2, 0, tzinfo=UTC), date(2026, 9, 28)),
        ("UTC", datetime(2026, 9, 29, 1, 59, tzinfo=UTC), date(2026, 9, 27)),
        ("Asia/Kolkata", datetime(2026, 9, 28, 20, 30, tzinfo=UTC), date(2026, 9, 28)),
        ("America/New_York", datetime(2026, 9, 29, 5, 0, tzinfo=UTC), date(2026, 9, 27)),
        ("America/New_York", datetime(2026, 9, 29, 6, 0, tzinfo=UTC), date(2026, 9, 28)),
    ],
)
def test_the_account_day_due_from_2am_local(timezone: str, now: datetime, day: date) -> None:
    assert due_day(timezone, now) == day


def test_every_window_is_named() -> None:
    assert [w.value for w in ages.WINDOWS] == [w.value for w in SnapshotWindow]
