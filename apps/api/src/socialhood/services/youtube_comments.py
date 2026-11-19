"""YouTube comment polling (YT4). YouTube sends no comment webhooks, so every 15 minutes
``dispatch_youtube_comments`` (jobs/tasks/youtube_comments.py) queues ``poll_youtube_comments``
for each live YouTube channel, and this reads the channel's comment threads newest first.

- Up to MAX_PAGES pages of ``commentThreads.list`` (100 threads each, 1 unit a page) go through
  the comment intake (services/automations/comments.py), which skips the channel's own comments
  and stores each comment once. The poll stops at the first page that stored nothing new.
- The first poll of a channel (no comment of it stored yet) is a backfill: stored the same way, no
  events, the posts recounted at the end of each page. Later polls are live: comment.created,
  post.updated and the post's total, like a webhook. No automation ever runs on a YouTube comment.
- The project's YouTube units (platforms/buckets.YouTubeQuota): a page is read only while the day's
  count is under YOUTUBE_POLL_CEILING, so people's replies keep the rest.
- A platform error ends the poll (logged); the next one, 15 minutes later, tries again.
- The sandbox channel's stateless comments are read per stored video
  (platforms/youtube/comments.SandboxComments).

shortcut: threads come newest thread first, so a new reply on an old thread is missed until the
6-hourly media sync's per-post backfill reads that video; poll per video if replies matter more.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import PlatformComment
from socialhood.platforms.buckets import YOUTUBE_POLL_CEILING, YOUTUBE_READ_UNITS, YouTubeQuota
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.adapter import YouTubeAdapter
from socialhood.platforms.youtube.comments import comments_for
from socialhood.platforms.youtube.publishing import is_sandbox_channel
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import comment_analyses as stats
from socialhood.repositories import comments as comments_repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services.comments import views

log = get_logger(__name__)

MAX_PAGES = 5
LIVE = (AccountStatus.ACTIVE, AccountStatus.ERROR)
SANDBOX_VIDEOS = 25


@dataclass(frozen=True)
class PollResult:
    pages: int = 0
    stored: int = 0
    backfill: bool = False


def poll_key(account_id: uuid.UUID) -> str:
    return f"ytcomments:{account_id}"


async def poll_account(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    now: datetime | None = None,
) -> PollResult | None:
    """The poll_youtube_comments job; None when the channel can't be read (gone, not live, no
    COMMENTS, the day's units used up before the first page)."""
    now = now or datetime.now(UTC)
    quota = YouTubeQuota(redis)
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            acct = await accounts.get(session, account_id)
            if acct is None or acct.platform != "youtube" or acct.status not in LIVE:
                return None
            backfill = not await comments_repo.account_has_comments(session, acct.id)
            videos = (
                [
                    i.platform_media_id
                    for i, _ in await stats.stored_counts(session, acct.id, SANDBOX_VIDEOS)
                ]
                if is_sandbox_channel(acct)
                else []
            )
        adapter = YouTubeAdapter(deps)
        try:
            if Capability.COMMENTS not in adapter.capabilities_for(acct):
                return None
            token = await adapter.access_token(acct)
        except PlatformError as error:
            log.warning("youtube_poll_skipped", account_id=str(account_id), error_code=error.code)
            await _flag_reconnect(sessionmaker, redis, acct, error)
            return None
        client = comments_for(acct, deps)
        sources: list[tuple[str | None, str | None]] = (
            [(acct.platform_account_id, v) for v in videos]
            if is_sandbox_channel(acct)
            else [(acct.platform_account_id, None)]
        )
        pages = stored = 0
        for channel_id, video_id in sources:
            cursor: str | None = None
            for _ in range(MAX_PAGES):
                if not await quota.take(YOUTUBE_READ_UNITS, ceiling=YOUTUBE_POLL_CEILING, now=now):
                    log.warning("youtube_poll_quota_reached", account_id=str(account_id))
                    return PollResult(pages, stored, backfill) if pages else None
                try:
                    page = await client.threads(
                        token, channel_id=channel_id, video_id=video_id, cursor=cursor
                    )
                except PlatformError as error:
                    log.warning(
                        "youtube_poll_failed", account_id=str(account_id), error_code=error.code
                    )
                    await _flag_reconnect(sessionmaker, redis, acct, error)
                    return PollResult(pages, stored, backfill)
                pages += 1
                new = await _store(sessionmaker, redis, deps, acct, page.comments, now, backfill)
                stored += new
                if not new or not page.next_cursor:
                    break
                cursor = page.next_cursor
    log.info("youtube_comments_polled", account_id=str(account_id), pages=pages, stored=stored)
    return PollResult(pages, stored, backfill)


async def _flag_reconnect(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    acct: SocialAccount,
    error: PlatformError,
) -> None:
    """Google revoked or expired the token (invalid_grant): show the channel as needing a
    reconnect, with the usual notification, instead of failing quietly every 15 minutes."""
    if error.code != "account_needs_reconnect":
        return
    from socialhood.services.connections import mark_needs_reconnect

    with workspace_scope(acct.workspace_id):
        async with sessionmaker() as session:
            fresh = await accounts.get(session, acct.id)
            if fresh is None or fresh.status != AccountStatus.ACTIVE:
                return
            await mark_needs_reconnect(session, fresh, "YouTube access was removed or has expired.")
            await commit_and_publish(session, redis)


async def _store(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    acct: SocialAccount,
    comments: Sequence[PlatformComment],
    now: datetime,
    backfill: bool,
) -> int:
    """One page through the intake, in one transaction; returns how many were new."""
    from socialhood.services.automations.comments import intake

    new = 0
    async with sessionmaker() as session:
        posts: set[uuid.UUID] = set()
        for comment in comments:
            taken = await intake(
                session, acct, comment, deps=lambda: deps, now=now, backfill=backfill
            )
            if taken.comment is not None:
                new += 1
                posts.add(taken.comment.media_item_id)
        if backfill and posts:
            for post in await stats.recount(session, posts):
                views.queue_post(session, post)
        await commit_and_publish(session, redis)
    return new
