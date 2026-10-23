"""Saved replies (GR-21): a workspace's snippets, typed after ``/`` in the composer."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

SHORTCUT_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,29}$"
Title = Annotated[str, Field(min_length=1, max_length=60)]
# Checked, with its message, in the service (a leading slash and capitals are accepted).
Shortcut = Annotated[str, Field(min_length=1, max_length=31)]
Body = Annotated[str, Field(min_length=1, max_length=1000)]


class SavedReply(ResponseModel):
    id: uuid.UUID
    title: str
    shortcut: str
    body: str
    created_at: datetime
    updated_at: datetime


class SavedReplyList(ResponseModel):
    items: list[SavedReply]
    max_items: int


class SavedReplyCreate(RequestModel):
    """The shortcut is what follows ``/`` in the composer: lower case letters, digits, ``-`` and
    ``_``, unique in the workspace. The body may use ``{first_name}``, ``{username}``, ``{name}``,
    ``{email}``, ``{phone}`` and a custom field's key; ``{first_name|there}`` names a fallback."""

    title: Title
    shortcut: Shortcut
    body: Body


class SavedReplyUpdate(RequestModel):
    title: Title | None = None
    shortcut: Shortcut | None = None
    body: Body | None = None


class SavedReplyFill(RequestModel):
    """The conversation whose contact the reply is filled for."""

    conversation_id: uuid.UUID


class SavedReplyFilled(ResponseModel):
    text: str
