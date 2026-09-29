"""The numbers behind a comparison (TR-AGT-05; agent-architecture §6): engagement rate, and one
metric of a post against a baseline's median and mean. Pure functions; nothing here guesses a
missing value (FR-AGT-04: numbers come from the database, never the model)."""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence

from socialhood.models.analytics import PostMetric
from socialhood.schemas.analytics import MIN_COMPARABLE_POSTS, MetricComparison, MetricName

INTERACTIONS = (PostMetric.LIKES, PostMetric.COMMENTS, PostMetric.SHARES, PostMetric.SAVES)


def engagement_rate(metrics: Mapping[str, int | None]) -> float | None:
    """(likes + comments + shares + saves) ÷ reach, in %, from figures at one age; None unless
    reach and all four interactions are known and reach is above 0."""
    reach = metrics.get(PostMetric.REACH)
    parts = [metrics.get(name) for name in INTERACTIONS]
    if not reach or reach <= 0 or any(part is None for part in parts):
        return None
    return round(sum(part or 0 for part in parts) / reach * 100, 2)


def compare(metric: MetricName, value: float | None, baseline: Sequence[float]) -> MetricComparison:
    """``value`` against the baseline values of the posts that have this metric at this age.

    The median and mean are given whenever there is a baseline; the difference in % and in
    standard deviations only from MIN_COMPARABLE_POSTS values (fewer say nothing reliable), and
    only against a median above 0 and a spread above 0.
    """
    size = len(baseline)
    if not size:
        return MetricComparison(metric=metric, value=value, sample_size=0)
    median = float(statistics.median(baseline))
    mean = float(statistics.fmean(baseline))
    diff_pct = z_score = None
    if value is not None and size >= MIN_COMPARABLE_POSTS:
        if median > 0:
            diff_pct = round((value - median) / median * 100, 1)
        spread = statistics.stdev(baseline)
        if spread > 0:
            z_score = round((value - mean) / spread, 2)
    return MetricComparison(
        metric=metric,
        value=value,
        baseline_median=round(median, 2),
        baseline_mean=round(mean, 2),
        diff_pct=diff_pct,
        z_score=z_score,
        sample_size=size,
    )
