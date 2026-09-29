"""Instagram content publishing (T7.2; TR-PL-01 and the Instagram table, FR-PUB-05, FR-PUB-11).
The adapter's publishing methods delegate here; payload shapes are parsed in ``parse.py``.

Calls (host graph.instagram.com, ``{ig}`` the account's professional id), checked against Meta's
Content Publishing guide and the IG User Media, IG Container, Content Publishing Limit and error
code references on 2026-09-29. Writes send a JSON body, as the guide's examples do; ``children``
is a comma-separated string, not a JSON array.
- quota: ``GET /{ig}/content_publishing_limit?fields=quota_usage,config`` → ``{"data":
  [{"quota_usage": n, "config": {"quota_total": 100, "quota_duration": 86400}}]}``
- image: ``POST /{ig}/media`` {image_url, caption} (JPEG only; our delivery URL converts)
- Reel: ``POST /{ig}/media`` {media_type: REELS, video_url, caption, share_to_feed}
- carousel child: ``POST /{ig}/media`` {image_url, is_carousel_item: true} or {media_type: VIDEO,
  video_url, is_carousel_item: true}; Reels can't be carousel items
- carousel: ``POST /{ig}/media`` {media_type: CAROUSEL, children: "id1,id2,…", caption}. Meta
  refuses a carousel whose children are still processing, so the publish job creates it only once
  every child is FINISHED.
- status: ``GET /{container_id}?fields=status_code,status`` (IN_PROGRESS, FINISHED, ERROR,
  EXPIRED, PUBLISHED; ``status`` carries the error subcode of an ERROR). Meta asks for at most one
  status call a minute, for no more than 5 minutes (videos take longer; the job goes on to 30).
- publish: ``POST /{ig}/media_publish`` {creation_id} → ``{"id": media id}``
- read back: ``GET /{media_id}?fields=…,permalink`` (the fields sync stores)
- lost answer: the account's recent posts (``GET /me/media``) matched on caption and time; an IG
  Container has no field naming the post it became
- first comment: ``POST /{media_id}/comments`` {message}

Creating containers may be retried (an unpublished container expires after 24 h).
``publish_container`` and ``post_comment`` are writes: failures go through
``platforms.outcome.for_write`` so a lost answer is ``delivery_unknown``. Error 2207042 (daily
limit) is already ``platform_rejected`` and 2207008 retryable in ``platforms.errors``; the other
publishing subcodes Meta calls temporary (2207001, 2207003, 2207027, 2207032, 2207053) are made
retryable here, and every known subcode gets a readable reason (FR-PUB-06).

Unverified until a real account publishes (T0.9, docs/verification.md): the quota answer's shape
under Instagram Login and whether ``since`` is needed; the exact ``status`` text of an ERROR;
JSON bodies for ``/comments``; the caption normalisation Instagram applies (the lost-answer match
compares captions with whitespace collapsed).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from socialhood.models.connections import SocialAccount
from socialhood.models.publishing import (
    CAROUSEL_MAX_ASSETS,
    CAROUSEL_MIN_ASSETS,
    DEFAULT_PUBLISHING_LIMIT,
)
from socialhood.platforms.base import (
    ContainerMedia,
    ContainerStatus,
    PlatformMedia,
    PublishingQuota,
)
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram import parse
from socialhood.platforms.instagram.reads import GRAPH_ID, MEDIA_FIELDS, list_media
from socialhood.platforms.outcome import DELIVERY_UNKNOWN, for_write

QUOTA_FIELDS = "quota_usage,config"
STATUS_FIELDS = "status_code,status"
# Recent posts searched for the post a lost publish answer made: the account can't have published
# more than a handful since the claim.
FIND_LIMIT = 25

# Publishing error subcodes (Meta's Instagram error-code reference, checked 2026-09-29) that Meta
# says to retry, or to retry with a new container.
TRANSIENT_SUBCODES = frozenset({2207001, 2207003, 2207008, 2207027, 2207032, 2207053})
# The reason a failed target shows (FR-PUB-06), by subcode.
REASONS: dict[int, str] = {
    2207001: "Instagram had a server error.",
    2207003: "Instagram took too long to download the media.",
    2207004: "The image is too large for Instagram (the limit is 8 MB).",
    2207005: "Instagram doesn't support this image format.",
    2207006: "Instagram couldn't find the uploaded media.",
    2207008: "Instagram's upload session expired.",
    2207009: "Instagram doesn't accept this image's aspect ratio (4:5 to 1.91:1).",
    2207010: "The caption is longer than 2,200 characters.",
    2207020: "The upload expired on Instagram.",
    2207023: "Instagram didn't recognise the media type.",
    2207026: "Instagram doesn't support this video format.",
    2207027: "The media wasn't ready to publish yet.",
    2207028: "A carousel needs 2 to 10 photos or videos.",
    2207032: "Instagram couldn't create the post.",
    2207040: "The caption tags more than 20 accounts.",
    2207042: "Instagram's daily publishing limit reached",
    2207050: "The Instagram account is restricted. Check the Instagram app.",
    2207051: "Instagram blocked this post to protect its community.",
    2207052: "Instagram couldn't fetch the media from its link.",
    2207053: "Instagram had an unknown upload error.",
    2207057: "The video's cover frame is outside the video.",
}
_SUBCODE = re.compile(r"\b(22070\d\d)\b")
_SPACES = re.compile(r"\s+")


# ---------------------------------------------------------------- errors


def _subcode(error: PlatformError) -> int | None:
    """The Graph error subcode (``platform_code`` is ``"code/subcode"``)."""
    _, _, sub = (error.platform_code or "").partition("/")
    return int(sub) if sub.isdigit() else None


def _refine(error: PlatformError) -> PlatformError:
    """A publishing error with its readable reason; Meta's temporary subcodes become retryable."""
    sub = _subcode(error)
    if sub is None or sub not in REASONS:
        return error
    code = "platform_unavailable" if sub in TRANSIENT_SUBCODES else error.code
    refined = PlatformError(
        code,
        platform_code=error.platform_code,
        message=REASONS[sub],
        retry_after_s=error.retry_after_s,
    )
    refined.__cause__ = error.__cause__
    return refined


