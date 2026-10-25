"""Facebook Reels and Page Stories (C-131) without a database: the upload, status and publish
calls and bodies, the lost-answer rules, the checklist for a Reel and the format a Reel choice
makes. Meta's shapes are unverified until a real Page publishes (docs/verification.md)."""

from __future__ import annotations

from datetime import UTC
from typing import Any

import pytest

from socialhood.models.publishing import PostFormat
from socialhood.platforms.base import ContainerMedia
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.facebook import publishing
from socialhood.platforms.outcome import DELIVERY_UNKNOWN
from socialhood.services.scheduled_posts import rules
from socialhood.services.scheduled_posts.rules import AssetFacts, PostFacts, TargetFacts
from tests.unit.test_facebook_publishing import (
    IMAGE,
    NOW,
    PAGE,
    VIDEO,
    Recorder,
    account,
    adapter,
)

UPLOAD = "https://rupload.facebook.com/video-upload/v25.0/7001"
START = {"video_id": "7001", "upload_url": UPLOAD}


# ---------------------------------------------------------------- a Facebook Reel


async def test_a_reel_starts_an_upload_then_hands_over_the_hosted_file() -> None:
    recorder = Recorder(START, {"success": True})
    ref = await adapter(recorder).create_reel_container(
        account(), video_url=VIDEO, caption="Tour", page_reel=True
    )
    assert ref == "reel:7001"
    start, upload = recorder.requests
    assert start.url.path.endswith("/me/video_reels")
    assert recorder.body(0) == {"upload_phase": "start"}
    assert start.headers["authorization"] == "Bearer page-token"
    assert str(upload.url) == UPLOAD
    assert upload.headers["authorization"] == "OAuth page-token"
    assert upload.headers["file_url"] == VIDEO


async def test_without_the_reel_choice_a_page_video_stays_a_normal_video() -> None:
    recorder = Recorder({"id": "8001"})
    ref = await adapter(recorder).create_reel_container(account(), video_url=VIDEO, caption="Tour")
    assert ref == "video:8001"
    assert recorder.requests[0].url.path.endswith("/me/videos")


@pytest.mark.parametrize(
    "address",
    [
        "http://rupload.facebook.com/video-upload/7001",  # not https
        "https://rupload.facebook.com.evil.example/7001",  # another host
        "https://evilfacebook.com/7001",
        None,
    ],
)
async def test_the_token_goes_only_to_a_facebook_upload_address(address: str | None) -> None:
    recorder = Recorder({"video_id": "7001", "upload_url": address})
    with pytest.raises(PlatformError):
        await adapter(recorder).create_reel_container(
            account(), video_url=VIDEO, caption="", page_reel=True
        )
    assert len(recorder.requests) == 1  # the upload was never attempted


async def test_a_refused_upload_hand_over_is_a_plain_rejection() -> None:
    recorder = Recorder(START, {"success": False})
    with pytest.raises(PlatformError) as raised:
        await adapter(recorder).create_reel_container(
            account(), video_url=VIDEO, caption="", page_reel=True
        )
    assert raised.value.code == "platform_rejected"


def _phases(**phases: str) -> dict[str, Any]:
    return {"status": {name: {"status": value} for name, value in phases.items()}}


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (_phases(uploading_phase="in_progress"), "IN_PROGRESS"),
        (_phases(uploading_phase="not_started"), "IN_PROGRESS"),
        (_phases(uploading_phase="complete", publishing_phase="not_started"), "FINISHED"),
        (_phases(uploading_phase="complete", publishing_phase="in_progress"), "PUBLISHED"),
        (_phases(uploading_phase="complete", publishing_phase="complete"), "PUBLISHED"),
        (_phases(uploading_phase="complete", processing_phase="error"), "ERROR"),
        (_phases(uploading_phase="error"), "ERROR"),
        ({"status": {"video_status": "expired"}}, "EXPIRED"),
        ({}, "IN_PROGRESS"),
    ],
)
def test_a_reels_phases_become_a_container_status(body: dict[str, Any], expected: str) -> None:
    assert publishing.upload_status(body).status_code == expected


async def test_a_reels_status_is_read_from_the_video() -> None:
    recorder = Recorder(_phases(uploading_phase="complete"))
    status = await adapter(recorder).get_container_status(account(), "reel:7001")
    assert status.status_code == "FINISHED"
    assert recorder.requests[0].url.path.endswith("/7001")
    assert recorder.requests[0].url.params["fields"] == "status"


