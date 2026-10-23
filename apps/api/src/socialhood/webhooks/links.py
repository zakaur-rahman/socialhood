"""GET /l/{code}: the tracked link redirect (GR-15), public and served by the API.

The code is an opaque token (services/automations/links.py). The link is found across
workspaces (the tenant bypass, this one lookup), then the click is stored inside the link's own
workspace. 302 to the stored address when it is a plain http or https link; 404 ``not_found``
otherwise (an unknown code, or an address that is not safe to send anyone to). Previews and
crawlers get the redirect too but are not counted. Rate limited per IP like the other public
routes. Not in the OpenAPI schema: it is a link for people, not part of the API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Path, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from socialhood.api import ratelimit
from socialhood.auth.deps import Session
from socialhood.db.tenancy import tenant_bypass_scope, workspace_scope
from socialhood.errors import ApiError
from socialhood.models.automations import TrackedLink
from socialhood.observability.logging import get_logger
from socialhood.services.automations import links

router = APIRouter(include_in_schema=False)
log = get_logger(__name__)

Code = Annotated[str, Path(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
REDIRECT_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex",
}


@router.api_route("/l/{code}", methods=["GET", "HEAD"], dependencies=[ratelimit.PUBLIC])
async def follow_link(code: Code, request: Request, session: Session) -> RedirectResponse:
    with tenant_bypass_scope():
        link = await session.scalar(select(TrackedLink).where(TrackedLink.code == code))
    if link is None:
        raise ApiError("not_found")
    target = links.safe_target(link.url)
    if target is None:
        log.warning("tracked_link_unsafe", link_id=str(link.id))
        raise ApiError("not_found")
    person = not links.is_bot(request.headers.get("user-agent"), request.method)
    if person:
        with workspace_scope(link.workspace_id):
            counted = await links.count_click(session, link, now=datetime.now(UTC))
            await session.commit()
        log.info("tracked_link_clicked", link_id=str(link.id), counted=counted)
    else:
        log.info("tracked_link_preview", link_id=str(link.id))
    return RedirectResponse(target, status_code=302, headers=REDIRECT_HEADERS)
