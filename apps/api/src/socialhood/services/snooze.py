"""Snoozed conversations coming back (GR-45).

A snoozed conversation (``conversations.snoozed_until``) is hidden from every inbox view but
"snoozed" and from the counts and the priority queue. The wake_snoozed job (jobs/tasks/snooze.py)
calls ``wake`` for each one whose time has come; a new customer message wakes it early
(services/ingest). Setting and clearing the snooze by hand is services/conversations.

shortcut: a woken conversation returns to its normal place in the list (by its last message), not
the top; moving it up would need its own sort key. Revisit if people ask.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.inbox import Conversation
from socialhood.models.notifications import NotificationType
from socialhood.realtime import events
from socialhood.repositories import inbox
from socialhood.services.follow_ups import contact_name
from socialhood.services.notifications import notify_user


async def wake(
    session: AsyncSession, conv: Conversation, *, now: datetime, human_agent: bool
) -> None:
    """End the snooze: unread again, the assignee told, and conversation.updated queued. Runs in
    the conversation's workspace scope on a row the caller locked; the caller commits with
    commit_and_publish."""
    until = conv.snoozed_until
    conv.snoozed_until = None
    conv.unread_count = max(1, conv.unread_count)
    await session.flush()
    contact = await inbox.get_contact(session, conv.contact_id)
    if conv.assignee_user_id is not None and until is not None:
        await notify_user(
            session,
            conv.assignee_user_id,
            type=NotificationType.CONVERSATION_SNOOZE_ENDED,
            severity="info",
            title=f"Snoozed: {contact_name(contact)} is back",
            body="The conversation you snoozed is back in your inbox.",
            link=f"/inbox/{conv.id}",
            dedupe_key=f"snooze_ended:{conv.id}:{until.isoformat()}",
        )
    await events.queue_conversation(
        session, conv, now=now, human_agent=human_agent, contact=contact
    )
