"""GR-34: the weekly report. Done when the report for a week gives the numbers the digest sent for
it, shows the week against the week before and the weeks leading up to it, keeps gaps as gaps
(weeks before the workspace, days without an insight reading, insights not granted), counts the
new sources (story mentions, entry links, ads, leads qualified and won), and the route is any
member's, 422 for a week that cannot be shown, and closed to people outside the workspace."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import time_machine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks.digests import send_due_digests
from socialhood.models.identity import Workspace
from socialhood.platforms.capabilities import Capability
from socialhood.schemas.reports import WeeklyReport
from socialhood.services import reports
from socialhood.services.analytics.common import View
from tests.integration.test_contact_segments import as_agent
from tests.integration.test_weekly_digest import NINE_IST, WEEK, Seed, ist, seed_week
from tests.support.analytics import make_account_day
from tests.support.api import Clerk, sign_in
from tests.support.automation_api import Ws, make_run, workspace
from tests.support.automations import make_automation
from tests.support.inbox import make_account, make_thread
from tests.support.notify_team import Team, make_team
from tests.support.post_metrics import make_instagram_account

KOLKATA = "Asia/Kolkata"
REPORT_WEEK = date(2026, 9, 21)  # the week the 28 September digest covers


def granted(_: Any) -> frozenset[Capability]:
    return frozenset({Capability.ACCOUNT_INSIGHTS})


async def report_for(
    team: Team, week: date, now: datetime = NINE_IST, *, capabilities: Any = granted
) -> WeeklyReport:
    with workspace_scope(team.wid):
        async with team.maker() as session:
            found = await session.get(Workspace, team.wid)
            assert found is not None
            return await reports.build(
                session, View(found.timezone, now, capabilities), found, week_start=week
            )


def metric(report: WeeklyReport, key: str) -> Any:
    return next(m for m in report.metrics if m.key == key)


@pytest.fixture
async def team(engine: AsyncEngine, clean_db: None) -> Team:
    return await make_team(engine, timezone=KOLKATA)


# ---------------------------------------------------------------- the digest's week


async def test_the_report_for_a_week_gives_the_numbers_the_digest_sent(team: Team) -> None:
    """The acceptance: the digest of Monday 28 September and the report for the week it covers
    are one set of numbers (the email links to this report)."""
    await seed_week(team)
    assert await send_due_digests(team.maker, now=NINE_IST) == {"sent": 1}
    [row] = await team.rows("SELECT * FROM weekly_digests WHERE workspace_id = :w", w=team.wid)
    sent = row["stats"]

    report = await report_for(team, REPORT_WEEK)

    assert (report.week.since, report.week.until) == (date(2026, 9, 21), date(2026, 9, 27))
    assert (report.previous_week.since, report.previous_week.until) == (
        date(2026, 9, 14),
        date(2026, 9, 20),
    )
    for item in report.metrics:
        assert item.value == sent[item.key], item.key
    assert reports.digest_extras(report)["trends"] == sent["trends"]
    assert reports.digest_extras(report)["account"] == sent["account"]
    assert report.needs_you == sent["needs_you"]
    assert report.open_questions == sent["open_questions"]
    assert [p.comments for p in report.top_posts] == [p["comments"] for p in sent["top_posts"]]
    assert [(i.intent, i.count) for i in report.top_intents] == [
        (i["intent"], i["count"]) for i in sent["top_intents"]
    ]
    assert metric(report, "messages_received").value == 7
    assert metric(report, "reply_rate").value == 60.0


async def test_the_week_before_and_the_series_come_from_the_same_definitions(team: Team) -> None:
    seed = await seed_week(team)
    # Four more messages in the week before (14-20 September; seed_week has one there) and two the
    # week before that.
    earlier = await seed.conversation("Nadia")
    for day in (15, 16, 17, 19):
        await seed.message(earlier, ist(day, 11))
    for day in (8, 9):
        await seed.message(earlier, ist(day, 11))

    report = await report_for(team, REPORT_WEEK)

    messages = metric(report, "messages_received")
    assert (messages.value, messages.previous) == (7, 5)
    assert (messages.change_pct, messages.direction) == (40.0, "up")
    assert len(messages.series) == reports.SERIES_WEEKS == report.series_weeks
    assert [p.week_start for p in messages.series] == [
        REPORT_WEEK - timedelta(weeks=i) for i in range(7, -1, -1)
    ]
    assert [p.value for p in messages.series][-3:] == [2, 5, 7]
    # A rate compares in points, not in percent.
    rate = metric(report, "reply_rate")
    assert (rate.value, rate.previous) == (60.0, 0.0)
    assert (rate.change_pct, rate.change_points, rate.direction) == (None, 60.0, "up")
    # The same week asked for from another Monday gives the same figures.
    later = await report_for(team, REPORT_WEEK, NINE_IST + timedelta(days=14))
    assert metric(later, "messages_received").value == 7


async def test_weeks_before_the_workspace_existed_are_gaps_not_zeros(team: Team) -> None:
    seed = await seed_week(team)
    await team.execute(
        "UPDATE workspaces SET created_at = :at WHERE id = :w", at=ist(10, 9), w=team.wid
    )
    assert seed.account_id

    report = await report_for(team, REPORT_WEEK)

    series = [p.value for p in metric(report, "messages_received").series]
    # 3 August to 31 August ended before 10 September with nothing in them: not known.
    assert series[:5] == [None] * 5
    # 7 and 14 September end after the workspace was created: real figures (seed_week has one
    # message in the week of 14 September).
    assert series[5:7] == [0, 1]
    assert series[7] == 7
    assert [p.value for p in metric(report, "reply_rate").series][:5] == [None] * 5


async def test_a_week_with_nothing_to_divide_has_no_rate(team: Team) -> None:
    await make_account(team.engine, team.wid)

    report = await report_for(team, REPORT_WEEK)

    assert metric(report, "messages_received").value == 0
    for key in ("reply_rate", "handled_by_ai_rate", "median_first_response_s"):
        found = metric(report, key)
        assert (found.value, found.change_points, found.change_pct, found.direction) == (
            None,
            None,
            None,
            None,
        )


# ---------------------------------------------------------------- the new sources


async def test_story_mentions_entries_and_leads_are_counted_in_their_week(team: Team) -> None:
    seed = Seed(team, await make_account(team.engine, team.wid))
    asha = await seed.conversation("Asha")
    hello = await seed.message(asha, ist(22, 10, 0))
    bina = await seed.conversation("Bina")
    await seed.message(bina, ist(30, 10, 0))  # after the week
    contacts = await team.rows(
        "SELECT id, display_name FROM contacts WHERE workspace_id = :w", w=team.wid
    )
    by_name = {c["display_name"]: c["id"] for c in contacts}

    # Story mentions: two in the week, one the week before, one after.
    for day, month in ((22, 9), (27, 9), (15, 9), (28, 9)):
        message = await seed.message(asha, ist(day, 12, 5, 0, month), status="received")
        await team.execute(
            "INSERT INTO story_mentions (workspace_id, social_account_id, contact_id,"
            " message_id, mentioned_at) VALUES (:w, :a, :c, :m, :at)",
            w=team.wid,
            a=seed.account_id,
            c=by_name["Asha"],
            m=message,
            at=ist(day, 12, 5, 0, month),
        )
    assert hello

    # Conversations from a link (two in the week, one before) and an ad (one in the week).
    for name, source, day in (
        ("Chetan", "link", 23),
        ("Divya", "link", 24),
        ("Esha", "link", 16),
        ("Farid", "ad", 25),
    ):
        conv = await seed.conversation(name)
        await team.execute(
            "UPDATE conversations SET entry_source = :s, entry_at = :at WHERE id = :c",
            s=source,
            at=ist(day, 9),
            c=conv,
        )

    # Leads: Asha qualified then won in the week, Bina qualified before it and won after.
    async def stage(contact: uuid.UUID, old: str, new: str, at: datetime) -> None:
        await team.execute(
            "INSERT INTO lead_stage_changes (workspace_id, contact_id, from_stage, to_stage,"
            " actor_kind, created_at) VALUES (:w, :c, :f, :t, 'system', :at)",
            w=team.wid,
            c=contact,
            f=old,
            t=new,
            at=at,
        )

    await stage(by_name["Asha"], "new", "qualified", ist(22, 11))
    await stage(by_name["Asha"], "qualified", "won", ist(26, 11))
    await stage(by_name["Bina"], "new", "qualified", ist(16, 11))
    await stage(by_name["Bina"], "qualified", "won", ist(29, 11))

    report = await report_for(team, REPORT_WEEK)

    assert metric(report, "story_mentions").value == 2
    assert metric(report, "story_mentions").previous == 1
    assert metric(report, "conversations_from_links").value == 2
    assert metric(report, "conversations_from_links").previous == 1
    assert metric(report, "conversations_from_ads").value == 1
    assert (
        metric(report, "leads_qualified").value,
        metric(report, "leads_qualified").previous,
    ) == (1, 1)
    assert (metric(report, "leads_won").value, metric(report, "leads_won").previous) == (1, 0)
    assert (metric(report, "leads_won").change_pct, metric(report, "leads_won").direction) == (
        None,
        "up",
    )
    assert not hasattr(report, "notes")


async def test_captures_are_the_answers_flows_took_in_each_week(team: Team) -> None:
    seed = Seed(team, await make_account(team.engine, team.wid))
    automation = await make_automation(
        team.engine, workspace_id=team.wid, account_id=seed.account_id, message_text=None
    )
    thread = await make_thread(team.engine, workspace_id=str(team.wid), account_id=seed.account_id)
    run = await make_run(
        team.engine,
        workspace_id=str(team.wid),
        automation_id=automation,
        created_at=ist(20, 9),
        trigger_message_id=thread.message_ids[0],
    )

    async def step(step_id: str, kind: str, detail: dict[str, Any], at: datetime) -> None:
        await team.execute(
            "INSERT INTO automation_run_steps (workspace_id, run_id, step_id, kind, status,"
            " detail, created_at, updated_at) VALUES (:w, :r, :s, :k, 'done',"
            " CAST(:d AS jsonb), :at, :at)",
            w=team.wid,
            r=run,
            s=step_id,
            k=kind,
            d=json.dumps(detail),
            at=at,
        )

    # In the week of 21 September: two answers taken. Not counted: a question skipped after its
    # tries, a quick-reply tap on a send step (it has an answer too), a question still waiting.
    await step("a", "ask", {"answer": "priya@example.com"}, ist(22, 10))
    await step("b", "ask", {"answer": "+919876543210", "tries": 2}, ist(26, 18))
    await step("c", "ask", {"skipped": True, "tries": 2}, ist(23, 10))
    await step("d", "send", {"answer": "Yes", "option": 0}, ist(23, 11))
    await step("e", "ask", {"tries": 1}, ist(24, 11))
    # The week before: one. After the week: one.
    await step("f", "ask", {"answer": "ravi@example.com"}, ist(16, 10))
    await step("g", "ask", {"answer": "late@example.com"}, ist(29, 10))

    report = await report_for(team, REPORT_WEEK)

    captures = metric(report, "captures")
    assert (captures.value, captures.previous) == (2, 1)
    assert (captures.change_pct, captures.direction) == (100.0, "up")
    assert [p.value for p in captures.series][-2:] == [1, 2]


# ---------------------------------------------------------------- account metrics


async def seed_days(
    team: Team,
    account: uuid.UUID,
    first: date,
    last: date,
    *,
    skip: tuple[date, ...] = (),
    **m: int,
) -> None:
    day = first
    while day <= last:
        if day not in skip:
            await make_account_day(
                team.engine,
                workspace_id=team.wid,
                account_id=account,
                day=day,
                followers_count=1000 + day.day,
                metrics=m,
            )
        day += timedelta(days=1)


def account_metric(report: WeeklyReport, name: str) -> Any:
    return next(a for a in report.account_metrics if a.figure.metric == name)


async def test_account_metrics_say_how_many_days_they_cover(team: Team) -> None:
    account = await make_instagram_account(team.engine, team.wid)
    # The week before is complete; this week lacks Saturday and Sunday (not written yet).
    await seed_days(team, account, date(2026, 9, 14), date(2026, 9, 20), reach=100)
    await seed_days(
        team,
        account,
        date(2026, 9, 21),
        date(2026, 9, 27),
        skip=(date(2026, 9, 26), date(2026, 9, 27)),
        reach=150,
    )

    report = await report_for(team, REPORT_WEEK)

    reach = account_metric(report, "reach")
    assert (reach.figure.current.value, reach.figure.current.days_known) == (750, 5)
    assert reach.figure.current.days_total == 7
    assert reach.figure.previous.value == 700
    assert (reach.figure.change_pct, reach.figure.direction) == (7.1, "up")
    # Followers are the latest reading in the week, not a sum.
    followers = account_metric(report, "followers")
    assert followers.figure.current.value == 1025
    # No day has views: null with the reason, never zero.
    views = account_metric(report, "views")
    assert (views.figure.current.value, views.figure.current.unavailable) == (None, "no_readings")
    assert views.figure.change_pct is None
    # The series is one point a week; weeks without a reading are gaps.
    assert len(reach.series) == reports.SERIES_WEEKS
    assert [p.value for p in reach.series][:6] == [None] * 6
    assert [(p.value, p.days_known) for p in reach.series][-2:] == [(700, 7), (750, 5)]


async def test_insights_that_were_not_granted_are_a_reason_not_a_zero(team: Team) -> None:
    account = await make_instagram_account(team.engine, team.wid, insights=False)
    await seed_days(team, account, date(2026, 9, 21), date(2026, 9, 27))

    def none_granted(_: Any) -> frozenset[Capability]:
        return frozenset()

    report = await report_for(team, REPORT_WEEK, capabilities=none_granted)

    reach = account_metric(report, "reach")
    assert (reach.figure.current.value, reach.figure.current.unavailable) == (
        None,
        "insights_not_granted",
    )
    assert account_metric(report, "followers").figure.current.value == 1027


async def test_no_instagram_account_is_said_so(team: Team) -> None:
    report = await report_for(team, REPORT_WEEK)
    reach = account_metric(report, "reach")
    assert (reach.figure.current.value, reach.figure.current.unavailable) == (None, "no_account")


# ---------------------------------------------------------------- the route


def clock(at: datetime) -> Any:
    return time_machine.travel(at, tick=True)


async def seed_account_week(ws: Ws, engine: AsyncEngine) -> None:
    """Messages in the week of 21 September for the sandbox account."""
    async with engine.begin() as conn:
        contact = (
            await conn.execute(
                text(
                    "INSERT INTO contacts (workspace_id, social_account_id, platform_user_id,"
                    " display_name) VALUES (:w, :a, 'igsid_r1', 'Rima') RETURNING id"
                ),
                {"w": ws.wid, "a": ws.account_id},
            )
        ).scalar_one()
        conv = (
            await conn.execute(
                text(
                    "INSERT INTO conversations (workspace_id, social_account_id, contact_id,"
                    " platform) VALUES (:w, :a, :c, 'instagram') RETURNING id"
                ),
                {"w": ws.wid, "a": ws.account_id, "c": contact},
            )
        ).scalar_one()
        for day in (22, 23):
            await conn.execute(
                text(
                    "INSERT INTO messages (workspace_id, conversation_id, social_account_id,"
                    " direction, source, kind, text, occurred_at, status)"
                    " VALUES (:w, :c, :a, 'inbound', 'customer', 'text', 'hi', :at, 'received')"
                ),
                {"w": ws.wid, "c": conv, "a": ws.account_id, "at": ist(day, 10)},
            )


async def test_the_route_serves_the_latest_finished_week_by_default(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, clean_db: None
) -> None:
    ws = await workspace(client, clerk)
    await engine_set_timezone(engine, ws.wid)
    await seed_account_week(ws, engine)

    with clock(NINE_IST):
        body = await ws.ok("GET", "/reports/weekly")
        asked = await ws.ok("GET", "/reports/weekly", params={"week": "2026-09-21"})

    WeeklyReport.model_validate(body)
    assert body == asked
    assert body["week_start"] == "2026-09-21"
    assert body["timezone"] == KOLKATA
    assert body["week"] == {"since": "2026-09-21", "until": "2026-09-27", "days": 7}
    assert body["weeks"][0] == "2026-09-21"
    assert len(body["weeks"]) == reports.PICKER_WEEKS
    messages = next(m for m in body["metrics"] if m["key"] == "messages_received")
    assert messages["value"] == 2
    assert len(messages["series"]) == 8
    assert "notes" not in body
    assert next(m for m in body["metrics"] if m["key"] == "captures")["value"] == 0
    assert {a["figure"]["metric"] for a in body["account_metrics"]} >= {"reach", "followers"}


async def engine_set_timezone(engine: AsyncEngine, wid: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET timezone = :t WHERE id = :w"), {"t": KOLKATA, "w": wid}
        )


@pytest.mark.parametrize(
    ("week", "field"),
    [
        ("2026-09-22", "week"),  # a Tuesday
        ("2026-09-28", "week"),  # not finished yet
        ("2025-01-06", "week"),  # over a year back
        ("not-a-date", "week"),
    ],
)
async def test_a_week_that_cannot_be_shown_is_422_on_week(
    client: httpx.AsyncClient, clerk: Clerk, clean_db: None, week: str, field: str
) -> None:
    ws = await workspace(client, clerk)
    with clock(NINE_IST):
        response = await ws.call("GET", "/reports/weekly", params={"week": week})
    assert response.status_code == 422, response.text
    assert any(
        field in str(e.get("field") or e.get("loc") or "") for e in response.json()["errors"]
    )


async def test_any_member_reads_it_and_outsiders_do_not(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, clean_db: None
) -> None:
    ws = await workspace(client, clerk)
    agent = await as_agent(ws, engine, client, clerk)
    outsider_id, _ = await sign_in(client, clerk, email="someone@example.com")

    with clock(NINE_IST):
        assert (await agent.call("GET", "/reports/weekly")).status_code == 200
        owner = await ws.call("GET", "/reports/weekly")
        outside = await client.get(
            f"/v1/w/{ws.wid}/reports/weekly", headers=clerk.headers(outsider_id)
        )
        anonymous = await client.get(f"/v1/w/{ws.wid}/reports/weekly")

    assert owner.status_code == 200
    assert outside.status_code == 404
    assert anonymous.status_code == 401


async def test_the_report_counts_only_this_workspaces_rows(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, clean_db: None
) -> None:
    mine = await workspace(client, clerk)
    theirs = await workspace(client, clerk, email="other@example.com")
    await seed_account_week(theirs, engine)

    with clock(NINE_IST):
        body = await mine.ok("GET", "/reports/weekly", params={"week": "2026-09-21"})

    messages = next(m for m in body["metrics"] if m["key"] == "messages_received")
    assert messages["value"] == 0
    assert all(p["value"] in (0, None) for p in messages["series"])


async def test_the_weeks_are_the_workspaces_not_utc(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, clean_db: None
) -> None:
    ws = await workspace(client, clerk)
    await engine_set_timezone(engine, ws.wid)
    # Sunday 27 September 23:30 in India is 18:00 UTC: still inside the 21-27 September week.
    sunday_night = datetime(2026, 9, 27, 18, 0, tzinfo=UTC)
    # Monday 28 September 00:30 in India is 19:00 UTC on the 27th: the week has just finished.
    after_midnight = datetime(2026, 9, 27, 19, 0, tzinfo=ZoneInfo("UTC"))
    with clock(sunday_night):
        before = await ws.call("GET", "/reports/weekly", params={"week": "2026-09-21"})
        default = await ws.ok("GET", "/reports/weekly")
    with clock(after_midnight):
        after = await ws.call("GET", "/reports/weekly", params={"week": "2026-09-21"})
    assert before.status_code == 422
    assert default["week_start"] == "2026-09-14"
    assert after.status_code == 200


# ---------------------------------------------------------------- the digest week constant


def test_the_digest_monday_is_the_day_after_the_reports_sunday() -> None:
    assert WEEK - timedelta(days=1) == date(2026, 9, 27)
    assert reports.week_span(KOLKATA, REPORT_WEEK).until == WEEK - timedelta(days=1)
