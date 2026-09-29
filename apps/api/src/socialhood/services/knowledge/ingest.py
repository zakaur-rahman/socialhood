"""The ingest_knowledge_source job's work (T5.3; TR-AI-08, FR-KB-02, SEC-09).

For one version of one source: mark it ``processing``; get its text (an FAQ's question and answer,
a note as written, a web page fetched under SEC-09 with its main text by trafilatura, a file
downloaded from storage and read by pypdf, python-docx or as text); split it into chunks
(services/knowledge/chunking.py); embed them as documents in batches of 100; then, in one
transaction, replace the source's chunks and mark it ``ready`` with its character and chunk
counts. Or ``failed`` with the reason in plain words, and no chunks.

No transaction is open while a page, a file or the model is awaited. The source row is locked
and its version re-checked before anything is written, so an edit made during ingestion wins: the
older job's result is dropped and the newer job does the work.

Transient failures (timeouts, 5xx, a retryable AI error) raise ``RetryLater`` while the job has
attempts left, leaving the source ``processing``; on the final attempt they mark it failed
(TR-JOB-04: never mark failed and then retry).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai.provider import AIError
from socialhood.ai.registry import get_provider
from socialhood.billing.plans import current_plan, entitlement
from socialhood.db.tenancy import workspace_scope
from socialhood.models.ai import EMBED_DIM, KnowledgeChunk, KnowledgeStatus, KnowledgeType
from socialhood.observability.logging import get_logger
from socialhood.repositories import knowledge as repo
from socialhood.security import ssrf
from socialhood.services.knowledge import extract
from socialhood.services.knowledge.chunking import split_faq, split_text, with_title
from socialhood.services.knowledge.sources import short_title, url_title
from socialhood.services.media_assets import PDF_DELIVERY_BLOCKED, file_format

log = get_logger(__name__)

EMBED_BATCH = 100  # TR-AI-08
DOWNLOAD_TIMEOUT_S = 30.0
GENERIC_FAILURE = "Couldn't process this source. Try again in a few minutes."
DOWNLOAD_FAILED = "Couldn't download the file from storage. Upload it again."

IngestOutcome = Literal["ready", "failed", "stale"]


class RetryLater(Exception):
    """A transient failure with attempts left: the job retries; the source stays processing."""


class _Failed(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _Transient(_Failed):
    pass


@dataclass(frozen=True)
class _Work:
    kind: KnowledgeType
    title: str
    question: str | None
    body: str | None
    url: str | None
    file_url: str | None
    file_format: str | None


@dataclass(frozen=True)
class _Prepared:
    title: str
    bodies: list[str]  # chunk texts without the title prefix
    char_count: int


async def ingest_source(
    sessionmaker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
    *,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    version: int,
    will_retry: bool,
    now: datetime | None = None,
) -> IngestOutcome:
    """Ingest ``version`` of the source; "stale" when it is gone, newer, or already done."""
    with workspace_scope(workspace_id):
        work = await _begin(sessionmaker, source_id, version)
        if work is None:
            return "stale"
        try:
            prepared = await _prepare(sessionmaker, http, source_id, work)
            contents = [with_title(prepared.title, body) for body in prepared.bodies]
            vectors = await _embed(contents)
        except _Transient as failure:
            if will_retry:
                raise RetryLater(failure.reason) from failure
            return await _fail(sessionmaker, source_id, version, work, failure.reason)
        except _Failed as failure:
            return await _fail(sessionmaker, source_id, version, work, failure.reason)
        except Exception:
            if will_retry:
                raise
            log.exception("knowledge_ingest_crashed", source_id=str(source_id))
            return await _fail(sessionmaker, source_id, version, work, GENERIC_FAILURE)
        return await _store(
            sessionmaker, source_id, version, prepared, contents, vectors, now or datetime.now(UTC)
        )


async def _begin(
    sessionmaker: async_sessionmaker[AsyncSession], source_id: uuid.UUID, version: int
) -> _Work | None:
    async with sessionmaker() as session:
        source = await repo.get_source(session, source_id, for_update=True)
        if source is None or source.version != version:
            return None
        if source.status in (KnowledgeStatus.READY, KnowledgeStatus.FAILED):
            return None  # this version is done (a repeated job)
        kind = KnowledgeType(source.type)
        asset = await repo.get_asset(session, source.file_asset_id)
        work = _Work(
            kind=kind,
            title=source.title,
            question=source.question,
            body=source.body,
            url=source.url,
            file_url=asset.secure_url if asset is not None else None,
            file_format=file_format(asset.format, asset.public_id) if asset is not None else None,
        )
        source.status = KnowledgeStatus.PROCESSING
        await session.commit()
        return work


async def _prepare(
    sessionmaker: async_sessionmaker[AsyncSession],
    http: httpx.AsyncClient,
    source_id: uuid.UUID,
    work: _Work,
) -> _Prepared:
    title = work.title
    if work.kind is KnowledgeType.FAQ:
        question, answer = work.question or "", work.body or ""
        return _Prepared(title, split_faq(question, answer), len(question) + len(answer))
    if work.kind is KnowledgeType.TEXT:
        text = work.body or ""
        return _prepared(title, text, len(text))
    if work.kind is KnowledgeType.URL:
        page = await _fetch(work.url or "")
        web = await _extract(extract.web_page, page.content, page.url)
        if web.title and work.url and title == url_title(httpx.URL(work.url)):
            title = short_title(web.title)  # the page's own title replaces its address
        text = web.text
    else:
        if not work.file_url or not work.file_format:
            raise _Failed("The file is missing. Upload it again.")
        data = await _download(http, work.file_url, work.file_format)
        text = await _extract(extract.file_text, data, work.file_format)
    await _check_quota(sessionmaker, source_id, len(text))
    return _prepared(title, text, len(text))


def _prepared(title: str, text: str, char_count: int) -> _Prepared:
    bodies = split_text(text)
    if not bodies:
        raise _Failed("This source has no text.")
    return _Prepared(title, bodies, char_count)


async def _extract[**P, R](function: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    """Run a CPU-bound extractor off the event loop; its ExtractError becomes the reason."""
    try:
        return await asyncio.to_thread(function, *args, **kwargs)
    except extract.ExtractError as error:
        raise _Failed(error.reason) from error


async def _fetch(url: str) -> ssrf.Page:
    try:
        return await ssrf.fetch_html(url)
    except ssrf.FetchError as error:
        if error.retryable:
            raise _Transient(error.message) from error
        raise _Failed(error.message) from error


async def _download(http: httpx.AsyncClient, url: str, fmt: str) -> bytes:
    """The uploaded file from Cloudinary, at most 10 MB."""
    too_large = _Failed(extract.FILE_FORMATS_COPY)
    try:
        async with http.stream("GET", url, timeout=DOWNLOAD_TIMEOUT_S) as response:
            status = response.status_code
            if status in (401, 403) and fmt == "pdf":
                raise _Failed(PDF_DELIVERY_BLOCKED)
            if status >= 500 or status == 429:
                raise _Transient("Couldn't download the file. Trying again.")
            if status >= 400:
                raise _Failed(DOWNLOAD_FAILED)
            declared = response.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > extract.MAX_FILE_BYTES:
                raise too_large
            data = bytearray()
            async for part in response.aiter_bytes():
                data.extend(part)
                if len(data) > extract.MAX_FILE_BYTES:
                    raise too_large
            return bytes(data)
    except httpx.TransportError as error:
        raise _Transient("Couldn't download the file. Trying again.") from error


async def _check_quota(
    sessionmaker: async_sessionmaker[AsyncSession], source_id: uuid.UUID, chars: int
) -> None:
    """A page or file whose text would pass knowledge_characters fails (§1.7)."""
    async with sessionmaker() as session:
        limit = entitlement(await current_plan(session), "knowledge_characters")
        if limit is None:
            return
        used = await repo.characters_used(session, exclude=source_id)
    if used + chars > limit:
        left = max(limit - used, 0)
        raise _Failed(
            f"This source has {chars:,} characters, more than the {left:,} left on your plan. "
            "Remove other sources or upgrade."
        )


async def _embed(contents: Sequence[str]) -> list[list[float]]:
    """Document embeddings, 100 per call (TR-AI-08); no credits (§1.7)."""
    provider = get_provider()
    vectors: list[list[float]] = []
    for start in range(0, len(contents), EMBED_BATCH):
        batch = list(contents[start : start + EMBED_BATCH])
        try:
            out = await provider.embed(batch, kind="document")
        except AIError as error:
            log.warning("knowledge_embed_failed", code=error.code, retryable=error.retryable)
            if error.retryable:
                raise _Transient(GENERIC_FAILURE) from error
            raise _Failed(GENERIC_FAILURE) from error
        if len(out) != len(batch) or any(len(vector) != EMBED_DIM for vector in out):
            log.error("knowledge_embed_shape", expected=EMBED_DIM, count=len(out))
            raise _Failed(GENERIC_FAILURE)
        vectors.extend(out)
    return vectors


async def _store(
    sessionmaker: async_sessionmaker[AsyncSession],
    source_id: uuid.UUID,
    version: int,
    prepared: _Prepared,
    contents: Sequence[str],
    vectors: Sequence[list[float]],
    now: datetime,
) -> IngestOutcome:
    """Swap in the new chunks and mark the source ready, atomically (TR-AI-08)."""
    async with sessionmaker() as session:
        source = await repo.get_source(session, source_id, for_update=True)
        if source is None or source.version != version:
            return "stale"  # edited or deleted meanwhile: the newer job decides
        chunks = [
            KnowledgeChunk(
                source_id=source_id,
                source_version=version,
                ordinal=ordinal,
                char_count=len(content),
                content=content,
                embedding=vector,
            )
            for ordinal, (content, vector) in enumerate(zip(contents, vectors, strict=True))
        ]
        await repo.replace_chunks(session, source_id, chunks)
        source.title = prepared.title
        source.status = KnowledgeStatus.READY
        source.error = None
        source.char_count = prepared.char_count
        source.chunk_count = len(chunks)
        source.last_ingested_at = now
        await session.commit()
    log.info("knowledge_ingested", source_id=str(source_id), version=version, chunks=len(chunks))
    return "ready"


async def _fail(
    sessionmaker: async_sessionmaker[AsyncSession],
    source_id: uuid.UUID,
    version: int,
    work: _Work,
    reason: str,
) -> IngestOutcome:
    """Failed with ``reason``; nothing of it stays searchable. A page or file that couldn't be
    read counts no characters; an FAQ or note keeps its own."""
    async with sessionmaker() as session:
        source = await repo.get_source(session, source_id, for_update=True)
        if source is None or source.version != version:
            return "stale"
        await repo.replace_chunks(session, source_id, [])
        source.status = KnowledgeStatus.FAILED
        source.error = reason
        source.chunk_count = 0
        if work.kind in (KnowledgeType.URL, KnowledgeType.FILE):
            source.char_count = 0
        await session.commit()
    log.info("knowledge_ingest_failed", source_id=str(source_id), version=version, reason=reason)
    return "failed"
