"""The post's status rule (F-13 state machine) and the ``scheduled_post.updated`` payload
(TR-RT-03) the publish jobs emit.

Status: a post's status derives from its targets once none is still running (pending,
publishing, container_created): all published → published; some published → partially_published;
none → failed, or canceled when every target was canceled (a target that never ran is not a
publish, so a canceled target next to published ones makes the post partly published).

Payload: ``{scheduled_post: ScheduledPost}`` (schemas/publishing.py). The composer's checklist
(FR-PUB-10) belongs to the posts service (T7.1); a post the jobs touch is publishing or done, so
its composer is read-only and the jobs send the checklist empty with ``ready`` false. When T7.1's
projection landed; ``scheduled_post_out`` now calls it (one place).
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.publishing import (
    ScheduledPost,
    ScheduledPostStatus,
    TargetStatus,
)
from socialhood.realtime import events
from socialhood.schemas.publishing import ScheduledPost as ScheduledPostOut

FINAL_TARGET_STATUSES = frozenset(
    {TargetStatus.PUBLISHED, TargetStatus.FAILED, TargetStatus.CANCELED}
)
RUNNING_TARGET_STATUSES = frozenset(
    {TargetStatus.PENDING, TargetStatus.PUBLISHING, TargetStatus.CONTAINER_CREATED}
)


def derive_status(target_statuses: Iterable[str]) -> ScheduledPostStatus | None:
    """The post's status from its targets' (F-13); None while any target is still running."""
    statuses = list(target_statuses)
    if not statuses or any(s not in FINAL_TARGET_STATUSES for s in statuses):
        return None
    published = sum(1 for s in statuses if s == TargetStatus.PUBLISHED)
    if published == len(statuses):
        return ScheduledPostStatus.PUBLISHED
    if published:
        return ScheduledPostStatus.PARTIALLY_PUBLISHED
    if all(s == TargetStatus.CANCELED for s in statuses):
        return ScheduledPostStatus.CANCELED
    return ScheduledPostStatus.FAILED


async def scheduled_post_out(session: AsyncSession, post: ScheduledPost) -> ScheduledPostOut:
    """The post as GET …/scheduled-posts/{id} shows it, checklist included: the posts service's
    projection (services/scheduled_posts/views.post_out), so the jobs' events and the API agree."""
    from socialhood.services.scheduled_posts.views import post_out

    return await post_out(session, post)


async def queue_post_updated(session: AsyncSession, post: ScheduledPost) -> None:
    """Queue ``scheduled_post.updated`` for after the commit. Flushes first: sessions do not
    autoflush, and the payload is read back from the database."""
    await session.flush()
    await session.refresh(post)
    out = await scheduled_post_out(session, post)
    events.queue(
        session,
        post.workspace_id,
        "scheduled_post.updated",
        {"scheduled_post": out.model_dump(mode="json")},
    )
