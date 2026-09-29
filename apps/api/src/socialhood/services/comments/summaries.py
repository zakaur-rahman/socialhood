"""Post summaries (T6.2; TR-AI-11, FR-CMT-04, FR-AI-05, FR-PRV-02).

``summarize_post(media_item_id)`` (bulk lane, queueing lock and run lock ``postsum:{id}``) runs
after 20 new analysed comments on the post (analyze_comments queues it a minute ahead, so a surge
is summarised about once a minute), once the post's summary is 24 hours behind an analysed comment
(``dispatch_post_summaries``, hourly), or at once when a member presses Refresh
(POST …/posts/{id}/summary, 202).

SQL computes the post's sentiment counts and its 50 most frequent topics (analysed comments that are
not spam and not deleted). The model (AI_MODEL_REPLY, prompt ``post_summary.v1``) gets them, the
caption and a sample of comments as data, and returns a summary of two or three sentences and at
most 6 labels, each listing the topics it merges (``{label, members[]}``). Code keeps only topics
from the input, each in the first label that claims it, then computes each label's comment count
and sentiment from the mapping (``count = positive + neutral + negative`` of its topics' comments)
and orders the labels largest first. The call costs 2 credits (post_summary, §1.7). The summary,
topics and summary_updated_at are stored and post.updated published.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai import prompts
from socialhood.ai.metering import QuotaExceeded, metered, quota
from socialhood.ai.provider import AIError, Turn
from socialhood.ai.registry import get_provider
from socialhood.billing.plans import CREDIT_COSTS
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.models.media import MediaItem
from socialhood.observability.logging import get_logger
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import comment_analyses as repo
from socialhood.repositories import comments as comments_repo
from socialhood.repositories import social_accounts as accounts
from socialhood.services.analysis import business_profile
from socialhood.services.comments import views
from socialhood.settings import Settings

log = get_logger(__name__)

FEATURE = "post_summary"
TOP_TOPICS = 50  # TR-AI-11
MAX_LABELS = 6
SAMPLE_COMMENTS = 30
COMMENT_CHARS = 300
CAPTION_CHARS = 600
LABEL_CHARS = 40
SUMMARY_CHARS = 700
MAX_OUTPUT_TOKENS = 1024
TEMPERATURE = 0.2
TIMEOUT_S = 20.0
AFTER_ANALYSIS_DELAY_S = 60.0
ANALYSIS_OFF = "AI analysis is off for this account, so its comments are not summarised."
NO_ANALYSES = "No comments on this post have been analysed yet."
NO_CREDITS = "Your AI credits are used up until they reset."
SENTIMENTS = ("positive", "neutral", "negative")


class TopicLabel(BaseModel):
    label: str
    members: list[str]


class PostSummaryOut(BaseModel):
    """What the model returns (TR-AI-11)."""

    summary: str
    labels: list[TopicLabel]


Outcome = Literal[
    "summarised", "not_found", "analysis_off", "no_analyses", "quota_exhausted", "failed"
]


@dataclass(frozen=True)
class SummaryRun:
    outcome: Outcome


def summary_key(media_item_id: uuid.UUID) -> str:
    return f"postsum:{media_item_id}"


async def enqueue_summary(
    media_item_id: uuid.UUID, workspace_id: uuid.UUID, *, delay_s: float = 0
) -> bool:
    """False when a summary of the post is already waiting. The analysis job delays it by
    AFTER_ANALYSIS_DELAY_S: during a surge every batch of 50 is 20 new comments, and the waiting
    job absorbs them, so a viral post is summarised about once a minute, not once a batch."""
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.comments import summarize_post as task

    key = summary_key(media_item_id)
    return await enqueue(
        task,
        key=key,
        lock=key,
        delay_s=delay_s,
        workspace_id=str(workspace_id),
        media_item_id=str(media_item_id),
    )


async def request_summary(session: AsyncSession, item: MediaItem) -> None:
    """The summary card's Refresh (UX-SCR-05): 409 with analysis off (FR-PRV-02) or without any
    analysed comment, 402 without the credits; otherwise the job is queued."""
    acct = await accounts.get(session, item.social_account_id)
    if acct is None or not acct.ai_analysis_enabled:
        raise ApiError("conflict", ANALYSIS_OFF)
    if not await repo.has_analyses(session, item.id):
        raise ApiError("conflict", NO_ANALYSES)
    if not (await quota(session)).allows(CREDIT_COSTS[FEATURE]):
        raise ApiError("quota_exceeded", NO_CREDITS)
    await enqueue_summary(item.id, item.workspace_id)


# ---------------------------------------------------------------- the topic mapping


def label_topics(
    labels: Sequence[TopicLabel],
    topics: Sequence[str],
    sentiments: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    """The stored ``media_items.topics``: the model's labels over the input topics, each topic in
    the first label that claims it, at most 6 labels, each with the count and sentiment of its
    topics' comments computed here (never by the model), largest first."""
    known = set(topics)
    claimed: set[str] = set()
    merged: dict[str, set[str]] = {}
    for entry in labels:
        label = " ".join(entry.label.casefold().split())[:LABEL_CHARS].strip()
        members = {m for m in entry.members if m in known and m not in claimed}
        if not label or not members:
            continue
        claimed |= members
        merged.setdefault(label, set()).update(members)
    out: list[dict[str, Any]] = []
    for label, members in merged.items():
        counts = {
            name: sum(sentiments.get(m, {}).get(name, 0) for m in members) for name in SENTIMENTS
        }
        count = sum(counts.values())
        if count:
            out.append({"label": label, "count": count, **counts})
    out.sort(key=lambda t: (-t["count"], t["label"]))
    return out[:MAX_LABELS]


def _render(
    caption: str | None,
    stats: dict[str, int],
    topics: Sequence[tuple[str, int]],
    samples: Sequence[str],
) -> str:
    lines = [
        f"POST CAPTION: {' '.join((caption or '').split())[:CAPTION_CHARS] or '-'}",
        (
            f"COMMENTS: {stats['positive']} positive, {stats['neutral']} neutral, "
            f"{stats['negative']} negative, {stats['spam']} spam"
        ),
        "TOPICS (topic: comments):",
        *[f"- {topic}: {count}" for topic, count in topics],
        "SAMPLE COMMENTS:",
        *[f"- {' '.join(text.split())[:COMMENT_CHARS]}" for text in samples],
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- the job


async def summarize_post(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    settings: Settings,
    *,
    workspace_id: uuid.UUID,
    media_item_id: uuid.UUID,
    now: datetime | None = None,
) -> SummaryRun:
    """The summarize_post job. A retryable AIError propagates (one retry; the credits were
    refunded)."""
    now = now or datetime.now(UTC)
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            item = await comments_repo.get_media_item(session, media_item_id)
            if item is None:
                return SummaryRun("not_found")
            acct = await accounts.get(session, item.social_account_id)
            if acct is None or not acct.ai_analysis_enabled:
                return SummaryRun("analysis_off")
            if not await repo.has_analyses(session, item.id):
                return SummaryRun("no_analyses")
            stats = await repo.count_stats(session, item.id)
            topics = await repo.top_topics(session, item.id, TOP_TOPICS)
            samples = await repo.sample_comments(session, item.id, SAMPLE_COMMENTS)
            name, description = await business_profile(session)
            caption = item.caption

        prompt = prompts.load("post_summary")
        try:
            async with metered(
                sessionmaker,
                workspace_id=workspace_id,
                feature=FEATURE,
                ref_type="media_item",
                ref_id=media_item_id,
                now=now,
            ) as meter:
                result = await get_provider().generate_json(
                    task="post_summary",
                    schema=PostSummaryOut,
                    system=prompt.render(business_name=name, business_description=description),
                    contents=[Turn("user", _render(caption, stats, topics, samples))],
                    model=settings.ai_model_reply,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    temperature=TEMPERATURE,
                    timeout_s=TIMEOUT_S,
                )
                meter.record(result)
        except QuotaExceeded:
            log.info("post_summary_skipped", media_item_id=str(media_item_id), reason="quota")
            return SummaryRun("quota_exhausted")
        except AIError as error:
            if error.retryable:
                raise
            log.warning("post_summary_failed", media_item_id=str(media_item_id), code=error.code)
            return SummaryRun("failed")

        summary = " ".join(result.value.summary.split())[:SUMMARY_CHARS]
        if not summary:
            log.warning("post_summary_failed", media_item_id=str(media_item_id), code="empty")
            return SummaryRun("failed")
        async with sessionmaker() as session:
            topic_names = [topic for topic, _ in topics]
            sentiments = await repo.topic_sentiments(session, media_item_id, topic_names)
            locked = await repo.lock_post(session, media_item_id)
            if locked is None:
                return SummaryRun("not_found")
            locked.summary = summary
            locked.topics = label_topics(result.value.labels, topic_names, sentiments)
            locked.summary_updated_at = now
            await session.flush()
            views.queue_post(session, locked)
            await commit_and_publish(session, redis)
    log.info("post_summarised", media_item_id=str(media_item_id), labels=len(locked.topics or []))
    return SummaryRun("summarised")
