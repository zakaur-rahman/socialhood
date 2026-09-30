"""Deleting a workspace (T9.6; FR-ACC-05, F-16, §5.9, C-052).

Two steps. ``begin`` runs in the request (or in Clerk's user.deleted) and makes the workspace
unreachable at once: it goes to ``deleting`` (who asked and when), every platform token is
destroyed and its accounts are disconnected (webhook routing ignores disconnected accounts), their
automations pause, scheduled messages and posts that haven't started are cancelled and queued
emails are skipped. The API answers 404 for a workspace that isn't active (auth/deps.py). Once the
transaction commits, ``purge_workspace`` is queued (bulk lane, key and lock ``purge:{id}``).

``purge_workspace`` (jobs/tasks/purge.py) then removes everything, and may run any number of
times: each step is safe to repeat and a run that stops half-way resumes where it was.

1. Billing first: the Dodo subscription is cancelled at once (services/workspaces.
   cancel_dodo_subscription). Dodo not answering doesn't hold the data back: it only keeps the
   subscriptions row, which names the subscription to cancel, and the workspace row.
2. Every other table holding the workspace's rows, children before parents, in batches committed
   one by one (repositories/workspace_deletion.workspace_tables: the TenantScoped registry, so a
   new table is covered, pgvector chunks and agent runs included), then the stored webhook
   payloads routed to it.
3. Its Valkey keys: every key naming the workspace or one of its accounts (the event stream,
   idempotency records, bulk slots, profile and template caches, rate buckets).
4. Its Cloudinary folder ``ws/{id}/`` (media/purge.py).
5. Only when billing, keys and media are all done: the subscription row and the workspace row.
   Otherwise the job fails and retries with backoff; sweep_deletions re-queues every deleting
   workspace every 15 minutes and raises an alert for one still deleting after 6 hours, well
   inside the 24 hours FR-ACC-05 promises.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import Table, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, SessionTransaction
from sqlalchemy.util import await_only
from sqlalchemy.util.concurrency import in_greenlet

from socialhood.auth.memberships import memberships_for
from socialhood.billing.dodo import DodoClient
from socialhood.db.tenancy import current_workspace_id, workspace_scope
from socialhood.errors import ApiError, FieldError
from socialhood.media.cloudinary import CloudinaryError
from socialhood.media.purge import MediaPurger
from socialhood.models.identity import User, Workspace, WorkspaceStatus
from socialhood.observability.logging import get_logger
from socialhood.repositories import subscriptions, users
from socialhood.repositories import workspace_deletion as repo
from socialhood.schemas.workspace_deletion import WorkspaceDeletion
from socialhood.services import provisioning
from socialhood.services.automations.definitions import pause_for_account
from socialhood.services.workspaces import cancel_dodo_subscription

log = get_logger(__name__)

PURGE_WITHIN = timedelta(hours=24)  # FR-ACC-05
OVERDUE_AFTER = timedelta(hours=6)  # sweep_deletions alerts well before the promise is broken
ROW_BATCH = 2000
RUN_BUDGET_S = 540.0  # a run hands over to a fresh job after this, like the bulk lane's 600 s
KEY_DELETE_CHUNK = 500
CONFIRM_MISMATCH = "Type the workspace name exactly as it is shown to confirm."

Source = Literal["owner", "clerk_user_deleted"]


# ---------------------------------------------------------------- step 1: stop everything now


async def begin(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    requested_by: uuid.UUID | None,
    source: Source,
    now: datetime,
) -> bool:
    """Mark the workspace deleting and stop everything it does; the purge is queued when the
    caller's transaction commits. False when it isn't active (gone, or already deleting)."""
    with workspace_scope(workspace_id):
        if not await repo.mark_deleting(session, workspace_id, requested_by=requested_by, at=now):
            return False
        account_ids = await repo.disconnect_accounts(session, at=now)
        paused = 0
        for account_id in account_ids:
            paused += await pause_for_account(session, account_id, now=now)
        stopped = await repo.stop_scheduled_work(session)
    purge_after_commit(session, workspace_id)
    log.info(
        "workspace_deletion_requested",
        workspace_id=str(workspace_id),
        requested_by=str(requested_by) if requested_by else None,
        source=source,
        accounts_disconnected=len(account_ids),
        automations_paused=paused,
        **stopped,
    )
    return True


async def request_deletion(
    session: AsyncSession, workspace: Workspace, user: User, *, confirm_name: str
) -> WorkspaceDeletion:
    """DELETE /v1/w/{wid} (owner only): the owner typed the workspace's name. The owner lands in
    another of their workspaces, or a new one when this was their last (F-16)."""
    if confirm_name.strip() != workspace.name.strip():
        raise ApiError("validation_error", errors=[FieldError("confirm_name", CONFIRM_MISMATCH)])
    now = datetime.now(UTC)
    if not await begin(session, workspace.id, requested_by=user.id, source="owner", now=now):
        raise ApiError("not_found")
    await _land_elsewhere(session, user)
    await session.commit()
    return WorkspaceDeletion(
        id=workspace.id,
        status="deleting",
        deletion_requested_at=now,
        purge_by=now + PURGE_WITHIN,
    )


async def _land_elsewhere(session: AsyncSession, user: User) -> uuid.UUID:
    """Point /app at another active workspace of the user's, creating one if there is none."""
    remaining = [m.workspace_id for m in await memberships_for(session, user.id)]
    if remaining:
        target = user.last_workspace_id if user.last_workspace_id in remaining else remaining[0]
    else:
        names = (user.name or "").split()
        first_name = names[0] if names else None
        with _no_workspace():  # its first rows belong to the new workspace, not this one
            target = await provisioning._create_personal_workspace(session, user.id, first_name)
    await users.set_last_workspace(session, user.id, target)
    return target


