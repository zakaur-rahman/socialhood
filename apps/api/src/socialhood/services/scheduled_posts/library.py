"""The media library (FR-PUB-13, UX-SCR-13): images and videos uploaded for posts, newest first,
for reuse in new posts, narrowed by type and by upload date (dates in the workspace time zone,
both included). Uploads for messages and knowledge are not listed (C-043)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.repositories import scheduled_posts as repo
from socialhood.schemas.publishing import MediaAssetList
from socialhood.services import media_assets
from socialhood.services.conversations import decode_cursor, encode_cursor
from socialhood.services.scheduled_posts.slots import zone


async def list_library(
    session: AsyncSession,
    *,
    asset_type: Literal["image", "video"] | None,
    since: date | None,
    until: date | None,
    cursor: str | None,
    limit: int,
    timezone: str,
) -> MediaAssetList:
    if since is not None and until is not None and until < since:
        raise ApiError(
            "validation_error",
            errors=[FieldError("until", "Pick an end date on or after the start date.")],
        )
    tz = zone(timezone)
    start = datetime.combine(since, time(0), tzinfo=tz) if since else None
    end = datetime.combine(until + timedelta(days=1), time(0), tzinfo=tz) if until else None
    rows = await repo.post_uploads(
        session,
        resource_type=asset_type,
        start=start,
        end=end,
        after=decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )
    page = rows[:limit]
    return MediaAssetList(
        items=[media_assets.asset_out(a) for a in page],
        next_cursor=(
            encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        ),
    )
