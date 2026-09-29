"""Ask Social Hood's comment, post and analytics tools against real data (TA.4; FR-AGT-02,
FR-AGT-03, FR-AGT-04, FR-AGT-06, TR-AGT-05): get_post_comments, search_comments,
prepare_comment_reply, get_posts, get_latest_post, search_posts, post_performance,
compare_posts, top_posts, sentiment_distribution and comment_topics, with their caps, caveats,
action cards and another workspace's ids."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.agent.timeparse import MONTH_ABBR
from socialhood.errors import ApiError
from socialhood.platforms.deps import PlatformDeps
from socialhood.schemas.agent import CommentReplyPrefill
from socialhood.settings import Settings
from tests.support.agent_tools import Shop, make_shop, tool_platform
from tests.support.analytics import make_comment_analysis
from tests.support.automations import make_comment
from tests.support.post_metrics import make_instagram_account, make_post, make_windows


@pytest.fixture
async def platform(api_settings: Settings) -> AsyncIterator[PlatformDeps]:
    async with tool_platform(api_settings) as deps:
        yield deps


@pytest.fixture
async def shop(engine: AsyncEngine, clean_db: None, platform: PlatformDeps) -> Shop:
    return await make_shop(engine, platform)


@pytest.fixture
async def other(engine: AsyncEngine, shop: Shop, platform: PlatformDeps) -> Shop:
    return await make_shop(engine, platform)


async def refused(shop: Shop, name: str, args: dict[str, Any]) -> ApiError:
    with pytest.raises(ApiError) as caught:
        await shop.call(name, args)
    return caught.value


def figures(reach: int, **rest: int) -> dict[str, int]:
    return {
        "reach": reach,
        "views": reach + 900,
        "likes": 300,
        "comments": 88,
        "shares": 20,
        "saves": 40,
        **rest,
    }


@dataclass
class Feed:
    """A reel published 26 hours ago with five comments, and older posts."""

    reel: uuid.UUID
    reel_label: str
    pricey: uuid.UUID  # negative, topic "price"
    love: uuid.UUID  # positive, topic "colours"
    shipping: uuid.UUID  # negative, topic "shipping cost"
    restock: uuid.UUID  # not analysed yet
    spam: uuid.UUID
    image: uuid.UUID  # 3 days old, "Diwali sale"
    old: uuid.UUID  # 40 days old, with an old comment
    old_comment: uuid.UUID


async def comment(
    shop: Shop, post: uuid.UUID, text: str, at: datetime, **analysis: Any
) -> uuid.UUID:
    comment_id = await make_comment(
        shop.engine,
        workspace_id=shop.wid,
        account_id=shop.account_id,
        media_item_id=post,
        text=text,
        commented_at=at,
    )
    if analysis:
        await make_comment_analysis(
            shop.engine, workspace_id=shop.wid, comment_id=comment_id, **analysis
        )
    return comment_id


@pytest.fixture
async def feed(shop: Shop) -> Feed:
    now = datetime.now(UTC)
    on = {"workspace_id": shop.wid, "account_id": shop.account_id}
    posted = now - timedelta(hours=26)
    reel = await make_post(
        shop.engine, posted_at=posted, media_type="reel", caption="Summer reel", **on
    )
    image = await make_post(
        shop.engine, posted_at=now - timedelta(days=3), caption="Diwali sale is on", **on
    )
    old = await make_post(shop.engine, posted_at=now - timedelta(days=40), caption="Old", **on)
    await make_post(shop.engine, posted_at=now - timedelta(hours=1), media_type="story", **on)
    local = posted.astimezone(ZoneInfo(shop.timezone))
    label = f"Reel of {local.day} {MONTH_ABBR[local.month - 1]}"
    at = now - timedelta(minutes=10)
    return Feed(
        reel=reel,
        reel_label=label,
        pricey=await comment(
            shop,
            reel,
            "Too expensive for me",
            at,
            sentiment="negative",
            topic="price",
            intent="pricing",
        ),
        love=await comment(
            shop,
            reel,
            "Love the colours",
            at + timedelta(minutes=1),
            sentiment="positive",
            topic="colours",
            intent="feedback",
        ),
        shipping=await comment(
            shop,
            reel,
            "Shipping cost is too high",
            at + timedelta(minutes=2),
            sentiment="negative",
            topic="shipping cost",
            intent="shipping",
        ),
        restock=await comment(shop, reel, "When will it restock?", at + timedelta(minutes=3)),
        spam=await comment(
            shop,
            reel,
            "Follow me for followers",
            at + timedelta(minutes=4),
            sentiment="neutral",
            topic=None,
            intent="spam",
            is_spam=True,
        ),
        image=image,
        old=old,
        old_comment=await comment(
            shop,
            old,
            "This was lovely",
            now - timedelta(days=39),
            sentiment="positive",
            topic="colours",
        ),
    )


# ---------------------------------------------------------------- comments


async def test_get_post_comments_filters_and_reports_what_isnt_analysed(
    shop: Shop, feed: Feed
) -> None:
    negative = await shop.call(
        "get_post_comments", {"post_id": str(feed.reel), "sentiment": "negative"}
    )
    assert [i.id for i in negative.items] == [feed.shipping, feed.pricey]  # newest first
    assert (negative.total, negative.in_scope, negative.pending) == (2, 5, 1)
    assert negative.summary == f"Found 2 negative comments on the {feed.reel_label}"
    assert negative.caveats == [
        "1 of 5 comments are still being analysed, so they aren't in these results."
    ]
    assert [(r.kind, r.id) for r in negative.refs] == [
        ("post", feed.reel),
        ("comment", feed.shipping),
        ("comment", feed.pricey),
    ]
    assert negative.refs[2].label == "“Too expensive for me”"
    assert negative.items[1].topic == "price"

    price = await shop.call("get_post_comments", {"post_id": str(feed.reel), "topic": "Price"})
    assert [i.id for i in price.items] == [feed.pricey]
    spam = await shop.call("get_post_comments", {"post_id": str(feed.reel), "spam": "only"})
    assert [i.id for i in spam.items] == [feed.spam]
    asking = await shop.call(
        "get_post_comments", {"post_id": str(feed.reel), "intents": ["pricing"]}
    )
    assert [i.id for i in asking.items] == [feed.pricey]

    everything = await shop.call("get_post_comments", {"post_id": str(feed.reel), "limit": 2})
    assert (everything.total, len(everything.items), everything.more) == (4, 2, 2)
    assert [i.analysis for i in everything.items] == ["pending", "done"]
    assert everything.caveats == ["1 of 5 comments are still being analysed."]
    unreplied = await shop.call("get_post_comments", {"post_id": str(feed.reel), "replied": False})
    assert unreplied.total == 4

    # Without a post: every post's comments of the last 30 days (the 39-day-old one is out).
    month = await shop.call("get_post_comments", {})
    assert month.total == 4
    assert month.period is not None
    assert feed.old_comment not in {i.id for i in month.items}
    older = await shop.call("get_post_comments", {"range": "the last 60 days"})
    assert older.total == 5


async def test_search_comments(shop: Shop, feed: Feed) -> None:
    found = await shop.call("search_comments", {"q": "expensive"})
    assert [i.id for i in found.items] == [feed.pricey]
    assert found.summary.startswith("Found 1 comment mentioning “expensive”")
    assert (await shop.call("search_comments", {"q": "restock"})).items[0].id == feed.restock
    none = await shop.call("search_comments", {"q": "lovely", "range": "this week"})
    assert none.total == 0


async def test_prepare_comment_reply_opens_the_reply_box_filled_in(shop: Shop, feed: Feed) -> None:
    public = await shop.call(
        "prepare_comment_reply",
        {"comment_id": str(feed.pricey), "text": "We have a sale this week!"},
    )
    card = public.action_card
    assert (card.kind, card.label) == ("reply_to_comment", "Reply to this comment")
    assert card.route == f"comments/{feed.reel}?comment={feed.pricey}&reply=public"
    assert card.prefill == CommentReplyPrefill(
        comment_id=feed.pricey, post_id=feed.reel, text="We have a sale this week!", private=False
    )
    assert [(r.kind, r.id, r.parent_id) for r in public.refs] == [
        ("comment", feed.pricey, feed.reel),  # a comment cites its post as its parent
        ("post", feed.reel, None),
    ]

    private = await shop.call(
        "prepare_comment_reply",
        {"comment_id": str(feed.pricey), "text": "Here's a discount code", "private": True},
    )
    assert private.action_card.route.endswith("&reply=private")
    assert private.action_card.prefill.private
    assert private.private_reply_until is not None
    assert private.action_card.note is not None
    assert private.action_card.note.startswith(
        "Instagram allows one private reply per comment, until"
    )
    assert await shop.rows("SELECT id FROM messages") == []  # nothing sent or queued


async def test_prepare_comment_reply_keeps_instagrams_limits(shop: Shop, feed: Feed) -> None:
    too_old = await refused(
        shop,
        "prepare_comment_reply",
        {"comment_id": str(feed.old_comment), "text": "Thanks!", "private": True},
    )
    assert (too_old.code, too_old.detail) == (
        "conflict",
        "Instagram only allows a private reply within 7 days of the comment.",
    )
    public = await shop.call(
        "prepare_comment_reply", {"comment_id": str(feed.old_comment), "text": "Thanks!"}
    )
    assert not public.private
    long = await refused(
        shop,
        "prepare_comment_reply",
        {"comment_id": str(feed.pricey), "text": "é" * 600, "private": True},
    )
    assert long.code == "validation_error"
    await shop.execute("UPDATE comments SET deleted_at = now() WHERE id = :id", id=feed.love)
    deleted = await refused(
        shop, "prepare_comment_reply", {"comment_id": str(feed.love), "text": "Thanks!"}
    )
    assert (deleted.code, deleted.detail) == ("conflict", "This comment was deleted.")


# ---------------------------------------------------------------- posts


async def test_get_posts_latest_post_and_search(shop: Shop, feed: Feed) -> None:
    posts = await shop.call("get_posts", {})
    assert [p.id for p in posts.items] == [feed.reel, feed.image, feed.old]  # stories left out
    first = posts.items[0]
    assert (first.format, first.age, first.label) == ("reel", "26 hours", feed.reel_label)
    assert (first.comment_stats.total, posts.refs[0].label) == (0, feed.reel_label)
    capped = await shop.call("get_posts", {"limit": 1})
    assert (capped.total, len(capped.items), capped.more) == (3, 1, 2)
    week = await shop.call("get_posts", {"range": "the last 7 days"})
    assert [p.id for p in week.items] == [feed.reel, feed.image]
    assert (await shop.call("get_posts", {"format": "story"})).total == 1
    assert (await shop.call("get_posts", {"format": "reel"})).total == 1

    latest = await shop.call("get_latest_post", {"account": "@maple.bakery"})
    assert latest.post is not None
    assert latest.post.id == feed.reel
    assert latest.summary == f"Your latest post is the {feed.reel_label}, published 26 hours ago"
    assert latest.refs[0].id == feed.reel
    feed_posts = await shop.call("get_latest_post", {"format": "feed"})
    assert feed_posts.post is not None
    assert feed_posts.post.id == feed.image

    diwali = await shop.call("search_posts", {"q": "diwali"})
    assert [p.id for p in diwali.items] == [feed.image]

    facebook = await shop.call("get_posts", {"platform": "facebook"})
    assert (facebook.total, facebook.caveats[0][:26]) == (0, "Facebook isn't connected: ")
    missing = await refused(shop, "get_posts", {"account": "@nobody"})
    assert missing.code == "not_found"


async def test_no_posts_yet_is_said_not_guessed(shop: Shop) -> None:
    latest = await shop.call("get_latest_post", {})
    assert latest.post is None
    assert latest.caveats == ["No posts have synced from Instagram yet."]


# ---------------------------------------------------------------- analytics


@dataclass
class History:
    reel: uuid.UUID
    label: str
    baseline: list[uuid.UUID]


@pytest.fixture
async def history(shop: Shop, feed: Feed) -> History:
    """The feed's reel at 24 hours (reach 4,120) and three earlier reels (2,800-3,000)."""
    now = datetime.now(UTC)
    on = {"workspace_id": shop.wid, "account_id": shop.account_id}
    reel_posted = now - timedelta(hours=26)
    await shop.execute(
        "UPDATE media_items SET posted_at = :at WHERE id = :id", at=reel_posted, id=feed.reel
    )
    await make_windows(
        shop.engine,
        workspace_id=shop.wid,
        post_id=feed.reel,
        posted_at=reel_posted,
        windows={"1h": {"likes": 40, "comments": 5}, "24h": figures(4120)},
    )
    baseline = []
    for days, reach in ((3, 2800), (4, 2900), (5, 3000)):
        posted = now - timedelta(days=days)
        post = await make_post(shop.engine, posted_at=posted, media_type="reel", **on)
        await make_windows(
            shop.engine,
            workspace_id=shop.wid,
            post_id=post,
            posted_at=posted,
            windows={"24h": figures(reach), "72h": figures(reach + 500)},
        )
        baseline.append(post)
    return History(feed.reel, feed.reel_label, baseline)


