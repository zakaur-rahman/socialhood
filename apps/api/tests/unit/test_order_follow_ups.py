"""GR-32 follow-ups, the parts that need no database: how a refund is split over payments, the
default words of a status message, the payment message of a part-paid order, the refund call to
Razorpay (the HTTP client and the sandbox), the "request payment" flow step's checks, and the
request shapes."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from socialhood.models.orders import (
    Order,
    OrderItem,
    OrderPayment,
    OrderRefund,
    OrderStatus,
    RefundStatus,
)
from socialhood.razorpay.client import WEBHOOK_EVENTS, Credentials
from socialhood.razorpay.fake import FakeRazorpay
from socialhood.razorpay.http import HttpRazorpayClient
from socialhood.schemas.flows import FlowDefinition, PaymentStep
from socialhood.schemas.orders import MarkPaid, NoticeIn, OrderEdit, RefundCreate
from socialhood.services import contact_timeline
from socialhood.services.automations import flows
from socialhood.services.orders import ledger, notices, orders

NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)
CREDS = Credentials("rzp_test_abc12345", "secret-123")


def order(**values: Any) -> Order:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "number": 12,
        "currency": "INR",
        "total_minor": 159800,
        "status": "draft",
        "amount_paid_minor": 0,
        "amount_refunded_minor": 0,
        "accept_partial": False,
    }
    return Order(**{**base, **values})


def payment(amount: int, minutes: int, method: str = "razorpay") -> OrderPayment:
    return OrderPayment(
        id=uuid.uuid4(),
        amount_minor=amount,
        method=method,
        paid_at=NOW + timedelta(minutes=minutes),
        created_at=NOW + timedelta(minutes=minutes),
    )


def refund(of: OrderPayment, amount: int, status: str = "processed") -> OrderRefund:
    return OrderRefund(payment_id=of.id, amount_minor=amount, status=status)


# ---------------------------------------------------------------- what is left


def test_what_is_left_to_pay_and_to_refund() -> None:
    row = order(amount_paid_minor=50000, amount_refunded_minor=10000)
    assert ledger.remaining(row) == 109800
    on_its_way = [OrderRefund(amount_minor=15000, status=RefundStatus.PENDING)]
    done = [OrderRefund(amount_minor=10000, status=RefundStatus.PROCESSED)]
    assert ledger.refundable(row, done) == 40000  # already counted in the order's total
    assert ledger.refundable(row, on_its_way) == 25000
    assert ledger.remaining(order(total_minor=100, amount_paid_minor=100)) == 0


# ---------------------------------------------------------------- splitting a refund


def test_a_refund_takes_the_newest_payment_first() -> None:
    old, new = payment(100000, 0), payment(59800, 10)
    parts = ledger._allocate([old, new], [], 70000)
    assert [(p.amount_minor, n) for p, n in parts] == [(59800, 59800), (100000, 10200)]


def test_what_was_refunded_before_is_not_available_again_but_a_failed_refund_is() -> None:
    first = payment(100000, 0)
    taken = [refund(first, 60000)]
    assert [(n) for _, n in ledger._allocate([first], taken, 100000)] == [40000]
    failed = [refund(first, 60000, "failed")]
    assert [(n) for _, n in ledger._allocate([first], failed, 100000)] == [100000]
    pending = [refund(first, 60000, "pending")]
    assert [(n) for _, n in ledger._allocate([first], pending, 100000)] == [40000]
    assert ledger._allocate([first], [refund(first, 100000)], 1) == []


# ---------------------------------------------------------------- the words


def test_the_default_status_messages() -> None:
    row = order(amount_paid_minor=50000, fulfilment_note="Delhivery 123")
    assert notices.default_text(row, "paid") == (
        "Thanks, we've got your payment for order #12 (INR 1598.00)."
    )
    assert notices.default_text(row, "partially_paid", amount_minor=50000) == (
        "We've received INR 500.00 for order #12. INR 1098.00 is still to pay."
    )
    assert notices.default_text(row, "fulfilled") == (
        "Good news: order #12 is on its way. Delhivery 123"
    )
    assert notices.default_text(row, "cancelled") == "Order #12 has been cancelled."
    assert notices.default_text(row, "refunded", amount_minor=20000) == (
        "We've refunded INR 200.00 for order #12. It can take a few days to show in your account."
    )
    assert notices.default_text(order(), "fulfilled") == "Good news: order #12 is on its way."


def test_a_template_has_room_for_four_details() -> None:
    from socialhood.models.inbox import Contact

    row = order(status="paid")
    who = Contact(display_name="Asha Rao")
    assert notices._variables(row, who, "paid") == ["Asha", "#12", "INR 1598.00", "paid"]
    assert notices._variables(row, None, "paid")[0] == "there"
    assert notices.MAX_VARIABLES == 4


def test_a_part_paid_order_says_what_is_left_in_its_payment_message() -> None:
    item = OrderItem(
        name="Cotton kurta", quantity=2, unit_price_minor=79900, line_total_minor=159800
    )
    fresh = orders.payment_text(order(), [item], pay_url="https://rzp.test/pay/1", vpa=None)
    assert "Paid so far" not in fresh
    part = orders.payment_text(
        order(amount_paid_minor=50000), [item], pay_url="https://rzp.test/pay/1", vpa=None
    )
    assert "Paid so far: INR 500.00\nLeft to pay: INR 1098.00" in part
    assert part.endswith("Pay here: https://rzp.test/pay/1")


def test_the_upi_link_is_for_what_is_left() -> None:
    link = orders.upi_link("shop@okbank", "Maple", order(amount_paid_minor=50000))
    assert "am=1098.00" in link
    assert "am=1598.00" in orders.upi_link("shop@okbank", "Maple", order())
    assert "am=5.00" in orders.upi_link("shop@okbank", "Maple", order(), 500)


def test_every_status_has_words_on_the_timeline_and_in_messages() -> None:
    for status in OrderStatus:
        assert status in contact_timeline.ORDER_VERB
        assert status in orders.STATUS_WORDS


# ---------------------------------------------------------------- Razorpay


def client_with(handler: Any) -> HttpRazorpayClient:
    return HttpRazorpayClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_a_refund_is_posted_against_the_payment() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "rfnd_1", "status": "processed"})

    done = await client_with(handler).refund_payment(
        CREDS, "pay_9", amount_minor=50000, reason="Damaged", receipt="order12"
    )
    assert (done.id, done.status) == ("rfnd_1", "processed")
    [request] = seen
    assert request.url == "https://api.razorpay.com/v1/payments/pay_9/refund"
    body = json.loads(request.content)
    assert (body["amount"], body["speed"], body["receipt"]) == (50000, "normal", "order12")
    assert body["notes"] == {"reason": "Damaged"}


@pytest.mark.parametrize(
    ("answer", "state"),
    [
        ("processed", "processed"),
        ("pending", "pending"),
        ("failed", "failed"),
        ("created", "pending"),
    ],
)
async def test_a_refunds_status_is_read_from_razorpay(answer: str, state: str) -> None:
    client = client_with(lambda r: httpx.Response(200, json={"id": "rfnd_1", "status": answer}))
    done = await client.refund_payment(CREDS, "pay_9", amount_minor=1, reason="x", receipt="r")
    assert done.status == state


async def test_an_answer_without_a_refund_id_is_refused() -> None:
    from socialhood.razorpay.client import RazorpayError

    client = client_with(lambda r: httpx.Response(200, json={"status": "processed"}))
    with pytest.raises(RazorpayError) as refused:
        await client.refund_payment(CREDS, "pay_9", amount_minor=1, reason="x", receipt="r")
    assert refused.value.kind == "rejected"


async def test_a_link_that_takes_parts_is_created_with_accept_partial() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "plink_1", "short_url": "https://rzp.io/i/abc"})

    await client_with(handler).create_payment_link(
        CREDS,
        amount_minor=100,
        currency="INR",
        reference_id="o1",
        description="Order",
        customer_name=None,
        customer_phone=None,
        expire_by=1_800_000_000,
        accept_partial=True,
    )
    assert json.loads(seen[0].content)["accept_partial"] is True


async def test_the_sandbox_refunds_and_can_leave_one_pending() -> None:
    fake = FakeRazorpay()
    first = await fake.refund_payment(CREDS, "pay_1", amount_minor=500, reason="x", receipt="r")
    assert (first.id, first.status) == ("rfnd_fake_1", "processed")
    fake.refund_status = "pending"
    second = await fake.refund_payment(CREDS, "pay_1", amount_minor=300, reason="x", receipt="r")
    assert (second.id, second.status) == ("rfnd_fake_2", "pending")
    assert fake.calls[0][1]["amount_minor"] == 500


def test_the_card_lists_the_refund_events_to_turn_on() -> None:
    assert {"refund.processed", "refund.failed", "payment_link.partially_paid"} <= set(
        WEBHOOK_EVENTS
    )


# ---------------------------------------------------------------- request shapes


def test_the_requests_check_their_fields() -> None:
    assert RefundCreate(reason="Damaged").amount_minor is None
    with pytest.raises(ValidationError):
        RefundCreate(reason="")
    with pytest.raises(ValidationError):
        RefundCreate(reason="x", amount_minor=0)
    assert MarkPaid().amount_minor is None
    with pytest.raises(ValidationError):
        MarkPaid(amount_minor=0)
    with pytest.raises(ValidationError):
        NoticeIn(template_name="order_shipped")  # a template needs its language too
    assert NoticeIn(template_name="order_shipped", template_language="en").message is None
    assert OrderEdit().items is None  # nothing given, nothing changed
    with pytest.raises(ValidationError):
        OrderEdit(items=[])


# ---------------------------------------------------------------- the flow step

PRODUCT = uuid.uuid4()
VARIANT = uuid.uuid4()


def pay_flow(**step: Any) -> FlowDefinition:
    return FlowDefinition.model_validate(
        {"start": "p", "steps": [{"type": "payment", "id": "p", **step}]}
    )


def context(**kw: Any) -> flows.Context:
    return flows.Context(trigger="dm_keyword", disclosure=None, **kw)


def errors(flow: FlowDefinition, ctx: flows.Context) -> dict[str, str]:
    return {e.field: e.message for e in flows.activation_errors(flow, ctx)}


def test_a_payment_step_parses_and_leads_on() -> None:
    flow = pay_flow(
        items=[{"product_id": str(PRODUCT), "quantity": 2}], intro="Order below", next=None
    )
    [step] = flow.steps
    assert isinstance(step, PaymentStep)
    assert (step.source, step.method, step.items[0].quantity) == ("items", "razorpay", 2)
    assert flows.successors(step) == [None]
    assert not flows.waits(step)
    with pytest.raises(ValidationError):
        pay_flow(items=[{"product_id": str(PRODUCT), "quantity": 0}])


def test_a_payment_step_needs_the_plan_the_method_and_live_products() -> None:
    line = {"product_id": str(PRODUCT), "variant_id": str(VARIANT)}
    products = {PRODUCT: (True, frozenset({VARIANT}))}
    ok = context(products=products)
    assert errors(pay_flow(items=[line]), ok) == {}
    assert errors(pay_flow(source="draft"), ok) == {}  # the conversation's order: no lines to check

    free = context(products=products, commerce=False)
    assert errors(pay_flow(items=[line]), free) == {
        "flow.steps.0.method": flows.COPY["payment_plan"]
    }
    no_keys = context(products=products, payment_methods=frozenset({"upi"}))
    assert errors(pay_flow(items=[line]), no_keys) == {
        "flow.steps.0.method": flows.COPY["payment_razorpay"]
    }
    no_upi = context(products=products, payment_methods=frozenset({"razorpay"}))
    assert errors(pay_flow(items=[line], method="upi"), no_upi) == {
        "flow.steps.0.method": flows.COPY["payment_upi"]
    }
    assert errors(pay_flow(), ok) == {"flow.steps.0.items": flows.COPY["payment_items"]}
    assert errors(pay_flow(items=[line]), context()) == {
        "flow.steps.0.items.0.product_id": flows.COPY["product_missing"]
    }
    off = context(products={PRODUCT: (False, frozenset({VARIANT}))})
    assert errors(pay_flow(items=[line]), off) == {
        "flow.steps.0.items.0.product_id": flows.COPY["product_off"]
    }
    no_variant = context(products={PRODUCT: (True, frozenset())})
    assert errors(pay_flow(items=[line]), no_variant) == {
        "flow.steps.0.items.0.variant_id": flows.COPY["variant_missing"]
    }
    needs_one = {"product_id": str(PRODUCT)}
    assert errors(pay_flow(items=[needs_one]), ok) == {
        "flow.steps.0.items.0.variant_id": flows.COPY["variant_needed"]
    }


def test_a_payment_step_cannot_follow_a_comments_private_reply() -> None:
    flow = FlowDefinition.model_validate(
        {
            "start": "a",
            "steps": [
                {"type": "send", "id": "a", "text": "Hi", "next": "p"},
                {"type": "payment", "id": "p", "source": "draft"},
            ],
        }
    )
    ctx = flows.Context(trigger="comment_keyword", disclosure=None)
    assert "flow.steps.1" in errors(flow, ctx)
