"""After a connect: the account's recent posts and conversation history (T3.14, FR-CON-01).

``sync_account_media`` upserts the 25 most recent posts into media_items, then queues the comment
backfill for posts missing comments (T6.1, TR-WH-08: services/comments/backfill).
``backfill_account`` stores recent threads through the same ingest as webhooks, with each
message's real direction; conversations appear in the inbox as each thread commits. Both depend
on the adapter's capabilities, never on platform names (TR-PL-11), and both are safe to run
again: rows are keyed by their platform ids.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import PlatformAdapter
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.realtime.events import commit_and_publish, queue_conversation
from socialhood.repositories import ingest as rows
from socialhood.repositories import social_accounts as accounts
from socialhood.services.automations import posts as automation_posts
from socialhood.services.comments import backfill as comment_backfill
from socialhood.services.ingest import ingest

log = get_logger(__name__)

RECENT_POSTS = 25  # FR-CON-01
RECENT_THREADS = 20  # the Conversations API's page; each thread brings its last 20 messages
POST_CAPABILITIES = frozenset({Capability.COMMENTS, Capability.PUBLISH})


async def start_initial_sync(acct: SocialAccount) -> None:
    """Enqueue sync_media and backfill_account for a newly connected (or reconnected) account.
    Runs after the connect has committed; a failed enqueue is logged, never raised."""
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.sync import backfill_account, sync_media

    for task, key in (
        (sync_media, f"mediasync:{acct.id}"),
        (backfill_account, f"backfill:{acct.id}"),
    ):
        try:
            await enqueue(
                task, key=key, workspace_id=str(acct.workspace_id), account_id=str(acct.id)
            )
        except Exception:
            log.warning("initial_sync_enqueue_failed", account_id=str(acct.id), task=task.name)


async def _load(
    sessionmaker: async_sessionmaker[AsyncSession],
    deps: PlatformDeps,
    account_id: uuid.UUID,
    needs: frozenset[Capability],
) -> tuple[SocialAccount, PlatformAdapter] | None:
    async with sessionmaker() as session:
        acct = await accounts.get(session, account_id)
    if acct is None or acct.status == AccountStatus.DISCONNECTED:
        return None
    try:
        adapter = adapter_for(acct, deps)
    except PlatformError as error:
        log.warning("sync_skipped", account_id=str(account_id), error_code=error.code)
        return None
    if not adapter.capabilities_for(acct) & needs:
        return None
    return acct, adapter


def _give_up(error: PlatformError, what: str, account_id: uuid.UUID) -> None:
    """Retryable errors go back to the job's retry strategy; the rest end this run."""
    if error.retryable:
        raise error
    log.warning(what, account_id=str(account_id), error_code=error.code)


# ---------------------------------------------------------------- posts


async def sync_account_media(
    sessionmaker: async_sessionmaker[AsyncSession],
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    now: datetime | None = None,
) -> int | None:
    """Upsert the account's recent posts; returns how many, or None when nothing ran."""
    now = now or datetime.now(UTC)
    with workspace_scope(workspace_id):
        loaded = await _load(sessionmaker, deps, account_id, POST_CAPABILITIES)
        if loaded is None:
            return None
        acct, adapter = loaded
        try:
            media = await adapter.list_media(acct, limit=RECENT_POSTS)
        except PlatformError as error:
            _give_up(error, "media_sync_failed", account_id)
            return None
        async with sessionmaker() as session:
            for item in media:
                await rows.upsert_media_item(
                    session, social_account_id=acct.id, media=item, synced_at=now
                )
            await automation_posts.link_next_posts(session, acct.id)  # FR-AUT-18
            await accounts.update(session, acct.id, media_synced_at=now)
            await session.commit()
            await comment_backfill.after_media_sync(session, acct)  # T6.1, TR-WH-08
    log.info("media_synced", account_id=str(account_id), posts=len(media))
    return len(media)


# ---------------------------------------------------------------- conversations


async def backfill_account(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    now: datetime | None = None,
) -> int | None:
    """Store recent conversations; returns the number of new messages, or None when the account
    cannot backfill (no capability, disconnected) or the platform refused."""
    now = now or datetime.now(UTC)
    with workspace_scope(workspace_id):
        loaded = await _load(
            sessionmaker, deps, account_id, frozenset({Capability.CONVERSATION_BACKFILL})
        )
        if loaded is None:
            return None
        acct, adapter = loaded
        try:
            threads = await adapter.list_threads(acct, limit=RECENT_THREADS)
        except PlatformError as error:
            _give_up(error, "backfill_failed", account_id)
            return None
        created = 0
        for thread in threads:
            if not thread.messages:
                continue
            async with sessionmaker() as session:  # one commit per thread: each shows up at once
                result = await ingest(session, acct, thread.messages, now=now, backfill=True)
                found = await rows.conversation_for_contact_ref(
                    session, acct.id, thread.contact_ref
                )
                if found is not None:
                    conv, contact = found
                    conv.platform_conversation_id = thread.platform_conversation_id
                    if contact.username is None and thread.contact_username:
                        contact.username = thread.contact_username
                        await session.flush()
                        await queue_conversation(session, conv, now=now, contact=contact)
                await commit_and_publish(session, redis)
            created += len(result.created_message_ids)
        async with sessionmaker() as session:
            await accounts.update(session, acct.id, backfilled_at=now)
            await session.commit()
    log.info(
        "account_backfilled", account_id=str(account_id), threads=len(threads), messages=created
    )
    return created
