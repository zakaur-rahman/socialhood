"""YouTube at the publish time (C-196): publish_target's step for a YouTube target, the upload job
for the media route, and the dispatcher's hold-back when YouTube's daily uploads are used up.

- **Direct route** (the video is on YouTube already, ``platform_media_id``): nothing is uploaded.
  An unlisted video goes unlisted now (YouTube's ``publishAt`` can only make a video public);
  then the target waits as ``container_created`` with the video id as its container, and
  poll_container reads it back (videos.list, 1 unit): processed and past its ``publishAt`` is
  FINISHED, ``publish_container`` changes nothing, and the target is published with its link.
- **Media route** (the video is in the media tray, the post also goes to Instagram or Facebook):
  one upload is counted (platforms/buckets.YouTubeUploads), a resumable session is opened with the
  chosen privacy and kept in ``container_id`` before a byte is sent, and ``upload_youtube_video``
  (bulk lane, so replies aren't held up) streams the file from storage in 8 MiB pieces. A crashed
  or retried job asks the session what arrived and goes on from there; a session that is gone is
  first checked against the channel's recent uploads (same title, since the claim), so a lost
  answer never posts twice. The finished upload's video id becomes the container and the polls
  wait for YouTube's processing, as for an Instagram video.
- **Daily limit**: a due post whose YouTube video still has to be uploaded, when the day's uploads
  are used up, is moved to the start of the next quota day (midnight Pacific Time, plus a minute)
  instead of failing, and its owners are told (``hold_back``, run by the dispatcher before it
  claims).

Failures name YouTube (``publish.reason_for`` uses the account's platform label).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.models.media import MediaAsset
from socialhood.models.publishing import ScheduledPost, ScheduledPostTarget, TargetStatus
from socialhood.observability.logging import get_logger
from socialhood.platforms.buckets import YouTubeUploads, next_google_day
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.adapter import YouTubeAdapter
from socialhood.platforms.youtube.publishing import Video, match_recent, videos_for
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import publish_targets as repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services.notifications import notify_admins
from socialhood.services.post_publishing import publish
from socialhood.services.post_publishing.projection import queue_post_updated
from socialhood.services.post_publishing.youtube_direct import changed, local_time, metadata
from socialhood.services.scheduled_posts import views

log = get_logger(__name__)

DAILY_LIMIT_REACHED = (
    "YouTube's daily upload limit is reached. Edit the post to try again after the limit resets."
)
NO_OPTIONS = "The YouTube details are missing. Edit the post and try again."
MOVED_AFTER = timedelta(minutes=1)  # past the quota day's start


def _upload_job_lock(target_id: uuid.UUID) -> str:
    return f"pub:{target_id}"  # publish_target's: the sweeper sees the upload as its work


async def enqueue_upload(target_id: uuid.UUID, workspace_id: uuid.UUID) -> bool:
    """``upload_youtube_video`` on the bulk lane, under publish_target's lock."""
    from socialhood.jobs.app import BULK
    from socialhood.jobs.enqueue import enqueue_named

    try:
        return await enqueue_named(
            "upload_youtube_video",
            lane=BULK,
            key=f"ytup:{target_id}",
            lock=_upload_job_lock(target_id),
            target_id=str(target_id),
            workspace_id=str(workspace_id),
        )
    except Exception:
        log.warning("youtube_upload_enqueue_failed", target_id=str(target_id))
        return False


def _the_video(assets: Sequence[MediaAsset]) -> MediaAsset | None:
    if len(assets) == 1 and assets[0].resource_type == "video" and assets[0].secure_url:
        return assets[0]
    return None


def _content_type(asset: MediaAsset) -> str:
    fmt = (asset.format or "mp4").lower()
    return "video/quicktime" if fmt == "mov" else f"video/{fmt}"


async def _fail(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    target_id: uuid.UUID,
    code: str,
    message: str,
) -> publish.Outcome:
    return await publish._end(
        sessionmaker, redis, target_id, expect=TargetStatus.PUBLISHING, code=code, message=message
    )


async def _to_processing(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    target_id: uuid.UUID,
    video_id: str,
    sent: dict[str, Any] | None = None,
) -> publish.Outcome:
    """The video exists: its id is the container; poll 1 is queued at once."""
    async with sessionmaker() as session:
        locked = await repo.lock_post_and_target(session, target_id)
        if locked is None or locked[1].status != TargetStatus.PUBLISHING:
            await session.rollback()
            log.warning("youtube_target_moved", target_id=str(target_id))
            return "skipped"
        post, target = locked
        target.container_id = video_id
        target.poll_count = 0
        target.status = TargetStatus.CONTAINER_CREATED
        if sent is not None:
            target.sent_metadata = sent
        await queue_post_updated(session, post)
        await commit_and_publish(session, redis)
        workspace_id = post.workspace_id
    await publish.enqueue_poll(target_id, workspace_id, 1)
    return "containers_created"


