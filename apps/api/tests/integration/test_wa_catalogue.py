"""GR-33: WhatsApp catalogue messages on the sandbox number and the sandbox Meta catalogue.

Connecting a catalogue (Pro and Max, PD-8; Meta must show it to the number), the sync (what is
sent, only what changed, deletes, what can't be sent and why), product and product-list messages
from the inbox, the flow step's native message and its text fallback, and a customer's cart
becoming an order awaiting payment."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks import send as send_tasks
from socialhood.metacatalog.client import CatalogueError
from socialhood.metacatalog.fake import FakeCatalogue
from socialhood.models.inbox import Conversation
from socialhood.platforms.sandbox import outbox
from socialhood.security.crypto import cipher_for
from socialhood.services.catalogue import wa_catalogue, wa_send
from socialhood.services.catalogue.products import ProductData, VariantData
from tests.support.api import Clerk
from tests.support.automation_api import workspace
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


async def connect(desk: Shop, catalog_id: str = "cat-1") -> dict[str, Any]:
    return await desk.ws.ok(
        "PUT",
        "/integrations/whatsapp-catalogue",
        json={"social_account_id": desk.ws.account_id, "catalog_id": catalog_id},
    )


async def sync(desk: Shop) -> str:
    """One pass of the sync job, as the worker runs it."""
    settings = desk.app.state.settings
    with workspace_scope(uuid.UUID(desk.ws.wid)):
        return await wa_catalogue.run_sync(
            make_sessionmaker(desk.engine),
            desk.app.state.http,
            settings,
            cipher_for(tuple(settings.token_encryption_keys)),
            now=datetime.now(UTC),
        )


async def synced(desk: Shop) -> None:
    await connect(desk)
    assert await sync(desk) == "done"


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
        json={"social_account_id": free.account_id, "catalog_id": "cat-1"},
    )
    assert refused.status_code == 402
    assert refused.json()["entitlement"] == "commerce"


async def test_connecting_checks_the_catalogue_with_meta(desk: Shop) -> None:
    for catalog_id in ("missing", "denied"):
        refused = await desk.ws.call(
            "PUT",
            "/integrations/whatsapp-catalogue",
            json={"social_account_id": desk.ws.account_id, "catalog_id": catalog_id},
        )
        assert refused.status_code == 409, catalog_id
    status = await connect(desk)
    assert (status["connected"], status["status"], status["catalog_id"]) == (
        True,
        "active",
        "cat-1",
    )
    assert status["catalog_name"] == "Sandbox catalogue cat-1"
    assert status["brand"]  # the workspace's name unless one is given


async def test_meta_not_answering_is_a_502_and_saves_nothing(
    desk: Shop, fake_catalogue: FakeCatalogue
) -> None:
    fake_catalogue.fail_next(CatalogueError("unavailable"))
    refused = await desk.ws.call(
        "PUT",
        "/integrations/whatsapp-catalogue",
        json={"social_account_id": desk.ws.account_id, "catalog_id": "cat-1"},
    )
    assert refused.status_code == 502
    assert (await desk.ws.ok("GET", "/integrations/whatsapp-catalogue"))["connected"] is False


# ---------------------------------------------------------------- the sync


async def test_the_sync_sends_one_item_per_variant_and_only_what_changed(
    desk: Shop, fake_catalogue: FakeCatalogue
) -> None:
    made = await kurta(desk)
    await synced(desk)

    held = fake_catalogue.items["cat-1"]
    assert set(held) == {str(v) for v in made.variants.values()}
    medium = held[str(made.variants["Blue / M"])]
    assert (medium["title"], medium["price"], medium["availability"]) == (
        "Cotton kurta - Blue / M",
        "799.00 INR",
        "in stock",
    )
    assert held[str(made.variants["Blue / L"])]["availability"] == "out of stock"
    status = await desk.ws.ok("GET", "/integrations/whatsapp-catalogue")
    assert (status["items_synced"], status["items_error"], status["items_pending"]) == (4, 0, 0)
    assert status["synced_at"] is not None

    # Nothing changed: nothing is sent.
    pushes = len([c for c in fake_catalogue.calls if c[0] == "push"])
    assert await sync(desk) == "done"
    assert len([c for c in fake_catalogue.calls if c[0] == "push"]) == pushes

    # One price changes: only that item goes.
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
    assert await sync(desk) == "done"
    last = [c for c in fake_catalogue.calls if c[0] == "push"][-1]
    assert last[1]["count"] == 1  # only Blue / M
    assert fake_catalogue.items["cat-1"][str(made.variants["Blue / M"])]["price"] == "899.00 INR"


async def test_a_deleted_or_switched_off_product_is_deleted_from_the_catalogue(
    desk: Shop, fake_catalogue: FakeCatalogue
) -> None:
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
    await synced(desk)
    assert len(fake_catalogue.items["cat-1"]) == 5

    await desk.ws.ok("PATCH", f"/products/{made.id}", json={"active": False})
    await desk.ws.ok("DELETE", f"/products/{scarf.id}", 204)
    assert await sync(desk) == "done"
    assert fake_catalogue.items["cat-1"] == {}
    assert (await desk.ws.ok("GET", "/integrations/whatsapp-catalogue"))["items_synced"] == 0


async def test_an_item_that_cannot_be_sent_says_why(
    desk: Shop, fake_catalogue: FakeCatalogue
) -> None:
    await make_product(desk.engine, workspace_id=desk.ws.wid, url=None, image_url=PICTURE)
    await synced(desk)
    assert fake_catalogue.items.get("cat-1", {}) == {}
    status = await desk.ws.ok("GET", "/integrations/whatsapp-catalogue")
    assert status["items_error"] == 4
    assert status["problems"][0]["message"] == wa_catalogue.NO_LINK


async def test_meta_refusing_the_token_asks_for_attention(
    desk: Shop, fake_catalogue: FakeCatalogue
) -> None:
    await kurta(desk)
    await connect(desk)
    fake_catalogue.fail_next(CatalogueError("auth"))
    assert await sync(desk) == "reconnect"
    status = await desk.ws.ok("GET", "/integrations/whatsapp-catalogue")
    assert status["status"] == "needs_reconnect"
    assert status["sync_error"]
    assert (await desk.ws.call("POST", "/integrations/whatsapp-catalogue/sync")).status_code == 409


async def test_disconnecting_forgets_the_connection(desk: Shop) -> None:
    await kurta(desk)
    await synced(desk)
    await desk.ws.ok("DELETE", "/integrations/whatsapp-catalogue", 204)
    status = await desk.ws.ok("GET", "/integrations/whatsapp-catalogue")
    assert status["connected"] is False
    assert await desk.rows("SELECT id FROM catalogue_items") == []


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
        "catalog_id": "cat-1",
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
    await connect(desk)  # connected, not yet synced
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
    assert message["text"].startswith("Sent an order of 3 items")
    assert "Order #1" in message["text"]


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
