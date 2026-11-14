"""The direct YouTube route (C-196): a post whose accounts are all YouTube channels and whose tray
is empty sends its video straight from the browser (or an AI app) to YouTube. Neither our server
nor storage sees the file.

- **start** (POST …/youtube-upload): checks the post (only YouTube channels, no tray media,
  editable, a time at least 1 minute ahead or none, meaning "now"), the channel's options, the
  workspace's open uploads (``OPEN_UPLOADS_MAX``) and YouTube's daily upload count
  (platforms/buckets.YouTubeUploads), then opens a resumable session with the metadata and keeps
  its address in the target's ``container_id`` (``upload_expires_at`` 24 hours on). A scheduled
  post uploads as private, with ``publishAt`` = the post's time when it is to be public (YouTube
  publishes it then); "now" uploads with the chosen privacy. Unlisted at a time can't be done by
  YouTube itself (``publishAt`` always makes a video public), so it uploads private and the
  publish job sets unlisted at the time. The channel's token never leaves the API.
- **complete** (POST …/youtube-upload/complete): reads the video (videos.list, 1 unit) and checks
  it is the channel's and has the session's title, stores its id (``platform_media_id``), then
  schedules the post (the checklist, the monthly count) or, for "now", publishes it as Publish
  now does.
- **After an upload** every change to the post queues ``sync_youtube_video`` after the commit
  (``queue_sync``; never for a transaction that rolls back): the job compares what YouTube should
  hold (``desired``) with what it was last sent (``sent_metadata``) and calls videos.update (50
  units) only when something differs: title, description, tags, category, privacy, the time
  (a scheduled post is private with ``publishAt``; a draft is private without one, so it doesn't
  go out). A video no target holds any more (the post deleted, the channel removed, the video
  replaced, Edit and retry, or another platform added: the tray takes over) is deleted
  (videos.delete, 50 units). A published video is never deleted.
- **Expiry** (``expire``): a session opened and not finished within 24 hours is dropped; the post
  goes back to a draft with "The upload didn't finish".

At the publish time the dispatcher claims the target like any other; publish_target's YouTube step
(services/post_publishing/youtube_media.py) reads the video back instead of uploading.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, SessionTransaction
from sqlalchemy.util import await_only
from sqlalchemy.util.concurrency import in_greenlet

from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.publishing import (
    MIN_SCHEDULE_LEAD,
    ScheduledPost,
    ScheduledPostStatus,
    ScheduledPostTarget,
    TargetStatus,
)
from socialhood.observability.logging import get_logger
from socialhood.platforms.buckets import YouTubeUploads, next_google_day
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.adapter import FAILED_UPLOADS, NOT_PROCESSED, YouTubeAdapter
from socialhood.platforms.youtube.publishing import (
    SESSION_LIFETIME,
    Videos,
    videos_for,
    web_origin,
)
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import publish_targets as targets_repo
from socialhood.repositories import scheduled_posts as posts_repo
from socialhood.repositories import social_accounts as accounts
from socialhood.schemas.publishing import (
    YouTubeOptions,
    YouTubeUploadComplete,
    YouTubeUploadSession,
)
from socialhood.services.post_publishing.projection import queue_post_updated
from socialhood.services.scheduled_posts import rules, views

log = get_logger(__name__)

OPEN_UPLOADS_MAX = 3  # direct uploads a workspace may have open at once
MIXED = "Posts to several platforms use the media tray."
IN_TRAY = "This post's video is in the media tray. It is sent to YouTube at the time."
NOT_EDITABLE = "This post can't take a new video now."
NO_CHANNEL = "This YouTube channel isn't on the post."
TOO_MANY_OPEN = (
    f"{OPEN_UPLOADS_MAX} YouTube uploads are already open in this workspace. Finish one, or wait "
    "for it to expire."
)
DAILY_LIMIT = "YouTube's daily upload limit is reached. Try again after {at}."
NOT_OPEN = "No upload is open for this channel. Start the upload again."
NO_SUCH_VIDEO = "YouTube has no such video on this channel."
NOT_THIS_UPLOAD = "This isn't the video this upload opened."
TAKEN = "This video is already on another post."
DIDNT_FINISH = "The upload didn't finish. Upload the video again."
TIME_OR_NOW = "Pick a time at least 1 minute from now, or none to post now."
EXPIRED_CODE = "upload_expired"
HELD = "held"  # sent_metadata: the video is waiting, private, for the post to be scheduled again


# ---------------------------------------------------------------- what YouTube should hold


def description(post: ScheduledPost, target: ScheduledPostTarget) -> str:
    return target.caption_override if target.caption_override is not None else post.caption


def metadata(
    post: ScheduledPost,
    target: ScheduledPostTarget,
    options: YouTubeOptions,
    *,
    at: datetime | None,
    now: bool,
) -> dict[str, Any]:
    """The video's snippet and status as we keep them (``sent_metadata``). ``now``: the chosen
    privacy, no time. Otherwise private, with ``publishAt`` = ``at`` only when it is to be
    public (YouTube's ``publishAt`` always makes a video public); without ``at`` it waits."""
    return {
        "title": options.title,
        "description": description(post, target),
        "tags": list(options.tags),
        "category_id": options.category_id,
        "made_for_kids": options.made_for_kids,
        "synthetic_media": options.synthetic_media,
        "notify_subscribers": options.notify_subscribers,
        "privacy": options.privacy if now else "private",
        "publish_at": (
            at.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if at is not None and not now and options.privacy == "public"
            else None
        ),
        "now": now,
    }


def desired(
    post: ScheduledPost, target: ScheduledPostTarget, now: datetime
) -> dict[str, Any] | None:
    """What YouTube should hold for a direct upload's video now; None when it isn't ours to
    change (no video, publishing or done, due: the publish job's)."""
    options = views.youtube_options(target.options)
    if options is None or target.status != TargetStatus.PENDING or not target.platform_media_id:
        return None
    if post.status == ScheduledPostStatus.DRAFT:
        return metadata(post, target, options, at=None, now=False)
    if (
        post.status == ScheduledPostStatus.SCHEDULED
        and post.publish_at is not None
        and post.publish_at > now
    ):
        return metadata(post, target, options, at=post.publish_at, now=False)
    return None


COMPARED = (
    "title",
    "description",
    "tags",
    "category_id",
    "made_for_kids",
    "synthetic_media",
    "privacy",
    "publish_at",
)


def changed(sent: dict[str, Any] | None, wanted: dict[str, Any]) -> bool:
    sent = sent or {}
    return any(sent.get(key) != wanted.get(key) for key in COMPARED)


def clear(target: ScheduledPostTarget) -> None:
    """Forget a direct upload: its session or its video (the caller queued the video's fate)."""
    target.container_id = None
    target.platform_media_id = None
    target.permalink = None
    target.upload_expires_at = None
    target.sent_metadata = None


# ---------------------------------------------------------------- after the commit

_KEY = "youtube_sync_after_commit"


@dataclass(frozen=True)
class PendingSync:
    target_id: uuid.UUID
    account_id: uuid.UUID
    video_id: str
    workspace_id: uuid.UUID


def queue_sync(
    session: AsyncSession | Session, target: ScheduledPostTarget, video_id: str | None = None
) -> None:
    """Have ``sync_youtube_video`` look at ``video_id`` (the target's, by default) once this
    transaction commits: update it to match the post, or delete it when no target holds it."""
    video = video_id or target.platform_media_id
    if not video:
        return
    pending: dict[tuple[uuid.UUID, str], PendingSync] = session.info.setdefault(_KEY, {})
    pending[(target.id, video)] = PendingSync(
        target.id, target.social_account_id, video, target.workspace_id
    )


def pending_syncs(session: AsyncSession | Session) -> list[PendingSync]:
    """What this session's commit will queue (tests)."""
    return list(session.info.get(_KEY, {}).values())


async def queue_changed(session: AsyncSession, post_ids: list[uuid.UUID]) -> None:
    """Every direct upload of these posts that is waiting on YouTube gets a sync after the
    commit (a changed post; videos.update only runs when something YouTube holds differs)."""
    if not post_ids:
        return
    rows = await session.scalars(
        select(ScheduledPostTarget).where(
            ScheduledPostTarget.scheduled_post_id.in_(post_ids),
            ScheduledPostTarget.status == TargetStatus.PENDING,
            ScheduledPostTarget.platform_media_id.is_not(None),
            ScheduledPostTarget.options.is_not(None),
        )
    )
    for target in rows:
        queue_sync(session, target)


async def defer(job: PendingSync) -> bool:
    from socialhood.jobs.app import INTERACTIVE
    from socialhood.jobs.enqueue import enqueue_named

    try:
        return await enqueue_named(
            "sync_youtube_video",
            lane=INTERACTIVE,
            key=f"ytsync:{job.target_id}:{job.video_id}",
            lock=f"ytsync:{job.video_id}",
            target_id=str(job.target_id),
            account_id=str(job.account_id),
            video_id=job.video_id,
            workspace_id=str(job.workspace_id),
        )
    except Exception:
        log.warning("youtube_sync_enqueue_failed", target_id=str(job.target_id))
        return False


@event.listens_for(Session, "after_commit")
def _defer_after_commit(session: Session) -> None:
    pending: dict[Any, PendingSync] | None = session.info.pop(_KEY, None)
    if not pending:
        return
    if not in_greenlet():  # a synchronous session: nothing here can await
        log.warning("youtube_sync_skipped", jobs=len(pending))
        return
    for job in pending.values():
        await_only(defer(job))


@event.listens_for(Session, "after_soft_rollback")
def _drop_on_rollback(session: Session, previous_transaction: SessionTransaction) -> None:
    if previous_transaction.parent is None:
        session.info.pop(_KEY, None)


# ---------------------------------------------------------------- start and complete


def _usable(acct: SocialAccount, deps: PlatformDeps) -> None:
    handle = rules.handle(acct.username, acct.display_name)
    if acct.status != AccountStatus.ACTIVE:
        raise ApiError(
            "account_needs_reconnect", f"{handle} needs reconnecting before it can upload."
        )
    if not views.can_publish(acct, deps):
        raise ApiError("capability_unavailable", f"{handle} can't publish videos.")


def api_error(error: PlatformError, acct: SocialAccount) -> ApiError:
    """A YouTube failure as the API answers it."""
    handle = rules.handle(acct.username, acct.display_name)
    if error.code == "account_needs_reconnect":
        return ApiError("account_needs_reconnect", f"{handle} needs reconnecting on YouTube.")
    if error.code == "platform_rate_limited":
        return ApiError("rate_limited", "YouTube is limiting requests right now. Try again later.")
    if error.code == "platform_rejected":
        return ApiError("platform_error", error.message or "YouTube refused the upload.")
    return ApiError("service_unavailable", "YouTube didn't respond. Try again.")


def local_time(at: datetime, timezone: str) -> str:
    """ "1:30 pm IST" in the workspace's zone."""
    try:
        local = at.astimezone(ZoneInfo(timezone))
    except Exception:
        local = at.astimezone(UTC)
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d} {'am' if local.hour < 12 else 'pm'} {local.tzname()}"


