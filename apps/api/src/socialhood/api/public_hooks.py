"""REST hooks of the public API (GR-26): what Zapier triggers subscribe and unsubscribe with.

A subscription is an ordinary webhook endpoint made on behalf of the key (services/api_hooks.py),
so the deliveries, signing, retries and log are GR-04's. Needs the ``webhooks:subscribe`` scope.
In the public API's OpenAPI document with api/public.py.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from socialhood.auth.api_key import ApiKeyContext, require_scope
from socialhood.auth.deps import Session
from socialhood.schemas.public_hooks import HookList, HookSubscribe, HookSubscribed
from socialhood.security.crypto import cipher_for
from socialhood.services import api_hooks

router = APIRouter(prefix="/public/v1")

Subscribe = Annotated[ApiKeyContext, Depends(require_scope("webhooks:subscribe"))]


# ---------------------------------------------------------------- REST hooks (Zapier triggers)


@router.get("/hooks", operation_id="list_hooks", tags=["REST hooks"])
async def list_hooks(ctx: Subscribe, session: Session) -> HookList:
    """The REST hooks subscribed with API keys."""
    return await api_hooks.list_hooks(session)


@router.post("/hooks", status_code=201, operation_id="subscribe_hook", tags=["REST hooks"])
async def subscribe_hook(
    request: Request, body: HookSubscribe, ctx: Subscribe, session: Session
) -> HookSubscribed:
    """Send a trigger's events to ``target_url``: the same signed deliveries, retries and log as
    an outbound webhook endpoint. The signing secret is in this response only."""
    settings = request.app.state.settings
    out = await api_hooks.subscribe(
        session,
        body,
        key_id=ctx.key_id,
        cipher=cipher_for(tuple(settings.token_encryption_keys)),
        allow_private=bool(settings.webhooks_allow_private),
    )
    await session.commit()
    return out


@router.delete(
    "/hooks/{hook_id}", status_code=204, operation_id="unsubscribe_hook", tags=["REST hooks"]
)
async def unsubscribe_hook(hook_id: uuid.UUID, ctx: Subscribe, session: Session) -> Response:
    await api_hooks.unsubscribe(session, hook_id)
    await session.commit()
    return Response(status_code=204)
