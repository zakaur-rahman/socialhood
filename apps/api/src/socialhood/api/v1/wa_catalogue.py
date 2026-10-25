"""The WhatsApp catalogue API (GR-33): connect a Meta commerce catalogue, see how its sync is
going, and send product and product-list messages in a WhatsApp conversation.

The rules are in services/catalogue/wa_catalogue.py (the sync) and wa_send.py (the messages).
Connecting and syncing need ``integrations.manage`` and ``commerce`` on the plan (PD-8: Pro and
Max, 402 ``entitlement_required`` on Free); reading the status never needs the plan. Sending a
message needs ``reply`` (any member) and commerce. A request that names another workspace's
account, conversation or product is a 404 before any plan check.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from socialhood.api import ratelimit
from socialhood.auth.deps import AnyMember, CanManageIntegrations, CanReply, Session
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
from socialhood.security.crypto import cipher_for
from socialhood.services import audit, sending
from socialhood.services.catalogue import wa_catalogue, wa_send
from socialhood.services.inbox_views import message_out

router = APIRouter(prefix="/v1/w/{wid}", tags=["catalogue"])


@router.get("/integrations/whatsapp-catalogue", operation_id="get_whatsapp_catalogue")
async def get_whatsapp_catalogue(ctx: AnyMember, session: Session) -> WaCatalogueStatus:
    """The connection, how many items Meta has, which ones it refused and why. Any member may read
    it (the inbox's "Send product" needs to know a catalogue is connected)."""
    return await wa_catalogue.status(session)


@router.put("/integrations/whatsapp-catalogue", operation_id="connect_whatsapp_catalogue")
async def connect_whatsapp_catalogue(
    request: Request, body: WaCatalogueConnect, ctx: CanManageIntegrations, session: Session
) -> WaCatalogueStatus:
    """Check Meta shows the catalogue to the number's business account, save the connection and
    start the first sync. 402 without commerce on the plan, 404 for an account that isn't this
    workspace's, 422 for a number that isn't WhatsApp, 409 for a catalogue Meta won't show (not
    found, or not connected to the number's business account), 502 when Meta doesn't answer."""
    settings = request.app.state.settings
    await wa_catalogue.connect(
        session,
        request.app.state.http,
        settings,
        cipher_for(tuple(settings.token_encryption_keys)),
        body,
        user_id=ctx.user.id,
    )
    await wa_catalogue.request_sync(session, datetime.now(UTC))
    await audit.record(
        session, ctx, "whatsapp_catalogue.connected", "whatsapp_catalogue", catalog=body.catalog_id
    )
    out = await wa_catalogue.status(session)
    await session.commit()
    await wa_catalogue.enqueue_sync(ctx.workspace_id)
    return out


@router.post(
    "/integrations/whatsapp-catalogue/sync", status_code=202, operation_id="sync_whatsapp_catalogue"
)
async def sync_whatsapp_catalogue(
    ctx: CanManageIntegrations, session: Session
) -> WaCatalogueStatus:
    """Send what changed now. While a sync runs this changes nothing."""
    queued = await wa_catalogue.request_sync(session, datetime.now(UTC))
    out = await wa_catalogue.status(session)
    await session.commit()
    if queued:
        await wa_catalogue.enqueue_sync(ctx.workspace_id)
    return out


@router.delete(
    "/integrations/whatsapp-catalogue",
    status_code=204,
    operation_id="disconnect_whatsapp_catalogue",
)
async def disconnect_whatsapp_catalogue(ctx: CanManageIntegrations, session: Session) -> Response:
    """Forget the connection. The catalogue itself is left as it is in Meta."""
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
    to 10 sections) in the conversation. Every item must be in the catalogue as last synced. 402
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
