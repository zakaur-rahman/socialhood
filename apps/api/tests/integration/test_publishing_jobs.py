"""T7.3 (F-13, FR-PUB-05, FR-PUB-06, FR-PUB-11, FR-AUT-18, TR-JOB-03…05): the dispatcher,
publish_target, poll_container, post_first_comment and the sweeper against sandbox accounts, each
job's body run in-process. Covers every container type, the polling paths (finished, error,
expired, timeout), quota exhausted → failed with the reason, partial success across two accounts,
a lost publish answer (never published twice), the first comment and automation linking."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.models.connections import SocialAccount
from socialhood.models.publishing import POLL_MAX, PROCESSING_TIMEOUT_MESSAGE
from socialhood.platforms.base import ContainerStatus
from socialhood.platforms.deps import deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.sandbox import history
from socialhood.platforms.sandbox import publishing as sandbox
from socialhood.services.post_publishing import publish
from socialhood.services.post_publishing.projection import derive_status
from socialhood.settings import Settings
from tests.support.api import _clear_queue
from tests.support.automations import make_automation
from tests.support.inbox import make_account, make_workspace
from tests.support.ingest import jobs, stream
from tests.support.instagram import GRAPH, fixture
from tests.support.post_metrics import IG_USER, make_instagram_account
from tests.support.publish_jobs import Desk, always, make_desk
from tests.support.sending import clean_outbox


@pytest.fixture(autouse=True)
def _sandbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def desk(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    clean_db: None,
    queue: None,
) -> AsyncIterator[Desk]:
    async with httpx.AsyncClient() as http:
        yield await make_desk(engine, redis, deps_from(http, api_settings))


async def post_events(desk: Desk, post_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        payload["scheduled_post"]
        for kind, payload in await stream(desk.redis, desk.wid)
        if kind == "scheduled_post.updated" and payload["scheduled_post"]["id"] == str(post_id)
    ]


async def claim(desk: Desk, target_id: uuid.UUID) -> None:
    assert target_id in await desk.dispatch()


# ---------------------------------------------------------------- each container type


async def test_an_image_post_publishes_end_to_end(desk: Desk) -> None:
    made = await desk.post(("image",), caption="Fresh bread #sourdough")
    [target_id] = made.target_ids.values()

    assert await desk.dispatch() == [target_id]
    claimed = await desk.target(target_id)
    assert (claimed["status"], claimed["attempts"]) == ("publishing", 1)
    assert (await desk.post_row(made.id))["status"] == "publishing"
    [job] = await jobs("publish_target")
    assert job["queueing_lock"] == f"pub:{target_id}"
    assert job["args"] == {"target_id": str(target_id), "workspace_id": str(desk.wid)}

    assert await desk.publish(target_id) == "containers_created"
    row = await desk.target(target_id)
    assert row["status"] == "container_created"
    container = sandbox.container(row["container_id"])
    assert container is not None
    assert (container.kind, container.caption) == ("image", "Fresh bread #sourdough")
    assert "/upload/f_jpg," in (container.url or "")  # the delivery URL (JPEG)
    [poll_job] = await jobs("poll_container")
    assert poll_job["queueing_lock"] == f"poll:{target_id}:1"
    assert poll_job["args"]["n"] == 1
    assert not poll_job["deferred"]  # poll 1 runs at once

    assert await desk.poll(target_id, 1) == "published"
    published = await desk.target(target_id)
    assert published["status"] == "published"
    assert published["platform_media_id"].startswith("sandbox_media_")
    assert published["permalink"].startswith("https://www.instagram.com/p/")
    post = await desk.post_row(made.id)
    assert post["status"] == "published"
    assert post["published_at"] == published["published_at"]
    [item] = await desk.rows(
        "SELECT * FROM media_items WHERE published_target_id = :t", t=target_id
    )
    assert (item["platform_media_id"], item["media_type"]) == (
        published["platform_media_id"],
        "image",
    )
    assert item["permalink"] == published["permalink"]
    assert await jobs("post_first_comment") == []  # no first comment

    events = await post_events(desk, made.id)
    assert [e["status"] for e in events] == ["publishing", "publishing", "published"]
    assert [e["targets"][0]["status"] for e in events] == [
        "publishing",
        "container_created",
        "published",
    ]
    last = events[-1]["targets"][0]
    assert last["post_id"] == str(item["id"])
    assert last["permalink"] == published["permalink"]
    assert await desk.notifications() == []


async def test_a_reel_waits_for_processing_then_publishes(desk: Desk) -> None:
    sandbox.processing_reads(2)
    made = await desk.post(("video",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    assert await desk.publish(target_id) == "containers_created"
    row = await desk.target(target_id)
    container = sandbox.container(row["container_id"])
    assert container is not None
    assert (container.kind, container.share_to_feed) == ("video", True)
    assert "vc_h264" in (container.url or "")  # H.264 MP4 delivery

    assert await desk.poll_until_done(target_id) == ["waiting", "waiting", "published"]
    assert container.status_reads == 3  # one status read per poll
    assert (await desk.target(target_id))["poll_count"] == 3
    [item] = await desk.rows("SELECT media_type FROM media_items")
    assert item["media_type"] == "reel"
    polls = await jobs("poll_container")
    assert [j["args"]["n"] for j in polls] == [1, 2, 3]
    assert [bool(j["deferred"]) for j in polls] == [False, True, True]


async def test_a_carousel_with_a_video_publishes_once_its_children_finish(desk: Desk) -> None:
    sandbox.processing_reads(1)
    made = await desk.post(("image", "video", "image"), caption="Our weekend menu")
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    assert await desk.publish(target_id) == "containers_created"
    row = await desk.target(target_id)
    assert row["container_id"] is None  # the carousel waits for its children
    children = [sandbox.container(c) for c in row["child_container_ids"]]
    assert [(c.kind, c.carousel_item) for c in children if c] == [
        ("image", True),
        ("video", True),
        ("image", True),
    ]

    assert await desk.poll(target_id, 1) == "waiting"  # the video child is still processing
    assert (await desk.target(target_id))["container_id"] is None
    assert await desk.poll(target_id, 2) == "published"
    row = await desk.target(target_id)
    parent = sandbox.container(row["container_id"])
    assert parent is not None
    assert parent.kind == "carousel"
    assert list(parent.children) == row["child_container_ids"]  # in the post's order
    assert parent.caption == "Our weekend menu"
    [item] = await desk.rows("SELECT media_type FROM media_items")
    assert item["media_type"] == "carousel"


async def test_a_carousel_parent_is_created_once(
    desk: Desk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A poll that created the carousel but could not read its status keeps its id: the next
    poll reads it again rather than creating a second carousel."""
    original = sandbox.container_status
    failed: list[str] = []

    def flaky(acct: SocialAccount, container_ref: str) -> ContainerStatus:
        row = sandbox.container(container_ref)
        if row is not None and row.kind == "carousel" and not failed:
            failed.append(container_ref)
            raise PlatformError("platform_unavailable", message="HTTP 503")
        return original(acct, container_ref)

    monkeypatch.setattr(sandbox, "container_status", flaky)
    made = await desk.post(("image", "image"))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)

    assert await desk.poll(target_id, 1) == "waiting"
    assert (await desk.target(target_id))["container_id"] == failed[0]
    assert await desk.poll(target_id, 2) == "published"
    assert [c.id for c in sandbox.STATE.containers.values() if c.kind == "carousel"] == failed


