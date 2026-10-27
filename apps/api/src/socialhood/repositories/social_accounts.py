"""Social account rows (tenant-scoped; writes are scoped to the current workspace)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.connections import AccountStatus, AiMode, SocialAccount
from socialhood.models.widget import WidgetSettings
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


def counts_as_channel() -> ColumnElement[bool]:
    """Whether an account is a channel the business has really connected (C-150).

    The website chat's account is made the first time its settings page opens (GR-28), before the
    business has switched it on or added a website. Until the widget is on and has at least one
    allowed website it can't receive a chat, so it doesn't count; every other platform's account
    counts as before.
    """
    widget_live = (
        select(WidgetSettings.id)
        .where(
            WidgetSettings.social_account_id == SocialAccount.id,
            WidgetSettings.enabled.is_(True),
            func.cardinality(WidgetSettings.allowed_domains) > 0,
        )
        .exists()
    )
    return or_(SocialAccount.platform != "web", widget_live)


async def any_live(session: AsyncSession) -> bool:
    count = await session.scalar(
        select(func.count())
        .select_from(SocialAccount)
        .where(SocialAccount.status != AccountStatus.DISCONNECTED, counts_as_channel())
    )
    return bool(count)


async def any_live_with_ai(session: AsyncSession) -> bool:
    """A connected account whose AI mode is Suggest or Auto (the checklist's AI step, C-060)."""
    count = await session.scalar(
        select(func.count())
        .select_from(SocialAccount)
        .where(
            SocialAccount.status != AccountStatus.DISCONNECTED,
            SocialAccount.ai_mode != AiMode.OFF,
            counts_as_channel(),
        )
    )
    return bool(count)


async def update(session: AsyncSession, account_id: uuid.UUID, **values: Any) -> None:
    await session.execute(scoped_update(SocialAccount, id=account_id).values(**values))
