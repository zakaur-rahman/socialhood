"""T5.4: suggested replies (TR-AI-06, FR-SUG-02, FR-SUG-03, FR-KB-06, F-08).

suggest_reply drafts from the conversation and knowledge (2 credits), stores a pending suggestion
(superseding the last one), records a knowledge gap when it cannot answer and publishes
suggestion.created; Regenerate (up to 5 per message) and Dismiss; sending a suggestion (sent or
edited_sent with the edit distance), a typed reply dismisses it, a new customer message
supersedes it; Conversation.pending_suggestion.

Done when: a question needing a fact absent from knowledge gives "Not in your knowledge" and
never a fabricated fact.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from socialhood.ai.provider import AIError
from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.runtime import Runtime
from socialhood.jobs.tasks import suggestions as suggestion_tasks
from socialhood.services.suggestions.knowledge_port import record_knowledge_gap
from socialhood.services.suggestions.service import Outcome
from socialhood.settings import get_settings
from tests.support.ai import make_suggestion
from tests.support.api import Clerk
from tests.support.inbox import make_thread
from tests.support.ingest import jobs
from tests.support.sending import clean_outbox, context, post_message
from tests.support.suggestions import (
    SHIPPING_REPLY,
    Ai,
    answer,
    cannot,
    make_ai,
)


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


# ---------------------------------------------------------------- the job (TR-AI-06)


async def test_a_suggestion_is_drafted_from_knowledge(ai: Ai) -> None:
    source = await ai.shipping_faq()
    [chunk] = await ai.rows("SELECT id FROM knowledge_chunks WHERE source_id = :s", s=source)
    ai.fake.respond("suggest", answer())

    assert await ai.suggest() is Outcome.STORED

    row = await ai.pending()
    assert (row["can_answer"], row["reply_text"]) == (True, SHIPPING_REPLY)
    assert row["used_chunk_ids"] == [chunk["id"]]
    assert row["model_confidence"] == pytest.approx(0.9)
    assert row["top_similarity"] >= get_settings().ai_retrieval_min_sim
    assert (row["message_id"], row["regeneration_index"]) == (ai.message_id, 0)
    assert (row["prompt_version"], row["input_tokens"], row["output_tokens"]) == (
        "suggest.v3",
        100,
        20,
    )
    # One call with TR-AI-06's settings; customer and knowledge text only in the contents.
    [call] = ai.fake.calls_for("suggest")
    assert (call.model, call.temperature, call.max_output_tokens, call.timeout_s) == (
        get_settings().ai_model_reply,
        0.4,
        600,
        12.0,
    )
    [turn] = call.contents
    assert "Customer [TARGET]: How much is shipping?" in turn.text
    assert "[k1] (How much is shipping?) [How much is shipping?] Q: How much is shipping?" in (
        turn.text
    )
    assert "How much is shipping" not in call.system
    assert [kind for _, kind in ai.fake.embed_calls] == ["query"]
    # 2 credits, one usage event.
    assert await ai.used() == 2
    [usage] = await ai.rows("SELECT feature, credits, ref_id FROM ai_usage_events")
    assert usage == {"feature": "reply_suggestion", "credits": 2, "ref_id": ai.message_id}

    [(_, created)] = await ai.events("suggestion.created")
    suggestion = created["suggestion"]
    assert created["conversation_id"] == str(ai.conversation_id)
    assert suggestion["status"] == "pending"
    assert suggestion["sources"] == [{"id": str(source), "title": "How much is shipping?"}]
    assert (suggestion["low_confidence"], suggestion["regenerations_left"]) == (False, 5)
    detail = (await ai.call("GET", f"/conversations/{ai.conversation_id}")).json()
    assert detail["pending_suggestion"] == suggestion


async def test_not_in_knowledge_never_invents_a_fact(ai: Ai) -> None:
    """Done-when (FR-SUG-03): no knowledge about Dubai → "Not in your knowledge"."""
    await ai.execute(
        "UPDATE messages SET text = 'Do you ship to Dubai?' WHERE id = :id", id=ai.message_id
    )
    ai.fake.respond("suggest", cannot())

    assert await ai.suggest() is Outcome.STORED

    row = await ai.pending()
    assert (row["can_answer"], row["reply_text"]) == (False, None)
    assert row["missing_info"] == "whether you ship to Dubai"
    assert row["missing_topic"] == "shipping to uae"
    [gap] = await ai.rows("SELECT * FROM knowledge_gaps")
    assert (gap["topic"], gap["status"], gap["occurrences"]) == ("shipping to uae", "open", 1)
    assert gap["example_message_ids"] == [ai.message_id]
    detail = (await ai.call("GET", f"/conversations/{ai.conversation_id}")).json()
    card = detail["pending_suggestion"]
    assert (card["can_answer"], card["reply_text"], card["missing_info"]) == (
        False,
        None,
        "whether you ship to Dubai",
    )
    assert card["low_confidence"] is True  # 0.2


async def test_a_fact_that_is_not_in_knowledge_is_never_offered(ai: Ai) -> None:
    """The output filter: a link, email or phone number knowledge doesn't have turns the draft
    into "Not in your knowledge" (FR-SUG-03)."""
    await ai.shipping_faq()
    ai.fake.respond("suggest", answer("Yes! Order at https://maple.example/sale today."))

    await ai.suggest()

    row = await ai.pending()
    assert (row["can_answer"], row["reply_text"]) == (False, None)
    assert row["missing_info"] == "the link https://maple.example/sale"
    assert row["missing_topic"] is None
    assert await ai.rows("SELECT id FROM knowledge_gaps") == []


async def test_a_link_from_knowledge_may_be_quoted(ai: Ai) -> None:
    await ai.shipping_faq()
    ai.fake.respond("suggest", answer("Track it at https://maple.example/track."))
    await ai.suggest()
    assert (await ai.pending())["reply_text"] == "Track it at https://maple.example/track."


async def test_only_the_knowledge_ids_given_are_kept(ai: Ai) -> None:
    source = await ai.shipping_faq()
    [chunk] = await ai.rows("SELECT id FROM knowledge_chunks WHERE source_id = :s", s=source)
    ai.fake.respond("suggest", answer(used=("k3", "k1", "k1")))
    await ai.suggest()
    assert (await ai.pending())["used_chunk_ids"] == [chunk["id"]]


async def test_a_long_reply_is_trimmed_at_a_sentence_to_instagrams_limit(ai: Ai) -> None:
    sentence = "We bake every cake to order in our Pune kitchen."
    ai.fake.respond("suggest", answer(" ".join([sentence] * 40), used=()))
    await ai.suggest()
    reply = (await ai.pending())["reply_text"]
    assert len(reply.encode()) <= 1000
    assert reply.endswith(sentence)


async def test_brand_voice_and_the_language_reach_the_prompt(ai: Ai) -> None:
    body = {
        "business_name": "Maple Bakery",
        "business_description": "Eggless cakes in Pune.",
        "tone": "concise",
        "emoji_policy": "none",
        "do_list": ["mention same-day delivery"],
        "dont_list": ["promise discounts"],
        "sign_off": "Team Maple",
        "takeover_minutes": 30,
    }
    assert (await ai.call("PUT", "/ai-settings", json=body)).status_code == 200
    await ai.analysis(language="hi-Latn")
    await ai.suggest()
    [call] = ai.fake.calls_for("suggest")
    for fragment in (
        "from Maple Bakery to a customer on Instagram",
        "Eggless cakes in Pune.",
        "Voice: concise. Emoji: none. Always: mention same-day delivery. "
        "Never: promise discounts. Sign-off: Team Maple.",
        "(hi-Latn)",
    ):
        assert fragment in call.system


async def test_the_query_joins_the_customers_last_10_minutes(ai: Ai) -> None:
    now = datetime.now(UTC)
    await ai.execute(
        "UPDATE messages SET occurred_at = :t WHERE id = :id",
        t=now - timedelta(hours=1),
        id=ai.message_id,
    )
    first = await ai.receive("Hi! Quick question", at=now - timedelta(minutes=12))
    second = await ai.receive("about your cakes", at=now - timedelta(minutes=5))
    last = await ai.receive("How much is shipping?", at=now)
    assert first is not None
    assert second is not None
    assert last is not None
    await ai.suggest(last)
    [(texts, kind)] = ai.fake.embed_calls
    assert (texts, kind) == (["about your cakes\nHow much is shipping?"], "query")


async def test_a_new_suggestion_supersedes_the_pending_one(ai: Ai) -> None:
    ai.fake.respond("suggest", answer(used=()), answer("Second draft.", used=()))
    await ai.suggest()
    first = await ai.pending()
    await ai.suggest(regeneration=1)

    statuses = [(r["status"], r["regeneration_index"]) for r in await ai.suggestions()]
    assert statuses == [("superseded", 0), ("pending", 1)]
    updated = await ai.events("suggestion.updated")
    assert [(p["suggestion"]["id"], p["suggestion"]["status"]) for _, p in updated] == [
        (str(first["id"]), "superseded")
    ]
    assert (await ai.pending())["reply_text"] == "Second draft."


async def test_open_gap_labels_reach_the_next_draft(ai: Ai) -> None:
    """C-034: the draft lists the open gap labels as data (KNOWN GAPS), so the model can reuse
    one exactly; suggest.v2 asks it to."""
    ai.fake.respond("suggest", cannot())
    await ai.suggest()  # records the gap "shipping to uae"
    await ai.suggest(regeneration=1)

    first, second = ai.fake.calls_for("suggest")
    assert "KNOWN GAPS" not in first.contents[0].text
    assert "KNOWN GAPS" in second.contents[0].text
    assert "- shipping to uae" in second.contents[0].text
    assert "KNOWN GAPS" in second.system  # the instruction, not the labels
    assert "shipping to uae" not in second.system.split("e.g.")[-1].split("\n")[1]


async def test_a_gap_counts_once_per_message(ai: Ai) -> None:
    ai.fake.respond("suggest", cannot())
    await ai.suggest()
    await ai.suggest(regeneration=1)
    [gap] = await ai.rows("SELECT occurrences FROM knowledge_gaps")
    assert gap["occurrences"] == 1


@pytest.mark.parametrize("reason", ["off", "answered", "handled", "newer"])
async def test_a_message_that_needs_no_suggestion_is_skipped(ai: Ai, reason: str) -> None:
    if reason == "off":
        await ai.mode("off")
    elif reason == "answered":
        assert (await post_message(ai.client, ai.setup, text="On it!")).status_code == 202
    elif reason == "handled":
        await ai.execute(
            "UPDATE messages SET automation_handled = true WHERE id = :id", id=ai.message_id
        )
    else:
        assert await ai.receive("hello?") is not None

    assert await ai.suggest() is Outcome.SKIPPED
    assert await ai.suggestions() == []
    assert ai.fake.calls_for("suggest") == []
    assert await ai.used() == 0


async def test_a_regeneration_is_drafted_after_a_reply(ai: Ai) -> None:
    assert (await post_message(ai.client, ai.setup, text="On it!")).status_code == 202
    assert await ai.suggest(regeneration=1) is Outcome.STORED


async def test_a_failed_call_stores_a_failed_suggestion(ai: Ai) -> None:
    ai.fake.respond("suggest", AIError("timeout", retryable=True))

    assert await ai.suggest() is Outcome.FAILED

    [row] = await ai.suggestions()
    assert (row["status"], row["error_code"], row["can_answer"]) == ("failed", "timeout", False)
    assert await ai.used() == 0  # refunded
    [(_, created)] = await ai.events("suggestion.created")
    assert created["suggestion"]["status"] == "failed"
    detail = (await ai.call("GET", f"/conversations/{ai.conversation_id}")).json()
    assert detail["pending_suggestion"] is None


async def test_used_up_credits_draft_nothing(ai: Ai) -> None:
    await ai.set_used(199)
    assert await ai.suggest() is Outcome.NO_CREDITS
    assert await ai.suggestions() == []
    assert ai.fake.calls_for("suggest") == []


async def test_auto_mode_asks_for_a_decision(ai: Ai) -> None:
    await ai.plan("pro")
    await ai.mode("auto")
    await ai.suggest()
    row = await ai.pending()
    [job] = await jobs("decide_auto_reply")
    assert job["queueing_lock"] == f"auto:{row['id']}"
    assert job["args"] == {"workspace_id": str(ai.wid), "suggestion_id": str(row["id"])}

    await ai.suggest(regeneration=1)  # a person asked for this one: no decision
    assert len(await jobs("decide_auto_reply")) == 1


# ---------------------------------------------------------------- regenerate and dismiss (F-08)


async def test_regenerate_queues_the_next_draft_up_to_five(ai: Ai) -> None:
    path = f"/conversations/{ai.conversation_id}/suggestions"
    response = await ai.call("POST", path)
    assert response.status_code == 202
    [job] = await jobs("suggest_reply")
    assert job["queueing_lock"] == f"suggest:{ai.message_id}:0"
    assert job["args"]["regeneration"] == 0

    for n in range(6):
        await ai.suggest(regeneration=n)
    assert (await ai.pending())["regeneration_index"] == 5
    detail = (await ai.call("GET", f"/conversations/{ai.conversation_id}")).json()
    assert detail["pending_suggestion"]["regenerations_left"] == 0

    limited = await ai.call("POST", path)
    assert limited.status_code == 409
    assert "up to 5 times" in limited.json()["detail"]


async def test_regenerate_needs_ai_and_credits(ai: Ai) -> None:
    path = f"/conversations/{ai.conversation_id}/suggestions"
    await ai.suggest()
    assert (await ai.call("POST", path)).status_code == 202
    [job] = await jobs("suggest_reply")
    assert job["queueing_lock"] == f"suggest:{ai.message_id}:1"

    await ai.set_used(199)
    response = await ai.call("POST", path)
    assert (response.status_code, response.json()["code"]) == (402, "quota_exceeded")

    await ai.mode("off")
    response = await ai.call("POST", path)
    assert (response.status_code, response.json()["code"]) == (409, "conflict")


async def test_dismiss_closes_the_card(ai: Ai) -> None:
    await ai.suggest()
    row = await ai.pending()

    response = await ai.call("POST", f"/suggestions/{row['id']}/dismiss")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "dismissed"
    [(_, updated)] = await ai.events("suggestion.updated")
    assert updated["suggestion"]["status"] == "dismissed"
    again = await ai.call("POST", f"/suggestions/{row['id']}/dismiss")
    assert again.json()["status"] == "dismissed"
    assert len(await ai.events("suggestion.updated")) == 1
    missing = await ai.call("POST", f"/suggestions/{uuid.uuid4()}/dismiss")
    assert missing.status_code == 404


# ---------------------------------------------------------------- what happens to a suggestion


async def test_sending_the_suggestion_marks_it_sent(ai: Ai) -> None:
    ai.fake.respond("suggest", answer(used=()))
    await ai.suggest()
    row = await ai.pending()

    response = await post_message(
        ai.client, ai.setup, text=f"  {SHIPPING_REPLY} ", suggestion_id=str(row["id"])
    )
    assert response.status_code == 202, response.text
    assert response.json()["suggestion_id"] == str(row["id"])

    [sent] = await ai.suggestions()
    assert (sent["status"], sent["edit_distance"]) == ("sent", 0.0)
    assert str(sent["sent_message_id"]) == response.json()["id"]
    [(_, updated)] = await ai.events("suggestion.updated")
    assert updated["suggestion"]["status"] == "sent"


async def test_an_edited_suggestion_records_the_edit_distance(ai: Ai) -> None:
    ai.fake.respond("suggest", answer("Shipping is free.", used=()))
    await ai.suggest()
    row = await ai.pending()

    response = await post_message(
        ai.client, ai.setup, text="Shipping is free!", suggestion_id=str(row["id"])
    )
    assert response.status_code == 202, response.text
    [sent] = await ai.suggestions()
    assert sent["status"] == "edited_sent"
    assert sent["edit_distance"] == pytest.approx(1 / 17, abs=1e-4)


async def test_a_typed_reply_dismisses_the_suggestion(ai: Ai) -> None:
    await ai.suggest()
    assert (await post_message(ai.client, ai.setup, text="Let me check")).status_code == 202
    [row] = await ai.suggestions()
    assert row["status"] == "dismissed"


async def test_a_suggestion_from_another_conversation_is_refused(
    ai: Ai, engine: AsyncEngine
) -> None:
    other = await make_thread(engine, workspace_id=ai.wid, account_id=ai.setup.account_id)
    elsewhere = await make_suggestion(
        engine,
        workspace_id=ai.wid,
        conversation_id=other.conversation_id,
        message_id=other.message_ids[0],
    )
    response = await post_message(ai.client, ai.setup, suggestion_id=str(elsewhere))
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "suggestion_id"


async def test_a_new_customer_message_supersedes_the_suggestion(ai: Ai) -> None:
    await ai.suggest()
    assert await ai.receive("Also, do you deliver on Sundays?") is not None
    [row] = await ai.suggestions()
    assert row["status"] == "superseded"
    [(_, updated)] = await ai.events("suggestion.updated")
    assert updated["suggestion"]["status"] == "superseded"


# ---------------------------------------------------------------- the jobs


@pytest.fixture
def worker(ai: Ai, monkeypatch: pytest.MonkeyPatch) -> Runtime:
    rt = Runtime(
        settings=ai.app.state.settings,
        sessionmaker=ai.maker,
        redis=ai.redis,
        http=ai.app.state.http,
    )
    monkeypatch.setattr(suggestion_tasks, "runtime", lambda: rt)
    return rt


async def test_suggest_reply_retries_a_retryable_error_once(ai: Ai, worker: Runtime) -> None:
    ai.fake.respond("suggest", AIError("timeout", retryable=True))
    kwargs = {
        "workspace_id": str(ai.wid),
        "conversation_id": str(ai.conversation_id),
        "message_id": str(ai.message_id),
    }
    with pytest.raises(AIError):
        await suggestion_tasks.suggest_reply(context(0), **kwargs)
    assert await ai.suggestions() == []  # the queue runs it again

    await suggestion_tasks.suggest_reply(context(1), **kwargs)  # the last try
    [row] = await ai.suggestions()
    assert (row["status"], row["error_code"]) == ("failed", "timeout")


def test_only_retryable_ai_errors_are_retried() -> None:
    job = context(0).job
    retry = suggestion_tasks.SUGGEST_RETRY
    assert retry.get_retry_decision(exception=AIError("timeout", retryable=True), job=job)
    assert retry.get_retry_decision(exception=AIError("invalid_output"), job=job) is None
    assert retry.get_retry_decision(exception=RuntimeError("boom"), job=job) is None
    last = context(1).job
    assert retry.get_retry_decision(exception=AIError("timeout", retryable=True), job=last) is None


async def test_decide_auto_reply_runs_the_policy(ai: Ai, worker: Runtime) -> None:
    await ai.suggest()
    row = await ai.pending()
    await suggestion_tasks.decide_auto_reply(workspace_id=str(ai.wid), suggestion_id=str(row["id"]))
    [decision] = await ai.rows("SELECT outcome, reason FROM ai_decisions")
    assert decision == {"outcome": "skipped", "reason": "mode_not_auto"}


# ---------------------------------------------------------------- knowledge gaps (adapter)


async def test_similar_questions_count_as_one_gap_and_a_dismissed_one_reopens(ai: Ai) -> None:
    now = datetime.now(UTC)
    with workspace_scope(ai.wid):
        async with ai.maker() as session:
            first = await record_knowledge_gap(session, "Shipping to UAE?", ai.message_id, now)
            same = await record_knowledge_gap(session, "shipping to the uae", None, now)
            other = await record_knowledge_gap(session, "refund policy", None, now)
            assert await record_knowledge_gap(session, " ?! ", None, now) is None
            await session.commit()
    assert first == same != other
    [gap] = await ai.rows("SELECT * FROM knowledge_gaps WHERE id = :id", id=first)
    assert (gap["topic"], gap["topic_normalized"], gap["occurrences"]) == (
        "Shipping to UAE?",
        "shipping to uae",
        2,
    )
    await ai.execute("UPDATE knowledge_gaps SET status = 'dismissed', dismissed_at = now()")
    with workspace_scope(ai.wid):
        async with ai.maker() as session:
            again = await record_knowledge_gap(session, "shipping to uae", None, now)
            await session.commit()
    assert again == first
    [reopened] = await ai.rows(
        "SELECT status, occurrences FROM knowledge_gaps WHERE id = :id", id=first
    )
    assert reopened == {"status": "open", "occurrences": 3}


# ---------------------------------------------------------------- small talk (C-062)

BUSINESS_INFO = cannot("information about the business", "business information")


async def small_talk(ai: Ai, text: str, *, intent: str = "greeting", language: str = "en") -> None:
    """The customer's message is ``text``, analysed with ``intent`` and ``language``."""
    await ai.execute("UPDATE messages SET text = :t WHERE id = :id", t=text, id=ai.message_id)
    await ai.analysis(intent=intent, language=language, sentiment_score=0.0, lead_score=10)


