"""WhatsApp broadcasts (GR-23): the composer's preview, the broadcast and its recipients."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from socialhood.schemas.common import RequestModel, ResponseModel

BroadcastStatusName = Literal[
    "draft", "scheduled", "sending", "paused", "completed", "cancelled", "failed"
]
# What a recipient shows: ours before the message exists, then WhatsApp's, furthest reached.
RecipientStatusName = Literal["queued", "sent", "delivered", "read", "failed", "skipped"]
QualityName = Literal["green", "yellow", "red", "unknown"]
Name = Annotated[str, Field(min_length=1, max_length=80)]


class VariableSpec(RequestModel):
    """One template variable: a contact field (with the text to use when the person has none) or
    a fixed text. ``field`` is first_name, name, username, email, phone or a custom field's key."""

    source: Literal["field", "fixed"]
    field: str | None = Field(default=None, max_length=40)
    value: str | None = Field(default=None, max_length=1024)
    fallback: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _one_source(self) -> VariableSpec:
        if self.source == "field" and not self.field:
            raise ValueError("choose a contact field")
        if self.source == "fixed" and not (self.value or "").strip():
            raise ValueError("write the text")
        return self


class VariableOut(ResponseModel):
    source: Literal["field", "fixed"]
    field: str | None = None
    value: str | None = None
    fallback: str | None = None


class BroadcastDraft(RequestModel):
    """What a broadcast says and who gets it; the preview takes only this."""

    social_account_id: uuid.UUID
    segment_id: uuid.UUID
    template_name: str = Field(min_length=1, max_length=512)
    template_language: str = Field(min_length=1, max_length=32)
    variables: list[VariableSpec] = Field(default_factory=list, max_length=10)


class BroadcastCreate(BroadcastDraft):
    name: Name


class BroadcastUpdate(RequestModel):
    """Change a draft or a scheduled broadcast. Everything is optional; a changed number,
    segment or template must still fit the others."""

    name: Name | None = None
    social_account_id: uuid.UUID | None = None
    segment_id: uuid.UUID | None = None
    template_name: str | None = Field(default=None, min_length=1, max_length=512)
    template_language: str | None = Field(default=None, min_length=1, max_length=32)
    variables: list[VariableSpec] | None = Field(default=None, max_length=10)


class BroadcastStart(RequestModel):
    """Send now, or at ``scheduled_at`` (at least a minute from now)."""

    scheduled_at: datetime | None = None


class AudienceCounts(ResponseModel):
    matching: int  # the segment's contacts on this WhatsApp number
    eligible: int  # marketing consent granted: these are sent to
    opted_out: int  # withdrew consent: skipped
    no_consent: int  # never agreed: skipped
    missing_value: int  # a variable has no value and no fallback: skipped


class CostEstimate(ResponseModel):
    """Meta's rate card times the people to send to. Information, not a charge: the business pays
    Meta directly (PD-3). The card is typed in by hand and unverified."""

    currency: str
    category: str
    per_message: Decimal
    total: Decimal
    as_of: str
    source: str
    verified: bool


class QuotaInfo(ResponseModel):
    limit: int
    used: int  # recipients already counted this period
    remaining: int
    period_end: datetime | None = None
    fits: bool  # whether everyone eligible fits in what is left


class NumberInfo(ResponseModel):
    quality_rating: QualityName
    daily_limit: int | None = None  # people a day; null: unlimited
    limit_known: bool  # false: a conservative default is used
    days_to_send: int


class SamplePreview(ResponseModel):
    contact_name: str | None = None
    text: str


class BroadcastPreview(ResponseModel):
    audience: AudienceCounts
    cost: CostEstimate
    quota: QuotaInfo
    number: NumberInfo
    sample: SamplePreview
    problems: list[str] = Field(default_factory=list)  # plain sentences that stop it being sent


class BroadcastCounts(ResponseModel):
    total: int
    queued: int
    sent: int  # reached WhatsApp and no further (not yet delivered)
    delivered: int
    read: int
    failed: int
    skipped: int
    replied: int  # of those sent to, how many answered (a STOP is an answer)
    stopped: int  # of those, how many withdrew consent


class BroadcastTemplate(ResponseModel):
    name: str
    language: str
    category: str
    body: str


class Broadcast(ResponseModel):
    id: uuid.UUID
    name: str
    status: BroadcastStatusName
    social_account_id: uuid.UUID
    account_label: str | None = None
    segment_id: uuid.UUID | None = None
    segment_name: str
    template: BroadcastTemplate
    variables: list[VariableOut]
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    paused_code: str | None = None
    paused_reason: str | None = None
    audience_size: int
    cost: CostEstimate | None = None
    counts: BroadcastCounts
    created_at: datetime


class BroadcastList(ResponseModel):
    items: list[Broadcast]
    total: int


class Recipient(ResponseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    contact_name: str
    username: str | None = None
    status: RecipientStatusName
    reason: str | None = None  # why it failed or was skipped, in plain words
    replied: bool
    stopped: bool
    dispatched_at: datetime | None = None
    conversation_id: uuid.UUID | None = None


class RecipientList(ResponseModel):
    items: list[Recipient]
    total: int


class RateCardOut(ResponseModel):
    currency: str
    country: str
    as_of: str
    source: str
    verified: bool
    rates: dict[str, Decimal]


class BroadcastAvailability(ResponseModel):
    """Whether the web shows broadcasts at all (the BROADCASTS_ENABLED setting), and what the plan
    allows."""

    enabled: bool
    plan_allowed: bool = False
    monthly_limit: int = 0
    used_this_period: int = 0
    period_end: datetime | None = None
    rate_card: RateCardOut | None = None
