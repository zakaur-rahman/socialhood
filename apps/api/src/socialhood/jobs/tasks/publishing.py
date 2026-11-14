"""Publishing jobs (T7.3; F-13, FR-PUB-05, FR-PUB-06, FR-PUB-11, FR-AUT-18, TR-JOB-02…05).
Thin tasks: the work is in services/post_publishing/. Interactive lane (TR-JOB-06). Each task
carries the workspace id, so none needs a cross-workspace lookup after the dispatcher's claim
(C-020).

- dispatch_due_posts: periodic, every 30 s (``* * * * * */30``, queueing lock). Claims the pending
  targets of posts whose publish_at has come (post scheduled or publishing), across workspaces:
  the posts with FOR UPDATE SKIP LOCKED (allowed in jobs/, TR-TEN-04), at most 200 at a time, then
  their pending targets: target ``publishing``, claimed_at = now, attempts + 1; the post becomes
  ``publishing`` (scheduled_post.updated). Enqueues publish_target for each under
  ``pub:{target_id}``. Its own task, like dispatch_comment_analysis: dispatch_due is the
  scheduled-message dispatcher.
- publish_target(target_id, workspace_id): also enqueued by publish now (a pending target of a
  due post is claimed by the job itself). Reads the publishing quota first (none left: target
  failed "Instagram's daily publishing limit reached"); creates the containers through the
  adapter (one for an image or a Reel; the children, in order, for a carousel: its parent waits
  for them to finish, see poll_container) by the assets' delivery URLs; status
  ``container_created``; then enqueues poll_container(target_id, 1) at once. Transient platform
  errors retry up to 3 tries (FR-PUB-05, PlatformRetry); the last try or a refusal marks the
  target failed. Queueing and run lock ``pub:{target_id}``.
- poll_container(target_id, n, workspace_id): one round of status reads. IN_PROGRESS: re-enqueue
  itself as n + 1 after 60 s up to poll 5, then every 5 minutes up to poll 10 (models/publishing.py
  POLL_*); still IN_PROGRESS at poll 10: failed "Instagram took too long to process the video". A
  carousel's children FINISHED: create the carousel container. FINISHED: publish the container (a
  lost answer, delivery_unknown, is resolved through the container's status and
  find_published_media, never by publishing twice), read the post back (permalink), then in one
  transaction: target published; the post's status derived from its targets; the media_items
  row (published_target_id); waiting automations linked (link_scheduled_post and
  link_next_posts); then post_first_comment queued when the post has one. ERROR or EXPIRED:
  failed with Instagram's reason. A post ending failed or partly published notifies the owners
  and admins (FR-PUB-06). Queueing lock ``poll:{target_id}:{n}``, run lock ``poll:{target_id}``,
  1 try (a crashed poll is picked up by the sweeper).
- post_first_comment(target_id, workspace_id): the first comment on the published post
  (FR-PUB-11); stores first_comment_platform_id, or first_comment_error after the last of 3
  tries (a lost answer is not retried); the post stays published either way. Lock
  ``firstc:{target_id}``.
- refresh_collaborator_invites: periodic, every 15 minutes (FR-PUB-07, C-134). Reads each
  collaborator's invite status (Pending or Accepted) of Instagram posts published in the last
  three days, a target at most once an hour; a failed read leaves the last answer.
- sweep_stuck_posts: periodic, every minute. Targets left ``publishing`` for more than 10 minutes
  with no publish_target waiting or running go back to pending (failed after the last attempt),
  and ``container_created`` targets idle for 10 minutes with no poll job waiting or running get
  their next poll enqueued (TR-JOB-03). A target whose YouTube upload job is waiting or running
  counts as busy too.

YouTube (C-196):
- the dispatcher first holds back due posts whose YouTube video still has to be uploaded when
  YouTube's daily uploads are used up: they move to the next quota day and their owners are told
  (services/post_publishing/youtube_media.hold_back);
- upload_youtube_video(target_id, workspace_id): bulk lane, publish_target's lock ``pub:{id}``,
  5 tries; streams the tray's video to the target's YouTube session (youtube_media.upload);
- sync_youtube_video(target_id, account_id, video_id, workspace_id): after a change to a post with
  a direct upload, videos.update when what YouTube holds differs, or videos.delete for a video no
  target holds any more (youtube_direct.sync); lock ``ytsync:{video_id}``;
- expire_youtube_uploads: periodic, every 10 minutes; direct uploads opened 24 hours ago and not
  finished: the post goes back to a draft ("The upload didn't finish").
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from procrastinate import JobContext
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import BULK, INTERACTIVE, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.retry import PlatformRetry
from socialhood.jobs.runtime import runtime
from socialhood.models.publishing import (
    COLLABORATOR_CHECK_EVERY,
    COLLABORATOR_CHECK_FOR,
    PUBLISH_ATTEMPTS,
    ScheduledPostTarget,
)
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.realtime import events
from socialhood.repositories import publish_targets as repo
from socialhood.services.post_publishing import (
    claims,
    collaborators,
    publish,
    youtube_direct,
    youtube_media,
)

log = get_logger(__name__)

CLAIM_BATCH = 200  # TR-JOB-03
SWEEP_BATCH = 200
COLLABORATOR_BATCH = 100
IDLE_AFTER = timedelta(minutes=10)  # longer than the slowest poll interval (5 minutes)
HEARTBEAT_S = 60  # a running job whose worker has been silent this long is dead
PUBLISH_RETRY = PlatformRetry(max_attempts=PUBLISH_ATTEMPTS)  # FR-PUB-05: 3 tries
FIRST_COMMENT_RETRY = PlatformRetry(max_attempts=3)
UPLOAD_RETRY = PlatformRetry(max_attempts=5)  # each try resumes from what YouTube holds
SYNC_RETRY = PlatformRetry(max_attempts=3)
# Jobs that work on a claimed target under its ``pub:{id}`` lock.
TARGET_TASKS = ("publish_target", "upload_youtube_video")


def _deps() -> PlatformDeps:
    rt = runtime()
    return deps_from(rt.http, rt.settings)


# ---------------------------------------------------------------- dispatcher


async def dispatch_due(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, now: datetime | None = None
) -> list[uuid.UUID]:
    """Claim the pending targets of due posts and enqueue their publish; returns the target ids.
    An enqueue that fails is logged: the sweeper returns the claim to pending later."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            posts = await repo.lock_due_posts(session, now, CLAIM_BATCH)
            targets = await repo.pending_targets_of(session, [p.id for p in posts])
        held = await youtube_media.hold_back(session, redis, posts, targets, now)
        posts = [p for p in posts if p.id not in held]
        targets = [t for t in targets if t.scheduled_post_id not in held]
        for post in posts:
            with workspace_scope(post.workspace_id):
                mine = [t for t in targets if t.scheduled_post_id == post.id]
                await claims.claim_post(session, post, mine, now)
        await events.commit_and_publish(session, redis)
    for target in targets:
        await enqueue_publish(target.id, target.workspace_id)
    if targets:
        log.info("publish_targets_claimed", posts=len(posts), targets=len(targets))
    return [t.id for t in targets]


