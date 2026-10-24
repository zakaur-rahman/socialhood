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
    FACEBOOK_CAPTION_MAX_CHARS,
    FACEBOOK_REEL_MIN_S,
    FIRST_COMMENT_MAX_CHARS,
    MAX_HASHTAGS,
    MAX_MENTIONS,
    MIN_SCHEDULE_LEAD,
    STORY_VIDEO_MAX_S,
    STORY_VIDEO_MIN_S,
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

# A Story is shown full screen, 9:16; other shapes are cropped or letterboxed by Instagram, so
# they pass with a note (unverified: Meta states 9:16 as the recommendation, C-114).
STORY_ASPECT = 9 / 16
STORY_ASPECT_TOLERANCE = 0.05
STORY_ONE_FILE = "A Story is one image or one video."
STORY_NO_CAPTION = "Stories are published without a caption"
# A Facebook Reel (C-131) is one video, 3 to 90 seconds, for a Page; 9:16 fits it best.
REEL_ONE_VIDEO = "A Facebook Reel is one video."
REEL_NEEDS_PAGE = (
    "Choose a Facebook Page for a Reel. Instagram already publishes a single video as a Reel."
)
REEL_NEEDS_VIDEO = "Add a video for the Reel."

# Facebook Pages (GR-30): a photo post takes several photos or one video, never both.
FACEBOOK_NO_MIX = "A Facebook post can have several photos or one video, not both."
FACEBOOK_NO_MEDIA = "Add a photo or video, or write the post's text."
NEEDS_MEDIA = "{handle} can't publish a post without a photo or video."

PUBLISHING_STARTED = "Publishing started."
ALREADY_PUBLISHED = "This post was already published."
NOT_SCHEDULED = "This post isn't scheduled."
TIME_TOO_SOON = "Pick a time at least 5 minutes from now."


# ---------------------------------------------------------------- format (§5.7)


def derive_format(
    resource_types: Sequence[str],
    *,
    story: bool = False,
    text: bool = False,
    reel: bool = False,
) -> PostFormat | None:
    """1 image: an image post; 1 video: a Reel; 2 to 10 images and videos: a carousel. Chosen as a
    Story (GR-39), exactly 1 image or video is a Story. No media but text for a Facebook Page
    (``text``, GR-30): a text post. Chosen as a Reel (``reel``, C-131), exactly 1 video is a Reel
    and nothing else is. Nothing else makes a post."""
    if any(kind not in ("image", "video") for kind in resource_types):
        return None
    if reel and not story:
        return PostFormat.REEL if list(resource_types) == ["video"] else None
    if not resource_types:
        return PostFormat.TEXT if text and not story else None
    if story:
        return PostFormat.STORY if len(resource_types) == 1 else None
    if len(resource_types) == 1:
        return PostFormat.IMAGE if resource_types[0] == "image" else PostFormat.REEL
    if CAROUSEL_MIN_ASSETS <= len(resource_types) <= CAROUSEL_MAX_ASSETS:
        return PostFormat.CAROUSEL
    return None


FORMAT_LABELS = {
    PostFormat.IMAGE: "Image post",
    PostFormat.REEL: "Reel",
    PostFormat.STORY: "Story",
    PostFormat.TEXT: "Text post",
}


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
    platform: str = "instagram"  # "instagram", "facebook", ...


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
    story: bool = False  # chosen as a Story (GR-39; a Facebook Page's too, C-131)
    reel: bool = False  # chosen as a Facebook Reel (C-131)


def handle(username: str | None, display_name: str | None = None) -> str:
    if username:
        return f"@{username}"
    return display_name or "This account"


def _account_problem(target: TargetFacts, *, text: bool = False) -> str | None:
    if target.status == AccountStatus.DISCONNECTED:
        return f"{target.handle} is disconnected. Reconnect it or remove it from this post."
    if target.status != AccountStatus.ACTIVE:
        return f"{target.handle} needs reconnecting before it can publish."
    if not target.can_publish:
        return f"{target.handle} can't publish posts."
    if text and target.platform != "facebook":
        return NEEDS_MEDIA.format(handle=target.handle)
    return None


