"""Deleting one connected account's data (C-067; FR-CON-06, F-16).

Three ways in, one purge:

- Disconnect and delete data (DELETE …/social-accounts/{id}?delete_data=true&confirm=…) and Remove
  (DELETE …/social-accounts/{id}?confirm=…, for a disconnected or sandbox account): owners and
  admins, who type the account's handle or number (``request``).
- Meta's data-deletion callback (jobs/tasks/privacy.py): every account of that platform user, in
  every workspace.

``begin`` stops the account at once, in the caller's transaction: its tokens are destroyed and it
is disconnected (webhook routing ignores it), its automations pause, its scheduled messages and
pending post targets are cancelled, and it is marked deleting (who asked and when; the web shows
"Deleting…"). Once the transaction commits, ``purge_account_data`` is queued (bulk lane, key and
lock ``acctpurge:{id}``).

``purge_account`` (jobs/tasks/purge.py) then removes everything the account holds, and may run
any number of times: each step is safe to repeat and a run that stops half-way resumes.

1. The files its messages own (inbound media copies and files uploaded to send), found through
   those messages while they exist: deleted from Cloudinary through the media purger, then their
   rows. A file anything outside the account still names (another account's message, a post in
   the library, a knowledge file) is kept.
2. Every table holding its rows, children before parents, in batches committed one by one
   (repositories/account_deletion.account_tables: built from the schema's cascading foreign
   keys): conversations, messages and their analyses, suggestions, AI decisions; contacts;
   comments and their analyses; posts, their metric snapshots and the daily account metrics;
   automations bound to it with their keywords, posts and runs (the private-reply queue);
   scheduled messages; its post targets and posting times. Then the webhook payloads routed to
   this workspace for it, and scheduled posts left with no account (repositories/
   account_deletion.settle_posts_without_accounts).
3. Its Valkey keys (rate buckets, profile and template caches), and the workspace's event stream,
   whose entries can carry its messages; a ``resync`` follows so every open page refetches.
4. The account row. Its cascade takes anything written since the batches ran.

Knowledge, workspace settings, billing and the workspace's other accounts are never touched. Plan
slots count live accounts (billing/entitlements.py), so the account stops counting when it is
disconnected. A step outside the database that fails (Cloudinary, Valkey) raises
AccountPurgeBlocked; the job retries with backoff and sweep_deletions re-queues any account still
deleting every 15 minutes, alerting after 6 hours. Each run logs ``account_data_purged`` (or
``account_purge_continues``) with the workspace, account, requester and rows deleted per table,
never content.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Awaitable, Callable
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

from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError, FieldError
from socialhood.media.cloudinary import CloudinaryError
from socialhood.media.purge import MediaPurger, StoredFile
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.identity import WorkspaceStatus
from socialhood.models.publishing import ScheduledPostStatus
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.sandbox.adapter import is_sandbox
from socialhood.realtime import events
from socialhood.repositories import account_deletion as repo
from socialhood.repositories import publish_targets
from socialhood.repositories import social_accounts as accounts
from socialhood.repositories.workspace_deletion import workspace_status
from socialhood.services.automations.definitions import pause_for_account
from socialhood.services.connections import account_out
from socialhood.services.post_publishing.projection import derive_status, queue_post_updated

log = get_logger(__name__)

ROW_BATCH = 2000
FILE_BATCH = 100
RUN_BUDGET_S = 540.0  # a run hands over to a fresh job after this, like the bulk lane's 600 s
KEY_DELETE_CHUNK = 500
OVERDUE_AFTER = timedelta(hours=6)  # sweep_deletions alerts on an account deleting this long

ACTIVE_ACCOUNT = "Disconnect this account first, or use Disconnect and delete data."
CONFIRM_MISMATCH = "Type {target} exactly as shown to confirm."

Source = Literal["member", "meta"]


# ---------------------------------------------------------------- the typed confirmation


def confirmation_target(acct: SocialAccount) -> str:
    """What the member types: the handle, else the number, else the name the card shows."""
    if acct.username:
        return f"@{acct.username}"
    return acct.phone_number or acct.display_name or acct.platform_account_id


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def confirms(acct: SocialAccount, typed: str) -> bool:
    """The handle with or without "@" in any case, or the number with any spacing or "+"."""
    given = typed.strip()
    if not given:
        return False
    if acct.username and given.lstrip("@").casefold() == acct.username.casefold():
        return True
    if acct.phone_number and _digits(given) and _digits(given) == _digits(acct.phone_number):
        return True
    return given.casefold() == confirmation_target(acct).casefold()


# ---------------------------------------------------------------- step 1: stop everything now


def is_live(acct: SocialAccount) -> bool:
    return acct.status != AccountStatus.DISCONNECTED


async def begin(
    session: AsyncSession,
    acct: SocialAccount,
    *,
    requested_by: uuid.UUID | None,
    deps: PlatformDeps,
    now: datetime | None = None,
) -> None:
    """Disconnect the account, stop what it would send and mark it deleting; the purge is
    queued when the caller's transaction commits (and ``social_account.updated`` published, if
    the caller commits with events.commit_and_publish). Runs in the account's workspace scope."""
    now = now or datetime.now(UTC)
    first = acct.deletion_requested_at is None
    await repo.mark_deleting(session, acct.id, requested_by=requested_by, at=now)
    paused = await pause_for_account(session, acct.id, now=now)
    scheduled = await repo.cancel_scheduled_messages(session, acct.id)
    posts = await repo.cancel_pending_targets(session, acct.id)
    for post_id in posts:
        await _settle_post(session, post_id)
    purge_after_commit(session, acct.workspace_id, acct.id)
    await session.refresh(acct)
    events.queue(
        session,
        acct.workspace_id,
        "social_account.updated",
        {"social_account": account_out(acct, deps).model_dump(mode="json")},
    )
    if first:
        log.info(
            "account_deletion_requested",
            workspace_id=str(acct.workspace_id),
            account_id=str(acct.id),
            requested_by=str(requested_by) if requested_by else None,
            source="member" if requested_by else "meta",
            automations_paused=paused,
            scheduled_messages_canceled=scheduled,
            post_targets_canceled=len(posts),
        )


