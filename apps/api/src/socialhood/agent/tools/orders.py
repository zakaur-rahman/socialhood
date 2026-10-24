"""The orders tool (GR-32; agent-architecture.html §5): list_orders, for "which orders are waiting
for payment?", "how much did we sell this week?" and "what did Priya order?". Owners and admins,
like the Orders page (``min_role`` admin).

Visuals (GR-38, VIS-09): the first orders as a ``table`` (admins only, like the tool).

R1 (read): totals, statuses and lines come from the orders as stored, in each order's currency
(services/orders), and the customer is named by their handle or name. Delivery addresses and
payment references are never returned. Nothing is changed; writes through the action gateway are
R2.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from socialhood.agent import visuals
from socialhood.agent.registry import ToolContext, ToolResult
from socialhood.agent.tools.common import clip, limit_field, ref, tool, visual, when
from socialhood.models.identity import Role
from socialhood.models.inbox import Contact
from socialhood.models.orders import Order, OrderStatus
from socialhood.schemas.agent import TableVisual, Visual
from socialhood.services.catalogue import money
from socialhood.services.orders import orders as order_service

MAX_ORDERS = 25
MAX_DAYS = 365


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListOrdersInput(_Input):
    status: Literal["draft", "awaiting_payment", "paid", "cancelled", "expired"] | None = Field(
        default=None, description="Only orders in this state; leave out for all."
    )
    customer: str | None = Field(
        default=None,
        max_length=100,
        description="Part of the customer's name or @handle.",
    )
    days: int = Field(default=30, ge=1, le=MAX_DAYS, description="Orders made in the last N days.")
    limit: int = limit_field(default=10, maximum=MAX_ORDERS)


class OrderLine(BaseModel):
    id: uuid.UUID
    number: int
    status: str
    total: str  # "INR 1598.00"
    customer: str | None = None
    items: list[str]  # "2 x Cotton kurta - Blue / M"
    payment_method: str | None = None
    created_at: datetime
    paid_at: datetime | None = None


class OrdersTotals(BaseModel):
    count: int  # all the orders that match, not only those listed
    paid_count: int
    paid_by_currency: dict[str, str]  # {"INR": "4793.00"}: paid orders only


class ListOrdersResult(ToolResult):
    items: list[OrderLine]
    totals: OrdersTotals
    visual: Visual | None = None  # GR-38 (VIS-09): the first orders as a table


def _orders_table(ctx: ToolContext, items: list[OrderLine], total: int) -> TableVisual:
    """Order number, customer, status, total (money text, right-aligned) and date."""
    return visuals.table(
        title="Orders",
        columns=[
            visuals.Column("order", "Order"),
            visuals.Column("customer", "Customer"),
            visuals.Column("status", "Status"),
            visuals.Column("total", "Total", figures=True),
            visuals.Column("date", "Date"),
        ],
        rows=[
            [
                f"#{i.number}",
                i.customer,
                i.status.replace("_", " ").capitalize(),
                i.total,
                when(ctx, i.created_at),
            ]
            for i in items
        ],
        total=total,
        more_route="orders",
    )


@tool(
    name="list_orders",
    label="Looking at your orders",
    description=(
        "Orders made in conversations: number, status (draft, awaiting payment, paid, cancelled, "
        "expired), total, customer and lines, with how many are paid and how much was paid in "
        "the period. For 'which orders are unpaid?' or 'what did we sell this week?'."
    ),
    input_model=ListOrdersInput,
    result_model=ListOrdersResult,
    min_role=Role.ADMIN,
)
async def list_orders(ctx: ToolContext, args: ListOrdersInput) -> ListOrdersResult:
    since = datetime.now(UTC) - timedelta(days=args.days)
    where = [Order.created_at >= since]
    if args.status:
        where.append(Order.status == args.status)
    if args.customer:
        word = args.customer.strip().lstrip("@").casefold()
        where.append(
            Order.contact_id.in_(
                select(Contact.id).where(
                    func.lower(func.coalesce(Contact.display_name, "")).contains(
                        word, autoescape=True
                    )
                    | func.lower(func.coalesce(Contact.username, "")).contains(
                        word, autoescape=True
                    )
                )
            )
        )
    count = int(
        await ctx.session.scalar(select(func.count()).select_from(Order).where(*where)) or 0
    )
    rows = (
        await ctx.session.scalars(
            select(Order)
            .where(*where)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(args.limit)
        )
    ).all()
    views = await order_service.views(ctx.session, list(rows))
    paid = (
        await ctx.session.execute(
            select(Order.currency, func.count(), func.sum(Order.total_minor))
            .where(*where, Order.status == OrderStatus.PAID)
            .group_by(Order.currency)
        )
    ).all()
    items = [
        OrderLine(
            id=v.id,
            number=v.number,
            status=v.status,
            total=money.label(v.total_minor, v.currency),
            customer=(f"@{v.contact.username}" if v.contact.username else v.contact.display_name),
            items=[
                f"{i.quantity} x {i.name}" + (f" - {i.variant_title}" if i.variant_title else "")
                for i in v.items
            ],
            payment_method=v.payment_method,
            created_at=v.created_at,
            paid_at=v.paid_at,
        )
        for v in views
    ]
    totals = OrdersTotals(
        count=count,
        paid_count=sum(int(n) for _, n, _ in paid),
        paid_by_currency={cur: money.plain(int(total or 0), cur) for cur, _, total in paid},
    )
    caveats = ["Only part of the matching orders is listed."] if count > len(items) else []
    return ListOrdersResult(
        summary=clip(
            f"{count} orders in the last {args.days} days"
            + (f", {totals.paid_count} paid" if totals.paid_count else ""),
            300,
        )
        or "Looked at orders",
        items=items,
        totals=totals,
        visual=visual(ctx, "table", lambda: _orders_table(ctx, items, count)) if items else None,
        refs=[ref("order", item.id, f"Order #{item.number}") for item in items],
        caveats=caveats,
    )
