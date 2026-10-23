"""The crawl_site job's work (GR-35; SEC-09): read a whole website into knowledge, page by page.

One crawl of one site source (its ``version`` numbers the crawl; see sites.py). In steps, each
safe to run again, so a crawl that is interrupted carries on where it stopped:

1. begin: lock the crawl, check the version, mark it ``running``;
2. robots.txt of the start address's site (our group, or ``*``): a missing file allows everything,
   one that can't be read fails the crawl;
3. seed, once per crawl: the start address, then every address of the site's sitemaps (the
   ``Sitemap:`` lines of robots.txt and /sitemap.xml, sitemap indexes followed, at most 20 files),
   added to ``site_pages`` up to the plan's page cap (``crawl_pages``). Pages the last crawl knew
   are queued to be checked again; pages the owner removed or excluded stay out;
4. read the queue breadth first (the shallowest page, then in the order found), one page at a time
   with a pause between pages (1 s, or the site's Crawl-delay up to 10 s): fetch it (conditional
   when we hold its ETag or Last-Modified), take its main text, and add the same-site links it
   holds. A page that answers 404 or 410 is gone and its knowledge removed; one that is
   disallowed, noindex, not HTML or another site is skipped; one that fails is marked failed and
   the crawl goes on. A page whose text is new or changed gets its own knowledge source (type
   ``page``) with the next version, which the existing ingest job chunks and embeds; an unchanged
   one (304, or the same text hash) is left alone;
5. finish: the crawl is ``done`` (``failed`` when no page could be read), the site source ``ready``,
   and the next crawl is due in a week when the site re-crawls weekly.

Every address is fetched by ssrf.fetch_document, so private addresses, redirects to them and
oversized or wrong-type answers are refused whatever the page, link or sitemap says. No
transaction is open while the network is awaited. After ``budget_s`` the job stops with "more" and
the task queues the rest as a new job. An edit or delete of the site during a crawl wins: the job
finds the version changed (or the row gone) and stops.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.models.ai import KnowledgeSource as SourceRow
from socialhood.models.ai import (
    KnowledgeStatus,
    KnowledgeType,
    SiteCrawl,
    SiteCrawlStatus,
    SitePage,
    SitePageStatus,
)
from socialhood.observability.logging import get_logger
from socialhood.repositories import knowledge as kb_repo
from socialhood.repositories import site_crawls as repo
from socialhood.security import ssrf
from socialhood.services.knowledge import crawl_rules, extract, sites
from socialhood.services.knowledge.crawl_rules import Robots
from socialhood.services.knowledge.sources import enqueue_job, short_title, url_title

log = get_logger(__name__)

POLITE_DELAY_S = 1.0  # between two requests to the site
MAX_DELAY_S = 10.0  # the longest Crawl-delay we honour
RUN_BUDGET_S = 240.0  # one job reads pages for this long, then queues the rest
MAX_DEPTH = 6  # links followed from the start page
PAGE_TEXT_CHARS = 20_000  # a page's text kept (knowledge_sources.body)
ROBOTS_BYTES = 512 * 1024
SITEMAP_BYTES = 5 * 1024 * 1024
MAX_SITEMAP_FILES = 20
ROBOTS_TIMEOUT_S = 10.0
TEXT_TYPES = frozenset({"text/plain"})
XML_TYPES = frozenset({"application/xml", "text/xml", "text/plain", "application/rss+xml"})
XML_ACCEPT = "application/xml,text/xml;q=0.9,text/plain;q=0.8,*/*;q=0.1"
TEXT_ACCEPT = "text/plain,*/*;q=0.1"

START_BLOCKED = "robots.txt on this site doesn't let us read it."
NOTHING_READ = "Couldn't read any page of this site."
ROBOTS_FAILED = "Couldn't read this site's robots.txt just now. Try again in a few minutes."
CRASHED = "Couldn't crawl this site. Try again in a few minutes."

CrawlOutcome = Literal["done", "failed", "more", "stale"]
Sleep = Callable[[float], Awaitable[None]]


class _Abort(Exception):
    """The crawl can't go on; ``reason`` is shown on the site."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class _Site:
    start_url: str
    excluded: list[str]
    seeded: bool
    cap: int
    created_by: uuid.UUID | None
    allow_private: bool = False  # development and e2e only (settings.crawl_allow_private)


@dataclass(frozen=True)
class _Todo:
    page_id: uuid.UUID
    url: str
    depth: int
    etag: str | None
    last_modified: str | None
    has_text: bool  # we hold this page's knowledge: a conditional request can be answered 304


