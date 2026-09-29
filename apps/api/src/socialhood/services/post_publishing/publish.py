"""Publishing one target (T7.3; F-13, FR-PUB-05, FR-PUB-06, FR-PUB-11, FR-AUT-18, TR-JOB-04,
TR-JOB-05). Each function is a job's body and runs in the post's workspace scope. Database locks
are never held across a platform call: a step reads what it needs, calls Instagram, then locks the
post and the target again (post first) and checks nothing moved before writing.

publish_target: the account must still be connected and able to publish (else the target fails,
or is canceled when the account was disconnected); the quota is read first (none left: failed
"Instagram's daily publishing limit reached"); then the containers are created from the assets'
delivery URLs: one for an image or a Reel, the children in order for a carousel (Meta refuses a
carousel whose children are still processing, so poll_container creates the carousel itself
once they are FINISHED). The target becomes ``container_created`` and poll 1 is queued at once.
Retryable errors retry while the job will (the target stays ``publishing``); the last try or a
refusal fails the target.

poll_container(n): one round of status reads, never more than one per container a minute.
Polls 1 to 5 run a minute apart, then 5 minutes apart up to poll 10; a video still IN_PROGRESS
at poll 10 fails with "Instagram took too long to process the video". ERROR and EXPIRED fail
with Instagram's reason. FINISHED publishes; PUBLISHED means an earlier publish went out and its
answer was lost (or the worker died before storing it), so the post is found with
find_published_media instead: a container is never published twice, because every poll reads
the container's status before publishing it. A lost publish answer (delivery_unknown), a
retryable publish error or a published post not found yet waits for the next poll, up to
EXTRA_POLLS past poll 10. Publishing stores the platform media id and permalink, inserts the
media_items row (published_target_id), links the automations scoped to the post and the
account's waiting next-post automations (FR-AUT-18), derives the post's status and queues
post_first_comment, all in one transaction.

A post ending failed or partly published notifies its owners and admins with the reasons
(FR-PUB-06). Every change queues ``scheduled_post.updated``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.media import MediaAsset, MediaType
from socialhood.models.publishing import (
    CAROUSEL_MAX_ASSETS,
    CAROUSEL_MIN_ASSETS,
    POLL_FAST_COUNT,
    POLL_FAST_DELAY,
    POLL_MAX,
    POLL_SLOW_DELAY,
    PROCESSING_TIMEOUT_MESSAGE,
    PostFormat,
    ScheduledPost,
    ScheduledPostStatus,
    ScheduledPostTarget,
    TargetStatus,
)
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import (
    ContainerMedia,
    ContainerStatus,
    PlatformAdapter,
    PlatformMedia,
    PublishingQuota,
)
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.outcome import DELIVERY_UNKNOWN
from socialhood.platforms.registry import adapter_for
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import publish_targets as repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services.automations import posts as automation_posts
from socialhood.services.connections import mark_needs_reconnect, platform_label
from socialhood.services.media_assets import delivery_url
from socialhood.services.notifications import notify_admins
from socialhood.services.post_publishing import claims
from socialhood.services.post_publishing.projection import derive_status, queue_post_updated

log = get_logger(__name__)

# Polls allowed past POLL_MAX when the container is done but the publish is not settled yet (a
# lost answer, a retryable publish error, a published post not found yet).
EXTRA_POLLS = 3
# find_published_media looks for posts from a little before the claim (clocks differ).
CLOCK_SKEW = timedelta(minutes=2)
LIMIT_REACHED = "Instagram's daily publishing limit reached"
EXPIRED_REASON = "The upload expired on Instagram before it was published."
PROCESSING_ERROR = "Instagram couldn't process the media."
BROKEN_POST = "This post's media changed after it was scheduled. Edit it and try again."
UNKNOWN_COMMENT_ID = "unknown"  # a first comment Instagram accepted without returning its id

Outcome = Literal["containers_created", "waiting", "published", "failed", "canceled", "skipped"]
CommentOutcome = Literal["posted", "failed", "skipped"]
WillRetry = Callable[[PlatformError], bool]


def poll_delay(n: int) -> timedelta:
    """The wait before poll ``n`` (n ≥ 2; poll 1 runs as soon as the containers exist)."""
    return POLL_FAST_DELAY if n <= POLL_FAST_COUNT else POLL_SLOW_DELAY


# ---------------------------------------------------------------- reasons (FR-PUB-06)


def _handle(acct: SocialAccount | None) -> str:
    return f"@{acct.username}" if acct is not None and acct.username else "This account"


def _specific(error: PlatformError) -> bool:
    """An unavailable error with a reason of its own (a publishing subcode Instagram explained,
    or the processing timeout) rather than a bare outage."""
    return "/" in (error.platform_code or "") or error.message == PROCESSING_TIMEOUT_MESSAGE


def reason_for(error: PlatformError, acct: SocialAccount) -> str:
    """What a failed target shows: Instagram's reason when it gave one."""
    name = platform_label(acct)
    handle = _handle(acct)
    if error.code == "platform_unavailable":
        return error.message if _specific(error) else f"{name} didn't respond. Try again."
    reasons = {
        "account_needs_reconnect": f"{handle} needs reconnecting before it can publish.",
        "capability_unavailable": f"{handle} can't publish posts.",
        "platform_rate_limited": f"{name} is limiting this account. Try again later.",
        "platform_rejected": error.message or f"{name} refused the post.",
        DELIVERY_UNKNOWN: (
            f"We couldn't confirm {name} published this post. Check {handle} before trying again."
        ),
    }
    return reasons.get(error.code, error.message or "Couldn't publish this post.")


