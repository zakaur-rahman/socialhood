"""T7.4: AI caption and hashtags for the composer (FR-PUB-02, TR-AI-04, TR-AI-09, UX-SCR-13).
Done when: credits are charged and the brand voice is applied. Plus: the modes' required input,
answers kept within the checklist's limits, suggested hashtags normalised and deduplicated, used-up
credits (402) and model failures (503, refunded). Runs with the fake AI provider, never Gemini;
other workspaces are covered by the tenancy suite."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from socialhood.ai.provider import AIError
from tests.support.analysis import use_credits
from tests.support.api import Clerk
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
            "emoji_policy": "lots",
            "do_list": ["mention the daily bake"],
            "dont_list": ["discounts"],
            "sign_off": "- Team Maple",
            "takeover_minutes": 120,
        },
    )
    return shop


async def _credits(shop: Shop) -> tuple[int, list[dict[str, object]]]:
    counter = await shop.rows("SELECT used FROM usage_counters WHERE metric = 'ai_credits'")
    events = await shop.rows(
        "SELECT feature, credits, outcome FROM ai_usage_events ORDER BY created_at"
    )
    return (counter[0]["used"] if counter else 0), events


async def test_a_caption_is_written_in_the_brand_voice_for_one_credit(
    shop: Shop, fake_ai: FakeProvider
) -> None:
    fake_ai.respond("caption", {"caption": "Fresh sourdough, straight from the oven! #sourdough"})

    out = await shop.ok("POST", "/ai/caption", {"brief": "Our new rye sourdough is here"})

    assert out == {"caption": "Fresh sourdough, straight from the oven! #sourdough"}
    [call] = fake_ai.calls_for("caption")
    # The brand voice is in the system prompt; the brief is data in the contents.
    for trait in (
        "Maple Bakery",
        "Sourdough and cakes baked daily in Pune.",
        "Voice: playful",
        "Emoji: lots",
        "mention the daily bake",
        "discounts",
        "2,200 characters, 30 hashtags and 20 @mentions",
    ):
        assert trait in call.system, trait
    assert "rye sourdough" not in call.system
    assert [t.text for t in call.contents] == [
        "BRIEF (what the post is about):\nOur new rye sourdough is here"
    ]
    used, events = await _credits(shop)
    assert used == 1
    assert events == [{"feature": "caption_generation", "credits": 1, "outcome": "ok"}]


async def test_improve_sends_the_caption_and_needs_one(shop: Shop, fake_ai: FakeProvider) -> None:
    fake_ai.respond("caption", {"caption": "Better caption"})

    out = await shop.ok(
        "POST", "/ai/caption", {"mode": "improve", "caption": "new bread today @friend #bread"}
    )

    assert out["caption"] == "Better caption"
    [call] = fake_ai.calls_for("caption")
    assert call.contents[0].text == "CAPTION TO IMPROVE:\nnew bread today @friend #bread"

    errors = await shop.fields("POST", "/ai/caption", {"mode": "improve", "brief": "bread"})
    assert errors == {"caption": "Write a caption to improve."}
    errors = await shop.fields("POST", "/ai/caption", {"mode": "write"})
    assert errors == {"brief": "Say what the post is about."}
    assert len(fake_ai.calls_for("caption")) == 1
    assert (await _credits(shop))[0] == 1


async def test_a_caption_is_kept_within_the_checklists_limits(
    shop: Shop, fake_ai: FakeProvider
) -> None:
    tags = " ".join(f"#tag{i}" for i in range(35))
    mentions = " ".join(f"@friend{i}" for i in range(25))
    fake_ai.respond(
        "caption",
        {"caption": f"Fresh bread {mentions}\n\n{tags}"},
        {"caption": ("word " * 600).strip()},
    )

    out = await shop.ok("POST", "/ai/caption", {"brief": "bread"})

    caption = out["caption"]
    assert caption.count("#") == 30
    assert caption.count("@") == 20
    assert "#tag29" in caption
    assert "#tag30" not in caption
    assert "  " not in caption

    long = await shop.ok("POST", "/ai/caption", {"brief": "bread"})
    assert len(long["caption"]) <= 2200
    assert long["caption"].endswith("word")


async def test_an_empty_or_failed_answer_is_503_and_refunded(
    shop: Shop, fake_ai: FakeProvider
) -> None:
    fake_ai.respond("caption", {"caption": "   "}, AIError("timeout", retryable=True))

    for _ in range(2):
        problem = await shop.problem("POST", "/ai/caption", {"brief": "bread"}, status=503)
        assert problem["code"] == "service_unavailable"

    used, events = await _credits(shop)
    assert used == 0
    assert [(e["credits"], e["outcome"]) for e in events] == [(0, "error"), (0, "timeout")]


async def test_used_up_credits_are_402_before_any_call(
    shop: Shop, fake_ai: FakeProvider, engine: AsyncEngine
) -> None:
    await use_credits(engine, uuid.UUID(shop.wid), 200, now=datetime.now(UTC))

    for path, body in (
        ("/ai/caption", {"brief": "bread"}),
        ("/ai/hashtags", {"caption": "bread"}),
    ):
        problem = await shop.problem("POST", path, body, status=402)
        assert problem["code"] == "quota_exceeded"
        assert problem["detail"].startswith("You've used all 200 AI credits for this month.")

    assert fake_ai.calls == []


async def test_hashtags_leave_out_the_captions_and_the_excluded_ones(
    shop: Shop, fake_ai: FakeProvider
) -> None:
    fake_ai.respond(
        "hashtags",
        {
            "hashtags": [
                "#Sourdough",
                "bread",
                "PuneFood",
                "baking",
                "pune food",
                "#bakery",
                "punefood",
                "fresh_bread",
                "",
            ]
        },
    )

    out = await shop.ok(
        "POST",
        "/ai/hashtags",
        {"caption": "New #Bread today", "exclude": ["#BAKERY"], "count": 3},
    )

    assert out == {"hashtags": ["sourdough", "punefood", "baking"]}
    [call] = fake_ai.calls_for("hashtags")
    assert "Maple Bakery" in call.system
    assert "up to 3 hashtags" in call.system
    assert [t.text for t in call.contents] == [
        "CAPTION:\nNew #Bread today",
        "LEAVE OUT: bakery, bread",
    ]
    used, events = await _credits(shop)
    assert used == 1
    assert events == [{"feature": "caption_generation", "credits": 1, "outcome": "ok"}]


async def test_hindi_hashtags_are_suggested_whole_and_left_out_whole(
    shop: Shop, fake_ai: FakeProvider
) -> None:
    fake_ai.respond("hashtags", {"hashtags": ["#दिवाली", "#मिठाई", "#पुणे_खाना", "रोटी"]})

    out = await shop.ok(
        "POST",
        "/ai/hashtags",
        {"caption": "दिवाली की मिठाई #दिवाली", "exclude": ["#रोटी"]},
    )

    assert out == {"hashtags": ["मिठाई", "पुणे_खाना"]}
    [call] = fake_ai.calls_for("hashtags")
    assert call.contents[1].text == "LEAVE OUT: दिवाली, रोटी"


async def test_hashtag_requests_are_validated(shop: Shop) -> None:
    errors = await shop.fields("POST", "/ai/hashtags", {"caption": "", "count": 21})
    assert set(errors) == {"caption", "count"}
