"""AI routes (§2.15): AI settings (T5.5), analysis corrections (T5.2), suggestions (T5.4),
summaries (T5.7) and auto-reply decisions (T5.6).

The signatures below are the P5 contract; each task implements its bodies and removes its
``openapi_extra`` marker so the tenancy suite covers the route.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.schemas.ai import (
    AiDecision,
    AiDecisionFeedback,
    AiSettings,
    AiSettingsUpdate,
    AnalysisCorrection,
)
from socialhood.schemas.inbox import MessageAnalysis, Suggestion

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


@router.patch(
    "/message-analyses/{analysis_id}",
    operation_id="correct_message_analysis",
    openapi_extra=pending("T5.2"),
)
async def correct_message_analysis(
    analysis_id: uuid.UUID, body: AnalysisCorrection, ctx: AnyMember, session: Session
) -> MessageAnalysis:
    """FR-AI-04: change a message's intent or sentiment."""
    raise NotImplementedError("T5.2")


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
    openapi_extra=pending("T5.7"),
)
async def refresh_summary(conversation_id: uuid.UUID, ctx: AnyMember, session: Session) -> Response:
    """FR-AI-03 on request; conversation.updated carries the new summary."""
    raise NotImplementedError("T5.7")


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
