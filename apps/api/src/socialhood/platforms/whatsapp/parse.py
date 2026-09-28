"""One stored WhatsApp event -> one typed inbound event (TR-PL-12, F-06).

Pure: no I/O and no clock. Messages become InboundMessage (text, image, video, audio, file,
sticker, location; a template button or interactive reply is text replying to our message;
anything else is kind ``unsupported``), reactions become Reaction, and ``statuses[]`` become
WhatsAppDeliveryStatus. Shapes we don't act on return Unsupported with the reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from socialhood.platforms.events import (
    DeliveryStatus,
    InboundEvent,
    InboundMediaRef,
    InboundMessage,
    Reaction,
    Unsupported,
)
from socialhood.platforms.whatsapp.errors import status_failure

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
Delivery = Literal["sent", "delivered", "read", "failed"]
DELIVERY_STATES: dict[str, Delivery] = {
    "sent": "sent",
    "delivered": "delivered",
    "read": "read",
    "failed": "failed",
}
MediaKind = Literal["image", "video", "audio", "file", "sticker"]
# WhatsApp message type -> (message kind, attachment kind)
MEDIA_KINDS: dict[str, tuple[str, MediaKind]] = {
    "image": ("image", "image"),
    "video": ("video", "video"),
    "audio": ("audio", "audio"),
    "document": ("file", "file"),
    "sticker": ("sticker", "sticker"),
}


@dataclass(frozen=True, kw_only=True)
class WhatsAppDeliveryStatus(DeliveryStatus):
    """A delivery status with WhatsApp's reason and code for a failure (the Failed bubble shows
    the reason; the code is kept for the log)."""

    error_message: str | None = None
    platform_code: str | None = None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _timestamp(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _location_text(location: dict[str, Any]) -> str | None:
    lines = [str(location[k]) for k in ("name", "address") if location.get(k)]
    lat, lng = location.get("latitude"), location.get("longitude")
    if lat is not None and lng is not None:
        lines.append(f"https://maps.google.com/?q={lat},{lng}")
    return "\n".join(lines) or None


def _content(message: dict[str, Any]) -> tuple[str, str | None, tuple[InboundMediaRef, ...]]:
    """(kind, text, attachments) for one message."""
    kind = str(message.get("type", ""))
    body = _dict(message.get(kind))
    if kind == "text":
        return "text", body.get("body"), ()
    if kind in MEDIA_KINDS:
        message_kind, media_kind = MEDIA_KINDS[kind]
        ref = InboundMediaRef(kind=media_kind, media_id=body.get("id"))
        return message_kind, body.get("caption"), (ref,)
    if kind == "location":
        return "location", _location_text(body), ()
    if kind == "button":  # a quick-reply button on one of our templates
        return "text", body.get("text") or body.get("payload"), ()
    if kind == "interactive":
        reply = _dict(body.get("button_reply")) or _dict(body.get("list_reply"))
        if reply.get("title"):
            return "text", str(reply["title"]), ()
    return "unsupported", None, ()


def _message(payload: dict[str, Any], account_ref: str) -> InboundEvent:
    message = _dict(payload.get("message"))
    occurred_at = _timestamp(message.get("timestamp"))
    sender = message.get("from")
    kind = str(message.get("type", ""))
    if occurred_at is None or not sender or not message.get("id"):
        return Unsupported(
            account_ref=account_ref,
            occurred_at=occurred_at or EPOCH,
            reason="message without id, sender or timestamp",
        )
    if kind in ("system", "request_welcome"):
        return Unsupported(
            account_ref=account_ref, occurred_at=occurred_at, reason=f"{kind} message"
        )
    if kind == "reaction":
        reaction = _dict(message.get("reaction"))
        if not reaction.get("message_id"):
            return Unsupported(
                account_ref=account_ref, occurred_at=occurred_at, reason="reaction without target"
            )
        return Reaction(
            account_ref=account_ref,
            occurred_at=occurred_at,
            contact_ref=str(sender),
            platform_message_id=str(reaction["message_id"]),
            emoji=reaction.get("emoji") or None,
        )
    message_kind, text, attachments = _content(message)
    profile = _dict(_dict(payload.get("contact")).get("profile"))
    context = _dict(message.get("context"))
    return InboundMessage(
        account_ref=account_ref,
        occurred_at=occurred_at,
        contact_ref=str(sender),
        contact_name=profile.get("name") or None,
        platform_message_id=str(message["id"]),
        kind=message_kind,
        text=text,
        attachments=attachments,
        reply_to_id=context.get("id") or None,
    )


def _status(payload: dict[str, Any], account_ref: str) -> InboundEvent:
    status = _dict(payload.get("status"))
    occurred_at = _timestamp(status.get("timestamp"))
    state = str(status.get("status", ""))
    delivery = DELIVERY_STATES.get(state)
    if occurred_at is None or not status.get("id"):
        return Unsupported(
            account_ref=account_ref,
            occurred_at=occurred_at or EPOCH,
            reason="status without id or timestamp",
        )
    if delivery is None:
        return Unsupported(
            account_ref=account_ref, occurred_at=occurred_at, reason=f"{state or 'unknown'} status"
        )
    code = message = platform_code = None
    if delivery == "failed":
        code, message, platform_code = status_failure(status.get("errors"))
    return WhatsAppDeliveryStatus(
        account_ref=account_ref,
        occurred_at=occurred_at,
        platform_message_id=str(status["id"]),
        status=delivery,
        error_code=code,
        error_message=message,
        platform_code=platform_code,
    )


def parse_event(payload: dict[str, Any]) -> InboundEvent:
    account_ref = str(_dict(payload.get("metadata")).get("phone_number_id") or "")
    kind = payload.get("kind")
    if kind == "message":
        return _message(payload, account_ref)
    if kind == "status":
        return _status(payload, account_ref)
    return Unsupported(
        account_ref=account_ref,
        occurred_at=EPOCH,
        reason=f"{payload.get('field') or 'unknown'} events are not used",
    )