async def test_post_performance_at_an_age(shop: Shop, history: History) -> None:
    got = await shop.call(
        "post_performance", {"post_id": str(history.reel), "at_age": "after 24 hours"}
    )
    assert (got.age, got.requested_age, got.age_label) == ("24h", "24h", "24 hours")
    assert (got.metrics.reach, got.metrics.likes) == (4120, 300)
    assert got.metrics.engagement_rate == round((300 + 88 + 20 + 40) / 4120 * 100, 2)
    assert got.insights_granted
    assert got.caveats == []
    assert got.refs[0].id == history.reel
    assert got.summary == f"{history.label} at 24 hours: reach 4,120, likes 300"

    # 2 days is read at the nearest snapshot age (72 h), which the 26-hour-old reel hasn't
    # reached: it is shown at 24 hours, and both are said.
    younger = await shop.call(
        "post_performance", {"post_id": str(history.reel), "at_age": "2 days"}
    )
    assert (younger.requested_age, younger.age) == ("72h", "24h")
    assert younger.caveats == [
        "Figures are recorded at 1 h, 6 h, 24 h, 72 h, 7 d and 30 d, so 2 days is read at 72 "
        "hours.",
        "The post is younger than 72 hours, so its figures are at 24 hours, the latest age it "
        "has reached.",
    ]
    early = await shop.call("post_performance", {"post_id": str(history.reel), "at_age": "1h"})
    assert early.metrics.reach is None
    assert early.caveats[-1].startswith("At 1 and 6 hours only likes and comments")
    lifetime = await shop.call(
        "post_performance", {"post_id": str(history.reel), "at_age": "lifetime"}
    )
    assert (lifetime.age, lifetime.metrics.reach) == ("lifetime", 4120)
    bad = await refused(shop, "post_performance", {"post_id": str(history.reel), "at_age": "?"})
    assert bad.code == "validation_error"


