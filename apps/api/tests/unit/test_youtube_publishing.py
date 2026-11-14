"""C-196: YouTube publishing's pure parts - the options, the checklist's YouTube rules and the
route, the processing states, Google's upload calls and their errors, the metadata we send and
when it changed, the quota day, the lost-answer match and the streaming from storage."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from socialhood.models.publishing import YOUTUBE_SHORT_MAX_S
from socialhood.platforms.buckets import google_day, next_google_day
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.adapter import GONE, container_status
from socialhood.platforms.youtube.fake import FakeYouTube
from socialhood.platforms.youtube.publishing import (
    HttpVideos,
    Video,
    match_recent,
    status_body,
    stream_from_source,
    web_origin,
)
from socialhood.schemas.publishing import YouTubeOptions, youtube_tags_length
from socialhood.services.post_publishing.youtube_direct import changed, metadata
from socialhood.services.scheduled_posts import rules
from socialhood.services.scheduled_posts.rules import AssetFacts, PostFacts, TargetFacts

NOW = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)
OPTIONS = {"title": "Bread", "made_for_kids": False, "synthetic_media": False}


# ---------------------------------------------------------------- the options


def test_options_need_both_answers_and_a_clean_title() -> None:
    options = YouTubeOptions.model_validate(OPTIONS)
    assert (options.privacy, options.format, options.notify_subscribers) == (
        "public",
        "video",
        True,
    )
    for missing in ("made_for_kids", "synthetic_media", "title"):
        with pytest.raises(ValidationError):
            YouTubeOptions.model_validate({k: v for k, v in OPTIONS.items() if k != missing})
    for title in ("<b>Bread</b>", "   ", "x" * 101):
        with pytest.raises(ValidationError):
            YouTubeOptions.model_validate({**OPTIONS, "title": title})
    with pytest.raises(ValidationError):
        YouTubeOptions.model_validate({**OPTIONS, "category_id": "music"})


def test_tags_count_as_youtube_counts_them() -> None:
    assert youtube_tags_length(["bread", "sour dough"]) == 5 + 12 + 1
    options = YouTubeOptions.model_validate({**OPTIONS, "tags": ["a", " a ", "b"]})
    assert options.tags == ["a", "b"]
    with pytest.raises(ValidationError):
        YouTubeOptions.model_validate({**OPTIONS, "tags": [f"{i}" + "x" * 99 for i in range(6)]})


# ---------------------------------------------------------------- the checklist and the route


def channel(options: dict[str, Any] | None = OPTIONS, **values: Any) -> TargetFacts:
    return TargetFacts(
        handle="@maple",
        status="active",
        can_publish=True,
        caption_override=values.pop("caption_override", None),
        recent_posts=0,
        platform="youtube",
        options=YouTubeOptions.model_validate(options) if options else None,
        **values,
    )


def instagram() -> TargetFacts:
    return TargetFacts(
        handle="@maple.bakery",
        status="active",
        can_publish=True,
        caption_override=None,
        recent_posts=0,
    )


def video(width: int = 1080, height: int = 1920, duration_s: float = 30) -> AssetFacts:
    return AssetFacts("video", "mp4", 1000, width, height, duration_s)


def post(*targets: TargetFacts, assets: tuple[AssetFacts, ...] = (), **values: Any) -> PostFacts:
    return PostFacts(
        targets=targets,
        assets=assets,
        caption=values.pop("caption", "Fresh bread"),
        first_comment=None,
        publish_at=NOW + timedelta(hours=1),
        **values,
    )


def youtube(facts: PostFacts) -> dict[str | None, str]:
    return {
        i.field: i.message
        for i in rules.checklist(facts, now=NOW, publishing_limit=50)
        if i.key == "youtube" and not i.ok
    }


def test_the_route_is_direct_only_for_youtube_channels_with_an_empty_tray() -> None:
    assert rules.youtube_direct(post(channel())) is True
    assert rules.youtube_direct(post(channel(), assets=(video(),))) is False
    assert rules.youtube_direct(post(channel(), instagram())) is False
    assert rules.youtube_direct(post()) is False


def test_a_direct_post_needs_its_upload_and_options() -> None:
    assert youtube(post(channel())) == {"targets.0": "Upload the video to YouTube for @maple."}
    assert youtube(post(channel(video_uploaded=True))) == {}
    missing = youtube(post(channel(None, video_uploaded=True)))
    assert list(missing) == ["targets.0.options"]
    items = rules.checklist(post(channel(video_uploaded=True)), now=NOW, publishing_limit=50)
    assert [i.message for i in items if i.key == "media"] == [rules.YOUTUBE_DIRECT]
    assert all(i.key != "hashtags" for i in items)  # Instagram's limits don't apply
    assert all(i.key != "publishing_limit" for i in items)


def test_the_media_route_needs_exactly_one_video() -> None:
    image = AssetFacts("image", "jpg", 1000, 1080, 1350, None)
    assert youtube(post(channel(), instagram(), assets=(image,))) == {
        "asset_ids": rules.YOUTUBE_ONE_VIDEO
    }
    assert youtube(post(channel(), instagram(), assets=(video(),))) == {}
    assert youtube(post(channel(), assets=(video(),), story=True)) == {
        "kind": rules.YOUTUBE_NO_STORY
    }


def test_a_short_is_vertical_and_up_to_three_minutes() -> None:
    short = {**OPTIONS, "format": "short"}
    assert youtube(post(channel(short), instagram(), assets=(video(),))) == {}
    assert youtube(post(channel(short), instagram(), assets=(video(1920, 1080),))) == {
        "asset_ids.0": rules.YOUTUBE_SHORT_SHAPE
    }
    long = video(duration_s=YOUTUBE_SHORT_MAX_S + 1)
    assert youtube(post(channel(short), assets=(long,))) == {
        "asset_ids.0": rules.YOUTUBE_SHORT_LENGTH
    }
    # A video (not a Short) for YouTube only has no length limit of ours.
    items = rules.checklist(
        post(channel(), assets=(video(duration_s=3600),)), now=NOW, publishing_limit=50
    )
    assert all(i.ok for i in items if i.key == "media_files")


def test_the_description_is_checked_in_bytes_and_for_brackets() -> None:
    long = "🍞" * 1251  # 4 bytes each: 5,004 bytes in 1,251 characters
    problems = youtube(post(channel(video_uploaded=True), caption=long))
    assert problems["caption"].startswith(
        "Shorten the YouTube description to 5,000 bytes (now 5,004)"
    )
    own = channel(video_uploaded=True, caption_override="Use <b>this</b>")
    assert youtube(post(own)) == {"targets.0.caption_override": rules.YOUTUBE_DESCRIPTION_BRACKETS}


# ---------------------------------------------------------------- processing


def vid(**values: Any) -> Video:
    return Video(id="v1", **values)


@pytest.mark.parametrize(
    ("video", "code"),
    [
        (None, "ERROR"),
        (vid(upload_status="failed", failure="codec"), "ERROR"),
        (vid(upload_status="rejected", failure="duplicate"), "ERROR"),
        (vid(upload_status="uploaded", processing="processing"), "IN_PROGRESS"),
        (vid(upload_status="uploaded", processing="succeeded"), "FINISHED"),
        (
            vid(upload_status="processed", privacy="private", publish_at=NOW + timedelta(hours=1)),
            "IN_PROGRESS",
        ),
        (vid(upload_status="processed", privacy="public"), "FINISHED"),
        (vid(upload_status="processed", privacy="private"), "FINISHED"),
    ],
)
def test_youtube_s_processing_maps_to_container_states(video: Video | None, code: str) -> None:
    assert container_status(video, NOW).status_code == code


def test_failures_say_youtube() -> None:
    assert container_status(None, NOW).detail == GONE
    failed = container_status(vid(upload_status="failed", failure="codec"), NOW)
    assert failed.detail == "YouTube couldn't process the video (codec)."


# ---------------------------------------------------------------- what we send


def test_scheduled_uploads_are_private_with_publish_at_only_when_public() -> None:
    p = SimpleNamespace(caption="Desc")
    t = SimpleNamespace(caption_override=None)
    at = NOW + timedelta(days=1)
    options = YouTubeOptions.model_validate(OPTIONS)
    public = metadata(p, t, options, at=at, now=False)  # type: ignore[arg-type]
    assert (public["privacy"], public["publish_at"]) == ("private", "2026-11-15T10:00:00Z")
    assert status_body(public)["publishAt"] == "2026-11-15T10:00:00Z"
    unlisted = YouTubeOptions.model_validate({**OPTIONS, "privacy": "unlisted"})
    held = metadata(p, t, unlisted, at=at, now=False)  # type: ignore[arg-type]
    assert (held["privacy"], held["publish_at"]) == ("private", None)
    now = metadata(p, t, unlisted, at=None, now=True)  # type: ignore[arg-type]
    assert (now["privacy"], now["publish_at"], now["now"]) == ("unlisted", None, True)
    assert "publishAt" not in status_body(now)
    assert status_body(now)["selfDeclaredMadeForKids"] is False
    assert changed(public, {**public, "notify_subscribers": False}) is False
    assert changed(public, {**public, "title": "Other"}) is True


def test_the_quota_day_is_google_s_pacific_day() -> None:
    assert google_day(NOW).isoformat() == "2026-11-14"  # 2 am in Los Angeles
    assert next_google_day(NOW) == datetime(2026, 11, 15, 8, 0, tzinfo=UTC)


def test_a_lost_answer_is_matched_by_title_and_time() -> None:
    since = NOW - timedelta(minutes=2)
    older = Video(id="a", title="Bread", published_at=NOW - timedelta(hours=1))
    mine = Video(id="b", title="Bread", published_at=NOW)
    other = Video(id="c", title="Cake", published_at=NOW)
    assert match_recent([older, mine, other], title="Bread", published_after=since) == mine
    assert match_recent([older, other], title="Bread", published_after=since) is None


def test_the_web_origin_is_the_app_s_scheme_and_host() -> None:
    settings: Any = SimpleNamespace(web_base_url="https://app.amplychat.com/w/x/")
    assert web_origin(settings) == "https://app.amplychat.com"
    assert web_origin(SimpleNamespace(web_base_url=None)) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------- Google's upload calls


def http_videos(handler: Any) -> HttpVideos:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    deps: Any = PlatformDeps(http=client, cipher=None, settings=None)  # type: ignore[arg-type]
    return HttpVideos(deps)


async def test_a_session_opens_with_the_upload_headers_and_the_origin() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, headers={"Location": "https://upload.test/s1"})

    meta = metadata(
        SimpleNamespace(caption="D"),  # type: ignore[arg-type]
        SimpleNamespace(caption_override=None),  # type: ignore[arg-type]
        YouTubeOptions.model_validate({**OPTIONS, "notify_subscribers": False}),
        at=None,
        now=True,
    )
    uri = await http_videos(handler).open_session(
        "tok", metadata=meta, size=1234, content_type="video/mp4", origin="https://web.test"
    )
    assert uri == "https://upload.test/s1"
    [request] = seen
    assert request.url.path == "/upload/youtube/v3/videos"
    assert dict(request.url.params) == {
        "uploadType": "resumable",
        "part": "snippet,status",
        "notifySubscribers": "false",
    }
    assert request.headers["X-Upload-Content-Length"] == "1234"
    assert request.headers["X-Upload-Content-Type"] == "video/mp4"
    assert request.headers["Origin"] == "https://web.test"
    assert request.headers["Authorization"] == "Bearer tok"
    body = json.loads(request.content)
    assert body["status"] == {
        "privacyStatus": "public",
        "selfDeclaredMadeForKids": False,
        "containsSyntheticMedia": False,
    }
    assert body["snippet"] == {"title": "Bread", "description": "D"}


async def test_pieces_read_range_and_a_gone_session_is_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        content_range = request.headers["Content-Range"]
        if content_range == "bytes */10":
            return httpx.Response(404)
        if content_range.startswith("bytes 0-"):
            return httpx.Response(308, headers={"Range": "bytes=0-4"})
        return httpx.Response(200, json={"id": "v9", "status": {"uploadStatus": "uploaded"}})

    videos = http_videos(handler)
    first = await videos.put_chunk("https://upload.test/s1", b"abcdef", start=0, total=10)
    assert (first.received, first.video) == (5, None)
    last = await videos.put_chunk("https://upload.test/s1", b"fghij", start=5, total=10)
    assert last.video is not None
    assert last.video.id == "v9"
    assert await videos.progress("https://upload.test/s1", total=10) is None


async def test_google_s_errors_on_upload_calls_are_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403, json={"error": {"code": 403, "errors": [{"reason": "quotaExceeded"}]}}
        )

    meta = metadata(
        SimpleNamespace(caption=""),  # type: ignore[arg-type]
        SimpleNamespace(caption_override=None),  # type: ignore[arg-type]
        YouTubeOptions.model_validate(OPTIONS),
        at=None,
        now=True,
    )
    with pytest.raises(PlatformError) as error:
        await http_videos(handler).open_session(
            "tok", metadata=meta, size=None, content_type="video/*"
        )
    assert (error.value.code, error.value.retryable) == ("platform_rate_limited", True)


# ---------------------------------------------------------------- streaming from storage


async def test_the_stream_sends_pieces_and_goes_on_from_an_offset() -> None:
    data = bytes(range(256)) * 4096  # 1 MiB
    ranges: list[str | None] = []

    def storage(request: httpx.Request) -> httpx.Response:
        rng = request.headers.get("range")
        ranges.append(rng)
        start = int(rng.removeprefix("bytes=").split("-")[0]) if rng else 0
        return httpx.Response(206 if rng else 200, content=data[start:])

    fake = FakeYouTube()
    fake.chunk_bytes = 256 * 1024
    meta = {"title": "Bread", "privacy": "public"}
    uri = await fake.open_session(
        "fake-yt-access:fake-yt-refresh:1", metadata=meta, size=len(data), content_type="video/mp4"
    )
    fake.sessions[uri].received = 512 * 1024  # an earlier try sent half
    async with httpx.AsyncClient(transport=httpx.MockTransport(storage)) as http:
        video = await stream_from_source(
            fake, http, uri, "https://res.test/v.mp4", offset=512 * 1024, total=len(data)
        )
    assert video.title == "Bread"
    assert ranges == ["bytes=524288-"]
    assert [c["start"] for c in fake.named("put_chunk")] == [512 * 1024, 768 * 1024]
