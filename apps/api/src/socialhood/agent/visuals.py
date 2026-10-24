"""Visual answers (GR-38; docs/architecture/generative-ui/05): the typed visuals a tool attaches to
its result, and the reading of the stored ones.

A builder is a pure function of the data a tool already holds from services/analytics: it never
reads the database, calls a model or works out a figure (the change in % and the comparable days
come from the service). The model neither writes a visual nor sees one (``strip`` in
agent/report.model_view), so it can't put a number, label or layout in one.

- ``metric_comparison``: cards for a period against another (compare_periods).
- ``ranked_posts``: posts by one metric, best first (top_posts).
- ``sentiment_summary``: the sentiment split and top topics (sentiment_distribution,
  comment_topics).
- ``trend``: one series over time, gaps kept as gaps (metric_trend; VIS-07).
- ``lead_list``: the best-scored contacts waiting for a reply (list_contacts with
  ``awaiting_reply``; VIS-08), and the conversations "Prepare replies" drafts for (VIS-12).
- ``table``: a short table of what a tool listed, for the tools that return tabular data only:
  search_conversations and list_orders (VIS-09).

``safe`` runs a builder: a failure, or a visual over MAX_VISUAL_BYTES, drops only the visual (the
tool's result and the answer stand), logged as ``agent_visual`` and counted. ``read`` re-checks a
stored visual with the current models and drops one that no longer fits (an older version).
Customer text (captions, topic labels) is clipped here and marked untrusted in the schema; the web
renders it as text. A thumbnail must be an https URL of at most 400 characters.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, cast
from urllib.parse import urlsplit

from pydantic import ValidationError

from socialhood.agent.timeparse import span_label
from socialhood.observability.logging import get_logger
from socialhood.observability.metrics import AGENT_VISUALS
from socialhood.schemas.agent import (
    LEAD_REPLY_MAX,
    MAX_LEADS,
    MAX_METRICS,
    MAX_RANKED,
    MAX_TABLE_COLUMNS,
    MAX_TABLE_ROWS,
    MAX_TOPICS,
    MAX_TREND_POINTS,
    MAX_VISUAL_BYTES,
    VISUAL_ADAPTER,
    LeadListVisual,
    LeadRow,
    MetricComparisonVisual,
    MetricDelta,
    MetricFormat,
    RankedPostRow,
    RankedPostsVisual,
    SentimentSummaryVisual,
    TableColumn,
    TableRow,
    TableVisual,
    Tone,
    TrendMetricKey,
    TrendPoint,
    TrendVisual,
    Visual,
    VisualMetricKey,
    VisualPeriod,
    VisualTopic,
)
from socialhood.schemas.analytics import (
    AccountMetricFigure,
    AccountMetrics,
    ChangeDirection,
    DaySpan,
    MetricGap,
)
from socialhood.schemas.contacts import ContactListItem

log = get_logger(__name__)

KINDS = ("metric_comparison", "ranked_posts", "sentiment_summary", "trend", "lead_list", "table")
THUMBNAIL_MAX_CHARS = 400
CAPTION_CHARS = 100
LABEL_CHARS = 60

# The card label, the format and whether more is better (None: neither, so no good or bad).
METRICS: dict[str, tuple[str, MetricFormat, bool | None]] = {
    "reach": ("Reach", "count", True),
    "views": ("Views", "count", True),
    "accounts_engaged": ("Accounts engaged", "count", True),
    "interactions": ("Interactions", "count", True),
    "followers": ("Followers", "count", True),
    "follows": ("New follows", "count", True),
    "unfollows": ("Unfollows", "count", False),
    "profile_link_taps": ("Profile link taps", "count", True),
    "comments": ("Comments received", "count", True),
    "messages_received": ("Messages received", "count", True),
    "likes": ("Likes", "count", True),
    "shares": ("Shares", "count", True),
    "saves": ("Saves", "count", True),
    "engagement_rate": ("Engagement rate", "percent", True),
}


def metric_label(key: str) -> str:
    return METRICS[key][0]


def gap_words(gap: MetricGap, who: str) -> str:
    """Why a figure is missing, in plain words: the visual's ``unavailable`` and the tool's
    caveat are this one string, so they can't disagree."""
    if gap == "insights_not_granted":
        return f"Insights aren't granted for {who}, so this isn't available."
    if gap == "no_account":
        return "No Instagram account is connected, so this isn't available."
    return "No daily figures are recorded for these days yet."