async def test_compare_posts_at_the_same_age(shop: Shop, history: History) -> None:
    got = await shop.call("compare_posts", {"post_id": str(history.reel), "at_age": "24h"})
    assert got.enough_history
    assert (got.age, got.baseline.size, got.baseline.label) == ("24h", 3, "the previous 10 reels")
    reach = next(m for m in got.metrics if m.metric == "reach")
    assert (reach.value, reach.baseline_median, reach.diff_pct, reach.sample_size) == (
        4120,
        2900,
        42.1,
        3,
    )
    assert got.summary == (
        f"Compared the {history.label} with the previous 10 reels at 24 hours: reach +42.1% "
        "against the median"
    )
    assert got.caveats == []

    two = await shop.call("compare_posts", {"post_id": str(history.reel), "n": 2})
    assert (two.baseline.size, two.enough_history) == (2, False)
    assert two.caveats == [
        "Only 2 comparable posts at 24 hours; at least 3 are needed, so there isn't enough "
        "history to compare."
    ]
    assert two.summary.endswith(": not enough history")

    ranged = await shop.call(
        "compare_posts",
        {"post_id": str(history.reel), "baseline": "range", "range": "the last 30 days"},
    )
    assert ranged.baseline.size == 3
    assert ranged.baseline.label.startswith("reels published ")