# ---------------------------------------------------------------- polling paths


async def test_polls_are_a_minute_apart_then_five_minutes_and_time_out_at_30(
    desk: Desk, monkeypatch: pytest.MonkeyPatch
) -> None:
    sandbox.processing_reads(1000)
    delays: list[tuple[int, float]] = []
    original = publish.enqueue_poll

    async def spy(
        target_id: uuid.UUID, workspace_id: uuid.UUID, n: int, *, delay_s: float = 0
    ) -> bool:
        delays.append((n, delay_s))
        return await original(target_id, workspace_id, n, delay_s=delay_s)

    monkeypatch.setattr(publish, "enqueue_poll", spy)
    made = await desk.post(("video",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)

    outcomes = await desk.poll_until_done(target_id)
    assert outcomes == ["waiting"] * (POLL_MAX - 1) + ["failed"]
    assert delays == [(1, 0)] + [(n, 60.0) for n in range(2, 6)] + [
        (n, 300.0) for n in range(6, 11)
    ]
    assert sum(d for _, d in delays) == 29 * 60  # poll 10 runs 29 minutes after poll 1
    row = await desk.target(target_id)
    assert (row["status"], row["error_message"]) == ("failed", PROCESSING_TIMEOUT_MESSAGE)
    assert (await desk.post_row(made.id))["status"] == "failed"


async def test_a_container_error_fails_with_instagrams_reason_and_notifies(desk: Desk) -> None:
    made = await desk.post(("video",), caption="How we bake")
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    sandbox.fail_next_container("ERROR", "Instagram doesn't support this video format.")
    await desk.publish(target_id)

    assert await desk.poll(target_id, 1) == "failed"
    row = await desk.target(target_id)
    assert (row["status"], row["error_code"], row["error_message"]) == (
        "failed",
        "platform_rejected",
        "Instagram doesn't support this video format.",
    )
    assert (await desk.post_row(made.id))["status"] == "failed"
    [note] = await desk.notifications()
    assert note["type"] == "post_failed"
    assert note["title"] == "Post didn't publish"
    assert note["link"] == f"/schedule/{made.id}"
    assert "@maple.bakery: Instagram doesn't support this video format." in note["body"]
    assert '"How we bake"' in note["body"]
    events = await post_events(desk, made.id)
    assert events[-1]["targets"][0]["error"] == {
        "code": "platform_rejected",
        "message": "Instagram doesn't support this video format.",
    }
    assert sandbox.publish_count() == 0


async def test_an_expired_container_fails(desk: Desk) -> None:
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    sandbox.fail_next_container("EXPIRED")
    await desk.publish(target_id)
    assert await desk.poll(target_id, 1) == "failed"
    assert (await desk.target(target_id))["error_message"] == publish.EXPIRED_REASON


async def test_quota_exhausted_fails_with_the_reason(desk: Desk) -> None:
    """T7.3 done-when: no room in the 24 h limit → the target fails with Instagram's reason and
    no container is created."""
    sandbox.set_quota(100, 100)
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)

    assert await desk.publish(target_id) == "failed"
    row = await desk.target(target_id)
    assert (row["status"], row["error_code"], row["error_message"]) == (
        "failed",
        "platform_rejected",
        "Instagram's daily publishing limit reached",
    )
    assert row["container_id"] is None
    assert row["child_container_ids"] == []
    assert sandbox.STATE.containers == {}
    assert await jobs("poll_container") == []
    assert (await desk.post_row(made.id))["status"] == "failed"
    [note] = await desk.notifications()
    assert "Instagram's daily publishing limit reached" in note["body"]


