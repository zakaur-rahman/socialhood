"""Conversation summaries (T5.7; FR-AI-03): up to three sentences and a suggested next step,
refreshed after 8 new messages or on request.

- Triggers: the analysis job refreshes ``messages_since_summary`` (customer and business messages
  since ``summary_updated_at``) and queues ``summarize_conversation`` once it reaches 8; a member
  can ask for one with POST …/conversations/{id}/summary (202). The job's queueing lock
  ``convsum:{conversation_id}`` keeps one waiting per conversation; it runs on the bulk lane in a
  per-workspace bulk slot (TR-JOB-06).
- The job reads the last 50 messages (the earlier summary, when there is one, comes first as
  context), reserves 1 credit and calls the provider with AI_MODEL_REPLY and the versioned prompt
  ``summary.v1``; the conversation is data in the contents (TR-AI-04). With AI analysis off for the
  account nothing is sent (FR-PRV-02); with the credits used up it stops before any call
  (FR-AI-05).
- It stores summary, summary_next_step and summary_updated_at, resets the counter and publishes
  conversation.updated, whose payload also carries ``summary`` (the list item has no summary).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

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
from socialhood.models.inbox import Conversation
from socialhood.observability.logging import get_logger
from socialhood.realtime import events
from socialhood.repositories import analyses, inbox, social_accounts
from socialhood.repositories import ingest as ingest_rows
from socialhood.schemas.inbox import ConversationSummary
from socialhood.services.analysis import business_profile, transcript
from socialhood.services.inbox_views import human_agent_allowed, list_item
from socialhood.settings import Settings

log = get_logger(__name__)

FEATURE = "conversation_summary"
SUMMARY_MESSAGES = 50
MAX_OUTPUT_TOKENS = 400
TEMPERATURE = 0.2
TIMEOUT_S = 12.0
SUMMARY_CHARS = 600
NEXT_STEP_CHARS = 200
ANALYSIS_OFF = "AI analysis is off for this account, so its conversations are not summarised."
NO_CREDITS = "Your AI credits are used up until they reset."


class SummaryOut(BaseModel):
    summary: str
    next_step: str | None


Outcome = Literal[
    "summarised", "not_found", "analysis_off", "no_messages", "quota_exhausted", "failed"
]


@dataclass(frozen=True)
class SummaryRun:
    outcome: Outcome


def summary_key(conversation_id: uuid.UUID) -> str:
    return f"convsum:{conversation_id}"


async def enqueue_summary(workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> bool:
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.analysis import summarize_conversation as task

    key = summary_key(conversation_id)
    return await enqueue(
        task,
        key=key,
        lock=key,
        workspace_id=str(workspace_id),
        conversation_id=str(conversation_id),
    )


async def request_summary(session: AsyncSession, conv: Conversation) -> None:
    """POST …/summary (FR-AI-03 on request): 409 with analysis off (FR-PRV-02), 402 without
    credits (the route's credits gate); otherwise the job is queued."""
    acct = await social_accounts.get(session, conv.social_account_id)
    if acct is None or not acct.ai_analysis_enabled:
        raise ApiError("conflict", ANALYSIS_OFF)
    if not (await quota(session)).allows(CREDIT_COSTS[FEATURE]):
        raise ApiError("quota_exceeded", NO_CREDITS)
    await enqueue_summary(conv.workspace_id, conv.id)


def _clean(text: str | None, limit: int) -> str | None:
    cleaned = " ".join((text or "").split())[:limit]
    return cleaned or None


async def summarize_conversation(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    settings: Settings,
    *,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    now: datetime | None = None,
) -> SummaryRun:
    """The summarize_conversation job. A retryable AIError propagates (one retry)."""
    now = now or datetime.now(UTC)
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            conv = await inbox.get_conversation(session, conversation_id)
            if conv is None:
                return SummaryRun("not_found")
            acct = await social_accounts.get(session, conv.social_account_id)
            if acct is None or not acct.ai_analysis_enabled:
                return SummaryRun("analysis_off")
            messages = await analyses.recent_messages(session, conv.id, SUMMARY_MESSAGES)
            if not messages:
                return SummaryRun("no_messages")
            name, description = await business_profile(session)
            earlier = conv.summary

    text = transcript(messages)
    if earlier:
        text = f"EARLIER SUMMARY: {earlier}\n\n{text}"
    prompt = prompts.load("summary")
    try:
        async with metered(
            sessionmaker,
            workspace_id=workspace_id,
            feature=FEATURE,
            ref_type="conversation",
            ref_id=conversation_id,
            now=now,
        ) as meter:
            result = await get_provider().generate_json(
                task="summary",
                schema=SummaryOut,
                system=prompt.render(business_name=name, business_description=description),
                contents=[Turn("user", text)],
                model=settings.ai_model_reply,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                temperature=TEMPERATURE,
                timeout_s=TIMEOUT_S,
            )
            meter.record(result)
    except QuotaExceeded:
        log.info("summary_skipped", conversation_id=str(conversation_id), reason="quota")
        return SummaryRun("quota_exhausted")
    except AIError as error:
        if error.retryable:
            raise
        log.warning("summary_failed", conversation_id=str(conversation_id), error_code=error.code)
        return SummaryRun("failed")

    summary = _clean(result.value.summary, SUMMARY_CHARS)
    if summary is None:
        log.warning("summary_failed", conversation_id=str(conversation_id), error_code="empty")
        return SummaryRun("failed")
    next_step = _clean(result.value.next_step, NEXT_STEP_CHARS)
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            conv = await ingest_rows.lock_conversation(session, conversation_id)
            if conv is None:
                return SummaryRun("not_found")
            conv.summary = summary
            conv.summary_next_step = next_step
            conv.summary_updated_at = now
            # Messages that arrived while the model wrote count towards the next refresh.
            conv.messages_since_summary = await analyses.messages_since(session, conv.id, now)
            await session.flush()
            await _queue_updated(session, conv, settings, now)
            await events.commit_and_publish(session, redis)
    return SummaryRun("summarised")


async def _queue_updated(
    session: AsyncSession, conv: Conversation, settings: Settings, now: datetime
) -> None:
    contact = await inbox.get_contact(session, conv.contact_id)
    acct = await social_accounts.get(session, conv.social_account_id)
    if contact is None or acct is None or conv.summary is None or conv.summary_updated_at is None:
        return
    human_agent = human_agent_allowed(acct, ig_human_agent_enabled=settings.ig_human_agent_enabled)
    item = list_item(conv, contact, now=now, human_agent=human_agent)
    summary = ConversationSummary(
        text=conv.summary, next_step=conv.summary_next_step, updated_at=conv.summary_updated_at
    )
    events.queue(
        session,
        conv.workspace_id,
        "conversation.updated",
        {
            "conversation": item.model_dump(mode="json"),
            "summary": summary.model_dump(mode="json"),
        },
    )