def asset_problem(
    asset: AssetFacts, *, story: bool = False, instagram: bool = True, reel: bool = False
) -> str | None:
    """TR-MED-02: type, size, aspect ratio and video length. A Story takes any image shape (9:16
    is only recommended) and a video of 3 to 60 seconds; a Facebook Reel a video of 3 to 90."""
    fmt = (asset.format or "").lower()
    if asset.resource_type == "image":
        if fmt and fmt not in IMAGE.formats:
            return "Use a JPEG, PNG, WEBP or HEIC image."
        if asset.bytes > IMAGE.max_bytes:
            return f"Images can be up to {IMAGE.max_bytes // MB} MB."
        if asset.width and asset.height and not story and instagram:
            ratio = asset.width / asset.height
            if ratio < MIN_ASPECT - ASPECT_SLACK or ratio > MAX_ASPECT + ASPECT_SLACK:
                return "Crop this image to between 4:5 (portrait) and 1.91:1 (landscape)."
        return None
    if asset.resource_type == "video":
        if fmt and fmt not in POST_VIDEO.formats:
            return "Use an MP4 or MOV video."
        if asset.bytes > POST_VIDEO.max_bytes:
            return f"Videos can be up to {POST_VIDEO.max_bytes // MB} MB."
        limit = STORY_VIDEO_MAX_S if story else POST_VIDEO.max_duration_s
        if limit is not None and asset.duration_s is not None and asset.duration_s > limit:
            return f"{'Story videos' if story else 'Videos'} can be up to {limit:.0f} seconds."
        if story and asset.duration_s is not None and asset.duration_s < STORY_VIDEO_MIN_S:
            return f"Story videos must be at least {STORY_VIDEO_MIN_S} seconds."
        if reel and asset.duration_s is not None and asset.duration_s < FACEBOOK_REEL_MIN_S:
            return f"Reel videos must be at least {FACEBOOK_REEL_MIN_S} seconds."
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


def story_shape_note(
    asset: AssetFacts, *, platforms: str = "Instagram", what: str = "Story"
) -> str | None:
    """A passing Story (or Facebook Reel) file that is not 9:16: the platform crops or letterboxes
    it. ``platforms`` names who does it: "Instagram", "Facebook" or "Instagram and Facebook"."""
    if not (asset.width and asset.height):
        return None
    ratio = asset.width / asset.height
    if abs(ratio - STORY_ASPECT) <= STORY_ASPECT_TOLERANCE * STORY_ASPECT:
        return None
    return f"9:16 fits a {what} best. {platforms} may crop or add bars to this file."


def _item(
    key: ChecklistKey, message: str, *, ok: bool = True, field: str | None = None
) -> ChecklistItem:
    return ChecklistItem(key=key, ok=ok, message=message, field=field)


def caption_limit(platforms: Iterable[str]) -> int:
    """The caption length a post to these platforms may have: Instagram's 2,200 unless every
    account is a Facebook Page (C-131). No accounts yet: Instagram's, the strictest."""
    kinds = list(platforms)
    if kinds and all(kind == "facebook" for kind in kinds):
        return FACEBOOK_CAPTION_MAX_CHARS
    return CAPTION_MAX_CHARS


def _limits(post: PostFacts) -> dict[str, int]:
    """The length limit of each caption field. An account's own caption is held to its own
    platform; the shared caption goes to every account without one, so it is held to the
    strictest of those (to the longest limit when each account has its own caption)."""
    limits = {"first_comment": FIRST_COMMENT_MAX_CHARS}
    shared = [t.platform for t in post.targets if t.caption_override is None]
    limits["caption"] = caption_limit(shared) if shared else FACEBOOK_CAPTION_MAX_CHARS
    for i, t in enumerate(post.targets):
        if t.caption_override is not None:
            limits[f"targets.{i}.caption_override"] = caption_limit([t.platform])
    return limits


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