def _clip(text: str | None, chars: int) -> str | None:
    if text is None:
        return None
    compact = " ".join(text.split())
    if not compact:
        return None
    return compact if len(compact) <= chars else compact[: chars - 1].rstrip() + "…"


def period_of(since: date, until: date) -> VisualPeriod:
    return VisualPeriod(
        start=since,
        end=until,
        label=span_label(since, until),
        days=(until - since).days + 1,
    )


def _period(span: DaySpan) -> VisualPeriod:
    return period_of(span.since, span.until)


def _coverage(known: int, total: int) -> str | None:
    return None if known >= total else f"{known} of {total} days"


def _tone(key: str, direction: str | None) -> Tone:
    better = METRICS[key][2]
    if direction in (None, "flat") or better is None:
        return "neutral"
    return "good" if (direction == "up") == better else "bad"


def _delta(figure: AccountMetricFigure, who: str) -> MetricDelta:
    label, fmt, _ = METRICS[figure.metric]
    now, before = figure.current, figure.previous
    assert before is not None
    gap = now.unavailable or before.unavailable
    return MetricDelta(
        key=cast(VisualMetricKey, figure.metric),
        label=label,
        format=fmt,
        current=now.value,
        previous=before.value,
        change_pct=figure.change_pct,
        direction=figure.direction,
        tone=_tone(figure.metric, figure.direction),
        current_coverage=_coverage(now.days_known, now.days_total)
        if now.value is not None
        else None,
        previous_coverage=(
            _coverage(before.days_known, before.days_total) if before.value is not None else None
        ),
        unavailable=(
            gap_words(gap, who) if gap and (now.value is None or before.value is None) else None
        ),
    )


def metric_comparison(
    data: AccountMetrics, *, account_label: str | None, note: str | None
) -> MetricComparisonVisual:
    """A card per metric: both periods' values, the change and its tone, and the days behind each
    value when some are missing. ``data`` must hold a previous period (compare_periods)."""
    assert data.previous_period is not None
    who = account_label or "these accounts"
    current, previous = _period(data.period), _period(data.previous_period)
    return MetricComparisonVisual(
        kind="metric_comparison",
        title=_clip(
            f"{account_label or 'All accounts'}: {current.label} against {previous.label}", 120
        )
        or "Period comparison",
        current=current,
        previous=previous,
        comparable=data.comparable,
        note=_clip(note, 240),
        account_label=_clip(account_label, LABEL_CHARS),
        metrics=[_delta(f, who) for f in data.figures[:MAX_METRICS]],
    )


@dataclass(frozen=True)
class RankedInput:
    """A ranked post as the tool holds it."""

    post_id: uuid.UUID
    label: str
    format: str
    caption: str | None
    thumbnail_url: str | None
    value: float


def safe_thumbnail(url: str | None) -> str | None:
    """The URL when it is a plain https address that fits; else None (the web draws a
    placeholder)."""
    if not url or len(url) > THUMBNAIL_MAX_CHARS or any(c.isspace() or ord(c) < 32 for c in url):
        return None
    parts = urlsplit(url)
    return url if parts.scheme == "https" and parts.hostname else None


def ranked_posts(
    *,
    metric: str,
    period: VisualPeriod | None,
    age_label: str | None,
    considered: int,
    rows: Sequence[RankedInput],
) -> RankedPostsVisual:
    label, fmt, _ = METRICS[metric]
    return RankedPostsVisual(
        kind="ranked_posts",
        title=f"Top posts by {label.lower()}",
        metric_key=cast(VisualMetricKey, metric),
        metric_label=label,
        format=fmt,
        period=period,
        age_label=_clip(age_label, 60),
        considered=considered,
        items=[
            RankedPostRow(
                post_id=r.post_id,
                label=_clip(r.label, LABEL_CHARS) or "Post",
                format=r.format[:20],
                caption=_clip(r.caption, CAPTION_CHARS),
                thumbnail_url=safe_thumbnail(r.thumbnail_url),
                value=r.value,
            )
            for r in rows[:MAX_RANKED]
        ],
    )


