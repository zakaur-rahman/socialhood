"""Ask Amplychat over MCP (01-design.md §4.1, decision D8): ask_amplychat and get_ask_answer.

Ask Amplychat's own agent has tools and numbers computed by services that the outside AI does not
(cited answers, correct date ranges). A question is a normal Ask run (``agent_runs.create``, the
route's own path): it uses the plan's AI credits, is limited by the ``ai`` rate limit, appears in
the member's Ask history, and is answered in the background by the same worker. This only waits
up to 25 seconds for it. A longer run comes back as an ``ask_run_id`` to collect with
``get_ask_answer``, because a tool call must answer within a client's timeout (Codex waits 60
seconds).

Ask is read-only (it never changes the workspace; FR-AGT-02), so these are read tools: they are
available in every mode that reads. The question is saved with its run, so the call commits its
own work before it waits.

A question sent twice in two minutes by one connection is the same run, so a client that retries a
broken response doesn't pay twice.
"""

from __future__ import annotations

import asyncio
import math
import time
import uuid

from pydantic import BaseModel, Field

from socialhood.agent import orchestrator
from socialhood.auth.deps import ROLE_RANK, WorkspaceContext
from socialhood.billing.entitlements import credits_gate
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.mcp.audit import digest
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import ToolInput, ToolOutput, registry, tool
from socialhood.models.agent import AgentRunStatus
from socialhood.models.identity import Role, User
from socialhood.observability.logging import get_logger
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import agent as agent_repo
from socialhood.schemas.agent import AgentRunCreate
from socialhood.security import ratelimit
from socialhood.services import agent_runs

log = get_logger(__name__)

WAIT_S = 25.0
POLL_S = 1.0
SAME_QUESTION_S = 120
DONE = frozenset(
    {
        AgentRunStatus.SUCCEEDED,
        AgentRunStatus.PARTIAL,
        AgentRunStatus.FAILED,
        AgentRunStatus.CANCELLED,
        AgentRunStatus.EXPIRED,
    }
)


class AskInput(ToolInput):
    question: str = Field(
        min_length=1,
        max_length=1000,
        description="A question about the business's own data, in plain words: “what are people "
        "asking in my DMs this week?”, “which Reel did best last month?”.",
    )


class AskRunInput(ToolInput):
    ask_run_id: uuid.UUID = Field(description="The ask_run_id ask_amplychat returned.")


class CitationOut(BaseModel):
    number: int  # [n] in the answer
    kind: str
    label: str
    id: uuid.UUID


class ActionLink(BaseModel):
    label: str
    dashboard_url: str | None = None
    note: str | None = None


class AskResult(ToolOutput):
    ask_run_id: uuid.UUID
    status: str  # queued, running, succeeded, partial, failed, cancelled, expired
    finished: bool
    answer: str | None = None  # markdown; its numbers come from Amplychat's services
    citations: list[CitationOut] = Field(default_factory=list)
    action_links: list[ActionLink] = Field(default_factory=list)  # screens in Amplychat
    credits_used: int = 0
    error: str | None = None
    next_step: str | None = None


async def _rate_limit(call: ToolCall) -> None:
    if not call.settings.rate_limits_enabled:
        return
    try:
        wait = await ratelimit.hit(call.redis, ratelimit.LIMITS["ai"], str(call.workspace.id))
    except Exception as error:
        log.warning("rate_limit_unavailable", limit="ai", error=type(error).__name__)
        return
    if wait > 0:
        seconds = max(1, math.ceil(wait))
        raise ApiError(
            "rate_limited",
            f"Too many questions to Amplychat just now. Try again in {seconds} seconds.",
            headers={"Retry-After": str(seconds)},
        )


