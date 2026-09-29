"""Ask Social Hood, the agent (§5.5 Agent; FR-AGT-01…15, TR-AGT-01…08; agent-architecture.html
§7): runs, their steps, approvals (R2) and the workspace's agent policy.

The PA contract. The caps and limits below are shared: the orchestrator and planner (TA.1, TA.2),
the tools (TA.4), the API and the database checks all read them. Credits reuse ai_usage_events
(feature ``agent_turn``, ref_type ``agent_run``); business, customer and conversation memory reuse
the knowledge base, contacts, analyses and summaries; task memory is the run.

Lifecycle (§9): a run starts ``queued``; run_agent moves it to ``planning`` (context and time
resolution) and ``running`` (tool calls, each a step), then ``succeeded``, ``partial`` (some steps
failed or were refused; the answer says which) or ``failed``. A member can cancel it at any point
(``cancelled``). In R2 a write the policy doesn't allow outright pauses the run in
``awaiting_approval`` until a person approves or rejects it, or 24 hours pass (``expired``).
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from socialhood.db.base import Base, IdMixin, TimestampMixin
from socialhood.db.tenancy import TenantScoped
from socialhood.models.identity import _in

# ---------------------------------------------------------------- caps (TR-AGT-02, §15, §17)

REQUEST_MAX_CHARS = 2000  # a request as typed (FR-AGT-01)
MAX_TOOL_CALLS = 8  # read tool calls in one answer loop
MAX_MODEL_TURNS = 6  # model calls in one answer loop (each is one agent_turn credit)
MAX_PLAN_STEPS = 12  # R2 plan first
MAX_REPLANS = 2  # R2: re-plans after a failed step
RUN_WALL_TIME = dt.timedelta(minutes=2)  # an R1 run that takes longer fails with what it has
RUN_CREDIT_CAP = 10  # per R1 answer, unless the member accepts a quote (R2)
THREAD_CONTEXT_RUNS = 6  # earlier exchanges of the thread passed to the model as data
STUCK_AFTER = dt.timedelta(minutes=10)  # sweep_agent_runs resumes runs running this long
APPROVAL_TTL = dt.timedelta(hours=24)  # FR-AGT-09
STEP_MAX_ATTEMPTS = 3  # write steps, transient platform errors (§15); reads retry once


class AgentRunSource(StrEnum):
    ASK = "ask"  # a member asked in the Ask panel or page
    STANDING = "standing"  # R3: a saved, scheduled or event-triggered instruction


class AgentMode(StrEnum):
    """The policy's mode (FR-AGT-10, §8). R1 has only ``read_only``."""

    READ_ONLY = "read_only"
    COPILOT = "copilot"  # R2: every write asks
    SUPERVISED = "supervised"  # R2: low-risk writes run, others ask
    AUTONOMOUS = "autonomous"  # R3: permitted writes run within caps


class AgentRunStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"  # R2
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"  # R2: an approval was not given in 24 h


# A run in one of these statuses is finished: cancel returns it as it is, the sweeper leaves it.
FINAL_RUN_STATUSES = frozenset(
    {
        AgentRunStatus.SUCCEEDED,
        AgentRunStatus.PARTIAL,
        AgentRunStatus.FAILED,
        AgentRunStatus.CANCELLED,
        AgentRunStatus.EXPIRED,
    }
)


class StepKind(StrEnum):
    TOOL = "tool"  # one tool call
    CONDITION = "condition"  # R2: a plan condition evaluated by code (agent/plan.py)
    REPORT = "report"  # the final answer written from stored results


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"  # a condition didn't hold, or a step it depends on failed
    BLOCKED = "blocked"  # R2: the gateway refused it (decision refuse:{reason})
    AWAITING_APPROVAL = "awaiting_approval"  # R2


class RiskTier(StrEnum):
    """A tool's fixed risk tier (TR-AGT-03, §8). Only ``read`` and ``draft`` exist in R1."""

    READ = "read"  # reads the workspace's data
    DRAFT = "draft"  # prepares something for a person to act on; changes nothing
    LOW = "low"  # R2: a single reply, schedule a message, pause an automation
    HIGH = "high"  # R2: bulk, send now, schedule or publish a post, activate an automation
    DESTRUCTIVE = "destructive"  # R2: delete an automation, cancel published content


WRITE_TIERS = frozenset({RiskTier.LOW, RiskTier.HIGH, RiskTier.DESTRUCTIVE})


class GatewayDecision(StrEnum):
    """agent_steps.decision for a write step (TR-AGT-04). A refusal is stored as
    ``refuse:{reason}``, e.g. ``refuse:agent_permission_off``."""

    EXECUTE = "execute"
    APPROVAL = "approval"
    REFUSE = "refuse"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"  # an edit replaced it with a new pending approval


class AgentCapability(StrEnum):
    """The policy's per-capability switches (FR-AGT-10), all off until an owner or admin turns
    them on in R2. Every write tool names one; a switched-off capability refuses in any mode."""

    SEND_REPLIES = "send_replies"
    SCHEDULE_MESSAGES = "schedule_messages"
    SCHEDULE_POSTS = "schedule_posts"
    CREATE_AUTOMATIONS = "create_automations"
    DELETE_AUTOMATIONS = "delete_automations"
    BULK_ACTIONS = "bulk_actions"


