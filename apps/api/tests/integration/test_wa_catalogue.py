"""GR-33 and C-215: the WhatsApp catalogue on the sandbox number.

Connecting a catalogue (Pro and Max, PD-8; Meta isn't asked), the feed Meta fetches (Meta's
data-file format, one row per variant, what can't be in it and why, the secret link, the plan),
product and product-list messages from the inbox (only items Meta fetched), the flow step's native
message and its text fallback, and a customer's cart becoming an order awaiting payment."""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks import send as send_tasks
from socialhood.models.inbox import Conversation
from socialhood.platforms.sandbox import outbox
from socialhood.services.catalogue import wa_catalogue, wa_send
from socialhood.services.catalogue.products import ProductData, VariantData
from socialhood.services.orders import orders as orders_service
from tests.support.ai import FakeProvider
from tests.support.api import Clerk
from tests.support.automation_api import workspace
from tests.support.billing import set_subscription
from tests.support.broadcasts import Shop, shop
from tests.support.catalogue import Made, make_product
from tests.support.sending import clean_outbox, context

PICTURE = "https://cdn.example/kurta.jpg"


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def desk(
    client: Any,
    clerk: Clerk,
    app: FastAPI,
    engine: AsyncEngine,
    redis: Redis,
    queue: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Shop:
    return await shop(client, clerk, app, engine, redis, monkeypatch)


async def kurta(desk: Shop) -> Made:
    """The cotton kurta with a picture, so every variant can be sent."""
    return await make_product(desk.engine, workspace_id=desk.ws.wid, image_url=PICTURE)


CATALOG = "1555280009762482"


async def connect(desk: Shop, catalog_id: str = CATALOG) -> dict[str, Any]:
    return await desk.ws.ok(
        "PUT",
        "/integrations/whatsapp-catalogue",
        json={"social_account_id": desk.ws.account_id, "catalog_id": catalog_id},
    )


def feed_path(status: dict[str, Any]) -> str:
    return urlsplit(status["feed_url"]).path


async def fetch(desk: Shop, path: str) -> httpx.Response:
    """Meta's fetch of the feed: no sign-in, only the link."""
    return await desk.ws.client.get(path)


def rows_of(response: httpx.Response) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(response.text)))


async def synced(desk: Shop) -> dict[str, Any]:
    """Connected, and Meta has fetched the feed once."""
    status = await connect(desk)
    assert (await fetch(desk, feed_path(status))).status_code == 200
    return status


# ---------------------------------------------------------------- the plan and the connection


async def test_free_reads_the_status_but_cannot_connect(
    client: Any, clerk: Clerk, engine: AsyncEngine, queue: None
) -> None:
    free = await workspace(client, clerk)
    status = await free.ok("GET", "/integrations/whatsapp-catalogue")
    assert (status["entitled"], status["connected"]) == (False, False)
    refused = await free.call(
        "PUT",
        "/integrations/whatsapp-catalogue",
        json={"social_account_id": free.account_id, "catalog_id": CATALOG},
    )
    assert refused.status_code == 402
    assert refused.json()["entitlement"] == "commerce"


async def test_connecting_saves_the_id_without_meta_and_makes_a_feed_link(desk: Shop) -> None:
    refused = await desk.ws.call(
        "PUT",
        "/integrations/whatsapp-catalogue",
        json={"social_account_id": desk.ws.account_id, "catalog_id": "SAR-001"},
    )
    assert refused.status_code == 422  # a product code, not Meta's catalogue id
    status = await connect(desk)
    assert (status["connected"], status["catalog_id"]) == (True, CATALOG)
    assert status["brand"]  # the workspace's name unless one is given
    assert status["feed_url"].endswith(".csv")
    assert status["feed_fetched_at"] is None
    # Connecting again keeps the link Meta was given.
    assert (await connect(desk))["feed_url"] == status["feed_url"]


