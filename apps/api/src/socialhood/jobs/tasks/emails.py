"""Email jobs (T8.5, T8.7; FR-NOT-02, FR-NOT-04, TR-JOB-02…06). Thin tasks: the work is in
notify/outbox.py.

- deliver_email(delivery_id, workspace_id): interactive lane, queueing lock ``email:{id}``,
  5 tries with backoff (10 s, 20 s, 40 s, 80 s) on retryable EmailErrors (timeouts, 429, 5xx).
  Deferred when the email_deliveries row commits (notify/dispatch.py). Calls
  ``notify.outbox.send_queued`` in the workspace's scope with ``notify.registry.get_email_sender``.
  The spec's catalogue keys it by notification id; it takes the outbox row instead, because
  digest emails have no notification (C-049).
- sweep_email_outbox: periodic, every minute (interactive lane, singleton). Across workspaces
  (the tenant bypass is allowed in jobs/, TR-TEN-04): re-enqueues deliveries still ``queued`` a
  minute after they were created (a lost enqueue, a worker that died mid-send; one waiting for
  a retry keeps its job, whose queueing lock makes the enqueue a no-op), and fails the ones still
  queued after a day rather than send them late.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from procrastinate import BaseRetryStrategy, JobContext, RetryDecision
from procrastinate.jobs import Job
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.retry import BASE_DELAY_S, MAX_DELAY_S
from socialhood.jobs.runtime import runtime
from socialhood.notify import dispatch, outbox
from socialhood.notify.email import EmailError
from socialhood.notify.push import PushError
from socialhood.notify.registry import get_email_sender
from socialhood.observability.logging import get_logger
from socialhood.repositories import email_deliveries

log = get_logger(__name__)

SWEEP_AFTER = timedelta(minutes=1)
GIVE_UP_AFTER = timedelta(days=1)
SWEEP_BATCH = 200


class DeliveryRetry(BaseRetryStrategy):
    """Retry only a retryable EmailError or PushError (the provider's timeout, 429 or 5xx), with
    the platform jobs' backoff; a refusal is never retried."""

    def __init__(self, max_attempts: int) -> None:
        self.max_attempts = max_attempts

    def get_retry_decision(self, *, exception: BaseException, job: Job) -> RetryDecision | None:
        if not isinstance(exception, EmailError | PushError) or not exception.retryable:
            return None
        if job.attempts + 1 >= self.max_attempts:
            return None
        return RetryDecision(
            retry_in={"seconds": min(MAX_DELAY_S, BASE_DELAY_S << min(job.attempts, 16))}
        )


EMAIL_RETRY = DeliveryRetry(max_attempts=outbox.MAX_ATTEMPTS)


@app.task(name="deliver_email", queue=INTERACTIVE, retry=EMAIL_RETRY, pass_context=True)
async def deliver_email(context: JobContext, delivery_id: str, workspace_id: str) -> None:
    rt = runtime()
    job = context.job

    def will_retry(error: EmailError) -> bool:
        return EMAIL_RETRY.get_retry_decision(exception=error, job=job) is not None

    with workspace_scope(uuid.UUID(workspace_id)):
        await outbox.send_queued(
            rt.sessionmaker,
            uuid.UUID(delivery_id),
            sender=get_email_sender(rt.http, rt.settings),
            settings=rt.settings,
            will_retry=will_retry,
        )


async def sweep_outbox(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> dict[str, int]:
    """Re-enqueue queued emails older than a minute; fail those older than a day."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            expired = await email_deliveries.expire_queued(
                session, created_before=now - GIVE_UP_AFTER, error="Not sent within a day"
            )
            stuck = await email_deliveries.queued_between(
                session,
                created_after=now - GIVE_UP_AFTER,
                created_before=now - SWEEP_AFTER,
                limit=SWEEP_BATCH,
            )
        await session.commit()
    requeued = 0
    for delivery_id, workspace_id in stuck:
        job = dispatch.PendingJob("deliver_email", delivery_id, workspace_id)
        requeued += int(await dispatch.defer_quietly(job))
    if requeued or expired:
        log.info("sweep_email_outbox", requeued=requeued, expired=expired)
    return {"requeued": requeued, "expired": expired}


@app.periodic(cron="* * * * *", periodic_id="sweep_email_outbox")
@app.task(name="sweep_email_outbox", queue=INTERACTIVE, queueing_lock="sweep_email_outbox")
async def sweep_email_outbox(timestamp: int) -> None:
    await sweep_outbox(runtime().sessionmaker)
