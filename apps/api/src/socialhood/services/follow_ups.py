"""Follow-up reminders before a reply window closes (T5.11; FR-INB-14, F-18).

``check_closing_windows`` runs every 15 minutes (jobs/tasks/analysis.py). It locks open
conversations with lead score >= 60 whose customer last wrote 18 to 22 hours ago, that were not
yet reminded for that message (``window_reminder_for`` <> ``last_inbound_at``) and where the
business sent nothing in the last 2 hours; for each, in its workspace, ``remind`` records the
reminder, publishes conversation.updated (the "Closing soon" signal, inbox_views.closing_soon)
and notifies the members (in-app and push): "Follow up with Priya: the reply window closes in 6 h",
linking to the conversation with the schedule popover open (``?schedule=1``).

One reminder per window: a new customer message moves ``last_inbound_at`` and so starts a new
window; the dedupe key holds the message's time too.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.inbox import Contact, Conversation
from socialhood.realtime import events
from socialhood.repositories import inbox
from socialhood.services.inbox_views import LEAD_SCORE, REMINDER_FROM
from socialhood.services.notifications import notify_members
from socialhood.services.reply_window import STANDARD_WINDOW

REMINDER_LEAD_SCORE = LEAD_SCORE
WROTE_BETWEEN = (REMINDER_FROM, timedelta(hours=22))
QUIET_FOR = timedelta(hours=2)
BATCH = 500


def contact_name(contact: Contact | None) -> str:
    if contact is not None and contact.display_name:
        return contact.display_name
    if contact is not None and contact.username:
        return f"@{contact.username}"
    return "a customer"


def _hours_left(last_inbound_at: datetime, now: datetime) -> int:
    left = last_inbound_at + STANDARD_WINDOW - now
    return max(1, round(left / timedelta(hours=1)))


async def remind(
    session: AsyncSession, conv: Conversation, *, now: datetime, human_agent: bool
) -> None:
    """Record and announce one reminder. Runs in the conversation's workspace scope on a row the
    caller locked; the caller commits with commit_and_publish."""
    last = conv.last_inbound_at
    if last is None:  # pragma: no cover - the due query requires it
        return
    conv.window_reminder_for = last
    await session.flush()
    contact = await inbox.get_contact(session, conv.contact_id)
    name = contact_name(contact)
    await notify_members(
        session,
        type="window_closing",
        severity="warning",
        title=f"Follow up with {name}",
        body=f"Follow up with {name}: the reply window closes in {_hours_left(last, now)} h.",
        link=f"/inbox/{conv.id}?schedule=1",
        dedupe_key=f"window_closing:{conv.id}:{last.isoformat()}",
        channels=("in_app", "push"),
    )
    if contact is not None:
        await events.queue_conversation(
            session, conv, now=now, human_agent=human_agent, contact=contact
        )
