"""Post metric snapshots (T6.5; FR-ANL-01): what snapshot_account_posts does for one account.

Every 15 minutes the snapshot_post_metrics tick finds accounts with a window due and queues this
work per account (bulk lane, TR-JOB-06). For each post with a window due (``ages.due_window``):

- 1 h and 6 h: the live counts (like_count, comments_count) only; Instagram's insights lag up to
  48 h.
- 24 h and later: the live counts plus the post's insights, when the account has granted them
  (Capability.POST_INSIGHTS; the scope is only requested with IG_REQUEST_INSIGHTS_SCOPE). Likes
  and comments come from the live counts when Instagram gives them, so they mean the same at
  every window; the insights fill them otherwise.
- The 72 h run (and any later one) re-reads the insights and marks the post's earlier snapshots
  final: Instagram only returns lifetime totals, so a value as of 24 h cannot be read again;
  what the re-read settles is that everything up to 24 h has been counted by 72 h. Rows from
  72 h on are final when written.
- A post Instagram no longer gives (deleted) gets an empty snapshot, so the window counts as
  captured and is not asked for again.

Each window is captured once: rows are inserted with ON CONFLICT DO NOTHING on (post, window) and
committed per post, so a re-run, a retry after a rate limit or a second worker writes nothing
twice. Retryable platform errors end the pass and go to the job's retry strategy (a rate limit
waits for the platform's regain time); a dead token or a refused account ends it quietly.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.models.analytics import LIVE_COUNT_WINDOWS, WINDOW_AGES, PostMetricSnapshot
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.media import MediaItem, MediaType
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import MediaCounts, MediaInsights, PlatformAdapter
from socialhood.platforms.buckets import Bucket, TokenBuckets
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.repositories import analytics as repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services.analytics.ages import (
    FINAL_WINDOWS,
    PROVISIONAL_WINDOWS,
    SNAPSHOT_HORIZON,
    WINDOWS,
    due_window,
    grace,
)

log = get_logger(__name__)

# Accounts that have posts to measure (TR-PL-11: by capability, never by platform name).
POST_CAPABILITIES = frozenset({Capability.COMMENTS, Capability.PUBLISH})
LIVE_STATUSES = (AccountStatus.ACTIVE, AccountStatus.ERROR)
MAX_INLINE_WAIT_S = 2.0  # wait this long for a bucket token; longer re-schedules the job

Sleep = Callable[[float], Awaitable[object]]


@dataclass
class SnapshotPass:
    """What one pass over an account captured: (post id, window) pairs."""

    captured: list[tuple[uuid.UUID, str]] = field(default_factory=list)


def due_condition(now: datetime) -> ColumnElement[bool]:
    """SQL for "this media item has a window due now and not captured": the same rule as
    ``ages.due_window``, for the tick that picks accounts."""
    per_window = []
    for window in WINDOWS:
        age = WINDOW_AGES[window]
        per_window.append(
            and_(
                MediaItem.posted_at <= now - age,
                MediaItem.posted_at > now - age - grace(window),
                ~exists().where(
                    PostMetricSnapshot.media_item_id == MediaItem.id,
                    PostMetricSnapshot.window == window.value,
                ),
            )
        )
    return and_(MediaItem.media_type != MediaType.STORY, or_(*per_window))


def measured(adapter: PlatformAdapter, acct: SocialAccount) -> bool:
    """Whether the account has posts whose metrics Social Hood records."""
    return bool(adapter.capabilities_for(acct) & POST_CAPABILITIES)


async def measured_account(
    sessionmaker: async_sessionmaker[AsyncSession], deps: PlatformDeps, account_id: uuid.UUID
) -> tuple[SocialAccount, PlatformAdapter] | None:
    """The live account and its adapter, or None when it has nothing to measure (in the
    current workspace scope)."""
    async with sessionmaker() as session:
        acct = await accounts.get(session, account_id)
    if acct is None or acct.status not in LIVE_STATUSES:
        return None
    try:
        adapter = adapter_for(acct, deps)
    except PlatformError as error:
        log.warning("snapshot_skipped", account_id=str(account_id), error_code=error.code)
        return None
    return (acct, adapter) if measured(adapter, acct) else None


async def take_token(
    buckets: TokenBuckets | None, account_id: uuid.UUID, sleep: Sleep = asyncio.sleep
) -> None:
    """One IG_INSIGHTS token for the next call (TR-PL-09). A short wait happens here; a longer
    one raises a rate limit, so the job re-runs when a token is free. A Valkey outage never
    blocks the snapshots (the platform still enforces its own limits)."""
    if buckets is None:
        return
    waited = 0.0
    while True:
        try:
            wait = await buckets.take(Bucket.IG_INSIGHTS, str(account_id))
        except Exception:
            log.warning("token_bucket_unavailable", bucket=str(Bucket.IG_INSIGHTS))
            return
        if wait <= 0:
            return
        if waited + wait > MAX_INLINE_WAIT_S:
            raise PlatformError(
                "platform_rate_limited",
                message="Waiting for this account's insights rate",
                retry_after_s=wait,
            )
        await sleep(wait)
        waited += wait


def snapshot_metrics(counts: MediaCounts | None, insights: MediaInsights | None) -> dict[str, int]:
    """The stored ``metrics``: the known insight values, with likes and comments taken from the
    live counts when the platform gave them."""
    metrics = insights.metrics() if insights is not None else {}
    if counts is not None:
        if counts.like_count is not None:
            metrics["likes"] = counts.like_count
        if counts.comments_count is not None:
            metrics["comments"] = counts.comments_count
    return metrics


async def _due_posts(
    session: AsyncSession, account_id: uuid.UUID, now: datetime
) -> list[tuple[MediaItem, str]]:
    posts = list(
        (
            await session.scalars(
                select(MediaItem)
                .where(
                    MediaItem.social_account_id == account_id,
                    MediaItem.media_type != MediaType.STORY,
                    MediaItem.posted_at > now - SNAPSHOT_HORIZON,
                    MediaItem.posted_at <= now - WINDOW_AGES[WINDOWS[0]],
                )
                .order_by(MediaItem.posted_at)
            )
        ).all()
    )
    taken: dict[uuid.UUID, set[str]] = defaultdict(set)
    if posts:
        rows = await session.execute(
            select(PostMetricSnapshot.media_item_id, PostMetricSnapshot.window).where(
                PostMetricSnapshot.media_item_id.in_([p.id for p in posts])
            )
        )
        for post_id, taken_window in rows.all():
            taken[post_id].add(taken_window)
    due: list[tuple[MediaItem, str]] = []
    for post in posts:
        window = due_window(post.posted_at, taken[post.id], now)
        if window is not None:
            due.append((post, window.value))
    return due


async def snapshot_account_posts(
    sessionmaker: async_sessionmaker[AsyncSession],
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    now: datetime | None = None,
    buckets: TokenBuckets | None = None,
    sleep: Sleep = asyncio.sleep,
) -> SnapshotPass | None:
    """Capture every window due now for the account's posts. None when the account has nothing
    to measure (disconnected, needs reconnecting, no posts capability)."""
    now = now or datetime.now(UTC)
    with workspace_scope(workspace_id):
        loaded = await measured_account(sessionmaker, deps, account_id)
        if loaded is None:
            return None
        acct, adapter = loaded
        with_insights = Capability.POST_INSIGHTS in adapter.capabilities_for(acct)
        async with sessionmaker() as session:
            due = await _due_posts(session, acct.id, now)
        done = SnapshotPass()
        for post, window in due:
            try:
                counts, insights = await _read(
                    adapter, acct, post, window, with_insights, buckets, sleep
                )
            except PlatformError as error:
                if error.retryable:
                    raise
                log.warning("snapshot_pass_stopped", account_id=str(acct.id), error_code=error.code)
                break
            async with sessionmaker() as session:
                inserted = await repo.insert_snapshot(
                    session,
                    media_item_id=post.id,
                    window=window,
                    captured_at=now,
                    metrics=snapshot_metrics(counts, insights),
                    insights_final=window in FINAL_WINDOWS,
                )
                if window in FINAL_WINDOWS:
                    await repo.mark_final(session, post.id, PROVISIONAL_WINDOWS)
                if counts is not None:
                    await repo.set_live_counts(
                        session,
                        post.id,
                        like_count=counts.like_count,
                        comments_count=counts.comments_count,
                    )
                await session.commit()
            if inserted:
                done.captured.append((post.id, window))
    log.info("post_snapshots", account_id=str(account_id), captured=len(done.captured))
    return done


async def _read(
    adapter: PlatformAdapter,
    acct: SocialAccount,
    post: MediaItem,
    window: str,
    with_insights: bool,
    buckets: TokenBuckets | None,
    sleep: Sleep,
) -> tuple[MediaCounts | None, MediaInsights | None]:
    await take_token(buckets, acct.id, sleep)
    counts = await adapter.get_media_counts(acct, post.platform_media_id)
    if counts is None or window in LIVE_COUNT_WINDOWS or not with_insights:
        return counts, None
    await take_token(buckets, acct.id, sleep)
    insights = await adapter.get_media_insights(
        acct, post.platform_media_id, media_type=post.media_type
    )
    return counts, insights
