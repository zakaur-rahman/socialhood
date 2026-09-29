"""Publishing shapes (§2.15 …/scheduled-posts, …/calendar, …/posting-slots, …/hashtag-groups,
…/media-assets, …/ai/caption and …/ai/hashtags; §5.10 ScheduledPost; FR-PUB-01…14, F-13,
UX-SCR-04, UX-SCR-13, UX-SCR-14).

The P7 contract. ``scheduled_post.updated`` carries a ``ScheduledPost`` (TR-RT-03), so the composer
and the Schedule page patch their caches from events.

Conventions:
- Times are UTC instants. Posting times (``local_time``) and calendar dates are in the workspace
  time zone, which every calendar and posting-times answer states.
- One set of field names serves the draft body, 422 validation errors (FieldError) and checklist
  items, so the composer can mark the control to fix: ``targets``, ``targets.{i}``,
  ``targets.{i}.caption_override``, ``asset_ids``, ``asset_ids.{i}``, ``caption``,
  ``first_comment``, ``publish_at`` (``{i}`` is the index in the body's list).
- A post can be edited (PUT), unscheduled or moved while it is a draft or scheduled; once a
  target is claimed it is ``publishing`` and those answer 409 conflict ("Publishing started").
  PUT also takes a failed or canceled post, which becomes a draft again (Edit and retry,
  UX-SCR-13). Delete works in any status but publishing.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import Field

from socialhood.models.publishing import (
    CAPTION_MAX_CHARS,
    FIRST_COMMENT_MAX_CHARS,
    HASHTAG_GROUP_NAME_MAX_CHARS,
    MAX_ASSETS,
    MAX_HASHTAGS,
    SUGGESTED_HASHTAGS_MAX,
)
from socialhood.schemas.automations import StatusName as AutomationStatusName
from socialhood.schemas.automations import TriggerName
from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.inbox import ErrorInfo, MediaAssetOut, ScheduledMessage

ScheduledPostStatusName = Literal[
    "draft", "scheduled", "publishing", "published", "partially_published", "failed", "canceled"
]
PostFormatName = Literal["image", "carousel", "reel"]
TargetStatusName = Literal[
    "pending", "publishing", "container_created", "published", "failed", "canceled"
]
# The List view's tabs (UX-SCR-04):
# - scheduled: scheduled and publishing, soonest first
# - drafts: drafts, most recently edited first (also the right rail's Unscheduled drafts)
# - published: published and partially_published, newest first
# - failed: failed and canceled, newest first
ScheduledPostView = Literal["scheduled", "drafts", "published", "failed"]
BulkActionName = Literal["shift", "unschedule", "delete"]
CalendarLayer = Literal["posts", "messages", "slots"]
FirstCommentStatus = Literal["pending", "posted", "failed"]

# The composer's checklist (FR-PUB-10, UX-SCR-13), in this order:
# - accounts: at least one account; each is connected and can publish (Capability.PUBLISH)
# - media: at least one asset, and the assets make a format (1 image; 1 video, a Reel; 2 to 10
#   images and videos, a carousel)
# - media_files: each asset's type, size, aspect ratio and video length (TR-MED-02)
# - caption: the caption and each per-account caption up to 2,200 characters
# - hashtags: at most 30 hashtags in each caption
# - mentions: at most 20 @mentions in each caption
# - publishing_limit: room in each account's 24-hour publishing limit on the post's day
# - publish_at: at least 5 minutes from now (only when the post has a time)
ChecklistKey = Literal[
    "accounts",
    "media",
    "media_files",
    "caption",
    "hashtags",
    "mentions",
    "publishing_limit",
    "publish_at",
]
CHECKLIST_KEYS: tuple[ChecklistKey, ...] = (
    "accounts",
    "media",
    "media_files",
    "caption",
    "hashtags",
    "mentions",
    "publishing_limit",
    "publish_at",
)

# As typed: with or without "#", any case; stored without "#", lowercase. Letters, digits and
# underscores only (else a field error on ``hashtags.{i}``).
Hashtag = Annotated[str, Field(min_length=1, max_length=100)]


# ---- scheduled posts


class PostAsset(ResponseModel):
    """One image or video of the post (§5.10), in order. ``id`` is the media asset's id: the
    composer sends these ids back, reordered, in ``asset_ids``."""

    id: uuid.UUID
    resource_type: Literal["image", "video"]
    url: str  # the uploaded file (media_assets.secure_url)
    thumbnail_url: str | None = None  # images: the image; videos: a frame of the video
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    position: int  # 0-based


class FirstCommentResult(ResponseModel):
    """FR-PUB-11 for one account: the first comment is posted right after the post; a failure
    leaves the post published and is shown on it."""

    status: FirstCommentStatus
    platform_comment_id: str | None = None
    error: str | None = None


class ScheduledPostTarget(ResponseModel):
    """One account the post publishes to (§5.10 ScheduledPost.targets)."""

    social_account_id: uuid.UUID
    caption_override: str | None = None
    status: TargetStatusName
    platform_media_id: str | None = None
    permalink: str | None = None  # View on Instagram
    post_id: uuid.UUID | None = None  # the media_items row once published (Comments, analytics)
    published_at: datetime | None = None
    error: ErrorInfo | None = None  # Instagram's reason when failed (FR-PUB-06)
    # None when the post has no first comment or this target has not published.
    first_comment: FirstCommentResult | None = None


class ScheduledPostSummary(ResponseModel):
    """A post in the List view, on the calendar and in bulk results (UX-SCR-04)."""

    id: uuid.UUID
    status: ScheduledPostStatusName
    format: PostFormatName | None = None  # derived from the assets on save
    caption: str
    # A draft's time, if it has one (a calendar click); always set once scheduled.
    publish_at: datetime | None = None
    published_at: datetime | None = None  # when the first target published
    thumbnail_url: str | None = None  # the first asset's
    asset_count: int
    targets: list[ScheduledPostTarget]
    created_at: datetime
    updated_at: datetime


class LinkedAutomation(ResponseModel):
    """A comment automation scoped to this post (FR-AUT-18, the composer's Automation step)."""

    id: uuid.UUID
    name: str
    status: AutomationStatusName
    trigger: TriggerName | None = None


class ChecklistItem(ResponseModel):
    """One line of the checklist (FR-PUB-10). A check that passes appears once; a failing check
    appears once per failing element, ``field`` naming it (for example ``asset_ids.2``), so each
    item links to its fix."""

    key: ChecklistKey
    ok: bool
    message: str  # what is wrong, or what passed ("Caption within 2,200 characters")
    field: str | None = None


class ScheduledPost(ScheduledPostSummary):
    """GET …/scheduled-posts/{id} (§5.10 ScheduledPost, UX-SCR-13): the composer's post."""

    first_comment: str | None = None
    assets: list[PostAsset]
    automations: list[LinkedAutomation]
    checklist: list[ChecklistItem]
    ready: bool  # every checklist item passes: Schedule and Publish now are enabled
    created_by_user_id: uuid.UUID | None = None


class ScheduledPostList(ResponseModel):
    items: list[ScheduledPostSummary]
    next_cursor: str | None = None


class TargetIn(RequestModel):
    """An account to publish to, with an optional caption for it alone."""

    social_account_id: uuid.UUID
    caption_override: str | None = Field(default=None, max_length=CAPTION_MAX_CHARS)


class ScheduledPostDraft(RequestModel):
    """POST …/scheduled-posts (a new draft) and PUT …/scheduled-posts/{id} (replace the whole
    editable post; the composer autosaves). Everything may be empty on a draft: the checklist says
    what is missing. Accounts must be this workspace's (else 422 on ``targets.{i}``), assets this
    workspace's post uploads (else 422 on ``asset_ids.{i}``).

    On a scheduled post (Update schedule) the saved result must still pass the checklist and
    ``publish_at`` must be set and at least 5 minutes away (else 422 with every failing field);
    its targets stay pending."""

    targets: list[TargetIn] = Field(default_factory=list, max_length=10)
    asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_ASSETS)
    caption: str = Field(default="", max_length=CAPTION_MAX_CHARS)
    first_comment: str | None = Field(default=None, max_length=FIRST_COMMENT_MAX_CHARS)
    # A draft may keep a time (a calendar click); a scheduled post's time.
    publish_at: datetime | None = None