async def test_top_posts_and_accounts_without_insights(shop: Shop, history: History) -> None:
    top = await shop.call("top_posts", {"metric": "reach", "at_age": "24 hours", "n": 2})
    assert top.considered == 4
    assert [i.post_id for i in top.items] == [history.reel, history.baseline[2]]
    assert [i.value for i in top.items] == [4120, 3000]
    assert top.days is not None
    assert top.caveats == []
    assert [r.id for r in top.refs] == [i.post_id for i in top.items]

    # A second account without the insights permission: likes and comments only, said so.
    bare = await make_instagram_account(
        shop.engine, shop.wid, insights=False, platform_account_id="17841400000000099"
    )
    posted = datetime.now(UTC) - timedelta(days=2)
    post = await make_post(shop.engine, workspace_id=shop.wid, account_id=bare, posted_at=posted)
    await make_windows(
        shop.engine,
        workspace_id=shop.wid,
        post_id=post,
        posted_at=posted,
        windows={"24h": {"likes": 12, "comments": 3}},
    )
    got = await shop.call("post_performance", {"post_id": str(post), "at_age": "24h"})
    assert not got.insights_granted
    assert (got.metrics.likes, got.metrics.reach) == (12, None)
    assert got.caveats[0].startswith("Insights aren't granted for @maple.bakery")
    ranked = await shop.call("top_posts", {"metric": "reach"})
    assert any(c.startswith("Insights aren't granted") for c in ranked.caveats)


