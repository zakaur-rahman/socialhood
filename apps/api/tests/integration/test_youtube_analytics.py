"""YouTube Analytics (Phase 4): a snapshot of a video stores watch time when the scope is granted
and the video is past the lag; an Analytics failure or a missing scope keeps the basic stats."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.analytics import VideoReport
from socialhood.platforms.youtube.fake import CHANNEL, FakeYouTube
from socialhood.platforms.youtube.oauth import ANALYTICS_SCOPE, SCOPE
from socialhood.platforms.youtube.publishing import Video
from socialhood.security.crypto import TokenCipher
from socialhood.services.analytics.snapshots import snapshot_account_posts
from socialhood.settings import Settings
from tests.support.api import TOKEN_KEY
from tests.support.inbox import make_workspace
from tests.support.ingest import rows, sessions
from tests.support.post_metrics import make_post
from tests.support.youtube import make_channel

VIDEO = "vid-analytics-1"


@pytest.fixture
async def deps(api_settings: Settings) -> AsyncIterator[PlatformDeps]:
    async with httpx.AsyncClient() as http:
        yield PlatformDeps(http=http, cipher=TokenCipher([TOKEN_KEY]), settings=api_settings)


async def snapshot_of_old_video(
    engine: AsyncEngine, deps: PlatformDeps, fake: FakeYouTube, scopes: list[str]
) -> list[dict[str, Any]]:
    posted = datetime.now(UTC) - timedelta(hours=73)
    fake.videos[VIDEO] = Video(
        id=VIDEO, channel_id=CHANNEL.id, views=100, likes=5, comments=2, published_at=posted
    )
    fake.video_reports[VIDEO] = VideoReport(
        views=100, watch_minutes=45, avg_view_seconds=30, avg_view_percent=55, subscribers_gained=3
    )
    wid = await make_workspace(engine)
    account = await make_channel(engine, wid, scopes=scopes)
    await make_post(
        engine,
        workspace_id=wid,
        account_id=account,
        posted_at=posted,
        media_type="video",
        platform_media_id=VIDEO,
    )
    await snapshot_account_posts(sessions(engine), deps, workspace_id=wid, account_id=account)
    return await rows(engine, "SELECT metrics FROM post_metric_snapshots ORDER BY captured_at")


async def test_a_three_day_old_video_stores_watch_time(
    engine: AsyncEngine, clean_db: None, deps: PlatformDeps, fake_youtube: FakeYouTube
) -> None:
    stored = await snapshot_of_old_video(engine, deps, fake_youtube, [SCOPE, ANALYTICS_SCOPE])
    assert stored
    assert stored[-1]["metrics"]["watch_minutes"] == 45
    assert stored[-1]["metrics"]["follows"] == 3


async def test_a_channel_without_the_analytics_scope_keeps_basic_stats(
    engine: AsyncEngine, clean_db: None, deps: PlatformDeps, fake_youtube: FakeYouTube
) -> None:
    stored = await snapshot_of_old_video(engine, deps, fake_youtube, [SCOPE])
    assert stored
    assert "watch_minutes" not in stored[-1]["metrics"]
    assert stored[-1]["metrics"]["views"] == 100
    assert fake_youtube.named("analytics_video") == []


async def test_an_analytics_failure_still_stores_basic_stats(
    engine: AsyncEngine, clean_db: None, deps: PlatformDeps, fake_youtube: FakeYouTube
) -> None:
    fake_youtube.fail_on("analytics_video", PlatformError("platform_rejected", platform_code="403"))
    stored = await snapshot_of_old_video(engine, deps, fake_youtube, [SCOPE, ANALYTICS_SCOPE])
    assert stored
    assert stored[-1]["metrics"]["views"] == 100
    assert "watch_minutes" not in stored[-1]["metrics"]
