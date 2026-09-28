"""WhatsApp delivery statuses on the messages we sent (FR-INB-07, F-07, TR-PL-03).

A ``statuses[]`` event moves an outbound message to sent, delivered or read, or to failed with the
mapped reason (a closed window, an unreachable number, ...). Statuses only move forward: a late
``delivered`` after ``read`` changes nothing, a failed message stays failed, and a failure after
delivery is ignored. Runs in the account's workspace scope, in the caller's transaction, and
queues message.updated for after the commit.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.connections import SocialAccount
from socialhood.models.identity import User
from socialhood.models.inbox import Direction, Message, MessageStatus
from socialhood.platforms.events import DeliveryStatus
from socialhood.platforms.whatsapp.parse import WhatsAppDeliveryStatus
from socialhood.realtime import events
from socialhood.services import scheduled

StatusResult = Literal["applied", "stale", "unknown_message"]

RANK: dict[str, int] = {
    MessageStatus.QUEUED: 0,
    MessageStatus.SENDING: 1,
    MessageStatus.SENT: 2,
    MessageStatus.DELIVERED: 3,
    MessageStatus.READ: 4,
}

# When WhatsApp gives no reason (§4.7 copy for the codes a status can carry).
REASONS = {
    "reply_window_closed": (
        "WhatsApp allows free-form replies for 24 hours after the customer's last message. "
        "Send an approved template instead."
    ),
    "recipient_unavailable": "This person can't receive messages right now.",
    "platform_rate_limited": (
        "WhatsApp is limiting messages from this number. Try again in a few minutes."
    ),
    "platform_rejected": "WhatsApp rejected this message.",
}


async def _outbound(session: AsyncSession, acct: SocialAccount, wamid: str) -> Message | None:
    """The message, locked: two statuses for one message are applied one after the other."""
    statement = (
        select(Message)
        .where(Message.social_account_id == acct.id, Message.platform_message_id == wamid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    msg = (await session.scalars(statement)).one_or_none()
    return msg if msg is not None and msg.direction == Direction.OUTBOUND else None


def _advance(msg: Message, event: DeliveryStatus) -> bool:
    if msg.status == MessageStatus.FAILED:
        return False
    current = RANK.get(msg.status or "", -1)
    at = event.occurred_at
    if event.status == "failed":
        if current >= RANK[MessageStatus.DELIVERED]:
            return False
        code = event.error_code or "platform_rejected"
        detail = event.error_message if isinstance(event, WhatsAppDeliveryStatus) else None
        msg.status = MessageStatus.FAILED
        msg.error_code = code
        msg.error_message = detail or REASONS.get(code, REASONS["platform_rejected"])
        return True
    if RANK[event.status] <= current:
        return False
    msg.status = event.status
    msg.sent_at = msg.sent_at or at
    if RANK[event.status] >= RANK[MessageStatus.DELIVERED]:
        msg.delivered_at = msg.delivered_at or at
    if event.status == "read":
        msg.read_at = at
    return True


async def apply_status(
    session: AsyncSession, acct: SocialAccount, event: DeliveryStatus
) -> StatusResult:
    msg = await _outbound(session, acct, event.platform_message_id)
    if msg is None:
        return "unknown_message"
    if not _advance(msg, event):
        return "stale"
    await session.flush()
    sender = (
        await session.scalar(select(User.name).where(User.id == msg.sent_by_user_id))
        if msg.sent_by_user_id
        else None
    )
    events.queue_message(session, msg, created=False, sent_by_name=sender)
    await scheduled.follow_message(session, msg)
    return "applied"
