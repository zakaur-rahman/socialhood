"""The WhatsApp catalogue API (GR-33, C-215): connect a Meta commerce catalogue, see how its feed
stands, and send product and product-list messages in a WhatsApp conversation.

The rules are in services/catalogue/wa_catalogue.py (the feed) and wa_send.py (the messages); the
feed itself is api/v1/catalogue_feed.py. Connecting needs ``integrations.manage`` and ``commerce``
on the plan (PD-8: Creator and Max, 402 ``entitlement_required`` on Free); renewing the link needs
``integrations.manage``; reading the status never needs the plan. Sending a
message needs ``reply`` (any member) and commerce. A request that names another workspace's
account, conversation or product is a 404 before any plan check.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, Response

from socialhood.api import ratelimit
from socialhood.auth.deps import (
    AnyMember,
    CanManageIntegrations,
    CanReply,
    Session,
    WorkspaceContext,
)
from socialhood.auth.permissions import Permission, has_permission
from socialhood.errors import ApiError
from socialhood.platforms.deps import deps_from
from socialhood.realtime import events as realtime
from socialhood.repositories import inbox
from socialhood.schemas.inbox import Message
from socialhood.schemas.wa_catalogue import (
    ProductMessageSend,
    WaCatalogueConnect,
    WaCatalogueStatus,
)
from socialhood.services import audit, sending
from socialhood.services.catalogue import wa_catalogue, wa_send
from socialhood.services.inbox_views import message_out

router = APIRouter(prefix="/v1/w/{wid}", tags=["catalogue"])


def _feed_base(request: Request, ctx: WorkspaceContext) -> str | None:
    """The API's public address, for the feed link: only for those who manage integrations."""
    if not has_permission(ctx.role, Permission.INTEGRATIONS_MANAGE):
        return None
    return request.app.state.settings.api_base_url or str(request.base_url)


@router.get("/integrations/whatsapp-catalogue", operation_id="get_whatsapp_catalogue")
async def get_whatsapp_catalogue(
    request: Request, ctx: AnyMember, session: Session
) -> WaCatalogueStatus:
    """The connection, how many items Meta got in its last fetch of the feed, which products
    can't be in it and why. Any member may read it (the inbox's "Send product" needs to know a
    catalogue is connected); only owners and admins get ``feed_url``."""
    return await wa_catalogue.status(session, feed_base=_feed_base(request, ctx))


@router.put("/integrations/whatsapp-catalogue", operation_id="connect_whatsapp_catalogue")
async def connect_whatsapp_catalogue(
    request: Request, body: WaCatalogueConnect, ctx: CanManageIntegrations, session: Session
) -> WaCatalogueStatus:
    """Save the WhatsApp number and the catalogue id, and make the feed link (C-215: Meta fetches
    the products from it; Meta isn't asked about the catalogue, it doesn't show it to the app).
    402 without commerce on the plan, 404 for an account that isn't this workspace's, 422 for a
    number that isn't WhatsApp or an id that isn't Meta's (digits)."""
    await wa_catalogue.connect(session, body, user_id=ctx.user.id)
    await audit.record(
        session, ctx, "whatsapp_catalogue.connected", "whatsapp_catalogue", catalog=body.catalog_id
    )
    out = await wa_catalogue.status(session, feed_base=_feed_base(request, ctx))
    await session.commit()
    return out


@router.post(
    "/integrations/whatsapp-catalogue/feed-link", operation_id="renew_whatsapp_catalogue_feed_link"
)
async def renew_whatsapp_catalogue_feed_link(
    request: Request, ctx: CanManageIntegrations, session: Session
) -> WaCatalogueStatus:
    """A new feed link; the old one stops working at once (paste the new one in Commerce
    Manager). 409 when no catalogue is connected."""
    await wa_catalogue.new_link(session)
    await audit.record(session, ctx, "whatsapp_catalogue.feed_link_renewed", "whatsapp_catalogue")
    out = await wa_catalogue.status(session, feed_base=_feed_base(request, ctx))
    await session.commit()
    return out


@router.delete(
    "/integrations/whatsapp-catalogue",
    status_code=204,
    operation_id="disconnect_whatsapp_catalogue",
)
async def disconnect_whatsapp_catalogue(ctx: CanManageIntegrations, session: Session) -> Response:
    """Forget the connection; its feed link stops working. The catalogue itself is left as it is
    in Meta."""
    await wa_catalogue.disconnect(session)
    await audit.record(session, ctx, "whatsapp_catalogue.disconnected", "whatsapp_catalogue")
    await session.commit()
    return Response(status_code=204)


@router.post(
    "/conversations/{conversation_id}/product-message",
    status_code=202,
    operation_id="send_product_message",
    dependencies=[ratelimit.SENDS],
)
async def send_product_message(
    request: Request,
    conversation_id: uuid.UUID,
    body: ProductMessageSend,
    ctx: CanReply,
    session: Session,
) -> Message:
    """Send a WhatsApp product message (one catalogue item) or product list (up to 30 items in up
    to 10 sections) in the conversation. Every item must have been in Meta's last fetch of the
    feed. 402
    without commerce on the plan, 409 when no catalogue is connected, it belongs to another number
    or the reply window is closed, 422 for an item that isn't ready or a list without a header."""
    conv = await inbox.get_conversation(session, conversation_id)
    if conv is None:
        raise ApiError("not_found")
    msg = await wa_send.send(
        session,
        conv,
        body,
        user_id=ctx.user.id,
        deps=deps_from(request.app.state.http, request.app.state.settings),
    )
    await audit.record(
        session,
        ctx,
        "message.sent",
        "message",
        msg.id,
        conversation_id=conversation_id,
        kind=body.kind,
    )
    await realtime.commit_and_publish(session, request.app.state.redis)
    return message_out(msg, sent_by_name=await sending.sender_name(session, msg.sent_by_user_id))
