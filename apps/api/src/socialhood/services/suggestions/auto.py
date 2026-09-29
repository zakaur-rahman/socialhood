"""decide_auto_reply (T5.6; TR-AI-07, FR-SUG-04, FR-SUG-06, F-09).

For a pending inbox suggestion in Auto mode, in one transaction holding the suggestion's and the
conversation's row locks: load the facts, evaluate the policy (ai/policy), write one
``ai_decisions`` row with all 13 checks, then act on the outcome:

- auto_sent: reserve 2 credits (``auto_reply``, with its usage event), queue an outbound message
  with source ``ai_auto`` and the suggestion's id through services/sending (so the suggestion
  becomes ``sent``), and link the decision to it. If the credits ran out meanwhile the decision
  becomes skipped · quota_exhausted; if the send pipeline refuses the message (the window
  closed, the account needs reconnecting…), nothing is charged and the decision is escalated
  (window_closed for the window, otherwise with no reason).
- escalated: the conversation needs a human with the reason, the suggestion stays pending for
  them, and the owners and admins get a notification.
- skipped: nothing visible.

A suggestion that is no longer pending (sent, dismissed, superseded) is not evaluated.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai import metering, output_filter, policy
from socialhood.ai.metering import QuotaExceeded
from socialhood.billing.plans import CREDIT_COSTS, current_plan, entitlement
from socialhood.errors import ApiError
from socialhood.models.ai import (
    AiDecision,
    EscalationReason,
    MessageAnalysis,
    ReplySuggestion,
    SuggestionStatus,
)
from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import Contact, Conversation, Message
from socialhood.observability.logging import get_logger
from socialhood.platforms.deps import PlatformDeps
from socialhood.realtime import events
from socialhood.repositories import inbox, social_accounts, usage
from socialhood.repositories import ingest as ingest_rows
from socialhood.repositories import suggestions as repo
from socialhood.services.notifications import notify_admins
from socialhood.services.reply_window import reply_window
from socialhood.services.suggestions import drafting
from socialhood.settings import get_settings

log = get_logger(__name__)

FEATURE = "auto_reply"
REASONS = frozenset(r.value for r in EscalationReason)  # conversations.needs_human_reason
RATE_WINDOW = timedelta(hours=1)
# A stable client_id per suggestion: deciding twice never queues two messages.
CLIENT_ID_NAMESPACE = uuid.UUID("0b9f4c1e-8a57-4f0e-9c2d-3e6a7b5d1f24")

# "AI didn't reply: …" (F-09): the notification and the banner's reason.
REASON_COPY: dict[str | None, str] = {
    "refund": "the customer is asking for a refund",
    "legal": "the customer mentions legal action",
    "complaint": "the customer has a complaint",
    "negative_sentiment": "the customer sounds unhappy",
    "abuse": "the message looks abusive",
    "account_or_payment": "it's about an account or payment problem",
    "human_requested": "the customer asked for a person",
    "low_confidence": "it wasn't sure enough of its answer",
    "out_of_knowledge": "the answer isn't in your knowledge",
    "window_closed": "the reply window has closed",
    "policy_keyword": "the message contains one of your escalation phrases",
    "output_blocked": "its draft mentioned something that isn't in your knowledge",
    None: "it couldn't send its reply",
}


def client_id_for(suggestion_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(CLIENT_ID_NAMESPACE, f"auto-reply:{suggestion_id}")


async def decide(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    suggestion_id: uuid.UUID,
    now: datetime | None = None,
) -> AiDecision | None:
    """The decide_auto_reply job, in the workspace's scope; returns the decision recorded."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        found = await repo.get(session, suggestion_id)
        if found is None:
            return None
        # Every writer locks the conversation, then its suggestion (suggest_reply, sends).
        conv = await ingest_rows.lock_conversation(session, found.conversation_id)
        row = await repo.lock(session, suggestion_id)
        if row is None or row.status != SuggestionStatus.PENDING or row.automation_run_id:
            return None
        msg = await inbox.get_message(session, row.message_id)
        acct = await social_accounts.get(session, conv.social_account_id) if conv else None
        if conv is None or msg is None or acct is None:
            return None
        facts = await policy_input(session, row, conv, msg, acct, now=now)
        decision = policy.evaluate(facts)
        outcome, reason, checks = decision.outcome, decision.reason, decision.checks_json
        sent_id: uuid.UUID | None = None
        if outcome == "auto_sent":
            result, sent_id = await _send(session, row, conv, deps, now=now)
            if result == "no_credits":
                outcome, reason = "skipped", "quota_exhausted"
                checks = _changed(checks, 2, passed=False, value="credits")
            elif result is not None:
                outcome = "escalated"
                reason = "window_closed" if result == "reply_window_closed" else None
                if result == "reply_window_closed":
                    checks = _changed(checks, 5, passed=False, value="closed")
        record = AiDecision(
            conversation_id=conv.id,
            message_id=msg.id,
            suggestion_id=row.id,
            sent_message_id=sent_id,
            outcome=outcome,
            reason=reason,
            checks=checks,
        )
        session.add(record)
        if outcome == "escalated":
            await escalate(session, conv, reason, message_id=msg.id, now=now)
        await session.flush()
        await session.refresh(record)
        await events.commit_and_publish(session, redis)
    log.info(
        "auto_reply_decided",
        suggestion_id=str(suggestion_id),
        outcome=record.outcome,
        reason=record.reason,
    )
    return record


