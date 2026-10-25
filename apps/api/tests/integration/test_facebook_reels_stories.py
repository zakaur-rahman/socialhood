"""C-131: Facebook Reels and Page Stories end to end on sandbox Pages. The composer's ``kind``
(``reel`` or ``story``) chooses them for a Page; a Page video stays a normal video without the
Reel choice; the same jobs publish and poll; a lost publish answer is found again for a Reel and a
video Story (their status shows the publishing phase) and never published twice for a photo Story;
a Page Story is not readable, so it has no address and is not in the live stories."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.platforms.deps import deps_from
from socialhood.platforms.registry import adapter_for
from socialhood.platforms.sandbox import publishing as sandbox
from socialhood.services.scheduled_posts import views as scheduled_post_views
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.inbox import make_account
from tests.support.publish_jobs import Desk, make_desk
from tests.support.publishing_api import Shop, failing, open_shop
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


async def page_of(shop: Shop) -> uuid.UUID:
    return await shop.account("maple.page", platform="facebook")


async def reel_draft(
    shop: Shop, page: Any, kinds: tuple[str, ...] = ("video",), **body: Any
) -> Any:
    assets = [await (shop.video() if k == "video" else shop.image()) for k in kinds]
    return await shop.ready_draft(
        targets=[{"social_account_id": page}], asset_ids=assets, kind="reel", **body
    )


# ---------------------------------------------------------------- the composer's API


async def test_a_video_chosen_as_a_reel_is_a_page_reel(shop: Shop) -> None:
    page = await page_of(shop)
    post = await reel_draft(shop, page, caption="Behind the counter")
    assert (post["kind"], post["format"]) == ("reel", "reel")
    assert post["ready"] is True, post["checklist"]
    keys = {i["key"] for i in post["checklist"]}
    assert "publishing_limit" not in keys  # a Page has none


async def test_the_same_video_without_the_reel_choice_is_a_normal_page_video(shop: Shop) -> None:
    page = await page_of(shop)
    post = await shop.ready_draft(
        targets=[{"social_account_id": page}], asset_ids=[await shop.video()]
    )
    assert (post["kind"], post["format"]) == ("post", "reel")  # the format name is unchanged


async def test_a_reel_is_one_video_for_a_page(shop: Shop) -> None:
    page = await page_of(shop)
    photo = await reel_draft(shop, page, ("image",))
    assert failing(photo) == {"asset_ids": "media"}
    two = await reel_draft(shop, page, ("video", "video"))
    assert failing(two) == {"asset_ids": "media"}
    messages = {i["message"] for i in two["checklist"] if not i["ok"]}
    assert messages == {"A Facebook Reel is one video."}


async def test_a_reel_needs_a_facebook_page(shop: Shop) -> None:
    video = await shop.video()
    post = await shop.ready_draft(
        targets=[{"social_account_id": shop.account_id}], asset_ids=[video], kind="reel"
    )
    assert failing(post) == {"targets": "accounts"}


async def test_a_reel_cross_posts_to_instagram_and_a_page(shop: Shop) -> None:
    page = await page_of(shop)
    post = await shop.ready_draft(
        targets=[{"social_account_id": shop.account_id}, {"social_account_id": page}],
        asset_ids=[await shop.video()],
        kind="reel",
    )
    assert post["ready"] is True, post["checklist"]
    copy = await shop.ok("POST", f"/scheduled-posts/{post['id']}/duplicate", status=201)
    assert copy["kind"] == "reel"


async def test_a_page_story_is_checked_by_the_story_rules(shop: Shop) -> None:
    page = await page_of(shop)
    good = await shop.ready_draft(
        targets=[{"social_account_id": page}],
        asset_ids=[await shop.image(height=1920)],
        kind="story",
    )
    assert (good["kind"], good["format"]) == ("story", "story")
    assert good["ready"] is True, good["checklist"]
    two = await shop.ready_draft(
        targets=[{"social_account_id": page}],
        asset_ids=[await shop.image(), await shop.image()],
        kind="story",
    )
    assert failing(two) == {"asset_ids": "media"}


# ---------------------------------------------------------------- the jobs


async def page_post(desk: Desk, kinds: tuple[str, ...], **values: Any) -> tuple[Any, Any, Any]:
    page = await make_account(desk.engine, desk.wid, platform="facebook", username="maple.page")
    made = await desk.post(kinds, accounts=[page], **values)
    return made, made.target_ids[page], page


async def test_a_page_reel_uploads_waits_then_publishes_as_a_reel(desk: Desk) -> None:
    sandbox.processing_reads(1)
    made, target_id, _ = await page_post(desk, ("video",), kind="reel", caption="Tour")
    await desk.dispatch()
    assert await desk.publish(target_id) == "containers_created"
    container = sandbox.container((await desk.target(target_id))["container_id"])
    assert container is not None
    assert (container.kind, container.page_reel) == ("video", True)

    assert await desk.poll_until_done(target_id) == ["waiting", "published"]
    [item] = await desk.rows("SELECT media_type, caption FROM media_items")
    assert (item["media_type"], item["caption"]) == ("reel", "Tour")
    assert (await desk.post_row(made.id))["status"] == "published"
    assert sandbox.publish_count() == 1


async def test_a_page_reel_whose_publish_answer_was_lost_is_found_not_published_twice(
    desk: Desk,
) -> None:
    sandbox.lose_next_publish_answer()
    _, target_id, _ = await page_post(desk, ("video",), kind="reel", caption="Tour")
    await desk.dispatch()
    await desk.publish(target_id)

    outcomes = await desk.poll_until_done(target_id)
    assert outcomes[-1] == "published"
    assert sandbox.publish_count() == 1
    [item] = await desk.rows("SELECT media_type FROM media_items")
    assert item["media_type"] == "reel"


async def test_a_page_photo_story_publishes_without_an_address(desk: Desk) -> None:
    made, target_id, page = await page_post(desk, ("image",), format="story", caption="not sent")
    await desk.dispatch()
    assert await desk.publish(target_id) == "containers_created"
    container = sandbox.container((await desk.target(target_id))["container_id"])
    assert container is not None
    assert (container.kind, container.story, container.caption) == ("image", True, None)
    assert await desk.poll(target_id, 1) == "published"

    row = await desk.target(target_id)
    assert row["permalink"] is None  # Facebook gives no way to read a Page Story back
    [item] = await desk.rows("SELECT media_type, caption FROM media_items")
    assert (item["media_type"], item["caption"]) == ("story", None)
    assert (await desk.post_row(made.id))["status"] == "published"

    acct = await desk.account(page)
    acct.platform = "facebook"  # the desk's helper builds an Instagram account
    assert await adapter_for(acct, desk.deps).list_stories(acct) == []  # no read API for Pages


async def test_a_page_video_story_waits_for_processing(desk: Desk) -> None:
    sandbox.processing_reads(1)
    _, target_id, _ = await page_post(desk, ("video",), format="story")
    await desk.dispatch()
    assert await desk.publish(target_id) == "containers_created"
    assert await desk.poll_until_done(target_id) == ["waiting", "published"]
    [item] = await desk.rows("SELECT media_type FROM media_items")
    assert item["media_type"] == "story"


async def test_a_lost_video_story_answer_is_found(desk: Desk) -> None:
    sandbox.lose_next_publish_answer()
    _, target_id, _ = await page_post(desk, ("video",), format="story")
    await desk.dispatch()
    await desk.publish(target_id)
    outcomes = await desk.poll_until_done(target_id)
    assert outcomes[-1] == "published"
    assert sandbox.publish_count() == 1


async def test_a_lost_photo_story_answer_ends_unconfirmed_and_is_never_published_twice(
    desk: Desk,
) -> None:
    sandbox.lose_next_publish_answer()
    _, target_id, _ = await page_post(desk, ("image",), format="story")
    await desk.dispatch()
    await desk.publish(target_id)

    assert await desk.poll(target_id, 1) == "failed"
    row = await desk.target(target_id)
    assert row["error_code"] == "delivery_unknown"
    assert sandbox.publish_count() == 1


async def test_a_page_video_without_the_reel_choice_stays_a_video(desk: Desk) -> None:
    _, target_id, _ = await page_post(desk, ("video",))
    await desk.dispatch()
    await desk.publish(target_id)
    await desk.poll_until_done(target_id)
    [item] = await desk.rows("SELECT media_type FROM media_items")
    assert item["media_type"] == "video"