def daily_limit_error(now: datetime, timezone: str) -> ApiError:
    reset = next_google_day(now)
    return ApiError(
        "rate_limited",
        DAILY_LIMIT.format(at=local_time(reset, timezone)),
        headers={"Retry-After": str(max(1, int((reset - now).total_seconds())))},
    )


@dataclass(frozen=True)
class _Found:
    post: ScheduledPost
    target: ScheduledPostTarget
    account: SocialAccount
    index: int


async def _find(
    session: AsyncSession, scheduled_post_id: uuid.UUID, target_id: uuid.UUID
) -> _Found:
    """The post (locked), checked for the direct route, and its YouTube target: ``target_id``
    is the channel's account id (the post's targets show it) or the target's own id."""
    post = await posts_repo.get(session, scheduled_post_id, for_update=True)
    if post is None:
        raise ApiError("not_found")
    [loaded] = await views.load(session, [post])
    if any(account.platform != "youtube" for _, account in loaded.targets):
        raise ApiError("conflict", MIXED)
    if loaded.assets:
        raise ApiError("conflict", IN_TRAY)
    for i, (target, account) in enumerate(loaded.targets):
        if target_id in (target.social_account_id, target.id):
            return _Found(post, target, account, i)
    raise ApiError("validation_error", errors=[FieldError("target_id", NO_CHANNEL)])


