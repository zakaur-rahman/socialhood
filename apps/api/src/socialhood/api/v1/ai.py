"""AI routes (§2.15): AI settings (T5.5), analysis corrections (T5.2), suggestions (T5.4),
summaries (T5.7) and auto-reply decisions (T5.6).

The signatures below are the P5 contract; each task implements its bodies and removes its
``openapi_extra`` marker so the tenancy suite covers the route.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.billing.entitlements import credits_gate
from socialhood.errors import ApiError
from socialhood.realtime.events import commit_and_publish
from socialhood.repositories import inbox
from socialhood.repositories import suggestions as suggestions_repo
from socialhood.schemas.ai import (
    AiDecision,
    AiDecisionFeedback,
    AiSettings,
    AiSettingsUpdate,
    AnalysisCorrection,
)
from socialhood.schemas.inbox import MessageAnalysis, Suggestion
from socialhood.services import ai_settings, analysis, conversations, summaries
from socialhood.services.suggestions import service as suggestions

router = APIRouter(prefix="/v1/w/{wid}", tags=["ai"])


def pending(task: str) -> dict[str, str]:
    """Stub marker: the tenancy suite skips x-pending routes."""
    return {"x-pending": task}


@router.get("/ai-settings", operation_id="get_ai_settings")
async def get_ai_settings(ctx: Admin, session: Session) -> AiSettings:
    """FR-KB-04, FR-SUG-05, FR-SUG-06: brand voice, takeover period and escalation phrases."""
    row = await ai_settings.load(session)
    await session.commit()
    return ai_settings.out(row)


@router.put("/ai-settings", operation_id="update_ai_settings")
async def update_ai_settings(body: AiSettingsUpdate, ctx: Admin, session: Session) -> AiSettings:
    """Replace the whole settings object."""
    row = await ai_settings.replace(session, body)
    await session.commit()
    return ai_settings.out(row)


@router.patch("/message-analyses/{analysis_id}", operation_id="correct_message_analysis")
async def correct_message_analysis(
    request: Request,
    analysis_id: uuid.UUID,
    body: AnalysisCorrection,
    ctx: AnyMember,
    session: Session,
) -> MessageAnalysis:
    """FR-AI-04: change a message's intent or sentiment. The answer shows the corrected values
    with ``corrected: true``; the conversation's chips follow a correction of its latest
    analysis (conversation.updated)."""
    corrected = await analysis.correct_analysis(
        session,
        analysis_id,
        body,
        user_id=ctx.user.id,
        ig_human_agent_enabled=bool(request.app.state.settings.ig_human_agent_enabled),
        now=datetime.now(UTC),
    )
    await commit_and_publish(session, request.app.state.redis)
    return corrected


@router.post(
    "/conversations/{conversation_id}/suggestions",
    status_code=202,
    operation_id="regenerate_suggestion",
)
async def regenerate_suggestion(
    conversation_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Response:
    """F-08 Regenerate: up to 5 per message; suggestion.created carries the result. 409 when
    the conversation's AI mode is off, there is no customer message, or the 5 are used; 402
    quota_exceeded when AI credits are used up."""
    conv = await inbox.get_conversation(session, conversation_id)
    if conv is None:
        raise ApiError("not_found")
    async with credits_gate(session):  # §2.15 "agent · credits": the 402 names the plan's limit
        await suggestions.regenerate(session, conv)
    await session.commit()
    return Response(status_code=202)


@router.post("/suggestions/{suggestion_id}/dismiss", operation_id="dismiss_suggestion")
async def dismiss_suggestion(
    request: Request, suggestion_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Suggestion:
    """F-08 Dismiss: a pending suggestion becomes dismissed (suggestion.updated); any other is
    returned as it is."""
    row = await suggestions_repo.get(session, suggestion_id)
    if row is None:
        raise ApiError("not_found")
    row = await suggestions.dismiss(session, row)
    out = await suggestions.suggestion_out(session, row)
    await commit_and_publish(session, request.app.state.redis)
    return out


@router.post(
    "/conversations/{conversation_id}/summary",
    status_code=202,
    operation_id="refresh_summary",
)
async def refresh_summary(conversation_id: uuid.UUID, ctx: AnyMember, session: Session) -> Response:
    """FR-AI-03 on request; conversation.updated carries the new summary (its ``summary`` key).
    402 quota_exceeded without credits; 409 when AI analysis is off for the account."""
    conv = await conversations.get_or_404(session, conversation_id)
    async with credits_gate(session):  # §2.15 "agent · credits"
        await summaries.request_summary(session, conv)
    return Response(status_code=202)


@router.get("/messages/{message_id}/ai-decision", operation_id="get_ai_decision")
async def get_ai_decision(message_id: uuid.UUID, ctx: AnyMember, session: Session) -> AiDecision:
    """The latest decision for an inbound message, or the one that sent this AI message
    (FR-SUG-04: the "Sent by AI" popover and the escalation banner). 404 when there is none."""
    msg = await inbox.get_message(session, message_id)
    if msg is None:
        raise ApiError("not_found")
    decision = await suggestions_repo.decision_for_message(session, msg)
    if decision is None:
        raise ApiError("not_found", "The AI made no decision about this message.")
    return AiDecision.model_validate(decision, from_attributes=True)


@router.post("/ai-decisions/{decision_id}/feedback", operation_id="give_ai_decision_feedback")
async def give_ai_decision_feedback(
    decision_id: uuid.UUID, body: AiDecisionFeedback, ctx: AnyMember, session: Session
) -> AiDecision:
    """Mark an auto reply "should not have sent" ("bad"), or clear the mark (null). Only a
    decision that sent a reply takes feedback (409 otherwise)."""
    decision = await suggestions_repo.get_decision(session, decision_id)
    if decision is None:
        raise ApiError("not_found")
    if decision.outcome != "auto_sent":
        raise ApiError("conflict", "Only replies the AI sent can be marked.")
    updated = await suggestions_repo.set_feedback(session, decision.id, body.feedback)
    if updated is None:  # pragma: no cover - deleted in between
        raise ApiError("not_found")
    await session.commit()
    return AiDecision.model_validate(updated, from_attributes=True)