class ScheduleRequest(RequestModel):
    """POST …/schedule and …/reschedule: at least 5 minutes from now (else 422 on
    ``publish_at``)."""

    publish_at: datetime


class BulkScheduledPostRequest(RequestModel):
    """POST …/scheduled-posts/bulk (FR-PUB-14): ``shift`` moves each post by ``shift_minutes``
    (required, not 0), ``unschedule`` returns scheduled posts to draft, ``delete`` deletes."""

    ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    action: BulkActionName
    shift_minutes: int | None = Field(default=None, ge=-525_600, le=525_600)


class BulkSkipped(ResponseModel):
    """A post the action could not apply to, and why (``conflict``: publishing started or
    published; ``validation_error``: the shifted time would be less than 5 minutes away)."""

    id: uuid.UUID
    code: str
    message: str


class BulkScheduledPostResult(ResponseModel):
    updated: list[ScheduledPostSummary]
    deleted_ids: list[uuid.UUID]
    skipped: list[BulkSkipped]


# ---- calendar


class CalendarMessage(ScheduledMessage):
    """A scheduled DM on the Messages layer (FR-SMS-02), with its account for the filter."""

    social_account_id: uuid.UUID


class CalendarSlot(ResponseModel):
    """A free posting time (FR-PUB-09): a dashed queue slot in the Week view. A slot is free when
    no scheduled or publishing post of the account is within 30 minutes of it."""

    social_account_id: uuid.UUID
    at: datetime


