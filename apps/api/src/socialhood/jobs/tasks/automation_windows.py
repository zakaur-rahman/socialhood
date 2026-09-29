"""Run windows (FR-AUT-17): pause automations past their end and tell their creator (T4.7).

end_automation_windows runs every minute. It locks active automations whose ends_at has passed,
across workspaces (a cross-workspace lookup, allowed in jobs/ by TR-TEN-04), with FOR UPDATE SKIP
LOCKED so two runs never end the same one, then pauses each in its workspace and notifies the
workspace's owners and admins "{name} ended" (services/automations/windows.py). Automations before
their start need nothing: the runtime only loads automations inside their window.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.runtime import runtime
from socialhood.observability.logging import get_logger
from socialhood.repositories import automations as repo
from socialhood.services.automations import windows

log = get_logger(__name__)

BATCH = 500


async def end_past_windows(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> list[uuid.UUID]:
    """Pause and announce the automations whose run window has ended; returns their ids."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            ended = await repo.lock_past_end(session, now, BATCH)
        for automation in ended:
            with workspace_scope(automation.workspace_id):
                await windows.end_window(session, automation, now)
        await session.commit()
    if ended:
        log.info("automation_windows_ended", count=len(ended))
    return [a.id for a in ended]


@app.periodic(cron="* * * * *", periodic_id="end_automation_windows")
@app.task(name="end_automation_windows", queue=INTERACTIVE, queueing_lock="end_automation_windows")
async def end_automation_windows(timestamp: int) -> None:
    await end_past_windows(runtime().sessionmaker)
