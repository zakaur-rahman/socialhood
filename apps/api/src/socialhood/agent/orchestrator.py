"""The run's state machine (TR-AGT-07, FR-AGT-07, TA.1, TA.2, TA.6; agent-architecture.html §9,
§15).

    queued → planning → running → succeeded | partial | failed
    any unfinished status → cancelled (the member)
    R2: running → awaiting_approval → running (approved, or rejected: step skipped) | expired

- Accept: POST …/agent/runs stores the run ``queued`` with the policy's mode and enqueues
  run_agent (jobs/tasks/agent.py, ``enqueue_run``). Nothing is reserved yet.
- Understand: ``planning`` (started_at, model, prompt version): the requester must still be a
  member (their role bounds the tools), the workspace must have a credit left (else ``failed``
  quota_exceeded before any model call), and the context (agent/context.py) is built.
- Execute: ``running``; the planner's tool calls run through the executor, one step each,
  persisted before and after (agent.step events). Cancellation is checked before every step and
  model turn: a cancelled run stops there and keeps what it did. In R2, writes pass the gateway
  and an approval pauses the run and returns the job.
- Report: the model's answer with its citations renumbered into answer_refs (agent/report.py), a
  ``report`` step, the run's credits and tokens, ``succeeded`` (``partial`` when a step failed),
  completed_at, then agent.run.updated and agent.completed. Every status change publishes
  agent.run.updated. A run finishes only if it is still unfinished (a conditional update), so a
  member's cancel is never overwritten.

Caps (models/agent.py): MAX_TOOL_CALLS, MAX_MODEL_TURNS, RUN_WALL_TIME, RUN_CREDIT_CAP; past one,
or when the credits run out mid-run, no model is asked again and the run reports what its
finished steps found (``partial``; ``failed`` when nothing finished). A model that doesn't answer
after the retry fails the run with "The AI didn't respond"; invalid output after the retry fails
it too. Unexpected errors fail the run with a generic reason and are logged.

Recovery (TA.6): steps are persisted before and after, so sweep_agent_runs (``recover``) enqueues
run_agent again for a run in flight with no progress for STUCK_AFTER and no job holding
``agent:{run_id}``. The job resumes from its last completed step: finished steps are replayed to
the model as the tool calls they were (never run again), a read step left ``running`` is marked
failed ("interrupted") and the model may call it again, and the wall-time cap restarts. A write
step left running would be re-checked by its verifier before any retry (R2; none exist in R1, so
such a run fails). A run older than RESUME_WINDOW is failed with the reason instead of resumed.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model
from pydantic_ai.usage import RunUsage
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.agent import planner, progress
from socialhood.agent.context import build_context
from socialhood.agent.executor import RunLimitReached, RunState, RunStopped
from socialhood.agent.registry import Principal, ToolContext, ToolRegistry
from socialhood.agent.report import Found, RefBook, cite, fallback_answer, model_view
from socialhood.ai.metering import QuotaExceeded, quota
from socialhood.billing.plans import CREDIT_COSTS
from socialhood.models.agent import (
    FINAL_RUN_STATUSES,
    RUN_WALL_TIME,
    WRITE_TIERS,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    StepKind,
    StepStatus,
)
from socialhood.models.billing import AiFeature
from socialhood.models.identity import Role
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import agent as repo

log = get_logger(__name__)

RESUME_WINDOW = timedelta(minutes=30)  # older runs found stuck are failed, not resumed
STOPPED_STEP = "Stopped before it finished."
INTERRUPTED_CODE = "interrupted"

# The run's error, in words for the member (ErrorInfo).
MESSAGES = {
    "quota_exceeded": "Your workspace has used its AI credits for this period.",
    "ai_unavailable": "The AI didn't respond. Try again in a moment.",
    "ai_invalid_output": "The AI couldn't put an answer together. Try asking again.",
    "ai_not_configured": "Ask Social Hood isn't set up on this server yet.",
    "forbidden": "The member who asked is no longer in this workspace.",
    "interrupted": "The run stopped before it finished and couldn't be resumed.",
    "internal": "Something went wrong while answering. Try again.",
}
LIMIT_REASONS = {
    "limit_reached": "it needed more steps than one answer allows",
    "quota_exceeded": "your workspace's AI credits ran out",
    "timeout": "it took longer than two minutes",
}


class RunRefused(Exception):
    """The run can't start: it fails with ``code`` before any model call."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# ---------------------------------------------------------------- entry points