class CalendarAccount(ResponseModel):
    """The right rail (UX-SCR-04): posts published in the last 24 hours against the account's
    publishing limit, and its next free posting time (None without posting times)."""

    social_account_id: uuid.UUID
    published_24h: int
    publishing_limit: int
    next_free_at: datetime | None = None


class Calendar(ResponseModel):
    """GET …/calendar: the range's items, ``start`` to ``end`` (dates in the workspace time zone,
    both included). Layers not asked for come back empty."""

    timezone: str
    start: date
    end: date
    # Posts with a time in the range, drafts with a time included (drawn muted).
    posts: list[ScheduledPostSummary]
    # Scheduled DMs sending in the range; canceled ones are left out.
    messages: list[CalendarMessage]
    # Free posting times from now to the end of the range, soonest first.
    slots: list[CalendarSlot]
    accounts: list[CalendarAccount]


# ---- posting times (FR-PUB-09, UX-SCR-14)


class PostingSlot(ResponseModel):
    weekday: int  # 0 = Monday … 6 = Sunday
    local_time: time  # workspace time zone, whole minutes


class PostingSlotIn(RequestModel):
    weekday: int = Field(ge=0, le=6)
    local_time: time  # "18:00"; seconds must be 0


class PostingSlotsUpdate(RequestModel):
    """PUT …/social-accounts/{id}/posting-slots replaces the account's weekly times (duplicates
    collapse). Posts already scheduled keep their times."""

    slots: list[PostingSlotIn] = Field(max_length=168)


class PostingSlots(ResponseModel):
    social_account_id: uuid.UUID
    timezone: str
    slots: list[PostingSlot]  # by weekday, then time
    next_free_at: list[datetime]  # the next 5 free times, soonest first ("Add to queue" preview)


# ---- hashtag groups (FR-PUB-12, UX-SCR-14)


class HashtagGroup(ResponseModel):
    id: uuid.UUID
    name: str
    hashtags: list[str]  # without "#", lowercase, in the order saved
    created_at: datetime
    updated_at: datetime


class HashtagGroupList(ResponseModel):
    """Every group of the workspace, by name."""

    items: list[HashtagGroup]


class HashtagGroupCreate(RequestModel):
    """A name unique in the workspace ignoring case (else 422 on ``name``); 1 to 30 hashtags
    (duplicates collapse)."""

    name: str = Field(min_length=1, max_length=HASHTAG_GROUP_NAME_MAX_CHARS)
    hashtags: list[Hashtag] = Field(min_length=1, max_length=MAX_HASHTAGS)


class HashtagGroupPatch(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=HASHTAG_GROUP_NAME_MAX_CHARS)
    hashtags: list[Hashtag] | None = Field(default=None, min_length=1, max_length=MAX_HASHTAGS)


# ---- media library (FR-PUB-13)


class MediaAssetList(ResponseModel):
    """Newest first."""

    items: list[MediaAssetOut]
    next_cursor: str | None = None


# ---- AI caption and hashtags (FR-PUB-02, T7.4)


class CaptionRequest(RequestModel):
    """POST …/ai/caption: ``write`` a caption from ``brief`` (what the post is about), or
    ``improve`` the ``caption`` given (required then). Written in the workspace's brand voice;
    costs AI credits (caption_generation)."""

    mode: Literal["write", "improve"] = "write"
    brief: str | None = Field(default=None, max_length=500)
    caption: str | None = Field(default=None, max_length=CAPTION_MAX_CHARS)


class CaptionSuggestion(ResponseModel):
    caption: str  # at most 2,200 characters


class HashtagSuggestionRequest(RequestModel):
    """POST …/ai/hashtags: hashtags for the caption, leaving out those already in it and in
    ``exclude``; costs AI credits (caption_generation)."""

    caption: str = Field(min_length=1, max_length=CAPTION_MAX_CHARS)
    count: int = Field(default=SUGGESTED_HASHTAGS_MAX, ge=1, le=SUGGESTED_HASHTAGS_MAX)
    exclude: list[Hashtag] = Field(default_factory=list, max_length=MAX_HASHTAGS)


class HashtagSuggestion(ResponseModel):
    hashtags: list[str]  # without "#", lowercase, at most ``count``
