"""Contacts, tags, custom fields and consent (GR-02)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

FieldTypeName = Literal["text", "email", "phone", "number", "date", "choice"]
ConsentChannelName = Literal["instagram", "whatsapp", "email"]
ConsentStatusName = Literal["granted", "revoked"]
ConsentSourceName = Literal["platform_optin", "flow", "stop_reply", "member", "import"]
Option = Annotated[str, Field(min_length=1, max_length=60)]  # a choice field's value


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


class BulkTagsUpdate(ContactTagsUpdate):
    contact_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class BulkTagsResult(ResponseModel):
    updated: int
