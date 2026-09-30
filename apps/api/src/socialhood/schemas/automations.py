"""Automation shapes (§5.10 Automation, extended for the redesigned editor: UX-SCR-02, 03, 11, 12).

The P4 contract. Activation failures are 422 validation_error with one entry per missing or invalid
field (FR-AUT-02), so the editor can mark each step.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

TriggerName = Literal["dm_keyword", "comment_keyword", "comment_any"]
MatchModeName = Literal["word", "exact", "contains"]
ActionName = Literal["send_message", "ai_reply"]
PostScopeName = Literal["all", "selected", "next_post"]
SurgeOrderName = Literal["oldest_first", "newest_first", "public_only"]
StatusName = Literal["draft", "active", "paused"]
# What the list and editor show: Scheduled before starts_at, Ended after ends_at (FR-AUT-17).
DisplayStatus = Literal["draft", "scheduled", "active", "paused", "ended"]
RunResultName = Literal[
    "queued",
    "sent",
    "partial",
    "failed",
    "skipped_cooldown",
    "skipped_expired",
    "escalated",
    "awaiting_reply",  # tap first: the opening went out; the message follows their tap or reply
    "skipped_read_only",  # the account is read-only after a downgrade (FR-BIL-07)
]
TemplateCategory = Literal["grow", "sell", "support"]


class LinkButton(ResponseModel):
    title: str
    url: str


class LinkButtonIn(RequestModel):
    title: str = Field(min_length=1, max_length=20)
    url: str = Field(min_length=1, max_length=2000)  # https, checked on activation


class PostRef(ResponseModel):
    """A post an automation is scoped to: a synced post, or a scheduled one not yet published."""

    media_item_id: uuid.UUID | None = None
    scheduled_post_id: uuid.UUID | None = None
    caption: str | None = None
    thumbnail_url: str | None = None
    media_type: str | None = None
    posted_at: datetime | None = None


class AutomationListStats(ResponseModel):
    runs_7d: int
    daily_7d: list[int]  # oldest first, for the 60 px trend line
    last_run_at: datetime | None = None


class QueueInfo(ResponseModel):
    """FR-AUT-10: private replies waiting in the account's 750/hour queue for this automation."""

    waiting: int
    eta_minutes: int | None = None  # the account queue at the private-reply bucket's rate
    order: SurgeOrderName


class OverlapWarning(ResponseModel):
    keyword: str
    automation_id: uuid.UUID
    automation_name: str
    this_runs_first: bool


class Automation(ResponseModel):
    id: uuid.UUID
    name: str
    status: StatusName
    display_status: DisplayStatus
    social_account_id: uuid.UUID | None = None
    trigger: TriggerName | None = None
    keywords: list[str]
    match_mode: MatchModeName
    action: ActionName | None = None
    message_text: str | None = None
    message_buttons: list[LinkButton]
    message_media_asset_id: uuid.UUID | None = None
    message_media_url: str | None = None
    ai_instructions: str | None = None
    public_reply_texts: list[str]
    post_scope: PostScopeName
    posts: list[PostRef]
    cooldown_hours: int
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    surge_order: SurgeOrderName
    # Tap first (FR-AUT-21, comment triggers) and the follow nudge (FR-AUT-22).
    confirm_first: bool
    opening_text: str | None = None
    opening_button: str | None = None
    follow_nudge: bool
    follow_nudge_text: str | None = None
    priority: int
    template_key: str | None = None
    activated_at: datetime | None = None
    paused_at: datetime | None = None
    last_run_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    stats: AutomationListStats
    queue: QueueInfo
    missing_for_activation: list[str]  # field names, e.g. ["keywords", "message_text"]
    overlaps: list[OverlapWarning]


class AutomationList(ResponseModel):
    items: list[Automation]
    next_cursor: str | None = None


class AutomationsSummary(ResponseModel):
    """UX-SCR-02's figures strip, for the last 7 days."""

    active: int
    runs_7d: int
    dms_sent_7d: int
    waiting: int
    longest_eta_minutes: int | None = None