async def enqueue_publish(target_id: uuid.UUID, workspace_id: uuid.UUID) -> bool:
    try:
        return await enqueue(
            publish_target,
            key=f"pub:{target_id}",
            lock=f"pub:{target_id}",
            target_id=str(target_id),
            workspace_id=str(workspace_id),
        )
    except Exception:
        log.warning("publish_enqueue_failed", target_id=str(target_id))
        return False


# ---------------------------------------------------------------- sweeper


_JOB_PENDING = """
SELECT EXISTS (
  SELECT 1 FROM procrastinate_jobs j
  LEFT JOIN procrastinate_workers w ON w.id = j.worker_id
  WHERE j.task_name = ANY(%(tasks)s)
    AND j.lock = %(lock)s
    AND (j.status = 'todo'
         OR (j.status = 'doing'
             AND w.last_heartbeat > now() - make_interval(secs => %(heartbeat)s)))
) AS pending
"""


async def job_pending(task: str | tuple[str, ...], lock: str) -> bool:
    """A job of ``task`` (or of any of them) with this run lock is waiting (a delayed poll, a
    retry after a rate limit) or running on a live worker."""
    tasks = [task] if isinstance(task, str) else list(task)
    row = await app.connector.execute_query_one_async(
        _JOB_PENDING, tasks=tasks, lock=lock, heartbeat=HEARTBEAT_S
    )
    return bool(row["pending"])


