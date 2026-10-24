"""Website chat widget settings (GR-28). Owners and admins read and change them.

``GET`` makes the workspace's widget the first time it is opened (one web account and its settings,
with a new public id and no allowed domains), so a read from an owner or admin can write.
``PUT`` changes the fields it is given: 422 names each bad domain, and turning "Powered by Social
Hood" off on Free is 402 entitlement_required (PD-7). The AI mode is the account's, changed with
the other accounts' (PATCH social-accounts).
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from socialhood.auth.deps import Admin, Session
from socialhood.schemas.widget import WidgetSettingsOut, WidgetSettingsUpdate
from socialhood.services.widget import settings as service

# TODO(GR-19): move both routes to require_permission("widget.manage") when the permission matrix
# lands (the member's role check here is Admin: owners and admins).
router = APIRouter(prefix="/v1/w/{wid}", tags=["widget"])


async def _out(request: Request, session: Session) -> WidgetSettingsOut:
    acct, row = await service.ensure(session)
    return await service.out(session, acct, row, request.app.state.settings, str(request.base_url))


@router.get("/widget", operation_id="get_widget_settings")
async def get_widget_settings(request: Request, ctx: Admin, session: Session) -> WidgetSettingsOut:
    """The widget's settings and its embed code."""
    await service.ensure(session)
    await session.commit()
    return await _out(request, session)


@router.put("/widget", operation_id="update_widget_settings")
async def update_widget_settings(
    request: Request, body: WidgetSettingsUpdate, ctx: Admin, session: Session
) -> WidgetSettingsOut:
    """Change the fields sent; the others stay as they are."""
    _, row = await service.ensure(session)
    await service.update(session, row, body)
    await session.commit()
    return await _out(request, session)