async def test_the_limit_counts_posts_already_published(desk: Desk) -> None:
    sandbox.set_quota(98, 100)
    first = await desk.post(("image",))
    second = await desk.post(("image",))
    third = await desk.post(("image",))
    targets = [next(iter(p.target_ids.values())) for p in (first, second, third)]
    assert sorted(await desk.dispatch()) == sorted(targets)
    for target_id in targets[:2]:
        await desk.publish(target_id)
        assert await desk.poll(target_id, 1) == "published"
    assert await desk.publish(targets[2]) == "failed"


# ---------------------------------------------------------------- two accounts


async def test_partial_success_across_two_accounts(desk: Desk) -> None:
    first, second = desk.account_ids
    made = await desk.post(("image",), accounts=[first, second])
    ids = made.target_ids
    assert sorted(await desk.dispatch()) == sorted(ids.values())
    assert await desk.publish(ids[first]) == "containers_created"
    assert await desk.publish(ids[second]) == "containers_created"

    sandbox.fail_next("platform_rejected", step="publish")
    assert await desk.poll(ids[first], 1) == "failed"
    assert (await desk.post_row(made.id))["status"] == "publishing"  # the other is still going
    assert await desk.notifications() == []
    assert await desk.poll(ids[second], 1) == "published"

    post = await desk.post_row(made.id)
    assert post["status"] == "partially_published"
    [note] = await desk.notifications()
    assert (note["title"], note["severity"]) == ("Post partly published", "warning")
    assert "@maple.bakery: Sandbox failure: platform_rejected" in note["body"]
    last = (await post_events(desk, made.id))[-1]
    assert last["status"] == "partially_published"
    assert sorted(t["status"] for t in last["targets"]) == ["failed", "published"]