async def sweep_stuck(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, now: datetime | None = None
) -> dict[str, int]:
    """TR-JOB-03 for publishing: stuck claims back to pending (or failed), lost poll chains
    picked up again."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            stuck = await repo.stuck_publishing(session, now - claims.STUCK_AFTER, SWEEP_BATCH)
            idle = await repo.idle_containers(session, now - IDLE_AFTER, SWEEP_BATCH)
    counts = {"reset": 0, "failed": 0, "requeued": 0}
    for target in stuck:
        if await job_pending(TARGET_TASKS, f"pub:{target.id}"):
            continue  # still retrying (a rate limit can wait longer than STUCK_AFTER)
        with workspace_scope(target.workspace_id):
            outcome = await publish.reset_stuck(sessionmaker, redis, target.id, now=now)
        if outcome != "skipped":
            counts[outcome] += 1
    for target in idle:
        if await job_pending("poll_container", f"poll:{target.id}"):
            continue
        with workspace_scope(target.workspace_id):
            resumed = await publish.resume_polling(
                sessionmaker, redis, target.id, idle_before=now - IDLE_AFTER
            )
        if resumed != "skipped":
            counts[resumed] += 1
    if any(counts.values()):
        log.info("sweep_stuck_posts", **counts)
    return counts


# ---------------------------------------------------------------- tasks


@app.periodic(cron="* * * * * */30", periodic_id="dispatch_due_posts")
@app.task(name="dispatch_due_posts", queue=INTERACTIVE, queueing_lock="dispatch_due_posts")
async def dispatch_due_posts(timestamp: int) -> None:
    rt = runtime()
    await dispatch_due(rt.sessionmaker, rt.redis)


@app.task(name="publish_target", queue=INTERACTIVE, retry=PUBLISH_RETRY, pass_context=True)
async def publish_target(context: JobContext, target_id: str, workspace_id: str) -> None:
    rt = runtime()
    job = context.job

    def will_retry(error: PlatformError) -> bool:
        return PUBLISH_RETRY.get_retry_decision(exception=error, job=job) is not None

    with workspace_scope(uuid.UUID(workspace_id)):
        await publish.publish_target(
            rt.sessionmaker,
            rt.redis,
            _deps(),
            target_id=uuid.UUID(target_id),
            will_retry=will_retry,
        )


@app.task(name="poll_container", queue=INTERACTIVE)
async def poll_container(target_id: str, n: int, workspace_id: str) -> None:
    rt = runtime()
    with workspace_scope(uuid.UUID(workspace_id)):
        await publish.poll_container(
            rt.sessionmaker, rt.redis, _deps(), target_id=uuid.UUID(target_id), n=n
        )


@app.task(
    name="post_first_comment", queue=INTERACTIVE, retry=FIRST_COMMENT_RETRY, pass_context=True
)
async def post_first_comment(context: JobContext, target_id: str, workspace_id: str) -> None:
    rt = runtime()
    job = context.job

    def will_retry(error: PlatformError) -> bool:
        return FIRST_COMMENT_RETRY.get_retry_decision(exception=error, job=job) is not None

    with workspace_scope(uuid.UUID(workspace_id)):
        await publish.post_first_comment(
            rt.sessionmaker,
            rt.redis,
            _deps(),
            target_id=uuid.UUID(target_id),
            will_retry=will_retry,
        )


@app.task(name="upload_youtube_video", queue=BULK, retry=UPLOAD_RETRY, pass_context=True)
async def upload_youtube_video(context: JobContext, target_id: str, workspace_id: str) -> None:
    rt = runtime()
    job = context.job

    def will_retry(error: PlatformError) -> bool:
        return UPLOAD_RETRY.get_retry_decision(exception=error, job=job) is not None

    with workspace_scope(uuid.UUID(workspace_id)):
        await youtube_media.upload(
            rt.sessionmaker,
            rt.redis,
            _deps(),
            target_id=uuid.UUID(target_id),
            will_retry=will_retry,
        )


@app.task(name="sync_youtube_video", queue=INTERACTIVE, retry=SYNC_RETRY)
async def sync_youtube_video(
    target_id: str, account_id: str, video_id: str, workspace_id: str
) -> None:
    rt = runtime()
    with workspace_scope(uuid.UUID(workspace_id)):
        await youtube_direct.sync(
            rt.sessionmaker,
            rt.redis,
            _deps(),
            target_id=uuid.UUID(target_id),
            account_id=uuid.UUID(account_id),
            video_id=video_id,
        )


@app.periodic(cron="*/10 * * * *", periodic_id="expire_youtube_uploads")
@app.task(name="expire_youtube_uploads", queue=INTERACTIVE, queueing_lock="expire_youtube_uploads")
async def expire_youtube_uploads(timestamp: int) -> None:
    rt = runtime()
    await expire_direct_uploads(rt.sessionmaker, rt.redis)


async def expire_direct_uploads(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, now: datetime | None = None
) -> int:
    """Finds direct YouTube uploads past their deadline in any workspace; the service ends each."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            due = list(
                await session.scalars(
                    select(ScheduledPostTarget)
                    .where(
                        ScheduledPostTarget.upload_expires_at <= now,
                        ScheduledPostTarget.platform_media_id.is_(None),
                    )
                    .limit(200)
                )
            )
    return await youtube_direct.expire(sessionmaker, redis, due, now)


async def refresh_collaborator_invites(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    now: datetime | None = None,
) -> int:
    """FR-PUB-07: read the collaborator invites of posts published in the last three days, each
    at most once an hour. Returns how many targets were read."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        with tenant_bypass_scope():
            due = await repo.collaborator_checks_due(
                session,
                now - COLLABORATOR_CHECK_FOR,
                now - COLLABORATOR_CHECK_EVERY,
                COLLABORATOR_BATCH,
            )
    read = 0
    for target in due:
        with workspace_scope(target.workspace_id):
            if await collaborators.refresh_target(
                sessionmaker, redis, deps, target_id=target.id, now=now
            ):
                read += 1
    return read


@app.periodic(cron="*/15 * * * *", periodic_id="refresh_collaborator_invites")
@app.task(
    name="refresh_collaborator_invites",
    queue=INTERACTIVE,
    queueing_lock="refresh_collaborator_invites",
)
async def refresh_collaborator_invites_task(timestamp: int) -> None:
    rt = runtime()
    await refresh_collaborator_invites(rt.sessionmaker, rt.redis, _deps())


@app.periodic(cron="* * * * *", periodic_id="sweep_stuck_posts")
@app.task(name="sweep_stuck_posts", queue=INTERACTIVE, queueing_lock="sweep_stuck_posts")
async def sweep_stuck_posts(timestamp: int) -> None:
    rt = runtime()
    await sweep_stuck(rt.sessionmaker, rt.redis)
