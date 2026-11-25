"""Maintenance: the periodic ping, the stuck-row sweep (TR-JOB-03), jobs left running by a dead
worker (recover_stalled_jobs, jobs/recovery.py), webhook health (TR-WH-08), failed-work alerts
(TR-OPS-04) and the daily storage check (Cloudinary credits, emailed to OPS_ALERT_EMAIL). Alerts are
error-level log events named ``alert``, which the error tracker picks up (T9.3)."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import httpx
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.jobs.app import BULK, INTERACTIVE, app
from socialhood.jobs.recovery import recover_stalled
from socialhood.jobs.runtime import runtime
from socialhood.media.cloudinary import Cloudinary, CloudinaryError
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.platform import WebhookEvent, WebhookStatus
from socialhood.notify.email import EmailError, EmailMessage
from socialhood.notify.registry import get_email_sender
from socialhood.observability.logging import get_logger
from socialhood.repositories import webhook_events
from socialhood.services.webhook_intake import enqueue_processing
from socialhood.settings import Settings

log = get_logger(__name__)

RECEIVED_GRACE = timedelta(seconds=60)
FAILURE_RATE_ALERT = 0.01  # TR-WH-08: 1% over 5 minutes
SILENCE_ALERT_MINUTES = 60
FAILED_WORK_ALERT = 20  # TR-OPS-04: per hour
STORAGE_ALERT_TOP = 90.0  # the second, louder level after CLOUDINARY_ALERT_PERCENT
STORAGE_ALERT_KEPT_S = 40 * 86_400  # one alert per level per month


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


@app.periodic(cron="*/2 * * * *", periodic_id="recover_stalled_jobs")
@app.task(name="recover_stalled_jobs", queue=BULK, queueing_lock="recover_stalled_jobs")
async def recover_stalled_jobs(timestamp: int) -> None:
    """Retry, release or fail the jobs of workers silent for 90 s, by their task's class. No run
    lock: a stalled copy of this job would hold it, and two runs at once are harmless (each job
    moves once; the other run finds it moved on)."""
    await recover_stalled(app)


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


def storage_alert_email(percent: float, level: float, to: str, key: str) -> EmailMessage:
    """The storage alert, in plain words, with what to do. ``key`` makes a resend a no-op."""
    subject = f"Amplychat: Cloudinary at {percent:.0f}% of this cycle's credits"
    text = (
        f"Cloudinary has used {percent:.0f}% of this cycle's credits "
        f"(alert level {level:.0f}%).\n\n"
        "When it reaches 100%, uploads and media delivery can stop until the cycle resets, and "
        "scheduled posts with media would fail.\n\n"
        "What to do: check usage in the Cloudinary dashboard. If it keeps climbing, upgrade the "
        "Cloudinary plan, or move videos to Cloudflare R2 with our own conversion step "
        "(the R2 plan)."
    )
    html = "".join(f"<p>{line}</p>" for line in text.split("\n\n"))
    return EmailMessage(to=to, subject=subject, html=html, text=text, idempotency_key=key)


async def check_storage_usage(
    http: httpx.AsyncClient, redis: Redis, settings: Settings, now: datetime | None = None
) -> float | None:
    """Read Cloudinary's credit usage; at CLOUDINARY_ALERT_PERCENT and again at 90%, alert once
    per level per month: an ``alert`` log event and, with OPS_ALERT_EMAIL, an email. The level is
    only marked sent once the email went, so a failed send tries again the next day. None when
    Cloudinary isn't configured."""
    cloud = Cloudinary(http, settings)
    if not cloud.configured:
        return None
    now = now or datetime.now(UTC)
    percent = await cloud.credits_used_percent()
    log.info("storage_usage", provider="cloudinary", credits_used_percent=round(percent, 1))
    crossed = [
        level
        for level in (settings.cloudinary_alert_percent, STORAGE_ALERT_TOP)
        if percent >= level
    ]
    if not crossed:
        return percent
    level = max(crossed)
    key = f"ops:storage_alert:{now:%Y-%m}:{level:.0f}"
    if await redis.exists(key):
        return percent
    log.error(
        "alert",
        kind="storage_usage",
        detail={"provider": "cloudinary", "percent": percent, "level": level},
    )
    if settings.ops_alert_email:
        try:
            await get_email_sender(http, settings).send(
                storage_alert_email(percent, level, settings.ops_alert_email, key)
            )
        except EmailError as error:
            log.warning("storage_alert_email_failed", error=str(error))
            return percent
    await redis.set(key, "1", ex=STORAGE_ALERT_KEPT_S)
    return percent


@app.periodic(cron="15 6 * * *", periodic_id="check_storage_usage")
@app.task(name="check_storage_usage", queue=BULK, queueing_lock="check_storage_usage")
async def check_storage_usage_task(timestamp: int) -> None:
    rt = runtime()
    try:
        await check_storage_usage(rt.http, rt.redis, rt.settings)
    except CloudinaryError as error:  # tomorrow's run tries again
        log.warning("storage_usage_failed", error=str(error))
