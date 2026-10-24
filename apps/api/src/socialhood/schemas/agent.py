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

- Visuals (GR-38) come from the run's succeeded tool steps: a tool that has chartable data builds
  one from the same service numbers it returns (agent/visuals.py), stores it in its result, and
  ``visuals`` lists them in step order, at most MAX_VISUALS. The model never writes a figure, a
  label or a layout in a visual, and doesn't see them. ``kind`` is a closed set the web draws
  with its own components. Text that came from a customer (a caption) is text: render it as text.
  Visuals are empty unless the ``agent_visuals_enabled`` setting is on.

Runs belong to the member who asked: a member sees their own runs and threads, owners and admins
see every run (FR-AGT-07). The real-time stream is shared by the workspace's members, so agent
events carry no request or answer text; the requester's panel fetches the run on
``agent.completed`` (TR-RT-03 otherwise).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter

from socialhood.models.agent import REQUEST_MAX_CHARS
from socialhood.schemas.analytics import ChangeDirection
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
ActionKind = Literal[
    "schedule_message",
    "reply_to_comment",
    "automation_draft",
    "flow_proposal",  # GR-36
    "segment_proposal",  # GR-36
]


# ---- answers


class AnswerRef(ResponseModel):
    """A record an answer used (FR-AGT-01): ``[n]`` in the answer is item n of answer_refs."""

    kind: AnswerRefKind
    id: uuid.UUID
    label: str  # short, e.g. "Reel of 26 Sep", "Priya Nair", "“Too expensive for me”"
    # Where the record is shown: the post of a comment, the conversation of a scheduled
    # message; None for records with a screen of their own.
    parent_id: uuid.UUID | None = None


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


class _ProposalCardBase(_ActionCardBase):
    """GR-36: a write the agent proposed. Nothing is saved until a member approves it; the card
    shows what will happen in plain words and the web reads the approval (status, result, who
    may decide) from …/agent/approvals. ``route`` opens the list the result will appear in."""

    approval_id: uuid.UUID
    title: str = Field(max_length=120)  # e.g. "New automation: Send the price list"
    lines: list[str] = Field(max_length=20)  # what will happen, one line each (trigger, steps)


class FlowProposalAction(_ProposalCardBase):
    kind: Literal["flow_proposal"]
    automation_id: uuid.UUID | None = None  # set when it changes an existing automation's flow
    step_count: int


class SegmentProposalAction(_ProposalCardBase):
    kind: Literal["segment_proposal"]
    match_count: int  # contacts that match the filter when it was proposed


# FR-AGT-03: a prepared action the member completes in the existing screen (the first three), or
# a proposed write that waits for the member's approval (GR-36, the last two).
ActionCard = Annotated[
    ScheduleMessageAction
    | CommentReplyAction
    | AutomationDraftAction
    | FlowProposalAction
    | SegmentProposalAction,
    Field(discriminator="kind"),
]


# ---- visuals (GR-38)

VISUAL_VERSION = 1
MAX_VISUALS = 3  # per run
MAX_VISUAL_BYTES = 8 * 1024  # serialised, per visual (test-enforced)
MAX_METRICS = 8
MAX_RANKED = 10
MAX_TOPICS = 6
MetricFormat = Literal["count", "percent"]
# Account metrics (schemas/analytics.AccountMetricName) and post metrics (MetricName).
VisualMetricKey = Literal[
    "reach",
    "views",
    "accounts_engaged",
    "interactions",
    "followers",
    "follows",
    "unfollows",
    "profile_link_taps",
    "comments",
    "messages_received",
    "likes",
    "shares",
    "saves",
    "engagement_rate",
]
Tone = Literal["good", "bad", "neutral"]


class VisualPeriod(ResponseModel):
    """Calendar days in the workspace's zone, both included, with the label the answer uses."""

    start: date
    end: date
    label: str = Field(max_length=60)  # e.g. "1-22 Oct"
    days: int = Field(ge=1, le=366)


class MetricDelta(ResponseModel):
    """One card of a comparison. Every figure and ``change_pct`` come from the analytics
    service; ``tone`` is the metric's rule (more unfollows is bad), not the model's."""

    key: VisualMetricKey
    label: str = Field(max_length=60)  # "Reach, summed over the days"
    format: MetricFormat
    current: float | None = None  # None: not available, see ``unavailable``
    previous: float | None = None
    change_pct: float | None = None  # None against 0 or an unknown side, or periods that differ
    direction: ChangeDirection | None = None
    tone: Tone
    current_coverage: str | None = Field(default=None, max_length=40)  # "21 of 22 days" if gaps
    previous_coverage: str | None = Field(default=None, max_length=40)
    unavailable: str | None = Field(default=None, max_length=200)  # the reason, in plain words


# ``kind`` has no default so that it is required in the OpenAPI document (the web narrows on it).
class MetricComparisonVisual(ResponseModel):
    """The current period against another, a card per metric (compare_periods)."""

    kind: Literal["metric_comparison"]
    version: Literal[1] = 1
    title: str = Field(max_length=120)
    current: VisualPeriod
    previous: VisualPeriod
    comparable: bool  # False: the periods differ in length and no change is shown
    note: str | None = Field(default=None, max_length=240)  # how the periods were matched
    account_label: str | None = Field(default=None, max_length=60)  # "@maple.bakery"
    metrics: list[MetricDelta] = Field(max_length=MAX_METRICS)


