"""GET …/overview: Home's numbers (FR-HOME-01, UX-SCR-01; T9.1).

Every metric comes from services/overview_stats.py, the functions the weekly digest uses, so the
two agree by construction (C-053). The range is 7 or 30 local days up to and including today in
the workspace's time zone (C-039), or a custom ``from``..``to`` (``custom_span``: local days,
both included, at most 90, ``to`` no later than today); ``previous`` is as many days just before
it, for the tiles' trend. States (needs reply, needs you, open questions, accounts needing
attention, the checklist, the priority queue) are as of ``now``. "Needs reply" is the inbox's own
count, so the tile and the inbox chip it links to always show the same number; the priority
queue (services/priority_queue.py) uses the same definitions.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.identity import Workspace
from socialhood.models.media import MediaItem
from socialhood.schemas.posts import CommentStats
from socialhood.schemas.workspaces import (
    AccountAttention,
    IntentCount,
    Overview,
    OverviewEngagement,
    OverviewGap,
    OverviewPeriod,
    OverviewPost,
    OverviewPreset,
    OverviewRange,
    QuestionCount,
    SentimentSplit,
)
from socialhood.services import overview_stats as stats
from socialhood.services import priority_queue, workspaces
from socialhood.services.analytics.common import DateRange, date_range, zone
from socialhood.services.conversations import inbox_counts

RANGE_DAYS: Final[dict[OverviewPreset, int]] = {"7d": 7, "30d": 30}
MAX_CUSTOM_DAYS: Final = 90


def _invalid(message: str, *errors: FieldError) -> ApiError:
    return ApiError("validation_error", message, errors=list(errors))


def custom_span(timezone: str, now: datetime, since: date | None, until: date | None) -> DateRange:
    """``from``..``to``: local days in the workspace's time zone, both included. Both are needed;
    ``from`` on or before ``to``, ``to`` no later than today, at most 90 days (422 otherwise,
    naming the field that is wrong)."""
    if since is None or until is None:
        missing = [
            FieldError(name, "Pick a date.")
            for name, value in (("from", since), ("to", until))
            if value is None
        ]
        raise _invalid("A custom range needs a start and an end date.", *missing)
    today = now.astimezone(zone(timezone)).date()
    if since > until:
        raise _invalid(
            "The start date is after the end date.",
            FieldError("from", "Pick a start date on or before the end date."),
        )
    if until > today:
        raise _invalid(
            "The end date is in the future.",
            FieldError("to", "Pick a date up to today."),
        )
    if (until - since).days + 1 > MAX_CUSTOM_DAYS:
        raise _invalid(
            f"A custom range is at most {MAX_CUSTOM_DAYS} days.",
            FieldError("from", f"Pick a start date at most {MAX_CUSTOM_DAYS} days before the end."),
        )
    return date_range(timezone, now, since, until)


def _period(span: DateRange, inbox: stats.InboxStats, comments: int) -> OverviewPeriod:
    return OverviewPeriod(
        since=span.since,
        until=span.until,
        messages_received=inbox.messages_received,
        conversations=inbox.conversations,
        conversations_replied=inbox.conversations_replied,
        reply_rate=inbox.reply_rate,
        handled_by_ai=inbox.handled_by_ai,
        handled_by_ai_rate=inbox.handled_by_ai_rate,
        first_responses=inbox.first_responses,
        median_first_response_s=inbox.median_first_response_s,
        comments_received=comments,
    )


def _split(split: stats.SentimentSplit) -> SentimentSplit:
    return SentimentSplit(
        total=split.total,
        analysed=split.analysed,
        positive=split.positive,
        neutral=split.neutral,
        negative=split.negative,
        spam=split.spam,
        positive_pct=split.share(split.positive),
        neutral_pct=split.share(split.neutral),
        negative_pct=split.share(split.negative),
    )


async def _posts(
    session: AsyncSession, ranked: list[stats.PostComments], rates: dict[uuid.UUID, float]
) -> list[OverviewPost]:
    """The ranked posts with what Home shows of them: the picture, the post's comment split and
    its engagement rate in the range (when a snapshot gives one)."""
    if not ranked:
        return []
    items = {
        item.id: item
        for item in await session.scalars(
            select(MediaItem).where(MediaItem.id.in_([post.post_id for post in ranked]))
        )
    }
    return [
        OverviewPost(
            id=item.id,
            social_account_id=item.social_account_id,
            media_type=item.media_type,
            caption=item.caption,
            media_url=item.media_url,
            thumbnail_url=item.thumbnail_url,
            permalink=item.permalink,
            posted_at=item.posted_at,
            comments=post.comments,
            stats=CommentStats.from_stored(item.comment_stats),
            engagement_rate=rates.get(item.id),
        )
        for post in ranked
        if (item := items.get(post.post_id)) is not None
    ]


def _gap(question: stats.LatestQuestion | None) -> OverviewGap | None:
    if question is None:
        return None
    return OverviewGap(
        id=question.gap_id,
        topic=question.topic,
        question=question.question,
        asked=question.asked,
        last_seen_at=question.last_seen_at,
        conversation_id=question.conversation_id,
        message_id=question.message_id,
    )


async def overview(
    session: AsyncSession,
    workspace: Workspace,
    *,
    range_: OverviewRange,
    now: datetime,
    since: date | None = None,
    until: date | None = None,
    human_agent: bool = False,
) -> Overview:
    """Home for the current workspace (the session is in its scope). ``range_`` "custom" takes
    ``since`` and ``until`` (validated by ``custom_span``). ``human_agent`` is
    IG_HUMAN_AGENT_ENABLED, for the priority queue's reply windows."""
    tz = workspace.timezone
    if range_ == "custom":
        span = custom_span(tz, now, since, until)
    else:
        span = stats.days_up_to_today(tz, now, RANGE_DAYS[range_])
    before = stats.period_before(tz, span)
    today = stats.days_up_to_today(tz, now, 1)

    current = await stats.compute(session, span=span, now=now)
    previous_inbox = await stats.inbox_stats(session, before)
    previous_comments = await stats.comments_received(session, before)
    counts = await inbox_counts(session)
    connected, platforms = await stats.accounts_connected(session)
    rates = await stats.engagement_rates(session, [p.post_id for p in current.top_posts], span)
    top_posts = await _posts(session, current.top_posts, rates)
    engagement = stats.mean_engagement(
        [p.engagement_rate for p in top_posts if p.engagement_rate is not None]
    )
    latest = await stats.latest_question(session, now=now) if current.open_questions else None
    oldest = await priority_queue.oldest_waiting_since(session) if counts.needs_reply else None

    return Overview.model_validate(
        {
            "range": range_,
            "days": (span.until - span.since).days + 1,
            "timezone": tz,
            "checklist": await workspaces.checklist(session, workspace),
            "needs_reply": counts.needs_reply,
            "needs_you": current.needs_you,
            "oldest_waiting_since": oldest,
            "knowledge_gaps_open": current.open_questions,
            "top_questions": [
                QuestionCount(topic=q.topic, asked=q.asked) for q in current.top_questions
            ],
            "latest_gap": _gap(latest),
            "accounts_needing_attention": [
                AccountAttention.model_validate(
                    {
                        "id": acct.account_id,
                        "platform": acct.platform,
                        "username": acct.username,
                        "status": acct.status,
                    }
                )
                for acct in await stats.accounts_needing_attention(session)
            ],
            "accounts_connected": connected,
            "platforms_connected": platforms,
            "priority_queue": await priority_queue.priority_queue(
                session, now=now, human_agent=human_agent
            ),
            "messages_today": await stats.messages_received(session, today),
            "current": _period(span, current.inbox, current.comments_received),
            "previous": _period(before, previous_inbox, previous_comments),
            "top_intents": [
                IntentCount.model_validate({"intent": item.intent, "count": item.count})
                for item in current.top_intents
            ],
            "message_sentiment": _split(await stats.message_sentiment(session, span)),
            "comment_sentiment": _split(
                await stats.comment_sentiment(session, span, timezone=tz, now=now)
            ),
            "top_posts": top_posts,
            "top_posts_engagement": (
                OverviewEngagement(rate=engagement.rate, posts=engagement.posts)
                if engagement is not None
                else None
            ),
        }
    )
