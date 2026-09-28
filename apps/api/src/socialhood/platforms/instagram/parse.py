"""Instagram payloads as typed events (T3.2, T3.14; F-06, TR-PL-12, FR-INB-09, FR-CON-01).

Webhooks: each stored event, in the shape ``webhooks.split_payload`` stores (``{object, entry_id,
time, kind: "messaging" | "change", field?, item}``), becomes exactly one ``InboundEvent``.
Anything we do not act on becomes ``Unsupported`` with a reason, which the webhook event row
keeps. Shapes follow Meta's Instagram messaging webhook reference; docs/verification.md records
what real payloads confirmed: ``entry.time`` is milliseconds for messaging and seconds for
changes, and an echo arrives under the sending account's own ``entry.id``. Parsing is tolerant:
a missing field falls back, it never fails the event.

Graph reads for sync and backfill live here too: ``/me/media`` items and Conversations API
threads. Their shapes are unverified until T0.9 item 7.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from socialhood.platforms.base import PlatformMedia, PlatformThread
from socialhood.platforms.events import (
    InboundComment,
    InboundEvent,
    InboundMediaRef,
    InboundMessage,
    MessageEdit,
    Reaction,
    ReadReceipt,
    Unsupported,
)

RefKind = Literal["image", "video", "audio", "file", "sticker", "story", "share", "unsupported"]

MILLISECONDS_ABOVE = 10**11  # epoch values above this are milliseconds (year 5138 in seconds)

# Webhook attachment type -> (message kind, attachment kind).
ATTACHMENT_TYPES: dict[str, tuple[str, RefKind]] = {
    "image": ("image", "image"),
    "video": ("video", "video"),
    "audio": ("audio", "audio"),
    "file": ("file", "file"),
    "sticker": ("sticker", "sticker"),
    "like_heart": ("sticker", "sticker"),
    "animated_image": ("image", "image"),  # a GIF
    "story_mention": ("story_mention", "story"),
    "share": ("share", "share"),
    "ig_post": ("share", "share"),
    "ig_reel": ("share", "share"),
    "reel": ("share", "share"),
}

# Meta sends the reaction name and, usually, the emoji itself.
REACTION_EMOJI = {"love": "❤️"}


# ---------------------------------------------------------------- shared helpers


def epoch_time(value: object, fallback: datetime | None = None) -> datetime:
    """A Meta epoch timestamp in seconds or milliseconds, as an aware datetime."""
    try:
        number = float(value)  # type: ignore[arg-type]
        if number > MILLISECONDS_ABOVE:
            number /= 1000
        return datetime.fromtimestamp(number, UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return fallback or datetime.now(UTC)


def graph_time(value: object) -> datetime | None:
    """A Graph API timestamp such as ``2026-09-28T10:00:00+0000``."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return None


def _id(value: object) -> str | None:
    return _str(_dict(value).get("id"))


def _data(value: object) -> list[dict[str, Any]]:
    """Graph edges come as ``{"data": [...]}``; tolerate a bare list."""
    items = value.get("data") if isinstance(value, dict) else value
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


# ---------------------------------------------------------------- webhooks


def parse(payload: Mapping[str, Any]) -> InboundEvent:
    """One stored webhook event -> one typed event."""
    entry_id = _str(payload.get("entry_id")) or ""
    entry_time = epoch_time(payload.get("time"))
    item = payload.get("item")
    if not isinstance(item, dict):
        return Unsupported(account_ref=entry_id, occurred_at=entry_time, reason="unreadable event")
    if payload.get("kind") == "change":
        return _change(entry_id, entry_time, str(payload.get("field") or ""), item)
    return _messaging(entry_id, epoch_time(item.get("timestamp"), entry_time), item)


def _messaging(entry_id: str, at: datetime, item: dict[str, Any]) -> InboundEvent:
    sender = _id(item.get("sender"))
    recipient = _id(item.get("recipient"))
    if "message" in item:
        return _message(entry_id, at, sender, recipient, _dict(item["message"]))
    if "reaction" in item:
        return _reaction(entry_id, at, sender, _dict(item["reaction"]))
    if "read" in item:
        if not sender or sender == entry_id:
            return Unsupported(account_ref=entry_id, occurred_at=at, reason="read by the account")
        mid = _str(_dict(item["read"]).get("mid"))
        return ReadReceipt(
            account_ref=entry_id, occurred_at=at, contact_ref=sender, last_read_message_id=mid
        )
    if "message_edit" in item:
        edit = _dict(item["message_edit"])
        mid, text = _str(edit.get("mid")), edit.get("text")
        if not mid or not isinstance(text, str):
            return Unsupported(account_ref=entry_id, occurred_at=at, reason="unreadable edit")
        return MessageEdit(account_ref=entry_id, occurred_at=at, platform_message_id=mid, text=text)
    if "postback" in item:
        return _postback(entry_id, at, sender, _dict(item["postback"]))
    for other in ("referral", "optin"):
        if other in item:
            return Unsupported(account_ref=entry_id, occurred_at=at, reason=f"{other} events")
    return Unsupported(account_ref=entry_id, occurred_at=at, reason="unknown messaging event")