async def test_a_greeting_gets_a_reply_without_knowledge(ai: Ai) -> None:
    """Seen live: "Hi" came back "Not in your knowledge" with the gap "business information".
    The model declines again here; the suggestion is a friendly reply all the same."""
    await small_talk(ai, "Hi")
    ai.fake.respond("suggest", BUSINESS_INFO)

    assert await ai.suggest() is Outcome.STORED

    row = await ai.pending()
    assert (row["can_answer"], row["reply_text"]) == (True, "Hi! How can I help you today?")
    assert (row["missing_info"], row["missing_topic"]) == (None, None)
    assert row["used_chunk_ids"] == []
    assert row["model_confidence"] == pytest.approx(0.9)
    assert row["prompt_version"] == "suggest.v3"
    assert await ai.rows("SELECT id FROM knowledge_gaps") == []
    [(_, created)] = await ai.events("suggestion.created")
    assert created["suggestion"]["can_answer"] is True
    assert created["suggestion"]["low_confidence"] is False
    # suggest.v3 tells the model small talk needs no knowledge, and never a business fact.
    [call] = ai.fake.calls_for("suggest")
    assert "Small talk needs no KNOWLEDGE." in call.system
    assert "states no business fact" in call.system


async def test_the_models_own_small_talk_reply_is_kept(ai: Ai) -> None:
    await small_talk(ai, "Hi")
    reply = "Hi there! Welcome to Maple. What can I do for you?"
    ai.fake.respond("suggest", answer(reply, used=(), confidence=0.95))

    await ai.suggest()

    row = await ai.pending()
    assert (row["can_answer"], row["reply_text"]) == (True, reply)
    assert row["model_confidence"] == pytest.approx(0.95)
    assert await ai.rows("SELECT id FROM knowledge_gaps") == []


