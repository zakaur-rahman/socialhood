"""Site sources (GR-35): a whole website as knowledge, read page by page by a crawl.

A site source is a knowledge source of type ``site`` with a ``site_crawls`` row (the re-crawl
setting, the excluded paths, where the crawl is). Its pages are ``site_pages`` rows, and each page
that has readable text is a knowledge source of its own (type ``page``, ``parent_source_id`` the
site): the same job chunks and embeds it, retrieval finds it, and deleting the site deletes the
pages. Pages are listed under their site, never in the main list.

What the owner can do here, none of it fetching anything (the crawl itself is crawl.py):

- add a site (``create``): the start address (checked like a web page's, SEC-09), a title and the
  re-crawl setting, ``weekly`` or ``off``. A crawl is queued once the caller has committed;
- crawl again now (``request_crawl``, also ``reingest`` in an edit): one crawl at a time, so a
  request while one is queued or running changes nothing;
- change the re-crawl setting or the excluded paths (``patch``): excluding a path removes its
  pages and their knowledge at once and keeps a crawl from adding them back;
- remove one page (``remove_page``): its knowledge goes and a crawl doesn't add it back.

The site source's ``version`` numbers its crawls: each request adds 1 and the crawl job for an
older number is dropped. Its ``status`` follows the crawl (pending and processing while it
runs, ready, or failed with the reason). It counts no characters itself; its pages do.

Nothing here commits.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.ai import (
    KnowledgeSource as SourceRow,
)
from socialhood.models.ai import (
    KnowledgeStatus,
    SiteCrawl,
    SiteCrawlStatus,
    SitePage,
    SitePageStatus,
)
from socialhood.observability.logging import get_logger
from socialhood.repositories import knowledge as kb_repo
from socialhood.repositories import site_crawls as repo
from socialhood.schemas.knowledge import (
    MAX_EXCLUDED_PATHS,
    KnowledgeSourcePatch,
    SiteCrawlInfo,
    SitePageList,
)
from socialhood.schemas.knowledge import SitePage as SitePageOut
from socialhood.services.knowledge import crawl_rules

log = get_logger(__name__)

RECRAWL_EVERY = {"weekly": timedelta(days=7)}  # a setting not here (off) is never crawled again
DEFAULT_RECRAWL = "weekly"
LOST_AFTER = timedelta(minutes=30)  # a queued or running crawl that hasn't moved this long
ALREADY_CRAWLING = "This site is being crawled now."
NOT_A_SITE = "This isn't a website source."


# ---------------------------------------------------------------- reads


async def info(session: AsyncSession, source: SourceRow) -> SiteCrawlInfo | None:
    crawl = await repo.get_crawl(session, source.id)
    if crawl is None:
        return None
    counts = (await repo.counts(session, [source.id])).get(source.id, {})
    totals = (await repo.chunk_totals(session, [source.id])).get(source.id, (0, 0))
    return site_info(crawl, counts, totals)


def site_info(
    crawl: SiteCrawl, counts: dict[str, int], totals: tuple[int, int] = (0, 0)
) -> SiteCrawlInfo:
    def n(*statuses: SitePageStatus) -> int:
        return sum(counts.get(status, 0) for status in statuses)

    return SiteCrawlInfo(
        status=crawl.status,
        recrawl=crawl.recrawl,
        excluded_paths=list(crawl.excluded_paths),
        pages_found=n(*repo.COUNTED),
        pages_done=n(SitePageStatus.DONE),
        pages_failed=n(SitePageStatus.FAILED),
        pages_skipped=n(SitePageStatus.SKIPPED),
        char_count=totals[0],
        chunk_count=totals[1],
        page_cap=crawl.page_cap,
        truncated=crawl.truncated,
        error=crawl.error,
        started_at=crawl.started_at,
        finished_at=crawl.finished_at,
        next_crawl_at=crawl.next_crawl_at,
    )


async def infos(session: AsyncSession, sources: list[SourceRow]) -> dict[uuid.UUID, SiteCrawlInfo]:
    """The crawl info of each site among ``sources``, in two queries."""
    ids = [source.id for source in sources if source.type == "site"]
    crawls = await repo.crawls_for(session, ids)
    counts = await repo.counts(session, ids)
    totals = await repo.chunk_totals(session, ids)
    return {
        sid: site_info(crawl, counts.get(sid, {}), totals.get(sid, (0, 0)))
        for sid, crawl in crawls.items()
    }


async def list_pages(
    session: AsyncSession, source_id: uuid.UUID, *, status: str | None, limit: int, offset: int
) -> SitePageList:
    await site_or_404(session, source_id)
    rows = await repo.list_pages(session, source_id, status=status, limit=limit, offset=offset)
    return SitePageList(
        items=[_page_out(page, source) for page, source in rows],
        total=await repo.count_pages(session, source_id, status=status),
    )


def _page_out(page: SitePage, source: SourceRow | None) -> SitePageOut:
    # A page the crawl read but whose knowledge failed to build shows the build's reason.
    status, error = page.status, page.error
    if source is not None and source.status == KnowledgeStatus.FAILED and status == "done":
        status, error = "failed", source.error
    return SitePageOut(
        id=page.id,
        url=page.url,
        title=page.title,
        status=status,
        error=error,
        ingest_status=source.status if source is not None else None,
        char_count=source.char_count if source is not None else 0,
        chunk_count=source.chunk_count if source is not None else 0,
        last_crawled_at=page.last_crawled_at,
    )


# ---------------------------------------------------------------- writes


async def start(session: AsyncSession, source: SourceRow, *, recrawl: str | None) -> SiteCrawl:
    """The crawl row of a new site source, with its first crawl queued (version 1)."""
    crawl = SiteCrawl(
        source_id=source.id,
        recrawl=recrawl or DEFAULT_RECRAWL,
        status=SiteCrawlStatus.QUEUED,
        page_cap=await page_cap(session),
        seeded=False,
    )
    session.add(crawl)
    await session.flush()
    await session.refresh(crawl)
    return crawl


async def page_cap(session: AsyncSession) -> int:
    """The plan's pages for one crawl (crawl_pages)."""
    return int(entitlement(await current_plan(session), "crawl_pages"))


