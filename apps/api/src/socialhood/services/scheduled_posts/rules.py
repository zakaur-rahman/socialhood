"""The publishing rules as pure functions (§5.7 format rules, FR-PUB-01, FR-PUB-10, FR-PUB-12,
TR-MED-02): the format a set of assets makes, hashtag and mention counts, hashtag normalisation,
the media file limits and the composer's checklist.

The checklist and 422 validation errors name the same fields (schemas/publishing.py): ``targets``,
``targets.{i}``, ``targets.{i}.caption_override``, ``asset_ids``, ``asset_ids.{i}``, ``caption``,
``first_comment``, ``publish_at``. Scheduling refuses a post with every failing item as a field
error, so "invalid formats rejected with field errors" (T7.1) is this module's ``checklist``
turned into ``field_errors``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from socialhood.errors import FieldError
from socialhood.models.connections import AccountStatus
from socialhood.models.publishing import (
    CAPTION_MAX_CHARS,
    CAROUSEL_MAX_ASSETS,
    CAROUSEL_MIN_ASSETS,
    FIRST_COMMENT_MAX_CHARS,
    MAX_HASHTAGS,
    MAX_MENTIONS,
    MIN_SCHEDULE_LEAD,
    PostFormat,
)
from socialhood.schemas.publishing import ChecklistItem, ChecklistKey
from socialhood.services.media_assets import IMAGE, MB, POST_VIDEO, file_format


def _combining_marks() -> str:
    """A regex class body of every combining mark (Unicode Mn, Mc, Me) and the zero-width
    joiners. Python's ``\\w`` leaves them out, which would cut Devanagari and other Indic words
    at their vowel signs and viramas ("#नमस्ते" would be "#नमस")."""
    ranges: list[tuple[int, int]] = []
    for code in (*range(0x20000), *range(0xE0000, 0xE1000)):
        if unicodedata.category(chr(code)).startswith("M") or code in (0x200C, 0x200D):
            if ranges and ranges[-1][1] == code - 1:
                ranges[-1] = (ranges[-1][0], code)
            else:
                ranges.append((code, code))
    return "".join(
        re.escape(chr(a)) if a == b else f"{re.escape(chr(a))}-{re.escape(chr(b))}"
        for a, b in ranges
    )


# A hashtag is "#" and a run of letters, digits, underscores and combining marks, in any script
# (so Hindi hashtags count whole); a mention is "@" and an Instagram username, not preceded by a
# word character (so email addresses don't count).
_WORD = rf"(?:\w|[{_combining_marks()}])"
HASHTAG = re.compile(rf"#({_WORD}+)")
MENTION = re.compile(r"(?<![\w@.])@([A-Za-z0-9._]+)")
HASHTAG_TEXT = re.compile(rf"{_WORD}+")

# TR-MED-02 (verify against Instagram's current specs, T0.9): images 4:5 to 1.91:1, with a little
# room for rounding (1080 x 1350 is exactly 4:5).
MIN_ASPECT = 4 / 5
MAX_ASPECT = 1.91
ASPECT_SLACK = 0.005

PUBLISHING_STARTED = "Publishing started."
ALREADY_PUBLISHED = "This post was already published."
NOT_SCHEDULED = "This post isn't scheduled."
TIME_TOO_SOON = "Pick a time at least 5 minutes from now."


# ---------------------------------------------------------------- format (§5.7)


def derive_format(resource_types: Sequence[str]) -> PostFormat | None:
    """1 image: an image post; 1 video: a Reel; 2 to 10 images and videos: a carousel. Nothing
    else makes a post."""
    if any(kind not in ("image", "video") for kind in resource_types):
        return None
    if len(resource_types) == 1:
        return PostFormat.IMAGE if resource_types[0] == "image" else PostFormat.REEL
    if CAROUSEL_MIN_ASSETS <= len(resource_types) <= CAROUSEL_MAX_ASSETS:
        return PostFormat.CAROUSEL
    return None


FORMAT_LABELS = {PostFormat.IMAGE: "Image post", PostFormat.REEL: "Reel"}


def format_label(fmt: PostFormat, count: int) -> str:
    return FORMAT_LABELS.get(fmt, f"Carousel of {count}")


# ---------------------------------------------------------------- hashtags and mentions


def _stored(tag: str) -> str:
    """Lowercase and NFC, so one hashtag typed two ways (a precomposed or a separate nukta,
    say) compares equal."""
    return unicodedata.normalize("NFC", tag).lower()


def hashtags_in(text: str | None) -> list[str]:
    """The hashtags of a text as stored (without "#", lowercase), in order (repeats kept)."""
    return [_stored(tag) for tag in HASHTAG.findall(text or "")]


def count_hashtags(text: str | None) -> int:
    return len(HASHTAG.findall(text or ""))


def count_mentions(text: str | None) -> int:
    return len(MENTION.findall(text or ""))


def normalize_hashtag(raw: str) -> str | None:
    """As stored (FR-PUB-12): without leading "#", lowercase, NFC; None unless what is left is
    letters, digits, underscores and combining marks (a Hindi hashtag is a hashtag)."""
    tag = _stored(raw.strip().lstrip("#").strip())
    return tag if HASHTAG_TEXT.fullmatch(tag) else None


def unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


# ---------------------------------------------------------------- the checklist (FR-PUB-10)


@dataclass(frozen=True)
class TargetFacts:
    """What the checklist needs to know about one of the post's accounts."""

    handle: str  # "@maple.bakery"
    status: str  # the account's status
    can_publish: bool  # Capability.PUBLISH
    caption_override: str | None
    # The account's other posts published or due in the 24 hours up to the post's time.
    recent_posts: int


