"""The weekly report per connected account: ``account_id`` narrows every figure to that account
(another workspace's account is 404), and the workspace-wide report lists each account's own
numbers side by side."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.models.identity import Workspace
from socialhood.platforms.capabilities import Capability
from socialhood.schemas.reports import WeeklyReport
from socialhood.services import reports
from socialhood.services.analytics.common import View
from tests.integration.test_weekly_digest import NINE_IST, Seed, ist
from tests.integration.test_weekly_report import (
    KOLKATA,
    REPORT_WEEK,
    clock,
    metric,
    seed_account_week,
)
from tests.support.api import Clerk
from tests.support.automation_api import workspace
from tests.support.inbox import make_account
from tests.support.notify_team import Team, make_team


def insights_on_instagram_only(account: Any) -> frozenset[Capability]:
    if account.platform == "instagram":
        return frozenset({Capability.ACCOUNT_INSIGHTS})
    return frozenset()


@pytest.fixture
async def team(engine: AsyncEngine, clean_db: None) -> Team:
    return await make_team(engine, timezone=KOLKATA)


async def report_for(
    team: Team, *, account_id: uuid.UUID | None = None, breakdown: bool = False
) -> WeeklyReport:
    with workspace_scope(team.wid):
        async with team.maker() as session:
            found = await session.get(Workspace, team.wid)
            assert found is not None
            return await reports.build(
                session,
                View(found.timezone, NINE_IST, insights_on_instagram_only),
                found,
                week_start=REPORT_WEEK,
                account_id=account_id,
                with_breakdown=breakdown,
            )


async def two_accounts(team: Team) -> tuple[Seed, Seed]:
    """Instagram: two people write in the week and one is answered, one wrote the week before.
    WhatsApp: one person writes in the week."""
    insta = Seed(team, await make_account(team.engine, team.wid, username="maple.bakery"))
    whats = Seed(
        team,
        await make_account(team.engine, team.wid, platform="whatsapp", username="+91 98765"),
    )
    asha = await insta.conversation("Asha")
    await insta.message(asha, ist(22, 10, 0))
    await insta.message(asha, ist(22, 10, 5), source="human")
    bina = await insta.conversation("Bina")
    await insta.message(bina, ist(23, 10, 0))
    await insta.message(bina, ist(15, 10, 0, 0, 9))  # the week before
    chetan = await whats.conversation("Chetan")
    await whats.message(chetan, ist(24, 10, 0))
    return insta, whats


async def test_an_account_report_has_only_that_accounts_figures(team: Team) -> None:
    insta, whats = await two_accounts(team)

    everyone = await report_for(team)
    mine = await report_for(team, account_id=insta.account_id)
    theirs = await report_for(team, account_id=whats.account_id)

    assert metric(everyone, "messages_received").value == 3
    assert metric(mine, "messages_received").value == 2
    assert metric(mine, "messages_received").previous == 1
    assert metric(mine, "conversations").value == 2
    assert metric(theirs, "messages_received").value == 1
    assert metric(theirs, "messages_received").previous is None  # before the workspace existed
    assert [p.value for p in metric(mine, "messages_received").series][-2:] == [1, 2]
    assert mine.account is not None
    assert mine.account.id == insta.account_id
    assert mine.account.platform == "instagram"
    assert everyone.account is None
    assert mine.breakdown is None
    # The picker lists both accounts either way.
    assert {a.id for a in mine.accounts} == {insta.account_id, whats.account_id}
    # Questions the AI could not answer belong to the workspace, not to an account.
    assert (mine.open_questions, mine.top_questions) == (0, [])
    # The account insights are that account's: WhatsApp has none to grant.
    reach = next(a for a in theirs.account_metrics if a.figure.metric == "reach")
    assert reach.figure.current.value is None
    assert reach.figure.current.unavailable == "insights_not_granted"


async def test_the_breakdown_lists_each_account_with_its_own_numbers(team: Team) -> None:
    insta, whats = await two_accounts(team)

    report = await report_for(team, breakdown=True)

    assert report.breakdown is not None
    by_account = {row.account.id: row for row in report.breakdown}
    assert set(by_account) == {insta.account_id, whats.account_id}
    assert by_account[insta.account_id].account.platform == "instagram"
    assert by_account[whats.account_id].account.platform == "whatsapp"

    def figure(account: uuid.UUID, key: str) -> Any:
        return next(m for m in by_account[account].metrics if m.key == key)

    messages = figure(insta.account_id, "messages_received")
    assert (messages.value, messages.previous, messages.direction) == (2, 1, "up")
    assert len(messages.series) == reports.SERIES_WEEKS
    assert figure(insta.account_id, "replies_sent").value == 1
    assert not figure(whats.account_id, "replies_sent").value  # nothing (the test workspace is new)
    assert figure(whats.account_id, "messages_received").value == 1
    # The breakdown adds up to the workspace-wide figure.
    total = sum(figure(a, "messages_received").value for a in by_account)
    assert total == metric(report, "messages_received").value
    # WhatsApp gives no insights: None with the reason, never zero.
    reach = figure(whats.account_id, "reach")
    assert reach.value is None
    assert reach.unavailable == "insights_not_granted"
    assert figure(insta.account_id, "reach").unavailable in (None, "no_readings")


async def test_comments_are_counted_per_account(team: Team) -> None:
    insta, whats = await two_accounts(team)
    media = await team.insert(
        "INSERT INTO media_items (workspace_id, social_account_id, platform_media_id,"
        " media_type, posted_at) VALUES (:w, :a, 'm1', 'image', :at) RETURNING id",
        w=team.wid,
        a=insta.account_id,
        at=ist(20, 9),
    )
    for _ in range(2):
        await team.execute(
            "INSERT INTO comments (workspace_id, social_account_id, media_item_id,"
            " platform_comment_id, text, commented_at) VALUES (:w, :a, :m, :p, 'nice', :at)",
            w=team.wid,
            a=insta.account_id,
            m=media,
            p=uuid.uuid4().hex,
            at=ist(23, 12),
        )

    report = await report_for(team, breakdown=True)

    assert report.breakdown is not None
    comments = {
        row.account.id: next(m for m in row.metrics if m.key == "comments_received").value
        for row in report.breakdown
    }
    assert comments == {insta.account_id: 2, whats.account_id: 0}
    only = await report_for(team, account_id=insta.account_id)
    assert metric(only, "comments_received").value == 2
    assert [p.id for p in only.top_posts] == [media]
    none = await report_for(team, account_id=whats.account_id)
    assert (metric(none, "comments_received").value, none.top_posts) == (0, [])


async def test_the_route_filters_by_account_and_hides_other_workspaces(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, clean_db: None
) -> None:
    mine = await workspace(client, clerk)
    theirs = await workspace(client, clerk, email="other@example.com")
    await seed_account_week(mine, engine)
    await seed_account_week(theirs, engine)

    with clock(NINE_IST):
        body = await mine.ok(
            "GET", "/reports/weekly", params={"week": "2026-09-21", "account_id": mine.account_id}
        )
        everyone = await mine.ok("GET", "/reports/weekly", params={"week": "2026-09-21"})
        other = await mine.call(
            "GET",
            "/reports/weekly",
            params={"week": "2026-09-21", "account_id": theirs.account_id},
        )
        junk = await mine.call("GET", "/reports/weekly", params={"account_id": "nope"})

    WeeklyReport.model_validate(body)
    assert body["account"]["id"] == str(mine.account_id)
    assert body["breakdown"] is None
    assert everyone["account"] is None
    assert [row["account"]["id"] for row in everyone["breakdown"]] == [str(mine.account_id)]
    assert other.status_code == 404, other.text
    assert other.json()["code"] == "not_found"
    assert junk.status_code == 422
    assert date.fromisoformat(body["week_start"]) == REPORT_WEEK