def _message(
    entry_id: str,
    at: datetime,
    sender: str | None,
    recipient: str | None,
    message: dict[str, Any],
) -> InboundEvent:
    mid = _str(message.get("mid"))
    if not mid:
        return Unsupported(account_ref=entry_id, occurred_at=at, reason="message without an id")
    if message.get("is_deleted"):
        # The customer unsent it. The schema cannot record a deletion yet: reported, not applied.
        return Unsupported(account_ref=entry_id, occurred_at=at, reason="message deleted")
    is_echo = bool(message.get("is_echo")) or (sender is not None and sender == entry_id)
    contact = recipient if is_echo else sender
    if not contact:
        return Unsupported(account_ref=entry_id, occurred_at=at, reason="message without a contact")

    text = _str(message.get("text"))
    kinds, refs = _attachments(message.get("attachments"))
    reply_to = _dict(message.get("reply_to"))
    story = reply_to.get("story")
    if message.get("is_unsupported"):
        kind = "unsupported"  # e.g. ephemeral media: shown as "Open in Instagram"
    elif isinstance(story, dict):
        # A reply to one of the account's stories; like a mention, the story is never copied.
        kind = "story_reply"
        refs.insert(0, InboundMediaRef(kind="story", url=_str(story.get("url"))))
    elif kinds:
        kind = kinds[0]  # an attachment-only message takes the attachment's kind (F-06)
    else:
        kind = "text" if text else "unsupported"
    return InboundMessage(
        account_ref=entry_id,
        occurred_at=at,
        contact_ref=contact,
        contact_name=None,  # Instagram webhooks carry no names; fetch_contact_profile adds them
        platform_message_id=mid,
        kind=kind,
        text=text,
        attachments=tuple(refs),
        reply_to_id=_str(reply_to.get("mid")),
        is_echo=is_echo,
    )


def _attachments(raw: object) -> tuple[list[str], list[InboundMediaRef]]:
    """The message kind and media ref of each attachment type we know (others are skipped)."""
    kinds: list[str] = []
    refs: list[InboundMediaRef] = []
    for attachment in raw if isinstance(raw, list) else []:
        known = ATTACHMENT_TYPES.get(str(_dict(attachment).get("type") or ""))
        if known is None:
            continue
        payload = _dict(attachment.get("payload"))
        message_kind, ref_kind = known
        if ref_kind == "image" and payload.get("sticker_id") is not None:
            message_kind, ref_kind = "sticker", "sticker"
        kinds.append(message_kind)
        refs.append(InboundMediaRef(kind=ref_kind, url=_str(payload.get("url"))))
    return kinds, refs


def _reaction(
    entry_id: str, at: datetime, sender: str | None, reaction: dict[str, Any]
) -> Unsupported | Reaction:
    mid = _str(reaction.get("mid"))
    if not mid or not sender:
        return Unsupported(account_ref=entry_id, occurred_at=at, reason="unreadable reaction")
    if sender == entry_id:
        # Reactions carry no "by" field yet; the account's own reactions are not stored.
        return Unsupported(account_ref=entry_id, occurred_at=at, reason="reaction by the account")
    emoji: str | None = None
    if reaction.get("action") != "unreact":
        name = _str(reaction.get("reaction"))
        emoji = _str(reaction.get("emoji")) or REACTION_EMOJI.get(name or "love", name)
    return Reaction(
        account_ref=entry_id,
        occurred_at=at,
        contact_ref=sender,
        platform_message_id=mid,
        emoji=emoji,
    )


def _postback(
    entry_id: str, at: datetime, sender: str | None, postback: dict[str, Any]
) -> InboundEvent:
    """A tapped ice breaker or button: stored as the customer's text so the thread reads right."""
    mid, title = _str(postback.get("mid")), _str(postback.get("title"))
    if not (mid and title and sender) or sender == entry_id:
        return Unsupported(account_ref=entry_id, occurred_at=at, reason="postback events")
    return InboundMessage(
        account_ref=entry_id,
        occurred_at=at,
        contact_ref=sender,
        contact_name=None,
        platform_message_id=mid,
        kind="text",
        text=title,
    )


def _change(entry_id: str, at: datetime, field: str, value: dict[str, Any]) -> InboundEvent:
    if field != "comments":
        return Unsupported(
            account_ref=entry_id, occurred_at=at, reason=f"{field or 'unknown'} changes"
        )
    comment_id = _str(value.get("id"))
    author = _dict(value.get("from"))
    media_id = _id(value.get("media"))
    if not comment_id or not media_id or not _id(author):
        return Unsupported(account_ref=entry_id, occurred_at=at, reason="unreadable comment")
    return InboundComment(
        account_ref=entry_id,
        occurred_at=graph_time(value.get("timestamp")) or at,
        platform_comment_id=comment_id,
        media_id=media_id,
        parent_id=_str(value.get("parent_id")),
        author_ref=_id(author) or "",
        author_username=_str(author.get("username")),
        text=str(value.get("text") or ""),
    )