@dataclass(frozen=True)
class AssetFacts:
    resource_type: str
    format: str | None
    bytes: int
    width: int | None
    height: int | None
    duration_s: float | None


@dataclass(frozen=True)
class PostFacts:
    targets: Sequence[TargetFacts]
    assets: Sequence[AssetFacts]
    caption: str
    first_comment: str | None
    publish_at: datetime | None


def handle(username: str | None, display_name: str | None = None) -> str:
    if username:
        return f"@{username}"
    return display_name or "This account"


def _account_problem(target: TargetFacts) -> str | None:
    if target.status == AccountStatus.DISCONNECTED:
        return f"{target.handle} is disconnected. Reconnect it or remove it from this post."
    if target.status != AccountStatus.ACTIVE:
        return f"{target.handle} needs reconnecting before it can publish."
    if not target.can_publish:
        return f"{target.handle} can't publish posts."
    return None


def asset_problem(asset: AssetFacts) -> str | None:
    """TR-MED-02: type, size, aspect ratio and video length."""
    fmt = (asset.format or "").lower()
    if asset.resource_type == "image":
        if fmt and fmt not in IMAGE.formats:
            return "Use a JPEG, PNG, WEBP or HEIC image."
        if asset.bytes > IMAGE.max_bytes:
            return f"Images can be up to {IMAGE.max_bytes // MB} MB."
        if asset.width and asset.height:
            ratio = asset.width / asset.height
            if ratio < MIN_ASPECT - ASPECT_SLACK or ratio > MAX_ASPECT + ASPECT_SLACK:
                return "Crop this image to between 4:5 (portrait) and 1.91:1 (landscape)."
        return None
    if asset.resource_type == "video":
        if fmt and fmt not in POST_VIDEO.formats:
            return "Use an MP4 or MOV video."
        if asset.bytes > POST_VIDEO.max_bytes:
            return f"Videos can be up to {POST_VIDEO.max_bytes // MB} MB."
        limit = POST_VIDEO.max_duration_s
        if limit is not None and asset.duration_s is not None and asset.duration_s > limit:
            return f"Videos can be up to {limit:.0f} seconds."
        return None
    return "Posts can only use images and videos."


def asset_facts(
    resource_type: str,
    fmt: str | None,
    public_id: str,
    size: int,
    width: int | None,
    height: int | None,
    duration_s: float | None,
) -> AssetFacts:
    return AssetFacts(resource_type, file_format(fmt, public_id), size, width, height, duration_s)


def _item(
    key: ChecklistKey, message: str, *, ok: bool = True, field: str | None = None
) -> ChecklistItem:
    return ChecklistItem(key=key, ok=ok, message=message, field=field)


def _texts(post: PostFacts, *, first_comment: bool) -> list[tuple[str, str | None]]:
    """(field, text) for the caption, each account's own caption and, when asked, the first
    comment."""
    texts: list[tuple[str, str | None]] = [("caption", post.caption)]
    texts += [
        (f"targets.{i}.caption_override", t.caption_override)
        for i, t in enumerate(post.targets)
        if t.caption_override is not None
    ]
    if first_comment and post.first_comment is not None:
        texts.append(("first_comment", post.first_comment))
    return texts


