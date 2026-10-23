"""GR-38 (docs/architecture/generative-ui/05, 06): the visual builders are pure functions of service
data (numbers, None, caps, size), a failing or oversized build drops only the visual, stored
visuals are re-checked on read, the model never sees one, and the run shows at most three."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from socialhood.agent import visuals
from socialhood.agent.report import model_view
from socialhood.schemas.agent import (
    MAX_METRICS,
    MAX_RANKED,
    MAX_TOPICS,
    MAX_VISUAL_BYTES,
    MAX_VISUALS,
    VISUAL_ADAPTER,
    AgentRun,
    MetricComparisonVisual,
    RankedPostsVisual,
    SentimentSummaryVisual,
    VisualMetricKey,
)
from socialhood.schemas.analytics import (
    AccountMetricFigure,
    AccountMetricName,
    AccountMetrics,
    DaySpan,
    MetricName,
    PeriodFigure,
)
from socialhood.services import agent_runs

OCT = DaySpan(since=date(2026, 10, 1), until=date(2026, 10, 22), days=22)
SEP = DaySpan(since=date(2026, 9, 1), until=date(2026, 9, 22), days=22)


def figure(
    metric: AccountMetricName,
    current: float | None,
    previous: float | None,
    pct: float | None = None,
    direction: str | None = None,
    *,
    known: int = 22,
    gap: Any = None,
) -> AccountMetricFigure:
    return AccountMetricFigure(
        metric=metric,
        current=PeriodFigure(
            value=current,
            days_known=known if current is not None else 0,
            days_total=22,
            unavailable=gap,
        ),
        previous=PeriodFigure(
            value=previous,
            days_known=22 if previous is not None else 0,
            days_total=22,
            unavailable=gap,
        ),
        change_pct=pct,
        direction=direction,  # type: ignore[arg-type]
    )


def data(*figures: AccountMetricFigure, comparable: bool = True) -> AccountMetrics:
    return AccountMetrics(
        period=OCT, previous_period=SEP, comparable=comparable, figures=list(figures)
    )


# ---------------------------------------------------------------- metric_comparison


def test_a_comparison_carries_the_services_numbers_unchanged() -> None:
    visual = visuals.metric_comparison(
        data(
            figure("reach", 11800, 10000, 18.0, "up"),
            figure("comments", 91, 100, -9.0, "down"),
            figure("followers", 1520, 1500, 1.3, "up"),
        ),
        account_label="@maple.bakery",
        note="Compared over the same 22 days of each period.",
    )
    assert isinstance(visual, MetricComparisonVisual)
    assert [(m.key, m.current, m.previous, m.change_pct, m.direction) for m in visual.metrics] == [
        ("reach", 11800, 10000, 18.0, "up"),
        ("comments", 91, 100, -9.0, "down"),
        ("followers", 1520, 1500, 1.3, "up"),
    ]
    assert [m.tone for m in visual.metrics] == ["good", "bad", "good"]
    assert (visual.current.label, visual.previous.label) == ("1-22 Oct 2026", "1-22 Sep 2026")
    assert (visual.current.days, visual.comparable) == (22, True)
    assert visual.title == "@maple.bakery: 1-22 Oct 2026 against 1-22 Sep 2026"
    assert visual.account_label == "@maple.bakery"


def test_more_unfollows_is_bad_news_and_a_flat_change_is_neutral() -> None:
    visual = visuals.metric_comparison(
        data(
            figure("unfollows", 30, 20, 50.0, "up"),
            figure("follows", 10, 20, -50.0, "down"),
            figure("views", 1000, 999, 0.1, "flat"),
        ),
        account_label=None,
        note=None,
    )
    assert [m.tone for m in visual.metrics] == ["bad", "bad", "neutral"]
    assert visual.title.startswith("All accounts: ")


def test_periods_that_cant_be_compared_show_no_change_and_no_tone() -> None:
    visual = visuals.metric_comparison(
        data(figure("reach", 500, 100), comparable=False),
        account_label=None,
        note="Different lengths.",
    )
    [m] = visual.metrics
    assert (visual.comparable, m.change_pct, m.direction, m.tone) == (False, None, None, "neutral")
    assert (m.current, m.previous) == (500, 100)  # the totals are still given


def test_a_figure_without_a_reading_is_unavailable_with_the_reason_never_zero() -> None:
    visual = visuals.metric_comparison(
        data(figure("reach", None, None, gap="insights_not_granted")),
        account_label="@maple.bakery",
        note=None,
    )
    [m] = visual.metrics
    assert (m.current, m.previous, m.change_pct, m.tone) == (None, None, None, "neutral")
    assert m.unavailable == "Insights aren't granted for @maple.bakery, so this isn't available."
    assert (m.current_coverage, m.previous_coverage) == (None, None)


def test_gaps_are_stated_as_n_of_m_days() -> None:
    visual = visuals.metric_comparison(
        data(figure("reach", 900, 1000, -10.0, "down", known=21)), account_label=None, note=None
    )
    [m] = visual.metrics
    assert (m.current_coverage, m.previous_coverage) == ("21 of 22 days", None)
    assert m.unavailable is None


def test_a_comparison_shows_at_most_eight_metrics() -> None:
    many = [figure("reach", 1, 1) for _ in range(MAX_METRICS + 3)]
    assert len(visuals.metric_comparison(data(*many), account_label=None, note=None).metrics) == 8


def test_the_reason_text_is_one_string_for_the_visual_and_the_caveat() -> None:
    assert "No daily figures" in visuals.gap_words("no_readings", "x")
    assert "No Instagram account" in visuals.gap_words("no_account", "x")
    assert "@shop" in visuals.gap_words("insights_not_granted", "@shop")


# ---------------------------------------------------------------- ranked_posts


def ranked(count: int = 3, **over: Any) -> RankedPostsVisual:
    rows = [
        visuals.RankedInput(
            post_id=uuid.uuid4(),
            label=f"Reel of {i + 1} Oct",
            format="reel",
            caption=f"Caption {i}",
            thumbnail_url=f"https://cdn.example/{i}.jpg",
            value=1000.0 - i,
        )
        for i in range(count)
    ]
    args: dict[str, Any] = {
        "metric": "reach",
        "period": visuals.period_of(date(2026, 10, 1), date(2026, 10, 22)),
        "age_label": "latest figures",
        "considered": count,
        "rows": rows,
    }
    return visuals.ranked_posts(**{**args, **over})


def test_ranked_posts_keep_the_services_order_and_values() -> None:
    visual = ranked(3)
    assert [i.value for i in visual.items] == [1000.0, 999.0, 998.0]
    assert (visual.title, visual.metric_label, visual.format) == (
        "Top posts by reach",
        "Reach",
        "count",
    )
    assert (visual.considered, visual.period.label if visual.period else None) == (
        3,
        "1-22 Oct 2026",
    )


def test_engagement_rate_is_a_percent() -> None:
    assert ranked(1, metric="engagement_rate").format == "percent"


def test_a_ranking_shows_at_most_ten_posts() -> None:
    assert len(ranked(MAX_RANKED + 5).items) == 10


@pytest.mark.parametrize(
    ("url", "kept"),
    [
        ("https://scontent.cdninstagram.com/v/t51/a.jpg?x=1", True),
        ("http://scontent.cdninstagram.com/a.jpg", False),
        ("javascript:alert(1)", False),
        ("data:image/png;base64,AAAA", False),
        ("//evil.example/a.jpg", False),
        ("https://", False),
        ("https://a.example/a b.jpg", False),
        ("https://a.example/" + "x" * 400, False),
        ("", False),
        (None, False),
    ],
)
def test_a_thumbnail_must_be_a_plain_https_address_that_fits(url: str | None, kept: bool) -> None:
    assert (visuals.safe_thumbnail(url) is not None) == kept


def test_customer_text_is_clipped_and_stays_text() -> None:
    nasty = "<img src=x onerror=alert(1)>\n‮evil " + "y" * 300
    visual = ranked(
        1, rows=[visuals.RankedInput(uuid.uuid4(), "Reel of 1 Oct", "reel", nasty, None, 5.0)]
    )
    [item] = visual.items
    assert item.caption is not None
    assert len(item.caption) <= 100
    assert item.caption.startswith("<img src=x onerror=alert(1)>")  # not stripped: rendered as text
    assert "\n" not in item.caption


# ---------------------------------------------------------------- sentiment_summary


def test_a_sentiment_summary_has_the_counts_and_at_most_six_topics() -> None:
    visual = visuals.sentiment_summary(
        scope="comments made 1-22 Oct",
        period=visuals.period_of(date(2026, 10, 1), date(2026, 10, 22)),
        total=120,
        positive=60,
        neutral=20,
        negative=10,
        spam=5,
        not_analysed=25,
        topics=[(f"topic {i}", 10 - i) for i in range(MAX_TOPICS + 4)],
    )
    assert isinstance(visual, SentimentSummaryVisual)
    assert (visual.total, visual.positive, visual.neutral, visual.negative) == (120, 60, 20, 10)
    assert (visual.spam, visual.not_analysed) == (5, 25)
    assert len(visual.topics) == 6
    assert visual.topics[0].count == 10


# ---------------------------------------------------------------- size and failure


def worst_comparison() -> MetricComparisonVisual:
    long_gap = "x" * 400
    figures = [
        AccountMetricFigure(
            metric=metric,
            current=PeriodFigure(value=123456789.5, days_known=300, days_total=366),
            previous=PeriodFigure(value=987654321.5, days_known=300, days_total=366),
            change_pct=-99999.9,
            direction="down",
        )
        for metric in get_args(AccountMetricName)[:8]
    ]
    visual = visuals.metric_comparison(
        AccountMetrics(
            period=DaySpan(since=date(2025, 9, 1), until=date(2026, 9, 1), days=366),
            previous_period=DaySpan(since=date(2024, 8, 1), until=date(2025, 8, 1), days=366),
            comparable=True,
            figures=figures,
        ),
        account_label="@" + "a" * 100,
        note=long_gap,
    )
    return visual


def test_the_biggest_visuals_fit_in_eight_kilobytes() -> None:
    comparison = worst_comparison()
    posts = ranked(
        MAX_RANKED,
        rows=[
            visuals.RankedInput(
                uuid.uuid4(),
                "R" * 80,
                "reel",
                "c" * 300,
                "https://cdn.example/" + "t" * 370,
                123456789.123,
            )
            for _ in range(MAX_RANKED)
        ],
    )
    split = visuals.sentiment_summary(
        scope="s" * 300,
        period=None,
        total=10**9,
        positive=1,
        neutral=1,
        negative=1,
        spam=1,
        not_analysed=1,
        topics=[("t" * 90, 10**9) for _ in range(MAX_TOPICS)],
    )
    for visual in (comparison, posts, split):
        assert visuals.size_of(visual) <= MAX_VISUAL_BYTES, visual.kind
    assert len(posts.items) == 10
    assert len(comparison.metrics) == 8


def test_a_builder_that_fails_drops_only_the_visual() -> None:
    def broken() -> MetricComparisonVisual:
        raise RuntimeError("boom")

    assert visuals.safe("metric_comparison", broken) is None
    assert visuals.safe("metric_comparison", worst_comparison) is not None


def test_a_visual_over_the_size_limit_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(visuals, "MAX_VISUAL_BYTES", 100)
    assert visuals.safe("ranked_posts", ranked) is None


# ---------------------------------------------------------------- reading stored visuals


def test_a_stored_visual_reads_back_as_the_same_visual() -> None:
    visual = ranked(2)
    stored = visual.model_dump(mode="json")
    assert visuals.read(stored) == visual


@pytest.mark.parametrize(
    "stored",
    [
        None,
        "not a visual",
        [],
        {},
        {"kind": "pie_chart", "title": "x"},  # a kind this version doesn't know
        {"kind": "ranked_posts"},  # missing fields
        {"kind": "metric_comparison", "title": "x", "metrics": "many"},
    ],
)
def test_an_invalid_stored_visual_is_dropped_not_raised(stored: Any) -> None:
    assert visuals.read(stored) is None


def test_the_union_is_closed_and_kind_is_required() -> None:
    for model in (MetricComparisonVisual, RankedPostsVisual, SentimentSummaryVisual):
        assert model.model_fields["kind"].is_required()  # the web narrows on it
    with pytest.raises(ValidationError):
        VISUAL_ADAPTER.validate_python({"kind": "table", "title": "x"})
    assert {
        get_args(m.model_fields["kind"].annotation)[0]
        for m in (MetricComparisonVisual, RankedPostsVisual, SentimentSummaryVisual)
    } == set(visuals.KINDS)


def test_every_metric_has_a_label_and_the_names_agree_across_schemas() -> None:
    keys = set(get_args(VisualMetricKey))
    assert set(visuals.METRICS) == keys
    assert set(get_args(AccountMetricName)) <= keys
    assert set(get_args(MetricName)) <= keys


# ---------------------------------------------------------------- the model's view and the run


def test_the_model_never_reads_the_visual() -> None:
    stored = {
        "summary": "Ranked 3 posts",
        "items": [{"value": 1}],
        "visual": ranked(1).model_dump(mode="json"),
        "refs": [],
    }
    seen = model_view(stored, [])
    assert "visual" not in seen
    assert seen["items"] == [{"value": 1}]
    assert "visual" in stored  # the stored result keeps it


def test_a_run_shows_its_visuals_in_step_order_at_most_three() -> None:
    a, b, c, d = (
        ranked(1, metric=m).model_dump(mode="json") for m in ("reach", "views", "likes", "saves")
    )
    shown = agent_runs.shown_visuals([a, b, c, d])
    assert [v.metric_key for v in shown if isinstance(v, RankedPostsVisual)] == [
        "reach",
        "views",
        "likes",
    ]
    assert len(shown) == MAX_VISUALS


def test_invalid_stored_visuals_are_skipped_without_losing_the_rest() -> None:
    good = ranked(1).model_dump(mode="json")
    shown = agent_runs.shown_visuals([{"kind": "old_kind"}, None, good, {"kind": "ranked_posts"}])
    assert len(shown) == 1


def test_the_same_visual_twice_is_shown_once() -> None:
    one = ranked(1).model_dump(mode="json")
    assert len(agent_runs.shown_visuals([one, dict(one)])) == 1


def split(topics: list[tuple[str, int]], scope: str = "comments made 1-22 Oct") -> dict[str, Any]:
    return visuals.sentiment_summary(
        scope=scope,
        period=None,
        total=10,
        positive=5,
        neutral=3,
        negative=2,
        spam=0,
        not_analysed=0,
        topics=topics,
    ).model_dump(mode="json")


def test_a_sentiment_summary_with_topics_replaces_the_one_without_for_the_same_scope() -> None:
    shown = agent_runs.shown_visuals([split([]), split([("price", 4)])])
    assert len(shown) == 1
    assert isinstance(shown[0], SentimentSummaryVisual)
    assert [t.label for t in shown[0].topics] == ["price"]
    other = agent_runs.shown_visuals([split([]), split([("price", 4)], scope="comments on a Reel")])
    assert len(other) == 2


def test_runs_can_hold_no_more_than_three_visuals() -> None:
    field = AgentRun.model_fields["visuals"]
    assert field.is_required()
    maxes = [getattr(m, "max_length", None) for m in field.metadata]
    assert MAX_VISUALS in maxes


def test_a_step_result_never_carries_its_visual_a_second_time() -> None:
    result = {"summary": "x", "visual": {"kind": "ranked_posts"}, "items": []}
    assert agent_runs._without_visual(result) == {"summary": "x", "items": []}
    assert "visual" in result  # the stored result is untouched
    assert agent_runs._without_visual(None) is None
    plain = {"summary": "x"}
    assert agent_runs._without_visual(plain) is plain
