"""Which workspace an inbound event belongs to (TR-WH-05). The one lookup that must look across
workspaces before any is known, so it lives here, where the tenant bypass is allowed (TR-TEN-04)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.models.catalogue import ShopifyConnection
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.orders import PaymentConnection


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


async def resolve_waba_accounts(session: AsyncSession, waba_id: str) -> list[RoutedAccount]:
    """The live WhatsApp numbers of one WhatsApp Business Account: events about the account
    (a number's quality or tier) arrive under its id, not a phone number's (GR-23)."""
    with tenant_bypass_scope():
        rows = (
            await session.execute(
                select(SocialAccount.id, SocialAccount.workspace_id).where(
                    SocialAccount.platform == "whatsapp",
                    SocialAccount.waba_id == waba_id,
                    SocialAccount.status != AccountStatus.DISCONNECTED,
                )
            )
        ).all()
    return [RoutedAccount(account_id=r[0], workspace_id=r[1]) for r in rows]


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


async def shopify_owner(session: AsyncSession, shop_domain: str) -> uuid.UUID | None:
    """The workspace that holds this Shopify store (GR-31), or None. A store belongs to one
    workspace at a time, and a webhook names only the store."""
    with tenant_bypass_scope():
        return await session.scalar(
            select(ShopifyConnection.workspace_id).where(
                ShopifyConnection.shop_domain == shop_domain
            )
        )


async def razorpay_owner(session: AsyncSession, token: str) -> uuid.UUID | None:
    """The workspace whose Razorpay webhook address carries this token (GR-32), or None."""
    if not token:
        return None
    with tenant_bypass_scope():
        return await session.scalar(
            select(PaymentConnection.workspace_id).where(
                PaymentConnection.webhook_token == token,
                PaymentConnection.razorpay_key_id.is_not(None),
            )
        )


async def razorpay_webhook_secret(session: AsyncSession, token: str) -> bytes | None:
    """The encrypted webhook secret for this address token (GR-32), or None. The caller decrypts
    it and checks the post's signature before anything else is read."""
    if not token:
        return None
    with tenant_bypass_scope():
        return await session.scalar(
            select(PaymentConnection.razorpay_webhook_secret_enc).where(
                PaymentConnection.webhook_token == token,
                PaymentConnection.razorpay_key_id.is_not(None),
            )
        )
