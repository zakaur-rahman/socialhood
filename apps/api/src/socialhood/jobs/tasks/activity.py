"""Activity alerts (GR-05): check_automation_failures runs every 10 minutes (interactive lane).
It finds automations with five or more failed runs in the last hour, across workspaces (a
cross-workspace lookup, allowed in jobs/ by TR-TEN-04), and tells each workspace's owners and
admins once per six hours (services/activity/alerts.py). A re-run is harmless: the notification
has a dedupe key."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.runtime import runtime
from socialhood.observability.logging import get_logger
from socialhood.repositories import activity as repo
from socialhood.services.activity import alerts

log = get_logger(__name__)

BATCH = 200


async def alert_failing_automations(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> int:
    """Notify the owners and admins of each automation that failed too often; returns the number
    of automations that had a new alert."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            failing = await repo.failing_automations(
                session, since=now - alerts.WINDOW, at_least=alerts.FAILING_RUNS, limit=BATCH
            )
        alerted = 0
        for row in failing:
            with workspace_scope(row.workspace_id):
                alerted += 1 if await alerts.alert(session, row, now) else 0
        await session.commit()
    if alerted:
        log.info("automation_failing_alerts", count=alerted)
    return alerted


@app.periodic(cron="*/10 * * * *", periodic_id="check_automation_failures")
@app.task(
    name="check_automation_failures",
    queue=INTERACTIVE,
    queueing_lock="check_automation_failures",
)
async def check_automation_failures(timestamp: int) -> None:
    await alert_failing_automations(runtime().sessionmaker)
