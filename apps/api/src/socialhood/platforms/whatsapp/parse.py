"""One stored WhatsApp event -> one typed inbound event (TR-PL-12, F-06).

Pure: no I/O and no clock. Messages become InboundMessage (text, image, video, audio, file,
sticker, location; a template button or interactive reply is text replying to our message;
anything else is kind ``unsupported``), reactions become Reaction, and ``statuses[]`` become
WhatsAppDeliveryStatus. Shapes we don't act on return Unsupported with the reason.

GR-01: a message from a Click to WhatsApp ad carries a ``referral`` object (``source_type`` ad or
post, ``source_id``, ``headline``, and ``ctwa_clid``, which Status ads leave out; Meta's messages
webhook reference). It becomes the message's ReferralInfo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from socialhood.platforms.events import (
    CartItem,
    CartOrder,
    DeliveryStatus,
    InboundEvent,
    InboundMediaRef,
    InboundMessage,
    Reaction,
    ReferralInfo,
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


def cart_of(message: dict[str, Any]) -> CartOrder | None:
    """A customer's cart from an ``order`` message: ``order.catalog_id``, ``order.text`` and
    ``order.product_items[]`` (``product_retailer_id``, ``quantity``, ``item_price``, ``currency``).
    Prices and quantities may arrive as numbers or text, so both are read; an item without a
    retailer id or a positive quantity is dropped. *Unverified against a live number (C-121).*"""
    body = _dict(message.get("order"))
    items: list[CartItem] = []
    for raw in body.get("product_items") or []:
        item = _dict(raw)
        retailer = item.get("product_retailer_id")
        try:
            quantity = int(item.get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0
        if not retailer or quantity < 1:
            continue
        price = item.get("item_price")
        items.append(
            CartItem(
                retailer_id=str(retailer),
                quantity=quantity,
                price=str(price) if price is not None else None,
                currency=str(item["currency"]) if item.get("currency") else None,
            )
        )
    if not items:
        return None
    catalog = body.get("catalog_id")
    note = body.get("text")
    return CartOrder(str(catalog) if catalog else None, str(note) if note else None, tuple(items))


def _content(message: dict[str, Any]) -> tuple[str, str | None, tuple[InboundMediaRef, ...]]:
    """(kind, text, attachments) for one message."""
    kind = str(message.get("type", ""))
    body = _dict(message.get(kind))
    if kind == "text":
        return "text", body.get("body"), ()
    if kind in MEDIA_KINDS:
        message_kind, media_kind = MEDIA_KINDS[kind]
        ref = InboundMediaRef(
            kind=media_kind,
            media_id=body.get("id"),
            mime_type=body.get("mime_type"),
            filename=body.get("filename"),
        )
        return message_kind, body.get("caption"), (ref,)
    if kind == "location":
        return "location", _location_text(body), ()
    if kind == "order":  # a cart sent from a catalogue message (GR-33): the text says so
        cart = cart_of(message)
        count = sum(i.quantity for i in cart.items) if cart else 0
        label = f"Sent an order of {count} {'item' if count == 1 else 'items'}"
        return "text", f"{label}. {cart.note}" if cart and cart.note else label, ()
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
        referral=referral_info(message.get("referral")),
        order=cart_of(message) if kind == "order" else None,
    )


def referral_info(raw: object) -> ReferralInfo | None:
    """A Click to WhatsApp ``referral`` as ours: an ad (``source_type: ad``) or a post; None when
    there is none."""
    referral = _dict(raw)
    if not referral:
        return None
    source_type = str(referral.get("source_type") or "") or None
    return ReferralInfo(
        source="ad" if source_type == "ad" else "other",
        ad_id=str(referral.get("source_id") or "") or None,
        ad_title=str(referral.get("headline") or "") or None,
        ctwa_clid=str(referral.get("ctwa_clid") or "") or None,
        platform_source=source_type,
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