def checklist(
    post: PostFacts,
    *,
    now: datetime,
    publishing_limit: int,
    check_time: bool = True,
) -> list[ChecklistItem]:
    """FR-PUB-10 in CHECKLIST_KEYS order. A passing check is one item; a failing check is one
    item per failing element, ``field`` naming it. ``check_time`` False leaves out the 5-minute
    rule (Publish now)."""
    items: list[ChecklistItem] = []

    # accounts
    if not post.targets:
        items.append(_item("accounts", "Choose at least one account.", ok=False, field="targets"))
    else:
        failing = [
            _item("accounts", problem, ok=False, field=f"targets.{i}")
            for i, t in enumerate(post.targets)
            if (problem := _account_problem(t)) is not None
        ]
        count = len(post.targets)
        items += failing or [
            _item(
                "accounts",
                f"Publishing to {post.targets[0].handle}"
                if count == 1
                else f"Publishing to {count} accounts",
            )
        ]

    # media and media_files
    fmt = derive_format([a.resource_type for a in post.assets])
    if not post.assets:
        items.append(_item("media", "Add an image or video.", ok=False, field="asset_ids"))
    elif fmt is None:
        items.append(
            _item(
                "media",
                "Use 1 image, 1 video, or 2 to 10 images and videos.",
                ok=False,
                field="asset_ids",
            )
        )
    else:
        items.append(_item("media", format_label(fmt, len(post.assets))))
    failing = [
        _item("media_files", problem, ok=False, field=f"asset_ids.{i}")
        for i, a in enumerate(post.assets)
        if (problem := asset_problem(a)) is not None
    ]
    items += failing or [_item("media_files", "Media meets Instagram's requirements")]

    # caption: lengths
    failing = []
    for field, text in _texts(post, first_comment=True):
        limit = FIRST_COMMENT_MAX_CHARS if field == "first_comment" else CAPTION_MAX_CHARS
        if len(text or "") > limit:
            what = "first comment" if field == "first_comment" else "caption"
            failing.append(
                _item(
                    "caption",
                    f"Shorten the {what} to {limit:,} characters (now {len(text or ''):,}).",
                    ok=False,
                    field=field,
                )
            )
    items += failing or [_item("caption", f"Caption within {CAPTION_MAX_CHARS:,} characters")]

    # hashtags: each caption and the first comment (where hashtags often go, FR-PUB-11)
    failing = []
    for field, text in _texts(post, first_comment=True):
        n = count_hashtags(text)
        if n > MAX_HASHTAGS:
            failing.append(
                _item(
                    "hashtags",
                    f"Use at most {MAX_HASHTAGS} hashtags (now {n}).",
                    ok=False,
                    field=field,
                )
            )
    items += failing or [_item("hashtags", f"Up to {MAX_HASHTAGS} hashtags")]

    # mentions: each caption
    failing = []
    for field, text in _texts(post, first_comment=False):
        n = count_mentions(text)
        if n > MAX_MENTIONS:
            failing.append(
                _item(
                    "mentions",
                    f"Mention at most {MAX_MENTIONS} accounts (now {n}).",
                    ok=False,
                    field=field,
                )
            )
    items += failing or [_item("mentions", f"Up to {MAX_MENTIONS} @mentions")]

    # publishing_limit: this post plus the account's others in the 24 hours up to its time
    failing = [
        _item(
            "publishing_limit",
            f"{t.handle} already has {t.recent_posts} posts in the 24 hours before this time; "
            f"Instagram allows {publishing_limit}.",
            ok=False,
            field=f"targets.{i}",
        )
        for i, t in enumerate(post.targets)
        if t.recent_posts + 1 > publishing_limit
    ]
    items += failing or [_item("publishing_limit", "Room in each account's daily publishing limit")]

    # publish_at: only when the post has a time
    if check_time and post.publish_at is not None:
        if post.publish_at < now + MIN_SCHEDULE_LEAD:
            items.append(_item("publish_at", TIME_TOO_SOON, ok=False, field="publish_at"))
        else:
            items.append(_item("publish_at", "At least 5 minutes from now"))
    return items


def field_errors(items: Sequence[ChecklistItem]) -> list[FieldError]:
    """The failing items as 422 field errors (same names, same messages)."""
    return [FieldError(i.field or i.key, i.message) for i in items if not i.ok]
