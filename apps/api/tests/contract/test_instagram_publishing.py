"""T7.2 (TR-PL-01, FR-PUB-05, FR-PUB-11): the Instagram adapter's content publishing calls, one
contract per container type, against responses shaped like Meta's documented ones (TR-TEST-01
contract layer): quota, image, Reel, carousel items (image and video) and carousel containers,
container status, publish, read-back, the lost-answer lookup and the first comment."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
import respx

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import ContainerMedia, ContainerStatus, PublishingQuota
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.instagram import oauth
from socialhood.platforms.instagram.adapter import InstagramAdapter
from socialhood.security.crypto import TokenCipher, new_key
from socialhood.settings import AppEnv, Settings
from tests.support.instagram import GRAPH, fixture

SETTINGS = Settings(
    _env_file=None,
    app_env=AppEnv.TEST,
    database_url="postgresql+asyncpg://x/y",
    database_url_direct="postgresql://x/y",
    redis_url="redis://x",
)
V = f"{GRAPH}/{SETTINGS.ig_graph_version}"
IG = "17841400000000001"
CONTAINER = "17889455560051444"
MEDIA = "17920238422030506"
IMAGE_URL = "https://res.cloudinary.com/demo/image/upload/f_jpg,q_auto,w_1440,c_limit/a.jpg"
VIDEO_URL = "https://res.cloudinary.com/demo/video/upload/vc_h264,ac_aac,f_mp4/b.mp4"


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


def body(route: respx.Route) -> dict[str, object]:
    return json.loads(route.calls.last.request.content)  # type: ignore[no-any-return]


# ---------------------------------------------------------------- quota


@respx.mock
async def test_the_quota_comes_from_content_publishing_limit(adapter: InstagramAdapter) -> None:
    route = respx.get(f"{V}/{IG}/content_publishing_limit").respond(
        200, json=fixture("publishing_limit.json")
    )
    quota = await adapter.get_publishing_quota(account(adapter))
    assert quota == PublishingQuota(used=2, limit=100, window_s=86_400)
    assert quota.remaining == 98
    request = route.calls.last.request
    assert request.url.params["fields"] == "quota_usage,config"
    assert request.headers["authorization"] == "Bearer IGQVJlong"


@respx.mock
async def test_a_quota_without_its_config_falls_back_to_the_default_limit(
    adapter: InstagramAdapter,
) -> None:
    respx.get(f"{V}/{IG}/content_publishing_limit").respond(
        200, json={"data": [{"quota_usage": 100}]}
    )
    quota = await adapter.get_publishing_quota(account(adapter))
    assert (quota.used, quota.limit, quota.remaining) == (100, 100, 0)


# ---------------------------------------------------------------- containers


@respx.mock
async def test_an_image_container(adapter: InstagramAdapter) -> None:
    route = respx.post(f"{V}/{IG}/media").respond(200, json=fixture("container_created.json"))
    got = await adapter.create_image_container(
        account(adapter), image_url=IMAGE_URL, caption="Fresh bread #sourdough"
    )
    assert got == CONTAINER
    assert body(route) == {"image_url": IMAGE_URL, "caption": "Fresh bread #sourdough"}
    assert route.calls.last.request.headers["content-type"] == "application/json"


@respx.mock
async def test_an_empty_caption_is_left_out(adapter: InstagramAdapter) -> None:
    route = respx.post(f"{V}/{IG}/media").respond(200, json=fixture("container_created.json"))
    await adapter.create_image_container(account(adapter), image_url=IMAGE_URL, caption="")
    assert body(route) == {"image_url": IMAGE_URL}


@respx.mock
async def test_a_reel_container_is_shared_to_the_feed(adapter: InstagramAdapter) -> None:
    route = respx.post(f"{V}/{IG}/media").respond(200, json=fixture("container_created.json"))
    got = await adapter.create_reel_container(
        account(adapter), video_url=VIDEO_URL, caption="How we bake"
    )
    assert got == CONTAINER
    assert body(route) == {
        "media_type": "REELS",
        "video_url": VIDEO_URL,
        "share_to_feed": True,
        "caption": "How we bake",
    }


@pytest.mark.parametrize(
    ("media", "expected"),
    [
        (
            ContainerMedia(kind="image", url=IMAGE_URL),
            {"image_url": IMAGE_URL, "is_carousel_item": True},
        ),
        (
            ContainerMedia(kind="video", url=VIDEO_URL),
            {"media_type": "VIDEO", "video_url": VIDEO_URL, "is_carousel_item": True},
        ),
    ],
    ids=["image-child", "video-child"],
)
@respx.mock
async def test_carousel_items(
    adapter: InstagramAdapter, media: ContainerMedia, expected: dict[str, object]
) -> None:
    route = respx.post(f"{V}/{IG}/media").respond(200, json=fixture("container_created.json"))
    assert await adapter.create_carousel_item(account(adapter), media) == CONTAINER
    assert body(route) == expected


@respx.mock
async def test_a_carousel_container_lists_its_children_in_order(
    adapter: InstagramAdapter,
) -> None:
    route = respx.post(f"{V}/{IG}/media").respond(200, json={"id": "17900000000000009"})
    got = await adapter.create_carousel_container(
        account(adapter), children=["17800000000000002", "17800000000000001"], caption="Menu"
    )
    assert got == "17900000000000009"
    assert body(route) == {
        "media_type": "CAROUSEL",
        "children": "17800000000000002,17800000000000001",
        "caption": "Menu",
    }


@pytest.mark.parametrize("count", [1, 11])
async def test_a_carousel_needs_2_to_10_children(adapter: InstagramAdapter, count: int) -> None:
    with pytest.raises(PlatformError) as caught:
        await adapter.create_carousel_container(
            account(adapter), children=[f"1780000000000000{i}" for i in range(count)], caption=""
        )
    assert caught.value.code == "platform_rejected"


@respx.mock
async def test_a_refused_container_says_why(adapter: InstagramAdapter) -> None:
    respx.post(f"{V}/{IG}/media").respond(400, json=fixture("error_2207009_aspect_ratio.json"))
    with pytest.raises(PlatformError) as caught:
        await adapter.create_image_container(account(adapter), image_url=IMAGE_URL, caption="")
    assert caught.value.code == "platform_rejected"
    assert not caught.value.retryable
    assert "aspect ratio" in caught.value.message


@respx.mock
async def test_a_temporary_create_failure_is_retryable(adapter: InstagramAdapter) -> None:
    respx.post(f"{V}/{IG}/media").respond(
        400,
        json={"error": {"message": "Fatal", "code": -1, "error_subcode": 2207032}},
    )
    with pytest.raises(PlatformError) as caught:
        await adapter.create_image_container(account(adapter), image_url=IMAGE_URL, caption="")
    assert caught.value.code == "platform_unavailable"
    assert caught.value.retryable


# ---------------------------------------------------------------- status


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("container_status_finished.json", ContainerStatus(status_code="FINISHED")),
        (
            "container_status_in_progress.json",
            ContainerStatus(
                status_code="IN_PROGRESS", detail="In Progress: Media is still being processed."
            ),
        ),
        (
            "container_status_error.json",
            ContainerStatus(
                status_code="ERROR", detail="Instagram doesn't support this video format."
            ),
        ),
    ],
    ids=["finished", "in-progress", "error"],
)
@respx.mock
async def test_container_status(
    adapter: InstagramAdapter, name: str, expected: ContainerStatus
) -> None:
    route = respx.get(f"{V}/{CONTAINER}").respond(200, json=fixture(name))
    assert await adapter.get_container_status(account(adapter), CONTAINER) == expected
    assert route.calls.last.request.url.params["fields"] == "status_code,status"


@respx.mock
async def test_an_error_without_a_known_subcode_keeps_instagrams_text(
    adapter: InstagramAdapter,
) -> None:
    respx.get(f"{V}/{CONTAINER}").respond(
        200, json={"status_code": "ERROR", "status": "Error: Something unusual", "id": CONTAINER}
    )
    status = await adapter.get_container_status(account(adapter), CONTAINER)
    assert status == ContainerStatus(status_code="ERROR", detail="Error: Something unusual")


@respx.mock
async def test_an_unknown_status_code_keeps_polling(adapter: InstagramAdapter) -> None:
    respx.get(f"{V}/{CONTAINER}").respond(200, json={"status_code": "QUEUED", "id": CONTAINER})
    status = await adapter.get_container_status(account(adapter), CONTAINER)
    assert status.status_code == "IN_PROGRESS"


@pytest.mark.parametrize("code", ["EXPIRED", "PUBLISHED"])
@respx.mock
async def test_final_status_codes(adapter: InstagramAdapter, code: str) -> None:
    respx.get(f"{V}/{CONTAINER}").respond(200, json={"status_code": code, "id": CONTAINER})
    assert (await adapter.get_container_status(account(adapter), CONTAINER)).status_code == code


# ---------------------------------------------------------------- publish


@respx.mock
async def test_publish_returns_the_media_id(adapter: InstagramAdapter) -> None:
    route = respx.post(f"{V}/{IG}/media_publish").respond(200, json=fixture("media_publish.json"))
    assert await adapter.publish_container(account(adapter), CONTAINER) == MEDIA
    assert body(route) == {"creation_id": CONTAINER}


@pytest.mark.parametrize(
    "failure",
    [httpx.ReadTimeout("read"), httpx.RemoteProtocolError("disconnected")],
    ids=["read-timeout", "disconnected"],
)
@respx.mock
async def test_a_lost_publish_answer_is_delivery_unknown(
    adapter: InstagramAdapter, failure: Exception
) -> None:
    respx.post(f"{V}/{IG}/media_publish").mock(side_effect=failure)
    with pytest.raises(PlatformError) as caught:
        await adapter.publish_container(account(adapter), CONTAINER)
    assert caught.value.code == "delivery_unknown"
    assert not caught.value.retryable


@respx.mock
async def test_a_publish_that_never_left_is_retryable(adapter: InstagramAdapter) -> None:
    respx.post(f"{V}/{IG}/media_publish").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(PlatformError) as caught:
        await adapter.publish_container(account(adapter), CONTAINER)
    assert caught.value.code == "platform_unavailable"


@respx.mock
async def test_an_answer_without_an_id_is_delivery_unknown(adapter: InstagramAdapter) -> None:
    respx.post(f"{V}/{IG}/media_publish").respond(200, json={})
    with pytest.raises(PlatformError) as caught:
        await adapter.publish_container(account(adapter), CONTAINER)
    assert caught.value.code == "delivery_unknown"


@respx.mock
async def test_the_daily_limit_is_a_refusal_with_its_reason(adapter: InstagramAdapter) -> None:
    respx.post(f"{V}/{IG}/media_publish").respond(
        400, json=fixture("error_2207042_publishing_limit.json")
    )
    with pytest.raises(PlatformError) as caught:
        await adapter.publish_container(account(adapter), CONTAINER)
    assert caught.value.code == "platform_rejected"
    assert caught.value.message == "Instagram's daily publishing limit reached"


@respx.mock
async def test_not_ready_to_publish_is_retryable(adapter: InstagramAdapter) -> None:
    respx.post(f"{V}/{IG}/media_publish").respond(400, json=fixture("error_2207027_not_ready.json"))
    with pytest.raises(PlatformError) as caught:
        await adapter.publish_container(account(adapter), CONTAINER)
    assert caught.value.code == "platform_unavailable"
    assert caught.value.retryable


# ---------------------------------------------------------------- read back and lookup


@respx.mock
async def test_the_published_post_is_read_back_with_its_permalink(
    adapter: InstagramAdapter,
) -> None:
    route = respx.get(f"{V}/{MEDIA}").respond(200, json=fixture("published_media.json"))
    media = await adapter.get_published_media(account(adapter), MEDIA)
    assert media is not None
    assert media.platform_media_id == MEDIA
    assert media.permalink == "https://www.instagram.com/p/C9new/"
    assert media.media_type == "carousel"
    assert "permalink" in route.calls.last.request.url.params["fields"].split(",")


@respx.mock
async def test_a_post_not_visible_yet_reads_back_as_none(adapter: InstagramAdapter) -> None:
    respx.get(f"{V}/{MEDIA}").respond(400, json=fixture("error_100_33_missing_media.json"))
    assert await adapter.get_published_media(account(adapter), MEDIA) is None


@respx.mock
async def test_a_read_back_outage_still_raises(adapter: InstagramAdapter) -> None:
    respx.get(f"{V}/{MEDIA}").respond(500, json={"error": {"message": "x", "code": 2}})
    with pytest.raises(PlatformError) as caught:
        await adapter.get_published_media(account(adapter), MEDIA)
    assert caught.value.retryable


def graph_item(media_id: str, caption: str, timestamp: str) -> dict[str, object]:
    return {
        "id": media_id,
        "caption": caption,
        "media_type": "IMAGE",
        "media_product_type": "FEED",
        "permalink": f"https://www.instagram.com/p/{media_id}/",
        "timestamp": timestamp,
    }


@respx.mock
async def test_a_lost_answer_is_found_by_caption_and_time(adapter: InstagramAdapter) -> None:
    route = respx.get(f"{V}/me/media").respond(
        200,
        json={
            "data": [
                graph_item("18100000000000009", "Something else", "2026-09-29T10:01:00+0000"),
                graph_item(
                    "18100000000000008", "Fresh  bread\n#sourdough", "2026-09-29T10:00:30+0000"
                ),
                graph_item(
                    "18100000000000007", "Fresh bread #sourdough", "2026-09-20T10:00:00+0000"
                ),
            ]
        },
    )
    found = await adapter.find_published_media(
        account(adapter),
        CONTAINER,
        caption="Fresh bread #sourdough",
        published_after=datetime(2026, 9, 29, 9, 58, tzinfo=UTC),
    )
    assert found is not None
    assert found.platform_media_id == "18100000000000008"  # last week's same caption is too old
    assert "permalink" in route.calls.last.request.url.params["fields"]


@respx.mock
async def test_no_match_is_none(adapter: InstagramAdapter) -> None:
    respx.get(f"{V}/me/media").respond(200, json=fixture("media_list.json"))
    found = await adapter.find_published_media(
        account(adapter),
        CONTAINER,
        caption="Not posted",
        published_after=datetime(2026, 9, 1, tzinfo=UTC),
    )
    assert found is None


# ---------------------------------------------------------------- first comment


@respx.mock
async def test_the_first_comment(adapter: InstagramAdapter) -> None:
    route = respx.post(f"{V}/{MEDIA}/comments").respond(200, json=fixture("comment_created.json"))
    got = await adapter.post_comment(account(adapter), MEDIA, "#bakery #sourdough")
    assert got == "17858893269000001"
    assert body(route) == {"message": "#bakery #sourdough"}


@respx.mock
async def test_a_lost_comment_answer_is_delivery_unknown(adapter: InstagramAdapter) -> None:
    respx.post(f"{V}/{MEDIA}/comments").mock(side_effect=httpx.ReadTimeout("read"))
    with pytest.raises(PlatformError) as caught:
        await adapter.post_comment(account(adapter), MEDIA, "#bakery")
    assert caught.value.code == "delivery_unknown"


# ---------------------------------------------------------------- ids in paths


@pytest.mark.parametrize("bad", ["../me/messages", "1789?fields=x", ""])
async def test_only_instagram_ids_reach_the_graph_path(adapter: InstagramAdapter, bad: str) -> None:
    acct = account(adapter)
    for call in (
        adapter.get_container_status(acct, bad),
        adapter.publish_container(acct, bad),
        adapter.get_published_media(acct, bad),
        adapter.post_comment(acct, bad, "hi"),
    ):
        with pytest.raises(PlatformError):
            await call