def _unconfirmed() -> PlatformError:
    return PlatformError(DELIVERY_UNKNOWN, retryable=False)


# ---------------------------------------------------------------- shared steps


@dataclass(frozen=True)
class _Stop:
    """Why the account can't publish: the target ends ``status`` with this error."""

    status: TargetStatus
    code: str
    message: str


def _adapter(acct: SocialAccount, deps: PlatformDeps) -> PlatformAdapter | _Stop:
    handle = _handle(acct)
    if acct.status == AccountStatus.DISCONNECTED:
        return _Stop(
            TargetStatus.CANCELED,
            "account_disconnected",
            f"{handle} was disconnected before the post published.",
        )
    if acct.status == AccountStatus.NEEDS_RECONNECT:
        return _Stop(
            TargetStatus.FAILED,
            "account_needs_reconnect",
            f"{handle} needs reconnecting before it can publish.",
        )
    try:
        adapter = adapter_for(acct, deps)
    except PlatformError as error:
        return _Stop(TargetStatus.FAILED, error.code, error.message or "Couldn't publish.")
    if Capability.PUBLISH not in adapter.capabilities_for(acct):
        return _Stop(
            TargetStatus.FAILED, "capability_unavailable", f"{handle} can't publish posts."
        )
    return adapter


def _caption(post: ScheduledPost, target: ScheduledPostTarget) -> str:
    return target.caption_override if target.caption_override is not None else post.caption


def container_media(post: ScheduledPost, assets: Sequence[MediaAsset]) -> list[ContainerMedia]:
    """The post's media by their delivery URLs (JPEG images, H.264 MP4 video; TR-MED-02), or
    [] when they no longer make the post's format (§5.7 format rules)."""
    media: list[ContainerMedia] = []
    for asset in assets:
        if asset.resource_type not in ("image", "video") or not asset.secure_url:
            return []
        kind: Literal["image", "video"] = "image" if asset.resource_type == "image" else "video"
        media.append(ContainerMedia(kind=kind, url=delivery_url(asset.secure_url, kind)))
    kinds = [m.kind for m in media]
    if post.format == PostFormat.IMAGE and kinds == ["image"]:
        return media
    if post.format == PostFormat.REEL and kinds == ["video"]:
        return media
    if post.format == PostFormat.CAROUSEL and (
        CAROUSEL_MIN_ASSETS <= len(media) <= CAROUSEL_MAX_ASSETS
    ):
        return media
    return []