@contextmanager
def _no_workspace() -> Iterator[None]:
    token = current_workspace_id.set(None)
    try:
        yield
    finally:
        current_workspace_id.reset(token)


# ---------------------------------------------------------------- queueing the purge


_PENDING = "purge_after_commit"


def purge_key(workspace_id: uuid.UUID) -> str:
    return f"purge:{workspace_id}"


def purge_after_commit(session: AsyncSession | Session, workspace_id: uuid.UUID) -> None:
    pending: set[uuid.UUID] = session.info.setdefault(_PENDING, set())
    pending.add(workspace_id)


async def enqueue_purge(workspace_id: uuid.UUID) -> bool:
    """Queue purge_workspace; False when one is already waiting (its queueing lock). The same
    lock serialises runs, so two never purge one workspace at once."""
    from socialhood.jobs.app import BULK
    from socialhood.jobs.enqueue import enqueue_named

    key = purge_key(workspace_id)
    return await enqueue_named(
        "purge_workspace", lane=BULK, key=key, lock=key, workspace_id=str(workspace_id)
    )


async def enqueue_purge_quietly(workspace_id: uuid.UUID) -> bool:
    """A lost enqueue is picked up by sweep_deletions within 15 minutes."""
    try:
        return await enqueue_purge(workspace_id)
    except Exception:
        log.warning("workspace_purge_defer_failed", workspace_id=str(workspace_id))
        return False


@event.listens_for(Session, "after_commit")
def _enqueue_after_commit(session: Session) -> None:
    pending: set[uuid.UUID] | None = session.info.pop(_PENDING, None)
    if not pending:
        return
    if not in_greenlet():  # a synchronous session: nothing here can await
        log.warning("workspace_purge_defer_skipped", workspaces=len(pending))
        return
    for workspace_id in sorted(pending):
        await_only(enqueue_purge_quietly(workspace_id))


@event.listens_for(Session, "after_soft_rollback")
def _drop_on_rollback(session: Session, previous_transaction: SessionTransaction) -> None:
    if previous_transaction.parent is None:
        session.info.pop(_PENDING, None)


# ---------------------------------------------------------------- step 2: the purge


class PurgeBlocked(Exception):
    """Something outside the database isn't done yet (billing, cache or media): the workspace
    row stays so the purge can finish later."""

    def __init__(self, workspace_id: uuid.UUID, reasons: list[str]) -> None:
        super().__init__(f"workspace {workspace_id} purge waiting on {', '.join(reasons)}")
        self.reasons = reasons


@dataclass(frozen=True)
class PurgeDeps:
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    dodo: DodoClient
    media: MediaPurger


PurgeStatus = Literal["purged", "gone", "not_deleting", "continue"]
BatchDelete = Callable[[AsyncSession, uuid.UUID, int], Awaitable[int]]


@dataclass
class PurgeResult:
    status: PurgeStatus
    deleted: dict[str, int] = field(default_factory=dict)


