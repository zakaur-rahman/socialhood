"""The flow step "request payment" (GR-32 follow-up, C-125).

A flow can ask the customer to pay: the step makes an order and returns the payment message
(a Razorpay link or a UPI request) for the engine to send.

- ``source = items``: the order is made from the step's chosen products and variants when the step
  runs, priced from the catalogue then (a request never carries a price), with the same checks as
  an order a member makes: a product that is switched off, has no price or is out of stock fails
  the step with a plain reason. Source ``flow``; no member made it.
- ``source = draft``: the conversation's latest order that isn't paid yet (a member's draft, the
  customer's WhatsApp cart, an order awaiting payment or only partly paid) is the one asked for;
  with none, the step fails with a plain reason.
- The plan gate and the method's setup are the product step's and the order API's: commerce on
  the plan (PD-8), the monthly cap for a new order, and Razorpay keys or a UPI address saved.
  Activation checks the same ahead of time (services/automations/flows.py); these are the
  run-time checks, because a plan or a setting can change after a flow is switched on.
- Nothing here commits and a refused Razorpay key is not saved to the payment card from inside a
  run (the run commits as a whole).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import allows
from socialhood.billing.plans import current_plan
from socialhood.errors import ApiError
from socialhood.models.inbox import Conversation
from socialhood.models.orders import Order, OrderSource, OrderStatus
from socialhood.platforms.deps import PlatformDeps
from socialhood.razorpay.registry import get_razorpay
from socialhood.schemas.flows import PaymentStep
from socialhood.services import audit
from socialhood.services.automations import actions
from socialhood.services.orders import orders

OPEN = (OrderStatus.DRAFT, OrderStatus.AWAITING_PAYMENT, OrderStatus.PARTIALLY_PAID)
NO_ORDER = "There is no unpaid order in this conversation to ask for."
NO_PLAN = "Orders are part of Pro."


class Failed(Exception):
    """The step can't run; ``code`` and ``reason`` go to the run log."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _failed(error: ApiError) -> Failed:
    return Failed(error.code, actions.api_error_reason(error))


async def _latest_open(session: AsyncSession, conv: Conversation) -> Order | None:
    return (
        await session.scalars(
            select(Order)
            .where(Order.conversation_id == conv.id, Order.status.in_(OPEN))
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(1)
            .with_for_update()
        )
    ).first()


async def request(
    session: AsyncSession,
    deps: PlatformDeps,
    conv: Conversation,
    step: PaymentStep,
    *,
    automation_name: str,
    now: datetime,
) -> tuple[Order, str]:
    """The order and the message to send. Raises ``Failed``."""
    if not allows(await current_plan(session), orders.KEY):
        raise Failed("entitlement_required", NO_PLAN)
    label = f"Automation: {automation_name}"
    try:
        if step.source == "draft":
            order = await _latest_open(session, conv)
            if order is None:
                raise Failed("no_order", NO_ORDER)
        else:
            lines = await orders.resolve_lines(
                session, [(i.product_id, i.variant_id, i.quantity) for i in step.items]
            )
            await orders.check_month(session, now)
            order, _ = await orders.add(
                session,
                conv=conv,
                lines=lines,
                address=None,
                note=None,
                source=OrderSource.FLOW,
                user_id=None,
                now=now,
            )
            audit.record_system(
                session,
                label,
                "order.created",
                "order",
                order.id,
                number=order.number,
                source="flow",
            )
        text = await orders.request_payment(
            session,
            order,
            step.method,
            client=get_razorpay(deps.http, deps.settings),
            cipher=deps.cipher,
            remember_refused_keys=False,
            now=now,
        )
    except ApiError as error:
        raise _failed(error) from error
    audit.record_system(
        session,
        label,
        "order.payment_requested",
        "order",
        order.id,
        number=order.number,
        method=step.method,
        sent=True,
    )
    intro = step.intro.strip()
    return order, f"{intro}\n\n{text}" if intro else text
