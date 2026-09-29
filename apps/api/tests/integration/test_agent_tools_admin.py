"""Ask Social Hood's automation and knowledge tools against real data (TA.4; FR-AGT-02,
FR-AGT-03, FR-AGT-06): list_automations, get_automation, get_automation_stats, test_automation,
prepare_automation, search_knowledge, answer_from_knowledge and list_knowledge_gaps; the role
bound on every owner-and-admin tool (§8) and another workspace's ids."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from socialhood.errors import ApiError
from socialhood.models.identity import Role
from socialhood.platforms.deps import PlatformDeps
from socialhood.settings import Settings
from tests.support.agent_tools import Shop, make_shop, tool_platform
from tests.support.ai import make_gap, make_source
from tests.support.automations import make_automation, make_media_item
from tests.support.inbox import make_thread


@pytest.fixture
async def platform(api_settings: Settings) -> AsyncIterator[PlatformDeps]:
    async with tool_platform(api_settings) as deps:
        yield deps


@pytest.fixture
async def shop(engine: AsyncEngine, clean_db: None, platform: PlatformDeps) -> Shop:
    return await make_shop(engine, platform)


@pytest.fixture
async def other(engine: AsyncEngine, shop: Shop, platform: PlatformDeps) -> Shop:
    return await make_shop(engine, platform)


async def refused(shop: Shop, name: str, args: dict[str, Any], **kw: Any) -> ApiError:
    with pytest.raises(ApiError) as caught:
        await shop.call(name, args, **kw)
    return caught.value


async def automation(shop: Shop, **values: Any) -> uuid.UUID:
    return await make_automation(
        shop.engine, workspace_id=shop.wid, account_id=shop.account_id, **values
    )


# ---------------------------------------------------------------- automations


async def test_list_get_and_stats(shop: Shop) -> None:
    link = await automation(shop, name="Send the link")
    draft = await automation(
        shop,
        name="Giveaway",
        status="draft",
        trigger="comment_any",
        keywords=(),
        action=None,
        message_text=None,
        activated_at=None,
    )
    listed = await shop.call("list_automations", {})
    assert listed.total == 2
    assert {i.name for i in listed.items} == {"Send the link", "Giveaway"}
    assert listed.summary == "Found 2 automations, 1 active"
    assert {(r.kind, r.id) for r in listed.refs} == {("automation", link), ("automation", draft)}
    active = await shop.call("list_automations", {"status": "active"})
    assert [i.id for i in active.items] == [link]
    capped = await shop.call("list_automations", {"limit": 1})
    assert (len(capped.items), capped.more) == (1, 1)

    got = await shop.call("get_automation", {"automation_id": str(link)})
    assert (got.trigger, got.keywords, got.action, got.account) == (
        "dm_keyword",
        ["link"],
        "send_message",
        "@maple.bakery",
    )
    assert got.caveats == []
    assert got.refs[0].label == "Send the link"
    unfinished = await shop.call("get_automation", {"automation_id": str(draft)})
    assert unfinished.missing_for_activation
    assert unfinished.caveats[0].startswith("Before it can be activated it needs: ")

    stats = await shop.call("get_automation_stats", {"automation_id": str(link), "days": 30})
    assert (stats.runs, stats.dms_sent, stats.failures, len(stats.daily)) == (0, 0, 0, 30)
    assert stats.summary.startswith("“Send the link”, ")


async def test_test_automation_sends_nothing(shop: Shop) -> None:
    link = await automation(shop, name="Send the link")
    hit = await shop.call(
        "test_automation",
        {"automation_id": str(link), "kind": "dm", "text": "can you send the link?"},
    )
    assert (hit.matched, hit.matched_keyword, hit.winner, hit.winner_id) == (
        True,
        "link",
        "Send the link",
        link,
    )
    assert hit.message is not None
    assert "Priya" in hit.message  # rendered with the sample name
    assert hit.summary == "“Send the link” would answer “can you send the link?”"
    miss = await shop.call(
        "test_automation", {"automation_id": str(link), "kind": "dm", "text": "hello"}
    )
    assert not miss.matched
    assert miss.reason == "None of its keywords is in this message."
    wrong = await shop.call(
        "test_automation", {"automation_id": str(link), "kind": "comment", "text": "link"}
    )
    assert wrong.reason == "This automation answers DMs, not comments."
    assert await shop.rows("SELECT id FROM automation_runs") == []
    assert await shop.rows("SELECT id FROM messages") == []


async def test_prepare_automation_from_a_template(shop: Shop) -> None:
    got = await shop.call(
        "prepare_automation",
        {"description": "Send my link to everyone who comments LINK on my reels"},
    )
    assert got.template_key == "send_link"
    assert got.template_rule is not None
    assert "the request says “link”" in got.template_rule
    card = got.action_card
    assert (card.kind, card.route, card.label) == (
        "automation_draft",
        "automations/new?draft=1",
        "Open the automation draft",
    )
    prefill = card.prefill
    assert (prefill.template_key, prefill.trigger, prefill.action) == (
        "send_link",
        "comment_keyword",
        "send_message",
    )
    assert prefill.keywords == ["link"]
    assert prefill.social_account_id == shop.account_id  # the only Instagram account
    assert prefill.public_reply_texts
    assert prefill.post_scope == "all"
    assert got.missing_for_activation == []
    assert got.caveats == []
    assert await shop.rows("SELECT id FROM automations") == []  # nothing is created


async def test_prepare_automation_from_the_members_fields(shop: Shop) -> None:
    post = await make_media_item(shop.engine, workspace_id=shop.wid, account_id=shop.account_id)
    got = await shop.call(
        "prepare_automation",
        {
            "description": "DM our price list to anyone who writes PRICE",
            "name": "Price list",
            "trigger": "comment_keyword",
            "keywords": ["price", "Price", " rates "],
            "action": "send_message",
            "post_ids": [str(post)],
        },
    )
    assert got.template_key is None
    prefill = got.action_card.prefill
    assert (prefill.name, prefill.keywords) == ("Price list", ["price", "rates"])
    assert (prefill.post_scope, prefill.media_item_ids) == ("selected", [post])
    assert got.missing_for_activation == ["the message"]
    assert got.caveats == ["Before it can be activated it needs: the message."]

    faqs = await shop.call(
        "prepare_automation", {"description": "Answer FAQs", "template_key": "answer_faqs"}
    )
    assert faqs.action == "ai_reply"
    assert "AI replies in automations are part of Pro" in faqs.caveats[-1]
    bad = await refused(
        shop, "prepare_automation", {"description": "x", "template_key": "surprise_me"}
    )
    assert bad.code == "validation_error"


# ---------------------------------------------------------------- knowledge


async def test_search_knowledge_cites_its_sources(shop: Shop) -> None:
    source = await make_source(
        shop.engine,
        workspace_id=shop.wid,
        question="How much is shipping?",
        body="Shipping is free on orders over ₹999.",
    )
    found = await shop.call("search_knowledge", {"q": "How much is shipping?"})
    assert found.hits[0].source_id == source
    assert found.hits[0].source == "How much is shipping?"
    assert found.hits[0].excerpt is not None
    assert "free on orders" in found.hits[0].excerpt
    assert [(r.kind, r.id) for r in found.refs] == [("knowledge_source", source)]
    nothing = await shop.call("search_knowledge", {"q": "zebra crossing lessons"})
    assert nothing.hits == []
    assert nothing.caveats == ["Nothing in the knowledge base matches this closely enough."]


async def test_answer_from_knowledge_like_the_test_box(shop: Shop, fake_ai: FakeProvider) -> None:
    source = await make_source(shop.engine, workspace_id=shop.wid)
    fake_ai.respond(
        "suggest",
        {
            "can_answer": True,
            "reply": "Shipping is free on orders over ₹999.",
            "missing_info": None,
            "missing_topic": None,
            "confidence": 0.9,
            "used_source_ids": ["k1"],
        },
        {"can_answer": False, "missing_info": "the delivery time"},  # the next question
    )
    got = await shop.call("answer_from_knowledge", {"question": "How much is shipping?"})
    assert (got.can_answer, got.answer) == (True, "Shipping is free on orders over ₹999.")
    assert got.sources == ["How much is shipping?"]
    assert [(r.kind, r.id) for r in got.refs] == [("knowledge_source", source)]
    usage = await shop.rows("SELECT feature, credits, ref_type, ref_id FROM ai_usage_events")
    assert usage == [
        {"feature": "knowledge_test", "credits": 1, "ref_type": "agent_run", "ref_id": shop.run_id}
    ]

    missing = await shop.call("answer_from_knowledge", {"question": "How long is delivery?"})
    assert not missing.can_answer
    assert missing.caveats == ["Missing from the knowledge base: the delivery time."]


async def test_list_knowledge_gaps_with_examples(shop: Shop) -> None:
    t = await make_thread(
        shop.engine,
        workspace_id=shop.wid,
        account_id=shop.account_id,
        texts=("Do you ship to Dubai?",),
    )
    gap = await make_gap(
        shop.engine,
        workspace_id=shop.wid,
        topic="shipping to uae",
        occurrences=4,
        example_message_ids=[t.message_ids[0]],
    )
    got = await shop.call("list_knowledge_gaps", {})
    [item] = got.items
    assert (item.id, item.topic, item.asked) == (gap, "shipping to uae", 4)
    assert [(e.conversation_id, e.text) for e in item.examples] == [
        (t.conversation_id, "Do you ship to Dubai?")
    ]
    assert [(r.kind, r.id, r.label) for r in got.refs] == [
        ("conversation", t.conversation_id, "“Do you ship to Dubai?”")
    ]
    assert got.summary == "1 unanswered question topics in the last 30 days: “shipping to uae” (4)"


# ---------------------------------------------------------------- roles and tenancy

ADMIN_TOOLS: dict[str, dict[str, Any]] = {
    "list_scheduled_posts": {},
    "list_automations": {},
    "get_automation": {"automation_id": str(uuid.uuid4())},
    "get_automation_stats": {"automation_id": str(uuid.uuid4())},
    "test_automation": {"automation_id": str(uuid.uuid4()), "kind": "dm", "text": "hi"},
    "prepare_automation": {"description": "Send my link"},
    "search_knowledge": {"q": "shipping"},
    "answer_from_knowledge": {"question": "How much is shipping?"},
    "list_knowledge_gaps": {},
}


@pytest.mark.parametrize(("name", "args"), list(ADMIN_TOOLS.items()))
async def test_agents_cant_use_owner_and_admin_tools(
    shop: Shop, fake_ai: FakeProvider, name: str, args: dict[str, Any]
) -> None:
    error = await refused(shop, name, args, role=Role.AGENT)
    assert (error.code, error.detail) == (
        "forbidden",
        "Only owners and admins can use this, as in the app.",
    )
    assert fake_ai.calls == []


async def test_admins_can(shop: Shop) -> None:
    await automation(shop)
    assert (await shop.call("list_automations", {}, role=Role.ADMIN)).total == 1


async def test_another_workspaces_automations_never_resolve(shop: Shop, other: Shop) -> None:
    theirs = await automation(other)
    mine = await automation(shop)
    their_post = await make_media_item(
        other.engine, workspace_id=other.wid, account_id=other.account_id
    )
    for name, args in [
        ("get_automation", {"automation_id": str(theirs)}),
        ("get_automation_stats", {"automation_id": str(theirs)}),
        ("test_automation", {"automation_id": str(theirs), "kind": "dm", "text": "link"}),
    ]:
        error = await refused(shop, name, args)
        assert error.code == "not_found", name
    error = await refused(
        shop,
        "test_automation",
        {"automation_id": str(mine), "kind": "comment", "text": "link", "post_id": str(their_post)},
    )
    assert error.code == "validation_error"
    error = await refused(
        shop, "prepare_automation", {"description": "Send my link", "post_ids": [str(their_post)]}
    )
    assert error.code == "validation_error"
    listed = await shop.call("list_automations", {})
    assert [i.id for i in listed.items] == [mine]
    await make_gap(other.engine, workspace_id=other.wid)
    assert (await shop.call("list_knowledge_gaps", {})).items == []
