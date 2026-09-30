"""Deletion and retention jobs (T9.6; FR-ACC-05, §5.9). Thin tasks: the workspace purge is in
services/workspace_deletion.py, the retention deletes in repositories/retention.py.

- purge_workspace(workspace_id): bulk lane, queueing lock and run lock ``purge:{id}`` (queued when
  a deletion commits). Retries any failure with backoff (10 s doubling, capped at 10 minutes, 8
  tries); a run that uses up its time budget queues the next one.
- sweep_deletions: periodic, every 15 minutes (bulk lane, singleton). Re-queues the purge of every
  workspace still deleting (a lost enqueue, a purge that ran out of retries) and alerts on one
  still deleting after 6 hours.
- purge_expired: periodic, daily 04:00 UTC (bulk lane, singleton, 600 s), §5.9's retention:
  webhook events 30 days (TR-WH-07; failed ones too, TR-OPS-04), notifications 90 days, AI usage
  events 13 months, finished agent runs 180 days (TR-AGT-08), messages beyond the plan's
  message_history_days (Free: 90) with the conversations they leave empty, and finished queue jobs
  30 days (TR-OPS-04). It also sweeps deletions. Idempotency keys live in Valkey with a 24-hour
  TTL (services/idempotency.py) and audit_logs doesn't exist in R1, so neither has a rule here.
"""

from __future__ import annotations

import asyncio
import calendar
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from procrastinate import BaseRetryStrategy, RetryDecision
from procrastinate.jobs import Job
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.billing.plans import PLANS, entitlement
from socialhood.billing.registry import get_dodo
from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.retry import BASE_DELAY_S, MAX_DELAY_S
from socialhood.jobs.runtime import runtime
from socialhood.media.purge import get_media_purger
from socialhood.observability.logging import get_logger
from socialhood.repositories import retention
from socialhood.services import workspace_deletion as deletion

log = get_logger(__name__)

PURGE_EXPIRED_TIMEOUT_S = 600
PURGE_EXPIRED_BUDGET_S = 540.0  # stop starting batches in time to commit and log
RETENTION_BATCH = 5000

WEBHOOK_EVENTS_KEPT = timedelta(days=30)
NOTIFICATIONS_KEPT = timedelta(days=90)
AGENT_RUNS_KEPT = timedelta(days=180)
AI_USAGE_KEPT_MONTHS = 13
FINISHED_JOBS_KEPT_HOURS = 30 * 24


# ---------------------------------------------------------------- purge_workspace


class PurgeRetry(BaseRetryStrategy):
    """Any failure is retried: Dodo, Cloudinary or Valkey not answering (PurgeBlocked), or the
    database. After the last try, sweep_deletions queues it again."""

    def __init__(self, max_attempts: int = 8) -> None:
        self.max_attempts = max_attempts

    def get_retry_decision(self, *, exception: BaseException, job: Job) -> RetryDecision | None:
        if job.attempts + 1 >= self.max_attempts:
            return None
        return RetryDecision(
            retry_in={"seconds": min(MAX_DELAY_S, BASE_DELAY_S << min(job.attempts, 16))}
        )


@app.task(name="purge_workspace", queue=BULK, retry=PurgeRetry())
async def purge_workspace(workspace_id: str) -> None:
    rt = runtime()
    deps = deletion.PurgeDeps(
        sessionmaker=rt.sessionmaker,
        redis=rt.redis,
        dodo=get_dodo(rt.http, rt.settings),
        media=get_media_purger(rt.http, rt.settings),
    )
    wid = uuid.UUID(workspace_id)
    result = await deletion.purge_workspace(deps, wid)
    if result.status == "continue":
        await deletion.enqueue_purge(wid)


@app.periodic(cron="*/15 * * * *", periodic_id="sweep_deletions")
@app.task(name="sweep_deletions", queue=BULK, queueing_lock="sweep_deletions")
async def sweep_deletions(timestamp: int) -> None:
    await deletion.sweep(runtime().sessionmaker, datetime.now(UTC))


# ---------------------------------------------------------------- purge_expired


def months_before(at: datetime, months: int) -> datetime:
    """The same day and time ``months`` calendar months earlier (the month's last day when that
    month is shorter)."""
    index = at.year * 12 + at.month - 1 - months
    year, month = divmod(index, 12)
    day = min(at.day, calendar.monthrange(year, month + 1)[1])
    return at.replace(year=year, month=month + 1, day=day)


