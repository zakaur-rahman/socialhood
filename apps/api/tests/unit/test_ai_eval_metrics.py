"""T5.9: the evaluation harness's metrics (TR-AI-10). The harness itself calls the model and is
run by hand; these check its arithmetic and its datasets' format only."""

from __future__ import annotations

from tests.ai_eval.run import (
    HERE,
    BinaryReport,
    ClassReport,
    SuggestionOut,
    fabricated,
    load_jsonl,
    passes_auto_policy,
)

KNOWLEDGE = "KNOWLEDGE:\n[k1] (Shipping) Free over ₹999, else ₹79. Help: help@maple.example"


def test_fabrication_is_a_fact_absent_from_knowledge() -> None:
    assert not fabricated("Shipping is ₹79, free over ₹999.", KNOWLEDGE)
    assert not fabricated("Write to help@maple.example", KNOWLEDGE)
    assert fabricated("Shipping is ₹99.", KNOWLEDGE)
    assert fabricated("Order at https://maple.example/shop", KNOWLEDGE)
    assert fabricated("Call +91 98765 43210", KNOWLEDGE)
    assert not fabricated("Happy to help!", KNOWLEDGE)


def test_auto_policy_checks_on_the_draft() -> None:
    def draft(**values: object) -> SuggestionOut:
        base: dict[str, object] = {
            "can_answer": True,
            "reply": "It's ₹79.",
            "missing_info": None,
            "missing_topic": None,
            "confidence": 0.9,
            "used_source_ids": ["k1"],
        }
        return SuggestionOut.model_validate({**base, **values})

    assert passes_auto_policy(draft(), KNOWLEDGE, 0.75)
    assert not passes_auto_policy(draft(confidence=0.7), KNOWLEDGE, 0.75)
    assert not passes_auto_policy(draft(can_answer=False, reply=None), KNOWLEDGE, 0.75)
    assert not passes_auto_policy(draft(reply="It's ₹49."), KNOWLEDGE, 0.75)
    assert not passes_auto_policy(draft(reply="a" * 1001), KNOWLEDGE, 0.75)


def test_class_and_binary_reports() -> None:
    intents = ClassReport()
    for expected, predicted in [
        ("pricing", "pricing"),
        ("pricing", "shipping"),
        ("refund", "refund"),
        ("refund", "complaint"),
    ]:
        intents.add(expected, predicted)
    assert intents.accuracy == 0.5
    assert intents.per_class() == {"pricing": (1, 2, 0.5), "refund": (1, 2, 0.5)}
    assert intents.confusion()["refund"]["complaint"] == 1

    human = BinaryReport()
    for expected, predicted in [(True, True), (True, False), (False, True), (False, False)]:
        human.add(expected, predicted)
    assert (human.precision, human.recall) == (0.5, 0.5)


def test_the_seed_datasets_parse_and_are_marked_placeholders() -> None:
    messages = load_jsonl(HERE / "messages.jsonl")
    suggestions = load_jsonl(HERE / "suggestions.jsonl")
    assert messages
    assert suggestions
    assert all(case["placeholder"] for case in [*messages, *suggestions])
    assert all({"intent", "sentiment", "needs_human"} <= case["labels"].keys() for case in messages)
