"""Sandbox publishing (T7.2; TR-PL-07, FR-PUB-05, F-13 end to end): containers, their processing
and published posts live in memory, so the composer, the calendar and the publish jobs can be
developed and tested without Meta. The adapter's publishing methods delegate here.

It behaves like Instagram where the jobs depend on it: image containers are FINISHED at once;
video containers (Reels and carousel video children) stay IN_PROGRESS for ``processing_reads``
status reads (2 unless set) before FINISHED; a carousel can only be created from FINISHED
children of the same account (Meta refuses the rest); publishing needs a FINISHED container and
room in the quota, and a published container reads PUBLISHED and can't be published again.
Published posts get a platform media id and a permalink and show up in ``history.post`` and
``list_media`` like synced posts; a first comment gets an id and is recorded in ``COMMENTS``.

A Facebook Page behaves like its real self where the jobs depend on it (C-131): a plain post's
container status never says it was published (a lost answer ends unconfirmed), a Reel's and a
video Story's does; a Page video is a normal video unless it was created as a Reel; a Page Story
has no permalink and can't be listed.

Failures are injectable for tests, like sends in ``outbox``:
- ``fail_next(code, step=…)`` makes the next call of a step fail (quota, container, status,
  publish, read, find, comment); ``lose_next_publish_answer()`` publishes but answers
  ``delivery_unknown``, as a timeout after the request went out would;
- ``set_quota(used, limit)`` sets the account's usage (published posts count on top);
- ``fail_next_container(status, detail)`` makes the next container created read ERROR or EXPIRED;
- ``processing_reads(n)`` sets how long videos process;
- a caption (or first comment) containing ``[sandbox:fail=<code>]`` fails its publish (or the
  comment) on every attempt, so end-to-end runs can show a failed post.
``outbox.reset()`` forgets all of it.

Instagram extras (FR-PUB-07, C-134): containers keep what they were created with (``extras``,
and a carousel image's ``user_tags``) and refuse what Meta refuses: more than 3 collaborators,
collaborators on a Story, tags outside 0 to 1, tags on a video, a location that is not a numeric
Page id. After publishing, ``list_collaborators`` answers each invited username as Pending, or
Accepted when it starts with "accept" (or ``accept_collaborator`` was called), so end-to-end runs
can show both.
"""

from __future__ import annotations

import secrets
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from socialhood.models.connections import SocialAccount
from socialhood.models.publishing import (
    CAROUSEL_MAX_ASSETS,
    CAROUSEL_MIN_ASSETS,
    COLLABORATORS_MAX,
    DEFAULT_PUBLISHING_LIMIT,
)
from socialhood.platforms.base import (
    CollaboratorStatus,
    ContainerMedia,
    ContainerStatus,
    ContainerStatusCode,
    PlatformMedia,
    PublishExtras,
    PublishingQuota,
    UserTag,
)
from socialhood.platforms.errors import PlatformError

PublishStep = Literal[
    "quota", "container", "status", "publish", "read", "find", "comment", "collaborators"
]
ContainerKind = Literal["image", "video", "carousel", "text"]
STORY_LIFETIME = timedelta(hours=24)

DEFAULT_PROCESSING_READS = 2
QUOTA_WINDOW = timedelta(hours=24)
LIMIT_REACHED = "Instagram's daily publishing limit reached"
KEEP = 200


@dataclass
class SandboxContainer:
    id: str
    account_ref: str
    kind: ContainerKind
    carousel_item: bool
    url: str | None = None
    caption: str | None = None
    children: tuple[str, ...] = ()
    share_to_feed: bool = True
    story: bool = False
    page_reel: bool = False  # a Facebook Reel (C-131)
    # Whether the status says "PUBLISHED" once published. Instagram's does; a Facebook Page's does
    # only for a Reel or a video Story (their publishing phase), not a plain post.
    shows_published: bool = True
    reads_left: int = 0  # status reads still IN_PROGRESS
    status_code: ContainerStatusCode = "IN_PROGRESS"
    detail: str | None = None
    media_id: str | None = None
    status_reads: int = 0
    extras: PublishExtras | None = None  # FR-PUB-07, as the container was created
    user_tags: tuple[UserTag, ...] = ()  # an image's (a carousel child's too)


@dataclass(frozen=True)
class SandboxComment:
    account_ref: str
    media_ref: str
    text: str
    platform_comment_id: str


