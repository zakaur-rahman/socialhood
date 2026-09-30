"""Me, workspace and overview shapes (§5.10 has none for these; see docs/QUESTIONS.md Q-007)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.inbox import ContactSummary, EscalationReason, IntentName, PlatformName
from socialhood.schemas.posts import CommentStats

RoleName = Literal["owner", "admin", "agent"]
PlanName = Literal["free", "pro", "max"]


class WorkspaceSummary(ResponseModel):
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    role: RoleName
    plan: PlanName


class Me(ResponseModel):
    id: uuid.UUID
    email: str
    name: str | None = None
    avatar_url: str | None = None
    last_workspace_id: uuid.UUID | None = None
    workspaces: list[WorkspaceSummary]


class WorkspaceList(ResponseModel):
    items: list[WorkspaceSummary]
    next_cursor: str | None = None


class WorkspaceOut(ResponseModel):
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    reply_language: str
    status: Literal["active", "deleting"]
    role: RoleName
    plan: PlanName
    automation_disclosure: str | None = None
    checklist_dismissed_at: datetime | None = None
    created_at: datetime
    member_count: int  # Settings → Workspace's summary (C-066)


class WorkspacePatch(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    slug: str | None = Field(default=None, min_length=3, max_length=48)
    timezone: str | None = Field(default=None, max_length=64)
    reply_language: str | None = Field(default=None, max_length=35)
    automation_disclosure: str | None = Field(default=None, max_length=60)
    checklist_dismissed: bool | None = None


ChecklistKey = Literal["connect_account", "add_knowledge", "choose_ai_mode", "create_automation"]


class ChecklistStep(ResponseModel):
    key: ChecklistKey
    done: bool


class Checklist(ResponseModel):
    dismissed: bool
    completed: int
    steps: list[ChecklistStep]


OverviewPreset = Literal["7d", "30d"]  # ?range=
OverviewRange = Literal["7d", "30d", "custom"]  # "custom": ?from=&to=
PriorityName = Literal["critical", "high", "medium", "low"]


class OverviewPeriod(ResponseModel):
    """One period's flows (services/overview_stats.py has the definitions, shared with the weekly
    digest): local days ``since`` to ``until``, both included, in the workspace's time zone.
    Percentages are 0 to 100 with one decimal, None when there is nothing to divide."""

    since: date
    until: date
    messages_received: int
    conversations: int  # where a customer wrote in the period
    conversations_replied: int
    reply_rate: float | None
    handled_by_ai: int  # replied conversations answered only by Auto or automations
    handled_by_ai_rate: float | None  # of the replied conversations
    first_responses: int  # customer turns answered in the period
    median_first_response_s: int | None
    comments_received: int


class SentimentSplit(ResponseModel):
    """Messages (customer, received) or comments (not deleted) in the period by sentiment.
    ``positive + neutral + negative`` are analysed and not spam; the shares are of that sum."""

    total: int
    analysed: int
    positive: int
    neutral: int
    negative: int
    spam: int
    positive_pct: float | None
    neutral_pct: float | None
    negative_pct: float | None


class IntentCount(ResponseModel):
    intent: IntentName
    count: int


class QuestionCount(ResponseModel):
    topic: str
    asked: int


class OverviewPost(ResponseModel):
    """One of the posts with the most comments in the period; ``stats`` is the post's own
    comment split, as on the Comments page."""

    id: uuid.UUID
    social_account_id: uuid.UUID
    media_type: str
    caption: str | None
    media_url: str | None
    thumbnail_url: str | None
    permalink: str | None
    posted_at: datetime
    comments: int  # made in the period
    stats: CommentStats
    # (likes + comments + shares + saves) / reach in %, from the post's latest metric snapshot
    # captured in the period; None without one (or without reach). Never estimated.
    engagement_rate: float | None


class OverviewEngagement(ResponseModel):
    """The mean engagement rate of the most commented posts that have one (``posts`` of them)."""

    rate: float
    posts: int


class OverviewGap(ResponseModel):
    """The open knowledge gap asked most recently: Home's View thread and Train AI. ``question``
    is the customer's newest example message (the topic when there is none); the conversation
    and message are where it came from, None for a comment's gap or a deleted message."""

    id: uuid.UUID
    topic: str
    question: str
    asked: int
    last_seen_at: datetime
    conversation_id: uuid.UUID | None
    message_id: uuid.UUID | None


class PriorityConversation(ResponseModel):
    """One row of Home's Live Priority Queue (services/priority_queue.py has the rules)."""

    id: uuid.UUID
    platform: PlatformName
    contact: ContactSummary
    last_customer_message: str | None  # clipped; "Photo" and the like for attachments
    last_customer_message_at: datetime | None
    waiting_since: datetime | None  # when the customer's unanswered turn began
    needs_you: bool
    needs_human_reason: EscalationReason | None
    awaiting_reply: bool
    has_pending_suggestion: bool  # a pending suggested reply with a draft (can answer)
    window_closes_at: datetime | None  # the reply window, None when closed
    lead_score: int | None
    priority: PriorityName | None


class AccountAttention(ResponseModel):
    id: uuid.UUID
    platform: PlatformName
    username: str | None
    status: Literal["needs_reconnect", "error"]


class Overview(ResponseModel):
    """GET …/overview (FR-HOME-01, UX-SCR-01). Flows cover ``current`` (the range: 7 or 30 local
    days up to and including today, or the custom ``from``..``to``) and ``previous`` (as many days
    just before it); states are as of now."""

    range: OverviewRange
    days: int  # local days in ``current``
    timezone: str
    checklist: Checklist
    # states
    needs_reply: int  # the inbox's "Needs reply" view
    needs_you: int  # open conversations the AI handed to a person
    # When the longest-waiting "Needs reply" conversation's unanswered turn began.
    oldest_waiting_since: datetime | None
    knowledge_gaps_open: int = 0  # FR-KB-06: Home's "Questions the AI couldn't answer" (T5.10)
    top_questions: list[QuestionCount]  # most asked first
    latest_gap: OverviewGap | None
    accounts_needing_attention: list[AccountAttention]
    accounts_connected: int  # active accounts
    platforms_connected: list[PlatformName]  # of the active accounts
    priority_queue: list[PriorityConversation]  # up to 5
    # flows
    messages_today: int
    current: OverviewPeriod
    previous: OverviewPeriod
    top_intents: list[IntentCount]  # other and spam left out
    message_sentiment: SentimentSplit
    comment_sentiment: SentimentSplit
    top_posts: list[OverviewPost]
    top_posts_engagement: OverviewEngagement | None