def _final(
    post: ScheduledPost, target: ScheduledPostTarget, options: Any, now: datetime
) -> dict[str, Any] | None:
    """What a direct upload's video must be sent at its time, or None when YouTube does it
    itself: a public video whose ``publishAt`` is now. Unlisted (which ``publishAt`` can't give),
    or a ``publishAt`` left far off (the time was cleared after the upload), are set now."""
    sent = target.sent_metadata or {}
    final = metadata(post, target, options, at=None, now=True)
    if sent.get("now") or not changed(sent, final):
        return None
    raw = sent.get("publish_at")
    later = bool(raw) and (
        datetime.fromisoformat(str(raw).replace("Z", "+00:00")) > now + MOVED_AFTER
    )
    return final if options.privacy != "public" or later else None


async def begin(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    target_id: uuid.UUID,
    will_retry: publish.WillRetry,
    now: datetime,
) -> publish.Outcome:
    """publish_target's step for a YouTube target it has claimed (``publishing``)."""
    async with sessionmaker() as session:
        locked = await repo.lock_post_and_target(session, target_id)
        if locked is None or locked[1].status != TargetStatus.PUBLISHING:
            await session.rollback()
            return "skipped"
        post, target = locked
        acct = await accounts.get(session, target.social_account_id)
        assets = await repo.assets_of(session, post.id)
        session.expunge_all()  # kept as read: the rollback that frees the locks expires rows
        await session.rollback()
    if acct is None:  # pragma: no cover - deleting the account deletes its targets
        return "skipped"
    options = views.youtube_options(target.options)
    if options is None:
        return await _fail(sessionmaker, redis, target_id, "validation_error", NO_OPTIONS)
    videos = videos_for(acct, deps)
    adapter = YouTubeAdapter(deps)

    try:
        if target.platform_media_id:  # direct: the video waits on YouTube
            final = _final(post, target, options, now)
            if final is not None:
                await videos.update(
                    await adapter.access_token(acct), target.platform_media_id, final
                )
            return await _to_processing(
                sessionmaker, redis, target_id, target.platform_media_id, final
            )

        video = _the_video(assets)
        if video is None:
            return await _fail(
                sessionmaker, redis, target_id, "validation_error", publish.BROKEN_POST
            )
        if not views.is_session(target.container_id):
            uploads = YouTubeUploads(redis)
            if not await uploads.take(now):
                return await _fail(
                    sessionmaker, redis, target_id, "platform_rejected", DAILY_LIMIT_REACHED
                )
            try:
                uri = await videos.open_session(
                    await adapter.access_token(acct),
                    metadata=metadata(post, target, options, at=None, now=True),
                    size=video.bytes,
                    content_type=_content_type(video),
                )
            except PlatformError:
                await uploads.give_back(now)
                raise
            if not await _keep_session(sessionmaker, target_id, uri, post, target, options):
                return "skipped"
    except PlatformError as error:
        if error.retryable and will_retry(error):
            raise
        return await publish._end_with(
            sessionmaker, redis, target_id, error, acct, expect=TargetStatus.PUBLISHING
        )
    await enqueue_upload(target_id, post.workspace_id)
    return "waiting"


async def _keep_session(
    sessionmaker: async_sessionmaker[AsyncSession],
    target_id: uuid.UUID,
    uri: str,
    post: ScheduledPost,
    target: ScheduledPostTarget,
    options: Any,
) -> bool:
    """Store the session before any byte goes, so a crash resumes it instead of uploading
    again."""
    async with sessionmaker() as session:
        locked = await repo.lock_target(session, target_id)
        if locked is None or locked.status != TargetStatus.PUBLISHING:
            await session.rollback()
            return False
        locked.container_id = uri
        locked.sent_metadata = metadata(post, target, options, at=None, now=True)
        await session.commit()
    return True