async def test_a_reel_is_published_by_finishing_the_upload_with_its_caption() -> None:
    recorder = Recorder({"success": True, "post_id": f"{PAGE}_9"})
    media_id = await adapter(recorder).publish_container(account(), "reel:7001", caption="Tour")
    assert media_id == "7001"  # the video id: it is what is read back and commented on
    assert recorder.requests[0].url.path.endswith("/me/video_reels")
    assert recorder.body() == {
        "upload_phase": "finish",
        "video_id": "7001",
        "video_state": "PUBLISHED",
        "description": "Tour",
    }


async def test_a_reel_publish_that_says_no_success_is_an_unconfirmed_answer() -> None:
    with pytest.raises(PlatformError) as raised:
        await adapter(Recorder({"success": False})).publish_container(
            account(), "reel:7001", caption="Tour"
        )
    assert raised.value.code == DELIVERY_UNKNOWN


async def test_a_lost_reel_is_found_by_its_video_id() -> None:
    recorder = Recorder(
        {
            "id": "7001",
            "description": "Tour",
            "created_time": "2026-10-25T10:00:00+0000",
            "permalink_url": "/reel/7001/",
            "picture": "https://cdn.example/p.jpg",
        }
    )
    found = await adapter(recorder).find_published_media(
        account(), "reel:7001", caption="Tour", published_after=NOW
    )
    assert found is not None
    assert (found.platform_media_id, found.permalink) == (
        "7001",
        "https://www.facebook.com/reel/7001/",
    )
    assert recorder.requests[0].url.path.endswith("/7001")


# ---------------------------------------------------------------- Page Stories


async def test_a_photo_story_is_an_unpublished_photo_then_a_photo_story() -> None:
    recorder = Recorder({"id": "9001"}, {"success": True, "post_id": f"{PAGE}_77"})
    page = adapter(recorder)
    ref = await page.create_story_container(account(), ContainerMedia(kind="image", url=IMAGE))
    assert ref == "storyphoto:9001"
    assert recorder.requests[0].url.path.endswith("/me/photos")
    assert recorder.body(0) == {"url": IMAGE, "published": False}
    assert (await page.get_container_status(account(), ref)).status_code == "FINISHED"

    media_id = await page.publish_container(account(), ref)
    assert media_id == f"{PAGE}_77"
    assert recorder.requests[1].url.path.endswith("/me/photo_stories")
    assert recorder.body(1) == {"photo_id": "9001"}


async def test_a_video_story_uploads_like_a_reel_and_finishes_without_a_caption() -> None:
    recorder = Recorder(START, {"success": True}, {"success": True, "post_id": f"{PAGE}_78"})
    page = adapter(recorder)
    ref = await page.create_story_container(account(), ContainerMedia(kind="video", url=VIDEO))
    assert ref == "storyvideo:7001"
    assert recorder.requests[0].url.path.endswith("/me/video_stories")
    assert recorder.requests[1].headers["file_url"] == VIDEO

    media_id = await page.publish_container(account(), ref, caption="never sent")
    assert media_id == f"{PAGE}_78"
    assert recorder.requests[2].url.path.endswith("/me/video_stories")
    assert recorder.body(2) == {"upload_phase": "finish", "video_id": "7001"}


async def test_a_story_without_a_post_id_keeps_the_upload_id() -> None:
    recorder = Recorder({"success": True})
    media_id = await adapter(recorder).publish_container(account(), "storyphoto:9001")
    assert media_id == "9001"


async def test_a_page_story_can_not_be_read_back_or_listed() -> None:
    recorder = Recorder()
    page = adapter(recorder)
    assert await page.get_published_media(account(), f"{PAGE}_78", story=True) is None
    assert await page.list_stories(account()) == []
    assert recorder.requests == []  # Facebook has no read API for them


async def test_a_lost_video_story_is_known_from_its_id_alone() -> None:
    recorder = Recorder()
    found = await adapter(recorder).find_published_media(
        account(), "storyvideo:7001", caption="", published_after=NOW, story=True
    )
    assert found is not None
    assert (found.platform_media_id, found.media_type, found.permalink) == ("7001", "story", None)
    assert found.posted_at.tzinfo is UTC
    assert recorder.requests == []


def test_only_a_reel_and_a_video_story_say_in_their_status_that_they_published() -> None:
    assert set(publishing.STATUS_SHOWS_PUBLISHED) == {"reel", "storyvideo"}
    for kind in ("reel", "storyphoto", "storyvideo"):
        assert publishing.split_ref(f"{kind}:1") == (kind, "1")
    with pytest.raises(PlatformError):
        publishing.split_ref("story:1")


