"""backfill_comments (T6.1; FR-CMT-01), analyze_comments and summarize_post (T6.2; TR-AI-11,
FR-CMT-02, FR-CMT-05), send_private_reply (T6.3; FR-CMT-04) and their dispatchers. Thin tasks: the
work is in services/comments/.

- backfill_comments(account_id): bulk lane, 2 tries, lock ``cmtbackfill:{account_id}``; queued by
  sync_media for posts missing comments (on connect, and gaps at each sync, TR-WH-08).
- analyze_comments(account_id): bulk lane, 2 tries (a retryable AIError), queueing lock and run
  lock ``cmt:{account_id}``; each run takes a per-workspace bulk slot (TR-JOB-06: without one it
  defers a fresh copy 5 s later, which does not use up its tries) and queues the next run while
  comments are still pending.
- summarize_post(media_item_id): bulk lane, 2 tries, lock ``postsum:{id}``, in a bulk slot.
- send_private_reply(comment_id, message_id): interactive lane, 5 tries (PlatformRetry), queueing
  lock ``send:{message_id}``, run lock ``conv:{conversation_id}``.
- dispatch_comment_analysis: every 30 s, queues analyze_comments for live accounts with pending
  comments (F-12). dispatch_post_summaries: hourly, queues summarize_post for posts whose summary is
  24 h behind an analysed comment (TR-AI-11). Both look across workspaces (allowed in jobs/,
  TR-TEN-04).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from procrastinate import JobContext
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, INTERACTIVE, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.fairness import BulkSemaphore, run_with_bulk_slot
from socialhood.jobs.retry import AIRetry, PlatformRetry
from socialhood.jobs.runtime import runtime
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.repositories import comment_analyses as repo
from socialhood.services.comments import analysis, backfill, private_replies, summaries

log = get_logger(__name__)

SEND_RETRY = PlatformRetry(max_attempts=5)
SUMMARY_STALE_AFTER = timedelta(hours=24)  # TR-AI-11


def _deps() -> PlatformDeps:
    rt = runtime()
    return deps_from(rt.http, rt.settings)


async def _in_bulk_slot(
    workspace_id: str,
    work: Callable[[], Awaitable[Any]],
    requeue: Callable[[float], Awaitable[Any]],
) -> None:
    rt = runtime()
    semaphore = BulkSemaphore(rt.redis, rt.settings.bulk_concurrency_per_workspace)
    await run_with_bulk_slot(semaphore, workspace_id, work, requeue)


@app.task(name="backfill_comments", queue=BULK, retry=PlatformRetry(max_attempts=2))
async def backfill_comments(workspace_id: str, account_id: str) -> None:
    rt = runtime()
    key = backfill.backfill_key(uuid.UUID(account_id))

    async def work() -> None:
        await backfill.backfill_comments(
            rt.sessionmaker,
            rt.redis,
            _deps(),
            workspace_id=uuid.UUID(workspace_id),
            account_id=uuid.UUID(account_id),
        )

    async def requeue(delay_s: float) -> None:
        await enqueue(
            backfill_comments,
            key=key,
            lock=key,
            delay_s=delay_s,
            workspace_id=workspace_id,
            account_id=account_id,
        )

    await _in_bulk_slot(workspace_id, work, requeue)


@app.task(name="analyze_comments", queue=BULK, retry=AIRetry(max_attempts=2))
async def analyze_comments(workspace_id: str, account_id: str) -> None:
    rt = runtime()
    key = analysis.analysis_key(uuid.UUID(account_id))

    async def work() -> None:
        run = await analysis.analyze_comments(
            rt.sessionmaker,
            rt.redis,
            rt.settings,
            _deps(),
            workspace_id=uuid.UUID(workspace_id),
            account_id=uuid.UUID(account_id),
        )
        if run.more:  # still in the slot: the next run waits for this one's lock
            await analysis.enqueue_analysis(uuid.UUID(account_id), uuid.UUID(workspace_id))

    async def requeue(delay_s: float) -> None:
        await enqueue(
            analyze_comments,
            key=key,
            lock=key,
            delay_s=delay_s,
            workspace_id=workspace_id,
            account_id=account_id,
        )

    await _in_bulk_slot(workspace_id, work, requeue)


@app.task(name="summarize_post", queue=BULK, retry=AIRetry(max_attempts=2))
async def summarize_post(workspace_id: str, media_item_id: str) -> None:
    rt = runtime()
    key = summaries.summary_key(uuid.UUID(media_item_id))

    async def work() -> None:
        await summaries.summarize_post(
            rt.sessionmaker,
            rt.redis,
            rt.settings,
            workspace_id=uuid.UUID(workspace_id),
            media_item_id=uuid.UUID(media_item_id),
        )

    async def requeue(delay_s: float) -> None:
        await enqueue(
            summarize_post,
            key=key,
            lock=key,
            delay_s=delay_s,
            workspace_id=workspace_id,
            media_item_id=media_item_id,
        )

    await _in_bulk_slot(workspace_id, work, requeue)


@app.task(name="send_private_reply", queue=INTERACTIVE, retry=SEND_RETRY, pass_context=True)
async def send_private_reply(
    context: JobContext,
    workspace_id: str,
    comment_id: str,
    message_id: str,
    conversation_id: str,
    resume: bool = False,
) -> None:
    rt = runtime()
    job = context.job

    def will_retry(error: PlatformError) -> bool:
        return SEND_RETRY.get_retry_decision(exception=error, job=job) is not None

    with workspace_scope(uuid.UUID(workspace_id)):
        await private_replies.send(
            rt.sessionmaker,
            rt.redis,
            _deps(),
            workspace_id=uuid.UUID(workspace_id),
            comment_id=uuid.UUID(comment_id),
            message_id=uuid.UUID(message_id),
            attempt=int(job.attempts),
            resume=resume,
            will_retry=will_retry,
        )


# ---------------------------------------------------------------- dispatchers


async def dispatch_analysis(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Queue analyze_comments for every live account with pending comments (F-12)."""
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            pending = await repo.accounts_with_pending(session)
    queued = await analysis.dispatch(pending)
    if queued:
        log.info("comment_analysis_dispatched", accounts=len(pending), queued=queued)
    return queued


async def dispatch_summaries(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> int:
    """Queue summarize_post for posts whose summary is 24 h behind an analysed comment."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            stale = await repo.stale_summaries(session, analysed_before=now - SUMMARY_STALE_AFTER)
    queued = 0
    for media_item_id, workspace_id in stale:
        try:
            queued += await summaries.enqueue_summary(media_item_id, workspace_id)
        except Exception:
            log.warning("post_summary_enqueue_failed", media_item_id=str(media_item_id))
    if queued:
        log.info("post_summaries_dispatched", posts=len(stale), queued=queued)
    return queued


@app.periodic(cron="* * * * * */30", periodic_id="dispatch_comment_analysis")
@app.task(
    name="dispatch_comment_analysis",
    queue=INTERACTIVE,
    queueing_lock="dispatch_comment_analysis",
)
async def dispatch_comment_analysis(timestamp: int) -> None:
    await dispatch_analysis(runtime().sessionmaker)


@app.periodic(cron="40 * * * *", periodic_id="dispatch_post_summaries")
@app.task(
    name="dispatch_post_summaries", queue=INTERACTIVE, queueing_lock="dispatch_post_summaries"
)
async def dispatch_post_summaries(timestamp: int) -> None:
    await dispatch_summaries(runtime().sessionmaker)
