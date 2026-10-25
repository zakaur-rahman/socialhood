"""Collaborator invites on published Instagram posts (FR-PUB-07, C-134).

After a post with collaborators publishes, each is shown as Pending. Instagram says when one
accepts (``GET /{media}/collaborators``, ``invite_status``), so ``refresh_collaborators`` reads it:
every hour for three days after publishing (``due``, the periodic job) and on demand (the
Schedule page's Refresh). A collaborator can not be added, changed or removed after publishing
(Meta has no such call), and the read needs the token of the media's creator, which is the
connected account's. Only collaborators who allow collaborator tags are returned, so one that is
missing stays Pending.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.connections import SocialAccount
from socialhood.models.publishing import (
    COLLABORATOR_CHECK_EVERY,
    COLLABORATOR_CHECK_FOR,
    ScheduledPost,
    ScheduledPostTarget,
    TargetStatus,
)
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import publish_targets as repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services.post_publishing.projection import queue_post_updated

log = get_logger(__name__)


def initial(post: ScheduledPost) -> list[dict[str, Any]]:
    """Every collaborator Pending, as the post publishes."""
    return [{"username": name, "status": "pending"} for name in post.collaborators or ()]


def is_due(target: ScheduledPostTarget, now: datetime) -> bool:
    if target.status != TargetStatus.PUBLISHED or not target.platform_media_id:
        return False
    if not target.collaborator_statuses or target.published_at is None:
        return False
    if now - target.published_at > COLLABORATOR_CHECK_FOR:
        return False
    checked = target.collaborators_checked_at
    return checked is None or now - checked >= COLLABORATOR_CHECK_EVERY


async def read(
    post: ScheduledPost,
    target: ScheduledPostTarget,
    acct: SocialAccount,
    deps: PlatformDeps,
    now: datetime,
) -> bool:
    """Read the invites from Instagram into the target. False (nothing changed) when the read
    failed or the target has none to read; the caller holds the rows and commits."""
    if target.status != TargetStatus.PUBLISHED or not target.platform_media_id:
        return False
    if acct.platform != "instagram" or not target.collaborator_statuses:
        return False
    try:
        listed = await adapter_for(acct, deps).list_collaborators(acct, target.platform_media_id)
    except PlatformError as error:
        log.info("collaborators_unreadable", target_id=str(target.id), error_code=error.code)
        return False
    accepted = {c.username.lower(): c.status for c in listed}
    target.collaborator_statuses = [
        {
            "username": row["username"],
            "status": accepted.get(str(row["username"]).lower(), "pending"),
        }
        for row in target.collaborator_statuses
    ]
    target.collaborators_checked_at = now
    return True


async def refresh_target(
    sessionmaker: Any, redis: Any, deps: PlatformDeps, *, target_id: uuid.UUID, now: datetime
) -> bool:
    """The periodic job's body for one target, in its workspace scope."""
    async with sessionmaker() as session:
        locked = await repo.lock_post_and_target(session, target_id)
        if locked is None:
            return False
        post, target = locked
        acct = await accounts.get(session, target.social_account_id)
        if acct is None or not is_due(target, now) or not await read(post, target, acct, deps, now):
            await session.rollback()
            return False
        await queue_post_updated(session, post)
        await commit_and_publish(session, redis)
    return True


async def refresh_post(
    session: AsyncSession, post: ScheduledPost, deps: PlatformDeps, now: datetime
) -> bool:
    """On demand: every published Instagram target of the post. True when any was read."""
    changed = False
    for target in await repo.targets_of(session, post.id):
        acct = await accounts.get(session, target.social_account_id)
        if acct is not None and await read(post, target, acct, deps, now):
            changed = True
    return changed
