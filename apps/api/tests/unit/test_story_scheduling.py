"""GR-39 (C-114) without a database or network: the Story format, its checklist rules, the
container body sent to Instagram, the Story wording of publishing errors, the sandbox's Story
lifecycle and the 24-hour expiry shown on a published target."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from socialhood.models.connections import SocialAccount
from socialhood.models.publishing import ScheduledPostTarget, TargetStatus
from socialhood.platforms.base import ContainerMedia
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.instagram import oauth
from socialhood.platforms.instagram.adapter import InstagramAdapter
from socialhood.platforms.sandbox import history, publishing
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.services.scheduled_posts import rules, views
from socialhood.services.scheduled_posts.rules import AssetFacts, PostFacts, TargetFacts
from socialhood.settings import AppEnv, Settings
from tests.support.instagram import GRAPH

SETTINGS = Settings(
    _env_file=None,
    app_env=AppEnv.TEST,
    database_url="postgresql+asyncpg://x/y",
    database_url_direct="postgresql://x/y",
    redis_url="redis://x",
)
V = f"{GRAPH}/{SETTINGS.ig_graph_version}"
IG = "17841400000000001"
NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
IMAGE_URL = "https://res.cloudinary.com/demo/image/upload/f_jpg/a.jpg"
VIDEO_URL = "https://res.cloudinary.com/demo/video/upload/vc_h264/b.mp4"
MB = 1024 * 1024


def _image(width: int = 1080, height: int = 1920, **values: object) -> AssetFacts:
    base: dict[str, object] = {
        "resource_type": "image",
        "format": "jpg",
        "bytes": 200_000,
        "width": width,
        "height": height,
        "duration_s": None,
    }
    return AssetFacts(**{**base, **values})  # type: ignore[arg-type]


def _video(duration_s: float = 20.0, **values: object) -> AssetFacts:
    base: dict[str, object] = {
        "resource_type": "video",
        "format": "mp4",
        "bytes": 20 * MB,
        "width": 1080,
        "height": 1920,
        "duration_s": duration_s,
    }
    return AssetFacts(**{**base, **values})  # type: ignore[arg-type]


def _target(**values: object) -> TargetFacts:
    base: dict[str, object] = {
        "handle": "@maple.bakery",
        "status": "active",
        "can_publish": True,
        "caption_override": None,
        "recent_posts": 0,
    }
    return TargetFacts(**{**base, **values})  # type: ignore[arg-type]


def _story(**values: object) -> PostFacts:
    base: dict[str, object] = {
        "targets": [_target()],
        "assets": [_image()],
        "caption": "kept on the draft, never sent",
        "first_comment": None,
        "publish_at": None,
        "story": True,
    }
    return PostFacts(**{**base, **values})  # type: ignore[arg-type]


def _checklist(post: PostFacts) -> dict[str, list[tuple[bool, str]]]:
    out: dict[str, list[tuple[bool, str]]] = {}
    for item in rules.checklist(post, now=NOW, publishing_limit=100):
        out.setdefault(item.key, []).append((item.ok, item.message))
    return out


# ---------------------------------------------------------------- format and checklist


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        (["image"], "story"),
        (["video"], "story"),
        ([], None),
        (["image", "image"], None),  # a Story can't be a carousel
        (["raw"], None),
    ],
)
def test_a_story_is_exactly_one_image_or_video(kinds: list[str], expected: str | None) -> None:
    assert rules.derive_format(kinds, story=True) == expected


def test_a_story_checklist_passes_and_has_no_caption_checks() -> None:
    items = _checklist(_story())
    assert items["media"] == [(True, "Story")]
    assert items["media_files"] == [(True, "Media meets Instagram's requirements")]
    assert items["caption"] == [(True, rules.STORY_NO_CAPTION)]
    assert "hashtags" not in items
    assert "mentions" not in items


def test_a_long_caption_on_a_story_draft_is_not_checked() -> None:
    long = "#tag " * 40 + "@someone " * 30
    assert all(ok for ok, _ in _checklist(_story(caption=long))["caption"])


def test_two_files_cannot_be_a_story() -> None:
    items = _checklist(_story(assets=[_image(), _image()]))
    assert items["media"] == [(False, rules.STORY_ONE_FILE)]


def test_a_story_image_that_is_not_nine_by_sixteen_passes_with_a_note() -> None:
    [(ok, message)] = _checklist(_story(assets=[_image(1080, 1080)]))["media_files"]
    assert ok
    assert "9:16" in message


@pytest.mark.parametrize(
    ("duration", "ok"), [(2.0, False), (3.0, True), (60.0, True), (61.0, False), (None, True)]
)
def test_story_video_length(duration: float | None, ok: bool) -> None:
    [(passed, message)] = _checklist(_story(assets=[_video(duration_s=duration)]))["media_files"]  # type: ignore[arg-type]
    assert passed is ok
    if not ok:
        assert "seconds" in message


def test_a_reel_can_still_be_90_seconds_but_a_story_cannot() -> None:
    assert rules.asset_problem(_video(80.0)) is None
    assert rules.asset_problem(_video(80.0), story=True) == "Story videos can be up to 60 seconds."


def test_a_facebook_page_cannot_take_a_story() -> None:
    items = _checklist(_story(targets=[_target(platform="facebook", handle="Maple Page")]))
    assert items["accounts"] == [
        (False, "Maple Page can't publish Stories. Remove it or choose a post.")
    ]


# ---------------------------------------------------------------- the container body


@pytest.fixture
async def adapter() -> AsyncIterator[InstagramAdapter]:
    async with httpx.AsyncClient() as http:
        yield InstagramAdapter(PlatformDeps(http, TokenCipher([new_key()]), SETTINGS))


def account(adapter: InstagramAdapter) -> SocialAccount:
    return SocialAccount(
        platform="instagram",
        platform_account_id=IG,
        username="maple.bakery",
        access_token_enc=adapter.deps.cipher.encrypt("IGQVJlong"),
        scopes=list(oauth.BASE_SCOPES),
    )


@respx.mock
async def test_an_image_story_container_is_media_type_stories_with_an_image_url(
    adapter: InstagramAdapter,
) -> None:
    route = respx.post(f"{V}/{IG}/media").respond(200, json={"id": "17889455560051444"})
    ref = await adapter.create_story_container(
        account(adapter), ContainerMedia(kind="image", url=IMAGE_URL)
    )
    assert ref == "17889455560051444"
    assert json.loads(route.calls.last.request.content) == {
        "media_type": "STORIES",
        "image_url": IMAGE_URL,
    }


@respx.mock
async def test_a_video_story_container_sends_video_url_and_no_caption(
    adapter: InstagramAdapter,
) -> None:
    route = respx.post(f"{V}/{IG}/media").respond(200, json={"id": "17889455560051445"})
    await adapter.create_story_container(
        account(adapter), ContainerMedia(kind="video", url=VIDEO_URL)
    )
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"media_type": "STORIES", "video_url": VIDEO_URL}


def _graph_error(sub: int) -> dict[str, object]:
    return {"error": {"message": "x", "type": "OAuthException", "code": 9004, "error_subcode": sub}}


@respx.mock
async def test_story_errors_use_story_wording_and_unknown_ones_the_general_reason(
    adapter: InstagramAdapter,
) -> None:
    respx.post(f"{V}/{IG}/media").respond(400, json=_graph_error(2207009))
    with pytest.raises(PlatformError) as shape:
        await adapter.create_story_container(
            account(adapter), ContainerMedia(kind="image", url=IMAGE_URL)
        )
    assert "9:16" in shape.value.message

    respx.post(f"{V}/{IG}/media").respond(400, json=_graph_error(2207050))
    with pytest.raises(PlatformError) as restricted:
        await adapter.create_story_container(
            account(adapter), ContainerMedia(kind="image", url=IMAGE_URL)
        )
    assert "restricted" in restricted.value.message


@respx.mock
async def test_a_story_is_found_again_by_time_in_the_live_stories(
    adapter: InstagramAdapter,
) -> None:
    stories = respx.get(f"{V}/me/stories").respond(
        200,
        json={
            "data": [
                {"id": "1", "media_type": "IMAGE", "timestamp": "2026-10-24T11:00:00+0000"},
                {"id": "2", "media_type": "IMAGE", "timestamp": "2026-10-24T12:05:00+0000"},
            ]
        },
    )
    found = await adapter.find_published_media(
        account(adapter), "17889455560051444", caption="", published_after=NOW, story=True
    )
    assert stories.called
    assert found is not None
    assert (found.platform_media_id, found.media_type) == ("2", "story")


@respx.mock
async def test_a_published_story_is_read_back_with_the_story_fields(
    adapter: InstagramAdapter,
) -> None:
    route = respx.get(f"{V}/17920238422030506").respond(
        200,
        json={
            "id": "17920238422030506",
            "media_type": "IMAGE",
            "permalink": "https://www.instagram.com/stories/maple.bakery/1/",
            "timestamp": "2026-10-24T12:00:00+0000",
        },
    )
    media = await adapter.get_published_media(account(adapter), "17920238422030506", story=True)
    assert media is not None
    assert media.media_type == "story"
    assert "caption" not in route.calls.last.request.url.params["fields"]


# ---------------------------------------------------------------- the sandbox


@pytest.fixture(autouse=True)
def _reset_sandbox() -> None:
    publishing.reset()


def _sandbox_account() -> SocialAccount:
    return SocialAccount(
        platform="instagram", platform_account_id="sandbox_ig_1", username="maple.bakery"
    )


def test_a_sandbox_story_publishes_and_is_listed_as_a_live_story_not_a_feed_post() -> None:
    acct = _sandbox_account()
    ref = publishing.create_story_container(acct, ContainerMedia(kind="image", url=IMAGE_URL))
    assert publishing.container_status(acct, ref).status_code == "FINISHED"
    media_id = publishing.publish_container(acct, ref)
    published = publishing.published_media(acct, media_id)
    assert published is not None
    assert published.media_type == "story"
    assert "/stories/" in (published.permalink or "")
    assert next(m.platform_media_id for m in history.stories(acct)) == media_id
    assert media_id not in [m.platform_media_id for m in history.posts(acct, limit=10)]


def test_a_sandbox_story_leaves_the_live_list_after_24_hours() -> None:
    acct = _sandbox_account()
    ref = publishing.create_story_container(acct, ContainerMedia(kind="image", url=IMAGE_URL))
    media_id = publishing.publish_container(acct, ref)
    later = datetime.now(UTC) + timedelta(hours=25)
    assert media_id not in [m.platform_media_id for m in history.stories(acct, now=later)]


def test_a_sandbox_video_story_processes_like_a_reel() -> None:
    acct = _sandbox_account()
    ref = publishing.create_story_container(acct, ContainerMedia(kind="video", url=VIDEO_URL))
    codes = [publishing.container_status(acct, ref).status_code for _ in range(3)]
    assert codes == ["IN_PROGRESS", "IN_PROGRESS", "FINISHED"]


def test_a_lost_story_publish_is_found_among_the_live_stories() -> None:
    acct = _sandbox_account()
    ref = publishing.create_story_container(acct, ContainerMedia(kind="image", url=IMAGE_URL))
    publishing.lose_next_publish_answer()
    with pytest.raises(PlatformError):
        publishing.publish_container(acct, ref)
    found = publishing.find_published_media(
        acct, ref, caption="", published_after=datetime.now(UTC) - timedelta(minutes=1), story=True
    )
    assert found is not None
    assert found.media_type == "story"


# ---------------------------------------------------------------- when it disappears


def test_a_published_story_target_says_when_it_disappears() -> None:
    published_at = NOW
    target = ScheduledPostTarget(
        social_account_id=uuid.uuid4(),
        status=TargetStatus.PUBLISHED,
        published_at=published_at,
        platform_media_id="1",
    )
    story = views.target_out(target, None, None, story=True)
    post = views.target_out(target, None, None)
    assert story.expires_at == published_at + timedelta(hours=24)
    assert post.expires_at is None
