"""Test identities: an RSA key pair standing in for Clerk's, signed session tokens, and Clerk
user objects in the Backend API's shape."""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://clerk.socialhood.test"
PARTY = "http://localhost:3000"
WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"socialhood-test-webhook-key!").decode()


@dataclass(frozen=True)
class Keys:
    private_pem: bytes
    public_pem: str


def make_keys() -> Keys:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return Keys(private_pem=private_pem, public_pem=public_pem)


def make_token(
    keys: Keys,
    sub: str,
    *,
    issuer: str = ISSUER,
    azp: str | None = PARTY,
    expires_in: int = 60,
    omit: tuple[str, ...] = (),
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "iss": issuer,
        "iat": now - 1,
        "nbf": now - 1,
        "exp": now + expires_in,
        "sid": "sess_test",
    }
    if azp is not None:
        claims["azp"] = azp
    for name in omit:
        claims.pop(name, None)
    return jwt.encode(claims, keys.private_pem, algorithm="RS256")


def clerk_user(
    clerk_id: str,
    *,
    email: str = "priya@example.com",
    verified: bool = True,
    first_name: str | None = "Priya",
    last_name: str | None = "Nair",
    image_url: str | None = "https://img.clerk.com/priya.png",
) -> dict[str, Any]:
    return {
        "id": clerk_id,
        "first_name": first_name,
        "last_name": last_name,
        "image_url": image_url,
        "primary_email_address_id": "idn_primary",
        "email_addresses": [
            {
                "id": "idn_primary",
                "email_address": email,
                "verification": {"status": "verified" if verified else "unverified"},
            }
        ],
    }
