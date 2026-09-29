"""The time resolver (FR-AGT-05, TA.3): a table of phrases, time zones and edge days resolves
exactly.

Every row of the tables below is checked in Asia/Kolkata, UTC and America/New_York: the expected
values are wall-clock times in the zone under test, at a "now" that is also a wall-clock time
there (a month end, a year end, the end of March, a Friday). Daylight-saving days in New York are
checked separately with their UTC instants.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from socialhood.agent.timeparse import (
    TimeParseError,
    calendar_days,
    resolve_age,
    resolve_instant,
    resolve_range,
)

ZONES = ("Asia/Kolkata", "UTC", "America/New_York")

MONTH_END = "2026-09-30 14:00"  # Wed 30 Sep 2026, 2:00 PM
YEAR_END = "2026-12-31 23:30"  # Thu 31 Dec 2026, 11:30 PM
MARCH_END = "2026-03-31 09:00"  # Tue 31 Mar 2026, 9:00 AM (after New York's DST start)
FRIDAY = "2026-10-02 10:00"  # Fri 2 Oct 2026, 10:00 AM
NOW = "now"  # an expected end equal to the scenario's now


def wall(zone: str, text: str) -> datetime:
    """A wall-clock time in ``zone`` as a UTC instant."""
    return datetime.fromisoformat(text).replace(tzinfo=ZoneInfo(zone)).astimezone(UTC)


# ---------------------------------------------------------------- instants

INSTANTS = [
    # (now, phrase, expected wall time, label, part of the rule or None)
    (MONTH_END, "tomorrow 7 PM", "2026-10-01 19:00", "Thu 1 Oct, 7:00 PM", None),
    (MONTH_END, "today 10am", "2026-09-30 10:00", "Wed 30 Sep, 10:00 AM", None),
    (MONTH_END, "next Monday 9am", "2026-10-05 09:00", "Mon 5 Oct, 9:00 AM", "first Monday"),
    (MONTH_END, "30 Sep 18:00", "2026-09-30 18:00", "Wed 30 Sep, 6:00 PM", None),
    (MONTH_END, "in 2 hours", "2026-09-30 16:00", "Wed 30 Sep, 4:00 PM", None),
    (MONTH_END, "in 30 minutes", "2026-09-30 14:30", "Wed 30 Sep, 2:30 PM", None),
    (MONTH_END, "Friday 10 AM", "2026-10-02 10:00", "Fri 2 Oct, 10:00 AM", None),
    (
        MONTH_END,
        "next Wednesday 10am",
        "2026-10-07 10:00",
        "Wed 7 Oct, 10:00 AM",
        "said on a Wednesday: a week from today",
    ),
    (
        MONTH_END,
        "wednesday 10am",
        "2026-10-07 10:00",
        "Wed 7 Oct, 10:00 AM",
        "10:00 AM has passed today, so next Wednesday",
    ),
    (MONTH_END, "Wednesday 6 pm", "2026-09-30 18:00", "Wed 30 Sep, 6:00 PM", None),
    (MONTH_END, "this Wednesday 10 am", "2026-09-30 10:00", "Wed 30 Sep, 10:00 AM", "this week"),
    (MONTH_END, "last friday 5pm", "2026-09-25 17:00", "Fri 25 Sep, 5:00 PM", "before today"),
    (MONTH_END, "7 pm", "2026-09-30 19:00", "Wed 30 Sep, 7:00 PM", None),
    (MONTH_END, "11 am", "2026-10-01 11:00", "Thu 1 Oct, 11:00 AM", "passed today, so tomorrow"),
    (MONTH_END, "tomorrow at 10", "2026-10-01 10:00", "Thu 1 Oct, 10:00 AM", "24-hour clock"),
    (MONTH_END, "tonight at 9", "2026-09-30 21:00", "Wed 30 Sep, 9:00 PM", None),
    (MONTH_END, "this evening 7", "2026-09-30 19:00", "Wed 30 Sep, 7:00 PM", None),
    (MONTH_END, "midnight", "2026-10-01 00:00", "Thu 1 Oct, 12:00 AM", "end of Wed 30 Sep"),
    (MONTH_END, "noon", "2026-10-01 12:00", "Thu 1 Oct, 12:00 PM", "so tomorrow"),
    (MONTH_END, "in 3 days", "2026-10-03 14:00", "Sat 3 Oct, 2:00 PM", None),
    (MONTH_END, "1 Jan 9am", "2027-01-01 09:00", "Fri 1 Jan 2027, 9:00 AM", "no year given"),
    (MONTH_END, "2026-10-02 18:30", "2026-10-02 18:30", "Fri 2 Oct, 6:30 PM", None),
    (MONTH_END, "7.30 p.m.", "2026-09-30 19:30", "Wed 30 Sep, 7:30 PM", None),
    (MONTH_END, "Oct 5, 9:15 am", "2026-10-05 09:15", "Mon 5 Oct, 9:15 AM", None),
    (MONTH_END, "at 7 pm tomorrow", "2026-10-01 19:00", "Thu 1 Oct, 7:00 PM", None),
    (YEAR_END, "tomorrow 9am", "2027-01-01 09:00", "Fri 1 Jan 2027, 9:00 AM", None),
    (YEAR_END, "in 2 hours", "2027-01-01 01:30", "Fri 1 Jan 2027, 1:30 AM", None),
    (YEAR_END, "midnight", "2027-01-01 00:00", "Fri 1 Jan 2027, 12:00 AM", "end of Thu 31 Dec"),
    (YEAR_END, "7 pm", "2027-01-01 19:00", "Fri 1 Jan 2027, 7:00 PM", "so tomorrow"),
    (YEAR_END, "next Monday 10am", "2027-01-04 10:00", "Mon 4 Jan 2027, 10:00 AM", "first"),
    (YEAR_END, "31 Dec 23:45", "2026-12-31 23:45", "Thu 31 Dec, 11:45 PM", None),
    (YEAR_END, "1 jan 9 am", "2027-01-01 09:00", "Fri 1 Jan 2027, 9:00 AM", "no year given"),
    (MARCH_END, "in 1 month", "2026-04-30 09:00", "Thu 30 Apr, 9:00 AM", None),
    (MARCH_END, "in 2 weeks", "2026-04-14 09:00", "Tue 14 Apr, 9:00 AM", None),
    (FRIDAY, "next Friday 5pm", "2026-10-09 17:00", "Fri 9 Oct, 5:00 PM", "said on a Friday"),
    (FRIDAY, "Friday 5pm", "2026-10-02 17:00", "Fri 2 Oct, 5:00 PM", None),
    (FRIDAY, "this friday 9am", "2026-10-02 09:00", "Fri 2 Oct, 9:00 AM", "this week"),
    (FRIDAY, "coming friday 9am", "2026-10-09 09:00", "Fri 9 Oct, 9:00 AM", "so next Friday"),
]


@pytest.mark.parametrize("zone", ZONES)
@pytest.mark.parametrize(("now", "phrase", "expected", "label", "rule"), INSTANTS)
def test_instants(
    zone: str, now: str, phrase: str, expected: str, label: str, rule: str | None
) -> None:
    got = resolve_instant(phrase, now=wall(zone, now), tz=ZoneInfo(zone))
    assert got.at == wall(zone, expected)
    assert got.at.tzinfo is not None
    assert got.label == label
    assert got.phrase == phrase
    if rule is None:
        assert got.rule is None
    else:
        assert got.rule is not None
        assert rule in got.rule


# ---------------------------------------------------------------- ranges

RANGES = [
    # (now, phrase, upcoming, expected start, expected end, label, part of the rule or None)
    (MONTH_END, "today", False, "2026-09-30", NOW, "Wed 30 Sep 2026, up to 2:00 PM", None),
    (MONTH_END, "today", True, "2026-09-30", "2026-10-01", "Wed 30 Sep 2026", None),
    (MONTH_END, "yesterday", False, "2026-09-29", "2026-09-30", "Tue 29 Sep 2026", None),
    (MONTH_END, "tomorrow", False, "2026-10-01", "2026-10-02", "Thu 1 Oct 2026", None),
    (
        MONTH_END,
        "this week",
        False,
        "2026-09-28",
        NOW,
        "28-30 Sep 2026, up to 2:00 PM",
        "Monday to Sunday",
    ),
    (MONTH_END, "this week", True, "2026-09-28", "2026-10-05", "28 Sep - 4 Oct 2026", "Monday"),
    (MONTH_END, "last week", False, "2026-09-21", "2026-09-28", "21-27 Sep 2026", "Monday"),
    (MONTH_END, "next week", False, "2026-10-05", "2026-10-12", "5-11 Oct 2026", "Monday"),
    (MONTH_END, "this month", False, "2026-09-01", NOW, "1-30 Sep 2026, up to 2:00 PM", None),
    (MONTH_END, "this month", True, "2026-09-01", "2026-10-01", "1-30 Sep 2026", None),
    (MONTH_END, "last month", False, "2026-08-01", "2026-09-01", "1-31 Aug 2026", None),
    (
        MONTH_END,
        "the last 30 days",
        False,
        "2026-08-31 14:00",
        NOW,
        "31 Aug 2026, 2:00 PM - 30 Sep 2026, 2:00 PM",
        None,
    ),
    (
        MONTH_END,
        "past 24 hours",
        False,
        "2026-09-29 14:00",
        NOW,
        "29 Sep 2026, 2:00 PM - 30 Sep 2026, 2:00 PM",
        None,
    ),
    (
        MONTH_END,
        "past week",
        False,
        "2026-09-23 14:00",
        NOW,
        "23 Sep 2026, 2:00 PM - 30 Sep 2026, 2:00 PM",
        "the last 7 days",
    ),
    (
        MONTH_END,
        "over the last 7 days",
        False,
        "2026-09-23 14:00",
        NOW,
        "23 Sep 2026, 2:00 PM - 30 Sep 2026, 2:00 PM",
        None,
    ),
    (
        MONTH_END,
        "since Monday",
        False,
        "2026-09-28",
        NOW,
        "28-30 Sep 2026, up to 2:00 PM",
        "most recent Monday, today included",
    ),
    (
        MONTH_END,
        "since Wednesday",
        False,
        "2026-09-30",
        NOW,
        "Wed 30 Sep 2026, up to 2:00 PM",
        "today included",
    ),
    (
        MONTH_END,
        "since 9 am",
        False,
        "2026-09-30 09:00",
        NOW,
        "30 Sep 2026, 9:00 AM - 30 Sep 2026, 2:00 PM",
        None,
    ),
    (
        MONTH_END,
        "since 3 pm",
        False,
        "2026-09-29 15:00",
        NOW,
        "29 Sep 2026, 3:00 PM - 30 Sep 2026, 2:00 PM",
        None,
    ),
    (
        MONTH_END,
        "since last week",
        False,
        "2026-09-21",
        NOW,
        "21-30 Sep 2026, up to 2:00 PM",
        "Monday",
    ),
    (MONTH_END, "between 1 and 15 Sep", False, "2026-09-01", "2026-09-16", "1-15 Sep 2026", None),
    (MONTH_END, "1-15 Sep 2026", True, "2026-09-01", "2026-09-16", "1-15 Sep 2026", None),
    (MONTH_END, "1-15 Oct", False, "2025-10-01", "2025-10-16", "1-15 Oct 2025", "most recent"),
    (MONTH_END, "1-15 Oct", True, "2026-10-01", "2026-10-16", "1-15 Oct 2026", None),
    (
        MONTH_END,
        "from 28 Dec to 3 Jan",
        False,
        "2025-12-28",
        "2026-01-04",
        "28 Dec 2025 - 3 Jan 2026",
        "most recent",
    ),
    (
        MONTH_END,
        "2026-09-01 to 2026-09-15",
        False,
        "2026-09-01",
        "2026-09-16",
        "1-15 Sep 2026",
        None,
    ),
    (MONTH_END, "12 Sep", False, "2026-09-12", "2026-09-13", "Sat 12 Sep 2026", None),
    (MONTH_END, "Monday", False, "2026-09-28", "2026-09-29", "Mon 28 Sep 2026", "most recent"),
    (MONTH_END, "Monday", True, "2026-10-05", "2026-10-06", "Mon 5 Oct 2026", "next Monday"),
    (
        MONTH_END,
        "Monday to Wednesday",
        True,
        "2026-10-05",
        "2026-10-08",
        "5-7 Oct 2026",
        "next Monday",
    ),
    (MONTH_END, "September", False, "2026-09-01", NOW, "1-30 Sep 2026, up to 2:00 PM", None),
    (MONTH_END, "October", False, "2025-10-01", "2025-11-01", "1-31 Oct 2025", "most recent"),
    (MONTH_END, "October", True, "2026-10-01", "2026-11-01", "1-31 Oct 2026", None),
    (
        MONTH_END,
        "next 7 days",
        False,
        NOW,
        "2026-10-07 14:00",
        "30 Sep 2026, 2:00 PM - 7 Oct 2026, 2:00 PM",
        None,
    ),
    (MONTH_END, "last weekend", False, "2026-09-26", "2026-09-28", "26-27 Sep 2026", "Monday"),
    (YEAR_END, "this week", False, "2026-12-28", NOW, "28-31 Dec 2026, up to 11:30 PM", "Monday"),
    (YEAR_END, "next week", False, "2027-01-04", "2027-01-11", "4-10 Jan 2027", "Monday"),
    (YEAR_END, "this year", False, "2026-01-01", NOW, "1 Jan - 31 Dec 2026, up to 11:30 PM", None),
    (YEAR_END, "last year", False, "2025-01-01", "2026-01-01", "1 Jan - 31 Dec 2025", None),
    (YEAR_END, "next month", False, "2027-01-01", "2027-02-01", "1-31 Jan 2027", None),
    (YEAR_END, "this month", True, "2026-12-01", "2027-01-01", "1-31 Dec 2026", None),
    (
        YEAR_END,
        "last 7 days",
        False,
        "2026-12-24 23:30",
        NOW,
        "24 Dec 2026, 11:30 PM - 31 Dec 2026, 11:30 PM",
        None,
    ),
    (YEAR_END, "1-15 Jan", False, "2026-01-01", "2026-01-16", "1-15 Jan 2026", None),
    (YEAR_END, "1-15 Jan", True, "2027-01-01", "2027-01-16", "1-15 Jan 2027", "next"),
    (MARCH_END, "last month", False, "2026-02-01", "2026-03-01", "1-28 Feb 2026", None),
    (
        MARCH_END,
        "past month",
        False,
        "2026-02-28 09:00",
        NOW,
        "28 Feb 2026, 9:00 AM - 31 Mar 2026, 9:00 AM",
        "this day last month",
    ),
    (
        MARCH_END,
        "last 3 months",
        False,
        "2025-12-31 09:00",
        NOW,
        "31 Dec 2025, 9:00 AM - 31 Mar 2026, 9:00 AM",
        None,
    ),
    (MARCH_END, "since 1 Mar", False, "2026-03-01", NOW, "1-31 Mar 2026, up to 9:00 AM", None),
    (MARCH_END, "next month", False, "2026-04-01", "2026-05-01", "1-30 Apr 2026", None),
]


@pytest.mark.parametrize("zone", ZONES)
@pytest.mark.parametrize(("now", "phrase", "upcoming", "start", "end", "label", "rule"), RANGES)
def test_ranges(
    zone: str,
    now: str,
    phrase: str,
    upcoming: bool,
    start: str,
    end: str,
    label: str,
    rule: str | None,
) -> None:
    at = wall(zone, now)

    def point(text: str) -> datetime:
        return at if text == NOW else wall(zone, text)

    got = resolve_range(phrase, now=at, tz=ZoneInfo(zone), upcoming=upcoming)
    assert (got.start, got.end) == (point(start), point(end))
    assert got.label == label
    if rule is None:
        assert got.rule is None
    else:
        assert got.rule is not None
        assert rule in got.rule


# ---------------------------------------------------------------- daylight saving (New York)

NEW_YORK = ZoneInfo("America/New_York")
BEFORE_SPRING = datetime(2026, 3, 7, 17, 0, tzinfo=UTC)  # Sat 7 Mar, 12:00 PM EST
BEFORE_FALL = datetime(2026, 10, 31, 16, 0, tzinfo=UTC)  # Sat 31 Oct, 12:00 PM EDT


@pytest.mark.parametrize(
    ("now", "phrase", "expected", "label", "rule"),
    [
        (BEFORE_SPRING, "tomorrow 2:30 AM", "2026-03-08T07:30", "Sun 8 Mar, 3:30 AM", "forward"),
        (BEFORE_SPRING, "tomorrow 3:30 AM", "2026-03-08T07:30", "Sun 8 Mar, 3:30 AM", None),
        (BEFORE_SPRING, "tomorrow 1:30 AM", "2026-03-08T06:30", "Sun 8 Mar, 1:30 AM", None),
        (BEFORE_SPRING, "in 24 hours", "2026-03-08T17:00", "Sun 8 Mar, 1:00 PM", None),
        (BEFORE_SPRING, "in 1 day", "2026-03-08T16:00", "Sun 8 Mar, 12:00 PM", None),
        (BEFORE_FALL, "tomorrow 1:30 AM", "2026-11-01T05:30", "Sun 1 Nov, 1:30 AM", "twice"),
        (BEFORE_FALL, "tomorrow 2:30 AM", "2026-11-01T07:30", "Sun 1 Nov, 2:30 AM", None),
        (BEFORE_FALL, "in 24 hours", "2026-11-01T16:00", "Sun 1 Nov, 11:00 AM", None),
        (BEFORE_FALL, "in 1 day", "2026-11-01T17:00", "Sun 1 Nov, 12:00 PM", None),
    ],
)
def test_instants_across_daylight_saving(
    now: datetime, phrase: str, expected: str, label: str, rule: str | None
) -> None:
    got = resolve_instant(phrase, now=now, tz=NEW_YORK)
    assert got.at == datetime.fromisoformat(expected).replace(tzinfo=UTC)
    assert got.label == label
    if rule is None:
        assert got.rule is None
    else:
        assert got.rule is not None
        assert rule in got.rule


@pytest.mark.parametrize(
    ("now", "phrase", "upcoming", "start", "end", "hours"),
    [
        (BEFORE_SPRING, "tomorrow", False, "2026-03-08T05:00", "2026-03-09T04:00", 23),
        (BEFORE_SPRING, "this week", True, "2026-03-02T05:00", "2026-03-09T04:00", 167),
        (BEFORE_SPRING, "next 7 days", False, "2026-03-07T17:00", "2026-03-14T16:00", 167),
        (BEFORE_FALL, "tomorrow", False, "2026-11-01T04:00", "2026-11-02T05:00", 25),
        (
            datetime(2026, 11, 3, 17, 0, tzinfo=UTC),  # Tue 3 Nov, 12:00 PM EST
            "last 7 days",
            False,
            "2026-10-27T16:00",  # Tue 27 Oct, 12:00 PM EDT: the same clock time
            "2026-11-03T17:00",
            169,
        ),
    ],
)
def test_ranges_across_daylight_saving(
    now: datetime, phrase: str, upcoming: bool, start: str, end: str, hours: int
) -> None:
    got = resolve_range(phrase, now=now, tz=NEW_YORK, upcoming=upcoming)
    assert got.start == datetime.fromisoformat(start).replace(tzinfo=UTC)
    assert got.end == datetime.fromisoformat(end).replace(tzinfo=UTC)
    assert got.end - got.start == timedelta(hours=hours)


@pytest.mark.parametrize("zone", ["Asia/Kolkata", "UTC"])
def test_zones_without_daylight_saving_need_no_rule(zone: str) -> None:
    now = wall(zone, "2026-03-07 12:00")
    got = resolve_instant("tomorrow 2:30 AM", now=now, tz=ZoneInfo(zone))
    assert got.at == wall(zone, "2026-03-08 02:30")
    assert got.rule is None
    day = resolve_range("tomorrow", now=now, tz=ZoneInfo(zone))
    assert day.end - day.start == timedelta(hours=24)


# ---------------------------------------------------------------- ages


@pytest.mark.parametrize(
    ("phrase", "age", "label", "rule"),
    [
        ("after 24 hours", timedelta(hours=24), "24 hours", None),
        ("24h", timedelta(hours=24), "24 hours", None),
        ("1 h", timedelta(hours=1), "1 hour", None),
        ("at 7 days", timedelta(days=7), "7 days", None),
        ("3 days", timedelta(hours=72), "3 days", None),
        ("a week", timedelta(days=7), "7 days", None),
        ("at the 24 hour mark", timedelta(hours=24), "24 hours", None),
        ("48 hours", timedelta(hours=48), "2 days", None),
        ("1 month", timedelta(days=30), "30 days", "30 days"),
        ("90 min", timedelta(minutes=90), "1.5 hours", None),
        ("after 6 hours of publishing", timedelta(hours=6), "6 hours", None),
        ("half an hour", timedelta(minutes=30), "30 minutes", None),
    ],
)
def test_ages(phrase: str, age: timedelta, label: str, rule: str | None) -> None:
    got = resolve_age(phrase)
    assert (got.age, got.label) == (age, label)
    assert (got.rule is None) if rule is None else (rule in (got.rule or ""))


# ---------------------------------------------------------------- refusals (FR-AGT-06)

KOLKATA = ZoneInfo("Asia/Kolkata")
AT = wall("Asia/Kolkata", MONTH_END)


@pytest.mark.parametrize(
    ("phrase", "message"),
    [
        ("tomorrow", "Which time"),
        ("Friday evening", "Which time"),
        ("", "Say when"),
        ("whenever you like", "can't read"),
        ("31 Sep 10am", "isn't a date"),
        ("25:00", "isn't a time"),
        ("13 pm", "isn't a time"),
    ],
)
def test_instants_it_cannot_read_are_refused(phrase: str, message: str) -> None:
    with pytest.raises(TimeParseError, match=message):
        resolve_instant(phrase, now=AT, tz=KOLKATA)


@pytest.mark.parametrize(
    ("phrase", "message"),
    [
        ("since tomorrow", "in the future"),
        ("between 15 and 1 Sep", "before the start"),
        ("2 hours", "can't read"),
        ("whenever", "can't read"),
        ("last 0 days", "isn't a period"),
        ("", "Say which period"),
    ],
)
def test_ranges_it_cannot_read_are_refused(phrase: str, message: str) -> None:
    with pytest.raises(TimeParseError, match=message):
        resolve_range(phrase, now=AT, tz=KOLKATA)


@pytest.mark.parametrize("phrase", ["lifetime", "0 hours", "soon", "400 days"])
def test_ages_it_cannot_read_are_refused(phrase: str) -> None:
    with pytest.raises(TimeParseError):
        resolve_age(phrase)


# ---------------------------------------------------------------- calendar days, determinism


@pytest.mark.parametrize(
    ("phrase", "since", "until"),
    [
        ("the last 30 days", date(2026, 9, 1), date(2026, 9, 30)),
        ("today", date(2026, 9, 30), date(2026, 9, 30)),
        ("since 9 am", date(2026, 9, 30), date(2026, 9, 30)),
        ("past 24 hours", date(2026, 9, 30), date(2026, 9, 30)),
        ("last week", date(2026, 9, 21), date(2026, 9, 27)),
        ("this month", date(2026, 9, 1), date(2026, 9, 30)),
        ("between 1 and 15 Sep", date(2026, 9, 1), date(2026, 9, 15)),
    ],
)
@pytest.mark.parametrize("zone", ZONES)
def test_calendar_days_for_analytics(zone: str, phrase: str, since: date, until: date) -> None:
    tz = ZoneInfo(zone)
    got = resolve_range(phrase, now=wall(zone, MONTH_END), tz=tz)
    assert calendar_days(got, tz) == (since, until)


def test_the_same_phrase_resolves_the_same_way() -> None:
    first = resolve_range("last week", now=AT, tz=KOLKATA)
    again = resolve_range("last week", now=AT, tz=KOLKATA)
    assert first == again
    assert resolve_instant("tomorrow 7 PM", now=AT, tz=KOLKATA) == resolve_instant(
        "tomorrow 7 PM", now=AT, tz=KOLKATA
    )
    # FR-AGT-05's example: "tomorrow 7 PM" said on 29 Sep in Kolkata.
    example = resolve_instant(
        "tomorrow 7 PM", now=wall("Asia/Kolkata", "2026-09-29 11:00"), tz=KOLKATA
    )
    assert example.at.astimezone(KOLKATA).isoformat() == "2026-09-30T19:00:00+05:30"
