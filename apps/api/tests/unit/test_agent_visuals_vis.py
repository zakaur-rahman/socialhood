"""VIS-07 to VIS-12 (C-123): the trend, lead list and table builders are pure functions of the
tool's data, a gap stays a gap, caps and links are enforced in the types, the biggest visuals fit
in 8 KB, the lead-list follow-up fits the run's credit cap, and the awaiting_reply filter reaches
the SQL."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from socialhood.agent import visuals
from socialhood.agent.registry import Release, registry
from socialhood.agent.report import model_view
from socialhood.agent.tools import load_tools
from socialhood.models.agent import MAX_MODEL_TURNS, MAX_TOOL_CALLS, RUN_CREDIT_CAP, RiskTier
from socialhood.schemas.agent import (
    LEAD_REPLY_MAX,
    MAX_LEADS,
    MAX_TABLE_COLUMNS,
    MAX_TABLE_ROWS,
    MAX_TREND_POINTS,
    MAX_VISUAL_BYTES,
    VISUAL_ADAPTER,
    AnswerRef,
    TableVisual,
    TrendPoint,
)
from socialhood.schemas.contacts import ContactListItem
from socialhood.services import agent_runs
from socialhood.services.contacts import ContactFilter, _filtered

PERIOD = visuals.period_of(date(2026, 10, 1), date(2026, 10, 30))


def point(day: int, value: float | None, known: int = 1) -> TrendPoint:
    return TrendPoint(day=date(2026, 10, day), value=value, days_known=known if value else 0)


def make_trend(points: list[TrendPoint], **over: Any) -> Any:
    known = [p for p in points if p.value is not None]
    args: dict[str, Any] = {
        "metric": "reach",
        "granularity": "day",
        "period": PERIOD,
        "account_label": "@maple.bakery",
        "points": points,
        "known_points": len(known),
        "first": known[0] if known else None,
        "last": known[-1] if known else None,
        "lowest": min(known, key=lambda p: p.value or 0) if known else None,
        "highest": max(known, key=lambda p: p.value or 0) if known else None,
        "change_pct": 25.0,
        "direction": "up",
        "note": None,
    }
    return visuals.trend(**{**args, **over})


# ---------------------------------------------------------------- trend (VIS-07)


def test_a_trend_keeps_the_tools_points_and_a_gap_stays_a_gap() -> None:
    points = [point(1, 100), point(2, None), point(3, 150)]
    visual = make_trend(points)
    assert [p.value for p in visual.points] == [100, None, 150]  # never a zero
    assert visual.known_points == 2
    assert visual.metric_label == "Reach"
    assert visual.change_pct == 25.0
    assert visual.title == "Reach, 1-30 Oct 2026: @maple.bakery"


def test_the_summary_says_the_chart_in_words_from_the_tools_numbers() -> None:
    visual = make_trend([point(1, 1200), point(2, None), point(3, 1500), point(4, 800)])
    assert visual.summary == (
        "Reach by day, 1-30 Oct 2026. From 1,200 on 1 Oct to 800 on 4 Oct (+25.0%)."
        " Lowest 800 on 4 Oct, highest 1,500 on 3 Oct."
    )


def test_a_summary_without_a_change_or_with_one_reading() -> None:
    one = make_trend([point(5, 90)])
    assert one.summary.endswith("One reading: 90 on 5 Oct.")
    nothing = make_trend([point(1, None), point(2, None)])
    assert nothing.summary.endswith("No readings.")
    no_pct = make_trend([point(1, 10), point(2, 20)], change_pct=None)
    assert "to 20 on 2 Oct." in no_pct.summary


def test_a_trend_longer_than_the_cap_fails_the_build_instead_of_being_cut() -> None:
    too_many = [
        TrendPoint(day=date(2026, 1, 1) + timedelta(days=i), value=1.0, days_known=1)
        for i in range(MAX_TREND_POINTS + 1)
    ]
    assert visuals.safe("trend", lambda: make_trend(too_many)) is None
    fits = too_many[:MAX_TREND_POINTS]
    assert visuals.safe("trend", lambda: make_trend(fits)) is not None


def test_the_biggest_trend_fits_in_eight_kilobytes() -> None:
    points = [
        TrendPoint(day=date(2026, 1, 1) + timedelta(days=i), value=123456789.5, days_known=7)
        for i in range(MAX_TREND_POINTS)
    ]
    visual = make_trend(points, account_label="@" + "a" * 100, note="n" * 300)
    assert visuals.size_of(visual) <= MAX_VISUAL_BYTES
    assert len(visual.points) == MAX_TREND_POINTS


# ---------------------------------------------------------------- lead_list (VIS-08, VIS-12)


def lead(score: int | None, *, conversation: bool = True, name: str = "Priya") -> ContactListItem:
    return ContactListItem(
        id=uuid.uuid4(),
        social_account_id=uuid.uuid4(),
        platform="instagram",
        name=name,
        tags=[],
        lead_score=score,
        conversation_id=uuid.uuid4() if conversation else None,
        last_activity_at=datetime(2026, 10, 24, tzinfo=UTC),
    )


def test_a_lead_list_keeps_the_services_order_and_numbers() -> None:
    leads = [lead(90), lead(72), lead(None)]
    visual = visuals.lead_list(
        items=leads, total=14, more_route="inbox?view=needs_reply", activity=["2 hours ago"]
    )
    assert [r.lead_score for r in visual.items] == [90, 72, None]
    assert [r.contact_id for r in visual.items] == [c.id for c in leads]
    assert visual.total == 14  # all that wait, not only those listed
    assert visual.items[0].last_activity_label == "2 hours ago"
    assert visual.items[2].last_activity_label is None
    assert visual.more_route == "inbox?view=needs_reply"


def test_a_lead_list_shows_at_most_ten_and_clips_customer_names() -> None:
    leads = [lead(i, name="N" * 200) for i in range(MAX_LEADS + 5)]
    visual = visuals.lead_list(items=leads, total=15, more_route=None)
    assert len(visual.items) == MAX_LEADS
    assert all(len(r.name) <= 60 for r in visual.items)


def test_replies_are_prepared_for_the_best_leads_that_have_a_conversation() -> None:
    leads = [lead(95, conversation=False), lead(90), lead(80), lead(70), lead(60)]
    visual = visuals.lead_list(items=leads, total=5, more_route=None)
    assert visual.reply_ids == [c.conversation_id for c in leads[1:4]]
    assert len(visual.reply_ids) == LEAD_REPLY_MAX
    # A contact who never messaged still opens, but has nothing to draft a reply to.
    assert visual.items[0].conversation_id is None


def test_the_reply_follow_up_fits_the_runs_caps() -> None:
    """draft_reply is 2 credits and one tool call. Even one model turn per draft plus the
    final answer stays inside the credit cap, and the tool calls inside the loop's cap."""
    load_tools()
    draft = registry.get("draft_reply")
    assert draft is not None
    assert draft.tier == RiskTier.DRAFT  # a draft: nothing is ever sent
    assert LEAD_REPLY_MAX <= MAX_TOOL_CALLS
    worst_turns = min(LEAD_REPLY_MAX + 1, MAX_MODEL_TURNS)
    assert 2 * LEAD_REPLY_MAX + worst_turns <= RUN_CREDIT_CAP


