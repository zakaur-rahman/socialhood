"""The workspace's headline numbers over a date range: one definition for the weekly digest
(FR-NOT-04, T8.7) and the Home overview (FR-HOME-01, T9.1).

**GET …/overview (T9.1, services/overview.py) builds its metrics on these functions**, so that
"numbers match the overview endpoint" (T8.7's acceptance) holds by construction: the digest is
``compute`` over the Monday to Sunday before it is sent (``week_before``), and the overview over
its range (``days_up_to_today``: 7d or 30d, the local days up to and including today, like the
analytics ranges of C-039), compared with the same number of days before it (``period_before``).
Home's extra numbers live here too: messages today (``messages_received`` over today), the
sentiment splits of messages and comments, and the accounts that need attention. Conversations
needing a reply are the inbox's own count (services/conversations.py ``inbox_counts``).

Ranges are local calendar days in the workspace's time zone (services/analytics/common.py
``date_range``), start included, end excluded. Definitions:

- **Messages received**: customer messages (inbound, source customer) that arrived in the range.
- **A reply** is a business message that reached the customer: outbound, from a person, Auto,
  an automation or the Instagram app (any source; system messages don't count), not failed or
  still queued; its time is when it was sent.
- **Reply rate**: of the conversations where a customer wrote in the range, the share (%) with a
  reply after that customer's first message in the range and before the range ended.
- **Handled by AI**: of those replied conversations, the share whose replies in that span all
  came from Auto or automations.
- **Median first response**: over customer turns that started in the range (a customer message
  whose previous message in the conversation, looking back 30 days, wasn't the customer's), the
  median time to the first reply, counting turns answered before the range ended
  (Response time in §1.2: "median time from inbound message to first reply, any source").
- **Top intents**: analysed customer messages in the range by intent (a member's correction
  wins), most first; "other" and "spam" are left out.
- **Needs you**: open conversations marked "Needs you" now.
- **Unanswered questions**: knowledge gaps open now, asked in the last 30 days, most asked first
  (the Knowledge page's list, FR-KB-06).
- **Comments** and **top posts**: comments made in the range and not deleted; posts ranked by
  them, most first, then the newest post.
- **Message sentiment**: customer messages received in the range, by their analysis's sentiment
  (a member's correction wins). Spam (the intent, correction winning) is counted apart and
  messages without an analysis are reported as such, never guessed; positive + neutral +
  negative are the analysed messages that are not spam, and the shares are of that sum.
- **Comment sentiment**: the analytics distribution for the same days (services/analytics/
  sentiment.py; C-039): comments made in the range and not deleted, spam apart.
- **Accounts needing attention**: connected accounts that need reconnecting or are in error.
Percentages are 0 to 100 with one decimal, None when there is nothing to divide.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import ColumnElement, and_, case, exists, extract, func, literal, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from socialhood.db.tenancy import require_workspace
from socialhood.models.ai import GapStatus, MessageAnalysis, Sentiment
from socialhood.models.automations import Comment
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.inbox import (
    Conversation,
    ConversationStatus,
    Direction,
    Message,
    MessageSource,
    MessageStatus,
)
from socialhood.models.media import MediaItem
from socialhood.platforms.capabilities import Capability
from socialhood.repositories import knowledge as knowledge_repo
from socialhood.services.analytics.common import DateRange, View, date_range, zone
from socialhood.services.analytics.sentiment import sentiment_distribution
from socialhood.services.knowledge import gaps

REPLY_SOURCES = (
    MessageSource.HUMAN,
    MessageSource.AI_AUTO,
    MessageSource.AUTOMATION,
    MessageSource.NATIVE_APP,
)
AI_SOURCES = (MessageSource.AI_AUTO, MessageSource.AUTOMATION)
REACHED = (MessageStatus.SENT, MessageStatus.DELIVERED, MessageStatus.READ)
LEFT_OUT_INTENTS = ("other", "spam")
SPAM_INTENT = "spam"
NEEDS_ATTENTION = (AccountStatus.NEEDS_RECONNECT, AccountStatus.ERROR)
TURN_LOOKBACK = timedelta(days=30)
TOP_N = 3


# ---------------------------------------------------------------- ranges


def days_up_to_today(timezone: str, now: datetime, days: int) -> DateRange:
    """The ``days`` local days ending today (the overview's 7d and 30d)."""
    today = now.astimezone(zone(timezone)).date()
    return date_range(timezone, now, today - timedelta(days=days - 1), today)


def period_before(timezone: str, span: DateRange) -> DateRange:
    """The same number of local days just before ``span`` (the overview's comparison). Local
    midnight to local midnight, so a daylight-saving change makes it an hour longer or shorter."""
    tz = zone(timezone)
    days = (span.until - span.since).days + 1
    since = span.since - timedelta(days=days)
    return DateRange(
        since=since,
        until=span.since - timedelta(days=1),
        start=datetime.combine(since, time.min, tzinfo=tz),
        end=datetime.combine(span.since, time.min, tzinfo=tz),
    )


def week_before(timezone: str, week_start: date) -> DateRange:
    """Monday to Sunday before ``week_start`` (a Monday), in the workspace's time zone: what
    the digest sent that Monday covers. Across a daylight-saving change the span is 167 or 169
    hours: local midnight to local midnight."""
    tz = zone(timezone)
    since = week_start - timedelta(days=7)
    return DateRange(
        since=since,
        until=week_start - timedelta(days=1),
        start=datetime.combine(since, time.min, tzinfo=tz),
        end=datetime.combine(week_start, time.min, tzinfo=tz),
    )


# ---------------------------------------------------------------- results


@dataclass(frozen=True)
class IntentCount:
    intent: str
    count: int


@dataclass(frozen=True)
class QuestionCount:
    topic: str
    asked: int


@dataclass(frozen=True)
class PostComments:
    post_id: uuid.UUID
    caption: str | None
    permalink: str | None
    media_type: str
    posted_at: datetime
    comments: int


@dataclass(frozen=True)
class InboxStats:
    messages_received: int
    conversations: int  # conversations where a customer wrote in the range
    conversations_replied: int
    handled_by_ai: int  # replied conversations answered only by Auto or automations
    first_responses: int  # customer turns in the median
    median_first_response_s: int | None

    @property
    def reply_rate(self) -> float | None:
        return pct(self.conversations_replied, self.conversations)

    @property
    def handled_by_ai_rate(self) -> float | None:
        return pct(self.handled_by_ai, self.conversations_replied)


@dataclass(frozen=True)
class OverviewStats:
    since: date
    until: date
    inbox: InboxStats
    top_intents: list[IntentCount] = field(default_factory=list)
    comments_received: int = 0
    top_posts: list[PostComments] = field(default_factory=list)
    needs_you: int = 0
    open_questions: int = 0
    top_questions: list[QuestionCount] = field(default_factory=list)

    @property
    def active(self) -> bool:
        """Anything to report: messages, comments, or conversations waiting for a person."""
        return bool(self.inbox.messages_received or self.comments_received or self.needs_you)

    def to_json(self) -> dict[str, Any]:
        """A JSON object (weekly_digests.stats, the digest email's data)."""
        inbox = self.inbox
        return {
            "since": self.since.isoformat(),
            "until": self.until.isoformat(),
            "messages_received": inbox.messages_received,
            "conversations": inbox.conversations,
            "conversations_replied": inbox.conversations_replied,
            "reply_rate": inbox.reply_rate,
            "handled_by_ai": inbox.handled_by_ai,
            "handled_by_ai_rate": inbox.handled_by_ai_rate,
            "first_responses": inbox.first_responses,
            "median_first_response_s": inbox.median_first_response_s,
            "top_intents": [asdict(item) for item in self.top_intents],
            "comments_received": self.comments_received,
            "top_posts": [
                {
                    **asdict(post),
                    "post_id": str(post.post_id),
                    "posted_at": post.posted_at.isoformat(),
                }
                for post in self.top_posts
            ],
            "needs_you": self.needs_you,
            "open_questions": self.open_questions,
            "top_questions": [asdict(item) for item in self.top_questions],
        }


@dataclass(frozen=True)
class SentimentSplit:
    total: int  # messages or comments in the range
    analysed: int  # of them, with an analysis
    positive: int  # analysed and not spam
    neutral: int
    negative: int
    spam: int

    def share(self, part: int) -> float | None:
        """A share of the analysed, non-spam total (positive + neutral + negative)."""
        return pct(part, self.positive + self.neutral + self.negative)


@dataclass(frozen=True)
class AccountAttention:
    account_id: uuid.UUID
    platform: str
    username: str | None
    status: str  # needs_reconnect or error


def pct(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None


# ---------------------------------------------------------------- queries


def _customer(m: type[Message] | Any) -> ColumnElement[bool]:
    return and_(m.direction == Direction.INBOUND, m.source == MessageSource.CUSTOMER)


def _reply(m: type[Message] | Any) -> ColumnElement[bool]:
    return and_(
        m.direction == Direction.OUTBOUND,
        m.source.in_(REPLY_SOURCES),
        or_(m.status.is_(None), m.status.in_(REACHED)),
    )


def _reply_at(m: type[Message] | Any) -> ColumnElement[datetime]:
    return func.coalesce(m.sent_at, m.occurred_at)


def _received_in(ws: uuid.UUID, span: DateRange) -> ColumnElement[bool]:
    """Customer messages that arrived in the range."""
    return and_(
        Message.workspace_id == ws,
        _customer(Message),
        Message.occurred_at >= span.start,
        Message.occurred_at < span.end,
    )


async def messages_received(session: AsyncSession, span: DateRange) -> int:
    """Messages received: Home's "Messages today" is this over today."""
    ws = require_workspace()
    return int(
        await session.scalar(
            select(func.count()).select_from(Message).where(_received_in(ws, span))
        )
        or 0
    )


async def inbox_stats(session: AsyncSession, span: DateRange) -> InboxStats:
    ws = require_workspace()
    start, end = span.start, span.end
    in_range = _received_in(ws, span)
    received = await messages_received(session, span)

    # Reply rate and handled by AI, per conversation.
    firsts = (
        select(
            Message.conversation_id.label("conv"),
            func.min(Message.occurred_at).label("first_at"),
        )
        .where(in_range)
        .group_by(Message.conversation_id)
        .cte("firsts")
    )
    reply = aliased(Message)
    after_first = and_(
        reply.workspace_id == ws,
        reply.conversation_id == firsts.c.conv,
        _reply(reply),
        _reply_at(reply) >= firsts.c.first_at,
        _reply_at(reply) < end,
    )
    replied = exists().where(after_first)
    by_person = exists().where(after_first, reply.source.not_in(AI_SOURCES))
    counts = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(replied),
                func.count().filter(and_(replied, not_(by_person))),
            ).select_from(firsts)
        )
    ).one()

    # First responses, per customer turn.
    who = case((_customer(Message), literal("c")), else_=literal("b"))
    at = case((_customer(Message), Message.occurred_at), else_=_reply_at(Message))
    touched = select(Message.conversation_id).where(in_range).distinct()
    stream = (
        select(Message.conversation_id.label("conv"), at.label("at"), who.label("who"))
        .where(
            Message.workspace_id == ws,
            Message.conversation_id.in_(touched),
            or_(_customer(Message), _reply(Message)),
            Message.occurred_at >= start - TURN_LOOKBACK,
            at < end,
        )
        .cte("stream")
    )
    marked = select(
        stream.c.conv,
        stream.c.at,
        stream.c.who,
        func.lag(stream.c.who).over(partition_by=stream.c.conv, order_by=stream.c.at).label("prev"),
    ).cte("marked")
    turns = (
        select(marked.c.conv, marked.c.at.label("asked_at"))
        .where(
            marked.c.who == "c",
            or_(marked.c.prev.is_(None), marked.c.prev == "b"),
            marked.c.at >= start,
        )
        .cte("turns")
    )
    answer = aliased(stream)
    first_reply = (
        select(func.min(answer.c.at))
        .where(answer.c.conv == turns.c.conv, answer.c.who == "b", answer.c.at > turns.c.asked_at)
        .correlate(turns)
        .scalar_subquery()
    )
    waits = select(extract("epoch", first_reply - turns.c.asked_at).label("wait")).subquery()
    median, answered = (
        await session.execute(
            select(
                func.percentile_cont(0.5).within_group(waits.c.wait),
                func.count(waits.c.wait),
            )
        )
    ).one()
    return InboxStats(
        messages_received=received,
        conversations=int(counts[0]),
        conversations_replied=int(counts[1]),
        handled_by_ai=int(counts[2]),
        first_responses=int(answered),
        median_first_response_s=round(float(median)) if median is not None else None,
    )


