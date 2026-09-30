"""The weekly digest (T8.7; FR-NOT-04).

Done when: sent once per workspace per week at 09:00 local time; numbers match the overview
endpoint. The numbers are checked against a week seeded by hand (every definition in
services/overview_stats.py has a case), and against ``overview_stats.compute`` for the same days,
the function T9.1's overview must use. Plus: time zones on a half hour and with daylight saving,
a re-run sending nothing, quiet weeks, opted-out members, and the unsubscribe headers."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks.digests import send_due_digests
from socialhood.notify import digest
from socialhood.notify.email_fake import FakeEmail
from socialhood.notify.templates.digest import DASH
from socialhood.notify.unsubscribe import read_token
from socialhood.services import overview_stats
from socialhood.settings import Settings
from tests.support.ai import make_analysis
from tests.support.api import TOKEN_KEY
from tests.support.inbox import make_account
from tests.support.notify_team import Team, make_team

KOLKATA = ZoneInfo("Asia/Kolkata")
WEEK = date(2026, 9, 28)  # the Monday the digest is sent; it covers 21-27 September
NINE_IST = datetime(2026, 9, 28, 3, 30, tzinfo=UTC)  # Monday 09:00 in Asia/Kolkata


def ist(day: int, hour: int, minute: int = 0, second: int = 0, month: int = 9) -> datetime:
    return datetime(2026, month, day, hour, minute, second, tzinfo=KOLKATA)


class Seed:
    """Rows written straight to the tables, as ingest and sending leave them."""

    def __init__(self, team: Team, account_id: uuid.UUID) -> None:
        self.team = team
        self.account_id = account_id

    async def conversation(
        self, name: str, *, needs_human: bool = False, status: str = "open"
    ) -> uuid.UUID:
        contact = await self.team.insert(
            "INSERT INTO contacts (workspace_id, social_account_id, platform_user_id,"
            " display_name) VALUES (:w, :a, :p, :n) RETURNING id",
            w=self.team.wid,
            a=self.account_id,
            p=f"igsid_{uuid.uuid4().hex[:8]}",
            n=name,
        )
        return await self.team.insert(
            "INSERT INTO conversations (workspace_id, social_account_id, contact_id, platform,"
            " needs_human, status) VALUES (:w, :a, :c, 'instagram', :h, :s) RETURNING id",
            w=self.team.wid,
            a=self.account_id,
            c=contact,
            h=needs_human,
            s=status,
        )

    async def message(
        self,
        conv: uuid.UUID,
        at: datetime,
        *,
        source: str = "customer",
        status: str | None = "sent",
        sent_at: datetime | None = None,
    ) -> uuid.UUID:
        inbound = source == "customer"
        return await self.team.insert(
            "INSERT INTO messages (workspace_id, conversation_id, social_account_id, direction,"
            " source, kind, text, occurred_at, status, sent_at)"
            " VALUES (:w, :c, :a, :d, :s, 'text', 'hi', :at, :st, :sent) RETURNING id",
            w=self.team.wid,
            c=conv,
            a=self.account_id,
            d="inbound" if inbound else "outbound",
            s=source,
            at=at,
            st="received" if inbound else status,
            sent=sent_at,
        )

    async def analysed(
        self, conv: uuid.UUID, message: uuid.UUID, intent: str, **values: Any
    ) -> None:
        await make_analysis(
            self.team.engine,
            workspace_id=self.team.wid,
            conversation_id=conv,
            message_id=message,
            intent=intent,
            **values,
        )

    async def post(self, caption: str) -> uuid.UUID:
        return await self.team.insert(
            "INSERT INTO media_items (workspace_id, social_account_id, platform_media_id,"
            " media_type, caption, posted_at) VALUES (:w, :a, :p, 'image', :c, :at) RETURNING id",
            w=self.team.wid,
            a=self.account_id,
            p=f"1790{uuid.uuid4().int % 10**12:012d}",
            c=caption,
            at=ist(20, 12),
        )

    async def comment(self, post: uuid.UUID, at: datetime, *, deleted: bool = False) -> None:
        await self.team.execute(
            "INSERT INTO comments (workspace_id, social_account_id, media_item_id,"
            " platform_comment_id, text, commented_at, deleted_at)"
            " VALUES (:w, :a, :m, :p, 'so pretty', :at, :del)",
            w=self.team.wid,
            a=self.account_id,
            m=post,
            p=f"1780{uuid.uuid4().int % 10**12:012d}",
            at=at,
            **{"del": at if deleted else None},
        )

    async def gap(self, topic: str, asked: int, *, status: str = "open", days_ago: int = 3) -> None:
        seen = NINE_IST - timedelta(days=days_ago)
        await self.team.execute(
            "INSERT INTO knowledge_gaps (workspace_id, topic, topic_normalized, status,"
            " occurrences, first_seen_at, last_seen_at) VALUES (:w, :t, :n, :s, :o, :at, :at)",
            w=self.team.wid,
            t=topic,
            n=topic.lower(),
            s=status,
            o=asked,
            at=seen,
        )


async def seed_week(team: Team) -> Seed:
    """The week of 21-27 September in Asia/Kolkata, one case per rule."""
    seed = Seed(team, await make_account(team.engine, team.wid))
    # Priya: two messages then Auto answers (a turn of 10 min 30 s, from the first message);
    # later a new turn answered by a person in 20 min. Replied, not by AI alone.
    priya = await seed.conversation("Priya")
    hello = await seed.message(priya, ist(22, 10, 0))
    price = await seed.message(priya, ist(22, 10, 2))
    await seed.message(priya, ist(22, 10, 10), source="ai_auto", sent_at=ist(22, 10, 10, 30))
    thanks = await seed.message(priya, ist(23, 12, 0))
    await seed.message(priya, ist(23, 12, 20), source="human", sent_at=ist(23, 12, 20))
    # Arjun: an automation answers in 5 s. Handled by AI.
    arjun = await seed.conversation("Arjun")
    arjun_asks = await seed.message(arjun, ist(24, 9, 0))
    await seed.message(arjun, ist(24, 9, 0, 5), source="automation", sent_at=ist(24, 9, 0, 5))
    # Meera: the only reply failed. Not replied; her turn is unanswered; she still needs you.
    meera = await seed.conversation("Meera", needs_human=True)
    meera_asks = await seed.message(meera, ist(25, 18, 0))
    await seed.message(meera, ist(25, 18, 30), source="human", status="failed")
    # Kabir: his turn began before the week (Sunday 20th), answered from the Instagram app in
    # the week. Replied (not by AI); no turn started in the week.
    kabir = await seed.conversation("Kabir")
    await seed.message(kabir, ist(20, 23, 0))
    kabir_again = await seed.message(kabir, ist(21, 0, 30))
    await seed.message(kabir, ist(21, 1, 0), source="native_app", status=None)
    # Zoya: wrote late on Sunday, answered after the week ended. Not replied in the week. Her
    # conversation is archived, so it doesn't count as waiting.
    zoya = await seed.conversation("Zoya", needs_human=True, status="archived")
    zoya_asks = await seed.message(zoya, ist(27, 23, 50))
    await seed.message(zoya, ist(28, 0, 10), source="human", sent_at=ist(28, 0, 10))
    # Farah: only on Monday, after the week.
    farah = await seed.conversation("Farah")
    farah_asks = await seed.message(farah, ist(28, 8, 0))

    for conv, message, intent, extra in (
        (priya, hello, "greeting", {}),
        (priya, price, "pricing", {}),
        (priya, thanks, "pricing", {"corrected_intent": "feedback"}),  # the correction wins
        (arjun, arjun_asks, "pricing", {}),
        (meera, meera_asks, "shipping", {}),
        (kabir, kabir_again, "other", {}),  # left out
        (zoya, zoya_asks, "spam", {}),  # left out
        (farah, farah_asks, "pricing", {}),  # after the week
    ):
        await seed.analysed(conv, message, intent, **extra)

    cakes = await seed.post("New autumn cakes are here")
    for at in (ist(21, 9), ist(24, 20), ist(27, 23, 59)):
        await seed.comment(cakes, at)
    await seed.comment(cakes, ist(25, 10), deleted=True)
    await seed.comment(cakes, ist(28, 9))  # after the week
    bread = await seed.post("Sourdough Saturdays")
    await seed.comment(bread, ist(26, 11))

    await seed.gap("Do you ship to Dubai?", 5)
    await seed.gap("Eggless options", 2)
    await seed.gap("Gift wrapping", 9, status="dismissed")
    await seed.gap("Store hours", 7, status="answered")
    await seed.gap("Bulk orders", 4, days_ago=40)  # asked too long ago
    return seed


def expected_stats(cakes_id: str, bread_id: str) -> dict[str, Any]:
    return {
        "since": "2026-09-21",
        "until": "2026-09-27",
        "messages_received": 7,  # Priya 3, Arjun, Meera, Kabir (the 21st), Zoya
        "conversations": 5,
        "conversations_replied": 3,  # Priya, Arjun, Kabir
        "reply_rate": 60.0,
        "handled_by_ai": 1,  # Arjun
        "handled_by_ai_rate": 33.3,
        "first_responses": 3,  # 630 s, 1,200 s and 5 s
        "median_first_response_s": 630,
        "top_intents": [
            {"intent": "pricing", "count": 2},
            {"intent": "feedback", "count": 1},
            {"intent": "greeting", "count": 1},
        ],
        "comments_received": 4,
        "top_posts": [
            {
                "post_id": cakes_id,
                "caption": "New autumn cakes are here",
                "permalink": None,
                "media_type": "image",
                "posted_at": ist(20, 12).astimezone(UTC).isoformat(),
                "comments": 3,
            },
            {
                "post_id": bread_id,
                "caption": "Sourdough Saturdays",
                "permalink": None,
                "media_type": "image",
                "posted_at": ist(20, 12).astimezone(UTC).isoformat(),
                "comments": 1,
            },
        ],
        "needs_you": 1,  # Meera (Zoya's conversation is archived)
        "open_questions": 2,
        "top_questions": [
            {"topic": "Do you ship to Dubai?", "asked": 5},
            {"topic": "Eggless options", "asked": 2},
        ],
    }


@pytest.fixture
async def team(engine: AsyncEngine, clean_db: None) -> Team:
    team = await make_team(engine, timezone="Asia/Kolkata")
    # The admin turned the digest off; the owner and the agent get it.
    await team.set_prefs(
        team.admin,
        {
            "email_digest": False,
            "push": {"needs_you": True, "new_lead": True, "window_closing": True, "account": True},
        },
    )
    return team


@pytest.fixture
def settings(api_settings: Settings) -> Settings:
    return api_settings.model_copy(update={"api_base_url": "http://api.test"})


async def digests(team: Team) -> list[dict[str, Any]]:
    return await team.rows(
        "SELECT * FROM weekly_digests WHERE workspace_id = :w ORDER BY week_start", w=team.wid
    )


async def post_ids(team: Team) -> tuple[str, str]:
    rows = await team.rows(
        "SELECT id, caption FROM media_items WHERE workspace_id = :w ORDER BY caption", w=team.wid
    )
    by_caption = {row["caption"]: str(row["id"]) for row in rows}
    return by_caption["New autumn cakes are here"], by_caption["Sourdough Saturdays"]


# ---------------------------------------------------------------- the numbers


async def test_monday_nine_sends_the_weeks_numbers_to_members_who_want_them(team: Team) -> None:
    await seed_week(team)

    assert await send_due_digests(team.maker, now=NINE_IST - timedelta(minutes=15)) == {}
    assert await digests(team) == []

    assert await send_due_digests(team.maker, now=NINE_IST) == {"sent": 1}

    expected = expected_stats(*await post_ids(team))
    [row] = await digests(team)
    assert (row["week_start"], row["status"], row["recipients"]) == (WEEK, "sent", 2)
    assert row["sent_at"] == NINE_IST
    assert row["stats"] == expected
    deliveries = await team.deliveries()
    assert {d["user_id"] for d in deliveries} == {team.owner, team.agent}
    for delivery in deliveries:
        assert delivery["template"] == "weekly_digest"
        assert delivery["dedupe_key"] == f"digest:2026-09-28:{delivery['user_id']}"
        assert delivery["notification_id"] is None
        assert delivery["data"] == {
            "workspace_name": "Maple Bakery",
            "workspace_slug": team.slug,
            "stats": expected,
        }


async def test_the_digest_numbers_are_the_overviews(team: Team) -> None:
    """T8.7: the numbers match the overview endpoint, whose metrics T9.1 builds on
    overview_stats; for the same days the overview computes exactly what was sent."""
    await seed_week(team)
    await send_due_digests(team.maker, now=NINE_IST)
    [row] = await digests(team)

    with workspace_scope(team.wid):
        async with team.maker() as session:
            last_week = overview_stats.days_up_to_today(
                "Asia/Kolkata", NINE_IST - timedelta(days=1), 7
            )
            overview = await overview_stats.compute(session, span=last_week, now=NINE_IST)

    assert overview.to_json() == row["stats"]


# ---------------------------------------------------------------- once a week


async def test_a_rerun_sends_nothing(team: Team) -> None:
    await seed_week(team)
    assert await send_due_digests(team.maker, now=NINE_IST) == {"sent": 1}

    for later in (timedelta(minutes=15), timedelta(hours=5), timedelta(hours=14, minutes=15)):
        assert await send_due_digests(team.maker, now=NINE_IST + later) == {}
    # Even past the pre-check (a concurrent run), the week's row refuses a second digest.
    with workspace_scope(team.wid):
        async with team.maker() as session:
            again = await digest.send_digest(session, week_start=WEEK, now=NINE_IST)
            await session.commit()
    assert again == "already"
    assert len(await digests(team)) == 1
    assert len(await team.deliveries()) == 2


async def test_a_missed_nine_oclock_catches_up_later_that_monday(team: Team) -> None:
    await seed_week(team)
    assert await send_due_digests(team.maker, now=NINE_IST + timedelta(hours=6)) == {"sent": 1}
    [row] = await digests(team)
    assert row["week_start"] == WEEK


async def test_after_monday_the_weeks_digest_is_not_sent(team: Team) -> None:
    await seed_week(team)
    assert await send_due_digests(team.maker, now=NINE_IST + timedelta(hours=15)) == {}
    assert await digests(team) == []


@pytest.mark.parametrize(
    ("monday", "sends_at"),
    [
        (
            date(2026, 10, 19),  # London still on summer time (BST, UTC+1)
            {
                "Asia/Kolkata": datetime(2026, 10, 19, 3, 30, tzinfo=UTC),
                "UTC": datetime(2026, 10, 19, 9, 0, tzinfo=UTC),
                "Europe/London": datetime(2026, 10, 19, 8, 0, tzinfo=UTC),
                "America/New_York": datetime(2026, 10, 19, 13, 0, tzinfo=UTC),
            },
        ),
        (
            date(2026, 10, 26),  # London back on GMT since Sunday; New York not yet
            {
                "Asia/Kolkata": datetime(2026, 10, 26, 3, 30, tzinfo=UTC),
                "UTC": datetime(2026, 10, 26, 9, 0, tzinfo=UTC),
                "Europe/London": datetime(2026, 10, 26, 9, 0, tzinfo=UTC),
                "America/New_York": datetime(2026, 10, 26, 13, 0, tzinfo=UTC),
            },
        ),
    ],
)
async def test_every_workspace_gets_one_digest_at_nine_its_time(
    engine: AsyncEngine, clean_db: None, monday: date, sends_at: dict[str, datetime]
) -> None:
    teams: dict[str, Team] = {}
    for zone in sends_at:
        team = await make_team(engine, timezone=zone)
        seed = Seed(team, await make_account(engine, team.wid))
        conv = await seed.conversation("Priya")
        midnight = datetime.combine(monday, datetime.min.time(), tzinfo=UTC)
        await seed.message(conv, midnight - timedelta(days=3) + timedelta(hours=12))  # Friday
        teams[zone] = team

    # Every quarter-hour tick from Sunday 18:00 to Monday 18:00 UTC (Monday 09:00 anywhere here).
    midnight = datetime.combine(monday, datetime.min.time(), tzinfo=UTC)
    tick, end = midnight - timedelta(hours=6), midnight + timedelta(hours=18)
    while tick < end:
        await send_due_digests(teams["UTC"].maker, now=tick)
        tick += timedelta(minutes=15)

    for zone, team in teams.items():
        [row] = await digests(team)
        assert (row["week_start"], row["status"]) == (monday, "sent"), zone
        assert row["sent_at"] == sends_at[zone], zone
        assert len(await team.deliveries()) == 3  # owner, admin and agent all want it


# ---------------------------------------------------------------- who gets it


async def test_a_quiet_week_is_skipped(team: Team) -> None:
    await make_account(team.engine, team.wid)

    assert await send_due_digests(team.maker, now=NINE_IST) == {"skipped": 1}

    [row] = await digests(team)
    assert (row["status"], row["recipients"], row["error"]) == (
        "skipped",
        0,
        "Nothing happened this week",
    )
    assert row["stats"]["messages_received"] == 0
    assert await team.deliveries() == []


async def test_nobody_opted_in_is_skipped(team: Team) -> None:
    await seed_week(team)
    for user in (team.owner, team.agent):
        await team.set_prefs(
            user,
            {
                "email_digest": False,
                "push": {
                    "needs_you": True,
                    "new_lead": True,
                    "window_closing": True,
                    "account": True,
                },
            },
        )

    assert await send_due_digests(team.maker, now=NINE_IST) == {"skipped": 1}
    assert await team.deliveries() == []


# ---------------------------------------------------------------- the email


async def test_the_email_carries_one_click_unsubscribe(
    team: Team, fake_email: FakeEmail, settings: Settings
) -> None:
    await seed_week(team)
    await send_due_digests(team.maker, now=NINE_IST)
    [delivery] = [d for d in await team.deliveries() if d["user_id"] == team.owner]

    assert await team.send_email(delivery["id"], fake_email, settings) == "sent"

    [email] = fake_email.outbox
    assert email.to == team.emails[team.owner]
    assert email.subject == f"Your week at Maple Bakery: 21{DASH}27 Sep"
    assert email.idempotency_key == f"{team.wid}:digest:2026-09-28:{team.owner}"
    assert email.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    header = email.headers["List-Unsubscribe"]
    assert header.startswith("<http://api.test/v1/digest/unsubscribe?token=")
    token = header.removesuffix(">").split("token=", 1)[1]
    claim = read_token(token, [TOKEN_KEY])
    assert claim is not None
    assert (claim.workspace_id, claim.user_id) == (team.wid, team.owner)
    assert f'href="http://web.test/unsubscribe?token={token}"' in email.html
    assert f"Unsubscribe: http://web.test/unsubscribe?token={token}" in email.text
    assert "60%" in email.text  # the reply rate


async def test_a_member_who_turned_it_off_since_is_skipped(
    team: Team, fake_email: FakeEmail, settings: Settings
) -> None:
    await seed_week(team)
    await send_due_digests(team.maker, now=NINE_IST)
    [delivery] = [d for d in await team.deliveries() if d["user_id"] == team.agent]
    await team.set_prefs(
        team.agent,
        {
            "email_digest": False,
            "push": {"needs_you": True, "new_lead": True, "window_closing": True, "account": True},
        },
    )

    assert await team.send_email(delivery["id"], fake_email, settings) == "skipped"
    assert fake_email.outbox == []