def test_the_lead_visual_ids_cap_is_in_the_type() -> None:
    leads = [lead(i) for i in range(MAX_LEADS)]
    visual = visuals.lead_list(items=leads, total=10, more_route=None)
    stored = visual.model_dump(mode="json")
    stored["reply_ids"] = [str(uuid.uuid4()) for _ in range(LEAD_REPLY_MAX + 1)]
    assert visuals.read(stored) is None


def test_the_biggest_lead_list_fits_in_eight_kilobytes() -> None:
    leads = [lead(100, name="N" * 200) for _ in range(MAX_LEADS)]
    visual = visuals.lead_list(
        items=leads,
        total=10**9,
        more_route="inbox?view=needs_reply",
        activity=["a" * 100] * MAX_LEADS,
    )
    assert visuals.size_of(visual) <= MAX_VISUAL_BYTES


# ---------------------------------------------------------------- table (VIS-09)

COLUMNS = [
    visuals.Column("order", "Order"),
    visuals.Column("customer", "Customer"),
    visuals.Column("total", "Total", figures=True),
]


def make_table(rows: list[list[Any]], **over: Any) -> TableVisual:
    args: dict[str, Any] = {
        "title": "Orders",
        "columns": COLUMNS,
        "rows": rows,
        "total": len(rows),
        "more_route": "orders",
    }
    return visuals.table(**{**args, **over})


