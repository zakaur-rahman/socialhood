"""Small talk without knowledge (C-062; services/suggestions/small_talk, suggest.v3)."""

from __future__ import annotations

import uuid

import pytest

from socialhood.ai import prompts
from socialhood.services.suggestions.drafting import Draft
from socialhood.services.suggestions.small_talk import (
    FALLBACK_CONFIDENCE,
    fallback_reply,
    is_small_talk,
    kind_of,
    reply_language,
    settle,
)


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Hi", "greeting"),
        ("hiiii!!", "greeting"),
        ("Hello there 👋", "greeting"),
        ("Good morning sir", "greeting"),
        ("How are you?", "greeting"),
        ("how\N{RIGHT SINGLE QUOTATION MARK}s it going", "greeting"),
        ("namaste", "greeting"),
        ("Namaste ji 🙏", "greeting"),
        ("kaise ho", "greeting"),
        ("Kya haal hai bhai?", "greeting"),
        ("नमस्ते", "greeting"),
        ("आप कैसे हैं?", "greeting"),
        ("thanks!", "thanks"),
        ("Thank you so much", "thanks"),
        ("tq", "thanks"),
        ("shukriya", "thanks"),
        ("धन्यवाद जी", "thanks"),
        ("ok", "ack"),
        ("okkk 👍", "ack"),
        ("haan ji", "ack"),
        ("ठीक है", "ack"),
        ("bye", "goodbye"),
        ("ok thanks bye", "goodbye"),
        ("hi, thanks", "thanks"),
        ("sir?", "greeting"),
    ],
)
def test_small_talk_is_recognised(text: str, kind: str) -> None:
    assert kind_of(text) == kind


@pytest.mark.parametrize(
    "text",
    [
        "Hi, what's the price?",
        "hi how much?",
        "Hello, do you ship to Dubai?",
        "Hi Maple Bakery",
        "ok send it",
        "ok, book it",
        "thanks for the info on shipping",
        "yes",
        "hi 2",
        "?",
        "👍",
        "😡",
        "",
        None,
        "hi " * 13,
    ],
)
def test_anything_more_is_not_small_talk(text: str | None) -> None:
    assert kind_of(text) is None


def test_the_analysis_can_rule_small_talk_out() -> None:
    assert is_small_talk("Hi", "greeting")
    assert is_small_talk("thanks!", "feedback")
    assert is_small_talk("ok", "other")
    assert is_small_talk("Hi", None)  # no analysis yet: the text decides
    assert not is_small_talk("ok", "purchase")  # "ok" to "Shall I book it?"
    assert not is_small_talk("hi", "complaint")
    assert not is_small_talk("Hi, what's the price?", "greeting")  # mislabelled: text decides


@pytest.mark.parametrize(
    ("text", "language", "expected"),
    [
        ("Hi", "en", "en"),
        ("Hi", None, "en"),
        ("Hi", "hi-Latn", "hi-Latn"),
        ("Hi", "hi", "hi-Latn"),  # Latin letters: Hinglish, not Devanagari
        ("namaste", "en", "hi-Latn"),
        ("ok ji", None, "hi-Latn"),
        ("नमस्ते", "en", "hi"),
    ],
)
def test_the_reply_language_follows_the_customer(
    text: str, language: str | None, expected: str
) -> None:
    assert reply_language(text, language) == expected


def test_fallback_replies_state_no_fact() -> None:
    assert fallback_reply("Hi", "en") == "Hi! How can I help you today?"
    assert fallback_reply("thanks!", None) == (
        "You're welcome! Let us know if you need anything else."
    )
    assert fallback_reply("kaise ho", None) == (
        "Namaste! Bataiye, hum aapki kya madad kar sakte hain?"
    )
    assert fallback_reply("धन्यवाद", "hi") == "आपका स्वागत है! कुछ और चाहिए तो बताइए।"
    for text in ("Hi", "thanks", "bye", "ok", "namaste", "नमस्ते", "shukriya", "ठीक है"):
        for language in ("en", "hi", "hi-Latn"):
            assert not any(ch.isdigit() for ch in fallback_reply(text, language))


def draft(**values: object) -> Draft:
    base: dict[str, object] = {
        "can_answer": False,
        "reply": None,
        "missing_info": "information about the business",
        "missing_topic": "business information",
        "confidence": 0.3,
        "used_chunk_ids": [uuid.uuid4()],
        "top_similarity": 0.4,
        "model": "fake-model",
        "prompt_version": "suggest.v3",
        "input_tokens": 100,
        "output_tokens": 20,
        "latency_ms": 5,
    }
    return Draft(**{**base, **values})  # type: ignore[arg-type]


def test_a_declined_small_talk_draft_becomes_the_fixed_reply() -> None:
    settled = settle(draft(), "Hi", "en")
    assert (settled.can_answer, settled.reply) == (True, "Hi! How can I help you today?")
    assert (settled.missing_info, settled.missing_topic) == (None, None)
    assert settled.confidence == FALLBACK_CONFIDENCE
    assert settled.used_chunk_ids == []
    assert (settled.model, settled.input_tokens) == ("fake-model", 100)  # the call is recorded


def test_the_models_own_reply_is_kept() -> None:
    own = draft(can_answer=True, reply="Hey! 😊 What can I get you?", confidence=0.95)
    assert settle(own, "Hi", "en") is own


def test_suggest_v3_allows_small_talk_and_keeps_the_fact_rules() -> None:
    prompt = prompts.load("suggest")
    assert prompt.version == "suggest.v3"
    text = prompt.template
    assert "Small talk needs no KNOWLEDGE." in text
    assert "states no business fact" in text
    assert '"Hi, what\'s the price?",\nis not small talk' in text
    # v2's rules are all still there.
    v2 = prompts.load("suggest", 2).template
    for line in v2.splitlines():
        assert line in text, line