async def policy_input(
    session: AsyncSession,
    row: ReplySuggestion,
    conv: Conversation,
    msg: Message,
    acct: SocialAccount,
    *,
    now: datetime,
) -> policy.PolicyInput:
    """Everything TR-AI-07's checks look at."""
    settings = get_settings()
    analysis = await session.scalar(
        select(MessageAnalysis)
        .where(MessageAnalysis.message_id == msg.id)
        .order_by(MessageAnalysis.created_at.desc())
        .limit(1)
    )
    brand = await drafting.load_brand(session)
    plan = await current_plan(session)
    credits = await metering.quota(session, now=now)
    reply = row.reply_text or ""
    allowed = await repo.chunk_texts(session, row.used_chunk_ids or []) + brand.texts()
    found = output_filter.candidates(reply)
    if found:
        allowed += await drafting.knowledge_mentioning(session, [v for _, v in found])
    window = reply_window(conv.platform, conv.last_inbound_at, human_agent=False, now=now)
    return policy.PolicyInput(
        effective_mode=conv.ai_mode_override or acct.ai_mode,
        auto_allowed="auto" in entitlement(plan, "ai_modes"),
        credits_available=credits.allows(CREDIT_COSTS[FEATURE]),
        paused_until=conv.ai_paused_until,
        now=now,
        automation_handled=msg.automation_handled,
        window_state=window.state,
        analysis=(
            policy.AnalysisFacts(
                intent=analysis.corrected_intent or analysis.intent,
                sentiment_score=analysis.sentiment_score,
                needs_human=analysis.needs_human,
                needs_human_reason=analysis.needs_human_reason,
            )
            if analysis is not None
            else None
        ),
        message_text=msg.text or "",
        escalation_phrases=brand.escalation_phrases,
        can_answer=row.can_answer,
        confidence=row.model_confidence,
        used_sources=len(row.used_chunk_ids or []),
        top_similarity=row.top_similarity,
        already_replied=await repo.replied_to(session, msg.id),
        ai_replies_last_hour=await repo.ai_replies_since(session, conv.id, now - RATE_WINDOW),
        reply_text=row.reply_text,
        allowed_texts=allowed,
        min_confidence=settings.auto_min_confidence,
        min_similarity=settings.ai_retrieval_min_sim,
    )


def _changed(checks: list[dict[str, Any]], n: int, **changes: Any) -> list[dict[str, Any]]:
    return [{**c, **changes} if c.get("n") == n else c for c in checks]


async def _send(
    session: AsyncSession,
    row: ReplySuggestion,
    conv: Conversation,
    deps: PlatformDeps,
    *,
    now: datetime,
) -> tuple[str | None, uuid.UUID | None]:
    """Charge the auto reply and queue it. (None, message id) once queued; ("no_credits",
    None) or (the send pipeline's error code, None) when nothing was queued or charged."""
    from socialhood.services import sending  # sending → suggestions.service → … → this module

    step = await session.begin_nested()
    try:
        await metering.reserve(session, cost=CREDIT_COSTS[FEATURE], now=now)
    except QuotaExceeded:
        await step.rollback()
        return "no_credits", None
    try:
        sent = await sending.queue_outbound(
            session,
            conv,
            source="ai_auto",
            client_id=client_id_for(row.id),
            text=row.reply_text,
            suggestion_id=row.id,
            deps=deps,
            now=now,
        )
    except ApiError as error:
        await step.rollback()
        log.info("auto_reply_refused", suggestion_id=str(row.id), error_code=error.code)
        return error.code, None
    await step.commit()
    usage.record_event(
        session,
        feature=FEATURE,
        model=row.model or "unknown",
        credits=CREDIT_COSTS[FEATURE],
        outcome="ok",
        ref_type="message",
        ref_id=sent.id,
    )
    return None, sent.id


async def escalate(
    session: AsyncSession,
    conv: Conversation,
    reason: str | None,
    *,
    message_id: uuid.UUID | None,
    now: datetime,
    dedupe_key: str | None = None,
) -> None:
    """F-09: "Needs you" with the reason, conversation.updated, and a notification for the
    owners and admins (once per message)."""
    conv.needs_human = True
    conv.needs_human_reason = reason if reason in REASONS else None
    await session.flush()
    contact = await inbox.get_contact(session, conv.contact_id)
    await events.queue_conversation(session, conv, now=now, contact=contact)
    await notify_admins(
        session,
        type="ai_escalated",
        severity="warning",
        title=f"{_name(contact)} needs you",
        body=f"AI didn't reply: {REASON_COPY.get(reason, REASON_COPY[None])}.",
        link=f"/inbox/{conv.id}",
        dedupe_key=dedupe_key or (f"ai_escalated:{message_id}" if message_id else None),
    )


def _name(contact: Contact | None) -> str:
    if contact is None:
        return "A customer"
    if contact.display_name:
        return contact.display_name
    if contact.username:
        return f"@{contact.username}"
    return "A customer"
