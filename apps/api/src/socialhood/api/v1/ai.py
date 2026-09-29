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
from socialhood.realtime.events import commit_and_publish
from socialhood.schemas.ai import (
    AiDecision,
    AiDecisionFeedback,
    AiSettings,
    AiSettingsUpdate,
    AnalysisCorrection,
)
from socialhood.schemas.inbox import MessageAnalysis, Suggestion
from socialhood.services import analysis, conversations, summaries

router = APIRouter(prefix="/v1/w/{wid}", tags=["ai"])


def pending(task: str) -> dict[str, str]:
    """Stub marker: the tenancy suite skips x-pending routes."""
    return {"x-pending": task}


@router.get("/ai-settings", operation_id="get_ai_settings", openapi_extra=pending("T5.5"))
async def get_ai_settings(ctx: Admin, session: Session) -> AiSettings:
    raise NotImplementedError("T5.5")


@router.put("/ai-settings", operation_id="update_ai_settings", openapi_extra=pending("T5.5"))
async def update_ai_settings(body: AiSettingsUpdate, ctx: Admin, session: Session) -> AiSettings:
    raise NotImplementedError("T5.5")


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
    openapi_extra=pending("T5.4"),
)
async def regenerate_suggestion(
    conversation_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Response:
    """F-08 Regenerate: up to 5 per message; suggestion.created carries the result."""
    raise NotImplementedError("T5.4")


@router.post(
    "/suggestions/{suggestion_id}/dismiss",
    operation_id="dismiss_suggestion",
    openapi_extra=pending("T5.4"),
)
async def dismiss_suggestion(
    suggestion_id: uuid.UUID, ctx: AnyMember, session: Session
) -> Suggestion:
    raise NotImplementedError("T5.4")


@router.post(
    "/conversations/{conversation_id}/summary",
    status_code=202,
    operation_id="refresh_summary",
)
async def refresh_summary(conversation_id: uuid.UUID, ctx: AnyMember, session: Session) -> Response:
    """FR-AI-03 on request; conversation.updated carries the new summary (its ``summary`` key).
    402 quota_exceeded without credits; 409 when AI analysis is off for the account."""
    conv = await conversations.get_or_404(session, conversation_id)
    await summaries.request_summary(session, conv)
    return Response(status_code=202)


@router.get(
    "/messages/{message_id}/ai-decision",
    operation_id="get_ai_decision",
    openapi_extra=pending("T5.6"),
)
async def get_ai_decision(message_id: uuid.UUID, ctx: AnyMember, session: Session) -> AiDecision:
    """The latest decision for an inbound message, or the one that sent this AI message."""
    raise NotImplementedError("T5.6")


@router.post(
    "/ai-decisions/{decision_id}/feedback",
    operation_id="give_ai_decision_feedback",
    openapi_extra=pending("T5.6"),
)
async def give_ai_decision_feedback(
    decision_id: uuid.UUID, body: AiDecisionFeedback, ctx: AnyMember, session: Session
) -> AiDecision:
    raise NotImplementedError("T5.6")