@dataclass
class _State:
    containers: dict[str, SandboxContainer] = field(default_factory=dict)
    # account ref -> its published posts, oldest first
    published: dict[str, list[PlatformMedia]] = field(default_factory=dict)
    quota_used: dict[str, int] = field(default_factory=dict)
    quota_limit: dict[str, int] = field(default_factory=dict)
    failures: deque[tuple[PublishStep, PlatformError]] = field(default_factory=deque)
    container_outcomes: deque[tuple[ContainerStatusCode, str | None]] = field(default_factory=deque)
    lose_publish_answers: int = 0
    processing_reads: int = DEFAULT_PROCESSING_READS
    publishes: list[str] = field(default_factory=list)  # container ids, in publish order
    # media id -> its collaborators' invite status (username -> accepted)
    invites: dict[str, dict[str, bool]] = field(default_factory=dict)


STATE = _State()
COMMENTS: deque[SandboxComment] = deque(maxlen=KEEP)


def reset() -> None:
    global STATE
    STATE = _State()
    COMMENTS.clear()


# ---------------------------------------------------------------- injection (tests, e2e)


def fail_next(
    code: str, *, step: PublishStep, times: int = 1, retry_after_s: float | None = None
) -> None:
    for _ in range(times):
        STATE.failures.append((step, _error(code, retry_after_s)))


def lose_next_publish_answer(times: int = 1) -> None:
    STATE.lose_publish_answers += times


def set_quota(used: int, limit: int = DEFAULT_PUBLISHING_LIMIT, *, account_ref: str = "*") -> None:
    """Posts already published in the last 24 h (published sandbox posts count on top)."""
    STATE.quota_used[account_ref] = used
    STATE.quota_limit[account_ref] = limit


def fail_next_container(
    status: Literal["ERROR", "EXPIRED"] = "ERROR", detail: str | None = None
) -> None:
    """The next container created reads ``status`` at its first status read."""
    STATE.container_outcomes.append((status, detail))


def processing_reads(count: int) -> None:
    STATE.processing_reads = count


def publish_count() -> int:
    return len(STATE.publishes)


def published(acct_ref: str) -> list[PlatformMedia]:
    """The account's published sandbox posts, newest first (``history.posts`` lists them)."""
    return sorted(STATE.published.get(acct_ref, []), key=lambda m: m.posted_at, reverse=True)


def accept_collaborator(media_ref: str, username: str) -> None:
    """A collaborator accepts the invite (the sandbox's stand-in for the Instagram app)."""
    STATE.invites.setdefault(media_ref, {})[username] = True


def container(container_ref: str) -> SandboxContainer | None:
    return STATE.containers.get(container_ref)


def _error(code: str, retry_after_s: float | None) -> PlatformError:
    return PlatformError(
        code,
        retryable=False if code == "delivery_unknown" else None,
        platform_code="sandbox",
        message=f"Sandbox failure: {code}",
        retry_after_s=retry_after_s,
    )


def _injected(step: PublishStep, text: str | None = None) -> None:
    from socialhood.platforms.sandbox.outbox import DIRECTIVE

    for index, (only, error) in enumerate(STATE.failures):
        if only == step:
            del STATE.failures[index]
            raise error
    match = DIRECTIVE.search(text or "")
    if match:
        raise _error(match.group(1), None)


def _rejected(message: str) -> PlatformError:
    return PlatformError("platform_rejected", platform_code="sandbox", message=message)


# ---------------------------------------------------------------- the adapter's calls


def publishing_quota(acct: SocialAccount, *, now: datetime | None = None) -> PublishingQuota:
    _injected("quota")
    return _quota(acct.platform_account_id, now or datetime.now(UTC))


def _quota(account_ref: str, now: datetime) -> PublishingQuota:
    posts = STATE.published.get(account_ref, [])
    recent = sum(1 for m in posts if m.posted_at > now - QUOTA_WINDOW)
    base = STATE.quota_used.get(account_ref, STATE.quota_used.get("*", 0))
    limit = STATE.quota_limit.get(account_ref, STATE.quota_limit.get("*", DEFAULT_PUBLISHING_LIMIT))
    return PublishingQuota(used=base + recent, limit=limit)


def _new_container(
    acct: SocialAccount,
    kind: ContainerKind,
    *,
    carousel_item: bool,
    url: str | None = None,
    caption: str | None = None,
    children: tuple[str, ...] = (),
    share_to_feed: bool = True,
    story: bool = False,
    page_reel: bool = False,
    extras: PublishExtras | None = None,
    user_tags: tuple[UserTag, ...] = (),
) -> str:
    _injected("container")
    _check_extras(acct, extras, kind=kind, user_tags=user_tags, story=story)
    container_id = f"sandbox_container_{secrets.token_hex(8)}"
    row = SandboxContainer(
        id=container_id,
        account_ref=acct.platform_account_id,
        kind=kind,
        carousel_item=carousel_item,
        url=url,
        caption=caption,
        children=children,
        share_to_feed=share_to_feed,
        story=story,
        page_reel=page_reel,
        shows_published=acct.platform != "facebook" or (kind == "video" and (story or page_reel)),
        extras=extras,
        user_tags=user_tags,
        reads_left=STATE.processing_reads if kind == "video" else 0,
        status_code="IN_PROGRESS" if kind == "video" else "FINISHED",
    )
    if STATE.container_outcomes:
        row.status_code, row.detail = STATE.container_outcomes.popleft()
        row.reads_left = 0
    STATE.containers[container_id] = row
    return container_id