async def _settle_post(session: AsyncSession, post_id: uuid.UUID) -> None:
    """A post whose target on this account was just canceled: its status follows its targets
    once none is running (F-13), e.g. canceled when this was its only account."""
    post = await publish_targets.lock_post(session, post_id)
    if post is None or post.status not in (
        ScheduledPostStatus.SCHEDULED,
        ScheduledPostStatus.PUBLISHING,
    ):
        return
    status = derive_status(t.status for t in await publish_targets.targets_of(session, post_id))
    if status is not None and status != post.status:
        post.status = status
        await queue_post_updated(session, post)


async def request(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    acct: SocialAccount,
    *,
    user_id: uuid.UUID,
    confirm: str | None,
    delete_data: bool,
) -> None:
    """DELETE …/social-accounts/{id} with ``delete_data`` (Disconnect and delete data) or with
    only ``confirm`` (Remove). Remove refuses a live account unless it is a sandbox (409):
    disconnecting first, or Disconnect and delete, says what happens to it. Either way the typed
    handle or number must match (422 on ``confirm``). Asking again for an account already being
    deleted queues its purge again (a no-op while one waits)."""
    if not delete_data and is_live(acct) and not is_sandbox(acct):
        raise ApiError("conflict", ACTIVE_ACCOUNT)
    if confirm is None or not confirms(acct, confirm):
        message = CONFIRM_MISMATCH.format(target=confirmation_target(acct))
        raise ApiError("validation_error", errors=[FieldError("confirm", message)])
    if acct.deletion_requested_at is None:
        await begin(session, acct, requested_by=user_id, deps=deps)
    else:
        purge_after_commit(session, acct.workspace_id, acct.id)
    await events.commit_and_publish(session, redis)


# ---------------------------------------------------------------- queueing the purge


_PENDING = "account_purge_after_commit"


def purge_key(account_id: uuid.UUID) -> str:
    return f"acctpurge:{account_id}"


def purge_after_commit(
    session: AsyncSession | Session, workspace_id: uuid.UUID, account_id: uuid.UUID
) -> None:
    pending: set[tuple[uuid.UUID, uuid.UUID]] = session.info.setdefault(_PENDING, set())
    pending.add((workspace_id, account_id))


async def enqueue_purge(workspace_id: uuid.UUID, account_id: uuid.UUID) -> bool:
    """Queue purge_account_data; False when one is already waiting (its queueing lock). The same
    lock serialises runs, so two never purge one account at once."""
    from socialhood.jobs.app import BULK
    from socialhood.jobs.enqueue import enqueue_named

    key = purge_key(account_id)
    return await enqueue_named(
        "purge_account_data",
        lane=BULK,
        key=key,
        lock=key,
        workspace_id=str(workspace_id),
        account_id=str(account_id),
    )


async def enqueue_purge_quietly(workspace_id: uuid.UUID, account_id: uuid.UUID) -> bool:
    """A lost enqueue is picked up by sweep_deletions within 15 minutes."""
    try:
        return await enqueue_purge(workspace_id, account_id)
    except Exception:
        log.warning("account_purge_defer_failed", account_id=str(account_id))
        return False


