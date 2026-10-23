"""Knowledge shapes (§5.5, §5.10; FR-KB-01…06, UX-SCR-06): sources, the test box, gaps."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.inbox import SuggestionSource

KnowledgeTypeName = Literal["faq", "text", "url", "file", "site", "page"]
KnowledgeCreateTypeName = Literal["faq", "text", "url", "file", "site"]  # a page is made by a crawl
RecrawlName = Literal["weekly", "off"]
SiteCrawlStatusName = Literal["idle", "queued", "running", "done", "failed"]
SitePageStatusName = Literal["queued", "done", "failed", "skipped", "gone", "excluded", "removed"]
ExcludedPath = Annotated[str, StringConstraints(min_length=1, max_length=200)]
MAX_EXCLUDED_PATHS = 50
KnowledgeStatusName = Literal["pending", "processing", "ready", "failed"]
GapStatusName = Literal["open", "answered", "dismissed"]


class SiteCrawlInfo(ResponseModel):
    """GR-35: where a site source's crawl is. Counts are of this site's pages."""

    status: SiteCrawlStatusName
    recrawl: RecrawlName
    excluded_paths: list[str]
    pages_found: int  # waiting, read and failed: what counts against the plan's page cap
    pages_done: int
    pages_failed: int
    pages_skipped: int  # robots.txt, noindex, not a page, another site
    char_count: int  # characters of the pages that are ready
    chunk_count: int
    page_cap: int  # the plan's pages for one crawl
    truncated: bool  # the last crawl stopped at the cap
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    next_crawl_at: datetime | None = None


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
    site: SiteCrawlInfo | None = None  # a site source's crawl (type "site")
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

    type: KnowledgeCreateTypeName
    title: str | None = Field(default=None, min_length=1, max_length=120)
    question: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, min_length=1, max_length=20000)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    file_asset_id: uuid.UUID | None = None
    gap_id: uuid.UUID | None = None
    recrawl: RecrawlName | None = None  # site only; weekly when left out


class KnowledgeSourcePatch(RequestModel):
    """PATCH …/knowledge-sources/{id}: edits re-ingest the source (version + 1)."""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    question: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, min_length=1, max_length=20000)
    url: str | None = Field(default=None, min_length=1, max_length=2000)
    reingest: bool = False  # fetch a web page or re-read a file again; crawl a site again
    recrawl: RecrawlName | None = None  # site only
    # Site only: the whole list of excluded paths (prefixes such as "/blog"), replacing the old.
    excluded_paths: list[ExcludedPath] | None = Field(default=None, max_length=MAX_EXCLUDED_PATHS)


class SitePage(ResponseModel):
    """GR-35: one address of a site crawl."""

    id: uuid.UUID
    url: str
    title: str | None = None
    status: SitePageStatusName  # the crawl's view of the page
    error: str | None = None  # why it failed or was skipped, in plain words
    ingest_status: KnowledgeStatusName | None = None  # the page's own knowledge source, if any
    char_count: int
    chunk_count: int
    last_crawled_at: datetime | None = None


class SitePageList(ResponseModel):
    items: list[SitePage]
    total: int


class ExcludePath(RequestModel):
    """POST …/excluded-paths: pages at this path or below it are removed and not crawled again."""

    path: str = Field(min_length=1, max_length=200)


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
