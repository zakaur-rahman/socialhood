"""Comment backfill on connect (T6.1; FR-CMT-01, F-12, TR-WH-08).

``sync_media`` stores the account's 25 most recent posts; right after, ``after_media_sync`` queues
``backfill_comments(account_id)`` (bulk lane, lock ``cmtbackfill:{account_id}``) when one of them
has fewer stored comments than Instagram's ``comments_count``. On connect that is every post with
comments; on the 6-hourly sync it is a post whose webhooks were missed (TR-WH-08).

The job reads each such post's comments through the adapter's ``list_comments``, page by page, up
to 200 per post (replies included), and takes each through the webhook intake
(services/automations/comments) with ``backfill=True``: the account's own comments are skipped,
contacts are stored by the commenter's IGSID and each comment is inserted once (ON CONFLICT DO
NOTHING), so running it again, or a webhook for the same comment, stores nothing new. No automation
runs on a backfilled comment. Each post commits on its own; its comment stats are recounted and
post.updated published. The comments wait for analyze_comments like any other (T6.2).

A temporary platform error fails the job, which retries (posts already stored are not stored
again); a post Instagram refuses is skipped; an account that needs reconnecting stops the run.
The account's own replies are counted by Instagram but never stored, so a post it replied on keeps
looking short and is read again at the next sync (at most 25 posts, each a few calls).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import PlatformAdapter, PlatformComment
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import comment_analyses as stats
from socialhood.repositories import social_accounts as accounts
from socialhood.services.comments import views

log = get_logger(__name__)

RECENT_POSTS = 25  # FR-CMT-01
MAX_PER_POST = 200


@dataclass(frozen=True)
class BackfillResult:
    posts: int = 0  # posts read
    stored: int = 0  # new comments


def backfill_key(account_id: uuid.UUID) -> str:
    return f"cmtbackfill:{account_id}"


async def enqueue_backfill(account_id: uuid.UUID, workspace_id: uuid.UUID) -> bool:
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.comments import backfill_comments

    key = backfill_key(account_id)
    return await enqueue(
        backfill_comments,
        key=key,
        lock=key,
        workspace_id=str(workspace_id),
        account_id=str(account_id),
    )


def _missing(stored: int, comments_count: int | None) -> bool:
    """Instagram counts more comments than we store (an unknown count is read to find out)."""
    return comments_count is None or stored < comments_count


async def after_media_sync(session: AsyncSession, acct: SocialAccount) -> bool:
    """Called by sync_media once the posts are stored: queue the backfill when a recent post is
    missing comments. A failed enqueue is logged, never raised (the next sync tries again)."""
    posts = await stats.stored_counts(session, acct.id, RECENT_POSTS)
    if not any(_missing(stored, item.comments_count) for item, stored in posts):
        return False
    try:
        return await enqueue_backfill(acct.id, acct.workspace_id)
    except Exception:
        log.warning("comment_backfill_enqueue_failed", account_id=str(acct.id))
        return False


async def _read(
    adapter: PlatformAdapter, acct: SocialAccount, media_ref: str
) -> list[PlatformComment]:
    """Up to MAX_PER_POST of the post's comments, page by page."""
    collected: list[PlatformComment] = []
    cursor: str | None = None
    while len(collected) < MAX_PER_POST:
        page = await adapter.list_comments(acct, media_ref, cursor=cursor)
        collected.extend(page.comments)
        if not page.next_cursor or not page.comments:
            break
        cursor = page.next_cursor
    return collected[:MAX_PER_POST]


async def backfill_comments(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    now: datetime | None = None,
) -> BackfillResult | None:
    """The backfill_comments job; None when the account cannot have comments (disconnected, no
    COMMENTS capability) or needs reconnecting."""
    from socialhood.services.automations.comments import intake

    now = now or datetime.now(UTC)
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            acct = await accounts.get(session, account_id)
            if acct is None or acct.status in (
                AccountStatus.DISCONNECTED,
                AccountStatus.NEEDS_RECONNECT,
            ):
                return None
            posts = await stats.stored_counts(session, acct.id, RECENT_POSTS)
        try:
            adapter = adapter_for(acct, deps)
        except PlatformError as error:
            log.warning("comment_backfill_skipped", account_id=str(account_id), error=error.code)
            return None
        if Capability.COMMENTS not in adapter.capabilities_for(acct):
            return None
        read = stored = 0
        for item, count in posts:
            if not _missing(count, item.comments_count):
                continue
            try:
                comments = await _read(adapter, acct, item.platform_media_id)
            except PlatformError as error:
                if error.retryable:
                    raise
                log.warning(
                    "comment_backfill_post_failed",
                    account_id=str(account_id),
                    media_item_id=str(item.id),
                    error_code=error.code,
                )
                if error.code == "account_needs_reconnect":
                    break
                continue
            read += 1
            async with sessionmaker() as session:
                new = 0
                for comment in comments:
                    taken = await intake(
                        session, acct, comment, deps=lambda: deps, now=now, backfill=True
                    )
                    new += taken.comment is not None
                if new:
                    for post in await stats.recount(session, [item.id]):
                        views.queue_post(session, post)
                await commit_and_publish(session, redis)
            stored += new
    log.info("comments_backfilled", account_id=str(account_id), posts=read, comments=stored)
    return BackfillResult(posts=read, stored=stored)
