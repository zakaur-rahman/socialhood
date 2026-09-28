"""Social account rows (tenant-scoped; writes are scoped to the current workspace)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.repositories.base import scoped_update


async def list_all(session: AsyncSession) -> list[SocialAccount]:
    result = await session.scalars(select(SocialAccount).order_by(SocialAccount.created_at))
    return list(result.all())


async def get(session: AsyncSession, account_id: uuid.UUID) -> SocialAccount | None:
    result = await session.scalars(select(SocialAccount).where(SocialAccount.id == account_id))
    return result.one_or_none()


async def find(
    session: AsyncSession, platform: str, platform_account_id: str
) -> SocialAccount | None:
    result = await session.scalars(
        select(SocialAccount).where(
            SocialAccount.platform == platform,
            SocialAccount.platform_account_id == platform_account_id,
        )
    )
    return result.one_or_none()


async def count_live(session: AsyncSession, platform: str) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(SocialAccount)
        .where(
            SocialAccount.platform == platform,
            SocialAccount.status != AccountStatus.DISCONNECTED,
        )
    )
    return int(count or 0)


async def count_reconnectable(session: AsyncSession, platform: str) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(SocialAccount)
        .where(
            SocialAccount.platform == platform,
            SocialAccount.status.in_([AccountStatus.NEEDS_RECONNECT, AccountStatus.ERROR]),
        )
    )
    return int(count or 0)


async def any_live(session: AsyncSession) -> bool:
    count = await session.scalar(
        select(func.count())
        .select_from(SocialAccount)
        .where(SocialAccount.status != AccountStatus.DISCONNECTED)
    )
    return bool(count)


async def update(session: AsyncSession, account_id: uuid.UUID, **values: Any) -> None:
    await session.execute(scoped_update(SocialAccount, id=account_id).values(**values))