async def test_both_accounts_published_is_published(desk: Desk) -> None:
    made = await desk.post(("image",), accounts=desk.account_ids)
    await desk.dispatch()
    for target_id in made.target_ids.values():
        await desk.publish(target_id)
        await desk.poll(target_id, 1)
    assert (await desk.post_row(made.id))["status"] == "published"
    assert len(await desk.rows("SELECT id FROM media_items")) == 2


async def test_per_account_captions(desk: Desk) -> None:
    first, second = desk.account_ids
    made = await desk.post(
        ("image",), accounts=[first, second], caption_overrides={second: "Cafe caption"}
    )
    await desk.dispatch()
    captions = []
    for account_id in (first, second):
        target_id = made.target_ids[account_id]
        await desk.publish(target_id)
        container = sandbox.container((await desk.target(target_id))["container_id"])
        assert container is not None
        captions.append(container.caption)
    assert captions == ["New arrivals this week #summer", "Cafe caption"]


# ---------------------------------------------------------------- never published twice


async def test_a_lost_publish_answer_is_found_not_published_again(desk: Desk) -> None:
    made = await desk.post(("image",), caption="Lost answer")
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)

    sandbox.lose_next_publish_answer()
    assert await desk.poll(target_id, 1) == "waiting"  # delivery_unknown: the status will tell
    assert sandbox.publish_count() == 1
    assert (await desk.target(target_id))["status"] == "container_created"

    assert await desk.poll(target_id, 2) == "published"  # PUBLISHED → find_published_media
    assert sandbox.publish_count() == 1
    acct = await desk.account(desk.account_ids[0])
    [on_instagram] = sandbox.published(acct.platform_account_id)
    row = await desk.target(target_id)
    assert row["platform_media_id"] == on_instagram.platform_media_id
    assert row["permalink"] == on_instagram.permalink


async def test_a_publish_the_worker_never_stored_is_recovered(desk: Desk) -> None:
    """The worker died between Instagram's answer and our commit: the container reads PUBLISHED
    on the next poll and the post is found, not published again."""
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)
    acct = await desk.account(desk.account_ids[0])
    media_id = sandbox.publish_container(acct, (await desk.target(target_id))["container_id"])

    assert await desk.poll(target_id, 1) == "published"
    assert sandbox.publish_count() == 1
    assert (await desk.target(target_id))["platform_media_id"] == media_id


async def test_a_published_post_not_found_keeps_looking_then_fails_unconfirmed(
    desk: Desk,
) -> None:
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)
    acct = await desk.account(desk.account_ids[0])
    sandbox.publish_container(acct, (await desk.target(target_id))["container_id"])
    sandbox.STATE.published.clear()  # Instagram doesn't list it (yet)

    outcomes = await desk.poll_until_done(target_id)
    assert outcomes == ["waiting"] * (POLL_MAX + publish.EXTRA_POLLS - 1) + ["failed"]
    row = await desk.target(target_id)
    assert row["error_code"] == "delivery_unknown"
    assert "couldn't confirm Instagram published" in row["error_message"]
    assert sandbox.publish_count() == 1


async def test_a_retryable_publish_error_publishes_on_the_next_poll(desk: Desk) -> None:
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)
    sandbox.fail_next("platform_unavailable", step="publish")
    assert await desk.poll(target_id, 1) == "waiting"
    assert await desk.poll(target_id, 2) == "published"
    assert sandbox.publish_count() == 1


