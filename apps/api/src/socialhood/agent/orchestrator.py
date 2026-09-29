"""The run's state machine (TR-AGT-07, FR-AGT-07; agent-architecture.html §9, §15).

    queued → planning → running → succeeded | partial | failed
    any unfinished status → cancelled (the member)
    R2: running → awaiting_approval → running (approved, or rejected: step skipped) | expired

- Accept: POST …/agent/runs stores the run ``queued`` with the policy's mode and enqueues
  run_agent (jobs/tasks/agent.py). Nothing is reserved yet.
- Understand: ``planning``; the context (agent/context.py) and the time resolver build the
  prompt.
- Execute: ``running``; the planner's tool calls run through the executor, one step each,
  persisted before and after (agent.step events). Cancellation is checked before every step and
  model turn. In R2, writes pass the gateway and an approval pauses the run and returns the job.
- Verify (R2): every write step runs its verifier; an unverified write makes the run ``partial``.
- Report: the answer and its citations are stored, the status becomes final, completed_at is set
  and agent.completed is published. agent.run.updated follows every status change.

Caps (models/agent.py): MAX_TOOL_CALLS, MAX_MODEL_TURNS, RUN_WALL_TIME, RUN_CREDIT_CAP; past one,
the run reports what it has. Recovery (TA.6): steps are persisted before and after, so
sweep_agent_runs resumes a run stuck ``running`` for STUCK_AFTER from its last completed step,
re-checking a write that was running with its verifier before any retry (its idempotency key is
``{run_id}:{ordinal}``), so nothing runs twice.

``run`` is the interface the job calls; TA.1 and TA.2 implement it.
"""

from __future__ import annotations

import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.platforms.deps import PlatformDeps


async def run(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    platform: PlatformDeps,
    *,
    run_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> None:
    """Take the run from where its stored steps leave it to a final status (or, in R2, an
    approval). A run already final is left as it is, so a duplicate job is harmless."""
    raise NotImplementedError("TA.2")
