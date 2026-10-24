"""Facebook Page publishing (GR-30; FR-PUB-05, F-13). The adapter's publishing methods delegate
here. Our own scheduler decides when to publish (not Meta's ``scheduled_publish_time``, C-115), so
every call below publishes at once.

Facebook has no containers, but the publish jobs are built on them, so a container here is a
*reference* to what was uploaded unpublished, and ``publish_container`` posts it:
- ``photo:{id}``: ``POST /me/photos`` {url, caption, published: false} → ``{"id": photo id}``.
  Single photo and children of a multi-photo post alike. Photos are ready at once.
- ``photos:{id1,id2,…}``: no call; the parent of 2 to 10 unpublished photos.
- ``video:{id}``: ``POST /me/videos`` {file_url, description, published: false} → ``{"id": video
  id}``. The video processes on Facebook: ``GET /{id}?fields=status`` →
  ``status.video_status`` (``ready``, ``processing``, ``uploading``, ``error``, ``expired``) is
  polled like Instagram's status.
- ``text:post``: no call; a post with only text (and a link, when the text has one).
- publish: a photo or photos: ``POST /me/feed`` {message, attached_media: [{media_fbid}, …]} →
  ``{"id": "{page}_{post}"}``; a video: ``POST /{id}`` {published: true} → the video id; text:
  ``POST /me/feed`` {message, link?}.
- read back: a post id (it has ``_``) with the Page post fields, a video id with video fields.
- lost answer: the Page's recent posts (``/me/published_posts``) matched on caption and time.
- first comment: ``POST /{id}/comments`` {message}.

Creating references may be retried (an unpublished photo or video is cleaned up by Facebook).
``publish_container`` and ``post_comment`` are writes: failures go through
``platforms.outcome.for_write`` so a lost answer is ``delivery_unknown``.

Page Stories (``/photo_stories``, ``/video_stories``) are not built: they need their own two step
upload and Page Stories have no read API we could list them with (C-115).

Unverified until a real Page publishes (docs/verification.md, C-115): JSON bodies on these edges
(Meta's examples are form encoded, and ``attached_media`` is documented as a list of JSON strings);
``file_url`` on ``graph.facebook.com`` rather than ``graph-video.facebook.com``; publishing an
unpublished video with ``published: true``; the ``status.video_status`` values; the error codes
below; the ``link`` field's preview behaviour; the permission ``pages_manage_posts``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from socialhood.platforms.base import ContainerMedia, ContainerStatus, PlatformMedia
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.facebook import reads
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram import parse as instagram
from socialhood.platforms.instagram.publishing import match_published
from socialhood.platforms.instagram.reads import GRAPH_ID
from socialhood.platforms.outcome import DELIVERY_UNKNOWN, for_write

PHOTOS_MIN = 2
PHOTOS_MAX = 10
VIDEO_FIELDS = "id,description,created_time,permalink_url,picture"
STATUS_FIELDS = "status"
FIND_LIMIT = 25
URL = re.compile(r"https?://[^\s<>\"']+")

# Facebook error codes (Graph API error reference) with a plain reason. Unknown codes keep the
# generic reason from platforms.errors.
REASONS: dict[int, str] = {
    200: "The Page didn't give Social Hood permission to publish. Reconnect it.",
    324: "Facebook couldn't read the photo or video.",
    368: "Facebook has temporarily blocked this Page from posting.",
    506: "Facebook refused this as a duplicate post. Change the text and try again.",
}


def _code(error: PlatformError) -> int | None:
    head, _, _ = (error.platform_code or "").partition("/")
    return int(head) if head.isdigit() else None


def _refine(error: PlatformError) -> PlatformError:
    code = _code(error)
    if code is None or code not in REASONS:
        return error
    refined = PlatformError(
        error.code,
        platform_code=error.platform_code,
        message=REASONS[code],
        retry_after_s=error.retry_after_s,
    )
    refined.__cause__ = error.__cause__
    return refined


def _id(ref: str, what: str) -> str:
    """A platform id placed in a Graph path; anything else could change the path."""
    if not GRAPH_ID.match(ref):
        raise PlatformError("platform_rejected", message=f"Not a Facebook {what} id")
    return ref


def split_ref(container_ref: str) -> tuple[str, str]:
    """('photo' | 'photos' | 'video' | 'text', the rest)."""
    kind, _, rest = container_ref.partition(":")
    if kind not in ("photo", "photos", "video", "text") or not rest:
        raise PlatformError("platform_rejected", message="Not a Facebook upload reference")
    return kind, rest


# ---------------------------------------------------------------- creating


async def _create(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    path: str,
    body: dict[str, Any],
    *,
    endpoint: str,
) -> str:
    try:
        answer = await http.request("POST", graph(path), endpoint=endpoint, token=token, json=body)
    except PlatformError as error:
        raise _refine(error) from error.__cause__
    created = answer.get("id") if isinstance(answer, dict) else None
    if not created:
        raise PlatformError("platform_unavailable", message="Facebook returned no id")
    return _id(str(created), "upload")


async def create_photo(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    *,
    image_url: str,
    caption: str = "",
) -> str:
    body: dict[str, Any] = {"url": image_url, "published": False}
    if caption:
        body["caption"] = caption
    return "photo:" + await _create(http, graph, token, "me/photos", body, endpoint="photos.create")


async def create_video(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    *,
    video_url: str,
    caption: str = "",
) -> str:
    body: dict[str, Any] = {"file_url": video_url, "published": False}
    if caption:
        body["description"] = caption
    return "video:" + await _create(http, graph, token, "me/videos", body, endpoint="videos.create")


def create_photos_parent(children: Sequence[str]) -> str:
    """The reference to 2 to 10 unpublished photos (no call: the post is made at publish)."""
    if not PHOTOS_MIN <= len(children) <= PHOTOS_MAX:
        raise PlatformError("platform_rejected", message="A photo post needs 2 to 10 photos.")
    ids = []
    for child in children:
        kind, rest = split_ref(child)
        if kind != "photo":
            raise PlatformError("platform_rejected", message="A Facebook post can't mix videos in.")
        ids.append(_id(rest, "photo"))
    return "photos:" + ",".join(ids)


def create_text() -> str:
    return "text:post"


async def create_child(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media: ContainerMedia
) -> str:
    if media.kind == "video":
        raise PlatformError(
            "platform_rejected", message="A Facebook post can have several photos or one video."
        )
    return await create_photo(http, graph, token, image_url=media.url)


# ---------------------------------------------------------------- status and publish


def video_status(body: object) -> ContainerStatus:
    """``status.video_status`` as a container status."""
    status = body.get("status") if isinstance(body, dict) else None
    value = str(status.get("video_status") or "").lower() if isinstance(status, dict) else ""
    if value == "ready":
        return ContainerStatus(status_code="FINISHED")
    if value == "error":
        return ContainerStatus(status_code="ERROR", detail="Facebook couldn't process the video.")
    if value == "expired":
        return ContainerStatus(status_code="EXPIRED")
    return ContainerStatus(status_code="IN_PROGRESS")


async def container_status(
    http: PlatformHttp, graph: Callable[[str], str], token: str, container_ref: str
) -> ContainerStatus:
    kind, rest = split_ref(container_ref)
    if kind != "video":
        return ContainerStatus(status_code="FINISHED")
    body = await http.request(
        "GET",
        graph(_id(rest, "video")),
        endpoint="video.status",
        token=token,
        params={"fields": STATUS_FIELDS},
    )
    return video_status(body)


def first_link(text: str) -> str | None:
    match = URL.search(text)
    return match.group(0).rstrip(".,;:!?)") if match else None


async def publish_container(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    container_ref: str,
    *,
    caption: str,
) -> str:
    """Post the reference. A failure after the request went out is delivery_unknown."""
    kind, rest = split_ref(container_ref)
    path = "me/feed"
    body: dict[str, Any]
    endpoint = "feed.create"
    if kind == "video":
        path, body, endpoint = _id(rest, "video"), {"published": True}, "video.publish"
    elif kind == "text":
        if not caption.strip():
            raise PlatformError("platform_rejected", message="A text post needs text.")
        body = {"message": caption}
        link = first_link(caption)
        if link:
            body["link"] = link
    else:
        ids = [_id(part, "photo") for part in rest.split(",")]
        body = {"attached_media": [{"media_fbid": photo} for photo in ids]}
        if caption:
            body["message"] = caption
    try:
        answer = await http.request("POST", graph(path), endpoint=endpoint, token=token, json=body)
    except PlatformError as error:
        raise for_write(_refine(error)) from error.__cause__
    if kind == "video":
        if isinstance(answer, dict) and answer.get("success") is False:
            raise _lost_error()
        return rest
    created = answer.get("id") if isinstance(answer, dict) else None
    if not created:  # it answered, so it may well have published
        raise _lost_error()
    return str(created)


def _lost_error() -> PlatformError:
    return PlatformError(
        DELIVERY_UNKNOWN, retryable=False, message="Facebook did not return the post's id"
    )


# ---------------------------------------------------------------- reading back


def _video_media(raw: dict[str, Any]) -> PlatformMedia | None:
    media_id = instagram._str(raw.get("id"))
    posted_at = instagram.graph_time(raw.get("created_time"))
    if not media_id or posted_at is None:
        return None
    link = instagram._str(raw.get("permalink_url"))
    if link and link.startswith("/"):
        link = f"https://www.facebook.com{link}"
    return PlatformMedia(
        platform_media_id=media_id,
        media_type="video",
        caption=instagram._str(raw.get("description")),
        media_url=None,
        thumbnail_url=instagram._str(raw.get("picture")),
        permalink=link,
        posted_at=posted_at,
    )


async def published_media(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str
) -> PlatformMedia | None:
    """The new post's fields, permalink included. A refusal (not visible yet) is None; retryable
    errors and a dead token raise. A post id has ``_`` in it; a video id is a bare number."""
    ref = _id(media_ref, "post")
    if "_" in ref:
        fields, parse = reads.POST_FIELDS, reads.media_item
    else:
        fields, parse = VIDEO_FIELDS, _video_media
    try:
        body = await http.request(
            "GET", graph(ref), endpoint="post.published", token=token, params={"fields": fields}
        )
    except PlatformError as error:
        if error.retryable or error.code == "account_needs_reconnect":
            raise
        return None
    return parse(body) if isinstance(body, dict) else None


async def find_published_media(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    *,
    caption: str,
    published_after: datetime,
) -> PlatformMedia | None:
    posts = await reads.list_media(http, graph, token, limit=FIND_LIMIT)
    return match_published(posts, caption=caption, published_after=published_after)


async def post_comment(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str, text: str
) -> str | None:
    """The Page's own comment on its post (the first comment): a write."""
    if not text.strip():
        raise PlatformError("platform_rejected", message="A comment needs text")
    try:
        body = await http.request(
            "POST",
            graph(f"{_id(media_ref, 'post')}/comments"),
            endpoint="post.comments.create",
            token=token,
            json={"message": text},
        )
    except PlatformError as error:
        raise for_write(error) from error.__cause__
    created = body.get("id") if isinstance(body, dict) else None
    return str(created) if created else None