async def test_stale_and_repeated_polls_are_skipped(desk: Desk) -> None:
    made = await desk.post(("video",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)
    assert await desk.poll(target_id, 2) == "skipped"  # not poll 1 yet
    assert await desk.poll(target_id, 1) == "waiting"
    assert await desk.poll(target_id, 1) == "skipped"  # a repeat
    assert await desk.publish(target_id) == "skipped"  # containers exist already


# ---------------------------------------------------------------- through Instagram's calls (respx)

CONTAINER = "17889455560051444"
MEDIA = "17920238422030506"


def graph_time(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S+0000")


async def instagram_post(desk: Desk) -> tuple[uuid.UUID, uuid.UUID]:
    account_id = await make_instagram_account(desk.engine, desk.wid)
    made = await desk.post(("image",), accounts=[account_id], caption="Fresh bread")
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    return made.id, target_id


async def test_an_instagram_post_publishes_through_the_graph_calls(
    desk: Desk, api_settings: Settings
) -> None:
    """The jobs with the real adapter: quota, container, status, publish, read-back."""
    post_id, target_id = await instagram_post(desk)
    v = f"{GRAPH}/{api_settings.ig_graph_version}"
    read_back = {**fixture("published_media.json"), "media_type": "IMAGE", "caption": "Fresh bread"}
    with respx.mock(assert_all_called=True) as meta:
        quota = meta.get(f"{v}/{IG_USER}/content_publishing_limit").respond(
            200, json=fixture("publishing_limit.json")
        )
        create = meta.post(f"{v}/{IG_USER}/media").respond(
            200, json=fixture("container_created.json")
        )
        meta.get(f"{v}/{CONTAINER}").respond(200, json=fixture("container_status_finished.json"))
        publish_call = meta.post(f"{v}/{IG_USER}/media_publish").respond(
            200, json=fixture("media_publish.json")
        )
        meta.get(f"{v}/{MEDIA}").respond(200, json=read_back)

        assert await desk.publish(target_id) == "containers_created"
        assert await desk.poll(target_id, 1) == "published"

    assert quota.call_count == 1
    sent = create.calls.last.request
    assert sent.headers["authorization"] == "Bearer IGQVJlong-test-token"
    assert b"f_jpg" in sent.content
    assert publish_call.call_count == 1
    row = await desk.target(target_id)
    assert (row["platform_media_id"], row["permalink"]) == (
        MEDIA,
        "https://www.instagram.com/p/C9new/",
    )
    [item] = await desk.rows("SELECT * FROM media_items")
    assert (item["media_type"], item["published_target_id"]) == ("image", target_id)
    assert (await desk.post_row(post_id))["status"] == "published"


async def test_a_lost_graph_answer_is_found_in_recent_posts(
    desk: Desk, api_settings: Settings
) -> None:
    """media_publish times out after the request went out: the next poll reads PUBLISHED and
    finds the post among the account's recent posts; media_publish is called once."""
    _, target_id = await instagram_post(desk)
    v = f"{GRAPH}/{api_settings.ig_graph_version}"
    with respx.mock(assert_all_called=True) as meta:
        meta.get(f"{v}/{IG_USER}/content_publishing_limit").respond(
            200, json=fixture("publishing_limit.json")
        )
        meta.post(f"{v}/{IG_USER}/media").respond(200, json=fixture("container_created.json"))
        meta.get(f"{v}/{CONTAINER}").mock(
            side_effect=[
                httpx.Response(200, json=fixture("container_status_finished.json")),
                httpx.Response(200, json={"status_code": "PUBLISHED", "id": CONTAINER}),
            ]
        )
        publish_call = meta.post(f"{v}/{IG_USER}/media_publish").mock(
            side_effect=httpx.ReadTimeout("read")
        )
        recent = meta.get(f"{v}/me/media").respond(
            200,
            json={
                "data": [
                    {
                        "id": MEDIA,
                        "caption": "Fresh bread",
                        "media_type": "IMAGE",
                        "media_product_type": "FEED",
                        "permalink": "https://www.instagram.com/p/C9new/",
                        "timestamp": graph_time(datetime.now(UTC)),
                    }
                ]
            },
        )

        assert await desk.publish(target_id) == "containers_created"
        assert await desk.poll(target_id, 1) == "waiting"
        assert await desk.poll(target_id, 2) == "published"

    assert publish_call.call_count == 1
    assert recent.call_count == 1
    row = await desk.target(target_id)
    assert (row["status"], row["platform_media_id"]) == ("published", MEDIA)


# ---------------------------------------------------------------- first comment (FR-PUB-11)


async def test_the_first_comment_is_posted_after_publish(desk: Desk) -> None:
    made = await desk.post(("image",), first_comment="#bakery #sourdough")
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)
    await desk.poll(target_id, 1)
    [job] = await jobs("post_first_comment")
    assert job["queueing_lock"] == f"firstc:{target_id}"
    assert job["args"] == {"target_id": str(target_id), "workspace_id": str(desk.wid)}
    assert (await post_events(desk, made.id))[-1]["targets"][0]["first_comment"] == {
        "status": "pending",
        "platform_comment_id": None,
        "error": None,
    }

    assert await desk.first_comment(target_id) == "posted"
    row = await desk.target(target_id)
    [comment] = list(sandbox.COMMENTS)
    assert (comment.media_ref, comment.text) == (row["platform_media_id"], "#bakery #sourdough")
    assert row["first_comment_platform_id"] == comment.platform_comment_id
    assert (await post_events(desk, made.id))[-1]["targets"][0]["first_comment"]["status"] == (
        "posted"
    )
    assert await desk.first_comment(target_id) == "skipped"  # once
    assert len(sandbox.COMMENTS) == 1


async def test_a_failed_first_comment_leaves_the_post_published(desk: Desk) -> None:
    made = await desk.post(("image",), first_comment="#bakery")
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)
    await desk.poll(target_id, 1)

    sandbox.fail_next("platform_unavailable", step="comment")
    with pytest.raises(PlatformError):  # retried while the job has tries left
        await desk.first_comment(target_id, will_retry=always)
    assert (await desk.target(target_id))["first_comment_error"] is None

    sandbox.fail_next("platform_rejected", step="comment")
    assert await desk.first_comment(target_id) == "failed"
    row = await desk.target(target_id)
    assert row["first_comment_error"] == (
        "The first comment wasn't posted: Sandbox failure: platform_rejected"
    )
    assert row["status"] == "published"
    assert (await desk.post_row(made.id))["status"] == "published"
    assert await desk.notifications() == []


