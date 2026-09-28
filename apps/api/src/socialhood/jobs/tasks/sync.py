"""sync_media and backfill_account after a connect (T3.14, FR-CON-01), and the 6-hourly media
sync for every live account (job catalogue).

Bulk lane, each in a per-workspace bulk slot (TR-JOB-06): a job that cannot take a slot defers a
fresh copy of itself 5 s later, which does not use up its retries. The work is in services/sync.py.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select

from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.fairness import BulkSemaphore, run_with_bulk_slot
from socialhood.jobs.retry import PlatformRetry
from socialhood.jobs.runtime import runtime
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import deps_from
from socialhood.services import sync

log = get_logger(__name__)


async def _in_bulk_slot(
    task: Any, key: str, workspace_id: str, account_id: str, work: Callable[[], Awaitable[Any]]
) -> None:
    rt = runtime()

    async def requeue(delay_s: float) -> None:
        await enqueue(
            task, key=key, delay_s=delay_s, workspace_id=workspace_id, account_id=account_id
        )

    semaphore = BulkSemaphore(rt.redis, rt.settings.bulk_concurrency_per_workspace)
    await run_with_bulk_slot(semaphore, workspace_id, work, requeue)


@app.task(name="sync_media", queue=BULK, retry=PlatformRetry(max_attempts=2))
async def sync_media(workspace_id: str, account_id: str) -> None:
    rt = runtime()

    async def work() -> None:
        await sync.sync_account_media(
            rt.sessionmaker,
            deps_from(rt.http, rt.settings),
            workspace_id=uuid.UUID(workspace_id),
            account_id=uuid.UUID(account_id),
        )

    await _in_bulk_slot(sync_media, f"mediasync:{account_id}", workspace_id, account_id, work)


@app.task(name="backfill_account", queue=BULK, retry=PlatformRetry(max_attempts=2))
async def backfill_account(workspace_id: str, account_id: str) -> None:
    rt = runtime()

    async def work() -> None:
        await sync.backfill_account(
            rt.sessionmaker,
            rt.redis,
            deps_from(rt.http, rt.settings),
            workspace_id=uuid.UUID(workspace_id),
            account_id=uuid.UUID(account_id),
        )

    await _in_bulk_slot(backfill_account, f"backfill:{account_id}", workspace_id, account_id, work)


@app.periodic(cron="20 */6 * * *", periodic_id="sync_all_media")
@app.task(name="sync_all_media", queue=BULK, queueing_lock="sync_all_media")
async def sync_all_media(timestamp: int) -> None:
    """Every 6 hours: queue sync_media for each live account (it skips accounts without posts)."""
    async with runtime().sessionmaker() as session:
        with tenant_bypass_scope():
            rows = (
                await session.execute(
                    select(SocialAccount.id, SocialAccount.workspace_id).where(
                        SocialAccount.status.in_([AccountStatus.ACTIVE, AccountStatus.ERROR])
                    )
                )
            ).all()
    queued = 0
    for account_id, workspace_id in rows:
        queued += await enqueue(
            sync_media,
            key=f"mediasync:{account_id}",
            workspace_id=str(workspace_id),
            account_id=str(account_id),
        )
    log.info("media_sync_run", accounts=len(rows), queued=queued)
