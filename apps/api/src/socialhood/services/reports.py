"""The weekly report (GR-34; roadmap P3): a finished Monday to Sunday against the week before,
and the weeks leading up to it. The report page, the weekly digest email and Home's link all read
this, so they show the same numbers.

Every figure is worked out here, from the functions Home and the digest already use
(services/overview_stats.py) and from GR-38's account metrics (services/analytics/account_metrics
.py). No model writes, rounds or ranks anything.

Rules:
- **Finished weeks only.** A week is Monday to Sunday in the workspace's time zone and can be
  asked for once Sunday is over, so every comparison is seven days against seven days (DST makes
  a span an hour longer or shorter, local midnight to local midnight, as everywhere else). A week
  still running is not shown: a part-week against a whole one would mislead. The latest week is
  the one before the current Monday; the oldest is ``MAX_WEEKS_BACK`` weeks back.
- **Trends** are the week against the week before (``account_metrics.change``, the one
  definition of a change) and ``SERIES_WEEKS`` weeks ending with it, oldest first. For a rate the
  change is in percentage points, not a percent of a percent.
- **Gaps are not zeros.** A week that ended before the workspace was created, with nothing
  recorded in it, has no value. A rate with nothing to divide is None. An account insight sums
  the days that have a reading and says how many (``days_known`` of ``days_total``); with none it
  is None and says why. A week's followers is its latest reading. These are GR-38's account
  metric rules, and its functions compute them.
- **Captures** (GR-14) are the answers a flow's question step took in the week, counted from the
  flow step log (overview_stats.captures_received), like the flow funnel does.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.agent import visuals
from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import SocialAccount
from socialhood.models.identity import Workspace
from socialhood.repositories import social_accounts
from socialhood.schemas.agent import MetricComparisonVisual
from socialhood.schemas.analytics import AccountMetricName, AccountMetrics, ChangeDirection, DaySpan
from socialhood.schemas.reports import (
    AccountBreakdown,
    BreakdownMetric,
    BreakdownMetricKey,
    ReportAccount,
    ReportAccountMetric,
    ReportIntent,
    ReportMetric,
    ReportMetricKey,
    ReportPoint,
    ReportPost,
    ReportQuestion,
    ReportUnit,
    WeeklyReport,
)
from socialhood.services import overview_stats as stats
from socialhood.services.analytics import account_metrics
from socialhood.services.analytics.common import DateRange, View, load_account, zone

SERIES_WEEKS: Final = 8
PICKER_WEEKS: Final = 12
MAX_WEEKS_BACK: Final = 52
FLAT_UNDER_POINTS: Final = 0.5


@dataclass(frozen=True)
class MetricDef:
    key: ReportMetricKey
    label: str
    unit: ReportUnit
    lower_is_better: bool = False


COUNT_METRICS: Final[tuple[MetricDef, ...]] = (
    MetricDef("messages_received", "Messages received", "count"),
    MetricDef("conversations", "People who wrote in", "count"),
    MetricDef("reply_rate", "Reply rate", "percent"),
    MetricDef("median_first_response_s", "Median first response", "seconds", lower_is_better=True),
    MetricDef("handled_by_ai_rate", "Handled by AI", "percent"),
    MetricDef("comments_received", "Comments received", "count"),
    MetricDef("story_mentions", "Story mentions", "count"),
    MetricDef("conversations_from_links", "Conversations from links", "count"),
    MetricDef("conversations_from_ads", "Conversations from ads", "count"),
    MetricDef("captures", "Leads captured", "count"),
    MetricDef("leads_qualified", "Leads qualified", "count"),
    MetricDef("leads_won", "Leads won", "count"),
)
ACCOUNT_METRICS: Final[tuple[tuple[AccountMetricName, str], ...]] = (
    ("reach", "Reach"),
    ("views", "Views"),
    ("accounts_engaged", "Accounts engaged"),
    ("interactions", "Interactions"),
    ("followers", "Followers"),
    ("follows", "Follows"),
    ("unfollows", "Unfollows"),
)
# What must all be zero for a week before the workspace existed to read as "not there yet".
QUIET_KEYS: Final = ("messages_received", "comments_received", "story_mentions", "captures")

ACCOUNT_NOTE: Final = (
    "Figures add up the days that have a reading. Reach counts a person once for each day they "
    "were reached."
)

Values = dict[str, float | None]


# ---------------------------------------------------------------- weeks


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def latest_week(timezone: str, now: datetime) -> date:
    """The Monday of the latest finished week: the one before the current Monday."""
    return monday_of(now.astimezone(zone(timezone)).date()) - timedelta(weeks=1)


def pickable_weeks(timezone: str, now: datetime, count: int = PICKER_WEEKS) -> list[date]:
    """The Mondays that can be asked for, newest first."""
    latest = latest_week(timezone, now)
    return [latest - timedelta(weeks=i) for i in range(min(count, MAX_WEEKS_BACK + 1))]


def week_span(timezone: str, week_start: date) -> DateRange:
    """Monday to Sunday starting ``week_start`` (the digest's span for the Monday after it)."""
    return stats.week_before(timezone, week_start + timedelta(weeks=1))


def check_week(timezone: str, now: datetime, week_start: date) -> None:
    """422 naming ``week`` unless it is a Monday whose Sunday is over, at most a year back."""
    latest = latest_week(timezone, now)
    if week_start.weekday() != 0:
        problem = "Pick a Monday: weeks run Monday to Sunday."
    elif week_start > latest:
        problem = "Pick a week that has finished."
    elif week_start < latest - timedelta(weeks=MAX_WEEKS_BACK):
        problem = f"Pick a week within the last {MAX_WEEKS_BACK} weeks."
    else:
        return
    raise ApiError(
        "validation_error",
        "That isn't a week the report can show.",
        errors=[FieldError("week", problem)],
    )


def ask_for(week: date | None, timezone: str, now: datetime) -> date:
    """The requested week, or the latest finished one."""
    return week if week is not None else latest_week(timezone, now)


# ---------------------------------------------------------------- values and changes


def stats_values(found: stats.OverviewStats) -> Values:
    """The report's numbers from a computed week (the digest's own stats)."""
    inbox = found.inbox
    median = inbox.median_first_response_s
    return {
        "messages_received": float(inbox.messages_received),
        "conversations": float(inbox.conversations),
        "reply_rate": inbox.reply_rate,
        "median_first_response_s": float(median) if median is not None else None,
        "handled_by_ai_rate": inbox.handled_by_ai_rate,
        "comments_received": float(found.comments_received),
        "story_mentions": float(found.story_mentions),
        "conversations_from_links": float(found.conversations_from_links),
        "conversations_from_ads": float(found.conversations_from_ads),
        "captures": float(found.captures),
        "leads_qualified": float(found.leads_qualified),
        "leads_won": float(found.leads_won),
    }


async def week_values(
    session: AsyncSession, span: DateRange, account_id: uuid.UUID | None = None
) -> Values:
    """The same numbers for another week, without the digest's states and rankings."""
    inbox = await stats.inbox_stats(session, span, account_id)
    entries = await stats.conversations_by_entry(session, span, account_id)
    qualified, won = await stats.leads_moved(session, span, account_id)
    return stats_values(
        stats.OverviewStats(
            since=span.since,
            until=span.until,
            inbox=inbox,
            comments_received=await stats.comments_received(session, span, account_id),
            story_mentions=await stats.story_mentions_received(session, span, account_id),
            conversations_from_ads=entries.get("ad", 0),
            conversations_from_links=entries.get("link", 0),
            leads_qualified=qualified,
            leads_won=won,
            captures=await stats.captures_received(session, span, account_id),
        )
    )


def points_change(
    current: float | None, previous: float | None
) -> tuple[float | None, ChangeDirection | None]:
    """The difference of two percentages in points, one decimal; flat under half a point."""
    if current is None or previous is None:
        return None, None
    diff = round(current - previous, 1)
    if abs(diff) < FLAT_UNDER_POINTS:
        return diff, "flat"
    return diff, "up" if diff > 0 else "down"


def metric_of(
    definition: MetricDef,
    current: float | None,
    previous: float | None,
    series: list[ReportPoint],
) -> ReportMetric:
    change_pct: float | None = None
    change_points: float | None = None
    if definition.unit == "percent":
        change_points, direction = points_change(current, previous)
    else:
        change_pct, direction = account_metrics.change(current, previous)
    return ReportMetric(
        key=definition.key,
        label=definition.label,
        unit=definition.unit,
        value=current,
        previous=previous,
        change_pct=change_pct,
        change_points=change_points,
        direction=direction,
        lower_is_better=definition.lower_is_better,
        series=series,
    )


# ---------------------------------------------------------------- the report


def _days(span: DateRange) -> DaySpan:
    return account_metrics.span_of(span.since, span.until)


async def _week_numbers(
    session: AsyncSession,
    workspace: Workspace,
    monday: date,
    known: dict[date, Values],
    account_id: uuid.UUID | None = None,
) -> Values:
    """One week's numbers. A week that ended before the workspace was created and has nothing
    recorded is a gap (the workspace did not exist), not a week of zeros."""
    if monday in known:
        return known[monday]
    span = week_span(workspace.timezone, monday)
    values = await week_values(session, span, account_id)
    if span.end <= workspace.created_at and not any(values[key] for key in QUIET_KEYS):
        values = {definition.key: None for definition in COUNT_METRICS}
    known[monday] = values
    return values


async def _account_figures(
    session: AsyncSession,
    view: View,
    mondays: Sequence[date],
    *,
    with_series: bool,
    account_id: uuid.UUID | None = None,
) -> tuple[list[ReportAccountMetric], AccountMetrics]:
    week = mondays[-1]
    current = _days(week_span(view.timezone, week))
    previous = _days(week_span(view.timezone, week - timedelta(weeks=1)))
    found = await account_metrics.account_metrics(
        session,
        view,
        current=current,
        previous=previous,
        account_id=account_id,
        metrics=[name for name, _ in ACCOUNT_METRICS],
    )
    figures = {figure.metric: figure for figure in found.figures}
    span = account_metrics.span_of(mondays[0], current.until)
    out: list[ReportAccountMetric] = []
    for name, label in ACCOUNT_METRICS:
        series: list[ReportPoint] = []
        if with_series:
            points, _ = await account_metrics.metric_series(
                session, view, metric=name, span=span, weekly=True, account_id=account_id
            )
            by_week = {point.day: point for point in points}
            for monday in mondays:
                point = by_week.get(monday)
                series.append(
                    ReportPoint(
                        week_start=monday,
                        value=point.value if point else None,
                        days_known=point.days_known if point else 0,
                        days_total=point.days_total if point else 7,
                    )
                )
        out.append(ReportAccountMetric(figure=figures[name], label=label, series=series))
    return out, found


def account_name(account: SocialAccount) -> str:
    if account.display_name:
        return account.display_name
    return f"@{account.username}" if account.username else account.platform.capitalize()


def account_ref(account: SocialAccount) -> ReportAccount:
    return ReportAccount(
        id=account.id,
        platform=account.platform,
        name=account_name(account),
        username=account.username,
        status=account.status,
    )


def account_comparison(
    found: AccountMetrics, account: SocialAccount | None = None
) -> MetricComparisonVisual:
    """The week's account figures as GR-38's metric comparison, so the page draws them with the
    component Ask uses (tone, gap wording and day coverage are that builder's)."""
    return visuals.metric_comparison(
        found, account_label=account_name(account) if account else None, note=ACCOUNT_NOTE
    )


BREAKDOWN_COUNTS: Final[tuple[tuple[BreakdownMetricKey, str], ...]] = (
    ("messages_received", "Messages received"),
    ("conversations", "People who wrote in"),
    ("comments_received", "Comments received"),
    ("replies_sent", "Replies sent"),
    ("automation_runs", "Automation runs"),
)
BREAKDOWN_INSIGHTS: Final[tuple[tuple[AccountMetricName, BreakdownMetricKey, str], ...]] = (
    ("reach", "reach", "Reach"),
    ("followers", "followers", "Followers"),
)


async def breakdown(
    session: AsyncSession,
    view: View,
    workspace: Workspace,
    accounts: Sequence[SocialAccount],
    mondays: Sequence[date],
) -> list[AccountBreakdown]:
    """Each account's own numbers for the week against the week before, and the weeks leading
    up to it. Counts (messages, people, comments, replies, automation runs) come from the
    account's own rows. Reach and followers are GR-38's insight readings: None with the reason
    where the platform or the grant doesn't give them (WhatsApp has no insights). A week before
    the workspace existed with nothing counted is a gap, as in the workspace-wide series."""
    tz = workspace.timezone
    counts: dict[date, dict[uuid.UUID, dict[str, float]]] = {}
    for monday in mondays:
        counts[monday] = await stats.counts_by_account(session, week_span(tz, monday))
    last = mondays[-1]
    current = _days(week_span(tz, last))
    previous = _days(week_span(tz, last - timedelta(weeks=1)))
    series_span = account_metrics.span_of(mondays[0], current.until)
    out: list[AccountBreakdown] = []
    for account in accounts:
        metrics: list[BreakdownMetric] = []
        for key, label in BREAKDOWN_COUNTS:
            series: list[ReportPoint] = []
            for monday in mondays:
                own = counts[monday].get(account.id, {})
                before = week_span(tz, monday).end <= workspace.created_at and not any(own.values())
                series.append(
                    ReportPoint(week_start=monday, value=None if before else own.get(key, 0.0))
                )
            value = series[-1].value
            prior = series[-2].value if len(series) > 1 else None
            pct, direction = account_metrics.change(value, prior)
            metrics.append(
                BreakdownMetric(
                    key=key,
                    label=label,
                    value=value,
                    previous=prior,
                    change_pct=pct,
                    direction=direction,
                    series=series,
                )
            )
        found = await account_metrics.account_metrics(
            session,
            view,
            current=current,
            previous=previous,
            account_id=account.id,
            metrics=[name for name, _, _ in BREAKDOWN_INSIGHTS],
        )
        figures = {figure.metric: figure for figure in found.figures}
        for name, key, label in BREAKDOWN_INSIGHTS:
            figure = figures[name]
            points, _ = await account_metrics.metric_series(
                session, view, metric=name, span=series_span, weekly=True, account_id=account.id
            )
            by_week = {point.day: point for point in points}
            insight_series: list[ReportPoint] = []
            for monday in mondays:
                point = by_week.get(monday)
                insight_series.append(
                    ReportPoint(
                        week_start=monday,
                        value=point.value if point else None,
                        days_known=point.days_known if point else 0,
                        days_total=point.days_total if point else 7,
                    )
                )
            metrics.append(
                BreakdownMetric(
                    key=key,
                    label=label,
                    value=figure.current.value,
                    previous=figure.previous.value if figure.previous else None,
                    change_pct=figure.change_pct,
                    direction=figure.direction,
                    unavailable=figure.current.unavailable,
                    series=insight_series,
                )
            )
        out.append(AccountBreakdown(account=account_ref(account), metrics=metrics))
    return out


async def build(
    session: AsyncSession,
    view: View,
    workspace: Workspace,
    *,
    week_start: date,
    current: stats.OverviewStats | None = None,
    with_series: bool = True,
    validate: bool = True,
    account_id: uuid.UUID | None = None,
    with_breakdown: bool = False,
) -> WeeklyReport:
    """The report for the week starting ``week_start`` (a finished Monday, see ``check_week``).
    ``current`` is that week's stats when the caller has computed them (the digest), so both
    report one set of numbers. Without ``with_series`` the series are left empty (the digest shows
    the change only). ``validate`` False skips ``check_week`` (the digest's week is the one it was
    due for, whatever the clock says now). With ``account_id`` every figure is that account's (404
    if it is not this workspace's; ``current`` must then be that account's too); without it the
    report is workspace-wide and ``with_breakdown`` adds each account side by side."""
    picked = await load_account(session, account_id) if account_id is not None else None
    tz = workspace.timezone
    if validate:
        check_week(tz, view.now, week_start)
    span = week_span(tz, week_start)
    before = week_start - timedelta(weeks=1)
    if current is None:
        current = await stats.compute(session, span=span, now=view.now, account_id=account_id)
    mondays = [week_start - timedelta(weeks=i) for i in range(SERIES_WEEKS - 1, -1, -1)]
    known: dict[date, Values] = {week_start: stats_values(current)}
    numbers = {
        monday: await _week_numbers(session, workspace, monday, known, account_id)
        for monday in (mondays if with_series else [before, week_start])
    }

    metrics: list[ReportMetric] = []
    for definition in COUNT_METRICS:
        series = (
            [
                ReportPoint(week_start=monday, value=numbers[monday][definition.key])
                for monday in mondays
            ]
            if with_series
            else []
        )
        metrics.append(
            metric_of(
                definition,
                numbers[week_start][definition.key],
                numbers[before][definition.key],
                series,
            )
        )
    account, account_found = await _account_figures(
        session, view, mondays, with_series=with_series, account_id=account_id
    )
    every = await social_accounts.list_all(session)
    return WeeklyReport(
        week_start=week_start,
        week=_days(span),
        previous_week=_days(week_span(tz, before)),
        timezone=tz,
        weeks=pickable_weeks(tz, view.now),
        series_weeks=SERIES_WEEKS,
        metrics=metrics,
        account_metrics=account,
        account_comparison=account_comparison(account_found, picked),
        top_intents=[ReportIntent(intent=i.intent, count=i.count) for i in current.top_intents],
        top_posts=[
            ReportPost(
                id=post.post_id,
                caption=post.caption,
                permalink=post.permalink,
                posted_at=post.posted_at,
                comments=post.comments,
            )
            for post in current.top_posts
        ],
        needs_you=current.needs_you,
        open_questions=current.open_questions,
        top_questions=[ReportQuestion(topic=q.topic, asked=q.asked) for q in current.top_questions],
        account=account_ref(picked) if picked is not None else None,
        accounts=[account_ref(a) for a in every],
        breakdown=(
            await breakdown(session, view, workspace, every, mondays)
            if with_breakdown and picked is None and with_series
            else None
        ),
    )


def digest_extras(report: WeeklyReport) -> dict[str, Any]:
    """What the digest carries beyond the overview stats: each metric's week, previous week and
    change, and the account metrics (no series). Plain JSON, stored in weekly_digests.stats."""
    return {
        "trends": [
            {
                "key": m.key,
                "label": m.label,
                "unit": m.unit,
                "value": m.value,
                "previous": m.previous,
                "change_pct": m.change_pct,
                "change_points": m.change_points,
                "direction": m.direction,
                "lower_is_better": m.lower_is_better,
            }
            for m in report.metrics
        ],
        "account": [
            {
                "metric": a.figure.metric,
                "label": a.label,
                "value": a.figure.current.value,
                "previous": a.figure.previous.value if a.figure.previous else None,
                "change_pct": a.figure.change_pct,
                "direction": a.figure.direction,
                "days_known": a.figure.current.days_known,
                "days_total": a.figure.current.days_total,
                "unavailable": a.figure.current.unavailable,
            }
            for a in report.account_metrics
        ],
    }
