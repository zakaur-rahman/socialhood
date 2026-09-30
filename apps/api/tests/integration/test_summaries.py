"""T5.7: conversation summaries (FR-AI-03). Done when: the summary refreshes after 8 new
messages. Plus: the call, storage and event, the earlier summary as context, analysis off and
used-up credits."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from socialhood.jobs.app import app as jobs_app
from tests.support.ai import make_source, make_suggestion
from tests.support.analysis import Inbox, make_inbox, use_credits
from tests.support.ingest import stream

CUSTOMER = "igsid_arjun"


@pytest.fixture
async def inbox(engine: AsyncEngine, redis: Redis, clean_db: None, queue: None) -> Inbox:
    return await make_inbox(engine, redis)


async def summary_jobs() -> list[dict[str, Any]]:
    return list(
        await jobs_app.connector.execute_query_all_async(
            "SELECT id, status FROM procrastinate_jobs"
            " WHERE task_name = 'summarize_conversation' AND status = 'todo'"
        )
    )


async def mark_done() -> None:
    await jobs_app.connector.execute_query_async(
        "UPDATE procrastinate_jobs SET status = 'succeeded' WHERE status = 'todo'"
    )


async def test_the_summary_refreshes_after_eight_new_messages(
    inbox: Inbox, redis: Redis, fake_ai: FakeProvider
) -> None:
    fake_ai.respond("analysis", {**_calm(), "needs_reply": False})
    fake_ai.respond(
        "summary",
        {"summary": "Arjun wants the blue kurta in M.", "next_step": "Confirm stock."},
        {"summary": "Arjun ordered the blue kurta.", "next_step": None},
    )
    t0 = datetime.now(UTC) - timedelta(hours=1)
    for i in range(8):
        await inbox.dm(CUSTOMER, f"message {i}", at=t0 + timedelta(minutes=i))
    conv_id = await inbox.conversation_id(CUSTOMER)
    assert (await inbox.analyze(conv_id)).summary_queued
    await mark_done()
    await redis.flushdb()

    run = await inbox.summarize(conv_id, now=t0 + timedelta(minutes=10))

    assert run.outcome == "summarised"
    [call] = fake_ai.calls_for("summary")
    assert (call.model, call.max_output_tokens, call.timeout_s) == (
        inbox.settings.ai_model_reply,
        400,
        12.0,
    )
    assert call.contents[0].text.splitlines()[1] == "customer: message 0"
    assert "message 0" not in call.system
    conv = await inbox.conversation(conv_id)
    assert (conv["summary"], conv["summary_next_step"]) == (
        "Arjun wants the blue kurta in M.",
        "Confirm stock.",
    )
    assert conv["summary_updated_at"] == t0 + timedelta(minutes=10)
    assert conv["messages_since_summary"] == 0
    [(kind, payload)] = await stream(redis, inbox.wid)
    assert kind == "conversation.updated"
    assert payload["conversation"]["id"] == str(conv_id)
    assert payload["summary"]["text"] == "Arjun wants the blue kurta in M."
    assert payload["summary"]["next_step"] == "Confirm stock."
    [usage] = await inbox.rows(
        "SELECT credits FROM ai_usage_events WHERE feature = 'conversation_summary'"
    )
    assert usage["credits"] == 1

    # Seven more messages: not yet. The eighth: refreshed, with the earlier summary as context.
    for i in range(8, 15):
        await inbox.dm(CUSTOMER, f"message {i}", at=t0 + timedelta(minutes=11 + i))
    assert not (await inbox.analyze(conv_id)).summary_queued
    assert await summary_jobs() == []
    await inbox.dm(CUSTOMER, "message 15", at=t0 + timedelta(minutes=30))
    assert (await inbox.analyze(conv_id)).summary_queued
    assert len(await summary_jobs()) == 1

    await inbox.summarize(conv_id, now=t0 + timedelta(minutes=31))
    second = fake_ai.calls_for("summary")[1]
    assert second.contents[0].text.startswith(
        "EARLIER SUMMARY: Arjun wants the blue kurta in M.\n\nCONVERSATION"
    )
    conv = await inbox.conversation(conv_id)
    assert (conv["summary"], conv["summary_next_step"]) == ("Arjun ordered the blue kurta.", None)


async def test_the_next_step_is_grounded_in_the_knowledge_the_latest_draft_used(
    inbox: Inbox, engine: AsyncEngine, fake_ai: FakeProvider
) -> None:
    """summary.v2 (C-063): KNOWLEDGE is the chunks of the newest draft that used any, read from
    the database: the same single call, no retrieval (no embedding call)."""
    message_id = await inbox.dm(CUSTOMER, "How much is shipping to Pune?")
    conv_id = await inbox.conversation_id(CUSTOMER)
    fake_ai.respond(
        "summary",
        {"summary": "Arjun asked about shipping.", "next_step": None},
        {
            "summary": "Arjun asked about shipping to Pune.",
            "next_step": "  Tell him shipping is free on orders over ₹999.  ",
        },
    )
    await inbox.summarize(conv_id)
    [first] = fake_ai.calls_for("summary")
    assert len(first.contents) == 1  # no draft used knowledge yet

    source = await make_source(engine, workspace_id=inbox.wid)
    [chunk] = await inbox.rows("SELECT id FROM knowledge_chunks WHERE source_id = :s", s=source)
    common = {"workspace_id": inbox.wid, "conversation_id": conv_id, "message_id": message_id}
    await make_suggestion(engine, **common, status="sent", used_chunk_ids=[chunk["id"]])
    # A newer draft without knowledge doesn't hide it.
    await make_suggestion(
        engine, **common, status="dismissed", can_answer=False, regeneration_index=1
    )

    assert (await inbox.summarize(conv_id)).outcome == "summarised"

    second = fake_ai.calls_for("summary")[1]
    assert "next_step: one short sentence" in second.system
    assert second.contents[1].text == (
        "KNOWLEDGE:\n- [How much is shipping?] Q: How much is shipping? "
        "A: Shipping is free on orders over ₹999."
    )
    assert fake_ai.embed_calls == []
    conv = await inbox.conversation(conv_id)
    assert conv["summary_next_step"] == "Tell him shipping is free on orders over ₹999."


async def test_no_summary_with_analysis_off_or_credits_used_up(
    inbox: Inbox, engine: AsyncEngine, fake_ai: FakeProvider
) -> None:
    await inbox.dm(CUSTOMER, "hi")
    conv_id = await inbox.conversation_id(CUSTOMER)
    await inbox.set("social_accounts", inbox.account_id, ai_analysis_enabled=False)
    assert (await inbox.summarize(conv_id)).outcome == "analysis_off"

    await inbox.set("social_accounts", inbox.account_id, ai_analysis_enabled=True)
    await use_credits(engine, inbox.wid, 200, now=datetime.now(UTC))
    assert (await inbox.summarize(conv_id)).outcome == "quota_exhausted"
    assert fake_ai.calls == []
    assert (await inbox.conversation(conv_id))["summary"] is None


def _calm() -> dict[str, Any]:
    return {
        "intent": "product_inquiry",
        "sentiment": "neutral",
        "sentiment_score": 0.0,
        "priority": "medium",
        "lead_score": 40,
        "language": "en",
        "topics": [],
        "needs_reply": True,
        "needs_human": False,
        "needs_human_reason": None,
    }
