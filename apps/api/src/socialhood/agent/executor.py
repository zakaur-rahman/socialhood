"""Runs one step (TR-AGT-03, TR-AGT-07, TR-AGT-08, TA.2; agent-architecture.html §9, §15, §16).

For each tool call the model makes, the executor:

1. checks the run is still open (a member may have cancelled it) and inside its wall time;
2. validates the arguments with the tool's input model; invalid ones go back to the model as a
   retry (once, then the run fails: §15) and are not a step;
3. inserts the step (next ordinal, kind ``tool``, the tool, its tier, the validated args,
   ``running``, attempt 1, idempotency_key ``{run_id}:{ordinal}``) and commits before running it
   (agent.step, agent.run.updated);
4. calls the handler with the run's ``ToolContext``; a transient error (a timeout, a dropped
   database connection, a retryable AI error) is retried once (§15);
5. stores the result (``result_model`` dumped as JSON), ``succeeded``, latency_ms and
   completed_at, or ``failed`` with error_code and error_message, and publishes agent.step. A
   failed step goes back to the model as a failed tool call, so it continues with what it has
   and the answer says which data was unavailable (FR-AGT-06).

The model sees a result with its refs numbered for citation (agent/report.py). Each step logs one
``agent_step`` line with the run id, ordinal, tool, status and latency (§16); arguments and
results stay in the table (SEC-07). R2 adds the gateway decision before a write, the verifier
after it, and retries of transient write errors with the same idempotency key.

``RunState`` is what one job knows about its run while the model loop runs: the clock, the
citation book, the next ordinal, and the checks every step and model turn make first.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from pydantic_ai import ModelRetry, ToolFailed
from redis.asyncio import Redis
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.agent import progress
from socialhood.agent.registry import ToolContext, ToolRegistry, ToolResult, ToolSpec
from socialhood.agent.report import RefBook, model_view
from socialhood.ai.provider import AIError
from socialhood.errors import ERROR_CODES, ApiError
from socialhood.models.agent import FINAL_RUN_STATUSES, AgentRun, AgentStep, StepKind, StepStatus
from socialhood.observability.logging import get_logger
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import agent as repo

log = get_logger(__name__)

TOOL_TIMEOUT_S = 30.0  # one attempt of one read tool
TOOL_ATTEMPTS = 2  # reads retry once on a transient error (§15)
ERROR_MAX_CHARS = 300


class RunStopped(Exception):
    """The run was cancelled (or finished elsewhere) while the loop ran: stop, write nothing."""


class RunLimitReached(Exception):
    """A cap was reached before the model wrote the answer (§15): the run reports what it has."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason  # "…because {reason}"


@dataclass(eq=False)
class RunState:
    """One job's view of its run while the model loop runs."""

    run: AgentRun  # loaded when the job started; status and error follow our own changes
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    tools: ToolRegistry
    deadline: float  # time.monotonic() past which the run stops (RUN_WALL_TIME)
    next_ordinal: int = 0
    step_count: int = 0
    failed_steps: int = 0
    book: RefBook = field(default_factory=RefBook)
    # Set when the tools were withheld so the model writes the answer (a cap is near).
    tools_withheld: bool = False
    # The latest model turn: its start (UTC) and latency, for the report step.
    last_turn: tuple[datetime, int] | None = None

    @property
    def run_id(self) -> uuid.UUID:
        return self.run.id

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.run.workspace_id

    def time_left(self) -> float:
        return self.deadline - time.monotonic()

    async def check_open(self) -> None:
        """Before every step and model turn: stop when the run is no longer unfinished, or when
        its wall time is up (§9, §15)."""
        async with self.sessionmaker() as session:
            status = await repo.run_status(session, self.run_id)
        if status is None or status in FINAL_RUN_STATUSES:
            raise RunStopped(status or "deleted")
        if self.time_left() <= 0:
            raise RunLimitReached("timeout", "it took longer than two minutes")

    async def credits_used(self) -> int:
        async with self.sessionmaker() as session:
            return (await repo.run_usage(session, self.run_id)).credits

    async def store_usage(self) -> None:
        """The run's credits and tokens so far (also shows the sweeper the run is alive)."""
        async with self.sessionmaker() as session:
            await repo.store_usage(session, self.run_id)
            await session.commit()

    # ---- steps

    async def start_step(self, spec: ToolSpec[Any, Any], args: dict[str, Any]) -> AgentStep:
        ordinal = self.next_ordinal
        self.next_ordinal += 1
        async with self.sessionmaker() as session:
            step = repo.add_step(
                session,
                self.run_id,
                ordinal,
                id=uuid.uuid4(),
                kind=StepKind.TOOL,
                tool=spec.name,
                tier=spec.tier,
                args=args,
                status=StepStatus.RUNNING,
                attempts=1,
                latency_ms=0,
                started_at=datetime.now(UTC),
            )
            await session.flush()
            self.step_count += 1
            progress.queue_step(
                session,
                self.tools,
                workspace_id=self.workspace_id,
                requested_by_user_id=self.run.requested_by_user_id,
                step=step,
            )
            progress.queue_run(session, self.run, self.step_count)
            await commit_and_publish(session, self.redis)
        return step

    async def end_step(self, step: AgentStep, **values: Any) -> None:
        async with self.sessionmaker() as session:
            await repo.update_step(session, step.id, **values)
            for name, value in values.items():
                setattr(step, name, value)
            progress.queue_step(
                session,
                self.tools,
                workspace_id=self.workspace_id,
                requested_by_user_id=self.run.requested_by_user_id,
                step=step,
            )
            await commit_and_publish(session, self.redis)
        log.info(
            "agent_step",
            run_id=str(self.run_id),
            ordinal=step.ordinal,
            tool=step.tool,
            status=step.status,
            latency_ms=step.latency_ms,
            attempts=step.attempts,
            error_code=step.error_code,
        )


