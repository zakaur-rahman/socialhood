"""ingest_knowledge_source(id, version) (T5.3; TR-AI-08, job catalogue: bulk lane, queueing lock
kb:{id}:{version}, 3 tries).

Thin: it takes a per-workspace bulk slot (TR-JOB-06; without one it defers a fresh copy 5 s later,
which does not use up its tries) and runs services/knowledge/ingest.py. The service raises only
while the job has tries left, so a source is marked failed on its final attempt, never before a
retry (TR-JOB-04).

crawl_site(id, version) (GR-35: bulk lane, queueing lock crawl:{id}:{version}, run lock
crawl:{id} so one crawl of a site runs at a time, 3 tries) reads one site's pages
(services/knowledge/crawl.py) for about four minutes at a time and queues itself again for the
rest, so a long crawl never holds a worker. dispatch_site_recrawls (hourly) starts the crawls that
are due, and queues again a crawl whose job was lost.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from procrastinate import JobContext
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.fairness import BulkSemaphore, run_with_bulk_slot
from socialhood.jobs.retry import BackoffRetry
from socialhood.jobs.runtime import runtime
from socialhood.models.ai import KnowledgeType
from socialhood.observability.logging import get_logger
from socialhood.repositories import knowledge as kb_repo
from socialhood.repositories import site_crawls
from socialhood.services.knowledge import crawl, ingest, sites
from socialhood.services.knowledge.sources import enqueue_job

log = get_logger(__name__)

INGEST_RETRY = BackoffRetry(max_attempts=3)


@app.task(name="ingest_knowledge_source", queue=BULK, retry=INGEST_RETRY, pass_context=True)
async def ingest_knowledge_source(
    context: JobContext, workspace_id: str, source_id: str, version: int
) -> None:
    rt = runtime()
    will_retry = int(context.job.attempts) + 1 < INGEST_RETRY.max_attempts

    async def work() -> None:
        await ingest.ingest_source(
            rt.sessionmaker,
            rt.http,
            workspace_id=uuid.UUID(workspace_id),
            source_id=uuid.UUID(source_id),
            version=int(version),
            will_retry=will_retry,
        )

    async def requeue(delay_s: float) -> None:
        await enqueue(
            ingest_knowledge_source,
            key=f"kb:{source_id}:{version}",
            delay_s=delay_s,
            workspace_id=workspace_id,
            source_id=source_id,
            version=version,
        )

    semaphore = BulkSemaphore(rt.redis, rt.settings.bulk_concurrency_per_workspace)
    await run_with_bulk_slot(semaphore, workspace_id, work, requeue)


CRAWL_RETRY = BackoffRetry(max_attempts=3)
RECRAWL_BATCH = 50


@app.task(name="crawl_site", queue=BULK, retry=CRAWL_RETRY, pass_context=True)
async def crawl_site(context: JobContext, workspace_id: str, source_id: str, version: int) -> None:
    rt = runtime()
    will_retry = int(context.job.attempts) + 1 < CRAWL_RETRY.max_attempts

    async def work() -> None:
        outcome = await crawl.run_crawl(
            rt.sessionmaker,
            workspace_id=uuid.UUID(workspace_id),
            source_id=uuid.UUID(source_id),
            version=int(version),
            will_retry=will_retry,
            allow_private=rt.settings.crawl_allow_private,
        )
        if outcome == "more":  # the budget ran out: the rest is a new job
            await enqueue_job(
                uuid.UUID(workspace_id), uuid.UUID(source_id), int(version), KnowledgeType.SITE
            )

    async def requeue(delay_s: float) -> None:
        await enqueue(
            crawl_site,
            key=f"crawl:{source_id}:{version}",
            lock=f"crawl:{source_id}",
            delay_s=delay_s,
            workspace_id=workspace_id,
            source_id=source_id,
            version=version,
        )

    semaphore = BulkSemaphore(rt.redis, rt.settings.bulk_concurrency_per_workspace)
    await run_with_bulk_slot(semaphore, workspace_id, work, requeue)


async def start_due_crawls(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
    """Queue the crawls that are due: (workspace, site, version) of each. A finished crawl whose
    next_crawl_at has come starts the next one; a queued or running crawl that hasn't moved for
    30 minutes (a lost job) is queued again under its own version. Idempotent: a crawl started
    here is queued, so the next tick leaves it alone."""
    now = now or datetime.now(UTC)
    started: list[tuple[uuid.UUID, uuid.UUID, int]] = []
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            due = await site_crawls.due(
                session, now=now, lost_before=crawl_lost_before(now), limit=RECRAWL_BATCH
            )
        for row in due:
            with workspace_scope(row.workspace_id):
                source = await kb_repo.get_source(session, row.source_id, for_update=True)
                if source is None:
                    continue
                if row.status in ("queued", "running"):
                    row.updated_at = now  # give the new job its 30 minutes
                elif not await sites.request_crawl(session, source, now=now):
                    continue
                started.append((row.workspace_id, source.id, source.version))
        await session.commit()
    for workspace_id, source_id, version in started:
        await enqueue_job(workspace_id, source_id, version, KnowledgeType.SITE)
    if started:
        log.info("site_recrawls_started", count=len(started))
    return started


def crawl_lost_before(now: datetime) -> datetime:
    return now - sites.LOST_AFTER


@app.periodic(cron="20 * * * *", periodic_id="dispatch_site_recrawls")
@app.task(name="dispatch_site_recrawls", queue=BULK, queueing_lock="dispatch_site_recrawls")
async def dispatch_site_recrawls(timestamp: int) -> None:
    await start_due_crawls(runtime().sessionmaker)
