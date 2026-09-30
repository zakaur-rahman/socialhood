"""When the weekly digest is due (FR-NOT-04, T8.7): Monday from 09:00 in the workspace's time
zone, on the job's quarter-hour ticks, including zones on a half hour (Asia/Kolkata), UTC and
zones with daylight saving (Europe/London, America/New_York); and the week each digest covers."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from socialhood.notify.digest import due_week_start
from socialhood.services.overview_stats import days_up_to_today, week_before

MONDAY = date(2026, 9, 28)
# Europe/London leaves summer time on Sunday 25 October 2026 and America/New_York on 1 November.
LONDON_AFTER_DST = date(2026, 10, 26)
LONDON_BEFORE_DST = date(2026, 10, 19)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("timezone", "now", "due"),
    [
        # Asia/Kolkata is UTC+05:30: Monday 09:00 IST is 03:30 UTC.
        ("Asia/Kolkata", utc(2026, 9, 28, 3, 15), None),  # 08:45 IST
        ("Asia/Kolkata", utc(2026, 9, 28, 3, 30), MONDAY),  # 09:00 IST
        ("Asia/Kolkata", utc(2026, 9, 28, 18, 29), MONDAY),  # 23:59 IST: still Monday
        ("Asia/Kolkata", utc(2026, 9, 28, 18, 30), None),  # Tuesday 00:00 IST
        ("Asia/Kolkata", utc(2026, 9, 27, 23, 0), None),  # Monday 04:30 IST: too early
        # UTC
        ("UTC", utc(2026, 9, 28, 8, 59), None),
        ("UTC", utc(2026, 9, 28, 9, 0), MONDAY),
        ("UTC", utc(2026, 9, 29, 9, 0), None),  # Tuesday
        ("UTC", utc(2026, 10, 4, 9, 0), None),  # Sunday
        # Europe/London: 09:00 is 08:00 UTC in summer time, 09:00 UTC after it ends.
        ("Europe/London", utc(2026, 10, 19, 7, 45), None),
        ("Europe/London", utc(2026, 10, 19, 8, 0), LONDON_BEFORE_DST),
        ("Europe/London", utc(2026, 10, 26, 8, 0), None),  # 08:00 GMT
        ("Europe/London", utc(2026, 10, 26, 9, 0), LONDON_AFTER_DST),
        # America/New_York: Monday 09:00 EDT is 13:00 UTC; 09:00 EST is 14:00 UTC.
        ("America/New_York", utc(2026, 10, 26, 13, 0), LONDON_AFTER_DST),
        ("America/New_York", utc(2026, 11, 2, 13, 45), None),
        ("America/New_York", utc(2026, 11, 2, 14, 0), date(2026, 11, 2)),
        # Sunday evening UTC is already Monday morning in Asia/Tokyo (UTC+9).
        ("Asia/Tokyo", utc(2026, 9, 28, 0, 0), MONDAY),
        # A zone name that isn't one reads as UTC.
        ("Mars/Olympus_Mons", utc(2026, 9, 28, 9, 0), MONDAY),
    ],
)
def test_the_digest_is_due_on_monday_from_nine_local_time(
    timezone: str, now: datetime, due: date | None
) -> None:
    assert due_week_start(timezone, now) == due


@pytest.mark.parametrize(
    "timezone",
    ["Asia/Kolkata", "UTC", "Europe/London", "America/New_York", "Asia/Kathmandu", "Asia/Tokyo"],
)
@pytest.mark.parametrize("week", [MONDAY, LONDON_BEFORE_DST, LONDON_AFTER_DST, date(2026, 11, 2)])
def test_the_quarter_hourly_job_sends_once_a_week_at_nine(timezone: str, week: date) -> None:
    """Every tick of the job (``*/15``) over the week around ``week``, with the weekly_digests
    guard: exactly one send, at 09:00 local time on that Monday."""
    claimed: set[date] = set()
    sends: list[datetime] = []
    tick = datetime.combine(week - timedelta(days=3), datetime.min.time(), tzinfo=UTC)
    end = tick + timedelta(days=7)
    while tick < end:
        due = due_week_start(timezone, tick)
        if due is not None and due not in claimed:
            claimed.add(due)
            sends.append(tick)
        tick += timedelta(minutes=15)
    assert claimed == {week}
    [sent] = sends
    local = sent.astimezone(ZoneInfo(timezone))
    assert (local.date(), local.weekday(), local.hour, local.minute) == (week, 0, 9, 0)


def test_a_digest_covers_the_monday_to_sunday_before_it() -> None:
    span = week_before("Asia/Kolkata", MONDAY)
    assert (span.since, span.until) == (date(2026, 9, 21), date(2026, 9, 27))
    assert span.start == datetime(2026, 9, 20, 18, 30, tzinfo=UTC)  # Monday 00:00 IST
    assert span.end == datetime(2026, 9, 27, 18, 30, tzinfo=UTC)
    assert span.end - span.start == timedelta(days=7)


def test_across_daylight_saving_the_week_is_local_midnight_to_midnight() -> None:
    span = week_before("Europe/London", LONDON_AFTER_DST)
    assert span.start == datetime(2026, 10, 18, 23, 0, tzinfo=UTC)  # 00:00 BST
    assert span.end == datetime(2026, 10, 26, 0, 0, tzinfo=UTC)  # 00:00 GMT
    # Elapsed time (Python subtracts same-zone datetimes on the wall clock).
    assert span.end.astimezone(UTC) - span.start.astimezone(UTC) == timedelta(days=7, hours=1)
    utc_week = week_before("UTC", MONDAY)
    assert utc_week.end - utc_week.start == timedelta(days=7)


def test_the_overview_range_is_the_last_days_up_to_today() -> None:
    now = datetime(2026, 9, 28, 3, 30, tzinfo=UTC)  # Monday 09:00 IST
    span = days_up_to_today("Asia/Kolkata", now, 7)
    assert (span.since, span.until) == (date(2026, 9, 22), date(2026, 9, 28))
    # Asked for last week's days, the overview's range is the digest's (T8.7 "numbers match").
    assert week_before("Asia/Kolkata", MONDAY) == days_up_to_today(
        "Asia/Kolkata", now - timedelta(days=1), 7
    )
