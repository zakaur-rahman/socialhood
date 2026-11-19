"""YouTube comment polling (YT4): YouTube has no comment webhooks. Thin: the work is in
services/youtube_comments.py.

- dispatch_youtube_comments: every 15 minutes, queues poll_youtube_comments for each live YouTube
  channel (a cross-workspace lookup, allowed in jobs/ by TR-TEN-04).
- poll_youtube_comments(account_id): bulk lane, queueing lock and run lock
  ``ytcomments:{account_id}``, in a per-workspace bulk slot (TR-JOB-06). No retries: the next poll
  is 15 minutes away.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.fairness import BulkSemaphore, run_with_bulk_slot
from socialhood.jobs.runtime import runtime
from socialhood.models.connections import SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import deps_from
from socialhood.services import youtube_comments as service

log = get_logger(__name__)


async def enqueue_poll(account_id: uuid.UUID, workspace_id: uuid.UUID, delay_s: float = 0) -> bool:
    key = service.poll_key(account_id)
    return await enqueue(
        poll_youtube_comments,
        key=key,
        lock=key,
        delay_s=delay_s,
        workspace_id=str(workspace_id),
        account_id=str(account_id),
    )


async def dispatch_polls(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Queue a poll for each live YouTube channel; returns how many were queued."""
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            rows = (
                await session.execute(
                    select(SocialAccount.id, SocialAccount.workspace_id).where(
                        SocialAccount.platform == "youtube",
                        SocialAccount.status.in_(service.LIVE),
                    )
                )
            ).all()
    queued = 0
    for account_id, workspace_id in rows:
        queued += await enqueue_poll(account_id, workspace_id)
    log.info("youtube_comment_polls_queued", accounts=len(rows), queued=queued)
    return queued


@app.periodic(cron="*/15 * * * *", periodic_id="dispatch_youtube_comments")
@app.task(name="dispatch_youtube_comments", queue=BULK, queueing_lock="dispatch_youtube_comments")
async def dispatch_youtube_comments(timestamp: int) -> None:
    await dispatch_polls(runtime().sessionmaker)


@app.task(name="poll_youtube_comments", queue=BULK)
async def poll_youtube_comments(workspace_id: str, account_id: str) -> None:
    rt = runtime()

    async def work() -> None:
        await service.poll_account(
            rt.sessionmaker,
            rt.redis,
            deps_from(rt.http, rt.settings),
            workspace_id=uuid.UUID(workspace_id),
            account_id=uuid.UUID(account_id),
        )

    async def requeue(delay_s: float) -> None:
        await enqueue_poll(uuid.UUID(account_id), uuid.UUID(workspace_id), delay_s)

    semaphore = BulkSemaphore(rt.redis, rt.settings.bulk_concurrency_per_workspace)
    await run_with_bulk_slot(semaphore, workspace_id, work, requeue)