async def _notify_failure(
    session: AsyncSession, post: ScheduledPost, targets: Sequence[ScheduledPostTarget]
) -> None:
    """FR-PUB-06: the owners and admins learn a post failed or published on some accounts only,
    and why. Once per publish time (a retried post that fails again notifies again)."""
    missed = [t for t in targets if t.status in (TargetStatus.FAILED, TargetStatus.CANCELED)]
    lines = []
    for target in missed[:3]:
        acct = await accounts.get(session, target.social_account_id)
        lines.append(f"{_handle(acct)}: {target.error_message or 'no reason given'}")
    if len(missed) > 3:
        lines.append(f"and {len(missed) - 3} more")
    excerpt = post.caption.strip().splitlines()[0][:40] if post.caption.strip() else ""
    subject = f'"{excerpt}"' if excerpt else "Your post"
    failed = post.status == ScheduledPostStatus.FAILED
    body = (
        f"{subject} didn't publish. " if failed else f"{subject} published on some accounts only. "
    ) + "; ".join(lines)
    at = int(post.publish_at.timestamp()) if post.publish_at else 0
    await notify_admins(
        session,
        type="post_failed",
        severity="critical" if failed else "warning",
        title="Post didn't publish" if failed else "Post partly published",
        body=body,
        link=f"/schedule/{post.id}",
        dedupe_key=f"post_failed:{post.id}:{at}",
    )


async def settle(
    session: AsyncSession,
    post: ScheduledPost,
    target: ScheduledPostTarget,
    status: TargetStatus,
    *,
    code: str | None = None,
    message: str | None = None,
    media: PlatformMedia | None = None,
) -> None:
    """The target ends ``status``; the post's status is derived again (the caller holds both
    rows) and its owners notified when it failed or partly published. Queues the event; the
    caller commits."""
    target.status = status
    target.error_code = code
    target.error_message = message
    if media is not None:
        target.platform_media_id = media.platform_media_id
        target.permalink = media.permalink
        target.published_at = media.posted_at
        if post.published_at is None or media.posted_at < post.published_at:
            post.published_at = media.posted_at
    await session.flush()
    targets = await repo.targets_of(session, post.id)
    derived = derive_status(t.status for t in targets)
    if derived is not None and derived != post.status:
        post.status = derived
        if derived in (ScheduledPostStatus.FAILED, ScheduledPostStatus.PARTIALLY_PUBLISHED):
            await _notify_failure(session, post, targets)
    await queue_post_updated(session, post)
    log.info(
        "publish_target_settled",
        target_id=str(target.id),
        post_id=str(post.id),
        status=str(status),
        post_status=post.status,
        error_code=code,
    )


async def _end(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    target_id: uuid.UUID,
    *,
    expect: TargetStatus,
    poll: int | None = None,
    status: TargetStatus = TargetStatus.FAILED,
    code: str,
    message: str,
    reconnect: SocialAccount | None = None,
) -> Outcome:
    """Fail (or cancel) the target, if it is still where this step left it."""
    async with sessionmaker() as session:
        locked = await repo.lock_post_and_target(session, target_id)
        if locked is None:
            return "skipped"
        post, target = locked
        if target.status != expect or (poll is not None and target.poll_count != poll):
            await session.rollback()
            return "skipped"
        if reconnect is not None:
            await mark_needs_reconnect(
                session,
                reconnect,
                f"{platform_label(reconnect)} stopped accepting this connection.",
            )
        await settle(session, post, target, status, code=code, message=message)
        await commit_and_publish(session, redis)
    return "canceled" if status == TargetStatus.CANCELED else "failed"


