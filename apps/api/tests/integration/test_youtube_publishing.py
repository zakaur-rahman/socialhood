"""C-196: YouTube publishing against a fake YouTube. The direct route (start: the session, the
Origin header, the daily count, mixed posts, the open-upload cap; complete: the channel check,
scheduling and "now"; edits, moves, unscheduling and deleting through the sync job; the 24-hour
expiry; the dispatcher's read-back), the media route (streaming with a resume after a cut,
processing, a lost answer never uploading twice, a processing failure, the daily limit moving the
post to the next day), and the per-target options."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks import publishing as publish_jobs
from socialhood.platforms.buckets import YOUTUBE_UPLOADS, google_day, next_google_day
from socialhood.platforms.deps import deps_from
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.youtube.fake import SESSION_PREFIX, FakeYouTube
from socialhood.services.post_publishing import publish, youtube_direct, youtube_media
from socialhood.services.scheduled_posts import views as scheduled_post_views
from tests.support.api import WEB, Clerk
from tests.support.ingest import jobs
from tests.support.publishing_api import Shop, failing, iso, later, open_shop
from tests.support.youtube import OPTIONS, clear_upload_quota, make_channel

MiB = 1024 * 1024
SOURCE = "https://res.cloudinary.com/demo/video/upload/sample.mp4"


def never(error: PlatformError) -> bool:
    return False


def always(error: PlatformError) -> bool:
    return True


@dataclass
class Tube:
    shop: Shop
    app: FastAPI
    engine: AsyncEngine
    fake: FakeYouTube
    channel: uuid.UUID
    clerk: Clerk

    @property
    def wid(self) -> uuid.UUID:
        return uuid.UUID(self.shop.wid)

    @property
    def maker(self) -> Any:
        return make_sessionmaker(self.engine)

    @property
    def deps(self) -> Any:
        return deps_from(self.app.state.http, self.app.state.settings)

    @property
    def redis(self) -> Any:
        return self.app.state.redis

    async def draft(self, *, options: dict[str, Any] | None = None, **body: Any) -> dict[str, Any]:
        body.setdefault(
            "targets", [{"social_account_id": self.channel, "options": options or OPTIONS}]
        )
        body.setdefault("caption", "How we fold the dough #baking")
        return await self.shop.draft(**body)

    async def start(self, post_id: str, **body: Any) -> httpx.Response:
        payload = {
            "target_id": str(self.channel),
            "file_size": 3 * MiB,
            "content_type": "video/mp4",
            **body,
        }
        return await self.shop.call("POST", f"/scheduled-posts/{post_id}/youtube-upload", payload)

    async def complete(self, post_id: str, video_id: str) -> httpx.Response:
        return await self.shop.call(
            "POST",
            f"/scheduled-posts/{post_id}/youtube-upload/complete",
            {"target_id": str(self.channel), "video_id": video_id},
        )

    async def uploaded(self, **draft: Any) -> tuple[dict[str, Any], str]:
        """A draft, its upload opened, the file sent and completed: (the post, the video id)."""
        post = await self.draft(**draft)
        opened = await self.start(post["id"])
        assert opened.status_code == 201, opened.text
        video = self.fake.finish_upload(opened.json()["upload_url"])
        done = await self.complete(post["id"], video.id)
        assert done.status_code == 200, done.text
        return done.json(), video.id

    async def target(self, post_id: str) -> dict[str, Any]:
        return await self.shop.one(
            "SELECT * FROM scheduled_post_targets WHERE scheduled_post_id = :p"
            " AND social_account_id = :a",
            p=uuid.UUID(post_id),
            a=self.channel,
        )

    # ---- the jobs' bodies

    async def sync(self, target_id: uuid.UUID, video_id: str) -> str:
        with workspace_scope(self.wid):
            return await youtube_direct.sync(
                self.maker,
                self.redis,
                self.deps,
                target_id=target_id,
                account_id=self.channel,
                video_id=video_id,
            )

    async def run_syncs(self) -> list[str]:
        out = []
        for job in await jobs("sync_youtube_video"):
            args = job["args"]
            out.append(await self.sync(uuid.UUID(args["target_id"]), args["video_id"]))
        return out

    async def publish(self, target_id: uuid.UUID, **kw: Any) -> str:
        with workspace_scope(self.wid):
            return await publish.publish_target(
                self.maker, self.redis, self.deps, target_id=target_id, will_retry=never, **kw
            )

    async def upload(
        self, target_id: uuid.UUID, will_retry: Callable[[PlatformError], bool] = never
    ) -> str:
        with workspace_scope(self.wid):
            return await youtube_media.upload(
                self.maker, self.redis, self.deps, target_id=target_id, will_retry=will_retry
            )

    async def poll(self, target_id: uuid.UUID, n: int) -> str:
        with workspace_scope(self.wid):
            return await publish.poll_container(
                self.maker, self.redis, self.deps, target_id=target_id, n=n
            )


@pytest.fixture
async def tube(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    queue: None,
    fake_youtube: FakeYouTube,
    monkeypatch: pytest.MonkeyPatch,
) -> Tube:
    await clear_upload_quota(app.state.redis)
    shop = await open_shop(app, client, clerk, engine)
    channel = await make_channel(engine, shop.wid)
    deps = deps_from(app.state.http, app.state.settings)
    # The jobs build the post's events with the worker's deps; use the test settings' instead.
    monkeypatch.setattr(scheduled_post_views, "_worker_deps", lambda: deps)
    return Tube(shop, app, engine, fake_youtube, channel, clerk)


def channel_of(tube: Tube, post: dict[str, Any]) -> dict[str, Any]:
    """The post's YouTube target (targets come in the accounts' order)."""
    [target] = [t for t in post["targets"] if t["social_account_id"] == str(tube.channel)]
    return target


async def used(tube: Tube) -> int:
    key = f"bucket:{YOUTUBE_UPLOADS}:{google_day(datetime.now(UTC))}"
    return int(await tube.redis.get(key) or 0)


# ---------------------------------------------------------------- options and the checklist


async def test_options_are_a_youtube_channel_s_only(tube: Tube) -> None:
    fields = await tube.shop.fields(
        "POST",
        "/scheduled-posts",
        {"targets": [{"social_account_id": str(tube.shop.account_id), "options": OPTIONS}]},
    )
    assert fields == {"targets.0.options": "Only a YouTube channel takes these options."}
    missing_kids = {k: v for k, v in OPTIONS.items() if k != "made_for_kids"}
    response = await tube.shop.call(
        "POST",
        "/scheduled-posts",
        {"targets": [{"social_account_id": str(tube.channel), "options": missing_kids}]},
    )
    assert response.status_code == 422  # no default for "made for kids"


async def test_a_youtube_only_draft_goes_straight_to_youtube(tube: Tube) -> None:
    bare = await tube.shop.draft(targets=[{"social_account_id": tube.channel}])
    assert failing(bare) == {"targets.0.options": "youtube", "targets.0": "youtube"}

    post = await tube.draft()
    assert post["format"] == "reel"  # one video, which is on YouTube rather than in the tray
    [target] = post["targets"]
    assert target["options"]["title"] == OPTIONS["title"]
    assert target["youtube"] == {
        "route": "direct",
        "state": "waiting_for_file",
        "video_id": None,
        "upload_expires_at": None,
        "url": None,
    }
    assert failing(post) == {"targets.0": "youtube"}  # only the upload is missing


# ---------------------------------------------------------------- start


async def test_start_opens_a_private_session_with_the_publish_time(tube: Tube) -> None:
    at = later(hours=3)
    post = await tube.draft(publish_at=at)
    response = await tube.start(post["id"])
    assert response.status_code == 201, response.text
    session = response.json()
    assert session["upload_url"].startswith(SESSION_PREFIX)
    assert session["chunk_bytes"] == 8 * MiB
    assert "fake-yt" not in response.text  # the channel's token never leaves the API
    [opened] = tube.fake.named("open_session")
    assert opened["origin"] == WEB.rstrip("/")  # the browser PUTs to the session itself
    assert opened["size"] == 3 * MiB
    meta = opened["metadata"]
    assert (meta["privacy"], meta["publish_at"]) == ("private", iso(at))
    assert (meta["title"], meta["description"]) == (OPTIONS["title"], post["caption"])
    assert (meta["made_for_kids"], meta["synthetic_media"]) == (False, False)
    assert await used(tube) == 1

    got = await tube.shop.ok("GET", f"/scheduled-posts/{post['id']}")
    youtube = got["targets"][0]["youtube"]
    assert youtube["state"] == "uploading"
    assert youtube["upload_expires_at"] is not None
    row = await tube.target(post["id"])
    assert row["container_id"] == session["upload_url"]


async def test_now_uploads_with_the_chosen_privacy(tube: Tube) -> None:
    post = await tube.draft(options={**OPTIONS, "privacy": "unlisted"})
    assert (await tube.start(post["id"])).status_code == 201
    [opened] = tube.fake.named("open_session")
    assert (opened["metadata"]["privacy"], opened["metadata"]["publish_at"]) == ("unlisted", None)


async def test_posts_to_several_platforms_use_the_media_tray(tube: Tube) -> None:
    post = await tube.draft(
        targets=[
            {"social_account_id": tube.channel, "options": OPTIONS},
            {"social_account_id": tube.shop.account_id},
        ]
    )
    problem = await tube.shop.problem(
        "POST",
        f"/scheduled-posts/{post['id']}/youtube-upload",
        {"target_id": str(tube.channel), "file_size": 10, "content_type": "video/mp4"},
        status=409,
    )
    assert problem["detail"] == "Posts to several platforms use the media tray."
    assert channel_of(tube, post)["youtube"]["route"] == "media"
    assert tube.fake.inserts == 0


async def test_a_time_under_a_minute_away_is_refused(tube: Tube) -> None:
    post = await tube.draft(publish_at=later(seconds=20))
    assert (await tube.start(post["id"])).status_code == 422


async def test_a_workspace_has_at_most_three_open_uploads(tube: Tube) -> None:
    for _ in range(3):
        post = await tube.draft()
        assert (await tube.start(post["id"])).status_code == 201
    fourth = await tube.draft()
    response = await tube.start(fourth["id"])
    assert response.status_code == 409
    assert "3 YouTube uploads" in response.json()["detail"]


async def test_the_daily_limit_refuses_with_the_reset_time(tube: Tube) -> None:
    now = datetime.now(UTC)
    await tube.redis.set(f"bucket:{YOUTUBE_UPLOADS}:{google_day(now)}", 100)
    post = await tube.draft()
    response = await tube.start(post["id"])
    assert response.status_code == 429
    assert response.json()["detail"].startswith(
        "YouTube's daily upload limit is reached. Try again after "
    )
    assert int(response.headers["Retry-After"]) > 0
    assert tube.fake.inserts == 0


async def test_a_session_that_fails_to_open_gives_its_count_back(tube: Tube) -> None:
    tube.fake.fail_on("open_session", PlatformError("platform_unavailable"))
    post = await tube.draft()
    assert (await tube.start(post["id"])).status_code == 503
    assert await used(tube) == 0


# ---------------------------------------------------------------- complete


async def test_complete_checks_the_channel_and_schedules_the_post(tube: Tube) -> None:
    at = later(hours=2)
    post = await tube.draft(publish_at=at)
    opened = (await tube.start(post["id"])).json()

    unknown = await tube.complete(post["id"], "nosuchvideo")
    assert unknown.status_code == 422
    assert unknown.json()["errors"][0]["field"] == "video_id"

    video = tube.fake.finish_upload(opened["upload_url"])
    done = await tube.complete(post["id"], video.id)
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "scheduled"
    youtube = body["targets"][0]["youtube"]
    assert (youtube["state"], youtube["video_id"]) == ("scheduled", video.id)
    assert youtube["url"] == f"https://www.youtube.com/watch?v={video.id}"
    assert youtube["upload_expires_at"] is None
    assert body["ready"] is True
    # The same answer again changes nothing.
    again = await tube.complete(post["id"], video.id)
    assert again.status_code == 200
    assert tube.fake.inserts == 1


async def test_another_channel_s_video_is_refused(tube: Tube) -> None:
    post = await tube.draft()
    opened = (await tube.start(post["id"])).json()
    video = tube.fake.finish_upload(opened["upload_url"])
    tube.fake.videos[video.id] = replace(video, channel_id="UCsomeoneElse")
    response = await tube.complete(post["id"], video.id)
    assert response.status_code == 422


async def test_now_publishes_once_the_upload_is_done(tube: Tube) -> None:
    post, _video_id = await tube.uploaded()
    assert post["status"] == "scheduled"
    published_at = datetime.fromisoformat(post["publish_at"].replace("Z", "+00:00"))
    assert abs(published_at - datetime.now(UTC)) < timedelta(seconds=30)
    [job] = await jobs("publish_target")  # handed over as Publish now does
    target = await tube.target(post["id"])
    assert job["args"]["target_id"] == str(target["id"])


# ---------------------------------------------------------------- after the upload


async def test_edits_moves_and_unscheduling_update_the_video(tube: Tube) -> None:
    at = later(days=1)
    post, video_id = await tube.uploaded(publish_at=at)
    assert await tube.run_syncs() == ["unchanged"]  # complete's check: nothing differs

    body = {
        "targets": [
            {"social_account_id": str(tube.channel), "options": {**OPTIONS, "title": "New title"}}
        ],
        "caption": "New description",
        "publish_at": iso(at),
    }
    await tube.shop.ok("PUT", f"/scheduled-posts/{post['id']}", body)
    outcomes = await tube.run_syncs()
    assert "updated" in outcomes
    sent = tube.fake.metadata[video_id]
    assert (sent["title"], sent["description"], sent["privacy"]) == (
        "New title",
        "New description",
        "private",
    )
    assert sent["publish_at"] == iso(at)

    moved = later(days=2)
    await tube.shop.ok(
        "POST", f"/scheduled-posts/{post['id']}/reschedule", {"publish_at": iso(moved)}
    )
    await tube.run_syncs()
    assert tube.fake.metadata[video_id]["publish_at"] == iso(moved)

    await tube.shop.ok("POST", f"/scheduled-posts/{post['id']}/unschedule")
    await tube.run_syncs()
    # A draft's video waits privately: YouTube must not publish it at the old time.
    held = tube.fake.metadata[video_id]
    assert (held["privacy"], held["publish_at"]) == ("private", None)
    updates = len(tube.fake.named("update"))
    await tube.run_syncs()
    assert len(tube.fake.named("update")) == updates  # nothing differs: no 50-unit call


async def test_deleting_the_post_deletes_its_private_video(tube: Tube) -> None:
    post, video_id = await tube.uploaded(publish_at=later(days=1))
    await tube.shop.ok("DELETE", f"/scheduled-posts/{post['id']}", status=204)
    assert "deleted" in await tube.run_syncs()
    assert tube.fake.deleted == [video_id]


async def test_adding_instagram_moves_the_post_to_the_tray(tube: Tube) -> None:
    post, video_id = await tube.uploaded(publish_at=later(days=1))
    await tube.shop.ok("POST", f"/scheduled-posts/{post['id']}/unschedule")
    body = {
        "targets": [
            {"social_account_id": str(tube.channel), "options": OPTIONS},
            {"social_account_id": str(tube.shop.account_id)},
        ],
        "caption": "Now on Instagram too",
    }
    out = await tube.shop.ok("PUT", f"/scheduled-posts/{post['id']}", body)
    youtube = channel_of(tube, out)["youtube"]
    assert (youtube["route"], youtube["video_id"]) == ("media", None)
    assert "deleted" in await tube.run_syncs()
    assert tube.fake.deleted == [video_id]


async def test_a_public_video_is_never_deleted(tube: Tube) -> None:
    post, video_id = await tube.uploaded(publish_at=later(days=1))
    tube.fake.videos[video_id] = replace(tube.fake.videos[video_id], privacy="public")
    await tube.shop.ok("DELETE", f"/scheduled-posts/{post['id']}", status=204)
    assert await tube.run_syncs() == ["skipped"]
    assert tube.fake.deleted == []


async def test_an_unfinished_upload_expires_after_a_day(tube: Tube) -> None:
    post = await tube.draft(publish_at=later(days=2))
    assert (await tube.start(post["id"])).status_code == 201
    await tube.shop.execute(
        "UPDATE scheduled_post_targets SET upload_expires_at = now() - interval '1 minute'"
    )
    assert await publish_jobs.expire_direct_uploads(tube.maker, tube.redis) == 1
    got = await tube.shop.ok("GET", f"/scheduled-posts/{post['id']}")
    target = got["targets"][0]
    assert got["status"] == "draft"
    assert target["error"] == {
        "code": "upload_expired",
        "message": "The upload didn't finish. Upload the video again.",
    }
    assert target["youtube"]["state"] == "waiting_for_file"
    assert await publish_jobs.expire_direct_uploads(tube.maker, tube.redis) == 0


# ---------------------------------------------------------------- at the publish time


async def _due(tube: Tube, post: dict[str, Any]) -> tuple[uuid.UUID, datetime]:
    at = datetime.fromisoformat(post["publish_at"].replace("Z", "+00:00"))
    when = at + timedelta(minutes=1)
    target = await tube.target(post["id"])
    assert target["id"] in await publish_jobs.dispatch_due(tube.maker, tube.redis, when)
    return target["id"], when


async def test_the_dispatcher_reads_a_direct_video_back(tube: Tube) -> None:
    post, video_id = await tube.uploaded(publish_at=later(hours=1))
    target_id, when = await _due(tube, post)
    assert await tube.publish(target_id, now=when) == "containers_created"
    assert tube.fake.named("update") == []  # public: YouTube's own publishAt does it
    assert tube.fake.inserts == 1  # nothing uploaded again
    # YouTube's time came: the video is public.
    tube.fake.videos[video_id] = replace(
        tube.fake.videos[video_id], publish_at=datetime.now(UTC) - timedelta(seconds=5)
    )
    assert await tube.poll(target_id, 1) == "published"
    row = await tube.target(post["id"])
    assert (row["status"], row["platform_media_id"]) == ("published", video_id)
    assert row["permalink"] == f"https://www.youtube.com/watch?v={video_id}"
    [item] = await tube.shop.rows(
        "SELECT media_type FROM media_items WHERE published_target_id = :t", t=target_id
    )
    assert item["media_type"] == "video"
    assert await jobs("post_first_comment") == []


async def test_an_unlisted_short_is_set_unlisted_at_its_time(tube: Tube) -> None:
    options = {**OPTIONS, "privacy": "unlisted", "format": "short"}
    post, video_id = await tube.uploaded(publish_at=later(hours=1), options=options)
    target_id, when = await _due(tube, post)
    assert await tube.publish(target_id, now=when) == "containers_created"
    [update] = tube.fake.named("update")
    assert (update["metadata"]["privacy"], update["metadata"]["publish_at"]) == ("unlisted", None)
    assert await tube.poll(target_id, 1) == "published"
    row = await tube.target(post["id"])
    assert row["permalink"] == f"https://www.youtube.com/shorts/{video_id}"
    [item] = await tube.shop.rows(
        "SELECT media_type FROM media_items WHERE published_target_id = :t", t=target_id
    )
    assert item["media_type"] == "reel"


# ---------------------------------------------------------------- the media route


def _source(tube: Tube, data: bytes) -> list[str | None]:
    """Storage serves ``data`` (Range requests honoured); returns the Range headers seen."""
    seen: list[str | None] = []

    def respond(request: httpx.Request) -> httpx.Response:
        rng = request.headers.get("range")
        seen.append(rng)
        if rng:
            start = int(rng.removeprefix("bytes=").split("-")[0])
            return httpx.Response(206, content=data[start:])
        return httpx.Response(200, content=data)

    tube.clerk.router.get(SOURCE).mock(side_effect=respond)
    return seen


async def _media_post(tube: Tube, size: int, **options: Any) -> tuple[dict[str, Any], uuid.UUID]:
    video = await tube.shop.video(size=size)
    post = await tube.draft(
        targets=[
            {"social_account_id": tube.channel, "options": {**OPTIONS, **options}},
            {"social_account_id": tube.shop.account_id},
        ],
        asset_ids=[video],
    )
    assert post["ready"] is True, post["checklist"]
    scheduled = await tube.shop.ok(
        "POST", f"/scheduled-posts/{post['id']}/schedule", {"publish_at": iso(later(hours=1))}
    )
    target_id, _when = await _due(tube, scheduled)
    return scheduled, target_id


async def test_the_media_route_streams_from_storage_and_resumes_after_a_cut(tube: Tube) -> None:
    piece = 256 * 1024
    data = bytes(range(256)) * ((2 * piece + 1000) // 256 + 1)
    data = data[: 2 * piece + 1000]
    seen = _source(tube, data)
    tube.fake.chunk_bytes = piece
    tube.fake.processing_reads = 1
    post, target_id = await _media_post(tube, len(data))

    assert await tube.publish(target_id) == "waiting"
    row = await tube.target(post["id"])
    assert row["container_id"].startswith(SESSION_PREFIX)  # kept before a byte goes
    [job] = await jobs("upload_youtube_video")
    assert (job["queue_name"], job["args"]["target_id"]) == ("bulk", str(target_id))
    [opened] = tube.fake.named("open_session")
    assert (opened["metadata"]["privacy"], opened["metadata"]["publish_at"]) == ("public", None)

    tube.fake.lose_next_answer()  # the first piece arrives; its answer doesn't
    with pytest.raises(PlatformError):
        await tube.upload(target_id, will_retry=always)
    assert await tube.upload(target_id) == "containers_created"
    assert seen == [None, f"bytes={piece}-"]  # the retry went on from what YouTube held
    assert tube.fake.inserts == 1
    starts = [call["start"] for call in tube.fake.named("put_chunk")]
    assert starts == [0, piece, 2 * piece]

    assert await tube.poll(target_id, 1) == "waiting"  # YouTube is processing
    assert await tube.poll(target_id, 2) == "published"
    row = await tube.target(post["id"])
    assert row["permalink"].startswith("https://www.youtube.com/watch?v=")


async def test_a_lost_last_answer_never_uploads_twice(tube: Tube) -> None:
    data = b"x" * 1000
    _source(tube, data)
    post, target_id = await _media_post(tube, len(data))
    assert await tube.publish(target_id) == "waiting"
    tube.fake.lose_next_answer()
    with pytest.raises(PlatformError):
        await tube.upload(target_id, will_retry=always)
    tube.fake.expire_sessions()  # and the session is gone too
    assert await tube.upload(target_id) == "containers_created"
    assert tube.fake.inserts == 1  # found among the channel's uploads by title and time
    [video_id] = tube.fake.videos
    assert (await tube.target(post["id"]))["container_id"] == video_id


async def test_a_video_youtube_can_t_process_fails_naming_youtube(tube: Tube) -> None:
    data = b"y" * 1000
    _source(tube, data)
    post, target_id = await _media_post(tube, len(data))
    await tube.publish(target_id)
    await tube.upload(target_id)
    [video_id] = tube.fake.videos
    tube.fake.fail_processing(video_id)
    assert await tube.poll(target_id, 1) == "failed"
    row = await tube.target(post["id"])
    assert row["error_message"] == "YouTube couldn't process the video (codec)."


async def test_the_daily_limit_moves_a_media_post_to_the_next_day(tube: Tube) -> None:
    video = await tube.shop.video(size=1000)
    post = await tube.draft(
        targets=[
            {"social_account_id": tube.channel, "options": OPTIONS},
            {"social_account_id": tube.shop.account_id},
        ],
        asset_ids=[video],
    )
    scheduled = await tube.shop.ok(
        "POST", f"/scheduled-posts/{post['id']}/schedule", {"publish_at": iso(later(hours=1))}
    )
    when = datetime.fromisoformat(scheduled["publish_at"].replace("Z", "+00:00")) + timedelta(
        minutes=1
    )
    await tube.redis.set(f"bucket:{YOUTUBE_UPLOADS}:{google_day(when)}", 100)
    assert await publish_jobs.dispatch_due(tube.maker, tube.redis, when) == []
    row = await tube.shop.one(
        "SELECT status, publish_at FROM scheduled_posts WHERE id = :p", p=uuid.UUID(post["id"])
    )
    assert row["status"] == "scheduled"  # moved, not failed
    assert row["publish_at"] == next_google_day(when) + timedelta(minutes=1)
    [note] = await tube.shop.rows(
        "SELECT title, body FROM notifications WHERE dedupe_key LIKE 'youtube_moved:%'"
    )
    assert note["title"] == "Post moved to tomorrow"
    assert "YouTube's daily upload limit is reached" in note["body"]


# ---------------------------------------------------------------- the sandbox channel


async def test_the_sandbox_channel_completes_a_direct_upload(
    tube: Tube, client: httpx.AsyncClient
) -> None:
    sandbox = await tube.shop.account("sandbox.channel", platform="youtube")
    post = await tube.shop.draft(
        targets=[{"social_account_id": sandbox, "options": OPTIONS}], caption="Sandbox"
    )
    opened = await tube.shop.call(
        "POST",
        f"/scheduled-posts/{post['id']}/youtube-upload",
        {"target_id": str(sandbox), "file_size": 600 * 1024, "content_type": "video/mp4"},
    )
    assert opened.status_code == 201, opened.text
    session = opened.json()
    assert session["chunk_bytes"] == 512 * 1024
    path = session["upload_url"].split("://", 1)[1].split("/", 1)[1]
    first = await client.put(
        f"/{path}", content=b"a" * 512 * 1024, headers={"Content-Range": "bytes 0-524287/614400"}
    )
    assert (first.status_code, first.headers["Range"]) == (308, "bytes=0-524287")
    last = await client.put(
        f"/{path}",
        content=b"b" * (614400 - 524288),
        headers={"Content-Range": "bytes 524288-614399/614400"},
    )
    assert last.status_code == 200
    video_id = last.json()["id"]
    assert video_id.startswith("sandbox_yt_")
    done = await tube.shop.call(
        "POST",
        f"/scheduled-posts/{post['id']}/youtube-upload/complete",
        {"target_id": str(sandbox), "video_id": video_id},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "scheduled"
