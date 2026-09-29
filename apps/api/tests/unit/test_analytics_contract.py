"""The P6 contract's shared names agree with each other (FR-ANL-01, FR-ANL-02, TR-AI-11,
UX-SCR-05): the adapters' insight fields are the stored metric keys, the API's ages and metrics
are the snapshot windows and metric names, and stored comment stats read back with zeros."""

from __future__ import annotations

from dataclasses import fields
from typing import get_args

from socialhood.models.ai import Intent
from socialhood.models.analytics import (
    LIVE_COUNT_WINDOWS,
    WINDOW_AGES,
    AccountMetric,
    PostMetric,
    SnapshotWindow,
)
from socialhood.platforms.base import AccountInsights, MediaInsights
from socialhood.schemas.analytics import AgeName, MetricName, PostMetrics
from socialhood.schemas.posts import COMMENT_FILTER_INTENTS, CommentFilter, CommentStats


def test_insight_fields_are_the_stored_metric_keys() -> None:
    assert {f.name for f in fields(MediaInsights)} == set(PostMetric)
    account = {f.name for f in fields(AccountInsights)} - {"followers_count"}
    assert account == set(AccountMetric)


def test_metrics_keep_only_known_values() -> None:
    assert MediaInsights(reach=10, likes=0).metrics() == {"reach": 10, "likes": 0}
    day = AccountInsights(followers_count=1500, follows=4)
    assert day.metrics() == {"follows": 4}
    assert AccountInsights(followers_count=1500).metrics() == {}


def test_windows_and_ages_agree() -> None:
    assert set(WINDOW_AGES) == set(SnapshotWindow)
    ages = list(WINDOW_AGES.values())
    assert ages == sorted(ages)
    assert sorted(LIVE_COUNT_WINDOWS) == ["1h", "6h"]
    assert set(get_args(AgeName)) == {w.value for w in SnapshotWindow} | {"lifetime"}


def test_api_metrics_come_from_snapshots() -> None:
    assert set(get_args(MetricName)) == set(PostMetrics.model_fields)
    assert set(get_args(MetricName)) - {"engagement_rate"} <= set(PostMetric)


def test_comment_filters_name_real_intents() -> None:
    assert set(COMMENT_FILTER_INTENTS) <= set(get_args(CommentFilter))
    for intents in COMMENT_FILTER_INTENTS.values():
        assert set(intents) <= set(Intent)


def test_stored_comment_stats_read_back_with_zeros() -> None:
    zero = CommentStats(total=0, analysed=0, positive=0, neutral=0, negative=0, spam=0)
    assert CommentStats.from_stored({}) == zero
    assert CommentStats.from_stored(None) == zero
    stored = {"total": 7, "analysed": 5, "positive": 3, "negative": 1, "spam": 1, "extra": 9}
    assert CommentStats.from_stored(stored) == zero.model_copy(
        update={"total": 7, "analysed": 5, "positive": 3, "negative": 1, "spam": 1}
    )
