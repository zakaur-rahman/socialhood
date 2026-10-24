"""The weekly report (GR-34; roadmap P3): one Monday to Sunday against the week before, with a
multi-week series for each main count. Every figure is worked out in services/reports.py from the
same functions as Home and the weekly digest; no model writes or rounds a number.

A value that cannot be known is ``None`` and never 0: a week before the workspace existed, a
rate with nothing to divide, an insight the account hasn't granted. Account figures say how many
days they cover.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from socialhood.schemas.agent import MetricComparisonVisual
from socialhood.schemas.analytics import AccountMetricFigure, ChangeDirection, DaySpan
from socialhood.schemas.common import ResponseModel

ReportMetricKey = Literal[
    "messages_received",
    "conversations",
    "reply_rate",
    "median_first_response_s",
    "handled_by_ai_rate",
    "comments_received",
    "story_mentions",
    "conversations_from_links",
    "conversations_from_ads",
    "captures",
    "leads_qualified",
    "leads_won",
]
ReportUnit = Literal["count", "percent", "seconds"]


class ReportPoint(ResponseModel):
    """One week of a series: the Monday it starts, and its value (None is a gap)."""

    week_start: date
    value: float | None = None
    days_known: int | None = None  # account series only: days with a reading
    days_total: int | None = None


class ReportMetric(ResponseModel):
    """A count or rate for the week, the week before, and the weeks leading up to it (oldest
    first, the last point is the week). ``change_pct`` is relative for counts and times; for a
    percentage ``change_points`` is the difference in percentage points instead."""

    key: ReportMetricKey
    label: str
    unit: ReportUnit
    value: float | None = None
    previous: float | None = None
    change_pct: float | None = None
    change_points: float | None = None
    direction: ChangeDirection | None = None
    lower_is_better: bool = False
    series: list[ReportPoint]


class ReportAccountMetric(ResponseModel):
    """An account insight (GR-38's service) for the week against the week before, with a weekly
    series. ``figure`` carries the gap reason and days covered."""

    figure: AccountMetricFigure
    label: str
    series: list[ReportPoint]


class ReportIntent(ResponseModel):
    intent: str
    count: int


class ReportQuestion(ResponseModel):
    topic: str
    asked: int


class ReportPost(ResponseModel):
    id: uuid.UUID
    caption: str | None = None
    permalink: str | None = None
    posted_at: datetime
    comments: int


class WeeklyReport(ResponseModel):
    """GET …/reports/weekly: the report for one finished week. ``week_start`` is its Monday in
    the workspace's time zone; ``weeks`` lists the Mondays that can be asked for, newest first.
    The digest email of that Monday carries the same numbers."""

    week_start: date
    week: DaySpan
    previous_week: DaySpan
    timezone: str
    weeks: list[date]
    series_weeks: int
    metrics: list[ReportMetric]
    account_metrics: list[ReportAccountMetric]
    account_comparison: MetricComparisonVisual
    top_intents: list[ReportIntent]
    top_posts: list[ReportPost]
    needs_you: int
    open_questions: int
    top_questions: list[ReportQuestion]
