"""Comment analysis (T6.2; TR-AI-11, FR-CMT-02, FR-CMT-05, FR-PRV-02, FR-AI-05, TR-JOB-06, §1.7).

Comments arrive ``pending`` (webhooks and the backfill, F-12). Every 30 seconds
``dispatch_comment_analysis`` queues ``analyze_comments(account_id)`` for each live account with
pending comments, under the queueing lock and run lock ``cmt:{account_id}``: at most one run waits
and one runs per account, so an account never holds more than one bulk slot, and a workspace never
more than BULK_CONCURRENCY_PER_WORKSPACE (4) through the per-workspace semaphore (TR-JOB-06). A
viral post's 20,000 comments are worked through in arrival order at a bounded rate while other
workspaces keep their own slots (FR-CMT-02); ``stats.analysed`` against ``stats.total`` shows the
progress. Each run does up to MAX_BATCHES_PER_RUN batches and, when comments are still pending,
queues the next run before it gives its slot back.

A batch:

1. With AI analysis off for the account, its pending comments become ``skipped`` and nothing is
   sent to the provider (FR-PRV-02). On a plan limiting ``comment_intelligence_posts`` (Free: the
   5 most recent posts), comments on older posts are skipped (§1.7). Deleted and empty comments
   are skipped.
2. Up to 50 pending comments of the account, oldest first, go to the provider in one call with
   AI_MODEL_ANALYSIS and the versioned prompt ``comment_analysis.v1``: the business's name and
   description in the system prompt, the captions and comments as data in the contents (TR-AI-04).
   Comments are numbered in the call and the answer must hold exactly one reading per number (the
   schema's validator, so Gemini retries once with the error). The call is metered as
   comment_analysis at 1 credit per 20 comments, rounded up (§1.7). With the credits used up
   nothing is called and the account's pending comments are skipped, like DMs (FR-AI-05), so the
   post's "Analysing n of m" completes (``analysed`` counts skipped comments too).
3. An answer that is still invalid, or blocked, is tried again in halves so one comment cannot sink
   the batch; a comment that fails alone, or is left when MAX_CALLS_PER_BATCH calls were made, is
   skipped. Another failure after part of the batch was read keeps the rest pending.
4. Spam is hidden on Instagram when the account's auto-hide is on (FR-CMT-05), before the batch is
   stored; a refusal leaves the comment visible.
5. The analyses are stored (once per comment), the comments marked done, their posts' comment stats
   recounted, and comment.updated and post.updated published. A post with 20 analyses since its
   last summary gets ``summarize_post`` (services/comments/summaries; the 24 h rule is swept
   hourly).
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, model_validator
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai import prompts
from socialhood.ai.metering import QuotaExceeded, metered
from socialhood.ai.provider import AIError, Turn
from socialhood.ai.registry import get_provider
from socialhood.billing.plans import current_plan, entitlement
from socialhood.db.tenancy import workspace_scope
from socialhood.models.automations import AnalysisStatus, Comment
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import comment_analyses as repo
from socialhood.repositories import comments as comments_repo
from socialhood.repositories import social_accounts as accounts
from socialhood.schemas.ai import SentimentName
from socialhood.schemas.inbox import IntentName
from socialhood.services.analysis import business_profile
from socialhood.services.comments import views
from socialhood.settings import Settings

log = get_logger(__name__)

FEATURE = "comment_analysis"
BATCH_SIZE = 50  # TR-AI-11
COMMENTS_PER_CREDIT = 20  # §1.7
MAX_BATCHES_PER_RUN = 10
MAX_CALLS_PER_BATCH = 12
MAX_OUTPUT_TOKENS = 4096
TEMPERATURE = 0.0
TIMEOUT_S = 30.0
COMMENT_CHARS = 500
CAPTION_CHARS = 300
TOPIC_WORDS = 3
TOPIC_CHARS = 60
SUMMARY_AFTER = 20  # TR-AI-11: new analysed comments since the post's last summary
SPLIT_CODES = frozenset({"invalid_output", "blocked"})

Outcome = Literal[
    "analysed", "nothing_pending", "not_found", "analysis_off", "quota_exhausted", "failed"
]


class CommentReading(BaseModel):
    """One comment's reading as the model returns it (TR-AI-11)."""

    id: str
    sentiment: SentimentName
    sentiment_score: float
    intent: IntentName
    is_spam: bool
    topic: str | None = None


