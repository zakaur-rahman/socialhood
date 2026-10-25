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
- Story (GR-39): ``POST /{ig}/media`` {media_type: STORIES, image_url} or {media_type: STORIES,
  video_url}; no caption. Then the same status polling and ``media_publish`` as any container. A
  story is read back with the story fields and found again (lost answer) in ``GET /me/stories``
  by time, since ``/me/media`` does not list stories.
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
- extras (FR-PUB-07, C-134; Meta's IG User Media and IG Media Collaborators references, checked
  2026-10-25): ``collaborators`` (a list of usernames; feed images, Reels and carousels, not
  Stories), ``location_id`` (a Facebook Page id with a location), ``user_tags`` ([{username, x, y}]
  on images, children of a carousel included) and, on a Reel, ``cover_url``, ``thumb_offset``
  (ms) and ``audio_name``. ``GET /{media_id}/collaborators?fields=username,invite_status`` reads
  each collaborator's invite after publishing.

Creating containers may be retried (an unpublished container expires after 24 h).
``publish_container`` and ``post_comment`` are writes: failures go through
``platforms.outcome.for_write`` so a lost answer is ``delivery_unknown``. Error 2207042 (daily
limit) is already ``platform_rejected`` and 2207008 retryable in ``platforms.errors``; the other
publishing subcodes Meta calls temporary (2207001, 2207003, 2207027, 2207032, 2207053) are made
retryable here, and every known subcode gets a readable reason (FR-PUB-06).

Unverified until a real account publishes (T0.9, docs/verification.md; Stories: C-114; extras:
C-134): whether the JSON body takes ``collaborators`` and ``user_tags`` as arrays (Meta's examples
use form encoding), the user tag limit per image, tags on Reels, ``location_id`` on carousels
(the reference says both ways), the wording of the extras' error messages, and the Story/other
limits below: the
Story limits (image 8 MB JPEG, video 3 to 60 s, 9:16 recommended), whether Stories count against
the publishing quota, the Story-specific error subcodes (STORY_REASONS reuses the general
subcodes with Story wording), the quota answer's shape
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
    CollaboratorStatus,
    ContainerMedia,
    ContainerStatus,
    PlatformMedia,
    PublishExtras,
    PublishingQuota,
)
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram import parse
from socialhood.platforms.instagram.reads import (
    GRAPH_ID,
    MEDIA_FIELDS,
    STORY_FIELDS,
    list_media,
    list_stories,
)
from socialhood.platforms.outcome import DELIVERY_UNKNOWN, for_write

QUOTA_FIELDS = "quota_usage,config"
STATUS_FIELDS = "status_code,status"
COLLABORATOR_FIELDS = "username,invite_status"
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
# The same subcodes with wording for a Story (GR-39). Meta documents no Story-only subcodes that we
# could check, so an unknown one falls back to REASONS and then to the generic reason.
STORY_REASONS: dict[int, str] = {
    2207004: "The image is too large for an Instagram Story (the limit is 8 MB).",
    2207005: "Instagram doesn't support this image format for a Story.",
    2207009: "Instagram doesn't accept this Story's shape. Use a 9:16 image or video.",
    2207026: "Instagram doesn't support this video format for a Story.",
    2207052: "Instagram couldn't fetch the Story's media from its link.",
}
# Meta's answers about the extras name the field; no numeric subcode for them is documented.
EXTRAS_REASONS: tuple[tuple[str, str], ...] = (
    ("location", "Instagram does not accept this location. Use a Facebook Page that has a place."),
    (
        "collaborator",
        "Instagram could not add a collaborator. Check each username is a public professional "
        "account that allows collaborator tags.",
    ),
    ("user_tag", "Instagram could not tag one of the accounts in the photo. Check the usernames."),
    ("cover", "Instagram could not use the Reel's cover image."),
    ("thumb_offset", "The Reel's cover frame is outside the video."),
    ("audio_name", "Instagram does not accept this audio name."),
)
_SUBCODE = re.compile(r"\b(22070\d\d)\b")
_SPACES = re.compile(r"\s+")


# ---------------------------------------------------------------- errors


def _subcode(error: PlatformError) -> int | None:
    """The Graph error subcode (``platform_code`` is ``"code/subcode"``)."""
    _, _, sub = (error.platform_code or "").partition("/")
    return int(sub) if sub.isdigit() else None


def _refine(error: PlatformError, *, story: bool = False) -> PlatformError:
    """A publishing error with its readable reason; Meta's temporary subcodes become retryable."""
    sub = _subcode(error)
    if sub is None or sub not in REASONS:
        return _extras_error(error)
    reason = STORY_REASONS.get(sub, REASONS[sub]) if story else REASONS[sub]
    code = "platform_unavailable" if sub in TRANSIENT_SUBCODES else error.code
    refined = PlatformError(
        code,
        platform_code=error.platform_code,
        message=reason,
        retry_after_s=error.retry_after_s,
    )
    refined.__cause__ = error.__cause__
    return refined


