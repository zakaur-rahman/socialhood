"""GR-33: the pieces of the WhatsApp catalogue that need no database. What a catalogue item is made
from, the product and product-list payloads, the stored message read back, a customer's cart parsed
from the webhook, and the feed Meta fetches (C-215)."""

from __future__ import annotations

import uuid
from typing import Any

from socialhood.models.catalogue import CatalogueConnection, Product, ProductVariant
from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import OutboundMessage, OutboundProducts
from socialhood.platforms.events import InboundMessage
from socialhood.platforms.sandbox import whatsapp as sandbox_whatsapp
from socialhood.platforms.whatsapp.adapter import outbound_payload
from socialhood.platforms.whatsapp.parse import parse_event
from socialhood.platforms.whatsapp.webhooks import split_payload
from socialhood.services.catalogue import wa_catalogue, wa_send
from socialhood.services.sending import _products_of

PICTURE = "https://cdn.example/kurta.jpg"


def product(**values: Any) -> Product:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": "Cotton kurta",
        "currency": "INR",
        "price_minor": None,
        "stock": None,
        "url": "https://maple.example/kurta",
        "image_url": PICTURE,
        "description": "Soft cotton.",
    }
    return Product(**{**base, **values})


def variant(parent: Product, **values: Any) -> ProductVariant:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "product_id": parent.id,
        "title": "Blue / M",
        "price_minor": 79900,
        "stock": 12,
    }
    return ProductVariant(**{**base, **values})


# ---------------------------------------------------------------- the catalogue item


def test_a_variant_is_one_item_keyed_by_its_id() -> None:
    kurta = product()
    medium = variant(kurta)
    wanted = wa_catalogue.wanted_item(kurta, medium, brand="Maple", image_url=None)
    assert wanted.retailer_id == str(medium.id)
    assert wanted.data == {
        "id": str(medium.id),
        "title": "Cotton kurta - Blue / M",
        "description": "Soft cotton.",
        "availability": "in stock",
        "condition": "new",
        "price": "799.00 INR",
        "link": "https://maple.example/kurta",
        "image_link": PICTURE,
        "brand": "Maple",
        "item_group_id": str(kurta.id),  # Meta groups a product's variants by it
    }


def test_the_feed_is_a_header_and_one_line_per_item() -> None:
    kurta = product(description="Soft cotton.\nHand-woven, Bihar.")
    scarf = product(name="Silk scarf", price_minor=49900)
    items = [
        wa_catalogue.wanted_item(kurta, variant(kurta), brand="Maple", image_url=None),
        wa_catalogue.wanted_item(scarf, None, brand="Maple", image_url=None),
    ]
    lines = wa_catalogue.render(items).splitlines()
    assert lines[0] == ",".join(wa_catalogue.FEED_COLUMNS)
    assert len(lines) == 3  # a description's line break never splits a row
    assert '"Soft cotton. Hand-woven, Bihar."' in lines[1]
    assert lines[2].endswith(",Maple,")  # no item_group_id without variants


def test_a_product_without_variants_is_keyed_by_its_own_id() -> None:
    scarf = product(name="Silk scarf", price_minor=49900, description=None)
    wanted = wa_catalogue.wanted_item(scarf, None, brand="Maple", image_url=None)
    assert wanted.retailer_id == str(scarf.id)
    assert wanted.data is not None
    assert (wanted.data["title"], wanted.data["description"]) == ("Silk scarf", "Silk scarf")
    assert wanted.data["price"] == "499.00 INR"


def test_stock_decides_availability_only_when_it_is_recorded() -> None:
    kurta = product()
    out = wa_catalogue.wanted_item(kurta, variant(kurta, stock=0), brand="B", image_url=None)
    unknown = wa_catalogue.wanted_item(kurta, variant(kurta, stock=None), brand="B", image_url=None)
    assert out.data is not None
    assert unknown.data is not None
    assert (out.data["availability"], unknown.data["availability"]) == ("out of stock", "in stock")


def test_an_uploaded_picture_wins_and_a_missing_link_or_picture_says_so() -> None:
    kurta = product()
    uploaded = wa_catalogue.wanted_item(
        kurta, variant(kurta), brand="B", image_url="https://res.example/up.jpg"
    )
    assert uploaded.data is not None
    assert uploaded.data["image_link"] == "https://res.example/up.jpg"
    no_link = wa_catalogue.wanted_item(
        product(url=None, price_minor=100), None, brand="B", image_url=None
    )
    assert (no_link.data, no_link.error) == (None, wa_catalogue.NO_LINK)
    plain = product(price_minor=100, image_url=None)
    no_picture = wa_catalogue.wanted_item(plain, None, brand="B", image_url=None)
    assert (no_picture.data, no_picture.error) == (None, wa_catalogue.NO_PICTURE)
    no_price = wa_catalogue.wanted_item(product(), None, brand="B", image_url=None)
    assert no_price.error == "Add a price to this product."