async def purge_workspace(
    deps: PurgeDeps,
    workspace_id: uuid.UUID,
    *,
    batch: int = ROW_BATCH,
    budget_s: float = RUN_BUDGET_S,
) -> PurgeResult:
    """Remove the workspace and everything it holds (see the module docstring). Raises
    PurgeBlocked when billing, cache or media must be tried again; returns ``continue`` when the
    run's time is up with rows left (the caller queues the next run)."""
    deadline = time.monotonic() + budget_s
    result = PurgeResult(status="purged")
    with workspace_scope(workspace_id):
        async with deps.sessionmaker() as session:
            status = await repo.workspace_status(session, workspace_id)
            if status is None:
                return PurgeResult(status="gone")
            if status != WorkspaceStatus.DELETING:
                log.error("workspace_purge_refused", workspace_id=str(workspace_id), status=status)
                return PurgeResult(status="not_deleting")

            blocked: list[str] = []
            if not await _cancel_billing(session, deps.dodo, workspace_id):
                blocked.append("billing")
            account_ids = await repo.account_ids(session, workspace_id)

            tables = repo.workspace_tables()
            steps: list[tuple[str, BatchDelete]] = [
                (table.name, _table_batch(table))
                for table in tables
                if table.name not in repo.BILLING_TABLES
            ]
            steps.append(("webhook_events", repo.delete_webhook_events))
            for name, delete_batch in steps:
                drained = await _drain(
                    session, workspace_id, name, delete_batch, result, batch, deadline
                )
                if not drained:
                    return PurgeResult(status="continue", deleted=result.deleted)

            if not await _clear_keys(deps.redis, workspace_id, account_ids):
                blocked.append("cache")
            if not await _delete_media(deps.media, workspace_id):
                blocked.append("media")
            if blocked:
                log.warning(
                    "workspace_purge_blocked", workspace_id=str(workspace_id), reasons=blocked
                )
                raise PurgeBlocked(workspace_id, blocked)

            for table in tables:
                if table.name in repo.BILLING_TABLES:
                    await _drain(
                        session, workspace_id, table.name, _table_batch(table), result, batch
                    )
            await repo.delete_workspace(session, workspace_id)
            await session.commit()
    log.info("workspace_purged", workspace_id=str(workspace_id), deleted=result.deleted)
    return result


def _table_batch(table: Table) -> BatchDelete:
    async def delete_batch(session: AsyncSession, workspace_id: uuid.UUID, limit: int) -> int:
        return await repo.delete_batch(session, table, workspace_id, limit)

    return delete_batch


async def _drain(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    name: str,
    delete_batch: BatchDelete,
    result: PurgeResult,
    batch: int,
    deadline: float | None = None,
) -> bool:
    """Delete the workspace's rows from one table, a batch per commit. False when the run's time
    ran out with rows left."""
    while True:
        n = await delete_batch(session, workspace_id, batch)
        await session.commit()
        if n:
            result.deleted[name] = result.deleted.get(name, 0) + n
        if n < batch:
            return True
        if deadline is not None and time.monotonic() > deadline:
            return False


async def _cancel_billing(session: AsyncSession, dodo: DodoClient, workspace_id: uuid.UUID) -> bool:
    """True once no live Dodo subscription is left to cancel (C-052)."""
    try:
        await cancel_dodo_subscription(session, dodo)
    except ApiError:
        sub = await subscriptions.current(session)
        log.error(
            "workspace_purge_dodo_cancel_failed",
            workspace_id=str(workspace_id),
            dodo_subscription_id=sub.dodo_subscription_id if sub else None,
        )
        return False
    return True


async def _clear_keys(redis: Redis, workspace_id: uuid.UUID, account_ids: list[uuid.UUID]) -> bool:
    """Every Valkey key naming the workspace or one of its accounts. Account keys (caches, rate
    buckets) also expire on their own; the workspace's event stream doesn't."""
    try:
        doomed: list[str] = []
        for ident in [workspace_id, *account_ids]:
            doomed.extend([key async for key in redis.scan_iter(match=f"*{ident}*", count=1000)])
        for start in range(0, len(doomed), KEY_DELETE_CHUNK):
            await redis.delete(*doomed[start : start + KEY_DELETE_CHUNK])
    except RedisError:
        log.warning("workspace_purge_cache_failed", workspace_id=str(workspace_id))
        return False
    return True


async def _delete_media(media: MediaPurger, workspace_id: uuid.UUID) -> bool:
    try:
        await media.delete_workspace_folder(workspace_id)
    except (CloudinaryError, httpx.HTTPError) as error:
        log.warning(
            "workspace_purge_media_failed", workspace_id=str(workspace_id), error=str(error)
        )
        return False
    return True


# ---------------------------------------------------------------- the sweeper


@dataclass(frozen=True)
class Sweep:
    requeued: int
    overdue: list[uuid.UUID]


async def sweep(sessionmaker: async_sessionmaker[AsyncSession], now: datetime) -> Sweep:
    """Queue a purge for every deleting workspace (a waiting one makes this a no-op) and alert on
    any still deleting after OVERDUE_AFTER: something outside the database keeps failing."""
    async with sessionmaker() as session:
        pending = await repo.deleting_workspaces(session)
    requeued = 0
    overdue: list[uuid.UUID] = []
    for workspace_id, requested_at in pending:
        requeued += int(await enqueue_purge_quietly(workspace_id))
        if requested_at is not None and now - requested_at > OVERDUE_AFTER:
            overdue.append(workspace_id)
            log.error(
                "alert",
                kind="workspace_purge_overdue",
                workspace_id=str(workspace_id),
                hours=round((now - requested_at).total_seconds() / 3600, 1),
                detail="see workspace_purge_blocked for what it waits on",
            )
    if pending:
        log.info("sweep_deletions", deleting=len(pending), requeued=requeued)
    return Sweep(requeued=requeued, overdue=overdue)