async def upload(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    target_id: uuid.UUID,
    will_retry: publish.WillRetry,
    now: datetime | None = None,
) -> publish.Outcome:
    """``upload_youtube_video``: send the tray's video to the target's session, from what it
    already holds. Retryable errors raise while the job retries (each try asks the session
    first); the last fails the target."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        target = await repo.get_target(session, target_id)
        if target is None or target.status != TargetStatus.PUBLISHING:
            return "skipped"
        post = await session.get(ScheduledPost, target.scheduled_post_id)
        acct = await accounts.get(session, target.social_account_id)
        assets = await repo.assets_of(session, target.scheduled_post_id)
    uri = target.container_id
    video_asset = _the_video(assets)
    options = views.youtube_options(target.options)
    if post is None or acct is None or not views.is_session(uri) or video_asset is None:
        return "skipped"
    assert uri is not None
    assert options is not None
    videos = videos_for(acct, deps)
    total = video_asset.bytes
    try:
        progress = await videos.progress(uri, total=total)
        done: Video | None = progress.video if progress is not None else None
        offset = progress.received if progress is not None else 0
        if progress is None:  # the session is gone: did an earlier try finish?
            token = await YouTubeAdapter(deps).access_token(acct)
            since = min(target.claimed_at or now, now) - publish.CLOCK_SKEW
            done = match_recent(
                await videos.recent_uploads(token, acct.platform_account_id),
                title=options.title,
                published_after=since,
            )
            if done is None:
                uploads = YouTubeUploads(redis)
                if not await uploads.take(now):
                    return await _fail(
                        sessionmaker, redis, target_id, "platform_rejected", DAILY_LIMIT_REACHED
                    )
                uri = await videos.open_session(
                    token,
                    metadata=metadata(post, target, options, at=None, now=True),
                    size=total,
                    content_type=_content_type(video_asset),
                )
                if not await _keep_session(sessionmaker, target_id, uri, post, target, options):
                    return "skipped"
                offset = 0
        if done is None:
            done = await videos.transfer(
                deps.http, uri, video_asset.secure_url or "", offset=offset, total=total
            )
    except PlatformError as error:
        if error.retryable and will_retry(error):
            log.info("youtube_upload_retry", target_id=str(target_id), error_code=error.code)
            raise
        return await publish._end_with(
            sessionmaker, redis, target_id, error, acct, expect=TargetStatus.PUBLISHING
        )
    log.info("youtube_upload_done", target_id=str(target_id))
    return await _to_processing(sessionmaker, redis, target_id, done.id)


# ---------------------------------------------------------------- the dispatcher's hold-back


def _needs_upload(target: ScheduledPostTarget) -> bool:
    """A YouTube target (it has options) whose video still has to go up at the time."""
    return (
        target.options is not None
        and not target.platform_media_id
        and not views.is_session(target.container_id)
    )


async def hold_back(
    session: AsyncSession,
    redis: Redis,
    posts: Sequence[ScheduledPost],
    targets: Sequence[ScheduledPostTarget],
    now: datetime,
) -> set[uuid.UUID]:
    """The due posts (locked by the caller) that wait for tomorrow's uploads: when the day's
    YouTube uploads can't cover them, the later ones move to the next quota day and their owners
    are told. Returns their ids (the caller doesn't claim them)."""
    needs: dict[uuid.UUID, int] = {}
    for target in targets:
        if _needs_upload(target):
            needs[target.scheduled_post_id] = needs.get(target.scheduled_post_id, 0) + 1
    if not needs:
        return set()
    left = await YouTubeUploads(redis).left(now)
    held: set[uuid.UUID] = set()
    moved_to = next_google_day(now) + MOVED_AFTER
    for post in sorted(posts, key=lambda p: p.publish_at or now):
        want = needs.get(post.id, 0)
        if not want:
            continue
        if want <= left:
            left -= want
            continue
        held.add(post.id)
        with workspace_scope(post.workspace_id):
            await _move(session, post, moved_to)
    if held:
        log.info("youtube_posts_held_for_quota", posts=len(held))
    return held


async def _move(session: AsyncSession, post: ScheduledPost, at: datetime) -> None:
    from socialhood.models.identity import Workspace

    post.publish_at = at
    post.updated_at = datetime.now(UTC)
    workspace = await session.get(Workspace, post.workspace_id)
    when = local_time(at, workspace.timezone if workspace is not None else "UTC")
    excerpt = post.caption.strip().splitlines()[0][:40] if post.caption.strip() else ""
    subject = f'"{excerpt}"' if excerpt else "Your post"
    await notify_admins(
        session,
        type="post_failed",
        severity="warning",
        title="Post moved to tomorrow",
        body=(
            f"YouTube's daily upload limit is reached, so {subject} will go out at {when} "
            "instead, on every account."
        ),
        link=f"/schedule/{post.id}",
        dedupe_key=f"youtube_moved:{post.id}:{at.date().isoformat()}",
    )
    await queue_post_updated(session, post)