def _text_items(post: PostFacts, *, hashtags_and_mentions: bool = True) -> list[ChecklistItem]:
    """The caption, hashtags and mentions checks (FR-PUB-10) of a post that has a caption.
    Hashtag and mention limits are Instagram's: a post for Facebook Pages only skips them."""
    items: list[ChecklistItem] = []
    # caption: lengths, each against the limit of the accounts it goes to
    failing = []
    limits = _limits(post)
    for field, text in _texts(post, first_comment=True):
        limit = limits[field]
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
    overall = caption_limit(t.platform for t in post.targets)
    items += failing or [_item("caption", f"Caption within {overall:,} characters")]
    if not hashtags_and_mentions:
        return items

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
    return items


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

    ig = any(t.platform == "instagram" for t in post.targets)
    fb = any(t.platform == "facebook" for t in post.targets)
    text_post = bool(post.caption.strip()) and fb and not ig and not post.story and not post.reel
    fmt = derive_format(
        [a.resource_type for a in post.assets],
        story=post.story,
        text=text_post,
        reel=post.reel,
    )

    # accounts
    if not post.targets:
        items.append(_item("accounts", "Choose at least one account.", ok=False, field="targets"))
    else:
        failing = [
            _item("accounts", problem, ok=False, field=f"targets.{i}")
            for i, t in enumerate(post.targets)
            if (problem := _account_problem(t, text=fmt == PostFormat.TEXT)) is not None
        ]
        if post.reel and not fb:
            failing.append(_item("accounts", REEL_NEEDS_PAGE, ok=False, field="targets"))
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
    mixed = (
        fb and fmt == PostFormat.CAROUSEL and any(a.resource_type == "video" for a in post.assets)
    )
    if fmt == PostFormat.TEXT:
        items.append(_item("media", format_label(fmt, 0)))
    elif not post.assets:
        items.append(
            _item(
                "media",
                REEL_NEEDS_VIDEO
                if post.reel
                else FACEBOOK_NO_MEDIA
                if fb and not ig
                else "Add an image or video.",
                ok=False,
                field="asset_ids",
            )
        )
    elif fmt is None:
        items.append(
            _item(
                "media",
                STORY_ONE_FILE
                if post.story
                else REEL_ONE_VIDEO
                if post.reel
                else "Use 1 image, 1 video, or 2 to 10 images and videos.",
                ok=False,
                field="asset_ids",
            )
        )
    elif mixed:
        items.append(_item("media", FACEBOOK_NO_MIX, ok=False, field="asset_ids"))
    else:
        items.append(_item("media", format_label(fmt, len(post.assets))))
    failing = [
        _item("media_files", problem, ok=False, field=f"asset_ids.{i}")
        for i, a in enumerate(post.assets)
        if (
            problem := asset_problem(
                a, story=post.story, instagram=ig or not fb, reel=post.reel and fb
            )
        )
        is not None
    ]
    names = "Instagram's and Facebook's" if ig and fb else "Facebook's" if fb else "Instagram's"
    who = "Instagram and Facebook" if ig and fb else "Facebook" if fb else "Instagram"
    note = None
    if len(post.assets) == 1 and (post.story or post.reel):
        note = story_shape_note(
            post.assets[0], platforms=who, what="Story" if post.story else "Reel"
        )
    if post.assets or fmt != PostFormat.TEXT:
        items += failing or [_item("media_files", note or f"Media meets {names} requirements")]

    if post.story:
        # A Story has no caption, hashtags or mentions: whatever the draft holds is kept but
        # never sent, so there is nothing to check.
        items.append(_item("caption", STORY_NO_CAPTION))
    else:
        items += _text_items(post, hashtags_and_mentions=ig or not fb)

    # publishing_limit: this post plus the account's others in the 24 hours up to its time
    # (Instagram only: Facebook Pages have no such limit)
    if ig or not post.targets:
        failing = [
            _item(
                "publishing_limit",
                f"{t.handle} already has {t.recent_posts} posts in the 24 hours before this time; "
                f"Instagram allows {publishing_limit}.",
                ok=False,
                field=f"targets.{i}",
            )
            for i, t in enumerate(post.targets)
            if t.platform == "instagram" and t.recent_posts + 1 > publishing_limit
        ]
        items += failing or [
            _item("publishing_limit", "Room in each account's daily publishing limit")
        ]

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