async def top_intents(session: AsyncSession, span: DateRange, n: int = TOP_N) -> list[IntentCount]:
    ws = require_workspace()
    intent = func.coalesce(MessageAnalysis.corrected_intent, MessageAnalysis.intent)
    count = func.count()
    rows = await session.execute(
        select(intent.label("intent"), count.label("n"))
        .select_from(MessageAnalysis)
        .join(Message, Message.id == MessageAnalysis.message_id)
        .where(
            MessageAnalysis.workspace_id == ws,
            Message.workspace_id == ws,
            Message.occurred_at >= span.start,
            Message.occurred_at < span.end,
            intent.not_in(LEFT_OUT_INTENTS),
        )
        .group_by(intent)
        .order_by(count.desc(), intent)
        .limit(n)
    )
    return [IntentCount(intent=row.intent, count=int(row.n)) for row in rows]


def _comments_in(ws: uuid.UUID, span: DateRange) -> ColumnElement[bool]:
    return and_(
        Comment.workspace_id == ws,
        Comment.deleted_at.is_(None),
        Comment.commented_at >= span.start,
        Comment.commented_at < span.end,
    )


async def comments_received(session: AsyncSession, span: DateRange) -> int:
    ws = require_workspace()
    return int(
        await session.scalar(
            select(func.count()).select_from(Comment).where(_comments_in(ws, span))
        )
        or 0
    )


