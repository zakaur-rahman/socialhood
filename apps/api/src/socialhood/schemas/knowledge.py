"""Knowledge shapes (§5.5, §5.10; FR-KB-01…06, UX-SCR-06): sources, the test box, gaps."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.inbox import SuggestionSource

KnowledgeTypeName = Literal["faq", "text", "url", "file"]
KnowledgeStatusName = Literal["pending", "processing", "ready", "failed"]
GapStatusName = Literal["open", "answered", "dismissed"]


class KnowledgeSource(ResponseModel):
    id: uuid.UUID
    type: KnowledgeTypeName
    title: str
    question: str | None = None  # FAQ
    body: str | None = None  # FAQ answer or note text
    url: str | None = None
    file_asset_id: uuid.UUID | None = None
    file_name: str | None = None
    status: KnowledgeStatusName  # Processing (pending, processing), Ready, Failed (FR-KB-02)
    error: str | None = None  # why it failed, in plain words
    version: int
    char_count: int
    chunk_count: int
    last_ingested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeUsage(ResponseModel):
    characters_used: int
    characters_limit: int | None = None  # knowledge_characters; None = unlimited


class KnowledgeSourceList(ResponseModel):
    items: list[KnowledgeSource]
    usage: KnowledgeUsage


class KnowledgeSourceCreate(RequestModel):
    """POST …/knowledge-sources. FAQ: question + body (title = question). Note: title + body.
    Web page: url (SEC-09). File: file_asset_id of an uploaded raw asset (PDF, DOCX, TXT, MD up to
    10 MB). ``gap_id`` answers a knowledge gap (FR-KB-06)."""

    type: KnowledgeTypeName
    title: str | None = Field(default=None, min_length=1, max_length=120)
    question: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, min_length=1, max_length=20000)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    file_asset_id: uuid.UUID | None = None
    gap_id: uuid.UUID | None = None


class KnowledgeSourcePatch(RequestModel):
    """PATCH …/knowledge-sources/{id}: edits re-ingest the source (version + 1)."""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    question: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, min_length=1, max_length=20000)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    reingest: bool = False  # fetch a web page or re-read a file again without other changes


class KnowledgeTest(RequestModel):
    question: str = Field(min_length=1, max_length=1000)


class KnowledgeTestResult(ResponseModel):
    """FR-KB-03: the drafted answer with the sources it used, or "Not in your knowledge"."""

    can_answer: bool
    answer: str | None = None
    missing_info: str | None = None
    sources: list[SuggestionSource]


class KnowledgeGapExample(ResponseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    text: str
    occurred_at: datetime


class KnowledgeGap(ResponseModel):
    id: uuid.UUID
    topic: str
    status: GapStatusName
    occurrences: int
    first_seen_at: datetime
    last_seen_at: datetime
    examples: list[KnowledgeGapExample]  # up to 3 shown


class KnowledgeGapList(ResponseModel):
    items: list[KnowledgeGap]
