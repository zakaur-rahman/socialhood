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
- sweep_stuck_posts: periodic, every minute. Targets left ``publishing`` for more than 10 minutes
  with no publish_target waiting or running go back to pending (failed after the last attempt),
  and ``container_created`` targets idle for 10 minutes with no poll job waiting or running get
  their next poll enqueued (TR-JOB-03).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from procrastinate import JobContext
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.retry import PlatformRetry
from socialhood.jobs.runtime import runtime
from socialhood.models.publishing import PUBLISH_ATTEMPTS
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.realtime import events
from socialhood.repositories import publish_targets as repo
from socialhood.services.post_publishing import claims, publish

log = get_logger(__name__)

CLAIM_BATCH = 200  # TR-JOB-03
SWEEP_BATCH = 200
IDLE_AFTER = timedelta(minutes=10)  # longer than the slowest poll interval (5 minutes)
HEARTBEAT_S = 60  # a running job whose worker has been silent this long is dead
PUBLISH_RETRY = PlatformRetry(max_attempts=PUBLISH_ATTEMPTS)  # FR-PUB-05: 3 tries
FIRST_COMMENT_RETRY = PlatformRetry(max_attempts=3)


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
  WHERE j.task_name = %(task)s
    AND j.lock = %(lock)s
    AND (j.status = 'todo'
         OR (j.status = 'doing'
             AND w.last_heartbeat > now() - make_interval(secs => %(heartbeat)s)))
) AS pending
"""


async def job_pending(task: str, lock: str) -> bool:
    """A job of ``task`` with this run lock is waiting (a delayed poll, a retry after a rate
    limit) or running on a live worker."""
    row = await app.connector.execute_query_one_async(
        _JOB_PENDING, task=task, lock=lock, heartbeat=HEARTBEAT_S
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
        if await job_pending("publish_target", f"pub:{target.id}"):
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


@app.periodic(cron="* * * * *", periodic_id="sweep_stuck_posts")
@app.task(name="sweep_stuck_posts", queue=INTERACTIVE, queueing_lock="sweep_stuck_posts")
async def sweep_stuck_posts(timestamp: int) -> None:
    rt = runtime()
    await sweep_stuck(rt.sessionmaker, rt.redis)
