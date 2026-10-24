"""VIS-07 to VIS-12 (C-123): the lead list on list_contacts (awaiting_reply, best score first, any
member), the trend line on metric_trend, the table on search_conversations, nothing built with the
setting off, a run exposing the new kinds, and the lead-reply follow-up: draft_reply once per
conversation, each drafting a card, sending nothing."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.ai.fake import FakeProvider
from socialhood.models.identity import Role
from socialhood.platforms.deps import PlatformDeps
from socialhood.schemas.agent import (
    LEAD_REPLY_MAX,
    LeadListVisual,
    TableVisual,
    TrendVisual,
)
from socialhood.settings import Settings
from tests.integration.test_agent_visuals import seed
from tests.support.agent import make_agent_run
from tests.support.agent_tools import Shop, make_shop, tool_platform
from tests.support.api import Clerk, sign_in
from tests.support.inbox import Thread, make_thread

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)

SUGGESTION = {
    "can_answer": True,
    "reply": "Yes! We deliver on Saturday.",
    "missing_info": None,
    "missing_topic": None,
    "confidence": 0.9,
    "used_source_ids": [],
}


@pytest.fixture
async def platform(api_settings: Settings) -> AsyncIterator[PlatformDeps]:
    async with tool_platform(api_settings.model_copy(update={"agent_visuals_enabled": True})) as d:
        yield d


@pytest.fixture
async def quiet_platform(api_settings: Settings) -> AsyncIterator[PlatformDeps]:
    async with tool_platform(api_settings) as deps:
        yield deps


@pytest.fixture
async def shop(engine: AsyncEngine, clean_db: None, platform: PlatformDeps) -> Shop:
    return await make_shop(engine, platform)


@pytest.fixture
async def quiet(engine: AsyncEngine, clean_db: None, quiet_platform: PlatformDeps) -> Shop:
    return await make_shop(engine, quiet_platform)


async def lead(
    shop: Shop, name: str, score: int | None, *, waiting: bool = True, text_: str = "Price?"
) -> Thread:
    """A contact with one conversation: waiting for our reply (they wrote last) or answered."""
    t = await make_thread(
        shop.engine,
        workspace_id=shop.wid,
        account_id=shop.account_id,
        display_name=name,
        username=name.lower().replace(" ", "."),
        texts=(text_,),
        direction="inbound" if waiting else "outbound",
    )
    if score is not None:
        await shop.execute(
            "UPDATE conversations SET lead_score = :s WHERE id = :id",
            s=score,
            id=t.conversation_id,
        )
    return t


# ---------------------------------------------------------------- lead_list (VIS-08)


async def test_awaiting_leads_come_best_score_first_with_how_many_wait(shop: Shop) -> None:
    low = await lead(shop, "Low Lead", 40)
    top = await lead(shop, "Top Lead", 90)
    mid = await lead(shop, "Mid Lead", 70)
    await lead(shop, "Answered Lead", 99, waiting=False)  # we wrote last: not waiting
    unscored = await lead(shop, "No Score", None)

    got = await shop.call("list_contacts", {"awaiting_reply": True}, role=Role.AGENT)
    assert [c.name for c in got.contacts] == ["Top Lead", "Mid Lead", "Low Lead", "No Score"]
    assert got.total == 4
    assert got.summary == "4 contacts waiting for a reply, best lead score first"
    assert isinstance(got.visual, LeadListVisual)
    visual = got.visual
    assert [r.lead_score for r in visual.items] == [90, 70, 40, None]
    assert [r.conversation_id for r in visual.items] == [
        top.conversation_id,
        mid.conversation_id,
        low.conversation_id,
        unscored.conversation_id,
    ]
    assert visual.total == 4
    assert visual.more_route == "inbox?view=needs_reply"
    # VIS-12: the replies are prepared for the best scores, a few at a time.
    assert visual.reply_ids == [top.conversation_id, mid.conversation_id, low.conversation_id]
    assert len(visual.reply_ids) == LEAD_REPLY_MAX
    assert [r.kind for r in got.refs] == ["conversation"] * 4


async def test_the_list_is_capped_at_ten_and_counts_the_rest(shop: Shop) -> None:
    for n in range(12):
        await lead(shop, f"Lead {n:02d}", n)
    got = await shop.call("list_contacts", {"awaiting_reply": True, "limit": 25}, role=Role.AGENT)
    assert got.total == 12
    assert isinstance(got.visual, LeadListVisual)
    assert len(got.visual.items) == 10  # the visual's cap; the tool lists all 12
    assert got.visual.total == 12
    assert got.visual.items[0].lead_score == 11


async def test_nobody_waiting_means_no_lead_visual(shop: Shop) -> None:
    await lead(shop, "Answered", 80, waiting=False)
    got = await shop.call("list_contacts", {"awaiting_reply": True})
    assert (got.contacts, got.total, got.visual) == ([], 0, None)


async def test_the_old_filters_still_list_by_activity_with_no_lead_visual(shop: Shop) -> None:
    await lead(shop, "Priya", 50)
    got = await shop.call("list_contacts", {})
    assert got.total is None
    assert got.visual is None
    assert [c.name for c in got.contacts] == ["Priya"]


async def test_lead_names_stay_text_and_a_min_score_still_applies(shop: Shop) -> None:
    await lead(shop, "<script>alert(1)</script>", 80)
    await lead(shop, "Cold", 10)
    got = await shop.call(
        "list_contacts", {"awaiting_reply": True, "min_lead_score": 50}, role=Role.AGENT
    )
    assert isinstance(got.visual, LeadListVisual)
    assert [r.name for r in got.visual.items] == ["<script>alert(1)</script>"]


async def test_nothing_is_built_with_the_setting_off(quiet: Shop) -> None:
    await lead(quiet, "Priya", 80)
    got = await quiet.call("list_contacts", {"awaiting_reply": True})
    assert got.visual is None
    assert got.total == 1  # the tool's answer is the same


async def test_another_workspaces_leads_are_never_listed(
    shop: Shop, engine: AsyncEngine, platform: PlatformDeps
) -> None:
    other = await make_shop(engine, platform)
    await lead(other, "Theirs", 95)
    await lead(shop, "Mine", 10)
    got = await shop.call("list_contacts", {"awaiting_reply": True})
    assert [c.name for c in got.contacts] == ["Mine"]


# ---------------------------------------------------------------- the follow-up (VIS-12)


async def test_replies_are_drafted_one_per_lead_as_cards_and_nothing_is_sent(
    shop: Shop, fake_ai: FakeProvider
) -> None:
    first = await lead(shop, "Top Lead", 90, text_="Do you deliver on Saturday?")
    second = await lead(shop, "Mid Lead", 70, text_="Can I get it delivered Saturday?")
    listed = await shop.call("list_contacts", {"awaiting_reply": True}, role=Role.AGENT)
    assert isinstance(listed.visual, LeadListVisual)
    fake_ai.respond("suggest", SUGGESTION)
    cards = []
    for conversation_id in listed.visual.reply_ids:
        drafted = await shop.call(
            "draft_reply", {"conversation_id": str(conversation_id)}, role=Role.AGENT
        )
        cards.append(drafted.action_card)
    assert [c.route for c in cards] == [
        f"inbox/{first.conversation_id}?schedule=1",
        f"inbox/{second.conversation_id}?schedule=1",
    ]
    assert all(c.prefill.text == SUGGESTION["reply"] for c in cards)
    assert all(c.prefill.send_at is None for c in cards)  # no time: the member picks one
    assert await shop.rows("SELECT id FROM messages WHERE direction = 'outbound'") == []
    usage = await shop.rows("SELECT credits FROM ai_usage_events")
    assert [u["credits"] for u in usage] == [2, 2]


# ---------------------------------------------------------------- trend (VIS-07)


async def test_a_trend_draws_the_tools_points_and_leaves_gaps_empty(shop: Shop) -> None:
    await seed(
        shop,
        "2026-10-01",
        "2026-10-22",
        lambda d: {"reach": 300 if d.day == 12 else 100},
        skip=("2026-10-05",),
    )
    got = await shop.call("metric_trend", {"metric": "reach", "range": "this month"}, now=NOW)
    assert isinstance(got.visual, TrendVisual)
    visual = got.visual
    assert [(p.day, p.value) for p in visual.points] == [(p.day, p.value) for p in got.points]
    assert visual.points[4].value is None  # 5 Oct: a gap, never a zero
    assert visual.known_points == 21
    assert (visual.highest.day, visual.highest.value) == (date(2026, 10, 12), 300)  # type: ignore[union-attr]
    assert visual.note == "1 of 22 days have no reading."
    assert "highest 300 on 12 Oct" in visual.summary
    assert visual.granularity == "day"


async def test_a_weekly_trend_is_drawn_by_week(shop: Shop) -> None:
    await seed(shop, "2026-07-01", "2026-10-22", lambda d: {"reach": 10})
    got = await shop.call("metric_trend", {"metric": "reach", "range": "the last 90 days"}, now=NOW)
    assert isinstance(got.visual, TrendVisual)
    assert got.visual.granularity == "week"
    assert len(got.visual.points) == len(got.points) <= 14


async def test_a_trend_and_a_comparison_cite_the_weekly_report_of_their_period(shop: Shop) -> None:
    """VIS-13: the latest finished week inside the period (12 to 18 Oct on Fri 23 Oct), for the
    account when the question named one; a period without a whole week cites none."""
    await seed(shop, "2026-10-01", "2026-10-22", lambda d: {"reach": 100})
    every = await shop.call("metric_trend", {"metric": "reach", "range": "this month"}, now=NOW)
    [report] = [r for r in every.refs if r.kind == "report"]
    assert (report.week, report.parent_id) == (date(2026, 10, 12), None)
    assert report.label == "Weekly report, 12-18 Oct 2026"
    one = await shop.call(
        "metric_trend",
        {"metric": "reach", "range": "this month", "account": "@maple.bakery"},
        now=NOW,
    )
    [mine] = [r for r in one.refs if r.kind == "report"]
    assert (mine.week, mine.parent_id) == (date(2026, 10, 12), shop.account_id)
    assert mine.id != report.id
    compared = await shop.call("compare_periods", {"range": "the last 7 days"}, now=NOW)
    assert [r.kind for r in compared.refs] == []  # 7 days ending yesterday hold no whole week
    month = await shop.call("compare_periods", {"range": "this month"}, now=NOW)
    assert [r.week for r in month.refs if r.kind == "report"] == [date(2026, 10, 12)]


async def test_no_readings_means_no_line(shop: Shop) -> None:
    got = await shop.call("metric_trend", {"metric": "reach", "range": "this month"}, now=NOW)
    assert got.known_points == 0
    assert got.visual is None


async def test_a_trend_builds_nothing_with_the_setting_off(quiet: Shop) -> None:
    await seed(quiet, "2026-10-01", "2026-10-22", lambda d: {"reach": 100})
    got = await quiet.call("metric_trend", {"metric": "reach", "range": "this month"}, now=NOW)
    assert got.known_points == 22
    assert got.visual is None


# ---------------------------------------------------------------- table (VIS-09)


async def test_the_conversation_list_is_also_a_table(shop: Shop) -> None:
    await lead(shop, "Priya Shah", 82, text_="Do you ship to Pune?")
    await lead(shop, "Rahul K", None, text_="Price?")
    got = await shop.call("search_conversations", {"view": "needs_reply"})
    assert isinstance(got.visual, TableVisual)
    table = got.visual
    assert [c.label for c in table.columns] == [
        "Customer",
        "Platform",
        "Last message",
        "When",
        "Lead score",
    ]
    assert table.columns[-1].align == "right"
    assert table.total == got.total == 2
    assert table.more_route == "inbox?view=needs_reply"
    by_name = {r.cells[0]: r.cells for r in table.rows}
    assert by_name["Priya Shah"][2] == "Do you ship to Pune?"
    assert by_name["Priya Shah"][4] == 82
    assert by_name["Rahul K"][4] is None  # no score: empty, never zero


async def test_an_empty_search_has_no_table_and_off_builds_none(shop: Shop, quiet: Shop) -> None:
    assert (await shop.call("search_conversations", {})).visual is None
    await lead(quiet, "Priya", 50)
    assert (await quiet.call("search_conversations", {})).visual is None


# ---------------------------------------------------------------- a run shows the new kinds


@pytest.fixture
async def desk(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> dict[str, Any]:
    owner, me = await sign_in(client, clerk, email="owner@example.com")
    return {
        "app": app,
        "client": client,
        "clerk": clerk,
        "engine": engine,
        "wid": me["workspaces"][0]["id"],
        "owner": owner,
        "owner_id": me["id"],
    }


async def test_a_run_lists_a_lead_list_a_trend_and_a_table_in_step_order(
    desk: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from socialhood.agent import visuals
    from socialhood.schemas.agent import TrendPoint
    from socialhood.schemas.contacts import ContactListItem

    monkeypatch.setattr(desk["app"].state.settings, "agent_visuals_enabled", True)
    conversation = uuid.uuid4()
    leads = visuals.lead_list(
        items=[
            ContactListItem(
                id=uuid.uuid4(),
                social_account_id=uuid.uuid4(),
                platform="instagram",
                name="Priya",
                tags=[],
                lead_score=90,
                conversation_id=conversation,
            )
        ],
        total=1,
        more_route=None,
    ).model_dump(mode="json")
    points = [
        TrendPoint(day=date(2026, 10, 1), value=5, days_known=1),
        TrendPoint(day=date(2026, 10, 2), value=None, days_known=0),
        TrendPoint(day=date(2026, 10, 3), value=7, days_known=1),
    ]
    line = visuals.trend(
        metric="reach",
        granularity="day",
        period=visuals.period_of(date(2026, 10, 1), date(2026, 10, 3)),
        account_label=None,
        points=points,
        known_points=2,
        first=points[0],
        last=points[2],
        lowest=points[0],
        highest=points[2],
        change_pct=40.0,
        direction="up",
        note=None,
    ).model_dump(mode="json")
    grid = visuals.table(
        title="Orders",
        columns=[visuals.Column("order", "Order"), visuals.Column("total", "Total", figures=True)],
        rows=[["#1", "INR 10.00"]],
        total=1,
        more_route="orders",
    ).model_dump(mode="json")

    def step(visual: dict[str, Any]) -> dict[str, Any]:
        return {
            "kind": "tool",
            "tool": "list_contacts",
            "tier": "read",
            "status": "succeeded",
            "result": {"summary": "x", "refs": [], "caveats": [], "visual": visual},
        }

    made = await make_agent_run(
        desk["engine"],
        workspace_id=desk["wid"],
        requested_by_user_id=desk["owner_id"],
        steps=[
            step(leads),
            step(line),
            step(grid),
            {"kind": "report", "args": {}, "result": {"summary": "Wrote the answer"}},
        ],
    )
    response = await desk["client"].get(
        f"/v1/w/{desk['wid']}/agent/runs/{made.id}", headers=desk["clerk"].headers(desk["owner"])
    )
    shown = response.json()["visuals"]
    assert [v["kind"] for v in shown] == ["lead_list", "trend", "table"]
    assert shown[0]["items"][0]["conversation_id"] == str(conversation)
    assert shown[1]["points"][1]["value"] is None
    assert shown[2]["rows"][0]["cells"] == ["#1", "INR 10.00"]
