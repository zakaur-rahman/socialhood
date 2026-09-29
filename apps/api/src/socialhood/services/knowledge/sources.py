"""Knowledge sources (T5.3; FR-KB-01, FR-KB-02, F-14, SEC-09): create, edit, list, delete.

A new or edited source is stored ``pending``; once the caller has committed, ``enqueue_ingest``
queues ingest_knowledge_source(id, version) at once (bulk lane, queueing lock kb:{id}:{version}),
so an edit is searchable well within 60 s (FR-KB-02). Every edit adds 1 to the version, and the
job ignores a version that is no longer current. Nothing here commits.

What each type needs: an FAQ a question and an answer (``body``; its title is the question); a
note a title and a body; a web page a public http(s) address (checked again, with DNS, when it is
fetched); a file an uploaded PDF, DOCX, TXT or MD asset up to 10 MB. ``gap_id`` (FAQ only)
answers a knowledge gap (F-17).

knowledge_characters (§1.7) caps the characters of all sources: an FAQ or note that would pass it
is refused with 402 quota_exceeded; a web page or file, whose length is known only after
extraction, is refused while the workspace is at the limit and fails in ingestion if its text
would pass it.
"""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.ai import KnowledgeSource as SourceRow
from socialhood.models.ai import KnowledgeStatus, KnowledgeType
from socialhood.models.media import MediaAsset
from socialhood.observability.logging import get_logger
from socialhood.repositories import knowledge as repo
from socialhood.schemas.knowledge import (
    KnowledgeSource,
    KnowledgeSourceCreate,
    KnowledgeSourceList,
    KnowledgeSourcePatch,
    KnowledgeUsage,
)
from socialhood.security import ssrf
from socialhood.services.knowledge import gaps
from socialhood.services.knowledge.extract import FILE_FORMATS, FILE_FORMATS_COPY, MAX_FILE_BYTES
from socialhood.services.media_assets import file_format

log = get_logger(__name__)

TITLE_CHARS = 120
# Fields each type takes on create (besides ``type``) and on edit.
CREATE_FIELDS: dict[KnowledgeType, frozenset[str]] = {
    KnowledgeType.FAQ: frozenset({"question", "body", "gap_id"}),
    KnowledgeType.TEXT: frozenset({"title", "body"}),
    KnowledgeType.URL: frozenset({"title", "url"}),
    KnowledgeType.FILE: frozenset({"title", "file_asset_id"}),
}
EDIT_FIELDS: dict[KnowledgeType, frozenset[str]] = {
    KnowledgeType.FAQ: frozenset({"question", "body"}),
    KnowledgeType.TEXT: frozenset({"title", "body"}),
    KnowledgeType.URL: frozenset({"title", "url"}),
    KnowledgeType.FILE: frozenset({"title"}),
}
NOT_FOR_TYPE = {
    KnowledgeType.FAQ: "An FAQ has a question and an answer.",
    KnowledgeType.TEXT: "A note has a title and text.",
    KnowledgeType.URL: "A web page source has an address and an optional title.",
    KnowledgeType.FILE: "A file source has a file and an optional title.",
}


# ---------------------------------------------------------------- reads


async def usage(session: AsyncSession) -> KnowledgeUsage:
    limit = entitlement(await current_plan(session), "knowledge_characters")
    return KnowledgeUsage(
        characters_used=await repo.characters_used(session), characters_limit=limit
    )


async def list_sources(session: AsyncSession) -> KnowledgeSourceList:
    rows = await repo.list_sources(session)
    return KnowledgeSourceList(
        items=[source_out(source, asset) for source, asset in rows], usage=await usage(session)
    )


async def get(session: AsyncSession, source_id: uuid.UUID) -> KnowledgeSource:
    return await view(session, await _get_or_404(session, source_id))


async def view(session: AsyncSession, source: SourceRow) -> KnowledgeSource:
    return source_out(source, await repo.get_asset(session, source.file_asset_id))