def _check_extras(
    acct: SocialAccount,
    extras: PublishExtras | None,
    *,
    kind: ContainerKind,
    user_tags: tuple[UserTag, ...],
    story: bool,
) -> None:
    """What Meta refuses about the extras (the reference, 2026-10-25)."""
    if acct.platform != "instagram":
        return
    tags = user_tags or (extras.user_tags if extras else ())
    if tags and kind != "image":
        raise _rejected("Sandbox: user_tags are for images")
    for tag in tags:
        if not (0 <= tag.x <= 1 and 0 <= tag.y <= 1) or not tag.username:
            raise _rejected("Sandbox: a user_tags position must be between 0 and 1")
    if extras is None:
        return
    if extras.collaborators and (story or len(extras.collaborators) > COLLABORATORS_MAX):
        raise _rejected("Sandbox: invalid collaborators")
    if extras.location_id and not extras.location_id.isdigit():
        raise _rejected("Sandbox: INSTAGRAM_PLATFORM_API__INVALID_LOCATION_ID")
    if (extras.cover_url or extras.thumb_offset_ms is not None) and kind != "video":
        raise _rejected("Sandbox: a cover is for a Reel")


def create_image_container(
    acct: SocialAccount, *, image_url: str, caption: str, extras: PublishExtras | None = None
) -> str:
    return _new_container(
        acct, "image", carousel_item=False, url=image_url, caption=caption, extras=extras
    )


def create_reel_container(
    acct: SocialAccount,
    *,
    video_url: str,
    caption: str,
    share_to_feed: bool,
    page_reel: bool = False,
    extras: PublishExtras | None = None,
) -> str:
    return _new_container(
        acct,
        "video",
        carousel_item=False,
        url=video_url,
        caption=caption,
        share_to_feed=share_to_feed,
        page_reel=page_reel,
        extras=extras,
    )


def create_text_container(acct: SocialAccount) -> str:
    """A text post (Facebook Pages): FINISHED at once; its text arrives with the publish."""
    return _new_container(acct, "text", carousel_item=False)


def create_story_container(acct: SocialAccount, media: ContainerMedia) -> str:
    """A Story: one image (FINISHED at once) or video (processes like a Reel), no caption."""
    return _new_container(acct, media.kind, carousel_item=False, url=media.url, story=True)


def create_carousel_item(acct: SocialAccount, media: ContainerMedia) -> str:
    return _new_container(
        acct, media.kind, carousel_item=True, url=media.url, user_tags=media.user_tags
    )


def create_carousel_container(
    acct: SocialAccount,
    *,
    children: Sequence[str],
    caption: str,
    extras: PublishExtras | None = None,
) -> str:
    if not CAROUSEL_MIN_ASSETS <= len(children) <= CAROUSEL_MAX_ASSETS:
        raise _rejected("A carousel needs 2 to 10 photos or videos.")
    for child_id in children:
        child = STATE.containers.get(child_id)
        if child is None or child.account_ref != acct.platform_account_id:
            raise _rejected("Sandbox: a carousel child wasn't found")
        if not child.carousel_item:
            raise _rejected("Sandbox: a carousel child must be created as a carousel item")
        if child.status_code != "FINISHED":  # Meta's invalid_children
            raise _rejected("Sandbox: carousel children are still processing")
    return _new_container(
        acct,
        "carousel",
        carousel_item=False,
        children=tuple(children),
        caption=caption,
        extras=extras,
    )


def _own(acct: SocialAccount, container_ref: str) -> SandboxContainer:
    row = STATE.containers.get(container_ref)
    if row is None or row.account_ref != acct.platform_account_id:
        raise _rejected("Sandbox: no such container")
    return row


def container_status(acct: SocialAccount, container_ref: str) -> ContainerStatus:
    _injected("status")
    row = _own(acct, container_ref)
    row.status_reads += 1
    if row.status_code == "IN_PROGRESS":
        if row.reads_left > 0:
            row.reads_left -= 1
        else:
            row.status_code = "FINISHED"
    if row.status_code == "PUBLISHED" and not row.shows_published:
        # A Facebook Page's plain post has no published state to read (C-115): it reads as it
        # did before the publish.
        return ContainerStatus(status_code="FINISHED", detail=row.detail)
    return ContainerStatus(status_code=row.status_code, detail=row.detail)