@dataclass
class _Read:
    """What fetching one page found."""

    kind: Literal["skipped", "gone", "failed", "unchanged", "read"]
    message: str | None = None
    final_url: str | None = None
    text: str = ""
    title: str | None = None
    text_hash: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    links: list[str] = field(default_factory=list)


async def run_crawl(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    version: int,
    will_retry: bool = False,
    allow_private: bool = False,
    delay_s: float = POLITE_DELAY_S,
    budget_s: float = RUN_BUDGET_S,
    sleep: Sleep = asyncio.sleep,
) -> CrawlOutcome:
    """Run (or carry on) the crawl numbered ``version``; "more" when the budget ran out."""
    with workspace_scope(workspace_id):
        site = await _begin(sessionmaker, source_id, version, allow_private)
        if site is None:
            return "stale"
        try:
            return await _crawl(
                sessionmaker, workspace_id, source_id, version, site, delay_s, budget_s, sleep
            )
        except _Abort as abort:
            return await _finish(sessionmaker, source_id, version, failure=abort.reason)
        except Exception:
            if will_retry:
                raise
            log.exception("site_crawl_crashed", source_id=str(source_id))
            return await _finish(sessionmaker, source_id, version, failure=CRASHED)


async def _crawl(
    sessionmaker: async_sessionmaker[AsyncSession],
    workspace_id: uuid.UUID,
    source_id: uuid.UUID,
    version: int,
    site: _Site,
    delay_s: float,
    budget_s: float,
    sleep: Sleep,
) -> CrawlOutcome:
    loop = asyncio.get_running_loop()
    started = loop.time()
    robots = await _robots(site.start_url, site.allow_private)
    delay = max(delay_s, min(robots.crawl_delay_s or 0.0, MAX_DELAY_S)) if delay_s else 0.0
    if not site.seeded:
        if not robots.allows(site.start_url):
            raise _Abort(START_BLOCKED)
        found = await _sitemap_pages(site, robots, delay, sleep)
        if not await _seed(sessionmaker, source_id, version, site, robots, found):
            return "stale"
    first = True
    while True:
        outcome, todo = await _next(sessionmaker, source_id, version)
        if outcome == "stale":
            return "stale"
        if todo is None:
            return await _finish(sessionmaker, source_id, version)
        if loop.time() - started > budget_s:
            return "more"
        if not first:
            await sleep(delay)
        first = False
        read = await _read_page(todo, site, robots, delay, sleep)
        queued = await _record(sessionmaker, source_id, version, todo, site, robots, read)
        if queued is None:
            return "stale"
        for child_id, child_version in queued:
            await enqueue_job(workspace_id, child_id, child_version, KnowledgeType.PAGE)


# ---------------------------------------------------------------- begin and finish


async def _begin(
    sessionmaker: async_sessionmaker[AsyncSession],
    source_id: uuid.UUID,
    version: int,
    allow_private: bool,
) -> _Site | None:
    async with sessionmaker() as session:
        live = await _live(session, source_id, version, starting=True)
        if live is None:
            return None
        source, crawl = live
        now = datetime.now(UTC)
        crawl.status = SiteCrawlStatus.RUNNING
        crawl.started_at = crawl.started_at or now
        crawl.updated_at = now
        source.status = KnowledgeStatus.PROCESSING
        site = _Site(
            start_url=source.url or "",
            excluded=list(crawl.excluded_paths),
            seeded=crawl.seeded,
            cap=crawl.page_cap,
            created_by=source.created_by_user_id,
            allow_private=allow_private,
        )
        await session.commit()
        return site


async def _live(
    session: AsyncSession, source_id: uuid.UUID, version: int, *, starting: bool = False
) -> tuple[SourceRow, SiteCrawl] | None:
    """The locked site and crawl rows when this job's crawl is still the current one."""
    source = await kb_repo.get_source(session, source_id, for_update=True)
    if source is None or source.version != version or source.type != KnowledgeType.SITE:
        return None
    crawl = await repo.get_crawl(session, source_id, for_update=True)
    if crawl is None:
        return None
    allowed = (
        (SiteCrawlStatus.QUEUED, SiteCrawlStatus.RUNNING)
        if starting
        else (SiteCrawlStatus.RUNNING,)
    )
    return (source, crawl) if crawl.status in allowed else None


