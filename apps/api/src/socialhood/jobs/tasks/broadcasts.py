"""WhatsApp broadcast jobs (GR-23).

``dispatch_broadcast(workspace_id, broadcast_id)`` (bulk lane, queueing lock and run lock
``broadcast:{id}``, 3 tries) runs one batch of a sending broadcast (services/broadcasts/dispatch)
and queues the next one a minute later, or when the number's daily limit frees a place. Progress
is the recipients' state, so a retry or a stalled job's re-run carries on and sends nobody twice.

``run_broadcasts`` (every minute, bulk lane) starts the scheduled broadcasts whose time has come
(the audience is fixed then; a broadcast that cannot start fails with the reason) and queues a
batch for every sending broadcast, so a lost job costs at most a minute. Both do nothing with
BROADCASTS_ENABLED off.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.retry import BackoffRetry
from socialhood.jobs.runtime import runtime
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import broadcasts as repo
from socialhood.services.broadcasts import dispatch, lifecycle, service

log = get_logger(__name__)

RETRY = BackoffRetry(max_attempts=3)
BATCH = 50


async def queue_batch(
    workspace_id: uuid.UUID, broadcast_id: uuid.UUID, *, delay_s: float = 0
) -> bool:
    """Queue a batch for one broadcast (one waiting job per broadcast)."""
    return await enqueue(
        dispatch_broadcast,
        key=f"broadcast:{broadcast_id}",
        lock=f"broadcast:{broadcast_id}",
        delay_s=delay_s,
        workspace_id=str(workspace_id),
        broadcast_id=str(broadcast_id),
    )


@app.task(name="dispatch_broadcast", queue=BULK, retry=RETRY)
async def dispatch_broadcast(workspace_id: str, broadcast_id: str) -> None:
    rt = runtime()
    result = await dispatch.run_batch(
        rt.sessionmaker,
        rt.redis,
        deps_from(rt.http, rt.settings),
        workspace_id=uuid.UUID(workspace_id),
        broadcast_id=uuid.UUID(broadcast_id),
    )
    if result.next_in_s is not None:
        await queue_batch(
            uuid.UUID(workspace_id), uuid.UUID(broadcast_id), delay_s=result.next_in_s
        )


async def start_due(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    now: datetime | None = None,
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Start the scheduled broadcasts that are due; returns (workspace, broadcast) of each that
    began sending. A broadcast that cannot start (the number is gone, the segment was deleted, no
    one is left to send to) fails with the reason and tells the owners and admins."""
    now = now or datetime.now(UTC)
    started: list[tuple[uuid.UUID, uuid.UUID]] = []
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            due = await repo.due(session, now=now, limit=BATCH)
        for row in due:
            with workspace_scope(row.workspace_id):
                try:
                    account, segment = await service.launch_inputs(session, row)
                except service.CannotStart as error:
                    await lifecycle.fail(session, row, str(error), now, code="start")
                    continue
                await service.launch(
                    session, row, account=account, segment=segment, now=now, strict=False
                )
                if row.status == "sending":
                    started.append((row.workspace_id, row.id))
        await commit_and_publish(session, redis)
    return started


@app.periodic(cron="* * * * *", periodic_id="run_broadcasts")
@app.task(name="run_broadcasts", queue=BULK, queueing_lock="run_broadcasts")
async def run_broadcasts(timestamp: int) -> None:
    rt = runtime()
    deps = deps_from(rt.http, rt.settings)
    if not rt.settings.broadcasts_enabled:
        return
    for workspace_id, broadcast_id in await start_due(rt.sessionmaker, rt.redis, deps):
        await queue_batch(workspace_id, broadcast_id)
    async with rt.sessionmaker() as session:
        with tenant_bypass_scope():
            sending = await repo.sending(session, limit=BATCH * 4)
    for workspace_id, broadcast_id in sending:
        await queue_batch(workspace_id, broadcast_id)
