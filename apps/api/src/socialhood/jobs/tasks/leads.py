"""mark_cold_leads (GR-18): the "gone cold" job.

Runs hourly. It locks qualified and follow-up leads whose customer has not written for their
workspace's ``lead_cold_days`` (counted from the last message or the last stage change, whichever
is later) and that are not flagged since that message, across workspaces (FOR UPDATE SKIP LOCKED
inside tenant_bypass_scope, allowed in jobs/ by TR-TEN-04), then flags each in its own workspace
scope (services/leads.go_cold). Idempotent: a flagged lead is no longer selected, and a run that
dies before it commits changes nothing. The rules are in services/leads.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.runtime import runtime
from socialhood.observability.logging import get_logger
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import leads as repo
from socialhood.services import leads

log = get_logger(__name__)

BATCH = 500


async def mark_cold(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    now: datetime | None = None,
) -> list[uuid.UUID]:
    """Flag every lead that has gone cold; returns their contact ids."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            due = await repo.lock_cold(session, now=now, limit=BATCH)
        for contact, conv, days in due:
            with workspace_scope(contact.workspace_id):
                await leads.go_cold(session, contact, conv, days=days, now=now)
        await commit_and_publish(session, redis)
    if due:
        log.info("leads_gone_cold", count=len(due))
    return [contact.id for contact, _, _ in due]


@app.periodic(cron="10 * * * *", periodic_id="mark_cold_leads")
@app.task(name="mark_cold_leads", queue=BULK, queueing_lock="mark_cold_leads")
async def mark_cold_leads(timestamp: int) -> None:
    rt = runtime()
    await mark_cold(rt.sessionmaker, rt.redis)