def _problems(error: ValidationError) -> str:
    parts = [
        f"{'.'.join(str(p) for p in e['loc']) or 'arguments'}: {e['msg']}"
        for e in error.errors()[:5]
    ]
    return "; ".join(parts)


def _transient(error: BaseException) -> bool:
    if isinstance(error, AIError):
        return error.retryable
    return isinstance(error, TimeoutError | OperationalError | InterfaceError | ConnectionError)


def _failure(error: BaseException) -> tuple[str, str]:
    """(error_code, message) for a failed step, in words safe to show the member."""
    if isinstance(error, ModelRetry | ToolFailed):  # the tool's own words for the model
        code = "invalid_arguments" if isinstance(error, ModelRetry) else "tool_failed"
        return code, str(error)[:ERROR_MAX_CHARS]
    if isinstance(error, ApiError):
        return error.code, (error.detail or ERROR_CODES[error.code].title)[:ERROR_MAX_CHARS]
    if isinstance(error, TimeoutError):
        return "timeout", "It took too long to answer."
    if isinstance(error, AIError):
        return "ai_unavailable", "The AI couldn't answer just now."
    return "tool_error", "Something went wrong while fetching this."


async def execute(
    state: RunState, ctx: ToolContext, spec: ToolSpec[Any, Any], raw: dict[str, Any]
) -> dict[str, Any]:
    """Run one tool call as a step; the result as the model sees it."""
    await state.check_open()
    try:
        args: BaseModel = spec.input_model.model_validate(raw)
    except ValidationError as error:
        raise ModelRetry(f"Invalid arguments for {spec.name}: {_problems(error)}") from error
    step = await state.start_step(spec, args.model_dump(mode="json"))
    started = time.monotonic()
    attempt = 1
    while True:
        try:
            async with asyncio.timeout(TOOL_TIMEOUT_S):
                result = await spec.handler(ctx, args)
            if not isinstance(result, spec.result_model) or not isinstance(result, ToolResult):
                raise TypeError(f"{spec.name} returned {type(result).__name__}")
            await ctx.session.commit()  # ends the read transaction; R1 tools change nothing
            break
        except Exception as error:
            await ctx.session.rollback()
            if attempt < TOOL_ATTEMPTS and _transient(error):
                attempt += 1
                continue
            code, message = _failure(error)
            if code == "tool_error":
                log.warning("agent_tool_failed", tool=spec.name, exc_info=True)
            state.failed_steps += 1
            await state.end_step(
                step,
                status=StepStatus.FAILED,
                attempts=attempt,
                latency_ms=round((time.monotonic() - started) * 1000),
                error_code=code,
                error_message=message,
                completed_at=datetime.now(UTC),
            )
            if isinstance(error, ModelRetry | ToolFailed):
                raise
            raise ToolFailed(
                f"{spec.label} failed: {message} Say this data isn't available; don't guess it."
            ) from error
    data = result.model_dump(mode="json")
    numbers = state.book.add(result.refs)
    await state.end_step(
        step,
        status=StepStatus.SUCCEEDED,
        attempts=attempt,
        result=data,
        latency_ms=round((time.monotonic() - started) * 1000),
        completed_at=datetime.now(UTC),
    )
    return model_view(data, numbers)