async def request_crawl(
    session: AsyncSession, source: SourceRow, *, now: datetime | None = None
) -> bool:
    """Queue a crawl of the site: the source gets the next version and the crawl row is reset.
    False (nothing changed) while a crawl is queued or running. The caller commits, then
    enqueues with ``sources.enqueue_ingest``."""
    now = now or datetime.now(UTC)
    crawl = await repo.get_crawl(session, source.id, for_update=True)
    if crawl is None:
        raise ApiError("not_found")
    if crawl.status in (SiteCrawlStatus.QUEUED, SiteCrawlStatus.RUNNING):
        return False
    source.version += 1
    source.status = KnowledgeStatus.PENDING
    source.error = None
    crawl.status = SiteCrawlStatus.QUEUED
    crawl.seeded = False
    crawl.truncated = False
    crawl.error = None
    crawl.page_cap = await page_cap(session)
    crawl.started_at = None
    crawl.finished_at = None
    crawl.next_crawl_at = None
    crawl.updated_at = now
    await session.flush()
    await session.refresh(source)
    return True


async def patch(
    session: AsyncSession, source: SourceRow, body: KnowledgeSourcePatch
) -> tuple[SourceRow, bool]:
    """Apply an edit to a site source; True when a crawl was queued (``reingest``)."""
    crawl = await repo.get_crawl(session, source.id, for_update=True)
    if crawl is None:
        raise ApiError("not_found")
    if body.title:
        source.title = body.title.strip()[:120]
    if body.recrawl is not None and body.recrawl != crawl.recrawl:
        crawl.recrawl = body.recrawl
        crawl.next_crawl_at = next_crawl_at(crawl)
    if body.excluded_paths is not None:
        await _set_excluded(session, source, crawl, body.excluded_paths)
    await session.flush()
    queued = await request_crawl(session, source) if body.reingest else False
    await session.refresh(source)
    return source, queued


async def exclude_path(session: AsyncSession, source_id: uuid.UUID, path: str) -> SourceRow:
    """Add a path to the excluded ones; its pages and their knowledge go now."""
    source = await site_or_404(session, source_id)
    crawl = await repo.get_crawl(session, source_id, for_update=True)
    if crawl is None:
        raise ApiError("not_found")
    await _set_excluded(session, source, crawl, [*crawl.excluded_paths, path])
    await session.flush()
    return source


async def remove_page(session: AsyncSession, source_id: uuid.UUID, page_id: uuid.UUID) -> None:
    """The page's knowledge goes; later crawls skip the address."""
    await site_or_404(session, source_id)
    page = await repo.get_page(session, source_id, page_id, for_update=True)
    if page is None:
        raise ApiError("not_found")
    await drop_page(session, page, SitePageStatus.REMOVED)
    await session.flush()


async def drop_page(session: AsyncSession, page: SitePage, status: SitePageStatus) -> None:
    """Take a page out of knowledge: its source (and chunks) go; the row keeps ``status``."""
    if page.source_id is not None:
        await repo.delete_child_source(session, page.source_id)
    page.source_id = None
    page.status = status
    page.error = None
    page.content_hash = None
    page.etag = None
    page.last_modified = None


def next_crawl_at(crawl: SiteCrawl, now: datetime | None = None) -> datetime | None:
    """When the crawl that just finished is due again (None: never, the re-crawl is off)."""
    every = RECRAWL_EVERY.get(crawl.recrawl)
    return (now or datetime.now(UTC)) + every if every else None


async def _set_excluded(
    session: AsyncSession, source: SourceRow, crawl: SiteCrawl, paths: list[str]
) -> None:
    prefixes: list[str] = []
    for raw in paths:
        prefix = crawl_rules.clean_prefix(raw)
        if prefix is None:
            raise ApiError(
                "validation_error",
                errors=[FieldError("excluded_paths", "Enter a path such as /blog.")],
            )
        if prefix not in prefixes:
            prefixes.append(prefix)
    if len(prefixes) > MAX_EXCLUDED_PATHS:
        raise ApiError(
            "validation_error",
            errors=[FieldError("excluded_paths", f"Exclude at most {MAX_EXCLUDED_PATHS} paths.")],
        )
    crawl.excluded_paths = prefixes
    for page in await repo.all_pages(session, source.id):
        if page.status not in (SitePageStatus.REMOVED, SitePageStatus.EXCLUDED) and (
            crawl_rules.excluded(page.url, prefixes)
        ):
            await drop_page(session, page, SitePageStatus.EXCLUDED)


async def site_or_404(session: AsyncSession, source_id: uuid.UUID) -> SourceRow:
    source = await kb_repo.get_source(session, source_id)
    if source is None or source.type != "site":
        raise ApiError("not_found")
    return source
