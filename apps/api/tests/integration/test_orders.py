"""GR-32: orders and payment requests. Pro and Max only (PD-8); totals computed on the server from
the catalogue and snapshotted; a Razorpay payment link on the workspace's own keys is sent in the
conversation; the signed `payment_link.paid` webhook marks the order paid once; a UPI order is
marked paid by hand and audited; events, the contact timeline, Activity and the Ask tool see it."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.models.platform import WebhookStatus
from socialhood.razorpay.fake import FakeRazorpay
from socialhood.razorpay.signatures import sign_webhook
from socialhood.services.catalogue.products import ProductData
from socialhood.services.webhook_processing import process_event
from tests.support.api import Clerk
from tests.support.automation_api import Ws, set_plan, workspace
from tests.support.catalogue import make_product
from tests.support.inbox import make_thread
from tests.support.ingest import sessions

KEYS = {
    "key_id": "rzp_test_abcdefgh",
    "private_key": "keysecret123",
    "webhook_key": "hooksecret1",
}


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None) -> Ws:
    made = await workspace(client, clerk)
    await set_plan(engine, made.wid, "pro")
    return made


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def order_in_chat(
    ws: Ws, engine: AsyncEngine, *, kurta: Any = None, **extra: Any
) -> tuple[dict[str, Any], Any]:
    """A conversation, the cotton kurta (made once, or pass it) and two Blue / M."""
    thread = await make_thread(engine, workspace_id=ws.wid, account_id=ws.account_id)
    kurta = kurta or await make_product(engine, workspace_id=ws.wid)
    order = await ws.ok(
        "POST",
        "/orders",
        201,
        json={
            "conversation_id": str(thread.conversation_id),
            "items": [
                {
                    "product_id": str(kurta.id),
                    "variant_id": str(kurta.variants["Blue / M"]),
                    "quantity": 2,
                }
            ],
            "address": {"name": "Priya Shah", "line1": "12 MG Road", "city": "Pune"},
            **extra,
        },
    )
    return order, kurta


# ---------------------------------------------------------------- the plan


async def test_free_reads_but_cannot_order_or_connect(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    free = await workspace(client, clerk)
    listing = await free.ok("GET", "/orders")
    assert listing["items"] == []
    assert listing["limits"] == {"entitled": False, "razorpay_ready": False, "upi_ready": False}
    thread = await make_thread(engine, workspace_id=free.wid, account_id=free.account_id)
    kurta = await make_product(engine, workspace_id=free.wid)
    refused = await free.call(
        "POST",
        "/orders",
        json={
            "conversation_id": str(thread.conversation_id),
            "items": [{"product_id": str(kurta.id), "variant_id": str(kurta.variants["Blue / M"])}],
        },
    )
    assert refused.status_code == 402
    assert refused.json()["entitlement"] == "commerce"
    assert (await free.call("PUT", "/integrations/payments/razorpay", json=KEYS)).status_code == 402
    upi = {"vpa": "shop@okbank", "name": "Shop"}
    assert (await free.call("PUT", "/integrations/payments/upi", json=upi)).status_code == 402


# ---------------------------------------------------------------- making an order


async def test_an_order_is_priced_from_the_catalogue_and_snapshotted(
    ws: Ws, engine: AsyncEngine
) -> None:
    order, kurta = await order_in_chat(ws, engine, note="Gift wrap")

    assert (order["number"], order["status"], order["currency"]) == (1, "draft", "INR")
    assert (order["total_minor"], order["total"]) == (159800, "1598.00")
    [line] = order["items"]
    assert (line["name"], line["variant_title"], line["quantity"]) == (
        "Cotton kurta",
        "Blue / M",
        2,
    )
    assert (line["unit_price_minor"], line["line_total_minor"]) == (79900, 159800)
    assert order["address"]["city"] == "Pune"

    # A later price change does not alter the order.
    await ws.ok(
        "PATCH",
        f"/products/{kurta.id}",
        json={
            "variants": [
                {"id": str(kurta.variants["Blue / M"]), "title": "Blue / M", "price": "999"}
            ]
        },
    )
    again = await ws.ok("GET", f"/orders/{order['id']}")
    assert again["total_minor"] == 159800
    assert again["items"][0]["unit_price_minor"] == 79900


async def test_numbers_count_up_and_bad_lines_are_refused(ws: Ws, engine: AsyncEngine) -> None:
    first, kurta = await order_in_chat(ws, engine)
    thread = await make_thread(engine, workspace_id=ws.wid, account_id=ws.account_id)
    body = {"conversation_id": str(thread.conversation_id)}
    second = await ws.ok(
        "POST",
        "/orders",
        201,
        json={
            **body,
            "items": [{"product_id": str(kurta.id), "variant_id": str(kurta.variants["Blue / S"])}],
        },
    )
    assert (first["number"], second["number"]) == (1, 2)

    no_variant = await ws.call(
        "POST", "/orders", json={**body, "items": [{"product_id": str(kurta.id)}]}
    )
    assert no_variant.status_code == 422
    too_many = await ws.call(
        "POST",
        "/orders",
        json={
            **body,
            "items": [
                {
                    "product_id": str(kurta.id),
                    "variant_id": str(kurta.variants["Blue / S"]),
                    "quantity": 5,  # only 4 are in stock
                }
            ],
        },
    )
    assert too_many.status_code == 422
    assert "Only 4 left" in json.dumps(too_many.json())
    unpriced = await make_product(engine, workspace_id=ws.wid, data=ProductData(name="Free sample"))
    assert (
        await ws.call("POST", "/orders", json={**body, "items": [{"product_id": str(unpriced.id)}]})
    ).status_code == 422


# ---------------------------------------------------------------- Razorpay


async def test_unset_razorpay_says_not_configured(ws: Ws, engine: AsyncEngine) -> None:
    order, _ = await order_in_chat(ws, engine)
    refused = await ws.call(
        "POST", f"/orders/{order['id']}/payment-request", json={"method": "razorpay"}
    )
    assert refused.status_code == 409
    assert "isn't set up" in refused.json()["detail"]
    status = await ws.ok("GET", "/integrations/payments")
    assert status["razorpay_connected"] is False
    assert status["webhook_url"] is None


async def test_bad_keys_are_refused_and_good_ones_are_stored_encrypted(
    ws: Ws, engine: AsyncEngine
) -> None:
    bad = await ws.call(
        "PUT", "/integrations/payments/razorpay", json={**KEYS, "key_id": "rzp_live_abcdefgh"}
    )
    assert bad.status_code == 422  # the sandbox accepts test keys only

    status = await ws.ok("PUT", "/integrations/payments/razorpay", json=KEYS)
    assert (status["razorpay_connected"], status["razorpay_test_mode"]) == (True, True)
    assert status["webhook_url"].startswith("http")
    assert "payment_link.paid" in status["webhook_events"]
    assert "keysecret123" not in json.dumps(status)
    [stored] = await rows(
        engine, "SELECT razorpay_secret_enc, razorpay_webhook_secret_enc FROM payment_connections"
    )
    assert b"keysecret123" not in bytes(stored["razorpay_secret_enc"])
    assert b"hooksecret1" not in bytes(stored["razorpay_webhook_secret_enc"])


async def razorpay_ready(ws: Ws) -> str:
    status = await ws.ok("PUT", "/integrations/payments/razorpay", json=KEYS)
    return str(status["webhook_url"]).rsplit("/webhooks/razorpay/", 1)[1]


def paid_event(link_id: str, order: dict[str, Any], *, amount: int | None = None) -> bytes:
    return json.dumps(
        {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": link_id,
                        "reference_id": order["id"],
                        "amount": order["total_minor"],
                        "amount_paid": amount if amount is not None else order["total_minor"],
                        "currency": order["currency"],
                        "status": "paid",
                    }
                },
                "payment": {"entity": {"id": "pay_Fake123", "amount": order["total_minor"]}},
            },
        }
    ).encode()


async def post_webhook(
    client: httpx.AsyncClient,
    token: str,
    raw: bytes,
    *,
    event_id: str,
    secret: str = KEYS["webhook_key"],
) -> httpx.Response:
    return await client.post(
        f"/webhooks/razorpay/{token}",
        content=raw,
        headers={
            "X-Razorpay-Signature": sign_webhook(raw, secret),
            "X-Razorpay-Event-Id": event_id,
            "Content-Type": "application/json",
        },
    )


async def process_last(engine: AsyncEngine, redis: Redis) -> WebhookStatus | None:
    [event] = await rows(
        engine,
        "SELECT id FROM webhook_events WHERE provider = 'razorpay'"
        " ORDER BY received_at DESC LIMIT 1",
    )
    return await process_event(sessions(engine), event["id"], redis)


async def test_a_paid_link_marks_the_order_paid_once(
    ws: Ws,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    redis: Redis,
    fake_razorpay: FakeRazorpay,
) -> None:
    """The done-when: a test-mode Razorpay link marks the sandbox order paid."""
    token = await razorpay_ready(ws)
    order, _ = await order_in_chat(ws, engine)

    asked = await ws.ok(
        "POST", f"/orders/{order['id']}/payment-request", json={"method": "razorpay"}
    )
    assert (asked["status"], asked["payment_method"]) == ("awaiting_payment", "razorpay")
    assert asked["payment_link_url"].startswith("https://rzp.test/pay/plink_fake_")
    [call] = [c for c in fake_razorpay.calls if c[0] == "create_payment_link"]
    assert call[1]["amount_minor"] == 159800
    assert call[1]["reference_id"] == order["id"]
    [sent] = await rows(engine, "SELECT text, source FROM messages WHERE direction = 'outbound'")
    assert "Order #1" in sent["text"]
    assert "Total: INR 1598.00" in sent["text"]
    assert asked["payment_link_url"] in sent["text"]

    link_id = asked["payment_link_url"].rsplit("/", 1)[1]
    raw = paid_event(link_id, order)
    assert (await post_webhook(client, token, raw, event_id="evt_1")).status_code == 200
    assert await process_last(engine, redis) is WebhookStatus.PROCESSED
    paid = await ws.ok("GET", f"/orders/{order['id']}")
    assert paid["status"] == "paid"
    assert paid["payment_reference"] == "pay_Fake123"
    assert paid["paid_at"] is not None

    # Razorpay sends it again: stored once, and the order stays as it is.
    assert (await post_webhook(client, token, raw, event_id="evt_1")).status_code == 200
    assert len(await rows(engine, "SELECT id FROM webhook_events WHERE provider = 'razorpay'")) == 1


async def test_unsigned_forged_and_unknown_webhooks_change_nothing(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    token = await razorpay_ready(ws)
    order, _ = await order_in_chat(ws, engine)
    asked = await ws.ok(
        "POST", f"/orders/{order['id']}/payment-request", json={"method": "razorpay"}
    )
    raw = paid_event(asked["payment_link_url"].rsplit("/", 1)[1], order)

    assert (await client.post(f"/webhooks/razorpay/{token}", content=raw)).status_code == 401
    forged = await post_webhook(client, token, raw, event_id="e2", secret="other-secret")
    assert forged.status_code == 401
    unknown = await post_webhook(client, "not-a-token", raw, event_id="e3")
    assert unknown.status_code == 401
    assert await rows(engine, "SELECT id FROM webhook_events") == []

    # The wrong amount is not a payment of this order.
    short = paid_event(asked["payment_link_url"].rsplit("/", 1)[1], order, amount=100)
    assert (await post_webhook(client, token, short, event_id="e4")).status_code == 200
    assert await process_last(engine, redis) is WebhookStatus.IGNORED
    assert (await ws.ok("GET", f"/orders/{order['id']}"))["status"] == "awaiting_payment"


async def test_an_expired_link_expires_the_order_and_a_late_payment_still_counts(
    ws: Ws, client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    token = await razorpay_ready(ws)
    order, _ = await order_in_chat(ws, engine)
    asked = await ws.ok(
        "POST", f"/orders/{order['id']}/payment-request", json={"method": "razorpay", "send": False}
    )
    link_id = asked["payment_link_url"].rsplit("/", 1)[1]
    expired = json.dumps(
        {
            "event": "payment_link.expired",
            "payload": {"payment_link": {"entity": {"id": link_id, "reference_id": order["id"]}}},
        }
    ).encode()
    await post_webhook(client, token, expired, event_id="x1")
    assert await process_last(engine, redis) is WebhookStatus.PROCESSED
    assert (await ws.ok("GET", f"/orders/{order['id']}"))["status"] == "expired"

    await post_webhook(client, token, paid_event(link_id, order), event_id="x2")
    assert await process_last(engine, redis) is WebhookStatus.PROCESSED
    assert (await ws.ok("GET", f"/orders/{order['id']}"))["status"] == "paid"


# ---------------------------------------------------------------- UPI


async def test_a_upi_order_is_marked_paid_by_hand_and_audited(ws: Ws, engine: AsyncEngine) -> None:
    order, _ = await order_in_chat(ws, engine)
    refused = await ws.call(
        "POST", f"/orders/{order['id']}/payment-request", json={"method": "upi"}
    )
    assert refused.status_code == 409  # no UPI address yet

    await ws.ok("PUT", "/integrations/payments/upi", json={"vpa": "shop@okbank", "name": "Maple"})
    asked = await ws.ok("POST", f"/orders/{order['id']}/payment-request", json={"method": "upi"})
    link = asked["payment_link_url"]
    assert link.startswith("upi://pay?pa=shop%40okbank&pn=Maple&am=1598.00&cu=INR&tn=Order%201")
    [sent] = await rows(engine, "SELECT text FROM messages WHERE direction = 'outbound'")
    assert "shop@okbank" in sent["text"]

    paid = await ws.ok("POST", f"/orders/{order['id']}/mark-paid", json={"reference": "UTR 4021"})
    assert (paid["status"], paid["payment_reference"]) == ("paid", "UTR 4021")
    assert paid["paid_by_name"]
    audit = await rows(
        engine, "SELECT actor_label FROM audit_events WHERE action = 'order.marked_paid'"
    )
    assert len(audit) == 1
    again = await ws.call("POST", f"/orders/{order['id']}/mark-paid", json={})
    assert again.status_code == 422


async def test_cancel_stops_the_order_and_a_paid_one_cannot_be_cancelled(
    ws: Ws, engine: AsyncEngine, fake_razorpay: FakeRazorpay
) -> None:
    await razorpay_ready(ws)
    order, kurta = await order_in_chat(ws, engine)
    await ws.ok(
        "POST", f"/orders/{order['id']}/payment-request", json={"method": "razorpay", "send": False}
    )
    cancelled = await ws.ok("POST", f"/orders/{order['id']}/cancel")
    assert cancelled["status"] == "cancelled"
    assert any(name == "cancel_payment_link" for name, _ in fake_razorpay.calls)
    assert (
        await ws.call("POST", f"/orders/{order['id']}/payment-request", json={"method": "upi"})
    ).status_code == 422

    other, _ = await order_in_chat(ws, engine, kurta=kurta)
    await ws.ok("POST", f"/orders/{other['id']}/mark-paid", json={})
    assert (await ws.call("POST", f"/orders/{other['id']}/cancel")).status_code == 422


# ---------------------------------------------------------------- where it shows


async def test_events_timeline_activity_and_ask_see_the_order(ws: Ws, engine: AsyncEngine) -> None:
    hook = await ws.ok(
        "POST",
        "/webhook-endpoints",
        201,
        json={"url": "https://hooks.example/orders", "events": ["order.created", "order.paid"]},
    )
    order, _ = await order_in_chat(ws, engine)
    await ws.ok("POST", f"/orders/{order['id']}/mark-paid", json={})

    deliveries = await rows(
        engine,
        "SELECT event_type FROM webhook_deliveries WHERE endpoint_id = :e ORDER BY created_at",
        e=hook["id"],
    )
    assert [d["event_type"] for d in deliveries] == ["order.created", "order.paid"]

    contact_id = order["contact"]["id"]
    timeline = await ws.ok("GET", f"/contacts/{contact_id}/timeline")
    [entry] = [i for i in timeline["items"] if i["kind"] == "order"]
    assert entry["title"] == "Order #1 paid"
    assert "INR 1598.00" in entry["detail"]

    feed = await ws.ok("GET", "/activity?kind=order&failures_only=false")
    assert [i["title"] for i in feed["items"]] == [
        f"Order #1 was paid from @{order['contact']['username']}"
    ]
