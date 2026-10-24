"""Sequences (GR-24): the editor's body, the sequence with its counts, the preview, a sequence's
enrolments and a contact's sequences."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from socialhood.schemas.broadcasts import VariableOut, VariableSpec
from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.contacts import LeadStageName

SequenceStatusName = Literal["draft", "active", "paused"]
EntryTypeName = Literal["captured", "tagged", "broadcast_replied"]
CaptureKindName = Literal["email", "phone", "field"]
DelayFromName = Literal["entry", "previous"]
EnrolmentStatusName = Literal["active", "completed", "stopped"]
StopReasonName = Literal["reply", "tag", "stage", "member", "ended"]
RunStatusName = Literal["sent", "skipped", "failed"]
Name = Annotated[str, Field(min_length=1, max_length=80)]

MAX_STEPS = 20  # per sequence, whatever the plan
MAX_DELAY_SECONDS = 30 * 24 * 3600


class EntryRule(RequestModel):
    """What starts the sequence for a contact: a lead captured (any, or an email, a phone or an
    answer), a tag added (``tag_id``), or a reply to a WhatsApp broadcast (any, or one)."""

    type: EntryTypeName
    tag_id: uuid.UUID | None = None
    broadcast_id: uuid.UUID | None = None
    capture_kind: CaptureKindName | None = None

    @model_validator(mode="after")
    def _fits_type(self) -> EntryRule:
        if self.type == "tagged" and self.tag_id is None:
            raise ValueError("choose the tag that starts the sequence")
        if self.type != "tagged" and self.tag_id is not None:
            raise ValueError("a tag only starts a sequence of type tagged")
        if self.type != "broadcast_replied" and self.broadcast_id is not None:
            raise ValueError("a broadcast only starts a sequence of type broadcast_replied")
        if self.type != "captured" and self.capture_kind is not None:
            raise ValueError("a capture kind only applies to a sequence of type captured")
        return self


class StopRules(RequestModel):
    """When to stop: the contact writing (on by default), a tag from the list being added, or
    their lead stage becoming one from the list."""

    on_reply: bool = True
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    stages: list[LeadStageName] = Field(default_factory=list, max_length=5)


class StepIn(RequestModel):
    """One message. It waits ``delay_seconds`` from the contact's entry or the step before, then
    sends ``text`` (while the messaging window is open), or on WhatsApp the approved template."""

    delay_seconds: int = Field(ge=0, le=MAX_DELAY_SECONDS)
    delay_from: DelayFromName = "previous"
    text: str | None = Field(default=None, max_length=1000)
    template_name: str | None = Field(default=None, min_length=1, max_length=512)
    template_language: str | None = Field(default=None, min_length=1, max_length=32)
    variables: list[VariableSpec] = Field(default_factory=list, max_length=10)
    respect_hours: bool = False

    @model_validator(mode="after")
    def _has_content(self) -> StepIn:
        if not (self.text or "").strip() and not self.template_name:
            raise ValueError("write the message, or choose a template")
        if bool(self.template_name) != bool(self.template_language):
            raise ValueError("a template needs its name and language")
        return self


class SequenceBody(RequestModel):
    """The whole sequence, as the editor sends it. Saving replaces the steps."""

    name: Name
    social_account_id: uuid.UUID
    entry: EntryRule
    stop: StopRules = Field(default_factory=StopRules)
    allow_reentry: bool = False
    steps: list[StepIn] = Field(min_length=1, max_length=MAX_STEPS)


class StepOut(ResponseModel):
    position: int
    delay_seconds: int
    delay_from: DelayFromName
    text: str | None = None
    template_name: str | None = None
    template_language: str | None = None
    template_category: str | None = None
    template_body: str | None = None
    variables: list[VariableOut] = Field(default_factory=list)
    respect_hours: bool


class EntryOut(ResponseModel):
    type: EntryTypeName
    tag_id: uuid.UUID | None = None
    tag_name: str | None = None
    broadcast_id: uuid.UUID | None = None
    broadcast_name: str | None = None
    capture_kind: CaptureKindName | None = None
    label: str  # in words: "A tag is added: VIP"


class StopOut(ResponseModel):
    on_reply: bool
    tag_ids: list[uuid.UUID]
    tag_names: list[str]
    stages: list[LeadStageName]


class EnrolmentCounts(ResponseModel):
    active: int
    completed: int
    stopped: int


class Sequence(ResponseModel):
    id: uuid.UUID
    name: str
    status: SequenceStatusName
    social_account_id: uuid.UUID
    account_label: str | None = None
    platform: str | None = None
    entry: EntryOut
    stop: StopOut
    allow_reentry: bool
    step_count: int
    steps: list[StepOut] | None = None  # the detail has them; the list does not
    enrolments: EnrolmentCounts
    activated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    problems: list[str] = Field(default_factory=list)  # why it can't run (a deleted tag, say)


class SequenceList(ResponseModel):
    items: list[Sequence]
    active: int  # sequences on now
    active_limit: int | None  # the plan's limit (null: unlimited)
    step_limit: int | None


class PreviewStep(ResponseModel):
    position: int
    after_seconds: int  # from the contact's entry, in a straight run
    sends: Literal["text", "template", "nothing"]
    text: str | None = None
    note: str | None = None  # a plain warning, such as "needs a template after 24 hours"


class SequencePreview(ResponseModel):
    contact_name: str
    steps: list[PreviewStep]
    problems: list[str]


class ContactRef(ResponseModel):
    id: uuid.UUID
    display_name: str | None = None
    username: str | None = None


class LastRun(ResponseModel):
    position: int
    status: RunStatusName
    reason: str | None = None
    at: datetime


class Enrolment(ResponseModel):
    id: uuid.UUID
    sequence_id: uuid.UUID
    sequence_name: str | None = None
    contact: ContactRef
    status: EnrolmentStatusName
    next_step: int | None = None  # 1-based, the step it is on; null once finished
    step_count: int
    next_due_at: datetime | None = None
    enrolled_at: datetime
    finished_at: datetime | None = None
    entry_event: str
    stop_reason: StopReasonName | None = None
    stop_text: str | None = None
    last_run: LastRun | None = None


class EnrolmentList(ResponseModel):
    items: list[Enrolment]
    total: int
    has_more: bool


class ContactStepRun(ResponseModel):
    position: int
    status: RunStatusName
    reason: str | None = None
    at: datetime


class ContactSequence(ResponseModel):
    enrolment: Enrolment
    runs: list[ContactStepRun]


class ContactSequenceList(ResponseModel):
    items: list[ContactSequence]