async def _open_uploads(session: AsyncSession, now: datetime, but: uuid.UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(ScheduledPostTarget)
        .where(
            ScheduledPostTarget.upload_expires_at > now,
            ScheduledPostTarget.id != but,
        )
    )
    return int(count or 0)


async def start(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    *,
    scheduled_post_id: uuid.UUID,
    target_id: uuid.UUID,
    file_size: int | None,
    content_type: str,
    now: datetime,
    timezone: str = "UTC",
) -> YouTubeUploadSession:
    """Open a direct upload (see the module docstring); ``file_size`` None when it isn't known
    yet (an AI app's upload page). The caller commits."""
    found = await _find(session, scheduled_post_id, target_id)
    post, target, acct = found.post, found.target, found.account
    if post.status not in (ScheduledPostStatus.DRAFT, ScheduledPostStatus.SCHEDULED):
        raise ApiError("conflict", NOT_EDITABLE)
    options = views.youtube_options(target.options)
    if options is None:
        raise ApiError(
            "validation_error",
            errors=[
                FieldError(
                    f"targets.{found.index}.options",
                    rules.YOUTUBE_OPTIONS.format(
                        handle=rules.handle(acct.username, acct.display_name)
                    ),
                )
            ],
        )
    _usable(acct, deps)
    at = post.publish_at
    if at is not None and at < now + MIN_SCHEDULE_LEAD:
        raise ApiError(
            "validation_error",
            errors=[FieldError("publish_at", TIME_OR_NOW)],
        )
    now_mode = at is None
    if await _open_uploads(session, now, target.id) >= OPEN_UPLOADS_MAX:
        raise ApiError("conflict", TOO_MANY_OPEN)
    uploads = YouTubeUploads(redis)
    if not await uploads.take(now):
        raise daily_limit_error(now, timezone)
    meta = metadata(post, target, options, at=at, now=now_mode)
    videos = videos_for(acct, deps)
    try:
        token = await YouTubeAdapter(deps).access_token(acct)
        uri = await videos.open_session(
            token,
            metadata=meta,
            size=file_size,
            content_type=content_type,
            origin=web_origin(deps.settings),
        )
    except PlatformError as error:
        await uploads.give_back(now)
        raise api_error(error, acct) from error
    if target.platform_media_id:  # a new file replaces the old video, which goes
        queue_sync(session, target, target.platform_media_id)
    clear(target)
    if post.status == ScheduledPostStatus.SCHEDULED:  # scheduled again once the file is there
        post.status = ScheduledPostStatus.DRAFT
    target.container_id = uri
    target.upload_expires_at = now + SESSION_LIFETIME
    target.sent_metadata = meta
    target.error_code = None
    target.error_message = None
    post.updated_at = now
    await views.publish_updated(session, [post], deps=deps, now=now)
    log.info("youtube_upload_opened", target_id=str(target.id), now=now_mode)
    return YouTubeUploadSession(
        target_id=target_id,
        upload_url=uri,
        chunk_bytes=videos.chunk_bytes,
        expires_at=target.upload_expires_at,
    )


