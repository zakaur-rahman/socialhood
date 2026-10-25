"""Account metrics (GR-38; FR-ANL-01): what an account did over a period, and against another.

The read path over ``account_daily_metrics`` (written by snapshot_account_daily, account_daily.py)
plus the comment and message tables. The route and Ask Social Hood's compare_periods and
metric_trend tools call the same functions, so a visual's numbers are the route's numbers.

Rules:
- A day with no row is a gap, never a zero. A metric sums the days that have a reading and says
  how many: ``days_known`` of ``days_total``. With no reading at all the value is None and
  ``unavailable`` says why (insights not granted, nothing recorded yet, no account).
- ``reach`` and the other insight metrics are daily values summed over the period (Instagram's
  per-day reach counts people reached that day, so a sum can count the same person twice; the
  label says "reach, summed over the days").
- ``followers`` isn't a sum: it is the latest reading in the period (per account, then added).
- ``comments`` and ``messages_received`` count rows over the period's local days, so every day is
  known.
- The change is (current - previous) / previous x 100, to one decimal, worked out here and
  nowhere else. None when either side is unknown or the previous value is 0; ``direction`` is
  flat under 0.5% and still up or down against a previous 0.
- Periods are compared over the same number of days (``align``): a period still running (it ends
  at the latest complete day) is matched by cutting the other one to its length from its start,
  so "this month against last month" on 23 October is 1-22 Oct against 1-22 Sep. Otherwise two
  periods of different length are ``comparable=False`` and no change is worked out.
- A day's row is written the morning after, so today never has one: ``complete_until`` is
  yesterday, and the agent's tools stop periods there instead of reporting a gap that is only the
  clock.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, get_args

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.analytics import AccountDailyMetric
from socialhood.models.connections import SocialAccount
from socialhood.platforms.capabilities import Capability
from socialhood.repositories import analytics as repo
from socialhood.repositories import social_accounts
from socialhood.schemas.analytics import (
    AccountMetricFigure,
    AccountMetricName,
    AccountMetrics,
    ChangeDirection,
    DaySpan,
    MetricGap,
    PeriodFigure,
)
from socialhood.services.analytics.common import View, load_account, zone

ALL_METRICS: tuple[AccountMetricName, ...] = get_args(AccountMetricName)
# The keys of account_daily_metrics.metrics (platforms/base.AccountInsights) by metric name.
STORED_KEY: dict[str, str] = {
    "reach": "reach",
    "views": "views",
    "accounts_engaged": "accounts_engaged",
    "interactions": "total_interactions",
    "follows": "follows",
    "unfollows": "unfollows",
    "profile_link_taps": "profile_links_taps",
}
COUNTED = frozenset({"comments", "messages_received"})
FLAT_UNDER_PCT = 0.5
MAX_SPAN_DAYS = 366


# ---------------------------------------------------------------- days and changes


def span_of(since: date, until: date) -> DaySpan:
    """The days ``since``..``until``, both included; ``since`` after ``until`` is 422, and so is
    a span longer than a year."""
    if since > until:
        raise ApiError(
            "validation_error",
            "The start date is after the end date.",
            errors=[FieldError("since", "Pick a start date on or before the end date.")],
        )
    days = (until - since).days + 1
    if days > MAX_SPAN_DAYS:
        raise ApiError(
            "validation_error",
            "That period is longer than a year.",
            errors=[FieldError("since", "Pick a period of at most 366 days.")],
        )
    return DaySpan(since=since, until=until, days=days)


def complete_until(view: View) -> date:
    """The latest day with a full record: yesterday in the workspace's zone."""
    return view.now.astimezone(zone(view.timezone)).date() - timedelta(days=1)


@dataclass(frozen=True)
class Closed:
    span: DaySpan
    open: bool  # the period runs to the latest complete day: it is still going
    cut_today: bool  # it asked for today (or later), which has no record yet


