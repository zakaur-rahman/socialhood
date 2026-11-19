"""YouTube Analytics reports (Phase 4): watch time and subscriber change.

``GET youtubeanalytics.googleapis.com/v2/reports`` has its own quota, apart from the Data API's.
Its data lags about two days, so a young video or a recent day answers an empty ``rows`` (read as
"nothing yet", not as zeros: every figure is None). The sandbox channel answers fixed numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.youtube.client import google_http

REPORTS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
VIDEO_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained"
)
DAY_METRICS = "views,estimatedMinutesWatched,subscribersGained,subscribersLost"


@dataclass(frozen=True, kw_only=True)
class VideoReport:
    views: int | None = None
    watch_minutes: int | None = None
    avg_view_seconds: int | None = None
    avg_view_percent: int | None = None
    subscribers_gained: int | None = None


@dataclass(frozen=True, kw_only=True)
class DayReport:
    views: int | None = None
    watch_minutes: int | None = None
    subscribers_gained: int | None = None
    subscribers_lost: int | None = None


def _number(raw: Any) -> int | None:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return None
    return round(raw)


def row_values(body: Any) -> dict[str, int | None]:
    """The first row by column name; no rows (or a malformed body) is an empty mapping."""
    if not isinstance(body, dict):
        return {}
    rows = body.get("rows") or []
    if not rows or not isinstance(rows[0], list):
        return {}
    names = [h.get("name") for h in body.get("columnHeaders") or [] if isinstance(h, dict)]
    return {str(n): _number(v) for n, v in zip(names, rows[0], strict=False)}


def video_report(body: Any) -> VideoReport:
    v = row_values(body)
    return VideoReport(
        views=v.get("views"),
        watch_minutes=v.get("estimatedMinutesWatched"),
        avg_view_seconds=v.get("averageViewDuration"),
        avg_view_percent=v.get("averageViewPercentage"),
        subscribers_gained=v.get("subscribersGained"),
    )


def day_report(body: Any) -> DayReport:
    v = row_values(body)
    return DayReport(
        views=v.get("views"),
        watch_minutes=v.get("estimatedMinutesWatched"),
        subscribers_gained=v.get("subscribersGained"),
        subscribers_lost=v.get("subscribersLost"),
    )


class YouTubeAnalytics(Protocol):
    async def video(
        self, token: str, video_id: str, *, since: date, until: date
    ) -> VideoReport: ...

    async def day(self, token: str, day: date) -> DayReport: ...


class HttpYouTubeAnalytics:
    def __init__(self, deps: PlatformDeps) -> None:
        self.http = google_http(deps.http)

    async def _report(self, endpoint: str, token: str, params: dict[str, str]) -> Any:
        return await self.http.request(
            "GET",
            REPORTS_URL,
            endpoint=endpoint,
            token=token,
            params={"ids": "channel==MINE", **params},
        )

    async def video(self, token: str, video_id: str, *, since: date, until: date) -> VideoReport:
        body = await self._report(
            "analytics.video",
            token,
            {
                "metrics": VIDEO_METRICS,
                "filters": f"video=={video_id}",
                "startDate": since.isoformat(),
                "endDate": until.isoformat(),
            },
        )
        return video_report(body)

    async def day(self, token: str, day: date) -> DayReport:
        body = await self._report(
            "analytics.day",
            token,
            {"metrics": DAY_METRICS, "startDate": day.isoformat(), "endDate": day.isoformat()},
        )
        return day_report(body)


class SandboxYouTubeAnalytics:
    """The sandbox channel's fixed numbers."""

    async def video(self, token: str, video_id: str, *, since: date, until: date) -> VideoReport:
        return VideoReport(
            views=120,
            watch_minutes=45,
            avg_view_seconds=30,
            avg_view_percent=55,
            subscribers_gained=3,
        )

    async def day(self, token: str, day: date) -> DayReport:
        return DayReport(views=200, watch_minutes=80, subscribers_gained=5, subscribers_lost=1)


def analytics_for(acct_is_sandbox: bool, deps: PlatformDeps) -> YouTubeAnalytics:
    """The sandbox's, a test's fake (it serves both), else Google's."""
    if acct_is_sandbox:
        return SandboxYouTubeAnalytics()
    from socialhood.platforms.youtube.oauth import youtube_for

    client = youtube_for(deps)
    if hasattr(client, "video_reports"):
        return client  # type: ignore[return-value]
    return HttpYouTubeAnalytics(deps)
