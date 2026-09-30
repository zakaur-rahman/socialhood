"""AI Polish (C-063): the composer's rewrite of a member's draft. Done when: the draft comes back
polished for 1 credit (reply_polish), with the conversation as context and the brand voice's
tone. Plus: a tone override, no conversation with AI analysis off (FR-PRV-02), anything added to
the draft refused (503, refunded), used-up credits (402 through the credits gate) and validation.
Runs with the fake AI provider, never Gemini; other workspaces are covered by the tenancy suite
and the AI rate limit by test_rate_limits."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from socialhood.ai.provider import AIError
from socialhood.services import polish
from tests.support.analysis import use_credits
from tests.support.api import Clerk
from tests.support.inbox import Thread, make_thread
from tests.support.publishing_api import Shop, open_shop


@pytest.fixture
async def shop(app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Shop:
    shop = await open_shop(app, client, clerk, engine)
    await shop.ok(
        "PUT",
        "/ai-settings",
        {
            "business_name": "Maple Bakery",
            "business_description": "Sourdough and cakes baked daily in Pune.",
            "tone": "playful",
            "emoji_policy": "light",
            "do_list": [],
            "dont_list": [],
            "sign_off": None,
            "takeover_minutes": 120,
        },
    )
    return shop


@pytest.fixture
async def thread(shop: Shop, engine: AsyncEngine) -> Thread:
    return await make_thread(
        engine,
        workspace_id=shop.wid,
        account_id=shop.account_id,
        texts=("hi", "kitne ka hai chocolate cake?"),
    )


def path(thread: Thread) -> str:
    return f"/conversations/{thread.conversation_id}/polish"


async def _credits(shop: Shop) -> tuple[int, list[dict[str, object]]]:
    counter = await shop.rows("SELECT used FROM usage_counters WHERE metric = 'ai_credits'")
    events = await shop.rows(
        "SELECT feature, credits, outcome, ref_type FROM ai_usage_events ORDER BY created_at"
    )
    return (counter[0]["used"] if counter else 0), events


async def test_the_draft_comes_back_polished_for_one_credit(
    shop: Shop, thread: Thread, fake_ai: FakeProvider
) -> None:
    fake_ai.respond("polish", {"text": "Chocolate cake ₹650 ka hai, aaj fresh bana hai!"})

    out = await shop.ok(
        "POST", path(thread), {"text": "  chocolate cake ₹650 ka hai aaj fresh bana hai  "}
    )

    assert out == {"text": "Chocolate cake ₹650 ka hai, aaj fresh bana hai!"}
    [call] = fake_ai.calls_for("polish")
    for trait in ("Maple Bakery", "Sourdough and cakes", "Instagram", "Voice: playful", "Hinglish"):
        assert trait in call.system, trait
    assert "kitne ka hai" not in call.system  # the conversation and draft are data (TR-AI-04)
    context, draft = (turn.text for turn in call.contents)
    assert context.splitlines() == [
        "CONVERSATION (oldest first):",
        "customer: hi",
        "customer: kitne ka hai chocolate cake?",
    ]
    assert draft == "DRAFT:\nchocolate cake ₹650 ka hai aaj fresh bana hai"
    used, events = await _credits(shop)
    assert used == 1
    assert events == [
        {"feature": "reply_polish", "credits": 1, "outcome": "ok", "ref_type": "conversation"}
    ]


async def test_a_tone_overrides_the_brand_voice_and_analysis_off_sends_no_conversation(
    shop: Shop, thread: Thread, fake_ai: FakeProvider
) -> None:
    await shop.execute(
        "UPDATE social_accounts SET ai_analysis_enabled = false WHERE id = :a", a=shop.account_id
    )

    out = await shop.ok("POST", path(thread), {"text": "thanks, see you", "tone": "professional"})

    assert out == {"text": "thanks, see you"}  # the fake echoes the draft
    [call] = fake_ai.calls_for("polish")
    assert "Voice: professional" in call.system
    assert [turn.text for turn in call.contents] == ["DRAFT:\nthanks, see you"]


@pytest.mark.parametrize(
    "answer",
    [
        "Yes, the cake is ₹650, and today it's 10% off!",  # a number the draft doesn't have
        "Yes, it's ₹650. Order at maplebakery.in",  # a link
        "Yes, it's ₹650. Call 98765 43210.",  # a phone number
        "",  # nothing
        "Yes " * 200,  # far longer than the draft
    ],
)
async def test_an_answer_that_adds_anything_is_refused_and_refunded(
    shop: Shop, thread: Thread, fake_ai: FakeProvider, answer: str
) -> None:
    fake_ai.respond("polish", {"text": answer})

    problem = await shop.problem("POST", path(thread), {"text": "yes its 650 rs"}, status=503)

    assert problem["code"] == "service_unavailable"
    used, events = await _credits(shop)
    assert used == 0
    assert [(e["feature"], e["credits"], e["outcome"]) for e in events] == [
        ("reply_polish", 0, "error")
    ]


async def test_a_model_failure_is_503_and_refunded(
    shop: Shop, thread: Thread, fake_ai: FakeProvider
) -> None:
    fake_ai.respond("polish", AIError("timeout", retryable=True))

    problem = await shop.problem("POST", path(thread), {"text": "ok"}, status=503)

    assert problem["detail"] == polish.AI_UNAVAILABLE
    assert (await _credits(shop))[0] == 0


async def test_used_up_credits_are_402_before_any_call(
    shop: Shop, thread: Thread, fake_ai: FakeProvider, engine: AsyncEngine
) -> None:
    await use_credits(engine, uuid.UUID(shop.wid), 200, now=datetime.now(UTC))

    problem = await shop.problem("POST", path(thread), {"text": "ok"}, status=402)

    assert problem["code"] == "quota_exceeded"
    assert problem["detail"].startswith("You've used all 200 AI credits for this month.")
    assert (problem["entitlement"], problem["limit"]) == ("ai_credits_monthly", 200)
    assert fake_ai.calls == []


async def test_polish_requests_are_validated(shop: Shop, thread: Thread) -> None:
    errors = await shop.fields("POST", path(thread), {"text": "   ", "tone": "angry"})
    assert set(errors) == {"text", "tone"}
    errors = await shop.fields("POST", path(thread), {"text": "x" * 4097})
    assert set(errors) == {"text"}
    missing = await shop.problem(
        "POST", f"/conversations/{uuid.uuid4()}/polish", {"text": "ok"}, status=404
    )
    assert missing["code"] == "not_found"


def test_numbers_links_and_quotes() -> None:
    assert polish.numbers("₹1,299.00 for 2") == {"129900", "2"}
    assert polish.added_details("It's ₹1,299.", "its 1299") is None
    assert polish.added_details("It's 1,300.", "its 1299") == "number 1300"
    assert polish.clean('"Sure, see you!"', "sure see you") == "Sure, see you!"
    assert polish.clean('"Hi" she said', '"hi" she said') == '"Hi" she said'
    assert polish.longest_allowed("ok") == 202
    assert polish.longest_allowed("x" * 3000) == 4096
