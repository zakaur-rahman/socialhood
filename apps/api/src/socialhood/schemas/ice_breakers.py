"""Conversation starters (GR-11): an Instagram account's ice breakers and how the last sync went."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel


class IceBreaker(ResponseModel):
    id: uuid.UUID
    position: int
    question: str
    # The automation a tap starts (one on the "conversation starter" trigger), or the AI.
    automation_id: uuid.UUID | None = None
    automation_name: str | None = None
    answer_with_ai: bool = False


class IceBreakerList(ResponseModel):
    items: list[IceBreaker]
    # When Instagram last took the list, and why the last push failed (a sentence), if it did.
    synced_at: datetime | None = None
    sync_error: str | None = None
    max_items: int = 4


class IceBreakerIn(RequestModel):
    question: str = Field(max_length=200)  # 80 characters, checked with a message
    automation_id: uuid.UUID | None = None
    answer_with_ai: bool = False


class IceBreakersUpdate(RequestModel):
    """The whole list, in order. An empty list removes the starters."""

    items: list[IceBreakerIn] = Field(max_length=10)  # 4 allowed, checked with a message
