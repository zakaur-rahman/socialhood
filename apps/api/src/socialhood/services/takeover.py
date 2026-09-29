"""Human takeover notes (T5.6; FR-SUG-05, F-09).

When a person replies (Social Hood, a scheduled message or the native app), services/sending
pauses Auto for the takeover period. If the conversation is in Auto and was not already paused,
a system note says so: "AI paused until 16:40 because you replied" (the workspace's time zone;
"16:40 tomorrow" past midnight; "until you resume it" for a pause without an end). Resume
(PATCH …/conversations/{id} {resume_ai: true}) ends the pause now with the note "AI resumed".

Notes are messages with direction, source and kind ``system``; they do not change the
conversation's last-message fields (the list keeps showing the reply). message.created is queued
on the caller's session.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.identity import Workspace
from socialhood.models.inbox import Conversation, Direction, Message, MessageKind, MessageSource
from socialhood.realtime import events
from socialhood.repositories import social_accounts

NOTE_OFFSET = timedelta(milliseconds=1)  # the note sorts after the reply that caused it
UNTIL_RESUMED_YEAR = 9999
RESUMED = "AI resumed"


async def effective_mode(session: AsyncSession, conv: Conversation) -> str:
    """The conversation's override, else its account's mode (FR-SUG-01)."""
    if conv.ai_mode_override:
        return conv.ai_mode_override
    acct = await social_accounts.get(session, conv.social_account_id)
    return acct.ai_mode if acct is not None else "off"


async def _zone(session: AsyncSession, conv: Conversation) -> ZoneInfo:
    name = await session.scalar(select(Workspace.timezone).where(Workspace.id == conv.workspace_id))
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def pause_text(until: datetime, now: datetime, zone: ZoneInfo) -> str:
    if until.year >= UNTIL_RESUMED_YEAR:
        return "AI paused until you resume it because you replied"
    local_until, local_now = until.astimezone(zone), now.astimezone(zone)
    when = local_until.strftime("%H:%M")
    if local_until.date() == local_now.date() + timedelta(days=1):
        when = f"{when} tomorrow"
    elif local_until.date() != local_now.date():
        when = f"{when} on {local_until.strftime('%d %b')}"
    return f"AI paused until {when} because you replied"


async def add_note(
    session: AsyncSession, conv: Conversation, text: str, *, at: datetime
) -> Message:
    note = Message(
        conversation_id=conv.id,
        social_account_id=conv.social_account_id,
        direction=Direction.SYSTEM,
        source=MessageSource.SYSTEM,
        kind=MessageKind.SYSTEM,
        text=text,
        occurred_at=at,
        attachments=[],
        buttons=[],
        quick_replies=[],
        reactions=[],
    )
    session.add(note)
    await session.flush()
    await session.refresh(note)
    events.queue_message(session, note, created=True)
    return note


async def paused_note(
    session: AsyncSession, conv: Conversation, *, until: datetime, now: datetime
) -> Message | None:
    """The takeover note, when the conversation is in Auto (else a pause changes nothing the
    user sees)."""
    if await effective_mode(session, conv) != "auto":
        return None
    until = until if until.tzinfo else until.replace(tzinfo=UTC)
    text = pause_text(until, now, await _zone(session, conv))
    return await add_note(session, conv, text, at=now + NOTE_OFFSET)


async def resumed_note(session: AsyncSession, conv: Conversation, *, now: datetime) -> Message:
    return await add_note(session, conv, RESUMED, at=now)
