"""The WhatsApp catalogue feed (C-215): ``GET /v1/feeds/whatsapp-catalogue/{token}.csv``, fetched by
Meta as a scheduled data feed (Commerce Manager, Data sources, Data file, Upload via URL).

No sign-in: the long random token in the link is the only key, so the link is secret and New link
replaces it (api/v1/wa_catalogue.py). It finds its workspace through the token
(webhooks/routing.catalogue_feed_owner, the one cross-workspace lookup), then serves the products
in Meta's data-file format and records what Meta was given (services/catalogue/wa_catalogue.fetch).
An unknown token, and a workspace whose plan lost commerce, get 404, so Meta keeps what it has.
Limited per IP like the other public routes. Not in the OpenAPI document.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Response

from socialhood.api import ratelimit
from socialhood.auth.deps import Session
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.services.catalogue import wa_catalogue
from socialhood.webhooks.routing import catalogue_feed_owner

router = APIRouter(prefix="/v1/feeds", tags=["catalogue"], include_in_schema=False)

TOKEN = re.compile(r"^[A-Za-z0-9_-]{20,100}$")


@router.get("/whatsapp-catalogue/{token}.csv", dependencies=[ratelimit.PUBLIC])
async def whatsapp_catalogue_feed(token: str, session: Session) -> Response:
    workspace_id = await catalogue_feed_owner(session, token) if TOKEN.match(token) else None
    if workspace_id is None:
        raise ApiError("not_found")
    with workspace_scope(workspace_id):
        body = await wa_catalogue.fetch(session)
        if body is None:
            raise ApiError("not_found")
        await session.commit()
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )
