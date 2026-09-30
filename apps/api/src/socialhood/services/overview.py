"""GET …/overview: Home's numbers (FR-HOME-01, UX-SCR-01; T9.1).

Every metric comes from services/overview_stats.py, the functions the weekly digest uses, so the
two agree by construction (C-053). The range is 7 or 30 local days up to and including today in
the workspace's time zone (C-039); ``previous`` is as many days just before it, for the tiles'
trend. States (needs reply, needs you, open questions, accounts needing attention, the
checklist) are as of ``now``. "Needs reply" is the inbox's own count, so the tile and the inbox
chip it links to always show the same number.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.identity import Workspace
from socialhood.models.media import MediaItem
from socialhood.schemas.posts import CommentStats
from socialhood.schemas.workspaces import (
    AccountAttention,
    IntentCount,
    Overview,
    OverviewPeriod,
    OverviewPost,
    OverviewRange,
    QuestionCount,
    SentimentSplit,
)
from socialhood.services import overview_stats as stats
from socialhood.services import workspaces
from socialhood.services.analytics.common import DateRange
from socialhood.services.conversations import inbox_counts

RANGE_DAYS: Final[dict[OverviewRange, int]] = {"7d": 7, "30d": 30}


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


async def _posts(session: AsyncSession, ranked: list[stats.PostComments]) -> list[OverviewPost]:
    """The ranked posts with what Home shows of them: the picture and the post's comment split."""
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
        )
        for post in ranked
        if (item := items.get(post.post_id)) is not None
    ]


async def overview(
    session: AsyncSession, workspace: Workspace, *, range_: OverviewRange, now: datetime
) -> Overview:
    """Home for the current workspace (the session is in its scope)."""
    tz = workspace.timezone
    span = stats.days_up_to_today(tz, now, RANGE_DAYS[range_])
    before = stats.period_before(tz, span)
    today = stats.days_up_to_today(tz, now, 1)

    current = await stats.compute(session, span=span, now=now)
    previous_inbox = await stats.inbox_stats(session, before)
    previous_comments = await stats.comments_received(session, before)
    counts = await inbox_counts(session)

    return Overview(
        range=range_,
        timezone=tz,
        checklist=await workspaces.checklist(session, workspace),
        needs_reply=counts.needs_reply,
        needs_you=current.needs_you,
        knowledge_gaps_open=current.open_questions,
        top_questions=[QuestionCount(topic=q.topic, asked=q.asked) for q in current.top_questions],
        accounts_needing_attention=[
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
        messages_today=await stats.messages_received(session, today),
        current=_period(span, current.inbox, current.comments_received),
        previous=_period(before, previous_inbox, previous_comments),
        top_intents=[
            IntentCount.model_validate({"intent": item.intent, "count": item.count})
            for item in current.top_intents
        ],
        message_sentiment=_split(await stats.message_sentiment(session, span)),
        comment_sentiment=_split(
            await stats.comment_sentiment(session, span, timezone=tz, now=now)
        ),
        top_posts=await _posts(session, current.top_posts),
    )
