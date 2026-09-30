"""AI caption and hashtags for the composer (§2.15 …/ai/caption, …/ai/hashtags; FR-PUB-02,
UX-SCR-13 Write with AI and Suggest hashtags). Owners and admins.

Both write in the workspace's brand voice (ai_settings) and cost AI credits (caption_generation,
§1.7), reserved before the model call and refunded if it fails (TR-AI-09): 402 quota_exceeded when
the credits are used up; 503 service_unavailable when the model can't answer. Nothing is stored:
the composer puts the result in the caption, where the member edits it. The rules are in
services/captions.py (T7.4).
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from socialhood.api import ratelimit
from socialhood.auth.deps import Admin, Session
from socialhood.schemas.publishing import (
    CaptionRequest,
    CaptionSuggestion,
    HashtagSuggestion,
    HashtagSuggestionRequest,
)
from socialhood.services import captions

router = APIRouter(prefix="/v1/w/{wid}", tags=["publishing"])


@router.post("/ai/caption", operation_id="generate_caption", dependencies=[ratelimit.AI])
async def generate_caption(
    request: Request, body: CaptionRequest, ctx: Admin, session: Session
) -> CaptionSuggestion:
    """Write a caption from a brief, or improve the caption given (422 on ``brief`` or
    ``caption`` when the one the mode needs is missing). At most 2,200 characters, 30 hashtags
    and 20 mentions, so it passes the checklist."""
    return await captions.generate_caption(
        session, request.app.state.sessionmaker, workspace_id=ctx.workspace_id, body=body
    )


@router.post("/ai/hashtags", operation_id="suggest_hashtags", dependencies=[ratelimit.AI])
async def suggest_hashtags(
    request: Request, body: HashtagSuggestionRequest, ctx: Admin, session: Session
) -> HashtagSuggestion:
    """Up to ``count`` (at most 20) hashtags for the caption, none already in it or in
    ``exclude``."""
    return await captions.suggest_hashtags(
        session, request.app.state.sessionmaker, workspace_id=ctx.workspace_id, body=body
    )
