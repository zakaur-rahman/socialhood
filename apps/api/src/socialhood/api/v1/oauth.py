"""GET /v1/oauth/instagram/callback (F-03): public; the single-use state proves who started it."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from socialhood.billing.plans import current_plan
from socialhood.db.tenancy import workspace_scope
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import deps_from
from socialhood.services import connections as service
from socialhood.settings import Settings

router = APIRouter(prefix="/v1/oauth", tags=["oauth"])
log = get_logger(__name__)


def _web(settings: Settings) -> str:
    return (settings.web_base_url or "http://localhost:3000").rstrip("/")


@router.get("/instagram/callback", operation_id="instagram_oauth_callback", include_in_schema=False)
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
    target = f"{_web(settings)}/w/{data['slug']}/settings/connections"
    if error or not code:
        reason = "access_denied" if error in (None, "access_denied") else "connect_failed"
        return RedirectResponse(f"{target}?error={reason}", status_code=303)

    deps = deps_from(request.app.state.http, settings)
    with workspace_scope(uuid.UUID(data["workspace_id"])):
        async with request.app.state.sessionmaker() as session:
            outcome = await service.complete_instagram_connect(
                session,
                deps,
                code=code,
                user_id=uuid.UUID(data["user_id"]),
                plan=await current_plan(session),
            )
    if outcome.error:
        extra = f"&limit={outcome.limit}" if outcome.limit is not None else ""
        return RedirectResponse(f"{target}?error={outcome.error}{extra}", status_code=303)
    return RedirectResponse(f"{target}?connected=instagram", status_code=303)
