"""The scheduled-message dispatcher, send_scheduled and the stuck-claim sweeper (T3.13; F-10,
FR-SMS-03, TR-JOB-02, TR-JOB-03). Thin: the rules are in services/scheduled.py.

dispatch_due runs every 30 seconds, so a message goes out within a minute of its time
(FR-SMS-03). It locks due rows across workspaces with FOR UPDATE SKIP LOCKED (a cross-workspace
lookup, allowed in jobs/ by TR-TEN-04), marks them ``sending`` and enqueues one send_scheduled per
row under the queueing lock ``smsg:{id}``. A second dispatcher skips or no longer sees the rows,
and send_scheduled only acts on a claimed row it can lock, so a message is sent once.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.runtime import runtime
from socialhood.observability.logging import get_logger
from socialhood.realtime import events
from socialhood.repositories import scheduled as repo
from socialhood.services import scheduled as service

log = get_logger(__name__)

CLAIM_BATCH = 200  # TR-JOB-03
SWEEP_BATCH = 500


async def dispatch_due_messages(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, now: datetime | None = None
) -> list[uuid.UUID]:
    """Claim due messages and enqueue their sends; returns the claimed ids."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            rows = await repo.lock_due(session, now, CLAIM_BATCH)
        service.mark_claimed(session, rows, now)
        await events.commit_and_publish(session, redis)
    for row in rows:
        await enqueue_send(row.scheduled.id, row.scheduled.workspace_id)
    if rows:
        log.info("scheduled_messages_claimed", count=len(rows))
    return [row.scheduled.id for row in rows]


async def enqueue_send(scheduled_message_id: uuid.UUID, workspace_id: uuid.UUID) -> bool:
    """An enqueue failure is logged, not raised: the claim is committed, and the sweeper returns
    the row to ``scheduled`` after STUCK_AFTER."""
    try:
        return await enqueue(
            send_scheduled,
            key=f"smsg:{scheduled_message_id}",
            scheduled_message_id=str(scheduled_message_id),
            workspace_id=str(workspace_id),
        )
    except Exception:
        log.warning("scheduled_enqueue_failed", scheduled_message_id=str(scheduled_message_id))
        return False


async def send_one(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    scheduled_message_id: uuid.UUID,
    workspace_id: uuid.UUID,
    *,
    human_agent_enabled: bool,
    now: datetime | None = None,
) -> service.SendOutcome:
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            outcome = await service.send_claimed(
                session,
                scheduled_message_id,
                human_agent_enabled=human_agent_enabled,
                now=now or datetime.now(UTC),
            )
            await events.commit_and_publish(session, redis)
    log.info(
        "scheduled_message_send", scheduled_message_id=str(scheduled_message_id), outcome=outcome
    )
    return outcome


async def sweep_stuck_messages(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, now: datetime | None = None
) -> dict[str, int]:
    """TR-JOB-03: claims older than STUCK_AFTER that never produced a message (a lost enqueue, or
    a worker that died mid-send) go back to ``scheduled``, or fail after MAX_ATTEMPTS claims."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            rows = await repo.lock_stuck(session, now - service.STUCK_AFTER, SWEEP_BATCH)
        counts = service.reset_stuck(session, rows)
        await events.commit_and_publish(session, redis)
    if rows:
        log.info("scheduled_messages_swept", **counts)
    return counts


@app.periodic(cron="* * * * * */30", periodic_id="dispatch_due")
@app.task(name="dispatch_due", queue=INTERACTIVE, queueing_lock="dispatch_due")
async def dispatch_due(timestamp: int) -> None:
    rt = runtime()
    await dispatch_due_messages(rt.sessionmaker, rt.redis)


@app.task(name="send_scheduled", queue=INTERACTIVE)
async def send_scheduled(scheduled_message_id: str, workspace_id: str) -> None:
    """No retry strategy: the send itself is retried by send_message; a crash here leaves the
    row ``sending`` for the sweeper."""
    rt = runtime()
    await send_one(
        rt.sessionmaker,
        rt.redis,
        uuid.UUID(scheduled_message_id),
        uuid.UUID(workspace_id),
        human_agent_enabled=rt.settings.ig_human_agent_enabled,
    )


@app.periodic(cron="* * * * *", periodic_id="sweep_stuck_scheduled")
@app.task(name="sweep_stuck_scheduled", queue=INTERACTIVE, queueing_lock="sweep_stuck_scheduled")
async def sweep_stuck_scheduled(timestamp: int) -> None:
    rt = runtime()
    await sweep_stuck_messages(rt.sessionmaker, rt.redis)
