"""GR-32: the pieces of orders that need no database. The Razorpay signature, the HTTP client's
requests and error kinds, the sandbox, the UPI link and the payment message, and the timeline and
Activity wording."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from socialhood.models.orders import Order, OrderItem
from socialhood.razorpay.client import Credentials, RazorpayError
from socialhood.razorpay.fake import FakeRazorpay
from socialhood.razorpay.http import HttpRazorpayClient
from socialhood.razorpay.signatures import sign_webhook, verify_webhook
from socialhood.services import contact_timeline
from socialhood.services.activity import feed
from socialhood.services.orders import orders

CREDS = Credentials("rzp_test_abc12345", "secret-123")
NOW = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)


def make_order(**values: Any) -> Order:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "number": 12,
        "currency": "INR",
        "total_minor": 159800,
        "status": "draft",
    }
    return Order(**{**base, **values})


def make_item(name: str, qty: int, each: int, variant: str | None = None) -> OrderItem:
    return OrderItem(
        name=name,
        variant_title=variant,
        quantity=qty,
        unit_price_minor=each,
        line_total_minor=qty * each,
    )


# ---------------------------------------------------------------- signatures


def test_a_webhook_is_signed_with_a_hex_hmac_and_checked_in_full() -> None:
    raw = b'{"event":"payment_link.paid"}'
    signature = sign_webhook(raw, "hooksecret1")
    assert len(signature) == 64
    assert verify_webhook(raw, signature, "hooksecret1")
    assert verify_webhook(raw, f" {signature} ", "hooksecret1")
    assert not verify_webhook(raw + b" ", signature, "hooksecret1")
    assert not verify_webhook(raw, signature, "other")
    assert not verify_webhook(raw, None, "hooksecret1")
    assert not verify_webhook(raw, signature, "")
    assert not verify_webhook(raw, "not-hex", "hooksecret1")


# ---------------------------------------------------------------- the HTTP client


def client_with(handler: Any) -> HttpRazorpayClient:
    return HttpRazorpayClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_a_payment_link_is_created_with_the_businesss_keys() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "plink_1", "short_url": "https://rzp.io/i/abc"})

    link = await client_with(handler).create_payment_link(
        CREDS,
        amount_minor=159800,
        currency="INR",
        reference_id="order-1",
        description="Order #12",
        customer_name="Priya",
        customer_phone="+919876543210",
        expire_by=1_800_000_000,
    )

    assert (link.id, link.short_url) == ("plink_1", "https://rzp.io/i/abc")
    [request] = seen
    assert request.url == "https://api.razorpay.com/v1/payment_links"
    assert request.headers["authorization"].startswith("Basic ")
    body = json.loads(request.content)
    assert (body["amount"], body["currency"], body["reference_id"]) == (159800, "INR", "order-1")
    assert body["notify"] == {"sms": False, "email": False}
    assert body["accept_partial"] is False
    assert body["customer"] == {"name": "Priya", "contact": "+919876543210"}


@pytest.mark.parametrize(
    ("status", "kind"),
    [(401, "auth"), (403, "auth"), (429, "rate_limited"), (500, "unavailable"), (400, "rejected")],
)
async def test_http_errors_become_kinds(status: int, kind: str) -> None:
    client = client_with(lambda request: httpx.Response(status, json={}))
    with pytest.raises(RazorpayError) as raised:
        await client.verify(CREDS)
    assert raised.value.kind == kind


async def test_a_link_without_an_https_address_is_refused() -> None:
    client = client_with(
        lambda request: httpx.Response(200, json={"id": "p", "short_url": "http://x"})
    )
    with pytest.raises(RazorpayError) as raised:
        await client.create_payment_link(
            CREDS,
            amount_minor=1,
            currency="INR",
            reference_id="r",
            description="d",
            customer_name=None,
            customer_phone=None,
            expire_by=1,
        )
    assert raised.value.kind == "rejected"


# ---------------------------------------------------------------- the sandbox


async def test_the_sandbox_accepts_test_keys_only_and_can_fail_on_demand() -> None:
    fake = FakeRazorpay()
    await fake.verify(CREDS)
    with pytest.raises(RazorpayError) as raised:
        await fake.verify(Credentials("rzp_live_abc12345", "s"))
    assert raised.value.kind == "auth"
    fake.fail_next(RazorpayError("unavailable"))
    with pytest.raises(RazorpayError):
        await fake.verify(CREDS)
    link = await fake.create_payment_link(
        CREDS,
        amount_minor=100,
        currency="INR",
        reference_id="r",
        description="d",
        customer_name=None,
        customer_phone=None,
        expire_by=1,
    )
    assert link.id == "plink_fake_1"
    await fake.cancel_payment_link(CREDS, link.id)
    assert fake.links == {}


# ---------------------------------------------------------------- the message


def test_the_upi_link_carries_the_total_in_rupees_and_the_order_number() -> None:
    link = orders.upi_link("shop@okbank", "Maple & Co", make_order())
    assert link == "upi://pay?pa=shop%40okbank&pn=Maple%20%26%20Co&am=1598.00&cu=INR&tn=Order%2012"


def test_the_payment_message_lists_the_lines_the_total_and_how_to_pay() -> None:
    order = make_order()
    items = [make_item("Cotton kurta", 2, 79900, "Blue / M")]
    text = orders.payment_text(order, items, pay_url="https://rzp.io/i/abc", vpa=None)
    assert text == (
        "Order #12\n"
        "2 x Cotton kurta - Blue / M: INR 1598.00\n"
        "Total: INR 1598.00\n"
        "\n"
        "Pay here: https://rzp.io/i/abc"
    )
    upi = orders.payment_text(order, items, pay_url="upi://pay?x=1", vpa="shop@okbank")
    assert "Pay with any UPI app: upi://pay?x=1" in upi
    assert "send it to shop@okbank" in upi


def test_a_long_order_names_five_lines_and_counts_the_rest() -> None:
    items = [make_item(f"Item {i}", 1, 100) for i in range(8)]
    text = orders.payment_text(make_order(), items, pay_url="https://x.example/p", vpa=None)
    assert "Item 4" in text
    assert "Item 5" not in text
    assert "and 3 more" in text


# ---------------------------------------------------------------- timeline and Activity


def timeline_row(**values: Any) -> Any:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "at": NOW,
        "number": 12,
        "status": "paid",
        "currency": "INR",
        "total_minor": 159800,
        "payment_method": "razorpay",
        "conversation_id": None,
    }
    return SimpleNamespace(**{**base, **values})


def test_the_timeline_says_what_happened_to_the_order() -> None:
    paid = contact_timeline.order_item(timeline_row())
    assert (paid.kind, paid.title) == ("order", "Order #12 paid")
    assert paid.detail == "INR 1598.00. Paid with Razorpay"
    upi = contact_timeline.order_item(timeline_row(payment_method="upi"))
    assert upi.detail == "INR 1598.00. Paid by UPI"
    made = contact_timeline.order_item(timeline_row(status="draft", payment_method=None))
    assert (made.title, made.detail) == ("Order #12 created", "INR 1598.00")
    waiting = contact_timeline.order_item(timeline_row(status="awaiting_payment"))
    assert waiting.title == "Order #12 waiting for payment"


def test_activity_shows_a_paid_order_and_an_expired_one_that_needs_a_new_link() -> None:
    row = SimpleNamespace(
        id=uuid.uuid4(),
        at=NOW,
        number=12,
        status="paid",
        currency="INR",
        total_minor=159800,
        account_id=uuid.uuid4(),
        platform="instagram",
        account_username="maple",
        account_display_name=None,
        contact_username="priya.shah",
        contact_display_name=None,
    )
    paid = feed._order_item(row)
    assert (paid.kind, paid.outcome) == ("order", "ok")
    assert paid.title == "Order #12 was paid from @priya.shah"
    row.status = "expired"
    expired = feed._order_item(row)
    assert expired.outcome == "attention"
    assert "Send a new one" in (expired.reason or "")