@event.listens_for(Session, "after_commit")
def _enqueue_after_commit(session: Session) -> None:
    pending: set[tuple[uuid.UUID, uuid.UUID]] | None = session.info.pop(_PENDING, None)
    if not pending:
        return
    if not in_greenlet():  # a synchronous session: nothing here can await
        log.warning("account_purge_defer_skipped", accounts=len(pending))
        return
    for workspace_id, account_id in sorted(pending):
        await_only(enqueue_purge_quietly(workspace_id, account_id))


@event.listens_for(Session, "after_soft_rollback")
def _drop_on_rollback(session: Session, previous_transaction: SessionTransaction) -> None:
    if previous_transaction.parent is None:
        session.info.pop(_PENDING, None)


# ---------------------------------------------------------------- step 2: the purge


class AccountPurgeBlocked(Exception):
    """Something outside the database isn't done yet (media or cache): the account row stays so
    the purge can finish later."""

    def __init__(self, account_id: uuid.UUID, reasons: list[str]) -> None:
        super().__init__(f"account {account_id} purge waiting on {', '.join(reasons)}")
        self.reasons = reasons


@dataclass(frozen=True)
class PurgeDeps:
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    media: MediaPurger


PurgeStatus = Literal["purged", "gone", "not_deleting", "workspace_deleting", "continue"]
BatchDelete = Callable[[AsyncSession, int], Awaitable[int]]


@dataclass
class PurgeResult:
    status: PurgeStatus
    deleted: dict[str, int] = field(default_factory=dict)
    files: int = 0


@dataclass(frozen=True)
class _Account:
    """What the audit line and the last steps need, read before anything is deleted."""

    platform: str
    platform_account_id: str
    requested_by: uuid.UUID | None


async def purge_account(
    deps: PurgeDeps,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    batch: int = ROW_BATCH,
    file_batch: int = FILE_BATCH,
    budget_s: float = RUN_BUDGET_S,
) -> PurgeResult:
    """Remove the account and everything it holds (see the module docstring). Raises
    AccountPurgeBlocked when media or cache must be tried again; returns ``continue`` when the
    run's time is up with rows left (the caller queues the next run)."""
    deadline = time.monotonic() + budget_s
    result = PurgeResult(status="purged")
    with workspace_scope(workspace_id):
        async with deps.sessionmaker() as session:
            acct = await accounts.get(session, account_id)
            if acct is None:
                return PurgeResult(status="gone")
            if acct.deletion_requested_at is None:
                log.error("account_purge_refused", account_id=str(account_id), status=acct.status)
                return PurgeResult(status="not_deleting")
            if await workspace_status(session, workspace_id) != WorkspaceStatus.ACTIVE:
                return PurgeResult(status="workspace_deleting")  # purge_workspace takes it
            facts = _Account(
                platform=acct.platform,
                platform_account_id=acct.platform_account_id,
                requested_by=acct.deletion_requested_by_user_id,
            )
            await session.commit()

            if not await _delete_files(
                session, deps.media, workspace_id, account_id, result, file_batch, deadline
            ):
                return _continues(workspace_id, account_id, facts, result)

            steps: list[tuple[str, BatchDelete]] = [
                (table.name, _table_batch(table, workspace_id, account_id))
                for table in repo.account_tables()
            ]
            steps.append(("webhook_events", _webhook_batch(workspace_id, facts)))
            for name, delete_batch in steps:
                if not await _drain(session, name, delete_batch, result, batch, deadline):
                    return _continues(workspace_id, account_id, facts, result)

            for name, n in (await repo.settle_posts_without_accounts(session)).items():
                if n:
                    result.deleted[name] = n
            await session.commit()

            if not await _clear_keys(deps.redis, workspace_id, account_id):
                log.warning("account_purge_blocked", account_id=str(account_id), reasons=["cache"])
                raise AccountPurgeBlocked(account_id, ["cache"])

            await repo.delete_account(session, workspace_id, account_id)
            await session.commit()
    _audit("account_data_purged", workspace_id, account_id, facts, result)
    # Every open page drops the account, its conversations, comments and posts.
    await events.publish(deps.redis, workspace_id, "resync", {})
    return result


def _audit(
    name: str,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    facts: _Account,
    result: PurgeResult,
) -> None:
    """The audit line: who asked, what went (row counts per table, files), never content."""
    log.info(
        name,
        workspace_id=str(workspace_id),
        account_id=str(account_id),
        platform=facts.platform,
        requested_by=str(facts.requested_by) if facts.requested_by else None,
        source="member" if facts.requested_by else "meta",
        deleted=result.deleted,
        files=result.files,
    )


