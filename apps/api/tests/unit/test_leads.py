"""GR-18: lead stages, the qualification rules, the gone-cold rule, request limits, the flow
condition and the event."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import TypeAdapter, ValidationError

from socialhood.jobs.recovery import Recovery, recovery_for
from socialhood.models.contacts import LeadStage, StageActor
from socialhood.models.inbox import Contact
from socialhood.schemas.contacts import ContactFilterSpec, ContactListItem
from socialhood.schemas.flows import BranchRule, Condition, LeadStageCondition
from socialhood.schemas.leads import LeadSettingsPatch, LeadStageUpdate
from socialhood.services import contacts, leads
from socialhood.services.contact_timeline import _stage_detail
from socialhood.services.webhooks import events

NOW = datetime(2026, 10, 24, 9, 0, tzinfo=UTC)


def test_the_stages_are_the_five_in_pipeline_order() -> None:
    assert [s.value for s in LeadStage] == ["new", "qualified", "follow_up", "won", "lost"]
    assert [s.value for s in leads.OPEN_STAGES] == ["new", "qualified", "follow_up"]
    assert set(leads.STAGE_LABEL) == set(LeadStage)


@pytest.mark.parametrize(
    ("score", "intent", "rule"),
    [
        (60, "other", "lead_score"),
        (95, "greeting", "lead_score"),
        (59, "other", None),
        (40, "pricing", "intent"),
        (59, "purchase", "intent"),
        (39, "pricing", None),
        (45, "support", None),
        (None, "pricing", None),
        (0, None, None),
    ],
)
def test_a_score_or_a_buying_intent_qualifies(
    score: int | None, intent: str | None, rule: str | None
) -> None:
    found = leads.qualification(score, intent)
    assert (found.rule if found else None) == rule
    if found:
        assert found.reason.endswith(".")


def test_the_reasons_read_in_plain_words() -> None:
    assert leads.qualification(72, "other").reason == "Lead score reached 72."  # type: ignore[union-attr]
    assert leads.qualification(45, "pricing").reason == (  # type: ignore[union-attr]
        "They asked about pricing (lead score 45)."
    )
    assert leads.qualification(45, "purchase").reason == (  # type: ignore[union-attr]
        "They want to buy (lead score 45)."
    )


def test_a_lead_is_cold_while_the_flag_is_later_than_their_last_message() -> None:
    contact = Contact(lead_cold_at=NOW)
    assert leads.is_cold(contact, NOW - timedelta(days=8))
    assert not leads.is_cold(contact, NOW + timedelta(hours=1))  # they wrote since
    assert leads.is_cold(contact, None)
    assert not leads.is_cold(Contact(lead_cold_at=None), NOW)


@pytest.mark.parametrize(
    ("kind", "user", "words"),
    [
        (StageActor.MEMBER, "Priya", "By Priya"),
        (StageActor.MEMBER, None, "By a team member"),
        (StageActor.RULE, None, "Automatically"),
        (StageActor.AUTOMATION, None, "By an automation"),
        (StageActor.SYSTEM, None, "By Amplychat"),
    ],
)
def test_who_moved_a_lead_in_words(kind: str, user: str | None, words: str) -> None:
    assert leads.actor_phrase(kind, user) == words


def test_the_history_line_says_from_who_and_why() -> None:
    assert _stage_detail("new", "member", "Priya", "Asked for a quote.") == (
        "From New. By Priya. Asked for a quote."
    )
    assert _stage_detail("qualified", "rule", None, None) == "From Qualified. Automatically."


def test_a_stage_request_has_limits() -> None:
    assert LeadStageUpdate(stage="won", note="Paid").note == "Paid"
    with pytest.raises(ValidationError):
        LeadStageUpdate(stage="hot")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        LeadStageUpdate(stage="won", note="x" * 301)
    with pytest.raises(ValidationError):
        LeadStageUpdate(stage="won", unknown=1)  # type: ignore[call-arg]


@pytest.mark.parametrize("days", [0, 91, -1])
def test_the_cold_setting_is_one_to_ninety_days(days: int) -> None:
    with pytest.raises(ValidationError):
        LeadSettingsPatch(cold_after_days=days)
    assert LeadSettingsPatch(cold_after_days=1).cold_after_days == 1
    assert LeadSettingsPatch(cold_after_days=90).cold_after_days == 90


def test_the_contacts_filter_takes_stages() -> None:
    spec = ContactFilterSpec(stages=["qualified", "follow_up"])
    assert contacts.filter_from_spec(spec).stages == ("qualified", "follow_up")
    assert contacts.ContactFilter().stages == ()
    with pytest.raises(ValidationError):
        ContactFilterSpec(stages=["hot"])  # type: ignore[list-item]
    with pytest.raises(ValidationError):
        ContactFilterSpec(stages=["new"] * 6)


def test_a_contact_item_defaults_to_a_new_lead() -> None:
    item = ContactListItem(
        id=uuid.uuid4(), social_account_id=uuid.uuid4(), platform="instagram", name="A", tags=[]
    )
    assert (item.lead_stage, item.lead_cold, item.lead_stage_reason) == ("new", False, None)


def test_the_flow_condition_is_any_of_some_stages() -> None:
    rule = TypeAdapter(BranchRule).validate_python(
        {"when": {"kind": "lead_stage", "stages": ["qualified", "follow_up"]}, "next": "a"}
    )
    assert isinstance(rule.when, LeadStageCondition)
    assert rule.when.stages == ["qualified", "follow_up"]
    adapter = TypeAdapter(Condition)
    for bad in ({"kind": "lead_stage", "stages": []}, {"kind": "lead_stage", "stages": ["hot"]}):
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "lead_stage", "stages": ["new"] * 6})


def test_the_stage_event_is_catalogued_and_emitted() -> None:
    assert events.BY_NAME["lead.stage_changed"].emitted
    assert events.BY_NAME["lead.stage_changed"].version == 1


def test_the_cold_job_is_recovered_by_running_it_again() -> None:
    assert recovery_for("mark_cold_leads") is Recovery.RETRY
