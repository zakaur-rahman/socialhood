"""Entry links (GR-08): the ig.me links that open a DM with an account and start an automation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

CODE_PATTERN = r"^[A-Za-z0-9_-]{3,40}$"
QrFormat = Literal["svg", "png"]


class EntryLinkCreate(RequestModel):
    """``code`` is the ?ref= value; leave it out and one is made. It can't be changed later, so
    printed QR codes keep working."""

    social_account_id: uuid.UUID
    name: Annotated[str, Field(min_length=1, max_length=80)]
    automation_id: uuid.UUID | None = None
    code: Annotated[str, Field(pattern=CODE_PATTERN, max_length=40)] | None = None


class EntryLinkUpdate(RequestModel):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    automation_id: uuid.UUID | None = None


class EntryLink(ResponseModel):
    """``url`` is the link to share (and what the QR code holds). ``opened_conversations`` counts
    conversations that began from the link, ``runs`` the automation runs they led to."""

    id: uuid.UUID
    social_account_id: uuid.UUID
    account_username: str | None = None
    name: str
    code: str
    url: str
    automation_id: uuid.UUID | None = None
    automation_name: str | None = None
    opened_conversations: int
    runs: int
    created_at: datetime


class EntryLinkList(ResponseModel):
    items: list[EntryLink]
