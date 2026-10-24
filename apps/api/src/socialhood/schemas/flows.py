"""Automation flows (GR-03): what an automation does after its trigger, as a graph of steps.

The trigger, keywords, posts, public replies and run settings stay on the automation; the flow is
the private part: the messages, questions, branches and actions. A flow is stored as this JSON,
versioned per automation (a run keeps the version it started on), and checked by
services/automations/flows.py.

Step ids are the author's (lower case, digits, ``_`` and ``-``): they name a step in errors and
in each run's step log, and give a step's message its stable client id, so an id must not be
reused for a different step in a later version.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.contacts import LeadStageName

FLOW_SCHEMA_VERSION = 1
MAX_STEPS = 50  # per flow; a plan cap may lower it (PD-5)

StepId = Annotated[str, StringConstraints(max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")]
FieldKey = Annotated[str, StringConstraints(max_length=40, pattern=r"^[a-z][a-z0-9_]{0,39}$")]
# A backstop like the editor's message_text; Instagram's 1,000 bytes are checked on activation.
StepText = Annotated[str, StringConstraints(max_length=4000)]


# ---------------------------------------------------------------- send


class FlowButton(RequestModel):
    """A link button: a https address, or the account's own Instagram profile (``profile``,
    the follow nudge's "View profile")."""

    title: str = Field(min_length=1, max_length=20)
    url: str | None = Field(default=None, max_length=2000)  # https, checked on activation
    profile: bool = False


class QuickReply(RequestModel):
    """A tap-to-answer option; the flow goes on at ``next`` when it's tapped."""

    title: str = Field(min_length=1, max_length=20)
    next: StepId | None = None


class SendStep(RequestModel):
    """A message. With quick replies the flow waits for an answer: a tap goes to that option's
    step, anything typed to ``on_text`` (quick replies don't show on desktop).

    With ``saved_reply_id`` (GR-21) the text is that saved reply's body, read and filled for the
    contact when the step runs, and ``text`` is ignored. A saved reply goes alone: no image,
    buttons or quick replies. A deleted reply fails the step."""

    type: Literal["send"] = "send"
    id: StepId
    text: StepText = ""
    saved_reply_id: uuid.UUID | None = None
    image_asset_id: uuid.UUID | None = None
    buttons: list[FlowButton] = Field(default_factory=list, max_length=3)
    quick_replies: list[QuickReply] = Field(default_factory=list, max_length=13)
    on_text: StepId | None = None
    next: StepId | None = None


# ---------------------------------------------------------------- ask


class AskStep(RequestModel):
    """A question whose answer is checked and saved: free text to a custom field, an email or a
    phone to the contact (or a custom field of that type). An answer that doesn't fit gets
    ``retry_text`` until ``tries`` run out, then the flow goes on at ``on_skip`` (GR-14: the editor
    makes that the same step as ``next`` unless the author picks another).

    ``consent`` adds a marketing question once the answer is saved: Yes or No quick replies (or
    those words typed), recorded in contact_consents with the messages as evidence.
    ``confirm_text`` is sent after the answer is saved (and the consent answered); blank sends
    nothing. Blank ``retry_text`` and ``consent_text`` use the default copy in engine.py."""

    type: Literal["ask"] = "ask"
    id: StepId
    text: StepText = ""
    expect: Literal["text", "email", "phone"] = "text"
    field_key: FieldKey | None = None  # None: an email or phone goes to the contact's own
    retry_text: Annotated[str, StringConstraints(max_length=300)] = ""
    tries: int = Field(default=2, ge=1, le=3)
    consent: bool = False
    consent_text: Annotated[str, StringConstraints(max_length=300)] = ""
    confirm_text: Annotated[str, StringConstraints(max_length=300)] = ""
    next: StepId | None = None
    on_skip: StepId | None = None


# ---------------------------------------------------------------- branch


class TagCondition(RequestModel):
    kind: Literal["tag"] = "tag"
    tag_id: uuid.UUID
    has: bool = True


class FieldCondition(RequestModel):
    """``equals`` ignores case; ``set`` is any value."""

    kind: Literal["field"] = "field"
    key: FieldKey
    op: Literal["set", "unset", "equals"] = "set"
    value: Annotated[str, StringConstraints(max_length=200)] | None = None


class ContactCondition(RequestModel):
    """Whether the contact's email or phone is known."""

    kind: Literal["contact"] = "contact"
    has: Literal["email", "phone"]
    known: bool = True


class FollowsCondition(RequestModel):
    """Whether they follow the account, read when the step runs; unknown counts as neither."""

    kind: Literal["follows_business"] = "follows_business"
    follows: bool = True