def publish_container(
    acct: SocialAccount, container_ref: str, *, now: datetime | None = None, text: str = ""
) -> str:
    row = _own(acct, container_ref)
    if text and not row.caption:  # Facebook: the text goes with the publish
        row.caption = text
    _injected("publish", row.caption)
    if row.carousel_item:
        raise _rejected("Sandbox: a carousel item is published through its carousel")
    if row.status_code == "PUBLISHED":
        raise _rejected("Sandbox: this container was already published")
    if row.status_code == "IN_PROGRESS":
        raise PlatformError(
            "platform_unavailable",
            platform_code="sandbox",
            message="The media wasn't ready to publish yet.",
        )
    if row.status_code != "FINISHED":
        raise _rejected(f"Sandbox: the container is {row.status_code}")
    at = now or datetime.now(UTC)
    if acct.platform == "instagram" and _quota(acct.platform_account_id, at).remaining <= 0:
        raise _rejected(LIMIT_REACHED)
    media_id = f"sandbox_media_{secrets.token_hex(8)}"
    media_type: Literal["image", "video", "carousel", "reel", "story"] = (
        "story"
        if row.story
        else "carousel"
        if row.kind == "carousel"
        else ("reel" if acct.platform == "instagram" or row.page_reel else "video")
        if row.kind == "video"
        else "image"
    )
    first_url = row.url
    if row.kind == "carousel" and row.children:
        first = STATE.containers.get(row.children[0])
        first_url = first.url if first else None
    STATE.published.setdefault(acct.platform_account_id, []).append(
        PlatformMedia(
            platform_media_id=media_id,
            media_type=media_type,
            caption=row.caption or None,
            media_url=first_url,
            thumbnail_url=None,
            # A Page Story has no address we could read back (C-131).
            permalink=(
                None
                if row.story and acct.platform == "facebook"
                else _permalink(acct, media_id, story=row.story)
            ),
            posted_at=at.replace(microsecond=0),
            like_count=0,
            comments_count=0,
        )
    )
    row.status_code = "PUBLISHED"
    row.media_id = media_id
    if row.extras and row.extras.collaborators:
        STATE.invites[media_id] = {
            name: name.lower().startswith("accept") for name in row.extras.collaborators
        }
    STATE.publishes.append(container_ref)
    if STATE.lose_publish_answers:
        STATE.lose_publish_answers -= 1
        raise PlatformError(
            "delivery_unknown", retryable=False, message="The platform did not confirm the send"
        )
    return media_id


def _permalink(acct: SocialAccount, media_id: str, *, story: bool) -> str:
    tail = media_id[-11:]
    if acct.platform == "facebook":
        return f"https://www.facebook.com/{acct.platform_account_id}/posts/{tail}"
    if story:
        return f"https://www.instagram.com/stories/{acct.username or 'sandbox'}/{tail}/"
    return f"https://www.instagram.com/p/{tail}/"


def published_media(acct: SocialAccount, media_ref: str) -> PlatformMedia | None:
    _injected("read")
    posts = STATE.published.get(acct.platform_account_id, [])
    return next((m for m in posts if m.platform_media_id == media_ref), None)


def stories(acct_ref: str, *, now: datetime | None = None) -> list[PlatformMedia]:
    """The account's published sandbox stories still live (the last 24 hours), newest first."""
    at = now or datetime.now(UTC)
    return [
        m
        for m in published(acct_ref)
        if m.media_type == "story" and m.posted_at + STORY_LIFETIME > at
    ]


def find_published_media(
    acct: SocialAccount,
    container_ref: str,
    *,
    caption: str,
    published_after: datetime,
    story: bool = False,
) -> PlatformMedia | None:
    """Like Instagram's: matched on caption and time among the account's recent posts (a Story:
    among its live stories, on time alone)."""
    from socialhood.platforms.instagram.publishing import match_published, match_story

    _injected("find")
    if story:
        return match_story(stories(acct.platform_account_id), published_after=published_after)
    return match_published(
        published(acct.platform_account_id), caption=caption, published_after=published_after
    )


def post_comment(acct: SocialAccount, media_ref: str, text: str) -> str | None:
    _injected("comment", text)
    comment_id = f"sandbox_comment_{secrets.token_hex(8)}"
    COMMENTS.append(SandboxComment(acct.platform_account_id, media_ref, text, comment_id))
    return comment_id


def list_collaborators(acct: SocialAccount, media_ref: str) -> list[CollaboratorStatus]:
    """The post's collaborators with their invite status, in the order they were invited."""
    _injected("collaborators")
    return [
        CollaboratorStatus(username=name, status="accepted" if accepted else "pending")
        for name, accepted in STATE.invites.get(media_ref, {}).items()
    ]
