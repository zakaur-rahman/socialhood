"""The weekly digest (T8.7; FR-NOT-04).

Monday 09:00 in the workspace time zone: messages received, reply rate, median first response,
share handled by AI, top three intents, top three unanswered questions (FR-KB-06), conversations
still "Needs you", and the post with most comments, over the Monday to Sunday before. The numbers
come from services/overview_stats.py, the functions the overview endpoint uses (T9.1), so they
match it (T8.7's acceptance).

- ``due_week_start(timezone, now)``: the local Monday when it is Monday from 09:00 on there, else
  None. send_weekly_digests runs every 15 minutes, so a zone on a half or quarter hour (India,
  Nepal) gets its digest at 09:00 too, and a run missed by an outage catches up later that
  Monday; weekly_digests' unique (workspace, week_start) keeps it to once a week.
- ``send_digest``: in one transaction, claims the week (insert weekly_digests; a conflict means
  it was sent or is being sent: nothing to do), computes the numbers once, and queues one email
  per member with ``email_digest`` on (notify/outbox.queue_email, dedupe
  ``digest:{week_start}:{user_id}``), then records sent with the numbers and the recipient count.
  A week with nothing to report (no messages, no comments, nobody waiting) or nobody opted in is
  ``skipped``. The emails carry a signed unsubscribe link and List-Unsubscribe headers, added
  when they are sent (notify/outbox.py). A failure rolls the claim back, so the next run tries
  again.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.identity import User, Workspace, WorkspaceMember
from socialhood.models.notifications import DigestStatus, EmailTemplate
from socialhood.notify import preferences
from socialhood.notify.outbox import queue_email
from socialhood.observability.logging import get_logger
from socialhood.repositories import weekly_digests as repo
from socialhood.services import overview_stats
from socialhood.services.analytics.common import zone

log = get_logger(__name__)

SEND_HOUR = 9  # local time, Monday
MONDAY = 0


def due_week_start(timezone: str, now: datetime) -> date | None:
    """The Monday (local date) whose digest is due at ``now``: Monday from 09:00 local until
    the day ends. An unknown zone name reads as UTC (like the analytics ranges)."""
    local = now.astimezone(zone(timezone))
    if local.weekday() != MONDAY or local.hour < SEND_HOUR:
        return None
    return local.date()


def dedupe_key(week_start: date, user_id: uuid.UUID) -> str:
    return f"digest:{week_start.isoformat()}:{user_id}"


async def _recipients(session: AsyncSession) -> list[tuple[uuid.UUID, str]]:
    """(user id, email) of the current workspace's members with the digest on."""
    rows = await session.execute(
        select(WorkspaceMember.user_id, WorkspaceMember.notification_prefs, User.email)
        .join(User, User.id == WorkspaceMember.user_id)
        .order_by(WorkspaceMember.created_at)
    )
    return [
        (row.user_id, row.email)
        for row in rows
        if row.email and preferences.wants_digest(row.notification_prefs)
    ]


async def send_digest(session: AsyncSession, *, week_start: date, now: datetime) -> str:
    """Queue the current workspace's digest for that week; returns ``sent``, ``skipped``, or
    ``already`` when the week was claimed before. The caller commits; the emails' jobs are
    deferred on commit."""
    workspace = await session.get(Workspace, require_workspace())
    if workspace is None:
        return "missing"
    digest_id = await repo.claim(session, week_start)
    if digest_id is None:
        return "already"
    span = overview_stats.week_before(workspace.timezone, week_start)
    stats = await overview_stats.compute(session, span=span, now=now)
    numbers = stats.to_json()
    recipients = await _recipients(session) if stats.active else []
    if not recipients:
        await repo.finish(
            session,
            digest_id,
            status=DigestStatus.SKIPPED,
            recipients=0,
            stats=numbers,
            sent_at=None,
            error="Nothing happened this week" if not stats.active else "Nobody gets the digest",
        )
        log.info("digest_skipped", week_start=week_start.isoformat(), active=stats.active)
        return DigestStatus.SKIPPED
    data = {"workspace_name": workspace.name, "workspace_slug": workspace.slug, "stats": numbers}
    queued = 0
    for user_id, email in recipients:
        delivery = await queue_email(
            session,
            template=EmailTemplate.WEEKLY_DIGEST,
            to_email=email,
            dedupe_key=dedupe_key(week_start, user_id),
            data=data,
            user_id=user_id,
        )
        queued += delivery is not None
    await repo.finish(
        session,
        digest_id,
        status=DigestStatus.SENT,
        recipients=queued,
        stats=numbers,
        sent_at=now,
    )
    log.info("digest_queued", week_start=week_start.isoformat(), recipients=queued)
    return DigestStatus.SENT