def closed_span(view: View, since: date, until: date) -> Closed:
    """The days ``since``..``until`` up to the latest complete day. 422 when none of them is
    complete yet (a period that starts today)."""
    last = complete_until(view)
    if since > last:
        raise ApiError(
            "validation_error",
            "That period has no complete day yet: a day's figures arrive the next morning.",
            errors=[FieldError("range", "Pick a period that includes a day before today.")],
        )
    cut = until > last
    end = min(until, last)
    return Closed(span_of(since, end), open=end == last, cut_today=cut)


def change(
    current: float | None, previous: float | None
) -> tuple[float | None, ChangeDirection | None]:
    """The change in % to one decimal and its direction; (None, None) when either side is
    unknown. Against a previous 0 the % is None but the direction is still up or down."""
    if current is None or previous is None:
        return None, None
    if previous == 0:
        if current == 0:
            return None, "flat"
        return None, "up" if current > 0 else "down"
    pct = round((current - previous) / previous * 100, 1)
    if abs(pct) < FLAT_UNDER_PCT:
        return pct, "flat"
    return pct, "up" if pct > 0 else "down"


@dataclass(frozen=True)
class Aligned:
    current: DaySpan
    previous: DaySpan
    comparable: bool
    note: str | None  # how the periods were matched, or why they can't be


def align(
    current: DaySpan, previous: DaySpan, *, current_open: bool, previous_open: bool = False
) -> Aligned:
    """Match two periods over the same number of days (module docstring). ``*_open``: the period
    is still running, so a shorter length is the calendar's, not the member's choice."""
    if current.days == previous.days:
        return Aligned(current, previous, True, None)
    if current_open and current.days < previous.days:
        cut = span_of(previous.since, previous.since + timedelta(days=current.days - 1))
        return Aligned(
            current,
            cut,
            True,
            f"Compared over the same {current.days} days of each period "
            f"(the earlier one is cut to its first {current.days} days).",
        )
    if previous_open and previous.days < current.days:
        cut = span_of(current.since, current.since + timedelta(days=previous.days - 1))
        return Aligned(
            cut,
            previous,
            True,
            f"Compared over the same {previous.days} days of each period "
            f"(the later one is cut to its first {previous.days} days).",
        )
    return Aligned(
        current,
        previous,
        False,
        f"The periods are {current.days} and {previous.days} days long, so no change is worked "
        "out: totals of different lengths can't be compared.",
    )


# ---------------------------------------------------------------- figures


