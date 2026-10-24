"""Contacts, tags, custom fields and consent (GR-02); saved segments, bulk tagging by filter and
the contact timeline (GR-17)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, model_validator

from socialhood.schemas.common import RequestModel, ResponseModel

FieldTypeName = Literal["text", "email", "phone", "number", "date", "choice"]
ConsentChannelName = Literal["instagram", "whatsapp", "email"]
ConsentStatusName = Literal["granted", "revoked"]
ConsentSourceName = Literal["platform_optin", "flow", "stop_reply", "member", "import"]
LeadStageName = Literal["new", "qualified", "follow_up", "won", "lost"]  # GR-18
Option = Annotated[str, Field(min_length=1, max_length=60)]  # a choice field's value
# A custom field filter: ``key:value`` (equal, ignoring case) or ``key:*`` (has any value).
FieldMatch = Annotated[str, StringConstraints(max_length=100, pattern=r"^[a-z][a-z0-9_]{0,39}:.")]


# ---- tags


class Tag(ResponseModel):
    id: uuid.UUID
    name: str
    color: int  # an index into the identity palette
    contact_count: int = 0


class TagList(ResponseModel):
    items: list[Tag]


class TagCreate(RequestModel):
    name: str = Field(min_length=1, max_length=40)
    color: int = Field(default=0, ge=0, le=15)


class TagPatch(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    color: int | None = Field(default=None, ge=0, le=15)


class TagRef(ResponseModel):
    id: uuid.UUID
    name: str
    color: int


# ---- custom fields


class FieldDefinition(ResponseModel):
    id: uuid.UUID
    key: str
    label: str
    type: FieldTypeName
    options: list[str]
    position: int


class FieldDefinitionList(ResponseModel):
    items: list[FieldDefinition]
    limit: int | None = None  # the plan's contact_fields; None means no limit


class FieldDefinitionCreate(RequestModel):
    key: str = Field(max_length=40, pattern=r"^[a-z][a-z0-9_]{0,39}$")
    label: str = Field(min_length=1, max_length=60)
    type: FieldTypeName = "text"
    # A choice field's values (1 to 30, each up to 60 characters); empty for other types.
    options: list[Option] = Field(default_factory=list, max_length=30)


class FieldDefinitionPatch(RequestModel):
    """A field's key and type never change: values are stored by key and validated by type."""

    label: str | None = Field(default=None, min_length=1, max_length=60)
    options: list[Option] | None = Field(default=None, max_length=30)
    position: int | None = Field(default=None, ge=0, le=999)


# ---- consent


class Consent(ResponseModel):
    """The current state for one channel: the latest record."""

    channel: ConsentChannelName
    purpose: Literal["marketing"]
    status: ConsentStatusName
    source: ConsentSourceName
    occurred_at: datetime
    note: str | None = None  # a member's note, for source "member"


class ConsentCreate(RequestModel):
    """A member records consent the customer gave elsewhere (a form, in person), or its
    withdrawal. The note says how it was given; it's the evidence."""

    channel: ConsentChannelName
    status: ConsentStatusName
    note: str = Field(min_length=3, max_length=300)


# ---- contacts


class ContactListItem(ResponseModel):
    id: uuid.UUID
    social_account_id: uuid.UUID
    platform: str
    name: str
    username: str | None = None
    profile_picture_url: str | None = None
    email: str | None = None
    phone: str | None = None
    tags: list[TagRef]
    lead_score: int | None = None
    # GR-18: the lead stage, when and why it last changed, and whether the lead has gone cold
    # (flagged by the gone-cold job and not written to since).
    lead_stage: LeadStageName = "new"
    lead_stage_at: datetime | None = None
    lead_stage_reason: str | None = None
    lead_cold: bool = False
    conversation_id: uuid.UUID | None = None  # None: never messaged (for example a commenter)
    last_activity_at: datetime | None = None
    first_seen_at: datetime | None = None


class ContactList(ResponseModel):
    items: list[ContactListItem]
    next_cursor: str | None = None


class ContactRecord(ContactListItem):
    """One contact with what the business knows about them."""

    fields: dict[str, Any]
    email_source: str | None = None
    email_verified: bool
    phone_source: str | None = None
    phone_verified: bool
    first_entry_source: str | None = None
    consents: list[Consent]  # the current state per channel that has any record


