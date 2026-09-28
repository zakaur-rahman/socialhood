"""Scheduled messages (T3.13; F-10, FR-SMS-01...03, TR-JOB-03, UX-INB-10).

The API schedules, edits, cancels and lists them. The dispatcher (jobs/tasks/scheduled.py) claims
due rows and runs ``send_claimed`` for each: it re-checks the reply window, then hands the text to
the send pipeline (``services.sending.queue_outbound``) as a normal human reply, or marks the row
expired and tells the owners. Every change queues ``scheduled_message.updated`` (TR-RT-03).
Nothing here commits: callers commit with ``realtime.events.commit_and_publish``.

Lifecycle (§3 state diagram): scheduled -> canceled (user) or sending (dispatcher claims);
sending -> sent, failed or expired, or back to scheduled when the sweeper resets a stuck claim.
"""

from __future__ import annotations

import base64
import binascii
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ERROR_CODES, ApiError, FieldError
from socialhood.models.inbox import Conversation, Message, ScheduledMessage
from socialhood.models.inbox import ScheduledStatus as S
from socialhood.realtime import events
from socialhood.repositories import inbox
from socialhood.repositories import scheduled as repo
from socialhood.repositories.scheduled import DONE, ScheduledRow
from socialhood.schemas.inbox import (
    ErrorInfo,
    ScheduledContact,
    ScheduledMessageCreate,
    ScheduledMessageList,
    ScheduledMessagePatch,
)
from socialhood.schemas.inbox import ScheduledMessage as ScheduledMessageOut
from socialhood.services import sending
from socialhood.services.notifications import notify_admins
from socialhood.services.reply_window import may_send, reply_window

MIN_LEAD = timedelta(minutes=1)  # the picker offers now + 2 minutes; this allows the round trip
WINDOW_MARGIN = timedelta(minutes=5)  # F-10: at the latest 5 minutes before the window closes
RECENT = timedelta(days=7)  # sent, failed and expired messages stay on the Scheduled tab this long
CONVERSATION_LIMIT = 100
STUCK_AFTER = timedelta(minutes=10)  # TR-JOB-03
MAX_ATTEMPTS = 5  # TR-JOB-03: a row claimed this often without producing a message fails
# client_id of the message a scheduled message becomes: stable, so a repeat never sends twice.
CLIENT_ID_NAMESPACE = uuid.UUID("5d3f0b8e-9c1a-4e27-8b6d-2f4a7c9e1b03")

WINDOW_CLOSED_COPY = {  # §4.7 reply_window_closed
    "instagram": "Instagram allows replies for 24 hours after the customer's last message.",
    "whatsapp": (
        "WhatsApp allows free-form replies for 24 hours after the customer's last message. "
        "Send an approved template instead."
    ),
}
EXPIRED_REASON = "The reply window closed before the send time."
STUCK_REASON = "Couldn't send this message. Schedule it again."
NOT_EDITABLE = {
    S.SENDING: "This message is being sent and can't be changed.",
    S.SENT: "This message was already sent.",
    S.FAILED: "This message wasn't sent. Schedule a new one.",
    S.EXPIRED: "This message wasn't sent. Schedule a new one.",
    S.CANCELED: "This message was canceled.",
}

SendOutcome = Literal["sent", "failed", "expired", "skipped"]


# ---- projection and events


def scheduled_out(row: ScheduledRow) -> ScheduledMessageOut:
    s, contact = row.scheduled, row.contact
    return ScheduledMessageOut(
        id=s.id,
        conversation_id=s.conversation_id,
        text=s.text,
        attachment_asset_ids=list(s.attachment_asset_ids or []),
        send_at=s.send_at,
        status=s.status,
        error=(
            ErrorInfo(code=s.error_code, message=s.error_message or "") if s.error_code else None
        ),
        contact=ScheduledContact(
            display_name=contact.display_name,
            username=contact.username,
            profile_picture_url=contact.profile_picture_url,
        ),
        platform=row.platform,
    )


def queue_updated(session: AsyncSession, row: ScheduledRow) -> None:
    events.queue(
        session,
        row.scheduled.workspace_id,
        "scheduled_message.updated",
        {"scheduled_message": scheduled_out(row).model_dump(mode="json")},
    )


