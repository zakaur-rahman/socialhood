"""Social account, notification and data-deletion shapes (§5.10)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from socialhood.schemas.common import RequestModel, ResponseModel

CapabilityName = Literal[
    "dm_send",
    "dm_attachments",
    "read_receipts",
    "human_agent",
    "templates",
    "conversation_backfill",
    "comments",
    "private_reply",
    "publish",
    "post_insights",
    "account_insights",
]


class SocialAccountOut(ResponseModel):
    """Never the token itself (SEC-02)."""

    id: uuid.UUID
    platform: Literal["instagram", "whatsapp", "facebook", "web"]
    display_name: str | None = None
    username: str | None = None
    profile_picture_url: str | None = None
    phone_number: str | None = None
    status: Literal["active", "needs_reconnect", "disconnected", "error"]
    last_error: str | None = None
    ai_mode: Literal["off", "suggest", "auto"]
    ai_analysis_enabled: bool
    auto_hide_spam: bool
    connected_at: datetime | None = None
    token_expires_at: datetime | None = None
    # When Social Hood last pulled the account's posts (every 6 h) or conversation history from
    # the platform; null when it never has (WhatsApp has neither: its messages only arrive).
    last_synced_at: datetime | None = None
    capabilities: list[CapabilityName]
    sandbox: bool = False
    # Its data is being deleted (C-067): disconnected, and gone once the purge finishes.
    deleting: bool = False


class SocialAccountList(ResponseModel):
    items: list[SocialAccountOut]
    next_cursor: str | None = None


class SocialAccountPatch(RequestModel):
    ai_mode: Literal["off", "suggest", "auto"] | None = None
    ai_analysis_enabled: bool | None = None
    auto_hide_spam: bool | None = None
    display_name: str | None = Field(default=None, max_length=80)


class ConnectStart(ResponseModel):
    authorize_url: str


class InstagramConnectComplete(RequestModel):
    """The nonce the OAuth callback put in the Connections page's URL (?instagram=…, X-1)."""

    nonce: str = Field(min_length=1, max_length=128)


class SandboxAccountCreate(RequestModel):
    """Which sandbox account to make (dev and e2e): an Instagram account, a Facebook Page (GR-29)
    or a WhatsApp number with approved templates (GR-23). No body makes an Instagram one."""

    platform: Literal["instagram", "facebook", "whatsapp"] = "instagram"


class SandboxCartItem(RequestModel):
    retailer_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(default=1, ge=1, le=999)
    price: str | None = Field(default=None, max_length=24)


class SandboxInbound(RequestModel):
    """A fake Instagram event, or a fake Facebook Page event for a sandbox Page (dev and e2e).
    GR-01 adds a referral without a message (an entry link opened, or an ad tapped), a tapped
    postback (an ice breaker), an opt-in and a Live comment; a DM can carry an ad referral (its
    first message from an ad). GR-06 and GR-07 add a
    story reply, a story like (the heart) and a story mention. A Facebook Page takes a DM, a
    comment on a post, a referral, a postback and an opt-in; the kinds it doesn't have are
    refused (GR-29).

    GR-23 adds two kinds for a sandbox WhatsApp number, and lets a ``dm`` be a WhatsApp customer's
    message (``from_id`` is their number): ``status`` is a delivery status for the last message we
    sent that contact (``delivery_status``, with ``error_code`` and ``error_text`` for a failure),
    and ``quality`` a ``phone_number_quality_update`` (``quality_event``, ``tier``)."""

    account_id: uuid.UUID
    kind: Literal[
        "dm",
        "comment",
        "live_comment",
        "referral",
        "postback",
        "optin",
        "story_reply",
        "story_like",
        "story_mention",
        "status",
        "quality",
        "order",
    ]
    # The message, comment, story reply or postback title. A referral, an opt-in, a story like and
    # a story mention have none.
    text: str | None = Field(default=None, min_length=1, max_length=1000)
    from_id: str | None = Field(default=None, max_length=64)
    from_username: str | None = Field(default=None, max_length=64)
    # A DM that is a tapped quick reply (tap first, FR-AUT-21): its payload, e.g. "shr:{run_id}".
    quick_reply_payload: str | None = Field(default=None, max_length=1000)
    # A postback's payload (an ice breaker, GR-11).
    postback_payload: str | None = Field(default=None, max_length=1000)
    # A referral (kind "referral", or a DM from an ad): an ad (ad_id) or an entry link (ref).
    referral_source: Literal["ad", "link"] | None = None
    ref: str | None = Field(default=None, max_length=200)
    ad_id: str | None = Field(default=None, max_length=64)
    ad_title: str | None = Field(default=None, max_length=200)
    # A story reply or a story like: the story it answers (the ids the sandbox lists as stories).
    story_id: str | None = Field(default=None, max_length=64)
    # A comment or Live comment that is this many seconds old when it arrives (a late webhook):
    # GR-10 uses it to show a Live comment arriving after the broadcast ended.
    age_seconds: int | None = Field(default=None, ge=0, le=7 * 86400)
    # GR-23, WhatsApp only: a delivery status for the last message sent to ``from_id``.
    delivery_status: Literal["sent", "delivered", "read", "failed"] | None = None
    error_code: int | None = Field(default=None, ge=1, le=999999)
    error_text: str | None = Field(default=None, max_length=300)
    # GR-23, WhatsApp only: a number's quality or tier change.
    quality_event: Literal["ONBOARDING", "UPGRADE", "DOWNGRADE", "FLAGGED", "UNFLAGGED"] | None = (
        None
    )
    tier: str | None = Field(default=None, max_length=32)
    # GR-33, WhatsApp only: the cart of an ``order`` message (retailer ids are our variant or
    # product ids) and the customer's note (``text``).
    cart: list[SandboxCartItem] | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def _needs_text(self) -> SandboxInbound:
        if self.kind == "status" and (not self.from_id or self.delivery_status is None):
            raise ValueError("from_id and delivery_status are required for a status")
        if self.kind == "quality" and self.quality_event is None:
            raise ValueError("quality_event is required for a quality update")
        if (
            self.kind in ("dm", "comment", "live_comment", "postback", "story_reply")
            and not self.text
        ):
            raise ValueError("text is required for a DM, a comment, a story reply or a postback")
        if self.kind == "order" and not self.cart:
            raise ValueError("cart is required for an order")
        if self.kind == "referral" and self.referral_source is None:
            raise ValueError("referral_source is required for a referral")
        return self


class SandboxInboundResult(ResponseModel):
    stored: int


class NotificationOut(ResponseModel):
    id: uuid.UUID
    type: str
    severity: Literal["info", "warning", "critical"]
    title: str
    body: str
    link: str | None = None
    read_at: datetime | None = None
    created_at: datetime


class NotificationList(ResponseModel):
    items: list[NotificationOut]
    next_cursor: str | None = None
    unread_count: int


class MarkRead(RequestModel):
    ids: list[uuid.UUID] | None = Field(default=None, max_length=200)
    all: bool = False


class DataDeletionStatus(ResponseModel):
    confirmation_code: str
    # received (pending) → processing → completed; failed while a purge is being retried.
    status: Literal["received", "processing", "completed", "failed"]
    created_at: datetime
    completed_at: datetime | None = None
