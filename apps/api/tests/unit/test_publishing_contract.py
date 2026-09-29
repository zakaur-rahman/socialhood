"""The P7 contract's shared names agree with each other (FR-PUB-01…14, F-13, TR-PL-01, TR-PL-11):
the API's statuses and formats are the stored ones, every adapter has the publishing methods with
the protocol's parameters (WhatsApp refusing them), the poll schedule adds up to Instagram's
30 minutes, and every P7 route is in the API."""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from typing import Any, get_args

import pytest

from socialhood.main import create_app
from socialhood.models.connections import SocialAccount
from socialhood.models.publishing import (
    POLL_FAST_COUNT,
    POLL_FAST_DELAY,
    POLL_MAX,
    POLL_SLOW_DELAY,
    PostFormat,
    ScheduledPostStatus,
    TargetStatus,
)
from socialhood.platforms.base import ContainerMedia, PlatformAdapter, PublishingQuota
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.instagram.adapter import InstagramAdapter
from socialhood.platforms.sandbox.adapter import SandboxAdapter
from socialhood.platforms.whatsapp.adapter import WhatsAppAdapter
from socialhood.schemas.publishing import (
    CHECKLIST_KEYS,
    ChecklistKey,
    PostFormatName,
    ScheduledPostStatusName,
    TargetStatusName,
)

PUBLISHING_METHODS = (
    "get_publishing_quota",
    "create_image_container",
    "create_reel_container",
    "create_carousel_item",
    "create_carousel_container",
    "get_container_status",
    "publish_container",
    "get_published_media",
    "find_published_media",
    "post_comment",
)

# operation id -> (method, path): §2.15's publishing rows.
P7_ROUTES = {
    "list_scheduled_posts": ("get", "/v1/w/{wid}/scheduled-posts"),
    "create_scheduled_post": ("post", "/v1/w/{wid}/scheduled-posts"),
    "get_scheduled_post": ("get", "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}"),
    "replace_scheduled_post": ("put", "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}"),
    "delete_scheduled_post": ("delete", "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}"),
    "schedule_post": ("post", "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/schedule"),
    "unschedule_post": ("post", "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/unschedule"),
    "publish_post_now": ("post", "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/publish-now"),
    "reschedule_post": ("post", "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/reschedule"),
    "queue_post": ("post", "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/queue"),
    "duplicate_scheduled_post": (
        "post",
        "/v1/w/{wid}/scheduled-posts/{scheduled_post_id}/duplicate",
    ),
    "bulk_update_scheduled_posts": ("post", "/v1/w/{wid}/scheduled-posts/bulk"),
    "get_calendar": ("get", "/v1/w/{wid}/calendar"),
    "get_posting_slots": ("get", "/v1/w/{wid}/social-accounts/{account_id}/posting-slots"),
    "replace_posting_slots": ("put", "/v1/w/{wid}/social-accounts/{account_id}/posting-slots"),
    "list_hashtag_groups": ("get", "/v1/w/{wid}/hashtag-groups"),
    "create_hashtag_group": ("post", "/v1/w/{wid}/hashtag-groups"),
    "update_hashtag_group": ("patch", "/v1/w/{wid}/hashtag-groups/{hashtag_group_id}"),
    "delete_hashtag_group": ("delete", "/v1/w/{wid}/hashtag-groups/{hashtag_group_id}"),
    "list_media_assets": ("get", "/v1/w/{wid}/media-assets"),
    "generate_caption": ("post", "/v1/w/{wid}/ai/caption"),
    "suggest_hashtags": ("post", "/v1/w/{wid}/ai/hashtags"),
}


def test_api_statuses_and_formats_are_the_stored_ones() -> None:
    assert set(get_args(ScheduledPostStatusName)) == set(ScheduledPostStatus)
    assert set(get_args(PostFormatName)) == set(PostFormat)
    assert set(get_args(TargetStatusName)) == set(TargetStatus)
    assert get_args(ChecklistKey) == CHECKLIST_KEYS


def test_polls_cover_thirty_minutes() -> None:
    total = POLL_FAST_COUNT * POLL_FAST_DELAY + (POLL_MAX - POLL_FAST_COUNT) * POLL_SLOW_DELAY
    assert total == timedelta(minutes=30)


def test_quota_remaining_never_goes_below_zero() -> None:
    assert PublishingQuota(used=40, limit=100).remaining == 60
    assert PublishingQuota(used=120, limit=100).remaining == 0


def _parameters(function: Any) -> list[tuple[str, Any, Any]]:
    return [
        (p.name, p.kind, p.default)
        for p in inspect.signature(function).parameters.values()
        if p.name != "self"
    ]


@pytest.mark.parametrize("adapter", [InstagramAdapter, SandboxAdapter, WhatsAppAdapter])
@pytest.mark.parametrize("method", PUBLISHING_METHODS)
def test_adapters_take_the_protocols_parameters(adapter: type, method: str) -> None:
    assert _parameters(getattr(adapter, method)) == _parameters(getattr(PlatformAdapter, method))


ARGS: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {
    "get_publishing_quota": ((), {}),
    "create_image_container": ((), {"image_url": "https://x/i.jpg", "caption": ""}),
    "create_reel_container": ((), {"video_url": "https://x/v.mp4", "caption": ""}),
    "create_carousel_item": ((ContainerMedia(kind="image", url="https://x/i.jpg"),), {}),
    "create_carousel_container": ((), {"children": ["1", "2"], "caption": ""}),
    "get_container_status": (("1",), {}),
    "publish_container": (("1",), {}),
    "get_published_media": (("1",), {}),
    "find_published_media": (
        ("1",),
        {"caption": "", "published_after": datetime(2026, 9, 29)},
    ),
    "post_comment": (("1", "#summer"), {}),
}


@pytest.mark.parametrize("method", PUBLISHING_METHODS)
async def test_whatsapp_numbers_cannot_publish(method: str) -> None:
    adapter = WhatsAppAdapter.__new__(WhatsAppAdapter)
    acct = SocialAccount(platform="whatsapp", platform_account_id="1")
    args, kwargs = ARGS[method]
    with pytest.raises(PlatformError) as caught:
        await getattr(adapter, method)(acct, *args, **kwargs)
    assert caught.value.code == "capability_unavailable"


def test_every_p7_route_is_in_the_api(api_settings: Any) -> None:
    openapi = create_app(api_settings).openapi()
    found = {
        operation["operationId"]: (method, path)
        for path, operations in openapi["paths"].items()
        for method, operation in operations.items()
        if operation.get("operationId") in P7_ROUTES
    }
    assert found == P7_ROUTES
