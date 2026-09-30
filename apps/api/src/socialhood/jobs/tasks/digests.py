"""Weekly digest job (T8.7; FR-NOT-04, TR-JOB-02…06). Thin task: the work is in notify/digest.py.

- send_weekly_digests: periodic, every 15 minutes (``*/15 * * * *``, bulk lane, queueing lock
  ``send_weekly_digests``). The catalogue says hourly; a quarter-hourly tick is what lets a zone
  on a half or quarter hour (India is UTC+05:30) get its digest at 09:00 rather than 09:30. Lists
  the active workspaces and their time zones; for each where ``notify.digest.due_week_start``
  says it is Monday from 09:00 locally, and whose week has no weekly_digests row yet (one
  cross-workspace read; the tenant bypass is allowed in jobs/, TR-TEN-04), calls
  ``notify.digest.send_digest`` in that workspace's scope and commits: the claim, the numbers
  and the queued emails together, then the emails' deliver_email jobs. weekly_digests' unique
  (workspace, week_start) makes a second run, a retry or a concurrent run send nothing twice. One
  workspace failing is logged and retried on the next tick; the others go ahead.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.runtime import runtime
from socialhood.models.identity import Workspace, WorkspaceStatus
from socialhood.notify import digest
from socialhood.observability.logging import get_logger
from socialhood.repositories import weekly_digests

log = get_logger(__name__)


async def due_workspaces(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime
) -> list[tuple[uuid.UUID, date]]:
    """(workspace, week_start) pairs whose digest is due now and not claimed yet."""
    async with sessionmaker() as session:
        rows = await session.execute(
            select(Workspace.id, Workspace.timezone).where(
                Workspace.status == WorkspaceStatus.ACTIVE
            )
        )
        due = [
            (row.id, week)
            for row in rows
            if (week := digest.due_week_start(row.timezone, now)) is not None
        ]
        if not due:
            return []
        with tenant_bypass_scope():
            claimed = await weekly_digests.claimed_weeks(session, due)
    return [pair for pair in due if pair not in claimed]


async def send_due_digests(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> dict[str, int]:
    """Send every digest due at ``now``; returns counts by outcome."""
    now = now or datetime.now(UTC)
    counts: dict[str, int] = {}
    for workspace_id, week_start in await due_workspaces(sessionmaker, now):
        try:
            with workspace_scope(workspace_id):
                async with sessionmaker() as session:
                    outcome = await digest.send_digest(session, week_start=week_start, now=now)
                    await session.commit()
        except Exception:
            log.exception("digest_failed", workspace_id=str(workspace_id))
            outcome = "failed"
        counts[outcome] = counts.get(outcome, 0) + 1
    if counts:
        log.info("send_weekly_digests", **counts)
    return counts


@app.periodic(cron="*/15 * * * *", periodic_id="send_weekly_digests")
@app.task(name="send_weekly_digests", queue=BULK, queueing_lock="send_weekly_digests")
async def send_weekly_digests(timestamp: int) -> None:
    await send_due_digests(runtime().sessionmaker)
