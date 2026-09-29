"""T5.6: the auto-reply policy (TR-AI-07, FR-SUG-04, FR-SUG-06) and its output filter.

Done when: 13 unit tests, each failing one check alone, produce the right outcome and reason.
Every evaluation records all 13 checks in order; the first failure decides.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from socialhood.ai import output_filter
from socialhood.ai.policy import (
    AnalysisFacts,
    PolicyInput,
    escalation_phrase,
    evaluate,
)

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
KNOWLEDGE = (
    "[Shipping] Q: How much is shipping?\nA: Shipping is free on orders over ₹999. "
    "Track orders at https://maple.example/track or call +91 98765 43210."
)
PASSING = PolicyInput(
    effective_mode="auto",
    auto_allowed=True,
    credits_available=True,
    paused_until=None,
    now=NOW,
    automation_handled=False,
    window_state="open",
    analysis=AnalysisFacts(intent="shipping", sentiment_score=0.2, needs_human=False),
    message_text="How much is shipping to Pune?",
    can_answer=True,
    confidence=0.9,
    used_sources=1,
    top_similarity=0.82,
    already_replied=False,
    ai_replies_last_hour=0,
    reply_text="Shipping is free on orders over ₹999. Track it at maple.example/track.",
    allowed_texts=[KNOWLEDGE],
    escalation_phrases=("wholesale",),
)
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


def failed_checks(p: PolicyInput) -> list[int]:
    return [c.n for c in evaluate(p).checks if not c.passed]


def test_every_check_passes_and_the_reply_is_sent() -> None:
    decision = evaluate(PASSING)
    assert (decision.outcome, decision.reason) == ("auto_sent", None)
    assert [c["n"] for c in decision.checks_json] == list(range(1, 14))
    assert [c["name"] for c in decision.checks_json] == NAMES
    assert all(c["passed"] for c in decision.checks_json)
    assert set(decision.checks_json[0]) == {"n", "name", "passed", "value"}


ONE_FAILURE: list[tuple[int, dict[str, Any], str, str]] = [
    (1, {"effective_mode": "suggest"}, "skipped", "mode_not_auto"),
    (2, {"credits_available": False}, "skipped", "quota_exhausted"),
    (3, {"paused_until": NOW + timedelta(minutes=30)}, "skipped", "paused"),
    (4, {"automation_handled": True}, "skipped", "automation_handled"),
    (5, {"window_state": "closed"}, "escalated", "window_closed"),
    (
        6,
        {
            "analysis": AnalysisFacts(
                intent="shipping",
                sentiment_score=0.2,
                needs_human=True,
                needs_human_reason="legal",
            )
        },
        "escalated",
        "legal",
    ),
    (7, {"message_text": "Can I get a refund on shipping?"}, "escalated", "policy_keyword"),
    (
        8,
        {"analysis": AnalysisFacts(intent="shipping", sentiment_score=-0.7, needs_human=False)},
        "escalated",
        "negative_sentiment",
    ),
    (9, {"can_answer": False}, "escalated", "out_of_knowledge"),
    (10, {"confidence": 0.74}, "escalated", "low_confidence"),
    (11, {"used_sources": 0}, "escalated", "out_of_knowledge"),
    (12, {"ai_replies_last_hour": 5}, "skipped", "rate_capped"),
    (
        13,
        {"reply_text": "Free over ₹999. See https://maple.example/sale"},
        "escalated",
        "output_blocked",
    ),
]


@pytest.mark.parametrize(
    ("n", "change", "outcome", "reason"), ONE_FAILURE, ids=[f"check_{c[0]}" for c in ONE_FAILURE]
)
def test_failing_one_check_alone_decides_the_outcome(
    n: int, change: dict[str, Any], outcome: str, reason: str
) -> None:
    facts = replace(PASSING, **change)
    decision = evaluate(facts)
    assert failed_checks(facts) == [n]
    assert (decision.outcome, decision.reason) == (outcome, reason)
    assert decision.failed is not None
    assert decision.failed.name == NAMES[n - 1]


def test_the_first_failure_decides_and_every_failure_is_recorded() -> None:
    facts = replace(PASSING, effective_mode="off", window_state="closed", confidence=0.1)
    decision = evaluate(facts)
    assert failed_checks(facts) == [1, 5, 10]
    assert (decision.outcome, decision.reason) == ("skipped", "mode_not_auto")


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ({"auto_allowed": False}, "plan"),
        ({"credits_available": False}, "credits"),
    ],
)
def test_a_plan_without_auto_or_no_credits_skips(change: dict[str, Any], value: str) -> None:
    decision = evaluate(replace(PASSING, **change))
    assert (decision.outcome, decision.reason) == ("skipped", "quota_exhausted")
    assert decision.checks_json[1]["value"] == value


def test_a_past_pause_does_not_stop_it() -> None:
    assert failed_checks(replace(PASSING, paused_until=NOW - timedelta(minutes=1))) == []


def test_one_reply_per_inbound_message() -> None:
    decision = evaluate(replace(PASSING, already_replied=True))
    assert (decision.outcome, decision.reason) == ("skipped", "rate_capped")
    assert decision.checks_json[11]["value"] == "already replied"


@pytest.mark.parametrize(("intent", "reason"), [("refund", "refund"), ("complaint", "complaint")])
def test_refund_and_complaint_intents_escalate(intent: str, reason: str) -> None:
    facts = replace(
        PASSING, analysis=AnalysisFacts(intent=intent, sentiment_score=0.0, needs_human=False)
    )
    assert evaluate(facts).reason == reason
    assert failed_checks(facts) == [7]


def test_the_analysis_reason_is_the_escalation_reason() -> None:
    facts = replace(
        PASSING,
        analysis=AnalysisFacts(intent="support", sentiment_score=0.0, needs_human=True),
    )
    assert evaluate(facts).reason == "human_requested"  # needs_human without a reason


def test_no_analysis_means_no_auto_reply() -> None:
    decision = evaluate(replace(PASSING, analysis=None))
    assert (decision.outcome, decision.reason) == ("escalated", "low_confidence")
    assert decision.checks_json[5]["value"] == "no analysis"


def test_non_fact_questions_need_no_source() -> None:
    greeting = AnalysisFacts(intent="greeting", sentiment_score=0.5, needs_human=False)
    assert failed_checks(replace(PASSING, analysis=greeting, used_sources=0)) == []
    below = replace(PASSING, top_similarity=0.59)
    assert evaluate(below).reason == "out_of_knowledge"


@pytest.mark.parametrize(
    ("text", "phrase"),
    [
        ("I will take legal action", "legal action"),
        ("Can I TALK TO A HUMAN please", "talk to a human"),
        ("Do you do wholesale orders?", "wholesale"),
        ("Is this a scam?", "scam"),
        ("Scammed? no, just asking about the price", None),
        ("What's the price?", None),
    ],
)
def test_escalation_phrases_match_whole_words(text: str, phrase: str | None) -> None:
    assert escalation_phrase(text, ["wholesale"]) == phrase


# ---------------------------------------------------------------- the output filter (check 13)


@pytest.mark.parametrize(
    ("reply", "finding"),
    [
        ("Track it at https://maple.example/track.", None),
        ("Track it at MAPLE.example/track", None),
        ("Track it at www.maple.example/track/", None),
        ("Our site is maple.example", None),
        ("Call +91 98765 43210 anytime", None),
        ("Call 098765-43210 anytime", None),
        ("Orders ship on 2026-10-02.", None),
        ("See https://maple.example/sale", ("link", "https://maple.example/sale")),
        ("See maple.example/trac", ("link", "maple.example/trac")),
        ("Write to hello@maple.example", ("email address", "hello@maple.example")),
        ("Call 99999 11111", ("phone number", "99999 11111")),
    ],
)
def test_the_output_filter_allows_only_what_knowledge_has(
    reply: str, finding: tuple[str, str] | None
) -> None:
    found = output_filter.check(reply, [KNOWLEDGE])
    assert (None if found is None else (found.kind, found.value)) == finding


def test_brand_settings_count_as_a_source() -> None:
    assert output_filter.check("Write to hello@maple.example", ["hello@maple.example"]) is None


def test_replies_over_1000_characters_are_blocked() -> None:
    found = output_filter.check("a" * 1001, [])
    assert found is not None
    assert found.kind == "length"
    assert output_filter.check("a" * 1001, [], max_chars=None) is None
