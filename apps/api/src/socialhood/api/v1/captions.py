"""AI caption and hashtags for the composer (§2.15 …/ai/caption, …/ai/hashtags; FR-PUB-02,
UX-SCR-13 Write with AI and Suggest hashtags). Owners and admins.

Both write in the workspace's brand voice (ai_settings) and cost AI credits (caption_generation,
§1.7), reserved before the model call and refunded if it fails (TR-AI-09): 402 quota_exceeded when
the credits are used up; 503 service_unavailable when the model can't answer. Nothing is stored:
the composer puts the result in the caption, where the member edits it.

The routes below are the P7 contract; T7.4 implements their bodies and removes each
``openapi_extra`` marker so the tenancy suite covers the route.
"""

from __future__ import annotations

from fastapi import APIRouter

from socialhood.api.v1.ai import pending
from socialhood.auth.deps import Admin, Session
from socialhood.schemas.publishing import (
    CaptionRequest,
    CaptionSuggestion,
    HashtagSuggestion,
    HashtagSuggestionRequest,
)

router = APIRouter(prefix="/v1/w/{wid}", tags=["publishing"])


@router.post("/ai/caption", operation_id="generate_caption", openapi_extra=pending("T7.4"))
async def generate_caption(body: CaptionRequest, ctx: Admin, session: Session) -> CaptionSuggestion:
    """Write a caption from a brief, or improve the caption given (422 on ``brief`` or
    ``caption`` when the one the mode needs is missing). At most 2,200 characters, 30 hashtags
    and 20 mentions, so it passes the checklist."""
    raise NotImplementedError("T7.4")


@router.post("/ai/hashtags", operation_id="suggest_hashtags", openapi_extra=pending("T7.4"))
async def suggest_hashtags(
    body: HashtagSuggestionRequest, ctx: Admin, session: Session
) -> HashtagSuggestion:
    """Up to ``count`` (at most 20) hashtags for the caption, none already in it or in
    ``exclude``."""
    raise NotImplementedError("T7.4")
