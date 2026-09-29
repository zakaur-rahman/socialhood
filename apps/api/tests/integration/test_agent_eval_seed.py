"""The agent eval's seeded workspace against the tools, without a model (TA.6): each figure the
eval expects (computed from the seed's declarations in tests/evals/seed.py) is what the tool
returns from the database at the seed's clock. A failure here is a seed or a tool bug, not the
model's."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.errors import ApiError
from socialhood.models.identity import Role
from socialhood.platforms.deps import PlatformDeps
from socialhood.settings import Settings
from tests.evals import seed as S
from tests.support.agent_tools import Shop, tool_platform


@pytest.fixture
async def platform(api_settings: Settings) -> AsyncIterator[PlatformDeps]:
    async with tool_platform(api_settings) as deps:
        yield deps


@pytest.fixture
async def shop(engine: AsyncEngine, clean_db: None, platform: PlatformDeps) -> Shop:
    seeded = await S.seed(engine)
    shop = Shop(
        engine,
        platform,
        seeded.workspace_id,
        seeded.users["owner"],
        seeded.accounts["ig"],
        timezone=S.TIMEZONE,
    )
    shop.seeded = seeded  # type: ignore[attr-defined]
    return shop


async def call(shop: Shop, name: str, role: Role = Role.OWNER, **args: Any) -> Any:
    return await shop.call(name, args, role=role, now=S.NOW)


def ids(shop: Shop) -> S.Seeded:
    return shop.seeded  # type: ignore[attr-defined, no-any-return]


async def test_inbox_views_and_ranges_match_the_seed(shop: Shop) -> None:
    lw_start, lw_end = S.days(*S.last_week())
    expected = {
        ("needs_reply", None): len(S.conversations("needs_reply")),
        ("leads", None): len(S.conversations("leads")),
        ("archived", None): len(S.conversations("archived")),
        ("all", "today"): len(S.conversations(start=S.day_start(S.TODAY))),
        ("all", "last week"): len(S.conversations(start=lw_start, end=lw_end)),
        ("all", "since Monday"): len(S.conversations(start=S.day_start(S.this_week()[0]))),
    }
    for (view, phrase), count in expected.items():
        found = await call(shop, "search_conversations", view=view, range=phrase)
        assert found.total == count, (view, phrase)
    whatsapp = await call(shop, "search_conversations", platform="whatsapp")
    assert whatsapp.total == len(S.conversations(platform="whatsapp"))
    closing = await call(shop, "search_conversations", view="closing_soon")
    assert [i.contact for i in closing.items] == [c.name for c in S.conversations("closing_soon")]
    leads = await call(shop, "search_conversations", view="leads")
    assert sorted(i.lead_score for i in leads.items) == sorted(
        c.lead_score for c in S.conversations("leads")
    )


async def test_customers_and_conversations_match_the_seed(shop: Shop) -> None:
    seeded = ids(shop)
    neha = await call(shop, "get_customer", contact_id=str(seeded.contacts["neha"]))
    assert neha.comment_count == sum(1 for _, c in S.COMMENT.values() if c.author == "neha.bakes")
    rahul = await call(shop, "get_conversation", conversation_id=str(seeded.conversations["rahul"]))
    assert rahul.analysis.sentiment == "negative"
    assert rahul.reply_window.state == "open"
    sneha = await call(shop, "get_conversation", conversation_id=str(seeded.conversations["sneha"]))
    assert sneha.analysis is None
    assert sneha.reply_window.state == "closed"
    priyas = await call(shop, "find_contact", name_or_handle="Priya")
    assert priyas.total == 2


async def test_comment_counts_match_the_seed(shop: Shop) -> None:
    lw = S.days(*S.last_week())
    tm = S.days(*S.this_month())
    yesterday = S.days(S.TODAY.replace(day=S.TODAY.day - 1), S.TODAY.replace(day=S.TODAY.day - 1))
    latest = str(ids(shop).posts["p1"])
    negative = await call(shop, "get_post_comments", post_id=latest, sentiment="negative")
    assert negative.total == len(S.comments(post="p1", sentiment="negative"))
    last_week = await call(shop, "get_post_comments", sentiment="negative", range="last week")
    assert last_week.total == len(S.comments(start=lw[0], end=lw[1], sentiment="negative"))
    spam = await call(shop, "get_post_comments", spam="only", range="this month")
    assert spam.total == len(S.comments(start=tm[0], end=tm[1], spam=True))
    replied = await call(
        shop, "get_post_comments", replied=True, spam="include", range="this month"
    )
    assert replied.total == len(S.comments(start=tm[0], end=tm[1], replied=True, spam=None))
    unreplied = await call(shop, "get_post_comments", post_id=latest, replied=False)
    assert unreplied.total == len(S.comments(post="p1", replied=False))
    kal = await call(shop, "get_post_comments", range="yesterday")
    assert (kal.total, kal.in_scope) == (
        len(S.comments(start=yesterday[0], end=yesterday[1])),
        len(S.comments(start=yesterday[0], end=yesterday[1], spam=None)),
    )
    eggless = await call(shop, "search_comments", q="eggless")
    assert eggless.total == len(S.comments(q="eggless", spam=None))
    # The default range is stated with its phrase, so the answer can say "the last 90 days".
    assert eggless.period is not None
    assert eggless.period.phrase == "the last 90 days"


async def test_posts_and_figures_match_the_seed(shop: Shop) -> None:
    seeded = ids(shop)
    tm = S.days(*S.this_month())
    lw = S.days(*S.last_week())
    month = await call(shop, "get_posts", range="this month")
    assert month.total == len(S.posts(start=tm[0]))
    week = await call(shop, "get_posts", range="last week")
    assert week.total == len(S.posts(start=lw[0], end=lw[1]))
    latest = await call(shop, "get_latest_post")
    assert latest.post.id == seeded.posts[S.latest_post().key]
    assert latest.post.age == f"{S.age_hours(S.latest_post())} hours"

    p1 = S.POST["p1"]
    figures = await call(shop, "post_performance", post_id=str(seeded.posts["p1"]))
    at_24h = S.metrics_at(p1, "24h")
    assert (figures.age, figures.metrics.reach, figures.metrics.likes) == (
        "24h",
        at_24h["reach"],
        at_24h["likes"],
    )
    assert figures.metrics.engagement_rate == S.engagement_rate(at_24h)
    p2 = await call(
        shop, "post_performance", post_id=str(seeded.posts["p2"]), at_age="after 72 hours"
    )
    assert p2.metrics.reach == S.metrics_at(S.POST["p2"], "72h")["reach"]
    p8 = await call(shop, "post_performance", post_id=str(seeded.posts["p8"]))
    assert not p8.insights_granted
    assert p8.metrics.reach is None

    compared = await call(shop, "compare_posts", post_id=str(seeded.posts["p1"]))
    reach = next(m for m in compared.metrics if m.metric == "reach")
    expected = S.compare(p1, "reach")
    assert (compared.baseline.size, reach.baseline_median, reach.diff_pct) == (
        expected.size,
        expected.median,
        expected.diff_pct,
    )

    top = await call(shop, "top_posts", metric="reach", range="this month", n=3)
    ranked, considered = S.top_posts("reach", *S.this_month(), n=3)
    assert [i.value for i in top.items] == [v for _, v in ranked]
    assert top.considered == considered
    # Only Instagram accounts have insights to grant: the WhatsApp number isn't named.
    assert [c for c in top.caveats if c.startswith("Insights aren't granted")] == [
        "Insights aren't granted for @maple.cakes, so reach, views, shares, saves and engagement "
        "rate aren't available; likes and comments are."
    ]
    er, _ = S.top_posts("engagement_rate", *S.last_month(), n=1)
    best = await call(shop, "top_posts", metric="engagement_rate", range="last month", n=1)
    assert best.items[0].value == er[0][1]


async def test_sentiment_and_topics_match_the_seed(shop: Shop) -> None:
    seeded = ids(shop)
    latest = await call(shop, "sentiment_distribution", post_id=str(seeded.posts["p1"]))
    split = S.sentiment_split(post="p1")
    assert (latest.total, latest.analysed, latest.positive_pct) == (
        split.total,
        split.analysed,
        split.pct("positive"),
    )
    month = await call(shop, "sentiment_distribution", range="this month")
    tm = S.sentiment_split(since=S.this_month()[0], until=S.TODAY)
    assert (month.total, month.positive_pct, month.negative_pct) == (
        tm.total,
        tm.pct("positive"),
        tm.pct("negative"),
    )
    topics = await call(shop, "comment_topics", range="this month")
    assert [(t.label, t.count) for t in topics.topics] == S.topic_counts(
        since=S.this_month()[0], until=S.TODAY
    )[:5]


async def test_schedules_automations_and_gaps_match_the_seed(shop: Shop) -> None:
    seeded = ids(shop)
    pending = await call(shop, "list_scheduled_messages")
    assert pending.total == len(S.pending_messages())
    today = await call(shop, "list_scheduled_messages", range="today")
    assert today.total == len(S.messages_timed(S.TODAY, S.TODAY))
    posts = await call(shop, "list_scheduled_posts")
    assert posts.total == len(S.pending_posts())
    week = await call(shop, "list_scheduled_posts", range="this week")
    assert week.total == len(S.posts_timed(*S.this_week()))

    automations = await call(shop, "list_automations")
    assert sum(1 for a in automations.items if a.status == "active") == len(S.active_automations())
    for key, days in (("menu", 7), ("price", 30), ("classes", 30)):
        stats = await call(
            shop, "get_automation_stats", automation_id=str(seeded.automations[key]), days=days
        )
        figures = S.automation_figures(key, days)
        assert (
            stats.runs,
            stats.dms_sent,
            stats.public_replies,
            stats.replied_24h,
            stats.failures,
            stats.skipped_cooldown,
        ) == (
            figures.runs,
            figures.dms_sent,
            figures.public_replies,
            figures.replied_24h,
            figures.failures,
            figures.skipped_cooldown,
        ), key

    gaps = await call(shop, "list_knowledge_gaps")
    assert [(g.topic, g.asked) for g in gaps.items] == [
        (g.topic, g.occurrences) for g in S.open_gaps()
    ]


async def test_a_member_cant_use_the_admin_tools(shop: Shop) -> None:
    for name, args in (
        ("list_automations", {}),
        ("list_scheduled_posts", {}),
        ("list_knowledge_gaps", {}),
    ):
        with pytest.raises(ApiError) as refused:
            await call(shop, name, role=Role.AGENT, **args)
        assert refused.value.code == "forbidden"
