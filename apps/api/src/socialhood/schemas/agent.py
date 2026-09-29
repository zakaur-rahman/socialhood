"""Ask Social Hood shapes (§2.15 …/agent/*; FR-AGT-01…10, TR-AGT-07, TR-AGT-08;
agent-architecture.html §11, §12).

The PA contract. Answers and their pieces:

- ``answer`` is a markdown subset: paragraphs, ``**bold**``, bullet (``- ``) and numbered
  (``1. ``) lists, and pipe tables with a header row for figures. No headings, links, images,
  code or HTML; the web renders anything else as plain text. Every answer states the time range
  and sample size it used (FR-AGT-04, FR-AGT-05).
- Citations: ``[n]`` in the answer is the n-th item of ``answer_refs`` (1-based), a record the
  answer used (FR-AGT-01). The web links each to its screen.
- Action cards (FR-AGT-03) come from the run's draft steps: each succeeded draft step's result
  holds one card (agent/registry.DraftResult), and ``action_cards`` lists them in step order. A
  card opens an existing screen pre-filled; the member completes the action there, so every
  existing check applies. Nothing in R1 changes anything (FR-AGT-02).

Runs belong to the member who asked: a member sees their own runs and threads, owners and admins
see every run (FR-AGT-07). The real-time stream is shared by the workspace's members, so agent
events carry no request or answer text; the requester's panel fetches the run on
``agent.completed`` (TR-RT-03 otherwise).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field

from socialhood.models.agent import REQUEST_MAX_CHARS
from socialhood.schemas.automations import ActionName, PostScopeName, TriggerName
from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.inbox import Actor, ErrorInfo

AgentRunStatusName = Literal[
    "queued",
    "planning",
    "running",
    "awaiting_approval",
    "succeeded",
    "partial",
    "failed",
    "cancelled",
    "expired",
]
AgentRunSourceName = Literal["ask", "standing"]
AgentModeName = Literal["read_only", "copilot", "supervised", "autonomous"]
StepKindName = Literal["tool", "condition", "report"]
StepStatusName = Literal[
    "pending", "running", "succeeded", "failed", "skipped", "blocked", "awaiting_approval"
]
RiskTierName = Literal["read", "draft", "low", "high", "destructive"]
ApprovalStatusName = Literal["pending", "approved", "rejected", "expired", "superseded"]
# What an answer can cite; each opens its screen in the web:
# - post: a published post (media item), Comments → post detail
# - conversation: an inbox conversation (also stands for its contact)
# - comment: a comment, on its post's detail
# - automation: an automation's editor
# - scheduled_message: a scheduled message, in its conversation
# - scheduled_post: a scheduled post, in the composer
# - knowledge_source: a knowledge source (FAQ, note, page or file)
AnswerRefKind = Literal[
    "post",
    "conversation",
    "comment",
    "automation",
    "scheduled_message",
    "scheduled_post",
    "knowledge_source",
]
ActionKind = Literal["schedule_message", "reply_to_comment", "automation_draft"]


# ---- answers


class AnswerRef(ResponseModel):
    """A record an answer used (FR-AGT-01): ``[n]`` in the answer is item n of answer_refs."""

    kind: AnswerRefKind
    id: uuid.UUID
    label: str  # short, e.g. "Reel of 26 Sep", "Priya Nair", "“Too expensive for me”"


class ScheduleMessagePrefill(ResponseModel):
    """The conversation's schedule popover (F-06), limited to the reply window."""

    conversation_id: uuid.UUID
    text: str
    # The resolved time (UTC), inside the window; None when no time fits (the card's note says
    # why and the member picks one).
    send_at: datetime | None = None
    window_closes_at: datetime | None = None  # the latest time the popover allows


class CommentReplyPrefill(ResponseModel):
    """The post detail's reply box on one comment (FR-CMT-04)."""

    comment_id: uuid.UUID
    post_id: uuid.UUID
    text: str
    private: bool = False  # a private reply (DM) instead of a public one


