"""A workspace's API keys (GR-25): make, list and revoke. Owners and admins; nothing here commits.

- A key is "shk_" and 43 random characters. It is shown once, in the create response; the row
  keeps its SHA-256 (the key is long and random, so a plain hash is enough) and its first
  twelve characters, so a member can tell keys apart in the list.
- Keys carry scopes (schemas/api_keys.py). A key never gains scopes: make another.
- Public API access is Pro and Max (PD-6, the ``public_api`` entitlement): making a key on Free
  is 402. Listing and revoking stay open, so a workspace that downgraded can still clean up.
- Revoking sets ``revoked_at`` and deletes the REST hooks the key subscribed (services/
  api_hooks.py): a key that is off sends nothing. Revoking again changes nothing.
- A workspace holds at most ``ACTIVE_LIMIT`` unrevoked keys.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import check_entitlement
from socialhood.errors import ApiError
from socialhood.models.api_keys import ApiKey
from socialhood.models.integrations import WebhookEndpoint
from socialhood.repositories.base import scoped_delete
from socialhood.schemas.api_keys import (
    SCOPE_DESCRIPTIONS,
    ApiKeyCreate,
    ApiKeyList,
    ApiKeyWithKey,
    ApiScope,
)
from socialhood.schemas.api_keys import ApiKey as ApiKeyOut

KEY_PREFIX = "shk_"
PREFIX_CHARS = 12  # shown in the list: "shk_" and eight characters
ACTIVE_LIMIT = 20


def generate_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def looks_like_key(value: str) -> bool:
    """Cheap shape check before any database work."""
    return value.startswith(KEY_PREFIX) and 20 <= len(value) <= 100


def key_out(key: ApiKey) -> ApiKeyOut:
    return ApiKeyOut.model_validate(key)


def scope_catalogue() -> list[ApiScope]:
    return [ApiScope(scope=s, description=d) for s, d in SCOPE_DESCRIPTIONS.items()]


async def list_keys(session: AsyncSession) -> ApiKeyList:
    rows = await session.scalars(select(ApiKey).order_by(ApiKey.created_at.desc(), ApiKey.id))
    return ApiKeyList(
        items=[key_out(k) for k in rows.all()],
        scopes=scope_catalogue(),
        active_limit=ACTIVE_LIMIT,
    )


async def create(
    session: AsyncSession, body: ApiKeyCreate, *, user_id: uuid.UUID | None
) -> ApiKeyWithKey:
    await check_entitlement(session, "public_api")
    active = await session.scalar(
        select(func.count()).select_from(ApiKey).where(ApiKey.revoked_at.is_(None))
    )
    if (active or 0) >= ACTIVE_LIMIT:
        raise ApiError(
            "conflict", f"You can have up to {ACTIVE_LIMIT} active API keys. Revoke one first."
        )
    key = generate_key()
    row = ApiKey(
        name=body.name,
        key_prefix=key[:PREFIX_CHARS],
        key_hash=hash_key(key),
        scopes=list(dict.fromkeys(body.scopes)),
        created_by_user_id=user_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return ApiKeyWithKey(**key_out(row).model_dump(), key=key)


async def revoke(session: AsyncSession, key_id: uuid.UUID, *, now: datetime) -> ApiKeyOut:
    row = await session.get(ApiKey, key_id, with_for_update=True)
    if row is None:
        raise ApiError("not_found", "That API key wasn't found.")
    if row.revoked_at is None:
        row.revoked_at = now
        await session.execute(scoped_delete(WebhookEndpoint, api_key_id=row.id))
        await session.flush()
    return key_out(row)
