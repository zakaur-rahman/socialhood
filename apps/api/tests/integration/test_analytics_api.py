"""T6.5 (FR-ANL-02, TR-AGT-05; agent-architecture §6 and §11): the analytics routes over seeded
snapshots: a post's figures at an age, the comparison with its account's earlier posts at the same
age (previous N or a range, same format by default, not enough history below 3), the sentiment
distribution and the top posts; ages, windows, formats, time zones and tenancy."""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import time_machine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.analytics import make_comment_analysis
from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace
from tests.support.automations import make_comment
from tests.support.inbox import make_account, make_workspace
from tests.support.post_metrics import make_instagram_account, make_post, make_windows, set_timezone

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def figures(
    reach: int | None = None,
    likes: int = 100,
    comments: int = 10,
    shares: int = 5,
    saves: int = 25,
    views: int | None = None,
) -> dict[str, int]:
    """Snapshot metrics; without reach, a live-counts-only snapshot (likes and comments)."""
    if reach is None:
        return {"likes": likes, "comments": comments}
    return {
        "reach": reach,
        "views": views if views is not None else reach * 2,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": saves,
    }


@pytest.fixture
def clock() -> Iterator[None]:
    with time_machine.travel(NOW, tick=True):
        yield


@dataclass
class Shop:
    ws: Ws
    engine: AsyncEngine

    @property
    def wid(self) -> str:
        return self.ws.wid

    @property
    def account(self) -> str:
        return self.ws.account_id

    async def post(
        self,
        age: timedelta,
        windows: Mapping[str, Mapping[str, int]] | None = None,
        *,
        media_type: str = "image",
        account: str | None = None,
        **values: Any,
    ) -> str:
        """A post published ``age`` ago with its snapshots (window -> metrics)."""
        posted_at = NOW - age
        post = await make_post(
            self.engine,
            workspace_id=self.wid,
            account_id=account or self.account,
            posted_at=posted_at,
            media_type=media_type,
            **values,
        )
        await make_windows(
            self.engine,
            workspace_id=self.wid,
            post_id=post,
            posted_at=posted_at,
            windows=windows or {},
        )
        return str(post)

    async def get(self, path: str, status: int = 200, **params: Any) -> Any:
        response = await self.ws.call("GET", f"/analytics{path}", params=params)
        assert response.status_code == status, response.text
        return response.json()


