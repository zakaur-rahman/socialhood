"""YouTube Analytics (Phase 4): report parsing and the adapter's reading of it."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from socialhood.models.connections import SocialAccount
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.adapter import YouTubeAdapter
from socialhood.platforms.youtube.analytics import (
    DayReport,
    VideoReport,
    day_report,
    video_report,
)
from socialhood.platforms.youtube.fake import CHANNEL, REFRESH_PREFIX, FakeYouTube
from socialhood.platforms.youtube.oauth import ANALYTICS_SCOPE, SCOPE, use_youtube
from socialhood.platforms.youtube.publishing import Video
from socialhood.security.crypto import TokenCipher, new_key

KEY = new_key()


def body(names: list[str], *rows: list[float]) -> dict[str, Any]:
    return {"columnHeaders": [{"name": n} for n in names], "rows": list(rows)}


def test_a_video_report_is_read_by_header_name_not_position() -> None:
    names = ["subscribersGained", "views", "averageViewPercentage", "estimatedMinutesWatched"]
    assert video_report(body(names, [3, 120, 54.6, 45.0])) == VideoReport(
        views=120, watch_minutes=45, avg_view_percent=55, subscribers_gained=3
    )


def test_a_day_report_maps_watch_time_and_subscribers() -> None:
    names = ["views", "estimatedMinutesWatched", "subscribersGained", "subscribersLost"]
    assert day_report(body(names, [10, 7, 2, 1])) == DayReport(
        views=10, watch_minutes=7, subscribers_gained=2, subscribers_lost=1
    )


def test_no_rows_means_nothing_known_yet() -> None:
    assert video_report(body(["views"])) == VideoReport()
    assert day_report({"columnHeaders": [], "rows": []}) == DayReport()
    assert day_report(None) == DayReport()


def channel(scopes: list[str]) -> SocialAccount:
    return SocialAccount(
        id=uuid.uuid4(),
        platform="youtube",
        platform_account_id="UCabc",
        status="active",
        scopes=scopes,
        access_token_enc=TokenCipher([KEY]).encrypt(REFRESH_PREFIX + "1"),
    )


def adapter() -> YouTubeAdapter:
    settings = SimpleNamespace(youtube_provider="fake")
    return YouTubeAdapter(
        PlatformDeps(http=MagicMock(), cipher=TokenCipher([KEY]), settings=settings)  # type: ignore[arg-type]
    )


def fake_with_video(age: timedelta) -> FakeYouTube:
    fake = FakeYouTube()
    fake.videos["v1"] = Video(
        id="v1",
        channel_id=CHANNEL.id,
        views=100,
        likes=5,
        comments=2,
        published_at=datetime.now(UTC) - age,
    )
    fake.video_reports["v1"] = VideoReport(
        views=100, watch_minutes=45, avg_view_seconds=30, avg_view_percent=55, subscribers_gained=3
    )
    return fake


async def test_a_three_day_old_video_gets_watch_time() -> None:
    with use_youtube(fake_with_video(timedelta(days=3))):
        got = await adapter().get_media_insights(
            channel([SCOPE, ANALYTICS_SCOPE]), "v1", media_type="video"
        )
    assert got.metrics() == {
        "views": 100,
        "likes": 5,
        "comments": 2,
        "watch_minutes": 45,
        "avg_view_seconds": 30,
        "avg_view_percent": 55,
        "follows": 3,
    }


async def test_a_young_video_or_a_missing_scope_keeps_the_basic_stats() -> None:
    basic = {"views": 100, "likes": 5, "comments": 2}
    fake = fake_with_video(timedelta(hours=10))
    with use_youtube(fake):
        got = await adapter().get_media_insights(
            channel([SCOPE, ANALYTICS_SCOPE]), "v1", media_type="video"
        )
    assert got.metrics() == basic
    fake = fake_with_video(timedelta(days=3))
    with use_youtube(fake):
        got = await adapter().get_media_insights(channel([SCOPE]), "v1", media_type="video")
    assert got.metrics() == basic
    assert fake.named("analytics_video") == []


async def test_an_analytics_failure_keeps_the_basic_stats() -> None:
    fake = fake_with_video(timedelta(days=3))
    fake.fail_on("analytics_video", PlatformError("platform_rejected", platform_code="403"))
    with use_youtube(fake):
        got = await adapter().get_media_insights(
            channel([SCOPE, ANALYTICS_SCOPE]), "v1", media_type="video"
        )
    assert got.metrics() == {"views": 100, "likes": 5, "comments": 2}


async def test_the_account_day_adds_watch_time_and_subscriber_change() -> None:
    fake = FakeYouTube()
    day = date(2026, 9, 1)
    fake.day_reports[day] = DayReport(
        views=10, watch_minutes=7, subscribers_gained=2, subscribers_lost=1
    )
    with use_youtube(fake):
        full = await adapter().get_account_insights(channel([SCOPE, ANALYTICS_SCOPE]), day)
        basic = await adapter().get_account_insights(channel([SCOPE]), day)
    assert full.followers_count == 1200
    assert full.metrics() == {"views": 10, "watch_minutes": 7, "follows": 2, "unfollows": 1}
    assert basic.followers_count == 1200
    assert basic.metrics() == {}