async def _snapshot(call: ToolCall, run_id: uuid.UUID) -> AskResult:
    """The run as it is now, read in a fresh transaction (the run is written by the worker)."""
    with workspace_scope(call.workspace.id):
        async with call.sessionmaker() as session:
            row = await agent_repo.get_run(session, run_id)
            if row is None or not (
                row.requested_by_user_id == call.principal.user_id
                or ROLE_RANK[call.principal.role] >= ROLE_RANK[Role.ADMIN]
            ):
                raise ApiError("not_found", "No Ask run with this id.")
            [out] = await agent_runs.runs_out(session, [row], with_visuals=False)
    status = AgentRunStatus(out.status)
    finished = status in DONE
    links: list[ActionLink] = []
    for card in out.action_cards:
        links.append(
            ActionLink(
                label=card.label,
                dashboard_url=call.dashboard_url(card.route),
                note=card.note,
            )
        )
    summary = {
        AgentRunStatus.SUCCEEDED: "Amplychat answered",
        AgentRunStatus.PARTIAL: "Amplychat answered part of the question",
        AgentRunStatus.FAILED: "Amplychat couldn't answer",
        AgentRunStatus.CANCELLED: "The question was cancelled",
        AgentRunStatus.EXPIRED: "The question expired",
    }.get(status, "Amplychat is still working on the question")
    return AskResult(
        summary=summary,
        ask_run_id=out.id,
        status=status.value,
        finished=finished,
        answer=out.answer,
        citations=[
            CitationOut(number=i, kind=r.kind, label=r.label, id=r.id)
            for i, r in enumerate(out.answer_refs, start=1)
        ],
        action_links=links,
        credits_used=out.credits,
        error=out.error.message if out.error else None,
        next_step=None
        if finished
        else "Still working. Call get_ask_answer with this ask_run_id in a few seconds.",
    )


async def _wait(call: ToolCall, run_id: uuid.UUID) -> AskResult:
    deadline = time.monotonic() + WAIT_S
    while True:
        result = await _snapshot(call, run_id)
        if result.finished or time.monotonic() >= deadline:
            return result
        await asyncio.sleep(POLL_S)


@tool(
    registry,
    name="ask_amplychat",
    title="Ask Amplychat",
    description=(
        "Ask Amplychat's own assistant a question about the business: inbox themes, comments, "
        "post performance, scheduled posts, knowledge gaps. It looks at the workspace's data "
        "with its own tools and returns an answer with numbers computed by Amplychat and "
        "references to the records used. It reads only. It uses the plan's AI credits. If the "
        "answer takes longer than 25 seconds it returns an ask_run_id for get_ask_answer."
    ),
    input_model=AskInput,
    output_model=AskResult,
    scope="ask",
)
async def ask_amplychat(call: ToolCall, args: AskInput) -> AskResult:
    key = f"mcp-ask:{call.principal.credential_id}:{digest({'q': args.question.strip()})}"
    try:
        existing = await call.redis.get(key)
    except Exception:
        existing = None
    if existing:
        return await _wait(
            call, uuid.UUID(existing.decode() if isinstance(existing, bytes) else existing)
        )
    await _rate_limit(call)
    user = await call.session.get(User, call.principal.user_id)
    if user is None:  # the member was removed after authenticating
        raise ApiError("forbidden", "This connection's member is no longer in the workspace.")
    ctx = WorkspaceContext(workspace=call.workspace, role=call.principal.role, user=user)
    async with credits_gate(call.session):
        row = await agent_runs.create(call.session, ctx, AgentRunCreate(request=args.question))
    run_id = row.id
    await commit_and_publish(call.session, call.redis)  # the worker reads it: commit first
    await orchestrator.enqueue_run(run_id, call.workspace.id)
    try:
        await call.redis.set(key, str(run_id), ex=SAME_QUESTION_S)
    except Exception:
        log.warning("mcp_ask_dedupe_unavailable")
    return await _wait(call, run_id)


@tool(
    registry,
    name="get_ask_answer",
    title="Get an Ask answer",
    description=(
        "Collect the answer to a question put to ask_amplychat that was still running. Waits up "
        "to 25 seconds, then reports the status. Members see their own questions; owners and "
        "admins see all."
    ),
    input_model=AskRunInput,
    output_model=AskResult,
    scope="ask",
)
async def get_ask_answer(call: ToolCall, args: AskRunInput) -> AskResult:
    return await _wait(call, args.ask_run_id)