def _extras_error(error: PlatformError) -> PlatformError:
    """A refusal that names a collaborator, tag, location, cover or audio name field gets a
    readable reason (FR-PUB-07); anything else is left as it was."""
    if error.code != "platform_rejected":
        return error
    text = (error.message or "").lower().replace("-", "_")
    for key, reason in EXTRAS_REASONS:
        if key in text:
            refined = PlatformError(
                error.code,
                platform_code=error.platform_code,
                message=reason,
                retry_after_s=error.retry_after_s,
            )
            refined.__cause__ = error.__cause__
            return refined
    return error


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
    story: bool = False,
) -> str:
    """``POST /{ig}/media``: a container. Safe to retry, so failures keep their mapped code."""
    try:
        answer = await http.request(
            "POST", graph(f"{_ig(acct)}/media"), endpoint=endpoint, token=token, json=body
        )
    except PlatformError as error:
        raise _refine(error, story=story) from error.__cause__
    container_id = parse.created_id(answer)
    if not container_id:
        raise PlatformError("platform_unavailable", message="Instagram returned no container id")
    return container_id


def _captioned(body: dict[str, Any], caption: str) -> dict[str, Any]:
    return {**body, "caption": caption} if caption else body


def _with_extras(
    body: dict[str, Any], extras: PublishExtras | None, *, tags: bool = False, reel: bool = False
) -> dict[str, Any]:
    """The container body with the optional fields set (FR-PUB-07): collaborators and location
    wherever they are set; user tags only when ``tags``; a Reel's cover and audio name when
    ``reel`` (``cover_url`` wins over ``thumb_offset``)."""
    if extras is None:
        return body
    out = dict(body)
    if extras.collaborators:
        out["collaborators"] = list(extras.collaborators)
    if extras.location_id:
        out["location_id"] = extras.location_id
    if tags and extras.user_tags:
        out["user_tags"] = [{"username": t.username, "x": t.x, "y": t.y} for t in extras.user_tags]
    if reel:
        if extras.cover_url:
            out["cover_url"] = extras.cover_url
        elif extras.thumb_offset_ms is not None:
            out["thumb_offset"] = extras.thumb_offset_ms
        if extras.audio_name:
            out["audio_name"] = extras.audio_name
    return out


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
    extras: PublishExtras | None = None,
) -> str:
    return await _create(
        http,
        graph,
        token,
        acct,
        _with_extras(_captioned({"image_url": image_url}, caption), extras, tags=True),
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
    extras: PublishExtras | None = None,
) -> str:
    body = {"media_type": "REELS", "video_url": video_url, "share_to_feed": share_to_feed}
    return await _create(
        http,
        graph,
        token,
        acct,
        _with_extras(_captioned(body, caption), extras, reel=True),
        endpoint="media.create.reel",
    )


async def create_story_container(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    media: ContainerMedia,
) -> str:
    """A Story's container: ``media_type: STORIES`` with ``image_url`` or ``video_url``. A Story
    has no caption, so none is sent."""
    body: dict[str, Any] = {"media_type": "STORIES"}
    body["video_url" if media.kind == "video" else "image_url"] = media.url
    return await _create(http, graph, token, acct, body, endpoint="media.create.story", story=True)


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
        if media.user_tags:
            body = _with_extras(body, PublishExtras(user_tags=media.user_tags), tags=True)
    return await _create(http, graph, token, acct, body, endpoint="media.create.carousel_item")


async def create_carousel_container(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    *,
    children: Sequence[str],
    caption: str,
    extras: PublishExtras | None = None,
) -> str:
    if not CAROUSEL_MIN_ASSETS <= len(children) <= CAROUSEL_MAX_ASSETS:
        raise PlatformError("platform_rejected", message=REASONS[2207028])
    body = {
        "media_type": "CAROUSEL",
        "children": ",".join(_id(child, "container") for child in children),
    }
    return await _create(
        http,
        graph,
        token,
        acct,
        _with_extras(_captioned(body, caption), extras),
        endpoint="media.create.carousel",
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
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    media_ref: str,
    *,
    story: bool = False,
) -> PlatformMedia | None:
    """The new post's fields, permalink included (a Story: the fields Stories have). A refusal
    (not visible yet) is None; retryable errors and a dead token raise."""
    url = graph(_id(media_ref, "media"))
    try:
        body = await http.request(
            "GET",
            url,
            endpoint="media.published",
            token=token,
            params={"fields": STORY_FIELDS if story else MEDIA_FIELDS},
        )
    except PlatformError as error:
        if error.retryable or error.code == "account_needs_reconnect":
            raise
        return None
    if not isinstance(body, dict):
        return None
    return parse.story_item(body) if story else parse.media_item(body)


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


def match_story(
    stories: Sequence[PlatformMedia], *, published_after: datetime
) -> PlatformMedia | None:
    """The earliest live story at or after ``published_after`` (a Story has no caption to match
    on; unverified, C-114)."""
    candidates = [s for s in stories if s.posted_at >= published_after]
    return min(candidates, key=lambda s: s.posted_at, default=None)


async def find_published_media(
    http: PlatformHttp,
    graph: Callable[[str], str],
    token: str,
    acct: SocialAccount,
    container_ref: str,
    *,
    caption: str,
    published_after: datetime,
    story: bool = False,
) -> PlatformMedia | None:
    _id(container_ref, "container")
    if story:
        return match_story(await list_stories(http, graph, token), published_after=published_after)
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


async def list_collaborators(
    http: PlatformHttp, graph: Callable[[str], str], token: str, media_ref: str
) -> list[CollaboratorStatus]:
    """``GET /{media}/collaborators``: each invited account with its invite status (Accepted or
    Pending). Needs the token of the media's creator; an unknown status counts as pending."""
    body = await http.request(
        "GET",
        graph(f"{_id(media_ref, 'media')}/collaborators"),
        endpoint="media.collaborators",
        token=token,
        params={"fields": COLLABORATOR_FIELDS},
    )
    return parse.collaborators(body)
