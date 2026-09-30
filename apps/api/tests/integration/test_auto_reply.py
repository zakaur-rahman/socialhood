"""T5.5 and T5.6: AI settings and modes (FR-SUG-01, FR-SUG-06), and Auto mode (TR-AI-07,
FR-SUG-04, FR-SUG-05, F-09).

decide_auto_reply evaluates the policy for a pending suggestion and writes one ai_decisions row
with all 13 checks: auto_sent queues an ai_auto message (2 more credits) and marks the suggestion
sent; escalated flags the conversation "Needs you" with the reason and notifies; skipped changes
nothing. A person's reply pauses Auto with a system note; Resume ends the pause. The decision
popover (GET …/ai-decision) and "should not have sent" feedback. Free workspaces cannot set Auto.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from tests.support.ai import make_suggestion
from tests.support.api import Clerk
from tests.support.ingest import jobs
from tests.support.sending import clean_outbox, post_message
from tests.support.suggestions import SHIPPING_REPLY, Ai, answer, cannot, make_ai

NAMES = [
    "mode_is_auto",
    "plan_and_credits",
    "not_paused",
    "no_automation",
    "window_open",
    "analysis_no_human",
    "no_escalation_topic",
    "sentiment",
    "can_answer",
    "confidence",
    "grounded_in_knowledge",
    "rate",
    "output_filter",
]


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
    return await make_ai(app, client, clerk, engine, redis, fake_ai)


async def ready(ai: Ai, response: dict[str, Any] | None = None, **analysis: Any) -> uuid.UUID:
    """Pro, Auto, the shipping FAQ, an analysis and a pending suggestion; its id."""
    await ai.plan("pro")
    await ai.mode("auto")
    await ai.shipping_faq()
    await ai.analysis(**analysis)
    ai.fake.respond("suggest", response or answer())
    await ai.suggest()
    return uuid.UUID(str((await ai.pending())["id"]))


async def decision_rows(ai: Ai) -> list[dict[str, Any]]:
    return await ai.rows("SELECT * FROM ai_decisions ORDER BY created_at, id")


async def notifications(ai: Ai) -> list[dict[str, Any]]:
    return await ai.rows("SELECT * FROM notifications WHERE type = 'ai_escalated'")


# ---------------------------------------------------------------- decisions (TR-AI-07)


async def test_every_check_passes_and_the_ai_replies(ai: Ai) -> None:
    suggestion_id = await ready(ai)

    decision = await ai.decide(suggestion_id)

    assert decision is not None
    assert (decision.outcome, decision.reason) == ("auto_sent", None)
    assert [c["name"] for c in decision.checks] == NAMES
    assert all(c["passed"] for c in decision.checks)
    [sent] = await ai.rows("SELECT * FROM messages WHERE direction = 'outbound'")
    assert (sent["source"], sent["text"], sent["status"]) == ("ai_auto", SHIPPING_REPLY, "queued")
    assert sent["suggestion_id"] == suggestion_id
    assert decision.sent_message_id == sent["id"]
    [row] = await ai.suggestions()
    assert (row["status"], row["sent_message_id"]) == ("sent", sent["id"])
    # 2 credits for the suggestion, 2 for the auto reply.
    assert await ai.used() == 4
    usage = await ai.rows("SELECT feature, credits FROM ai_usage_events ORDER BY created_at")
    assert [(u["feature"], u["credits"]) for u in usage] == [
        ("reply_suggestion", 2),
        ("auto_reply", 2),
    ]
    [job] = await jobs("send_message")
    assert job["queueing_lock"] == f"send:{sent['id']}"
    kinds = [kind for kind, _ in await ai.events()]
    assert {"message.created", "suggestion.updated", "conversation.updated"} <= set(kinds)
    # The AI's own reply is not a takeover.
    [conv] = await ai.rows("SELECT ai_paused_until, needs_human FROM conversations")
    assert conv == {"ai_paused_until": None, "needs_human": False}

    assert await ai.decide(suggestion_id) is None  # no longer pending: not evaluated again
    assert len(await decision_rows(ai)) == 1


async def test_an_escalation_needs_you_and_keeps_the_suggestion(ai: Ai) -> None:
    suggestion_id = await ready(ai, needs_human=True, needs_human_reason="refund")

    decision = await ai.decide(suggestion_id)

    assert decision is not None
    assert (decision.outcome, decision.reason) == ("escalated", "refund")
    assert [c["n"] for c in decision.checks if not c["passed"]] == [6]
    [conv] = await ai.rows("SELECT needs_human, needs_human_reason FROM conversations")
    assert conv == {"needs_human": True, "needs_human_reason": "refund"}
    assert (await ai.pending())["id"] == suggestion_id
    assert await ai.rows("SELECT id FROM messages WHERE direction = 'outbound'") == []
    [note] = await notifications(ai)
    assert (note["title"], note["body"]) == (
        "Priya Shah needs you",
        "AI didn't reply: the customer is asking for a refund.",
    )
    assert note["link"] == f"/inbox/{ai.conversation_id}"
    [(_, updated)] = await ai.events("conversation.updated")
    assert (updated["conversation"]["needs_human"], updated["conversation"]["signal"]) == (
        True,
        "needs_you",
    )
    assert await ai.used() == 2  # nothing charged for the decision


async def test_auto_answers_a_greeting_without_knowledge(ai: Ai) -> None:
    """C-062: "Hi" needs no knowledge. Even when the model declines, the suggestion is the fixed
    small-talk reply, and Auto sends it like any confident reply."""
    await ai.execute("UPDATE messages SET text = 'Hi' WHERE id = :id", id=ai.message_id)
    declined = cannot("information about the business", "business information")
    suggestion_id = await ready(ai, declined, intent="greeting", sentiment_score=0.0)

    decision = await ai.decide(suggestion_id)

    assert decision is not None
    assert (decision.outcome, decision.reason) == ("auto_sent", None)
    [sent] = await ai.rows("SELECT source, text FROM messages WHERE direction = 'outbound'")
    assert sent == {"source": "ai_auto", "text": "Hi! How can I help you today?"}
    assert await ai.rows("SELECT id FROM knowledge_gaps") == []


async def test_out_of_knowledge_escalates(ai: Ai) -> None:
    suggestion_id = await ready(ai, cannot())
    decision = await ai.decide(suggestion_id)
    assert decision is not None
    assert (decision.outcome, decision.reason) == ("escalated", "out_of_knowledge")
    [conv] = await ai.rows("SELECT needs_human_reason FROM conversations")
    assert conv["needs_human_reason"] == "out_of_knowledge"


async def test_a_workspace_escalation_phrase_escalates(ai: Ai) -> None:
    settings = {"escalation_phrases": ["wholesale"], "takeover_minutes": 120}
    assert (await ai.call("PUT", "/ai-settings", json=settings)).status_code == 200
    await ai.execute(
        "UPDATE messages SET text = 'Wholesale price for shipping?' WHERE id = :id",
        id=ai.message_id,
    )
    decision = await ai.decide(await ready(ai))
    assert decision is not None
    assert (decision.outcome, decision.reason) == ("escalated", "policy_keyword")
    assert decision.checks[6]["value"] == "wholesale"


@pytest.mark.parametrize("case", ["suggest_mode", "paused", "no_credits", "handled"])
async def test_a_skip_changes_nothing_visible(ai: Ai, case: str) -> None:
    suggestion_id = await ready(ai)
    if case == "suggest_mode":
        await ai.mode("suggest")
        expected = "mode_not_auto"
    elif case == "paused":
        await ai.execute(
            "UPDATE conversations SET ai_paused_until = :t",
            t=datetime.now(UTC) + timedelta(hours=1),
        )
        expected = "paused"
    elif case == "no_credits":
        await ai.set_used(4999)
        expected = "quota_exhausted"
    else:
        await ai.execute(
            "UPDATE messages SET automation_handled = true WHERE id = :id", id=ai.message_id
        )
        expected = "automation_handled"

    decision = await ai.decide(suggestion_id)

    assert decision is not None
    assert (decision.outcome, decision.reason) == ("skipped", expected)
    assert (await ai.pending())["id"] == suggestion_id
    assert await ai.rows("SELECT id FROM messages WHERE direction = 'outbound'") == []
    assert await notifications(ai) == []
    [conv] = await ai.rows("SELECT needs_human FROM conversations")
    assert conv["needs_human"] is False


async def test_a_closed_window_escalates(ai: Ai) -> None:
    suggestion_id = await ready(ai)
    await ai.execute(
        "UPDATE conversations SET last_inbound_at = :t", t=datetime.now(UTC) - timedelta(hours=25)
    )
    decision = await ai.decide(suggestion_id)
    assert decision is not None
    assert (decision.outcome, decision.reason) == ("escalated", "window_closed")


async def test_one_ai_reply_per_customer_message(ai: Ai, engine: AsyncEngine) -> None:
    await ai.decide(await ready(ai))
    [chunk] = await ai.rows("SELECT id FROM knowledge_chunks")
    again = await make_suggestion(
        engine,
        workspace_id=ai.wid,
        conversation_id=ai.conversation_id,
        message_id=ai.message_id,
        reply_text=SHIPPING_REPLY,
        used_chunk_ids=[chunk["id"]],
        top_similarity=0.8,
    )
    decision = await ai.decide(again)
    assert decision is not None
    assert (decision.outcome, decision.reason) == ("skipped", "rate_capped")
    assert len(await ai.rows("SELECT id FROM messages WHERE source = 'ai_auto'")) == 1


# ---------------------------------------------------------------- the decision popover (FR-SUG-04)


async def test_the_decision_is_shown_for_both_messages_and_takes_feedback(ai: Ai) -> None:
    decision = await ai.decide(await ready(ai))
    assert decision is not None
    assert decision.sent_message_id is not None

    for message_id in (ai.message_id, decision.sent_message_id):
        response = await ai.call("GET", f"/messages/{message_id}/ai-decision")
        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["id"], body["outcome"], body["reason"]) == (
            str(decision.id),
            "auto_sent",
            None,
        )
        assert [c["n"] for c in body["checks"]] == list(range(1, 14))

    path = f"/ai-decisions/{decision.id}/feedback"
    marked = await ai.call("POST", path, json={"feedback": "bad"})
    assert marked.status_code == 200, marked.text
    assert marked.json()["user_feedback"] == "bad"
    cleared = await ai.call("POST", path, json={"feedback": None})
    assert cleared.json()["user_feedback"] is None


async def test_feedback_is_for_sent_replies_and_decisions_can_be_missing(ai: Ai) -> None:
    missing = await ai.call("GET", f"/messages/{ai.message_id}/ai-decision")
    assert missing.status_code == 404
    decision = await ai.decide(await ready(ai, cannot()))
    assert decision is not None
    response = await ai.call(
        "POST", f"/ai-decisions/{decision.id}/feedback", json={"feedback": "bad"}
    )
    assert (response.status_code, response.json()["code"]) == (409, "conflict")
    shown = await ai.call("GET", f"/messages/{ai.message_id}/ai-decision")
    assert (shown.json()["outcome"], shown.json()["reason"]) == ("escalated", "out_of_knowledge")


# ---------------------------------------------------------------- takeover (FR-SUG-05, F-09)


async def notes(ai: Ai) -> list[str]:
    found = await ai.rows(
        "SELECT text FROM messages WHERE direction = 'system' ORDER BY occurred_at, id"
    )
    return [n["text"] for n in found]


async def test_a_reply_in_auto_pauses_it_with_a_note(ai: Ai) -> None:
    await ai.plan("pro")
    await ai.mode("auto")
    await ai.execute("UPDATE workspaces SET timezone = 'Asia/Kolkata' WHERE id = :w", w=ai.wid)

    assert (await post_message(ai.client, ai.setup)).status_code == 202

    [conv] = await ai.rows("SELECT ai_paused_until FROM conversations")
    until = conv["ai_paused_until"].astimezone(ZoneInfo("Asia/Kolkata"))
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    when = until.strftime("%H:%M") + (" tomorrow" if until.date() != today else "")
    assert await notes(ai) == [f"AI paused until {when} because you replied"]
    [note] = await ai.rows("SELECT * FROM messages WHERE direction = 'system'")
    assert (note["source"], note["kind"]) == ("system", "system")
    created = [p["message"] for _, p in await ai.events("message.created")]
    assert [m["direction"] for m in created] == ["outbound", "system"]
    # The list keeps showing the reply, not the note.
    [listed] = await ai.rows("SELECT last_message_direction FROM conversations")
    assert listed["last_message_direction"] == "outbound"

    # Another reply during the pause extends it without another note.
    assert (await post_message(ai.client, ai.setup, text="One more")).status_code == 202
    assert len(await notes(ai)) == 1


async def test_a_pause_without_auto_has_no_note(ai: Ai) -> None:
    assert (await post_message(ai.client, ai.setup)).status_code == 202
    [conv] = await ai.rows("SELECT ai_paused_until FROM conversations")
    assert conv["ai_paused_until"] is not None
    assert await notes(ai) == []


async def test_until_resumed_says_so(ai: Ai) -> None:
    await ai.plan("pro")
    await ai.mode("auto")
    await ai.execute("UPDATE ai_settings SET takeover_minutes = 0")
    assert (await post_message(ai.client, ai.setup)).status_code == 202
    assert await notes(ai) == ["AI paused until you resume it because you replied"]


async def test_a_reply_from_the_instagram_app_is_a_takeover(ai: Ai) -> None:
    await ai.plan("pro")
    await ai.mode("auto")
    await ai.suggest()

    assert await ai.receive("Replied from my phone", echo=True) is not None

    [conv] = await ai.rows("SELECT ai_paused_until FROM conversations")
    assert conv["ai_paused_until"] > datetime.now(UTC) + timedelta(minutes=110)
    assert len(await notes(ai)) == 1
    [row] = await ai.suggestions()
    assert row["status"] == "dismissed"


async def test_resume_ends_the_pause(ai: Ai) -> None:
    await ai.plan("pro")
    await ai.mode("auto")
    assert (await post_message(ai.client, ai.setup)).status_code == 202
    path = f"/conversations/{ai.conversation_id}"
    paused = (await ai.call("GET", path)).json()["ai"]["paused_until"]
    assert paused is not None

    resumed = await ai.call("PATCH", path, json={"resume_ai": True})

    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["ai"]["paused_until"] is None
    assert (await notes(ai))[-1] == "AI resumed"
    [conv] = await ai.rows("SELECT ai_paused_until FROM conversations")
    assert conv["ai_paused_until"] is None
    assert [p["message"]["text"] for _, p in await ai.events("message.created")][-1] == (
        "AI resumed"
    )
    # Resuming what isn't paused changes nothing.
    again = await ai.call("PATCH", path, json={"resume_ai": True})
    assert again.status_code == 200
    assert (await notes(ai)).count("AI resumed") == 1


# ---------------------------------------------------------------- AI settings and modes (T5.5)


async def test_ai_settings_read_and_replace(ai: Ai) -> None:
    shown = await ai.call("GET", "/ai-settings")
    assert shown.status_code == 200, shown.text
    defaults = shown.json()
    assert {k: v for k, v in defaults.items() if k != "updated_at"} == {
        "business_name": None,
        "business_description": None,
        "tone": "friendly",
        "emoji_policy": "light",
        "do_list": [],
        "dont_list": [],
        "escalation_phrases": [],
        "sign_off": None,
        "takeover_minutes": 120,
    }
    body = {
        "business_name": "  Maple Bakery ",
        "business_description": "Eggless cakes in Pune.",
        "tone": "playful",
        "emoji_policy": "lots",
        "do_list": ["Mention delivery", "mention  delivery", " "],
        "dont_list": [],
        "escalation_phrases": ["wholesale", "bulk order"],
        "sign_off": "",
        "takeover_minutes": 1440,
    }
    # One blank list item is not a valid item.
    assert (await ai.call("PUT", "/ai-settings", json=body)).status_code == 422
    body["do_list"] = ["Mention delivery", "mention  delivery"]
    saved = await ai.call("PUT", "/ai-settings", json=body)
    assert saved.status_code == 200, saved.text
    out = saved.json()
    assert (out["business_name"], out["sign_off"], out["do_list"]) == (
        "Maple Bakery",
        None,
        ["Mention delivery"],
    )
    assert (out["tone"], out["emoji_policy"], out["takeover_minutes"]) == ("playful", "lots", 1440)
    assert (await ai.call("GET", "/ai-settings")).json() == out


@pytest.mark.parametrize(
    "change",
    [
        {"tone": "angry"},
        {"emoji_policy": "some"},
        {"takeover_minutes": 45},
        {"do_list": [f"item {i}" for i in range(21)]},
        {"escalation_phrases": ["x" * 121]},
        {"business_description": "x" * 1001},
        {"sign_off": "x" * 61},
        {"surprise": True},
    ],
)
async def test_ai_settings_are_validated(ai: Ai, change: dict[str, Any]) -> None:
    response = await ai.call("PUT", "/ai-settings", json=change)
    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


async def test_a_free_workspace_cannot_set_auto(ai: Ai) -> None:
    """Done-when (T5.5): 402 on the account and on the conversation until the plan allows it."""
    account = f"/social-accounts/{ai.setup.account_id}"
    conversation = f"/conversations/{ai.conversation_id}"
    for path, body in (
        (account, {"ai_mode": "auto"}),
        (conversation, {"ai_mode_override": "auto"}),
    ):
        response = await ai.call("PATCH", path, json=body)
        assert (response.status_code, response.json()["code"]) == (402, "entitlement_required")

    await ai.plan("pro")
    assert (await ai.call("PATCH", account, json={"ai_mode": "auto"})).json()["ai_mode"] == "auto"
    detail = (await ai.call("GET", conversation)).json()
    assert detail["ai"]["effective_mode"] == "auto"
    override = await ai.call("PATCH", conversation, json={"ai_mode_override": "suggest"})
    assert override.json()["ai"] == {
        "effective_mode": "suggest",
        "override": "suggest",
        "paused_until": None,
    }
