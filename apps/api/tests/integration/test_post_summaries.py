"""T6.2: summarize_post (TR-AI-11, FR-CMT-04). Done when: topic counts match the mapping. SQL
counts the sentiments and the 50 most frequent topics, the model writes the summary and merges the
topics into at most 6 labels, and code counts each label's comments and sentiment. Plus: the
stored summary and event, the 2-credit charge, the 24 h sweep, and when nothing is summarised."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from socialhood.jobs.tasks.comments import dispatch_summaries
from socialhood.services.comments.summaries import TopicLabel, label_topics
from socialhood.settings import Settings
from tests.support.analysis import use_credits
from tests.support.analytics import make_comment_analysis
from tests.support.automations import make_comment
from tests.support.comments import Comments
from tests.support.ingest import jobs, stream
from tests.support.runtime import make_world, platform_deps
from tests.support.sending import clean_outbox


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def cw(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    clean_db: None,
    queue: None,
) -> AsyncIterator[Comments]:
    async with platform_deps(api_settings, monkeypatch) as deps:
        yield Comments(await make_world(engine, redis, deps))


async def analysed(
    cw: Comments,
    post: uuid.UUID,
    topic: str | None,
    sentiment: str,
    n: int = 1,
    *,
    spam: bool = False,
    deleted: bool = False,
    **values: Any,
) -> None:
    """``n`` comments on the post, each with its analysis."""
    for i in range(n):
        comment_id = await make_comment(
            cw.world.engine,
            workspace_id=cw.wid,
            account_id=cw.account_id,
            media_item_id=post,
            text=f"about {topic or 'nothing'} ({sentiment} {i})",
        )
        await make_comment_analysis(
            cw.world.engine,
            workspace_id=cw.wid,
            comment_id=comment_id,
            sentiment=sentiment,
            topic=topic,
            is_spam=spam,
            **values,
        )
        if deleted:
            await cw.execute("UPDATE comments SET deleted_at = now() WHERE id = :id", id=comment_id)


async def test_topic_counts_match_the_mapping(cw: Comments, fake_ai: FakeProvider) -> None:
    post = await cw.post(caption="Blue linen shirts are back")
    await analysed(cw, post, "price", "positive", 3)
    await analysed(cw, post, "price", "negative", 2)
    await analysed(cw, post, "cost", "neutral", 2)
    await analysed(cw, post, "shipping", "positive", 2)
    await analysed(cw, post, "shipping", "negative", 2)
    await analysed(cw, post, "delivery time", "negative")
    await analysed(cw, post, "blue colour", "positive", 3)
    await analysed(cw, post, None, "positive")
    await analysed(cw, post, "price", "neutral", 2, spam=True)  # spam: not a topic
    await analysed(cw, post, "price", "positive", deleted=True)  # deleted: not counted
    fake_ai.respond(
        "post_summary",
        {
            "summary": "  People ask about prices\nand delivery.  Most love the blue colour. ",
            "labels": [
                {"label": "Price", "members": ["price", "cost", "a topic nobody wrote"]},
                {"label": "Delivery", "members": ["shipping", "delivery time", "price"]},
                {"label": "Nothing here", "members": ["nope"]},
            ],
        },
    )
    now = datetime.now(UTC)

    run = await cw.summarize(post, now=now)

    assert run.outcome == "summarised"
    [call] = fake_ai.calls_for("post_summary")
    assert (call.model, call.max_output_tokens) == (cw.settings.ai_model_reply, 1024)
    lines = call.contents[0].text.splitlines()
    assert lines[:8] == [
        "POST CAPTION: Blue linen shirts are back",
        "COMMENTS: 9 positive, 2 neutral, 5 negative, 2 spam",
        "TOPICS (topic: comments):",
        "- price: 5",
        "- shipping: 4",
        "- blue colour: 3",
        "- cost: 2",
        "- delivery time: 1",
    ]
    assert "SAMPLE COMMENTS:" in lines
    assert "about price (neutral" not in call.contents[0].text  # spam is no sample
    assert "blue" not in call.system.casefold()  # the post is data, not instructions

    row = await cw.one(
        "SELECT summary, topics, summary_updated_at FROM media_items WHERE id = :id", id=post
    )
    assert row["summary"] == "People ask about prices and delivery. Most love the blue colour."
    # Each label: its topics' comments (spam and deleted left out) counted by code.
    assert row["topics"] == [
        {"label": "price", "count": 7, "positive": 3, "neutral": 2, "negative": 2},
        {"label": "delivery", "count": 5, "positive": 2, "neutral": 0, "negative": 3},
    ]
    assert row["summary_updated_at"] == now
    [event] = await cw.rows("SELECT feature, credits FROM ai_usage_events")
    assert event == {"feature": "post_summary", "credits": 2}
    [(kind, payload)] = await stream(cw.world.redis, cw.wid)
    assert kind == "post.updated"
    assert payload["post"]["summary"] == row["summary"]
    assert [t["label"] for t in payload["post"]["topics"]] == ["price", "delivery"]
    assert payload["post"]["stats"] == {
        "total": 0,  # the factory's comments were never counted at intake
        "analysed": 0,
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "spam": 0,
    }


def test_at_most_six_labels_are_kept_largest_first() -> None:
    topics = [f"topic {i}" for i in range(8)]
    sentiments = {f"topic {i}": {"positive": i + 1} for i in range(8)}
    labels = [TopicLabel(label=f"Label {i}", members=[f"topic {i}"]) for i in range(8)]
    kept = label_topics(labels, topics, sentiments)
    assert [t["label"] for t in kept] == [f"label {i}" for i in (7, 6, 5, 4, 3, 2)]
    assert kept[0] == {"label": "label 7", "count": 8, "positive": 8, "neutral": 0, "negative": 0}


def test_labels_with_the_same_name_merge_and_empty_ones_go() -> None:
    kept = label_topics(
        [
            TopicLabel(label="Price", members=["price"]),
            TopicLabel(label=" price ", members=["cost"]),
            TopicLabel(label="", members=["size"]),
        ],
        ["price", "cost", "size"],
        {"price": {"positive": 2}, "cost": {"negative": 1}, "size": {"neutral": 4}},
    )
    assert kept == [{"label": "price", "count": 3, "positive": 2, "neutral": 0, "negative": 1}]


async def test_the_hourly_sweep_queues_summaries_24_hours_behind(cw: Comments) -> None:
    now = datetime.now(UTC)
    stale = await cw.post()
    fresh = await cw.post()
    current = await cw.post()
    behind = await cw.post()
    await analysed(cw, stale, "price", "neutral", created_at=now - timedelta(hours=25))
    await analysed(cw, fresh, "price", "neutral", created_at=now - timedelta(hours=1))
    await analysed(cw, current, "price", "neutral", created_at=now - timedelta(hours=30))
    await cw.execute(
        "UPDATE media_items SET summary_updated_at = :at WHERE id = :id",
        at=now - timedelta(hours=10),
        id=current,
    )
    await analysed(cw, behind, "price", "neutral", created_at=now - timedelta(hours=26))
    await cw.execute(
        "UPDATE media_items SET summary_updated_at = :at WHERE id = :id",
        at=now - timedelta(hours=30),
        id=behind,
    )

    assert await dispatch_summaries(cw.world.maker, now=now) == 2

    queued = sorted(j["queueing_lock"] for j in await jobs("summarize_post"))
    assert queued == sorted([f"postsum:{stale}", f"postsum:{behind}"])


async def test_nothing_is_summarised_without_analyses_analysis_or_credits(
    cw: Comments, fake_ai: FakeProvider
) -> None:
    post = await cw.post()
    assert (await cw.summarize(post)).outcome == "no_analyses"
    assert (await cw.summarize(uuid.uuid4())).outcome == "not_found"

    await analysed(cw, post, "price", "positive")
    await cw.execute(
        "UPDATE social_accounts SET ai_analysis_enabled = false WHERE id = :id", id=cw.account_id
    )
    assert (await cw.summarize(post)).outcome == "analysis_off"
    await cw.execute(
        "UPDATE social_accounts SET ai_analysis_enabled = true WHERE id = :id", id=cw.account_id
    )
    await use_credits(cw.world.engine, cw.wid, 199, now=datetime.now(UTC))  # 1 left, 2 needed
    assert (await cw.summarize(post)).outcome == "quota_exhausted"

    assert fake_ai.calls_for("post_summary") == []
    row = await cw.one(
        "SELECT summary, summary_updated_at FROM media_items WHERE id = :id", id=post
    )
    assert row == {"summary": None, "summary_updated_at": None}
