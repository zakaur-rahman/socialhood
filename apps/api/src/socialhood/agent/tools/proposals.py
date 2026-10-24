"""Proposal tools (GR-36; FR-AGT-02, FR-AGT-03; agent-architecture.html §4, §5): the agent drafts a
flow or a segment, a member approves it, and only then is it saved. Owners and admins, as in the
UI (``min_role`` admin).

- propose_flow: a new automation with a flow (trigger, keywords, steps, branches), or a new flow
  for an existing automation. Approving saves a DRAFT automation; it is never switched on.
- propose_segment: a saved contact segment from a description (tags, platform, email, lead stage,
  activity, fields), with the number of people it matches.
- propose_broadcast: the slot for broadcast drafts (GR-23). Registered for R2 so the model never
  sees it; ``agent.actions.UNAVAILABLE`` holds the plain reason. When GR-23 lands, add its action
  to agent/actions.py, switch this to R1 with a real handler, and drop the entry.

These are draft-tier tools: they change nothing in the workspace. Each stores a pending approval
through the action gateway (services/agent_actions.propose) and returns a card that shows what
will happen; the member decides in the Ask panel or the "Waiting for you" list. The model writes
step texts and filters in plain words; this module resolves names (tags, the account) to ids,
builds the typed flow or filter and lets the gateway validate it with the screens' own checks, so
the model never writes an id or a rule of its own.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent import actions
from socialhood.agent.registry import DraftResult, Release, ToolContext, ToolSpec, registry
from socialhood.agent.tools.automations import NO_KEYWORD_TRIGGERS
from socialhood.agent.tools.common import clip, find_account, tool
from socialhood.errors import ApiError, FieldError
from socialhood.models.agent import RiskTier
from socialhood.models.connections import AccountStatus
from socialhood.models.identity import Role
from socialhood.repositories import social_accounts
from socialhood.schemas.agent import FlowProposalAction, SegmentProposalAction
from socialhood.schemas.contacts import ConsentChannelName, ContactFilterSpec, LeadStageName
from socialhood.schemas.flows import (
    Action,
    ActionStep,
    AddTag,
    AiReplyStep,
    AskStep,
    BranchRule,
    BranchStep,
    Condition,
    ContactCondition,
    DelayStep,
    EndStep,
    FieldCondition,
    FlowButton,
    FlowDefinition,
    HandOff,
    LeadStageCondition,
    NotifyTeam,
    PlatformCondition,
    QuickReply,
    RemoveTag,
    SendStep,
    SetField,
    Step,
    TagCondition,
)
from socialhood.services import agent_actions, contacts

MAX_PROPOSED_STEPS = 30
FlowTrigger = Literal[
    "dm_keyword",
    "comment_keyword",
    "comment_any",
    "story_reply",
    "story_mention",
    "first_message",
]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- the flow the model describes


class ProposedQuickReply(_Input):
    title: str = Field(min_length=1, max_length=20)
    goto: str | None = Field(
        default=None, max_length=40, description="Step id this option leads to; blank: next step."
    )


class ProposedButton(_Input):
    title: str = Field(min_length=1, max_length=20)
    url: str = Field(max_length=2000, description="A https link.")


class ProposedCondition(_Input):
    kind: Literal["tag", "field", "has_email", "has_phone", "platform", "lead_stage"]
    tag: str | None = Field(default=None, max_length=40, description="Tag name (kind tag).")
    has: bool = Field(default=True, description="tag: has it; has_email/has_phone: known.")
    key: str | None = Field(default=None, max_length=40, description="Custom field key.")
    op: Literal["set", "unset", "equals"] = "set"
    value: str | None = Field(default=None, max_length=200)
    platform: Literal["instagram", "whatsapp"] | None = None
    stages: list[LeadStageName] = Field(default_factory=list, max_length=5)


class ProposedRule(_Input):
    when: ProposedCondition
    goto: str = Field(max_length=40, description="Step id to go to when it holds.")


class ProposedStep(_Input):
    """One step. Steps run in the order given; a step goes on to the next one unless ``goto`` (or a
    branch rule, or a quick reply's goto) says otherwise. Give a step an ``id`` only when another
    step points at it."""

    id: str | None = Field(default=None, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    type: Literal["send", "ask", "action", "delay", "branch", "ai_reply", "end"]
    text: str | None = Field(default=None, max_length=1000, description="send/ask: the message.")
    buttons: list[ProposedButton] = Field(default_factory=list, max_length=3)
    quick_replies: list[ProposedQuickReply] = Field(default_factory=list, max_length=6)
    expect: Literal["text", "email", "phone"] = Field(default="text", description="ask only.")
    field_key: str | None = Field(default=None, max_length=40, description="ask: custom field.")
    action: Literal["add_tag", "remove_tag", "set_field", "notify_team", "hand_off"] | None = None
    tag: str | None = Field(default=None, max_length=40, description="add_tag/remove_tag name.")
    value: str | None = Field(default=None, max_length=200, description="set_field value.")
    note: str | None = Field(default=None, max_length=200, description="notify_team note.")
    seconds: int | None = Field(default=None, ge=1, le=23 * 3600, description="delay only.")
    instructions: str | None = Field(default=None, max_length=2000, description="ai_reply only.")
    rules: list[ProposedRule] = Field(default_factory=list, max_length=10, description="branch.")
    otherwise: str | None = Field(default=None, max_length=40, description="branch: else go to.")
    goto: str | None = Field(default=None, max_length=40, description="Overrides the next step.")


def _invalid(field: str, message: str) -> ApiError:
    return ApiError("validation_error", message, errors=[FieldError(field, message)])


def _tag_id(names: dict[str, uuid.UUID], name: str | None, where: str) -> uuid.UUID:
    wanted = (name or "").strip().casefold()
    if wanted not in names:
        have = ", ".join(sorted(names)) or "none yet"
        raise _invalid(
            where,
            f"There's no tag called “{name or ''}”. Tags in this workspace: {have}. "
            "Use one of those, or ask the member to create the tag first.",
        )
    return names[wanted]


def _condition(c: ProposedCondition, names: dict[str, uuid.UUID], where: str) -> Condition:
    match c.kind:
        case "tag":
            return TagCondition(tag_id=_tag_id(names, c.tag, where), has=c.has)
        case "field":
            if not c.key:
                raise _invalid(where, "A field condition needs the field key.")
            return FieldCondition(key=c.key, op=c.op, value=c.value)
        case "has_email" | "has_phone":
            return ContactCondition(has="email" if c.kind == "has_email" else "phone", known=c.has)
        case "platform":
            if c.platform is None:
                raise _invalid(where, "A platform condition needs instagram or whatsapp.")
            return PlatformCondition(platform=c.platform)
        case _:
            if not c.stages:
                raise _invalid(where, "A lead stage condition needs at least one stage.")
            return LeadStageCondition(stages=c.stages)


def _action(s: ProposedStep, names: dict[str, uuid.UUID], where: str) -> Action:
    match s.action:
        case "add_tag":
            return AddTag(tag_id=_tag_id(names, s.tag, where))
        case "remove_tag":
            return RemoveTag(tag_id=_tag_id(names, s.tag, where))
        case "set_field":
            if not s.field_key or s.value is None:
                raise _invalid(where, "set_field needs field_key and value.")
            return SetField(key=s.field_key, value=s.value)
        case "notify_team":
            return NotifyTeam(note=s.note or "")
        case "hand_off":
            return HandOff()
        case _:
            raise _invalid(where, "An action step needs an action.")


def build_flow(steps: list[ProposedStep], tags: dict[str, uuid.UUID]) -> FlowDefinition:
    """The typed flow for the steps in order (module docstring). Raises ``validation_error`` that
    names the step and what to fix, so the model can correct it and call again. Nothing about the
    graph's soundness is checked here: ``flows.graph`` does that, in the gateway."""
    ids = [s.id or f"s{i + 1}" for i, s in enumerate(steps)]
    if len(set(ids)) != len(ids):
        raise _invalid("steps", "Two steps have the same id. Give each step its own.")

    def following(i: int) -> str | None:
        return ids[i + 1] if i + 1 < len(ids) else None

    built: list[Step] = []
    for i, s in enumerate(steps):
        where = f"steps.{i}"
        sid = ids[i]
        nxt = s.goto or following(i)
        match s.type:
            case "send":
                if not s.text:
                    raise _invalid(f"{where}.text", "A send step needs the message text.")
                built.append(
                    SendStep(
                        id=sid,
                        text=s.text,
                        buttons=[FlowButton(title=b.title, url=b.url) for b in s.buttons],
                        quick_replies=[
                            QuickReply(title=q.title, next=q.goto or following(i))
                            for q in s.quick_replies
                        ],
                        on_text=following(i) if s.quick_replies else None,
                        next=nxt,
                    )
                )
            case "ask":
                if not s.text:
                    raise _invalid(f"{where}.text", "An ask step needs the question.")
                built.append(
                    AskStep(
                        id=sid,
                        text=s.text,
                        expect=s.expect,
                        field_key=s.field_key,
                        next=nxt,
                        on_skip=nxt,
                    )
                )
            case "action":
                built.append(ActionStep(id=sid, action=_action(s, tags, where), next=nxt))
            case "delay":
                if s.seconds is None:
                    raise _invalid(f"{where}.seconds", "A delay step needs seconds.")
                built.append(DelayStep(id=sid, seconds=s.seconds, next=nxt))
            case "branch":
                if not s.rules:
                    raise _invalid(f"{where}.rules", "A branch step needs at least one rule.")
                built.append(
                    BranchStep(
                        id=sid,
                        rules=[
                            BranchRule(
                                when=_condition(r.when, tags, f"{where}.rules.{j}"), next=r.goto
                            )
                            for j, r in enumerate(s.rules)
                        ],
                        otherwise=s.otherwise or following(i),
                    )
                )
            case "ai_reply":
                built.append(AiReplyStep(id=sid, instructions=s.instructions or ""))
            case _:
                built.append(EndStep(id=sid))
    return FlowDefinition(start=ids[0], steps=built)


# ---------------------------------------------------------------- shared


class ProposalResult(DraftResult):
    """A proposal: nothing is saved until a member approves it."""

    approval_id: uuid.UUID
    status: Literal["pending"] = "pending"
    title: str
    lines: list[str]


async def _tags(ctx: ToolContext) -> dict[str, uuid.UUID]:
    listed = await contacts.list_tags(ctx.session)
    return {t.name.strip().casefold(): t.id for t in listed.items}


def _clean_keywords(typed: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for word in typed:
        clean = " ".join(word.split())[:100]
        if clean and clean.casefold() not in seen:
            seen[clean.casefold()] = clean
    return list(seen.values())


# ---------------------------------------------------------------- propose_flow


class ProposeFlowInput(_Input):
    request: str = Field(
        min_length=1, max_length=500, description="What the member asked for, in a few words."
    )
    name: str | None = Field(default=None, max_length=80, description="Automation name.")
    automation_id: uuid.UUID | None = Field(
        default=None,
        description="Change this automation's flow (from list_automations) instead of a new one.",
    )
    account: str | None = Field(default=None, max_length=100, description="@handle or id.")
    trigger: FlowTrigger | None = Field(default=None, description="New automations only.")
    keywords: list[str] = Field(default_factory=list, max_length=actions.MAX_FLOW_KEYWORDS)
    public_reply_texts: list[str] = Field(
        default_factory=list, max_length=5, description="Comment triggers: public reply options."
    )
    steps: list[ProposedStep] = Field(min_length=1, max_length=MAX_PROPOSED_STEPS)


class ProposeFlowResult(ProposalResult):
    step_count: int
    missing_for_activation: list[str]


@tool(
    name=actions.FLOW_TOOL,
    label="Drafting an automation for your approval",
    description=(
        "Propose a new automation with its flow (trigger, keywords, steps, branches), or a new "
        "flow for an existing one (automation_id). Steps run in order: send, ask, action, delay, "
        "branch, ai_reply, end. Name tags, never ids. Nothing is saved until the member approves; "
        "an approved flow is a draft, not switched on. Use it to create or change an automation; "
        "prepare_automation only to open the editor for the member to fill in."
    ),
    input_model=ProposeFlowInput,
    result_model=ProposeFlowResult,
    tier=RiskTier.DRAFT,
    min_role=Role.ADMIN,
)
async def propose_flow(ctx: ToolContext, args: ProposeFlowInput) -> ProposeFlowResult:
    acct = await find_account(ctx, args.account)
    if acct is None and args.automation_id is None:
        live = [
            a
            for a in await social_accounts.list_all(ctx.session)
            if a.platform == "instagram" and a.status != AccountStatus.DISCONNECTED
        ]
        acct = live[0] if len(live) == 1 else None
    flow = build_flow(args.steps, await _tags(ctx))
    keywords = _clean_keywords(args.keywords)
    name = args.name or clip(args.request, 80) or "New automation"
    proposed = actions.FlowActionArgs(
        automation_id=args.automation_id,
        name=name,
        social_account_id=acct.id if acct else None,
        trigger=None if args.automation_id else args.trigger,
        keywords=[] if args.automation_id else keywords,
        public_reply_texts=[] if args.automation_id else list(args.public_reply_texts),
        definition=flow,
    )
    approval, summary = await agent_actions.propose(ctx, actions.FLOW, proposed)
    missing = []
    if args.automation_id is None:
        if acct is None:
            missing.append("an account")
        if args.trigger is None:
            missing.append("a trigger")
        elif args.trigger not in NO_KEYWORD_TRIGGERS and not keywords:
            missing.append("keywords")
    caveats = []
    if missing:
        caveats.append("Before it can be switched on it needs: " + ", ".join(missing) + ".")
    return ProposeFlowResult(
        summary=clip(f"Proposed “{name}” for approval: {len(flow.steps)} steps", 300) or "Proposed",
        caveats=caveats,
        approval_id=approval.id,
        title=summary.title,
        lines=summary.lines,
        step_count=len(flow.steps),
        missing_for_activation=missing,
        action_card=FlowProposalAction(
            kind="flow_proposal",
            label="Review and approve",
            route="automations",
            note="Nothing is saved until you approve it.",
            approval_id=approval.id,
            title=summary.title,
            lines=summary.lines,
            automation_id=args.automation_id,
            step_count=len(flow.steps),
        ),
    )


# ---------------------------------------------------------------- propose_segment


class ProposeSegmentInput(_Input):
    name: str = Field(min_length=1, max_length=60, description="Segment name.")
    tags: list[str] = Field(
        default_factory=list, max_length=10, description="Tag names; contacts need all of them."
    )
    platform: Literal["instagram", "whatsapp"] | None = None
    account: str | None = Field(default=None, max_length=100, description="@handle or id.")
    has_email: bool | None = Field(default=None, description="True: gave an email.")
    has_phone: bool | None = Field(default=None, description="True: gave a phone number.")
    marketing_consent: ConsentChannelName | None = None
    stages: list[LeadStageName] = Field(default_factory=list, max_length=5)
    min_lead_score: int | None = Field(default=None, ge=0, le=100)
    active_within_days: int | None = Field(default=None, ge=1, le=3650)
    inactive_for_days: int | None = Field(default=None, ge=1, le=3650)
    fields: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Custom fields as key:value, or key:* for any value (city:pune).",
    )
    text: str | None = Field(default=None, max_length=100, description="Name, email or phone.")


class ProposeSegmentResult(ProposalResult):
    match_count: int


@tool(
    name=actions.SEGMENT_TOOL,
    label="Drafting a segment for your approval",
    description=(
        "Propose a saved contact segment from a description: tag names, platform, email or phone "
        "given, marketing consent, lead stages, activity (active in the last N days, or none for N "
        "days) and custom fields. The result says how many people match now. Nothing is saved "
        "until the member approves. Use it when asked to create or save a segment or list; to "
        "only count or look up people, use list_contacts."
    ),
    input_model=ProposeSegmentInput,
    result_model=ProposeSegmentResult,
    tier=RiskTier.DRAFT,
    min_role=Role.ADMIN,
)
async def propose_segment(ctx: ToolContext, args: ProposeSegmentInput) -> ProposeSegmentResult:
    names = await _tags(ctx)
    tag_ids = [_tag_id(names, tag, "tags") for tag in args.tags]
    acct = await find_account(ctx, args.account)
    try:
        spec = ContactFilterSpec(
            q=args.text,
            tag_ids=list(dict.fromkeys(tag_ids)),
            platform=args.platform,
            account_id=acct.id if acct else None,
            has_email=args.has_email,
            has_phone=args.has_phone,
            marketing_consent=args.marketing_consent,
            min_lead_score=args.min_lead_score,
            stages=args.stages,
            active_within_days=args.active_within_days,
            inactive_for_days=args.inactive_for_days,
            fields=args.fields,
        )
    except ValueError as error:
        raise _invalid("fields", "Write each field as key:value, like city:pune.") from error
    proposed = actions.SegmentActionArgs(name=args.name.strip(), filter=spec)
    approval, summary = await agent_actions.propose(ctx, actions.SEGMENT, proposed)
    count = summary.match_count or 0
    people = "1 person" if count == 1 else f"{count} people"
    return ProposeSegmentResult(
        summary=clip(f"Proposed the segment “{proposed.name}” for approval: {people}", 300)
        or "Proposed",
        approval_id=approval.id,
        title=summary.title,
        lines=summary.lines,
        match_count=count,
        action_card=SegmentProposalAction(
            kind="segment_proposal",
            label="Review and approve",
            route="contacts",
            note="Nothing is saved until you approve it.",
            approval_id=approval.id,
            title=summary.title,
            lines=summary.lines,
            match_count=count,
        ),
    )


# ---------------------------------------------------------------- propose_broadcast (GR-23)


class ProposeBroadcastInput(_Input):
    request: str = Field(min_length=1, max_length=500)


class ProposeBroadcastResult(ProposalResult):
    pass


async def propose_broadcast(
    ctx: ToolContext, args: ProposeBroadcastInput
) -> ProposeBroadcastResult:
    raise ApiError("conflict", actions.UNAVAILABLE[actions.BROADCAST_TOOL])


registry.register(
    ToolSpec(
        name=actions.BROADCAST_TOOL,
        label="Drafting a broadcast for your approval",
        description="Propose a broadcast draft. Not available yet: broadcasts arrive with GR-23.",
        input_model=ProposeBroadcastInput,
        result_model=ProposeBroadcastResult,
        tier=RiskTier.DRAFT,
        release=Release.R2,  # not offered to the model until broadcasts exist
        min_role=Role.ADMIN,
        handler=propose_broadcast,
    )
)