@pytest.fixture
async def shop(clock: None, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Shop:
    return Shop(await workspace(client, clerk), engine)


def by_metric(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {m["metric"]: m for m in body["metrics"]}


# ---------------------------------------------------------------- performance


async def test_a_posts_figures_at_an_age(shop: Shop) -> None:
    post = await shop.post(
        timedelta(days=5),
        {
            "1h": figures(likes=20, comments=2),
            "6h": figures(likes=60, comments=6),
            "24h": figures(reach=2000, likes=100, comments=10, shares=5, saves=25),
            "72h": figures(reach=2600, likes=130, comments=12, shares=8, saves=30),
        },
    )
    body = await shop.get(f"/posts/{post}/performance", age="24h")
    assert (body["requested_age"], body["age"]) == ("24h", "24h")
    assert body["metrics"] == {
        "reach": 2000,
        "views": 4000,
        "likes": 100,
        "comments": 10,
        "shares": 5,
        "saves": 25,
        "engagement_rate": 7.0,  # (100 + 10 + 5 + 25) / 2000
    }
    assert datetime.fromisoformat(body["captured_at"]) == NOW - timedelta(days=4)
    assert (body["insights_granted"], body["insights_final"]) == (True, True)
    assert body["media_type"] == "image"

    latest = await shop.get(f"/posts/{post}/performance")
    assert (latest["requested_age"], latest["age"]) == (None, "72h")  # 7 d not reached yet
    assert latest["metrics"]["reach"] == 2600


async def test_live_count_windows_have_no_reach_or_rate(shop: Shop) -> None:
    post = await shop.post(timedelta(hours=3), {"1h": figures(likes=20, comments=2)})
    body = await shop.get(f"/posts/{post}/performance", age="1h")
    assert body["metrics"] == {
        "reach": None,
        "views": None,
        "likes": 20,
        "comments": 2,
        "shares": None,
        "saves": None,
        "engagement_rate": None,
    }


async def test_a_younger_post_is_shown_at_its_current_age(shop: Shop) -> None:
    post = await shop.post(
        timedelta(days=2), {"1h": figures(), "6h": figures(), "24h": figures(reach=900)}
    )
    body = await shop.get(f"/posts/{post}/performance", age="7d")
    assert (body["requested_age"], body["age"]) == ("7d", "24h")
    assert body["metrics"]["reach"] == 900


async def test_a_post_without_that_window_uses_the_closest_snapshot(shop: Shop) -> None:
    """Published before the account was connected: only 7 d and 30 d were captured."""
    post = await shop.post(
        timedelta(days=40), {"7d": figures(reach=5000), "30d": figures(reach=7000)}
    )
    body = await shop.get(f"/posts/{post}/performance", age="24h")
    assert (body["requested_age"], body["age"], body["metrics"]["reach"]) == ("24h", "7d", 5000)


async def test_lifetime_is_the_latest_known_values(shop: Shop) -> None:
    measured = await shop.post(
        timedelta(days=10), {"24h": figures(reach=1000), "7d": figures(reach=4000)}
    )
    body = await shop.get(f"/posts/{measured}/performance", age="lifetime")
    assert (body["age"], body["metrics"]["reach"]) == ("lifetime", 4000)

    never = await shop.post(timedelta(days=90), like_count=57, comments_count=4)
    old = await shop.get(f"/posts/{never}/performance", age="lifetime")
    assert (old["age"], old["captured_at"]) == ("lifetime", None)
    assert (old["metrics"]["likes"], old["metrics"]["comments"], old["metrics"]["reach"]) == (
        57,
        4,
        None,
    )


async def test_a_brand_new_post_has_no_figures_yet(shop: Shop) -> None:
    post = await shop.post(timedelta(minutes=20))
    body = await shop.get(f"/posts/{post}/performance")
    assert (body["age"], body["captured_at"], body["insights_final"]) == ("1h", None, False)
    assert set(body["metrics"].values()) == {None}


async def test_an_account_without_insights_says_so(shop: Shop) -> None:
    account = await make_instagram_account(shop.engine, shop.wid, insights=False)
    post = await shop.post(
        timedelta(days=2), {"24h": figures(likes=40, comments=3)}, account=str(account)
    )
    body = await shop.get(f"/posts/{post}/performance", age="24h")
    assert body["insights_granted"] is False
    assert (body["metrics"]["likes"], body["metrics"]["reach"]) == (40, None)


async def test_an_unknown_post_or_age_is_refused(shop: Shop) -> None:
    await shop.get(f"/posts/{uuid.uuid4()}/performance", 404)
    post = await shop.post(timedelta(days=2))
    await shop.get(f"/posts/{post}/performance", 422, age="2h")


# ---------------------------------------------------------------- comparison


async def previous_posts(shop: Shop, reaches: list[int], *, media_type: str = "image") -> list[str]:
    """Posts published 10, 11, … days ago with 24 h and 72 h snapshots; newest first."""
    posts = []
    for i, reach in enumerate(reaches):
        posts.append(
            await shop.post(
                timedelta(days=10 + i),
                {"24h": figures(reach=reach), "72h": figures(reach=reach * 2)},
                media_type=media_type,
            )
        )
    return posts


async def test_a_post_against_its_previous_posts_at_the_same_age(shop: Shop) -> None:
    earlier = await previous_posts(shop, [1000, 2000, 2000, 3000, 4000])
    await previous_posts(shop, [90000], media_type="reel")  # another format: left out
    post = await shop.post(timedelta(days=5), {"24h": figures(reach=3000, likes=100)})

    body = await shop.get(f"/posts/{post}/compare", age="24h", n=10)
    assert body["age"] == "24h"
    assert body["baseline"] == {
        "kind": "previous",
        "n": 10,
        "since": None,
        "until": None,
        "same_format": True,
        "post_ids": earlier,
    }
    assert (body["baseline_size"], body["enough_history"]) == (5, True)
    reach = by_metric(body)["reach"]
    assert reach["value"] == 3000
    assert (reach["baseline_median"], reach["baseline_mean"], reach["sample_size"]) == (
        2000,
        2400,
        5,
    )
    assert reach["diff_pct"] == 50.0
    assert reach["z_score"] == pytest.approx(0.53, abs=0.005)  # (3000 - 2400) / 1140
    rate = by_metric(body)["engagement_rate"]
    assert rate["value"] == pytest.approx(140 / 3000 * 100, abs=0.01)
    assert rate["sample_size"] == 5
    assert [m["metric"] for m in body["metrics"]] == [
        "reach",
        "views",
        "likes",
        "comments",
        "shares",
        "saves",
        "engagement_rate",
    ]

    everything = await shop.get(f"/posts/{post}/compare", age="24h", same_format="false")
    assert everything["baseline_size"] == 6


async def test_the_previous_n_posts_are_the_newest_before_this_one(shop: Shop) -> None:
    earlier = await previous_posts(shop, [1000, 2000, 3000, 4000, 5000])
    post = await shop.post(timedelta(days=5), {"24h": figures(reach=3000)})
    await shop.post(timedelta(days=1), {"24h": figures(reach=99999)})  # later: never a baseline
    body = await shop.get(f"/posts/{post}/compare", age="24h", n=3)
    assert body["baseline"]["post_ids"] == earlier[:3]
    assert by_metric(body)["reach"]["baseline_median"] == 2000


async def test_too_little_history_draws_no_conclusion(shop: Shop) -> None:
    await previous_posts(shop, [1000, 2000])
    post = await shop.post(timedelta(days=5), {"24h": figures(reach=3000)})
    body = await shop.get(f"/posts/{post}/compare", age="24h")
    assert (body["baseline_size"], body["enough_history"]) == (2, False)
    reach = by_metric(body)["reach"]
    assert (reach["baseline_median"], reach["sample_size"]) == (1500, 2)
    assert (reach["diff_pct"], reach["z_score"]) == (None, None)


async def test_posts_join_the_baseline_only_at_ages_they_have(shop: Shop) -> None:
    """Posts published before the account was connected have no 24 h snapshot."""
    with_24h = await previous_posts(shop, [1000, 2000])
    for i in range(3):
        await shop.post(timedelta(days=20 + i), {"7d": figures(reach=8000)})
    post = await shop.post(
        timedelta(days=9), {"24h": figures(reach=3000), "7d": figures(reach=9000)}
    )

    at_24h = await shop.get(f"/posts/{post}/compare", age="24h")
    assert at_24h["baseline"]["post_ids"] == with_24h
    assert (at_24h["baseline_size"], at_24h["enough_history"]) == (2, False)
    at_7d = await shop.get(f"/posts/{post}/compare", age="7d")
    assert (at_7d["baseline_size"], at_7d["enough_history"]) == (3, True)
    assert by_metric(at_7d)["reach"]["diff_pct"] == 12.5


async def test_a_younger_post_is_compared_at_its_current_age(shop: Shop) -> None:
    await previous_posts(shop, [1000, 2000, 3000])
    post = await shop.post(timedelta(days=2), {"24h": figures(reach=2500)})
    body = await shop.get(f"/posts/{post}/compare", age="7d")
    assert (body["post"]["requested_age"], body["age"]) == ("7d", "24h")
    assert by_metric(body)["reach"]["baseline_median"] == 2000  # the 24 h values, not 72 h


async def test_a_range_baseline_in_the_workspace_time_zone(shop: Shop, engine: AsyncEngine) -> None:
    await set_timezone(engine, shop.wid, "Asia/Kolkata")
    # 20 Sep 20:00 UTC is 21 Sep 01:30 in Kolkata.
    late = await shop.post(
        NOW - datetime(2026, 9, 20, 20, 0, tzinfo=UTC), {"24h": figures(reach=10)}
    )
    inside = [
        await shop.post(NOW - datetime(2026, 9, d, 9, 0, tzinfo=UTC), {"24h": figures(reach=r)})
        for d, r in ((21, 20), (22, 30))
    ]
    await shop.post(NOW - datetime(2026, 9, 23, 9, 0, tzinfo=UTC), {"24h": figures(reach=99)})
    post = await shop.post(
        NOW - datetime(2026, 9, 22, 12, 0, tzinfo=UTC), {"24h": figures(reach=40)}
    )

    body = await shop.get(
        f"/posts/{post}/compare", baseline="range", since="2026-09-21", until="2026-09-22"
    )
    assert body["baseline"]["post_ids"] == [inside[1], inside[0], late]
    assert (body["baseline"]["n"], body["baseline"]["since"], body["baseline"]["until"]) == (
        None,
        "2026-09-21",
        "2026-09-22",
    )
    assert by_metric(body)["reach"]["baseline_median"] == 20


async def test_a_comparison_request_is_checked(shop: Shop) -> None:
    post = await shop.post(timedelta(days=2))
    await shop.get(f"/posts/{post}/compare", 422, baseline="range", since="2026-09-01")
    await shop.get(
        f"/posts/{post}/compare", 422, baseline="range", since="2026-09-10", until="2026-09-01"
    )
    await shop.get(f"/posts/{post}/compare", 422, n=2)
    await shop.get(f"/posts/{uuid.uuid4()}/compare", 404)


# ---------------------------------------------------------------- sentiment


async def comment(
    shop: Shop,
    post: str,
    *,
    sentiment: str | None = None,
    spam: bool = False,
    at: datetime | None = None,
    account: str | None = None,
) -> uuid.UUID:
    made = await make_comment(
        shop.engine,
        workspace_id=shop.wid,
        account_id=account or shop.account,
        media_item_id=uuid.UUID(post),
        commented_at=at or NOW - timedelta(hours=2),
    )
    if sentiment is not None:
        await make_comment_analysis(
            shop.engine, workspace_id=shop.wid, comment_id=made, sentiment=sentiment, is_spam=spam
        )
    return made


async def test_sentiment_for_a_post(shop: Shop, engine: AsyncEngine) -> None:
    post = await shop.post(timedelta(days=1))
    other = await shop.post(timedelta(days=2))
    for sentiment in ("positive", "positive", "positive", "neutral", "negative"):
        await comment(shop, post, sentiment=sentiment)
    await comment(shop, post, sentiment="positive", spam=True)
    await comment(shop, post)  # not analysed yet
    await comment(shop, post)
    deleted = await comment(shop, post, sentiment="negative")
    await comment(shop, other, sentiment="negative")
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE comments SET deleted_at = now() WHERE id = :c"), {"c": deleted}
        )

    body = await shop.get("/sentiment", post_id=post, since="2026-01-01")
    assert body == {
        "post_id": post,
        "account_id": shop.account,
        "since": None,  # a post's comments, whenever they were made
        "until": None,
        "total": 8,
        "analysed": 6,
        "positive": 3,
        "neutral": 1,
        "negative": 1,
        "spam": 1,
        "positive_pct": 60.0,
        "neutral_pct": 20.0,
        "negative_pct": 20.0,
    }


async def test_sentiment_for_a_range_of_workspace_days(shop: Shop, engine: AsyncEngine) -> None:
    await set_timezone(engine, shop.wid, "Asia/Kolkata")
    second = await make_instagram_account(engine, shop.wid)
    post = await shop.post(timedelta(days=10))
    elsewhere = await shop.post(timedelta(days=10), account=str(second))
    day_start = datetime(2026, 9, 24, 18, 30, tzinfo=UTC)  # 25 Sep 00:00 in Kolkata
    await comment(shop, post, sentiment="positive", at=day_start - timedelta(minutes=1))
    await comment(shop, post, sentiment="negative", at=day_start)
    await comment(shop, post, sentiment="neutral", at=day_start + timedelta(hours=23, minutes=59))
    await comment(shop, post, at=day_start + timedelta(hours=12))
    await comment(
        shop,
        elsewhere,
        sentiment="positive",
        at=day_start + timedelta(hours=1),
        account=str(second),
    )

    body = await shop.get("/sentiment", since="2026-09-25", until="2026-09-25")
    assert (body["total"], body["analysed"], body["positive"], body["negative"]) == (4, 3, 1, 1)
    one = await shop.get(
        "/sentiment", since="2026-09-25", until="2026-09-25", account_id=shop.account
    )
    assert (one["account_id"], one["total"], one["positive"], one["neutral"]) == (
        shop.account,
        3,
        0,
        1,
    )
    assert (one["negative_pct"], one["neutral_pct"]) == (50.0, 50.0)

    default = await shop.get("/sentiment")
    assert (default["since"], default["until"]) == ("2026-08-31", "2026-09-29")
    assert default["total"] == 5
    await shop.get("/sentiment", 422, since="2026-09-26", until="2026-09-25")


async def test_no_analysed_comments_give_no_percentages(shop: Shop) -> None:
    post = await shop.post(timedelta(days=1))
    await comment(shop, post)
    body = await shop.get("/sentiment", post_id=post)
    assert (body["total"], body["analysed"], body["positive_pct"]) == (1, 0, None)


# ---------------------------------------------------------------- top posts


async def test_top_posts_by_a_metric_at_an_age(shop: Shop) -> None:
    best = await shop.post(
        timedelta(days=5), {"24h": figures(reach=5000), "72h": figures(reach=6000)}
    )
    second = await shop.post(
        timedelta(days=6), {"24h": figures(reach=3000), "72h": figures(reach=9000)}
    )
    await shop.post(timedelta(days=7), {"24h": figures(reach=1000)})
    await shop.post(timedelta(days=40), {"24h": figures(reach=99999)})  # outside the 30 days
    await shop.post(timedelta(days=8), {"7d": figures(reach=7000)})  # no 24 h snapshot
    young = await shop.post(
        timedelta(hours=12), {"1h": figures(likes=900), "6h": figures(likes=950)}
    )

    body = await shop.get("/top-posts", metric="reach", age="24h", n=2)
    assert (body["metric"], body["requested_age"], body["considered"]) == ("reach", "24h", 3)
    assert (body["since"], body["until"]) == ("2026-08-31", "2026-09-29")
    assert [(i["post"]["id"], i["value"], i["age"]) for i in body["items"]] == [
        (best, 5000, "24h"),
        (second, 3000, "24h"),
    ]
    assert body["items"][0]["post"]["stats"]["total"] == 0

    likes = await shop.get("/top-posts", metric="likes", age="24h", n=1)
    assert [(i["post"]["id"], i["age"]) for i in likes["items"]] == [(young, "6h")]  # younger
    lifetime = await shop.get("/top-posts", metric="reach", n=1)
    assert [(i["post"]["id"], i["value"], i["age"]) for i in lifetime["items"]] == [
        (second, 9000, "lifetime")
    ]
    rate = await shop.get("/top-posts", metric="engagement_rate", age="24h")
    assert rate["considered"] == 3
    assert rate["items"][0]["post"]["id"] not in (best, second)  # the smallest reach, 14 %


async def test_top_posts_of_one_account_and_range(shop: Shop, engine: AsyncEngine) -> None:
    await set_timezone(engine, shop.wid, "America/New_York")
    second = await make_instagram_account(engine, shop.wid)
    mine = await shop.post(
        NOW - datetime(2026, 9, 21, 3, 0, tzinfo=UTC), {"24h": figures(reach=100)}
    )  # 20 Sep 23:00 in New York
    await shop.post(
        NOW - datetime(2026, 9, 21, 5, 0, tzinfo=UTC), {"24h": figures(reach=200)}
    )  # 21 Sep 01:00
    await shop.post(timedelta(days=8), {"24h": figures(reach=300)}, account=str(second))
    body = await shop.get(
        "/top-posts", since="2026-09-20", until="2026-09-20", account_id=shop.account
    )
    assert [i["post"]["id"] for i in body["items"]] == [mine]
    everyone = await shop.get("/top-posts", age="24h")
    assert everyone["considered"] == 3
    await shop.get("/top-posts", 404, account_id=str(uuid.uuid4()))
    await shop.get("/top-posts", 422, metric="impressions")


# ---------------------------------------------------------------- tenancy


async def test_another_workspaces_posts_and_accounts_are_not_found(
    shop: Shop, engine: AsyncEngine
) -> None:
    """TR-TEN-03 for ids in the query string (the isolation suite covers path ids)."""
    other = await make_workspace(engine)
    their_account = await make_account(engine, other)
    their_post = await make_post(
        engine, workspace_id=other, account_id=their_account, posted_at=NOW - timedelta(days=3)
    )
    await make_windows(
        engine,
        workspace_id=other,
        post_id=their_post,
        posted_at=NOW - timedelta(days=3),
        windows={"24h": figures(reach=1)},
    )
    await make_comment(
        engine, workspace_id=other, account_id=their_account, media_item_id=their_post
    )
    await shop.post(timedelta(days=3), {"24h": figures(reach=2)})

    await shop.get(f"/posts/{their_post}/performance", 404)
    await shop.get(f"/posts/{their_post}/compare", 404)
    await shop.get("/sentiment", 404, post_id=str(their_post))
    await shop.get("/sentiment", 404, account_id=str(their_account))
    await shop.get("/top-posts", 404, account_id=str(their_account))
    # Workspace-wide reads count only this workspace's rows.
    assert (await shop.get("/sentiment"))["total"] == 0
    top = await shop.get("/top-posts", age="24h")
    assert top["considered"] == 1


async def test_members_of_other_workspaces_are_not_let_in(
    shop: Shop, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    post = await shop.post(timedelta(days=3))
    outsider = await workspace(client, clerk, email="someone@example.com")
    for path in (
        f"/posts/{post}/performance",
        f"/posts/{post}/compare",
        "/sentiment",
        "/top-posts",
    ):
        response = await client.get(f"/v1/w/{shop.wid}/analytics{path}", headers=outsider.headers)
        assert response.status_code == 404, path