async def enqueue_run(run_id: uuid.UUID, workspace_id: uuid.UUID) -> bool:
    """Queue run_agent (interactive lane; queueing and run lock ``agent:{run_id}``) after the
    caller has committed. A lost enqueue leaves the run queued; the sweeper queues it again."""
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.agent import run_agent

    try:
        return await enqueue(
            run_agent,
            key=f"agent:{run_id}",
            lock=f"agent:{run_id}",
            run_id=str(run_id),
            workspace_id=str(workspace_id),
        )
    except Exception:
        log.warning("agent_enqueue_failed", run_id=str(run_id), exc_info=True)
        return False


async def run(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    platform: PlatformDeps,
    *,
    run_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> None:
    """Take the run from where its stored steps leave it to a final status (or, in R2, an
    approval). A run already final is left as it is, so a duplicate job is harmless. Runs in the
    workspace's scope (the job sets it)."""
    async with sessionmaker() as session:
        row = await repo.get_run(session, run_id)
        if row is None or row.workspace_id != workspace_id:
            return
        if row.status in FINAL_RUN_STATUSES or row.status == AgentRunStatus.AWAITING_APPROVAL:
            return
        steps = await repo.steps_of(session, run_id)
    state = _state(row, steps, sessionmaker, redis, planner.current_tools())
    try:
        async with asyncio.timeout(RUN_WALL_TIME.total_seconds()):
            output = await _answer(state, platform, steps)
    except RunStopped:
        await state.store_usage()  # cancelled: keep what it used
        log.info("agent_run_stopped", run_id=str(run_id))
    except RunRefused as refused:
        await _fail(state, refused.code)
    except RunLimitReached as limit:
        await _stop_early(state, limit.code, limit.reason)
    except TimeoutError:
        await _stop_early(state, "timeout", LIMIT_REASONS["timeout"])
    except QuotaExceeded:
        await _stop_early(state, "quota_exceeded", LIMIT_REASONS["quota_exceeded"])
    except UsageLimitExceeded:
        await _stop_early(state, "limit_reached", LIMIT_REASONS["limit_reached"])
    except UnexpectedModelBehavior:
        if state.tools_withheld:  # it kept calling tools past the caps
            await _stop_early(state, "limit_reached", LIMIT_REASONS["limit_reached"])
        else:
            log.warning("agent_invalid_output", run_id=str(run_id), exc_info=True)
            await _fail(state, "ai_invalid_output")
    except planner.ModelUnavailable:
        await _fail(state, "ai_unavailable")
    except planner.ModelNotConfigured:
        await _fail(state, "ai_not_configured")
    except Exception:
        log.exception("agent_run_failed", run_id=str(run_id))
        await _fail(state, "internal")
    else:
        await _finish(state, output)


async def recover(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    run_id: uuid.UUID,
    *,
    now: datetime,
) -> Literal["resumed", "failed", "skipped"]:
    """The sweeper found the run in flight with no progress and no job (TA.6): queue it again to
    resume from its last completed step, or fail it with the reason. Runs in its workspace's
    scope."""
    async with sessionmaker() as session:
        row = await repo.get_run(session, run_id)
        if row is None or row.status not in repo.IN_FLIGHT:
            return "skipped"
        steps = await repo.steps_of(session, run_id)
    write_running = any(s.status == StepStatus.RUNNING and s.tier in WRITE_TIERS for s in steps)
    if write_running or row.created_at < now - RESUME_WINDOW:
        state = _state(row, steps, sessionmaker, redis, planner.current_tools())
        await _fail(state, "interrupted")
        return "failed"
    if await enqueue_run(row.id, row.workspace_id):
        log.info("agent_run_resumed", run_id=str(run_id), steps=len(steps))
        return "resumed"
    return "skipped"


# ---------------------------------------------------------------- the run


def _state(
    row: AgentRun,
    steps: list[AgentStep],
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    tools: ToolRegistry,
) -> RunState:
    return RunState(
        run=row,
        sessionmaker=sessionmaker,
        redis=redis,
        tools=tools,
        deadline=time.monotonic() + RUN_WALL_TIME.total_seconds(),
        next_ordinal=max((s.ordinal for s in steps), default=-1) + 1,
        step_count=len(steps),
        failed_steps=sum(_failed(s) for s in steps),
    )


def _failed(step: AgentStep) -> bool:
    """A tool step that failed on its own (an interrupted one is the job's, and the model may
    call it again; it doesn't make the run partial)."""
    return (
        step.kind == StepKind.TOOL
        and step.status == StepStatus.FAILED
        and step.error_code != INTERRUPTED_CODE
    )


async def _move(state: RunState, status: AgentRunStatus, **values: Any) -> None:
    """An unfinished run to ``status`` (agent.run.updated); RunStopped when it was finished
    meanwhile."""
    async with state.sessionmaker() as session:
        if not await repo.set_status(session, state.run_id, status, **values):
            raise RunStopped(status)
        state.run.status = status
        for name, value in values.items():
            setattr(state.run, name, value)
        progress.queue_run(session, state.run, state.step_count)
        await commit_and_publish(session, state.redis)


@dataclass(frozen=True)
class _Resume:
    replay: list[ModelMessage]
    usage: RunUsage | None


async def _resume(session: AsyncSession, state: RunState, steps: list[AgentStep]) -> _Resume:
    """What a crashed job finished, for the model; a read step left running becomes failed
    (interrupted). Numbers the finished steps' refs, so citations keep their numbers."""
    if not steps:
        return _Resume([], None)
    at = datetime.now(UTC)
    interrupted = [s for s in steps if s.status == StepStatus.RUNNING]
    if interrupted:
        await repo.fail_running_steps(
            session, state.run_id, code=INTERRUPTED_CODE, message=planner.INTERRUPTED, at=at
        )
        for step in interrupted:
            step.status, step.error_code, step.error_message = (
                StepStatus.FAILED,
                INTERRUPTED_CODE,
                planner.INTERRUPTED,
            )
            step.completed_at = at
            progress.queue_step(
                session,
                state.tools,
                workspace_id=state.workspace_id,
                requested_by_user_id=state.run.requested_by_user_id,
                step=step,
            )
        await commit_and_publish(session, state.redis)
    replay: list[ModelMessage] = []
    tool_steps = [s for s in steps if s.kind == StepKind.TOOL and s.tool is not None]
    for step in tool_steps:
        assert step.tool is not None
        call_id = f"step-{step.ordinal}"
        if step.status == StepStatus.SUCCEEDED and step.result is not None:
            outcome: dict[str, Any] | str = model_view(
                step.result, state.book.add_stored(step.result)
            )
            replay += planner.replayed_call(step.tool, step.args, call_id, outcome, failed=False)
        else:
            reason = step.error_message or "This call failed."
            replay += planner.replayed_call(step.tool, step.args, call_id, reason, failed=True)
    turns = (await repo.run_usage(session, state.run_id)).turns
    return _Resume(replay, RunUsage(requests=turns, tool_calls=len(tool_steps)))


async def _answer(state: RunState, platform: PlatformDeps, steps: list[AgentStep]) -> str:
    """Planning, then the answer loop; returns the model's answer."""
    run_row = state.run
    settings = platform.settings
    model: Model = planner.base_model(settings)  # ModelNotConfigured without a key
    now = datetime.now(UTC)
    if run_row.status == AgentRunStatus.QUEUED:
        await _move(
            state,
            AgentRunStatus.PLANNING,
            started_at=now,
            model=model.model_name,
            prompt_version=planner.prompt_version(),
        )
    clock = run_row.started_at or now  # a resumed run keeps its clock (FR-AGT-05)
    async with state.sessionmaker() as session:
        user_id = run_row.requested_by_user_id
        role = await repo.member_role(session, user_id) if user_id is not None else None
        if user_id is None or role is None:
            raise RunRefused("forbidden")
        credits = await quota(session, now=now)
        await session.commit()
        if not credits.allows(CREDIT_COSTS[AiFeature.AGENT_TURN]):
            raise RunRefused("quota_exceeded")
        context = await build_context(session, run_row, now=clock)
        resume = await _resume(session, state, steps)
        await session.commit()
    if run_row.status != AgentRunStatus.RUNNING:
        await _move(state, AgentRunStatus.RUNNING)
    async with state.sessionmaker() as tool_session:
        deps = ToolContext(
            session=tool_session,
            sessionmaker=state.sessionmaker,
            platform=platform,
            workspace_id=state.workspace_id,
            timezone=context.timezone,
            now=clock,
            principal=Principal(user_id=user_id, role=Role(role)),
            run_id=state.run_id,
        )
        return await planner.answer(
            state,
            deps,
            context,
            request=run_row.request,
            replay=resume.replay,
            usage=resume.usage,
            model=model,
            settings=settings,
        )


# ---------------------------------------------------------------- endings


async def _finish(state: RunState, output: str) -> None:
    """The model's answer: citations renumbered, succeeded (partial when a step failed)."""
    text = output.strip()
    if not text:
        await _fail(state, "ai_invalid_output")
        return
    answer, refs = cite(text, state.book)
    status = AgentRunStatus.PARTIAL if state.failed_steps else AgentRunStatus.SUCCEEDED
    await _complete(
        state, status, answer=answer, answer_refs=refs, report_summary="Wrote the answer"
    )


async def _stop_early(state: RunState, code: str, reason: str) -> None:
    """A cap or the credits stopped the loop (§15): no model is asked again; the answer lists
    what the finished steps found (partial), or the run fails when nothing finished."""
    async with state.sessionmaker() as session:
        await repo.fail_running_steps(
            session, state.run_id, code=code, message=STOPPED_STEP, at=datetime.now(UTC)
        )
        await session.commit()
        steps = await repo.steps_of(session, state.run_id)
    book = RefBook()  # numbered from the stored steps, like the model's view
    found: list[Found] = []
    for step in steps:
        if step.kind != StepKind.TOOL:
            continue
        label = progress.step_label(state.tools, step.kind, step.tool)
        if step.status == StepStatus.SUCCEEDED and step.result is not None:
            caveats = step.result.get("caveats") or []
            found.append(
                Found(
                    label=label,
                    summary=progress.step_summary(step.result) or label,
                    numbers=book.add_stored(step.result),
                    caveats=[c for c in caveats if isinstance(c, str)],
                )
            )
        else:
            found.append(Found(label=label, summary=None, error=step.error_message))
    message = f"Stopped before finishing because {reason}."
    text = fallback_answer(reason, found)
    if text is None:
        await _complete(
            state,
            AgentRunStatus.FAILED,
            error_code=code,
            error_message=MESSAGES.get(code, message),
        )
        return
    answer, refs = cite(text, book)
    await _complete(
        state,
        AgentRunStatus.PARTIAL,
        answer=answer,
        answer_refs=refs,
        error_code=code,
        error_message=message,
        report_summary="Listed what I found before stopping",
    )


async def _fail(state: RunState, code: str) -> None:
    async with state.sessionmaker() as session:
        await repo.fail_running_steps(
            session, state.run_id, code=code, message=STOPPED_STEP, at=datetime.now(UTC)
        )
        await session.commit()
    await _complete(state, AgentRunStatus.FAILED, error_code=code, error_message=MESSAGES[code])


async def _complete(
    state: RunState,
    status: AgentRunStatus,
    *,
    answer: str | None = None,
    answer_refs: list[Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    report_summary: str | None = None,
) -> None:
    """The final status, answer, citations and usage in one conditional update, with the report
    step when there is an answer; agent.run.updated and agent.completed. A run finished
    meanwhile (cancelled) keeps its status; only its usage is stored."""
    completed = datetime.now(UTC)
    refs = [ref.model_dump(mode="json") for ref in answer_refs or []]
    async with state.sessionmaker() as session:
        usage = await repo.run_usage(session, state.run_id)
        values: dict[str, Any] = {
            "answer": answer,
            "answer_refs": refs,
            "error_code": error_code,
            "error_message": error_message,
            "completed_at": completed,
            "credits": usage.credits,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        }
        if not await repo.set_status(session, state.run_id, status, **values):
            await session.rollback()
            await state.store_usage()
            return
        if report_summary is not None:
            started_at, latency = state.last_turn or (completed, 0)
            step = repo.add_step(
                session,
                state.run_id,
                state.next_ordinal,
                id=uuid.uuid4(),
                kind=StepKind.REPORT,
                args={},
                result={"summary": report_summary},
                status=StepStatus.SUCCEEDED,
                attempts=1,
                latency_ms=latency,
                started_at=started_at,
                completed_at=completed,
            )
            await session.flush()
            state.next_ordinal += 1
            state.step_count += 1
            progress.queue_step(
                session,
                state.tools,
                workspace_id=state.workspace_id,
                requested_by_user_id=state.run.requested_by_user_id,
                step=step,
            )
        state.run.status = status
        for name, value in values.items():
            setattr(state.run, name, value)
        progress.queue_run(session, state.run, state.step_count)
        await commit_and_publish(session, state.redis)
    log.info(
        "agent_run",
        run_id=str(state.run_id),
        status=status,
        steps=state.step_count,
        turns=usage.turns,
        credits=usage.credits,
        error_code=error_code,
    )
