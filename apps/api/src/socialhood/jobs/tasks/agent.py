"""Ask Social Hood jobs (TA.1, TA.2, TA.6; TR-AGT-07, TR-JOB-02…06; agent-architecture.html §10).
Thin tasks: the work is in agent/orchestrator.py. Each task carries the workspace id, so none needs
a cross-workspace lookup except the sweeper's (allowed in jobs/, TR-TEN-04).

- run_agent(run_id, workspace_id): interactive lane, queueing lock and lock ``agent:{run_id}``,
  1 try (the orchestrator handles model and tool retries itself, §15). Enqueued by POST
  …/agent/runs after the run commits (``orchestrator.enqueue_run``). Calls
  ``agent.orchestrator.run`` in the workspace's scope, which takes the run to a final status (or,
  in R2, an approval) and publishes agent.run.updated, agent.step and agent.completed. A run
  already final or cancelled is left as it is, so a duplicate job is harmless. An agent run never
  does bulk work inside its own job: in R2 that becomes an existing background task the run waits
  on (FR-AGT-11).
- sweep_agent_runs: periodic, every 5 minutes (``*/5 * * * *``, bulk lane, singleton). Runs left
  ``queued``, ``planning`` or ``running`` with no progress (neither the run nor a step changed)
  for STUCK_AFTER (10 minutes, models/agent.py) and no run_agent waiting or running on a live
  worker under ``agent:{run_id}`` are enqueued again and resume from their last completed step
  (``orchestrator.recover``); a run too old to resume, or with a write step found running (R2:
  re-checked by its verifier first), is failed with the reason, so nothing runs twice (TA.6).

R2 adds resume_agent_run(run_id, workspace_id) (after an approval or a finished long task; same
lock) and expire_agent_approvals (every 15 minutes: pending approvals past expires_at become
expired and their runs end partial).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.agent import orchestrator
from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, INTERACTIVE, app
from socialhood.jobs.runtime import runtime
from socialhood.models.agent import STUCK_AFTER
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import deps_from
from socialhood.repositories import agent as repo

log = get_logger(__name__)

SWEEP_BATCH = 100
HEARTBEAT_S = 60  # a running job whose worker has been silent this long is dead

_JOB_PENDING = """
SELECT EXISTS (
  SELECT 1 FROM procrastinate_jobs j
  LEFT JOIN procrastinate_workers w ON w.id = j.worker_id
  WHERE j.task_name = 'run_agent'
    AND j.lock = %(lock)s
    AND (j.status = 'todo'
         OR (j.status = 'doing'
             AND w.last_heartbeat > now() - make_interval(secs => %(heartbeat)s)))
) AS pending
"""


async def run_job_pending(run_id: uuid.UUID) -> bool:
    """A run_agent for this run is waiting, or running on a live worker."""
    row = await app.connector.execute_query_one_async(
        _JOB_PENDING, lock=f"agent:{run_id}", heartbeat=HEARTBEAT_S
    )
    return bool(row["pending"])


async def sweep(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, now: datetime | None = None
) -> dict[str, int]:
    """TA.6: resume (or fail) runs in flight with no progress for STUCK_AFTER and no job."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            stuck = await repo.stuck_runs(session, now - STUCK_AFTER, SWEEP_BATCH)
    counts = {"resumed": 0, "failed": 0}
    for row in stuck:
        if await run_job_pending(row.id):
            continue
        with workspace_scope(row.workspace_id):
            outcome = await orchestrator.recover(sessionmaker, redis, row.id, now=now)
        if outcome != "skipped":
            counts[outcome] += 1
    if any(counts.values()):
        log.info("sweep_agent_runs", **counts)
    return counts


@app.task(name="run_agent", queue=INTERACTIVE)
async def run_agent(run_id: str, workspace_id: str) -> None:
    rt = runtime()
    wid = uuid.UUID(workspace_id)
    with workspace_scope(wid):
        await orchestrator.run(
            rt.sessionmaker,
            rt.redis,
            deps_from(rt.http, rt.settings),
            run_id=uuid.UUID(run_id),
            workspace_id=wid,
        )


@app.periodic(cron="*/5 * * * *", periodic_id="sweep_agent_runs")
@app.task(name="sweep_agent_runs", queue=BULK, queueing_lock="sweep_agent_runs")
async def sweep_agent_runs(timestamp: int) -> None:
    rt = runtime()
    await sweep(rt.sessionmaker, rt.redis)