async def complete(
    session: AsyncSession,
    deps: PlatformDeps,
    *,
    scheduled_post_id: uuid.UUID,
    body: YouTubeUploadComplete,
    env: Any,  # services.scheduled_posts.posts.Env
) -> tuple[Any, Any]:
    """Take the finished upload's video (see the module docstring); returns the post and, for
    "now", the HandOver the caller gives the publishing jobs after its commit."""
    from socialhood.services.scheduled_posts import posts

    found = await _find(session, scheduled_post_id, body.target_id)
    post, target, acct = found.post, found.target, found.account
    if target.platform_media_id == body.video_id:  # done already: the same answer again
        return await views.post_out(session, post, deps=deps, now=env.now), None
    if post.status not in (ScheduledPostStatus.DRAFT, ScheduledPostStatus.SCHEDULED):
        raise ApiError("conflict", NOT_EDITABLE)
    if not views.is_session(target.container_id):
        raise ApiError("conflict", NOT_OPEN)
    taken = await session.scalar(
        select(func.count())
        .select_from(ScheduledPostTarget)
        .where(
            ScheduledPostTarget.platform_media_id == body.video_id,
            ScheduledPostTarget.id != target.id,
        )
    )
    if taken:
        raise ApiError("conflict", TAKEN)
    try:
        token = await YouTubeAdapter(deps).access_token(acct)
        video = await videos_for(acct, deps).get(token, body.video_id)
    except PlatformError as error:
        raise api_error(error, acct) from error
    if video is None or (video.channel_id and video.channel_id != acct.platform_account_id):
        raise ApiError("validation_error", errors=[FieldError("video_id", NO_SUCH_VIDEO)])
    sent = target.sent_metadata or {}
    if video.title is not None and sent.get("title") and video.title != sent["title"]:
        raise ApiError("validation_error", errors=[FieldError("video_id", NOT_THIS_UPLOAD)])
    if video.upload_status in FAILED_UPLOADS:
        raise ApiError("platform_error", f"{NOT_PROCESSED}: {video.failure or 'unknown reason'}.")
    target.platform_media_id = video.id
    target.container_id = None
    target.upload_expires_at = None
    target.error_code = None
    target.error_message = None
    await session.flush()
    now_mode = (
        bool(sent.get("now"))
        or post.publish_at is None
        or (post.publish_at < env.now + MIN_SCHEDULE_LEAD)
    )
    out, handover = await posts.schedule_uploaded(session, post, env, now=now_mode)
    if not now_mode:
        queue_sync(session, target)  # a title or time changed while the file went up
    log.info("youtube_upload_completed", target_id=str(target.id), now=now_mode)
    return out, handover


