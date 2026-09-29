"""Runs one step (TR-AGT-03, TR-AGT-07, TR-AGT-08; agent-architecture.html §9, §15, §16).

For each tool call the executor:

1. looks the tool up in the registry (unknown or not shipped: the call goes back to the model as
   an error) and validates the arguments with the tool's input model;
2. inserts the step (next ordinal, kind ``tool``, the tool, its tier, the validated args,
   ``pending``, idempotency_key ``{run_id}:{ordinal}``) and commits before running it;
3. marks it ``running`` (started_at, attempts + 1; agent.step), then calls the handler with the
   run's ``ToolContext``;
4. stores the result (``result_model`` dumped as JSON), ``succeeded``, latency_ms and
   completed_at, or ``failed`` with error_code and error_message; publishes agent.step;
5. in R2, asks the gateway first (``decision``), runs the verifier after a write
   (``verification``) and retries transient write errors with the same idempotency key.

Read tools retry once on a transient error; otherwise the step fails and the model may continue
with what it has, and the answer says which data was unavailable (FR-AGT-06). Logs one
``agent_step`` line per step with the run id, ordinal, tool, status and latency (§16); secrets and
long text are redacted as elsewhere (SEC-07).

The executor is built with the planner (TA.2).
"""

from __future__ import annotations