def _continues(
    workspace_id: uuid.UUID, account_id: uuid.UUID, facts: _Account, result: PurgeResult
) -> PurgeResult:
    result.status = "continue"
    _audit("account_purge_continues", workspace_id, account_id, facts, result)
    return result


def _table_batch(table: Table, workspace_id: uuid.UUID, account_id: uuid.UUID) -> BatchDelete:
    async def delete_batch(session: AsyncSession, limit: int) -> int:
        return await repo.delete_batch(session, table, workspace_id, account_id, limit)

    return delete_batch


def _webhook_batch(workspace_id: uuid.UUID, facts: _Account) -> BatchDelete:
    async def delete_batch(session: AsyncSession, limit: int) -> int:
        return await repo.delete_webhook_events(
            session, workspace_id, facts.platform_account_id, limit
        )

    return delete_batch


async def _drain(
    session: AsyncSession,
    name: str,
    delete_batch: BatchDelete,
    result: PurgeResult,
    batch: int,
    deadline: float,
) -> bool:
    """Delete the account's rows from one table, a batch per commit. False when the run's time
    ran out with rows left."""
    while True:
        n = await delete_batch(session, batch)
        await session.commit()
        if n:
            result.deleted[name] = result.deleted.get(name, 0) + n
        if n < batch:
            return True
        if time.monotonic() > deadline:
            return False


async def _delete_files(
    session: AsyncSession,
    media: MediaPurger,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    result: PurgeResult,
    file_batch: int,
    deadline: float,
) -> bool:
    """The files the account's messages own, a batch at a time: storage first, then the rows
    (so a failed storage call leaves the row to find them again). False when time ran out."""
    candidates = await repo.message_files(session, workspace_id, account_id)
    await session.commit()
    for start in range(0, len(candidates), file_batch):
        chunk = candidates[start : start + file_batch]
        shared = await repo.shared_files(
            session, workspace_id, account_id, [f.asset_id for f in chunk]
        )
        owned = [f for f in chunk if f.asset_id not in shared]
        if owned:
            try:
                await media.delete_files(
                    workspace_id, [StoredFile(f.public_id, f.resource_type) for f in owned]
                )
            except (CloudinaryError, httpx.HTTPError) as error:
                log.warning(
                    "account_purge_blocked",
                    account_id=str(account_id),
                    reasons=["media"],
                    error=str(error),
                )
                raise AccountPurgeBlocked(account_id, ["media"]) from error
            n = await repo.delete_assets(session, workspace_id, [f.asset_id for f in owned])
            result.files += len(owned)
            if n:
                result.deleted["media_assets"] = result.deleted.get("media_assets", 0) + n
        await session.commit()
        if start + file_batch < len(candidates) and time.monotonic() > deadline:
            return False
    return True


async def _clear_keys(redis: Redis, workspace_id: uuid.UUID, account_id: uuid.UUID) -> bool:
    """Every Valkey key naming the account (rate buckets, profile and template caches), and the
    workspace's event stream: its entries can carry the account's messages, and the resync that
    follows makes every open page refetch, so nothing else is lost with it."""
    try:
        doomed = [key async for key in redis.scan_iter(match=f"*{account_id}*", count=1000)]
        for start in range(0, len(doomed), KEY_DELETE_CHUNK):
            await redis.delete(*doomed[start : start + KEY_DELETE_CHUNK])
        await redis.delete(events.stream_key(workspace_id))
    except RedisError:
        log.warning("account_purge_cache_failed", account_id=str(account_id))
        return False
    return True


# ---------------------------------------------------------------- the sweeper


@dataclass(frozen=True)
class Sweep:
    requeued: int
    overdue: list[uuid.UUID]


async def sweep(pending: list[tuple[uuid.UUID, uuid.UUID, datetime]], now: datetime) -> Sweep:
    """Queue a purge for every account still deleting (``pending``: account, workspace, asked
    at; a waiting purge makes this a no-op) and alert on any still deleting after
    OVERDUE_AFTER: something outside the database keeps failing."""
    requeued = 0
    overdue: list[uuid.UUID] = []
    for account_id, workspace_id, requested_at in pending:
        requeued += int(await enqueue_purge_quietly(workspace_id, account_id))
        if now - requested_at > OVERDUE_AFTER:
            overdue.append(account_id)
            log.error(
                "alert",
                kind="account_purge_overdue",
                workspace_id=str(workspace_id),
                account_id=str(account_id),
                hours=round((now - requested_at).total_seconds() / 3600, 1),
                detail="see account_purge_blocked for what it waits on",
            )
    if pending:
        log.info("sweep_account_deletions", deleting=len(pending), requeued=requeued)
    return Sweep(requeued=requeued, overdue=overdue)