def history_limits() -> dict[str, int]:
    """Plans with a finite message history, and its length in days (§1.7)."""
    limits: dict[str, int] = {}
    for plan in PLANS:
        days = entitlement(plan, "message_history_days")
        if days is not None:
            limits[plan] = int(days)
    return limits


Batch = Callable[[AsyncSession], Awaitable[int]]


async def purge_expired_rows(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    now: datetime | None = None,
    batch: int = RETENTION_BATCH,
    budget_s: float = PURGE_EXPIRED_BUDGET_S,
) -> dict[str, int]:
    """Apply §5.9's retention rules, a batch per transaction, until done or the budget is spent
    (the next day's run continues). Returns the rows deleted per rule."""
    now = now or datetime.now(UTC)
    deadline = time.monotonic() + budget_s
    counts: dict[str, int] = {}

    async def drain(rule: str, delete: Batch) -> bool:
        """False once the time is up."""
        while True:
            async with sessionmaker() as session:
                n = await delete(session)
                await session.commit()
            counts[rule] = counts.get(rule, 0) + n
            if n < batch:
                return True
            if time.monotonic() > deadline:
                return False

    webhook_cutoff = now - WEBHOOK_EVENTS_KEPT
    notification_cutoff = now - NOTIFICATIONS_KEPT
    usage_cutoff = months_before(now, AI_USAGE_KEPT_MONTHS)
    runs_cutoff = now - AGENT_RUNS_KEPT
    rules: list[tuple[str, Batch]] = [
        (
            "webhook_events",
            lambda s: retention.webhook_events_before(s, webhook_cutoff, limit=batch),
        ),
        (
            "notifications",
            lambda s: retention.notifications_before(s, notification_cutoff, limit=batch),
        ),
        (
            "ai_usage_events",
            lambda s: retention.ai_usage_events_before(s, usage_cutoff, limit=batch),
        ),
        ("agent_runs", lambda s: retention.agent_runs_before(s, runs_cutoff, limit=batch)),
    ]
    for rule, delete in rules:
        if not await drain(rule, delete):
            break
    else:
        await _expire_message_history(sessionmaker, now, drain, batch)
    counts = {rule: n for rule, n in counts.items() if n}
    log.info("purge_expired_run", **counts)
    return counts


Drain = Callable[[str, Batch], Awaitable[bool]]


async def _expire_message_history(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime, drain: Drain, batch: int
) -> None:
    for plan, days in history_limits().items():
        cutoff = now - timedelta(days=days)
        async with sessionmaker() as session:
            with tenant_bypass_scope():
                workspace_ids = await retention.workspaces_on_plans(session, [plan])
        for workspace_id in workspace_ids:
            if not await _expire_workspace_history(drain, workspace_id, cutoff, batch):
                return


async def _expire_workspace_history(
    drain: Drain, workspace_id: uuid.UUID, cutoff: datetime, batch: int
) -> bool:
    async def messages(session: AsyncSession) -> int:
        return await retention.messages_before(session, workspace_id, cutoff, limit=batch)

    async def conversations(session: AsyncSession) -> int:
        return await retention.empty_conversations(session, workspace_id, cutoff, limit=batch)

    with workspace_scope(workspace_id):
        return await drain("messages", messages) and await drain("conversations", conversations)


async def delete_finished_jobs() -> None:
    """TR-OPS-04: queue jobs that finished (succeeded, failed, cancelled or aborted) more than 30
    days ago, through the queue's own API."""
    await app.job_manager.delete_old_jobs(
        nb_hours=FINISHED_JOBS_KEPT_HOURS,
        include_failed=True,
        include_cancelled=True,
        include_aborted=True,
    )


async def _purge_expired() -> None:
    rt = runtime()
    await purge_expired_rows(rt.sessionmaker)
    await delete_finished_jobs()
    await deletion.sweep(rt.sessionmaker, datetime.now(UTC))


@app.periodic(cron="0 4 * * *", periodic_id="purge_expired")
@app.task(name="purge_expired", queue=BULK, queueing_lock="purge_expired")
async def purge_expired(timestamp: int) -> None:
    await asyncio.wait_for(_purge_expired(), timeout=PURGE_EXPIRED_TIMEOUT_S)