async def _finish(
    sessionmaker: async_sessionmaker[AsyncSession],
    source_id: uuid.UUID,
    version: int,
    *,
    failure: str | None = None,
) -> CrawlOutcome:
    async with sessionmaker() as session:
        live = await _live(session, source_id, version)
        if live is None:
            return "stale"
        source, crawl = live
        counts = (await repo.counts(session, [source_id])).get(source_id, {})
        if failure is None and counts.get(SitePageStatus.DONE, 0) == 0:
            failure = await _first_error(session, source_id) or NOTHING_READ
        now = datetime.now(UTC)
        crawl.finished_at = now
        crawl.updated_at = now
        crawl.next_crawl_at = sites.next_crawl_at(crawl, now)
        crawl.error = failure
        crawl.status = SiteCrawlStatus.FAILED if failure else SiteCrawlStatus.DONE
        source.status = KnowledgeStatus.FAILED if failure else KnowledgeStatus.READY
        source.error = failure
        if failure is None:
            source.last_ingested_at = now
        await session.commit()
    log.info(
        "site_crawled",
        source_id=str(source_id),
        version=version,
        pages_done=counts.get(SitePageStatus.DONE, 0),
        pages_failed=counts.get(SitePageStatus.FAILED, 0),
        failed=failure is not None,
    )
    return "failed" if failure else "done"


async def _first_error(session: AsyncSession, source_id: uuid.UUID) -> str | None:
    for page, _ in await repo.list_pages(session, source_id, status=None, limit=1, offset=0):
        return page.error
    return None


# ---------------------------------------------------------------- robots.txt and sitemaps


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


async def _robots(start_url: str, allow_private: bool = False) -> Robots:
    try:
        page = await ssrf.fetch_document(
            f"{_origin(start_url)}/robots.txt",
            types=TEXT_TYPES,
            accept=TEXT_ACCEPT,
            max_bytes=ROBOTS_BYTES,
            timeout_s=ROBOTS_TIMEOUT_S,
            allow_private=allow_private,
        )
    except ssrf.FetchError as error:
        if error.code in ("http_error", "not_html", "too_large") and not error.retryable:
            return crawl_rules.ALLOW_ALL  # no robots.txt (RFC 9309: a 4xx means no rules)
        log.info("site_robots_unavailable", http_status=error.status, reason=error.code)
        raise _Abort(ROBOTS_FAILED if error.retryable else error.message) from error
    return crawl_rules.parse_robots(page.content.decode("utf-8-sig", errors="replace"))


async def _sitemap_pages(site: _Site, robots: Robots, delay: float, sleep: Sleep) -> list[str]:
    """The same-site page addresses the site's sitemaps list: at most the cap plus one."""
    queue = list(dict.fromkeys([*robots.sitemaps, f"{_origin(site.start_url)}/sitemap.xml"]))
    pages: dict[str, None] = {}
    fetched = 0
    while queue and fetched < MAX_SITEMAP_FILES and len(pages) <= site.cap:
        address = queue.pop(0)
        if fetched:
            await sleep(delay)
        fetched += 1
        try:
            document = await ssrf.fetch_document(
                address,
                types=XML_TYPES,
                accept=XML_ACCEPT,
                max_bytes=SITEMAP_BYTES,
                timeout_s=ROBOTS_TIMEOUT_S,
                allow_private=site.allow_private,
            )
        except ssrf.FetchError as error:
            log.info("site_sitemap_unavailable", http_status=error.status, reason=error.code)
            continue
        sitemap = crawl_rules.sitemap_urls(document.content)
        if sitemap.is_index:
            queue.extend(url for url in sitemap.urls if url not in queue)
            continue
        for raw in sitemap.urls:
            url = crawl_rules.normalise(raw)
            if url and _wanted(url, site, robots):
                pages.setdefault(url)
    return list(pages)


def _wanted(url: str, site: _Site, robots: Robots) -> bool:
    return (
        crawl_rules.same_site(url, site.start_url)
        and crawl_rules.is_page_address(url)
        and not crawl_rules.excluded(url, site.excluded)
        and robots.allows(url)
    )


# ---------------------------------------------------------------- the queue


