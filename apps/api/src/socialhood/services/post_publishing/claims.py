"""The dispatcher's claim and the sweeper's repairs (T7.3; F-13, TR-JOB-03).

The jobs lock the rows across workspaces (``tenant_bypass_scope`` in jobs/); these functions
change them in the post's workspace scope, which the caller sets, and queue
``scheduled_post.updated``. Nothing here commits.

- claim: each pending target of a due post becomes ``publishing`` (claimed_at now, attempts + 1)
  and the post ``publishing`` (the F-13 "first target claimed" transition).
- a target left ``publishing`` for STUCK_AFTER (its publish_target was lost, or its worker died
  before creating containers) goes back to ``pending`` for the dispatcher, or fails once it has
  been claimed PUBLISH_ATTEMPTS times.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.publishing import (
    PUBLISH_ATTEMPTS,
    ScheduledPost,
    ScheduledPostStatus,
    ScheduledPostTarget,
    TargetStatus,
)
from socialhood.services.post_publishing.projection import queue_post_updated

STUCK_AFTER = timedelta(minutes=10)  # TR-JOB-03
STUCK_REASON = "Couldn't publish this post. Edit it and try again."


def claim_target(post: ScheduledPost, target: ScheduledPostTarget, now: datetime) -> None:
    """A pending target of a due post starts publishing (the caller holds both rows)."""
    target.status = TargetStatus.PUBLISHING
    target.claimed_at = now
    target.attempts = (target.attempts or 0) + 1
    target.error_code = None
    target.error_message = None
    if post.status == ScheduledPostStatus.SCHEDULED:
        post.status = ScheduledPostStatus.PUBLISHING


async def claim_post(
    session: AsyncSession,
    post: ScheduledPost,
    targets: Sequence[ScheduledPostTarget],
    now: datetime,
) -> None:
    """The dispatcher's claim of one due post's pending targets (all locked by the caller)."""
    for target in targets:
        claim_target(post, target, now)
    await queue_post_updated(session, post)


def is_due(post: ScheduledPost, now: datetime) -> bool:
    return (
        post.status in (ScheduledPostStatus.SCHEDULED, ScheduledPostStatus.PUBLISHING)
        and post.publish_at is not None
        and post.publish_at <= now
    )


def give_up_or_retry(target: ScheduledPostTarget) -> bool:
    """A stuck ``publishing`` target (locked by the caller): back to pending, or failed after
    its last attempt. Returns True when it failed (the caller then settles the post)."""
    if (target.attempts or 0) >= PUBLISH_ATTEMPTS:
        return True
    target.status = TargetStatus.PENDING
    target.claimed_at = None
    return False