def test_a_table_aligns_figures_right_and_keeps_the_cells() -> None:
    visual = make_table([["#12", "Priya", "INR 1598.00"], ["#13", None, "INR 799.00"]])
    assert [c.align for c in visual.columns] == ["left", "left", "right"]
    assert [r.cells for r in visual.rows] == [
        ["#12", "Priya", "INR 1598.00"],
        ["#13", None, "INR 799.00"],
    ]


def test_a_table_shows_at_most_ten_rows_and_counts_the_rest() -> None:
    rows = [[f"#{i}", "x", "INR 1.00"] for i in range(MAX_TABLE_ROWS + 7)]
    visual = make_table(rows, total=40)
    assert len(visual.rows) == MAX_TABLE_ROWS
    assert visual.total == 40  # the "+N more" is total minus the rows shown


def test_a_table_has_at_most_six_columns_and_a_cell_per_column() -> None:
    wide = [visuals.Column(f"c{i}", f"C{i}") for i in range(MAX_TABLE_COLUMNS + 1)]
    with pytest.raises(ValueError, match="1 to 6 columns"):
        make_table([["a"] * 7], columns=wide)
    with pytest.raises(ValueError, match="a cell for every column"):
        make_table([["only one cell"]])
    six = wide[:MAX_TABLE_COLUMNS]
    assert len(make_table([["a"] * 6], columns=six).columns) == 6


def test_customer_text_in_a_cell_is_clipped() -> None:
    visual = make_table([["#1", "C" * 500, "INR 1.00"]])
    assert len(str(visual.rows[0].cells[1])) <= visuals.TEXT_CELL_CHARS


@pytest.mark.parametrize(
    "route",
    [
        "https://evil.example/x",
        "//evil.example",
        "../etc",
        "inbox#frag",
        "inbox?view=a b",
        "/inbox",
    ],
)
def test_a_link_must_be_a_plain_workspace_path(route: str) -> None:
    assert (
        visuals.safe("table", lambda: make_table([["#1", "x", "INR 1.00"]], more_route=route))
        is None
    )


@pytest.mark.parametrize("route", ["orders", "inbox?view=needs_reply", "settings/agent"])
def test_plain_workspace_paths_are_kept(route: str) -> None:
    assert make_table([["#1", "x", "INR 1.00"]], more_route=route).more_route == route


def test_the_biggest_table_fits_in_eight_kilobytes() -> None:
    columns = [visuals.Column(f"col{i}", "L" * 60, figures=i % 2 == 0) for i in range(6)]
    rows = [["c" * 200] * 6 for _ in range(MAX_TABLE_ROWS)]
    visual = make_table(rows, columns=columns, title="T" * 300, total=10**9)
    assert visuals.size_of(visual) <= MAX_VISUAL_BYTES


# ---------------------------------------------------------------- the union, the model, the run


def test_the_new_kinds_read_back_and_unknown_ones_are_dropped() -> None:
    for visual in (
        make_trend([point(1, 5), point(2, 6)]),
        visuals.lead_list(items=[lead(50)], total=1, more_route=None),
        make_table([["#1", "x", "INR 1.00"]]),
    ):
        assert visuals.read(visual.model_dump(mode="json")) == visual
        assert VISUAL_ADAPTER.validate_python(visual.model_dump(mode="json")) == visual
    assert visuals.read({"kind": "pie_chart"}) is None
    assert set(visuals.KINDS) >= {"trend", "lead_list", "table"}


def test_the_model_never_reads_the_new_visuals() -> None:
    visual = visuals.lead_list(items=[lead(50)], total=1, more_route=None)
    result = {"summary": "1 contact", "contacts": [], "visual": visual.model_dump(mode="json")}
    seen = model_view(result, [])
    assert "visual" not in seen


def test_a_run_shows_the_new_kinds_in_step_order() -> None:
    stored = [
        make_trend([point(1, 5), point(2, 6)]).model_dump(mode="json"),
        visuals.lead_list(items=[lead(50)], total=1, more_route=None).model_dump(mode="json"),
        make_table([["#1", "x", "INR 1.00"]]).model_dump(mode="json"),
    ]
    assert [v.kind for v in agent_runs.shown_visuals(stored)] == ["trend", "lead_list", "table"]


