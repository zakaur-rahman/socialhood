"""GR-23: which messages withdraw WhatsApp marketing consent (services/broadcasts/stop.py)."""

from __future__ import annotations

import pytest

from socialhood.services.broadcasts import stop


@pytest.mark.parametrize(
    "text",
    [
        "STOP",
        "stop",
        "Stop.",
        "  stop  ",
        "STOP!!",
        "stop all",
        "Unsubscribe",
        "unsubscribe me",
        "UNSUB",
        "opt out",
        "opt-out",
        "optout",
        "cancel",
        "please stop",
        "stop please",
        "Please STOP now",
        "remove me from the list",
        "don't message me",
        "dont message me",
        "do not message me",
        "No more messages",
        "band karo",
        "Band kar do!",
        "bandh karo",
        "mat bhejo",
        "msg mat bhejo",
        "message mat bhejo",
        "bhejna band karo",
        "nahi chahiye",
        "kripya band karo",
        "बंद करो",
        "मत भेजो",
        "स्टॉप",
        "STOP \U0001f64f",
    ],
)
def test_a_stop_phrase_is_recognised(text: str) -> None:
    assert stop.is_stop(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "hello",
        "Please don't stop the delivery",
        "stop by tomorrow",
        "can you stop at the shop",
        "I want to cancel my order",
        "what is the stop for the bus",
        "yes",
        "price?",
        "bandh karo darwaza",
        "x" * 500,
    ],
)
def test_other_messages_are_not(text: str | None) -> None:
    assert not stop.is_stop(text)


def test_normalising_drops_punctuation_fillers_and_case() -> None:
    assert stop.normalize("  Please, STOP!!! thanks ") == "stop"
    assert stop.normalize("Don" + chr(0x2019) + "t message me") == "dont message me"
    assert stop.normalize("❤️ STOP ❤️") == "stop"


def test_every_listed_phrase_is_stored_normalised() -> None:
    """A phrase that normalises to something else would never match."""
    for phrase in stop.PHRASES:
        assert stop.normalize(phrase) == phrase, phrase
