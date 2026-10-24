"""API keys API (GR-25): list, make and revoke a workspace's keys. Owners and admins. The rules
are in services/api_keys.py; the keys themselves work on /public/v1 (api/public.py). They need
the integrations permission, like the webhook endpoints beside them (GR-19).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter

from socialhood.auth.deps import CanManageIntegrations, Session
from socialhood.schemas.api_keys import ApiKey, ApiKeyCreate, ApiKeyList, ApiKeyWithKey
from socialhood.services import api_keys as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["integrations"])


@router.get("/api-keys", operation_id="list_api_keys")
async def list_api_keys(ctx: CanManageIntegrations, session: Session) -> ApiKeyList:
    """Newest first, revoked keys included, with every scope a key can carry."""
    return await service.list_keys(session)


@router.post("/api-keys", status_code=201, operation_id="create_api_key")
async def create_api_key(
    body: ApiKeyCreate, ctx: CanManageIntegrations, session: Session
) -> ApiKeyWithKey:
    """The key is in this response only. 402 entitlement_required on Free (the public API is part
    of Pro); 409 at 20 active keys."""
    out = await service.create(session, body, user_id=ctx.user.id)
    await session.commit()
    return out


@router.delete("/api-keys/{key_id}", operation_id="revoke_api_key")
async def revoke_api_key(key_id: uuid.UUID, ctx: CanManageIntegrations, session: Session) -> ApiKey:
    """Stops the key working at once and removes the REST hooks it subscribed. Revoking a revoked
    key changes nothing."""
    out = await service.revoke(session, key_id, now=datetime.now(UTC))
    await session.commit()
    return out
