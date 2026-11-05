"""Billing jobs (T8.3; TR-BIL-03, TR-JOB-02…06). Thin tasks: the work is in billing/.

- reconcile_billing: TR-BIL-03's subscription reconciliation, periodic every 6 hours
  (``0 */6 * * *``, bulk lane, queueing lock, timeout 300 s). The job catalogue calls it
  reconcile_subscriptions, but that name is already the 6-hourly webhook re-subscription task
  (jobs/tasks/accounts.py, TR-WH-08), so this one is reconcile_billing. It lists the
  subscriptions that aren't Free across workspaces (the tenant bypass is allowed in jobs/,
  TR-TEN-04), then for each calls ``billing.reconcile.reconcile_one`` in that workspace's scope
  with ``billing.registry.get_dodo``: drift is corrected and logged, and a subscription past
  grace_until still on hold goes to Free (with the downgrade effects). A Dodo error skips that
  workspace until the next run, except that a subscription Dodo says it doesn't have goes to Free
  once ``_settle_missing`` is sure of it.

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

from socialhood.billing import lifecycle
from socialhood.billing.dodo import DodoClient, DodoError
from socialhood.billing.orphans import cancel_orphan
from socialhood.billing.reconcile import (
    MISSING_RUNS,
    dodo_key_works,
    reconcile_one,
    too_many_missing,
)
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
MISSING_KEY_TTL_S = 13 * 3600  # over two runs: a run that finds it lets the count lapse


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
    missing: list[uuid.UUID] = []
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
        if result.missing:
            missing.append(workspace_id)
    if missing and redis is not None and settings is not None:
        counts["corrected"] += await _settle_missing(
            sessionmaker, dodo, redis, settings, missing, checked=counts["checked"], now=now
        )
    log.info("billing_reconcile_run", **counts)
    return counts


async def _settle_missing(
    sessionmaker: async_sessionmaker[AsyncSession],
    dodo: DodoClient,
    redis: Redis,
    settings: Settings,
    missing: list[uuid.UUID],
    *,
    checked: int,
    now: datetime,
) -> int:
    """Free for the subscriptions Dodo has said it doesn't have for MISSING_RUNS runs in a row.
    Returns how many."""
    if too_many_missing(len(missing), checked):
        log.error(
            "alert",
            kind="billing_many_subscriptions_missing",
            detail=f"Dodo has no record of {len(missing)} of {checked} paid subscriptions",
        )
        return 0
    if not await dodo_key_works(dodo, settings):
        log.warning("billing_missing_skipped", reason="the Dodo key can't read our product")
        return 0
    expired = 0
    for workspace_id in missing:
        key = f"billing:missing:{workspace_id}"
        try:
            runs = await redis.incr(key)
            await redis.expire(key, MISSING_KEY_TTL_S)
        except Exception as error:
            log.warning("billing_missing_uncounted", error=type(error).__name__)
            return expired
        if runs < MISSING_RUNS:
            continue
        with workspace_scope(workspace_id):
            async with sessionmaker() as session:
                await lifecycle.expire_now(session, now=now, reason="Dodo has no such subscription")
                await commit_and_publish(session, redis)
        log.error(
            "alert",
            kind="billing_subscription_missing",
            detail=f"workspace {workspace_id} moved to Free: Dodo has no such subscription",
        )
        expired += 1
    return expired


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
    if not rt.settings.billing_enabled:
        return  # C-149: no Dodo to reconcile with; every workspace is on Free
    dodo = get_dodo(rt.http, rt.settings)
    await asyncio.wait_for(
        reconcile_all(rt.sessionmaker, dodo, redis=rt.redis, settings=rt.settings),
        timeout=TIMEOUT_S,
    )
