"""wake_snoozed (GR-45): every minute, bring back the conversations whose snooze has ended.
Thin: the rules are in services/snooze.py.

It locks due conversations across workspaces with FOR UPDATE SKIP LOCKED inside
tenant_bypass_scope (a cross-workspace lookup, allowed in jobs/ by TR-TEN-04) and wakes each in
its own workspace scope, so a second run skips or no longer sees them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.runtime import runtime
from socialhood.observability.logging import get_logger
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import conversations as repo
from socialhood.repositories import social_accounts
from socialhood.services import snooze
from socialhood.services.inbox_views import human_agent_allowed
from socialhood.settings import Settings

log = get_logger(__name__)

BATCH = 200


async def wake_due_conversations(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    settings: Settings,
    now: datetime | None = None,
) -> list[uuid.UUID]:
    """Wake every conversation whose snooze has ended; returns their ids."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            due = await repo.lock_due_snoozed(session, now, BATCH)
        for conv in due:
            with workspace_scope(conv.workspace_id):
                acct = await social_accounts.get(session, conv.social_account_id)
                human_agent = acct is not None and human_agent_allowed(
                    acct, ig_human_agent_enabled=settings.ig_human_agent_enabled
                )
                await snooze.wake(session, conv, now=now, human_agent=human_agent)
        await commit_and_publish(session, redis)
    if due:
        log.info("snoozed_conversations_woken", count=len(due))
    return [conv.id for conv in due]


@app.periodic(cron="* * * * *", periodic_id="wake_snoozed")
@app.task(name="wake_snoozed", queue=INTERACTIVE, queueing_lock="wake_snoozed")
async def wake_snoozed(timestamp: int) -> None:
    rt = runtime()
    await wake_due_conversations(rt.sessionmaker, rt.redis, rt.settings)
