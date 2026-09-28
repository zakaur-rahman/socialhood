"""API projections of inbox rows (§5.10). REST responses and real-time events both use these, so
a client can patch its cache from an event without refetching (TR-RT-03)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import Contact, Conversation, Message
from socialhood.schemas.inbox import (
    Actor,
    Attachment,
    ContactSummary,
    ConversationListItem,
    ErrorInfo,
    MessageButton,
    Reaction,
    Signal,
    TemplateInfo,
)
from socialhood.schemas.inbox import (
    Message as MessageOut,
)
from socialhood.services.reply_window import reply_window

LEAD_SCORE = 60  # FR-INB-01 "Leads" and the Lead chip
CLOSING_SOON = timedelta(hours=3)  # the "Closing in 3h" chip (FR-INB-14)
PREVIEW_CHARS = 200


def human_agent_allowed(acct: SocialAccount, *, ig_human_agent_enabled: bool) -> bool:
    """Human Agent applies to Instagram only, once Meta has approved it (IG_HUMAN_AGENT_ENABLED)."""
    return ig_human_agent_enabled and acct.platform == "instagram"


def signal_for(
    conv: Conversation, *, now: datetime, window_closes_at: datetime | None
) -> Signal | None:
    """At most one chip, in UX-INB-04's priority order."""
    if conv.needs_human:
        return "needs_you"
    if conv.last_intent == "complaint":
        return "complaint"
    if (
        conv.awaiting_reply
        and window_closes_at is not None
        and timedelta(0) < window_closes_at - now <= CLOSING_SOON
    ):
        return "closing_soon"
    if conv.lead_score is not None and conv.lead_score >= LEAD_SCORE:
        return "lead"
    if conv.last_sentiment == "negative":
        return "negative"
    return None


def list_item(
    conv: Conversation, contact: Contact, *, now: datetime, human_agent: bool = False
) -> ConversationListItem:
    window = reply_window(conv.platform, conv.last_inbound_at, human_agent=human_agent, now=now)
    closes_at = window.closes_at if window.state == "open" else None
    return ConversationListItem(
        id=conv.id,
        platform=conv.platform,
        social_account_id=conv.social_account_id,
        contact=ContactSummary(
            id=contact.id,
            display_name=contact.display_name,
            username=contact.username,
            profile_picture_url=contact.profile_picture_url,
        ),
        status=conv.status,
        last_message_at=conv.last_message_at,
        last_message_preview=conv.last_message_preview,
        last_message_direction=conv.last_message_direction,
        last_message_source=conv.last_message_source,
        last_message_kind=conv.last_message_kind,
        unread_count=conv.unread_count,
        awaiting_reply=conv.awaiting_reply,
        needs_human=conv.needs_human,
        needs_human_reason=conv.needs_human_reason,
        signal=signal_for(conv, now=now, window_closes_at=closes_at),
        reply_window_closes_at=closes_at,
        lead_score=conv.lead_score,
    )


def message_out(msg: Message, *, sent_by_name: str | None = None) -> MessageOut:
    return MessageOut(
        id=msg.id,
        conversation_id=msg.conversation_id,
        client_id=msg.client_id,
        direction=msg.direction,
        source=msg.source,
        kind=msg.kind,
        text=msg.text,
        attachments=[Attachment.model_validate(a) for a in msg.attachments or []],
        template=TemplateInfo.model_validate(msg.template) if msg.template else None,
        buttons=[MessageButton.model_validate(b) for b in msg.buttons or []],
        status=msg.status,
        error=(
            ErrorInfo(code=msg.error_code, message=msg.error_message or "")
            if msg.error_code
            else None
        ),
        occurred_at=msg.occurred_at,
        sent_at=msg.sent_at,
        delivered_at=msg.delivered_at,
        read_at=msg.read_at,
        edited_at=msg.edited_at,
        deleted_at=msg.deleted_at,
        sent_by=Actor(id=msg.sent_by_user_id, name=sent_by_name) if msg.sent_by_user_id else None,
        automation=None,  # P4
        suggestion_id=msg.suggestion_id,
        human_agent_tag=msg.human_agent_tag,
        reactions=[Reaction.model_validate(r) for r in msg.reactions or []],
    )


ATTACHMENT_PREVIEW = {
    "image": "Photo",
    "video": "Video",
    "audio": "Voice message",
    "file": "File",
    "sticker": "Sticker",
    "story_mention": "Mentioned you in a story",
    "story_reply": "Story reply",
    "share": "Shared a post",
    "template": "Template",
    "location": "Location",
    "unsupported": "Message",
}
UNSENT_PREVIEW = "Message unsent"


def preview_text(kind: str, text: str | None) -> str:
    """The list preview for a message (UX-INB-04); prefixes like "You: " are added by the client."""
    if text:
        compact = " ".join(text.split())
        return compact[:PREVIEW_CHARS]
    return ATTACHMENT_PREVIEW.get(kind, "Message")


def conversation_touch(msg: Message) -> dict[str, Any]:
    """The conversation columns a new message updates (last message fields)."""
    return {
        "last_message_at": msg.occurred_at,
        "last_message_preview": preview_text(msg.kind, msg.text),
        "last_message_direction": msg.direction,
        "last_message_source": msg.source,
        "last_message_kind": msg.kind,
    }