@pytest.mark.parametrize(
    ("text", "intent", "expected"),
    [
        ("thanks!", "feedback", "You're welcome! Let us know if you need anything else."),
        ("Thank you so much 🙏", "other", "You're welcome! Let us know if you need anything else."),
        ("ok bye", "other", "Thanks for reaching out! Take care."),
    ],
)
async def test_thanks_and_goodbyes_get_a_reply_too(
    ai: Ai, text: str, intent: str, expected: str
) -> None:
    await small_talk(ai, text, intent=intent)
    ai.fake.respond("suggest", BUSINESS_INFO)

    await ai.suggest()

    row = await ai.pending()
    assert (row["can_answer"], row["reply_text"]) == (True, expected)
    assert await ai.rows("SELECT id FROM knowledge_gaps") == []


@pytest.mark.parametrize(
    ("text", "language", "expected"),
    [
        ("namaste", "hi-Latn", "Namaste! Bataiye, hum aapki kya madad kar sakte hain?"),
        ("kaise ho?", "en", "Namaste! Bataiye, hum aapki kya madad kar sakte hain?"),
        ("Hi", "hi-Latn", "Namaste! Bataiye, hum aapki kya madad kar sakte hain?"),
        ("नमस्ते जी", "hi", "नमस्ते! बताइए, हम आपकी क्या मदद कर सकते हैं?"),
        ("shukriya bhai", "hi-Latn", "Aapka swagat hai! Kuch aur chahiye toh bataiye."),
    ],
)
async def test_hindi_and_hinglish_small_talk_is_answered_in_kind(
    ai: Ai, text: str, language: str, expected: str
) -> None:
    await small_talk(ai, text, language=language)
    ai.fake.respond("suggest", BUSINESS_INFO)

    await ai.suggest()

    row = await ai.pending()
    assert (row["can_answer"], row["reply_text"]) == (True, expected)
    assert await ai.rows("SELECT id FROM knowledge_gaps") == []


async def test_a_greeting_with_a_question_still_needs_knowledge(ai: Ai) -> None:
    """ "Hi, what's the price?" is a pricing question: no knowledge, no answer, and the gap."""
    await small_talk(ai, "Hi, what's the price?", intent="pricing")
    ai.fake.respond("suggest", cannot("the price of the red dress", "red dress price"))

    await ai.suggest()

    row = await ai.pending()
    assert (row["can_answer"], row["reply_text"]) == (False, None)
    assert row["missing_topic"] == "red dress price"
    [gap] = await ai.rows("SELECT topic, occurrences FROM knowledge_gaps")
    assert gap == {"topic": "red dress price", "occurrences": 1}


async def test_small_talk_the_analysis_reads_as_business_is_left_to_the_model(ai: Ai) -> None:
    """ "ok" answering "Shall I book it?" is a purchase: the model's answer stands."""
    await small_talk(ai, "ok", intent="purchase")
    ai.fake.respond("suggest", cannot("whether the booking is confirmed", "booking confirmation"))

    await ai.suggest()

    row = await ai.pending()
    assert row["can_answer"] is False
    assert len(await ai.rows("SELECT id FROM knowledge_gaps")) == 1
