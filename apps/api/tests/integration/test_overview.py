"""T9.1: GET …/overview, Home's metrics (FR-HOME-01, UX-SCR-01).

Done when: values match hand-computed SQL on seed data. Every metric is checked against a query
written here, apart from the service (local days by ``AT TIME ZONE`` instead of computed bounds),
and against numbers worked out by hand for the seed. Edge cases: an empty workspace, the first
and last second of a local day (and a daylight-saving change), replies from the Instagram app,
failed and queued sends, a turn that began before the range, archived conversations, deleted
comments, corrections, and the weekly digest's week giving the digest's numbers.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
import time_machine
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.db.tenancy import workspace_scope
from socialhood.models.identity import Workspace
from socialhood.schemas.workspaces import Overview, OverviewRange
from socialhood.services import overview as overview_service
from socialhood.services.conversations import inbox_counts
from tests.integration.test_weekly_digest import expected_stats, post_ids, seed_week
from tests.support.ai import make_analysis
from tests.support.analytics import make_comment_analysis
from tests.support.api import Clerk, sign_in
from tests.support.inbox import make_account
from tests.support.notify_team import Team, make_team

KOLKATA = "Asia/Kolkata"
NEW_YORK = "America/New_York"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=ZoneInfo(KOLKATA))  # Wednesday noon in India


def ist(day: int, hour: int, minute: int = 0, second: int = 0, month: int = 9) -> datetime:
    return datetime(2026, month, day, hour, minute, second, tzinfo=ZoneInfo(KOLKATA))


# ---------------------------------------------------------------- seeding


class Seed:
    """Rows written straight to the tables, as ingest, sending and analysis leave them."""

    def __init__(self, team: Team, account_id: uuid.UUID) -> None:
        self.team = team
        self.account_id = account_id

    async def conversation(
        self,
        name: str,
        *,
        needs_human: bool = False,
        awaiting_reply: bool = False,
        status: str = "open",
        last_message_at: datetime | None = None,
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
            " needs_human, awaiting_reply, status, last_message_at)"
            " VALUES (:w, :a, :c, 'instagram', :h, :r, :s, :at) RETURNING id",
            w=self.team.wid,
            a=self.account_id,
            c=contact,
            h=needs_human,
            r=awaiting_reply,
            s=status,
            at=last_message_at or NOW - timedelta(days=1),
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
        self, conv: uuid.UUID, message: uuid.UUID, intent: str, sentiment: str, **values: Any
    ) -> None:
        await make_analysis(
            self.team.engine,
            workspace_id=self.team.wid,
            conversation_id=conv,
            message_id=message,
            intent=intent,
            sentiment=sentiment,
            **values,
        )

    async def post(
        self, caption: str, posted_at: datetime, stats: dict[str, int] | None = None
    ) -> uuid.UUID:
        return await self.team.insert(
            "INSERT INTO media_items (workspace_id, social_account_id, platform_media_id,"
            " media_type, caption, thumbnail_url, posted_at, comment_stats)"
            " VALUES (:w, :a, :p, 'image', :c, :t, :at, CAST(:s AS jsonb)) RETURNING id",
            w=self.team.wid,
            a=self.account_id,
            p=f"1790{uuid.uuid4().int % 10**12:012d}",
            c=caption,
            t=f"https://cdn.example/{caption.split()[0].lower()}.jpg",
            at=posted_at,
            s=json.dumps(stats or {}),
        )

    async def comment(
        self,
        post: uuid.UUID,
        at: datetime,
        *,
        deleted: bool = False,
        sentiment: str | None = None,
        spam: bool = False,
    ) -> uuid.UUID:
        comment = await self.team.insert(
            "INSERT INTO comments (workspace_id, social_account_id, media_item_id,"
            " platform_comment_id, text, commented_at, deleted_at)"
            " VALUES (:w, :a, :m, :p, 'so pretty', :at, :del) RETURNING id",
            w=self.team.wid,
            a=self.account_id,
            m=post,
            p=f"1780{uuid.uuid4().int % 10**12:012d}",
            at=at,
            **{"del": at if deleted else None},
        )
        if sentiment is not None:
            await make_comment_analysis(
                self.team.engine,
                workspace_id=self.team.wid,
                comment_id=comment,
                sentiment=sentiment,
                is_spam=spam,
            )
        return comment

    async def gap(self, topic: str, asked: int, *, status: str = "open", days_ago: int = 3) -> None:
        seen = NOW - timedelta(days=days_ago)
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

    async def account(self, username: str, status: str, connected_days_ago: int) -> uuid.UUID:
        account = await make_account(self.team.engine, self.team.wid, username=username)
        await self.team.execute(
            "UPDATE social_accounts SET status = :s, connected_at = :at WHERE id = :id",
            s=status,
            at=NOW - timedelta(days=connected_days_ago),
            id=account,
        )
        return account


async def seed_month(team: Team) -> dict[str, uuid.UUID]:
    """September 2026 in Asia/Kolkata, seen on Wednesday the 30th at noon: the 7 days are the
    24th to the 30th, the 7 before them the 17th to the 23rd."""
    seed = Seed(team, await seed_main_account(team))
    ids: dict[str, uuid.UUID] = {}
    # Priya: two messages then Auto answers 10 min 30 s after the first. Handled by AI.
    priya = await seed.conversation("Priya")
    p1 = await seed.message(priya, ist(29, 10, 0))
    p2 = await seed.message(priya, ist(29, 10, 2))
    await seed.message(priya, ist(29, 10, 10), source="ai_auto", sent_at=ist(29, 10, 10, 30))
    await seed.analysed(priya, p1, "pricing", "positive")
    await seed.analysed(priya, p2, "pricing", "neutral", corrected_sentiment="positive")
    # Arjun, today: an automation answers in 5 s. Handled by AI.
    arjun = await seed.conversation("Arjun")
    a1 = await seed.message(arjun, ist(30, 9, 0))
    await seed.message(arjun, ist(30, 9, 0, 5), source="automation", sent_at=ist(30, 9, 0, 5))
    await seed.analysed(arjun, a1, "shipping", "negative")
    # Meera: the only reply failed. Not replied, turn unanswered; needs you and a reply.
    meera = await seed.conversation("Meera", needs_human=True, awaiting_reply=True)
    m1 = await seed.message(meera, ist(28, 18, 0))
    await seed.message(meera, ist(28, 18, 30), source="human", status="failed")
    await seed.analysed(meera, m1, "complaint", "negative")
    # Kabir: answered from the Instagram app 30 min later (no status, no sent_at). Replied.
    kabir = await seed.conversation("Kabir")
    k1 = await seed.message(kabir, ist(26, 11, 0))
    await seed.message(kabir, ist(26, 11, 30), source="native_app", status=None)
    await seed.analysed(kabir, k1, "other", "neutral")  # left out of intents, not of sentiment
    # Zoya: wrote at the last second of the 23rd and the first second of the 30th; a person
    # answers at 00:20 on the 30th. In the 7 days she is replied, but her turn began on the 23rd
    # (before the range); in the 7 days before, she is not replied (the answer came after).
    zoya = await seed.conversation("Zoya")
    await seed.message(zoya, ist(23, 23, 59, 59))
    z2 = await seed.message(zoya, ist(30, 0, 0, 0))
    await seed.message(zoya, ist(30, 0, 20), source="human", sent_at=ist(30, 0, 20))
    await seed.analysed(zoya, z2, "spam", "neutral")  # spam: apart in sentiment, not an intent
    # Farah: only in the 7 days before; answered in an hour.
    farah = await seed.conversation("Farah")
    f1 = await seed.message(farah, ist(20, 10, 0))
    await seed.message(farah, ist(20, 11, 0), source="human", sent_at=ist(20, 11, 0))
    await seed.analysed(farah, f1, "pricing", "positive")
    # Dev: the reply is still queued. Not replied; waiting for a reply; not analysed.
    dev = await seed.conversation("Dev", awaiting_reply=True)
    await seed.message(dev, ist(25, 14, 0))
    await seed.message(dev, ist(25, 14, 5), source="human", status="queued")
    # Rhea: archived. Her message counts; her conversation waits for nobody.
    rhea = await seed.conversation("Rhea", needs_human=True, awaiting_reply=True, status="archived")
    r1 = await seed.message(rhea, ist(27, 12, 0))
    await seed.analysed(rhea, r1, "pricing", "positive")
    # Ishaan: at the first second of the 24th; answered in 5 min. The correction wins.
    ishaan = await seed.conversation("Ishaan")
    i1 = await seed.message(ishaan, ist(24, 0, 0, 0))
    await seed.message(ishaan, ist(24, 0, 5), source="human", sent_at=ist(24, 0, 5))
    await seed.analysed(ishaan, i1, "greeting", "positive", corrected_intent="feedback")

    cakes = await seed.post(
        "New autumn cakes are here",
        ist(22, 12),
        {"total": 5, "analysed": 4, "positive": 2, "neutral": 0, "negative": 1, "spam": 1},
    )
    await seed.comment(cakes, ist(24, 0, 0, 0), sentiment="positive")
    await seed.comment(cakes, ist(29, 20), sentiment="negative")
    await seed.comment(cakes, ist(30, 11), sentiment="neutral", spam=True)
    await seed.comment(cakes, ist(26, 10), deleted=True, sentiment="positive")  # left out
    await seed.comment(cakes, ist(23, 23, 59, 59), sentiment="positive")  # the 7 days before
    bread = await seed.post("Sourdough Saturdays", ist(25, 9))
    await seed.comment(bread, ist(27, 11))  # not analysed yet
    old = await seed.post("Summer menu", ist(10, 9))
    await seed.comment(old, ist(18, 9), sentiment="negative")
    await seed.comment(old, ist(19, 9), sentiment="positive")
    ids |= {"cakes": cakes, "bread": bread, "old": old}

    await seed.gap("Do you ship to Dubai?", 5)
    await seed.gap("Eggless options", 2)
    await seed.gap("Gift wrapping", 9, status="dismissed")
    await seed.gap("Bulk orders", 4, days_ago=40)  # asked too long ago

    ids["outlet"] = await seed.account("maple.outlet", "needs_reconnect", 20)
    ids["broken"] = await seed.account("maple.broken", "error", 10)
    await seed.account("maple.gone", "disconnected", 5)  # not a problem to fix
    return ids


async def seed_main_account(team: Team) -> uuid.UUID:
    account = await make_account(team.engine, team.wid)
    await team.execute(
        "UPDATE social_accounts SET connected_at = :at WHERE id = :id",
        at=NOW - timedelta(days=60),
        id=account,
    )
    return account


# ---------------------------------------------------------------- the hand-written SQL


class Hand:
    """Each metric as a query of its own over the raw tables. Local days come from
    ``AT TIME ZONE`` (the service computes UTC bounds in Python)."""

    def __init__(self, team: Team, timezone: str, since: date, until: date) -> None:
        self.team = team
        self.params: dict[str, Any] = {"w": team.wid, "tz": timezone, "s": since, "u": until}

    async def one(self, sql: str, **params: Any) -> dict[str, Any]:
        [row] = await self.team.rows(sql, **{**self.params, **params})
        return row

    async def messages_received(self) -> int:
        row = await self.one(
            "SELECT count(*) AS n FROM messages WHERE workspace_id = :w"
            " AND direction = 'inbound' AND source = 'customer'"
            " AND (occurred_at AT TIME ZONE :tz)::date BETWEEN :s AND :u"
        )
        return int(row["n"])

    async def replies(self) -> tuple[int, int, int]:
        """Conversations with a customer message, those replied, those replied only by AI."""
        row = await self.one(
            """
            WITH firsts AS (
                SELECT conversation_id, min(occurred_at) AS first_at FROM messages
                WHERE workspace_id = :w AND direction = 'inbound' AND source = 'customer'
                  AND (occurred_at AT TIME ZONE :tz)::date BETWEEN :s AND :u
                GROUP BY conversation_id
            ), answered AS (
                SELECT f.conversation_id,
                       bool_and(r.source IN ('ai_auto', 'automation')) AS by_ai
                FROM firsts f JOIN messages r ON r.conversation_id = f.conversation_id
                WHERE r.direction = 'outbound'
                  AND r.source IN ('human', 'ai_auto', 'automation', 'native_app')
                  AND (r.status IS NULL OR r.status IN ('sent', 'delivered', 'read'))
                  AND coalesce(r.sent_at, r.occurred_at) >= f.first_at
                  AND (coalesce(r.sent_at, r.occurred_at) AT TIME ZONE :tz)::date <= :u
                GROUP BY f.conversation_id
            )
            SELECT (SELECT count(*) FROM firsts) AS conversations,
                   (SELECT count(*) FROM answered) AS replied,
                   (SELECT count(*) FROM answered WHERE by_ai) AS by_ai
            """
        )
        return int(row["conversations"]), int(row["replied"]), int(row["by_ai"])

    async def first_responses(self) -> tuple[int, int | None]:
        """Customer turns begun in the range and answered in it, and their median wait (s)."""
        row = await self.one(
            """
            WITH events AS (
                SELECT conversation_id, 'c' AS who, occurred_at AS at FROM messages
                WHERE workspace_id = :w AND direction = 'inbound' AND source = 'customer'
                UNION ALL
                SELECT conversation_id, 'b', coalesce(sent_at, occurred_at) FROM messages
                WHERE workspace_id = :w AND direction = 'outbound'
                  AND source IN ('human', 'ai_auto', 'automation', 'native_app')
                  AND (status IS NULL OR status IN ('sent', 'delivered', 'read'))
            ), turns AS (
                SELECT conversation_id, at FROM (
                    SELECT conversation_id, who, at,
                           lag(who) OVER (PARTITION BY conversation_id ORDER BY at) AS prev
                    FROM events
                ) e
                WHERE who = 'c' AND prev IS DISTINCT FROM 'c'
                  AND (at AT TIME ZONE :tz)::date BETWEEN :s AND :u
            ), waits AS (
                SELECT extract(epoch FROM answer.at - t.at) AS wait
                FROM turns t CROSS JOIN LATERAL (
                    SELECT min(e.at) AS at FROM events e
                    WHERE e.conversation_id = t.conversation_id AND e.who = 'b' AND e.at > t.at
                      AND (e.at AT TIME ZONE :tz)::date <= :u
                ) answer
                WHERE answer.at IS NOT NULL
            )
            SELECT count(*) AS n, percentile_cont(0.5) WITHIN GROUP (ORDER BY wait) AS median
            FROM waits
            """
        )
        median = row["median"]
        return int(row["n"]), round(float(median)) if median is not None else None

    async def top_intents(self) -> list[dict[str, Any]]:
        return await self.team.rows(
            """
            SELECT coalesce(a.corrected_intent, a.intent) AS intent, count(*) AS count
            FROM message_analyses a JOIN messages m ON m.id = a.message_id
            WHERE m.workspace_id = :w AND (m.occurred_at AT TIME ZONE :tz)::date BETWEEN :s AND :u
              AND coalesce(a.corrected_intent, a.intent) NOT IN ('other', 'spam')
            GROUP BY 1 ORDER BY count DESC, intent LIMIT 3
            """,
            **self.params,
        )

    async def message_sentiment(self) -> dict[str, int]:
        return await self.one(
            """
            SELECT count(*) AS total, count(a.id) AS analysed,
              count(*) FILTER (WHERE coalesce(a.corrected_intent, a.intent) <> 'spam'
                AND coalesce(a.corrected_sentiment, a.sentiment) = 'positive') AS positive,
              count(*) FILTER (WHERE coalesce(a.corrected_intent, a.intent) <> 'spam'
                AND coalesce(a.corrected_sentiment, a.sentiment) = 'neutral') AS neutral,
              count(*) FILTER (WHERE coalesce(a.corrected_intent, a.intent) <> 'spam'
                AND coalesce(a.corrected_sentiment, a.sentiment) = 'negative') AS negative,
              count(*) FILTER (WHERE coalesce(a.corrected_intent, a.intent) = 'spam') AS spam
            FROM messages m LEFT JOIN message_analyses a ON a.message_id = m.id
            WHERE m.workspace_id = :w AND m.direction = 'inbound' AND m.source = 'customer'
              AND (m.occurred_at AT TIME ZONE :tz)::date BETWEEN :s AND :u
            """
        )

    async def comments_by_post(self) -> list[dict[str, Any]]:
        return await self.team.rows(
            """
            SELECT c.media_item_id AS id, count(*) AS comments
            FROM comments c JOIN media_items p ON p.id = c.media_item_id
            WHERE c.workspace_id = :w AND c.deleted_at IS NULL
              AND (c.commented_at AT TIME ZONE :tz)::date BETWEEN :s AND :u
            GROUP BY c.media_item_id, p.posted_at ORDER BY comments DESC, p.posted_at DESC
            """,
            **self.params,
        )

    async def comment_sentiment(self) -> dict[str, int]:
        return await self.one(
            """
            SELECT count(*) AS total, count(a.id) AS analysed,
              count(*) FILTER (WHERE NOT a.is_spam AND a.sentiment = 'positive') AS positive,
              count(*) FILTER (WHERE NOT a.is_spam AND a.sentiment = 'neutral') AS neutral,
              count(*) FILTER (WHERE NOT a.is_spam AND a.sentiment = 'negative') AS negative,
              count(*) FILTER (WHERE a.is_spam) AS spam
            FROM comments c LEFT JOIN comment_analyses a ON a.comment_id = c.id
            WHERE c.workspace_id = :w AND c.deleted_at IS NULL
              AND (c.commented_at AT TIME ZONE :tz)::date BETWEEN :s AND :u
            """
        )


async def hand_states(team: Team, now: datetime) -> dict[str, Any]:
    """What is true now: waiting conversations, open questions, accounts to fix."""
    w = {"w": team.wid}
    [waiting] = await team.rows(
        "SELECT count(*) FILTER (WHERE awaiting_reply AND last_message_at IS NOT NULL) AS reply,"
        " count(*) FILTER (WHERE needs_human) AS you"
        " FROM conversations WHERE workspace_id = :w AND status = 'open'",
        **w,
    )
    questions = await team.rows(
        "SELECT topic, occurrences AS asked FROM knowledge_gaps WHERE workspace_id = :w"
        " AND status = 'open' AND last_seen_at >= :since ORDER BY occurrences DESC",
        since=now - timedelta(days=30),
        **w,
    )
    accounts = await team.rows(
        "SELECT id, platform, username, status FROM social_accounts WHERE workspace_id = :w"
        " AND status IN ('needs_reconnect', 'error') ORDER BY connected_at, id",
        **w,
    )
    return {
        "needs_reply": int(waiting["reply"]),
        "needs_you": int(waiting["you"]),
        "knowledge_gaps_open": len(questions),
        "top_questions": questions[:3],
        "accounts_needing_attention": [{**a, "id": str(a["id"])} for a in accounts],
    }


def split(row: dict[str, int]) -> dict[str, Any]:
    """A hand-counted sentiment row with its shares of positive + neutral + negative."""
    clean = row["positive"] + row["neutral"] + row["negative"]

    def share(n: int) -> float | None:
        return round(n / clean * 100, 1) if clean else None

    return {
        **{k: int(v) for k, v in row.items()},
        "positive_pct": share(row["positive"]),
        "neutral_pct": share(row["neutral"]),
        "negative_pct": share(row["negative"]),
    }


def rate(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None


async def hand_period(hand: Hand) -> dict[str, Any]:
    conversations, replied, by_ai = await hand.replies()
    answered, median = await hand.first_responses()
    by_post = await hand.comments_by_post()
    return {
        "since": hand.params["s"].isoformat(),
        "until": hand.params["u"].isoformat(),
        "messages_received": await hand.messages_received(),
        "conversations": conversations,
        "conversations_replied": replied,
        "reply_rate": rate(replied, conversations),
        "handled_by_ai": by_ai,
        "handled_by_ai_rate": rate(by_ai, replied),
        "first_responses": answered,
        "median_first_response_s": median,
        "comments_received": sum(int(row["comments"]) for row in by_post),
    }


def local_days(timezone: str, now: datetime, days: int) -> tuple[date, date, date, date]:
    """The range and the one before it, worked out apart from the service."""
    today = now.astimezone(ZoneInfo(timezone)).date()
    since = today - timedelta(days=days - 1)
    return since, today, since - timedelta(days=days), since - timedelta(days=1)


async def assert_matches_hand_sql(
    team: Team, body: dict[str, Any], *, timezone: str, now: datetime, days: int
) -> None:
    since, until, before_since, before_until = local_days(timezone, now, days)
    hand = Hand(team, timezone, since, until)
    before = Hand(team, timezone, before_since, before_until)
    today = Hand(team, timezone, until, until)

    assert body["current"] == await hand_period(hand)
    assert body["previous"] == await hand_period(before)
    assert body["messages_today"] == await today.messages_received()
    assert body["top_intents"] == [
        {"intent": row["intent"], "count": int(row["count"])} for row in await hand.top_intents()
    ]
    assert body["message_sentiment"] == split(await hand.message_sentiment())
    assert body["comment_sentiment"] == split(await hand.comment_sentiment())
    top = (await hand.comments_by_post())[:3]
    assert [(p["id"], p["comments"]) for p in body["top_posts"]] == [
        (str(row["id"]), int(row["comments"])) for row in top
    ]
    states = await hand_states(team, now)
    for key, value in states.items():
        assert body[key] == value, key


# ---------------------------------------------------------------- running the service


async def overview(team: Team, range_: OverviewRange, now: datetime) -> dict[str, Any]:
    with workspace_scope(team.wid):
        async with team.maker() as session:
            workspace = await session.get(Workspace, team.wid)
            assert workspace is not None
            result = await overview_service.overview(session, workspace, range_=range_, now=now)
    return result.model_dump(mode="json")


@pytest.fixture
async def team(engine: AsyncEngine, clean_db: None) -> Team:
    return await make_team(engine, timezone=KOLKATA)


# ---------------------------------------------------------------- the numbers


async def test_the_seven_days_match_the_hand_written_sql_and_the_hand_counts(team: Team) -> None:
    ids = await seed_month(team)

    body = await overview(team, "7d", NOW)

    await assert_matches_hand_sql(team, body, timezone=KOLKATA, now=NOW, days=7)
    # And the same numbers worked out by hand for the seed (see seed_month).
    assert (body["range"], body["timezone"]) == ("7d", KOLKATA)
    assert body["current"] == {
        "since": "2026-09-24",
        "until": "2026-09-30",
        "messages_received": 9,  # Priya 2, Arjun, Meera, Kabir, Zoya (the 30th), Dev, Rhea, Ishaan
        "conversations": 8,
        "conversations_replied": 5,  # Priya, Arjun, Kabir (the app), Zoya, Ishaan
        "reply_rate": 62.5,
        "handled_by_ai": 2,  # Priya (Auto), Arjun (an automation)
        "handled_by_ai_rate": 40.0,
        "first_responses": 4,  # 5 s, 300 s, 630 s, 1,800 s (Zoya's turn began on the 23rd)
        "median_first_response_s": 465,
        "comments_received": 4,  # the deleted one left out
    }
    assert body["previous"] == {
        "since": "2026-09-17",
        "until": "2026-09-23",
        "messages_received": 2,  # Zoya at 23:59:59 on the 23rd, Farah
        "conversations": 2,
        "conversations_replied": 1,  # Farah; Zoya's answer came after the 23rd
        "reply_rate": 50.0,
        "handled_by_ai": 0,
        "handled_by_ai_rate": 0.0,
        "first_responses": 1,
        "median_first_response_s": 3600,
        "comments_received": 3,
    }
    assert body["messages_today"] == 2  # Zoya at 00:00:00 and Arjun
    assert body["top_intents"] == [
        {"intent": "pricing", "count": 3},  # Priya twice, Rhea (archived still counts)
        {"intent": "complaint", "count": 1},
        {"intent": "feedback", "count": 1},  # Ishaan's corrected greeting
    ]
    assert body["message_sentiment"] == {
        "total": 9,
        "analysed": 8,  # Dev's message wasn't analysed
        "positive": 4,  # Priya twice (one corrected), Rhea, Ishaan
        "neutral": 1,  # Kabir
        "negative": 2,  # Arjun, Meera
        "spam": 1,  # Zoya
        "positive_pct": 57.1,
        "neutral_pct": 14.3,
        "negative_pct": 28.6,
    }
    assert body["comment_sentiment"] == {
        "total": 4,
        "analysed": 3,
        "positive": 1,
        "neutral": 0,
        "negative": 1,
        "spam": 1,
        "positive_pct": 50.0,
        "neutral_pct": 0.0,
        "negative_pct": 50.0,
    }
    cakes, bread = body["top_posts"]
    assert (cakes["id"], cakes["comments"], bread["id"], bread["comments"]) == (
        str(ids["cakes"]),
        3,
        str(ids["bread"]),
        1,
    )
    assert cakes["thumbnail_url"] == "https://cdn.example/new.jpg"
    assert cakes["stats"] == {  # the post's own split, as the Comments page shows it
        "total": 5,
        "analysed": 4,
        "positive": 2,
        "neutral": 0,
        "negative": 1,
        "spam": 1,
    }
    assert bread["stats"]["total"] == 0  # not analysed yet: {} reads as zeros
    assert (body["needs_reply"], body["needs_you"]) == (2, 1)  # Meera and Dev; Meera
    assert body["knowledge_gaps_open"] == 2
    assert body["top_questions"] == [
        {"topic": "Do you ship to Dubai?", "asked": 5},
        {"topic": "Eggless options", "asked": 2},
    ]
    assert [(a["username"], a["status"]) for a in body["accounts_needing_attention"]] == [
        ("maple.outlet", "needs_reconnect"),
        ("maple.broken", "error"),
    ]
    # The accounts start in Suggest, so the AI mode step is done with them (C-060).
    assert [s["key"] for s in body["checklist"]["steps"] if s["done"]] == [
        "connect_account",
        "choose_ai_mode",
    ]


async def test_the_thirty_days_match_the_hand_written_sql(team: Team) -> None:
    ids = await seed_month(team)

    body = await overview(team, "30d", NOW)

    await assert_matches_hand_sql(team, body, timezone=KOLKATA, now=NOW, days=30)
    current = body["current"]
    assert (current["since"], current["until"]) == ("2026-09-01", "2026-09-30")
    assert body["previous"]["since"] == "2026-08-02"
    # Zoya's turn from the 23rd is now in range: 6 days 20 min 1 s joins 5 s, 300 s, 630 s,
    # 1,800 s and Farah's 3,600 s.
    assert (current["messages_received"], current["conversations_replied"]) == (11, 6)
    assert (current["first_responses"], current["median_first_response_s"]) == (6, 1215)
    assert [(p["id"], p["comments"]) for p in body["top_posts"]] == [
        (str(ids["cakes"]), 4),
        (str(ids["old"]), 2),
        (str(ids["bread"]), 1),
    ]
    assert body["previous"]["messages_received"] == 0
    assert body["previous"]["reply_rate"] is None


async def test_needs_reply_is_the_inbox_chips_count(team: Team) -> None:
    await seed_month(team)
    body = await overview(team, "7d", NOW)
    with workspace_scope(team.wid):
        async with team.maker() as session:
            counts = await inbox_counts(session)
    assert (body["needs_reply"], body["needs_you"]) == (counts.needs_reply, counts.needs_you)


# ---------------------------------------------------------------- edge cases


async def test_an_empty_workspace_has_zeros_and_nothing_to_divide(team: Team) -> None:
    body = await overview(team, "7d", NOW)

    await assert_matches_hand_sql(team, body, timezone=KOLKATA, now=NOW, days=7)
    empty_period = {
        "messages_received": 0,
        "conversations": 0,
        "conversations_replied": 0,
        "reply_rate": None,
        "handled_by_ai": 0,
        "handled_by_ai_rate": None,
        "first_responses": 0,
        "median_first_response_s": None,
        "comments_received": 0,
    }
    assert {k: v for k, v in body["current"].items() if k not in ("since", "until")} == (
        empty_period
    )
    assert {k: v for k, v in body["previous"].items() if k not in ("since", "until")} == (
        empty_period
    )
    nothing: dict[str, Any] = {
        "total": 0,
        "analysed": 0,
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "spam": 0,
    }
    nothing |= {"positive_pct": None, "neutral_pct": None, "negative_pct": None}
    assert body["message_sentiment"] == body["comment_sentiment"] == nothing
    assert body["messages_today"] == body["needs_reply"] == body["needs_you"] == 0
    assert body["top_intents"] == body["top_posts"] == body["top_questions"] == []
    assert body["accounts_needing_attention"] == []
    assert body["checklist"]["completed"] == 0


async def test_replies_from_the_instagram_app_count_and_failed_or_queued_sends_dont(
    team: Team,
) -> None:
    seed = Seed(team, await seed_main_account(team))
    app = await seed.conversation("Answered in the app")
    await seed.message(app, ist(29, 9, 0))
    await seed.message(app, ist(29, 9, 12), source="native_app", status=None)
    failed = await seed.conversation("Failed")
    await seed.message(failed, ist(29, 10, 0))
    await seed.message(failed, ist(29, 10, 1), source="ai_auto", status="failed")
    await seed.message(failed, ist(29, 10, 2), source="human", status="sending")
    retried = await seed.conversation("Failed, then sent")
    await seed.message(retried, ist(29, 11, 0))
    await seed.message(retried, ist(29, 11, 1), source="ai_auto", status="failed")
    await seed.message(retried, ist(29, 11, 20), source="human", sent_at=ist(29, 11, 20))
    system = await seed.conversation("Only a system note")
    await seed.message(system, ist(29, 12, 0))
    await seed.message(system, ist(29, 12, 1), source="system", status=None)

    body = await overview(team, "7d", NOW)

    await assert_matches_hand_sql(team, body, timezone=KOLKATA, now=NOW, days=7)
    current = body["current"]
    assert (current["conversations"], current["conversations_replied"]) == (4, 2)
    # The app's reply is a person's; the failed Auto reply doesn't make "Failed, then sent" AI's.
    assert (current["handled_by_ai"], current["handled_by_ai_rate"]) == (0, 0.0)
    assert (current["first_responses"], current["median_first_response_s"]) == (2, 960)


async def test_local_days_across_a_daylight_saving_change(
    engine: AsyncEngine, clean_db: None
) -> None:
    """New York falls back on 1 November 2026: the 7 days to Thursday 5 November run from
    00:00 EDT on 30 October (04:00 UTC) to 00:00 EST on 6 November (05:00 UTC)."""
    team = await make_team(engine, timezone=NEW_YORK)
    seed = Seed(team, await seed_main_account(team))
    now = datetime(2026, 11, 5, 17, 0, tzinfo=UTC)  # 12:00 EST
    conv = await seed.conversation("Night owl")
    utc = [
        datetime(2026, 10, 30, 3, 59, 59, tzinfo=UTC),  # 29 Oct 23:59:59 EDT: the week before
        datetime(2026, 10, 30, 4, 0, 0, tzinfo=UTC),  # 30 Oct 00:00:00 EDT: first second
        datetime(2026, 11, 1, 5, 30, tzinfo=UTC),  # 1 Nov 01:30 EST, the repeated hour
        datetime(2026, 11, 5, 4, 59, 59, tzinfo=UTC),  # 4 Nov 23:59:59 EST
        datetime(2026, 11, 5, 5, 0, 0, tzinfo=UTC),  # 5 Nov 00:00:00 EST: today
        datetime(2026, 11, 5, 16, 0, tzinfo=UTC),  # 5 Nov 11:00 EST: today
    ]
    for i, at in enumerate(utc):
        await seed.message(conv, at)
        await seed.message(conv, at + timedelta(minutes=1), source="human", sent_at=None)
        if i == 0:
            await seed.message(conv, at + timedelta(minutes=2), source="human", status="failed")
    post = await seed.post("Pumpkin loaf", datetime(2026, 10, 20, tzinfo=UTC))
    await seed.comment(post, utc[0], sentiment="positive")
    await seed.comment(post, utc[1], sentiment="negative")

    body = await overview(team, "7d", now)

    await assert_matches_hand_sql(team, body, timezone=NEW_YORK, now=now, days=7)
    assert (body["current"]["since"], body["current"]["until"]) == ("2026-10-30", "2026-11-05")
    assert body["current"]["messages_received"] == 5
    assert body["previous"]["messages_received"] == 1
    assert body["messages_today"] == 2
    assert (body["current"]["comments_received"], body["previous"]["comments_received"]) == (1, 1)
    assert body["comment_sentiment"]["negative"] == 1
    assert body["current"]["median_first_response_s"] == 60

    # The same rows in UTC fall on other days.
    await team.execute("UPDATE workspaces SET timezone = 'UTC' WHERE id = :w", w=team.wid)
    in_utc = await overview(team, "7d", now)
    await assert_matches_hand_sql(team, in_utc, timezone="UTC", now=now, days=7)
    assert (in_utc["current"]["since"], in_utc["messages_today"]) == ("2026-10-30", 3)


async def test_the_digests_week_gives_the_digests_numbers(team: Team) -> None:
    """T8.7's "numbers match the overview endpoint": seen late on Sunday 27 September, the 7
    days are the digest's week (21-27 September) and the overview shows what it sent."""
    await seed_week(team)
    sunday_night = datetime(2026, 9, 27, 23, 0, tzinfo=ZoneInfo(KOLKATA))

    body = await overview(team, "7d", sunday_night)

    sent = expected_stats(*await post_ids(team))
    assert body["current"] == {key: sent[key] for key in body["current"]}
    assert body["top_intents"] == sent["top_intents"]
    assert [p["id"] for p in body["top_posts"]] == [p["post_id"] for p in sent["top_posts"]]
    assert body["needs_you"] == sent["needs_you"]
    assert body["knowledge_gaps_open"] == sent["open_questions"]