async def test_the_feed_is_meta_s_format_one_row_per_variant_and_records_the_fetch(
    desk: Shop,
) -> None:
    made = await kurta(desk)
    status = await connect(desk)
    assert (status["items_synced"], status["items_pending"]) == (0, 4)

    response = await fetch(desk, feed_path(status))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.splitlines()[0] == ",".join(wa_catalogue.FEED_COLUMNS)
    rows = {row["id"]: row for row in rows_of(response)}
    assert set(rows) == {str(v) for v in made.variants.values()}
    medium = rows[str(made.variants["Blue / M"])]
    assert (medium["title"], medium["price"], medium["availability"], medium["condition"]) == (
        "Cotton kurta - Blue / M",
        "799.00 INR",
        "in stock",
        "new",
    )
    assert (medium["image_link"], medium["item_group_id"]) == (PICTURE, str(made.id))
    assert rows[str(made.variants["Blue / L"])]["availability"] == "out of stock"
    status = await desk.ws.ok("GET", "/integrations/whatsapp-catalogue")
    assert (status["items_synced"], status["items_pending"], status["items_error"]) == (4, 0, 0)
    assert status["feed_fetched_at"] is not None

    # One price changes: that item waits for Meta's next fetch.
    await desk.ws.ok(
        "PATCH",
        f"/products/{made.id}",
        json={
            "variants": [
                {"id": str(made.variants[t]), "title": t, "price": price, "stock": stock}
                for t, price, stock in [  # stock is sent too: leaving it out would clear it
                    ("Blue / S", "799", 4),
                    ("Blue / M", "899", 12),
                    ("Blue / L", "849", 0),
                    ("Red / M", "799", None),
                ]
            ]
        },
    )
    status = await desk.ws.ok("GET", "/integrations/whatsapp-catalogue")
    assert (status["items_synced"], status["items_pending"]) == (4, 1)
    again = rows_of(await fetch(desk, feed_path(status)))
    assert {r["id"]: r["price"] for r in again}[str(made.variants["Blue / M"])] == "899.00 INR"
    status = await desk.ws.ok("GET", "/integrations/whatsapp-catalogue")
    assert status["items_pending"] == 0


async def test_a_deleted_or_switched_off_product_leaves_the_feed(desk: Shop) -> None:
    made = await kurta(desk)
    scarf = await make_product(
        desk.engine,
        workspace_id=desk.ws.wid,
        data=ProductData(
            name="Silk scarf",
            price_minor=49900,
            url="https://maple.example/scarf",
            image_url=PICTURE,
            variants=[VariantData("One size", 49900)],
        ),
    )
    status = await synced(desk)
    assert (await desk.ws.ok("GET", "/integrations/whatsapp-catalogue"))["items_synced"] == 5

    await desk.ws.ok("PATCH", f"/products/{made.id}", json={"active": False})
    await desk.ws.ok("DELETE", f"/products/{scarf.id}", 204)
    assert rows_of(await fetch(desk, feed_path(status))) == []
    assert (await desk.ws.ok("GET", "/integrations/whatsapp-catalogue"))["items_synced"] == 0


async def test_a_product_that_cannot_be_in_the_feed_says_why(desk: Shop) -> None:
    await make_product(desk.engine, workspace_id=desk.ws.wid, url=None, image_url=PICTURE)
    status = await synced(desk)
    assert rows_of(await fetch(desk, feed_path(status))) == []
    status = await desk.ws.ok("GET", "/integrations/whatsapp-catalogue")
    assert (status["items_error"], status["items_pending"]) == (4, 0)
    assert status["problems"][0]["message"] == wa_catalogue.NO_LINK


async def test_the_link_is_the_only_key_and_a_new_link_replaces_it(desk: Shop) -> None:
    await kurta(desk)
    status = await connect(desk)
    old = feed_path(status)
    for path in (
        "/v1/feeds/whatsapp-catalogue/short.csv",
        "/v1/feeds/whatsapp-catalogue/" + "x" * 43 + ".csv",
    ):
        assert (await fetch(desk, path)).status_code == 404, path

    renewed = await desk.ws.ok("POST", "/integrations/whatsapp-catalogue/feed-link")
    assert renewed["feed_url"] != status["feed_url"]
    assert (await fetch(desk, old)).status_code == 404
    assert (await fetch(desk, feed_path(renewed))).status_code == 200


async def test_the_feed_stops_when_the_plan_loses_commerce(desk: Shop) -> None:
    await kurta(desk)
    status = await synced(desk)
    await set_subscription(desk.engine, workspace_id=desk.ws.wid, plan="free")
    assert (await fetch(desk, feed_path(status))).status_code == 404  # Meta keeps what it has
    status = await desk.ws.ok("GET", "/integrations/whatsapp-catalogue")
    assert status["last_error"] == wa_catalogue.PLAN_STOPPED
    assert status["items_synced"] == 4


async def test_another_catalogue_starts_empty(desk: Shop) -> None:
    await kurta(desk)
    await synced(desk)
    status = await connect(desk, catalog_id="2000000000000001")
    assert (status["items_synced"], status["items_pending"], status["feed_fetched_at"]) == (
        0,
        4,
        None,
    )


