"""Live progress of a run (TA.1; FR-AGT-01, TR-RT-03; agent-architecture.html §11, §12): the
payloads of agent.run.updated, agent.step and agent.completed, and steps in plain words.

The stream is shared by the workspace's members while a run is its requester's, so the payloads
carry ids, statuses and plain-word steps only: never the request, the answer, arguments or
results (schemas/agent.py). The requester's panel fetches the run on agent.completed.

A step's label is its tool's label from the registry ("Looking up your latest post"), "Checking
a condition" or "Writing the answer"; never the model's reasoning.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.agent.registry import ToolRegistry
from socialhood.models.agent import FINAL_RUN_STATUSES, AgentRun, AgentStep, StepKind
from socialhood.realtime import events
from socialhood.schemas.agent import AgentRunEvent, AgentStepEvent, AgentStepProgress
from socialhood.schemas.inbox import ErrorInfo

KIND_LABELS = {
    StepKind.CONDITION.value: "Checking a condition",
    StepKind.REPORT.value: "Writing the answer",
}


def step_label(tools: ToolRegistry, kind: str, tool: str | None) -> str:
    """The step in plain words; a tool no longer registered gets its name in words."""
    if kind != StepKind.TOOL or tool is None:
        return KIND_LABELS.get(kind, "Working")
    spec = tools.get(tool)
    return spec.label if spec is not None else tool.replace("_", " ").capitalize()


def error_info(code: str | None, message: str | None) -> ErrorInfo | None:
    if code is None:
        return None
    return ErrorInfo(code=code, message=message or "Something went wrong.")


def run_payload(run: AgentRun, step_count: int) -> dict[str, Any]:
    """``{run: AgentRunEvent}``."""
    event = AgentRunEvent.model_validate(
        {
            "id": run.id,
            "thread_id": run.thread_id,
            "requested_by_user_id": run.requested_by_user_id,
            "status": run.status,
            "step_count": step_count,
            "error": error_info(run.error_code, run.error_message),
        }
    )
    return {"run": event.model_dump(mode="json")}


def queue_run(session: AsyncSession, run: AgentRun, step_count: int) -> None:
    """agent.run.updated, and agent.completed when the run is final; published on commit."""
    payload = run_payload(run, step_count)
    events.queue(session, run.workspace_id, "agent.run.updated", payload)
    if run.status in FINAL_RUN_STATUSES:
        events.queue(session, run.workspace_id, "agent.completed", payload)


def queue_step(
    session: AsyncSession,
    tools: ToolRegistry,
    *,
    workspace_id: uuid.UUID,
    requested_by_user_id: uuid.UUID | None,
    step: AgentStep,
) -> None:
    """agent.step: a step started (running) or ended."""
    event = AgentStepEvent(
        run_id=step.run_id,
        requested_by_user_id=requested_by_user_id,
        step=AgentStepProgress.model_validate(
            {
                "id": step.id,
                "ordinal": step.ordinal,
                "kind": step.kind,
                "tool": step.tool,
                "label": step_label(tools, step.kind, step.tool),
                "status": step.status,
                "summary": step_summary(step.result),
                "latency_ms": step.latency_ms or 0,
            }
        ),
    )
    events.queue(session, workspace_id, "agent.step", event.model_dump(mode="json"))


def step_summary(result: dict[str, Any] | None) -> str | None:
    summary = (result or {}).get("summary")
    return summary if isinstance(summary, str) else None