DEFAULT_PERMISSIONS: dict[str, bool] = {capability.value: False for capability in AgentCapability}
DEFAULT_LIMITS: dict[str, int] = {"bulk_max": 50, "writes_per_hour": 30, "writes_per_day": 200}


def _jsonb(value: object) -> Any:
    return sql(f"'{json.dumps(value)}'::jsonb")


class AgentRun(IdMixin, TimestampMixin, TenantScoped, Base):
    """One request (R1) or one run of a standing instruction (R3) (FR-AGT-07, TR-AGT-08)."""

    __tablename__ = "agent_runs"

    # The Ask panel thread; runs in one thread share context. A new thread's id is its first
    # run's id.
    thread_id: Mapped[uuid.UUID] = mapped_column()
    # The principal; null for standing instructions (R3).
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(Text, server_default=sql("'ask'"))
    request: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)  # the policy's mode when the run started
    status: Mapped[str] = mapped_column(Text, server_default=sql("'queued'"))
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # R2: agent/plan.Plan
    answer: Mapped[str | None] = mapped_column(Text)  # the report (markdown subset)
    # Citations [{kind, id, label}] (schemas/agent.AnswerRef); [n] in the answer is item n.
    answer_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=_jsonb([]))
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    credits: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_agent_runs_workspace", "workspace_id", sql("created_at DESC")),
        Index("ix_agent_runs_thread", "thread_id", "created_at"),
        CheckConstraint(_in("source", AgentRunSource), name="source"),
        CheckConstraint(_in("mode", AgentMode), name="mode"),
        CheckConstraint(_in("status", AgentRunStatus), name="status"),
        CheckConstraint(
            f"char_length(request) BETWEEN 1 AND {REQUEST_MAX_CHARS}", name="request_length"
        ),
        CheckConstraint("jsonb_typeof(answer_refs) = 'array'", name="answer_refs"),
    )


class AgentStep(IdMixin, TimestampMixin, TenantScoped, Base):
    """Every tool call, condition and report of a run, in order (TR-AGT-07, TR-AGT-08). Persisted
    before and after it runs, so a crashed run resumes from its last completed step."""

    __tablename__ = "agent_steps"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(SmallInteger)  # 0-based, in the order they ran
    kind: Mapped[str] = mapped_column(Text)
    tool: Mapped[str | None] = mapped_column(Text)  # the registered tool's name (tool steps)
    tier: Mapped[str | None] = mapped_column(Text)  # the tool's risk tier
    # The validated input (secrets never; message text is kept, it is the user's data).
    args: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # The compact typed result (agent/registry.ToolResult): summary, refs, action card, data.
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default=sql("'pending'"))
    decision: Mapped[str | None] = mapped_column(Text)  # R2 gateway: GatewayDecision
    # {verified, checked, external_ids} (R2 writes, TR-AGT-06)
    verification: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # "{run_id}:{ordinal}", reused on every retry so a write never runs twice (TR-AGT-07).
    idempotency_key: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=sql("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, server_default=sql("0"))
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("run_id", "ordinal"),
        CheckConstraint(_in("kind", StepKind), name="kind"),
        CheckConstraint(f"tier IS NULL OR {_in('tier', RiskTier)}", name="tier"),
        CheckConstraint(_in("status", StepStatus), name="status"),
        CheckConstraint(
            "decision IS NULL OR decision ~ '^(execute|approval|refuse:[a-z_]+)$'",
            name="decision",
        ),
        CheckConstraint("kind <> 'tool' OR (tool IS NOT NULL AND tier IS NOT NULL)", name="tool"),
        CheckConstraint("ordinal >= 0", name="ordinal"),
        CheckConstraint("attempts >= 0", name="attempts"),
    )


class AgentApproval(IdMixin, TimestampMixin, TenantScoped, Base):
    """R2 (FR-AGT-09): a write the policy doesn't allow outright, waiting for a person. Created
    now so the contract is fixed; nothing writes it in R1."""

    __tablename__ = "agent_approvals"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    step_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_steps.id", ondelete="CASCADE"))
    summary: Mapped[str] = mapped_column(Text)  # what will happen, in plain words
    # The exact tool and args that will run ({tool, args}); an edit replaces it and is re-checked.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default=sql("'pending'"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # created + 24 h
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_agent_approvals_pending",
            "step_id",
            unique=True,
            postgresql_where=sql("status = 'pending'"),
        ),
        CheckConstraint(_in("status", ApprovalStatus), name="status"),
    )


class AgentPolicy(IdMixin, TimestampMixin, TenantScoped, Base):
    """The workspace's agent configuration (FR-AGT-10, §8): one row, created with the workspace.
    Owners and admins edit it in R2; no tool can change it."""

    __tablename__ = "agent_policies"

    mode: Mapped[str] = mapped_column(Text, server_default=sql("'read_only'"))
    # AgentCapability -> bool, all false by default.
    permissions: Mapped[dict[str, bool]] = mapped_column(
        JSONB, server_default=_jsonb(DEFAULT_PERMISSIONS)
    )
    # {bulk_max, writes_per_hour, writes_per_day}
    limits: Mapped[dict[str, int]] = mapped_column(JSONB, server_default=_jsonb(DEFAULT_LIMITS))
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("workspace_id"),
        CheckConstraint(_in("mode", AgentMode), name="mode"),
        CheckConstraint("jsonb_typeof(permissions) = 'object'", name="permissions"),
        CheckConstraint("jsonb_typeof(limits) = 'object'", name="limits"),
    )