class RankedPostRow(ResponseModel):
    """One post of a ranking. ``label`` is server copy; ``caption`` is the customer's own text:
    render it as text."""

    post_id: uuid.UUID
    label: str = Field(max_length=60)  # "Reel of 26 Sep"
    format: str = Field(max_length=20)  # feed, reel or story
    caption: str | None = Field(default=None, max_length=100)
    thumbnail_url: str | None = Field(default=None, max_length=400)  # https only
    value: float


class RankedPostsVisual(ResponseModel):
    """Posts ranked by one metric, best first (top_posts)."""

    kind: Literal["ranked_posts"]
    version: Literal[1] = 1
    title: str = Field(max_length=120)
    metric_key: VisualMetricKey
    metric_label: str = Field(max_length=40)
    format: MetricFormat
    period: VisualPeriod | None = None
    age_label: str | None = Field(default=None, max_length=60)  # the age the figures are at
    considered: int = Field(ge=0)  # posts that had the metric: the sample size
    items: list[RankedPostRow] = Field(max_length=MAX_RANKED)


class VisualTopic(ResponseModel):
    label: str = Field(max_length=40)  # customer-derived: render as text
    count: int = Field(ge=0)


class SentimentSummaryVisual(ResponseModel):
    """Comment sentiment as one split, with the top topics when the run found them
    (sentiment_distribution, comment_topics)."""

    kind: Literal["sentiment_summary"]
    version: Literal[1] = 1
    title: str = Field(max_length=120)
    scope: str = Field(max_length=120)  # "comments made 1-30 Sep 2026"
    period: VisualPeriod | None = None  # None for one post
    total: int = Field(ge=0)  # comments in scope
    positive: int = Field(ge=0)
    neutral: int = Field(ge=0)
    negative: int = Field(ge=0)
    spam: int = Field(ge=0)
    not_analysed: int = Field(ge=0)
    topics: list[VisualTopic] = Field(max_length=MAX_TOPICS)


# GR-38 (docs/architecture/generative-ui/05): built by agent/visuals.py from service data.
Visual = Annotated[
    MetricComparisonVisual | RankedPostsVisual | SentimentSummaryVisual,
    Field(discriminator="kind"),
]
VISUAL_ADAPTER: TypeAdapter[Visual] = TypeAdapter(Visual)


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
    visuals: list[Visual] = Field(
        max_length=MAX_VISUALS
    )  # GR-38: at most MAX_VISUALS, in step order; empty with the flag off
    credits: int  # AI credits the run used: its model turns and any AI-calling tools
    error: ErrorInfo | None = None  # failed runs: e.g. "The AI didn't respond"
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentRunDetail(AgentRun):
    """GET …/agent/runs/{run_id}: the run with every step (TR-AGT-08)."""

    steps: list[AgentStep]
    approvals: list[AgentApproval]  # GR-36: the writes it proposed, with their audit events
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


ApprovalListStatus = Literal["pending", "approved", "rejected", "expired", "superseded", "all"]
ApprovalEventName = Literal["proposed", "approved", "rejected", "expired", "executed", "failed"]
ApprovalResourceKind = Literal["automation", "segment"]


class ApprovalOutcome(ResponseModel):
    """What approving did (GR-36). ``ok`` false: the service refused it, nothing was saved, and
    the approval is still pending so the member can edit it or reject it."""

    ok: bool
    summary: str  # e.g. "Saved the draft automation “Send the price list”."
    resource_kind: ApprovalResourceKind | None = None
    resource_id: uuid.UUID | None = None
    route: str | None = None  # the screen with the result, relative to /w/{slug}/
    error_code: str | None = None


class ApprovalEvent(ResponseModel):
    """One line of an approval's audit trail (GR-36): who did what, and when."""

    id: uuid.UUID
    event: ApprovalEventName
    actor: Actor | None = None  # None: the agent's own proposal for a deleted user, or an expiry
    detail: dict[str, Any]
    created_at: datetime


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
    payload: dict[str, Any]  # {tool, args, preview}: the exact call that will run
    # GR-36: what it said when it was shown, one line each, and the figures beside it.
    lines: list[str] = Field(default_factory=list)
    match_count: int | None = None  # segments: people the filter matched when proposed or approved
    step_count: int | None = None  # flows
    status: ApprovalStatusName
    expires_at: datetime
    # GR-36: whether the caller's role may decide it (Approve is disabled when false).
    can_decide: bool = False
    requested_by: Actor | None = None
    decided_by: Actor | None = None
    decided_at: datetime | None = None
    outcome: ApprovalOutcome | None = None
    events: list[ApprovalEvent] = Field(default_factory=list)
    created_at: datetime


class AgentApprovalList(ResponseModel):
    """Soonest to expire first; ``next_cursor`` fetches more."""

    items: list[AgentApproval]
    next_cursor: str | None = None


class ApprovalApprove(RequestModel):
    """Approve as shown, or with edited arguments (Edit): the edit replaces the payload and is
    checked by the gateway again (TR-AGT-04)."""

    args: dict[str, Any] | None = None
