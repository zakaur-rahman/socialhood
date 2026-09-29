"""The post's status rule (F-13 state machine) and the ``scheduled_post.updated`` payload
(TR-RT-03) the publish jobs emit.

Status: a post's status derives from its targets once none is still running (pending,
publishing, container_created): all published → published; some published → partially_published;
none → failed, or canceled when every target was canceled (a target that never ran is not a
publish, so a canceled target next to published ones makes the post partly published).

Payload: ``{scheduled_post: ScheduledPost}`` (schemas/publishing.py). The composer's checklist
(FR-PUB-10) belongs to the posts service (T7.1); a post the jobs touch is publishing or done, so
its composer is read-only and the jobs send the checklist empty with ``ready`` false. When T7.1's
projection lands, ``scheduled_post_out`` should call it instead (one place).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.media import MediaAsset
from socialhood.models.publishing import (
    ScheduledPost,
    ScheduledPostStatus,
    ScheduledPostTarget,
    TargetStatus,
)
from socialhood.realtime import events
from socialhood.repositories import publish_targets as repo
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


def _thumbnail(asset: MediaAsset) -> str | None:
    """Images: the image; videos: their first frame (Cloudinary makes a JPEG of a video URL)."""
    url = asset.secure_url
    if not url or asset.resource_type != "video":
        return url
    head, sep, tail = url.partition("/upload/")
    if not sep:
        return None
    stem = tail.rsplit(".", 1)[0]
    return f"{head}/upload/so_0/{stem}.jpg"


def _first_comment(post: ScheduledPost, target: ScheduledPostTarget) -> dict[str, Any] | None:
    if not post.first_comment or target.status != TargetStatus.PUBLISHED:
        return None
    if target.first_comment_platform_id:
        return {"status": "posted", "platform_comment_id": target.first_comment_platform_id}
    if target.first_comment_error:
        return {"status": "failed", "error": target.first_comment_error}
    return {"status": "pending"}


def _target(
    post: ScheduledPost, target: ScheduledPostTarget, items: dict[Any, Any]
) -> dict[str, Any]:
    error = (
        {"code": target.error_code, "message": target.error_message or ""}
        if target.error_code
        else None
    )
    return {
        "social_account_id": target.social_account_id,
        "caption_override": target.caption_override,
        "status": target.status,
        "platform_media_id": target.platform_media_id,
        "permalink": target.permalink,
        "post_id": items.get(target.id),
        "published_at": target.published_at,
        "error": error,
        "first_comment": _first_comment(post, target),
    }


async def scheduled_post_out(session: AsyncSession, post: ScheduledPost) -> ScheduledPostOut:
    """The post as GET …/scheduled-posts/{id} shows it, in the current workspace scope."""
    targets = await repo.targets_of(session, post.id)
    assets = await repo.assets_of(session, post.id)
    items = await repo.media_items_of(session, [t.id for t in targets])
    automations = await repo.linked_automations(session, post.id)
    return ScheduledPostOut.model_validate(
        {
            "id": post.id,
            "status": post.status,
            "format": post.format,
            "caption": post.caption,
            "publish_at": post.publish_at,
            "published_at": post.published_at,
            "thumbnail_url": _thumbnail(assets[0]) if assets else None,
            "asset_count": len(assets),
            "targets": [_target(post, t, items) for t in targets],
            "created_at": post.created_at,
            "updated_at": post.updated_at,
            "first_comment": post.first_comment,
            "assets": [
                {
                    "id": asset.id,
                    "resource_type": asset.resource_type,
                    "url": asset.secure_url or "",
                    "thumbnail_url": _thumbnail(asset),
                    "width": asset.width,
                    "height": asset.height,
                    "duration_s": asset.duration_s,
                    "position": position,
                }
                for position, asset in enumerate(assets)
            ],
            "automations": [
                {"id": a.id, "name": a.name, "status": a.status, "trigger": a.trigger}
                for a in automations
            ],
            "checklist": [],
            "ready": False,
            "created_by_user_id": post.created_by_user_id,
        }
    )


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
