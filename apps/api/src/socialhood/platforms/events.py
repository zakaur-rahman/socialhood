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


@dataclass(frozen=True, kw_only=True)
class Inbound:
    account_ref: str  # Instagram entry.id, WhatsApp metadata.phone_number_id
    occurred_at: datetime  # the platform's timestamp, not arrival time


@dataclass(frozen=True, kw_only=True)
class InboundMessage(Inbound):
    contact_ref: str  # IGSID or WhatsApp wa_id
    contact_name: str | None
    platform_message_id: str
    kind: str
    text: str | None
    attachments: tuple[InboundMediaRef, ...] = field(default_factory=tuple)
    reply_to_id: str | None = None
    is_echo: bool = False  # sent by the business outside Social Hood


@dataclass(frozen=True, kw_only=True)
class InboundComment(Inbound):
    platform_comment_id: str
    media_id: str
    parent_id: str | None
    author_ref: str
    author_username: str | None
    text: str


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
    | Reaction
    | ReadReceipt
    | MessageEdit
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
