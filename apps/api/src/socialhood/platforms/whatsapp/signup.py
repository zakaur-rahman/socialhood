"""Embedded Signup v4, server side (F-04, FR-CON-02, TR-PL table).

The page runs Meta's dialog (FB.login with WHATSAPP_CONFIG_ID) and sends us the code with the
waba_id and phone_number_id from the session-info event. Here: code -> business token, then the
number's details. T0.9 item 14 confirms the exchange and field names against a real signup.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from socialhood.platforms.errors import PlatformError
from socialhood.platforms.whatsapp.graph import WhatsAppHttp
from socialhood.settings import Settings

NUMBER_FIELDS = "display_phone_number,verified_name,quality_rating"


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
    return PhoneNumber(
        id=str(body.get("id") or phone_number_id),
        display_phone_number=body.get("display_phone_number"),
        verified_name=body.get("verified_name"),
        quality_rating=body.get("quality_rating"),
    )
