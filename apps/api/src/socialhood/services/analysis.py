"""Message analysis (T5.2; TR-AI-05, FR-AI-01, FR-AI-02, FR-AI-04, FR-AI-05).

Ingest queues ``analyze_conversation`` for every new customer message with the queueing lock
``analyze:{conversation_id}``, deferred 4 s: a second message during the delay finds the job
waiting and queues nothing, so a burst is analysed once, as context for its newest message
(FR-AI-01). The same key is the job's run lock, so one conversation's analyses never overlap. The
job:

1. skips when AI analysis is off for the account (FR-PRV-02: no message text reaches the
   provider), when the conversation has no customer message in its last 12, or when that message
   already has an analysis;
2. loads the last 12 messages, marks the newest customer message TARGET and reserves 1 credit; with
   the credits used up it stops before any call and messaging carries on (FR-AI-05);
3. calls the provider with AI_MODEL_ANALYSIS, temperature 0, 400 tokens, 8 s and the versioned
   prompt (the business's name and description; the conversation goes in the contents as data,
   TR-AI-04);
4. clamps the scores, stores ``message_analyses`` and updates the conversation's cached signals:
   lead_score, priority, last_intent and last_sentiment follow the latest analysis; needs_human is
   only ever raised here (with its reason), because a later calm message must not clear an
   escalation nobody has answered (a business reply clears it, F-09). It also refreshes
   ``messages_since_summary``. A lead score crossing 70 notifies every member once per
   conversation (``new_lead``: in-app, and push under the "new lead" switch; FR-NOT-03). Then it
   publishes analysis.created and conversation.updated;
5. queues ``suggest_reply`` when TARGET needs a reply and the effective AI mode is Suggest or Auto,
   a summary refresh once 8 messages arrived since the last summary (FR-AI-03), and itself again
   when a newer customer message arrived during the call.

A correction (FR-AI-04) keeps the model's answer and stores the member's intent or sentiment next
to it; the API shows the corrected values with ``corrected: true``, the conversation's chips follow
a correction of its latest analysis, and tests/ai_eval/export_corrections.py exports them into the
evaluation set (TR-AI-10).
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai import prompts
from socialhood.ai.metering import Meter, QuotaExceeded, metered
from socialhood.ai.provider import AIError, Turn
from socialhood.ai.registry import get_provider
from socialhood.db.tenancy import require_workspace, workspace_scope
from socialhood.errors import ApiError, FieldError
from socialhood.models.ai import AiSettings, MessageAnalysis
from socialhood.models.connections import AiMode, SocialAccount
from socialhood.models.identity import Workspace
from socialhood.models.inbox import Contact, Conversation, Direction, Message, MessageSource
from socialhood.models.notifications import NotificationType
from socialhood.observability.logging import get_logger
from socialhood.realtime import events
from socialhood.repositories import analyses, inbox, social_accounts
from socialhood.repositories import ingest as ingest_rows
from socialhood.schemas.ai import AnalysisCorrection, SentimentName
from socialhood.schemas.inbox import EscalationReason, IntentName
from socialhood.schemas.inbox import MessageAnalysis as MessageAnalysisOut
from socialhood.services.inbox_views import ATTACHMENT_PREVIEW, human_agent_allowed
from socialhood.services.notifications import notify_members
from socialhood.settings import Settings

log = get_logger(__name__)

ANALYZE_DELAY_S = 4.0
CONTEXT_MESSAGES = 12
MAX_OUTPUT_TOKENS = 400
TIMEOUT_S = 8.0
MESSAGE_CHARS = 1_000
MAX_TOPICS = 3
TOPIC_CHARS = 60
LANGUAGE_CHARS = 35
SUMMARY_AFTER = 8  # FR-AI-03
SUGGEST_MODES = frozenset({AiMode.SUGGEST, AiMode.AUTO})
NO_DESCRIPTION = "no description given yet"
NEW_LEAD_SCORE = 70  # FR-NOT-03: "a new lead (lead score reaches 70)"
LEAD_WANTS = {  # the new-lead notification's body, by intent
    "pricing": "asked about prices",
    "product_inquiry": "asked about a product",
    "purchase": "wants to buy",
    "order_status": "asked about an order",
    "shipping": "asked about shipping",
    "collaboration": "wants to collaborate",
}

PriorityName = Literal["critical", "high", "medium", "low"]


class AnalysisOut(BaseModel):
    """What the model returns (TR-AI-05's MessageAnalysisOut); scores are clamped after parse."""

    intent: IntentName
    sentiment: SentimentName
    sentiment_score: float
    priority: PriorityName
    lead_score: int
    language: str
    topics: list[str]
    needs_reply: bool
    needs_human: bool
    needs_human_reason: EscalationReason | None


Outcome = Literal[
    "analysed",
    "not_found",
    "analysis_off",
    "no_customer_message",
    "already_analysed",
    "quota_exhausted",
    "failed",
]


@dataclass(frozen=True)
class AnalysisRun:
    outcome: Outcome
    analysis_id: uuid.UUID | None = None
    suggestion_queued: bool = False
    summary_queued: bool = False
    requeued: bool = False


@dataclass(frozen=True)
class _Context:
    conversation_id: uuid.UUID
    messages: list[Message]
    target: Message
    business_name: str
    business_description: str


# ---------------------------------------------------------------- queueing


def analyze_key(conversation_id: uuid.UUID) -> str:
    return f"analyze:{conversation_id}"


async def enqueue_analysis(
    workspace_id: uuid.UUID, conversation_id: uuid.UUID, *, delay_s: float = ANALYZE_DELAY_S
) -> bool:
    """TR-AI-05: False when a job for the conversation is already waiting (the burst joins it)."""
    from socialhood.jobs.enqueue import enqueue
    from socialhood.jobs.tasks.analysis import analyze_conversation as task

    key = analyze_key(conversation_id)
    return await enqueue(
        task,
        key=key,
        lock=key,
        delay_s=delay_s,
        workspace_id=str(workspace_id),
        conversation_id=str(conversation_id),
    )


async def enqueue_suggestion(
    workspace_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID
) -> bool:
    """``suggest_reply`` (T5.4, TR-AI-06) by name; its first draft for the message is n = 0 of
    the job catalogue's ``suggest:{message_id}:{n}``."""
    from socialhood.jobs.app import INTERACTIVE
    from socialhood.jobs.enqueue import enqueue_named

    return await enqueue_named(
        "suggest_reply",
        lane=INTERACTIVE,
        key=f"suggest:{message_id}:0",
        workspace_id=str(workspace_id),
        conversation_id=str(conversation_id),
        message_id=str(message_id),
    )


# ---------------------------------------------------------------- prompt input


async def business_profile(session: AsyncSession) -> tuple[str, str]:
    """The current workspace's name and description for prompts: ai_settings, else the
    workspace name (§5.5)."""
    row = (
        await session.execute(select(AiSettings.business_name, AiSettings.business_description))
    ).first()
    name = row.business_name if row is not None else None
    description = row.business_description if row is not None else None
    if not name:
        name = await session.scalar(
            select(Workspace.name).where(Workspace.id == require_workspace())
        )
    return (name or "the business").strip(), (description or NO_DESCRIPTION).strip()


def render_message(msg: Message) -> str:
    """One message as the model reads it: one line (a customer cannot start a fake new turn),
    at most 1,000 characters, attachments named."""
    if msg.deleted_at is not None:
        return "[message unsent]"
    text = " ".join((msg.text or "").split())[:MESSAGE_CHARS]
    if msg.kind != "text":
        label = ATTACHMENT_PREVIEW.get(msg.kind, "Message")
        return f"[{label}] {text}".strip()
    return text or "[empty message]"


def transcript(messages: Sequence[Message], target_id: uuid.UUID | None = None) -> str:
    """The conversation, oldest first, with TARGET marked (TR-AI-05)."""
    lines = ["CONVERSATION (oldest first):"]
    for msg in messages:
        who = "customer" if msg.direction == Direction.INBOUND else "business"
        mark = " [TARGET]" if msg.id == target_id else ""
        lines.append(f"{who}{mark}: {render_message(msg)}")
    return "\n".join(lines)


def _is_customer(msg: Message) -> bool:
    return (
        msg.direction == Direction.INBOUND
        and msg.source == MessageSource.CUSTOMER
        and msg.deleted_at is None
    )


async def _context(session: AsyncSession, conversation_id: uuid.UUID) -> _Context | Outcome:
    conv = await inbox.get_conversation(session, conversation_id)
    if conv is None:
        return "not_found"
    acct = await social_accounts.get(session, conv.social_account_id)
    if acct is None or not acct.ai_analysis_enabled:
        return "analysis_off"
    messages = await analyses.recent_messages(session, conv.id, CONTEXT_MESSAGES)
    target = next((m for m in reversed(messages) if _is_customer(m)), None)
    if target is None:
        return "no_customer_message"
    if await analyses.exists_for_message(session, target.id):
        return "already_analysed"
    name, description = await business_profile(session)
    return _Context(conv.id, messages, target, name, description)


# ---------------------------------------------------------------- the job


def _clamp(value: float, low: float, high: float) -> float:
    return low if math.isnan(value) else max(low, min(high, value))


def _topics(topics: list[str]) -> list[str]:
    cleaned: list[str] = []
    for topic in topics:
        text = " ".join(topic.casefold().split())[:TOPIC_CHARS]
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned[:MAX_TOPICS]


def _values(
    out: AnalysisOut, *, ctx: _Context, model: str, version: str, meter: Meter
) -> dict[str, Any]:
    return {
        "message_id": ctx.target.id,
        "conversation_id": ctx.conversation_id,
        "intent": out.intent,
        "sentiment": out.sentiment,
        "sentiment_score": _clamp(out.sentiment_score, -1.0, 1.0),
        "priority": out.priority,
        "lead_score": int(_clamp(out.lead_score, 0, 100)),
        "language": out.language.strip()[:LANGUAGE_CHARS] or "und",
        "topics": _topics(out.topics),
        "needs_reply": out.needs_reply,
        "needs_human": out.needs_human,
        "needs_human_reason": out.needs_human_reason if out.needs_human else None,
        "model": model,
        "prompt_version": version,
        "input_tokens": meter.input_tokens,
        "output_tokens": meter.output_tokens,
        "latency_ms": meter.latency_ms,
    }


def _apply_signals(conv: Conversation, row: MessageAnalysis) -> None:
    conv.lead_score = row.lead_score
    conv.priority = row.priority
    conv.last_intent = row.intent
    conv.last_sentiment = row.sentiment
    if row.needs_human:
        conv.needs_human = True
        conv.needs_human_reason = row.needs_human_reason or conv.needs_human_reason


def _contact_name(contact: Contact | None) -> str:
    if contact is not None and contact.display_name:
        return contact.display_name
    if contact is not None and contact.username:
        return f"@{contact.username}"
    return "A customer"


async def _announce_lead(
    session: AsyncSession, conv: Conversation, row: MessageAnalysis, previous_score: int | None
) -> None:
    """FR-NOT-03's new lead: the conversation's lead score reached NEW_LEAD_SCORE. Once per
    conversation (the dedupe key), when the score crosses it, so a conversation that was a lead
    already never announces itself again. Every member is told (in-app, and push under the "new
    lead" switch); the caller commits."""
    if row.lead_score < NEW_LEAD_SCORE or (
        previous_score is not None and previous_score >= NEW_LEAD_SCORE
    ):
        return
    name = _contact_name(await inbox.get_contact(session, conv.contact_id))
    wants = LEAD_WANTS.get(row.corrected_intent or row.intent, "is interested")
    await notify_members(
        session,
        type=NotificationType.NEW_LEAD,
        severity="info",
        title=f"New lead: {name}",
        body=f"{name} {wants}. Lead score {row.lead_score}.",
        link=f"/inbox/{conv.id}",
        dedupe_key=f"new_lead:{conv.id}",
    )


async def analyze_conversation(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    settings: Settings,
    *,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    now: datetime | None = None,
) -> AnalysisRun:
    """The analyze_conversation job (TR-AI-05). A retryable AIError propagates (the job retries
    once; the credit was refunded); any other AI failure is logged and ends the job."""
    now = now or datetime.now(UTC)
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            ctx = await _context(session, conversation_id)
    if not isinstance(ctx, _Context):
        log.info("analysis_skipped", conversation_id=str(conversation_id), reason=ctx)
        return AnalysisRun(ctx)

    prompt = prompts.load("analysis")
    system = prompt.render(
        business_name=ctx.business_name, business_description=ctx.business_description
    )
    try:
        async with metered(
            sessionmaker,
            workspace_id=workspace_id,
            feature="message_analysis",
            ref_type="message",
            ref_id=ctx.target.id,
            now=now,
        ) as meter:
            result = await get_provider().generate_json(
                task="analysis",
                schema=AnalysisOut,
                system=system,
                contents=[Turn("user", transcript(ctx.messages, ctx.target.id))],
                model=settings.ai_model_analysis,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.0,
                timeout_s=TIMEOUT_S,
            )
            meter.record(result)
    except QuotaExceeded:
        log.info("analysis_skipped", conversation_id=str(conversation_id), reason="quota")
        return AnalysisRun("quota_exhausted")
    except AIError as error:
        if error.retryable:
            raise
        log.warning("analysis_failed", conversation_id=str(conversation_id), error_code=error.code)
        return AnalysisRun("failed")

    values = _values(result.value, ctx=ctx, model=result.model, version=prompt.version, meter=meter)
    return await _store(sessionmaker, redis, settings, workspace_id, ctx, values, now)


async def _store(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    settings: Settings,
    workspace_id: uuid.UUID,
    ctx: _Context,
    values: dict[str, Any],
    now: datetime,
) -> AnalysisRun:
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            row = await analyses.insert_analysis(session, values)
            conv = await ingest_rows.lock_conversation(session, ctx.conversation_id)
            acct: SocialAccount | None = None
            if conv is not None:
                acct = await social_accounts.get(session, conv.social_account_id)
            if row is None or conv is None or acct is None:
                await session.rollback()
                return AnalysisRun("already_analysed" if row is None else "not_found")
            previous_score = conv.lead_score
            _apply_signals(conv, row)
            await _announce_lead(session, conv, row, previous_score)
            conv.messages_since_summary = await analyses.messages_since(
                session, conv.id, conv.summary_updated_at
            )
            await session.flush()
            events.queue(
                session,
                workspace_id,
                "analysis.created",
                {"conversation_id": str(conv.id), "analysis": _json(analysis_out(row))},
            )
            human_agent = human_agent_allowed(
                acct, ig_human_agent_enabled=settings.ig_human_agent_enabled
            )
            await events.queue_conversation(session, conv, now=now, human_agent=human_agent)
            mode = conv.ai_mode_override or acct.ai_mode
            summary_due = conv.messages_since_summary >= SUMMARY_AFTER
            newest = await analyses.newest_customer_message_id(session, conv.id)
            await events.commit_and_publish(session, redis)
    log.info(
        "analysis_stored",
        conversation_id=str(ctx.conversation_id),
        intent=row.intent,
        lead_score=row.lead_score,
    )
    from socialhood.services.summaries import enqueue_summary

    suggest = summary = requeue = False
    if row.needs_reply and mode in SUGGEST_MODES:
        suggest = await _quietly(
            enqueue_suggestion(workspace_id, ctx.conversation_id, row.message_id)
        )
    if summary_due:
        summary = await _quietly(enqueue_summary(workspace_id, ctx.conversation_id))
    if newest is not None and newest != row.message_id:  # it arrived during the call
        requeue = await _quietly(enqueue_analysis(workspace_id, ctx.conversation_id))
    return AnalysisRun(
        "analysed",
        analysis_id=row.id,
        suggestion_queued=suggest,
        summary_queued=summary,
        requeued=requeue,
    )


async def _quietly(queued: Awaitable[bool]) -> bool:
    """A follow-up that cannot be queued is logged; it never fails the stored analysis."""
    try:
        return await queued
    except Exception:
        log.warning("analysis_followup_enqueue_failed", exc_info=True)
        return False


def _json(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


# ---------------------------------------------------------------- the API (§5.10, FR-AI-04)


def analysis_out(row: MessageAnalysis) -> MessageAnalysisOut:
    """The API shape: a member's correction replaces the model's intent or sentiment."""
    return MessageAnalysisOut.model_validate(
        {
            "id": row.id,
            "message_id": row.message_id,
            "intent": row.corrected_intent or row.intent,
            "sentiment": row.corrected_sentiment or row.sentiment,
            "sentiment_score": row.sentiment_score,
            "priority": row.priority,
            "lead_score": row.lead_score,
            "language": row.language,
            "topics": list(row.topics or []),
            "needs_reply": row.needs_reply,
            "needs_human": row.needs_human,
            "needs_human_reason": row.needs_human_reason,
            "corrected": row.corrected_at is not None,
            "created_at": row.created_at,
        }
    )


async def latest_analysis(
    session: AsyncSession, conversation_id: uuid.UUID
) -> MessageAnalysisOut | None:
    row = await analyses.latest(session, conversation_id)
    return analysis_out(row) if row is not None else None


async def correct_analysis(
    session: AsyncSession,
    analysis_id: uuid.UUID,
    body: AnalysisCorrection,
    *,
    user_id: uuid.UUID,
    ig_human_agent_enabled: bool,
    now: datetime,
) -> MessageAnalysisOut:
    """FR-AI-04: store the corrected intent and/or sentiment. When it is the conversation's
    latest analysis, the conversation's cached chips follow and conversation.updated is queued;
    the caller commits with commit_and_publish."""
    if body.intent is None and body.sentiment is None:
        raise ApiError(
            "validation_error",
            errors=[FieldError("intent", "Choose the right intent, sentiment or both.")],
        )
    if await analyses.get(session, analysis_id) is None:
        raise ApiError("not_found")
    values: dict[str, Any] = {"corrected_by_user_id": user_id, "corrected_at": now}
    if body.intent is not None:
        values["corrected_intent"] = body.intent
    if body.sentiment is not None:
        values["corrected_sentiment"] = body.sentiment
    row = await analyses.correct(session, analysis_id, values)
    if row is None:  # pragma: no cover - deleted between the two statements
        raise ApiError("not_found")
    latest = await analyses.latest(session, row.conversation_id)
    if latest is not None and latest.id == row.id:
        conv = await ingest_rows.lock_conversation(session, row.conversation_id)
        if conv is not None:
            intent = row.corrected_intent or row.intent
            sentiment = row.corrected_sentiment or row.sentiment
            if (conv.last_intent, conv.last_sentiment) != (intent, sentiment):
                conv.last_intent, conv.last_sentiment = intent, sentiment
                await session.flush()
                acct = await social_accounts.get(session, conv.social_account_id)
                human_agent = acct is not None and human_agent_allowed(
                    acct, ig_human_agent_enabled=ig_human_agent_enabled
                )
                await events.queue_conversation(session, conv, now=now, human_agent=human_agent)
    return analysis_out(row)
