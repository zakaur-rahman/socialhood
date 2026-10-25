"""The writes the agent can propose (GR-36; agent-architecture.html §4, §8): what each one is,
how it is checked, how it reads to a person, and how it runs.

The action gateway (services/agent_actions.py) is the only caller. A proposal tool turns the
model's request into one of the argument models below (ids resolved, nothing left to guess), the
gateway stores it as a pending approval, and only a member's approval runs ``execute`` here. Every
``execute`` calls the same service functions the screens call (``definitions.create`` and
``flow_store.save`` for a flow, ``contact_segments.create_segment`` for a segment), so the
validation, plan limits and tenancy are the UI's, never a second write path.

Rules:
- ``check`` raises ``ApiError`` with the UI's own messages and writes nothing. It runs when the
  agent proposes and again when a member approves (the workspace may have changed in between),
  and again after an edit.
- ``summarize`` is what the approval card says, in plain words, from the arguments only.
- A flow is only ever saved as a DRAFT automation: approving never activates it. An existing
  automation keeps its status, and if it is live the card says so.
- ``min_role`` is the least role that may do this by hand (both screens are for owners and
  admins). GR-19's ``Permission`` plugs in at ``required_role`` below: replace its body with the
  matrix lookup and keep the signature.
- Broadcast drafts (GR-23) don't exist yet: ``UNAVAILABLE`` says so in plain words and the
  gateway refuses them with that reason.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.agent.tools.automations import TRIGGER_WORDS
from socialhood.billing.plans import current_plan
from socialhood.errors import ApiError, FieldError
from socialhood.models.automations import AutomationStatus
from socialhood.models.contacts import Tag
from socialhood.models.identity import Role
from socialhood.repositories import social_accounts, workspaces
from socialhood.schemas.assignment import AssignmentOverview
from socialhood.schemas.automations import AutomationCreate, AutomationDefinition, TriggerName
from socialhood.schemas.contacts import ContactFilterSpec, SegmentCreate
from socialhood.schemas.flows import ActionStep, Assign, FlowDefinition
from socialhood.services import assignment, contact_segments, contacts
from socialhood.services.automations import definitions, flow_store, flows
from socialhood.services.automations.validation import COMMENT_TRIGGERS

FLOW_TOOL = "propose_flow"
SEGMENT_TOOL = "propose_segment"
BROADCAST_TOOL = "propose_broadcast"
MAX_FLOW_KEYWORDS = 20
APPROVAL_SUMMARY_CHARS = 300

# Writes that can't be proposed yet, and why, in words for the member (GR-23 builds broadcasts).
UNAVAILABLE: dict[str, str] = {
    BROADCAST_TOOL: (
        "Broadcasts aren't available yet, so there's nothing to draft. "
        "You can send a single reply from the inbox."
    ),
}


@dataclass(kw_only=True)
class ActionEnv:
    """Who the write is for and where: the approver's session, in the workspace's scope."""

    session: AsyncSession
    workspace_id: uuid.UUID
    user_id: uuid.UUID | None
    role: Role
    now: datetime


@dataclass(frozen=True)
class Summary:
    """What the approval card says (and what the approval's ``summary`` column holds)."""

    title: str
    lines: list[str] = field(default_factory=list)
    match_count: int | None = None  # segments: contacts the filter matches now
    step_count: int | None = None  # flows


@dataclass(frozen=True)
class Outcome:
    summary: str
    resource_kind: Literal["automation", "segment"]
    resource_id: uuid.UUID
    route: str


class FlowActionArgs(BaseModel):
    """A flow for a new draft automation, or a new version of an existing automation's flow."""

    model_config = ConfigDict(extra="forbid")

    automation_id: uuid.UUID | None = None  # set: change this automation's flow
    name: str = Field(min_length=1, max_length=80)
    social_account_id: uuid.UUID | None = None
    trigger: TriggerName | None = None  # new automations only
    keywords: list[str] = Field(default_factory=list, max_length=MAX_FLOW_KEYWORDS)
    public_reply_texts: list[str] = Field(default_factory=list, max_length=5)
    definition: FlowDefinition


class SegmentActionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=60)
    filter: ContactFilterSpec


type Check[A: BaseModel] = Callable[[ActionEnv, A], Awaitable[None]]
type Describe[A: BaseModel] = Callable[[ActionEnv, A], Awaitable[Summary]]
type Execute[A: BaseModel] = Callable[[ActionEnv, A], Awaitable[Outcome]]


@dataclass(frozen=True, kw_only=True)
class ActionSpec[A: BaseModel]:
    tool: str  # the proposal tool's name; payload["tool"]
    key: Literal["flow", "segment"]
    noun: str  # for messages: "automation", "segment"
    min_role: Role
    args_model: type[A]
    check: Check[A]
    summarize: Describe[A]
    execute: Execute[A]