def source_out(source: SourceRow, asset: MediaAsset | None) -> KnowledgeSource:
    return KnowledgeSource.model_validate(
        {
            "id": source.id,
            "type": source.type,
            "title": source.title,
            "question": source.question,
            "body": source.body,
            "url": source.url,
            "file_asset_id": source.file_asset_id,
            "file_name": file_name(asset),
            "status": source.status,
            "error": source.error,
            "version": source.version,
            "char_count": source.char_count,
            "chunk_count": source.chunk_count,
            "last_ingested_at": source.last_ingested_at,
            "created_at": source.created_at,
            "updated_at": source.updated_at,
        }
    )


def file_name(asset: MediaAsset | None) -> str | None:
    if asset is None:
        return None
    if asset.original_filename:
        return asset.original_filename
    name = asset.public_id.rsplit("/", 1)[-1]
    fmt = file_format(asset.format, asset.public_id)
    return name if not fmt or name.lower().endswith(f".{fmt}") else f"{name}.{fmt}"


# ---------------------------------------------------------------- writes


async def create(
    session: AsyncSession, body: KnowledgeSourceCreate, *, user_id: uuid.UUID
) -> SourceRow:
    """Store a pending source (and answer its gap); the caller commits, then enqueue_ingest."""
    kind = KnowledgeType(body.type)
    sent = _sent(body, exclude={"type"})
    if kind is KnowledgeType.FAQ:
        sent.discard("title")  # an FAQ's title is its question
    _reject_other_fields(kind, sent, CREATE_FIELDS[kind])
    gap = await gaps.gap_to_answer(session, body.gap_id) if body.gap_id else None
    chars = 0
    if kind is KnowledgeType.FAQ:
        question = _required(body.question, "question", "Enter the customer's question.")
        answer = _required(body.body, "body", "Enter the answer.")
        source = SourceRow(type=kind, title=short_title(question), question=question, body=answer)
        chars = len(question) + len(answer)
    elif kind is KnowledgeType.TEXT:
        title = _required(body.title, "title", "Give the note a title.")
        text = _required(body.body, "body", "Write the note.")
        source = SourceRow(type=kind, title=short_title(title), body=text)
        chars = len(text)
    elif kind is KnowledgeType.URL:
        url = _checked_url(_required(body.url, "url", ssrf.BAD_ADDRESS))
        title = short_title(body.title) if body.title else url_title(url)
        source = SourceRow(type=kind, title=title, url=str(url))
    else:
        asset_id = _required(body.file_asset_id, "file_asset_id", "Upload a file.")
        asset = await _knowledge_file(session, asset_id)
        title = short_title(body.title or file_name(asset) or "File")
        source = SourceRow(type=kind, title=title, file_asset_id=asset.id)
    await _check_quota(session, adding=chars)
    source.status = KnowledgeStatus.PENDING
    source.char_count = chars
    source.created_by_user_id = user_id
    session.add(source)
    await session.flush()
    if gap is not None:
        gaps.mark_answered(gap, source.id)
        await session.flush()
    await session.refresh(source)
    return source


async def update(
    session: AsyncSession, source_id: uuid.UUID, body: KnowledgeSourcePatch
) -> tuple[SourceRow, bool]:
    """Apply an edit; returns the source and whether it must be ingested again (version + 1)."""
    source = await _get_or_404(session, source_id, for_update=True)
    kind = KnowledgeType(source.type)
    sent = _sent(body, exclude={"reingest"})
    if kind is KnowledgeType.FAQ:
        sent.discard("title")  # an FAQ's title is its question
    _reject_other_fields(kind, sent, EDIT_FIELDS[kind])
    changed = False

    def assign(name: str, value: str | None) -> None:
        nonlocal changed
        if getattr(source, name) != value:
            setattr(source, name, value)
            changed = True

    if kind is KnowledgeType.FAQ:
        assign("question", body.question or source.question)
        assign("body", body.body or source.body)
        assign("title", short_title(source.question or source.title))
    elif kind is KnowledgeType.TEXT:
        assign("title", short_title(body.title) if body.title else source.title)
        assign("body", body.body or source.body)
    elif kind is KnowledgeType.URL:
        old_url = source.url or ""
        if body.url:
            url = _checked_url(body.url)
            assign("url", str(url))
            if not body.title and source.title == url_title(httpx.URL(old_url)):
                assign("title", url_title(url))  # the title was the old address
        if body.title:
            assign("title", short_title(body.title))
    elif body.title:
        assign("title", short_title(body.title))
    if not changed and not body.reingest:
        return source, False
    if kind in (KnowledgeType.FAQ, KnowledgeType.TEXT):
        chars = len(source.question or "") + len(source.body or "")
        if chars > source.char_count:  # shortening is always allowed, even over the limit
            await _check_quota(session, adding=chars, exclude=source.id)
        source.char_count = chars
    source.version += 1
    source.status = KnowledgeStatus.PENDING
    source.error = None
    await session.flush()
    await session.refresh(source)
    return source, True