async def test_disconnecting_forgets_the_connection_and_its_link(desk: Shop) -> None:
    await kurta(desk)
    status = await synced(desk)
    await desk.ws.ok("DELETE", "/integrations/whatsapp-catalogue", 204)
    assert (await desk.ws.ok("GET", "/integrations/whatsapp-catalogue"))["connected"] is False
    assert await desk.rows("SELECT id FROM catalogue_items") == []
    assert (await fetch(desk, feed_path(status))).status_code == 404


# ---------------------------------------------------------------- sending


async def customer_conversation(desk: Shop) -> str:
    person = await desk.customer("Asha Rao")
    return str(person.conversation_id)


async def test_a_product_message_goes_out_as_meta_s_interactive_message(desk: Shop) -> None:
    made = await kurta(desk)
    await synced(desk)
    conversation = await customer_conversation(desk)

    queued = await desk.ws.ok(
        "POST",
        f"/conversations/{conversation}/product-message",
        202,
        json={
            "kind": "product",
            "body": "This one in blue?",
            "item": {
                "product_id": str(made.id),
                "variant_id": str(made.variants["Blue / M"]),
            },
        },
    )
    assert queued["text"] == "This one in blue?"
    await send_tasks.send_message(
        context(),
        message_id=queued["id"],
        conversation_id=conversation,
        workspace_id=desk.ws.wid,
    )
    [sent] = outbox.SENT
    assert sent.message.text == "This one in blue?"
    assert sent.message.products is not None
    assert sent.message.products.retailer_id == str(made.variants["Blue / M"])
    [row] = await desk.rows("SELECT interactive FROM messages WHERE id = :m", m=queued["id"])
    assert row["interactive"] == {
        "type": "product",
        "catalog_id": CATALOG,
        "retailer_id": str(made.variants["Blue / M"]),
    }


async def test_a_product_list_has_sections_and_needs_a_header(desk: Shop) -> None:
    made = await kurta(desk)
    await synced(desk)
    conversation = await customer_conversation(desk)
    items = lambda *titles: [  # noqa: E731
        {"product_id": str(made.id), "variant_id": str(made.variants[t])} for t in titles
    ]
    path = f"/conversations/{conversation}/product-message"
    body = {
        "kind": "product_list",
        "body": "Have a look",
        "header": "Our kurtas",
        "sections": [
            {"title": "Blue", "items": items("Blue / S", "Blue / M")},
            {"title": "Red", "items": items("Red / M")},
        ],
    }
    queued = await desk.ws.ok("POST", path, 202, json=body)
    [row] = await desk.rows("SELECT interactive FROM messages WHERE id = :m", m=queued["id"])
    assert row["interactive"]["type"] == "product_list"
    assert [s["title"] for s in row["interactive"]["sections"]] == ["Blue", "Red"]
    assert len(row["interactive"]["sections"][0]["retailer_ids"]) == 2

    headless = await desk.ws.call("POST", path, json={**body, "header": None})
    assert headless.status_code == 422


async def test_an_item_not_in_the_catalogue_yet_is_refused_by_name(desk: Shop) -> None:
    made = await kurta(desk)
    await connect(desk)  # connected; Meta hasn't fetched the feed yet
    conversation = await customer_conversation(desk)
    refused = await desk.ws.call(
        "POST",
        f"/conversations/{conversation}/product-message",
        json={
            "kind": "product",
            "body": "This one?",
            "item": {"product_id": str(made.id), "variant_id": str(made.variants["Blue / M"])},
        },
    )
    assert refused.status_code == 422
    assert "isn't in the WhatsApp catalogue yet" in refused.text


async def test_a_message_with_no_catalogue_connected_is_refused(desk: Shop) -> None:
    made = await kurta(desk)
    conversation = await customer_conversation(desk)
    body = {
        "kind": "product",
        "body": "This one?",
        "item": {"product_id": str(made.id), "variant_id": str(made.variants["Blue / M"])},
    }
    path = f"/conversations/{conversation}/product-message"
    assert (await desk.ws.call("POST", path, json=body)).status_code == 409


# ---------------------------------------------------------------- the flow step


