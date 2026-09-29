"""T5.2: message analysis (TR-AI-05, FR-AI-01, FR-AI-02, FR-AI-05).

Done when: a burst of 5 messages produces 1 analysis; with the credits used up there is no call and
messaging is unaffected. Plus: the call's settings and TARGET, clamping, the conversation's cached
signals, events, the suggest_reply and summary follow-ups, analysis off (FR-PRV-02), retries and
the re-queue when a newer message arrived during the call.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from socialhood.ai.provider import AIError
from socialhood.jobs.app import app as jobs_app
from tests.support.analysis import Inbox, make_inbox, use_credits
from tests.support.ingest import jobs, stream

CUSTOMER = "igsid_priya"


@pytest.fixture
async def inbox(engine: AsyncEngine, redis: Redis, clean_db: None, queue: None) -> Inbox:
    return await make_inbox(engine, redis)


def analysis(**values: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "intent": "pricing",
        "sentiment": "neutral",
        "sentiment_score": 0.1,
        "priority": "medium",
        "lead_score": 65,
        "language": "en",
        "topics": ["red dress"],
        "needs_reply": True,
        "needs_human": False,
        "needs_human_reason": None,
    }
    return {**base, **values}


async def job_rows(task: str) -> list[dict[str, Any]]:
    return list(
        await jobs_app.connector.execute_query_all_async(
            "SELECT task_name, queue_name, queueing_lock, lock, args, status"
            " FROM procrastinate_jobs WHERE task_name = %(t)s ORDER BY id",
            t=task,
        )
    )


async def start_jobs() -> None:
    """The worker picked up every waiting job (their queueing locks are free again)."""
    await jobs_app.connector.execute_query_async(
        "UPDATE procrastinate_jobs SET status = 'doing' WHERE status = 'todo'"
    )


async def test_a_burst_of_five_messages_is_analysed_once(
    inbox: Inbox, fake_ai: FakeProvider
) -> None:
    fake_ai.respond("analysis", analysis())
    t0 = datetime.now(UTC)
    texts = ["hi", "do you have the red dress", "in M?", "and in blue", "how much is it?"]
    ids = [
        await inbox.dm(CUSTOMER, body, at=t0 + timedelta(seconds=4 * i))
        for i, body in enumerate(texts)
    ]
    conv_id = await inbox.conversation_id(CUSTOMER)

    [job] = await jobs("analyze_conversation")
    assert job["queueing_lock"] == f"analyze:{conv_id}"
    assert job["queue_name"] == "interactive"
    assert job["deferred"]  # 4 s: the burst joins it
    assert job["args"] == {"workspace_id": str(inbox.wid), "conversation_id": str(conv_id)}
    [row] = await job_rows("analyze_conversation")
    assert row["lock"] == f"analyze:{conv_id}"  # one conversation's analyses never overlap

    run = await inbox.analyze(conv_id)

    assert run.outcome == "analysed"
    [call] = fake_ai.calls_for("analysis")
    assert (call.model, call.temperature, call.max_output_tokens, call.timeout_s) == (
        inbox.settings.ai_model_analysis,
        0.0,
        400,
        8.0,
    )
    [turn] = call.contents
    assert turn.role == "user"
    lines = turn.text.splitlines()
    assert lines[0] == "CONVERSATION (oldest first):"
    assert lines[1:] == [
        "customer: hi",
        "customer: do you have the red dress",
        "customer: in M?",
        "customer: and in blue",
        "customer [TARGET]: how much is it?",
    ]
    # Customer text is data, never in the system prompt (TR-AI-04); the workspace name stands in
    # for the business name.
    assert "how much" not in call.system
    [workspace] = await inbox.rows("SELECT name FROM workspaces WHERE id = :w", w=inbox.wid)
    assert f"for {workspace['name']}:" in call.system
    stored = await inbox.rows("SELECT message_id, prompt_version FROM message_analyses")
    assert stored == [{"message_id": ids[-1], "prompt_version": "analysis.v1"}]

    # Nothing new: no second call, no second credit.
    assert (await inbox.analyze(conv_id)).outcome == "already_analysed"
    assert len(fake_ai.calls_for("analysis")) == 1
    [usage] = await inbox.rows("SELECT feature, credits, outcome, ref_id FROM ai_usage_events")
    assert usage == {
        "feature": "message_analysis",
        "credits": 1,
        "outcome": "ok",
        "ref_id": ids[-1],
    }


async def test_the_analysis_is_stored_clamped_and_cached_on_the_conversation(
    inbox: Inbox, redis: Redis, fake_ai: FakeProvider
) -> None:
    fake_ai.respond(
        "analysis",
        analysis(
            intent="refund",
            sentiment="negative",
            sentiment_score=-3.5,
            priority="high",
            lead_score=140,
            language=" hi-Latn ",
            topics=["Late Delivery", "late  delivery", "Refund", "packaging", "tone"],
            needs_human=True,
            needs_human_reason="refund",
        ),
        analysis(intent="other", lead_score=20),  # the follow-up below
    )
    message_id = await inbox.dm(CUSTOMER, "mera order late hai, refund chahiye")
    conv_id = await inbox.conversation_id(CUSTOMER)
    await redis.flushdb()

    run = await inbox.analyze(conv_id)

    [row] = await inbox.rows("SELECT * FROM message_analyses")
    assert run.analysis_id == row["id"]
    assert (row["message_id"], row["conversation_id"]) == (message_id, conv_id)
    assert (row["sentiment_score"], row["lead_score"], row["language"]) == (-1.0, 100, "hi-Latn")
    assert row["topics"] == ["late delivery", "refund", "packaging"]
    assert (row["needs_human"], row["needs_human_reason"]) == (True, "refund")
    assert (row["model"], row["input_tokens"], row["output_tokens"]) == (
        "gemini-3.5-flash-lite",
        100,
        20,
    )
    conv = await inbox.conversation(conv_id)
    assert (conv["last_intent"], conv["last_sentiment"], conv["priority"], conv["lead_score"]) == (
        "refund",
        "negative",
        "high",
        100,
    )
    assert (conv["needs_human"], conv["needs_human_reason"]) == (True, "refund")

    published = await stream(redis, inbox.wid)
    assert [t for t, _ in published] == ["analysis.created", "conversation.updated"]
    created = published[0][1]
    assert created["conversation_id"] == str(conv_id)
    assert created["analysis"]["id"] == str(row["id"])
    assert created["analysis"]["intent"] == "refund"
    assert created["analysis"]["corrected"] is False
    assert published[1][1]["conversation"]["signal"] == "needs_you"

    # A calm follow-up does not clear the escalation nobody answered (F-09 clears it on reply).
    await inbox.dm(CUSTOMER, "?")
    await inbox.analyze(conv_id)
    conv = await inbox.conversation(conv_id)
    assert (conv["needs_human"], conv["needs_human_reason"], conv["lead_score"]) == (
        True,
        "refund",
        20,
    )
    assert conv["last_intent"] == "other"


@pytest.mark.parametrize(
    ("account_mode", "override", "needs_reply", "queued"),
    [
        ("suggest", None, True, True),
        ("auto", None, True, True),
        ("off", None, True, False),
        ("off", "suggest", True, True),
        ("suggest", "off", True, False),
        ("suggest", None, False, False),
    ],
)
async def test_suggest_reply_follows_when_a_reply_is_needed(
    inbox: Inbox,
    fake_ai: FakeProvider,
    account_mode: str,
    override: str | None,
    needs_reply: bool,
    queued: bool,
) -> None:
    await inbox.set("social_accounts", inbox.account_id, ai_mode=account_mode)
    fake_ai.respond("analysis", analysis(needs_reply=needs_reply))
    message_id = await inbox.dm(CUSTOMER, "how much is shipping?")
    conv_id = await inbox.conversation_id(CUSTOMER)
    await inbox.set("conversations", conv_id, ai_mode_override=override)

    run = await inbox.analyze(conv_id)

    assert run.suggestion_queued is queued
    suggest = await job_rows("suggest_reply")
    if not queued:
        assert suggest == []
        return
    [job] = suggest
    assert job["queue_name"] == "interactive"
    assert job["queueing_lock"] == f"suggest:{message_id}:0"
    assert job["args"] == {
        "workspace_id": str(inbox.wid),
        "conversation_id": str(conv_id),
        "message_id": str(message_id),
    }


async def test_with_credits_used_up_nothing_is_called_and_messaging_carries_on(
    inbox: Inbox, engine: AsyncEngine, fake_ai: FakeProvider
) -> None:
    await use_credits(engine, inbox.wid, 200, now=datetime.now(UTC))
    await inbox.dm(CUSTOMER, "hello?")
    conv_id = await inbox.conversation_id(CUSTOMER)

    run = await inbox.analyze(conv_id)

    assert run.outcome == "quota_exhausted"
    assert fake_ai.calls == []
    assert await inbox.rows("SELECT id FROM message_analyses") == []
    assert await inbox.rows("SELECT id FROM ai_usage_events") == []
    assert await job_rows("suggest_reply") == []
    [notice] = await inbox.rows("SELECT type FROM notifications")
    assert notice["type"] == "ai_credits_100"  # the banner's companion (FR-AI-05)
    # Messaging is unaffected: the next message is stored and counted as usual.
    await inbox.dm(CUSTOMER, "anyone there?")
    conv = await inbox.conversation(conv_id)
    assert (conv["unread_count"], conv["awaiting_reply"], conv["last_message_preview"]) == (
        2,
        True,
        "anyone there?",
    )
    assert (conv["last_intent"], conv["lead_score"]) == (None, None)


async def test_with_analysis_off_no_text_reaches_the_provider(
    inbox: Inbox, fake_ai: FakeProvider
) -> None:
    await inbox.set("social_accounts", inbox.account_id, ai_analysis_enabled=False)
    await inbox.dm(CUSTOMER, "my card number is 4111…")
    conv_id = await inbox.conversation_id(CUSTOMER)

    assert await jobs("analyze_conversation") == []  # FR-PRV-02: not even queued
    assert (await inbox.analyze(conv_id)).outcome == "analysis_off"
    assert fake_ai.calls == []


async def test_a_retryable_failure_refunds_and_raises_for_the_retry(
    inbox: Inbox, fake_ai: FakeProvider
) -> None:
    fake_ai.respond("analysis", AIError("timeout", retryable=True))
    await inbox.dm(CUSTOMER, "hi")
    conv_id = await inbox.conversation_id(CUSTOMER)

    with pytest.raises(AIError):
        await inbox.analyze(conv_id)

    [counter] = await inbox.rows("SELECT used FROM usage_counters")
    assert counter["used"] == 0
    [event] = await inbox.rows("SELECT credits, outcome FROM ai_usage_events")
    assert event == {"credits": 0, "outcome": "timeout"}
    assert await inbox.rows("SELECT id FROM message_analyses") == []


async def test_invalid_output_ends_the_job_without_an_analysis(
    inbox: Inbox, fake_ai: FakeProvider
) -> None:
    fake_ai.respond("analysis", AIError("invalid_output"))
    await inbox.dm(CUSTOMER, "hi")
    conv_id = await inbox.conversation_id(CUSTOMER)

    assert (await inbox.analyze(conv_id)).outcome == "failed"
    assert await inbox.rows("SELECT id FROM message_analyses") == []


async def test_a_message_that_arrives_during_the_call_queues_another_analysis(
    inbox: Inbox, fake_ai: FakeProvider
) -> None:
    await inbox.dm(CUSTOMER, "hi")
    conv_id = await inbox.conversation_id(CUSTOMER)
    await start_jobs()
    # A newer customer message is stored while the model answers (written directly, so ingest's
    # own enqueue does not hide the job's re-queue).
    original = fake_ai.generate_json

    async def generate_json(**kwargs: Any) -> Any:
        result = await original(**kwargs)
        async with inbox.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO messages (workspace_id, conversation_id, social_account_id,"
                    " direction, source, kind, text, occurred_at, status)"
                    " VALUES (:w, :c, :a, 'inbound', 'customer', 'text', 'one more thing',"
                    " now() + interval '1 second', 'received')"
                ),
                {"w": inbox.wid, "c": conv_id, "a": inbox.account_id},
            )
        return result

    fake_ai.generate_json = generate_json  # type: ignore[method-assign]

    run = await inbox.analyze(conv_id)

    assert (run.outcome, run.requeued) == ("analysed", True)
    todo = [j for j in await job_rows("analyze_conversation") if j["status"] == "todo"]
    assert [j["queueing_lock"] for j in todo] == [f"analyze:{conv_id}"]


async def test_eight_new_messages_queue_a_summary(inbox: Inbox, fake_ai: FakeProvider) -> None:
    fake_ai.respond("analysis", analysis(needs_reply=False))
    t0 = datetime.now(UTC) - timedelta(minutes=30)
    for i in range(7):
        await inbox.dm(CUSTOMER, f"message {i}", at=t0 + timedelta(minutes=i))
    conv_id = await inbox.conversation_id(CUSTOMER)

    run = await inbox.analyze(conv_id)
    assert run.summary_queued is False
    assert (await inbox.conversation(conv_id))["messages_since_summary"] == 7
    assert await job_rows("summarize_conversation") == []

    await inbox.dm(CUSTOMER, "message 7", at=t0 + timedelta(minutes=8))
    run = await inbox.analyze(conv_id)

    assert run.summary_queued is True
    assert (await inbox.conversation(conv_id))["messages_since_summary"] == 8
    [job] = await job_rows("summarize_conversation")
    assert (job["queue_name"], job["queueing_lock"]) == ("bulk", f"convsum:{conv_id}")
    assert job["args"] == {"workspace_id": str(inbox.wid), "conversation_id": str(conv_id)}


async def test_the_newest_customer_message_is_the_target_even_after_replies(
    inbox: Inbox, fake_ai: FakeProvider
) -> None:
    t0 = datetime.now(UTC) - timedelta(minutes=10)
    await inbox.dm(CUSTOMER, "is it in stock?", at=t0)
    conv_id = await inbox.conversation_id(CUSTOMER)
    await inbox.business(conv_id, "Yes, in all sizes.", at=t0 + timedelta(minutes=1))

    await inbox.analyze(conv_id)

    [call] = fake_ai.calls_for("analysis")
    assert call.contents[0].text.splitlines()[1:] == [
        "customer [TARGET]: is it in stock?",
        "business: Yes, in all sizes.",
    ]


async def test_an_unknown_conversation_is_skipped(inbox: Inbox, fake_ai: FakeProvider) -> None:
    assert (await inbox.analyze(uuid.uuid4())).outcome == "not_found"
    assert fake_ai.calls == []
