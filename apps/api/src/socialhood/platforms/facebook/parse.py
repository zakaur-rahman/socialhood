"""Facebook Page payloads as typed events (GR-29; F-06, TR-PL-12, F-12).

Messenger's webhook shapes are Instagram messaging's: ``messages`` (with echoes, quick replies,
attachments, reply-to and a referral on the first message from an ad), ``messaging_postbacks``,
``messaging_referrals``, ``message_reactions``, ``message_edits`` and ``messaging_optins``. Those
go through the Instagram parser. What differs is parsed here:

- ``message_reads`` carry a watermark (a time), not a message id: everything we sent before it
  is read;
- ``message_deliveries`` name the messages delivered; they are split into one event per message
  (webhooks.py) and each becomes a ``DeliveryStatus``;
- a postback may come without a ``mid``; one is made from the person and the time so the tap
  is stored once;
- post activity arrives as the ``feed`` field: a new comment (``item: comment``, ``verb: add``)
  becomes an ``InboundComment``; edits, removals, hides and every other item are ``Unsupported``.
  A comment's ``parent_id`` is the post's id for a top-level comment and a comment id for a reply.

Anything we do not act on becomes ``Unsupported`` with a reason, which the webhook event row
keeps. Parsing is tolerant: a missing field falls back, it never fails the event. Unverified until
a real Page confirms the shapes (docs/verification.md).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from socialhood.platforms.events import (
    DeliveryStatus,
    InboundComment,
    InboundEvent,
    ReadReceipt,
    Unsupported,
)
from socialhood.platforms.instagram import parse as instagram
from socialhood.platforms.instagram.parse import _dict, _id, _str, epoch_time

# Where a Page's own comment object can name an attachment-only comment.
MISSING_TEXT = ""


def parse(payload: Mapping[str, Any]) -> InboundEvent:
    """One stored webhook event -> one typed event."""
    entry_id = _str(payload.get("entry_id")) or ""
    entry_time = epoch_time(payload.get("time"))
    item = payload.get("item")
    if not isinstance(item, dict):
        return Unsupported(account_ref=entry_id, occurred_at=entry_time, reason="unreadable event")
    if payload.get("kind") == "change":
        return _change(entry_id, entry_time, str(payload.get("field") or ""), item)
    at = epoch_time(item.get("timestamp"), entry_time)
    sender = _id(item.get("sender"))
    if "read" in item:
        return _read(entry_id, at, sender, _dict(item["read"]))
    if "delivery" in item:
        return _delivery(entry_id, at, _dict(item["delivery"]))
    if "postback" in item:
        item = _with_postback_id(item, sender, at)
    return instagram.parse({**payload, "item": item})


def _with_postback_id(item: dict[str, Any], sender: str | None, at: datetime) -> dict[str, Any]:
    postback = _dict(item["postback"])
    if _str(postback.get("mid")):
        return item
    mid = f"postback_{sender}_{int(at.timestamp() * 1000)}"
    return {**item, "postback": {**postback, "mid": mid}}


def _read(entry_id: str, at: datetime, sender: str | None, read: dict[str, Any]) -> InboundEvent:
    if not sender or sender == entry_id:
        return Unsupported(account_ref=entry_id, occurred_at=at, reason="read by the Page")
    watermark = read.get("watermark")
    return ReadReceipt(
        account_ref=entry_id,
        occurred_at=epoch_time(watermark, at) if watermark is not None else at,
        contact_ref=sender,
        last_read_message_id=None,
    )


def _delivery(entry_id: str, at: datetime, delivery: dict[str, Any]) -> InboundEvent:
    mids = delivery.get("mids")
    mid = _str(mids[0]) if isinstance(mids, list) and mids else None
    if mid is None:
        return Unsupported(
            account_ref=entry_id, occurred_at=at, reason="delivery without a message"
        )
    watermark = delivery.get("watermark")
    return DeliveryStatus(
        account_ref=entry_id,
        occurred_at=epoch_time(watermark, at) if watermark is not None else at,
        platform_message_id=mid,
        status="delivered",
    )


def _change(entry_id: str, at: datetime, field: str, value: dict[str, Any]) -> InboundEvent:
    if field != "feed":
        return Unsupported(
            account_ref=entry_id, occurred_at=at, reason=f"{field or 'unknown'} changes"
        )
    item = _str(value.get("item"))
    if item != "comment":
        return Unsupported(account_ref=entry_id, occurred_at=at, reason=f"feed {item or 'other'}")
    verb = _str(value.get("verb"))
    if verb is not None and verb != "add":
        # An edit, a removal or a hide must not be taken for a new comment (and fire automations).
        return Unsupported(account_ref=entry_id, occurred_at=at, reason=f"comment {verb} events")
    comment_id = _str(value.get("comment_id")) or _str(value.get("id"))
    post_id = _str(value.get("post_id"))
    author = _dict(value.get("from"))
    author_ref = _id(author)
    if not comment_id or not post_id or not author_ref:
        return Unsupported(account_ref=entry_id, occurred_at=at, reason="unreadable comment")
    parent = _str(value.get("parent_id"))
    return InboundComment(
        account_ref=entry_id,
        occurred_at=epoch_time(value.get("created_time"), at),
        platform_comment_id=comment_id,
        media_id=post_id,
        parent_id=None if parent in (None, post_id) else parent,
        author_ref=author_ref,
        author_username=_str(author.get("name")),
        text=str(value.get("message") or MISSING_TEXT),
    )