def _number(value: Any) -> float | None:
    """A stored insight value as a number (a bool or text is not one)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _gap(accounts: Sequence[SocialAccount], view: View, metric: str) -> MetricGap:
    if not accounts:
        return "no_account"
    if metric in STORED_KEY and not any(
        Capability.ACCOUNT_INSIGHTS in view.capabilities(a) for a in accounts
    ):
        return "insights_not_granted"
    return "no_readings"


def _insight_figure(
    rows: Sequence[AccountDailyMetric], metric: str, span: DaySpan, gap: MetricGap
) -> PeriodFigure:
    key = STORED_KEY[metric]
    total = 0.0
    known: set[date] = set()
    for row in rows:
        value = _number((row.metrics or {}).get(key))
        if value is not None:
            total += value
            known.add(row.date)
    if not known:
        return PeriodFigure(days_known=0, days_total=span.days, unavailable=gap)
    return PeriodFigure(value=total, days_known=len(known), days_total=span.days)


def _followers_figure(
    rows: Sequence[AccountDailyMetric], span: DaySpan, gap: MetricGap
) -> PeriodFigure:
    """The latest reading in the period for each account, added up."""
    latest: dict[uuid.UUID, AccountDailyMetric] = {}
    known: set[date] = set()
    for row in rows:  # oldest first
        if row.followers_count is not None:
            latest[row.social_account_id] = row
            known.add(row.date)
    if not latest:
        return PeriodFigure(days_known=0, days_total=span.days, unavailable=gap)
    total = sum(float(r.followers_count or 0) for r in latest.values())
    return PeriodFigure(value=total, days_known=len(known), days_total=span.days)


async def _counted(
    session: AsyncSession,
    view: View,
    metric: str,
    span: DaySpan,
    account_ids: list[uuid.UUID] | None,
) -> PeriodFigure:
    tz = zone(view.timezone)
    start = datetime.combine(span.since, time.min, tzinfo=tz)
    end = datetime.combine(span.until + timedelta(days=1), time.min, tzinfo=tz)
    count = repo.count_comments if metric == "comments" else repo.count_inbound_messages
    value = await count(session, start=start, end=end, account_ids=account_ids)
    return PeriodFigure(value=float(value), days_known=span.days, days_total=span.days)


async def period_figures(
    session: AsyncSession,
    view: View,
    *,
    accounts: Sequence[SocialAccount],
    only_account: bool,
    span: DaySpan,
    metrics: Sequence[AccountMetricName],
    rows: Sequence[AccountDailyMetric] | None = None,
) -> dict[AccountMetricName, PeriodFigure]:
    """Each metric for the span. ``only_account``: ``accounts`` is the one the member picked, so
    the comment and message counts are that account's; otherwise they cover every account.
    ``rows`` are the accounts' daily rows when the caller has already read a longer range (the
    weekly report reads its eight weeks once); they are cut to the span here."""
    if rows is None:
        rows = await repo.account_daily_rows(
            session, [a.id for a in accounts], span.since, span.until
        )
    else:
        rows = [r for r in rows if span.since <= r.date <= span.until]
    ids = [a.id for a in accounts] if only_account else None
    found: dict[AccountMetricName, PeriodFigure] = {}
    for metric in metrics:
        if metric in COUNTED:
            found[metric] = await _counted(session, view, metric, span, ids)
        elif metric == "followers":
            found[metric] = _followers_figure(rows, span, _gap(accounts, view, metric))
        else:
            found[metric] = _insight_figure(rows, metric, span, _gap(accounts, view, metric))
    return found


async def accounts_for(
    session: AsyncSession, account_id: uuid.UUID | None
) -> tuple[list[SocialAccount], bool]:
    """The picked account (404 if it isn't this workspace's) or all of them; whether one was
    picked."""
    if account_id is not None:
        return [await load_account(session, account_id)], True
    return await social_accounts.list_all(session), False


async def account_metrics(
    session: AsyncSession,
    view: View,
    *,
    current: DaySpan,
    previous: DaySpan | None = None,
    comparable: bool = True,
    account_id: uuid.UUID | None = None,
    metrics: Sequence[AccountMetricName] | None = None,
) -> AccountMetrics:
    """The figures for ``current`` and, when given, ``previous`` (already matched by ``align``;
    ``comparable`` False draws no change)."""
    wanted = tuple(dict.fromkeys(metrics)) if metrics else ALL_METRICS
    accounts, picked = await accounts_for(session, account_id)
    now_figures = await period_figures(
        session, view, accounts=accounts, only_account=picked, span=current, metrics=wanted
    )
    before = (
        await period_figures(
            session, view, accounts=accounts, only_account=picked, span=previous, metrics=wanted
        )
        if previous is not None
        else None
    )
    figures: list[AccountMetricFigure] = []
    for metric in wanted:
        prior = before[metric] if before is not None else None
        pct = direction = None
        if prior is not None and comparable:
            pct, direction = change(now_figures[metric].value, prior.value)
        figures.append(
            AccountMetricFigure(
                metric=metric,
                current=now_figures[metric],
                previous=prior,
                change_pct=pct,
                direction=direction,
            )
        )
    return AccountMetrics(
        account_id=account_id,
        period=current,
        previous_period=previous,
        comparable=comparable if previous is not None else True,
        figures=figures,
    )


# ---------------------------------------------------------------- series (metric_trend)

SERIES_METRICS: tuple[AccountMetricName, ...] = (
    "reach",
    "views",
    "accounts_engaged",
    "interactions",
    "followers",
    "follows",
    "unfollows",
    "profile_link_taps",
)


@dataclass(frozen=True)
class SeriesPoint:
    """A day (or the Monday of a week) and its value; None is a gap."""

    day: date
    value: float | None
    days_known: int  # days behind the value (1 for a day)
    days_total: int


@dataclass(frozen=True)
class SeriesSummary:
    first: SeriesPoint | None  # the earliest point with a value
    last: SeriesPoint | None
    low: SeriesPoint | None
    high: SeriesPoint | None
    change_pct: float | None  # first to last
    direction: ChangeDirection | None
    known: int  # points with a value


def summarize(points: Sequence[SeriesPoint]) -> SeriesSummary:
    """First, last, lowest and highest points with a value, and the change from first to
    last."""
    valued = [p for p in points if p.value is not None]
    if not valued:
        return SeriesSummary(None, None, None, None, None, None, 0)
    first, last = valued[0], valued[-1]
    pct, direction = change(last.value, first.value) if len(valued) > 1 else (None, None)
    return SeriesSummary(
        first=first,
        last=last,
        low=min(valued, key=lambda p: (p.value or 0.0, p.day)),
        high=max(valued, key=lambda p: (p.value or 0.0, -p.day.toordinal())),
        change_pct=pct,
        direction=direction,
        known=len(valued),
    )


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


async def metric_series(
    session: AsyncSession,
    view: View,
    *,
    metric: AccountMetricName,
    span: DaySpan,
    weekly: bool,
    account_id: uuid.UUID | None = None,
    accounts: Sequence[SocialAccount] | None = None,
    rows: Sequence[AccountDailyMetric] | None = None,
) -> tuple[list[SeriesPoint], MetricGap | None]:
    """One point per day of the span, or per week (Monday to Sunday, cut to the span) with
    ``weekly``: a week's value is the sum of its known days (``followers``: its latest
    reading). The second value is why no point has a value, when none does. ``accounts`` and
    ``rows`` are given by a caller that has already read them for the span (one read for many
    series)."""
    if metric not in SERIES_METRICS:
        raise ApiError("validation_error", f"There's no daily series for {metric}.")
    if accounts is None:
        accounts, _ = await accounts_for(session, account_id)
    if rows is None:
        rows = await repo.account_daily_rows(
            session, [a.id for a in accounts], span.since, span.until
        )
    by_day: dict[date, list[AccountDailyMetric]] = {}
    for row in rows:
        by_day.setdefault(row.date, []).append(row)
    days = [span.since + timedelta(days=i) for i in range(span.days)]

    def day_value(day: date) -> float | None:
        values: list[float] = []
        for row in by_day.get(day, []):
            if metric == "followers":
                if row.followers_count is not None:
                    values.append(float(row.followers_count))
            elif (value := _number((row.metrics or {}).get(STORED_KEY[metric]))) is not None:
                values.append(value)
        return sum(values) if values else None

    daily = {day: day_value(day) for day in days}
    points: list[SeriesPoint] = []
    if not weekly:
        points = [
            SeriesPoint(day, value, 1 if value is not None else 0, 1)
            for day, value in daily.items()
        ]
    else:
        weeks: dict[date, list[date]] = {}
        for day in days:
            weeks.setdefault(_monday(day), []).append(day)
        for monday, members in weeks.items():
            known = [d for d in members if daily[d] is not None]
            if not known:
                value = None
            elif metric == "followers":
                value = daily[known[-1]]
            else:
                value = sum(daily[d] or 0.0 for d in known)
            points.append(SeriesPoint(max(monday, members[0]), value, len(known), len(members)))
    reason = None if any(p.value is not None for p in points) else _gap(accounts, view, metric)
    return points, reason