# ---------------------------------------------------------------- the jobs' bodies

SyncOutcome = Literal["updated", "deleted", "unchanged", "skipped", "failed"]


async def sync(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    target_id: uuid.UUID,
    account_id: uuid.UUID,
    video_id: str,
    now: datetime | None = None,
) -> SyncOutcome:
    """``sync_youtube_video``: make YouTube match the post, or delete a video no target holds.
    Retryable YouTube errors raise (the job retries); a dead token ends it."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        acct = await accounts.get(session, account_id)
        target = await targets_repo.get_target(session, target_id)
        post = (
            await session.get(ScheduledPost, target.scheduled_post_id)
            if target is not None
            else None
        )
    if acct is None or acct.status == AccountStatus.DISCONNECTED:
        return "skipped"  # the token is gone with the connection
    holds = target is not None and views.youtube_video_id(target) == video_id
    if holds and target is not None and target.status == TargetStatus.PUBLISHED:
        return "unchanged"
    try:
        token = await YouTubeAdapter(deps).access_token(acct)
        videos: Videos = videos_for(acct, deps)
        if not holds:
            current = await videos.get(token, video_id)
            if current is not None and current.privacy != "private":
                log.warning("youtube_video_kept", video_id=video_id)  # it is out there already
                return "skipped"
            await videos.delete(token, video_id)
            log.info("youtube_video_deleted", video_id=video_id)
            return "deleted"
        assert target is not None
        assert post is not None
        wanted = desired(post, target, now)
        if wanted is None or not changed(target.sent_metadata, wanted):
            return "unchanged"
        await videos.update(token, video_id, wanted)
    except PlatformError as error:
        if error.retryable:
            raise
        log.warning("youtube_sync_failed", video_id=video_id, error_code=error.code)
        return "failed"
    async with sessionmaker() as session:
        locked = await targets_repo.lock_target(session, target_id)
        if locked is not None and views.youtube_video_id(locked) == video_id:
            locked.sent_metadata = wanted
        await session.commit()
    return "updated"


async def expire(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    due: list[ScheduledPostTarget],
    now: datetime,
) -> int:
    """Direct uploads opened and not finished in time: the session is dropped, the post goes back
    to a draft with "The upload didn't finish". ``due`` comes from the job's cross-workspace query
    (TR-TEN-04); each row is re-checked under its own workspace. Returns how many."""
    expired = 0
    for row in due:
        with workspace_scope(row.workspace_id):
            async with sessionmaker() as session:
                locked = await targets_repo.lock_post_and_target(session, row.id)
                if locked is None:
                    continue
                post, target = locked
                if (
                    target.upload_expires_at is None
                    or target.upload_expires_at > now
                    or target.platform_media_id
                ):
                    await session.rollback()
                    continue
                clear(target)
                target.error_code = EXPIRED_CODE
                target.error_message = DIDNT_FINISH
                if post.status == ScheduledPostStatus.SCHEDULED:
                    post.status = ScheduledPostStatus.DRAFT
                post.updated_at = now
                await queue_post_updated(session, post)
                await commit_and_publish(session, redis)
                expired += 1
    if expired:
        log.info("youtube_uploads_expired", count=expired)
    return expired