async def comments(
    session: AsyncSession, span: DateRange, n: int = TOP_N
) -> tuple[int, list[PostComments]]:
    """Comments made in the range, and the ``n`` posts with the most of them."""
    ws = require_workspace()
    scope = _comments_in(ws, span)
    total = await comments_received(session, span)
    if not total:
        return 0, []
    count = func.count(Comment.id)
    rows = await session.execute(
        select(
            MediaItem.id,
            MediaItem.caption,
            MediaItem.permalink,
            MediaItem.media_type,
            MediaItem.posted_at,
            count.label("n"),
        )
        .join(Comment, Comment.media_item_id == MediaItem.id)
        .where(scope, MediaItem.workspace_id == ws)
        .group_by(MediaItem.id)
        .order_by(count.desc(), MediaItem.posted_at.desc(), MediaItem.id)
        .limit(n)
    )
    return total, [
        PostComments(
            post_id=row.id,
            caption=row.caption,
            permalink=row.permalink,
            media_type=row.media_type,
            posted_at=row.posted_at,
            comments=int(row.n),
        )
        for row in rows
    ]


async def needs_you(session: AsyncSession) -> int:
    ws = require_workspace()
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(
                Conversation.workspace_id == ws,
                Conversation.status == ConversationStatus.OPEN,
                Conversation.needs_human.is_(True),
            )
        )
        or 0
    )


