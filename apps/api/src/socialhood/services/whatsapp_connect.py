"""Connecting a WhatsApp number through Embedded Signup v4 (F-04, FR-CON-02, FR-CON-03).

The page completes Meta's dialog and posts {code, waba_id?, phone_number_id?}: the ids come from
Meta's session-info message, which doesn't always arrive or name a number (FINISH_ONLY_WABA). Here:
check the plan, exchange the code for the business token, find any id the page couldn't give, read
the number, store it (a reconnect updates the same row), and subscribe our app to its WhatsApp
Business Account. Runs in the workspace scope and commits. Every refused or failed attempt is
logged for follow-up (F-04: Meta may refuse while Social Hood's weekly onboarding allowance is used
up).
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
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
from socialhood.repositories import workspaces
from socialhood.schemas.whatsapp import EmbeddedSignup
from socialhood.services.connections import _at_capacity, _upsert, subscribe
from socialhood.settings import Settings

log = get_logger(__name__)

CONNECT_FAILED = "WhatsApp didn't finish the connection. Try connecting again."
IN_USE = "This number is connected to another Social Hood workspace. Disconnect it there first."
CHOOSE_BUSINESS_ACCOUNT = (
    "Meta didn't say which WhatsApp Business Account to connect. Connect again and choose one "
    "in Meta's popup."
)
# Meta's test number (API Setup) can't be picked in Embedded Signup, which is how a WABA with no
# number usually comes back; docs/dev-whatsapp.md connects one for development.
NO_PHONE_NUMBER = (
    "This WhatsApp Business Account has no phone number yet. Add and verify one in Meta's popup "
    "or in WhatsApp Manager, then connect again. Meta's test numbers can't be connected this "
    "way; use a number your business owns."
)
CHOOSE_NUMBER = (
    "This WhatsApp Business Account has more than one number. Connect again and pick the one to "
    "use in Meta's popup."
)


@dataclass(frozen=True)
class _Ids:
    """The number to connect and where each id came from (logged, never a token)."""

    waba_id: str
    phone_number_id: str
    number: meta.PhoneNumber | None  # already read from the account's list
    waba_source: str  # session_info | debug_token
    phone_source: str  # session_info | phone_numbers


def _check_ids(body: EmbeddedSignup) -> None:
    """Meta's ids are numeric; anything else must never reach a Graph URL path."""
    errors = [
        FieldError(name, "Must be the numeric id from Meta's signup.")
        for name, value in (("waba_id", body.waba_id), ("phone_number_id", body.phone_number_id))
        if value is not None and not value.isdigit()
    ]
    if errors:
        raise ApiError("validation_error", errors=errors)


async def _resolve_ids(
    wa: WhatsAppHttp, settings: Settings, token: str, signup: EmbeddedSignup
) -> _Ids:
    """The ids the session info gave, and the rest from Meta with the business token: the shared
    WhatsApp Business Account from debug_token, then its number from phone_numbers. More than one
    of either, or no number, is the owner's to settle in Meta's popup (422)."""
    waba_id, waba_source = signup.waba_id, "session_info"
    if waba_id is None:
        waba_source = "debug_token"
        shared = await meta.shared_waba_ids(wa, settings, token)
        if len(shared) != 1:
            code = "wa_choose_business_account"
            log.info("whatsapp_connect_refused", reason=code, shared_wabas=len(shared))
            raise ApiError(code, CHOOSE_BUSINESS_ACCOUNT)
        waba_id = shared[0]
    if signup.phone_number_id is not None:
        return _Ids(waba_id, signup.phone_number_id, None, waba_source, "session_info")
    numbers = await meta.phone_numbers(wa, token, waba_id)
    if len(numbers) == 1:
        return _Ids(waba_id, numbers[0].id, numbers[0], waba_source, "phone_numbers")
    code, detail = (
        ("wa_choose_number", CHOOSE_NUMBER) if numbers else ("wa_no_phone_number", NO_PHONE_NUMBER)
    )
    log.info(
        "whatsapp_connect_refused",
        reason=code,
        waba_id=waba_id,
        waba_source=waba_source,
        numbers=len(numbers),
    )
    raise ApiError(code, detail)


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
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    plan: str,
) -> SocialAccount:
    settings = deps.settings
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise ApiError("service_unavailable", "WhatsApp connections are not configured.")
    _check_ids(signup)
    if signup.phone_number_id is not None:
        # Before the code is spent; a number found below is checked once it is known.
        await _check_capacity(session, signup.phone_number_id, plan)

    wa = WhatsAppHttp(deps.http, settings)
    try:
        grant = await meta.exchange_code(wa, settings, signup.code)
        ids = await _resolve_ids(wa, settings, grant.access_token, signup)
    except PlatformError as error:
        _log_failed(error, waba_id=signup.waba_id, phone_number_id=signup.phone_number_id)
        raise ApiError("platform_error", CONNECT_FAILED) from error
    log.info(
        "whatsapp_signup_ids",
        waba_id=ids.waba_id,
        phone_number_id=ids.phone_number_id,
        waba_source=ids.waba_source,
        phone_source=ids.phone_source,
    )
    return await connect_number(
        session,
        deps,
        grant=grant,
        waba_id=ids.waba_id,
        phone_number_id=ids.phone_number_id,
        number=ids.number,
        workspace_id=workspace_id,
        user_id=user_id,
        plan=plan,
        capacity_checked=signup.phone_number_id is not None,
    )


async def connect_number(
    session: AsyncSession,
    deps: PlatformDeps,
    *,
    grant: meta.BusinessToken,
    waba_id: str,
    phone_number_id: str,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID | None,
    plan: str,
    number: meta.PhoneNumber | None = None,
    capacity_checked: bool = False,
) -> SocialAccount:
    """Everything after the token (Embedded Signup, and scripts/connect_whatsapp_number.py in
    development): read the number, check the plan and that the workspace is active, store the
    number with the token encrypted (a reconnect updates the same row; 409 account_in_use when
    it is live in another workspace), subscribe our app to its WhatsApp Business Account, register
    it, and commit. Runs in the workspace scope."""
    attempt = {"waba_id": waba_id, "phone_number_id": phone_number_id}
    wa = WhatsAppHttp(deps.http, deps.settings)
    if not capacity_checked:
        await _check_capacity(session, phone_number_id, plan)
    if number is None:
        try:
            number = await meta.phone_number(wa, grant.access_token, phone_number_id)
        except PlatformError as error:
            _log_failed(error, **attempt)
            raise ApiError("platform_error", CONNECT_FAILED) from error
    # A deletion that began after the request was let in: nothing may be added to it (T9.6).
    if not await workspaces.is_active(session, workspace_id, lock=True):
        raise ApiError("not_found")

    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "waba_id": waba_id,
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
    acct = await _upsert(session, Platform.WHATSAPP, phone_number_id, values)
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


def _log_failed(error: PlatformError, **attempt: str | None) -> None:
    log.warning(
        "whatsapp_connect_failed",
        **attempt,
        error_code=error.code,
        platform_code=error.platform_code,
        platform_message=error.message,
    )


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
