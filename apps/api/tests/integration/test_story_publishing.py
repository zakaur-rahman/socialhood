"""GR-39 (C-114): Instagram Story scheduling end to end on sandbox accounts. The composer's
``kind: story`` makes one image or video a Story; the checklist refuses what Meta refuses; it
counts against scheduled_posts_monthly like any post; the publish jobs create a STORIES container,
poll videos like Reels, never send the caption, publish, and the story then shows in the live
stories the automation picker lists with its 24-hour expiry."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.platforms.deps import deps_from
from socialhood.platforms.sandbox import history
from socialhood.platforms.sandbox import publishing as sandbox
from socialhood.services.scheduled_posts import views as scheduled_post_views
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.ingest import jobs, stream
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


async def story_draft(
    shop: Shop, kinds: tuple[str, ...] = ("image",), **body: Any
) -> dict[str, Any]:
    assets = [await (shop.image(height=1920) if k == "image" else shop.video()) for k in kinds]
    return await shop.ready_draft(asset_ids=assets, kind="story", **body)


# ---------------------------------------------------------------- the API


@pytest.mark.parametrize("kind", ["image", "video"])
async def test_one_image_or_video_chosen_as_a_story_is_a_story(shop: Shop, kind: str) -> None:
    post = await story_draft(shop, (kind,))

    assert post["format"] == "story"
    assert post["ready"] is True, post["checklist"]
    caption = next(i for i in post["checklist"] if i["key"] == "caption")
    assert caption["message"] == "Stories are published without a caption"
    assert {i["key"] for i in post["checklist"]}.isdisjoint({"hashtags", "mentions"})


async def test_the_same_media_without_the_story_choice_is_not_a_story(shop: Shop) -> None:
    image = await shop.image()
    post = await shop.ready_draft(asset_ids=[image])
    assert post["format"] == "image"


async def test_a_story_can_not_be_a_carousel(shop: Shop) -> None:
    post = await story_draft(shop, ("image", "image"))

    assert post["format"] is None
    assert post["ready"] is False
    assert failing(post)["asset_ids"] == "media"
    media = next(i for i in post["checklist"] if i["key"] == "media")
    assert media["message"] == "A Story is one image or one video."


async def test_story_video_length_is_checked(shop: Shop) -> None:
    long = await shop.video(duration_s=75.0)
    short = await shop.video(duration_s=2.0)

    too_long = await shop.ready_draft(asset_ids=[long], kind="story")
    too_short = await shop.ready_draft(asset_ids=[short], kind="story")

    assert failing(too_long) == {"asset_ids.0": "media_files"}
    assert failing(too_short) == {"asset_ids.0": "media_files"}
    messages = {i["message"] for p in (too_long, too_short) for i in p["checklist"] if not i["ok"]}
    assert messages == {
        "Story videos can be up to 60 seconds.",
        "Story videos must be at least 3 seconds.",
    }
    # The same 75 second video is fine as a Reel.
    assert (await shop.ready_draft(asset_ids=[long]))["ready"] is True


async def test_a_caption_kept_on_a_story_draft_is_not_checked(shop: Shop) -> None:
    post = await story_draft(shop, caption="#x " * 700)  # 700 hashtags: far over the limit
    assert post["ready"] is True, post["checklist"]
    assert post["caption"].count("#") == 700


async def test_a_story_is_refused_on_a_facebook_page(shop: Shop) -> None:
    page = await shop.account("maple.page", platform="facebook")
    post = await story_draft(
        shop, targets=[{"social_account_id": shop.account_id}, {"social_account_id": page}]
    )
    assert failing(post) == {"targets.1": "accounts"}


async def test_a_story_counts_against_the_plans_scheduled_posts(shop: Shop) -> None:
    post = await story_draft(shop)
    await shop.ok(
        "POST", f"/scheduled-posts/{post['id']}/schedule", {"publish_at": iso(later(days=1))}
    )
    counter = await shop.one("SELECT used FROM usage_counters WHERE metric = 'scheduled_posts'")
    assert counter["used"] == 1

    await shop.execute(
        "UPDATE usage_counters SET used = 10 WHERE metric = 'scheduled_posts'"
        " AND workspace_id = :w",
        w=shop.wid,
    )
    second = await story_draft(shop)
    problem = await shop.problem(
        "POST",
        f"/scheduled-posts/{second['id']}/schedule",
        {"publish_at": iso(later(days=1))},
        status=402,
    )
    assert problem["code"] == "quota_exceeded"


async def test_a_story_survives_edit_and_duplicate(shop: Shop) -> None:
    post = await story_draft(shop)
    copy = await shop.ok("POST", f"/scheduled-posts/{post['id']}/duplicate", status=201)
    assert copy["format"] == "story"
    back = await shop.ok(
        "PUT",
        f"/scheduled-posts/{post['id']}",
        {
            "targets": [{"social_account_id": str(shop.account_id)}],
            "asset_ids": [a["id"] for a in post["assets"]],
            "kind": "post",
        },
    )
    assert back["format"] == "image"


# ---------------------------------------------------------------- the jobs


async def test_a_story_publishes_without_its_caption_and_expires_in_24_hours(desk: Desk) -> None:
    made = await desk.post(("image",), caption="never sent", format="story", first_comment="no")
    [target_id] = made.target_ids.values()

    assert await desk.dispatch() == [target_id]
    assert await desk.publish(target_id) == "containers_created"
    row = await desk.target(target_id)
    container = sandbox.container(row["container_id"])
    assert container is not None
    assert (container.kind, container.story, container.caption) == ("image", True, None)

    assert await desk.poll(target_id, 1) == "published"
    published = await desk.target(target_id)
    assert "/stories/" in published["permalink"]
    [item] = await desk.rows("SELECT media_type, caption FROM media_items")
    assert (item["media_type"], item["caption"]) == ("story", None)
    # A story takes no first comment and no "next post" automation.
    assert await jobs("post_first_comment") == []

    events = [
        p["scheduled_post"]
        for kind, p in await stream(desk.redis, desk.wid)
        if kind == "scheduled_post.updated"
    ]
    last = events[-1]
    assert (last["status"], last["format"]) == ("published", "story")
    expires = datetime.fromisoformat(last["targets"][0]["expires_at"].replace("Z", "+00:00"))
    published_at = published["published_at"]
    assert abs(expires - (published_at + timedelta(hours=24))) < timedelta(seconds=1)


async def test_a_published_story_is_in_the_live_stories_the_picker_lists(desk: Desk) -> None:
    made = await desk.post(("image",), format="story")
    [target_id] = made.target_ids.values()
    await desk.dispatch()
    await desk.publish(target_id)
    await desk.poll(target_id, 1)
    published = await desk.target(target_id)

    acct = await desk.account(desk.account_ids[0])
    live = history.stories(acct)
    assert published["platform_media_id"] in [s.platform_media_id for s in live]
    assert published["platform_media_id"] not in [
        p.platform_media_id for p in history.posts(acct, limit=20)
    ]


async def test_a_video_story_waits_for_processing_like_a_reel(desk: Desk) -> None:
    sandbox.processing_reads(1)
    made = await desk.post(("video",), format="story")
    [target_id] = made.target_ids.values()
    await desk.dispatch()
    assert await desk.publish(target_id) == "containers_created"

    assert await desk.poll_until_done(target_id) == ["waiting", "published"]
    [item] = await desk.rows("SELECT media_type FROM media_items")
    assert item["media_type"] == "story"


async def test_a_failed_story_says_why_in_plain_words(desk: Desk) -> None:
    sandbox.fail_next_container("ERROR", "Instagram doesn't accept this Story's shape.")
    made = await desk.post(("image",), format="story")
    [target_id] = made.target_ids.values()
    await desk.dispatch()
    await desk.publish(target_id)
    assert await desk.poll(target_id, 1) == "failed"

    row = await desk.target(target_id)
    assert (row["status"], row["error_message"]) == (
        "failed",
        "Instagram doesn't accept this Story's shape.",
    )
    [note] = await desk.notifications()
    assert note["type"] == "post_failed"
    assert note["body"].startswith("Your Story didn't publish.")


async def test_a_lost_story_publish_answer_is_found_among_the_stories(desk: Desk) -> None:
    sandbox.lose_next_publish_answer()
    made = await desk.post(("image",), format="story")
    [target_id] = made.target_ids.values()
    await desk.dispatch()
    await desk.publish(target_id)

    outcomes = await desk.poll_until_done(target_id)
    assert outcomes[-1] == "published"
    assert sandbox.publish_count() == 1  # never published twice
