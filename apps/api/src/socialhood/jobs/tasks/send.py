"""send_message, mark_read and the in-flight sweeper (T3.6; TR-JOB-03, TR-JOB-04, TR-JOB-05).

Thin tasks: the work is in services/sending.py and services/read_receipts.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from procrastinate import JobContext
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.retry import PlatformRetry
from socialhood.jobs.runtime import runtime
from socialhood.models.inbox import MessageStatus
from socialhood.observability.logging import get_logger
from socialhood.platforms.buckets import TokenBuckets
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.repositories import messages as messages_repo
from socialhood.services import read_receipts, sending

log = get_logger(__name__)

SEND_RETRY = PlatformRetry(max_attempts=5)  # job catalogue: send_message, 5 tries
QUEUED_GRACE = timedelta(minutes=1)  # a queued message with no job after this is re-enqueued
SENDING_STUCK = timedelta(minutes=10)  # TR-JOB-03
HEARTBEAT_S = 60  # a running job whose worker has been silent this long is dead


def _deps() -> PlatformDeps:
    rt = runtime()
    return deps_from(rt.http, rt.settings)


@app.task(name="send_message", queue=INTERACTIVE, retry=SEND_RETRY, pass_context=True)
async def send_message(
    context: JobContext,
    message_id: str,
    conversation_id: str,
    workspace_id: str,
    not_found: int = 0,
) -> None:
    rt = runtime()
    job = context.job

    def will_retry(error: PlatformError) -> bool:
        return SEND_RETRY.get_retry_decision(exception=error, job=job) is not None

    request = sending.SendJob(
        message_id=uuid.UUID(message_id),
        conversation_id=uuid.UUID(conversation_id),
        workspace_id=uuid.UUID(workspace_id),
        attempt=int(job.attempts),
        not_found=not_found,
    )
    with workspace_scope(request.workspace_id):
        await sending.deliver(rt.sessionmaker, rt.redis, _deps(), request, will_retry=will_retry)


@app.task(name="mark_read", queue=INTERACTIVE)
async def mark_read(conversation_id: str, workspace_id: str) -> None:
    rt = runtime()
    with workspace_scope(uuid.UUID(workspace_id)):
        await read_receipts.send_read_receipt(
            rt.sessionmaker, _deps(), uuid.UUID(conversation_id), buckets=TokenBuckets(rt.redis)
        )


# ---------------------------------------------------------------- sweeper


_SEND_JOB_PENDING = """
SELECT EXISTS (
  SELECT 1 FROM procrastinate_jobs j
  LEFT JOIN procrastinate_workers w ON w.id = j.worker_id
  WHERE j.queueing_lock = %(key)s
    AND (j.status = 'todo'
         OR (j.status = 'doing'
             AND w.last_heartbeat > now() - make_interval(secs => %(heartbeat)s)))
) AS pending
"""


async def send_job_pending(message_id: uuid.UUID) -> bool:
    """A send_message job for the message is waiting (a retry) or running on a live worker."""
    row = await app.connector.execute_query_one_async(
        _SEND_JOB_PENDING, key=f"send:{message_id}", heartbeat=HEARTBEAT_S
    )
    return bool(row["pending"])


async def sweep_in_flight(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, now: datetime | None = None
) -> dict[str, int]:
    """Messages that stopped moving (ix_messages_in_flight): a queued one lost its job, so it is
    enqueued again (a waiting job makes that a no-op); a sending one whose job is gone may have
    reached the platform, so it fails as delivery_unknown and is never re-sent (TR-JOB-05)."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            rows = await messages_repo.in_flight(
                session, queued_before=now - QUEUED_GRACE, sending_before=now - SENDING_STUCK
            )
    counts = {"requeued": 0, "abandoned": 0}
    for row in rows:
        if row.status == MessageStatus.QUEUED:
            counts["requeued"] += int(
                await sending.enqueue_send(row.id, row.conversation_id, row.workspace_id)
            )
        elif not await send_job_pending(row.id):
            with workspace_scope(row.workspace_id):
                counts["abandoned"] += int(await sending.give_up(sessionmaker, redis, row.id))
    if any(counts.values()):
        log.info("sweep_messages", **counts)
    return counts


@app.periodic(cron="* * * * *", periodic_id="sweep_messages")
@app.task(name="sweep_messages", queue=INTERACTIVE, queueing_lock="sweep_messages")
async def sweep_messages(timestamp: int) -> None:
    rt = runtime()
    await sweep_in_flight(rt.sessionmaker, rt.redis)