async def _end_with(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    target_id: uuid.UUID,
    error: PlatformError,
    acct: SocialAccount,
    *,
    expect: TargetStatus,
    poll: int | None = None,
) -> Outcome:
    return await _end(
        sessionmaker,
        redis,
        target_id,
        expect=expect,
        poll=poll,
        code=error.code,
        message=reason_for(error, acct),
        reconnect=acct if error.code == "account_needs_reconnect" else None,
    )


# ---------------------------------------------------------------- enqueues (by name: jobs/)


async def enqueue_poll(
    target_id: uuid.UUID, workspace_id: uuid.UUID, n: int, *, delay_s: float = 0
) -> bool:
    """poll_container(n) under ``poll:{target_id}:{n}``; one poll of a target runs at a time.
    A failed enqueue is logged: the sweeper finds the idle target and queues the poll again."""
    from socialhood.jobs.app import INTERACTIVE
    from socialhood.jobs.enqueue import enqueue_named

    try:
        return await enqueue_named(
            "poll_container",
            lane=INTERACTIVE,
            key=f"poll:{target_id}:{n}",
            lock=f"poll:{target_id}",
            delay_s=delay_s,
            target_id=str(target_id),
            n=n,
            workspace_id=str(workspace_id),
        )
    except Exception:
        log.warning("poll_enqueue_failed", target_id=str(target_id), n=n)
        return False


async def enqueue_first_comment(target_id: uuid.UUID, workspace_id: uuid.UUID) -> bool:
    from socialhood.jobs.app import INTERACTIVE
    from socialhood.jobs.enqueue import enqueue_named

    try:
        return await enqueue_named(
            "post_first_comment",
            lane=INTERACTIVE,
            key=f"firstc:{target_id}",
            lock=f"firstc:{target_id}",
            target_id=str(target_id),
            workspace_id=str(workspace_id),
        )
    except Exception:
        log.warning("first_comment_enqueue_failed", target_id=str(target_id))
        return False


# ---------------------------------------------------------------- publish_target


