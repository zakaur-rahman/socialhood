"""Story insights (C-131): a Story is read at 1 h, 6 h and 23 h, before it goes down at 24 h."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from socialhood.models.analytics import STORY_WINDOWS, WINDOW_AGES, PostMetric, SnapshotWindow
from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import MediaInsights
from socialhood.platforms.sandbox import insights as sandbox
from socialhood.schemas.analytics import ExtraMetrics
from socialhood.services.analytics import ages
from socialhood.services.analytics.queries import EXTRA_METRICS, Figures

T0 = datetime(2026, 10, 25, 10, 0, tzinfo=UTC)


def test_a_story_has_its_own_windows_and_feed_posts_never_get_23h() -> None:
    assert [w.value for w in STORY_WINDOWS] == ["1h", "6h", "23h"]
    assert SnapshotWindow.H23 not in ages.WINDOWS
    assert ages.windows_for("story") == STORY_WINDOWS
    assert ages.windows_for("image") == ages.WINDOWS
    assert ages.windows_for("reel") == ages.WINDOWS


def test_a_stories_last_reading_ends_before_it_goes_down() -> None:
    assert ages.grace(SnapshotWindow.H23, story=True) == timedelta(minutes=50)
    # Every Story reading, grace included, ends 10 minutes before the Story's 24 hours.
    for window in STORY_WINDOWS:
        end = WINDOW_AGES[window] + ages.grace(window, story=True)
        assert end <= timedelta(hours=24) - ages.STORY_READ_MARGIN
    assert timedelta(hours=23, minutes=50) == ages.STORY_HORIZON
    # A feed post keeps the usual grace.
    assert ages.grace(SnapshotWindow.H24) == timedelta(hours=6)


def test_due_windows_of_a_story() -> None:
    def due(after: timedelta, taken: tuple[str, ...] = ()) -> str | None:
        window = ages.due_window(T0, taken, T0 + after, STORY_WINDOWS)
        return window.value if window else None

    assert due(timedelta(minutes=59)) is None
    assert due(timedelta(hours=1, minutes=5)) == "1h"
    assert due(timedelta(hours=1, minutes=5), ("1h",)) is None
    assert due(timedelta(hours=6, minutes=1)) == "6h"
    assert due(timedelta(hours=23, minutes=10)) == "23h"
    assert due(timedelta(hours=23, minutes=55)) is None  # the Story is about to go
    assert due(timedelta(hours=25)) is None
    # The same age for a feed post is no window at all.
    assert ages.due_window(T0, (), T0 + timedelta(hours=23, minutes=10)) is None


def test_the_age_a_story_is_shown_at() -> None:
    taken = {"1h", "6h"}
    now = T0 + timedelta(hours=8)
    assert ages.shown_age(T0, taken, None, now, STORY_WINDOWS) == "6h"
    assert ages.shown_age(T0, taken, "23h", now, STORY_WINDOWS) == "6h"  # not reached yet
    later = T0 + timedelta(hours=23, minutes=30)
    assert ages.shown_age(T0, {*taken, "23h"}, None, later, STORY_WINDOWS) == "23h"
    assert ages.shown_age(T0, taken, "23h", later, STORY_WINDOWS) == "6h"  # missed: the nearest
    assert ages.exact_age(T0, {"1h"}, "23h", now, STORY_WINDOWS) == "1h"
    assert ages.exact_age(T0, {"1h"}, "23h", later, STORY_WINDOWS) is None


def test_story_figures_are_stored_and_read_back() -> None:
    insights = MediaInsights(reach=900, views=1100, replies=5, taps_forward=700, exits=60)
    assert insights.metrics() == {
        "reach": 900,
        "views": 1100,
        "replies": 5,
        "taps_forward": 700,
        "exits": 60,
    }
    stored = {"replies", "taps_forward", "taps_back", "swipes_forward", "exits", "clicks"}
    assert stored <= set(PostMetric)
    assert set(EXTRA_METRICS) == set(ExtraMetrics.model_fields) == stored
    figures = Figures("23h", insights.metrics())
    assert figures.extra() == ExtraMetrics(replies=5, taps_forward=700, exits=60)
    assert Figures("24h", {"reach": 5}).extra() is None


def _account(platform: str) -> SocialAccount:
    return SocialAccount(platform=platform, platform_account_id=f"sandbox_{platform}_1")


def test_the_sandbox_gives_a_story_replies_and_taps_but_no_likes() -> None:
    got = sandbox.media_insights(_account("instagram"), "sandbox_media_x", media_type="story")
    assert (got.likes, got.comments, got.saves) == (None, None, None)
    taps = (got.replies, got.taps_forward, got.taps_back, got.swipes_forward, got.exits)
    assert None not in taps


def test_the_sandbox_gives_a_page_post_clicks_and_a_page_story_nothing() -> None:
    page = sandbox.media_insights(_account("facebook"), "sandbox_media_p", media_type="video")
    assert page.clicks is not None
    assert (page.saves, page.follows) == (None, None)
    assert page.likes is not None
    assert page.shares is not None
    story = sandbox.media_insights(_account("facebook"), "sandbox_media_s", media_type="story")
    assert story == MediaInsights()
