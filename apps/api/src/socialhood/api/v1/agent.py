"""Ask Social Hood (§2.15 …/agent/*; FR-AGT-01…10, TR-AGT-07, TR-AGT-08; agent-architecture.html
§9, §11): runs, threads, the agent policy and approvals.

A member starts a run with a question; it is stored ``queued`` and run_agent (jobs/tasks/agent.py)
answers it in the background, publishing agent.run.updated, agent.step and agent.completed
(schemas/agent.py) as it goes. A member sees their own runs and threads; owners and admins see
every run (FR-AGT-07). A run, thread or approval that isn't this workspace's (or, for a member,
isn't theirs) is 404 not_found. A refused write is a step result, never an HTTP error.

The routes below are the PA contract. TA.1 built the runs, threads and policy read
(services/agent_runs.py); the policy change and approvals are R2 and keep their ``openapi_extra``
marker until built, so the tenancy suite covers them then.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from socialhood.agent import orchestrator
from socialhood.api.v1.ai import pending
from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.billing.entitlements import credits_gate
from socialhood.realtime.events import commit_and_publish
from socialhood.schemas.agent import (
    AgentApproval,
    AgentApprovalList,
    AgentPolicy,
    AgentPolicyUpdate,
    AgentRun,
    AgentRunCreate,
    AgentRunDetail,
    AgentRunList,
    AgentThreadList,
    ApprovalApprove,
    ApprovalStatusName,
)
from socialhood.services import agent_runs

router = APIRouter(prefix="/v1/w/{wid}", tags=["agent"])


# ---------------------------------------------------------------- runs (TA.1)


@router.post("/agent/runs", status_code=202, operation_id="create_agent_run")
async def create_agent_run(
    request: Request, body: AgentRunCreate, ctx: AnyMember, session: Session
) -> AgentRun:
    """FR-AGT-01: ask a question. The run is stored ``queued`` with the policy's mode, run_agent
    is enqueued (interactive lane, lock ``agent:{run_id}``) and the queued run is returned; nothing
    is reserved yet. 404 when ``thread_id`` isn't one of the caller's threads; 402 quota_exceeded
    (ai_credits_monthly, with the plan's limit) when the workspace has no AI credits left
    (nothing is stored)."""
    async with credits_gate(session):  # §2.15 "agent · credits": the 402 names the plan's limit
        row = await agent_runs.create(session, ctx, body)
    [out] = await agent_runs.runs_out(session, [row])
    await commit_and_publish(session, request.app.state.redis)
    await orchestrator.enqueue_run(row.id, row.workspace_id)  # after the commit
    return out


@router.get("/agent/runs", operation_id="list_agent_runs")
async def list_agent_runs(
    ctx: AnyMember,
    session: Session,
    thread_id: Annotated[uuid.UUID | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AgentRunList:
    """FR-AGT-07 run history, newest first: the caller's runs, or every run for owners and
    admins. ``thread_id`` keeps one thread's runs (the Ask panel reverses them into a
    conversation); a thread that isn't the caller's lists nothing."""
    return await agent_runs.list_runs(session, ctx, thread_id=thread_id, cursor=cursor, limit=limit)


@router.get("/agent/runs/{run_id}", operation_id="get_agent_run")
async def get_agent_run(run_id: uuid.UUID, ctx: AnyMember, session: Session) -> AgentRunDetail:
    """One run with every step: the tool in plain words, arguments, status, result summary,
    verification, latency; the run's credits, model and prompt version (TR-AGT-08)."""
    row = await agent_runs.visible_run(session, ctx, run_id)
    return await agent_runs.detail_out(session, row)


@router.post("/agent/runs/{run_id}/cancel", operation_id="cancel_agent_run")
async def cancel_agent_run(
    request: Request, run_id: uuid.UUID, ctx: AnyMember, session: Session
) -> AgentRun:
    """Stop at the next step (§9): an unfinished run becomes ``cancelled`` at once and run_agent
    stops before its next step or model turn; a step already running finishes and is kept. A
    finished run is returned as it is. Only the member who asked, or an owner or admin."""
    row = await agent_runs.cancel(session, ctx, run_id)
    [out] = await agent_runs.runs_out(session, [row])
    await commit_and_publish(session, request.app.state.redis)
    return out


@router.get("/agent/threads", operation_id="list_agent_threads")
async def list_agent_threads(
    ctx: AnyMember,
    session: Session,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AgentThreadList:
    """The caller's Ask panel threads, most recent activity first (owners and admins too: threads
    are personal; other members' runs are in the run history)."""
    return await agent_runs.list_threads(session, ctx, cursor=cursor, limit=limit)


# ---------------------------------------------------------------- policy (FR-AGT-10)


@router.get("/agent/policy", operation_id="get_agent_policy")
async def get_agent_policy(ctx: Admin, session: Session) -> AgentPolicy:
    """The workspace's agent mode, capability switches and limits. In R1 the mode is always
    read_only and every switch is off."""
    row = await agent_runs.load_policy(session)
    out = await agent_runs.policy_out(session, row)
    await session.commit()
    return out


@router.put("/agent/policy", operation_id="update_agent_policy", openapi_extra=pending("R2"))
async def update_agent_policy(body: AgentPolicyUpdate, ctx: Admin, session: Session) -> AgentPolicy:
    """R2: replace the policy (owners and admins). 409 for ``autonomous`` until R3."""
    raise NotImplementedError("R2")


# ---------------------------------------------------------------- approvals (R2, FR-AGT-09)


@router.get("/agent/approvals", operation_id="list_agent_approvals", openapi_extra=pending("R2"))
async def list_agent_approvals(
    ctx: AnyMember,
    session: Session,
    status: Annotated[ApprovalStatusName, Query()] = "pending",
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AgentApprovalList:
    """R2: approvals across runs; a member sees the ones they may decide (their own runs' writes
    their role allows), owners and admins all."""
    raise NotImplementedError("R2")


@router.post(
    "/agent/approvals/{approval_id}/approve",
    operation_id="approve_agent_approval",
    openapi_extra=pending("R2"),
)
async def approve_agent_approval(
    approval_id: uuid.UUID, body: ApprovalApprove, ctx: AnyMember, session: Session
) -> AgentApproval:
    """R2: run the write as shown, or with edited ``args`` (re-checked by the gateway). The
    caller's role must allow the tool (403 forbidden); 409 when it is no longer pending."""
    raise NotImplementedError("R2")


@router.post(
    "/agent/approvals/{approval_id}/reject",
    operation_id="reject_agent_approval",
    openapi_extra=pending("R2"),
)
async def reject_agent_approval(
    approval_id: uuid.UUID, ctx: AnyMember, session: Session
) -> AgentApproval:
    """R2: cancel the write; the step is skipped and the run continues without it. 409 when it
    is no longer pending."""
    raise NotImplementedError("R2")