class CommentReadings(BaseModel):
    """The model's answer for a batch. ``readings_schema`` makes a subclass that requires exactly
    one reading per comment number of the batch."""

    items: list[CommentReading]

    expected_ids: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _one_per_comment(self) -> CommentReadings:
        expected = type(self).expected_ids
        if not expected:
            return self
        seen = [item.id for item in self.items]
        problems = [
            f"{label}: {', '.join(sorted(ids, key=_number))}"
            for label, ids in (
                ("missing ids", expected - set(seen)),
                ("unknown ids", set(seen) - expected),
                ("repeated ids", {i for i in seen if seen.count(i) > 1}),
            )
            if ids
        ]
        if problems:
            raise ValueError("return exactly one item per comment; " + "; ".join(problems))
        return self


def _number(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (1 << 30, value)


def readings_schema(ids: Sequence[str]) -> type[CommentReadings]:
    """The answer schema for a batch whose comments are numbered ``ids``."""
    return type(
        "CommentReadings",
        (CommentReadings,),
        {"expected_ids": frozenset(ids), "__module__": __name__},
    )


@dataclass(frozen=True)
class BatchRun:
    outcome: Outcome
    analysed: int = 0
    skipped: int = 0
    hidden: int = 0
    calls: int = 0
    more: bool = False  # comments are still pending
    summaries_queued: int = 0


@dataclass(frozen=True)
class AccountRun:
    """One analyze_comments run: its batches, and whether another run should follow."""

    outcome: Outcome
    batches: int = 0
    analysed: int = 0
    skipped: int = 0
    hidden: int = 0
    calls: int = 0
    more: bool = False


@dataclass
class _Batch:
    acct: SocialAccount
    comments: list[Comment]
    captions: dict[uuid.UUID, str | None]
    system: str
    prompt_version: str
    skipped_posts: set[uuid.UUID] = field(default_factory=set)
    skipped: int = 0


@dataclass
class _Readings:
    by_comment: dict[uuid.UUID, CommentReading] = field(default_factory=dict)
    given_up: set[uuid.UUID] = field(default_factory=set)  # failed alone, or over the call cap
    calls: int = 0
    model: str = ""


# ---------------------------------------------------------------- queueing


def analysis_key(account_id: uuid.UUID) -> str:
    return f"cmt:{account_id}"


async def enqueue_analysis(account_id: uuid.UUID, workspace_id: uuid.UUID) -> bool:
    """False when a run for the account is already waiting (the job catalogue's cmt:{id})."""
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.comments import analyze_comments as task

    key = analysis_key(account_id)
    return await enqueue(
        task, key=key, lock=key, workspace_id=str(workspace_id), account_id=str(account_id)
    )


async def dispatch(pending: Sequence[tuple[uuid.UUID, uuid.UUID]]) -> int:
    """Queue analyze_comments for each (account, workspace) with pending comments; returns how
    many were queued (a waiting run makes it a no-op)."""
    queued = 0
    for account_id, workspace_id in pending:
        try:
            queued += await enqueue_analysis(account_id, workspace_id)
        except Exception:
            log.warning("comment_analysis_enqueue_failed", account_id=str(account_id))
    return queued


# ---------------------------------------------------------------- the prompt input


def _line(text: str | None, limit: int) -> str:
    """One line (a comment cannot start a fake new entry), at most ``limit`` characters."""
    return " ".join((text or "").split())[:limit]


def render_batch(
    numbered: Sequence[tuple[str, Comment]], captions: dict[uuid.UUID, str | None]
) -> str:
    """Each post's caption, then its comments as "number: text" (TR-AI-04: data, not system)."""
    lines: list[str] = []
    current: uuid.UUID | None = None
    for number, comment in numbered:
        if comment.media_item_id != current:
            current = comment.media_item_id
            if lines:
                lines.append("")
            lines.append(f"POST CAPTION: {_line(captions.get(current), CAPTION_CHARS) or '-'}")
            lines.append("COMMENTS:")
        lines.append(f"{number}: {_line(comment.text, COMMENT_CHARS)}")
    return "\n".join(lines)


def clean_topic(topic: str | None) -> str | None:
    """At most 3 lowercase words and 60 characters, punctuation dropped; None when empty."""
    kept = "".join(c if c.isalnum() or c.isspace() or c in "-'&" else " " for c in topic or "")
    text = " ".join(kept.casefold().split()[:TOPIC_WORDS])[:TOPIC_CHARS].strip()
    return text or None


def _clamp(value: float) -> float:
    return 0.0 if math.isnan(value) else max(-1.0, min(1.0, value))


def _is_spam(reading: CommentReading) -> bool:
    return reading.is_spam or reading.intent == "spam"


# ---------------------------------------------------------------- the job


async def analyze_comments(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    settings: Settings,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    now: datetime | None = None,
    max_batches: int = MAX_BATCHES_PER_RUN,
) -> AccountRun:
    """The analyze_comments job: batches until nothing is pending or ``max_batches`` ran. A
    retryable AIError on a batch's first call propagates (the job retries once; the credits were
    refunded)."""
    total = {"batches": 0, "analysed": 0, "skipped": 0, "hidden": 0, "calls": 0}
    run = BatchRun("nothing_pending")
    for _ in range(max_batches):
        run = await analyze_batch(
            sessionmaker,
            redis,
            settings,
            deps,
            workspace_id=workspace_id,
            account_id=account_id,
            now=now,
        )
        total["batches"] += 1
        total["analysed"] += run.analysed
        total["skipped"] += run.skipped
        total["hidden"] += run.hidden
        total["calls"] += run.calls
        if run.outcome != "analysed" or not run.more:
            break
    if total["analysed"] or total["skipped"]:
        log.info("comments_analysed", account_id=str(account_id), outcome=run.outcome, **total)
    return AccountRun(outcome=run.outcome, more=run.outcome == "analysed" and run.more, **total)


async def analyze_batch(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    settings: Settings,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    now: datetime | None = None,
) -> BatchRun:
    """One batch (steps 1 to 5 of the module docstring)."""
    now = now or datetime.now(UTC)
    with workspace_scope(workspace_id):
        prepared = await _prepare(sessionmaker, redis, account_id)
        if not isinstance(prepared, _Batch):
            return prepared
        if not prepared.comments:
            return await _finish_skipped(sessionmaker, redis, prepared)
        try:
            read = await _read_all(sessionmaker, settings, workspace_id, prepared, now)
        except QuotaExceeded:  # FR-AI-05: skipped, like DMs, so the progress completes
            log.info("comment_analysis_skipped", account_id=str(account_id), reason="quota")
            async with sessionmaker() as session:
                skipped = await repo.skip_pending(session, account_id)
                await _publish_posts(session, redis, skipped | prepared.skipped_posts)
            return BatchRun("quota_exhausted", skipped=prepared.skipped + len(prepared.comments))
        except AIError as error:
            if error.retryable:
                raise
            log.warning("comment_analysis_failed", account_id=str(account_id), code=error.code)
            return BatchRun("failed", skipped=prepared.skipped, more=True)
        hidden = await _auto_hide(deps, prepared, read.by_comment)
        return await _store(sessionmaker, redis, prepared, read, hidden, now)


async def _prepare(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, account_id: uuid.UUID
) -> _Batch | BatchRun:
    """Skip what must not be analysed, then take the next batch (steps 1 and 2)."""
    async with sessionmaker() as session:
        acct = await accounts.get(session, account_id)
        if acct is None or acct.status == AccountStatus.DISCONNECTED:
            return BatchRun("not_found")
        if not acct.ai_analysis_enabled:  # FR-PRV-02: no comment text reaches the provider
            await _publish_posts(session, redis, await repo.skip_pending(session, acct.id))
            return BatchRun("analysis_off")
        skipped_posts: set[uuid.UUID] = set()
        limit = entitlement(await current_plan(session), "comment_intelligence_posts")
        if limit is not None:  # §1.7 comment_intelligence_posts
            recent = await repo.recent_post_ids(session, acct.id, int(limit))
            skipped_posts |= await repo.skip_pending(session, acct.id, except_posts=recent)
        batch = await repo.pending_batch(session, acct.id, BATCH_SIZE)
        if not batch and not skipped_posts:
            await session.rollback()
            return BatchRun("nothing_pending")
        unreadable = {c.id for c, _ in batch if c.deleted_at is not None or not c.text.strip()}
        skipped_posts |= await repo.skip_pending(session, acct.id, comment_ids=unreadable)
        name, description = await business_profile(session)
        await session.commit()
    prompt = prompts.load("comment_analysis")
    return _Batch(
        acct=acct,
        comments=[c for c, _ in batch if c.id not in unreadable],
        captions={c.media_item_id: caption for c, caption in batch},
        system=prompt.render(business_name=name, business_description=description),
        prompt_version=prompt.version,
        skipped_posts=skipped_posts,
        skipped=len(unreadable),
    )


async def _publish_posts(
    session: AsyncSession, redis: Redis, media_item_ids: set[uuid.UUID]
) -> None:
    for item in await repo.recount(session, media_item_ids):
        views.queue_post(session, item)
    await commit_and_publish(session, redis)


async def _finish_skipped(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, batch: _Batch
) -> BatchRun:
    async with sessionmaker() as session:
        more = await repo.has_pending(session, batch.acct.id)
        await _publish_posts(session, redis, batch.skipped_posts)
    return BatchRun("analysed", skipped=batch.skipped, more=more)


# ---------------------------------------------------------------- the model calls


async def _read_all(
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    workspace_id: uuid.UUID,
    batch: _Batch,
    now: datetime,
) -> _Readings:
    """Readings by comment (step 3: an invalid or blocked answer is tried again in halves)."""
    read = _Readings(model=settings.ai_model_analysis)
    pending = [[(str(i), c) for i, c in enumerate(batch.comments, start=1)]]
    while pending:
        if read.calls >= MAX_CALLS_PER_BATCH:
            read.given_up |= {c.id for part in pending for _, c in part}
            break
        part = pending.pop(0)
        read.calls += 1
        try:
            answer, model = await _call(sessionmaker, settings, workspace_id, batch, part, now)
        except (AIError, QuotaExceeded) as error:
            split = isinstance(error, AIError) and error.code in SPLIT_CODES
            if not split:
                if not read.by_comment:
                    raise
                log.info("comment_analysis_partial", account_id=str(batch.acct.id))
                break  # store what was read; the rest stays pending
            log.info(
                "comment_analysis_split",
                account_id=str(batch.acct.id),
                size=len(part),
                code=getattr(error, "code", ""),
            )
            if len(part) == 1:
                read.given_up.add(part[0][1].id)
            else:
                half = len(part) // 2
                pending[:0] = [part[:half], part[half:]]
            continue
        read.model = model
        by_number = dict(part)
        for item in answer.items:
            comment = by_number.get(item.id)
            if comment is not None and comment.id not in read.by_comment:
                read.by_comment[comment.id] = item
    return read


async def _call(
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    workspace_id: uuid.UUID,
    batch: _Batch,
    part: list[tuple[str, Comment]],
    now: datetime,
) -> tuple[CommentReadings, str]:
    """One metered call for ``part``: 1 credit per 20 comments, rounded up (§1.7)."""
    async with metered(
        sessionmaker,
        workspace_id=workspace_id,
        feature=FEATURE,
        ref_type="social_account",
        ref_id=batch.acct.id,
        now=now,
        cost=math.ceil(len(part) / COMMENTS_PER_CREDIT),
    ) as meter:
        result = await get_provider().generate_json(
            task="comment_analysis",
            schema=readings_schema([number for number, _ in part]),
            system=batch.system,
            contents=[Turn("user", render_batch(part, batch.captions))],
            model=settings.ai_model_analysis,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            temperature=TEMPERATURE,
            timeout_s=TIMEOUT_S,
        )
        meter.record(result)
    return result.value, result.model


# ---------------------------------------------------------------- auto-hide (FR-CMT-05)


async def _auto_hide(
    deps: PlatformDeps, batch: _Batch, readings: dict[uuid.UUID, CommentReading]
) -> set[uuid.UUID]:
    """Hide the batch's spam on Instagram when the account's auto-hide is on; returns the comments
    hidden. A refusal is logged and the comment stays visible; a temporary error or a broken
    connection stops hiding for this batch."""
    acct = batch.acct
    spam = [
        c for c in batch.comments if c.id in readings and _is_spam(readings[c.id]) and not c.hidden
    ]
    if not acct.auto_hide_spam or not spam or acct.status == AccountStatus.NEEDS_RECONNECT:
        return set()
    try:
        adapter = adapter_for(acct, deps)
    except PlatformError as error:
        log.warning("comment_auto_hide_skipped", account_id=str(acct.id), error_code=error.code)
        return set()
    if Capability.COMMENTS not in adapter.capabilities_for(acct):
        return set()
    hidden: set[uuid.UUID] = set()
    for comment in spam:
        try:
            await adapter.hide_comment(acct, comment.platform_comment_id)
        except PlatformError as error:
            log.warning(
                "comment_auto_hide_failed",
                account_id=str(acct.id),
                comment_id=str(comment.id),
                error_code=error.code,
                platform_code=error.platform_code,
            )
            if error.retryable or error.code == "account_needs_reconnect":
                break
            continue
        hidden.add(comment.id)
    return hidden


# ---------------------------------------------------------------- storing (step 5)


def _values(
    comment: Comment, reading: CommentReading, *, model: str, version: str, now: datetime
) -> dict[str, Any]:
    return {
        "comment_id": comment.id,
        "media_item_id": comment.media_item_id,
        "sentiment": reading.sentiment,
        "sentiment_score": _clamp(reading.sentiment_score),
        "intent": reading.intent,
        "is_spam": _is_spam(reading),
        "topic": clean_topic(reading.topic),
        "model": model,
        "prompt_version": version,
        "created_at": now,
    }


async def _store(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    batch: _Batch,
    read: _Readings,
    hidden: set[uuid.UUID],
    now: datetime,
) -> BatchRun:
    from socialhood.services.comments.summaries import AFTER_ANALYSIS_DELAY_S, enqueue_summary

    async with sessionmaker() as session:
        locked = await comments_repo.lock_many(session, [c.id for c in batch.comments])
        still_pending = [c for c in locked if c.analysis_status == AnalysisStatus.PENDING]
        stored = await repo.insert_analyses(
            session,
            [
                _values(
                    c,
                    read.by_comment[c.id],
                    model=read.model,
                    version=batch.prompt_version,
                    now=now,
                )
                for c in still_pending
                if c.id in read.by_comment
            ],
        )
        await repo.mark_done(session, stored)
        given_up = {c.id for c in still_pending if c.id in read.given_up}
        await repo.skip_pending(session, batch.acct.id, comment_ids=given_up)
        await repo.mark_hidden(session, hidden & stored)
        changed = stored | given_up
        posts = {c.media_item_id for c in still_pending if c.id in changed} | batch.skipped_posts
        items = await repo.recount(session, posts)
        await views.queue_comments(session, changed)
        due: list[uuid.UUID] = []
        for item in items:
            views.queue_post(session, item)
            since = await repo.analysed_since(session, item.id, item.summary_updated_at)
            if since >= SUMMARY_AFTER:
                due.append(item.id)
        more = await repo.has_pending(session, batch.acct.id)
        await commit_and_publish(session, redis)
    queued = 0
    for media_item_id in due:
        queued += await _quietly(
            enqueue_summary(media_item_id, batch.acct.workspace_id, delay_s=AFTER_ANALYSIS_DELAY_S)
        )
    return BatchRun(
        "analysed",
        analysed=len(stored),
        skipped=batch.skipped + len(given_up),
        hidden=len(hidden & stored),
        calls=read.calls,
        more=more,
        summaries_queued=queued,
    )


async def _quietly(queued: Awaitable[bool]) -> int:
    """A summary that cannot be queued is logged; the hourly sweep queues it later."""
    try:
        return int(await queued)
    except Exception:
        log.warning("post_summary_enqueue_failed", exc_info=True)
        return 0