# ---------------------------------------------------------------- the route


async def test_the_route_serves_the_range_in_the_workspaces_time_zone(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine
) -> None:
    clerk_id, me = await sign_in(client, clerk)
    wid = uuid.UUID(me["workspaces"][0]["id"])
    owner = uuid.UUID(me["id"])
    team = Team(engine, wid, "", "", owner, owner, owner)
    await team.execute("UPDATE workspaces SET timezone = :t WHERE id = :w", t=KOLKATA, w=wid)
    seed = Seed(team, await seed_main_account(team))
    conv = await seed.conversation("Priya", awaiting_reply=True)
    await seed.message(conv, ist(30, 0, 30))  # today in India, yesterday in UTC
    await seed.message(conv, ist(20, 10, 0))  # 11 days ago: in 30d, not in 7d

    with time_machine.travel(NOW, tick=True):
        week = await client.get(f"/v1/w/{wid}/overview", headers=clerk.headers(clerk_id))
        month = await client.get(f"/v1/w/{wid}/overview?range=30d", headers=clerk.headers(clerk_id))
        bad = await client.get(f"/v1/w/{wid}/overview?range=90d", headers=clerk.headers(clerk_id))

    assert week.status_code == 200, week.text
    body = week.json()
    Overview.model_validate(body)
    assert (body["range"], body["timezone"]) == ("7d", KOLKATA)
    assert (body["messages_today"], body["current"]["messages_received"]) == (1, 1)
    assert body["needs_reply"] == 1
    assert body == await overview(team, "7d", NOW)
    assert month.json()["current"]["messages_received"] == 2
    assert month.json()["current"]["since"] == "2026-09-01"
    assert bad.status_code == 422
