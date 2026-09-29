"""The weekly digest (T8.7; FR-NOT-04).

Monday 09:00 in the workspace time zone: messages received, reply rate, median first response,
share handled by AI, top three intents, top three unanswered questions (FR-KB-06), conversations
still "Needs you", and the post with most comments, over the 7 days before. The numbers come
from the same queries as the overview endpoint, so they match it (T8.7's acceptance).

- ``due_week_start(timezone, now)``: the Monday (local date) when it is Monday 09:00-09:59 there,
  else None; send_weekly_digests runs hourly and asks this for each active workspace.
- ``send_digest``: claims the week (insert weekly_digests, unique per workspace and week_start;
  a conflict means it was already sent), computes the numbers once, and queues one email per
  member with ``email_digest`` on (notify/outbox.queue_email, dedupe
  ``digest:{week_start}:{user_id}``) with List-Unsubscribe headers carrying a signed token
  (notify/unsubscribe.py). A week with no activity is ``skipped``.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.settings import Settings

SEND_HOUR = 9  # local time, Monday


def due_week_start(timezone: str, now: datetime) -> date | None:
    raise NotImplementedError("T8.7")


async def send_digest(
    session: AsyncSession, *, week_start: date, settings: Settings, now: datetime
) -> str:
    """Send (queue) the current workspace's digest for that week; returns its final status."""
    raise NotImplementedError("T8.7")
