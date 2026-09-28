"""Account upkeep: token refresh (FR-CON-05) and webhook re-subscription (TR-WH-08).

These start without a workspace, so they list due accounts across workspaces (allowed in jobs/,
TR-TEN-04) and then handle each account inside its own workspace scope.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.runtime import runtime
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.repositories import social_accounts as accounts
from socialhood.services import connections

log = get_logger(__name__)


async def _live_accounts(session: AsyncSession) -> list[tuple[uuid.UUID, uuid.UUID]]:
    with tenant_bypass_scope():
        rows = await session.execute(
            select(SocialAccount.id, SocialAccount.workspace_id).where(
                SocialAccount.status.in_([AccountStatus.ACTIVE, AccountStatus.ERROR])
            )
        )
        return [(r[0], r[1]) for r in rows.all()]


async def refresh_due_tokens(
    sessionmaker: async_sessionmaker[AsyncSession], deps: PlatformDeps, now: datetime | None = None
) -> dict[str, int]:
    now = now or datetime.now(UTC)
    counts = {"refreshed": 0, "failed": 0, "skipped": 0}
    async with sessionmaker() as session:
        candidates = await _live_accounts(session)
    for account_id, workspace_id in candidates:
        with workspace_scope(workspace_id):
            async with sessionmaker() as session:
                acct = await accounts.get(session, account_id)
                if acct is None or not connections.refresh_due(acct, now):
                    counts["skipped"] += 1
                    continue
                try:
                    ok = await connections.refresh_account(session, acct, deps)
                except PlatformError as error:  # retryable: try again tomorrow, well before expiry
                    log.warning(
                        "token_refresh_deferred", account_id=str(account_id), error_code=error.code
                    )
                    counts["failed"] += 1
                    continue
                counts["refreshed" if ok else "failed"] += 1
    log.info("token_refresh_run", **counts)
    return counts


async def resubscribe_all(
    sessionmaker: async_sessionmaker[AsyncSession], deps: PlatformDeps
) -> int:
    ok = 0
    async with sessionmaker() as session:
        candidates = await _live_accounts(session)
    for account_id, workspace_id in candidates:
        with workspace_scope(workspace_id):
            async with sessionmaker() as session:
                acct = await accounts.get(session, account_id)
                if acct is not None and await connections.subscribe(session, acct, deps):
                    ok += 1
                await session.commit()
    log.info("resubscribe_run", accounts=len(candidates), subscribed=ok)
    return ok


def _deps() -> PlatformDeps:
    rt = runtime()
    return deps_from(rt.http, rt.settings)


@app.periodic(cron="0 3 * * *", periodic_id="refresh_tokens")
@app.task(name="refresh_tokens", queue=BULK, queueing_lock="refresh_tokens")
async def refresh_tokens(timestamp: int) -> None:
    await refresh_due_tokens(runtime().sessionmaker, _deps())


@app.periodic(cron="30 1,7,13,19 * * *", periodic_id="reconcile_subscriptions")
@app.task(name="reconcile_subscriptions", queue=BULK, queueing_lock="reconcile_subscriptions")
async def reconcile_subscriptions(timestamp: int) -> None:
    await resubscribe_all(runtime().sessionmaker, _deps())
