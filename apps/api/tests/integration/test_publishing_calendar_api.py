"""T7.1: the content calendar, posting times, hashtag groups and the media library through the API
(FR-PUB-08, FR-PUB-09, FR-PUB-12, FR-PUB-13, FR-SMS-02, UX-SCR-04, UX-SCR-14; C-043). Other
workspaces' rows never show; every route's isolation is also covered by the tenancy suite."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.support.api import Clerk
from tests.support.inbox import make_account, make_asset, make_scheduled, make_thread
from tests.support.publishing import make_hashtag_group, make_posting_slot, make_scheduled_post
from tests.support.publishing_api import Shop, later, open_shop, parse


@pytest.fixture
async def shop(app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine) -> Shop:
    return await open_shop(app, client, clerk, engine)


def _day(days: int) -> date:
    return (datetime.now(UTC) + timedelta(days=days)).date()


def _at(days: int, hour: int = 18) -> datetime:
    return datetime.combine(_day(days), time(hour), tzinfo=UTC)


# ---------------------------------------------------------------- calendar (FR-PUB-08)


async def test_the_range_is_at_most_42_days_and_in_order(shop: Shop) -> None:
    start = _day(0)
    ok = await shop.ok(
        "GET", "/calendar", **{"from": start.isoformat(), "to": (start + timedelta(41)).isoformat()}
    )
    assert (ok["start"], ok["timezone"]) == (start.isoformat(), "UTC")

    too_long = await shop.problem(
        "GET",
        "/calendar",
        status=422,
        **{"from": start.isoformat(), "to": (start + timedelta(42)).isoformat()},
    )
    assert too_long["errors"] == [{"field": "to", "message": "Show at most 42 days at a time."}]
    backwards = await shop.problem(
        "GET",
        "/calendar",
        status=422,
        **{"from": start.isoformat(), "to": (start - timedelta(1)).isoformat()},
    )
    assert [e["field"] for e in backwards["errors"]] == ["to"]


async def test_the_calendar_shows_posts_messages_and_free_slots(
    shop: Shop, engine: AsyncEngine
) -> None:
    second = await shop.account("second.shop")
    draft_with_time = await shop.ready_draft(publish_at=later(days=1))
    scheduled = await shop.scheduled(at=_at(2, 9))
    await shop.scheduled(at=later(days=20))  # after the range
    await shop.ready_draft()  # a draft without a time is not on the calendar
    on_second = await shop.scheduled(at=_at(3, 9), targets=[{"social_account_id": second}])
    thread = await make_thread(engine, workspace_id=shop.wid, account_id=shop.account_id)
    dm = await make_scheduled(engine, workspace_id=shop.wid, conversation_id=thread.conversation_id)
    await make_scheduled(
        engine,
        workspace_id=shop.wid,
        conversation_id=thread.conversation_id,
        status="canceled",
    )
    free_day, busy_day = _at(4), _at(5)
    for day in (free_day, busy_day):
        await make_posting_slot(
            engine, workspace_id=shop.wid, account_id=shop.account_id, weekday=day.weekday()
        )
    busy = await shop.scheduled(at=busy_day + timedelta(minutes=20))  # takes that day's slot
    from tests.support.inbox import make_workspace

    other = await make_workspace(engine)
    await make_scheduled_post(engine, workspace_id=other, status="scheduled", publish_at=_at(2))
    range_ = {"from": _day(0).isoformat(), "to": _day(6).isoformat()}

    cal = await shop.ok("GET", "/calendar", **range_)

    post_ids = [p["id"] for p in cal["posts"]]
    assert set(post_ids) == {draft_with_time["id"], scheduled["id"], on_second["id"], busy["id"]}
    assert [parse(p["publish_at"]) for p in cal["posts"]] == sorted(
        parse(p["publish_at"]) for p in cal["posts"]
    )
    assert "checklist" not in cal["posts"][0]
    assert [m["id"] for m in cal["messages"]] == [str(dm)]
    assert cal["messages"][0]["social_account_id"] == str(shop.account_id)
    slots = [(s["social_account_id"], parse(s["at"])) for s in cal["slots"]]
    assert (str(shop.account_id), free_day) in slots
    assert (str(shop.account_id), busy_day) not in slots
    rail = {a["social_account_id"]: a for a in cal["accounts"]}
    assert set(rail) == {str(shop.account_id), str(second)}
    assert rail[str(shop.account_id)]["publishing_limit"] == 100
    assert parse(rail[str(shop.account_id)]["next_free_at"]) == free_day
    assert rail[str(second)]["next_free_at"] is None

    narrowed = await shop.ok(
        "GET", "/calendar", account_ids=[str(second)], layers=["posts", "slots"], **range_
    )
    assert [p["id"] for p in narrowed["posts"]] == [on_second["id"]]
    assert (narrowed["messages"], narrowed["slots"]) == ([], [])
    assert [a["social_account_id"] for a in narrowed["accounts"]] == [str(second)]


async def test_the_right_rail_counts_posts_published_in_the_last_day(
    shop: Shop, engine: AsyncEngine
) -> None:
    for hours in (2, 20, 30):
        await make_scheduled_post(
            engine,
            workspace_id=shop.wid,
            account_ids=[shop.account_id],
            status="published",
            target_status="published",
            publish_at=later(hours=-hours),
            target_values={"published_at": later(hours=-hours)},
        )
    whatsapp = await make_account(
        engine, shop.wid, platform="whatsapp", platform_account_id="1555000222"
    )

    cal = await shop.ok(
        "GET", "/calendar", **{"from": _day(-2).isoformat(), "to": _day(0).isoformat()}
    )

    rail = {a["social_account_id"]: a for a in cal["accounts"]}
    assert rail[str(shop.account_id)]["published_24h"] == 2
    assert str(whatsapp) not in rail  # WhatsApp numbers can't publish
    assert len(cal["posts"]) == 3


async def test_calendar_dates_are_the_workspaces_days(shop: Shop, engine: AsyncEngine) -> None:
    await shop.set_timezone("Asia/Kolkata")
    zone = ZoneInfo("Asia/Kolkata")
    day = datetime.now(zone).date() + timedelta(days=2)
    # 00:30 in Kolkata is still the previous day in UTC.
    early = datetime.combine(day, time(0, 30), tzinfo=zone)
    post = await shop.scheduled(at=early)

    same_day = await shop.ok("GET", "/calendar", **{"from": day.isoformat(), "to": day.isoformat()})
    day_before = await shop.ok(
        "GET",
        "/calendar",
        **{"from": (day - timedelta(1)).isoformat(), "to": (day - timedelta(1)).isoformat()},
    )

    assert same_day["timezone"] == "Asia/Kolkata"
    assert [p["id"] for p in same_day["posts"]] == [post["id"]]
    assert day_before["posts"] == []


# ---------------------------------------------------------------- posting times (FR-PUB-09)


async def test_posting_times_are_replaced_as_a_whole(shop: Shop) -> None:
    empty = await shop.ok("GET", f"/social-accounts/{shop.account_id}/posting-slots")
    assert (empty["slots"], empty["next_free_at"], empty["timezone"]) == ([], [], "UTC")

    out = await shop.ok(
        "PUT",
        f"/social-accounts/{shop.account_id}/posting-slots",
        {
            "slots": [
                {"weekday": 4, "local_time": "18:00"},
                {"weekday": 0, "local_time": "18:00"},
                {"weekday": 2, "local_time": "09:30"},
                {"weekday": 0, "local_time": "18:00"},
            ]
        },
    )

    assert out["slots"] == [
        {"weekday": 0, "local_time": "18:00:00"},
        {"weekday": 2, "local_time": "09:30:00"},
        {"weekday": 4, "local_time": "18:00:00"},
    ]
    upcoming = [parse(t) for t in out["next_free_at"]]
    assert len(upcoming) == 5
    assert upcoming == sorted(upcoming)
    assert all(t > datetime.now(UTC) + timedelta(minutes=5) for t in upcoming)
    assert {(t.weekday(), t.time()) for t in upcoming} <= {
        (0, time(18)),
        (2, time(9, 30)),
        (4, time(18)),
    }

    cleared = await shop.ok(
        "PUT", f"/social-accounts/{shop.account_id}/posting-slots", {"slots": []}
    )
    assert cleared["slots"] == []


async def test_posting_times_are_local_to_the_workspace(shop: Shop) -> None:
    await shop.set_timezone("Asia/Kolkata")
    out = await shop.ok(
        "PUT",
        f"/social-accounts/{shop.account_id}/posting-slots",
        {"slots": [{"weekday": d, "local_time": "18:00"} for d in range(7)]},
    )
    assert out["timezone"] == "Asia/Kolkata"
    zone = ZoneInfo("Asia/Kolkata")
    for at in out["next_free_at"]:
        assert parse(at).astimezone(zone).time() == time(18)


async def test_posting_times_refuse_seconds_and_accounts_that_cannot_publish(
    shop: Shop, engine: AsyncEngine
) -> None:
    errors = await shop.fields(
        "PUT",
        f"/social-accounts/{shop.account_id}/posting-slots",
        {
            "slots": [
                {"weekday": 1, "local_time": "18:00"},
                {"weekday": 1, "local_time": "18:00:30"},
            ]
        },
    )
    assert errors == {"slots.1.local_time": "Use a time in whole minutes, like 18:00."}
    errors = await shop.fields(
        "PUT",
        f"/social-accounts/{shop.account_id}/posting-slots",
        {"slots": [{"weekday": 7, "local_time": "18:00"}]},
    )
    assert set(errors) == {"slots.0.weekday"}

    whatsapp = await make_account(
        engine, shop.wid, platform="whatsapp", platform_account_id="1555000333"
    )
    problem = await shop.problem(
        "PUT",
        f"/social-accounts/{whatsapp}/posting-slots",
        {"slots": [{"weekday": 1, "local_time": "18:00"}]},
        status=409,
    )
    assert problem["code"] == "capability_unavailable"
    await shop.problem("GET", f"/social-accounts/{uuid.uuid4()}/posting-slots", status=404)


async def test_changing_posting_times_never_moves_scheduled_posts(shop: Shop) -> None:
    at = _at(2)
    await make_posting_slot(
        shop.engine, workspace_id=shop.wid, account_id=shop.account_id, weekday=at.weekday()
    )
    post = await shop.ready_draft()
    queued = await shop.ok("POST", f"/scheduled-posts/{post['id']}/queue")
    assert parse(queued["publish_at"]) == at

    slots = await shop.ok("PUT", f"/social-accounts/{shop.account_id}/posting-slots", {"slots": []})

    assert slots["slots"] == []
    got = await shop.ok("GET", f"/scheduled-posts/{post['id']}")
    assert (got["status"], parse(got["publish_at"])) == ("scheduled", at)


# ---------------------------------------------------------------- hashtag groups (FR-PUB-12)


async def test_hashtag_groups_are_stored_normalised_and_listed_by_name(
    shop: Shop, engine: AsyncEngine
) -> None:
    created = await shop.ok(
        "POST",
        "/hashtag-groups",
        {"name": "Summer sale", "hashtags": ["#Summer", "sale", "##SALE", " linen_shirts "]},
        status=201,
    )
    assert created["hashtags"] == ["summer", "sale", "linen_shirts"]
    await shop.ok("POST", "/hashtag-groups", {"name": "autumn", "hashtags": ["autumn"]}, status=201)
    from tests.support.inbox import make_workspace

    other = await make_workspace(engine)
    await make_hashtag_group(engine, workspace_id=other, name="Theirs")

    listed = await shop.ok("GET", "/hashtag-groups")

    assert [g["name"] for g in listed["items"]] == ["autumn", "Summer sale"]


async def test_hashtag_group_names_are_unique_ignoring_case(shop: Shop) -> None:
    first = await shop.ok(
        "POST", "/hashtag-groups", {"name": "Summer", "hashtags": ["summer"]}, status=201
    )
    second = await shop.ok(
        "POST", "/hashtag-groups", {"name": "Winter", "hashtags": ["winter"]}, status=201
    )

    errors = await shop.fields("POST", "/hashtag-groups", {"name": "SUMMER", "hashtags": ["x"]})
    assert errors == {"name": "You already have a group with this name."}
    errors = await shop.fields("PATCH", f"/hashtag-groups/{second['id']}", {"name": "summer"})
    assert errors == {"name": "You already have a group with this name."}
    # Renaming a group to its own name in another case is fine.
    renamed = await shop.ok("PATCH", f"/hashtag-groups/{first['id']}", {"name": "SUMMER"})
    assert renamed["name"] == "SUMMER"


async def test_hindi_hashtags_are_stored_whole(shop: Shop) -> None:
    group = await shop.ok(
        "POST",
        "/hashtag-groups",
        {"name": "दिवाली", "hashtags": ["#दिवाली2026", "हिंदी_पोस्ट", "#नमस्ते", "दिवाली2026"]},
        status=201,
    )
    assert group["hashtags"] == ["दिवाली2026", "हिंदी_पोस्ट", "नमस्ते"]
    errors = await shop.fields("POST", "/hashtag-groups", {"name": "Split", "hashtags": ["नमस् ते"]})
    assert errors == {"hashtags.0": "Use letters, numbers and underscores only."}

    # The checklist counts each Hindi hashtag once, whole.
    many = " ".join(f"#दिवाली{i}" for i in range(31))
    post = await shop.ready_draft(caption=many)
    [item] = [i for i in post["checklist"] if i["key"] == "hashtags"]
    assert (item["ok"], item["field"], item["message"]) == (
        False,
        "caption",
        "Use at most 30 hashtags (now 31).",
    )


async def test_hashtag_group_hashtags_must_be_words(shop: Shop) -> None:
    errors = await shop.fields(
        "POST",
        "/hashtag-groups",
        {"name": "Bad", "hashtags": ["good", "two words", "#", "emoji🙂"]},
    )
    assert set(errors) == {"hashtags.1", "hashtags.2", "hashtags.3"}
    errors = await shop.fields(
        "POST", "/hashtag-groups", {"name": "Many", "hashtags": [f"t{i}" for i in range(31)]}
    )
    assert set(errors) == {"hashtags"}


async def test_a_hashtag_group_can_be_edited_and_deleted(shop: Shop) -> None:
    group = await shop.ok(
        "POST", "/hashtag-groups", {"name": "Summer", "hashtags": ["summer"]}, status=201
    )

    patched = await shop.ok(
        "PATCH", f"/hashtag-groups/{group['id']}", {"hashtags": ["Beach", "#sun", "beach"]}
    )
    assert (patched["name"], patched["hashtags"]) == ("Summer", ["beach", "sun"])
    assert patched["updated_at"] > group["updated_at"]

    await shop.ok("DELETE", f"/hashtag-groups/{group['id']}", status=204)
    await shop.problem("DELETE", f"/hashtag-groups/{group['id']}", status=404)
    await shop.problem("PATCH", f"/hashtag-groups/{group['id']}", {"name": "x"}, status=404)
    assert (await shop.ok("GET", "/hashtag-groups"))["items"] == []


# ---------------------------------------------------------------- media library (FR-PUB-13)


async def test_the_library_lists_post_uploads_newest_first(shop: Shop, engine: AsyncEngine) -> None:
    image = await shop.image()
    video = await shop.video()
    newest = await shop.image()
    await make_asset(engine, workspace_id=shop.wid, purpose="message")
    await make_asset(engine, workspace_id=shop.wid, purpose="knowledge", fmt="pdf")
    from tests.support.inbox import make_workspace

    other = await make_workspace(engine)
    await make_asset(engine, workspace_id=other, purpose="post")

    listed = await shop.ok("GET", "/media-assets")
    assert [a["id"] for a in listed["items"]] == [str(newest), str(video), str(image)]
    assert listed["items"][0]["mime_type"] == "image/jpeg"
    assert listed["next_cursor"] is None

    videos = await shop.ok("GET", "/media-assets", type="video")
    assert [a["id"] for a in videos["items"]] == [str(video)]

    page = await shop.ok("GET", "/media-assets", limit=2)
    assert [a["id"] for a in page["items"]] == [str(newest), str(video)]
    rest = await shop.ok("GET", "/media-assets", limit=2, cursor=page["next_cursor"])
    assert [a["id"] for a in rest["items"]] == [str(image)]


async def test_the_library_filters_by_upload_date_in_the_workspaces_time_zone(
    shop: Shop,
) -> None:
    await shop.set_timezone("Asia/Kolkata")
    zone = ZoneInfo("Asia/Kolkata")
    old = await shop.image()
    recent = await shop.image()
    # Uploaded at 23:00 UTC on 1 March: 04:30 on 2 March in Kolkata.
    await shop.execute(
        "UPDATE media_assets SET created_at = :at WHERE id = :id",
        at=datetime(2026, 3, 1, 23, 0, tzinfo=UTC),
        id=old,
    )
    today = datetime.now(zone).date()

    march_2 = await shop.ok("GET", "/media-assets", since="2026-03-02", until="2026-03-02")
    assert [a["id"] for a in march_2["items"]] == [str(old)]
    march_1 = await shop.ok("GET", "/media-assets", until="2026-03-01")
    assert march_1["items"] == []
    since_today = await shop.ok("GET", "/media-assets", since=today.isoformat())
    assert [a["id"] for a in since_today["items"]] == [str(recent)]

    problem = await shop.problem(
        "GET", "/media-assets", since="2026-03-02", until="2026-03-01", status=422
    )
    assert [e["field"] for e in problem["errors"]] == ["until"]


async def test_the_scheduled_post_and_library_routes_are_for_the_workspaces_members(
    shop: Shop, client: httpx.AsyncClient
) -> None:
    for path in ("/scheduled-posts", "/calendar?from=2026-01-01&to=2026-01-02", "/media-assets"):
        response = await client.get(shop.url(path))
        assert response.status_code == 401
