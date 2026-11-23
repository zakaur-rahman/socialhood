"""A YouTube video's custom thumbnail (C-203): the image chosen in the target's options
(``YouTubeOptions.thumbnail_media_id``), set with thumbnails.set (50 of the project's units,
platforms/buckets.YouTubeQuota) once the video is on YouTube.

- **When.** ``set_youtube_thumbnail`` is queued once the video id is known: the direct route's
  syncs (after the upload completes and after every change to the post: youtube_direct.defer),
  and the publish step's ``_to_processing`` (the media route's finished upload, and a direct
  video at its time). It is its own job, so a thumbnail never fails or holds up the video.
- **Once per image.** The target's ``sent_metadata`` keeps the image last sent and, when YouTube
  refused it, why (``views.THUMBNAIL_SENT`` / ``THUMBNAIL_ERROR``); the job does nothing while
  the chosen image is the one sent. Removing the thumbnail forgets that (YouTube keeps the image:
  the API can't bring back its own), so choosing it again sends it again.
- **Failures.** 403 (the channel can't use custom thumbnails: not verified) and 400 (a bad
  image) are recorded on the target, which the composer shows; they are not retried. YouTube
  being down is retried like the other YouTube jobs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.models.connections import AccountStatus
from socialhood.models.publishing import ScheduledPost
from socialhood.observability.logging import get_logger
from socialhood.platforms.buckets import YOUTUBE_WRITE_CEILING, YOUTUBE_WRITE_UNITS, YouTubeQuota
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.adapter import YouTubeAdapter
from socialhood.platforms.youtube.publishing import videos_for
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import publish_targets as targets_repo
from socialhood.repositories import scheduled_posts as posts_repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services.media_assets import MIME_TYPES
from socialhood.services.post_publishing.projection import queue_post_updated
from socialhood.services.scheduled_posts import rules, views
from socialhood.services.scheduled_posts.views import THUMBNAIL_ERROR, THUMBNAIL_SENT

log = get_logger(__name__)

NOT_VERIFIED = (
    "YouTube didn't take the thumbnail: custom thumbnails need a verified channel. Verify at "
    "youtube.com/verify, then pick the thumbnail again."
)
BAD_IMAGE = "YouTube didn't take the thumbnail. Use a JPG or PNG up to 2 MB, then pick it again."

RECONNECT = (
    "YouTube didn't take the thumbnail: the channel needs reconnecting. Reconnect it, then pick "
    "the thumbnail again."
)
NO_UNITS = (
    "YouTube didn't take the thumbnail: Amplychat's daily YouTube limit is reached. Pick the "
    "thumbnail again tomorrow."
)

Outcome = Literal["set", "failed", "unchanged", "skipped"]


async def enqueue(target_id: uuid.UUID, video_id: str, workspace_id: uuid.UUID) -> bool:
    """``set_youtube_thumbnail`` on the interactive lane, one at a time per video."""
    from socialhood.jobs.app import INTERACTIVE
    from socialhood.jobs.enqueue import enqueue_named

    try:
        return await enqueue_named(
            "set_youtube_thumbnail",
            lane=INTERACTIVE,
            key=f"ytthumb:{target_id}:{video_id}",
            lock=f"ytthumb:{video_id}",
            target_id=str(target_id),
            video_id=video_id,
            workspace_id=str(workspace_id),
        )
    except Exception:
        log.warning("youtube_thumbnail_enqueue_failed", target_id=str(target_id))
        return False


def wanted(options: dict[str, Any] | None, sent: dict[str, Any] | None) -> bool:
    """Whether a target has a thumbnail for the job to look at (one chosen, or one to forget)."""
    return bool((options or {}).get("thumbnail_media_id") or (sent or {}).get(THUMBNAIL_SENT))


def refusal(error: PlatformError) -> str:
    """What the composer says when YouTube refused the thumbnail."""
    if error.platform_code in ("forbidden", "403"):
        return NOT_VERIFIED
    if error.code == "account_needs_reconnect":
        return RECONNECT
    return BAD_IMAGE


async def apply(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    target_id: uuid.UUID,
    video_id: str,
    now: datetime | None = None,
) -> Outcome:
    """``set_youtube_thumbnail``: send the chosen image when it isn't the one sent (see the module
    docstring). Retryable YouTube errors raise (the job retries)."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        target = await targets_repo.get_target(session, target_id)
        if target is None or views.youtube_video_id(target) != video_id:
            return "skipped"  # the video was replaced or dropped
        options = views.youtube_options(target.options)
        image_id = options.thumbnail_media_id if options is not None else None
        sent = target.sent_metadata or {}
        if image_id is None:
            if THUMBNAIL_SENT not in sent:
                return "unchanged"
            await _record(session, redis, target_id, video_id, None, None)
            return "unchanged"
        if sent.get(THUMBNAIL_SENT) == str(image_id):
            return "unchanged"
        acct = await accounts.get(session, target.social_account_id)
        image = (await posts_repo.assets_by_id(session, [image_id])).get(image_id)
    if acct is None or acct.status == AccountStatus.DISCONNECTED:
        return "skipped"
    problem = rules.youtube_thumbnail_problem(image)
    if problem is None and not await YouTubeQuota(redis).take(
        YOUTUBE_WRITE_UNITS, ceiling=YOUTUBE_WRITE_CEILING, now=now
    ):
        problem = NO_UNITS
    if problem is None:
        assert image is not None
        try:
            await videos_for(acct, deps).set_thumbnail(
                await YouTubeAdapter(deps).access_token(acct),
                video_id,
                image.secure_url or "",
                content_type=MIME_TYPES.get((image.format or "").lower(), "image/jpeg"),
            )
        except PlatformError as error:
            if error.retryable:
                raise
            log.warning(
                "youtube_thumbnail_refused", target_id=str(target_id), error_code=error.code
            )
            problem = refusal(error)
    async with sessionmaker() as session:
        await _record(session, redis, target_id, video_id, str(image_id), problem)
    log.info("youtube_thumbnail_done", target_id=str(target_id), ok=problem is None)
    return "set" if problem is None else "failed"


async def _record(
    session: AsyncSession,
    redis: Redis,
    target_id: uuid.UUID,
    video_id: str,
    image_id: str | None,
    problem: str | None,
) -> None:
    """Keep what was sent (or forget it: ``image_id`` None) and tell the composer."""
    locked = await targets_repo.lock_target(session, target_id)
    if locked is None or views.youtube_video_id(locked) != video_id:
        await session.rollback()
        return
    kept = dict(locked.sent_metadata or {})
    kept.pop(THUMBNAIL_SENT, None)
    kept.pop(THUMBNAIL_ERROR, None)
    if image_id is not None:
        kept[THUMBNAIL_SENT] = image_id
        if problem:
            kept[THUMBNAIL_ERROR] = problem
    locked.sent_metadata = kept
    post = await session.get(ScheduledPost, locked.scheduled_post_id)
    if post is not None:
        await queue_post_updated(session, post)
    await commit_and_publish(session, redis)