# ---------------------------------------------------------------- Graph: media (sync_media)


def media_item(raw: Mapping[str, Any]) -> PlatformMedia | None:
    """One ``/me/media`` item; None when it lacks an id or a timestamp."""
    media_id = _str(raw.get("id"))
    posted_at = graph_time(raw.get("timestamp"))
    if not media_id or posted_at is None:
        return None
    product = str(raw.get("media_product_type") or "").upper()
    media_type = str(raw.get("media_type") or "").upper()
    kind: Literal["image", "video", "carousel", "reel", "story"]
    if product == "STORY":
        kind = "story"
    elif product == "REELS":
        kind = "reel"
    elif media_type == "CAROUSEL_ALBUM":
        kind = "carousel"
    elif media_type == "VIDEO":
        kind = "video"
    else:
        kind = "image"
    return PlatformMedia(
        platform_media_id=media_id,
        media_type=kind,
        caption=_str(raw.get("caption")),
        media_url=_str(raw.get("media_url")),
        thumbnail_url=_str(raw.get("thumbnail_url")),
        permalink=_str(raw.get("permalink")),
        posted_at=posted_at,
        like_count=_count(raw.get("like_count")),
        comments_count=_count(raw.get("comments_count")),
    )


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


# ---------------------------------------------------------------- Graph: threads (backfill)


def thread(
    conversation: Mapping[str, Any],
    messages: Iterable[Mapping[str, Any]],
    *,
    account_ref: str,
    own_ids: frozenset[str],
    own_username: str | None,
) -> PlatformThread | None:
    """One Conversations API thread, messages oldest first. ``own_ids`` and ``own_username``
    identify the account's side, which decides each message's direction. None when the thread
    has no id or no other participant."""

    def is_own(person: Mapping[str, Any]) -> bool:
        pid, username = _str(person.get("id")), _str(person.get("username"))
        return (pid is not None and pid in own_ids) or (
            own_username is not None and username == own_username
        )

    contact: dict[str, Any] = next(
        (p for p in _data(conversation.get("participants")) if not is_own(p) and _id(p)), {}
    )
    rows: list[tuple[str, datetime, bool, str | None, tuple[InboundMediaRef, ...]]] = []
    for raw in messages:
        mid, at = _str(raw.get("id")), graph_time(raw.get("created_time"))
        if not mid or at is None:
            continue
        sender = _dict(raw.get("from"))
        outbound = is_own(sender)
        if not contact:  # no participants field: the other side of the first message
            other = _data(raw.get("to"))[:1] if outbound else [sender]
            contact = other[0] if other and _id(other[0]) else {}
        refs = tuple(r for r in (_graph_attachment(a) for a in _data(raw.get("attachments"))) if r)
        rows.append((mid, at, outbound, _str(raw.get("message")), refs))

    conversation_id, contact_ref = _str(conversation.get("id")), _id(contact)
    if not conversation_id or not contact_ref:
        return None
    parsed = tuple(
        InboundMessage(
            account_ref=account_ref,
            occurred_at=at,
            contact_ref=contact_ref,
            contact_name=None,
            platform_message_id=mid,
            kind=(refs[0].kind if refs else "text" if text else "unsupported"),
            text=text,
            attachments=refs,
            is_echo=outbound,
        )
        for mid, at, outbound, text, refs in sorted(rows, key=lambda r: r[1])
    )
    return PlatformThread(
        platform_conversation_id=conversation_id,
        contact_ref=contact_ref,
        contact_username=_str(contact.get("username")),
        messages=parsed,
    )


def _graph_attachment(raw: Mapping[str, Any]) -> InboundMediaRef | None:
    """A Conversations API attachment: ``image_data``, ``video_data``, ``audio_data`` or a
    ``file_url`` with its ``mime_type`` (Messenger's documented shape; unverified for Instagram)."""
    for key, kind in (("image_data", "image"), ("video_data", "video"), ("audio_data", "audio")):
        data = _dict(raw.get(key))
        if data:
            if kind == "image" and raw.get("sticker_id") is not None:
                return InboundMediaRef(kind="sticker", url=_str(data.get("url")))
            return InboundMediaRef(kind=_ref_kind(kind), url=_str(data.get("url")))
    url = _str(raw.get("file_url")) or _str(raw.get("url"))
    if not url:
        return None
    return InboundMediaRef(kind=_ref_kind(str(raw.get("mime_type") or "").split("/")[0]), url=url)


def _ref_kind(value: str) -> RefKind:
    """image, video or audio; anything else is a file."""
    kinds: dict[str, RefKind] = {"image": "image", "video": "video", "audio": "audio"}
    return kinds.get(value, "file")
