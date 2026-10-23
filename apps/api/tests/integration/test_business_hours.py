"""GR-22: business hours and away messages. The routes and who may change them, the away message at
runtime (once per closed window, after automations, never on top of the AI), automations that need
"inside" or "outside" hours, and Auto mode that waits for closing time."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.services import business_hours
from socialhood.services.automations.runtime import Outcome
from socialhood.settings import Settings
from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace
from tests.support.automations import make_automation
from tests.support.runtime import World, make_world, platform_deps
from tests.support.sending import clean_outbox

WEEKDAYS = [
    {"day": day, "ranges": [{"start": "09:00", "end": "17:00"}]} for day in range(5)
]  # Monday to Friday
AWAY = "We're closed. Back at 9, {first_name}."
KOLKATA = "Asia/Kolkata"


def hours(**values: Any) -> dict[str, Any]:
    return {"enabled": True, "days": WEEKDAYS, "away_enabled": True, "away_message": AWAY, **values}


def kolkata(text_: str) -> datetime:
    """A wall-clock time in Kolkata (UTC+5:30, no daylight saving) as an aware UTC datetime."""
    return datetime.fromisoformat(text_).replace(tzinfo=UTC) - timedelta(hours=5, minutes=30)


# Monday 2026-10-19.
MON_23 = kolkata("2026-10-19 23:00")
MON_11 = kolkata("2026-10-19 11:00")
TUE_07 = kolkata("2026-10-20 07:00")
TUE_23 = kolkata("2026-10-20 23:00")


# ---------------------------------------------------------------- the routes


@pytest.fixture
async def ws(client: httpx.AsyncClient, clerk: Clerk) -> Ws:
    return await workspace(client, clerk)


def fields_of(response: httpx.Response) -> list[str]:
    return [e["field"] for e in response.json().get("errors", [])]


async def test_a_workspace_starts_without_hours_and_keeps_what_is_saved(ws: Ws) -> None:
    start = await ws.ok("GET", "/business-hours")
    assert start["workspace"]["configured"] is False
    assert start["workspace"]["enabled"] is False
    assert [d["day"] for d in start["workspace"]["days"]] == list(range(7))
    assert [a["social_account_id"] for a in start["accounts"]] == [ws.account_id]
    assert start["accounts"][0]["override"] is None

    saved = await ws.ok("PUT", "/business-hours", json=hours(auto_mode="out_of_hours"))
    assert (saved["configured"], saved["enabled"], saved["auto_mode"]) == (
        True,
        True,
        "out_of_hours",
    )
    assert saved["away_message"] == AWAY
    assert [len(d["ranges"]) for d in saved["days"]] == [1, 1, 1, 1, 1, 0, 0]
    assert saved["open_now"] in (True, False)
    again = await ws.ok("GET", "/business-hours")
    assert again["workspace"]["days"] == saved["days"]


async def test_a_bad_schedule_names_each_field(ws: Ws) -> None:
    overlapping = {
        "day": 0,
        "ranges": [{"start": "09:00", "end": "13:00"}, {"start": "12:00", "end": "17:00"}],
    }
    response = await ws.call("PUT", "/business-hours", json=hours(days=[overlapping]))
    assert response.status_code == 422
    assert fields_of(response) == ["days.0.ranges.1.start"]

    backwards = {"day": 1, "ranges": [{"start": "17:00", "end": "09:00"}]}
    response = await ws.call("PUT", "/business-hours", json=hours(days=[backwards]))
    assert fields_of(response) == ["days.0.ranges.0.end"]

    response = await ws.call("PUT", "/business-hours", json=hours(days=[]))
    assert fields_of(response) == ["days"]  # on, with nothing open

    response = await ws.call("PUT", "/business-hours", json=hours(away_message=""))
    assert fields_of(response) == ["away_message"]

    malformed = {"day": 0, "ranges": [{"start": "9am", "end": "17:00"}]}
    response = await ws.call("PUT", "/business-hours", json=hours(days=[malformed]))
    assert response.status_code == 422

    off = await ws.call("PUT", "/business-hours", json={"enabled": False, "days": []})
    assert off.status_code == 200


async def test_an_account_can_have_its_own_hours_and_go_back(ws: Ws) -> None:
    await ws.ok("PUT", "/business-hours", json=hours())
    own = await ws.ok(
        "PUT",
        f"/social-accounts/{ws.account_id}/business-hours",
        json=hours(days=[{"day": 5, "ranges": [{"start": "10:00", "end": "14:00"}]}]),
    )
    assert own["social_account_id"] == ws.account_id
    listed = await ws.ok("GET", "/business-hours")
    assert listed["accounts"][0]["override"]["days"][5]["ranges"] == [
        {"start": "10:00", "end": "14:00"}
    ]
    assert listed["workspace"]["days"][5]["ranges"] == []  # the workspace's is untouched

    await ws.ok("DELETE", f"/social-accounts/{ws.account_id}/business-hours", 204)
    assert (await ws.ok("GET", "/business-hours"))["accounts"][0]["override"] is None
    gone = await ws.call("PUT", f"/social-accounts/{uuid.uuid4()}/business-hours", json=hours())
    assert gone.status_code == 404


async def test_agents_read_the_hours_but_do_not_change_them(engine: AsyncEngine, ws: Ws) -> None:
    await ws.ok("PUT", "/business-hours", json=hours())
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspace_members SET role = 'agent' WHERE workspace_id = :w"),
            {"w": ws.wid},
        )
    assert (await ws.ok("GET", "/business-hours"))["workspace"]["enabled"] is True
    assert (await ws.call("PUT", "/business-hours", json=hours())).status_code == 403
    path = f"/social-accounts/{ws.account_id}/business-hours"
    assert (await ws.call("PUT", path, json=hours())).status_code == 403
    assert (await ws.call("DELETE", path)).status_code == 403


async def test_an_automation_keeps_its_hours_condition(ws: Ws) -> None:
    draft = await ws.draft(hours_condition="outside")
    assert draft["hours_condition"] == "outside"
    copy = await ws.ok("POST", f"/automations/{draft['id']}/duplicate", 201)
    assert copy["hours_condition"] == "outside"
    cleared = await ws.ok(
        "PUT", f"/automations/{draft['id']}", json=ws.definition(hours_condition=None)
    )
    assert cleared["hours_condition"] is None
    bad = await ws.call(
        "PUT", f"/automations/{draft['id']}", json=ws.definition(hours_condition="sometimes")
    )
    assert bad.status_code == 422


# ---------------------------------------------------------------- the runtime


@pytest.fixture(autouse=True)
def _outbox() -> Iterator[None]:
    yield from clean_outbox()


@pytest.fixture
async def world(
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    clean_db: None,
    queue: None,
) -> AsyncIterator[World]:
    async with platform_deps(api_settings, monkeypatch) as deps:
        w = await make_world(engine, redis, deps)
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE workspaces SET timezone = :z WHERE id = :w"),
                {"z": KOLKATA, "w": w.wid},
            )
        yield w


async def set_hours(world: World, *, account: bool = False, **values: Any) -> None:
    """Hours straight into the table: Monday to Friday, 09:00 to 17:00 (Kolkata)."""
    body = hours(**values)
    async with world.engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO business_hours (workspace_id, social_account_id, enabled, schedule,"
                " away_enabled, away_message, auto_mode) VALUES (:w, :a, :e, CAST(:s AS jsonb),"
                " :on, :m, :mode)"
            ),
            {
                "w": world.wid,
                "a": world.account_id if account else None,
                "e": body["enabled"],
                "s": json.dumps(body["days"]),
                "on": body["away_enabled"],
                "m": body["away_message"],
                "mode": body.get("auto_mode", "always"),
            },
        )


async def outbound(world: World) -> list[dict[str, Any]]:
    return await world.rows(
        "SELECT * FROM messages WHERE direction = 'outbound' ORDER BY occurred_at, created_at"
    )


async def customer_dm(
    world: World, at: datetime, text_: str = "hello?", who: str = "igsid_night"
) -> uuid.UUID:
    dm = await world.dm(who, text_, at=at)
    assert dm is not None
    return dm


async def name_everyone(world: World) -> None:
    async with world.engine.begin() as conn:
        await conn.execute(text("UPDATE contacts SET display_name = 'Priya Shah'"))


async def test_a_message_at_23_00_gets_the_away_reply_once(world: World) -> None:
    await set_hours(world)
    first = await customer_dm(world, MON_23)
    await name_everyone(world)

    assert await world.run("dm", first, now=MON_23) is Outcome.FIRED

    [away] = await outbound(world)
    assert away["text"] == "We're closed. Back at 9, Priya."
    assert away["source"] == "automation"
    [conv] = await world.rows("SELECT away_sent_at FROM conversations")
    assert conv["away_sent_at"] is not None

    # Another message in the same closed window, even the next morning before opening: nothing.
    second = await customer_dm(world, MON_23 + timedelta(minutes=5), "are you there?")
    assert await world.run("dm", second, now=MON_23 + timedelta(minutes=5)) is Outcome.NO_MATCH
    third = await customer_dm(world, TUE_07, "good morning")
    assert await world.run("dm", third, now=TUE_07) is Outcome.NO_MATCH
    assert len(await outbound(world)) == 1

    # The next night is a new closed window.
    fourth = await customer_dm(world, TUE_23, "still there?")
    assert await world.run("dm", fourth, now=TUE_23) is Outcome.FIRED
    assert len(await outbound(world)) == 2


async def test_a_retried_job_does_not_send_the_away_reply_twice(world: World) -> None:
    await set_hours(world)
    dm = await customer_dm(world, MON_23)

    assert await world.run("dm", dm, now=MON_23) is Outcome.FIRED
    assert await world.run("dm", dm, now=MON_23) is Outcome.NO_MATCH

    assert len(await outbound(world)) == 1


async def test_inside_hours_there_is_no_away_reply(world: World) -> None:
    await set_hours(world)
    dm = await customer_dm(world, MON_11)

    assert await world.run("dm", dm, now=MON_11) is Outcome.NO_MATCH

    assert await outbound(world) == []


async def test_the_away_reply_is_off_unless_it_is_on_and_has_words(world: World) -> None:
    await set_hours(world, away_enabled=False, away_message=None)
    dm = await customer_dm(world, MON_23)

    assert await world.run("dm", dm, now=MON_23) is Outcome.NO_MATCH

    assert await outbound(world) == []


async def test_an_automation_answers_and_the_away_reply_stays_quiet(world: World) -> None:
    await set_hours(world)
    await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("price",),
        message_text="Prices start at 499.",
    )
    dm = await customer_dm(world, MON_23, "price?")

    assert await world.run("dm", dm, now=MON_23) is Outcome.FIRED

    [reply] = await outbound(world)
    assert reply["text"] == "Prices start at 499."
    [conv] = await world.rows("SELECT away_sent_at FROM conversations")
    assert conv["away_sent_at"] is None  # the window is still unused

    other = await customer_dm(world, MON_23 + timedelta(minutes=1), "and the shipping?")
    assert await world.run("dm", other, now=MON_23 + timedelta(minutes=1)) is Outcome.FIRED
    assert [m["text"] for m in await outbound(world)][-1] == "We're closed. Back at 9, there."


async def test_the_welcome_goes_first_and_the_away_reply_does_not_pile_on(world: World) -> None:
    await set_hours(world)
    await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=(),
        trigger="first_message",
        message_text="Welcome!",
    )
    dm = await customer_dm(world, MON_23)

    assert await world.run("dm", dm, now=MON_23) is Outcome.FIRED

    assert [m["text"] for m in await outbound(world)] == ["Welcome!"]


async def test_no_away_reply_when_the_ai_will_answer(world: World) -> None:
    await set_hours(world)
    async with world.engine.begin() as conn:
        await conn.execute(text("UPDATE social_accounts SET ai_mode = 'auto'"))
    dm = await customer_dm(world, MON_23)

    assert await world.run("dm", dm, now=MON_23) is Outcome.NO_MATCH

    assert await outbound(world) == []


async def test_taps_and_story_mentions_get_no_away_reply(world: World) -> None:
    await set_hours(world)
    mention = await world.story("igsid_story", kind="story_mention", at=MON_23)
    assert mention is not None
    tap = await world.dm("igsid_tap", "Yes", payload="some:payload", at=MON_23)
    assert tap is not None

    assert await world.run("dm", mention, now=MON_23) is Outcome.NO_MATCH
    assert await world.run("dm", tap, now=MON_23) is Outcome.NO_MATCH

    assert await outbound(world) == []


async def test_an_accounts_own_hours_replace_the_workspaces(world: World) -> None:
    await set_hours(world)
    await set_hours(world, account=True, enabled=False)  # this account has no hours: always open
    dm = await customer_dm(world, MON_23)

    assert await world.run("dm", dm, now=MON_23) is Outcome.NO_MATCH

    assert await outbound(world) == []


async def test_the_workspace_time_zone_decides_when_it_is_late(
    world: World, engine: AsyncEngine
) -> None:
    await set_hours(world)
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE workspaces SET timezone = 'UTC'"))
    # 11:00 in Kolkata is 05:30 UTC: closed if the schedule is read in UTC, open in Kolkata.
    dm = await customer_dm(world, MON_11)

    assert await world.run("dm", dm, now=MON_11) is Outcome.FIRED

    assert len(await outbound(world)) == 1


async def test_an_automation_can_require_inside_or_outside_hours(world: World) -> None:
    await set_hours(world, away_enabled=False, away_message=None)
    inside = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("price",),
        message_text="Come in, we're open.",
        hours_condition="inside",
    )
    outside = await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("price",),
        message_text="Leave your number, we'll call.",
        hours_condition="outside",
        priority=200,
    )

    day = await customer_dm(world, MON_11, "price?", who="igsid_day")
    assert await world.run("dm", day, now=MON_11) is Outcome.FIRED
    night = await customer_dm(world, MON_23, "price?", who="igsid_night2")
    assert await world.run("dm", night, now=MON_23) is Outcome.FIRED

    texts = [m["text"] for m in await outbound(world)]
    assert sorted(texts) == ["Come in, we're open.", "Leave your number, we'll call."]
    runs = await world.rows("SELECT automation_id FROM automation_runs ORDER BY created_at")
    assert [r["automation_id"] for r in runs] == [inside, outside]


async def test_an_automation_with_hours_runs_any_time_when_there_are_no_hours(world: World) -> None:
    await make_automation(
        world.engine,
        workspace_id=world.wid,
        account_id=world.account_id,
        keywords=("price",),
        message_text="Open!",
        hours_condition="inside",
    )
    dm = await customer_dm(world, MON_23, "price?")

    assert await world.run("dm", dm, now=MON_23) is Outcome.FIRED  # no hours: always inside


# ---------------------------------------------------------------- Auto mode


async def test_auto_mode_can_wait_for_closing_time(world: World) -> None:
    await set_hours(world, auto_mode="out_of_hours")

    with workspace_scope(world.wid):
        async with world.maker() as session:
            open_ = await business_hours.auto_blocked(session, world.account_id, MON_11)
            closed = await business_hours.auto_blocked(session, world.account_id, MON_23)
    assert open_ is True  # open: Auto keeps quiet
    assert closed is False  # closed: Auto works


async def test_auto_mode_works_at_any_hour_by_default(world: World) -> None:
    await set_hours(world)  # auto_mode "always"

    with workspace_scope(world.wid):
        async with world.maker() as session:
            assert await business_hours.auto_blocked(session, world.account_id, MON_11) is False
            assert await business_hours.auto_blocked(session, world.account_id, MON_23) is False
    # No hours at all: nothing changes either.


async def test_auto_mode_is_not_held_back_when_there_are_no_hours(world: World) -> None:
    with workspace_scope(world.wid):
        async with world.maker() as session:
            assert await business_hours.auto_blocked(session, world.account_id, MON_11) is False