async def test_a_lost_first_comment_answer_is_not_retried(desk: Desk) -> None:
    made = await desk.post(("image",), first_comment="#bakery")
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)
    await desk.poll(target_id, 1)
    sandbox.fail_next("delivery_unknown", step="comment")
    assert await desk.first_comment(target_id, will_retry=always) == "failed"
    assert "couldn't confirm" in (await desk.target(target_id))["first_comment_error"]


# ---------------------------------------------------------------- automations (FR-AUT-18)


async def test_automations_waiting_for_the_post_are_linked(desk: Desk) -> None:
    account_id = desk.account_ids[0]
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    scoped = await make_automation(
        desk.engine,
        workspace_id=desk.wid,
        account_id=account_id,
        trigger="comment_keyword",
        post_scope="selected",
    )
    other_account = await make_automation(
        desk.engine,
        workspace_id=desk.wid,
        account_id=desk.account_ids[1],
        trigger="comment_keyword",
        post_scope="selected",
    )
    for automation_id in (scoped, other_account):
        async with desk.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO automation_posts (workspace_id, automation_id, scheduled_post_id)"
                    " VALUES (:w, :a, :p)"
                ),
                {"w": desk.wid, "a": automation_id, "p": made.id},
            )
    next_post = await make_automation(
        desk.engine,
        workspace_id=desk.wid,
        account_id=account_id,
        trigger="comment_keyword",
        post_scope="next_post",
        activated_at=datetime.now(UTC) - timedelta(hours=1),
    )
    await claim(desk, target_id)
    await desk.publish(target_id)
    assert await desk.poll(target_id, 1) == "published"

    [item] = await desk.rows(
        "SELECT id FROM media_items WHERE published_target_id = :t", t=target_id
    )
    links = {
        r["automation_id"]: (r["media_item_id"], r["scheduled_post_id"])
        for r in await desk.rows("SELECT * FROM automation_posts")
    }
    assert links[scoped] == (item["id"], made.id)
    assert links[other_account] == (None, made.id)  # another account's automation waits
    assert links[next_post] == (item["id"], None)
    last = (await post_events(desk, made.id))[-1]
    assert {a["id"] for a in last["automations"]} == {str(scoped), str(other_account)}