async def _seed(
    sessionmaker: async_sessionmaker[AsyncSession],
    source_id: uuid.UUID,
    version: int,
    site: _Site,
    robots: Robots,
    found: list[str],
) -> bool:
    async with sessionmaker() as session:
        live = await _live(session, source_id, version)
        if live is None:
            return False
        _, crawl = live
        for page in await repo.all_pages(session, source_id):
            again = page.status in (
                SitePageStatus.DONE,
                SitePageStatus.FAILED,
                SitePageStatus.SKIPPED,
            )
            freed = page.status == SitePageStatus.EXCLUDED and not crawl_rules.excluded(
                page.url, site.excluded
            )
            if again or freed:
                page.status = SitePageStatus.QUEUED
        start = crawl_rules.normalise(site.start_url)
        if start is not None:
            await _add_pages(session, crawl, source_id, site, robots, [start], depth=0)
        await _add_pages(session, crawl, source_id, site, robots, found, depth=1)
        crawl.seeded = True
        crawl.updated_at = datetime.now(UTC)
        await session.commit()
        return True


async def _add_pages(
    session: AsyncSession,
    crawl: SiteCrawl,
    source_id: uuid.UUID,
    site: _Site,
    robots: Robots,
    urls: list[str],
    *,
    depth: int,
) -> None:
    """Add the addresses that are new (or gone in an earlier crawl and listed again) while there
    is room under the cap; setting ``truncated`` when some had to be left out."""
    wanted = [url for url in dict.fromkeys(urls) if _wanted(url, site, robots)]
    known = await repo.known_urls(session, source_id, wanted)
    room = crawl.page_cap - await repo.counted_pages(session, source_id)
    ordinal = await repo.next_ordinal(session, source_id)
    for url in wanted:
        page = known.get(url)
        if page is not None and not _came_back(page, crawl):
            continue  # known: queued, read, skipped, excluded or removed
        if room <= 0:
            crawl.truncated = True
            continue
        room -= 1
        if page is not None:
            page.status = SitePageStatus.QUEUED
            page.error = None
            continue
        session.add(
            SitePage(
                site_source_id=source_id,
                url=url,
                ordinal=ordinal,
                depth=depth,
                status=SitePageStatus.QUEUED,
            )
        )
        ordinal += 1
    await session.flush()


def _came_back(page: SitePage, crawl: SiteCrawl) -> bool:
    """A page found gone by an earlier crawl is read again when it is listed or linked again; one
    found gone by this crawl is not (a broken link on several pages is asked about once)."""
    if page.status != SitePageStatus.GONE:
        return False
    return (
        page.last_crawled_at is None
        or crawl.started_at is None
        or page.last_crawled_at < crawl.started_at
    )


async def _next(
    sessionmaker: async_sessionmaker[AsyncSession], source_id: uuid.UUID, version: int
) -> tuple[Literal["stale", "ok"], _Todo | None]:
    async with sessionmaker() as session:
        live = await _live(session, source_id, version)
        if live is None:
            return "stale", None
        page = await repo.next_queued(session, source_id)
        if page is None:
            return "ok", None
        return "ok", _Todo(
            page_id=page.id,
            url=page.url,
            depth=page.depth,
            etag=page.etag,
            last_modified=page.last_modified,
            has_text=page.source_id is not None and page.content_hash is not None,
        )


# ---------------------------------------------------------------- one page


async def _read_page(todo: _Todo, site: _Site, robots: Robots, delay: float, sleep: Sleep) -> _Read:
    if crawl_rules.excluded(todo.url, site.excluded):
        return _Read("skipped", "Under a path you excluded.")
    if not robots.allows(todo.url):
        return _Read("skipped", "robots.txt asks crawlers to stay away from this page.")
    headers: dict[str, str] = {}
    if todo.has_text and todo.etag:
        headers["If-None-Match"] = todo.etag
    if todo.has_text and todo.last_modified:
        headers["If-Modified-Since"] = todo.last_modified
    page: ssrf.Page | None = None
    for attempt in range(2):
        try:
            page = await ssrf.fetch_document(
                todo.url,
                headers=headers,
                not_modified=True,
                allow_private=site.allow_private,
            )
            break
        except ssrf.FetchError as error:
            if error.status in (404, 410):
                return _Read("gone", f"Not found ({error.status}).")
            if error.code == "not_html":
                return _Read("skipped", "Not a web page.")
            if error.retryable and attempt == 0:
                await sleep(max(delay, 1.0) * 2)
                continue
            return _Read("failed", error.message)
    if page is None:  # pragma: no cover - the loop returns or breaks
        return _Read("failed", CRASHED)
    if page.status == 304:
        return _Read(
            "unchanged", final_url=todo.url, etag=todo.etag, last_modified=todo.last_modified
        )
    final = crawl_rules.normalise(page.url) or todo.url
    if not crawl_rules.same_site(final, site.start_url):
        return _Read("skipped", "Redirects to another website.", final_url=final)
    links = crawl_rules.page_links(page.content, final)
    if links.noindex:
        return _Read("skipped", "The page asks not to be indexed.", final_url=final)
    follow = [] if links.nofollow or todo.depth >= MAX_DEPTH else links.urls
    try:
        web = await asyncio.to_thread(extract.web_page, page.content, final)
    except extract.ExtractError as error:
        return _Read("failed", error.reason, final_url=final, links=follow)
    text = web.text[:PAGE_TEXT_CHARS]
    return _Read(
        "read",
        final_url=final,
        text=text,
        title=web.title,
        text_hash=crawl_rules.content_hash(text),
        etag=page.etag,
        last_modified=page.last_modified,
        links=follow,
    )