def status_reason(detail: str | None) -> str | None:
    """The reason for a container ERROR: the known subcode in Instagram's ``status``, else its
    text."""
    if not detail:
        return None
    match = _SUBCODE.search(detail)
    if match and int(match.group(1)) in REASONS:
        return REASONS[int(match.group(1))]
    return detail


def _id(ref: str, what: str) -> str:
    """A platform id placed in a Graph path; anything else could change the path."""
    if not GRAPH_ID.match(ref):
        raise PlatformError("platform_rejected", message=f"Not an Instagram {what} id")
    return ref


def _ig(acct: SocialAccount) -> str:
    return _id(acct.platform_account_id, "account")


# ---------------------------------------------------------------- calls


async def _create(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    body: dict[str, Any],
    *,
    endpoint: str,
) -> str:
    """``POST /{ig}/media``: a container. Safe to retry, so failures keep their mapped code."""
    try:
        answer = await http.request(
            "POST", graph(f"{_ig(acct)}/media"), endpoint=endpoint, token=token, json=body
        )
    except PlatformError as error:
        raise _refine(error) from error.__cause__
    container_id = parse.created_id(answer)
    if not container_id:
        raise PlatformError("platform_unavailable", message="Instagram returned no container id")
    return container_id


def _captioned(body: dict[str, Any], caption: str) -> dict[str, Any]:
    return {**body, "caption": caption} if caption else body


async def publishing_quota(
    http: PlatformHttp, graph: Callable[[str], str], token: str, acct: SocialAccount
) -> PublishingQuota:
    """Posts published through the API in the rolling 24 h against the account's limit."""
    body = await http.request(
        "GET",
        graph(f"{_ig(acct)}/content_publishing_limit"),
        endpoint="content_publishing_limit",
        token=token,
        params={"fields": QUOTA_FIELDS},
    )
    return parse.publishing_quota(body, default_limit=DEFAULT_PUBLISHING_LIMIT)