class PlatformCondition(RequestModel):
    kind: Literal["platform"] = "platform"
    platform: Literal["instagram", "whatsapp", "facebook"]


class LeadScoreCondition(RequestModel):
    kind: Literal["lead_score"] = "lead_score"
    at_least: int = Field(ge=0, le=100)


class LeadStageCondition(RequestModel):
    """Whether the contact's lead stage (GR-18) is any of ``stages``, read when the step runs."""

    kind: Literal["lead_stage"] = "lead_stage"
    stages: list[LeadStageName] = Field(min_length=1, max_length=5)


Condition = Annotated[
    TagCondition
    | FieldCondition
    | ContactCondition
    | FollowsCondition
    | PlatformCondition
    | LeadScoreCondition
    | LeadStageCondition,
    Field(discriminator="kind"),
]


class BranchRule(RequestModel):
    when: Condition
    next: StepId | None = None


class BranchStep(RequestModel):
    """The first rule that holds picks the next step; none does, ``otherwise``."""

    type: Literal["branch"] = "branch"
    id: StepId
    rules: list[BranchRule] = Field(default_factory=list, max_length=10)
    otherwise: StepId | None = None


# ---------------------------------------------------------------- action


class AddTag(RequestModel):
    kind: Literal["add_tag"] = "add_tag"
    tag_id: uuid.UUID


class RemoveTag(RequestModel):
    kind: Literal["remove_tag"] = "remove_tag"
    tag_id: uuid.UUID


class SetField(RequestModel):
    kind: Literal["set_field"] = "set_field"
    key: FieldKey
    value: Annotated[str, StringConstraints(max_length=200)]


class NotifyTeam(RequestModel):
    kind: Literal["notify_team"] = "notify_team"
    note: Annotated[str, StringConstraints(max_length=200)] = ""


class HandOff(RequestModel):
    """The conversation goes to Needs you, and the AI stops replying in it."""

    kind: Literal["hand_off"] = "hand_off"


Action = Annotated[
    AddTag | RemoveTag | SetField | NotifyTeam | HandOff, Field(discriminator="kind")
]


class ActionStep(RequestModel):
    type: Literal["action"] = "action"
    id: StepId
    action: Action
    next: StepId | None = None


# ---------------------------------------------------------------- delay, randomize, AI, end


class DelayStep(RequestModel):
    """A pause, at most 23 hours, so what follows can still go inside the 24-hour reply window
    (a send the window no longer allows ends the run instead)."""

    type: Literal["delay"] = "delay"
    id: StepId
    seconds: int = Field(ge=1, le=23 * 3600)
    next: StepId | None = None


class SplitPath(RequestModel):
    weight: int = Field(default=1, ge=1, le=100)
    next: StepId | None = None


class RandomizeStep(RequestModel):
    """An A/B split: each run takes one path, at random by weight."""

    type: Literal["randomize"] = "randomize"
    id: StepId
    paths: list[SplitPath] = Field(min_length=2, max_length=5)


class AiReplyStep(RequestModel):
    """An AI reply from the knowledge base (T5.8), or a hand-off when it can't answer. It ends
    the flow."""

    type: Literal["ai_reply"] = "ai_reply"
    id: StepId
    instructions: Annotated[str, StringConstraints(max_length=2000)] = ""


class EndStep(RequestModel):
    type: Literal["end"] = "end"
    id: StepId


Step = Annotated[
    SendStep
    | AskStep
    | BranchStep
    | ActionStep
    | DelayStep
    | RandomizeStep
    | AiReplyStep
    | EndStep,
    Field(discriminator="type"),
]
StepType = Literal["send", "ask", "branch", "action", "delay", "randomize", "ai_reply", "end"]


class FlowDefinition(RequestModel):
    """``start`` is the first step; a step without a next ends the flow."""

    schema_version: Literal[1] = 1  # FLOW_SCHEMA_VERSION
    start: StepId
    steps: list[Step] = Field(min_length=1, max_length=MAX_STEPS)


# ---------------------------------------------------------------- the API


FlowSource = Literal["legacy", "flow"]


class Flow(ResponseModel):
    """GET and PUT …/automations/{id}/flow. ``source`` says how it was made: ``legacy`` is
    compiled from the automation's message settings (the current editor), ``flow`` was saved as
    a flow."""

    automation_id: uuid.UUID
    version: int
    source: FlowSource
    definition: FlowDefinition
    missing_for_activation: list[str]  # field paths, e.g. ["flow.steps.0.text"]