async def test_the_flow_step_is_native_when_it_can_be_and_text_otherwise(desk: Shop) -> None:
    made = await kurta(desk)
    person = await desk.customer("Asha Rao")

    async def native(variant: str | None) -> wa_send.Native | None:
        async with AsyncSession(desk.engine, expire_on_commit=False) as session:
            with workspace_scope(uuid.UUID(desk.ws.wid)):
                conv = await session.get(Conversation, person.conversation_id)
                assert conv is not None
                return await wa_send.native_for_step(
                    session, conv, made.id, made.variants[variant] if variant else None, "Here:"
                )

    assert await native("Blue / M") is None  # no catalogue connected: the text and link go
    await synced(desk)
    one = await native("Blue / M")
    assert one is not None
    assert (one.text, one.interactive["type"]) == ("Here:", "product")
    everything = await native(None)
    assert everything is not None
    assert everything.interactive["type"] == "product_list"
    assert len(everything.interactive["sections"][0]["retailer_ids"]) == 4


# ---------------------------------------------------------------- a customer's cart


async def test_a_cart_becomes_an_order_awaiting_payment(desk: Shop) -> None:
    made = await kurta(desk)
    person = await desk.customer("Asha Rao")
    medium, small = str(made.variants["Blue / M"]), str(made.variants["Blue / S"])

    sent = await desk.inject(
        kind="order",
        from_id=person.wa_id,
        text="Gift wrap please",
        cart=[
            {"retailer_id": medium, "quantity": 2, "price": "799.00"},
            {"retailer_id": small, "quantity": 1, "price": "700.00"},  # the price changed
            {"retailer_id": str(uuid.uuid4()), "quantity": 1},  # not ours
        ],
    )
    assert sent.status_code == 200, sent.text
    await desk.process_webhooks()

    orders = (await desk.ws.ok("GET", "/orders"))["items"]
    [order] = orders
    assert (order["status"], order["source"], order["number"]) == (
        "awaiting_payment",
        "whatsapp",
        1,
    )
    assert order["total_minor"] == 2 * 79900 + 79900
    assert [(i["variant_title"], i["quantity"]) for i in order["items"]] == [
        ("Blue / M", 2),
        ("Blue / S", 1),
    ]
    assert "Gift wrap please" in order["note"]
    assert "1 item in the cart wasn't available" in order["note"]
    assert "Some prices changed" in order["note"]
    [message] = await desk.rows(
        "SELECT text FROM messages WHERE direction = 'inbound' ORDER BY created_at DESC LIMIT 1"
    )
    assert message["text"].startswith("Order #1: 3 items, ")  # the inbox list and search
    # C-218: the inbox shows the message as the order's card.
    listed = await desk.ws.ok("GET", f"/conversations/{person.conversation_id}/messages")
    [cart] = [m for m in listed["items"] if m["order"]]
    assert cart["order"] == {"id": order["id"], "number": 1}


async def test_a_cart_with_nothing_orderable_makes_no_order(desk: Shop) -> None:
    person = await desk.customer("Asha Rao")
    await desk.inject(
        kind="order", from_id=person.wa_id, cart=[{"retailer_id": str(uuid.uuid4()), "quantity": 1}]
    )
    await desk.process_webhooks()
    assert (await desk.ws.ok("GET", "/orders"))["items"] == []
    [message] = await desk.rows(
        "SELECT text FROM messages WHERE direction = 'inbound' ORDER BY created_at DESC LIMIT 1"
    )
    assert message["text"] == "Sent an order of 1 item"


# ---------------------------------------------------------------- C-218: order reply, address


async def ordered(desk: Shop) -> tuple[Any, dict[str, Any]]:
    """A customer's cart of one kurta, made an order."""
    made = await kurta(desk)
    person = await desk.customer("Asha Rao")
    await desk.inject(
        kind="order",
        from_id=person.wa_id,
        cart=[{"retailer_id": str(made.variants["Blue / M"]), "quantity": 1}],
    )
    await desk.process_webhooks()
    [order] = (await desk.ws.ok("GET", "/orders"))["items"]
    return person, order


async def last_outbound(desk: Shop) -> str:
    [row] = await desk.rows(
        "SELECT text FROM messages WHERE direction = 'outbound' ORDER BY created_at DESC LIMIT 1"
    )
    return str(row["text"])


async def test_one_item_s_order_names_it(desk: Shop) -> None:
    _, order = await ordered(desk)
    [message] = await desk.rows(
        "SELECT text FROM messages WHERE direction = 'inbound' ORDER BY created_at DESC LIMIT 1"
    )
    assert message["text"].startswith("Order #1: 1 x Cotton kurta - Blue / M, ")
    [conv] = await desk.rows("SELECT last_message_preview FROM conversations")
    assert conv["last_message_preview"].startswith("Order #1: 1 x Cotton kurta")  # the list
    assert order["address"] is None


