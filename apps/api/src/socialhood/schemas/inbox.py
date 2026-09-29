"""Inbox shapes (§5.10): conversations, messages, attachments, scheduled messages, media assets.

These are the P3 contract. The read, send, real-time and scheduling code all return these, and
real-time events carry the same projections (TR-RT-03). Analysis and suggestion shapes are defined
now so the contract is stable; they stay empty until P5.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

PlatformName = Literal["instagram", "whatsapp"]
MessageSourceName = Literal["customer", "human", "ai_auto", "automation", "native_app", "system"]
MessageKindName = Literal[
    "text",
    "image",
    "video",
    "audio",
    "file",
    "sticker",
    "story_mention",
    "story_reply",
    "share",
    "template",
    "location",
    "unsupported",
    "system",
]
DirectionName = Literal["inbound", "outbound", "system"]
MessageStatusName = Literal["received", "queued", "sending", "sent", "delivered", "read", "failed"]
AiModeName = Literal["off", "suggest", "auto"]
EscalationReason = Literal[
    "refund",
    "legal",
    "complaint",
    "negative_sentiment",
    "abuse",
    "account_or_payment",
    "human_requested",
    "low_confidence",
    "out_of_knowledge",
    "window_closed",
    "policy_keyword",
    "output_blocked",
]
IntentName = Literal[
    "pricing",
    "product_inquiry",
    "purchase",
    "order_status",
    "shipping",
    "support",
    "complaint",
    "refund",
    "feedback",
    "collaboration",
    "greeting",
    "spam",
    "other",
]
Signal = Literal["needs_you", "complaint", "closing_soon", "lead", "negative"]
WindowState = Literal["open", "human_agent", "template_only", "closed"]
InboxView = Literal["all", "unread", "needs_reply", "leads", "ai_handled", "archived"]


class ErrorInfo(ResponseModel):
    code: str
    message: str


# ---- contacts and conversations


class ContactSummary(ResponseModel):
    id: uuid.UUID
    display_name: str | None = None
    username: str | None = None
    profile_picture_url: str | None = None


class ContactDetail(ContactSummary):
    first_seen_at: datetime
    platform_user_id: str
    follows_business: bool | None = None  # FR-AUT-22; None until known


class ConversationListItem(ResponseModel):
    id: uuid.UUID
    platform: PlatformName
    social_account_id: uuid.UUID
    contact: ContactSummary
    status: Literal["open", "archived"]
    last_message_at: datetime | None = None
    last_message_preview: str | None = None
    last_message_direction: DirectionName | None = None
    last_message_source: MessageSourceName | None = None
    last_message_kind: MessageKindName | None = None
    unread_count: int
    awaiting_reply: bool
    needs_human: bool
    needs_human_reason: EscalationReason | None = None
    signal: Signal | None = None  # computed, in UX-INB-04's priority order
    reply_window_closes_at: datetime | None = None  # for the "Closing in 3h" chip
    lead_score: int | None = None


class ReplyWindow(ResponseModel):
    state: WindowState
    closes_at: datetime | None = None


class ConversationAi(ResponseModel):
    effective_mode: AiModeName
    override: AiModeName | None = None
    paused_until: datetime | None = None


class MessageAnalysis(ResponseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    intent: IntentName
    sentiment: Literal["positive", "neutral", "negative"]
    sentiment_score: float
    priority: Literal["critical", "high", "medium", "low"]
    lead_score: int
    language: str
    topics: list[str]
    needs_reply: bool
    needs_human: bool
    needs_human_reason: EscalationReason | None = None
    corrected: bool
    created_at: datetime


class SuggestionSource(ResponseModel):
    id: uuid.UUID
    title: str


class Suggestion(ResponseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    status: Literal[
        "pending", "sent", "edited_sent", "dismissed", "superseded", "expired", "failed"
    ]
    can_answer: bool
    reply_text: str | None = None
    missing_info: str | None = None
    low_confidence: bool
    sources: list[SuggestionSource]
    regenerations_left: int
    created_at: datetime


class ConversationSummary(ResponseModel):
    text: str
    next_step: str | None = None
    updated_at: datetime


class ConversationAccount(ResponseModel):
    id: uuid.UUID
    username: str | None = None
    display_name: str | None = None
    status: str


class Conversation(ConversationListItem):
    contact: ContactDetail
    reply_window: ReplyWindow
    ai: ConversationAi
    latest_analysis: MessageAnalysis | None = None  # P5
    pending_suggestion: Suggestion | None = None  # P5
    summary: ConversationSummary | None = None  # P5
    social_account: ConversationAccount
    scheduled_count: int
    last_inbound_at: datetime | None = None  # the customer's last message (reply window)


class ConversationList(ResponseModel):
    items: list[ConversationListItem]
    next_cursor: str | None = None


class InboxCounts(ResponseModel):
    """The Inbox nav badge (FR-INB-04) and view chips."""

    unread: int
    needs_reply: int
    needs_you: int


class ConversationPatch(RequestModel):
    status: Literal["open", "archived"] | None = None
    ai_mode_override: AiModeName | None = None
    clear_ai_mode_override: bool = False


# ---- messages


class Attachment(ResponseModel):
    id: str
    type: Literal["image", "video", "audio", "file", "sticker", "story", "share"]
    url: str  # storage URL once re-hosted (TR-MED-03), else the platform URL
    mime_type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    filename: str | None = None
    thumbnail_url: str | None = None
    permalink: str | None = None
    expired: bool | None = None


class TemplateInfo(ResponseModel):
    name: str
    language: str
    params: list[str]


class Actor(ResponseModel):
    id: uuid.UUID
    name: str | None = None


class AutomationRef(ResponseModel):
    id: uuid.UUID
    name: str


class MessageButton(ResponseModel):
    title: str
    url: str


class QuickReplyOut(ResponseModel):
    """A quick reply offered with the text (tap first, FR-AUT-21); shown, not tappable, here."""

    title: str


class Reaction(ResponseModel):
    emoji: str
    by: Literal["customer", "business"]
    at: datetime


class Message(ResponseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    client_id: uuid.UUID | None = None
    direction: DirectionName
    source: MessageSourceName
    kind: MessageKindName
    text: str | None = None
    attachments: list[Attachment]
    template: TemplateInfo | None = None
    buttons: list[MessageButton] = Field(default_factory=list)  # link buttons (automation DMs)
    quick_replies: list[QuickReplyOut] = Field(default_factory=list)  # tap first openings
    status: MessageStatusName | None = None
    error: ErrorInfo | None = None
    occurred_at: datetime
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    edited_at: datetime | None = None  # the customer edited it; ``text`` is the latest version
    deleted_at: datetime | None = None  # the customer unsent it; text and attachments are gone
    sent_by: Actor | None = None
    automation: AutomationRef | None = None  # P4
    suggestion_id: uuid.UUID | None = None
    human_agent_tag: bool
    reactions: list[Reaction]


class MessageList(ResponseModel):
    """Newest first; ``next_cursor`` fetches older messages."""

    items: list[Message]
    next_cursor: str | None = None


class TemplateSend(RequestModel):
    name: str = Field(min_length=1, max_length=512)
    language: str = Field(min_length=2, max_length=15)
    params: list[str] = Field(default_factory=list, max_length=20)


class SendMessage(RequestModel):
    """POST …/conversations/{id}/messages with an Idempotency-Key header (TR-API-05)."""

    client_id: uuid.UUID
    text: str | None = Field(default=None, max_length=4096)
    attachment_asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    template: TemplateSend | None = None  # WhatsApp outside the window
    sticker: Literal["like_heart"] | None = None  # Instagram's heart sticker, on its own
    sticker_asset_id: uuid.UUID | None = None  # a WhatsApp sticker: an uploaded 512x512 WebP
    suggestion_id: uuid.UUID | None = None  # P5: sending a suggestion


# ---- scheduled messages (F-10)


class ScheduledContact(ResponseModel):
    display_name: str | None = None
    username: str | None = None
    profile_picture_url: str | None = None


class ScheduledMessage(ResponseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    text: str
    attachment_asset_ids: list[uuid.UUID]
    send_at: datetime
    status: Literal["scheduled", "sending", "sent", "failed", "canceled", "expired"]
    error: ErrorInfo | None = None
    contact: ScheduledContact
    platform: PlatformName


class ScheduledMessageList(ResponseModel):
    items: list[ScheduledMessage]
    next_cursor: str | None = None


class ScheduledMessageCreate(RequestModel):
    text: str = Field(min_length=1, max_length=2000)
    attachment_asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    send_at: datetime


class ScheduledMessagePatch(RequestModel):
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    send_at: datetime | None = None


# ---- media assets (TR-MED-01, TR-MED-02)

AssetPurposeName = Literal["post", "message", "knowledge"]
ResourceTypeName = Literal["image", "video", "raw"]


class UploadSignatureRequest(RequestModel):
    resource_type: ResourceTypeName
    purpose: AssetPurposeName


class UploadSignature(ResponseModel):
    cloud_name: str
    api_key: str
    timestamp: int
    folder: str
    signature: str
    upload_url: str


class MediaAssetCreate(RequestModel):
    public_id: str = Field(min_length=1, max_length=512)
    resource_type: ResourceTypeName


class MediaAssetOut(ResponseModel):
    id: uuid.UUID
    public_id: str
    resource_type: ResourceTypeName
    purpose: str
    format: str | None = None
    mime_type: str | None = None
    original_filename: str | None = None
    secure_url: str | None = None
    bytes: int
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    created_at: datetime