# ---------------------------------------------------------------- the checklist and format


def _target(platform: str = "facebook", **values: object) -> TargetFacts:
    base: dict[str, object] = {
        "handle": "@maple.page" if platform == "facebook" else "@maple.bakery",
        "status": "active",
        "can_publish": True,
        "caption_override": None,
        "recent_posts": 0,
        "platform": platform,
    }
    return TargetFacts(**{**base, **values})  # type: ignore[arg-type]


def _video(duration_s: float | None = 20.0, **values: object) -> AssetFacts:
    base: dict[str, object] = {
        "resource_type": "video",
        "format": "mp4",
        "bytes": 20 * 1024 * 1024,
        "width": 1080,
        "height": 1920,
        "duration_s": duration_s,
    }
    return AssetFacts(**{**base, **values})  # type: ignore[arg-type]


def _image() -> AssetFacts:
    return AssetFacts("image", "jpg", 200_000, 1080, 1350, None)


def _reel(**values: object) -> PostFacts:
    base: dict[str, object] = {
        "targets": [_target()],
        "assets": [_video()],
        "caption": "Behind the counter",
        "first_comment": None,
        "publish_at": None,
        "reel": True,
    }
    return PostFacts(**{**base, **values})  # type: ignore[arg-type]


def _items(post: PostFacts) -> dict[str, list[tuple[bool, str]]]:
    out: dict[str, list[tuple[bool, str]]] = {}
    for item in rules.checklist(post, now=NOW, publishing_limit=100):
        out.setdefault(item.key, []).append((item.ok, item.message))
    return out


def test_one_video_chosen_as_a_reel_is_a_reel_and_nothing_else_is() -> None:
    assert rules.derive_format(["video"], reel=True) == PostFormat.REEL
    assert rules.derive_format(["image"], reel=True) is None
    assert rules.derive_format(["video", "video"], reel=True) is None
    assert rules.derive_format([], reel=True, text=True) is None
    assert rules.derive_format(["video"]) == PostFormat.REEL  # as before: a single video


def test_a_page_reel_passes_with_a_caption_and_no_publishing_limit() -> None:
    items = _items(_reel())
    assert all(ok for rows in items.values() for ok, _ in rows), items
    assert items["media"] == [(True, "Reel")]
    assert "publishing_limit" not in items


def test_a_reel_needs_a_page_and_one_video() -> None:
    assert _items(_reel(targets=[_target("instagram")]))["accounts"] == [
        (
            False,
            "Choose a Facebook Page for a Reel. Instagram already publishes a single video "
            "as a Reel.",
        )
    ]
    assert _items(_reel(assets=[_image()]))["media"] == [(False, "A Facebook Reel is one video.")]
    assert _items(_reel(assets=[_video(), _video()]))["media"] == [
        (False, "A Facebook Reel is one video.")
    ]
    assert _items(_reel(assets=[]))["media"] == [(False, "Add a video for the Reel.")]


@pytest.mark.parametrize(
    ("duration", "message"),
    [
        (2.0, "Reel videos must be at least 3 seconds."),
        (91.0, "Videos can be up to 90 seconds."),
    ],
)
def test_a_reel_video_runs_3_to_90_seconds(duration: float, message: str) -> None:
    assert _items(_reel(assets=[_video(duration)]))["media_files"] == [(False, message)]
    assert _items(_reel(assets=[_video(3.0)]))["media_files"][0][0] is True
    assert _items(_reel(assets=[_video(90.0)]))["media_files"][0][0] is True


def test_a_reel_that_is_not_9_16_passes_with_a_note_naming_the_platform() -> None:
    wide = _video(width=1920, height=1080)
    assert _items(_reel(assets=[wide]))["media_files"] == [
        (True, "9:16 fits a Reel best. Facebook may crop or add bars to this file.")
    ]
    cross = _reel(targets=[_target(), _target("instagram")], assets=[wide])
    assert _items(cross)["media_files"] == [
        (True, "9:16 fits a Reel best. Instagram and Facebook may crop or add bars to this file.")
    ]


def test_a_reel_keeps_its_caption_checks_and_is_never_a_text_post() -> None:
    long = "x" * 2300
    cross = _reel(targets=[_target(), _target("instagram")], caption=long)
    assert [ok for ok, _ in _items(cross)["caption"]] == [False]  # Instagram's 2,200
    assert [ok for ok, _ in _items(_reel(caption=long))["caption"]] == [True]  # a Page's
    assert _items(_reel(assets=[], caption="Only text"))["media"][0][0] is False
