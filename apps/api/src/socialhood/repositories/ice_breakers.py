"""An account's conversation starters (GR-11). Tenant-scoped: reads are filtered by the session's
workspace, deletes go through ``scoped_delete``."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import IceBreaker
from socialhood.repositories.base import scoped_delete


async def for_account(session: AsyncSession, social_account_id: uuid.UUID) -> list[IceBreaker]:
    """The account's starters in order."""
    result = await session.scalars(
        select(IceBreaker)
        .where(IceBreaker.social_account_id == social_account_id)
        .order_by(IceBreaker.position)
    )
    return list(result.all())


async def get(session: AsyncSession, ice_breaker_id: uuid.UUID) -> IceBreaker | None:
    return (
        await session.scalars(select(IceBreaker).where(IceBreaker.id == ice_breaker_id))
    ).one_or_none()


async def delete_from(
    session: AsyncSession, social_account_id: uuid.UUID, *, position: int
) -> None:
    """Drop the starters at ``position`` and after it."""
    await session.execute(
        scoped_delete(IceBreaker, social_account_id=social_account_id).where(
            IceBreaker.position >= position
        )
    )