async def message_sentiment(session: AsyncSession, span: DateRange) -> SentimentSplit:
    ws = require_workspace()
    sentiment = func.coalesce(MessageAnalysis.corrected_sentiment, MessageAnalysis.sentiment)
    is_spam = func.coalesce(MessageAnalysis.corrected_intent, MessageAnalysis.intent) == SPAM_INTENT
    analysed = func.count(MessageAnalysis.id)

    def clean(name: Sentiment) -> ColumnElement[int]:
        return analysed.filter(and_(not_(is_spam), sentiment == name.value))

    row = (
        await session.execute(
            select(
                func.count(Message.id),
                analysed,
                clean(Sentiment.POSITIVE),
                clean(Sentiment.NEUTRAL),
                clean(Sentiment.NEGATIVE),
                analysed.filter(is_spam),
            )
            .select_from(Message)
            .outerjoin(
                MessageAnalysis,
                and_(
                    MessageAnalysis.message_id == Message.id,
                    MessageAnalysis.workspace_id == ws,
                ),
            )
            .where(_received_in(ws, span))
        )
    ).one()
    total, done, positive, neutral, negative, spam = (int(v or 0) for v in row)
    return SentimentSplit(total, done, positive, neutral, negative, spam)


def _no_capabilities(acct: SocialAccount) -> frozenset[Capability]:
    return frozenset()  # the sentiment distribution reads no insights


async def comment_sentiment(
    session: AsyncSession, span: DateRange, *, timezone: str, now: datetime
) -> SentimentSplit:
    """``span`` must be local days in ``timezone`` (``days_up_to_today``, ``period_before``):
    the analytics distribution is asked for the same days."""
    dist = await sentiment_distribution(
        session, View(timezone, now, _no_capabilities), since=span.since, until=span.until
    )
    return SentimentSplit(
        dist.total, dist.analysed, dist.positive, dist.neutral, dist.negative, dist.spam
    )


async def accounts_needing_attention(session: AsyncSession) -> list[AccountAttention]:
    ws = require_workspace()
    rows = await session.execute(
        select(
            SocialAccount.id, SocialAccount.platform, SocialAccount.username, SocialAccount.status
        )
        .where(SocialAccount.workspace_id == ws, SocialAccount.status.in_(NEEDS_ATTENTION))
        .order_by(SocialAccount.connected_at, SocialAccount.id)
    )
    return [
        AccountAttention(
            account_id=row.id, platform=row.platform, username=row.username, status=row.status
        )
        for row in rows
    ]


async def unanswered_questions(
    session: AsyncSession, *, now: datetime, n: int = TOP_N
) -> tuple[int, list[QuestionCount]]:
    open_count = await gaps.count_open(session, now=now)
    if not open_count:
        return 0, []
    rows = await knowledge_repo.list_gaps(
        session, status=GapStatus.OPEN, since=now - gaps.WINDOW, limit=n
    )
    return open_count, [QuestionCount(topic=row.topic, asked=row.occurrences) for row in rows]


async def compute(session: AsyncSession, *, span: DateRange, now: datetime) -> OverviewStats:
    """Every number for the current workspace: flows over ``span``, states as of ``now``."""
    received, posts = await comments(session, span)
    open_count, questions = await unanswered_questions(session, now=now)
    return OverviewStats(
        since=span.since,
        until=span.until,
        inbox=await inbox_stats(session, span),
        top_intents=await top_intents(session, span),
        comments_received=received,
        top_posts=posts,
        needs_you=await needs_you(session),
        open_questions=open_count,
        top_questions=questions,
    )