def required_role(spec: ActionSpec[Any]) -> Role:
    """The least role that may approve ``spec``. GR-19: replace with the permission matrix
    (automations.manage for a flow, contacts.manage for a segment); callers don't change."""
    return spec.min_role


# ---------------------------------------------------------------- flows


def _validation(errors: list[FieldError]) -> ApiError:
    return ApiError("validation_error", errors=errors)


def flow_lines(
    definition: FlowDefinition, member_names: dict[uuid.UUID, str] | None = None
) -> list[str]:
    """One line per step a run can reach, without the step ids. An assign step names the member."""
    return [
        line.partition(": ")[2] or line for line in flows.describe(definition, member_names or {})
    ]


def assign_notes(definition: FlowDefinition, overview: AssignmentOverview) -> list[str]:
    """What to switch on for the assign steps in the flow to work, in plain words. Round-robin in a
    flow works whatever the workspace's own setting says (C-117), but it hands the conversation to
    an *available* member: with none available the step is skipped."""
    if not any(
        isinstance(step, ActionStep)
        and isinstance(step.action, Assign)
        and step.action.mode == "round_robin"
        for step in definition.steps
    ):
        return []
    notes: list[str] = []
    if not any(member.available for member in overview.members):
        notes.append(
            "Nobody is available for assignment now, so the assign step would be skipped. "
            "Turn on availability for a member under Members."
        )
    if not overview.round_robin:
        notes.append(
            "New conversations are not handed out in turn yet (Settings, Members). "
            "This step still assigns in turn when it runs."
        )
    return notes


async def check_flow(env: ActionEnv, args: FlowActionArgs) -> None:
    session = env.session
    if args.automation_id is not None:
        await definitions.get_or_404(session, args.automation_id)
    if args.social_account_id is not None and (
        await social_accounts.get(session, args.social_account_id) is None
    ):
        raise ApiError("not_found", "That account wasn't found.")
    try:
        flows.graph(args.definition)
    except flows.FlowError as error:
        raise _validation(error.errors) from error
    flow_store.check_step_cap(args.definition, await current_plan(session))
    if errors := await flow_store.reference_errors(session, args.definition):
        raise _validation(errors)


async def summarize_flow(env: ActionEnv, args: FlowActionArgs) -> Summary:
    steps = len(args.definition.steps)
    lines: list[str] = []
    if args.automation_id is not None:
        automation = await definitions.get_or_404(env.session, args.automation_id)
        title = f"Change the flow of “{automation.name}”"
        if automation.status == AutomationStatus.ACTIVE:
            lines.append("This automation is live: the new flow applies to new conversations.")
        else:
            lines.append(f"The automation stays {automation.status}.")
    else:
        title = f"New automation: {args.name}"
        lines.append(_trigger_line(args))
        lines.append("It's saved as a draft. Nothing is switched on.")
    roster = await assignment.roster(env.session)
    names = {user_id: label for user_id, label, _ in roster.members}
    lines += [f"{i}. {line}" for i, line in enumerate(flow_lines(args.definition, names), start=1)]
    overview = await assignment.overview(env.session, env.user_id or uuid.UUID(int=0))
    lines += assign_notes(args.definition, overview)
    return Summary(title=title, lines=lines, step_count=steps)


def _trigger_line(args: FlowActionArgs) -> str:
    what = TRIGGER_WORDS.get(args.trigger or "", "a trigger you choose in the editor")
    if args.keywords:
        quoted = ", ".join(f"“{k}”" for k in args.keywords)
        return f"Starts on {what}: {quoted}."
    return f"Starts on {what}."


async def execute_flow(env: ActionEnv, args: FlowActionArgs) -> Outcome:
    session = env.session
    workspace = await workspaces.get(session, env.workspace_id)
    disclosure = workspace.automation_disclosure if workspace else None
    plan = await current_plan(session)
    user_id = env.user_id
    if user_id is None:  # an approval is always a member's act
        raise ApiError("forbidden")
    if args.automation_id is None:
        automation = await definitions.create(
            session,
            AutomationCreate(name=args.name, social_account_id=args.social_account_id),
            user_id=user_id,
            now=env.now,
        )
        await definitions.update(
            session,
            automation.id,
            AutomationDefinition(
                name=args.name,
                social_account_id=automation.social_account_id,
                trigger=args.trigger,
                keywords=list(args.keywords),
                match_mode=automation.match_mode,
                public_reply_texts=(
                    list(args.public_reply_texts) if args.trigger in COMMENT_TRIGGERS else []
                ),
                cooldown_hours=automation.cooldown_hours,
                surge_order=automation.surge_order,
                comment_surface=automation.comment_surface,
                confirm_first=automation.confirm_first,
                opening_text=automation.opening_text,
                opening_button=automation.opening_button,
                follow_nudge=automation.follow_nudge,
                follow_nudge_text=automation.follow_nudge_text,
            ),
            disclosure=disclosure,
            now=env.now,
        )
        automation_id = automation.id
        what = f"Saved the draft automation “{args.name}”."
    else:
        automation_id = args.automation_id
        what = "Saved the new flow."
    saved = await flow_store.save(
        session,
        automation_id,
        args.definition,
        user_id=user_id,
        plan=plan,
        disclosure=disclosure,
        now=env.now,
    )
    if args.automation_id is not None:
        what = f"Saved the new flow of “{saved.name}”."
    return Outcome(
        summary=what,
        resource_kind="automation",
        resource_id=automation_id,
        route=f"automations/{automation_id}",
    )


