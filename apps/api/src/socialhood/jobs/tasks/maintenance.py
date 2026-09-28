"""Maintenance: the periodic ping, the stuck-row sweep (TR-JOB-03), webhook health (TR-WH-08)
and failed-work alerts (TR-OPS-04). Alerts are error-level log events named ``alert``, which the
error tracker picks up (T9.3)."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.jobs.app import BULK, INTERACTIVE, app
from socialhood.jobs.runtime import runtime
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.platform import WebhookEvent, WebhookStatus
from socialhood.observability.logging import get_logger
from socialhood.repositories import webhook_events
from socialhood.services.webhook_intake import enqueue_processing

log = get_logger(__name__)

RECEIVED_GRACE = timedelta(seconds=60)
FAILURE_RATE_ALERT = 0.01  # TR-WH-08: 1% over 5 minutes
SILENCE_ALERT_MINUTES = 60
FAILED_WORK_ALERT = 20  # TR-OPS-04: per hour


@app.periodic(cron="* * * * *", periodic_id="ping")
@app.task(name="ping", queue=INTERACTIVE, queueing_lock="ping")
async def ping(timestamp: int) -> None:
    log.info("ping", tick=timestamp)


async def sweep_webhook_events(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> dict[str, int]:
    """Re-queue events still ``received`` after a minute: a lost enqueue, or a worker that died
    mid-way (its transaction rolled back, so the row never left ``received``). Events waiting
    for a retry already have a queued job, whose queueing lock makes the enqueue a no-op."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        stuck = await webhook_events.stuck_received(session, now - RECEIVED_GRACE)
    requeued = 0
    for event_id in stuck:
        requeued += int(await enqueue_processing(event_id))
    if requeued:
        log.info("sweep_stuck", requeued=requeued)
    return {"requeued": requeued}


@app.periodic(cron="* * * * *", periodic_id="sweep_stuck")
@app.task(name="sweep_stuck", queue=INTERACTIVE, queueing_lock="sweep_stuck")
async def sweep_stuck(timestamp: int) -> None:
    await sweep_webhook_events(runtime().sessionmaker)


async def webhook_health(
    redis: Redis, sessionmaker: async_sessionmaker[AsyncSession], now_minute: int | None = None
) -> list[str]:
    """TR-WH-08: alert on >1% failed deliveries over 5 minutes, or an hour of silence while
    Instagram accounts are connected. Returns the alerts raised."""
    minute = now_minute if now_minute is not None else int(time.time() // 60)
    alerts: list[str] = []
    ok = fail = 0
    for m in range(minute - 4, minute + 1):
        ok += int(await redis.get(f"wh:instagram:{m}:ok") or 0)
        fail += int(await redis.get(f"wh:instagram:{m}:fail") or 0)
    if fail and fail / (ok + fail) > FAILURE_RATE_ALERT:
        alerts.append(f"instagram webhook failures {fail} of {ok + fail} in 5 minutes")

    async with sessionmaker() as session:
        with tenant_bypass_scope():
            connected = await session.scalar(
                select(func.count())
                .select_from(SocialAccount)
                .where(
                    SocialAccount.platform == "instagram",
                    SocialAccount.status == AccountStatus.ACTIVE,
                )
            )
    last = await redis.get("wh:instagram:last")
    if connected and last is not None and minute - int(last) >= SILENCE_ALERT_MINUTES:
        alerts.append(f"no instagram webhook for {minute - int(last)} minutes")
    for alert in alerts:
        log.error("alert", kind="webhook_health", detail=alert)
    return alerts


@app.periodic(cron="*/5 * * * *", periodic_id="check_webhook_health")
@app.task(name="check_webhook_health", queue=BULK, queueing_lock="check_webhook_health")
async def check_webhook_health(timestamp: int) -> None:
    rt = runtime()
    await webhook_health(rt.redis, rt.sessionmaker)


async def failed_work_alerts(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> list[str]:
    """TR-OPS-04: more than 20 failed webhook events or jobs in the last hour."""
    now = now or datetime.now(UTC)
    since = now - timedelta(hours=1)
    async with sessionmaker() as session:
        failed_events = await session.scalar(
            select(func.count())
            .select_from(WebhookEvent)
            .where(WebhookEvent.status == WebhookStatus.FAILED, WebhookEvent.received_at >= since)
        )
    failed_jobs = await app.connector.execute_query_one_async(
        "SELECT count(*) AS n FROM procrastinate_jobs j WHERE status = 'failed' AND EXISTS ("
        " SELECT 1 FROM procrastinate_events e WHERE e.job_id = j.id AND e.type = 'failed'"
        " AND e.at >= %(since)s)",
        since=since,
    )
    alerts = []
    if (failed_events or 0) > FAILED_WORK_ALERT:
        alerts.append(f"{failed_events} webhook events failed in the last hour")
    if int(failed_jobs["n"]) > FAILED_WORK_ALERT:
        alerts.append(f"{failed_jobs['n']} jobs failed in the last hour")
    for alert in alerts:
        log.error("alert", kind="failed_work", detail=alert)
    return alerts


@app.periodic(cron="7 * * * *", periodic_id="check_failures")
@app.task(name="check_failures", queue=BULK, queueing_lock="check_failures")
async def check_failures(timestamp: int) -> None:
    await failed_work_alerts(runtime().sessionmaker)
