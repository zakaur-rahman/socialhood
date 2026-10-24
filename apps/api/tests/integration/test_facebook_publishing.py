"""GR-30 (C-115): publishing to Facebook Pages on sandbox Pages, and best posting times. The
composer's accounts may be Pages: a text post (no media, only Pages), photos, several photos, a
video, scheduled through our own scheduler and published by the same jobs as Instagram's; the
checklist speaks per platform; a lost publish answer is never retried on a Page; the best-times
route works out a weekday suggestion from the account's own posts."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.platforms.deps import deps_from
from socialhood.platforms.sandbox import publishing as sandbox
from socialhood.services.scheduled_posts import views as scheduled_post_views
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.automations import make_media_item
from tests.support.inbox import make_account
from tests.support.ingest import jobs
from tests.support.publish_jobs import Desk, make_desk
from tests.support.publishing_api import Shop, failing, iso, later, open_shop
from tests.support.sending import clean_outbox


@pytest.fixture(autouse=True)
def _sandbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def shop(app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Shop:
    return await open_shop(app, client, clerk, engine)


@pytest.fixture
async def desk(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    clean_db: None,
    queue: None,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Desk]:
    async with httpx.AsyncClient() as http:
        deps = deps_from(http, api_settings)
        monkeypatch.setattr(scheduled_post_views, "_worker_deps", lambda: deps)
        yield await make_desk(engine, redis, deps)


async def page_of(shop: Shop, name: str = "maple.page") -> uuid.UUID:
    return await shop.account(name, platform="facebook")


async def page_draft(shop: Shop, page: Any, **body: Any) -> dict[str, Any]:
    body.setdefault("targets", [{"social_account_id": page}])
    return await shop.draft(**body)


# ---------------------------------------------------------------- the composer's API


async def test_text_for_a_page_alone_is_a_text_post_that_passes(shop: Shop) -> None:
    page = await page_of(shop)
    post = await page_draft(shop, page, caption="Open late tonight https://maple.example/menu")

    assert post["format"] == "text"
    assert post["ready"] is True, post["checklist"]
    keys = {i["key"] for i in post["checklist"]}
    assert keys.isdisjoint({"media_files", "hashtags", "mentions", "publishing_limit"})
    media = next(i for i in post["checklist"] if i["key"] == "media")
    assert media["message"] == "Text post"


async def test_text_with_an_instagram_account_still_needs_media(shop: Shop) -> None:
    page = await page_of(shop)
    post = await shop.draft(
        targets=[{"social_account_id": shop.account_id}, {"social_account_id": page}],
        caption="Text only",
    )
    assert post["format"] is None
    assert failing(post) == {"asset_ids": "media"}


async def test_a_page_alone_with_no_text_or_media_is_asked_for_either(shop: Shop) -> None:
    page = await page_of(shop)
    post = await page_draft(shop, page)
    assert failing(post) == {"asset_ids": "media"}
    assert (
        "write the post's text"
        in next(i for i in post["checklist"] if i["key"] == "media")["message"]
    )


async def test_a_page_takes_a_wide_photo_that_instagram_would_refuse(shop: Shop) -> None:
    page = await page_of(shop)
    wide = await shop.image(width=3000, height=500)
    only_page = await page_draft(shop, page, asset_ids=[wide], caption="Banner")
    assert only_page["ready"] is True, only_page["checklist"]
    both = await shop.draft(
        targets=[{"social_account_id": shop.account_id}, {"social_account_id": page}],
        asset_ids=[wide],
        caption="Banner",
    )
    assert failing(both) == {"asset_ids.0": "media_files"}


async def test_photos_and_a_video_do_not_mix_on_a_page(shop: Shop) -> None:
    page = await page_of(shop)
    post = await page_draft(
        shop, page, asset_ids=[await shop.image(), await shop.video()], caption="Mix"
    )
    assert failing(post) == {"asset_ids": "media"}
    mixed = next(i for i in post["checklist"] if i["key"] == "media")
    assert mixed["message"] == "A Facebook post can have several photos or one video, not both."


async def test_hashtags_are_not_limited_on_a_page(shop: Shop) -> None:
    page = await page_of(shop)
    post = await page_draft(shop, page, caption=" ".join(f"#t{i}" for i in range(45)))
    assert post["ready"] is True, post["checklist"]


async def test_a_page_post_schedules_and_counts_like_any_post(shop: Shop) -> None:
    page = await page_of(shop)
    post = await page_draft(shop, page, caption="Open late tonight")
    out = await shop.ok(
        "POST", f"/scheduled-posts/{post['id']}/schedule", {"publish_at": iso(later(days=1))}
    )
    assert (out["status"], out["format"]) == ("scheduled", "text")
    counter = await shop.one("SELECT used FROM usage_counters WHERE metric = 'scheduled_posts'")
    assert counter["used"] == 1


# ---------------------------------------------------------------- the jobs


async def page_post(desk: Desk, kinds: tuple[str, ...], **values: Any) -> tuple[Any, Any]:
    page = await make_account(desk.engine, desk.wid, platform="facebook", username="maple.page")
    made = await desk.post(kinds, accounts=[page], **values)
    return made, made.target_ids[page]


async def test_a_text_post_publishes_to_a_sandbox_page(desk: Desk) -> None:
    made, target_id = await page_post(
        desk, (), caption="Open late tonight https://maple.example", format="text"
    )
    assert await desk.dispatch() == [target_id]
    assert await desk.publish(target_id) == "containers_created"
    assert await desk.poll(target_id, 1) == "published"

    published = await desk.target(target_id)
    assert published["permalink"].startswith("https://www.facebook.com/")
    [item] = await desk.rows("SELECT media_type, caption FROM media_items")
    assert (item["media_type"], item["caption"]) == (
        "image",
        "Open late tonight https://maple.example",
    )
    assert (await desk.post_row(made.id))["status"] == "published"
    assert sandbox.publish_count() == 1


async def test_photos_and_a_video_publish_to_a_page(desk: Desk) -> None:
    made, target_id = await page_post(desk, ("image", "image"), caption="Weekend menu")
    await desk.dispatch()
    assert await desk.publish(target_id) == "containers_created"
    assert (await desk.target(target_id))["container_id"] is None  # the post waits for its photos
    assert await desk.poll(target_id, 1) == "published"
    [item] = await desk.rows("SELECT media_type FROM media_items")
    assert item["media_type"] == "carousel"
    assert (await desk.post_row(made.id))["status"] == "published"


async def test_a_page_video_waits_for_processing_then_publishes(desk: Desk) -> None:
    sandbox.processing_reads(1)
    _, target_id = await page_post(desk, ("video",))
    await desk.dispatch()
    await desk.publish(target_id)
    assert await desk.poll_until_done(target_id) == ["waiting", "published"]
    [item] = await desk.rows("SELECT media_type FROM media_items")
    assert item["media_type"] == "video"  # a Page video, not a Reel


async def test_a_page_has_no_publishing_limit(desk: Desk) -> None:
    sandbox.set_quota(used=100, limit=100)
    made, target_id = await page_post(desk, ("image",))
    await desk.dispatch()
    assert await desk.publish(target_id) == "containers_created"
    assert await desk.poll(target_id, 1) == "published"
    assert (await desk.post_row(made.id))["status"] == "published"


async def test_a_page_post_can_carry_a_first_comment(desk: Desk) -> None:
    _, target_id = await page_post(desk, ("image",), first_comment="Link in bio")
    await desk.dispatch()
    await desk.publish(target_id)
    await desk.poll(target_id, 1)
    assert await jobs("post_first_comment") != []
    assert await desk.first_comment(target_id) == "posted"


async def test_a_refused_page_post_fails_with_the_reason_and_notifies(desk: Desk) -> None:
    made, target_id = await page_post(
        desk, ("image",), caption="Bad [sandbox:fail=platform_rejected]"
    )
    await desk.dispatch()
    await desk.publish(target_id)
    assert await desk.poll(target_id, 1) == "failed"

    row = await desk.target(target_id)
    assert (row["status"], row["error_code"]) == ("failed", "platform_rejected")
    assert (await desk.post_row(made.id))["status"] == "failed"
    [note] = await desk.notifications()
    assert note["type"] == "post_failed"


async def test_a_lost_answer_on_a_page_is_never_published_twice(desk: Desk) -> None:
    sandbox.lose_next_publish_answer()
    _, target_id = await page_post(desk, ("image",))
    await desk.dispatch()
    await desk.publish(target_id)

    assert await desk.poll(target_id, 1) == "failed"
    row = await desk.target(target_id)
    assert row["error_code"] == "delivery_unknown"
    assert "Check" in row["error_message"]
    assert sandbox.publish_count() == 1


async def test_a_page_without_the_publish_permission_fails_clearly(desk: Desk) -> None:
    page = await make_account(
        desk.engine,
        desk.wid,
        platform="facebook",
        platform_account_id="1098765",
        username="real.page",
    )
    made = await desk.post(("image",), accounts=[page])
    [target_id] = made.target_ids.values()
    await desk.dispatch()
    assert await desk.publish(target_id) == "failed"
    row = await desk.target(target_id)
    assert row["status"] == "failed"


# ---------------------------------------------------------------- best times


async def seed_posts(shop: Shop, account_id: Any, count: int, *, hour: int = 18) -> None:
    """``count`` weekly Monday posts at ``hour`` UTC, newest a week ago, with rising engagement."""
    monday = datetime.now(UTC).replace(hour=hour, minute=10, second=0, microsecond=0)
    monday -= timedelta(days=monday.weekday())
    for week in range(count):
        item = await make_media_item(
            shop.engine,
            workspace_id=shop.wid,
            account_id=account_id,
            posted_at=monday - timedelta(weeks=week + 1),
        )
        await shop.execute(
            "UPDATE media_items SET like_count = :likes, comments_count = 3 WHERE id = :id",
            likes=40 + 10 * (week % 3),
            id=item,
        )


async def test_best_times_say_when_there_is_too_little_history(shop: Shop) -> None:
    await seed_posts(shop, shop.account_id, 3)
    out = await shop.ok("GET", f"/social-accounts/{shop.account_id}/best-times")
    assert out["enough_history"] is False
    assert (out["sample_size"], out["min_posts"]) == (3, 10)
    assert [d["weekday"] for d in out["days"]] == list(range(7))
    assert all(d["local_time"] is None for d in out["days"])
    assert out["timezone"] == "UTC"
    assert out["method"]


async def test_best_times_suggest_the_hour_of_the_busy_weekday(shop: Shop) -> None:
    await seed_posts(shop, shop.account_id, 12)
    out = await shop.ok("GET", f"/social-accounts/{shop.account_id}/best-times")
    assert out["enough_history"] is True
    assert out["sample_size"] == 12
    monday = out["days"][0]
    assert monday["local_time"] == "18:00:00"
    assert monday["posts"] == 12
    assert out["days"][1]["local_time"] is None  # nothing was posted on Tuesdays


async def test_best_times_work_for_a_facebook_page_from_its_counts(shop: Shop) -> None:
    page = await page_of(shop)
    await seed_posts(shop, page, 12, hour=9)
    out = await shop.ok("GET", f"/social-accounts/{page}/best-times")
    assert out["days"][0]["local_time"] == "09:00:00"


async def test_best_times_are_cached_and_follow_the_workspace_time_zone(shop: Shop) -> None:
    await seed_posts(shop, shop.account_id, 12)
    await shop.set_timezone("Asia/Kolkata")
    first = await shop.ok("GET", f"/social-accounts/{shop.account_id}/best-times")
    assert first["days"][0]["local_time"] == "23:00:00"  # 18:10 UTC is 23:40 in Kolkata
    await shop.execute("DELETE FROM media_items WHERE social_account_id = :a", a=shop.account_id)
    again = await shop.ok("GET", f"/social-accounts/{shop.account_id}/best-times")
    assert again["computed_at"] == first["computed_at"]  # from the cache


async def test_best_times_are_for_the_workspaces_accounts_and_signed_in_people(
    shop: Shop, client: httpx.AsyncClient
) -> None:
    assert (
        await client.get(shop.url(f"/social-accounts/{shop.account_id}/best-times"))
    ).status_code == 401
    other = uuid.uuid4()
    assert (await shop.call("GET", f"/social-accounts/{other}/best-times")).status_code == 404
