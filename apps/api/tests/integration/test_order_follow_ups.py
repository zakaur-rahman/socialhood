"""GR-32 follow-ups on the sandbox: part payments (by hand, and on a Razorpay link that allows
them), refunds (through Razorpay with the business's keys, and recorded by hand for UPI), shipping,
editing an order, and the status message to the customer (text in the window, an approved utility
template after it on WhatsApp, a plain reason when it can't go)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.models.platform import WebhookStatus
from socialhood.razorpay.fake import FakeRazorpay
from tests.integration.test_orders import (
    order_in_chat,
    paid_event,
    post_webhook,
    process_last,
    razorpay_ready,
    rows,
)
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.broadcasts import Shop, shop
from tests.support.catalogue import kurta_data, make_product


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None) -> Ws:
    made = await workspace(client, clerk)
    await set_plan(engine, made.wid, "pro")
    return made


@pytest.fixture
async def desk(
    client: httpx.AsyncClient,
    clerk: Clerk,
    app: FastAPI,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Shop:
    return await shop(client, clerk, app, engine, redis, monkeypatch)


TOTAL = 159800  # two Blue / M kurtas at INR 799.00


async def upi_ready(ws: Ws) -> None:
    await ws.ok("PUT", "/integrations/payments/upi", json={"vpa": "shop@okbank", "name": "Maple"})


async def paid_by_razorpay(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis, **extra: Any
) -> dict[str, Any]:
    """An order paid in full through a signed `payment_link.paid` webhook (payment pay_Fake123)."""
    token = await razorpay_ready(ws)
    order, _ = await order_in_chat(ws, engine, **extra)
    asked = await ws.ok(
        "POST", f"/orders/{order['id']}/payment-request", json={"method": "razorpay", "send": False}
    )
    link_id = asked["payment_link_url"].rsplit("/", 1)[1]
    await post_webhook(client, token, paid_event(link_id, order), event_id="paid-1")
    assert await process_last(engine, redis) is WebhookStatus.PROCESSED
    return {**await ws.ok("GET", f"/orders/{order['id']}"), "_token": token}


def refund_event(
    event: str, refund_id: str, payment_id: str, amount: int, status: str = "processed"
) -> bytes:
    return json.dumps(
        {
            "event": event,
            "payload": {
                "refund": {
                    "entity": {
                        "id": refund_id,
                        "payment_id": payment_id,
                        "amount": amount,
                        "status": status,
                    }
                },
                "payment": {"entity": {"id": payment_id}},
            },
        }
    ).encode()


def link_event(
    event: str, link_id: str, order: dict[str, Any], *, paid: int, payment: str, amount: int
) -> bytes:
    return json.dumps(
        {
            "event": event,
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": link_id,
                        "reference_id": order["id"],
                        "amount": order["total_minor"],
                        "amount_paid": paid,
                        "currency": order["currency"],
                    }
                },
                "payment": {"entity": {"id": payment, "amount": amount}},
            },
        }
    ).encode()


# ---------------------------------------------------------------- part payments


async def test_a_upi_order_is_paid_in_parts_by_hand(ws: Ws, engine: AsyncEngine) -> None:
    await upi_ready(ws)
    order, _ = await order_in_chat(ws, engine)
    await ws.ok("POST", f"/orders/{order['id']}/payment-request", json={"method": "upi"})

    part = await ws.ok(
        "POST",
        f"/orders/{order['id']}/mark-paid",
        json={"amount_minor": 50000, "reference": "UTR 1"},
    )
    assert part["status"] == "partially_paid"
    assert (part["amount_paid_minor"], part["amount_left_minor"]) == (50000, 109800)
    assert (part["amount_paid"], part["amount_left"]) == ("500.00", "1098.00")
    assert [p["amount_minor"] for p in part["payments"]] == [50000]
    assert part["payments"][0]["recorded_by_name"]

    # Asking for the rest says what is left, and the UPI link is for that amount.
    again = await ws.ok("POST", f"/orders/{order['id']}/payment-request", json={"method": "upi"})
    assert "am=1098.00" in again["payment_link_url"]
    assert again["status"] == "partially_paid"  # asking again does not undo what was paid
    texts = [r["text"] for r in await rows(engine, "SELECT text FROM messages ORDER BY created_at")]
    assert "Paid so far: INR 500.00" in texts[-1]
    assert "Left to pay: INR 1098.00" in texts[-1]

    too_much = await ws.call(
        "POST", f"/orders/{order['id']}/mark-paid", json={"amount_minor": 200000}
    )
    assert too_much.status_code == 422
    assert too_much.json()["detail"] == "That payment is more than what is left to pay."

    # A partly paid order can't be cancelled or edited: there is money on it.
    cancel = await ws.call("POST", f"/orders/{order['id']}/cancel")
    assert cancel.status_code == 422
    assert cancel.json()["detail"] == "This order has payments. Refund them before you cancel it."
    edit = await ws.call("PATCH", f"/orders/{order['id']}", json={"note": "x"})
    assert edit.status_code == 422

    done = await ws.ok("POST", f"/orders/{order['id']}/mark-paid", json={})  # all that is left
    assert (done["status"], done["amount_paid_minor"], done["amount_left_minor"]) == (
        "paid",
        TOTAL,
        0,
    )
    assert [p["amount_minor"] for p in done["payments"]] == [50000, 109800]
    assert done["paid_at"] is not None
    audits = await rows(
        engine, "SELECT detail FROM audit_events WHERE action = 'order.marked_paid'"
    )
    assert sorted(a["detail"]["amount_minor"] for a in audits) == [50000, 109800]


async def test_a_razorpay_link_that_takes_parts_records_each_payment_once(
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    redis: Redis,
    fake_razorpay: FakeRazorpay,
) -> None:
    token = await razorpay_ready(ws)
    order, _ = await order_in_chat(ws, engine)
    asked = await ws.ok(
        "POST",
        f"/orders/{order['id']}/payment-request",
        json={"method": "razorpay", "send": False, "allow_partial": True},
    )
    assert asked["accept_partial"] is True
    [call] = [c for c in fake_razorpay.calls if c[0] == "create_payment_link"]
    assert call[1]["accept_partial"] is True
    link_id = asked["payment_link_url"].rsplit("/", 1)[1]

    first = link_event(
        "payment_link.partially_paid", link_id, order, paid=60000, payment="pay_P1", amount=60000
    )
    await post_webhook(client, token, first, event_id="part-1")
    assert await process_last(engine, redis) is WebhookStatus.PROCESSED
    part = await ws.ok("GET", f"/orders/{order['id']}")
    assert (part["status"], part["amount_paid_minor"]) == ("partially_paid", 60000)

    # The same payment under another event id is not counted twice.
    await post_webhook(client, token, first, event_id="part-1b")
    assert await process_last(engine, redis) is WebhookStatus.IGNORED
    assert (await ws.ok("GET", f"/orders/{order['id']}"))["amount_paid_minor"] == 60000

    last = link_event(
        "payment_link.paid", link_id, order, paid=TOTAL, payment="pay_P2", amount=99800
    )
    await post_webhook(client, token, last, event_id="part-2")
    assert await process_last(engine, redis) is WebhookStatus.PROCESSED
    done = await ws.ok("GET", f"/orders/{order['id']}")
    assert (done["status"], done["amount_paid_minor"]) == ("paid", TOTAL)
    assert [p["amount_minor"] for p in done["payments"]] == [60000, 99800]
    assert done["payment_reference"] == "pay_P2"


async def test_a_link_without_part_payments_ignores_a_part_and_a_part_link_needs_rupees(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    token = await razorpay_ready(ws)
    order, _ = await order_in_chat(ws, engine)
    asked = await ws.ok(
        "POST", f"/orders/{order['id']}/payment-request", json={"method": "razorpay", "send": False}
    )
    assert asked["accept_partial"] is False
    link_id = asked["payment_link_url"].rsplit("/", 1)[1]
    part = link_event(
        "payment_link.partially_paid", link_id, order, paid=1000, payment="pay_X", amount=1000
    )
    await post_webhook(client, token, part, event_id="p")
    assert await process_last(engine, redis) is WebhookStatus.IGNORED
    assert (await ws.ok("GET", f"/orders/{order['id']}"))["status"] == "awaiting_payment"

    # A second product in the same workspace needs its own SKUs.
    data = kurta_data()
    data.currency = "USD"
    for variant in data.variants:
        variant.sku = f"USD-{variant.sku}"
    usd = await make_product(engine, workspace_id=ws.wid, data=data)
    other, _ = await order_in_chat(ws, engine, kurta=usd)
    refused = await ws.call(
        "POST",
        f"/orders/{other['id']}/payment-request",
        json={"method": "razorpay", "allow_partial": True},
    )
    assert refused.status_code == 422
    assert "rupees" in refused.json()["detail"]


# ---------------------------------------------------------------- refunds


async def test_a_razorpay_order_is_refunded_in_part_then_in_full(
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    redis: Redis,
    fake_razorpay: FakeRazorpay,
) -> None:
    hook = await ws.ok(
        "POST",
        "/webhook-endpoints",
        201,
        json={"url": "https://hooks.example/refunds", "events": ["order.refunded"]},
    )
    order = await paid_by_razorpay(ws, client, engine, redis)
    assert (order["status"], order["refundable_minor"]) == ("paid", TOTAL)

    part = await ws.ok(
        "POST",
        f"/orders/{order['id']}/refunds",
        json={"amount_minor": 50000, "reason": "One kurta was damaged"},
    )
    assert part["status"] == "paid"  # a part refund leaves it paid
    assert (part["amount_refunded_minor"], part["refundable_minor"]) == (50000, 109800)
    [made] = part["refunds"]
    assert (made["method"], made["status"], made["reason"]) == (
        "razorpay",
        "processed",
        "One kurta was damaged",
    )
    [call] = [c for c in fake_razorpay.calls if c[0] == "refund_payment"]
    assert (call[1]["payment_id"], call[1]["amount_minor"]) == ("pay_Fake123", 50000)

    rest = await ws.ok(
        "POST", f"/orders/{order['id']}/refunds", json={"reason": "Customer changed their mind"}
    )
    assert (rest["status"], rest["amount_refunded_minor"], rest["refundable_minor"]) == (
        "refunded",
        TOTAL,
        0,
    )
    again = await ws.call("POST", f"/orders/{order['id']}/refunds", json={"reason": "Again"})
    assert again.status_code == 422
    assert again.json()["detail"] == "Everything paid on this order has been refunded."

    kinds = await rows(
        engine,
        "SELECT payload FROM webhook_deliveries WHERE endpoint_id = :e ORDER BY created_at",
        e=hook["id"],
    )
    refunds = [k["payload"]["data"]["refund"] for k in kinds]
    assert [(r["amount_minor"], r["full"]) for r in refunds] == [(50000, False), (109800, True)]
    assert kinds[0]["payload"]["type"] == "order.refunded"
    audits = await rows(
        engine,
        "SELECT detail FROM audit_events WHERE action = 'order.refunded' ORDER BY created_at",
    )
    assert len(audits) == 2
    assert {a["detail"]["reason"] for a in audits} == {
        "One kurta was damaged",
        "Customer changed their mind",
    }


async def test_a_refund_must_have_a_reason_and_fit_what_was_paid(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    unpaid, kurta = await order_in_chat(ws, engine)
    nothing = await ws.call("POST", f"/orders/{unpaid['id']}/refunds", json={"reason": "x"})
    assert nothing.status_code == 422
    assert nothing.json()["detail"] == "Only an order with a payment can be refunded."

    order = await paid_by_razorpay(ws, client, engine, redis, kurta=kurta)
    no_reason = await ws.call("POST", f"/orders/{order['id']}/refunds", json={"reason": ""})
    assert no_reason.status_code == 422
    too_big = await ws.call(
        "POST", f"/orders/{order['id']}/refunds", json={"amount_minor": TOTAL + 1, "reason": "x"}
    )
    assert too_big.status_code == 422
    assert too_big.json()["detail"] == "You can refund up to INR 1598.00 on this order."
    # A paid order can't be cancelled or marked paid again, and a refund isn't an edit.
    assert (await ws.call("POST", f"/orders/{order['id']}/cancel")).status_code == 422
    assert (await ws.call("POST", f"/orders/{order['id']}/mark-paid", json={})).status_code == 422


async def test_a_pending_refund_waits_for_razorpay_and_a_failed_one_frees_the_money(
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    redis: Redis,
    fake_razorpay: FakeRazorpay,
) -> None:
    order = await paid_by_razorpay(ws, client, engine, redis)
    token = order["_token"]
    fake_razorpay.refund_status = "pending"

    pending = await ws.ok(
        "POST",
        f"/orders/{order['id']}/refunds",
        json={"amount_minor": 100000, "reason": "Late delivery"},
    )
    assert pending["refunds"][0]["status"] == "pending"
    assert (pending["amount_refunded_minor"], pending["refundable_minor"]) == (0, 59800)
    over = await ws.call(
        "POST", f"/orders/{order['id']}/refunds", json={"amount_minor": 70000, "reason": "x"}
    )
    assert over.status_code == 422  # 1000.00 is already on its way back

    refund_id = "rfnd_fake_1"
    done = refund_event("refund.processed", refund_id, "pay_Fake123", 100000)
    await post_webhook(client, token, done, event_id="r-1")
    assert await process_last(engine, redis) is WebhookStatus.PROCESSED
    settled = await ws.ok("GET", f"/orders/{order['id']}")
    assert settled["refunds"][0]["status"] == "processed"
    assert (settled["amount_refunded_minor"], settled["refundable_minor"]) == (100000, 59800)
    await post_webhook(client, token, done, event_id="r-1b")  # a repeat changes nothing
    assert await process_last(engine, redis) is WebhookStatus.IGNORED

    failing = await ws.ok(
        "POST", f"/orders/{order['id']}/refunds", json={"amount_minor": 59800, "reason": "Rest"}
    )
    assert failing["refundable_minor"] == 0
    lost = refund_event("refund.failed", "rfnd_fake_2", "pay_Fake123", 59800, "failed")
    await post_webhook(client, token, lost, event_id="r-2")
    assert await process_last(engine, redis) is WebhookStatus.PROCESSED
    after = await ws.ok("GET", f"/orders/{order['id']}")
    assert [r["status"] for r in after["refunds"]] == ["processed", "failed"]
    assert after["refunds"][1]["failure"] == "Razorpay could not make this refund."
    assert (after["amount_refunded_minor"], after["refundable_minor"]) == (100000, 59800)
    assert after["status"] == "paid"


async def test_a_refund_made_in_the_razorpay_dashboard_is_recorded(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    order = await paid_by_razorpay(ws, client, engine, redis)
    event = refund_event("refund.processed", "rfnd_dash_1", "pay_Fake123", TOTAL)
    await post_webhook(client, order["_token"], event, event_id="dash-1")
    assert await process_last(engine, redis) is WebhookStatus.PROCESSED
    seen = await ws.ok("GET", f"/orders/{order['id']}")
    assert (seen["status"], seen["amount_refunded_minor"]) == ("refunded", TOTAL)
    [refund] = seen["refunds"]
    assert refund["reason"] == "Refunded in the Razorpay dashboard"
    assert refund["created_by_name"] is None

    stranger = refund_event("refund.processed", "rfnd_x", "pay_unknown", 100)
    await post_webhook(client, order["_token"], stranger, event_id="dash-2")
    assert await process_last(engine, redis) is WebhookStatus.IGNORED


async def test_a_razorpay_failure_on_a_refund_is_reported_and_nothing_is_recorded(
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    redis: Redis,
    fake_razorpay: FakeRazorpay,
) -> None:
    from socialhood.razorpay.client import RazorpayError

    order = await paid_by_razorpay(ws, client, engine, redis)
    fake_razorpay.fail_next(RazorpayError("unavailable"))
    down = await ws.call("POST", f"/orders/{order['id']}/refunds", json={"reason": "Return"})
    assert down.status_code == 502
    assert (await ws.ok("GET", f"/orders/{order['id']}"))["refunds"] == []
    fake_razorpay.fail_next(RazorpayError("rejected"))
    refused = await ws.call("POST", f"/orders/{order['id']}/refunds", json={"reason": "Return"})
    assert refused.status_code == 422
    assert refused.json()["detail"] == "Razorpay refused this refund."


async def test_a_upi_payment_is_refunded_by_the_business_and_recorded(
    ws: Ws, engine: AsyncEngine, fake_razorpay: FakeRazorpay
) -> None:
    await upi_ready(ws)
    order, _ = await order_in_chat(ws, engine)
    await ws.ok("POST", f"/orders/{order['id']}/payment-request", json={"method": "upi"})
    await ws.ok("POST", f"/orders/{order['id']}/mark-paid", json={"reference": "UTR 9"})

    refunded = await ws.ok(
        "POST",
        f"/orders/{order['id']}/refunds",
        json={"amount_minor": TOTAL, "reason": "Sent back by UPI"},
    )
    assert refunded["status"] == "refunded"
    [refund] = refunded["refunds"]
    assert (refund["method"], refund["status"]) == ("manual", "processed")
    assert refund["created_by_name"]
    assert not [c for c in fake_razorpay.calls if c[0] == "refund_payment"]  # no Razorpay call


async def test_a_refund_is_split_over_payments_newest_first(ws: Ws, engine: AsyncEngine) -> None:
    await upi_ready(ws)
    order, _ = await order_in_chat(ws, engine)
    await ws.ok("POST", f"/orders/{order['id']}/payment-request", json={"method": "upi"})
    await ws.ok("POST", f"/orders/{order['id']}/mark-paid", json={"amount_minor": 100000})
    await ws.ok("POST", f"/orders/{order['id']}/mark-paid", json={})  # 598.00 more

    out = await ws.ok(
        "POST", f"/orders/{order['id']}/refunds", json={"amount_minor": 70000, "reason": "Return"}
    )
    # The newest payment (598.00) is used up first, then the earlier one gives the rest.
    assert sorted(r["amount_minor"] for r in out["refunds"]) == [10200, 59800]
    assert out["amount_refunded_minor"] == 70000


# ---------------------------------------------------------------- shipping


async def test_a_paid_order_is_marked_shipped_and_a_shipped_one_can_still_be_refunded(
    ws: Ws, engine: AsyncEngine
) -> None:
    await upi_ready(ws)
    order, _ = await order_in_chat(ws, engine)
    early = await ws.call("POST", f"/orders/{order['id']}/fulfil", json={})
    assert early.status_code == 422
    assert early.json()["detail"] == "Only a paid order can be marked shipped."

    await ws.ok("POST", f"/orders/{order['id']}/payment-request", json={"method": "upi"})
    await ws.ok("POST", f"/orders/{order['id']}/mark-paid", json={})
    shipped = await ws.ok(
        "POST", f"/orders/{order['id']}/fulfil", json={"note": "Delhivery 123456"}
    )
    assert (shipped["status"], shipped["fulfilment_note"]) == ("fulfilled", "Delhivery 123456")
    assert shipped["fulfilled_at"] is not None
    assert (await ws.call("POST", f"/orders/{order['id']}/fulfil", json={})).status_code == 422
    audit = await rows(engine, "SELECT detail FROM audit_events WHERE action = 'order.fulfilled'")
    assert audit[0]["detail"]["note"] == "Delhivery 123456"

    back = await ws.ok(
        "POST", f"/orders/{order['id']}/refunds", json={"amount_minor": 1000, "reason": "Small"}
    )
    assert back["status"] == "fulfilled"
    listed = await ws.ok("GET", "/orders", params={"status": "fulfilled"})
    assert [o["id"] for o in listed["items"]] == [order["id"]]


# ---------------------------------------------------------------- editing


async def test_a_draft_is_re_priced_when_its_lines_change(ws: Ws, engine: AsyncEngine) -> None:
    order, kurta = await order_in_chat(ws, engine)
    assert order["total_minor"] == TOTAL
    edited = await ws.ok(
        "PATCH",
        f"/orders/{order['id']}",
        json={
            "items": [
                {
                    "product_id": str(kurta.id),
                    "variant_id": str(kurta.variants["Blue / S"]),
                    "quantity": 1,
                }
            ],
            "address": {"name": "Priya Shah", "line1": "5 FC Road", "city": "Pune"},
            "note": "Gift wrap",
        },
    )
    assert edited["total_minor"] == 79900
    assert [(i["variant_title"], i["quantity"]) for i in edited["items"]] == [("Blue / S", 1)]
    assert edited["address"]["line1"] == "5 FC Road"
    assert edited["note"] == "Gift wrap"
    audit = await rows(engine, "SELECT detail FROM audit_events WHERE action = 'order.edited'")
    assert audit[0]["detail"]["total_before"] == TOTAL
    assert audit[0]["detail"]["total_after"] == 79900

    cleared = await ws.ok("PATCH", f"/orders/{order['id']}", json={"note": ""})
    assert cleared["note"] is None
    nothing = await ws.call(
        "PATCH",
        f"/orders/{order['id']}",
        json={"items": [{"product_id": "00000000-0000-4000-8000-000000000000", "quantity": 1}]},
    )
    assert nothing.status_code == 404


async def test_a_new_total_cancels_the_old_link_and_can_send_a_new_one(
    ws: Ws, engine: AsyncEngine, fake_razorpay: FakeRazorpay
) -> None:
    await razorpay_ready(ws)
    order, kurta = await order_in_chat(ws, engine)
    asked = await ws.ok(
        "POST", f"/orders/{order['id']}/payment-request", json={"method": "razorpay", "send": False}
    )
    old = asked["payment_link_url"]

    # An edit that keeps the total (the address) leaves the link alone.
    same = await ws.ok("PATCH", f"/orders/{order['id']}", json={"note": "Ring the bell"})
    assert (same["status"], same["payment_link_url"]) == ("awaiting_payment", old)

    one = {"items": [{"product_id": str(kurta.id), "variant_id": str(kurta.variants["Blue / M"])}]}
    edited = await ws.ok("PATCH", f"/orders/{order['id']}", json=one)
    assert (edited["status"], edited["payment_link_url"]) == ("draft", None)
    assert edited["total_minor"] == 79900
    assert any(name == "cancel_payment_link" for name, _ in fake_razorpay.calls)

    asked_again = await ws.ok(
        "PATCH",
        f"/orders/{order['id']}",
        json={
            "items": [
                {
                    "product_id": str(kurta.id),
                    "variant_id": str(kurta.variants["Blue / M"]),
                    "quantity": 3,
                }
            ],
            "payment": {"method": "razorpay", "send": True},
        },
    )
    assert asked_again["status"] == "awaiting_payment"
    assert asked_again["total_minor"] == 239700
    assert asked_again["payment_link_url"] not in (None, old)
    creates = [c for c in fake_razorpay.calls if c[0] == "create_payment_link"]
    assert creates[-1][1]["amount_minor"] == 239700
    [sent] = await rows(
        engine, "SELECT text FROM messages WHERE direction = 'outbound' ORDER BY created_at DESC"
    )
    assert "Total: INR 2397.00" in sent["text"]


async def test_a_paid_or_cancelled_order_cannot_be_edited(ws: Ws, engine: AsyncEngine) -> None:
    paid, kurta = await order_in_chat(ws, engine)
    await ws.ok("POST", f"/orders/{paid['id']}/mark-paid", json={})
    refused = await ws.call("PATCH", f"/orders/{paid['id']}", json={"note": "x"})
    assert refused.status_code == 422
    assert (
        refused.json()["detail"]
        == "An order can be changed until someone pays it. This one is paid."
    )

    gone, _ = await order_in_chat(ws, engine, kurta=kurta)
    await ws.ok("POST", f"/orders/{gone['id']}/cancel")
    assert (await ws.call("PATCH", f"/orders/{gone['id']}", json={"note": "x"})).status_code == 422


# ---------------------------------------------------------------- the message to the customer


async def test_a_status_message_goes_as_text_inside_the_window(ws: Ws, engine: AsyncEngine) -> None:
    order, _ = await order_in_chat(ws, engine)
    paid = await ws.ok("POST", f"/orders/{order['id']}/mark-paid", json={"notice": {}})
    assert paid["notice"] == {"sent": True, "reason": None}
    [sent] = await rows(engine, "SELECT text, source FROM messages WHERE direction = 'outbound'")
    assert sent["text"] == "Thanks, we've got your payment for order #1 (INR 1598.00)."
    assert sent["source"] == "human"

    shipped = await ws.ok(
        "POST",
        f"/orders/{order['id']}/fulfil",
        json={"note": "Tracking 42", "notice": {"message": "Out for delivery today!"}},
    )
    assert shipped["notice"]["sent"] is True
    texts = [r["text"] for r in await rows(engine, "SELECT text FROM messages ORDER BY created_at")]
    assert texts[-1] == "Out for delivery today!"

    quiet = await ws.ok("POST", f"/orders/{order['id']}/refunds", json={"reason": "Return"})
    assert quiet["notice"] is None  # no message was asked for


async def test_a_status_message_that_cannot_go_says_why_and_the_change_still_happens(
    ws: Ws, engine: AsyncEngine
) -> None:
    order, _ = await order_in_chat(ws, engine)
    async with engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(
            text("UPDATE conversations SET last_inbound_at = :t"),
            {"t": datetime.now(UTC) - timedelta(days=10)},  # past Human Agent's seven days
        )
    paid = await ws.ok("POST", f"/orders/{order['id']}/mark-paid", json={"notice": {}})
    assert paid["status"] == "paid"
    assert paid["notice"]["sent"] is False
    assert "messaging window has closed" in paid["notice"]["reason"]
    assert await rows(engine, "SELECT id FROM messages WHERE direction = 'outbound'") == []
    sent_audit = await rows(
        engine, "SELECT detail FROM audit_events WHERE action = 'order.status_message'"
    )
    assert sent_audit[0]["detail"]["sent"] is False


async def test_a_cancel_can_carry_a_message_and_still_works_without_a_body(
    ws: Ws, engine: AsyncEngine
) -> None:
    order, kurta = await order_in_chat(ws, engine)
    cancelled = await ws.ok(
        "POST", f"/orders/{order['id']}/cancel", json={"notice": {"message": "Sorry, cancelled."}}
    )
    assert (cancelled["status"], cancelled["notice"]["sent"]) == ("cancelled", True)
    other, _ = await order_in_chat(ws, engine, kurta=kurta)
    plain = await ws.ok("POST", f"/orders/{other['id']}/cancel")
    assert (plain["status"], plain["notice"]) == ("cancelled", None)


# ---------------------------------------------------------------- the message on WhatsApp


async def whatsapp_order(desk: Shop, name: str = "Asha Rao") -> dict[str, Any]:
    customer = await desk.customer(name)
    kurta = await make_product(desk.engine, workspace_id=desk.ws.wid)
    return await desk.ws.ok(
        "POST",
        "/orders",
        201,
        json={
            "conversation_id": str(customer.conversation_id),
            "items": [
                {
                    "product_id": str(kurta.id),
                    "variant_id": str(kurta.variants["Blue / M"]),
                    "quantity": 1,
                }
            ],
        },
    )


async def close_window(desk: Shop) -> None:
    from sqlalchemy import text

    async with desk.engine.begin() as conn:
        await conn.execute(
            text("UPDATE conversations SET last_inbound_at = :t"),
            {"t": datetime.now(UTC) - timedelta(days=3)},
        )


async def test_after_the_window_a_whatsapp_update_needs_an_approved_utility_template(
    desk: Shop,
) -> None:
    order = await whatsapp_order(desk)
    await close_window(desk)
    ws = desk.ws

    none_chosen = await ws.ok("POST", f"/orders/{order['id']}/mark-paid", json={"notice": {}})
    assert none_chosen["status"] == "paid"
    assert none_chosen["notice"]["sent"] is False
    assert "Choose a utility template" in none_chosen["notice"]["reason"]

    marketing = await ws.ok(
        "POST",
        f"/orders/{order['id']}/fulfil",
        json={"notice": {"template_name": "sale_offer", "template_language": "en"}},
    )
    assert marketing["notice"] == {
        "sent": False,
        "reason": "Only an approved utility template can carry an order update.",
    }

    unknown = await ws.ok(
        "POST",
        f"/orders/{order['id']}/refunds",
        json={
            "amount_minor": 100,
            "reason": "Small",
            "notice": {"template_name": "no_such", "template_language": "en"},
        },
    )
    assert (
        unknown["notice"]["reason"]
        == "That template isn't approved on this number. Choose another."
    )

    sent = await ws.ok(
        "POST",
        f"/orders/{order['id']}/refunds",
        json={
            "amount_minor": 100,
            "reason": "Small",
            "notice": {"template_name": "order_shipped", "template_language": "en"},
        },
    )
    assert sent["notice"] == {"sent": True, "reason": None}
    [message] = await desk.rows(
        "SELECT template FROM messages WHERE direction = 'outbound' AND template IS NOT NULL"
    )
    assert message["template"]["name"] == "order_shipped"
    assert message["template"]["params"] == ["Asha", "#1"]  # first name, order number


async def test_inside_the_window_a_whatsapp_update_is_text_even_when_a_template_is_chosen(
    desk: Shop,
) -> None:
    order = await whatsapp_order(desk)
    paid = await desk.ws.ok(
        "POST",
        f"/orders/{order['id']}/mark-paid",
        json={"notice": {"template_name": "order_shipped", "template_language": "en"}},
    )
    assert paid["notice"]["sent"] is True
    [message] = await desk.rows("SELECT text, template FROM messages WHERE direction = 'outbound'")
    assert message["template"] in (None, {})
    assert message["text"].startswith("Thanks, we've got your payment for order #1")
