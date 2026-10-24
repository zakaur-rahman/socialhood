"""Orders and payment requests API (GR-32).

The rules are in services/orders/: orders.py (making an order from the catalogue, asking for
payment, paid, cancelled), payments.py (the workspace's own Razorpay keys and UPI address) and
webhook.py (what Razorpay reports). Any member who can reply may make an order in a conversation,
send its payment request and mark it paid or cancel it; the payment settings need
``integrations.manage``. Reading is never refused; making, paying and connecting need ``commerce``
on the plan (PD-8: Pro and Max, 402 ``entitlement_required`` on Free).

A request that names another workspace's conversation, product or order is a 404 before any plan
check, so nothing reveals what exists.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response

from socialhood.auth.deps import AnyMember, CanManageIntegrations, CanReply, Session
from socialhood.platforms.deps import deps_from
from socialhood.razorpay.client import RazorpayClient
from socialhood.razorpay.registry import get_razorpay
from socialhood.realtime import events as realtime
from socialhood.repositories import inbox
from socialhood.schemas.orders import (
    MarkPaid,
    OrderCreate,
    OrderList,
    OrderOut,
    PaymentRequest,
    PaymentSettings,
    RazorpayConnect,
    UpiSave,
)
from socialhood.security.crypto import TokenCipher, cipher_for
from socialhood.services import audit, sending
from socialhood.services.orders import orders, payments

router = APIRouter(prefix="/v1/w/{wid}", tags=["orders"])

OrderStatusFilter = Literal["draft", "awaiting_payment", "paid", "cancelled", "expired"]


def _cipher(request: Request) -> TokenCipher:
    return cipher_for(tuple(request.app.state.settings.token_encryption_keys))


def _client(request: Request) -> RazorpayClient:
    return get_razorpay(request.app.state.http, request.app.state.settings)


# ---------------------------------------------------------------- orders


@router.get("/orders", operation_id="list_orders")
async def list_orders(
    ctx: AnyMember,
    session: Session,
    status: Annotated[OrderStatusFilter | None, Query()] = None,
    contact_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> OrderList:
    """Newest first, with whether the plan and the payment settings are ready."""
    return await orders.list_orders(
        session, status=status, contact_id=contact_id, limit=limit, offset=offset
    )


@router.post("/orders", status_code=201, operation_id="create_order")
async def create_order(body: OrderCreate, ctx: CanReply, session: Session) -> OrderOut:
    """An order for the conversation's customer, priced from the catalogue now (the request
    never carries a price). 402 without commerce on the plan or over the month's orders, 404
    for a conversation or product that isn't this workspace's, 422 on the lines (a variant
    needed, a product switched off or without a price, more than is in stock)."""
    order = await orders.create(session, body, user_id=ctx.user.id)
    out = await orders.view(session, order)
    await audit.record(
        session, ctx, "order.created", "order", order.id, number=order.number, source="inbox"
    )
    await session.commit()
    return out


@router.get("/orders/{order_id}", operation_id="get_order")
async def get_order(order_id: uuid.UUID, ctx: AnyMember, session: Session) -> OrderOut:
    return await orders.view(session, await orders.get(session, order_id))


@router.post("/orders/{order_id}/payment-request", operation_id="request_order_payment")
async def request_payment(
    request: Request,
    order_id: uuid.UUID,
    body: PaymentRequest,
    ctx: CanReply,
    session: Session,
) -> OrderOut:
    """Make a Razorpay payment link or a UPI request for the order and, unless ``send`` is false,
    send it as a message on the order's conversation. 409 when the method isn't set up ("Razorpay
    isn't set up for this workspace"), 409 ``reply_window_closed`` when the message can't go,
    422 for an order that is paid or cancelled."""
    order = await orders.get(session, order_id, lock=True)
    text = await orders.request_payment(
        session, order, body.method, client=_client(request), cipher=_cipher(request)
    )
    if body.send and order.conversation_id is not None:
        conv = await inbox.get_conversation(session, order.conversation_id)
        if conv is not None:
            await sending.queue_outbound(
                session,
                conv,
                source="human",
                client_id=uuid.uuid4(),
                text=text,
                sent_by_user_id=ctx.user.id,
                deps=deps_from(request.app.state.http, request.app.state.settings),
            )
    await audit.record(
        session,
        ctx,
        "order.payment_requested",
        "order",
        order.id,
        method=body.method,
        sent=body.send,
    )
    out = await orders.view(session, order)
    await realtime.commit_and_publish(session, request.app.state.redis)
    return out


@router.post("/orders/{order_id}/mark-paid", operation_id="mark_order_paid")
async def mark_order_paid(
    order_id: uuid.UUID, body: MarkPaid, ctx: CanReply, session: Session
) -> OrderOut:
    """A member says the order was paid: for UPI, which has no webhook. Who and when are kept on
    the order and in the audit trail. 422 when it is already paid or cancelled."""
    order = await orders.get(session, order_id, lock=True)
    await orders.mark_paid(session, order, reference=body.reference, user_id=ctx.user.id)
    await audit.record(
        session,
        ctx,
        "order.marked_paid",
        "order",
        order.id,
        number=order.number,
        method=order.payment_method,
    )
    out = await orders.view(session, order)
    await session.commit()
    return out


@router.post("/orders/{order_id}/cancel", operation_id="cancel_order")
async def cancel_order(
    request: Request, order_id: uuid.UUID, ctx: CanReply, session: Session
) -> OrderOut:
    """Cancel an order that isn't paid, and its Razorpay link. 422 for a paid order."""
    order = await orders.get(session, order_id, lock=True)
    await orders.cancel(session, order, client=_client(request), cipher=_cipher(request))
    await audit.record(session, ctx, "order.cancelled", "order", order.id, number=order.number)
    out = await orders.view(session, order)
    await session.commit()
    return out


# ---------------------------------------------------------------- payment settings


@router.get("/integrations/payments", operation_id="get_payment_settings")
async def get_payment_settings(
    request: Request, ctx: CanManageIntegrations, session: Session
) -> PaymentSettings:
    """Whether Razorpay and/or UPI are set up, and the webhook address to add in Razorpay. The
    keys and secrets are never returned."""
    return await payments.status(session, api_base_url=request.app.state.settings.api_base_url)


@router.put("/integrations/payments/razorpay", operation_id="connect_razorpay")
async def connect_razorpay(
    request: Request, body: RazorpayConnect, ctx: CanManageIntegrations, session: Session
) -> PaymentSettings:
    """Check the keys with Razorpay and save them (encrypted). 402 without commerce on the plan,
    422 when Razorpay refuses the keys, 502 when it doesn't answer."""
    await payments.connect_razorpay(
        session, _client(request), _cipher(request), body, user_id=ctx.user.id
    )
    await audit.record(session, ctx, "payments.razorpay_connected", "payments")
    out = await payments.status(session, api_base_url=request.app.state.settings.api_base_url)
    await session.commit()
    return out


@router.delete(
    "/integrations/payments/razorpay", status_code=204, operation_id="disconnect_razorpay"
)
async def disconnect_razorpay(ctx: CanManageIntegrations, session: Session) -> Response:
    await payments.disconnect_razorpay(session)
    await audit.record(session, ctx, "payments.razorpay_disconnected", "payments")
    await session.commit()
    return Response(status_code=204)


@router.put("/integrations/payments/upi", operation_id="save_upi")
async def save_upi(
    request: Request, body: UpiSave, ctx: CanManageIntegrations, session: Session
) -> PaymentSettings:
    """The UPI address customers pay (a plain UPI request has no webhook: such an order is marked
    paid by hand)."""
    await payments.save_upi(session, body, user_id=ctx.user.id)
    await audit.record(session, ctx, "payments.upi_saved", "payments")
    out = await payments.status(session, api_base_url=request.app.state.settings.api_base_url)
    await session.commit()
    return out


@router.delete("/integrations/payments/upi", status_code=204, operation_id="remove_upi")
async def remove_upi(ctx: CanManageIntegrations, session: Session) -> Response:
    await payments.remove_upi(session)
    await audit.record(session, ctx, "payments.upi_removed", "payments")
    await session.commit()
    return Response(status_code=204)
