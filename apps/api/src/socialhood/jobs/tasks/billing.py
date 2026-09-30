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

- cancel_orphan_subscription(subscription_id): bulk lane, queueing lock
  ``dodo_cancel:{subscription_id}``, queued by the Dodo webhook handler for a live subscription
  whose workspace was deleted (C-060). Cancels it at once (billing/orphans.py); retries while Dodo
  times out or answers 429/5xx.

Dodo webhook events are processed by the shared process_webhook_event job
(services/webhook_handlers/dodo.py), not here.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from procrastinate import BaseRetryStrategy, RetryDecision
from procrastinate.jobs import Job
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.billing.dodo import DodoClient, DodoError
from socialhood.billing.orphans import cancel_orphan
from socialhood.billing.reconcile import reconcile_one
from socialhood.billing.registry import get_dodo
from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.retry import BASE_DELAY_S, MAX_DELAY_S
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


class DodoRetry(BaseRetryStrategy):
    """Retry a retryable DodoError (timeout, 429, 5xx) with the usual backoff (10 s doubling,
    capped at 10 minutes): 8 tries cover about 25 minutes of Dodo being down. A final failure
    reaches Sentry with the subscription id, next to the alert that queued it."""

    def __init__(self, max_attempts: int = 8) -> None:
        self.max_attempts = max_attempts

    def get_retry_decision(self, *, exception: BaseException, job: Job) -> RetryDecision | None:
        if not isinstance(exception, DodoError) or not exception.retryable:
            return None
        if job.attempts + 1 >= self.max_attempts:
            return None
        return RetryDecision(
            retry_in={"seconds": min(MAX_DELAY_S, BASE_DELAY_S << min(job.attempts, 16))}
        )


@app.task(name="cancel_orphan_subscription", queue=BULK, retry=DodoRetry())
async def cancel_orphan_subscription(subscription_id: str) -> None:
    """A live subscription whose workspace was deleted: cancel it in Dodo now (C-060)."""
    rt = runtime()
    await cancel_orphan(get_dodo(rt.http, rt.settings), subscription_id)


@app.periodic(cron="0 */6 * * *", periodic_id="reconcile_billing")
@app.task(name="reconcile_billing", queue=BULK, queueing_lock="reconcile_billing")
async def reconcile_billing(timestamp: int) -> None:
    rt = runtime()
    dodo = get_dodo(rt.http, rt.settings)
    await asyncio.wait_for(
        reconcile_all(rt.sessionmaker, dodo, redis=rt.redis, settings=rt.settings),
        timeout=TIMEOUT_S,
    )
