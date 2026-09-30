"""Billing jobs (T8.3; TR-BIL-03, TR-JOB-02…06). Thin tasks: the work is in billing/.

- reconcile_billing: TR-BIL-03's subscription reconciliation, periodic every 6 hours
  (``0 */6 * * *``, bulk lane, queueing lock, timeout 300 s). The job catalogue calls it
  reconcile_subscriptions, but that name is already the 6-hourly webhook re-subscription task
  (jobs/tasks/accounts.py, TR-WH-08), so this one is reconcile_billing. It lists the
  subscriptions that aren't Free across workspaces (the tenant bypass is allowed in jobs/,
  TR-TEN-04), then for each calls ``billing.reconcile.reconcile_one`` in that workspace's scope
  with ``billing.registry.get_dodo``: drift is corrected and logged, and a subscription past
  grace_until still on hold goes to Free (with the downgrade effects). A Dodo error skips that
  workspace until the next run.

Dodo webhook events are processed by the shared process_webhook_event job
(services/webhook_handlers/dodo.py), not here.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.billing.dodo import DodoClient
from socialhood.billing.reconcile import reconcile_one
from socialhood.billing.registry import get_dodo
from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.runtime import runtime
from socialhood.models.billing import Plan, Subscription
from socialhood.models.identity import Workspace, WorkspaceStatus
from socialhood.observability.logging import get_logger
from socialhood.realtime.events import commit_and_publish
from socialhood.settings import Settings

log = get_logger(__name__)

TIMEOUT_S = 300


async def _paid_workspaces(session: AsyncSession) -> list[uuid.UUID]:
    with tenant_bypass_scope():
        rows = await session.scalars(
            select(Subscription.workspace_id)
            .join(Workspace, Workspace.id == Subscription.workspace_id)
            .where(Subscription.plan != Plan.FREE, Workspace.status == WorkspaceStatus.ACTIVE)
            .order_by(Subscription.workspace_id)
        )
        return list(rows.all())


async def reconcile_all(
    sessionmaker: async_sessionmaker[AsyncSession],
    dodo: DodoClient,
    *,
    redis: Redis | None = None,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    now = now or datetime.now(UTC)
    counts = {"checked": 0, "corrected": 0, "failed": 0}
    async with sessionmaker() as session:
        workspace_ids = await _paid_workspaces(session)
    for workspace_id in workspace_ids:
        counts["checked"] += 1
        with workspace_scope(workspace_id):
            async with sessionmaker() as session:
                try:
                    result = await reconcile_one(session, dodo, now=now, settings=settings)
                    if redis is not None:
                        await commit_and_publish(session, redis)
                    else:
                        await session.commit()
                except Exception:
                    await session.rollback()
                    counts["failed"] += 1
                    log.exception("billing_reconcile_failed", workspace_id=str(workspace_id))
                    continue
        counts["corrected"] += int(result.drift)
    log.info("billing_reconcile_run", **counts)
    return counts


@app.periodic(cron="0 */6 * * *", periodic_id="reconcile_billing")
@app.task(name="reconcile_billing", queue=BULK, queueing_lock="reconcile_billing")
async def reconcile_billing(timestamp: int) -> None:
    rt = runtime()
    dodo = get_dodo(rt.http, rt.settings)
    await asyncio.wait_for(
        reconcile_all(rt.sessionmaker, dodo, redis=rt.redis, settings=rt.settings),
        timeout=TIMEOUT_S,
    )