def test_the_contact_ref_kind_exists_and_is_a_valid_citation() -> None:
    ref = AnswerRef(kind="contact", id=uuid.uuid4(), label="Priya")
    assert ref.kind == "contact"


def test_the_visual_json_has_no_secret_like_names() -> None:
    for model in (TableVisual,):
        assert not any(k in model.model_json_schema()["properties"] for k in ("token", "secret"))


# ---------------------------------------------------------------- the tools


def test_the_tools_that_draw_these_exist_with_their_roles() -> None:
    load_tools()
    shipped = {s.name: s for s in registry.available(release=Release.R1)}
    for name in ("list_contacts", "search_conversations", "draft_reply", "metric_trend"):
        assert name in shipped
    # list_contacts and search_conversations are for any member, as in the app; orders are admin.
    assert shipped["list_contacts"].min_role.value == "agent"
    assert shipped["list_orders"].min_role.value == "admin"
    assert "awaiting_reply" in shipped["list_contacts"].input_model.model_fields


# ---------------------------------------------------------------- the awaiting_reply filter


def sql(filt: ContactFilter) -> str:
    """The WHERE clause only (the SELECT lists every conversation column)."""
    text = str(_filtered(filt).compile(dialect=postgresql.dialect()))
    return text.partition("WHERE")[2]


def test_awaiting_reply_filters_on_the_conversation_flag() -> None:
    waiting = sql(ContactFilter(awaiting_reply=True))
    assert "conversations.awaiting_reply IS true" in waiting
    assert "awaiting_reply" not in sql(ContactFilter())
    answered = sql(ContactFilter(awaiting_reply=False))
    assert "coalesce(conversations.awaiting_reply" in answered


def test_a_trend_point_model_rejects_a_week_of_more_than_seven_days() -> None:
    with pytest.raises(ValidationError):
        TrendPoint(day=date(2026, 10, 1), value=1.0, days_known=8)


# ---------------------------------------------------------------- the orders table


def test_the_orders_table_has_right_aligned_money_and_links_to_orders() -> None:
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    from socialhood.agent.tools import orders

    ctx: Any = SimpleNamespace(
        timezone=ZoneInfo("Asia/Kolkata"), now=datetime(2026, 10, 23, tzinfo=UTC)
    )
    lines = [
        orders.OrderLine(
            id=uuid.uuid4(),
            number=n,
            status="awaiting_payment",
            total="INR 1598.00",
            customer="@priya" if n % 2 else None,
            items=["2 x Cotton kurta"],
            created_at=datetime(2026, 10, 22, tzinfo=UTC),
        )
        for n in range(1, 13)
    ]
    table = orders._orders_table(ctx, lines, 40)
    assert [c.label for c in table.columns] == ["Order", "Customer", "Status", "Total", "Date"]
    assert table.columns[3].align == "right"
    assert len(table.rows) == MAX_TABLE_ROWS
    assert table.rows[0].cells[:4] == ["#1", "@priya", "Awaiting payment", "INR 1598.00"]
    assert table.rows[1].cells[1] is None
    assert (table.total, table.more_route) == (40, "orders")


# ---------------------------------------------------------------- the web's list of visual tools


def test_the_web_refetches_for_exactly_the_tools_that_can_carry_a_visual() -> None:
    """VIS-10: apps/web/src/lib/agent/cache.ts lists the tools whose finished step makes the
    client fetch the run again. It must be the tools whose result has a ``visual``."""
    import re
    from pathlib import Path

    source = Path(__file__).parents[3] / "web" / "src" / "lib" / "agent" / "cache.ts"
    listed = re.search(
        r"VISUAL_TOOLS[^=]*=\s*new Set\(\[(.*?)\]\)", source.read_text("utf-8"), re.S
    )
    assert listed is not None
    web = set(re.findall(r'"([a-z_]+)"', listed.group(1)))
    load_tools()
    api = {
        spec.name
        for spec in registry.available(release=Release.R1)
        if "visual" in spec.result_model.model_fields
    }
    assert web == api
