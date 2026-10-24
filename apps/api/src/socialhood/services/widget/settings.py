"""The widget's settings (GR-28): one web account and one settings row per workspace.

Decisions (docs/CONFLICTS.md C-110):
- **One widget per workspace.** The settings page makes the account the first time an owner or
  admin opens it (``ensure``). Its ``platform_account_id`` is the public widget id (``wgt_`` and
  22 random characters), which is the only thing the embed carries. Several sites share one widget
  through the allowed-domains list.
- **Domains are required.** A new widget allows no site; the frame is refused everywhere until a
  domain is added (services/widget/origin.py).
- **Branding.** Free always shows "Powered by Social Hood"; Pro and Max can turn it off (PD-7,
  decided 2026-10-24). The stored choice is kept across a downgrade; what the visitor sees is
  ``show_branding`` only while the plan allows removing it.
- **AI mode** is the account's, changed with the other accounts' (PATCH social-accounts); the
  settings only report it.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import allows, check_entitlement
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.widget import WidgetSettings
from socialhood.repositories import widget as repo
from socialhood.schemas.widget import WidgetSettingsOut, WidgetSettingsUpdate
from socialhood.services.widget import origin
from socialhood.settings import Settings

WIDGET_ID_PREFIX = "wgt_"
ACCOUNT_NAME = "Website chat"
SCRIPT_PATH = "/widget.js"


def new_widget_id() -> str:
    return WIDGET_ID_PREFIX + secrets.token_urlsafe(16)


def day_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


async def ensure(session: AsyncSession) -> tuple[SocialAccount, WidgetSettings]:
    """The workspace's widget account and settings, made on first use. Runs in the workspace
    scope; the caller commits."""
    acct = await repo.find_account(session)
    if acct is None:
        acct = await _create_account(session)
    elif acct.status == AccountStatus.DISCONNECTED:
        if acct.deletion_requested_at is not None:
            raise ApiError("conflict", "The website chat is being deleted. Try again in a minute.")
        acct.status = AccountStatus.ACTIVE  # switched off by a disconnect: back on, same id
        acct.disconnected_at = None
        await session.flush()
    row = await repo.get_settings(session, acct.id)
    if row is None:
        row = WidgetSettings(social_account_id=acct.id)
        session.add(row)
        await session.flush()
        await session.refresh(row)
    return acct, row


async def _create_account(session: AsyncSession) -> SocialAccount:
    acct = SocialAccount(
        platform="web",
        platform_account_id=new_widget_id(),
        display_name=ACCOUNT_NAME,
        status=AccountStatus.ACTIVE,
        connected_at=datetime.now(UTC),
    )
    try:
        async with session.begin_nested():
            session.add(acct)
            await session.flush()
    except IntegrityError:  # two first visits at once: one web account per workspace
        found = await repo.find_account(session)
        if found is None:
            raise
        return found
    return acct


def script_url(settings: Settings, request_base: str) -> str:
    base = (settings.api_base_url or request_base).rstrip("/")
    return f"{base}{SCRIPT_PATH}"


def snippet(url: str, widget_id: str) -> str:
    return f'<script src="{url}" data-widget="{widget_id}" async></script>'


async def out(
    session: AsyncSession,
    acct: SocialAccount,
    row: WidgetSettings,
    settings: Settings,
    request_base: str,
    *,
    now: datetime | None = None,
) -> WidgetSettingsOut:
    plan = await current_plan(session)
    can_remove = allows(plan, "widget_remove_branding")
    url = script_url(settings, request_base)
    return WidgetSettingsOut(
        account_id=acct.id,
        widget_id=acct.platform_account_id,
        enabled=row.enabled,
        allowed_domains=list(row.allowed_domains or []),
        accent_color=row.accent_color,
        title=row.title,
        greeting=row.greeting,
        position=row.position,
        email_capture=row.email_capture,
        email_prompt=row.email_prompt,
        marketing_consent_enabled=row.marketing_consent_enabled,
        marketing_consent_text=row.marketing_consent_text,
        show_branding=row.show_branding or not can_remove,
        can_remove_branding=can_remove,
        ai_mode=acct.ai_mode,
        script_url=url,
        embed_snippet=snippet(url, acct.platform_account_id),
        conversations_today=await repo.count_conversations_since(
            session, acct.id, day_start(now or datetime.now(UTC))
        ),
        conversations_daily_limit=int(entitlement(plan, "widget_conversations_daily")),
        updated_at=row.updated_at,
    )


def _domain_errors(values: list[str]) -> tuple[list[str], list[FieldError]]:
    cleaned: list[str] = []
    errors: list[FieldError] = []
    for index, value in enumerate(values):
        try:
            domain = origin.normalize_domain(value)
        except ValueError as error:
            errors.append(FieldError(f"allowed_domains.{index}", str(error)))
            continue
        if domain not in cleaned:
            cleaned.append(domain)
    return cleaned, errors


async def update(session: AsyncSession, row: WidgetSettings, body: WidgetSettingsUpdate) -> None:
    """Apply the fields that were sent. 422 names each bad domain; turning the branding off on
    Free is 402 entitlement_required. The caller commits."""
    values: dict[str, Any] = body.model_dump(exclude_unset=True)
    if body.allowed_domains is not None:
        cleaned, errors = _domain_errors(body.allowed_domains)
        if errors:
            raise ApiError("validation_error", errors=errors)
        values["allowed_domains"] = cleaned
    if values.get("show_branding") is False:
        await check_entitlement(
            session,
            "widget_remove_branding",
            detail='Removing "Powered by Social Hood" is part of Pro.',
        )
    if values.get("accent_color"):
        values["accent_color"] = values["accent_color"].upper()
    nulls = [name for name, value in values.items() if value is None]
    if nulls:
        raise ApiError(
            "validation_error", errors=[FieldError(name, "This can't be empty.") for name in nulls]
        )
    if values:
        await repo.update_settings(session, row.id, **values)
        await session.refresh(row)
