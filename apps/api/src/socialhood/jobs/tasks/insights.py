"""Metric snapshots (T6.5; FR-ANL-01), bulk lane (TR-JOB-06). Thin tasks: the work is in
services/analytics (snapshots.py, account_daily.py).

- snapshot_post_metrics: every 15 minutes, queue snapshot_account_posts for each live account
  with a post whose window (1 h, 6 h, 24 h, 72 h, 7 d, 30 d after publishing) is due and not
  captured yet (key ``snap:{account_id}``).
- snapshot_account_posts(account_id): capture those windows; 1 h and 6 h hold the live counts
  only, insights start at 24 h behind the insights capability (IG_REQUEST_INSIGHTS_SCOPE), and
  the 72 h run marks the earlier snapshots final. Each window is captured once.
- snapshot_account_daily: hourly, queue snapshot_account_day for each live account once it is
  02:00 or later in its workspace's time zone and yesterday's row is missing
  (key ``acctday:{account_id}:{date}``).
- snapshot_account_day(account_id, day): one account_daily_metrics row per account per day
  (followers, and that day's account insights when granted).

The per-account jobs run in a per-workspace bulk slot; one that cannot take a slot defers a fresh
copy of itself 5 s later, which does not use up its retries. Rate limits wait for the platform's
regain time (PlatformRetry).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.fairness import BulkSemaphore, run_with_bulk_slot
from socialhood.jobs.retry import PlatformRetry
from socialhood.jobs.runtime import runtime
from socialhood.models.analytics import AccountDailyMetric
from socialhood.models.connections import SocialAccount
from socialhood.models.identity import Workspace
from socialhood.models.media import MediaItem
from socialhood.observability.logging import get_logger
from socialhood.platforms.buckets import TokenBuckets
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.services.analytics import account_daily, snapshots
from socialhood.services.analytics.ages import SNAPSHOT_HORIZON

log = get_logger(__name__)


async def _in_bulk_slot(
    task: Any, key: str, work: Callable[[], Awaitable[Any]], **kwargs: Any
) -> None:
    """Run ``work`` in the workspace's bulk slot, or defer ``task`` with ``kwargs`` again."""
    rt = runtime()

    async def requeue(delay_s: float) -> None:
        await enqueue(task, key=key, lock=key, delay_s=delay_s, **kwargs)

    semaphore = BulkSemaphore(rt.redis, rt.settings.bulk_concurrency_per_workspace)
    await run_with_bulk_slot(semaphore, kwargs["workspace_id"], work, requeue)


# ---------------------------------------------------------------- posts


@app.task(name="snapshot_account_posts", queue=BULK, retry=PlatformRetry(max_attempts=3))
async def snapshot_account_posts(workspace_id: str, account_id: str) -> None:
    rt = runtime()

    async def work() -> None:
        await snapshots.snapshot_account_posts(
            rt.sessionmaker,
            deps_from(rt.http, rt.settings),
            workspace_id=uuid.UUID(workspace_id),
            account_id=uuid.UUID(account_id),
            buckets=TokenBuckets(rt.redis),
        )

    await _in_bulk_slot(
        snapshot_account_posts,
        f"snap:{account_id}",
        work,
        workspace_id=workspace_id,
        account_id=account_id,
    )


async def queue_post_snapshots(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> int:
    """Queue snapshot_account_posts for every live account with a window due; returns how many
    were queued (an account already waiting is not queued twice)."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            rows = (
                await session.execute(
                    select(MediaItem.social_account_id, MediaItem.workspace_id)
                    .join(SocialAccount, SocialAccount.id == MediaItem.social_account_id)
                    .where(
                        SocialAccount.status.in_(snapshots.LIVE_STATUSES),
                        MediaItem.posted_at > now - SNAPSHOT_HORIZON,
                        snapshots.due_condition(now),
                    )
                    .distinct()
                )
            ).all()
    queued = 0
    for account_id, workspace_id in rows:
        queued += await enqueue(
            snapshot_account_posts,
            key=f"snap:{account_id}",
            lock=f"snap:{account_id}",
            workspace_id=str(workspace_id),
            account_id=str(account_id),
        )
    log.info("post_snapshots_queued", accounts=len(rows), queued=queued)
    return queued


@app.periodic(cron="*/15 * * * *", periodic_id="snapshot_post_metrics")
@app.task(name="snapshot_post_metrics", queue=BULK, queueing_lock="snapshot_post_metrics")
async def snapshot_post_metrics(timestamp: int) -> None:
    await queue_post_snapshots(runtime().sessionmaker)


# ---------------------------------------------------------------- accounts


@app.task(name="snapshot_account_day", queue=BULK, retry=PlatformRetry(max_attempts=3))
async def snapshot_account_day(workspace_id: str, account_id: str, day: str) -> None:
    rt = runtime()

    async def work() -> None:
        await account_daily.snapshot_account_day(
            rt.sessionmaker,
            deps_from(rt.http, rt.settings),
            workspace_id=uuid.UUID(workspace_id),
            account_id=uuid.UUID(account_id),
            day=date.fromisoformat(day),
        )

    await _in_bulk_slot(
        snapshot_account_day,
        f"acctday:{account_id}:{day}",
        work,
        workspace_id=workspace_id,
        account_id=account_id,
        day=day,
    )


def _measured(acct: SocialAccount, deps: PlatformDeps) -> bool:
    try:
        return snapshots.measured(adapter_for(acct, deps), acct)
    except PlatformError:
        return False


async def queue_account_days(
    sessionmaker: async_sessionmaker[AsyncSession],
    deps: PlatformDeps,
    now: datetime | None = None,
) -> int:
    """Queue snapshot_account_day for every live account whose latest due day (yesterday, from
    02:00 in its workspace's time zone) has no row yet; returns how many were queued."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            rows = (
                await session.execute(
                    select(SocialAccount, Workspace.timezone)
                    .join(Workspace, Workspace.id == SocialAccount.workspace_id)
                    .where(SocialAccount.status.in_(snapshots.LIVE_STATUSES))
                )
            ).all()
            due = {
                acct.id: (acct.workspace_id, account_daily.due_day(tz, now))
                for acct, tz in rows
                if _measured(acct, deps)
            }
            done: set[tuple[uuid.UUID, date]] = set()
            if due:
                pairs = [(account_id, day) for account_id, (_, day) in due.items()]
                stored = await session.execute(
                    select(AccountDailyMetric.social_account_id, AccountDailyMetric.date).where(
                        tuple_(AccountDailyMetric.social_account_id, AccountDailyMetric.date).in_(
                            pairs
                        )
                    )
                )
                done = {(a, d) for a, d in stored.all()}
    queued = 0
    for account_id, (workspace_id, day) in due.items():
        if (account_id, day) in done:
            continue
        queued += await enqueue(
            snapshot_account_day,
            key=f"acctday:{account_id}:{day.isoformat()}",
            lock=f"acctday:{account_id}:{day.isoformat()}",
            workspace_id=str(workspace_id),
            account_id=str(account_id),
            day=day.isoformat(),
        )
    log.info("account_days_queued", accounts=len(due), queued=queued)
    return queued


@app.periodic(cron="5 * * * *", periodic_id="snapshot_account_daily")
@app.task(name="snapshot_account_daily", queue=BULK, queueing_lock="snapshot_account_daily")
async def snapshot_account_daily(timestamp: int) -> None:
    rt = runtime()
    await queue_account_days(rt.sessionmaker, deps_from(rt.http, rt.settings))
