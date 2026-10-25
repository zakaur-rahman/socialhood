"""GR-30 (C-115) without a database: the Facebook Page publishing calls (references, bodies, status
and errors), the capability that needs pages_manage_posts, the platform-aware checklist and the
best-times arithmetic including too little data. Meta's shapes are unverified until a real Page
publishes (docs/verification.md)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, time, timedelta
from typing import Any

import httpx
import pytest

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import ContainerMedia
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.facebook import oauth, publishing
from socialhood.platforms.facebook.adapter import FacebookAdapter
from socialhood.platforms.outcome import DELIVERY_UNKNOWN
from socialhood.security.crypto import cipher_for, new_key
from socialhood.services.scheduled_posts import best_times, rules
from socialhood.services.scheduled_posts.rules import AssetFacts, PostFacts, TargetFacts
from socialhood.settings import AppEnv, Settings

PAGE = "109876543210001"
KEY = new_key()
IMAGE = "https://res.cloudinary.com/demo/image/upload/f_jpg/a.jpg"
VIDEO = "https://res.cloudinary.com/demo/video/upload/vc_h264/b.mp4"
NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
MB = 1024 * 1024


class Recorder:
    def __init__(self, *answers: Any, status: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self.answers = list(answers) or [{"success": True}]
        self.status = status

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return httpx.Response(self.status, json=answer)

    def body(self, index: int = -1) -> dict[str, Any]:
        return json.loads(self.requests[index].content)  # type: ignore[no-any-return]


def account(scopes: list[str] | None = None) -> SocialAccount:
    return SocialAccount(
        platform="facebook",
        platform_account_id=PAGE,
        username="mapleshop",
        access_token_enc=cipher_for((KEY,)).encrypt("page-token"),
        scopes=list(oauth.SCOPES) if scopes is None else scopes,
    )


def adapter(recorder: Recorder) -> FacebookAdapter:
    settings = Settings(
        _env_file=None,
        app_env=AppEnv.TEST,
        database_url="postgresql+asyncpg://x:x@127.0.0.1/x",
        database_url_direct="postgresql://x:x@127.0.0.1/x",
        redis_url="redis://127.0.0.1:6379/14",
        token_encryption_keys=[KEY],
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))
    return FacebookAdapter(PlatformDeps(http=client, cipher=cipher_for((KEY,)), settings=settings))


# ---------------------------------------------------------------- capability


def test_publishing_needs_the_pages_manage_posts_permission() -> None:
    page = adapter(Recorder())
    assert Capability.PUBLISH in page.capabilities_for(account())
    old = account(scopes=["pages_show_list", "pages_messaging"])
    assert Capability.PUBLISH not in page.capabilities_for(old)


def test_the_connect_url_asks_for_pages_manage_posts() -> None:
    assert "pages_manage_posts" in oauth.SCOPES


# ---------------------------------------------------------------- the calls


async def test_a_photo_is_uploaded_unpublished_with_its_caption_then_posted_to_the_feed() -> None:
    recorder = Recorder({"id": "9001"}, {"id": f"{PAGE}_555"})
    page = adapter(recorder)
    ref = await page.create_image_container(account(), image_url=IMAGE, caption="Fresh bread")
    assert ref == "photo:9001"
    assert recorder.requests[0].url.path.endswith("/me/photos")
    assert recorder.body(0) == {"url": IMAGE, "published": False, "caption": "Fresh bread"}
    assert (await page.get_container_status(account(), ref)).status_code == "FINISHED"

    post_id = await page.publish_container(account(), ref, caption="Fresh bread")
    assert post_id == f"{PAGE}_555"
    assert recorder.requests[1].url.path.endswith("/me/feed")
    assert recorder.body(1) == {
        "attached_media": [{"media_fbid": "9001"}],
        "message": "Fresh bread",
    }
    assert recorder.requests[1].headers["authorization"] == "Bearer page-token"


async def test_several_photos_become_one_feed_post_with_attached_media() -> None:
    recorder = Recorder({"id": "9001"}, {"id": "9002"}, {"id": "9003"}, {"id": f"{PAGE}_556"})
    page = adapter(recorder)
    children = [
        await page.create_carousel_item(account(), ContainerMedia(kind="image", url=IMAGE))
        for _ in range(3)
    ]
    assert recorder.body(0) == {"url": IMAGE, "published": False}  # no caption on a child
    parent = await page.create_carousel_container(account(), children=children, caption="x")
    assert parent == "photos:9001,9002,9003"
    await page.publish_container(account(), parent, caption="Weekend menu")
    assert recorder.body(-1) == {
        "attached_media": [{"media_fbid": id_} for id_ in ("9001", "9002", "9003")],
        "message": "Weekend menu",
    }


async def test_a_video_can_not_join_several_photos_and_one_photo_is_not_a_post_of_photos() -> None:
    page = adapter(Recorder())
    with pytest.raises(PlatformError, match="several photos or one video"):
        await page.create_carousel_item(account(), ContainerMedia(kind="video", url=VIDEO))
    with pytest.raises(PlatformError):
        await page.create_carousel_container(account(), children=["photo:1"], caption="")


async def test_a_video_uploads_unpublished_is_polled_then_published() -> None:
    recorder = Recorder(
        {"id": "7001"},
        {"status": {"video_status": "processing"}},
        {"status": {"video_status": "ready"}},
        {"success": True},
    )
    page = adapter(recorder)
    ref = await page.create_reel_container(account(), video_url=VIDEO, caption="Tour")
    assert ref == "video:7001"
    assert recorder.body(0) == {"file_url": VIDEO, "published": False, "description": "Tour"}
    assert (await page.get_container_status(account(), ref)).status_code == "IN_PROGRESS"
    assert (await page.get_container_status(account(), ref)).status_code == "FINISHED"
    assert recorder.requests[1].url.params["fields"] == "status"
    assert await page.publish_container(account(), ref, caption="Tour") == "7001"
    assert recorder.requests[-1].url.path.endswith("/7001")
    assert recorder.body() == {"published": True}


async def test_a_video_that_fails_to_process_reads_as_an_error() -> None:
    page = adapter(Recorder({"status": {"video_status": "error"}}))
    status = await page.get_container_status(account(), "video:7001")
    assert (status.status_code, status.detail) == ("ERROR", "Facebook couldn't process the video.")


async def test_a_text_post_sends_the_message_and_the_first_link() -> None:
    recorder = Recorder({"id": f"{PAGE}_557"})
    page = adapter(recorder)
    ref = await page.create_text_container(account())
    assert ref == "text:post"
    await page.publish_container(
        account(), ref, caption="New menu is up. See https://maple.example/menu."
    )
    assert recorder.body() == {
        "message": "New menu is up. See https://maple.example/menu.",
        "link": "https://maple.example/menu",
    }
    with pytest.raises(PlatformError, match="needs text"):
        await page.publish_container(account(), ref, caption="  ")


async def test_a_lost_publish_answer_is_delivery_unknown_and_known_errors_have_reasons() -> None:
    lost = adapter(Recorder({}))  # answered, but without an id
    with pytest.raises(PlatformError) as unknown:
        await lost.publish_container(account(), "text:post", caption="hi")
    assert unknown.value.code == DELIVERY_UNKNOWN

    duplicate = adapter(Recorder({"error": {"code": 506, "message": "Duplicate"}}, status=400))
    with pytest.raises(PlatformError) as refused:
        await duplicate.publish_container(account(), "text:post", caption="hi")
    assert "duplicate" in refused.value.message


async def test_the_new_post_is_read_back_by_its_kind_of_id() -> None:
    recorder = Recorder(
        {"id": f"{PAGE}_555", "created_time": "2026-10-24T12:00:00+0000", "message": "hi"},
        {
            "id": "7001",
            "description": "Tour",
            "created_time": "2026-10-24T12:00:00+0000",
            "permalink_url": "/mapleshop/videos/7001/",
        },
    )
    page = adapter(recorder)
    post = await page.get_published_media(account(), f"{PAGE}_555")
    video = await page.get_published_media(account(), "7001")
    assert post is not None
    assert post.media_type == "image"
    assert video is not None
    assert (video.media_type, video.permalink) == (
        "video",
        "https://www.facebook.com/mapleshop/videos/7001/",
    )
    assert "permalink_url" in recorder.requests[1].url.params["fields"]


async def test_the_publishing_quota_is_not_available_on_a_page() -> None:
    page = adapter(Recorder())
    with pytest.raises(PlatformError) as raised:
        await page.get_publishing_quota(account())
    assert raised.value.code == "capability_unavailable"


def test_the_first_link_drops_trailing_punctuation() -> None:
    assert publishing.first_link("see (https://a.example/x), ok") == "https://a.example/x"
    assert publishing.first_link("no link") is None


# ---------------------------------------------------------------- the checklist per platform


def _asset(kind: str = "image", width: int = 1080, height: int = 1920, **values: Any) -> AssetFacts:
    base: dict[str, Any] = {
        "resource_type": kind,
        "format": "jpg" if kind == "image" else "mp4",
        "bytes": MB,
        "width": width,
        "height": height,
        "duration_s": 20.0 if kind == "video" else None,
    }
    return AssetFacts(**{**base, **values})


def _target(platform: str, handle: str = "@x") -> TargetFacts:
    return TargetFacts(
        handle=handle,
        status="active",
        can_publish=True,
        caption_override=None,
        recent_posts=0,
        platform=platform,
    )


def _post(
    *targets: TargetFacts, assets: list[AssetFacts] | None = None, **values: Any
) -> PostFacts:
    base: dict[str, Any] = {
        "targets": list(targets),
        "assets": [] if assets is None else assets,
        "caption": "Fresh bread #sourdough",
        "first_comment": None,
        "publish_at": None,
    }
    return PostFacts(**{**base, **values})


def _failing(post: PostFacts) -> dict[str, str]:
    items = rules.checklist(post, now=NOW, publishing_limit=100)
    return {i.field or i.key: i.message for i in items if not i.ok}


def _keys(post: PostFacts) -> list[str]:
    return [i.key for i in rules.checklist(post, now=NOW, publishing_limit=100)]


def test_text_with_only_pages_is_a_text_post() -> None:
    post = _post(_target("facebook", "Maple"))
    assert rules.derive_format([], text=True) == "text"
    assert _failing(post) == {}
    assert "media_files" not in _keys(post)
    assert "publishing_limit" not in _keys(post)  # Pages have none
    assert {"hashtags", "mentions"}.isdisjoint(_keys(post))  # Instagram's limits


def test_text_with_an_instagram_account_needs_media() -> None:
    post = _post(_target("instagram"), _target("facebook", "Maple"))
    assert _failing(post) == {"asset_ids": "Add an image or video."}


def test_a_page_alone_with_nothing_is_told_it_can_be_text() -> None:
    assert _failing(_post(_target("facebook"), caption="")) == {
        "asset_ids": rules.FACEBOOK_NO_MEDIA
    }


def test_a_page_takes_any_photo_shape_but_instagram_does_not() -> None:
    wide = [_asset(width=3000, height=500)]
    assert _failing(_post(_target("facebook"), assets=wide)) == {}
    assert "asset_ids.0" in _failing(_post(_target("instagram"), assets=wide))
    both = _post(_target("instagram"), _target("facebook"), assets=wide)
    assert "asset_ids.0" in _failing(both)  # the stricter platform decides


def test_photos_and_a_video_do_not_mix_on_a_page() -> None:
    mixed = [_asset(height=1350), _asset("video")]
    assert _failing(_post(_target("facebook"), assets=mixed)) == {
        "asset_ids": rules.FACEBOOK_NO_MIX
    }
    assert _failing(_post(_target("instagram"), assets=mixed)) == {}


def test_hashtag_and_mention_limits_are_instagrams_only() -> None:
    many = " ".join(f"#t{i}" for i in range(40))
    assert _failing(_post(_target("facebook"), assets=[_asset()], caption=many)) == {}
    assert "caption" in _failing(_post(_target("instagram"), assets=[_asset()], caption=many))


def test_only_instagram_counts_towards_the_publishing_limit() -> None:
    busy = TargetFacts(
        handle="@p",
        status="active",
        can_publish=True,
        caption_override=None,
        recent_posts=500,
        platform="facebook",
    )
    assert _failing(_post(busy, assets=[_asset()])) == {}


# ---------------------------------------------------------------- best times


def _at(day: int, hour: int) -> datetime:
    # 2026-10-05 is a Monday
    return datetime(2026, 10, 5 + day, hour, 15, tzinfo=UTC)


def _history() -> list[tuple[datetime, int]]:
    posts: list[tuple[datetime, int]] = []
    for week in range(3):
        shift = timedelta(weeks=week)
        posts.append((_at(0, 18) + shift, 90))  # Monday 18:00 does well
        posts.append((_at(0, 9) + shift, 20))
        posts.append((_at(2, 12) + shift, 50))
        posts.append((_at(2, 12) + shift + timedelta(minutes=20), 40))
    return posts


def test_the_best_hour_of_each_weekday_with_enough_posts_each() -> None:
    days, enough = best_times.suggest(_history(), "UTC")
    assert enough is True
    assert days[0].local_time == time(18, 0)
    assert days[0].posts == 3
    assert days[0].lift_percent is not None
    assert days[0].lift_percent > 0
    assert days[2].local_time == time(12, 0)
    assert days[2].posts == 6
    assert [d.local_time for d in days[3:]] == [None] * 4  # no post those days
    assert [d.weekday for d in days] == list(range(7))


def test_an_hour_needs_two_posts_to_count() -> None:
    posts = [*_history(), (_at(1, 7), 1000)]  # one huge post, alone at its hour
    days, _ = best_times.suggest(posts, "UTC")
    assert days[1].local_time is None


def test_the_hour_is_in_the_workspace_time_zone() -> None:
    days, _ = best_times.suggest(_history(), "Asia/Kolkata")  # UTC+5:30
    assert days[0].local_time == time(23, 0)  # 18:15 UTC is 23:45 IST: the 23:00 hour


def test_too_little_history_gives_no_suggestions() -> None:
    days, enough = best_times.suggest(_history()[: best_times.MIN_POSTS - 1], "UTC")
    assert enough is False
    assert all(d.local_time is None and d.posts == 0 for d in days)
    assert len(days) == 7


def test_a_zero_median_does_not_divide_by_zero() -> None:
    posts = [(_at(0, 10) + timedelta(weeks=w), 0) for w in range(12)]
    days, enough = best_times.suggest(posts, "UTC")
    assert enough is True
    assert days[0].lift_percent is None  # nothing to compare against
