"""Connecting a WhatsApp number through Embedded Signup v4 (F-04, FR-CON-02, FR-CON-03).

The page completes Meta's dialog and posts {code, waba_id, phone_number_id}. Here: check the plan,
exchange the code for the business token, read the number, store it (a reconnect updates the same
row), and subscribe our app to its WhatsApp Business Account. Runs in the workspace scope and
commits. Every refused or failed attempt is logged for follow-up (F-04: Meta may refuse while
Social Hood's weekly onboarding allowance is used up).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import quota_error
from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import AccountStatus, Platform, SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.whatsapp import signup as meta
from socialhood.platforms.whatsapp.graph import WhatsAppHttp
from socialhood.repositories import social_accounts as accounts
from socialhood.schemas.whatsapp import EmbeddedSignup
from socialhood.services.connections import _at_capacity, _upsert, subscribe

log = get_logger(__name__)

CONNECT_FAILED = "WhatsApp didn't finish the connection. Try connecting again."
IN_USE = "This number is connected to another Social Hood workspace. Disconnect it there first."


def _check_ids(body: EmbeddedSignup) -> None:
    """Meta's ids are numeric; anything else must never reach a Graph URL path."""
    errors = [
        FieldError(name, "Must be the numeric id from Meta's signup.")
        for name, value in (("waba_id", body.waba_id), ("phone_number_id", body.phone_number_id))
        if not value.isdigit()
    ]
    if errors:
        raise ApiError("validation_error", errors=errors)


async def _check_capacity(session: AsyncSession, phone_number_id: str, plan: str) -> None:
    existing = await accounts.find(session, Platform.WHATSAPP, phone_number_id)
    if existing is not None and existing.status != AccountStatus.DISCONNECTED:
        return  # reconnecting a live number uses its own slot
    limit = await _at_capacity(session, Platform.WHATSAPP, plan)
    if limit is not None:
        noun = "account" if limit == 1 else "accounts"
        raise quota_error(
            "accounts_per_platform", limit, f"Your plan includes {limit} WhatsApp {noun}."
        )


async def complete_signup(
    session: AsyncSession,
    deps: PlatformDeps,
    *,
    signup: EmbeddedSignup,
    user_id: uuid.UUID,
    plan: str,
) -> SocialAccount:
    settings = deps.settings
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise ApiError("service_unavailable", "WhatsApp connections are not configured.")
    _check_ids(signup)
    await _check_capacity(session, signup.phone_number_id, plan)

    attempt = {"waba_id": signup.waba_id, "phone_number_id": signup.phone_number_id}
    wa = WhatsAppHttp(deps.http, settings)
    try:
        grant = await meta.exchange_code(wa, settings, signup.code)
        number = await meta.phone_number(wa, grant.access_token, signup.phone_number_id)
    except PlatformError as error:
        log.warning(
            "whatsapp_connect_failed",
            **attempt,
            error_code=error.code,
            platform_code=error.platform_code,
            platform_message=error.message,
        )
        raise ApiError("platform_error", CONNECT_FAILED) from error

    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "waba_id": signup.waba_id,
        "display_name": number.verified_name or number.display_phone_number,
        "phone_number": number.display_phone_number,
        "access_token_enc": deps.cipher.encrypt(grant.access_token),
        "token_expires_at": grant.expires_at,
        "token_refreshed_at": now,
        "status": AccountStatus.ACTIVE,
        "last_error": None,
        "connected_at": now,
        "disconnected_at": None,
        "connected_by_user_id": user_id,
    }
    acct = await _upsert(session, Platform.WHATSAPP, signup.phone_number_id, values)
    if acct is None:
        log.info("whatsapp_connect_refused", reason="account_in_use", **attempt)
        raise ApiError("account_in_use", IN_USE)
    await subscribe(session, acct, deps)
    await _register(session, deps, wa, acct, grant.access_token)
    await session.commit()
    await session.refresh(acct)
    log.info(
        "whatsapp_connected",
        account_id=str(acct.id),
        status=acct.status,
        token_expires=grant.expires_at is not None,
        quality_rating=number.quality_rating,
        **attempt,
    )
    return acct


def new_pin() -> str:
    return f"{secrets.randbelow(10**6):06d}"


async def _register(
    session: AsyncSession, deps: PlatformDeps, wa: WhatsAppHttp, acct: SocialAccount, token: str
) -> None:
    """Q-017: register the number with a two-step verification PIN we generate and keep
    (encrypted), so nobody has to choose one. A reconnect reuses the stored PIN. A failure is
    logged and leaves the account usable: a number already registered elsewhere keeps working."""
    pin = deps.cipher.decrypt(acct.whatsapp_pin_enc) if acct.whatsapp_pin_enc else new_pin()
    try:
        await meta.register_number(wa, token, acct.platform_account_id, pin)
    except PlatformError as error:
        log.warning(
            "whatsapp_register_failed",
            account_id=str(acct.id),
            error_code=error.code,
            platform_code=error.platform_code,
            platform_message=error.message,
        )
        return
    await accounts.update(session, acct.id, whatsapp_pin_enc=deps.cipher.encrypt(pin))
