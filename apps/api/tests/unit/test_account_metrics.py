"""GR-38: the account metrics' arithmetic (services/analytics/account_metrics.py) without a
database: the change in %, gaps ("N of M days"), None without readings, followers as the latest
reading, matching two periods over the same days, and the series summary."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from socialhood.errors import ApiError
from socialhood.platforms.capabilities import Capability
from socialhood.schemas.analytics import AccountMetricName, DaySpan
from socialhood.services.analytics import account_metrics as am
from socialhood.services.analytics.common import View

A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
B = uuid.UUID("00000000-0000-0000-0000-00000000000b")


def span(first: str, last: str) -> DaySpan:
    return am.span_of(date.fromisoformat(first), date.fromisoformat(last))


def row(day: str, account: uuid.UUID = A, followers: int | None = None, **metrics: Any) -> Any:
    return SimpleNamespace(
        date=date.fromisoformat(day),
        social_account_id=account,
        followers_count=followers,
        metrics=metrics,
    )


def view(now: str = "2026-10-23T09:00:00+00:00", tz: str = "UTC") -> View:
    return View(
        timezone=tz,
        now=datetime.fromisoformat(now),
        capabilities=lambda acct: frozenset({Capability.ACCOUNT_INSIGHTS}),
    )


# ---------------------------------------------------------------- the change


@pytest.mark.parametrize(
    ("current", "previous", "pct", "direction"),
    [
        (118, 100, 18.0, "up"),
        (91, 100, -9.0, "down"),
        (100.2, 100, 0.2, "flat"),  # under 0.5% is flat
        (99.6, 100, -0.4, "flat"),
        (1234, 1000, 23.4, "up"),
        (5, 0, None, "up"),  # new: no percentage against zero
        (0, 0, None, "flat"),
        (0, 40, -100.0, "down"),
        (None, 40, None, None),  # unknown is neither up nor down
        (40, None, None, None),
    ],
)
def test_the_change_is_worked_out_here(
    current: float | None, previous: float | None, pct: float | None, direction: str | None
) -> None:
    assert am.change(current, previous) == (pct, direction)


# ---------------------------------------------------------------- spans


def test_a_span_counts_both_ends_and_refuses_backwards_or_huge_ranges() -> None:
    assert span("2026-10-01", "2026-10-22").days == 22
    assert span("2026-10-01", "2026-10-01").days == 1
    with pytest.raises(ApiError):
        span("2026-10-02", "2026-10-01")
    with pytest.raises(ApiError):
        span("2025-01-01", "2026-10-01")


def test_today_has_no_record_so_a_running_period_stops_yesterday() -> None:
    v = view("2026-10-23T09:00:00+00:00")
    assert am.complete_until(v) == date(2026, 10, 22)
    running = am.closed_span(v, date(2026, 10, 1), date(2026, 10, 23))
    assert (running.span.until, running.open, running.cut_today) == (date(2026, 10, 22), True, True)
    over = am.closed_span(v, date(2026, 9, 1), date(2026, 9, 30))
    assert (over.span.days, over.open, over.cut_today) == (30, False, False)
    with pytest.raises(ApiError) as error:
        am.closed_span(v, date(2026, 10, 23), date(2026, 10, 23))  # starts today
    assert error.value.code == "validation_error"


def test_the_workspaces_zone_decides_what_yesterday_is() -> None:
    # 23 Oct 22:00 UTC is already 24 Oct in Kolkata, so 23 Oct is complete there.
    v = view("2026-10-23T22:00:00+00:00", "Asia/Kolkata")
    assert am.complete_until(v) == date(2026, 10, 23)


def test_this_month_against_last_month_compares_the_same_days() -> None:
    aligned = am.align(
        span("2026-10-01", "2026-10-22"), span("2026-09-01", "2026-09-30"), current_open=True
    )
    assert aligned.comparable
    assert (aligned.current.days, aligned.previous.days) == (22, 22)
    assert (aligned.previous.since, aligned.previous.until) == (date(2026, 9, 1), date(2026, 9, 22))
    assert aligned.note is not None
    assert "22 days" in aligned.note


def test_the_other_way_round_cuts_the_longer_later_period() -> None:
    aligned = am.align(
        span("2026-09-01", "2026-09-30"),
        span("2026-10-01", "2026-10-22"),
        current_open=False,
        previous_open=True,
    )
    assert aligned.comparable
    assert (aligned.current.until, aligned.previous.days) == (date(2026, 9, 22), 22)


def test_equal_periods_need_no_cutting() -> None:
    aligned = am.align(
        span("2026-10-01", "2026-10-07"), span("2026-09-24", "2026-09-30"), current_open=False
    )
    assert (aligned.comparable, aligned.note) == (True, None)


def test_periods_of_different_length_that_are_both_finished_are_not_comparable() -> None:
    aligned = am.align(
        span("2026-09-01", "2026-09-30"), span("2026-08-01", "2026-08-07"), current_open=False
    )
    assert not aligned.comparable
    assert aligned.note is not None
    assert "30 and 7 days" in aligned.note
    # Nothing is cut: the figures are still given for the periods asked.
    assert (aligned.current.days, aligned.previous.days) == (30, 7)


# ---------------------------------------------------------------- figures


def test_a_metric_sums_the_days_that_have_a_reading() -> None:
    rows = [row("2026-10-01", reach=100), row("2026-10-02", reach=50), row("2026-10-04", views=9)]
    figure = am._insight_figure(rows, "reach", span("2026-10-01", "2026-10-04"), "no_readings")
    assert (figure.value, figure.days_known, figure.days_total, figure.unavailable) == (
        150.0,
        2,
        4,
        None,
    )


def test_no_reading_is_none_with_the_reason_never_zero() -> None:
    figure = am._insight_figure(
        [row("2026-10-01")], "reach", span("2026-10-01", "2026-10-04"), "insights_not_granted"
    )
    assert (figure.value, figure.days_known, figure.unavailable) == (
        None,
        0,
        "insights_not_granted",
    )
    # A real zero is a reading.
    zero = am._insight_figure(
        [row("2026-10-01", reach=0)], "reach", span("2026-10-01", "2026-10-04"), "no_readings"
    )
    assert (zero.value, zero.days_known) == (0.0, 1)


def test_stored_text_or_booleans_are_not_readings() -> None:
    rows = [
        row("2026-10-01", reach="12"),
        row("2026-10-02", reach=True),
        row("2026-10-03", reach=7),
    ]
    figure = am._insight_figure(rows, "reach", span("2026-10-01", "2026-10-04"), "no_readings")
    assert (figure.value, figure.days_known) == (7.0, 1)


def test_interactions_and_link_taps_use_the_stored_names() -> None:
    rows = [row("2026-10-01", total_interactions=40, profile_links_taps=3)]
    s = span("2026-10-01", "2026-10-01")
    assert am._insight_figure(rows, "interactions", s, "no_readings").value == 40.0
    assert am._insight_figure(rows, "profile_link_taps", s, "no_readings").value == 3.0


def test_followers_are_the_latest_reading_of_each_account_added_up() -> None:
    rows = [
        row("2026-10-01", A, followers=100),
        row("2026-10-02", A, followers=110),
        row("2026-10-01", B, followers=40),
        row("2026-10-03", A, followers=None),  # no reading that day
    ]
    figure = am._followers_figure(rows, span("2026-10-01", "2026-10-03"), "no_readings")
    assert (figure.value, figure.days_known, figure.days_total) == (150.0, 2, 3)
    none = am._followers_figure([], span("2026-10-01", "2026-10-03"), "no_account")
    assert (none.value, none.unavailable) == (None, "no_account")


def test_the_reason_a_figure_is_missing() -> None:
    v = view()
    acct = SimpleNamespace(id=A)
    assert am._gap([], v, "reach") == "no_account"
    assert am._gap([acct], v, "reach") == "no_readings"  # insights granted, nothing yet
    denied = View(timezone="UTC", now=v.now, capabilities=lambda a: frozenset())
    assert am._gap([acct], denied, "reach") == "insights_not_granted"
    assert am._gap([acct], denied, "followers") == "no_readings"  # followers need no insights


def test_every_metric_is_either_stored_counted_or_followers() -> None:
    metrics: tuple[AccountMetricName, ...] = am.ALL_METRICS
    for metric in metrics:
        assert (metric in am.STORED_KEY) + (metric in am.COUNTED) + (metric == "followers") == 1


# ---------------------------------------------------------------- the series


def point(day: str, value: float | None) -> am.SeriesPoint:
    return am.SeriesPoint(date.fromisoformat(day), value, 0 if value is None else 1, 1)


def test_a_series_summary_skips_gaps() -> None:
    points = [
        point("2026-10-01", None),
        point("2026-10-02", 100),
        point("2026-10-03", None),
        point("2026-10-04", 150),
        point("2026-10-05", 80),
    ]
    summary = am.summarize(points)
    assert (summary.first, summary.last) == (points[1], points[4])
    assert (summary.low, summary.high, summary.known) == (points[4], points[3], 3)
    assert (summary.change_pct, summary.direction) == (-20.0, "down")


def test_a_series_without_readings_or_with_one_has_no_change() -> None:
    empty = am.summarize([point("2026-10-01", None)])
    assert (empty.first, empty.change_pct, empty.known) == (None, None, 0)
    single = am.summarize([point("2026-10-01", 5)])
    assert (single.first, single.change_pct, single.direction) == (single.last, None, None)