class ContactPatch(RequestModel):
    """Only what is sent changes. ``fields`` merges: a key set to null is removed. An email or
    phone set here is marked as entered by a member and not verified."""

    email: str | None = Field(default=None, max_length=254)
    clear_email: bool = False
    phone: str | None = Field(default=None, max_length=32)
    clear_phone: bool = False
    fields: dict[str, Any] | None = None


class ContactTagsUpdate(RequestModel):
    add: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    remove: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class ContactFilterSpec(RequestModel):
    """The contacts list's filter as a body (a saved segment, a bulk tag on everything that
    matches). The same keys, rules and limits as the list's query string."""

    q: str | None = Field(default=None, max_length=100)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)  # every one of them
    platform: Literal["instagram", "whatsapp", "facebook"] | None = None
    account_id: uuid.UUID | None = None
    has_email: bool | None = None
    has_phone: bool | None = None
    marketing_consent: ConsentChannelName | None = None
    min_lead_score: int | None = Field(default=None, ge=0, le=100)
    stages: list[LeadStageName] = Field(default_factory=list, max_length=5)  # any of them (GR-18)
    active_after: datetime | None = None
    active_before: datetime | None = None
    # Moving ranges, so a saved segment stays "active this week": active in the last N days, or
    # with no activity for N days or more.
    active_within_days: int | None = Field(default=None, ge=1, le=3650)
    inactive_for_days: int | None = Field(default=None, ge=1, le=3650)
    fields: list[FieldMatch] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def _range(self) -> ContactFilterSpec:
        if self.active_after and self.active_before and self.active_after >= self.active_before:
            raise ValueError("The activity range ends before it starts.")
        return self


class ContactFilterOut(ResponseModel):
    """A saved filter as returned. A separate class from the request's, so the API description
    keeps one name for each (a model used both ways with defaults would be split in two)."""

    q: str | None = None
    tag_ids: list[uuid.UUID] = Field(default_factory=list)
    platform: Literal["instagram", "whatsapp", "facebook"] | None = None
    account_id: uuid.UUID | None = None
    has_email: bool | None = None
    has_phone: bool | None = None
    marketing_consent: ConsentChannelName | None = None
    min_lead_score: int | None = None
    stages: list[LeadStageName] = Field(default_factory=list)
    active_after: datetime | None = None
    active_before: datetime | None = None
    active_within_days: int | None = None
    inactive_for_days: int | None = None
    fields: list[str] = Field(default_factory=list)


class BulkTagsUpdate(ContactTagsUpdate):
    """Name the contacts (up to 500) or give a filter for everything that matches it (up to the
    service's cap); not both."""

    contact_ids: list[uuid.UUID] | None = Field(default=None, min_length=1, max_length=500)
    filter: ContactFilterSpec | None = None

    @model_validator(mode="after")
    def _one_target(self) -> BulkTagsUpdate:
        if (self.contact_ids is None) == (self.filter is None):
            raise ValueError("Send either contact_ids or filter.")
        return self


class BulkTagsResult(ResponseModel):
    updated: int


class ContactCount(ResponseModel):
    count: int


# ---- saved segments


class Segment(ResponseModel):
    id: uuid.UUID
    name: str
    filter: ContactFilterOut
    created_at: datetime


class SegmentList(ResponseModel):
    items: list[Segment]


class SegmentCreate(RequestModel):
    name: str = Field(min_length=1, max_length=60)
    filter: ContactFilterSpec


class SegmentPatch(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    filter: ContactFilterSpec | None = None


# ---- timeline

TimelineKind = Literal[
    "conversation", "comment", "automation_run", "story_mention", "consent", "tag", "lead_stage"
]


class TimelineItem(ResponseModel):
    id: uuid.UUID  # unique across kinds, so it is the item's key and half its cursor
    kind: TimelineKind
    occurred_at: datetime
    title: str
    detail: str | None = None  # a comment's text, a run's outcome, where consent came from
    conversation_id: uuid.UUID | None = None  # where to open it, when there is a conversation


class TimelineList(ResponseModel):
    items: list[TimelineItem]
    next_cursor: str | None = None
