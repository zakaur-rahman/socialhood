"""Embedded Signup v4, server side (F-04, FR-CON-02, TR-PL table).

The page runs Meta's dialog (FB.login with WHATSAPP_CONFIG_ID) and sends us the code with the
waba_id and phone_number_id from the session-info event when it arrived. Here: code -> business
token, the ids the page couldn't give (the shared WhatsApp Business Accounts from debug_token, the
account's numbers from phone_numbers), then the number's details. T0.9 item 14 confirms the
exchange and field names against a real signup.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from socialhood.platforms.errors import PlatformError
from socialhood.platforms.whatsapp.graph import WhatsAppHttp
from socialhood.settings import Settings

NUMBER_FIELDS = "display_phone_number,verified_name,quality_rating"
# The permission whose granular scope lists the WhatsApp Business Accounts shared with the app.
WABA_SCOPE = "whatsapp_business_management"


@dataclass(frozen=True)
class BusinessToken:
    access_token: str
    # Business integration system-user tokens are documented as not expiring; keep an expiry
    # only if Meta sends one.
    expires_at: datetime | None


@dataclass(frozen=True)
class PhoneNumber:
    id: str
    display_phone_number: str | None
    verified_name: str | None
    quality_rating: str | None


def _expiry(expires_in: Any) -> datetime | None:
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None
    return datetime.now(UTC) + timedelta(seconds=seconds) if seconds > 0 else None


async def exchange_code(wa: WhatsAppHttp, settings: Settings, code: str) -> BusinessToken:
    secret = settings.meta_app_secret.get_secret_value() if settings.meta_app_secret else ""
    body = await wa.request(
        "GET",
        "oauth/access_token",
        endpoint="oauth.access_token",
        params={"client_id": settings.meta_app_id or "", "client_secret": secret, "code": code},
    )
    if not isinstance(body, dict) or not body.get("access_token"):
        raise PlatformError("platform_rejected", message="Meta returned no access token")
    return BusinessToken(str(body["access_token"]), _expiry(body.get("expires_in")))


def _number(item: dict[str, Any], fallback_id: str = "") -> PhoneNumber:
    return PhoneNumber(
        id=str(item.get("id") or fallback_id),
        display_phone_number=item.get("display_phone_number"),
        verified_name=item.get("verified_name"),
        quality_rating=item.get("quality_rating"),
    )


async def shared_waba_ids(wa: WhatsAppHttp, settings: Settings, token: str) -> list[str]:
    """Meta's documented fallback when the session info didn't name the WhatsApp Business
    Account: debug_token on the business token, read with the app token, lists the shared
    accounts as the target_ids of the whatsapp_business_management granular scope (most
    recently onboarded first)."""
    secret = settings.meta_app_secret.get_secret_value() if settings.meta_app_secret else ""
    body = await wa.request(
        "GET",
        "debug_token",
        endpoint="debug_token",
        token=f"{settings.meta_app_id or ''}|{secret}",
        params={"input_token": token},
    )
    data = body.get("data") if isinstance(body, dict) else None
    scopes = data.get("granular_scopes") if isinstance(data, dict) else None
    ids: list[str] = []
    for scope in scopes if isinstance(scopes, list) else []:
        if not isinstance(scope, dict) or scope.get("scope") != WABA_SCOPE:
            continue
        targets = scope.get("target_ids")
        for target in targets if isinstance(targets, list) else []:
            value = str(target)
            if value.isdigit() and value not in ids:
                ids.append(value)
    return ids


async def phone_numbers(wa: WhatsAppHttp, token: str, waba_id: str) -> list[PhoneNumber]:
    """The numbers on a WhatsApp Business Account (first page; one is all we can take)."""
    body = await wa.request(
        "GET",
        f"{waba_id}/phone_numbers",
        endpoint="waba.phone_numbers",
        token=token,
        params={"fields": f"id,{NUMBER_FIELDS}"},
    )
    items = body.get("data") if isinstance(body, dict) else None
    if not isinstance(items, list):
        raise PlatformError("platform_rejected", message="Meta returned no phone number list")
    return [
        _number(item)
        for item in items
        if isinstance(item, dict) and str(item.get("id") or "").isdigit()
    ]


async def phone_number(wa: WhatsAppHttp, token: str, phone_number_id: str) -> PhoneNumber:
    body = await wa.request(
        "GET",
        phone_number_id,
        endpoint="phone_number",
        token=token,
        params={"fields": NUMBER_FIELDS},
    )
    if not isinstance(body, dict):
        raise PlatformError("platform_rejected", message="Meta returned no phone number details")
    return _number(body, phone_number_id)


async def register_number(wa: WhatsAppHttp, token: str, phone_number_id: str, pin: str) -> None:
    """Register the number on the Cloud API with a two-step verification PIN (Q-017). Without it
    a number new to the Cloud API cannot send (133010)."""
    body = await wa.request(
        "POST",
        f"{phone_number_id}/register",
        endpoint="phone_number.register",
        token=token,
        json={"messaging_product": "whatsapp", "pin": pin},
    )
    if not (isinstance(body, dict) and body.get("success")):
        raise PlatformError("platform_rejected", message="Meta did not confirm the registration")
