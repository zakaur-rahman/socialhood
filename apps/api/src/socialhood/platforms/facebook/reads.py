"""Facebook Page reads: posts, one post's counts, the Page's followers, a person's profile and
Messenger conversations for the backfill on connect (GR-29; FR-CON-01, F-12). The adapter's
``list_media``, ``get_media``, ``get_media_counts``, ``fetch_contact_profile`` and
``list_threads`` delegate here.

Posts are the Page's own (``/me/published_posts``), not visitors' posts. A post's likes are its
reactions. Unverified until a real Page confirms them (docs/verification.md): the post fields,
that ``attachments`` tells photo posts from video and album posts, the Conversations API fields
with ``platform=messenger``, and the profile fields a person has agreed to share.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Literal

from socialhood.models.connections import SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import ContactProfile, MediaCounts, PlatformMedia, PlatformThread
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram import parse as instagram
from socialhood.platforms.instagram.reads import (
    CONVERSATIONS_PACE_S,
    GRAPH_ID,
    THREAD_FIELDS,
    THREAD_LIST_FIELDS,
    _items,
)

log = get_logger("socialhood.platforms")

POST_FIELDS = (
    "id,message,created_time,full_picture,permalink_url,attachments{type,media_type},"
    "comments.summary(true).limit(0),reactions.summary(true).limit(0)"
)
COUNT_FIELDS = "comments.summary(true).limit(0),reactions.summary(true).limit(0)"
PROFILE_FIELDS = "name,profile_pic"
VIDEO_TYPES = ("video", "video_inline", "video_autoplay", "animated_image_video")
NOT_FOUND = frozenset({"100", "100/33"})


def _total(raw: object) -> int | None:
    summary = raw.get("summary") if isinstance(raw, dict) else None
    total = summary.get("total_count") if isinstance(summary, dict) else None
    return total if isinstance(total, int) and not isinstance(total, bool) else None


def media_item(raw: dict[str, Any]) -> PlatformMedia | None:
    """One Page post; None when it lacks an id or a time."""
    media_id = instagram._str(raw.get("id"))
    posted_at = instagram.graph_time(raw.get("created_time"))
    if not media_id or posted_at is None:
        return None
    attachments = instagram._data(raw.get("attachments"))
    kinds = {str(a.get("media_type") or a.get("type") or "").lower() for a in attachments}
    kind: Literal["image", "video", "carousel"] = "image"
    if "album" in kinds or len(attachments) > 1:
        kind = "carousel"
    elif any(k in VIDEO_TYPES for k in kinds):
        kind = "video"
    picture = instagram._str(raw.get("full_picture"))
    return PlatformMedia(
        platform_media_id=media_id,
        media_type=kind,
        caption=instagram._str(raw.get("message")),
        media_url=picture,
        thumbnail_url=picture,
        permalink=instagram._str(raw.get("permalink_url")),
        posted_at=posted_at,
        like_count=_total(raw.get("reactions")),
        comments_count=_total(raw.get("comments")),
    )


async def list_media(
    http: PlatformHttp, graph: Callable[[str], str], token: str, *, limit: int
) -> list[PlatformMedia]:
    body = await http.request(
        "GET",
        graph("me/published_posts"),
        endpoint="me.published_posts",
        token=token,
        params={"fields": POST_FIELDS, "limit": limit},
    )
    return [m for m in map(media_item, _items(body)) if m is not None][:limit]


def _post_id(media_ref: str) -> str:
    """A platform id placed in a Graph path; anything else could change the path."""
    if not GRAPH_ID.match(media_ref):
        raise PlatformError("platform_rejected", message="Not a Facebook post id")
    return media_ref


async def get_media(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str
) -> PlatformMedia | None:
    """One post (``GET /{post_id}``), for a comment on a post not synced yet (F-12)."""
    body = await http.request(
        "GET",
        graph(_post_id(media_ref)),
        endpoint="post",
        token=token,
        params={"fields": POST_FIELDS},
    )
    return media_item(body) if isinstance(body, dict) else None


async def media_counts(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str
) -> MediaCounts | None:
    """A post's live comment and reaction counts; None when the post no longer exists."""
    try:
        body = await http.request(
            "GET",
            graph(_post_id(media_ref)),
            endpoint="post.counts",
            token=token,
            params={"fields": COUNT_FIELDS},
        )
    except PlatformError as error:
        if error.platform_code in NOT_FOUND:
            return None
        raise
    if not isinstance(body, dict):
        return None
    return MediaCounts(
        like_count=_total(body.get("reactions")), comments_count=_total(body.get("comments"))
    )


async def followers(http: PlatformHttp, graph: Callable[[str], str], token: str) -> int | None:
    """The Page's followers now (``followers_count``, else the likes in ``fan_count``)."""
    body = await http.request(
        "GET",
        graph("me"),
        endpoint="me.followers",
        token=token,
        params={"fields": "followers_count,fan_count"},
    )
    if not isinstance(body, dict):
        return None
    for key in ("followers_count", "fan_count"):
        value = body.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


async def contact_profile(
    http: PlatformHttp, graph: Callable[[str], str], token: str, platform_user_id: str
) -> ContactProfile | None:
    """Messenger's User Profile API: the name and picture of someone who messaged the Page."""
    if not GRAPH_ID.match(platform_user_id):
        raise PlatformError("platform_rejected", message="Not a Facebook user id")
    body = await http.request(
        "GET",
        graph(platform_user_id),
        endpoint="user_profile",
        token=token,
        params={"fields": PROFILE_FIELDS},
    )
    if not isinstance(body, dict):
        return None
    return ContactProfile(
        name=body.get("name"),
        username=None,  # Messenger people have no handle
        profile_picture_url=body.get("profile_pic"),
    )


async def list_threads(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    *,
    limit: int,
) -> list[PlatformThread]:
    """Recent Messenger threads with their latest messages. A thread Meta refuses is skipped; a
    retryable failure fails the whole call."""
    body = await http.request(
        "GET",
        graph("me/conversations"),
        endpoint="me.conversations",
        token=token,
        params={"platform": "messenger", "fields": THREAD_LIST_FIELDS, "limit": limit},
    )
    threads: list[PlatformThread] = []
    for conversation in _items(body)[:limit]:
        conversation_id = str(conversation.get("id") or "")
        if not GRAPH_ID.match(conversation_id):
            continue
        await asyncio.sleep(CONVERSATIONS_PACE_S)
        try:
            detail = await http.request(
                "GET",
                graph(conversation_id),
                endpoint="conversation.messages",
                token=token,
                params={"fields": THREAD_FIELDS},
            )
        except PlatformError as error:
            if error.retryable:
                raise
            log.warning("backfill_thread_skipped", error_code=error.code)
            continue
        parsed = instagram.thread(
            conversation,
            _items(detail, "messages"),
            account_ref=acct.platform_account_id,
            own_ids=frozenset({acct.platform_account_id}),
            own_username=None,
        )
        if parsed is not None:
            threads.append(parsed)
    return threads
