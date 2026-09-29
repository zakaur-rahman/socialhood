"""analyze_conversation (T5.2; TR-AI-05), summarize_conversation (T5.7; FR-AI-03) and
check_closing_windows (T5.11; FR-INB-14, F-18). Thin tasks: the work is in services/analysis.py,
services/summaries.py and services/follow_ups.py.

- analyze_conversation: interactive lane, 2 tries (a retryable AIError is retried once); queued
  by ingest with the queueing lock and run lock ``analyze:{conversation_id}``.
- summarize_conversation: bulk lane in a per-workspace bulk slot (TR-JOB-06), 2 tries; lock
  ``convsum:{conversation_id}``.
- check_closing_windows: every 15 minutes, interactive lane. It locks due conversations across
  workspaces (FOR UPDATE SKIP LOCKED inside tenant_bypass_scope, allowed in jobs/ by TR-TEN-04)
  and reminds each in its own workspace scope.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, INTERACTIVE, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.fairness import BulkSemaphore, run_with_bulk_slot
from socialhood.jobs.retry import AIRetry
from socialhood.jobs.runtime import runtime
from socialhood.observability.logging import get_logger
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import analyses, social_accounts
from socialhood.services import analysis, follow_ups, summaries
from socialhood.services.inbox_views import human_agent_allowed
from socialhood.settings import Settings

log = get_logger(__name__)


@app.task(name="analyze_conversation", queue=INTERACTIVE, retry=AIRetry(max_attempts=2))
async def analyze_conversation(workspace_id: str, conversation_id: str) -> None:
    rt = runtime()
    await analysis.analyze_conversation(
        rt.sessionmaker,
        rt.redis,
        rt.settings,
        workspace_id=uuid.UUID(workspace_id),
        conversation_id=uuid.UUID(conversation_id),
    )


@app.task(name="summarize_conversation", queue=BULK, retry=AIRetry(max_attempts=2))
async def summarize_conversation(workspace_id: str, conversation_id: str) -> None:
    rt = runtime()
    key = summaries.summary_key(uuid.UUID(conversation_id))

    async def work() -> None:
        await summaries.summarize_conversation(
            rt.sessionmaker,
            rt.redis,
            rt.settings,
            workspace_id=uuid.UUID(workspace_id),
            conversation_id=uuid.UUID(conversation_id),
        )

    async def requeue(delay_s: float) -> None:
        await enqueue(
            summarize_conversation,
            key=key,
            lock=key,
            delay_s=delay_s,
            workspace_id=workspace_id,
            conversation_id=conversation_id,
        )

    semaphore = BulkSemaphore(rt.redis, rt.settings.bulk_concurrency_per_workspace)
    await run_with_bulk_slot(semaphore, workspace_id, work, requeue)


async def remind_closing_windows(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    settings: Settings,
    now: datetime | None = None,
) -> list[uuid.UUID]:
    """F-18: remind for every due conversation; returns their ids."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            due = await analyses.lock_due_reminders(
                session,
                now=now,
                lead_score=follow_ups.REMINDER_LEAD_SCORE,
                wrote_between=follow_ups.WROTE_BETWEEN,
                quiet_for=follow_ups.QUIET_FOR,
                limit=follow_ups.BATCH,
            )
        for conv in due:
            with workspace_scope(conv.workspace_id):
                acct = await social_accounts.get(session, conv.social_account_id)
                human_agent = acct is not None and human_agent_allowed(
                    acct, ig_human_agent_enabled=settings.ig_human_agent_enabled
                )
                await follow_ups.remind(session, conv, now=now, human_agent=human_agent)
        await commit_and_publish(session, redis)
    if due:
        log.info("closing_window_reminders", count=len(due))
    return [conv.id for conv in due]


@app.periodic(cron="*/15 * * * *", periodic_id="check_closing_windows")
@app.task(name="check_closing_windows", queue=INTERACTIVE, queueing_lock="check_closing_windows")
async def check_closing_windows(timestamp: int) -> None:
    rt = runtime()
    await remind_closing_windows(rt.sessionmaker, rt.redis, rt.settings)
