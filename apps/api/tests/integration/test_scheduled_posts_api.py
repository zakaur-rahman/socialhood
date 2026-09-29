"""T7.1: scheduled posts through the API (F-13, FR-PUB-01, FR-PUB-04, FR-PUB-08, FR-PUB-09,
FR-PUB-10, FR-PUB-14; C-043). Done when: invalid formats are rejected with field errors. Plus:
drafts and the derived format, the checklist and its field names, schedule within
scheduled_posts_monthly (a post counts once), unschedule, reschedule, publish now handing over to
publish_target, Add to queue, duplicate, delete keeping published automation links, bulk actions,
the List view, and other workspaces' accounts, uploads and posts. Every route's isolation is also
covered by the tenancy suite (tests/tenancy)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.jobs import runtime as jobs_runtime
from socialhood.jobs.runtime import Runtime
from socialhood.repositories import scheduled_posts as scheduled_posts_repo
from socialhood.services.scheduled_posts import views
from tests.support.api import Clerk
from tests.support.automations import make_automation, make_media_item
from tests.support.inbox import make_account, make_asset
from tests.support.ingest import jobs
from tests.support.publishing import make_posting_slot, make_scheduled_post
from tests.support.publishing_api import (
    Shop,
    by_key,
    failing,
    iso,
    later,
    open_shop,
    parse,
)


@pytest.fixture
async def shop(app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Shop:
    return await open_shop(app, client, clerk, engine)


def _near(value: str | None, expected: datetime, within: timedelta = timedelta(seconds=5)) -> bool:
    return value is not None and abs(parse(value) - expected) <= within


# ---------------------------------------------------------------- drafts and the derived format


async def test_an_empty_draft_says_what_is_missing(shop: Shop) -> None:
    post = await shop.draft()

    assert (post["status"], post["format"], post["caption"], post["publish_at"]) == (
        "draft",
        None,
        "",
        None,
    )
    assert (post["targets"], post["assets"], post["asset_count"]) == ([], [], 0)
    assert post["ready"] is False
    assert failing(post) == {"targets": "accounts", "asset_ids": "media"}
    # Passing checks appear once, in the contract's order; no time means no publish_at item.
    assert [i["key"] for i in post["checklist"]] == [
        "accounts",
        "media",
        "media_files",
        "caption",
        "hashtags",
        "mentions",
        "publishing_limit",
    ]
    [event] = await shop.events()
    assert event["scheduled_post"]["id"] == post["id"]
    assert event["scheduled_post"]["checklist"] == post["checklist"]


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        (["image"], "image"),
        (["video"], "reel"),
        (["image", "video", "image"], "carousel"),
    ],
)
async def test_the_format_is_derived_from_the_assets(
    shop: Shop, kinds: list[str], expected: str
) -> None:
    assets = [await (shop.image() if kind == "image" else shop.video()) for kind in kinds]

    post = await shop.ready_draft(asset_ids=assets)

    assert post["format"] == expected
    assert [a["id"] for a in post["assets"]] == [str(a) for a in assets]
    assert [a["position"] for a in post["assets"]] == list(range(len(assets)))
    assert post["asset_count"] == len(assets)
    assert post["ready"] is True, post["checklist"]
    first = post["assets"][0]
    assert first["thumbnail_url"].endswith(".jpg")
    assert "/upload/c_limit" in first["thumbnail_url"] or "/upload/so_0" in first["thumbnail_url"]
    assert post["thumbnail_url"] == first["thumbnail_url"]
    if kinds[0] == "video":
        assert "so_0" in first["thumbnail_url"]
        assert first["duration_s"] == 15.0


async def test_a_draft_names_accounts_and_uploads_that_are_not_this_workspaces(
    shop: Shop, engine: AsyncEngine
) -> None:
    from tests.support.inbox import make_workspace

    other = await make_workspace(engine)
    foreign_account = await make_account(engine, other, username="not.yours")
    foreign_asset = await make_asset(engine, workspace_id=other, purpose="post")
    message_upload = await make_asset(engine, workspace_id=shop.wid, purpose="message")
    image = await shop.image()

    errors = await shop.fields(
        "POST",
        "/scheduled-posts",
        {
            "targets": [
                {"social_account_id": str(shop.account_id)},
                {"social_account_id": str(foreign_account)},
                {"social_account_id": str(shop.account_id)},
            ],
            "asset_ids": [str(image), str(foreign_asset), str(message_upload), str(image)],
        },
    )

    assert errors == {
        "targets.1": "Account not found.",
        "targets.2": "This account is already selected.",
        "asset_ids.1": "This file wasn't found. Upload it again.",
        "asset_ids.2": "This file wasn't uploaded for a post.",
        "asset_ids.3": "This file is already in the post.",
    }
    assert await shop.rows("SELECT id FROM scheduled_posts") == []


async def test_schema_limits_are_field_errors(shop: Shop) -> None:
    errors = await shop.fields(
        "POST",
        "/scheduled-posts",
        {"caption": "x" * 2201, "asset_ids": [str(uuid.uuid4()) for _ in range(11)]},
    )
    assert set(errors) == {"caption", "asset_ids"}


async def test_put_replaces_the_post_and_keeps_the_rows_of_kept_accounts(shop: Shop) -> None:
    second = await shop.account("second.shop")
    post = await shop.ready_draft(
        targets=[{"social_account_id": shop.account_id}, {"social_account_id": second}]
    )
    before = {
        r["social_account_id"]: r["id"]
        for r in await shop.rows(
            "SELECT id, social_account_id FROM scheduled_post_targets WHERE scheduled_post_id = :p",
            p=post["id"],
        )
    }
    third = await shop.account("third.shop")
    video = await shop.video()

    out = await shop.ok(
        "PUT",
        f"/scheduled-posts/{post['id']}",
        {
            "targets": [
                {"social_account_id": str(third)},
                {"social_account_id": str(shop.account_id), "caption_override": "Only here"},
            ],
            "asset_ids": [str(video)],
            "caption": "Now a Reel",
            "first_comment": "#reels #linen",
            "publish_at": iso(later(days=3)),
        },
    )

    assert (out["status"], out["format"], out["caption"], out["first_comment"]) == (
        "draft",
        "reel",
        "Now a Reel",
        "#reels #linen",
    )
    # Targets come back in the accounts' order, whatever the body's order.
    assert [t["social_account_id"] for t in out["targets"]] == [str(shop.account_id), str(third)]
    assert out["targets"][0]["caption_override"] == "Only here"
    after = {
        r["social_account_id"]: r["id"]
        for r in await shop.rows(
            "SELECT id, social_account_id FROM scheduled_post_targets WHERE scheduled_post_id = :p",
            p=post["id"],
        )
    }
    assert after[shop.account_id] == before[shop.account_id]
    assert second not in after
    assert out["updated_at"] > post["updated_at"]
    # An empty first comment is none.
    cleared = await shop.ok(
        "PUT", f"/scheduled-posts/{post['id']}", {"first_comment": "", "caption": "x"}
    )
    assert cleared["first_comment"] is None


# ---------------------------------------------------------------- the checklist (FR-PUB-10)


async def test_media_files_are_checked_against_instagrams_limits(shop: Shop) -> None:
    tall = await shop.image(width=1080, height=1920)  # 9:16, a Reel's shape but not a photo's
    wide = await shop.image(width=2000, height=1000)  # 2:1
    heavy = await shop.image(size=9 * 1024 * 1024)
    long_video = await shop.video(duration_s=120)
    square = await shop.image(width=1080, height=1080)

    post = await shop.ready_draft(asset_ids=[square, tall, wide, heavy, long_video])

    assert post["format"] == "carousel"
    assert failing(post) == {
        "asset_ids.1": "media_files",
        "asset_ids.2": "media_files",
        "asset_ids.3": "media_files",
        "asset_ids.4": "media_files",
    }
    messages = {i["field"]: i["message"] for i in by_key(post["checklist"], "media_files")}
    assert "4:5" in messages["asset_ids.1"]
    assert messages["asset_ids.3"] == "Images can be up to 8 MB."
    assert messages["asset_ids.4"] == "Videos can be up to 90 seconds."


async def test_caption_hashtag_and_mention_limits_name_each_text(shop: Shop) -> None:
    many_tags = " ".join(f"#tag{i}" for i in range(31))
    many_mentions = " ".join(f"@friend{i}" for i in range(21))
    second = await shop.account("second.shop")

    post = await shop.ready_draft(
        targets=[
            {"social_account_id": shop.account_id},
            {"social_account_id": second, "caption_override": many_mentions},
        ],
        caption=many_tags + " write to hello@example.com",
        first_comment=many_tags,
    )

    assert failing(post) == {
        "caption": "hashtags",
        "first_comment": "hashtags",
        "targets.1.caption_override": "mentions",
    }
    [hashtags_caption, _] = by_key(post["checklist"], "hashtags")
    assert hashtags_caption["message"] == "Use at most 30 hashtags (now 31)."
    # An email address is not a mention.
    assert by_key(post["checklist"], "caption") == [
        {"key": "caption", "ok": True, "message": "Caption within 2,200 characters", "field": None}
    ]


async def test_accounts_must_be_connected_and_able_to_publish(shop: Shop) -> None:
    reconnect = await shop.account("stale.shop")
    await shop.execute(
        "UPDATE social_accounts SET status = 'needs_reconnect' WHERE id = :a", a=reconnect
    )
    whatsapp = await make_account(
        shop.engine,
        shop.wid,
        platform="whatsapp",
        platform_account_id="1555000111",
        username="shop.whatsapp",
    )

    post = await shop.ready_draft(
        targets=[
            {"social_account_id": shop.account_id},
            {"social_account_id": reconnect},
            {"social_account_id": whatsapp},
        ]
    )

    accounts = {i["field"]: i["message"] for i in by_key(post["checklist"], "accounts")}
    order = [t["social_account_id"] for t in post["targets"]]
    assert order == [str(shop.account_id), str(reconnect), str(whatsapp)]
    assert accounts == {
        "targets.1": "@stale.shop needs reconnecting before it can publish.",
        "targets.2": "@shop.whatsapp can't publish posts.",
    }


async def test_the_publishing_limit_counts_the_accounts_other_posts_that_day(
    shop: Shop, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(views, "PUBLISHING_LIMIT", 2)
    at = later(days=2)
    await make_scheduled_post(
        shop.engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status="scheduled",
        publish_at=at - timedelta(hours=3),
    )
    await make_scheduled_post(
        shop.engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status="scheduled",
        publish_at=at - timedelta(hours=30),  # outside the 24 hours before
    )
    post = await shop.ready_draft(publish_at=at)
    assert post["ready"] is True, post["checklist"]

    await make_scheduled_post(
        shop.engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status="scheduled",
        publish_at=at - timedelta(hours=1),
    )
    again = await shop.ok("GET", f"/scheduled-posts/{post['id']}")

    assert failing(again) == {"targets.0": "publishing_limit"}
    [item] = by_key(again["checklist"], "publishing_limit")
    assert item["message"].startswith("@maple.bakery already has 2 posts")


# ---------------------------------------------------------------- schedule (F-13)


async def test_invalid_formats_are_rejected_with_field_errors(shop: Shop) -> None:
    """T7.1 done-when: scheduling a post without media, or with files Instagram refuses, is a 422
    naming each field; nothing changes."""
    empty = await shop.draft(targets=[{"social_account_id": str(shop.account_id)}])
    errors = await shop.fields(
        "POST", f"/scheduled-posts/{empty['id']}/schedule", {"publish_at": iso(later(days=1))}
    )
    assert errors == {"asset_ids": "Add an image or video."}

    long_video = await shop.video(duration_s=91)
    tall = await shop.image(width=1080, height=1920)
    bad = await shop.ready_draft(asset_ids=[long_video, tall])
    errors = await shop.fields(
        "POST", f"/scheduled-posts/{bad['id']}/schedule", {"publish_at": iso(later(minutes=2))}
    )
    assert set(errors) == {"asset_ids.0", "asset_ids.1", "publish_at"}
    assert errors["publish_at"] == "Pick a time at least 5 minutes from now."

    nothing = await shop.draft()
    errors = await shop.fields(
        "POST", f"/scheduled-posts/{nothing['id']}/schedule", {"publish_at": iso(later(days=1))}
    )
    assert errors == {
        "targets": "Choose at least one account.",
        "asset_ids": "Add an image or video.",
    }
    statuses = await shop.rows("SELECT status FROM scheduled_posts")
    assert {r["status"] for r in statuses} == {"draft"}


async def test_schedule_makes_the_post_scheduled_and_counts_it_once(shop: Shop) -> None:
    post = await shop.ready_draft()
    at = later(days=1).replace(microsecond=0)

    out = await shop.ok("POST", f"/scheduled-posts/{post['id']}/schedule", {"publish_at": iso(at)})

    assert out["status"] == "scheduled"
    assert parse(out["publish_at"]) == at
    assert [t["status"] for t in out["targets"]] == ["pending"]
    assert [i["key"] for i in out["checklist"]][-1] == "publish_at"
    assert out["ready"] is True
    counter = await shop.one(
        "SELECT used, \"limit\" FROM usage_counters WHERE metric = 'scheduled_posts'"
    )
    assert counter == {"used": 1, "limit": 10}

    # Unschedule and schedule again in the same period: still one.
    draft = await shop.ok("POST", f"/scheduled-posts/{post['id']}/unschedule")
    assert (draft["status"], draft["publish_at"]) == ("draft", out["publish_at"])
    await shop.ok("POST", f"/scheduled-posts/{post['id']}/schedule", {"publish_at": iso(at)})
    counter = await shop.one("SELECT used FROM usage_counters WHERE metric = 'scheduled_posts'")
    assert counter["used"] == 1

    billing = await shop.ok("GET", "/billing")
    usage = {u["metric"]: u for u in billing["usage"]}
    assert (usage["scheduled_posts"]["used"], usage["scheduled_posts"]["limit"]) == (1, 10)

    events = await shop.events()
    assert [e["scheduled_post"]["status"] for e in events][-3:] == [
        "scheduled",
        "draft",
        "scheduled",
    ]


async def test_scheduling_past_the_plans_posts_is_402(shop: Shop) -> None:
    first = await shop.scheduled()
    await shop.execute(
        "UPDATE usage_counters SET used = 10"
        " WHERE metric = 'scheduled_posts' AND workspace_id = :w",
        w=shop.wid,
    )
    post = await shop.ready_draft()

    problem = await shop.problem(
        "POST",
        f"/scheduled-posts/{post['id']}/schedule",
        {"publish_at": iso(later(days=1))},
        status=402,
    )

    assert problem["code"] == "quota_exceeded"
    assert problem["detail"] == "Your plan includes 10 scheduled posts a month."
    assert (await shop.one("SELECT status FROM scheduled_posts WHERE id = :p", p=post["id"])) == {
        "status": "draft"
    }
    # A post counted this period moves freely.
    await shop.ok("POST", f"/scheduled-posts/{first['id']}/unschedule")
    await shop.ok(
        "POST", f"/scheduled-posts/{first['id']}/schedule", {"publish_at": iso(later(days=2))}
    )


async def test_a_scheduled_post_can_be_updated_only_while_it_still_passes(shop: Shop) -> None:
    post = await shop.scheduled()
    asset_ids = [a["id"] for a in post["assets"]]
    body = {
        "targets": [{"social_account_id": str(shop.account_id)}],
        "asset_ids": asset_ids,
        "caption": "Updated caption",
        "publish_at": post["publish_at"],
    }

    updated = await shop.ok("PUT", f"/scheduled-posts/{post['id']}", body)
    assert (updated["status"], updated["caption"]) == ("scheduled", "Updated caption")

    errors = await shop.fields(
        "PUT",
        f"/scheduled-posts/{post['id']}",
        {**body, "asset_ids": [], "publish_at": None},
    )
    assert errors == {
        "asset_ids": "Add an image or video.",
        "publish_at": "Pick a time at least 5 minutes from now.",
    }
    row = await shop.one("SELECT caption, format FROM scheduled_posts WHERE id = :p", p=post["id"])
    assert row == {"caption": "Updated caption", "format": "image"}


@pytest.mark.parametrize(
    ("status", "target_status", "message"),
    [
        ("publishing", "publishing", "Publishing started."),
        ("published", "published", "This post was already published."),
        ("partially_published", "published", "This post was already published."),
    ],
)
async def test_a_post_that_started_publishing_cannot_change(
    shop: Shop, status: str, target_status: str, message: str
) -> None:
    made = await make_scheduled_post(
        shop.engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status=status,
        target_status=target_status,
    )
    path = f"/scheduled-posts/{made.id}"
    at = {"publish_at": iso(later(days=1))}

    for method, suffix, body in [
        ("PUT", "", {"caption": "Changed"}),
        ("POST", "/schedule", at),
        ("POST", "/unschedule", None),
        ("POST", "/reschedule", at),
        ("POST", "/queue", None),
        ("POST", "/publish-now", None),
    ]:
        problem = await shop.problem(method, path + suffix, body, status=409)
        assert (problem["code"], problem["detail"]) == ("conflict", message), suffix

    if status == "publishing":
        problem = await shop.problem("DELETE", path, status=409)
        assert problem["detail"] == "Publishing started."
    else:
        await shop.ok("DELETE", path, status=204)


async def test_edit_and_retry_makes_a_failed_post_a_draft_again(shop: Shop) -> None:
    made = await make_scheduled_post(
        shop.engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status="failed",
        target_status="failed",
        target_values={
            "error_code": "platform_rejected",
            "error_message": "The aspect ratio is not supported.",
            "attempts": 3,
            "container_id": "c1",
        },
    )
    got = await shop.ok("GET", f"/scheduled-posts/{made.id}")
    assert got["targets"][0]["error"] == {
        "code": "platform_rejected",
        "message": "The aspect ratio is not supported.",
    }
    problem = await shop.problem(
        "POST",
        f"/scheduled-posts/{made.id}/schedule",
        {"publish_at": iso(later(days=1))},
        status=409,
    )
    assert problem["detail"] == "This post didn't publish. Edit it to try again."

    out = await shop.ok(
        "PUT",
        f"/scheduled-posts/{made.id}",
        {
            "targets": [{"social_account_id": str(shop.account_id)}],
            "asset_ids": [str(a) for a in made.asset_ids],
            "caption": "Second try",
        },
    )

    assert out["status"] == "draft"
    assert out["targets"][0]["status"] == "pending"
    assert out["targets"][0]["error"] is None
    target = await shop.one(
        "SELECT attempts, container_id, error_code FROM scheduled_post_targets WHERE id = :t",
        t=made.target_ids[shop.account_id],
    )
    assert target == {"attempts": 0, "container_id": None, "error_code": None}


# ---------------------------------------------------------------- reschedule and unschedule


async def test_reschedule_moves_a_scheduled_post_at_least_five_minutes_ahead(shop: Shop) -> None:
    post = await shop.scheduled()
    new_at = later(days=4).replace(microsecond=0)

    moved = await shop.ok(
        "POST", f"/scheduled-posts/{post['id']}/reschedule", {"publish_at": iso(new_at)}
    )
    assert (moved["status"], parse(moved["publish_at"])) == ("scheduled", new_at)

    errors = await shop.fields(
        "POST", f"/scheduled-posts/{post['id']}/reschedule", {"publish_at": iso(later(minutes=3))}
    )
    assert errors == {"publish_at": "Pick a time at least 5 minutes from now."}

    draft = await shop.ready_draft()
    problem = await shop.problem(
        "POST",
        f"/scheduled-posts/{draft['id']}/reschedule",
        {"publish_at": iso(new_at)},
        status=409,
    )
    assert problem["detail"] == "This post is a draft. Schedule it instead."


async def test_unscheduling_a_draft_returns_it_as_it_is(shop: Shop) -> None:
    draft = await shop.ready_draft(publish_at=later(days=1))
    out = await shop.ok("POST", f"/scheduled-posts/{draft['id']}/unschedule")
    assert (out["status"], out["publish_at"], out["updated_at"]) == (
        "draft",
        draft["publish_at"],
        draft["updated_at"],
    )


# ---------------------------------------------------------------- publish now (F-13)


async def test_publish_now_hands_every_target_to_the_publish_jobs(shop: Shop, queue: None) -> None:
    second = await shop.account("second.shop")
    post = await shop.ready_draft(
        targets=[{"social_account_id": shop.account_id}, {"social_account_id": second}]
    )

    response = await shop.call("POST", f"/scheduled-posts/{post['id']}/publish-now")

    assert response.status_code == 202, response.text
    out = response.json()
    assert out["status"] == "scheduled"
    assert _near(out["publish_at"], datetime.now(UTC))
    # Publish now skips the 5-minute rule; the post's own checklist says its time has come.
    assert failing(out) == {"publish_at": "publish_at"}
    targets = {
        r["social_account_id"]: r["id"]
        for r in await shop.rows(
            "SELECT id, social_account_id FROM scheduled_post_targets WHERE scheduled_post_id = :p",
            p=post["id"],
        )
    }
    queued = await jobs("publish_target")
    assert sorted((j["queueing_lock"], j["queue_name"]) for j in queued) == sorted(
        (f"pub:{t}", "interactive") for t in targets.values()
    )
    assert {j["args"]["target_id"] for j in queued} == {str(t) for t in targets.values()}
    assert {j["args"]["workspace_id"] for j in queued} == {shop.wid}
    assert (await shop.one("SELECT used FROM usage_counters WHERE metric = 'scheduled_posts'"))[
        "used"
    ] == 1


async def test_publish_now_runs_the_checklist(shop: Shop, queue: None) -> None:
    post = await shop.draft(targets=[{"social_account_id": str(shop.account_id)}])
    errors = await shop.fields("POST", f"/scheduled-posts/{post['id']}/publish-now")
    assert errors == {"asset_ids": "Add an image or video."}
    assert await jobs("publish_target") == []


# ---------------------------------------------------------------- Add to queue (FR-PUB-09)


def _slot_at(days: int, hour: int = 18) -> datetime:
    day = (datetime.now(UTC) + timedelta(days=days)).date()
    return datetime.combine(day, time(hour), tzinfo=UTC)


async def test_add_to_queue_takes_the_next_free_posting_time(shop: Shop) -> None:
    at = _slot_at(2)
    await make_posting_slot(
        shop.engine, workspace_id=shop.wid, account_id=shop.account_id, weekday=at.weekday()
    )
    post = await shop.ready_draft()

    queued = await shop.ok("POST", f"/scheduled-posts/{post['id']}/queue")
    assert (queued["status"], parse(queued["publish_at"])) == ("scheduled", at)

    # That slot is now taken (a post within 30 minutes): the next post goes a week later.
    other = await shop.ready_draft()
    queued = await shop.ok("POST", f"/scheduled-posts/{other['id']}/queue")
    assert parse(queued["publish_at"]) == at + timedelta(weeks=1)

    # Queueing the first post again keeps its own slot.
    again = await shop.ok("POST", f"/scheduled-posts/{post['id']}/queue")
    assert parse(again["publish_at"]) == at


async def test_add_to_queue_needs_a_time_every_account_has_free(shop: Shop) -> None:
    second = await shop.account("second.shop")
    x, y = _slot_at(2), _slot_at(3)
    for day in (x, y):
        await make_posting_slot(
            shop.engine, workspace_id=shop.wid, account_id=shop.account_id, weekday=day.weekday()
        )
    post = await shop.ready_draft(
        targets=[{"social_account_id": shop.account_id}, {"social_account_id": second}]
    )

    errors = await shop.fields("POST", f"/scheduled-posts/{post['id']}/queue")
    assert errors == {"targets.1": "Add posting times for @second.shop first."}

    await make_posting_slot(
        shop.engine, workspace_id=shop.wid, account_id=second, weekday=y.weekday()
    )
    queued = await shop.ok("POST", f"/scheduled-posts/{post['id']}/queue")
    assert parse(queued["publish_at"]) == y


async def test_add_to_queue_without_accounts_is_a_field_error(shop: Shop) -> None:
    post = await shop.draft()
    errors = await shop.fields("POST", f"/scheduled-posts/{post['id']}/queue")
    assert errors == {"targets": "Choose at least one account."}


# ---------------------------------------------------------------- duplicate and delete


async def test_duplicate_copies_everything_but_the_time_and_automations(shop: Shop) -> None:
    second = await shop.account("second.shop")
    post = await shop.scheduled(
        targets=[
            {"social_account_id": shop.account_id},
            {"social_account_id": second, "caption_override": "Hi second"},
        ],
        asset_ids=[await shop.image(), await shop.video()],
        first_comment="#linen",
    )
    automation = await make_automation(
        shop.engine, workspace_id=shop.wid, account_id=shop.account_id, trigger="comment_keyword"
    )
    await shop.execute(
        "INSERT INTO automation_posts (workspace_id, automation_id, scheduled_post_id)"
        " VALUES (:w, :a, :p)",
        w=shop.wid,
        a=automation,
        p=post["id"],
    )
    got = await shop.ok("GET", f"/scheduled-posts/{post['id']}")
    assert [a["id"] for a in got["automations"]] == [str(automation)]
    assert got["automations"][0]["trigger"] == "comment_keyword"

    copy = await shop.ok("POST", f"/scheduled-posts/{post['id']}/duplicate", status=201)

    assert copy["id"] != post["id"]
    assert (copy["status"], copy["publish_at"], copy["automations"]) == ("draft", None, [])
    assert (copy["caption"], copy["first_comment"], copy["format"]) == (
        post["caption"],
        "#linen",
        "carousel",
    )
    assert [a["id"] for a in copy["assets"]] == [a["id"] for a in post["assets"]]
    assert [(t["social_account_id"], t["caption_override"]) for t in copy["targets"]] == [
        (t["social_account_id"], t["caption_override"]) for t in post["targets"]
    ]


async def test_deleting_a_published_post_keeps_the_automations_that_answer_its_comments(
    shop: Shop,
) -> None:
    second = await shop.account("second.shop")
    made = await make_scheduled_post(
        shop.engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status="partially_published",
        target_status="published",
    )
    item = await make_media_item(shop.engine, workspace_id=shop.wid, account_id=shop.account_id)
    target = made.target_ids[shop.account_id]
    await shop.execute(
        "UPDATE media_items SET published_target_id = :t WHERE id = :i", t=target, i=item
    )
    answering = await make_automation(
        shop.engine, workspace_id=shop.wid, account_id=shop.account_id
    )
    waiting = await make_automation(shop.engine, workspace_id=shop.wid, account_id=second)
    await shop.execute(
        "INSERT INTO automation_posts (workspace_id, automation_id, scheduled_post_id,"
        " media_item_id) VALUES (:w, :a, :p, :i), (:w, :b, :p, NULL)",
        w=shop.wid,
        a=answering,
        b=waiting,
        p=made.id,
        i=item,
    )
    got = await shop.ok("GET", f"/scheduled-posts/{made.id}")
    assert got["targets"][0]["post_id"] == str(item)

    await shop.ok("DELETE", f"/scheduled-posts/{made.id}", status=204)

    links = await shop.rows(
        "SELECT automation_id, scheduled_post_id, media_item_id FROM automation_posts"
    )
    assert links == [{"automation_id": answering, "scheduled_post_id": None, "media_item_id": item}]
    assert await shop.one("SELECT published_target_id FROM media_items WHERE id = :i", i=item) == {
        "published_target_id": None
    }
    assert await shop.rows("SELECT id FROM scheduled_posts") == []
    await shop.problem("DELETE", f"/scheduled-posts/{made.id}", status=404)


async def test_a_published_target_shows_its_post_and_first_comment_result(shop: Shop) -> None:
    second = await shop.account("second.shop")
    made = await make_scheduled_post(
        shop.engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id, second],
        status="published",
        target_status="published",
        first_comment="#linen",
    )
    await shop.execute(
        "UPDATE scheduled_post_targets SET first_comment_platform_id = '1799' WHERE id = :t",
        t=made.target_ids[shop.account_id],
    )
    await shop.execute(
        "UPDATE scheduled_post_targets SET first_comment_error = 'Comments are off' WHERE id = :t",
        t=made.target_ids[second],
    )

    got = await shop.ok("GET", f"/scheduled-posts/{made.id}")

    results = [t["first_comment"] for t in got["targets"]]
    assert results == [
        {"status": "posted", "platform_comment_id": "1799", "error": None},
        {"status": "failed", "platform_comment_id": None, "error": "Comments are off"},
    ]
    assert all(t["permalink"] for t in got["targets"])


# ---------------------------------------------------------------- bulk (FR-PUB-14)


async def test_bulk_shift_moves_scheduled_posts_and_skips_the_rest(shop: Shop) -> None:
    soon = await shop.scheduled(at=later(minutes=30))
    later_post = await shop.scheduled(at=later(days=1))
    draft = await shop.ready_draft()
    publishing = await make_scheduled_post(
        shop.engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status="publishing",
        target_status="publishing",
    )

    result = await shop.ok(
        "POST",
        "/scheduled-posts/bulk",
        {
            "ids": [later_post["id"], soon["id"], draft["id"], str(publishing.id)],
            "action": "shift",
            "shift_minutes": -28,
        },
    )

    assert [p["id"] for p in result["updated"]] == [later_post["id"]]
    assert parse(result["updated"][0]["publish_at"]) == parse(later_post["publish_at"]) - (
        timedelta(minutes=28)
    )
    assert result["deleted_ids"] == []
    assert {(s["id"], s["code"]) for s in result["skipped"]} == {
        (soon["id"], "validation_error"),
        (draft["id"], "conflict"),
        (str(publishing.id), "conflict"),
    }
    errors = await shop.fields(
        "POST", "/scheduled-posts/bulk", {"ids": [soon["id"]], "action": "shift"}
    )
    assert set(errors) == {"shift_minutes"}


async def test_bulk_unschedule_and_delete(shop: Shop) -> None:
    scheduled = await shop.scheduled()
    draft = await shop.ready_draft()
    publishing = await make_scheduled_post(
        shop.engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status="publishing",
        target_status="publishing",
    )

    result = await shop.ok(
        "POST",
        "/scheduled-posts/bulk",
        {"ids": [scheduled["id"], draft["id"], str(publishing.id)], "action": "unschedule"},
    )
    assert [(p["id"], p["status"]) for p in result["updated"]] == [
        (scheduled["id"], "draft"),
        (draft["id"], "draft"),
    ]
    assert [(s["id"], s["message"]) for s in result["skipped"]] == [
        (str(publishing.id), "Publishing started.")
    ]

    result = await shop.ok(
        "POST",
        "/scheduled-posts/bulk",
        {"ids": [scheduled["id"], draft["id"], str(publishing.id)], "action": "delete"},
    )
    assert sorted(result["deleted_ids"]) == sorted([scheduled["id"], draft["id"]])
    assert [s["id"] for s in result["skipped"]] == [str(publishing.id)]
    assert [r["id"] for r in await shop.rows("SELECT id FROM scheduled_posts")] == [publishing.id]


async def test_bulk_naming_another_workspaces_post_changes_nothing(
    shop: Shop, engine: AsyncEngine
) -> None:
    from tests.support.inbox import make_workspace

    other = await make_workspace(engine)
    theirs = await make_scheduled_post(engine, workspace_id=other)
    mine = await shop.ready_draft()

    problem = await shop.problem(
        "POST",
        "/scheduled-posts/bulk",
        {"ids": [mine["id"], str(theirs.id)], "action": "delete"},
        status=404,
    )

    assert problem["code"] == "not_found"
    remaining = {r["id"] for r in await shop.rows("SELECT id FROM scheduled_posts")}
    assert remaining == {uuid.UUID(mine["id"]), theirs.id}


# ---------------------------------------------------------------- the List view (UX-SCR-04)


async def test_list_tabs_orders_filters_and_pages(shop: Shop, engine: AsyncEngine) -> None:
    second = await shop.account("second.shop")
    s1 = await shop.scheduled(at=later(days=2))
    s2 = await shop.scheduled(at=later(days=1))
    s3 = await shop.scheduled(at=later(days=3), targets=[{"social_account_id": second}])
    d1 = await shop.ready_draft()
    d2 = await shop.ready_draft()
    old = later(days=-2)
    published = await make_scheduled_post(
        engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status="published",
        target_status="published",
        publish_at=old,
        published_at=old,
    )
    failed = await make_scheduled_post(
        engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status="failed",
        target_status="failed",
        publish_at=old,
    )
    from tests.support.inbox import make_workspace

    other = await make_workspace(engine)
    await make_scheduled_post(engine, workspace_id=other, status="scheduled")

    async def ids(**params: Any) -> list[str]:
        page = await shop.ok("GET", "/scheduled-posts", **params)
        return [p["id"] for p in page["items"]]

    assert await ids() == [s2["id"], s1["id"], s3["id"]]
    assert await ids(view="drafts") == [d2["id"], d1["id"]]
    assert await ids(view="published") == [str(published.id)]
    assert await ids(view="failed") == [str(failed.id)]
    assert await ids(account_ids=[str(second)]) == [s3["id"]]

    first = await shop.ok("GET", "/scheduled-posts", limit=2)
    assert [p["id"] for p in first["items"]] == [s2["id"], s1["id"]]
    rest = await shop.ok("GET", "/scheduled-posts", limit=2, cursor=first["next_cursor"])
    assert [p["id"] for p in rest["items"]] == [s3["id"]]
    assert rest["next_cursor"] is None
    summary = first["items"][0]
    assert set(summary) == {
        "id",
        "status",
        "format",
        "caption",
        "publish_at",
        "published_at",
        "thumbnail_url",
        "asset_count",
        "targets",
        "created_at",
        "updated_at",
    }
    errors = await shop.fields("GET", "/scheduled-posts?cursor=nonsense")
    assert set(errors) == {"cursor"}


async def test_the_composer_reads_a_post_by_id(shop: Shop) -> None:
    post = await shop.ready_draft(first_comment="#linen")
    got = await shop.ok("GET", f"/scheduled-posts/{post['id']}")
    assert got == post
    await shop.problem("GET", f"/scheduled-posts/{uuid.uuid4()}", status=404)


async def test_the_publish_jobs_can_build_the_event_payload(
    shop: Shop, monkeypatch: pytest.MonkeyPatch
) -> None:
    """views.post_out without PlatformDeps (the worker's are used): what scheduled_post.updated
    carries after each publish step (T7.3)."""
    app = shop.app
    worker = Runtime(
        settings=app.state.settings,
        sessionmaker=app.state.sessionmaker,
        redis=app.state.redis,
        http=app.state.http,
    )
    monkeypatch.setattr(jobs_runtime, "runtime", lambda: worker)
    made = await make_scheduled_post(
        shop.engine,
        workspace_id=shop.wid,
        account_ids=[shop.account_id],
        status="publishing",
        target_status="publishing",
    )
    with workspace_scope(uuid.UUID(shop.wid)):
        async with make_sessionmaker(shop.engine)() as session:
            post = await scheduled_posts_repo.get(session, made.id)
            assert post is not None
            out = await views.post_out(session, post)

    assert (out.id, out.status, out.format) == (made.id, "publishing", "image")
    assert [t.status for t in out.targets] == ["publishing"]
    assert out.ready is True  # its time is an hour away
    assert out.checklist[0].message == "Publishing to @maple.bakery"
