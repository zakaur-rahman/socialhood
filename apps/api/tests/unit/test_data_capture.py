"""GR-14: what a question step checks and says: email and phone normalisation, the free-text
cap, the retry copy, tries, and reading a consent answer."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from socialhood.schemas.flows import AskStep
from socialhood.services import contacts
from socialhood.services.automations import capture, engine


def ask(**kw: object) -> AskStep:
    return AskStep.model_validate({"id": "q", "text": "Your email?", **kw})


@pytest.mark.parametrize(
    ("raw", "email"),
    [
        ("  Priya@Example.COM ", "priya@example.com"),
        ("a.b+tag@mail.co.in", "a.b+tag@mail.co.in"),
    ],
)
def test_an_email_is_trimmed_and_lower_cased(raw: str, email: str) -> None:
    assert contacts.normalize_email(raw) == email


@pytest.mark.parametrize("raw", ["not sure", "a@b", "a b@c.com", "@x.com", ""])
def test_a_bad_email_is_refused(raw: str) -> None:
    with pytest.raises(ValueError, match="email"):
        contacts.normalize_email(raw)


@pytest.mark.parametrize(
    ("raw", "phone"),
    [
        ("98765 43210", "+919876543210"),
        ("+91 98765-43210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("+1 (415) 555-0132", "+14155550132"),
    ],
)
def test_a_phone_is_e164_with_india_by_default(raw: str, phone: str) -> None:
    assert contacts.normalize_phone(raw) == phone


@pytest.mark.parametrize("raw", ["12345", "call me", "5987654321", "+1234567890123456"])
def test_a_bad_phone_is_refused(raw: str) -> None:
    with pytest.raises(ValueError, match="phone"):
        contacts.normalize_phone(raw)


def test_free_text_is_trimmed_and_capped() -> None:
    assert capture.check_text("  Goa ") == "Goa"
    assert capture.check_text("x" * capture.TEXT_MAX) == "x" * capture.TEXT_MAX
    with pytest.raises(ValueError, match="characters"):
        capture.check_text("x" * (capture.TEXT_MAX + 1))
    with pytest.raises(ValueError, match="empty"):
        capture.check_text("   ")


def test_an_ask_step_checks_text_through_the_cap() -> None:
    step = ask(expect="text", field_key="city")
    assert engine._check(step, " Goa ", None) == "Goa"
    with pytest.raises(ValueError, match="characters"):
        engine._check(step, "x" * 501, None)


def test_tries_are_one_to_three_with_two_by_default() -> None:
    assert ask().tries == 2
    assert ask(tries=3).tries == 3
    for bad in (0, 4):
        with pytest.raises(ValidationError):
            ask(tries=bad)


def test_the_retry_prompt_is_the_steps_or_the_default_for_its_kind() -> None:
    assert capture.retry_text(ask(expect="email")) == capture.RETRY_COPY["email"]
    assert capture.retry_text(ask(expect="phone")) == capture.RETRY_COPY["phone"]
    assert capture.retry_text(ask(retry_text=" Try again, please ")) == "Try again, please"


def test_the_consent_question_is_the_steps_or_the_default() -> None:
    assert capture.consent_text(ask()) == capture.CONSENT_COPY
    assert capture.consent_text(ask(consent_text="Want offers?")) == "Want offers?"


@pytest.mark.parametrize(
    ("text", "option", "said"),
    [
        (None, 0, True),
        ("anything", 1, False),
        ("Yes!", None, True),
        ("  yes please ", None, True),
        ("Haan", None, True),
        ("No thanks.", None, False),
        ("nope", None, False),
        ("maybe later", None, None),
        ("", None, None),
        (None, None, None),
    ],
)
def test_a_consent_answer_is_a_tap_or_a_word(
    text: str | None, option: int | None, said: bool | None
) -> None:
    assert capture.consent_answer(text, option) is said


def test_consent_is_recorded_for_instagram_and_whatsapp_only() -> None:
    assert capture.consent_channel("instagram") == "instagram"
    assert capture.consent_channel("whatsapp") == "whatsapp"
    assert capture.consent_channel("facebook") is None