async def publish_target(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    target_id: uuid.UUID,
    will_retry: WillRetry,
    now: datetime | None = None,
) -> Outcome:
    """Check the quota and create the target's containers (FR-PUB-05). A pending target of a due
    post (publish now enqueues it directly) is claimed here."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        locked = await repo.lock_post_and_target(session, target_id)
        if locked is None:
            return "skipped"
        post, target = locked
        claimed = target.status == TargetStatus.PENDING and claims.is_due(post, now)
        if claimed:
            claims.claim_target(post, target, now)
        elif target.status != TargetStatus.PUBLISHING:
            await session.rollback()
            return "skipped"
        acct = await accounts.get(session, target.social_account_id)
        if acct is None:  # pragma: no cover - deleting the account deletes its targets
            await session.rollback()
            return "skipped"
        got = _adapter(acct, deps)
        if isinstance(got, _Stop):
            await settle(session, post, target, got.status, code=got.code, message=got.message)
            await commit_and_publish(session, redis)
            return "canceled" if got.status == TargetStatus.CANCELED else "failed"
        media = container_media(post, await repo.assets_of(session, post.id))
        if not media:
            await settle(
                session,
                post,
                target,
                TargetStatus.FAILED,
                code="validation_error",
                message=BROKEN_POST,
            )
            await commit_and_publish(session, redis)
            return "failed"
        if claimed:
            await queue_post_updated(session, post)
        await commit_and_publish(session, redis)
    adapter, caption, workspace_id = got, _caption(post, target), post.workspace_id

    try:
        quota = await _quota(adapter, acct)
        if quota is not None and quota.remaining <= 0:
            return await _end(
                sessionmaker,
                redis,
                target_id,
                expect=TargetStatus.PUBLISHING,
                code="platform_rejected",
                message=LIMIT_REACHED,
            )
        container_id, children = await _create(adapter, acct, post.format, media, caption)
    except PlatformError as error:
        if error.retryable and will_retry(error):
            log.info("publish_target_retry", target_id=str(target_id), error_code=error.code)
            raise
        return await _end_with(
            sessionmaker, redis, target_id, error, acct, expect=TargetStatus.PUBLISHING
        )

    async with sessionmaker() as session:
        locked = await repo.lock_post_and_target(session, target_id)
        if locked is None or locked[1].status != TargetStatus.PUBLISHING:
            await session.rollback()
            log.warning("publish_target_moved", target_id=str(target_id))  # containers expire
            return "skipped"
        post, target = locked
        target.container_id = container_id
        target.child_container_ids = children
        target.poll_count = 0
        target.status = TargetStatus.CONTAINER_CREATED
        await queue_post_updated(session, post)
        await commit_and_publish(session, redis)
    await enqueue_poll(target_id, workspace_id, 1)
    return "containers_created"


async def _quota(adapter: PlatformAdapter, acct: SocialAccount) -> PublishingQuota | None:
    """The quota, or None when Instagram won't say (it enforces the limit at publish anyway).
    Retryable errors and a dead token raise."""
    try:
        return await adapter.get_publishing_quota(acct)
    except PlatformError as error:
        if error.retryable or error.code == "account_needs_reconnect":
            raise
        log.warning("publishing_quota_unreadable", account_id=str(acct.id), error_code=error.code)
        return None


async def _create(
    adapter: PlatformAdapter,
    acct: SocialAccount,
    post_format: str | None,
    media: Sequence[ContainerMedia],
    caption: str,
) -> tuple[str | None, list[str]]:
    """(container id, children): a carousel's children only, its parent comes once they are
    FINISHED (poll_container)."""
    if post_format == PostFormat.CAROUSEL:
        return None, [await adapter.create_carousel_item(acct, m) for m in media]
    if post_format == PostFormat.REEL:
        return await adapter.create_reel_container(
            acct, video_url=media[0].url, caption=caption, share_to_feed=True
        ), []
    return await adapter.create_image_container(acct, image_url=media[0].url, caption=caption), []


# ---------------------------------------------------------------- poll_container


@dataclass(frozen=True)
class _Poll:
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    target_id: uuid.UUID
    workspace_id: uuid.UUID
    n: int
    now: datetime
    post: ScheduledPost
    target: ScheduledPostTarget
    acct: SocialAccount
    adapter: PlatformAdapter

    @property
    def caption(self) -> str:
        return _caption(self.post, self.target)


async def poll_container(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    target_id: uuid.UUID,
    n: int,
    now: datetime | None = None,
) -> Outcome:
    """Poll ``n`` of a target waiting for Instagram. Runs only as the next poll of a target
    still ``container_created`` (a repeat or a stale poll is skipped)."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        target = await repo.lock_target(session, target_id, skip_locked=True)
        if (
            target is None
            or target.status != TargetStatus.CONTAINER_CREATED
            or target.poll_count != n - 1
        ):
            await session.rollback()
            return "skipped"
        target.poll_count = n
        post = await session.get(ScheduledPost, target.scheduled_post_id)
        acct = await accounts.get(session, target.social_account_id)
        await session.commit()
    if post is None or acct is None:  # pragma: no cover - both cascade to the target
        return "skipped"
    got = _adapter(acct, deps)
    if isinstance(got, _Stop):
        return await _end(
            sessionmaker,
            redis,
            target_id,
            expect=TargetStatus.CONTAINER_CREATED,
            poll=n,
            status=got.status,
            code=got.code,
            message=got.message,
        )
    poll = _Poll(sessionmaker, redis, target_id, post.workspace_id, n, now, post, target, acct, got)
    return await _poll(poll)


