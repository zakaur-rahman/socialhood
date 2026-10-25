"""GR-31: Shopify. The store address, the two signatures, the two product shapes, the mapping to
catalogue data, the built-in store and the flow's "send product" step. Everything Shopify-side is
unverified against a real store (docs/CONFLICTS.md, C-116); these pin what the code assumes."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from socialhood.schemas.flows import FlowDefinition, ProductStep
from socialhood.services.automations import flows
from socialhood.services.catalogue import shopify as service
from socialhood.shopify import parse, signatures
from socialhood.shopify.client import ShopifyError, normalize_shop, numeric_id
from socialhood.shopify.fake import CODE_PREFIX, FakeShopify, seed_products

SHOP = "my-store.myshopify.com"
SECRET = "shpss_test_secret"


# ---------------------------------------------------------------- the store address


@pytest.mark.parametrize(
    ("text", "shop"),
    [
        ("my-store", SHOP),
        ("My-Store.myshopify.com", SHOP),
        ("https://my-store.myshopify.com/admin/products", SHOP),
        ("  my-store  ", SHOP),
    ],
)
def test_a_store_is_named_by_its_myshopify_address(text: str, shop: str) -> None:
    assert normalize_shop(text) == shop


@pytest.mark.parametrize(
    "text",
    [
        "",
        "my store",
        "evil.example.com",
        "my-store.myshopify.com.evil.test",
        "-x.myshopify.com",
    ],
)
def test_nothing_else_is_ever_called(text: str) -> None:
    assert normalize_shop(text) is None


def test_ids_lose_their_gid_prefix() -> None:
    assert numeric_id("gid://shopify/Product/123") == "123"
    assert numeric_id(456) == "456"
    assert numeric_id("nope") is None


# ---------------------------------------------------------------- signatures


def test_a_webhook_is_verified_over_the_raw_body() -> None:
    raw = b'{"id": 1}'
    good = signatures.sign_webhook(raw, SECRET)
    assert signatures.verify_webhook(raw, good, SECRET)
    assert not signatures.verify_webhook(raw + b" ", good, SECRET)
    assert not signatures.verify_webhook(raw, good, "other")
    assert not signatures.verify_webhook(raw, None, SECRET)
    assert not signatures.verify_webhook(raw, good, "")
    assert not signatures.verify_webhook(raw, "not-base64", SECRET)


def test_the_install_redirect_is_verified_over_its_sorted_parameters() -> None:
    params = {"code": "abc", "shop": SHOP, "state": "s1", "timestamp": "170"}
    signed = {**params, "hmac": signatures.sign_query(params, SECRET)}
    assert signatures.verify_query(signed, SECRET)
    assert not signatures.verify_query({**signed, "code": "tampered"}, SECRET)
    assert not signatures.verify_query(params, SECRET)  # no hmac
    assert not signatures.verify_query(signed, "")
    # The order the parameters arrive in doesn't matter.
    assert signatures.verify_query(dict(reversed(list(signed.items()))), SECRET)


# ---------------------------------------------------------------- product shapes


GRAPHQL: dict[str, Any] = {
    "id": "gid://shopify/Product/55",
    "title": "Cotton kurta",
    "descriptionHtml": "<p>Soft &amp; light.</p><p>Straight cut</p>",
    "handle": "cotton-kurta",
    "status": "ACTIVE",
    "onlineStoreUrl": None,
    "featuredImage": {"url": "https://cdn.shopify.test/k.jpg"},
    "variants": {
        "nodes": [
            {
                "id": "gid://shopify/ProductVariant/1",
                "title": "Blue / M",
                "sku": "K-BL-M",
                "price": "799.00",
                "inventoryQuantity": 12,
                "inventoryItem": {"tracked": True},
                "selectedOptions": [
                    {"name": "Colour", "value": "Blue"},
                    {"name": "Size", "value": "M"},
                ],
            },
            {
                "id": "gid://shopify/ProductVariant/2",
                "title": "Blue / L",
                "sku": "",
                "price": "849.00",
                "inventoryQuantity": 0,
                "inventoryItem": {"tracked": False},  # untracked: no stock to report
                "selectedOptions": [{"name": "Size", "value": "L"}],
            },
        ]
    },
}


def test_a_graphql_product_is_read() -> None:
    product = parse.from_graphql(GRAPHQL)
    assert product is not None
    assert (product.id, product.title, product.status) == ("55", "Cotton kurta", "active")
    assert product.description == "Soft & light.\nStraight cut"
    first, second = product.variants
    assert (first.id, first.sku, first.price, first.inventory) == ("1", "K-BL-M", "799.00", 12)
    assert first.options == {"Colour": "Blue", "Size": "M"}
    assert (second.sku, second.inventory) == (None, None)


def test_a_webhook_product_is_read_and_stock_only_when_tracked() -> None:
    body = {
        "id": 55,
        "title": "Cotton kurta",
        "body_html": "<p>Soft</p>",
        "handle": "cotton-kurta",
        "status": "active",
        "options": [{"name": "Size"}],
        "image": {"src": "https://cdn.shopify.test/k.jpg"},
        "variants": [
            {
                "id": 1,
                "title": "M",
                "sku": "K-M",
                "price": "799.00",
                "option1": "M",
                "inventory_quantity": 3,
                "inventory_management": "shopify",
            },
            {
                "id": 2,
                "title": "L",
                "sku": "K-L",
                "price": "799.00",
                "option1": "L",
                "inventory_quantity": 0,
                "inventory_management": None,
            },
        ],
    }
    product = parse.from_webhook(body)
    assert product is not None
    assert [(v.id, v.inventory, v.options) for v in product.variants] == [
        ("1", 3, {"Size": "M"}),
        ("2", None, {"Size": "L"}),
    ]
    assert product.image_url == "https://cdn.shopify.test/k.jpg"
    assert parse.from_webhook({"title": "No id"}) is None
    assert parse.from_graphql({"id": "gid://shopify/Product/1"}) is None


# ---------------------------------------------------------------- the mapping


def test_a_product_with_variants_maps_each_with_its_own_price() -> None:
    shopify = parse.from_graphql(GRAPHQL)
    assert shopify is not None
    data, cut = service.to_data(shopify, currency="INR", storefront="shop.example")
    assert data is not None
    assert cut == 0
    assert data.price_minor is None
    assert data.external_id == "55"
    assert data.active
    assert data.url == "https://shop.example/products/cotton-kurta"
    assert [(v.title, v.price_minor, v.stock, v.sku, v.external_id) for v in data.variants] == [
        ("Blue / M", 79900, 12, "K-BL-M", "1"),
        ("Blue / L", 84900, None, None, "2"),
    ]


def test_the_one_default_variant_makes_a_plain_product() -> None:
    [_, scarf, jacket] = seed_products(SHOP)
    data, _ = service.to_data(scarf, currency="INR", storefront=SHOP)
    assert data is not None
    assert (data.price_minor, data.stock, data.sku, data.variants) == (49900, None, "SCARF-1", [])
    off, _ = service.to_data(jacket, currency="INR", storefront=SHOP)
    assert off is not None
    assert off.active is False
    assert off.url == f"https://{SHOP}/products/draft-jacket"


def test_a_product_with_no_readable_price_is_left_out() -> None:
    [_, scarf, _] = seed_products(SHOP)
    broken = type(scarf)(
        **{
            **scarf.__dict__,
            "variants": (
                scarf.variants[0].__class__(
                    id="1", title="Default Title", sku=None, price="free", inventory=None
                ),
            ),
        }
    )
    data, _ = service.to_data(broken, currency="INR", storefront=SHOP)
    assert data is None


def test_more_variants_than_we_hold_are_counted() -> None:
    [kurta, _, _] = seed_products(SHOP)
    extra = tuple(
        kurta.variants[0].__class__(
            id=str(1000 + n),
            title=f"V{n}",
            sku=None,
            price="1.00",
            inventory=1,
            options={"N": str(n)},
        )
        for n in range(120)
    )
    big = type(kurta)(**{**kurta.__dict__, "variants": extra})
    data, cut = service.to_data(big, currency="INR", storefront=None)
    assert data is not None
    assert len(data.variants) == service.MAX_VARIANTS
    assert cut == 20


# ---------------------------------------------------------------- the built-in store


async def test_the_built_in_store_walks_pages_and_goes_away_when_revoked() -> None:
    fake = FakeShopify(pages=2)
    url = fake.authorize_url(SHOP, "state1")
    assert f"code={CODE_PREFIX}{SHOP}".replace(":", "%3A") in url or CODE_PREFIX in url
    grant = await fake.exchange_code(SHOP, f"{CODE_PREFIX}{SHOP}")
    first = await fake.list_products(SHOP, grant.access_token, None)
    assert [p.title for p in first.products] == ["Cotton kurta", "Silk scarf"]
    assert first.next_cursor is not None
    second = await fake.list_products(SHOP, grant.access_token, first.next_cursor)
    assert [p.title for p in second.products] == ["Draft jacket"]
    assert second.next_cursor is None
    with pytest.raises(ShopifyError):
        await fake.exchange_code(SHOP, "forged")
    await fake.revoke_access(grant.access_token)
    with pytest.raises(ShopifyError) as refused:
        await fake.list_products(SHOP, grant.access_token, None)
    assert refused.value.kind == "auth"


# ---------------------------------------------------------------- the "send product" step


TAG = uuid.uuid4()
PRODUCT = uuid.uuid4()
VARIANT = uuid.uuid4()


def definition(**step: Any) -> FlowDefinition:
    return FlowDefinition.model_validate(
        {
            "start": "p",
            "steps": [{"type": "product", "id": "p", "product_id": str(PRODUCT), **step}],
        }
    )


def context(**kw: Any) -> flows.Context:
    return flows.Context(trigger="dm_keyword", disclosure=None, **kw)


def errors(flow: FlowDefinition, ctx: flows.Context) -> dict[str, str]:
    return {e.field: e.message for e in flows.activation_errors(flow, ctx)}


def test_a_product_step_parses_and_leads_on() -> None:
    flow = definition(variant_id=str(VARIANT), intro="Here you go", next=None)
    [step] = flow.steps
    assert isinstance(step, ProductStep)
    assert (step.product_id, step.variant_id, step.intro) == (PRODUCT, VARIANT, "Here you go")
    assert flows.successors(step) == [None]
    assert not flows.waits(step)


def test_a_product_step_needs_a_live_product_and_the_plan() -> None:
    ok = context(products={PRODUCT: (True, frozenset({VARIANT}))})
    assert errors(definition(variant_id=str(VARIANT)), ok) == {}
    assert errors(definition(), ok) == {}
    gone = errors(definition(), context())
    assert gone == {"flow.steps.0.product_id": flows.COPY["product_missing"]}
    off = context(products={PRODUCT: (False, frozenset())})
    assert errors(definition(), off) == {"flow.steps.0.product_id": flows.COPY["product_off"]}
    no_variant = context(products={PRODUCT: (True, frozenset())})
    assert errors(definition(variant_id=str(VARIANT)), no_variant) == {
        "flow.steps.0.variant_id": flows.COPY["variant_missing"]
    }
    free = context(products={PRODUCT: (True, frozenset())}, commerce=False)
    assert errors(definition(), free) == {"flow.steps.0.product_id": flows.COPY["product_plan"]}


def test_a_product_cannot_follow_a_comments_private_reply() -> None:
    flow = FlowDefinition.model_validate(
        {
            "start": "a",
            "steps": [
                {"type": "send", "id": "a", "text": "Hi", "next": "p"},
                {"type": "product", "id": "p", "product_id": str(PRODUCT)},
            ],
        }
    )
    ctx = flows.Context(
        trigger="comment_keyword",
        disclosure=None,
        products={PRODUCT: (True, frozenset())},
    )
    assert "flow.steps.1" in errors(flow, ctx)