class AutomationDraftPrefill(ResponseModel):
    """The automation editor, new and unsaved, filled with a draft (F-11). Field names and rules
    are AutomationDefinition's (schemas/automations.py); the editor saves it like any draft."""

    template_key: str | None = None  # the template it started from (FR-AUT-12)
    name: str
    social_account_id: uuid.UUID | None = None
    trigger: TriggerName | None = None
    keywords: list[str] = Field(default_factory=list)
    action: ActionName | None = None
    message_text: str | None = None
    ai_instructions: str | None = None
    public_reply_texts: list[str] = Field(default_factory=list)
    post_scope: PostScopeName = "all"
    media_item_ids: list[uuid.UUID] = Field(default_factory=list)


class _ActionCardBase(ResponseModel):
    label: str  # the button, e.g. "Schedule this message"
    # The screen it opens, relative to the workspace (/w/{slug}/), with its query string, e.g.
    # "inbox/{conversation_id}?schedule=1".
    route: str
    note: str | None = None  # one line shown on the card, e.g. "Priya's window closes 8:12 AM."


# ``kind`` has no default so that it is required in the OpenAPI document (the web narrows on it).
class ScheduleMessageAction(_ActionCardBase):
    kind: Literal["schedule_message"]
    prefill: ScheduleMessagePrefill


class CommentReplyAction(_ActionCardBase):
    kind: Literal["reply_to_comment"]
    prefill: CommentReplyPrefill


class AutomationDraftAction(_ActionCardBase):
    kind: Literal["automation_draft"]
    prefill: AutomationDraftPrefill


# FR-AGT-03: a prepared action the member completes in the existing screen.
ActionCard = Annotated[
    ScheduleMessageAction | CommentReplyAction | AutomationDraftAction,
    Field(discriminator="kind"),
]


# ---- runs and steps


class StepVerification(ResponseModel):
    """R2 (TR-AGT-06): what the verifier read back after a write."""

    verified: bool
    checked: list[str]  # what was read back, in plain words
    external_ids: list[str]  # platform ids, e.g. a sent message's id


class AgentStep(ResponseModel):
    """One tool call, condition or report (TR-AGT-08), for the live steps and run history."""

    id: uuid.UUID
    ordinal: int  # 0-based, in the order they ran
    kind: StepKindName
    tool: str | None = None  # the registered tool's name
    # The step in plain words, never the model's reasoning: the tool's label ("Looking up your
    # latest post"), "Checking a condition" or "Writing the answer".
    label: str
    tier: RiskTierName | None = None
    status: StepStatusName
    args: dict[str, Any]  # the validated input
    summary: str | None = None  # the result in plain words; None until the step finishes
    result: dict[str, Any] | None = None  # the compact typed result
    decision: str | None = None  # R2 gateway: execute, approval or refuse:{reason}
    verification: StepVerification | None = None
    attempts: int
    latency_ms: int
    error: ErrorInfo | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentRun(ResponseModel):
    """A run in the history and a thread's exchanges (FR-AGT-01, FR-AGT-07); also the 202 answer
    of POST …/agent/runs."""

    id: uuid.UUID
    thread_id: uuid.UUID
    request: str
    source: AgentRunSourceName
    mode: AgentModeName
    status: AgentRunStatusName
    requested_by: Actor | None = None  # None for standing instructions (R3) or a deleted user
    answer: str | None = None  # markdown subset (module docstring); None until reported
    answer_refs: list[AnswerRef]
    action_cards: list[ActionCard]
    credits: int  # AI credits the run used: its model turns and any AI-calling tools
    error: ErrorInfo | None = None  # failed runs: e.g. "The AI didn't respond"
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentRunDetail(AgentRun):
    """GET …/agent/runs/{run_id}: the run with every step (TR-AGT-08)."""

    steps: list[AgentStep]
    plan: dict[str, Any] | None = None  # R2: agent/plan.Plan
    model: str | None = None
    prompt_version: str | None = None
    # Token counts stay in the table (TR-AGT-08) and ai_usage_events; like every other AI row
    # they aren't part of the API (SEC-02's schema check refuses "token" properties).


class AgentRunList(ResponseModel):
    """Newest first; ``next_cursor`` fetches older runs."""

    items: list[AgentRun]
    next_cursor: str | None = None


class AgentRunCreate(RequestModel):
    """POST …/agent/runs: a question in plain language (English, Hindi or Hinglish)."""

    request: str = Field(min_length=1, max_length=REQUEST_MAX_CHARS)
    # Continue one of the caller's threads; omitted: a new thread whose id is this run's id.
    thread_id: uuid.UUID | None = None