def client_id_for(scheduled_message_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(CLIENT_ID_NAMESPACE, str(scheduled_message_id))


# ---- lists (FR-SMS-02, UX-INB-10)


@dataclass(frozen=True)
class _Cursor:
    done: bool  # False: still in the pending part of the list
    send_at: datetime
    id: uuid.UUID


def _encode(row: ScheduledRow) -> str:
    s = row.scheduled
    raw = json.dumps([int(s.status in DONE), s.send_at.isoformat(), str(s.id)])
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode(value: str) -> _Cursor:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        done, send_at, row_id = json.loads(raw)
        return _Cursor(bool(done), datetime.fromisoformat(send_at), uuid.UUID(row_id))
    except (ValueError, TypeError, binascii.Error) as error:
        raise ApiError(
            "validation_error", errors=[FieldError("cursor", "This page link isn't valid.")]
        ) from error


def _page(rows: Sequence[ScheduledRow], more: bool) -> ScheduledMessageList:
    return ScheduledMessageList(
        items=[scheduled_out(r) for r in rows], next_cursor=_encode(rows[-1]) if more else None
    )


async def list_tab(
    session: AsyncSession, *, cursor: str | None, limit: int, now: datetime
) -> ScheduledMessageList:
    """Pending messages by send time, then sent, failed and expired ones of the last week, most
    recent first. The cursor carries the part of the list and the (send_at, id) key."""
    after = _decode(cursor) if cursor else None
    rows: list[ScheduledRow] = []
    before_done: tuple[datetime, uuid.UUID] | None = None
    if after is None or not after.done:
        key = (after.send_at, after.id) if after else None
        rows = await repo.list_pending(session, limit=limit + 1, after=key)
        if len(rows) > limit:
            return _page(rows[:limit], more=True)
    else:
        before_done = (after.send_at, after.id)
    room = limit - len(rows)
    done = await repo.list_done(session, since=now - RECENT, limit=room + 1, before=before_done)
    rows += done[:room]
    if not rows:
        return ScheduledMessageList(items=[])
    return _page(rows, more=len(done) > room)


async def list_for_conversation(
    session: AsyncSession, conversation_id: uuid.UUID
) -> ScheduledMessageList:
    """The conversation's pending messages, soonest first (the thread's "1 scheduled" chip)."""
    await _conversation_or_404(session, conversation_id)
    rows = await repo.list_pending(
        session, limit=CONVERSATION_LIMIT, conversation_id=conversation_id
    )
    return ScheduledMessageList(items=[scheduled_out(r) for r in rows])


# ---- schedule, edit, cancel (F-10, FR-SMS-01, FR-SMS-02)


async def create(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    body: ScheduledMessageCreate,
    *,
    user_id: uuid.UUID,
    human_agent_enabled: bool,
    now: datetime,
) -> ScheduledMessageOut:
    conv = await _conversation_or_404(session, conversation_id)
    send_at = _check_send_at(conv, body.send_at, human_agent_enabled=human_agent_enabled, now=now)
    asset_ids = await _check_assets(session, body.attachment_asset_ids)
    await _check_capacity(session)
    contact = await inbox.get_contact(session, conv.contact_id)
    if contact is None:  # pragma: no cover - a conversation always has its contact
        raise ApiError("not_found")
    row = ScheduledMessage(
        conversation_id=conv.id,
        text=body.text,
        attachment_asset_ids=asset_ids,
        send_at=send_at,
        status=S.SCHEDULED,
        attempts=0,
        created_by_user_id=user_id,
    )
    session.add(row)
    await session.flush()
    result = ScheduledRow(row, conv.platform, contact)
    queue_updated(session, result)
    return scheduled_out(result)


async def update(
    session: AsyncSession,
    scheduled_message_id: uuid.UUID,
    body: ScheduledMessagePatch,
    *,
    human_agent_enabled: bool,
    now: datetime,
) -> ScheduledMessageOut:
    """Edit the text or the time until the dispatcher claims the message."""
    row = await _get_or_404(session, scheduled_message_id)
    s = row.scheduled
    if s.status != S.SCHEDULED:
        raise ApiError("conflict", NOT_EDITABLE.get(S(s.status)))
    changed = False
    if body.send_at is not None:
        conv = await _conversation_or_404(session, s.conversation_id)
        send_at = _check_send_at(
            conv, body.send_at, human_agent_enabled=human_agent_enabled, now=now
        )
        changed |= send_at != s.send_at
        s.send_at = send_at
    if body.text is not None:
        changed |= body.text != s.text
        s.text = body.text
    if changed:
        await session.flush()
        queue_updated(session, row)
    return scheduled_out(row)


async def cancel(session: AsyncSession, scheduled_message_id: uuid.UUID) -> None:
    """Cancel until the dispatcher claims it; canceling twice is fine."""
    row = await _get_or_404(session, scheduled_message_id)
    s = row.scheduled
    if s.status == S.CANCELED:
        return
    if s.status != S.SCHEDULED:
        raise ApiError("conflict", NOT_EDITABLE.get(S(s.status)))
    s.status = S.CANCELED
    await session.flush()
    queue_updated(session, row)


async def _conversation_or_404(session: AsyncSession, conversation_id: uuid.UUID) -> Conversation:
    conv = await inbox.get_conversation(session, conversation_id)
    if conv is None:
        raise ApiError("not_found")
    return conv


async def _get_or_404(session: AsyncSession, scheduled_message_id: uuid.UUID) -> ScheduledRow:
    """Locked, so an edit and the dispatcher's claim never interleave."""
    row = await repo.get(session, scheduled_message_id, for_update=True)
    if row is None:
        raise ApiError("not_found")
    return row


def _human_agent(platform: str, enabled: bool) -> bool:
    """As inbox_views.human_agent_allowed: Instagram only, once Meta has approved it."""
    return enabled and platform == "instagram"


def _field_error(field: str, message: str) -> ApiError:
    return ApiError("validation_error", errors=[FieldError(field, message)])


def _check_send_at(
    conv: Conversation, send_at: datetime, *, human_agent_enabled: bool, now: datetime
) -> datetime:
    """F-10: a human reply must be allowed now and still 5 minutes after the send time."""
    human_agent = _human_agent(conv.platform, human_agent_enabled)
    window = reply_window(conv.platform, conv.last_inbound_at, human_agent=human_agent, now=now)
    if not may_send(window, "human"):
        raise ApiError("reply_window_closed", WINDOW_CLOSED_COPY.get(conv.platform))
    at = send_at if send_at.tzinfo is not None else send_at.replace(tzinfo=UTC)
    if at < now + MIN_LEAD:
        raise _field_error("send_at", "Pick a time at least 2 minutes from now.")
    later = reply_window(
        conv.platform, conv.last_inbound_at, human_agent=human_agent, now=at + WINDOW_MARGIN
    )
    if not may_send(later, "human"):
        raise _field_error(
            "send_at", "Pick a time at least 5 minutes before the reply window closes."
        )
    return at


async def _check_assets(session: AsyncSession, asset_ids: Sequence[uuid.UUID]) -> list[uuid.UUID]:
    unique = list(dict.fromkeys(asset_ids))
    if len(await repo.existing_asset_ids(session, unique)) != len(unique):
        raise _field_error("attachment_asset_ids", "An attachment wasn't found. Upload it again.")
    return unique


async def _check_capacity(session: AsyncSession) -> None:
    limit = entitlement(await current_plan(session), "pending_scheduled_messages")
    if limit is not None and await repo.count_pending(session) >= limit:
        raise ApiError("quota_exceeded", f"Your plan includes {limit} scheduled messages.")


# ---- the dispatcher's side (TR-JOB-03, FR-SMS-03)


def mark_claimed(session: AsyncSession, rows: Sequence[ScheduledRow], now: datetime) -> None:
    """The claim: rows the caller has locked become ``sending`` with one more attempt."""
    for row in rows:
        s = row.scheduled
        s.status = S.SENDING
        s.claimed_at = now
        s.attempts = (s.attempts or 0) + 1
        queue_updated(session, row)


def reset_stuck(session: AsyncSession, rows: Sequence[ScheduledRow]) -> dict[str, int]:
    """Locked rows stuck in ``sending``: back to ``scheduled`` so the dispatcher claims them
    again, or ``failed`` once they have been claimed MAX_ATTEMPTS times."""
    counts = {"reset": 0, "failed": 0}
    for row in rows:
        s = row.scheduled
        if (s.attempts or 0) >= MAX_ATTEMPTS:
            _finish(session, row, S.FAILED, error_code="internal", error_message=STUCK_REASON)
            counts["failed"] += 1
        else:
            s.status = S.SCHEDULED
            s.claimed_at = None
            queue_updated(session, row)
            counts["reset"] += 1
    return counts


async def send_claimed(
    session: AsyncSession,
    scheduled_message_id: uuid.UUID,
    *,
    human_agent_enabled: bool,
    now: datetime,
) -> SendOutcome:
    """send_scheduled's work, in the message's workspace scope. Call it with a session that has
    no other queued events: a refused send discards the ones the send pipeline queued.

    Only a claimed row that no other worker holds is sent, and its message has a client_id
    derived from the row, so a repeat or a concurrent run never sends twice.
    """
    row = await repo.lock_sending(session, scheduled_message_id)
    if row is None:
        return "skipped"  # already finished, reset, or being sent by another worker
    s = row.scheduled
    conv = await inbox.get_conversation(session, s.conversation_id)
    if conv is None:  # pragma: no cover - deleting the conversation deletes the row
        return "skipped"
    client_id = client_id_for(s.id)
    earlier = await repo.find_sent_message(session, conv.id, client_id)
    if earlier is not None:
        _finish(session, row, S.SENT, message_id=earlier.id)
        return "sent"

    human_agent = _human_agent(conv.platform, human_agent_enabled)
    window = reply_window(conv.platform, conv.last_inbound_at, human_agent=human_agent, now=now)
    if not may_send(window, "human"):
        await _expire(session, row)
        return "expired"

    try:
        async with session.begin_nested():
            message = await sending.queue_outbound(
                session,
                conv,
                source="human",
                client_id=client_id,
                text=s.text,
                attachment_asset_ids=list(s.attachment_asset_ids or []),
                sent_by_user_id=s.created_by_user_id,
                scheduled_message_id=s.id,
            )
            await session.flush()
    except ApiError as error:
        # The pipeline refused (TR-JOB-04: recorded, not re-raised). Its writes were rolled back
        # with the savepoint; drop the events it queued and reload the row.
        events.discard(session)
        await session.refresh(s)
        if error.code == "reply_window_closed":
            await _expire(session, row)
            return "expired"
        detail = error.detail or ERROR_CODES[error.code].title
        _finish(session, row, S.FAILED, error_code=error.code, error_message=detail)
        return "failed"
    _finish(session, row, S.SENT, message_id=message.id)
    return "sent"


def _finish(
    session: AsyncSession,
    row: ScheduledRow,
    status: S,
    *,
    message_id: uuid.UUID | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    s = row.scheduled
    s.status = status
    s.message_id = message_id
    s.error_code = error_code
    s.error_message = error_message
    queue_updated(session, row)


def _contact_name(row: ScheduledRow) -> str:
    contact = row.contact
    if contact.display_name:
        return contact.display_name
    if contact.username:
        return f"@{contact.username}"
    return "a customer"


async def _expire(session: AsyncSession, row: ScheduledRow) -> None:
    """FR-SMS-03: the window closed before the send time. Marked expired, owners notified."""
    _finish(session, row, S.EXPIRED, error_code="reply_window_closed", error_message=EXPIRED_REASON)
    s = row.scheduled
    await notify_admins(
        session,
        type="scheduled_message_expired",
        severity="warning",
        title="Scheduled message not sent",
        body=f"Scheduled message to {_contact_name(row)} wasn't sent: the reply window closed.",
        link=f"/inbox/{s.conversation_id}",
        dedupe_key=f"smsg_expired:{s.id}",
    )


# ---- following the message it became (Q-015)

MESSAGE_SENT = frozenset({"sent", "delivered", "read"})


async def follow_message(session: AsyncSession, msg: Message) -> None:
    """A scheduled message shows its send's final result (Q-015): its message failing makes the
    row failed with the same reason, and a later successful retry makes it sent again. Runs in the
    caller's transaction and queues scheduled_message.updated; rows already expired or canceled
    are left alone."""
    if msg.scheduled_message_id is None:
        return
    if msg.status == "failed":
        target, code, reason = S.FAILED, msg.error_code, msg.error_message
    elif msg.status in MESSAGE_SENT:
        target, code, reason = S.SENT, None, None
    else:
        return
    row = await repo.get(session, msg.scheduled_message_id, for_update=True)
    if row is None or row.scheduled.status not in (S.SENT, S.FAILED):
        return
    s = row.scheduled
    if (s.status, s.error_code) == (target, code):
        return
    _finish(session, row, target, message_id=msg.id, error_code=code, error_message=reason)
