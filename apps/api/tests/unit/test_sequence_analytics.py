"""GR-24 follow-up: the sequence numbers are built from grouped counts (pure), the new entry and
stop rules validate, and the stop reasons have words."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from socialhood.schemas.sequences import EntryRule, SequenceAnalytics, StopRules
from socialhood.services.sequences import analytics, rules

NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)


def build(**more: object) -> SequenceAnalytics:
    base: dict[str, object] = {
        "sequence_id": uuid.uuid4(),
        "step_count": 3,
        "enrolments": {"active": 2, "completed": 1, "stopped": 1},
        "stop_reasons": {"reply": 1},
        "runs": [],
        "replies": {},
        "waiting": {},
        "now": NOW,
    }
    return analytics.build(**{**base, **more})  # type: ignore[arg-type]


def test_an_empty_sequence_has_zeros_and_no_rates() -> None:
    out = build(enrolments={}, stop_reasons={})
    assert (out.enrolled, out.sent, out.replied, out.reply_rate) == (0, 0, 0, None)
    assert [s.position for s in out.steps] == [1, 2, 3]
    assert all(s.share == 0.0 and s.reply_rate is None for s in out.steps)


def test_runs_are_added_up_by_status_reason_and_step() -> None:
    out = build(
        runs=[
            (0, "sent", None, 3),
            (0, "skipped", "no_consent", 1),
            (1, "sent", None, 2),
            (1, "skipped", "opted_out", 1),
            (1, "failed", "send_failed", 1),
        ],
        replies={0: 1, 1: 1},
        waiting={2: 2},
        enrolments={"active": 2, "completed": 2, "stopped": 0},
        stop_reasons={},
    )
    assert (out.enrolled, out.sent, out.skipped, out.failed) == (4, 5, 2, 1)
    assert [(r.code, r.count) for r in out.skipped_by] == [("no_consent", 1), ("opted_out", 1)]
    assert out.skipped_by[0].text == rules.REASONS["no_consent"]
    assert (out.replied, out.reply_rate) == (2, 0.4)
    first, second, third = out.steps
    assert (first.reached, first.sent, first.skipped, first.replied) == (4, 3, 1, 1)
    assert first.share == 1.0
    assert first.reply_rate == pytest.approx(0.3333, abs=0.001)
    assert (second.reached, second.failed) == (4, 1)
    assert (third.reached, third.waiting, third.share) == (2, 2, 0.5)


def test_the_stop_reasons_come_with_words_most_first() -> None:
    out = build(stop_reasons={"reply": 1, "tag_removed": 3, "stage": 1})
    assert [(r.code, r.count) for r in out.stopped_by] == [
        ("tag_removed", 3),
        ("reply", 1),
        ("stage", 1),
    ]
    assert out.stopped_by[0].text == "A tag they needed was taken off"


def test_the_stage_entry_needs_its_stage_and_only_its_own_type() -> None:
    assert EntryRule(type="lead_stage", stage="won").stage == "won"
    with pytest.raises(ValidationError):
        EntryRule(type="lead_stage")
    with pytest.raises(ValidationError):
        EntryRule(type="captured", stage="won")
    with pytest.raises(ValidationError):
        EntryRule(type="lead_stage", stage="elsewhere")  # type: ignore[arg-type]


def test_the_removed_tag_list_is_capped() -> None:
    assert StopRules(removed_tag_ids=[uuid.uuid4() for _ in range(20)])
    with pytest.raises(ValidationError):
        StopRules(removed_tag_ids=[uuid.uuid4() for _ in range(21)])


def test_a_removed_tag_stop_reads_in_words() -> None:
    assert rules.stop_text("tag_removed", "VIP") == "A tag they needed was taken off: VIP"