# ---------------------------------------------------------------- segments


def _segment_body(args: SegmentActionArgs) -> SegmentCreate:
    return SegmentCreate(name=args.name, filter=args.filter)


async def count_matching(session: AsyncSession, spec: ContactFilterSpec) -> int:
    return await contacts.count_contacts(session, contacts.filter_from_spec(spec))


async def check_segment(env: ActionEnv, args: SegmentActionArgs) -> None:
    if args.filter.account_id is not None and (
        await social_accounts.get(env.session, args.filter.account_id) is None
    ):
        raise ApiError("not_found", "That account wasn't found.")
    await contact_segments.validate_new(env.session, _segment_body(args))


async def summarize_segment(env: ActionEnv, args: SegmentActionArgs) -> Summary:
    count = await count_matching(env.session, args.filter)
    names: dict[uuid.UUID, str] = {}
    if args.filter.tag_ids:
        rows = await env.session.execute(
            select(Tag.id, Tag.name).where(Tag.id.in_(args.filter.tag_ids))
        )
        names = {tag_id: name for tag_id, name in rows.all()}
    lines = filter_lines(args.filter, names)
    people = "1 person" if count == 1 else f"{count} people"
    lines.append(
        f"Matches {people} right now. It always follows whoever matches, not a fixed list."
    )
    return Summary(title=f"New segment: {args.name}", lines=lines, match_count=count)


def filter_lines(spec: ContactFilterSpec, tag_names: dict[uuid.UUID, str]) -> list[str]:
    """The filter in plain words, one condition per line."""
    lines: list[str] = []
    if spec.q:
        lines.append(f"Name, email or phone contains “{spec.q}”")
    for tag_id in spec.tag_ids:
        lines.append(f"Has the tag {tag_names.get(tag_id, 'a deleted tag')}")
    if spec.platform:
        lines.append(f"On {spec.platform.capitalize()}")
    if spec.has_email is not None:
        lines.append("Has an email" if spec.has_email else "Has no email")
    if spec.has_phone is not None:
        lines.append("Has a phone number" if spec.has_phone else "Has no phone number")
    if spec.marketing_consent:
        lines.append(f"Agreed to marketing on {spec.marketing_consent}")
    if spec.min_lead_score is not None:
        lines.append(f"Lead score is {spec.min_lead_score} or more")
    if spec.stages:
        lines.append("Lead stage is " + " or ".join(s.replace("_", " ") for s in spec.stages))
    if spec.active_within_days:
        lines.append(f"Active in the last {spec.active_within_days} days")
    if spec.inactive_for_days:
        lines.append(f"No activity for {spec.inactive_for_days} days or more")
    for match in spec.fields:
        key, value = contacts.parse_field_match(match)
        lines.append(f"{key} is filled in" if value is None else f"{key} is {value}")
    return lines or ["Everyone"]


async def execute_segment(env: ActionEnv, args: SegmentActionArgs) -> Outcome:
    segment = await contact_segments.create_segment(
        env.session, _segment_body(args), user_id=env.user_id
    )
    count = await count_matching(env.session, args.filter)
    people = "1 person" if count == 1 else f"{count} people"
    return Outcome(
        summary=f"Saved the segment “{segment.name}”. It matches {people} right now.",
        resource_kind="segment",
        resource_id=segment.id,
        route=f"contacts?segment={segment.id}",
    )


# ---------------------------------------------------------------- the registry

FLOW = ActionSpec(
    tool=FLOW_TOOL,
    key="flow",
    noun="automation",
    min_role=Role.ADMIN,
    args_model=FlowActionArgs,
    check=check_flow,
    summarize=summarize_flow,
    execute=execute_flow,
)
SEGMENT = ActionSpec(
    tool=SEGMENT_TOOL,
    key="segment",
    noun="segment",
    min_role=Role.ADMIN,
    args_model=SegmentActionArgs,
    check=check_segment,
    summarize=summarize_segment,
    execute=execute_segment,
)
ACTIONS: dict[str, ActionSpec[Any]] = {spec.tool: spec for spec in (FLOW, SEGMENT)}


def action_for(tool: str) -> ActionSpec[Any] | None:
    return ACTIONS.get(tool)
