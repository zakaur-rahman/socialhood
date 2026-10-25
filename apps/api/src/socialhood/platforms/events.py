"""Typed inbound events (TR-PL-12). Each platform's parser turns one stored webhook event into
one of these; everything after the parser is platform-agnostic (services/ingest.py, P3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, kw_only=True)
class InboundMediaRef:
    kind: Literal["image", "video", "audio", "file", "sticker", "story", "share", "unsupported"]
    url: str | None = None
    media_id: str | None = None  # WhatsApp media id
    mime_type: str | None = None
    filename: str | None = None  # documents


@dataclass(frozen=True, kw_only=True)
class ReferralInfo:
    """How a conversation was entered (GR-01): an ad, an entry link (ig.me ``ref``) or something
    else Meta names. ``source`` is ours; ``platform_source`` is Meta's own value ("ADS", the
    ig.me link, WhatsApp's ``source_type``)."""

    source: Literal["ad", "link", "other"]
    ref: str | None = None  # ig.me ?ref= value
    ad_id: str | None = None
    ad_title: str | None = None
    ctwa_clid: str | None = None  # WhatsApp click id, for a later Conversions API (GR-09)
    platform_source: str | None = None


@dataclass(frozen=True, kw_only=True)
class Inbound:
    account_ref: str  # Instagram entry.id, WhatsApp metadata.phone_number_id
    occurred_at: datetime  # the platform's timestamp, not arrival time


@dataclass(frozen=True)
class CartItem:
    """One line of a customer's WhatsApp cart (GR-33): the catalogue item's retailer id, how many
    and the price the customer saw (a decimal text, in ``currency``)."""

    retailer_id: str
    quantity: int
    price: str | None = None
    currency: str | None = None


@dataclass(frozen=True)
class CartOrder:
    """A customer's WhatsApp cart sent as an ``order`` message (GR-33)."""

    catalog_id: str | None
    note: str | None
    items: tuple[CartItem, ...]


@dataclass(frozen=True, kw_only=True)
class InboundMessage(Inbound):
    contact_ref: str  # IGSID or WhatsApp wa_id
    contact_name: str | None
    platform_message_id: str
    kind: str
    text: str | None
    attachments: tuple[InboundMediaRef, ...] = field(default_factory=tuple)
    reply_to_id: str | None = None
    is_echo: bool = False  # sent by the business outside Amplychat
    quick_reply_payload: str | None = None  # the quick reply they tapped (FR-AUT-21)
    postback_payload: str | None = None  # the ice breaker or button they tapped (GR-01, GR-11)
    referral: ReferralInfo | None = None  # an ad the message came from (GR-01)
    order: CartOrder | None = None  # a WhatsApp cart (GR-33)


@dataclass(frozen=True, kw_only=True)
class InboundComment(Inbound):
    platform_comment_id: str
    media_id: str
    parent_id: str | None
    author_ref: str
    author_username: str | None
    text: str
    is_live: bool = False  # a comment on a live broadcast (GR-01; automations in GR-10)


@dataclass(frozen=True, kw_only=True)
class Referral(Inbound):
    """Someone opened the conversation from an entry link or an ad without sending a message yet
    (Instagram ``messaging_referral``). Recorded on the contact; it becomes the conversation's
    entry when the conversation starts (GR-01)."""

    contact_ref: str
    referral: ReferralInfo


@dataclass(frozen=True, kw_only=True)
class OptIn(Inbound):
    """Someone agreed to receive messages from the account (Instagram ``messaging_optins``).
    Parsed now and kept in the stored webhook event; GR-02 records it as consent."""

    contact_ref: str
    topic: str | None = None
    status: str | None = None


@dataclass(frozen=True, kw_only=True)
class Reaction(Inbound):
    contact_ref: str
    platform_message_id: str
    emoji: str | None  # None = removed


@dataclass(frozen=True, kw_only=True)
class ReadReceipt(Inbound):
    contact_ref: str
    last_read_message_id: str | None


@dataclass(frozen=True, kw_only=True)
class MessageEdit(Inbound):
    platform_message_id: str
    text: str


@dataclass(frozen=True, kw_only=True)
class MessageDeleted(Inbound):
    """The customer unsent a message."""

    platform_message_id: str


@dataclass(frozen=True, kw_only=True)
class DeliveryStatus(Inbound):
    platform_message_id: str
    status: Literal["sent", "delivered", "read", "failed"]
    error_code: str | None = None


@dataclass(frozen=True, kw_only=True)
class Unsupported(Inbound):
    reason: str


InboundEvent = (
    InboundMessage
    | InboundComment
    | Referral
    | OptIn
    | Reaction
    | ReadReceipt
    | MessageEdit
    | MessageDeleted
    | DeliveryStatus
    | Unsupported
)


@dataclass(frozen=True)
class RawEvent:
    """One event split out of a webhook body, ready to store once (TR-WH-03, TR-WH-04)."""

    dedupe_key: str
    event_type: str
    account_ref: str
    payload: dict[str, object]
