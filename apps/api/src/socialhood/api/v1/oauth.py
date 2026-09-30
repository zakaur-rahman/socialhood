"""GET /v1/oauth/instagram/callback (F-03): public; the single-use state proves who started it.

It never connects anything itself (X-1, login CSRF): the browser that brings the code back may
not belong to the member who started the connect. The code is parked under a one-time nonce and
the signed-in Connections page finishes with POST …/social-accounts/instagram/complete, which
only the member who started it can do (services/connections.finish_instagram_connect)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from socialhood.api import ratelimit
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import deps_from
from socialhood.repositories import workspaces
from socialhood.services import connections as service
from socialhood.settings import Settings

router = APIRouter(prefix="/v1/oauth", tags=["oauth"])
log = get_logger(__name__)


def _web(settings: Settings) -> str:
    return (settings.web_base_url or "http://localhost:3000").rstrip("/")


@router.get(
    "/instagram/callback",
    operation_id="instagram_oauth_callback",
    dependencies=[ratelimit.OAUTH_CALLBACK],
    include_in_schema=False,
)
async def instagram_callback(
    request: Request,
    code: Annotated[str | None, Query(max_length=2048)] = None,
    state: Annotated[str | None, Query(max_length=128)] = None,
    error: Annotated[str | None, Query(max_length=128)] = None,
) -> RedirectResponse:
    settings: Settings = request.app.state.settings
    data = await service.pop_state(request.app.state.redis, state)
    if data is None:
        # Expired, reused or forged state: we cannot tell which workspace, so /app routes it.
        return RedirectResponse(f"{_web(settings)}/app?error=state_invalid", status_code=303)
    async with request.app.state.sessionmaker() as session:
        active = await workspaces.is_active(session, uuid.UUID(data["workspace_id"]))
    if not active:  # deleted or being deleted since the connect started (T9.6)
        return RedirectResponse(f"{_web(settings)}/app?error=state_invalid", status_code=303)
    target = f"{_web(settings)}/w/{data['slug']}/settings/connections"
    if error or not code:
        reason = "access_denied" if error in (None, "access_denied") else "connect_failed"
        return RedirectResponse(f"{target}?error={reason}", status_code=303)

    deps = deps_from(request.app.state.http, settings)
    nonce = await service.hold_instagram_code(request.app.state.redis, deps, data, code)
    return RedirectResponse(f"{target}?instagram={nonce}", status_code=303)