async def test_sentiment_distribution_counts_what_is_analysed(shop: Shop, feed: Feed) -> None:
    got = await shop.call("sentiment_distribution", {"post_id": str(feed.reel)})
    assert (got.total, got.analysed, got.not_analysed) == (5, 4, 1)
    assert (got.positive, got.neutral, got.negative, got.spam) == (1, 0, 2, 1)
    assert (got.positive_pct, got.negative_pct, got.positive_share) == (33.3, 66.7, 0.333)
    assert got.scope == f"comments on the {feed.reel_label}"
    assert got.caveats == [
        "1 of 5 comments aren't analysed yet (still being analysed, or analysis is off), so "
        "they aren't in the percentages."
    ]
    assert got.refs[0].id == feed.reel
    month = await shop.call("sentiment_distribution", {"range": "the last 30 days"})
    assert (month.total, month.positive) == (5, 1)
    assert month.days is not None
    assert month.scope == f"comments made {month.days.label}"
    empty = await shop.call("sentiment_distribution", {"range": "between 1 and 15 Jan 2020"})
    assert empty.caveats == ["There are no comments made 1-15 Jan 2020."]


async def test_comment_topics_with_examples(shop: Shop, feed: Feed) -> None:
    got = await shop.call("comment_topics", {"post_id": str(feed.reel)})
    assert [(t.label, t.count) for t in got.topics] == [
        ("colours", 1),
        ("price", 1),
        ("shipping cost", 1),
    ]
    assert (got.topic_count, got.analysed, got.total, got.pending) == (3, 3, 5, 1)
    assert got.topics[1].examples[0].comment_id == feed.pricey
    assert {r.id for r in got.refs} == {feed.reel, feed.love, feed.pricey, feed.shipping}
    assert {r.parent_id for r in got.refs if r.kind == "comment"} == {feed.reel}
    assert got.caveats == ["1 of 5 comments are still being analysed, so they aren't counted."]

    negative = await shop.call(
        "comment_topics", {"post_id": str(feed.reel), "sentiment": "negative", "n": 1}
    )
    assert [(t.label, t.negative) for t in negative.topics] == [("price", 1)]
    assert (negative.topic_count, negative.analysed) == (2, 2)
    assert "topics in 2 analysed negative comments" in negative.summary


# ---------------------------------------------------------------- tenancy


async def test_another_workspaces_posts_and_comments_never_resolve(
    shop: Shop, feed: Feed, other: Shop
) -> None:
    now = datetime.now(UTC)
    theirs = await make_post(
        other.engine, workspace_id=other.wid, account_id=other.account_id, posted_at=now
    )
    their_comment = await make_comment(
        other.engine,
        workspace_id=other.wid,
        account_id=other.account_id,
        media_item_id=theirs,
        text="Too expensive",
    )
    for name, args in [
        ("get_post_comments", {"post_id": str(theirs)}),
        ("search_comments", {"q": "expensive", "post_id": str(theirs)}),
        ("prepare_comment_reply", {"comment_id": str(their_comment), "text": "Hi"}),
        ("post_performance", {"post_id": str(theirs)}),
        ("compare_posts", {"post_id": str(theirs)}),
        ("sentiment_distribution", {"post_id": str(theirs)}),
        ("comment_topics", {"post_id": str(theirs)}),
    ]:
        error = await refused(shop, name, args)
        assert error.code == "not_found", name
    posts = await shop.call("get_posts", {})
    assert theirs not in {p.id for p in posts.items}
    found = await shop.call("search_comments", {"q": "expensive"})
    assert [i.id for i in found.items] == [feed.pricey]
    latest = await shop.call("get_latest_post", {})
    assert latest.post is not None
    assert latest.post.id == feed.reel
