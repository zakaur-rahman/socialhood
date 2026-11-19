"""The business's reaction to a message (GR-42).

One reaction per message from the business, stored in ``messages.reactions`` with
``by: "business"`` next to the customer's. The platform call happens in the request, not in a
job: a reaction is small and the member sees the answer at once. The reply window applies as for
text. WhatsApp refuses a reaction to a message older than 30 days (Meta's 131009), so that is
checked first; Instagram and Facebook take only a heart (the adapters refuse the rest).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import check_account_writable
from socialhood.errors import ApiError
from socialhood.models.inbox import Contact, Conversation, Direction, Message
from socialhood.platforms.capabilities import Capability, require
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.realtime import events
from socialhood.repositories import social_accounts as accounts
from socialhood.services import sending
from socialhood.services.reply_window import may_send, reply_window

WHATSAPP_MAX_AGE = timedelta(days=30)


async def react(
    session: AsyncSession,
    redis: Redis,
    conv: Conversation,
    message_id: uuid.UUID,
    emoji: str | None,
    *,
    deps: PlatformDeps,
    now: datetime,
) -> tuple[Message, bool]:
    """Set (or with None remove) the business's reaction; returns the message and whether it
    changed. Queues message.updated; the caller records the audit event and commits."""
    msg = await session.scalar(
        select(Message)
        .where(Message.id == message_id, Message.conversation_id == conv.id)
        .with_for_update()
    )
    if msg is None:
        raise ApiError("not_found")
    current = list(msg.reactions or [])
    ours = next((r.get("emoji") for r in current if r.get("by") == "business"), None)
    if ours == emoji:
        return msg, False
    ref = msg.platform_message_id
    if not ref or msg.deleted_at is not None or msg.direction == Direction.SYSTEM:
        raise ApiError("validation_error", "This message can't take a reaction.")
    if conv.platform == "whatsapp" and now - msg.occurred_at > WHATSAPP_MAX_AGE:
        raise ApiError(
            "validation_error", "WhatsApp only takes reactions to messages from the last 30 days."
        )

    acct = await accounts.get(session, conv.social_account_id)
    contact = await session.get(Contact, conv.contact_id)
    if acct is None or contact is None:
        raise ApiError("not_found")
    sending.check_account(acct)
    await check_account_writable(session, acct)
    caps = sending.capabilities(acct, deps)
    require(caps, Capability.DM_SEND)
    window = reply_window(
        conv.platform, conv.last_inbound_at, human_agent=Capability.HUMAN_AGENT in caps, now=now
    )
    if not may_send(window, "human"):
        raise ApiError("reply_window_closed", sending.window_closed_detail(conv.platform))

    try:
        await adapter_for(acct, deps).react(acct, contact.platform_user_id, ref, emoji)
    except PlatformError as error:
        if error.code == "reaction_not_supported":
            raise ApiError("reaction_not_supported", error.message or None) from error
        from socialhood.services.comments.actions import _refused

        raise await _refused(session, redis, acct, error) from error

    others = [r for r in current if r.get("by") != "business"]
    mine = [{"emoji": emoji, "by": "business", "at": now.isoformat()}] if emoji else []
    msg.reactions = [*others, *mine]
    await session.flush()
    name = await sending.sender_name(session, msg.sent_by_user_id)
    events.queue_message(session, msg, created=False, sent_by_name=name)
    return msg, True
