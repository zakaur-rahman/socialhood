"""GR-31 done-when: asking "price of the blue kurta in M?" gets the right price and link, from
Suggest or Auto, through the knowledge pipeline with structured product facts.

The model is the fake provider, answering the way a faithful model would from the PRODUCTS lines it
is given; what the tests pin is what the app gives it, what it keeps of the answer (the product's
id as the used source, the link allowed through the output filter, an invented link blocked), and
that Auto mode treats a cited product as grounded."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.agent.tools import load_tools
from socialhood.ai.fake import FakeCall, FakeProvider
from socialhood.errors import ApiError
from socialhood.models.identity import Role
from socialhood.platforms.deps import PlatformDeps
from socialhood.services.suggestions.service import Outcome
from socialhood.settings import Settings
from tests.support.agent_tools import Shop, make_shop, tool_platform
from tests.support.api import Clerk
from tests.support.catalogue import KURTA_URL, make_product
from tests.support.sending import clean_outbox
from tests.support.suggestions import Ai, make_ai

QUESTION = "price of the blue kurta in M?"


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def ai(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    fake_ai: FakeProvider,
    queue: None,
) -> Ai:
    return await make_ai(app, client, clerk, engine, redis, fake_ai, question=QUESTION)


def faithful(call: FakeCall) -> dict[str, Any]:
    """What a model that reads its PRODUCTS lines does: quotes the marked variant."""
    text = "\n".join(turn.text for turn in call.contents)
    entry = re.search(r"\[p1\] (?P<name>[^|\n]+)\| link: (?P<link>\S+)", text)
    marked = re.search(
        r"  - (?P<variant>[^|\n]+)\|(?: SKU [^|\n]+\|)? price (?P<price>[^|\n]+)\|"
        r"[^\n]*matches the question",
        text,
    )
    if entry is None or marked is None:
        return {
            "can_answer": False,
            "reply": None,
            "missing_info": "which product",
            "missing_topic": "product",
            "confidence": 0.2,
            "used_source_ids": [],
        }
    return {
        "can_answer": True,
        "reply": f"{entry['name'].strip()} in {marked['variant'].strip()} is "
        f"{marked['price'].strip()}. {entry['link']}",
        "missing_info": None,
        "missing_topic": None,
        "confidence": 0.95,
        "used_source_ids": ["p1"],
    }


# ---------------------------------------------------------------- Suggest


async def test_suggest_answers_the_price_of_the_blue_kurta_in_m(ai: Ai) -> None:
    await ai.plan("pro")
    kurta = await make_product(ai.engine, workspace_id=ai.wid)
    ai.fake.respond("suggest", faithful)

    assert await ai.suggest() is Outcome.STORED

    row = await ai.pending()
    assert row["can_answer"] is True
    assert row["reply_text"] == f"Cotton kurta in Blue / M is INR 799.00. {KURTA_URL}"
    assert row["used_chunk_ids"] == [kurta.id]  # the product, cited by its id
    assert row["top_similarity"] == 1.0  # an exact fact
    [call] = ai.fake.calls_for("suggest")
    [turn] = call.contents
    assert "PRODUCTS (" in turn.text
    assert (
        "  - Blue / M | SKU KUR-BL-M | price INR 799.00 | 12 in stock | matches the question"
        in (turn.text)
    )
    assert "  - Blue / L | SKU KUR-BL-L | price INR 849.00 | out of stock" in turn.text
    assert "  - Red / M | SKU KUR-RD-M | price INR 799.00 | stock not recorded" in turn.text
    assert "INR 799" not in call.system  # the catalogue is data, never in the system prompt


async def test_no_product_word_means_no_products_section(ai: Ai) -> None:
    await ai.plan("pro")
    await make_product(ai.engine, workspace_id=ai.wid)
    await ai.execute(
        "UPDATE messages SET text = 'Do you ship to Dubai?' WHERE id = :i", i=ai.message_id
    )

    await ai.suggest()

    [call] = ai.fake.calls_for("suggest")
    assert "PRODUCTS" not in call.contents[0].text


async def test_an_invented_link_is_never_offered(ai: Ai) -> None:
    await ai.plan("pro")
    await make_product(ai.engine, workspace_id=ai.wid)
    ai.fake.respond(
        "suggest",
        {
            "can_answer": True,
            "reply": "The blue kurta in M is INR 799. Buy it at https://invented.example/kurta",
            "missing_info": None,
            "missing_topic": None,
            "confidence": 0.9,
            "used_source_ids": ["p1"],
        },
    )

    await ai.suggest()

    row = await ai.pending()
    assert (row["can_answer"], row["reply_text"]) == (False, None)
    assert "invented.example" in row["missing_info"]


async def test_a_product_that_is_switched_off_is_never_offered(ai: Ai) -> None:
    await ai.plan("pro")
    await make_product(ai.engine, workspace_id=ai.wid, active=False)
    ai.fake.respond("suggest", faithful)

    await ai.suggest()

    [call] = ai.fake.calls_for("suggest")
    assert "PRODUCTS" not in call.contents[0].text
    assert (await ai.pending())["can_answer"] is False


# ---------------------------------------------------------------- Auto


async def test_auto_sends_the_catalogue_answer_as_grounded(ai: Ai) -> None:
    await ai.plan("pro")
    await ai.mode("auto")
    await make_product(ai.engine, workspace_id=ai.wid)
    await ai.analysis(intent="pricing")
    ai.fake.respond("suggest", faithful)
    await ai.suggest()
    suggestion_id = (await ai.pending())["id"]

    decision = await ai.decide(suggestion_id)

    assert decision is not None
    assert (decision.outcome, decision.reason) == ("auto_sent", None)
    grounded = next(c for c in decision.checks if c["name"] == "grounded_in_knowledge")
    assert grounded["passed"] is True
    [sent] = await ai.rows("SELECT * FROM messages WHERE direction = 'outbound'")
    assert sent["source"] == "ai_auto"
    assert sent["text"] == f"Cotton kurta in Blue / M is INR 799.00. {KURTA_URL}"


async def test_auto_still_stops_when_the_answer_cites_nothing(ai: Ai) -> None:
    await ai.plan("pro")
    await ai.mode("auto")
    await make_product(ai.engine, workspace_id=ai.wid)
    await ai.analysis(intent="pricing")
    reply = faithful
    ai.fake.respond(
        "suggest",
        lambda call: {**reply(call), "used_source_ids": []},  # a guess, no source
    )
    await ai.suggest()

    decision = await ai.decide((await ai.pending())["id"])

    assert decision is not None
    assert decision.outcome == "escalated"
    assert decision.reason == "out_of_knowledge"


# ---------------------------------------------------------------- the test box


async def test_the_knowledge_test_box_reads_the_catalogue_too(ai: Ai) -> None:
    await ai.plan("pro")
    await make_product(ai.engine, workspace_id=ai.wid)
    ai.fake.respond("suggest", faithful)

    response = await ai.call("POST", "/knowledge/test", json={"question": QUESTION})

    assert response.status_code == 200, response.text
    assert response.json()["can_answer"] is True
    assert KURTA_URL in response.json()["answer"]
    [call] = ai.fake.calls_for("suggest")
    assert "[p1] Cotton kurta" in call.contents[0].text


# ---------------------------------------------------------------- Ask Amplychat


@pytest.fixture
async def platform(api_settings: Settings) -> AsyncIterator[PlatformDeps]:
    async with tool_platform(api_settings) as deps:
        yield deps


@pytest.fixture
async def shop(engine: AsyncEngine, clean_db: None, platform: PlatformDeps) -> Shop:
    return await make_shop(engine, platform)


async def test_search_products_answers_with_price_stock_and_link(shop: Shop) -> None:
    kurta = await make_product(shop.engine, workspace_id=shop.wid)

    found = await shop.call("search_products", {"q": "blue kurta M"})

    [item] = found.items
    assert (item.name, item.link) == ("Cotton kurta", KURTA_URL)
    matched = [v for v in item.variants if v.matches]
    assert [(v.title, v.price, v.stock) for v in matched] == [
        ("Blue / M", "INR 799.00", "12 in stock")
    ]
    assert {v.title: v.stock for v in item.variants}["Red / M"] == "stock not recorded"
    assert [(r.kind, r.id) for r in found.refs] == [("product", kurta.id)]


async def test_search_products_falls_back_to_a_plain_search_and_says_when_empty(shop: Shop) -> None:
    await make_product(
        shop.engine, workspace_id=shop.wid, active=False
    )  # off: a plain search shows it
    plain = await shop.call("search_products", {"q": "cotton"})
    assert [(i.name, i.active) for i in plain.items] == [("Cotton kurta", False)]
    nothing = await shop.call("search_products", {"q": "zebra"})
    assert nothing.items == []
    assert nothing.caveats == ["No product in the catalogue matches these words."]


async def test_search_products_is_for_owners_and_admins(shop: Shop) -> None:
    with pytest.raises(ApiError) as agent:
        await shop.call("search_products", {"q": "kurta"}, role=Role.AGENT)
    assert agent.value.code == "forbidden"
    spec = load_tools().get("search_products")
    assert spec is not None
    assert spec.min_role == Role.ADMIN
