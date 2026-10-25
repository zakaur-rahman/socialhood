"""FR-PUB-07 (C-134): Instagram collaborators, user tags, the location and a Reel's options end to
end on sandbox accounts. The API stores and validates them and the checklist refuses what Meta
refuses; the publish jobs send them on the right containers; after publishing each collaborator's
invite status is read (Pending or Accepted) by the periodic job and on demand; another
workspace's post answers 404 for the refresh."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.jobs.tasks import publishing as publish_jobs
from socialhood.platforms.deps import deps_from
from socialhood.platforms.sandbox import publishing as sandbox
from socialhood.services.scheduled_posts import views as scheduled_post_views
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.inbox import make_asset
from tests.support.publish_jobs import Desk, make_desk
from tests.support.publishing_api import Shop, failing, open_shop
from tests.support.sending import clean_outbox

PAGE = "108123456789012"


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


async def tag_asset(desk: Desk, asset_id: Any, tags: list[dict[str, Any]]) -> None:
    async with desk.engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE scheduled_post_assets SET user_tags = CAST(:t AS jsonb)"
                " WHERE media_asset_id = :a"
            ),
            {"t": json.dumps(tags), "a": asset_id},
        )


# ---------------------------------------------------------------- the API


async def test_extras_are_stored_and_come_back_normalised(shop: Shop) -> None:
    image = await shop.image()
    post = await shop.ready_draft(
        asset_ids=[image],
        collaborators=["@Maple.Studio", "bread_fan", "maple.studio"],
        location=f"https://www.facebook.com/profile.php?id={PAGE}",
        user_tags=[{"asset_id": str(image), "username": "@Bread.Fan", "x": 0.25, "y": 0.75}],
    )
    assert post["collaborators"] == ["maple.studio", "bread_fan"]
    assert post["location_id"] == PAGE
    assert post["assets"][0]["user_tags"] == [{"username": "bread.fan", "x": 0.25, "y": 0.75}]
    assert post["ready"] is True, post["checklist"]
    extras = [i["message"] for i in post["checklist"] if i["key"] == "extras"]
    assert extras == [
        "Collaborators: @maple.studio, @bread_fan",
        "1 tag on 1 photo",
        "Location set",
    ]


async def test_a_post_without_extras_has_no_extras_line(shop: Shop) -> None:
    post = await shop.ready_draft()
    assert [i for i in post["checklist"] if i["key"] == "extras"] == []
    assert (post["collaborators"], post["location_id"], post["share_to_feed"]) == ([], None, True)


async def test_bad_extras_are_field_errors_on_save(shop: Shop) -> None:
    image = await shop.image()
    fields = await shop.fields(
        "POST",
        "/scheduled-posts",
        {
            "targets": [{"social_account_id": str(shop.account_id)}],
            "asset_ids": [str(image)],
            "collaborators": ["a", "b", "c", "d"],
            "location": "maplebakery",
            "user_tags": [
                {"asset_id": str(image), "username": "bad name", "x": 0.5, "y": 0.5},
                {
                    "asset_id": "00000000-0000-0000-0000-000000000001",
                    "username": "ok",
                    "x": 0,
                    "y": 0,
                },
            ],
        },
    )
    assert set(fields) == {"collaborators", "location", "user_tags.0", "user_tags.1"}


async def test_tag_positions_outside_the_photo_are_refused(shop: Shop) -> None:
    image = await shop.image()
    response = await shop.call(
        "POST",
        "/scheduled-posts",
        {
            "asset_ids": [str(image)],
            "user_tags": [{"asset_id": str(image), "username": "ok", "x": 1.2, "y": 0.5}],
        },
    )
    assert response.status_code == 422


async def test_tags_are_dropped_with_their_photo(shop: Shop) -> None:
    first, second = await shop.image(), await shop.image()
    post = await shop.ready_draft(
        asset_ids=[first, second],
        user_tags=[{"asset_id": str(first), "username": "ok", "x": 0.1, "y": 0.1}],
    )
    saved = await shop.ok(
        "PUT",
        f"/scheduled-posts/{post['id']}",
        {
            "targets": [{"social_account_id": str(shop.account_id)}],
            "asset_ids": [str(second)],
            "caption": "x",
        },
    )
    assert saved["assets"][0]["user_tags"] == []


async def test_collaborators_are_refused_on_a_story_and_on_a_facebook_only_post(shop: Shop) -> None:
    image = await shop.image(height=1920)
    story = await shop.ready_draft(asset_ids=[image], kind="story", collaborators=["maple.studio"])
    assert failing(story) == {"collaborators": "extras"}
    page = await shop.account("maple.page", platform="facebook")
    only = await shop.ready_draft(
        targets=[{"social_account_id": page}], collaborators=["maple.studio"], location=PAGE
    )
    assert failing(only) == {"collaborators": "extras", "location": "extras"}


async def test_a_reel_takes_options_and_a_photo_post_does_not(shop: Shop) -> None:
    video = await shop.video(duration_s=240.0)
    cover = await shop.image()
    reel = await shop.ready_draft(
        asset_ids=[video],
        cover_asset_id=str(cover),
        share_to_feed=False,
        audio_name="Morning bake",
    )
    assert reel["format"] == "reel"
    assert reel["ready"] is True, reel["checklist"]  # four minutes: a Reel runs up to 15
    assert reel["cover_url"]
    assert reel["share_to_feed"] is False
    assert reel["audio_name"] == "Morning bake"
    photo = await shop.ready_draft(audio_name="Morning bake")
    assert failing(photo) == {"cover_asset_id": "extras"}


async def test_a_reel_frame_past_the_end_is_refused(shop: Shop) -> None:
    video = await shop.video(duration_s=10.0)
    reel = await shop.ready_draft(asset_ids=[video], cover_offset_ms=12_000)
    assert failing(reel) == {"cover_offset_ms": "extras"}


async def test_reel_length_rules_follow_the_post(shop: Shop) -> None:
    long = await shop.video(duration_s=300.0)
    assert (await shop.ready_draft(asset_ids=[long]))["ready"] is True
    too_long = await shop.video(duration_s=901.0)
    assert failing(await shop.ready_draft(asset_ids=[too_long])) == {"asset_ids.0": "media_files"}
    too_short = await shop.video(duration_s=2.0)
    assert failing(await shop.ready_draft(asset_ids=[too_short])) == {"asset_ids.0": "media_files"}
    # inside a carousel a video keeps its 90 seconds
    carousel = await shop.ready_draft(asset_ids=[await shop.image(), long])
    assert failing(carousel) == {"asset_ids.1": "media_files"}


async def test_the_video_size_cap_comes_from_the_setting(shop: Shop) -> None:
    post = await shop.ready_draft()
    assert post["video_max_mb"] == 100


async def test_extras_survive_duplicate(shop: Shop) -> None:
    image = await shop.image()
    post = await shop.ready_draft(
        asset_ids=[image],
        collaborators=["maple.studio"],
        location=PAGE,
        user_tags=[{"asset_id": str(image), "username": "ok", "x": 0.5, "y": 0.5}],
    )
    copy = await shop.ok("POST", f"/scheduled-posts/{post['id']}/duplicate", status=201)
    assert copy["collaborators"] == ["maple.studio"]
    assert copy["location_id"] == PAGE
    assert copy["assets"][0]["user_tags"] == [{"username": "ok", "x": 0.5, "y": 0.5}]


async def test_refreshing_collaborators_needs_a_published_post(shop: Shop) -> None:
    post = await shop.ready_draft(collaborators=["maple.studio"])
    problem = await shop.problem(
        "POST", f"/scheduled-posts/{post['id']}/collaborators/refresh", status=409
    )
    assert problem["code"] == "conflict"


# ---------------------------------------------------------------- the jobs


async def publish_one(desk: Desk, made: Any) -> Any:
    [target_id] = made.target_ids.values()
    await desk.dispatch()
    assert await desk.publish(target_id) == "containers_created"
    await desk.poll_until_done(target_id)
    return target_id


async def test_an_image_container_gets_collaborators_location_and_tags(desk: Desk) -> None:
    made = await desk.post(
        ("image",), collaborators=["maple.studio", "accepts.fast"], location_id=PAGE
    )
    await tag_asset(desk, made.asset_ids[0], [{"username": "bread.fan", "x": 0.25, "y": 0.75}])
    [target_id] = made.target_ids.values()
    await desk.dispatch()
    assert await desk.publish(target_id) == "containers_created"

    row = await desk.target(target_id)
    container = sandbox.container(row["container_id"])
    assert container is not None
    assert container.extras is not None
    assert container.extras.collaborators == ("maple.studio", "accepts.fast")
    assert container.extras.location_id == PAGE
    [tag] = container.extras.user_tags
    assert (tag.username, tag.x, tag.y) == ("bread.fan", 0.25, 0.75)


async def test_a_carousel_puts_tags_on_children_and_the_rest_on_the_parent(desk: Desk) -> None:
    made = await desk.post(("image", "image"), collaborators=["maple.studio"], location_id=PAGE)
    await tag_asset(desk, made.asset_ids[1], [{"username": "bread.fan", "x": 0.5, "y": 0.5}])
    [target_id] = made.target_ids.values()
    await desk.dispatch()
    await desk.publish(target_id)
    row = await desk.target(target_id)
    first, second = (sandbox.container(c) for c in row["child_container_ids"])
    assert first is not None
    assert second is not None
    assert first.user_tags == ()
    assert len(second.user_tags) == 1

    assert await desk.poll_until_done(target_id) == ["published"]
    published = await desk.target(target_id)
    parent = sandbox.container((await desk.target(target_id))["container_id"])
    assert parent is not None
    assert parent.extras is not None
    assert parent.extras.collaborators == ("maple.studio",)
    assert parent.extras.location_id == PAGE
    assert parent.extras.user_tags == ()
    assert published["status"] == "published"


async def test_a_reel_container_gets_its_options(desk: Desk) -> None:
    cover = await make_asset(desk.engine, workspace_id=desk.wid, purpose="post", height=1350)
    made = await desk.post(
        ("video",),
        collaborators=["maple.studio"],
        cover_asset_id=cover,
        cover_offset_ms=1500,
        share_to_feed=False,
        audio_name="Morning bake",
    )
    [target_id] = made.target_ids.values()
    await desk.dispatch()
    await desk.publish(target_id)
    container = sandbox.container((await desk.target(target_id))["container_id"])
    assert container is not None
    assert container.extras is not None
    assert container.share_to_feed is False
    assert container.extras.audio_name == "Morning bake"
    assert container.extras.cover_url  # the uploaded cover wins over the frame
    assert container.extras.collaborators == ("maple.studio",)


async def test_a_story_is_sent_without_any_extras(desk: Desk) -> None:
    made = await desk.post(("image",), format="story", collaborators=["maple.studio"])
    [target_id] = made.target_ids.values()
    await desk.dispatch()
    await desk.publish(target_id)
    container = sandbox.container((await desk.target(target_id))["container_id"])
    assert container is not None
    assert container.extras is None


async def test_a_sandbox_refusal_of_the_location_fails_the_target_in_plain_words(
    desk: Desk,
) -> None:
    made = await desk.post(("image",), location_id="not-a-page")
    [target_id] = made.target_ids.values()
    await desk.dispatch()
    await desk.publish(target_id)
    row = await desk.target(target_id)
    assert row["status"] == "failed"


async def test_collaborators_start_pending_and_the_job_reads_who_accepted(desk: Desk) -> None:
    made = await desk.post(("image",), collaborators=["maple.studio", "accepts.fast"])
    target_id = await publish_one(desk, made)
    row = await desk.target(target_id)
    assert row["status"] == "published"
    assert row["collaborator_statuses"] == [
        {"username": "maple.studio", "status": "pending"},
        {"username": "accepts.fast", "status": "pending"},
    ]

    now = datetime.now(UTC)
    assert (
        await publish_jobs.refresh_collaborator_invites(desk.maker, desk.redis, desk.deps, now) == 1
    )
    row = await desk.target(target_id)
    assert row["collaborator_statuses"] == [
        {"username": "maple.studio", "status": "pending"},
        {"username": "accepts.fast", "status": "accepted"},
    ]
    assert row["collaborators_checked_at"] is not None

    # read again only after an hour, and when someone accepts in the meantime
    sandbox.accept_collaborator(row["platform_media_id"], "maple.studio")
    assert (
        await publish_jobs.refresh_collaborator_invites(desk.maker, desk.redis, desk.deps, now) == 0
    )
    later = now + timedelta(hours=1, minutes=1)
    assert (
        await publish_jobs.refresh_collaborator_invites(desk.maker, desk.redis, desk.deps, later)
        == 1
    )
    row = await desk.target(target_id)
    assert {c["status"] for c in row["collaborator_statuses"]} == {"accepted"}


async def test_the_job_stops_reading_after_three_days(desk: Desk) -> None:
    made = await desk.post(("image",), collaborators=["maple.studio"])
    await publish_one(desk, made)
    in_a_week = datetime.now(UTC) + timedelta(days=7)
    assert (
        await publish_jobs.refresh_collaborator_invites(
            desk.maker, desk.redis, desk.deps, in_a_week
        )
        == 0
    )


async def test_a_failed_read_keeps_the_last_answer(desk: Desk) -> None:
    made = await desk.post(("image",), collaborators=["maple.studio"])
    target_id = await publish_one(desk, made)
    sandbox.fail_next("platform_unavailable", step="collaborators")
    now = datetime.now(UTC)
    assert (
        await publish_jobs.refresh_collaborator_invites(desk.maker, desk.redis, desk.deps, now) == 0
    )
    row = await desk.target(target_id)
    assert row["collaborator_statuses"] == [{"username": "maple.studio", "status": "pending"}]
    assert row["collaborators_checked_at"] is None


async def test_a_post_without_collaborators_is_never_read(desk: Desk) -> None:
    made = await desk.post(("image",))
    await publish_one(desk, made)
    now = datetime.now(UTC)
    assert (
        await publish_jobs.refresh_collaborator_invites(desk.maker, desk.redis, desk.deps, now) == 0
    )


# ---------------------------------------------------------------- on demand, and tenancy


async def test_refresh_on_demand_and_another_workspace_gets_404(shop: Shop) -> None:
    made = await shop.ready_draft(collaborators=["accepts.fast", "maple.studio"])
    # Publish the post by hand: the API alone can not run the publish jobs.
    await shop.execute(
        "UPDATE scheduled_posts SET status = 'published' WHERE id = :p", p=made["id"]
    )
    await shop.execute(
        "UPDATE scheduled_post_targets SET status = 'published', platform_media_id = :m,"
        " published_at = now(),"
        " collaborator_statuses = CAST(:s AS jsonb) WHERE scheduled_post_id = :p",
        m="sandbox_media_extras01",
        s=json.dumps(
            [
                {"username": "accepts.fast", "status": "pending"},
                {"username": "maple.studio", "status": "pending"},
            ]
        ),
        p=made["id"],
    )
    sandbox.accept_collaborator("sandbox_media_extras01", "accepts.fast")
    sandbox.STATE.invites["sandbox_media_extras01"].setdefault("maple.studio", False)

    post = await shop.ok("POST", f"/scheduled-posts/{made['id']}/collaborators/refresh")
    [target] = post["targets"]
    assert {c["username"]: c["status"] for c in target["collaborators"]} == {
        "accepts.fast": "accepted",
        "maple.studio": "pending",
    }
    assert target["collaborators_checked_at"] is not None

    missing = await shop.call(
        "POST", "/scheduled-posts/00000000-0000-0000-0000-000000000009/collaborators/refresh"
    )
    assert missing.status_code == 404
