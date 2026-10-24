"""GR-24: the sequence rules that need no database: what a step may send and why it is skipped,
when a step is due, business hours holding a step, the entry and step bodies, a step's client id,
and the plan's numbers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from socialhood.billing.plans import entitlement
from socialhood.schemas.sequences import EntryRule, SequenceBody, StepIn, StopRules
from socialhood.services.business_hours import Hours
from socialhood.services.sequences import entry, rules, runner, schedule, service

NOW = datetime(2026, 10, 26, 10, 0, tzinfo=UTC)  # a Monday


def decide(**values: object) -> rules.Decision:
    base: dict[str, object] = {
        "platform": "whatsapp",
        "window_open": False,
        "has_conversation": True,
        "has_text": True,
        "has_template": True,
        "consent_skip": None,
        "marketing_enabled": True,
    }
    return rules.decide(**{**base, **values})  # type: ignore[arg-type]


# ---------------------------------------------------------------- what a step sends


def test_whatsapp_inside_the_window_sends_the_text_without_asking_for_consent() -> None:
    assert decide(window_open=True, consent_skip="no_consent") == rules.Decision("text")


def test_whatsapp_outside_the_window_sends_the_template_to_someone_who_agreed() -> None:
    assert decide() == rules.Decision("template")


@pytest.mark.parametrize("why", ["no_consent", "opted_out"])
def test_whatsapp_outside_the_window_skips_a_template_without_marketing_consent(why: str) -> None:
    found = decide(consent_skip=why)
    assert found == rules.Decision("skip", why)
    assert found.reason == rules.REASONS[why]


def test_whatsapp_text_only_outside_the_window_is_skipped() -> None:
    found = decide(has_template=False)
    assert found == rules.Decision("skip", "window_closed_no_template")
    assert "template" in (found.reason or "")


def test_a_template_only_step_inside_the_window_still_needs_consent() -> None:
    assert decide(window_open=True, has_text=False) == rules.Decision("template")
    assert decide(window_open=True, has_text=False, consent_skip="no_consent").code == "no_consent"


def test_marketing_messages_wait_for_the_legal_check() -> None:
    assert decide(marketing_enabled=False) == rules.Decision("skip", "marketing_off")
    # Text inside the window is not a marketing template.
    assert decide(window_open=True, marketing_enabled=False) == rules.Decision("text")


@pytest.mark.parametrize("platform", ["instagram", "facebook"])
def test_instagram_and_messenger_send_only_while_the_window_is_open(platform: str) -> None:
    assert decide(platform=platform, window_open=True) == rules.Decision("text")
    assert decide(platform=platform, window_open=False) == rules.Decision("skip", "window_closed")
    assert decide(platform=platform, has_conversation=False) == rules.Decision(
        "skip", "no_conversation"
    )
    assert decide(platform=platform, has_text=False, window_open=True) == rules.Decision(
        "skip", "no_text"
    )


def test_every_skip_code_has_words() -> None:
    for code in (
        "window_closed",
        "window_closed_no_template",
        "no_consent",
        "opted_out",
        "marketing_off",
        "missing_value",
        "no_text",
        "no_conversation",
    ):
        assert rules.REASONS[code].endswith(".")


def test_a_stop_reason_in_words() -> None:
    assert rules.stop_text("reply", None) == "They replied"
    assert rules.stop_text("tag", "VIP") == "A stop tag was added: VIP"
    assert rules.stop_text("stage", "Won") == "Their lead stage changed: Won"
    assert rules.stop_text(None, None) is None


# ---------------------------------------------------------------- when a step is due


def test_a_step_counts_from_entry_or_from_the_step_before() -> None:
    entered, ran = NOW, NOW + timedelta(days=1, hours=2)
    kwargs = {"enrolled_at": entered, "previous_ran_at": ran}
    assert schedule.due_at(delay_seconds=86400, delay_from="entry", position=1, **kwargs) == (
        entered + timedelta(days=1)
    )
    assert schedule.due_at(delay_seconds=86400, delay_from="previous", position=1, **kwargs) == (
        ran + timedelta(days=1)
    )


def test_the_first_step_always_counts_from_entry() -> None:
    assert schedule.due_at(
        delay_seconds=3600,
        delay_from="previous",
        position=0,
        enrolled_at=NOW,
        previous_ran_at=NOW + timedelta(days=9),
    ) == NOW + timedelta(hours=1)


def hours(*weekdays: tuple[int, int], tz: str = "UTC") -> Hours:
    """Monday to Friday 09:00 to 17:00 when called with (540, 1020) five times; else as given."""
    days = [() for _ in range(7)]
    for day, (start, end) in enumerate(weekdays):
        days[day] = ((start, end),)
    return Hours(tz, tuple(days))


NINE_TO_FIVE = hours(*[(540, 1020)] * 5)


def test_inside_business_hours_a_step_is_not_held() -> None:
    assert schedule.next_open_at(NINE_TO_FIVE, NOW) == NOW


def test_outside_business_hours_a_step_waits_for_the_next_opening() -> None:
    evening = NOW.replace(hour=19)
    assert schedule.next_open_at(NINE_TO_FIVE, evening) == datetime(2026, 10, 27, 9, tzinfo=UTC)
    saturday = datetime(2026, 10, 31, 12, tzinfo=UTC)
    assert schedule.next_open_at(NINE_TO_FIVE, saturday) == datetime(2026, 11, 2, 9, tzinfo=UTC)
    early = NOW.replace(hour=6)
    assert schedule.next_open_at(NINE_TO_FIVE, early) == NOW.replace(hour=9)


def test_business_hours_follow_the_workspace_time_zone() -> None:
    kolkata = hours(*[(540, 1020)] * 5, tz="Asia/Kolkata")
    # 03:00 UTC is 08:30 in Kolkata: the shop opens at 09:00 there, 03:30 UTC.
    early = NOW.replace(hour=3, minute=0)
    assert schedule.next_open_at(kolkata, early) == NOW.replace(hour=3, minute=30)


def test_hours_that_never_open_give_no_time() -> None:
    assert schedule.next_open_at(hours(), NOW) is None


# ---------------------------------------------------------------- bodies and keys


def test_an_entry_names_what_its_type_needs() -> None:
    assert EntryRule(type="captured", capture_kind="email").capture_kind == "email"
    assert EntryRule(type="broadcast_replied").broadcast_id is None
    with pytest.raises(ValidationError):
        EntryRule(type="tagged")  # no tag
    with pytest.raises(ValidationError):
        EntryRule(type="captured", tag_id=uuid.uuid4())
    with pytest.raises(ValidationError):
        EntryRule(type="tagged", tag_id=uuid.uuid4(), broadcast_id=uuid.uuid4())
    with pytest.raises(ValidationError):
        EntryRule(type="tagged", tag_id=uuid.uuid4(), capture_kind="email")


def test_a_step_needs_a_message_or_a_template_and_a_template_needs_its_language() -> None:
    assert StepIn(delay_seconds=0, text="Hi").text == "Hi"
    assert StepIn(delay_seconds=0, template_name="sale", template_language="en").template_name
    with pytest.raises(ValidationError):
        StepIn(delay_seconds=0)
    with pytest.raises(ValidationError):
        StepIn(delay_seconds=0, text="  ")
    with pytest.raises(ValidationError):
        StepIn(delay_seconds=0, template_name="sale")
    with pytest.raises(ValidationError):
        StepIn(delay_seconds=31 * 24 * 3600, text="Hi")


def test_a_sequence_has_between_one_and_twenty_steps() -> None:
    body = {
        "name": "Follow up",
        "social_account_id": str(uuid.uuid4()),
        "entry": {"type": "captured"},
        "steps": [{"delay_seconds": 60, "text": "Hi"}],
    }
    assert SequenceBody.model_validate(body).stop == StopRules()
    assert SequenceBody.model_validate(body).stop.on_reply is True
    with pytest.raises(ValidationError):
        SequenceBody.model_validate({**body, "steps": []})
    with pytest.raises(ValidationError):
        SequenceBody.model_validate({**body, "steps": [body["steps"][0]] * 21})
    with pytest.raises(ValidationError):
        SequenceBody.model_validate({**body, "name": ""})
    with pytest.raises(ValidationError):
        SequenceBody.model_validate({**body, "stop": {"stages": ["bought"]}})


def test_a_step_has_one_message_id_however_often_it_is_queued() -> None:
    enrolment = uuid.uuid4()
    assert runner.client_id(enrolment, 1) == runner.client_id(enrolment, 1)
    assert runner.client_id(enrolment, 1) != runner.client_id(enrolment, 2)
    assert runner.client_id(enrolment, 1) != runner.client_id(uuid.uuid4(), 1)


def test_a_captured_answer_is_an_email_a_phone_or_a_field() -> None:
    assert [entry.capture_kind(k) for k in ("email", "phone", "field", "text")] == [
        "email",
        "phone",
        "field",
        "field",
    ]


# ---------------------------------------------------------------- the plan


def test_the_plan_limits_are_the_proposed_ones() -> None:
    assert [entitlement(p, service.KEY_ACTIVE) for p in ("free", "pro", "max")] == [1, 10, 50]
    assert [entitlement(p, service.KEY_STEPS) for p in ("free", "pro", "max")] == [3, 10, 20]
