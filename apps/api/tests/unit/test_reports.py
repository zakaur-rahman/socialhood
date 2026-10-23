"""The weekly report's rules (GR-34): finished Monday to Sunday weeks in the workspace's zone,
changes worked out in the service, rates compared in points, and gaps that stay gaps."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from itertools import pairwise

import pytest

from socialhood.errors import ApiError
from socialhood.schemas.analytics import (
    AccountMetricFigure,
    AccountMetrics,
    MetricGap,
    PeriodFigure,
)
from socialhood.schemas.reports import ReportAccountMetric, ReportPoint, WeeklyReport
from socialhood.services import overview_stats as stats
from socialhood.services import reports
from socialhood.services.analytics.account_metrics import span_of

NEW_YORK = "America/New_York"
KOLKATA = "Asia/Kolkata"
# Monday 28 Sep 2026 09:00 in India.
MONDAY_NINE = datetime(2026, 9, 28, 3, 30, tzinfo=UTC)


def test_the_latest_week_is_the_one_before_the_current_monday() -> None:
    assert reports.latest_week(KOLKATA, MONDAY_NINE) == date(2026, 9, 21)
    # Sunday night in India: the week of the 21st has finished, the 28th's has not started.
    sunday = datetime(2026, 9, 27, 18, 0, tzinfo=UTC)  # Sunday 23:30 IST
    assert reports.latest_week(KOLKATA, sunday) == date(2026, 9, 14)
    # The same instant is already Monday in India but still Sunday in New York.
    edge = datetime(2026, 9, 27, 19, 0, tzinfo=UTC)  # Monday 00:30 IST, Sunday 15:00 EDT
    assert reports.latest_week(KOLKATA, edge) == date(2026, 9, 21)
    assert reports.latest_week(NEW_YORK, edge) == date(2026, 9, 14)


def test_the_picker_lists_twelve_mondays_newest_first() -> None:
    weeks = reports.pickable_weeks(KOLKATA, MONDAY_NINE)
    assert len(weeks) == reports.PICKER_WEEKS
    assert weeks[0] == date(2026, 9, 21)
    assert all(w.weekday() == 0 for w in weeks)
    gaps = {a - b for a, b in pairwise(weeks)}
    assert gaps == {timedelta(weeks=1)}


def test_a_week_span_is_monday_to_sunday_in_the_zone() -> None:
    span = reports.week_span(KOLKATA, date(2026, 9, 21))
    assert (span.since, span.until) == (date(2026, 9, 21), date(2026, 9, 27))
    assert span.start == datetime(2026, 9, 20, 18, 30, tzinfo=UTC)
    assert span.end == datetime(2026, 9, 27, 18, 30, tzinfo=UTC)
    # It is the span the digest of the Monday after covers.
    assert span == stats.week_before(KOLKATA, date(2026, 9, 28))


def test_a_week_across_the_autumn_clock_change_is_an_hour_longer() -> None:
    span = reports.week_span(NEW_YORK, date(2026, 10, 26))  # clocks go back on 1 Nov
    assert (span.end.astimezone(UTC) - span.start.astimezone(UTC)).total_seconds() == 169 * 3600
    assert (span.since, span.until) == (date(2026, 10, 26), date(2026, 11, 1))


@pytest.mark.parametrize(
    ("week", "text"),
    [
        (date(2026, 9, 22), "Monday"),  # a Tuesday
        (date(2026, 9, 28), "finished"),  # the week that has not finished
        (date(2026, 9, 21) - timedelta(weeks=53), "last 52 weeks"),
    ],
)
def test_a_week_the_report_cannot_show_is_422_on_week(week: date, text: str) -> None:
    with pytest.raises(ApiError) as caught:
        reports.check_week(KOLKATA, MONDAY_NINE, week)
    error = caught.value
    assert error.code == "validation_error"
    assert error.errors[0].field == "week"
    assert text in error.errors[0].message


def test_the_latest_and_the_oldest_week_are_accepted() -> None:
    reports.check_week(KOLKATA, MONDAY_NINE, date(2026, 9, 21))
    reports.check_week(KOLKATA, MONDAY_NINE, date(2026, 9, 21) - timedelta(weeks=52))


def test_no_week_asked_for_means_the_latest() -> None:
    assert reports.ask_for(None, KOLKATA, MONDAY_NINE) == date(2026, 9, 21)
    assert reports.ask_for(date(2026, 8, 3), KOLKATA, MONDAY_NINE) == date(2026, 8, 3)


@pytest.mark.parametrize(
    ("current", "previous", "points", "direction"),
    [
        (63.2, 60.0, 3.2, "up"),
        (50.0, 60.0, -10.0, "down"),
        (60.2, 60.0, 0.2, "flat"),
        (None, 60.0, None, None),
        (60.0, None, None, None),
    ],
)
def test_a_rate_changes_in_points(
    current: float | None, previous: float | None, points: float | None, direction: str | None
) -> None:
    assert reports.points_change(current, previous) == (points, direction)


def definition(key: str) -> reports.MetricDef:
    return next(d for d in reports.COUNT_METRICS if d.key == key)


def test_a_count_changes_in_percent_and_a_rate_in_points() -> None:
    count = reports.metric_of(definition("messages_received"), 120.0, 100.0, [])
    assert (count.change_pct, count.change_points, count.direction) == (20.0, None, "up")
    rate = reports.metric_of(definition("reply_rate"), 88.4, 80.0, [])
    assert (rate.change_pct, rate.change_points, rate.direction) == (None, 8.4, "up")


def test_a_change_against_nothing_has_a_direction_but_no_percent() -> None:
    won = reports.metric_of(definition("leads_won"), 2.0, 0.0, [])
    assert (won.change_pct, won.direction) == (None, "up")
    unknown = reports.metric_of(definition("median_first_response_s"), None, 600.0, [])
    assert (unknown.value, unknown.change_pct, unknown.direction) == (None, None, None)


def test_a_faster_response_goes_down_and_says_lower_is_better() -> None:
    median = reports.metric_of(definition("median_first_response_s"), 300.0, 600.0, [])
    assert (median.direction, median.change_pct, median.lower_is_better) == ("down", -50.0, True)


def inbox(**values: int | None) -> stats.InboxStats:
    found: dict[str, int | None] = {
        "messages_received": 0,
        "conversations": 0,
        "conversations_replied": 0,
        "handled_by_ai": 0,
        "first_responses": 0,
        "median_first_response_s": None,
    }
    found.update(values)
    return stats.InboxStats(**found)  # type: ignore[arg-type]


def test_a_week_with_nothing_to_divide_has_no_rates_not_zero() -> None:
    values = reports.stats_values(
        stats.OverviewStats(since=date(2026, 9, 21), until=date(2026, 9, 27), inbox=inbox())
    )
    assert values["messages_received"] == 0.0
    assert values["reply_rate"] is None
    assert values["handled_by_ai_rate"] is None
    assert values["median_first_response_s"] is None


def test_the_numbers_are_the_ones_the_digest_stores() -> None:
    found = stats.OverviewStats(
        since=date(2026, 9, 21),
        until=date(2026, 9, 27),
        inbox=inbox(
            messages_received=7,
            conversations=5,
            conversations_replied=3,
            handled_by_ai=1,
            median_first_response_s=630,
        ),
        comments_received=4,
        story_mentions=2,
        conversations_from_ads=1,
        conversations_from_links=3,
        leads_qualified=2,
        leads_won=1,
    )
    values = reports.stats_values(found)
    assert set(values) == {d.key for d in reports.COUNT_METRICS}
    stored = found.to_json()
    for key, value in values.items():
        assert value == stored[key], key


def figure(value: float | None, days: int, gap: MetricGap | None = None) -> PeriodFigure:
    return PeriodFigure(value=value, days_known=days, days_total=7, unavailable=gap)


def report_with(
    metrics: list[reports.ReportMetric], account: list[ReportAccountMetric]
) -> WeeklyReport:
    return WeeklyReport(
        week_start=date(2026, 9, 21),
        week=span_of(date(2026, 9, 21), date(2026, 9, 27)),
        previous_week=span_of(date(2026, 9, 14), date(2026, 9, 20)),
        timezone=KOLKATA,
        weeks=[],
        series_weeks=8,
        metrics=metrics,
        account_metrics=account,
        account_comparison=reports.account_comparison(
            AccountMetrics(
                period=span_of(date(2026, 9, 21), date(2026, 9, 27)),
                previous_period=span_of(date(2026, 9, 14), date(2026, 9, 20)),
                comparable=True,
                figures=[a.figure for a in account],
            )
        ),
        top_intents=[],
        top_posts=[],
        needs_you=0,
        open_questions=0,
        top_questions=[],
        notes=["captures_not_built"],
    )


def test_the_digest_extras_keep_gaps_as_gaps() -> None:
    reach = AccountMetricFigure(
        metric="reach",
        current=figure(None, 0, "insights_not_granted"),
        previous=figure(900.0, 7),
    )
    followers = AccountMetricFigure(
        metric="followers",
        current=figure(1250.0, 5),
        previous=figure(1200.0, 7),
        change_pct=4.2,
        direction="up",
    )
    report = report_with(
        [
            reports.metric_of(definition("messages_received"), 120.0, 100.0, []),
            reports.metric_of(definition("reply_rate"), None, 80.0, []),
        ],
        [
            ReportAccountMetric(figure=reach, label="Reach", series=[]),
            ReportAccountMetric(
                figure=followers,
                label="Followers",
                series=[ReportPoint(week_start=date(2026, 9, 21), value=1250.0)],
            ),
        ],
    )
    extras = reports.digest_extras(report)
    assert [t["key"] for t in extras["trends"]] == ["messages_received", "reply_rate"]
    assert extras["trends"][1]["value"] is None
    assert extras["trends"][1]["change_points"] is None
    assert extras["account"][0] == {
        "metric": "reach",
        "label": "Reach",
        "value": None,
        "previous": 900.0,
        "change_pct": None,
        "direction": None,
        "days_known": 0,
        "days_total": 7,
        "unavailable": "insights_not_granted",
    }
    assert (extras["account"][1]["days_known"], extras["account"][1]["value"]) == (5, 1250.0)


def test_captures_are_noted_as_not_built_until_a_source_exists() -> None:
    assert "captures_not_built" in reports.NOTES
    assert all("capture" not in d.key for d in reports.COUNT_METRICS)


def test_the_account_comparison_is_the_ask_visual_with_its_gap_words() -> None:
    reach = AccountMetricFigure(
        metric="reach",
        current=figure(None, 0, "insights_not_granted"),
        previous=figure(900.0, 7),
    )
    unfollows = AccountMetricFigure(
        metric="unfollows",
        current=figure(9.0, 7),
        previous=figure(3.0, 7),
        change_pct=200.0,
        direction="up",
    )
    visual = reports.account_comparison(
        AccountMetrics(
            period=span_of(date(2026, 9, 21), date(2026, 9, 27)),
            previous_period=span_of(date(2026, 9, 14), date(2026, 9, 20)),
            comparable=True,
            figures=[reach, unfollows],
        )
    )
    assert visual.kind == "metric_comparison"
    by_key = {m.key: m for m in visual.metrics}
    assert by_key["reach"].current is None
    assert "aren't granted" in (by_key["reach"].unavailable or "")
    # More unfollows is bad news, whatever the direction.
    assert (by_key["unfollows"].direction, by_key["unfollows"].tone) == ("up", "bad")