def test_the_digest_changes_with_the_content_only() -> None:
    kurta = product()
    medium = variant(kurta)
    first = wa_catalogue.wanted_item(kurta, medium, brand="B", image_url=None)
    again = wa_catalogue.wanted_item(kurta, medium, brand="B", image_url=None)
    medium.price_minor = 84900
    changed = wa_catalogue.wanted_item(kurta, medium, brand="B", image_url=None)
    assert first.digest == again.digest
    assert first.digest != changed.digest


# ---------------------------------------------------------------- the messages


def connection() -> CatalogueConnection:
    return CatalogueConnection(catalog_id="cat-1", brand="Maple")


def test_interactive_json_round_trips_to_the_outbound_message() -> None:
    conn = connection()
    stored = wa_send.interactive_of(
        "product_list",
        conn,
        header="Our kurtas",
        footer=" Free delivery ",
        sections=[("Blue", ["v1", "v2"]), ("Red", ["v3"])],
    )
    assert stored["footer"] == "Free delivery"
    products = _products_of(stored)
    assert products == OutboundProducts(
        type="product_list",
        catalog_id="cat-1",
        header="Our kurtas",
        footer="Free delivery",
        sections=(("Blue", ("v1", "v2")), ("Red", ("v3",))),
    )
    single = _products_of(wa_send.interactive_of("product", conn, retailer_id="v9"))
    assert (single.type, single.retailer_id) == ("product", "v9")


def test_a_product_message_is_meta_s_interactive_product() -> None:
    message = OutboundMessage(
        text="This one?",
        products=OutboundProducts(type="product", catalog_id="cat-1", retailer_id="v1"),
    )
    assert outbound_payload("919812345678", message) == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "919812345678",
        "type": "interactive",
        "interactive": {
            "type": "product",
            "body": {"text": "This one?"},
            "action": {"catalog_id": "cat-1", "product_retailer_id": "v1"},
        },
    }


def test_a_product_list_has_a_header_sections_and_items() -> None:
    message = OutboundMessage(
        text="Have a look",
        products=OutboundProducts(
            type="product_list",
            catalog_id="cat-1",
            header="Kurtas",
            footer="Free delivery",
            sections=(("Blue", ("v1", "v2")),),
        ),
    )
    interactive = outbound_payload("919812345678", message)["interactive"]
    assert interactive == {
        "type": "product_list",
        "header": {"type": "text", "text": "Kurtas"},
        "body": {"text": "Have a look"},
        "footer": {"text": "Free delivery"},
        "action": {
            "catalog_id": "cat-1",
            "sections": [
                {
                    "title": "Blue",
                    "product_items": [
                        {"product_retailer_id": "v1"},
                        {"product_retailer_id": "v2"},
                    ],
                }
            ],
        },
    }


# ---------------------------------------------------------------- a customer's cart


def inbound(items: list[tuple[str, int, str | None]], note: str | None = None) -> InboundMessage:
    account = SocialAccount(platform="whatsapp", platform_account_id="sandbox_1")
    payload = sandbox_whatsapp.order(
        account, sender="919812345678", name="Priya", note=note, items=items
    )
    [event] = [parse_event(e.payload) for e in split_payload(payload)]
    assert isinstance(event, InboundMessage)
    return event


def test_an_order_message_carries_the_cart_and_reads_as_text() -> None:
    event = inbound([("v1", 2, "799.00"), ("v2", 1, None)], note="Gift wrap please")
    assert event.kind == "text"
    assert event.text == "Sent an order of 3 items. Gift wrap please"
    assert event.order is not None
    assert event.order.note == "Gift wrap please"
    assert [(i.retailer_id, i.quantity, i.price) for i in event.order.items] == [
        ("v1", 2, "799.00"),
        ("v2", 1, "0"),
    ]


def test_a_cart_drops_lines_it_cannot_read() -> None:
    account = SocialAccount(platform="whatsapp", platform_account_id="sandbox_1")
    payload = sandbox_whatsapp.order(
        account, sender="919812345678", name="Priya", note=None, items=[("v1", 1, "5")]
    )
    order = payload["entry"][0]["changes"][0]["value"]["messages"][0]["order"]
    order["product_items"] += [
        {"product_retailer_id": "v2", "quantity": "x"},
        {"quantity": 1},
        {"product_retailer_id": "v3", "quantity": "3", "item_price": 10, "currency": "INR"},
    ]
    [event] = [parse_event(e.payload) for e in split_payload(payload)]
    assert isinstance(event, InboundMessage)
    assert event.order is not None
    assert [(i.retailer_id, i.quantity) for i in event.order.items] == [("v1", 1), ("v3", 3)]