async def test_a_post_sync_stored_first_is_linked_not_duplicated(desk: Desk) -> None:
    """A comment webhook or sync may store the new post before the publish job does."""
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)
    acct = await desk.account(desk.account_ids[0])
    media_id = sandbox.publish_container(acct, (await desk.target(target_id))["container_id"])
    async with desk.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO media_items (workspace_id, social_account_id, platform_media_id,"
                " media_type, posted_at, comments_count) VALUES (:w, :a, :m, 'image', now(), 3)"
            ),
            {"w": desk.wid, "a": desk.account_ids[0], "m": media_id},
        )
    assert await desk.poll(target_id, 1) == "published"
    [item] = await desk.rows("SELECT * FROM media_items")
    assert (item["published_target_id"], item["comments_count"]) == (target_id, 3)


# ---------------------------------------------------------------- claims, retries, accounts


async def test_the_dispatcher_claims_only_due_posts_once(desk: Desk, engine: AsyncEngine) -> None:
    due = await desk.post(("image",))
    future = await desk.post(("image",), publish_at=datetime.now(UTC) + timedelta(hours=1))
    draft = await desk.post(("image",), status="draft")
    other_wid = await make_workspace(engine)
    other_account = await make_account(engine, other_wid)
    theirs = await desk.post(("image",), workspace_id=other_wid, accounts=[other_account])

    claimed = await desk.dispatch()
    assert sorted(claimed) == sorted([*due.target_ids.values(), *theirs.target_ids.values()])
    assert await desk.dispatch() == []  # claimed once
    for made in (future, draft):
        [target_id] = made.target_ids.values()
        assert (await desk.target(target_id))["status"] == "pending"
    assert {j["queueing_lock"] for j in await jobs("publish_target")} == {
        f"pub:{t}" for t in claimed
    }
    theirs_events = [
        p["scheduled_post"]["id"]
        for kind, p in await stream(desk.redis, other_wid)
        if kind == "scheduled_post.updated"
    ]
    assert theirs_events == [str(theirs.id)]  # each workspace hears only about its own post


async def test_publish_now_claims_a_pending_target_itself(desk: Desk) -> None:
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    assert await desk.publish(target_id) == "containers_created"  # enqueued by publish now
    row = await desk.target(target_id)
    assert (row["status"], row["attempts"]) == ("container_created", 1)
    assert await desk.dispatch() == []

    later = await desk.post(("image",), publish_at=datetime.now(UTC) + timedelta(hours=1))
    [later_target] = later.target_ids.values()
    assert await desk.publish(later_target) == "skipped"  # not due: the dispatcher's job


async def test_transient_errors_retry_then_fail(desk: Desk) -> None:
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)

    sandbox.fail_next("platform_unavailable", step="container")
    with pytest.raises(PlatformError):
        await desk.publish(target_id, will_retry=always)
    assert (await desk.target(target_id))["status"] == "publishing"  # stays while retrying

    sandbox.fail_next("platform_unavailable", step="quota")
    assert await desk.publish(target_id) == "failed"  # the last try
    row = await desk.target(target_id)
    assert (row["error_code"], row["error_message"]) == (
        "platform_unavailable",
        "Instagram didn't respond. Try again.",
    )


async def test_a_refused_container_fails_at_once(desk: Desk) -> None:
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    sandbox.fail_next("platform_rejected", step="container")
    assert await desk.publish(target_id, will_retry=always) == "failed"


async def test_an_unreadable_quota_does_not_stop_the_publish(desk: Desk) -> None:
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    sandbox.fail_next("platform_rejected", step="quota")
    assert await desk.publish(target_id) == "containers_created"


async def test_a_disconnected_account_cancels_its_target(desk: Desk) -> None:
    first = desk.account_ids[0]
    made = await desk.post(("image",), accounts=[first])
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.set("social_accounts", first, status="disconnected")
    assert await desk.publish(target_id) == "canceled"
    row = await desk.target(target_id)
    assert (row["status"], row["error_code"]) == ("canceled", "account_disconnected")
    assert (await desk.post_row(made.id))["status"] == "canceled"
    assert await desk.notifications() == []