async def delete(session: AsyncSession, source_id: uuid.UUID) -> None:
    """The source and its chunks (ON DELETE CASCADE); a gap it answered keeps its status."""
    if not await repo.delete_source(session, source_id):
        raise ApiError("not_found")


async def enqueue_ingest(source: SourceRow) -> bool:
    """Queue ingestion of the source's current version, after the caller has committed. A lost
    enqueue leaves the source pending; saving it again (or ``reingest``) queues it again."""
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.knowledge import ingest_knowledge_source

    try:
        return await enqueue(
            ingest_knowledge_source,
            key=f"kb:{source.id}:{source.version}",
            workspace_id=str(source.workspace_id),
            source_id=str(source.id),
            version=source.version,
        )
    except Exception:
        log.warning("knowledge_enqueue_failed", source_id=str(source.id), exc_info=True)
        return False


# ---------------------------------------------------------------- helpers


def short_title(text: str) -> str:
    """At most 120 characters on one line (FAQ titles are questions of up to 500)."""
    title = " ".join(text.split())
    return title if len(title) <= TITLE_CHARS else title[: TITLE_CHARS - 1].rstrip() + "…"


def url_title(url: httpx.URL) -> str:
    """A web page's title until its own is known: host and path."""
    path = url.path.rstrip("/")
    return short_title(f"{url.host}{path}")


def _sent(body: KnowledgeSourceCreate | KnowledgeSourcePatch, *, exclude: set[str]) -> set[str]:
    return {
        name
        for name in body.model_fields_set
        if name not in exclude and getattr(body, name) is not None
    }


def _reject_other_fields(kind: KnowledgeType, sent: set[str], allowed: frozenset[str]) -> None:
    wrong = sorted(sent - allowed)
    if wrong:
        raise ApiError(
            "validation_error", errors=[FieldError(name, NOT_FOR_TYPE[kind]) for name in wrong]
        )


def _required[T](value: T | None, field: str, message: str) -> T:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ApiError("validation_error", errors=[FieldError(field, message)])
    return value


def _checked_url(raw: str) -> httpx.URL:
    try:
        return ssrf.check_url(raw)
    except ssrf.FetchError as error:
        raise ApiError("validation_error", errors=[FieldError("url", error.message)]) from error


async def _knowledge_file(session: AsyncSession, asset_id: uuid.UUID) -> MediaAsset:
    asset = await repo.get_asset(session, asset_id)
    if asset is None:
        raise ApiError(
            "validation_error",
            errors=[FieldError("file_asset_id", "File not found. Upload it again.")],
        )
    fmt = file_format(asset.format, asset.public_id)
    if fmt not in FILE_FORMATS or asset.bytes > MAX_FILE_BYTES:
        raise ApiError("unsupported_media", FILE_FORMATS_COPY)
    return asset


async def _check_quota(
    session: AsyncSession, *, adding: int, exclude: uuid.UUID | None = None
) -> None:
    """402 when ``adding`` characters would pass knowledge_characters, or when a source of
    unknown length (``adding`` 0) is added at the limit."""
    limit = entitlement(await current_plan(session), "knowledge_characters")
    if limit is None:
        return
    used = await repo.characters_used(session, exclude=exclude)
    if used + adding > limit or (adding == 0 and used >= limit):
        raise ApiError(
            "quota_exceeded",
            f"Your plan includes {limit:,} characters of knowledge and {used:,} are in use. "
            "Remove a source or upgrade to add more.",
        )


async def _get_or_404(
    session: AsyncSession, source_id: uuid.UUID, *, for_update: bool = False
) -> SourceRow:
    source = await repo.get_source(session, source_id, for_update=for_update)
    if source is None:
        raise ApiError("not_found")
    return source
