"""The Home redesign's additions to GET …/overview (C-065): the custom range, the Live Priority
Queue, the latest open question with where it came from, the most commented posts' engagement
rate, the connected channels and the oldest wait. The numbers the weekly digest shares are
tested in test_overview.py; here the custom range is checked against the same hand-written SQL.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
import time_machine
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.models.identity import Workspace
from socialhood.schemas.workspaces import Overview, OverviewRange
from socialhood.services import overview as overview_service
from socialhood.services import priority_queue
from socialhood.services.conversations import ListFilters, inbox_counts, list_conversations
from tests.integration.test_overview import (
    KOLKATA,
    NOW,
    Hand,
    Seed,
    hand_period,
    ist,
    seed_main_account,
    seed_month,
)
from tests.support.ai import make_gap
from tests.support.api import Clerk
from tests.support.automation_api import Ws, workspace
from tests.support.inbox import make_account, make_thread
from tests.support.notify_team import Team, make_team


@pytest.fixture
async def team(engine: AsyncEngine, clean_db: None) -> Team:
    return await make_team(engine, timezone=KOLKATA)


async def overview(
    team: Team,
    range_: OverviewRange = "7d",
    now: datetime = NOW,
    *,
    since: date | None = None,
    until: date | None = None,
    human_agent: bool = False,
) -> dict[str, Any]:
    with workspace_scope(team.wid):
        async with team.maker() as session:
            workspace = await session.get(Workspace, team.wid)
            assert workspace is not None
            result = await overview_service.overview(
                session,
                workspace,
                range_=range_,
                now=now,
                since=since,
                until=until,
                human_agent=human_agent,
            )
    return result.model_dump(mode="json")


# ---------------------------------------------------------------- custom range


async def test_a_custom_range_of_the_last_seven_days_is_the_seven_days(team: Team) -> None:
    await seed_month(team)

    week = await overview(team, "7d")
    custom = await overview(team, "custom", since=date(2026, 9, 24), until=date(2026, 9, 30))

    assert (custom["range"], custom["days"], week["days"]) == ("custom", 7, 7)
    assert {k: v for k, v in custom.items() if k != "range"} == {
        k: v for k, v in week.items() if k != "range"
    }


async def test_a_custom_range_matches_the_hand_written_sql_and_compares_as_many_days_before(
    team: Team,
) -> None:
    await seed_month(team)

    body = await overview(team, "custom", since=date(2026, 9, 19), until=date(2026, 9, 30))

    assert body["days"] == 12
    assert body["current"] == await hand_period(
        Hand(team, KOLKATA, date(2026, 9, 19), date(2026, 9, 30))
    )
    assert body["previous"] == await hand_period(
        Hand(team, KOLKATA, date(2026, 9, 7), date(2026, 9, 18))
    )
    # Farah (the 20th) is in; Zoya's message at 23:59:59 on the 23rd too.
    assert body["current"]["messages_received"] == 11

    # A range that ends before today: the week before, and the week before that to compare.
    past = await overview(team, "custom", since=date(2026, 9, 17), until=date(2026, 9, 23))
    week = await overview(team, "7d")
    assert past["current"] == week["previous"]
    assert (past["previous"]["since"], past["previous"]["until"]) == ("2026-09-10", "2026-09-16")
    assert past["messages_today"] == week["messages_today"]  # states and today are still now


@pytest.mark.parametrize(
    ("since", "until", "field", "detail"),
    [
        (date(2026, 9, 25), date(2026, 9, 24), "from", "The start date is after the end date."),
        (date(2026, 9, 25), date(2026, 10, 1), "to", "The end date is in the future."),
        (date(2026, 7, 2), date(2026, 9, 30), "from", "A custom range is at most 90 days."),
        (None, date(2026, 9, 30), "from", "A custom range needs a start and an end date."),
    ],
)
async def test_a_custom_range_is_checked(
    team: Team, since: date | None, until: date | None, field: str, detail: str
) -> None:
    with pytest.raises(ApiError) as caught:
        await overview(team, "custom", since=since, until=until)
    assert (caught.value.code, caught.value.detail) == ("validation_error", detail)
    assert [e.field for e in caught.value.errors] == [field]


async def test_ninety_days_up_to_today_is_the_longest_custom_range(team: Team) -> None:
    body = await overview(team, "custom", since=date(2026, 7, 3), until=date(2026, 9, 30))
    assert (body["days"], body["previous"]["since"]) == (90, "2026-04-04")


async def test_the_route_takes_from_and_to(
    client: httpx.AsyncClient, clerk: Clerk, queue: None
) -> None:
    ws = await workspace(client, clerk)
    await ws.ok("PATCH", "", json={"timezone": KOLKATA})

    with time_machine.travel(NOW, tick=True):
        custom = await ws.ok("GET", "/overview?from=2026-09-19&to=2026-09-30")
        default = await ws.ok("GET", "/overview")
        month = await ws.ok("GET", "/overview?range=30d")
        errors = {
            name: await ws.call("GET", f"/overview?{query}")
            for name, query in {
                "backwards": "from=2026-09-25&to=2026-09-24",
                "future": "from=2026-09-25&to=2026-10-01",
                "too_long": "from=2026-06-01&to=2026-09-30",
                "half": "from=2026-09-25",
                "both": "range=7d&from=2026-09-25&to=2026-09-30",
                "not_a_date": "from=25-09-2026&to=2026-09-30",
            }.items()
        }

    Overview.model_validate(custom)
    assert (custom["range"], custom["days"]) == ("custom", 12)
    assert (custom["current"]["since"], custom["current"]["until"]) == ("2026-09-19", "2026-09-30")
    assert (custom["previous"]["since"], custom["previous"]["until"]) == (
        "2026-09-07",
        "2026-09-18",
    )
    assert (default["range"], default["days"], month["range"], month["days"]) == (
        "7d",
        7,
        "30d",
        30,
    )
    for name, response in errors.items():
        assert response.status_code == 422, (name, response.text)
        assert response.json()["code"] == "validation_error", name
    fields = {name: [e["field"] for e in r.json()["errors"]] for name, r in errors.items()}
    assert fields["backwards"] == fields["too_long"] == ["from"]
    assert fields["future"] == fields["half"] == ["to"]
    assert fields["both"] == ["range"]


# ---------------------------------------------------------------- the priority queue


class Queue:
    """Conversations seeded as ingest, analysis and suggestions leave them, seen at NOW."""

    def __init__(self, team: Team, instagram: uuid.UUID, whatsapp: uuid.UUID) -> None:
        self.team = team
        self.accounts = {"instagram": instagram, "whatsapp": whatsapp}

    async def conversation(
        self,
        name: str,
        *,
        wrote: list[timedelta] | None = None,  # the customer's messages, this long before NOW
        replied: timedelta | None = None,  # the business's last message, this long before NOW
        platform: str = "instagram",
        awaiting_reply: bool = True,
        needs_human: bool = False,
        status: str = "open",
        lead_score: int | None = None,
        priority: str | None = None,
        text: str | None = None,
    ) -> uuid.UUID:
        account = self.accounts[platform]
        contact = await self.team.insert(
            "INSERT INTO contacts (workspace_id, social_account_id, platform_user_id,"
            " display_name, username) VALUES (:w, :a, :p, :n, :u) RETURNING id",
            w=self.team.wid,
            a=account,
            p=f"id_{uuid.uuid4().hex[:10]}",
            n=name,
            u=name.lower().replace(" ", "."),
        )
        times = sorted((NOW - ago for ago in wrote or []), reverse=False)
        last_in = times[-1] if times else None
        last_out = NOW - replied if replied is not None else None
        last = max((t for t in (last_in, last_out) if t is not None), default=None)
        conv = await self.team.insert(
            "INSERT INTO conversations (workspace_id, social_account_id, contact_id, platform,"
            " status, needs_human, needs_human_reason, awaiting_reply, last_message_at,"
            " last_inbound_at, last_outbound_at, lead_score, priority)"
            " VALUES (:w, :a, :c, :pl, :s, :h, :hr, :r, :at, :li, :lo, :ls, :pr) RETURNING id",
            w=self.team.wid,
            a=account,
            c=contact,
            pl=platform,
            s=status,
            h=needs_human,
            hr="complaint" if needs_human else None,
            r=awaiting_reply,
            at=last,
            li=last_in,
            lo=last_out,
            ls=lead_score,
            pr=priority,
        )
        for i, at in enumerate(times):
            final = i == len(times) - 1
            await self.message(conv, account, at, text if final and text else f"{name} #{i + 1}")
        if last_out is not None:
            await self.message(conv, account, last_out, "Thanks!", inbound=False)
        return conv

    async def message(
        self, conv: uuid.UUID, account: uuid.UUID, at: datetime, text: str, *, inbound: bool = True
    ) -> uuid.UUID:
        return await self.team.insert(
            "INSERT INTO messages (workspace_id, conversation_id, social_account_id, direction,"
            " source, kind, text, occurred_at, status)"
            " VALUES (:w, :c, :a, :d, :s, 'text', :t, :at, :st) RETURNING id",
            w=self.team.wid,
            c=conv,
            a=account,
            d="inbound" if inbound else "outbound",
            s="customer" if inbound else "human",
            t=text,
            at=at,
            st="received" if inbound else "sent",
        )

    async def suggestion(
        self, conv: uuid.UUID, *, status: str = "pending", can_answer: bool = True
    ) -> None:
        [row] = await self.team.rows(
            "SELECT id FROM messages WHERE conversation_id = :c AND direction = 'inbound'"
            " ORDER BY occurred_at DESC LIMIT 1",
            c=conv,
        )
        await self.team.execute(
            "INSERT INTO reply_suggestions (workspace_id, conversation_id, message_id, status,"
            " can_answer, reply_text) VALUES (:w, :c, :m, :s, :ok, :t)",
            w=self.team.wid,
            c=conv,
            m=row["id"],
            s=status,
            ok=can_answer,
            t="Yes, we do!" if can_answer else None,
        )


H = timedelta(hours=1)
M = timedelta(minutes=1)
LONG = "Hello! " + "Could you tell me whether the linen dress comes in a size larger? " * 3


async def seed_queue(team: Team) -> dict[str, uuid.UUID]:
    instagram = await seed_main_account(team)
    whatsapp = await make_account(team.engine, team.wid, platform="whatsapp", username="maple.wa")
    q = Queue(team, instagram, whatsapp)
    ids: dict[str, uuid.UUID] = {}
    # Needs you: first, whatever the window; the higher lead score first.
    ids["escalated_old"] = await q.conversation(
        "Escalated Old", wrote=[72 * H], awaiting_reply=False, needs_human=True
    )
    ids["escalated_lead"] = await q.conversation(
        "Escalated Lead", wrote=[1 * H], needs_human=True, lead_score=20
    )
    # Needs a reply, the window open: lead score, then priority, then the longest wait.
    ids["hot"] = await q.conversation("Hot Lead", wrote=[30 * M], lead_score=90, priority="low")
    ids["critical"] = await q.conversation(
        "Warm Critical", wrote=[10 * M], lead_score=50, priority="critical"
    )
    ids["warm_low"] = await q.conversation("Warm Low", wrote=[5 * H], lead_score=50, priority="low")
    # No score: the longest wait first. Waiting since 20 h (the reply 22 h ago answered 23 h).
    ids["long_wait"] = await q.conversation(
        "Long Wait", wrote=[23 * H, 20 * H, 19 * H], replied=22 * H, text=LONG
    )
    ids["short_wait"] = await q.conversation("Short Wait", wrote=[2 * H], priority="high")
    ids["whatsapp"] = await q.conversation("Wa Open", wrote=[3 * H], platform="whatsapp")
    # Left out.
    ids["archived"] = await q.conversation(
        "Archived", wrote=[1 * H], needs_human=True, status="archived", lead_score=99
    )
    ids["ig_closed"] = await q.conversation("Ig Closed", wrote=[31 * H, 30 * H], lead_score=95)
    ids["wa_closed"] = await q.conversation(
        "Wa Closed", wrote=[30 * H], platform="whatsapp", lead_score=95
    )
    ids["answered"] = await q.conversation(
        "Answered", wrote=[2 * H], replied=1 * H, awaiting_reply=False, lead_score=99
    )
    ids["empty"] = await q.conversation("No Messages", lead_score=99)  # no last message
    # Suggestions: only a pending draft that can answer counts.
    await q.suggestion(ids["hot"])
    await q.suggestion(ids["critical"], can_answer=False)
    await q.suggestion(ids["warm_low"], status="sent")
    await q.suggestion(ids["escalated_lead"], status="dismissed")
    await q.suggestion(ids["escalated_old"])
    return ids


async def queue_of(team: Team, *, human_agent: bool = False, limit: int = 20) -> list[Any]:
    with workspace_scope(team.wid):
        async with team.maker() as session:
            rows = await priority_queue.priority_queue(
                session, now=NOW, human_agent=human_agent, limit=limit
            )
    return [row.model_dump(mode="json") for row in rows]


async def test_the_queue_puts_needs_you_first_then_lead_score_priority_and_wait(
    team: Team,
) -> None:
    ids = await seed_queue(team)
    names = {v: k for k, v in ids.items()}

    queue = await queue_of(team)

    assert [names[uuid.UUID(row["id"])] for row in queue] == [
        "escalated_lead",  # needs you, lead 20
        "escalated_old",  # needs you, no score; its window closed long ago
        "hot",  # lead 90
        "critical",  # lead 50, critical
        "warm_low",  # lead 50, low
        "short_wait",  # no score: priority high before none
        "long_wait",  # no score, no priority: waiting since 20 h
        "whatsapp",  # waiting 3 h
    ]


async def test_the_queue_leaves_out_archived_closed_answered_and_other_workspaces(
    team: Team, engine: AsyncEngine
) -> None:
    ids = await seed_queue(team)
    other = await make_team(engine, timezone=KOLKATA)
    theirs = Queue(other, await seed_main_account(other), uuid.uuid4())
    await theirs.conversation("Not Ours", wrote=[5 * M], lead_score=100, needs_human=True)

    queue = {uuid.UUID(row["id"]) for row in await queue_of(team)}

    for left_out in ("archived", "ig_closed", "wa_closed", "answered", "empty"):
        assert ids[left_out] not in queue, left_out
    assert len(queue) == 8
    # With Human Agent, a person can still answer Instagram for 7 days; WhatsApp stays closed.
    agent = [uuid.UUID(row["id"]) for row in await queue_of(team, human_agent=True)]
    assert agent[2] == ids["ig_closed"]  # lead 95
    assert ids["wa_closed"] not in agent


async def test_the_queue_rows_carry_what_home_shows(team: Team) -> None:
    ids = await seed_queue(team)

    rows = {uuid.UUID(row["id"]): row for row in await queue_of(team)}

    hot = rows[ids["hot"]]
    assert hot["contact"]["display_name"] == "Hot Lead"
    assert hot["contact"]["username"] == "hot.lead"
    assert (hot["platform"], hot["lead_score"], hot["priority"]) == ("instagram", 90, "low")
    assert (hot["needs_you"], hot["awaiting_reply"], hot["has_pending_suggestion"]) == (
        False,
        True,
        True,
    )
    assert hot["last_customer_message"] == "Hot Lead #1"
    assert datetime.fromisoformat(hot["last_customer_message_at"]) == NOW - 30 * M
    assert datetime.fromisoformat(hot["window_closes_at"]) == NOW - 30 * M + 24 * H

    # A "can't answer" card, a sent or a dismissed suggestion is no draft to review.
    assert rows[ids["critical"]]["has_pending_suggestion"] is False
    assert rows[ids["warm_low"]]["has_pending_suggestion"] is False
    assert rows[ids["escalated_lead"]]["has_pending_suggestion"] is False

    old = rows[ids["escalated_old"]]
    assert (old["needs_you"], old["needs_human_reason"], old["window_closes_at"]) == (
        True,
        "complaint",
        None,
    )
    assert old["has_pending_suggestion"] is True

    wait = rows[ids["long_wait"]]
    assert datetime.fromisoformat(wait["waiting_since"]) == NOW - 20 * H  # the turn's start
    assert datetime.fromisoformat(wait["last_customer_message_at"]) == NOW - 19 * H
    assert len(wait["last_customer_message"]) <= priority_queue.PREVIEW_CHARS
    assert wait["last_customer_message"].endswith("…")
    assert wait["last_customer_message"].startswith("Hello! Could you tell me")

    wa = rows[ids["whatsapp"]]
    assert (wa["platform"], wa["priority"], wa["lead_score"]) == ("whatsapp", None, None)


async def test_the_overview_has_five_the_oldest_wait_and_agrees_with_the_inbox(
    team: Team,
) -> None:
    ids = await seed_queue(team)

    body = await overview(team)

    assert [row["id"] for row in body["priority_queue"]] == [
        row["id"] for row in (await queue_of(team))[:5]
    ]
    with workspace_scope(team.wid):
        async with team.maker() as session:
            counts = await inbox_counts(session)
            waiting = await list_conversations(
                session,
                ListFilters(view="needs_reply"),
                cursor=None,
                limit=100,
                ig_human_agent_enabled=False,
                now=NOW,
            )
    assert (body["needs_reply"], body["needs_you"]) == (counts.needs_reply, counts.needs_you)
    needs_reply = {item.id for item in waiting.items}
    for row in await queue_of(team):
        assert row["needs_you"] or uuid.UUID(row["id"]) in needs_reply
    # The oldest wait is over every "Needs reply" conversation, closed windows included:
    # Instagram's closed one began 31 h ago.
    assert ids["ig_closed"] in needs_reply
    assert datetime.fromisoformat(body["oldest_waiting_since"]) == NOW - 31 * H


async def test_an_empty_workspace_has_an_empty_queue(team: Team) -> None:
    body = await overview(team)
    assert body["priority_queue"] == []
    assert body["oldest_waiting_since"] is None
    assert (body["accounts_connected"], body["platforms_connected"]) == (0, [])
    assert body["latest_gap"] is None
    assert body["top_posts_engagement"] is None


# ---------------------------------------------------------------- connected channels


async def test_channels_connected_counts_active_accounts(team: Team) -> None:
    await seed_month(team)  # one active; needs reconnect, error and disconnected ones
    assert (await overview(team))["accounts_connected"] == 1
    await make_account(team.engine, team.wid, platform="whatsapp", username="maple.wa")
    body = await overview(team)
    assert (body["accounts_connected"], body["platforms_connected"]) == (
        2,
        ["instagram", "whatsapp"],
    )


# ---------------------------------------------------------------- the latest question


async def test_the_latest_open_question_names_its_conversation(team: Team) -> None:
    account = await seed_main_account(team)
    seed = Seed(team, account)
    dubai_conv = await seed.conversation("Priya")
    dubai = await seed.message(dubai_conv, NOW - 2 * 24 * H)
    eggless_conv = await seed.conversation("Arjun")
    old = await seed.message(eggless_conv, NOW - 3 * H)
    eggless = await seed.message(eggless_conv, NOW - 2 * H)
    await team.execute(
        "UPDATE messages SET text = :t WHERE id = :id", t="Any eggless cakes?", id=eggless
    )
    await make_gap(
        team.engine,
        workspace_id=team.wid,
        topic="shipping to uae",
        occurrences=5,
        first_seen_at=NOW - 3 * 24 * H,
        last_seen_at=NOW - 2 * 24 * H,
        example_message_ids=[dubai],
    )
    gap = await make_gap(
        team.engine,
        workspace_id=team.wid,
        topic="eggless options",
        occurrences=2,
        first_seen_at=NOW - 3 * H,
        last_seen_at=NOW - 2 * H,
        example_message_ids=[eggless, old],  # newest first
    )
    await make_gap(  # dismissed and answered ones are not open
        team.engine,
        workspace_id=team.wid,
        topic="gift wrapping",
        status="dismissed",
        last_seen_at=NOW - 1 * H,
        first_seen_at=NOW - 1 * H,
    )

    body = await overview(team)

    assert body["knowledge_gaps_open"] == 2
    assert [q["topic"] for q in body["top_questions"]] == ["shipping to uae", "eggless options"]
    assert body["latest_gap"] == {
        "id": str(gap),
        "topic": "eggless options",
        "question": "Any eggless cakes?",
        "asked": 2,
        "last_seen_at": body["latest_gap"]["last_seen_at"],
        "conversation_id": str(eggless_conv),
        "message_id": str(eggless),
    }
    assert datetime.fromisoformat(body["latest_gap"]["last_seen_at"]) == NOW - 2 * H

    # The customer unsent it: the next example; none left, the topic and no conversation.
    await team.execute("UPDATE messages SET deleted_at = :at WHERE id = :id", at=NOW, id=eggless)
    latest = (await overview(team))["latest_gap"]
    assert (latest["message_id"], latest["question"]) == (str(old), "hi")
    await team.execute("UPDATE messages SET deleted_at = :at WHERE id = :id", at=NOW, id=old)
    latest = (await overview(team))["latest_gap"]
    assert (latest["question"], latest["conversation_id"], latest["message_id"]) == (
        "eggless options",
        None,
        None,
    )


async def test_a_comments_question_has_no_conversation(team: Team) -> None:
    await make_gap(
        team.engine, workspace_id=team.wid, topic="sizes", first_seen_at=NOW, last_seen_at=NOW
    )
    latest = (await overview(team))["latest_gap"]
    assert (latest["topic"], latest["question"], latest["conversation_id"]) == (
        "sizes",
        "sizes",
        None,
    )


async def test_train_ai_answers_the_latest_question_through_the_faq_path(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, queue: None
) -> None:
    ws: Ws = await workspace(client, clerk)
    thread = await make_thread(
        engine, workspace_id=ws.wid, account_id=ws.account_id, texts=("Do you ship to Dubai?",)
    )
    now = datetime.now(UTC)
    gap = await make_gap(
        engine,
        workspace_id=ws.wid,
        topic="shipping to uae",
        first_seen_at=now,
        last_seen_at=now,
        example_message_ids=thread.message_ids,
    )

    before = await ws.ok("GET", "/overview")
    latest = before["latest_gap"]
    assert (latest["id"], latest["question"], latest["conversation_id"]) == (
        str(gap),
        "Do you ship to Dubai?",
        str(thread.conversation_id),
    )

    # Home's Train AI sends what the Knowledge page's Add answer sends.
    await ws.ok(
        "POST",
        "/knowledge-sources",
        201,
        json={
            "type": "faq",
            "question": latest["question"],
            "body": "Yes, to all of the UAE in 7-10 days.",
            "gap_id": latest["id"],
        },
    )

    after = await ws.ok("GET", "/overview")
    assert (after["knowledge_gaps_open"], after["latest_gap"]) == (0, None)


# ---------------------------------------------------------------- engagement rate


async def snapshot(
    team: Team, post: uuid.UUID, window: str, captured_at: datetime, **metrics: int
) -> None:
    await team.execute(
        'INSERT INTO post_metric_snapshots (workspace_id, media_item_id, "window",'
        " captured_at, metrics) VALUES (:w, :m, :win, :at, CAST(:x AS jsonb))",
        w=team.wid,
        m=post,
        win=window,
        at=captured_at,
        x=json.dumps(metrics),
    )


async def test_engagement_comes_only_from_snapshots_in_the_range(team: Team) -> None:
    seed = Seed(team, await seed_main_account(team))
    cakes = await seed.post("Autumn cakes", ist(20, 12))
    for day in (25, 26, 27):
        await seed.comment(cakes, ist(day, 10))
    bread = await seed.post("Sourdough", ist(15, 9))
    for day in (25, 26):
        await seed.comment(bread, ist(day, 10))
    tart = await seed.post("Tarts", ist(24, 9))
    await seed.comment(tart, ist(28, 10))

    full = {"likes": 50, "comments": 3, "shares": 2, "saves": 5}
    # Cakes: the 72 h snapshot (6%), then the 7-day one (5%): the latest in the range counts.
    await snapshot(team, cakes, "72h", ist(23, 12), reach=1000, **full)  # before the range
    await snapshot(team, cakes, "7d", ist(27, 12), reach=1200, **full)  # 60/1200 = 5%
    # Bread: its only snapshot in the range has no reach (1 h: live counts only).
    await snapshot(team, bread, "30d", ist(15, 12), reach=100, **full)  # before the range
    await snapshot(team, bread, "1h", ist(25, 10), likes=5, comments=1)
    # Tarts: reach but a missing count gives nothing.
    await snapshot(team, tart, "24h", ist(25, 9), reach=500, likes=10, comments=1, shares=1)

    body = await overview(team)

    rates = {p["id"]: p["engagement_rate"] for p in body["top_posts"]}
    assert rates == {str(cakes): 5.0, str(bread): None, str(tart): None}
    assert body["top_posts_engagement"] == {"rate": 5.0, "posts": 1}

    # Tarts' 72 h snapshot has every count: 12 / 400 = 3%. The mean of 5% and 3%.
    await snapshot(
        team, tart, "72h", ist(27, 9), reach=400, likes=10, comments=1, shares=1, saves=0
    )
    body = await overview(team)
    assert [p["engagement_rate"] for p in body["top_posts"]] == [5.0, None, 3.0]
    assert body["top_posts_engagement"] == {"rate": 4.0, "posts": 2}
