"""Meta data-deletion requests (F-16, FR-PRV-01, C-067).

Meta calls /webhooks/meta/data-deletion when the business person who connected an account through
Instagram (or Facebook) Login asks Meta to delete their data; the signed request's user id names
that connected account's user. ``delete_platform_user_data`` then, across every workspace (the
tenant bypass, through webhooks/routing.accounts_for_platform_user):

1. marks the request ``processing``;
2. disconnects each of that user's accounts (tokens destroyed, owners told) and marks it deleting,
   which queues its ``purge_account_data`` (services/account_deletion.py: conversations, messages,
   comments, contacts, posts, automations, files, cached keys and the account itself);
3. deletes the raw webhook payloads Meta sent for those accounts, wherever they were routed.

The request is ``completed`` once none of the user's accounts is left: the last purge to finish
settles it (``settle_requests``), or this job when there was nothing to purge. A purge that fails
marks it ``failed`` while the purge is retried; the retry marks it ``processing`` again. The public
status page reads GET /v1/data-deletion/{code}. sweep_deletions (every 15 minutes) re-queues a
request still received or failed, and settles one whose accounts are all gone.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Collection
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.retry import BackoffRetry
from socialhood.jobs.runtime import runtime
from socialhood.models.platform import DeletionStatus
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.realtime import events
from socialhood.repositories import data_deletion, webhook_events
from socialhood.repositories import social_accounts as accounts
from socialhood.services import account_deletion
from socialhood.services.connections import mark_disconnected_by_platform
from socialhood.webhooks.routing import accounts_for_platform_user

log = get_logger(__name__)


async def delete_user_data(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    confirmation_code: str,
) -> bool:
    """Steps 1-3 above; False when the request is unknown or already completed."""
    async with sessionmaker() as session:
        request = await data_deletion.get_by_code(session, confirmation_code)
        if request is None or request.status == DeletionStatus.COMPLETED:
            return False
        user_id, request_id = request.platform_user_id, request.id
        await data_deletion.set_status(session, confirmation_code, DeletionStatus.PROCESSING)
        await session.commit()

        now = datetime.now(UTC)
        platform_ids = {user_id}
        routed = await accounts_for_platform_user(session, user_id)
        for found in routed:
            with workspace_scope(found.workspace_id):
                acct = await accounts.get(session, found.account_id)
                if acct is None:
                    continue
                platform_ids.add(acct.platform_account_id)
                await mark_disconnected_by_platform(session, acct)
                await account_deletion.begin(session, acct, requested_by=None, deps=deps, now=now)
                await events.commit_and_publish(session, redis)  # queues its purge

        for platform_account_id in sorted(platform_ids):
            await webhook_events.delete_for_account(session, platform_account_id)
        await session.commit()
    log.info(  # never the confirmation code: it opens the public status page
        "data_deletion_started",
        request_id=str(request_id),
        accounts=len(routed),
        workspaces=len({found.workspace_id for found in routed}),
    )
    await settle_requests(sessionmaker, [user_id])
    return True


@app.task(name="delete_platform_user_data", queue=BULK, retry=BackoffRetry())
async def delete_platform_user_data(confirmation_code: str) -> None:
    """Retried on any error; the request shows ``failed`` meanwhile, and sweep_deletions
    queues it again after the last try."""
    rt = runtime()
    try:
        await delete_user_data(
            rt.sessionmaker, rt.redis, deps_from(rt.http, rt.settings), confirmation_code
        )
    except Exception:
        await _quietly(_set(rt.sessionmaker, confirmation_code, DeletionStatus.FAILED))
        raise


async def enqueue_request(confirmation_code: str) -> bool:
    return await enqueue(
        delete_platform_user_data,
        key=f"deletion:{confirmation_code}",
        confirmation_code=confirmation_code,
    )


# ---------------------------------------------------------------- kept in step by the purges


async def platform_ids(
    sessionmaker: async_sessionmaker[AsyncSession], workspace_id: uuid.UUID, account_id: uuid.UUID
) -> set[str]:
    """The ids a Meta request can name the account by (its platform and app-scoped ids); empty
    once the account is gone."""
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            acct = await accounts.get(session, account_id)
    if acct is None:
        return set()
    return {i for i in (acct.platform_account_id, acct.app_scoped_id) if i}


async def purge_started(
    sessionmaker: async_sessionmaker[AsyncSession], ids: Collection[str]
) -> None:
    """A purge run starts: a request that was waiting on its retry is in progress again."""
    await _move(sessionmaker, ids, DeletionStatus.FAILED, DeletionStatus.PROCESSING)


async def purge_failed(
    sessionmaker: async_sessionmaker[AsyncSession], ids: Collection[str]
) -> None:
    """A purge run failed and will be retried."""
    await _quietly(_move(sessionmaker, ids, DeletionStatus.PROCESSING, DeletionStatus.FAILED))


async def settle_requests(
    sessionmaker: async_sessionmaker[AsyncSession], ids: Collection[str] | None = None
) -> int:
    """Complete every request in progress (for these platform users, when given) whose accounts
    are all gone; returns how many."""
    done = 0
    async with sessionmaker() as session:
        waiting = await data_deletion.open_requests(
            session, ids, statuses=(DeletionStatus.PROCESSING, DeletionStatus.FAILED)
        )
        for request in waiting:
            if not await accounts_for_platform_user(session, request.platform_user_id):
                await data_deletion.set_status(
                    session, request.confirmation_code, DeletionStatus.COMPLETED
                )
                done += 1
                log.info("data_deletion_completed", request_id=str(request.id))
        await session.commit()
    return done


async def sweep_requests(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """sweep_deletions: re-queue requests still received (a lost job) or failed (their retry),
    and settle the ones whose accounts are gone. Returns how many were re-queued."""
    async with sessionmaker() as session:
        stuck = await data_deletion.open_requests(
            session, statuses=(DeletionStatus.RECEIVED, DeletionStatus.FAILED)
        )
    requeued = 0
    for request in stuck:
        try:
            requeued += int(await enqueue_request(request.confirmation_code))
        except Exception:
            log.warning("data_deletion_defer_failed", request_id=str(request.id))
    await settle_requests(sessionmaker)
    return requeued


async def _move(
    sessionmaker: async_sessionmaker[AsyncSession],
    ids: Collection[str],
    from_status: DeletionStatus,
    to_status: DeletionStatus,
) -> None:
    if not ids:
        return
    async with sessionmaker() as session:
        await data_deletion.move(session, ids, from_status=from_status, to_status=to_status)
        await session.commit()


async def _set(
    sessionmaker: async_sessionmaker[AsyncSession], code: str, status: DeletionStatus
) -> None:
    async with sessionmaker() as session:
        await data_deletion.set_status(session, code, status)
        await session.commit()


async def _quietly(step: Awaitable[None]) -> None:
    """A status write on the way out of a failure never hides that failure."""
    try:
        await step
    except Exception:
        log.warning("data_deletion_status_failed", exc_info=True)
