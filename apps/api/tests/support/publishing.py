"""P7 rows for tests: scheduled posts with their assets and targets, posting times and hashtag
groups (written through the ORM in the workspace's scope, committed, returned as ids). Accounts
come from tests/support/inbox.py (make_account), uploads from make_asset (purpose "post")."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.media import MediaAsset
from socialhood.models.publishing import (
    HashtagGroup,
    PostingSlot,
    ScheduledPost,
    ScheduledPostAsset,
    ScheduledPostTarget,
)
from tests.support.inbox import make_asset


def _uuid(value: uuid.UUID | str) -> uuid.UUID:
    return uuid.UUID(str(value))


@dataclass(frozen=True)
class MadePost:
    id: uuid.UUID
    asset_ids: tuple[uuid.UUID, ...]
    target_ids: Mapping[uuid.UUID, uuid.UUID]  # account id -> target id


def derived_format(resource_types: Sequence[str]) -> str | None:
    """§5.7's format rules: 1 image is an image post, 1 video a Reel, 2 to 10 a carousel."""
    if len(resource_types) == 1:
        return "image" if resource_types[0] == "image" else "reel"
    if 2 <= len(resource_types) <= 10:
        return "carousel"
    return None


async def make_scheduled_post(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    account_ids: Sequence[uuid.UUID | str] = (),
    asset_ids: Sequence[uuid.UUID | str] | None = None,
    status: str = "draft",
    caption: str = "New arrivals this week #summer",
    first_comment: str | None = None,
    publish_at: datetime | None = None,
    caption_overrides: Mapping[uuid.UUID | str, str] | None = None,
    target_status: str = "pending",
    target_values: Mapping[str, Any] | None = None,
    **values: Any,
) -> MadePost:
    """A post with its assets (in the order given) and one target per account.

    Without ``asset_ids``, one new 1080 x 1350 JPEG uploaded for posts. The format is derived from
    the assets unless ``format`` is given; a post past draft gets a time an hour from now unless
    ``publish_at`` is given. Published targets get a platform media id and permalink unless
    ``target_values`` sets them. Other ScheduledPost columns go in ``values``.
    """
    wid = _uuid(workspace_id)
    if asset_ids is None:
        asset_ids = [await make_asset(engine, workspace_id=wid, purpose="post", height=1350)]
    assets = [_uuid(a) for a in asset_ids]
    overrides = {_uuid(k): v for k, v in (caption_overrides or {}).items()}
    if publish_at is None and status != "draft":
        publish_at = datetime.now(UTC) + timedelta(hours=1)
    with workspace_scope(wid):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            kinds = []
            for asset_id in assets:
                asset = await session.get(MediaAsset, asset_id)
                assert asset is not None, "no such asset in this workspace"
                kinds.append(asset.resource_type)
            values.setdefault("format", derived_format(kinds))
            post = ScheduledPost(
                status=status,
                caption=caption,
                first_comment=first_comment,
                publish_at=publish_at,
                **values,
            )
            session.add(post)
            await session.flush()
            session.add_all(
                ScheduledPostAsset(scheduled_post_id=post.id, media_asset_id=a, position=i)
                for i, a in enumerate(assets)
            )
            targets: dict[uuid.UUID, uuid.UUID] = {}
            for account in account_ids:
                account_id = _uuid(account)
                extra = dict(target_values or {})
                extra.setdefault("caption_override", overrides.get(account_id))
                if target_status == "published":
                    extra.setdefault("platform_media_id", f"1790{uuid.uuid4().int % 10**12:012d}")
                    extra.setdefault("permalink", "https://www.instagram.com/p/published/")
                    extra.setdefault("published_at", datetime.now(UTC))
                target = ScheduledPostTarget(
                    scheduled_post_id=post.id,
                    social_account_id=account_id,
                    status=target_status,
                    **extra,
                )
                session.add(target)
                await session.flush()
                targets[account_id] = target.id
            await session.commit()
            return MadePost(post.id, tuple(assets), targets)


async def make_posting_slot(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    account_id: uuid.UUID | str,
    weekday: int = 2,
    local_time: time = time(18, 0),
) -> uuid.UUID:
    """A weekly posting time; by default Wednesday 18:00 in the workspace time zone."""
    with workspace_scope(_uuid(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = PostingSlot(
                social_account_id=_uuid(account_id), weekday=weekday, local_time=local_time
            )
            session.add(row)
            await session.commit()
            return row.id


async def make_hashtag_group(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    name: str = "Summer sale",
    hashtags: Sequence[str] = ("summer", "sale", "newarrivals"),
) -> uuid.UUID:
    """A saved group; hashtags are stored as given (without "#", lowercase)."""
    with workspace_scope(_uuid(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = HashtagGroup(name=name, hashtags=list(hashtags))
            session.add(row)
            await session.commit()
            return row.id
