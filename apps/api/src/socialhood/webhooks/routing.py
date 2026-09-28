"""Which workspace an inbound event belongs to (TR-WH-05). The one lookup that must look across
workspaces before any is known, so it lives here, where the tenant bypass is allowed (TR-TEN-04)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.models.connections import AccountStatus, SocialAccount


@dataclass(frozen=True)
class RoutedAccount:
    account_id: uuid.UUID
    workspace_id: uuid.UUID


async def resolve_account(
    session: AsyncSession, platform: str, platform_account_id: str
) -> RoutedAccount | None:
    """The live account for this platform id, or None (unknown or disconnected)."""
    with tenant_bypass_scope():
        row = (
            await session.execute(
                select(SocialAccount.id, SocialAccount.workspace_id).where(
                    SocialAccount.platform == platform,
                    SocialAccount.platform_account_id == platform_account_id,
                    SocialAccount.status != AccountStatus.DISCONNECTED,
                )
            )
        ).one_or_none()
    return RoutedAccount(account_id=row[0], workspace_id=row[1]) if row else None


async def accounts_for_platform_user(
    session: AsyncSession, platform_user_id: str
) -> list[RoutedAccount]:
    """Accounts matching a Meta user id from a deauthorize or data-deletion callback."""
    with tenant_bypass_scope():
        rows = (
            await session.execute(
                select(SocialAccount.id, SocialAccount.workspace_id).where(
                    or_(
                        SocialAccount.app_scoped_id == platform_user_id,
                        SocialAccount.platform_account_id == platform_user_id,
                    )
                )
            )
        ).all()
    return [RoutedAccount(account_id=r[0], workspace_id=r[1]) for r in rows]