class AutomationCreate(RequestModel):
    """A draft, blank or from a template (FR-AUT-12)."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    template_key: str | None = Field(default=None, max_length=60)
    social_account_id: uuid.UUID | None = None


class AutomationDefinition(RequestModel):
    """PUT …/automations/{id}: the whole editable definition (autosaved, F-11). Drafts may be
    incomplete; activation checks completeness."""

    name: str = Field(min_length=1, max_length=80)
    social_account_id: uuid.UUID | None = None
    trigger: TriggerName | None = None
    keywords: list[str] = Field(default_factory=list, max_length=50)
    match_mode: MatchModeName = "word"
    action: ActionName | None = None
    message_text: str | None = Field(default=None, max_length=4000)  # bytes checked on activation
    message_buttons: list[LinkButtonIn] = Field(default_factory=list, max_length=3)
    message_media_asset_id: uuid.UUID | None = None
    ai_instructions: str | None = Field(default=None, max_length=2000)
    public_reply_texts: list[str] = Field(default_factory=list, max_length=5)
    post_scope: PostScopeName = "all"
    media_item_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    scheduled_post_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    cooldown_hours: int = Field(default=24, ge=0, le=72)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    surge_order: SurgeOrderName = "oldest_first"
    # Tap first (FR-AUT-21): the private reply is the opening with a quick-reply button; the
    # message follows their tap or reply. Comment triggers only.
    confirm_first: bool = False
    opening_text: str | None = Field(default=None, max_length=2000)  # bytes checked on activation
    opening_button: str | None = Field(default=None, max_length=20)
    # Follow nudge (FR-AUT-22): after the message, only to people who don't follow the account.
    follow_nudge: bool = False
    follow_nudge_text: str | None = Field(default=None, max_length=300)


class PrioritiesUpdate(RequestModel):
    social_account_id: uuid.UUID
    ordered_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class BulkPause(RequestModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class AutomationTemplate(ResponseModel):
    key: str
    name: str
    outcome: str  # one line, e.g. "Send your link to everyone who comments LINK"
    category: TemplateCategory
    icon: str  # a lucide icon name
    trigger: TriggerName
    action: ActionName
    requires_paid_plan: bool


class AutomationTemplateList(ResponseModel):
    items: list[AutomationTemplate]


class RunContact(ResponseModel):
    id: uuid.UUID
    display_name: str | None = None
    username: str | None = None
    profile_picture_url: str | None = None


class RunError(ResponseModel):
    code: str
    message: str


class AutomationRun(ResponseModel):
    id: uuid.UUID
    created_at: datetime
    trigger_kind: Literal["dm", "comment"]
    trigger_text: str | None = None  # excerpt of the message or comment
    matched_keyword: str
    result: RunResultName
    contact: RunContact | None = None
    conversation_id: uuid.UUID | None = None
    private_reply_message_id: uuid.UUID | None = None
    public_reply_platform_id: str | None = None
    contact_replied_at: datetime | None = None
    confirmed_at: datetime | None = None  # tap first: when their tap or reply released it
    follows_business: bool | None = None  # when the message went out; None: unknown
    nudge_message_id: uuid.UUID | None = None
    error: RunError | None = None


class AutomationRunList(ResponseModel):
    items: list[AutomationRun]
    next_cursor: str | None = None


class DailyRuns(ResponseModel):
    date: date
    runs: int
    failures: int


class SkippedCounts(ResponseModel):
    cooldown: int
    expired: int
    outside_window: int


class AutomationStats(ResponseModel):
    """FR-AUT-16 / UX-SCR-12, for the last 7 or 30 days."""

    days: Literal[7, 30]
    runs: int
    dms_sent: int
    public_replies: int
    replied_24h: int
    failures: int
    skipped: SkippedCounts
    queued_now: int
    daily: list[DailyRuns]
    # Tap first and the follow nudge (FR-AUT-21, 22): runs whose opening was answered, runs
    # still waiting for an answer now, and nudges sent.
    tapped: int = 0
    awaiting_now: int = 0
    nudged: int = 0


class AutomationTest(RequestModel):
    kind: Literal["dm", "comment"]
    text: str = Field(min_length=1, max_length=2000)
    media_item_id: uuid.UUID | None = None  # a comment on this post (post scope)
    first_name: str | None = Field(default=None, max_length=60)  # sample for the preview
    username: str | None = Field(default=None, max_length=60)


class WinningAutomation(ResponseModel):
    id: uuid.UUID
    name: str


class AutomationTestResult(ResponseModel):
    """What would happen; nothing is sent (T4.3)."""

    matched: bool  # this automation matches the text
    matched_keyword: str | None = None
    winner: WinningAutomation | None = None  # the automation that would actually run
    reason: str | None = None  # why this one would not run, in plain words
    rendered_message: str | None = None
    rendered_public_reply: str | None = None
    rendered_opening: str | None = None  # tap first: the private reply before the message
    rendered_nudge: str | None = None  # the follow nudge, as a non-follower would get it
