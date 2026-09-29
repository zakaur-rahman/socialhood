"""Ask Social Hood jobs (TA.1, TA.2, TA.6; TR-AGT-07, TR-JOB-02…06; agent-architecture.html §10).
Thin tasks: the work is in agent/orchestrator.py. Each task carries the workspace id, so none needs
a cross-workspace lookup except the sweeper's (allowed in jobs/, TR-TEN-04).

- run_agent(run_id, workspace_id): interactive lane, queueing lock and lock ``agent:{run_id}``,
  1 try (the orchestrator handles model and tool retries itself, §15). Enqueued by POST
  …/agent/runs after the run commits. Calls ``agent.orchestrator.run`` in the workspace's scope,
  which takes the run to a final status (or, in R2, an approval) and publishes agent.run.updated,
  agent.step and agent.completed. A run already final or cancelled is left as it is, so a
  duplicate job is harmless. An agent run never does bulk work inside its own job: in R2 that
  becomes an existing background task the run waits on (FR-AGT-11).
- sweep_agent_runs: periodic, every 5 minutes (``*/5 * * * *``, bulk lane, singleton). Runs left
  ``planning`` or ``running`` for STUCK_AFTER (10 minutes, models/agent.py) with no job holding
  ``agent:{run_id}`` are enqueued again and resume from their last completed step; a write step
  found running is re-checked by its verifier first (R2), so nothing runs twice (TA.6).

R2 adds resume_agent_run(run_id, workspace_id) (after an approval or a finished long task; same
lock) and expire_agent_approvals (every 15 minutes: pending approvals past expires_at become
expired and their runs end partial).
"""

from __future__ import annotations
