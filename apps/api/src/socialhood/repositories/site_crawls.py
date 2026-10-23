"""Site crawl queries (GR-35): the crawl state of a site source and its pages.

Selects are filtered to the current workspace by the session event (TR-TEN-02); deletes go
through ``scoped_delete``. ``due`` looks across workspaces, so its caller wraps it in
``tenant_bypass_scope`` (jobs/ only, TR-TEN-04).
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Sequence
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.ai import (
    KnowledgeSource,
    SiteCrawl,
    SiteCrawlStatus,
    SitePage,
    SitePageStatus,
)
from socialhood.repositories.base import scoped_delete

# Pages that count against the plan's crawl_pages: the ones a crawl holds or reads.
COUNTED = (SitePageStatus.QUEUED, SitePageStatus.DONE, SitePageStatus.FAILED)


async def get_crawl(
    session: AsyncSession, source_id: uuid.UUID, *, for_update: bool = False
) -> SiteCrawl | None:
    statement = select(SiteCrawl).where(SiteCrawl.source_id == source_id)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return (await session.scalars(statement)).one_or_none()


async def crawls_for(
    session: AsyncSession, source_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, SiteCrawl]:
    if not source_ids:
        return {}
    rows = await session.scalars(select(SiteCrawl).where(SiteCrawl.source_id.in_(source_ids)))
    return {crawl.source_id: crawl for crawl in rows}


async def counts(
    session: AsyncSession, site_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    """Pages of each site by status."""
    if not site_ids:
        return {}
    rows = await session.execute(
        select(SitePage.site_source_id, SitePage.status, func.count())
        .where(SitePage.site_source_id.in_(site_ids))
        .group_by(SitePage.site_source_id, SitePage.status)
    )
    out: dict[uuid.UUID, dict[str, int]] = {}
    for site_id, status, number in rows:
        out.setdefault(site_id, {})[status] = int(number)
    return out


async def chunk_totals(
    session: AsyncSession, site_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int]]:
    """Characters and chunks of the ready pages of each site."""
    if not site_ids:
        return {}
    rows = await session.execute(
        select(
            KnowledgeSource.parent_source_id,
            func.coalesce(func.sum(KnowledgeSource.char_count), 0),
            func.coalesce(func.sum(KnowledgeSource.chunk_count), 0),
        )
        .where(KnowledgeSource.parent_source_id.in_(site_ids), KnowledgeSource.status == "ready")
        .group_by(KnowledgeSource.parent_source_id)
    )
    return {site_id: (int(chars), int(chunks)) for site_id, chars, chunks in rows if site_id}


async def list_pages(
    session: AsyncSession, site_id: uuid.UUID, *, status: str | None, limit: int, offset: int
) -> list[tuple[SitePage, KnowledgeSource | None]]:
    statement = (
        select(SitePage, KnowledgeSource)
        .outerjoin(KnowledgeSource, KnowledgeSource.id == SitePage.source_id)
        .where(SitePage.site_source_id == site_id)
        .order_by(SitePage.depth, SitePage.ordinal)
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        statement = statement.where(SitePage.status == status)
    return [(page, source) for page, source in await session.execute(statement)]


async def count_pages(session: AsyncSession, site_id: uuid.UUID, *, status: str | None) -> int:
    statement = select(func.count()).select_from(SitePage).where(SitePage.site_source_id == site_id)
    if status is not None:
        statement = statement.where(SitePage.status == status)
    return int(await session.scalar(statement) or 0)


async def get_page(
    session: AsyncSession, site_id: uuid.UUID, page_id: uuid.UUID, *, for_update: bool = False
) -> SitePage | None:
    statement = select(SitePage).where(SitePage.id == page_id, SitePage.site_source_id == site_id)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return (await session.scalars(statement)).one_or_none()


async def all_pages(session: AsyncSession, site_id: uuid.UUID) -> list[SitePage]:
    rows = await session.scalars(
        select(SitePage).where(SitePage.site_source_id == site_id).order_by(SitePage.ordinal)
    )
    return list(rows)


async def next_queued(session: AsyncSession, site_id: uuid.UUID) -> SitePage | None:
    """The page to read next: shallowest first, then in the order found (breadth first)."""
    return (
        await session.scalars(
            select(SitePage)
            .where(SitePage.site_source_id == site_id, SitePage.status == SitePageStatus.QUEUED)
            .order_by(SitePage.depth, SitePage.ordinal)
            .limit(1)
        )
    ).one_or_none()


async def counted_pages(session: AsyncSession, site_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(SitePage)
            .where(SitePage.site_source_id == site_id, SitePage.status.in_(COUNTED))
        )
        or 0
    )


async def next_ordinal(session: AsyncSession, site_id: uuid.UUID) -> int:
    top = await session.scalar(
        select(func.max(SitePage.ordinal)).where(SitePage.site_source_id == site_id)
    )
    return int(top or 0) + 1


async def known_urls(
    session: AsyncSession, site_id: uuid.UUID, urls: Sequence[str]
) -> dict[str, SitePage]:
    if not urls:
        return {}
    rows = await session.scalars(
        select(SitePage).where(SitePage.site_source_id == site_id, SitePage.url.in_(urls))
    )
    return {page.url: page for page in rows}


async def delete_child_source(session: AsyncSession, source_id: uuid.UUID) -> None:
    """A page's knowledge source and, by the cascade, its chunks."""
    await session.execute(scoped_delete(KnowledgeSource, id=source_id))


async def due(
    session: AsyncSession, *, now: datetime, lost_before: datetime, limit: int
) -> list[SiteCrawl]:
    """Crawls to start: finished ones whose next_crawl_at has come (re-crawl on), and queued or
    running ones that haven't moved since ``lost_before`` (a lost job). Locked, skipping rows
    another run holds."""
    waiting = (SiteCrawlStatus.IDLE, SiteCrawlStatus.DONE, SiteCrawlStatus.FAILED)
    rows = await session.scalars(
        select(SiteCrawl)
        .where(
            or_(
                (SiteCrawl.recrawl == "weekly")
                & SiteCrawl.status.in_(waiting)
                & (SiteCrawl.next_crawl_at <= now),
                SiteCrawl.status.in_((SiteCrawlStatus.QUEUED, SiteCrawlStatus.RUNNING))
                & (SiteCrawl.updated_at < lost_before),
            )
        )
        .order_by(SiteCrawl.next_crawl_at.nulls_last())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(rows)