async def _poll(p: _Poll) -> Outcome:
    container_id = p.target.container_id
    if container_id is None:  # a carousel: its children first
        children = list(p.target.child_container_ids)
        try:
            statuses = [await p.adapter.get_container_status(p.acct, c) for c in children]
        except PlatformError as error:
            return await _later(p, error, processing=True)
        failed = next((s for s in statuses if s.status_code in ("ERROR", "EXPIRED")), None)
        if failed is not None or not children:
            return await _container_failed(p, failed)
        if any(s.status_code != "FINISHED" for s in statuses):
            return await _next_poll(p, processing=True)
        try:
            container_id = await p.adapter.create_carousel_container(
                p.acct, children=children, caption=p.caption
            )
        except PlatformError as error:
            return await _later(p, error, processing=False)
        if not await _store_parent(p, container_id):
            return "skipped"

    try:
        status = await p.adapter.get_container_status(p.acct, container_id)
    except PlatformError as error:
        return await _later(p, error, processing=True)
    if status.status_code == "IN_PROGRESS":
        return await _next_poll(p, processing=True)
    if status.status_code in ("ERROR", "EXPIRED"):
        return await _container_failed(p, status)
    if status.status_code == "PUBLISHED":
        return await _recover(p, container_id)

    try:
        media_id = await p.adapter.publish_container(p.acct, container_id)
    except PlatformError as error:
        if error.code == DELIVERY_UNKNOWN:
            # It may have published: the next poll reads the status before anything else.
            log.warning("publish_answer_lost", target_id=str(p.target_id), n=p.n)
            return await _next_poll(p, processing=False, error=error)
        return await _later(p, error, processing=False)
    return await _published(p, await _read_back(p, media_id))


async def _store_parent(p: _Poll, container_id: str) -> bool:
    """Keep the carousel's container id, so a later poll never creates a second one."""
    async with p.sessionmaker() as session:
        target = await repo.lock_target(session, p.target_id)
        if (
            target is None
            or target.status != TargetStatus.CONTAINER_CREATED
            or target.poll_count != p.n
        ):
            await session.rollback()
            return False
        target.container_id = container_id
        await session.commit()
    return True


async def _later(p: _Poll, error: PlatformError, *, processing: bool) -> Outcome:
    """A retryable error waits for the next poll; anything else fails the target."""
    if error.retryable:
        return await _next_poll(p, processing=processing, error=error)
    return await _end_with(
        p.sessionmaker,
        p.redis,
        p.target_id,
        error,
        p.acct,
        expect=TargetStatus.CONTAINER_CREATED,
        poll=p.n,
    )


async def _next_poll(p: _Poll, *, processing: bool, error: PlatformError | None = None) -> Outcome:
    """Queue poll n + 1, or give up: a container still processing after POLL_MAX polls times
    out; a publish still unsettled gets EXTRA_POLLS more."""
    if p.n >= (POLL_MAX if processing else POLL_MAX + EXTRA_POLLS):
        if error is None:
            error = (
                PlatformError("platform_unavailable", message=PROCESSING_TIMEOUT_MESSAGE)
                if processing
                else _unconfirmed()
            )
        return await _end(
            p.sessionmaker,
            p.redis,
            p.target_id,
            expect=TargetStatus.CONTAINER_CREATED,
            poll=p.n,
            code=error.code,
            message=reason_for(error, p.acct),
        )
    delay = poll_delay(p.n + 1).total_seconds()
    if error is not None and error.retry_after_s:
        delay = max(delay, error.retry_after_s)
    await enqueue_poll(p.target_id, p.workspace_id, p.n + 1, delay_s=delay)
    return "waiting"


async def _container_failed(p: _Poll, status: ContainerStatus | None) -> Outcome:
    if status is not None and status.status_code == "EXPIRED":
        message = EXPIRED_REASON
    else:
        message = (status.detail if status is not None else None) or PROCESSING_ERROR
    return await _end(
        p.sessionmaker,
        p.redis,
        p.target_id,
        expect=TargetStatus.CONTAINER_CREATED,
        poll=p.n,
        code="platform_rejected",
        message=message,
    )