async def _record(
    sessionmaker: async_sessionmaker[AsyncSession],
    source_id: uuid.UUID,
    version: int,
    todo: _Todo,
    site: _Site,
    robots: Robots,
    read: _Read,
) -> list[tuple[uuid.UUID, int]] | None:
    """Store what the page gave, in one transaction; the page-sources to ingest, or None when the
    crawl is no longer current. A page the owner removed meanwhile is left as it is."""
    async with sessionmaker() as session:
        live = await _live(session, source_id, version)
        if live is None:
            return None
        parent, crawl = live
        page = await repo.get_page(session, source_id, todo.page_id, for_update=True)
        if page is None or page.status != SitePageStatus.QUEUED:
            return []
        now = datetime.now(UTC)
        queued: list[tuple[uuid.UUID, int]] = []
        page.last_crawled_at = now
        crawl.updated_at = now
        if read.kind in ("read", "failed") and read.final_url and read.final_url != page.url:
            # The page redirected within the site: it is stored under the address it ended at,
            # or, when that address has a row already, skipped as its duplicate.
            other = (await repo.known_urls(session, source_id, [read.final_url])).get(
                read.final_url
            )
            if other is None:
                page.url = read.final_url
            else:
                read = _Read("skipped", "The same page as another address.", links=read.links)
        if read.kind == "skipped":
            await sites.drop_page(session, page, SitePageStatus.SKIPPED)
            page.error = read.message
        elif read.kind == "gone":
            await sites.drop_page(session, page, SitePageStatus.GONE)
            page.error = read.message
        elif read.kind == "failed":
            page.status = SitePageStatus.FAILED  # its earlier knowledge, if any, stays
            page.error = read.message
        else:
            queued = await _store_page(session, parent, page, read)
        await _add_pages(session, crawl, source_id, site, robots, read.links, depth=todo.depth + 1)
        await session.commit()
        return queued


async def _store_page(
    session: AsyncSession, parent: SourceRow, page: SitePage, read: _Read
) -> list[tuple[uuid.UUID, int]]:
    """A read (or unchanged) page becomes done; new or changed text goes to a page-source."""
    page.status = SitePageStatus.DONE
    page.error = None
    page.etag = read.etag or page.etag
    page.last_modified = read.last_modified or page.last_modified
    child = (
        await kb_repo.get_source(session, page.source_id, for_update=True)
        if page.source_id
        else None
    )
    if read.kind == "unchanged":
        return _retry_unfinished(child)
    if child is not None and page.content_hash == read.text_hash:
        return _retry_unfinished(child)
    title = (
        short_title(read.title) if read.title else url_title(httpx.URL(read.final_url or page.url))
    )
    if child is None:
        child = SourceRow(
            type=KnowledgeType.PAGE,
            parent_source_id=parent.id,
            title=title,
            url=read.final_url or page.url,
            created_by_user_id=parent.created_by_user_id,
        )
        session.add(child)
    else:
        child.version += 1
        child.title = title
        child.url = read.final_url or page.url
    child.body = read.text
    child.status = KnowledgeStatus.PENDING
    child.error = None
    await session.flush()
    await session.refresh(child)
    page.source_id = child.id
    page.title = title
    page.content_hash = read.text_hash
    return [(child.id, child.version)]


def _retry_unfinished(child: SourceRow | None) -> list[tuple[uuid.UUID, int]]:
    """An unchanged page whose last ingest never ran is queued again (the job is idempotent), and
    one whose ingest failed (over the knowledge limit, say) gets a new version to try again."""
    if child is None:
        return []
    if child.status == KnowledgeStatus.FAILED:
        child.version += 1
        child.status = KnowledgeStatus.PENDING
        child.error = None
        return [(child.id, child.version)]
    if child.status == KnowledgeStatus.PENDING:
        return [(child.id, child.version)]
    return []