def sentiment_summary(
    *,
    scope: str,
    period: VisualPeriod | None,
    total: int,
    positive: int,
    neutral: int,
    negative: int,
    spam: int,
    not_analysed: int,
    topics: Sequence[tuple[str, int]] = (),
) -> SentimentSummaryVisual:
    return SentimentSummaryVisual(
        kind="sentiment_summary",
        title="Comment sentiment",
        scope=_clip(scope, 120) or "comments",
        period=period,
        total=total,
        positive=positive,
        neutral=neutral,
        negative=negative,
        spam=spam,
        not_analysed=not_analysed,
        topics=[
            VisualTopic(label=_clip(label, 40) or "topic", count=count)
            for label, count in topics[:MAX_TOPICS]
        ],
    )


# ---------------------------------------------------------------- trend (VIS-07)


def _count(value: float | None) -> str:
    return "no reading" if value is None else f"{value:,.0f}"


def _day(point: TrendPoint) -> str:
    return f"{point.day.day} {point.day:%b}"


def trend_summary(
    *,
    label: str,
    granularity: str,
    period: VisualPeriod,
    first: TrendPoint | None,
    last: TrendPoint | None,
    lowest: TrendPoint | None,
    highest: TrendPoint | None,
    change_pct: float | None,
) -> str:
    """The chart in words, from the tool's own figures (the aria label and the text fallback)."""
    text = f"{label} by {granularity}, {period.label}."
    if first is None or last is None:
        return f"{text} No readings."
    if first.day == last.day:
        text += f" One reading: {_count(first.value)} on {_day(first)}."
    else:
        text += (
            f" From {_count(first.value)} on {_day(first)} to {_count(last.value)} on {_day(last)}"
        )
        text += f" ({change_pct:+.1f}%)." if change_pct is not None else "."
    if lowest and highest and lowest.day != highest.day:
        text += (
            f" Lowest {_count(lowest.value)} on {_day(lowest)},"
            f" highest {_count(highest.value)} on {_day(highest)}."
        )
    return text


def trend(
    *,
    metric: str,
    granularity: str,
    period: VisualPeriod,
    account_label: str | None,
    points: Sequence[TrendPoint],
    known_points: int,
    first: TrendPoint | None,
    last: TrendPoint | None,
    lowest: TrendPoint | None,
    highest: TrendPoint | None,
    change_pct: float | None,
    direction: ChangeDirection | None,
    note: str | None,
) -> TrendVisual:
    """One series, in the tool's order. A point without a reading stays ``None``; this never
    fills one in. More than MAX_TREND_POINTS points (the tool's own spans never make that many)
    fail the build, so a chart is never silently cut."""
    if len(points) > MAX_TREND_POINTS:
        raise ValueError("too many points for a trend")
    label, fmt, _ = METRICS[metric]
    where = _clip(account_label, LABEL_CHARS)
    return TrendVisual(
        kind="trend",
        title=_clip(f"{label}, {period.label}" + (f": {where}" if where else ""), 120) or label,
        metric_key=cast(TrendMetricKey, metric),
        metric_label=label,
        format=fmt,
        granularity=cast(Any, granularity),
        period=period,
        account_label=where,
        points=list(points),
        known_points=known_points,
        first=first,
        last=last,
        lowest=lowest,
        highest=highest,
        change_pct=change_pct,
        direction=direction,
        summary=_clip(
            trend_summary(
                label=label,
                granularity=granularity,
                period=period,
                first=first,
                last=last,
                lowest=lowest,
                highest=highest,
                change_pct=change_pct,
            ),
            300,
        )
        or label,
        note=_clip(note, 200),
    )


# ---------------------------------------------------------------- lead_list (VIS-08, VIS-12)