async def create_image_container(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    *,
    image_url: str,
    caption: str,
) -> str:
    return await _create(
        http,
        graph,
        token,
        acct,
        _captioned({"image_url": image_url}, caption),
        endpoint="media.create.image",
    )


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
    body = {"media_type": "REELS", "video_url": video_url, "share_to_feed": share_to_feed}
    return await _create(
        http, graph, token, acct, _captioned(body, caption), endpoint="media.create.reel"
    )


async def create_carousel_item(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    media: ContainerMedia,
) -> str:
    body: dict[str, Any]
    if media.kind == "video":
        body = {"media_type": "VIDEO", "video_url": media.url, "is_carousel_item": True}
    else:
        body = {"image_url": media.url, "is_carousel_item": True}
    return await _create(http, graph, token, acct, body, endpoint="media.create.carousel_item")


async def create_carousel_container(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    *,
    children: Sequence[str],
    caption: str,
) -> str:
    if not CAROUSEL_MIN_ASSETS <= len(children) <= CAROUSEL_MAX_ASSETS:
        raise PlatformError("platform_rejected", message=REASONS[2207028])
    body = {
        "media_type": "CAROUSEL",
        "children": ",".join(_id(child, "container") for child in children),
    }
    return await _create(
        http, graph, token, acct, _captioned(body, caption), endpoint="media.create.carousel"
    )


async def container_status(
    http: PlatformHttp, graph: Callable[[str], str], token: str, container_ref: str
) -> ContainerStatus:
    body = await http.request(
        "GET",
        graph(_id(container_ref, "container")),
        endpoint="container.status",
        token=token,
        params={"fields": STATUS_FIELDS},
    )
    status = parse.container_status(body)
    if status.status_code == "ERROR":
        return ContainerStatus(status_code="ERROR", detail=status_reason(status.detail))
    return status


async def publish_container(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    container_ref: str,
) -> str:
    """``media_publish``: a write. A failure after the request went out is delivery_unknown."""
    try:
        body = await http.request(
            "POST",
            graph(f"{_ig(acct)}/media_publish"),
            endpoint="media_publish",
            token=token,
            json={"creation_id": _id(container_ref, "container")},
        )
    except PlatformError as error:
        raise for_write(_refine(error)) from error.__cause__
    media_id = parse.created_id(body)
    if not media_id:  # it answered, so it may well have published
        raise PlatformError(
            DELIVERY_UNKNOWN, retryable=False, message="Instagram did not return the post's id"
        )
    return media_id


async def published_media(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str
) -> PlatformMedia | None:
    """The new post's fields, permalink included. A refusal (not visible yet) is None; retryable
    errors and a dead token raise."""
    url = graph(_id(media_ref, "media"))
    try:
        body = await http.request(
            "GET",
            url,
            endpoint="media.published",
            token=token,
            params={"fields": MEDIA_FIELDS},
        )
    except PlatformError as error:
        if error.retryable or error.code == "account_needs_reconnect":
            raise
        return None
    return parse.media_item(body) if isinstance(body, dict) else None


def normalized_caption(caption: str | None) -> str:
    """Captions compared for the lost-answer match: whitespace collapsed, ends trimmed."""
    return _SPACES.sub(" ", caption or "").strip()


def match_published(
    posts: Sequence[PlatformMedia], *, caption: str, published_after: datetime
) -> PlatformMedia | None:
    """The earliest post at or after ``published_after`` with this caption (stories aside)."""
    wanted = normalized_caption(caption)
    candidates = [
        post
        for post in posts
        if post.media_type != "story"
        and post.posted_at >= published_after
        and normalized_caption(post.caption) == wanted
    ]
    return min(candidates, key=lambda post: post.posted_at, default=None)


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
    _id(container_ref, "container")
    posts = await list_media(http, graph, token, limit=FIND_LIMIT)
    return match_published(posts, caption=caption, published_after=published_after)


async def post_comment(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str, text: str
) -> str | None:
    """The account's own comment on its post (the first comment, FR-PUB-11): a write."""
    if not text.strip():
        raise PlatformError("platform_rejected", message="A comment needs text")
    try:
        body = await http.request(
            "POST",
            graph(f"{_id(media_ref, 'media')}/comments"),
            endpoint="media.comments.create",
            token=token,
            json={"message": text},
        )
    except PlatformError as error:
        raise for_write(error) from error.__cause__
    return parse.created_id(body)
