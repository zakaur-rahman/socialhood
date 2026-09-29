"""Hashtag groups (FR-PUB-12, UX-SCR-14): named sets of hashtags inserted into a caption or first
comment with a click. Names are unique in the workspace ignoring case (422 on ``name``); hashtags
are stored without "#", lowercase (NFC), 1 to 30 of them, duplicates collapsed; each must be
letters, digits and underscores in any script, with their combining marks, so Hindi hashtags
such as #दिवाली are stored whole (422 on ``hashtags.{i}`` otherwise). Nothing here commits."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.publishing import HashtagGroup
from socialhood.repositories import scheduled_posts as repo
from socialhood.schemas.publishing import HashtagGroup as HashtagGroupOut
from socialhood.schemas.publishing import (
    HashtagGroupCreate,
    HashtagGroupList,
    HashtagGroupPatch,
)
from socialhood.services.scheduled_posts import rules

NAME_TAKEN = "You already have a group with this name."
NOT_A_HASHTAG = "Use letters, numbers and underscores only."


def group_out(row: HashtagGroup) -> HashtagGroupOut:
    return HashtagGroupOut.model_validate(row)


def normalize(hashtags: Sequence[str]) -> list[str]:
    """Stored form, duplicates collapsed in order; 422 naming each tag that isn't one."""
    tags: list[str] = []
    errors: list[FieldError] = []
    for i, raw in enumerate(hashtags):
        tag = rules.normalize_hashtag(raw)
        if tag is None:
            errors.append(FieldError(f"hashtags.{i}", NOT_A_HASHTAG))
        else:
            tags.append(tag)
    if errors:
        raise ApiError("validation_error", errors=errors)
    return rules.unique(tags)


async def list_groups(session: AsyncSession) -> HashtagGroupList:
    return HashtagGroupList(items=[group_out(g) for g in await repo.hashtag_groups(session)])


async def _check_name(
    session: AsyncSession, name: str, *, except_id: uuid.UUID | None = None
) -> None:
    if await repo.hashtag_group_name_taken(session, name, except_id=except_id):
        raise ApiError("validation_error", errors=[FieldError("name", NAME_TAKEN)])


async def _save(session: AsyncSession, row: HashtagGroup) -> HashtagGroup:
    """Flush; a name taken at the same moment by another request is the same 422."""
    try:
        async with session.begin_nested():
            session.add(row)
            await session.flush()
    except IntegrityError as error:
        raise ApiError("validation_error", errors=[FieldError("name", NAME_TAKEN)]) from error
    await session.refresh(row)
    return row


async def create(session: AsyncSession, body: HashtagGroupCreate) -> HashtagGroupOut:
    hashtags = normalize(body.hashtags)
    await _check_name(session, body.name)
    row = await _save(session, HashtagGroup(name=body.name, hashtags=hashtags))
    return group_out(row)


async def update(
    session: AsyncSession, hashtag_group_id: uuid.UUID, body: HashtagGroupPatch, *, now: datetime
) -> HashtagGroupOut:
    row = await repo.hashtag_group(session, hashtag_group_id, for_update=True)
    if row is None:
        raise ApiError("not_found")
    if body.hashtags is not None:
        row.hashtags = normalize(body.hashtags)
    if body.name is not None:
        await _check_name(session, body.name, except_id=row.id)
        row.name = body.name
    row.updated_at = now
    return group_out(await _save(session, row))


async def delete(session: AsyncSession, hashtag_group_id: uuid.UUID) -> None:
    if not await repo.delete_hashtag_group(session, hashtag_group_id):
        raise ApiError("not_found")
