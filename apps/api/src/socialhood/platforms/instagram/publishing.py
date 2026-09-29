"""Instagram content publishing (T7.2; TR-PL-01 and the Instagram table, FR-PUB-05, FR-PUB-11).
The adapter's publishing methods delegate here; payload shapes belong in ``parse.py``.

Calls (host graph.instagram.com, ``{ig}`` the account's professional id; verify at build time):
- quota: ``GET /{ig}/content_publishing_limit?fields=quota_usage,config``
- image: ``POST /{ig}/media`` image_url, caption
- Reel: ``POST /{ig}/media`` media_type=REELS, video_url, caption, share_to_feed=true
- carousel child: ``POST /{ig}/media`` is_carousel_item=true, image_url (or media_type=VIDEO,
  video_url)
- carousel: ``POST /{ig}/media`` media_type=CAROUSEL, children=id1,id2,…, caption
- status: ``GET /{container_id}?fields=status_code,status``
- publish: ``POST /{ig}/media_publish`` creation_id → the media id
- permalink: ``GET /{media_id}?fields=…,permalink``
- first comment: ``POST /{media_id}/comments`` message

Creating containers may be retried. ``publish_container`` and ``post_comment`` are writes: map
failures with ``platforms.outcome.for_write`` so a lost answer is ``delivery_unknown``. Error
2207042 (daily limit) is already ``platform_rejected`` and 2207008 retryable in
``platforms.errors``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import (
    ContainerMedia,
    ContainerStatus,
    PlatformMedia,
    PublishingQuota,
)
from socialhood.platforms.http import PlatformHttp


async def publishing_quota(
    http: PlatformHttp, graph: Callable[[str], str], token: str, acct: SocialAccount
) -> PublishingQuota:
    raise NotImplementedError("T7.2")


async def create_image_container(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    *,
    image_url: str,
    caption: str,
) -> str:
    raise NotImplementedError("T7.2")


async def create_reel_container(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    *,
    video_url: str,
    caption: str,
    share_to_feed: bool,
) -> str:
    raise NotImplementedError("T7.2")


async def create_carousel_item(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    media: ContainerMedia,
) -> str:
    raise NotImplementedError("T7.2")


async def create_carousel_container(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    *,
    children: Sequence[str],
    caption: str,
) -> str:
    raise NotImplementedError("T7.2")


async def container_status(
    http: PlatformHttp, graph: Callable[[str], str], token: str, container_ref: str
) -> ContainerStatus:
    raise NotImplementedError("T7.2")


async def publish_container(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    container_ref: str,
) -> str:
    raise NotImplementedError("T7.2")


async def published_media(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str
) -> PlatformMedia | None:
    raise NotImplementedError("T7.2")


async def find_published_media(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    container_ref: str,
    *,
    caption: str,
    published_after: datetime,
) -> PlatformMedia | None:
    raise NotImplementedError("T7.2")


async def post_comment(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str, text: str
) -> str | None:
    raise NotImplementedError("T7.2")