async def test_the_payment_message_asks_for_the_address_until_there_is_one(desk: Shop) -> None:
    _, order = await ordered(desk)
    await desk.ws.ok(
        "PUT", "/integrations/payments/upi", json={"vpa": "maple@okaxis", "name": "Maple"}
    )
    await desk.ws.ok(
        "POST",
        f"/orders/{order['id']}/payment-request",
        json={"method": "upi", "ask_address": True},
    )
    assert (await last_outbound(desk)).endswith(orders_service.ADDRESS_ASK)

    await desk.ws.ok(
        "PATCH",
        f"/orders/{order['id']}",
        json={"address": {"name": "Asha Rao", "line1": "12 MG Road", "pincode": "800001"}},
    )
    await desk.ws.ok(
        "POST",
        f"/orders/{order['id']}/payment-request",
        json={"method": "upi", "ask_address": True},
    )
    assert orders_service.ADDRESS_ASK not in await last_outbound(desk)


async def test_the_ai_reads_the_customer_s_reply_into_the_address(
    desk: Shop, fake_ai: FakeProvider
) -> None:
    person, order = await ordered(desk)
    await desk.inject(
        kind="dm", from_id=person.wa_id, text="Asha Rao, 12 MG Road, near City Mall, Patna 800001"
    )
    await desk.process_webhooks()
    [reply] = await desk.rows(
        "SELECT id FROM messages WHERE direction = 'inbound' ORDER BY created_at DESC LIMIT 1"
    )
    read = await desk.ws.ok(
        "POST", f"/orders/{order['id']}/address/read", json={"message_id": str(reply["id"])}
    )
    assert read["found"] is True
    assert (read["address"]["city"], read["address"]["pincode"]) == ("Patna", "800001")
    [call] = fake_ai.calls_for("address")
    assert "12 MG Road" in str(call.contents)
    # Nothing is saved until a member saves it.
    assert (await desk.ws.ok("GET", f"/orders/{order['id']}"))["address"] is None
    [usage] = await desk.rows("SELECT feature FROM ai_usage_events WHERE feature = 'address_read'")
    assert usage["feature"] == "address_read"

    # A message that holds no address comes back empty.
    fake_ai.respond("address", {"found": False})
    empty = await desk.ws.ok(
        "POST", f"/orders/{order['id']}/address/read", json={"message_id": str(reply["id"])}
    )
    assert empty["found"] is False
    assert set(empty["address"].values()) == {None}

    # Only the customer's own message in that conversation.
    for message_id in (uuid.uuid4(), order["id"]):  # unknown, or not a message at all
        refused = await desk.ws.call(
            "POST", f"/orders/{order['id']}/address/read", json={"message_id": str(message_id)}
        )
        assert refused.status_code == 422
    note = await desk.ws.ok(
        "POST",
        f"/conversations/{person.conversation_id}/messages",
        202,
        json={"text": "Thanks!", "client_id": str(uuid.uuid4())},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    refused = await desk.ws.call(
        "POST", f"/orders/{order['id']}/address/read", json={"message_id": note["id"]}
    )
    assert refused.status_code == 422  # our own message


async def test_a_paid_order_still_takes_its_address_but_not_new_lines(desk: Shop) -> None:
    """C-218: customers often pay first and send the address after."""
    _, order = await ordered(desk)
    await desk.ws.ok("POST", f"/orders/{order['id']}/mark-paid", json={"reference": "UTR 1"})
    saved = await desk.ws.ok(
        "PATCH", f"/orders/{order['id']}", json={"address": {"city": "Patna", "pincode": "800001"}}
    )
    assert (saved["status"], saved["address"]["city"]) == ("paid", "Patna")
    [line] = order["items"]
    refused = await desk.ws.call(
        "PATCH",
        f"/orders/{order['id']}",
        json={
            "items": [
                {"product_id": line["product_id"], "variant_id": line["variant_id"], "quantity": 2}
            ]
        },
    )
    assert refused.status_code == 422
    assert "paid" in refused.text.lower()  # refused for its state, not the line


async def test_a_whatsapp_customer_s_contact_has_their_phone(desk: Shop) -> None:
    """C-220: a WhatsApp id is the customer's number; the contact panel shows it as the phone."""
    await desk.inject(kind="dm", from_id="919811112222", text="Hi, is the kurta available?")
    await desk.process_webhooks()
    [contact] = await desk.rows(
        "SELECT phone, phone_source, phone_verified FROM contacts WHERE platform_user_id = :w",
        w="919811112222",
    )
    assert contact == {
        "phone": "+919811112222",
        "phone_source": "whatsapp",
        "phone_verified": True,
    }
