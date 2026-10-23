"""GR-22: business hours. ``is_open`` and ``closed_since`` at their edges (midnight, ranges that
touch, daylight saving, a time zone ahead of UTC), the schedule checks, which messages the away
message may answer, and the policy's Auto-mode gate (pure: no database)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from zoneinfo import ZoneInfo

import pytest

from socialhood.ai.policy import AnalysisFacts, PolicyInput, evaluate
from socialhood.models.inbox import Message
from socialhood.schemas.business_hours import BusinessHoursUpdate
from socialhood.services import business_hours as bh

KOLKATA = "Asia/Kolkata"
NEW_YORK = "America/New_York"


def hours(timezone: str, **days: list[tuple[str, str]]) -> bh.Hours:
    """``hours("UTC", mon=[("09:00", "17:00")])``; days not named are closed."""
    names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    schedule = [
        {"day": names.index(name), "ranges": [{"start": s, "end": e} for s, e in ranges]}
        for name, ranges in days.items()
    ]
    return bh.hours_from_schedule(schedule, timezone)


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def local(text: str, zone: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=ZoneInfo(zone))


WEEKDAYS = {d: [("09:00", "17:00")] for d in ("mon", "tue", "wed", "thu", "fri")}


# ---------------------------------------------------------------- is_open


@pytest.mark.parametrize(
    ("at", "expected"),
    [
        ("2026-10-26 08:59:59", False),  # Monday, a second before opening
        ("2026-10-26 09:00:00", True),  # the opening minute is open
        ("2026-10-26 16:59:59", True),
        ("2026-10-26 17:00:00", False),  # the closing minute is closed
        ("2026-10-26 23:00:00", False),  # 23:00 is the away-message case
        ("2026-10-24 12:00:00", False),  # Saturday is closed
        ("2026-10-25 12:00:00", False),  # Sunday too
    ],
)
def test_is_open_by_the_week(at: str, expected: bool) -> None:
    assert bh.is_open(hours("UTC", **WEEKDAYS), utc(at)) is expected


def test_several_ranges_in_a_day_leave_the_gap_closed() -> None:
    lunch = hours("UTC", mon=[("09:00", "12:00"), ("13:00", "17:00")])
    assert bh.is_open(lunch, utc("2026-10-26 11:59:00"))
    assert not bh.is_open(lunch, utc("2026-10-26 12:30:00"))
    assert bh.is_open(lunch, utc("2026-10-26 13:00:00"))


def test_the_time_zone_decides_the_weekday_and_hour() -> None:
    shop = hours(KOLKATA, mon=[("09:00", "17:00")])
    # 03:30 UTC on Monday is 09:00 in Kolkata: open; 03:29 is not yet.
    assert bh.is_open(shop, utc("2026-10-26 03:30:00"))
    assert not bh.is_open(shop, utc("2026-10-26 03:29:00"))
    # 20:00 UTC on Sunday is 01:30 on Monday in Kolkata, still before opening.
    assert not bh.is_open(shop, utc("2026-10-25 20:00:00"))
    # 17:00 on Monday in Kolkata is 11:30 UTC.
    assert bh.is_open(shop, utc("2026-10-26 11:29:00"))
    assert not bh.is_open(shop, utc("2026-10-26 11:30:00"))


def test_a_range_can_end_at_midnight_and_the_next_day_start_at_midnight() -> None:
    late = hours("UTC", fri=[("18:00", "24:00")], sat=[("00:00", "02:00")])
    assert bh.is_open(late, utc("2026-10-23 23:59:00"))  # Friday
    assert bh.is_open(late, utc("2026-10-24 00:00:00"))  # Saturday, straight after
    assert bh.is_open(late, utc("2026-10-24 01:59:00"))
    assert not bh.is_open(late, utc("2026-10-24 02:00:00"))


def test_wall_clock_hours_survive_daylight_saving() -> None:
    shop = hours(NEW_YORK, sun=[("09:00", "17:00")], mon=[("09:00", "17:00")])
    # The clocks went back on Sunday 2026-11-01. 09:00 stays 09:00 before and after.
    assert bh.is_open(shop, local("2026-10-26 09:00", NEW_YORK))
    assert bh.is_open(shop, local("2026-11-02 09:00", NEW_YORK))
    assert not bh.is_open(shop, local("2026-11-02 17:00", NEW_YORK))
    # 13:00 UTC is 09:00 in New York in summer and 08:00 in winter.
    assert bh.is_open(shop, utc("2026-10-26 13:00:00"))
    assert not bh.is_open(shop, utc("2026-11-02 13:00:00"))
    assert bh.is_open(shop, utc("2026-11-02 14:00:00"))


def test_a_naive_time_is_read_as_utc() -> None:
    assert bh.is_open(hours("UTC", mon=[("09:00", "17:00")]), datetime(2026, 10, 26, 10, 0))


def test_an_unknown_zone_falls_back_to_utc() -> None:
    assert bh.is_open(hours("Mars/Olympus", mon=[("09:00", "17:00")]), utc("2026-10-26 10:00:00"))


# ---------------------------------------------------------------- closed_since


def test_closed_since_is_none_while_open() -> None:
    assert bh.closed_since(hours("UTC", **WEEKDAYS), utc("2026-10-26 10:00:00")) is None


def test_the_window_starts_when_the_last_range_ended() -> None:
    week = hours("UTC", **WEEKDAYS)
    # Monday 23:00 and Tuesday 07:00 are one closed window that began Monday 17:00.
    assert bh.closed_since(week, utc("2026-10-26 23:00:00")) == utc("2026-10-26 17:00:00")
    assert bh.closed_since(week, utc("2026-10-27 07:00:00")) == utc("2026-10-26 17:00:00")


def test_a_weekend_is_one_window() -> None:
    week = hours("UTC", **WEEKDAYS)
    friday_close = utc("2026-10-23 17:00:00")
    assert bh.closed_since(week, utc("2026-10-24 12:00:00")) == friday_close
    assert bh.closed_since(week, utc("2026-10-26 08:00:00")) == friday_close


def test_ranges_that_touch_are_one_open_stretch() -> None:
    late = hours("UTC", fri=[("09:00", "24:00")], sat=[("00:00", "02:00")])
    assert bh.closed_since(late, utc("2026-10-24 03:00:00")) == utc("2026-10-24 02:00:00")


def test_the_window_is_returned_in_utc_for_a_zone_ahead() -> None:
    shop = hours(KOLKATA, mon=[("09:00", "17:00")])
    # Monday 23:00 in Kolkata is 17:30 UTC; the shop closed at 17:00 Kolkata = 11:30 UTC.
    at = local("2026-10-26 23:00", KOLKATA)
    assert bh.closed_since(shop, at) == utc("2026-10-26 11:30:00")


def test_a_day_closes_at_most_a_week_back() -> None:
    mondays = hours("UTC", mon=[("09:00", "17:00")])
    # Sunday night: the last range ended six days ago.
    assert bh.closed_since(mondays, utc("2026-11-01 22:00:00")) == utc("2026-10-26 17:00:00")


def test_no_range_at_all_has_no_start() -> None:
    assert bh.closed_since(hours("UTC"), utc("2026-10-26 10:00:00")) == bh.NEVER


def test_a_second_message_in_the_same_window_is_not_due_again() -> None:
    """The away rule in one line: told after the window began means told for this window."""
    week = hours("UTC", **WEEKDAYS)
    since = bh.closed_since(week, utc("2026-10-26 23:30:00"))
    assert since is not None
    told_at = utc("2026-10-26 23:00:00")
    assert told_at >= since  # not due again
    next_night = bh.closed_since(week, utc("2026-10-27 23:00:00"))
    assert next_night is not None
    assert told_at < next_night  # due again the next night


# ---------------------------------------------------------------- the checks


def update(**values: object) -> BusinessHoursUpdate:
    base: dict[str, object] = {
        "enabled": True,
        "days": [{"day": 0, "ranges": [{"start": "09:00", "end": "17:00"}]}],
    }
    return BusinessHoursUpdate.model_validate({**base, **values})


def problems(body: BusinessHoursUpdate) -> dict[str, str]:
    return {e.field: e.message for e in bh.check(body)}


def test_a_good_schedule_has_no_problems() -> None:
    assert problems(update()) == {}


def test_touching_ranges_are_allowed() -> None:
    body = update(
        days=[
            {
                "day": 1,
                "ranges": [{"start": "09:00", "end": "12:00"}, {"start": "12:00", "end": "17:00"}],
            }
        ]
    )
    assert problems(body) == {}


def test_overlapping_ranges_name_the_later_one() -> None:
    body = update(
        days=[
            {
                "day": 0,
                "ranges": [{"start": "13:00", "end": "17:00"}, {"start": "09:00", "end": "14:00"}],
            }
        ]
    )
    assert problems(body) == {"days.0.ranges.0.start": bh.COPY["overlap"]}


def test_a_closing_time_before_the_opening_one_is_refused() -> None:
    body = update(days=[{"day": 0, "ranges": [{"start": "17:00", "end": "09:00"}]}])
    assert problems(body) == {"days.0.ranges.0.end": bh.COPY["order"]}
    same = update(days=[{"day": 0, "ranges": [{"start": "09:00", "end": "09:00"}]}])
    assert "days.0.ranges.0.end" in problems(same)


def test_an_opening_time_of_24_00_is_refused() -> None:
    body = update(days=[{"day": 0, "ranges": [{"start": "24:00", "end": "24:00"}]}])
    assert problems(body) == {"days.0.ranges.0.start": bh.COPY["start_midnight"]}


def test_a_day_listed_twice_is_refused() -> None:
    day = {"day": 2, "ranges": [{"start": "09:00", "end": "17:00"}]}
    assert problems(update(days=[day, day])) == {"days.1.day": bh.COPY["twice"]}


def test_hours_switched_on_need_a_range_but_switched_off_may_be_empty() -> None:
    assert problems(update(days=[])) == {"days": bh.COPY["none"]}
    assert problems(update(enabled=False, days=[])) == {}


def test_an_away_message_needs_its_words() -> None:
    assert problems(update(away_enabled=True)) == {"away_message": bh.COPY["away"]}
    assert problems(update(away_enabled=True, away_message="   ")) == {
        "away_message": bh.COPY["away"]
    }
    assert problems(update(away_enabled=True, away_message="Back at 9")) == {}


def test_the_stored_schedule_keeps_days_with_ranges_in_order() -> None:
    body = update(
        days=[
            {"day": 3, "ranges": []},
            {
                "day": 2,
                "ranges": [{"start": "13:00", "end": "17:00"}, {"start": "09:00", "end": "12:00"}],
            },
            {"day": 0, "ranges": [{"start": "09:00", "end": "17:00"}]},
        ]
    )
    assert bh._stored(body) == [
        {"day": 0, "ranges": [{"start": "09:00", "end": "17:00"}]},
        {
            "day": 2,
            "ranges": [{"start": "09:00", "end": "12:00"}, {"start": "13:00", "end": "17:00"}],
        },
    ]


def test_the_view_always_has_seven_days() -> None:
    days = bh._days_out([{"day": 4, "ranges": [{"start": "10:00", "end": "11:00"}]}])
    assert [d.day for d in days] == list(range(7))
    assert [len(d.ranges) for d in days] == [0, 0, 0, 0, 1, 0, 0]


# ---------------------------------------------------------------- which messages get an away reply


def message(
    kind: str = "text",
    postback: str | None = None,
    quick_reply: str | None = None,
    text: str = "hi",
) -> Message:
    return cast(
        Message,
        SimpleNamespace(
            kind=kind,
            text=text,
            attachments=[],
            postback_payload=postback,
            quick_reply_payload=quick_reply,
        ),
    )


@pytest.mark.parametrize(
    ("msg", "expected"),
    [
        (message(), True),
        (message("image"), True),
        (message("story_reply", text="Love it"), True),
        (message("story_reply", text="❤️"), False),  # a story like is no message
        (message("story_mention"), False),
        (message(postback="ib:1"), False),
        (message(quick_reply="shf:x"), False),
    ],
    ids=["text", "image", "story_reply", "story_like", "story_mention", "postback", "quick_reply"],
)
def test_the_away_message_answers_a_person_writing(msg: Message, expected: bool) -> None:
    assert bh.away_applies(msg) is expected


# ---------------------------------------------------------------- Auto mode and the hours

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
AUTO = PolicyInput(
    effective_mode="auto",
    auto_allowed=True,
    credits_available=True,
    paused_until=None,
    now=NOW,
    automation_handled=False,
    window_state="open",
    analysis=AnalysisFacts(intent="shipping", sentiment_score=0.2, needs_human=False),
    message_text="How much is shipping?",
    can_answer=True,
    confidence=0.9,
    used_sources=1,
    top_similarity=0.8,
    already_replied=False,
    ai_replies_last_hour=0,
    reply_text="Shipping is free.",
    allowed_texts=["Shipping is free."],
)


def test_auto_works_as_before_unless_the_hours_hold_it_back() -> None:
    assert evaluate(AUTO).outcome == "auto_sent"
    assert evaluate(replace(AUTO, auto_hours_blocked=False)).outcome == "auto_sent"


def test_auto_that_waits_for_closing_time_skips_while_open() -> None:
    decision = evaluate(replace(AUTO, auto_hours_blocked=True))
    assert (decision.outcome, decision.reason) == ("skipped", "mode_not_auto")
    assert decision.failed is not None
    assert decision.failed.n == 1
    assert [c.n for c in decision.checks if not c.passed] == [1]


def test_the_hours_gate_does_not_wake_a_mode_that_is_not_auto() -> None:
    decision = evaluate(replace(AUTO, effective_mode="suggest", auto_hours_blocked=True))
    assert decision.reason == "mode_not_auto"
