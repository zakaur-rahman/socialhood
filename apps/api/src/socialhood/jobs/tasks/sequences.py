"""Sequence jobs (GR-24).

``run_sequences`` (every minute, bulk lane, one waiting job at a time) runs the due steps of the
active sequences: up to ``BATCH`` enrolments a minute, each in its own transaction (see
services/sequences/runner). Progress is the enrolment's current step, and a step runs once however
often the job is retried or two workers meet (the lock skips a row another holds, the message has a
stable client id and ``sequence_step_runs`` is unique per enrolment and step), so a stalled job is
simply run again. A backlog larger than a batch is cleared over the next minutes, oldest first.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.runtime import runtime
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.repositories import sequences as repo
from socialhood.services.sequences import runner

log = get_logger(__name__)

BATCH = 100


async def sweep(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    now: datetime | None = None,
    limit: int = BATCH,
) -> Counter[str]:
    """Find the due enrolments across workspaces and run them; returns how many ended each way."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            due = await repo.due(session, now, limit)
    return await runner.run_due(sessionmaker, redis, deps, due, now=now)


@app.periodic(cron="* * * * *", periodic_id="run_sequences")
@app.task(name="run_sequences", queue=BULK, queueing_lock="run_sequences")
async def run_sequences(timestamp: int) -> None:
    rt = runtime()
    outcomes = await sweep(rt.sessionmaker, rt.redis, deps_from(rt.http, rt.settings))
    if outcomes:
        log.info("sequences_run", **dict(outcomes))
