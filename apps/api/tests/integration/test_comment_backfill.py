"""T6.1 and F-12: comments are stored from webhooks and from a backfill on connect (FR-CMT-01: the
25 most recent posts, up to 200 comments each), both through the same intake. Done when: a
replayed comment event stores nothing new. Plus: no automation runs on a backfilled comment, the
account's own comments are skipped, a second backfill stores nothing, the post counts and events
(TR-RT-03), and Instagram's pages read through the Graph API."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.models.platform import WebhookStatus
from socialhood.platforms.base import CommentPage, PlatformComment
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.sandbox import comments as sandbox_comments
from socialhood.security.crypto import TokenCipher
from socialhood.settings import Settings
from tests.support.api import TOKEN_KEY
from tests.support.automations import make_automation
from tests.support.comments import Comments
from tests.support.ingest import deliver, jobs, replay_all, sessions, stream
from tests.support.instagram import GRAPH, fixture
from tests.support.runtime import make_world, platform_deps
from tests.support.sending import clean_outbox

IG_ACCOUNT = "17841400000000001"


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


def sandbox_comment(account_ref: str, comment_id: str, **value: Any) -> dict[str, Any]:
    change = {
        "id": comment_id,
        "text": "Is this in stock?",
        "from": {"id": "990000000000002", "username": "curious.cat"},
        "media": {"id": f"{account_ref}_post_0", "media_product_type": "FEED"},
        **value,
    }
    return {
        "object": "instagram",
        "entry": [
            {
                "id": account_ref,
                "time": int(datetime.now(UTC).timestamp()),
                "changes": [{"field": "comments", "value": change}],
            }
        ],
    }


async def mark_jobs_done() -> None:
    from socialhood.jobs.app import app as jobs_app

    await jobs_app.connector.execute_query_async(
        "UPDATE procrastinate_jobs SET status = 'succeeded' WHERE status = 'todo'"
    )


# ---------------------------------------------------------------- webhooks (F-12)


async def test_a_replayed_comment_event_stores_nothing_new(cw: Comments) -> None:
    ref = await cw.account_ref()
    maker = sessions(cw.world.engine)
    body = sandbox_comment(ref, "18000000000000091")

    assert await deliver(maker, cw.world.redis, body) == [WebhookStatus.PROCESSED]
    [comment] = await cw.rows("SELECT * FROM comments")
    events = await stream(cw.world.redis, cw.wid)
    assert [kind for kind, _ in events] == ["comment.created", "post.updated"]
    created, post = events[0][1], events[1][1]
    assert (created["comment"]["id"], created["comment"]["analysis_status"]) == (
        str(comment["id"]),
        "pending",
    )
    assert created["comment"]["author_username"] == "curious.cat"
    assert post["post"]["id"] == str(comment["media_item_id"])
    assert post["post"]["stats"]["total"] == 1  # the card counts it at once
    await cw.world.redis.delete(f"events:{cw.wid}")

    # Replayed (TR-OPS-04) and delivered again: nothing new is stored, counted or published.
    assert await replay_all(cw.world.engine, maker, cw.world.redis) == [WebhookStatus.IGNORED]
    assert await deliver(maker, cw.world.redis, body, copy="again") == [WebhookStatus.IGNORED]
    assert len(await cw.rows("SELECT id FROM comments")) == 1
    assert (await cw.stats(comment["media_item_id"]))["total"] == 1
    assert await stream(cw.world.redis, cw.wid) == []

    # The backfill reading the same comment from Instagram stores nothing either.
    sandbox_comments.seed(
        f"{ref}_post_0",
        [
            PlatformComment(
                account_ref=ref,
                occurred_at=datetime.now(UTC),
                platform_comment_id="18000000000000091",
                media_id=f"{ref}_post_0",
                parent_id=None,
                author_ref="990000000000002",
                author_username="curious.cat",
                text="Is this in stock?",
            )
        ],
    )
    await cw.sync()
    result = await cw.backfill()
    assert result is not None
    assert result.stored == 3  # only the other posts' 2 + 1 are new
    on_post = await cw.rows(
        "SELECT platform_comment_id FROM comments WHERE media_item_id = :m",
        m=comment["media_item_id"],
    )
    assert on_post == [{"platform_comment_id": "18000000000000091"}]


# ---------------------------------------------------------------- the backfill (FR-CMT-01)


async def test_connecting_backfills_the_recent_posts_comments_once(cw: Comments) -> None:
    await make_automation(
        cw.world.engine,
        workspace_id=cw.wid,
        account_id=cw.account_id,
        trigger="comment_any",
        keywords=(),
        public_reply_texts=["Thanks!"],
    )
    ref = await cw.account_ref()

    assert await cw.sync() == 3  # sync_media on connect stores the posts ...
    [job] = await jobs("backfill_comments")  # ... and queues the backfill for their comments
    assert job["queueing_lock"] == f"cmtbackfill:{cw.account_id}"
    assert job["args"] == {"workspace_id": str(cw.wid), "account_id": str(cw.account_id)}

    result = await cw.backfill()

    assert result is not None
    assert (result.posts, result.stored) == (3, 6)  # 3 + 2 + 1
    rows = await cw.rows(
        "SELECT c.*, m.platform_media_id FROM comments c"
        " JOIN media_items m ON m.id = c.media_item_id ORDER BY c.platform_comment_id"
    )
    assert [r["platform_comment_id"] for r in rows] == [
        f"{ref}_post_0_comment_0",
        f"{ref}_post_0_comment_1",
        f"{ref}_post_0_comment_2",
        f"{ref}_post_1_comment_0",
        f"{ref}_post_1_comment_1",
        f"{ref}_post_2_comment_0",
    ]
    assert {r["analysis_status"] for r in rows} == {"pending"}
    first = rows[1]
    assert (first["author_username"], first["like_count"], first["text"]) == (
        "price.asker",
        1,
        "How much is this one?",
    )
    contact = await cw.one("SELECT * FROM contacts WHERE id = :id", id=first["contact_id"])
    assert (contact["platform_user_id"], contact["username"]) == (
        "sandbox_commenter_1",
        "price.asker",
    )
    # No automation runs on a backfilled comment, although one matches any comment.
    assert await jobs("run_automation") == []
    assert await cw.rows("SELECT id FROM automation_runs") == []
    # Each post is counted once and published once, with no per-comment events.
    posts = await cw.rows(
        "SELECT id, platform_media_id, comment_stats FROM media_items ORDER BY platform_media_id"
    )
    assert [p["comment_stats"]["total"] for p in posts] == [3, 2, 1]
    assert [p["comment_stats"]["analysed"] for p in posts] == [0, 0, 0]
    events = await stream(cw.world.redis, cw.wid)
    assert sorted(kind for kind, _ in events) == ["post.updated"] * 3

    # Running it again stores nothing new.
    again = await cw.backfill()
    assert again is not None
    assert again.stored == 0
    assert len(await cw.rows("SELECT id FROM comments")) == 6

    # The next sync finds nothing missing, so no backfill is queued.
    await mark_jobs_done()
    await cw.sync()
    assert [j for j in await jobs("backfill_comments")] == [job]


async def test_the_backfill_reads_up_to_200_comments_per_post_and_skips_the_account_s_own(
    cw: Comments, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref = await cw.account_ref()
    media_ref = f"{ref}_post_2"
    at = datetime.now(UTC) - timedelta(days=4)

    def comment(i: int, **values: Any) -> PlatformComment:
        defaults: dict[str, Any] = {
            "account_ref": ref,
            "occurred_at": at + timedelta(minutes=i),
            "platform_comment_id": f"1790000000{i:07d}",
            "media_id": media_ref,
            "parent_id": None,
            "author_ref": f"99{i:013d}",
            "author_username": f"fan{i}",
            "text": f"comment {i}",
        }
        return PlatformComment(**{**defaults, **values})

    seeded = [
        comment(0, author_ref="17841499999999999", author_username="maple.bakery"),  # own
        comment(1, like_count=7, hidden=True),
        comment(2, parent_id="17900000000000001"),
        *[comment(i) for i in range(3, 260)],
    ]
    sandbox_comments.seed(media_ref, seeded)
    pages: list[str | None] = []
    real_page = sandbox_comments.page

    def spy(acct: Any, ref_: str, *, cursor: str | None) -> CommentPage:
        if ref_ == media_ref:
            pages.append(cursor)
        return real_page(acct, ref_, cursor=cursor)

    monkeypatch.setattr(sandbox_comments, "page", spy)
    await cw.sync()
    await cw.backfill()

    assert pages == [None, "50", "100", "150"]  # 200 read, page by page
    stored = await cw.rows(
        "SELECT c.* FROM comments c JOIN media_items m ON m.id = c.media_item_id"
        " WHERE m.platform_media_id = :m ORDER BY c.platform_comment_id",
        m=media_ref,
    )
    assert len(stored) == 199  # the account's own comment is skipped
    assert stored[0]["platform_comment_id"] == "17900000000000001"
    assert (stored[0]["like_count"], stored[0]["hidden"]) == (7, True)
    assert stored[1]["parent_platform_comment_id"] == "17900000000000001"
    assert stored[-1]["platform_comment_id"] == "17900000000000199"


async def test_the_backfill_reads_instagram_page_by_page(cw: Comments) -> None:
    from tests.support.inbox import make_account

    account = await make_account(cw.world.engine, cw.wid, platform_account_id=IG_ACCOUNT)
    await cw.execute(
        "UPDATE social_accounts SET access_token_enc = :t WHERE id = :id",
        t=TokenCipher([TOKEN_KEY]).encrypt("IGQVJbackfill"),
        id=account,
    )
    cw.world.account_id = account
    post = await cw.post(platform_media_id="18100000000000003")
    other = await cw.post(platform_media_id="18100000000000002")
    await cw.execute("UPDATE media_items SET comments_count = 6 WHERE id = :id", id=post)
    await cw.execute("UPDATE media_items SET comments_count = 0 WHERE id = :id", id=other)

    def comments(request: httpx.Request) -> httpx.Response:
        name = "media_comments_page2.json" if "after" in request.url.params else "page1"
        if name == "page1":
            name = "media_comments_page1.json"
        return httpx.Response(200, json=fixture(name))

    with respx.mock(assert_all_called=False) as router:
        route = router.get(url__regex=rf"{GRAPH}/v[\d.]+/18100000000000003/comments").mock(
            side_effect=comments
        )
        result = await cw.backfill()

    assert route.call_count == 2
    assert result is not None
    assert (result.posts, result.stored) == (1, 4)  # the other has none
    rows = await cw.rows("SELECT * FROM comments ORDER BY platform_comment_id")
    assert [r["platform_comment_id"] for r in rows] == [
        "17900000000000001",
        "17900000000000003",  # the account's own reply (…002) is skipped
        "17900000000000004",
        "17900000000000006",
    ]
    assert rows[1]["parent_platform_comment_id"] == "17900000000000001"
    assert rows[2]["hidden"] is True
    assert (await cw.stats(post))["total"] == 4


async def test_a_post_instagram_refuses_is_skipped_and_a_temporary_error_retries(
    cw: Comments,
) -> None:
    from tests.support.inbox import make_account

    account = await make_account(cw.world.engine, cw.wid, platform_account_id=IG_ACCOUNT)
    await cw.execute(
        "UPDATE social_accounts SET access_token_enc = :t WHERE id = :id",
        t=TokenCipher([TOKEN_KEY]).encrypt("IGQVJbackfill"),
        id=account,
    )
    cw.world.account_id = account
    now = datetime.now(UTC)
    await cw.post(platform_media_id="18100000000000003", posted_at=now - timedelta(days=1))
    await cw.post(platform_media_id="18100000000000002", posted_at=now - timedelta(days=2))

    with respx.mock(assert_all_called=False) as router:
        router.get(url__regex=rf"{GRAPH}/v[\d.]+/18100000000000003/comments").respond(
            400, json={"error": {"code": 100, "message": "Unsupported get request"}}
        )
        router.get(url__regex=rf"{GRAPH}/v[\d.]+/18100000000000002/comments").respond(
            200, json=fixture("media_comments_page2.json")
        )
        result = await cw.backfill()
    assert result is not None
    assert (result.posts, result.stored) == (1, 1)

    with respx.mock(assert_all_called=False) as router:
        router.get(url__regex=rf"{GRAPH}/v[\d.]+/18100000000000003/comments").respond(
            500, json={"error": {"code": 2, "message": "Service temporarily unavailable"}}
        )
        with pytest.raises(PlatformError) as down:
            await cw.backfill()
    assert down.value.retryable  # the job's PlatformRetry tries again


async def test_accounts_without_comments_are_not_backfilled(cw: Comments) -> None:
    await cw.execute(
        "UPDATE social_accounts SET status = 'needs_reconnect' WHERE id = :id", id=cw.account_id
    )
    assert await cw.backfill() is None
    cw.world.account_id = uuid.uuid4()  # unknown
    assert await cw.backfill() is None