async def test_an_account_needing_reconnect_fails_its_target(desk: Desk) -> None:
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.set("social_accounts", desk.account_ids[0], status="needs_reconnect")
    assert await desk.publish(target_id) == "failed"
    row = await desk.target(target_id)
    assert row["error_message"] == "@maple.bakery needs reconnecting before it can publish."


async def test_a_dead_token_marks_the_account(desk: Desk) -> None:
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    sandbox.fail_next("account_needs_reconnect", step="container")
    assert await desk.publish(target_id, will_retry=always) == "failed"
    [acct] = await desk.rows(
        "SELECT status FROM social_accounts WHERE id = :id", id=desk.account_ids[0]
    )
    assert acct["status"] == "needs_reconnect"
    types = sorted(n["type"] for n in await desk.notifications())
    assert types == ["account_needs_reconnect", "post_failed"]


# ---------------------------------------------------------------- sweeper (TR-JOB-03)


async def test_the_sweeper_returns_stuck_claims_then_fails_them(desk: Desk) -> None:
    long_ago = datetime.now(UTC) - timedelta(minutes=11)
    made = await desk.post(
        ("image",),
        status="publishing",
        target_status="publishing",
        target_values={"claimed_at": long_ago, "attempts": 1},
    )
    [target_id] = made.target_ids.values()
    assert (await desk.sweep())["reset"] == 1
    row = await desk.target(target_id)
    assert (row["status"], row["claimed_at"]) == ("pending", None)
    assert await desk.dispatch() == [target_id]  # the dispatcher claims it again

    await desk.set("scheduled_post_targets", target_id, claimed_at=long_ago, attempts=3)
    # its publish_target is still waiting (say, for a rate limit): left alone
    assert await desk.sweep() == {"reset": 0, "failed": 0, "requeued": 0}
    await _clear_queue()  # the job is gone
    assert (await desk.sweep())["failed"] == 1
    row = await desk.target(target_id)
    assert (row["status"], row["error_code"]) == ("failed", "internal")
    assert (await desk.post_row(made.id))["status"] == "failed"


async def test_the_sweeper_resumes_a_lost_poll_chain(desk: Desk) -> None:
    made = await desk.post(("video",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)
    await desk.poll(target_id, 1)  # queues poll 2
    later = datetime.now(UTC) + timedelta(minutes=11)
    assert (await desk.sweep(later))["requeued"] == 0  # poll 2 is waiting

    await _clear_queue()  # the chain is lost
    assert (await desk.sweep(later))["requeued"] == 1
    [job] = await jobs("poll_container")
    assert job["queueing_lock"] == f"poll:{target_id}:2"
    assert await desk.poll_until_done(target_id, first=2) == ["waiting", "published"]


async def test_the_sweeper_leaves_fresh_work_alone(desk: Desk) -> None:
    made = await desk.post(("image",))
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    assert await desk.sweep() == {"reset": 0, "failed": 0, "requeued": 0}
    await desk.publish(target_id)
    assert await desk.sweep() == {"reset": 0, "failed": 0, "requeued": 0}


# ---------------------------------------------------------------- the status rule and the sandbox


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["published", "published"], "published"),
        (["published", "failed"], "partially_published"),
        (["published", "canceled"], "partially_published"),
        (["failed", "canceled"], "failed"),
        (["canceled", "canceled"], "canceled"),
        (["published", "container_created"], None),
        (["pending"], None),
        ([], None),
    ],
)
def test_the_post_status_derives_from_its_targets(
    statuses: list[str], expected: str | None
) -> None:
    assert derive_status(statuses) == expected


async def test_published_sandbox_posts_show_up_like_synced_ones(desk: Desk) -> None:
    made = await desk.post(("image",), caption="Shows in sync")
    [target_id] = made.target_ids.values()
    await claim(desk, target_id)
    await desk.publish(target_id)
    await desk.poll(target_id, 1)
    acct = await desk.account(desk.account_ids[0])
    media_id = (await desk.target(target_id))["platform_media_id"]
    listed = history.posts(acct, limit=25)
    assert listed[0].platform_media_id == media_id
    assert len(listed) == 1 + len(history.POSTS)
    assert history.post(acct, media_id).caption == "Shows in sync"
