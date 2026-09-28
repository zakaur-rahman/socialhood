"""Clerk: session token verification (TR-AUTH-02) and the Backend API user fetch (TR-AUTH-03).

Tokens are verified locally with the instance's PEM public key, so no request makes a network
call to Clerk. The Backend API is called once per user, the first time they are seen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import jwt

from socialhood.settings import Settings

CLERK_API = "https://api.clerk.com/v1"


class InvalidToken(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ClerkUnavailable(Exception):
    """The Clerk Backend API could not be reached or refused the request."""


def verify_session_token(token: str, settings: Settings) -> str:
    """Return the Clerk user id (``sub``) of a valid session token, or raise InvalidToken."""
    if not settings.clerk_jwt_key or not settings.clerk_issuer:
        raise InvalidToken("clerk_not_configured")
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            settings.clerk_jwt_key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            leeway=5,
            options={"require": ["exp", "iat", "nbf", "sub", "iss"]},
        )
    except jwt.PyJWTError as error:
        raise InvalidToken("invalid_token") from error
    azp = claims.get("azp")
    if azp is not None and azp not in settings.clerk_authorized_parties:
        raise InvalidToken("invalid_azp")
    subject = claims["sub"]
    if not isinstance(subject, str) or not subject:
        raise InvalidToken("invalid_sub")
    return subject


@dataclass(frozen=True)
class ClerkUser:
    id: str
    email: str | None
    email_verified: bool
    first_name: str | None
    name: str | None
    image_url: str | None


def parse_clerk_user(data: dict[str, Any]) -> ClerkUser:
    """Read the fields we use from a Clerk user object (API response or webhook ``data``)."""
    primary_id = data.get("primary_email_address_id")
    email: str | None = None
    verified = False
    for address in data.get("email_addresses") or []:
        if address.get("id") == primary_id:
            email = address.get("email_address")
            verified = (address.get("verification") or {}).get("status") == "verified"
            break
    first = (data.get("first_name") or "").strip() or None
    last = (data.get("last_name") or "").strip() or None
    full = " ".join(part for part in (first, last) if part) or None
    return ClerkUser(
        id=str(data["id"]),
        email=email.strip().lower() if email else None,
        email_verified=verified,
        first_name=first,
        name=full,
        image_url=data.get("image_url") or None,
    )


class ClerkClient:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self.http = http
        self.secret = (
            settings.clerk_secret_key.get_secret_value() if settings.clerk_secret_key else ""
        )

    async def get_user(self, user_id: str) -> ClerkUser:
        if not self.secret:
            raise ClerkUnavailable("CLERK_SECRET_KEY is not set")
        try:
            response = await self.http.get(
                f"{CLERK_API}/users/{user_id}",
                headers={"Authorization": f"Bearer {self.secret}"},
            )
        except httpx.HTTPError as error:
            raise ClerkUnavailable("clerk_unreachable") from error
        if response.status_code != 200:
            raise ClerkUnavailable(f"clerk_status_{response.status_code}")
        return parse_clerk_user(response.json())