async def _recover(p: _Poll, container_id: str) -> Outcome:
    """The container is PUBLISHED but we never stored the post: find it (TR-JOB-05)."""
    published_after = (p.target.claimed_at or p.now) - CLOCK_SKEW
    try:
        media = await p.adapter.find_published_media(
            p.acct, container_id, caption=p.caption, published_after=published_after
        )
    except PlatformError as error:
        return await _later(p, error, processing=False)
    if media is None:
        log.warning("published_media_not_found", target_id=str(p.target_id), n=p.n)
        return await _next_poll(p, processing=False)
    log.info("published_media_recovered", target_id=str(p.target_id))
    return await _published(p, media)


async def _read_back(p: _Poll, media_id: str) -> PlatformMedia:
    """The new post's fields and permalink; what we know when Instagram won't say yet (sync
    fills the rest later)."""
    try:
        media = await p.adapter.get_published_media(p.acct, media_id)
    except PlatformError as error:
        log.warning("published_media_read_failed", target_id=str(p.target_id), error=error.code)
        media = None
    if media is not None and media.platform_media_id == media_id:
        return media
    media_type: Literal["image", "carousel", "reel"] = (
        "carousel"
        if p.post.format == PostFormat.CAROUSEL
        else "reel"
        if p.post.format == PostFormat.REEL
        else "image"
    )
    return PlatformMedia(
        platform_media_id=media_id,
        media_type=media_type,
        caption=p.caption or None,
        media_url=None,
        thumbnail_url=None,
        permalink=None,
        posted_at=p.now,
    )


async def _published(p: _Poll, media: PlatformMedia) -> Outcome:
    """One transaction: the target published, its post in media_items, the automations waiting
    for it linked (FR-AUT-18), the post's status; then the first comment is queued."""
    first_comment = False
    async with p.sessionmaker() as session:
        locked = await repo.lock_post_and_target(session, p.target_id)
        if locked is None:
            return "skipped"
        post, target = locked
        if target.status != TargetStatus.CONTAINER_CREATED or target.poll_count != p.n:
            await session.rollback()
            log.warning("publish_result_dropped", target_id=str(p.target_id), n=p.n)
            return "skipped"
        owner = await repo.media_item_owner(session, p.acct.id, media.platform_media_id)
        if owner is not None and owner != target.id:  # another post's: keep looking
            await session.rollback()
            return await _next_poll(p, processing=False)
        item = await repo.upsert_published_item(
            session,
            social_account_id=p.acct.id,
            target_id=target.id,
            media=media,
            synced_at=p.now,
        )
        await automation_posts.link_scheduled_post(session, post.id, item)
        if item.media_type != MediaType.STORY:
            await automation_posts.link_next_posts(session, p.acct.id)
        await settle(session, post, target, TargetStatus.PUBLISHED, media=media)
        first_comment = bool(post.first_comment)
        await commit_and_publish(session, p.redis)
    if first_comment:
        await enqueue_first_comment(p.target_id, p.workspace_id)
    return "published"


# ---------------------------------------------------------------- post_first_comment


async def post_first_comment(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    target_id: uuid.UUID,
    will_retry: WillRetry,
) -> CommentOutcome:
    """FR-PUB-11: the post's first comment, by the account, on the post it just published. A
    failure is stored on the target and the post stays published; a lost answer is never
    retried (the comment may be there)."""
    async with sessionmaker() as session:
        target = await repo.get_target(session, target_id)
        if target is None:
            return "skipped"
        post = await session.get(ScheduledPost, target.scheduled_post_id)
        acct = await accounts.get(session, target.social_account_id)
    if (
        post is None
        or acct is None
        or not post.first_comment
        or target.status != TargetStatus.PUBLISHED
        or not target.platform_media_id
        or target.first_comment_platform_id
        or target.first_comment_error
    ):
        return "skipped"
    got = _adapter(acct, deps)
    if isinstance(got, _Stop):
        return await _store_comment(sessionmaker, redis, target_id, error=got.message)
    try:
        comment_id = await got.post_comment(acct, target.platform_media_id, post.first_comment)
    except PlatformError as error:
        if error.retryable and will_retry(error):
            raise
        return await _store_comment(
            sessionmaker,
            redis,
            target_id,
            error=_comment_reason(error, acct),
            reconnect=acct if error.code == "account_needs_reconnect" else None,
        )
    return await _store_comment(
        sessionmaker, redis, target_id, comment_id=comment_id or UNKNOWN_COMMENT_ID
    )


