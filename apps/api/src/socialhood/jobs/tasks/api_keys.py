"""notify_expiring_api_keys (C-167): owners and admins hear, in the app, 7 days before an API key
expires.

Daily at 05:15 UTC (bulk lane, singleton). It finds unrevoked keys that expire within 7 days and
whose owners weren't told yet, across workspaces (tenant_bypass_scope, allowed in jobs/ by
TR-TEN-04), then notifies each in its own workspace scope (services/api_keys.notify_expiring),
which records ``expiry_notified_at``: a key is announced once, and a run that dies before it
commits changes nothing. A key made to expire in under 7 days (none can be: 30 days is the
shortest) would be announced on the next run.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.runtime import runtime
from socialhood.observability.logging import get_logger
from socialhood.repositories import api_keys as repo
from socialhood.services import api_keys

log = get_logger(__name__)

BATCH = 500


async def notify_expiring(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> list[uuid.UUID]:
    """Announce every key expiring within ``api_keys.EXPIRY_NOTICE``; returns their ids."""
    now = now or datetime.now(UTC)
    told: list[uuid.UUID] = []
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            due = await repo.expiring_unnoticed(
                session, now, now + api_keys.EXPIRY_NOTICE, limit=BATCH
            )
        for key_id, workspace_id in due:
            with workspace_scope(workspace_id):
                if await api_keys.notify_expiring(session, key_id, now=now):
                    told.append(key_id)
        await session.commit()
    if told:
        log.info("api_keys_expiring_notified", count=len(told))
    return told


@app.periodic(cron="15 5 * * *", periodic_id="notify_expiring_api_keys")
@app.task(name="notify_expiring_api_keys", queue=BULK, queueing_lock="notify_expiring_api_keys")
async def notify_expiring_api_keys(timestamp: int) -> None:
    await notify_expiring(runtime().sessionmaker)