class AgentThread(ResponseModel):
    """An Ask panel thread: the caller's runs that share context."""

    id: uuid.UUID
    title: str  # the first request, cut to 80 characters
    run_count: int
    last_status: AgentRunStatusName  # the latest run's
    created_at: datetime  # the first run's
    last_run_at: datetime


class AgentThreadList(ResponseModel):
    """Most recent activity first; ``next_cursor`` fetches older threads."""

    items: list[AgentThread]
    next_cursor: str | None = None


# ---- events (TR-RT-03): ids, statuses and plain-word steps; never the request or answer.
# Events aren't in the OpenAPI document: their fields are AgentRun's and AgentStep's (same names
# and types), so the web types them as picks of those plus requested_by_user_id and step_count.


class AgentRunEvent(ResponseModel):
    """``agent.run.updated`` (status or step progress) and ``agent.completed`` (a final status):
    ``{run: AgentRunEvent}``."""

    id: uuid.UUID
    thread_id: uuid.UUID
    requested_by_user_id: uuid.UUID | None = None
    status: AgentRunStatusName
    step_count: int  # steps so far
    error: ErrorInfo | None = None


class AgentStepProgress(ResponseModel):
    """A step as the live list shows it."""

    id: uuid.UUID
    ordinal: int
    kind: StepKindName
    tool: str | None = None
    label: str
    status: StepStatusName
    summary: str | None = None
    latency_ms: int


class AgentStepEvent(ResponseModel):
    """``agent.step``: published when a step starts (running) and when it ends."""

    run_id: uuid.UUID
    requested_by_user_id: uuid.UUID | None = None
    step: AgentStepProgress


# ---- policy (FR-AGT-10; PUT is R2)


class AgentPermissions(ResponseModel):
    """Per-capability switches (models/agent.AgentCapability), all off until an owner or admin
    turns them on (R2). A key missing from the stored row reads as its default
    (``{**DEFAULT_PERMISSIONS, **row.permissions}``)."""

    send_replies: bool
    schedule_messages: bool
    schedule_posts: bool
    create_automations: bool
    delete_automations: bool
    bulk_actions: bool


class AgentLimits(ResponseModel):
    """Read like the permissions: ``{**DEFAULT_LIMITS, **row.limits}``."""

    bulk_max: int  # most items one write may touch
    writes_per_hour: int
    writes_per_day: int


class AgentPolicy(ResponseModel):
    """The workspace's agent mode, switches and limits. R1: always read_only, all off."""

    mode: AgentModeName
    permissions: AgentPermissions
    limits: AgentLimits
    updated_by: Actor | None = None
    updated_at: datetime


class AgentPermissionsUpdate(RequestModel):
    send_replies: bool
    schedule_messages: bool
    schedule_posts: bool
    create_automations: bool
    delete_automations: bool
    bulk_actions: bool


class AgentLimitsUpdate(RequestModel):
    bulk_max: int = Field(ge=1, le=200)
    writes_per_hour: int = Field(ge=1, le=500)
    writes_per_day: int = Field(ge=1, le=5000)


class AgentPolicyUpdate(RequestModel):
    """PUT …/agent/policy (R2): the whole policy. ``autonomous`` is refused until R3 (409)."""

    mode: AgentModeName
    permissions: AgentPermissionsUpdate
    limits: AgentLimitsUpdate


# ---- approvals (R2; FR-AGT-09)


class AgentApproval(ResponseModel):
    """A write waiting for a person: exactly what will happen (recipients, text, scope, count)."""

    id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID
    request: str  # the run's request, for context
    tool: str
    label: str  # the tool in plain words
    tier: RiskTierName
    summary: str  # what will happen, in plain words
    payload: dict[str, Any]  # {tool, args}: the exact call that will run
    status: ApprovalStatusName
    expires_at: datetime
    decided_by: Actor | None = None
    decided_at: datetime | None = None
    created_at: datetime


class AgentApprovalList(ResponseModel):
    """Soonest to expire first; ``next_cursor`` fetches more."""

    items: list[AgentApproval]
    next_cursor: str | None = None


class ApprovalApprove(RequestModel):
    """Approve as shown, or with edited arguments (Edit): the edit replaces the payload and is
    checked by the gateway again (TR-AGT-04)."""

    args: dict[str, Any] | None = None