def _comment_reason(error: PlatformError, acct: SocialAccount) -> str:
    if error.code == DELIVERY_UNKNOWN:
        return (
            f"We couldn't confirm the first comment was posted. Check the post on "
            f"{platform_label(acct)} before adding it again."
        )
    return f"The first comment wasn't posted: {reason_for(error, acct)}"


async def _store_comment(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    target_id: uuid.UUID,
    *,
    comment_id: str | None = None,
    error: str | None = None,
    reconnect: SocialAccount | None = None,
) -> CommentOutcome:
    async with sessionmaker() as session:
        locked = await repo.lock_post_and_target(session, target_id)
        if locked is None:
            return "skipped"
        post, target = locked
        if target.first_comment_platform_id or target.first_comment_error:
            await session.rollback()
            return "skipped"
        if reconnect is not None:
            await mark_needs_reconnect(
                session,
                reconnect,
                f"{platform_label(reconnect)} stopped accepting this connection.",
            )
        target.first_comment_platform_id = comment_id
        target.first_comment_error = error
        await queue_post_updated(session, post)
        await commit_and_publish(session, redis)
    log.info("first_comment", target_id=str(target_id), posted=comment_id is not None)
    return "posted" if comment_id is not None else "failed"


# ---------------------------------------------------------------- the sweeper's repairs


async def reset_stuck(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    target_id: uuid.UUID,
    *,
    now: datetime,
) -> Literal["reset", "failed", "skipped"]:
    """A target left ``publishing`` since before now - STUCK_AFTER: back to pending (the
    dispatcher claims it again), or failed after PUBLISH_ATTEMPTS claims."""
    async with sessionmaker() as session:
        locked = await repo.lock_post_and_target(session, target_id)
        if locked is None:
            return "skipped"
        post, target = locked
        if (
            target.status != TargetStatus.PUBLISHING
            or target.claimed_at is None
            or target.claimed_at >= now - claims.STUCK_AFTER
        ):
            await session.rollback()
            return "skipped"
        if claims.give_up_or_retry(target):
            await settle(
                session,
                post,
                target,
                TargetStatus.FAILED,
                code="internal",
                message=claims.STUCK_REASON,
            )
            outcome: Literal["reset", "failed"] = "failed"
        else:
            await queue_post_updated(session, post)
            outcome = "reset"
        await commit_and_publish(session, redis)
    return outcome


async def resume_polling(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    target_id: uuid.UUID,
    *,
    idle_before: datetime,
) -> Literal["requeued", "failed", "skipped"]:
    """A ``container_created`` target whose last poll is older than ``idle_before`` and has no
    poll job waiting (the caller checked): queue its next poll, which reads the status before
    anything else. One that has used up every poll fails as unconfirmed."""
    async with sessionmaker() as session:
        target = await repo.get_target(session, target_id)
        acct = await accounts.get(session, target.social_account_id) if target else None
    if (
        target is None
        or acct is None
        or target.status != TargetStatus.CONTAINER_CREATED
        or target.updated_at >= idle_before
    ):
        return "skipped"
    if target.poll_count > POLL_MAX + EXTRA_POLLS:
        await _end(
            sessionmaker,
            redis,
            target_id,
            expect=TargetStatus.CONTAINER_CREATED,
            poll=target.poll_count,
            code=DELIVERY_UNKNOWN,
            message=reason_for(_unconfirmed(), acct),
        )
        return "failed"
    await enqueue_poll(target_id, target.workspace_id, target.poll_count + 1)
    return "requeued"