def lead_list(
    *,
    items: Sequence[ContactListItem],
    total: int,
    more_route: str | None,
    activity: Sequence[str | None] = (),
) -> LeadListVisual:
    """The leads as the contacts service listed them (already best score first). ``reply_ids``
    are the first LEAD_REPLY_MAX that have a conversation: the ones "Prepare replies" drafts for.
    ``activity`` is each lead's last-activity words, from the tool."""
    shown = list(items[:MAX_LEADS])
    return LeadListVisual(
        kind="lead_list",
        title="Leads waiting for your reply",
        total=total,
        items=[
            LeadRow(
                contact_id=c.id,
                conversation_id=c.conversation_id,
                name=_clip(c.name, LABEL_CHARS) or "Customer",
                platform=c.platform[:20],
                lead_score=c.lead_score,
                lead_stage=c.lead_stage,
                last_activity_label=_clip(activity[i], 60) if i < len(activity) else None,
            )
            for i, c in enumerate(shown)
        ],
        reply_ids=[c.conversation_id for c in shown if c.conversation_id][:LEAD_REPLY_MAX],
        more_route=more_route,
    )


# ---------------------------------------------------------------- table (VIS-09)

TEXT_CELL_CHARS = 80


@dataclass(frozen=True)
class Column:
    """A table column: ``figures`` are right-aligned (a count, a percent or money text)."""

    key: str
    label: str
    figures: bool = False
    format: Literal["text", "count", "percent"] = "text"


def table(
    *,
    title: str,
    columns: Sequence[Column],
    rows: Sequence[Sequence[str | float | None]],
    total: int,
    more_route: str | None,
) -> TableVisual:
    """The first MAX_TABLE_ROWS rows of what a tool listed, cells in the columns' order. A row of
    the wrong width fails the build."""
    if not 1 <= len(columns) <= MAX_TABLE_COLUMNS:
        raise ValueError("a table has 1 to 6 columns")
    if any(len(row) != len(columns) for row in rows):
        raise ValueError("a row must have a cell for every column")
    return TableVisual(
        kind="table",
        title=_clip(title, 120) or "Table",
        columns=[
            TableColumn(
                key=c.key[:30],
                label=_clip(c.label, 40) or c.key,
                align="right" if c.figures else "left",
                format=c.format,
            )
            for c in columns
        ],
        rows=[
            TableRow(cells=[_clip(v, TEXT_CELL_CHARS) if isinstance(v, str) else v for v in row])
            for row in rows[:MAX_TABLE_ROWS]
        ],
        total=total,
        more_route=more_route,
    )


# ---------------------------------------------------------------- building and reading


def size_of(visual: Visual) -> int:
    return len(visual.model_dump_json().encode())


def safe[V: Visual](kind: str, build: Callable[[], V]) -> V | None:
    """``build()``, or None (logged and counted) when it fails or is over MAX_VISUAL_BYTES: the
    visual is dropped and the tool's result stands."""
    started = time.monotonic()
    try:
        visual = build()
        size = size_of(visual)
    except Exception:
        log.warning("agent_visual_failed", kind=kind, exc_info=True)
        AGENT_VISUALS.inc(kind=kind, outcome="dropped")
        return None
    if size > MAX_VISUAL_BYTES:
        log.warning("agent_visual_too_large", kind=kind, bytes=size)
        AGENT_VISUALS.inc(kind=kind, outcome="dropped")
        return None
    log.info(
        "agent_visual",
        kind=kind,
        bytes=size,
        build_ms=round((time.monotonic() - started) * 1000),
    )
    AGENT_VISUALS.inc(kind=kind, outcome="built")
    return visual


def read(raw: Any) -> Visual | None:
    """A stored ``visual`` as the current model, or None (counted) when it doesn't fit any more
    (an older version, a hand-edited row)."""
    if not isinstance(raw, dict):
        return None
    try:
        return VISUAL_ADAPTER.validate_python(raw)
    except ValidationError:
        kind = raw.get("kind")
        label = kind if kind in KINDS else "unknown"
        log.warning("agent_visual_invalid", kind=label)
        AGENT_VISUALS.inc(kind=label, outcome="dropped_stored")
        return None
