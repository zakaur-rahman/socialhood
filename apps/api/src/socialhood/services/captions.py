"""AI caption and hashtags for the composer (T7.4; FR-PUB-02, UX-SCR-13 Write with AI and Suggest
hashtags, TR-AI-04, TR-AI-09).

Both write in the workspace's brand voice (ai_settings, FR-KB-04): the system prompt holds the
business's name, description, tone, emoji use and do and don't lists; the brief or caption is
data in the contents. Each call costs caption_generation credits (1, §1.7), reserved before the
model runs and refunded when it fails (``ai.metering.metered``): 402 quota_exceeded when the
credits are used up, 503 service_unavailable when the model can't answer. Nothing is stored.

The answer is made to pass the checklist (FR-PUB-10): a caption is cut to 2,200 characters and
keeps at most 30 hashtags and 20 mentions; suggested hashtags are normalised like hashtag groups
(no "#", lowercase, letters, digits and underscores), without those already in the caption or
excluded, at most ``count``.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai import prompts
from socialhood.ai.metering import QuotaExceeded, metered, quota
from socialhood.ai.provider import AIError, Turn
from socialhood.ai.registry import get_provider
from socialhood.errors import ApiError, FieldError
from socialhood.models.publishing import CAPTION_MAX_CHARS, MAX_HASHTAGS, MAX_MENTIONS
from socialhood.observability.logging import get_logger
from socialhood.schemas.publishing import (
    CaptionRequest,
    CaptionSuggestion,
    HashtagSuggestion,
    HashtagSuggestionRequest,
)
from socialhood.services.scheduled_posts import rules
from socialhood.services.suggestions.drafting import Brand, load_brand
from socialhood.settings import get_settings

log = get_logger(__name__)

FEATURE = "caption_generation"
CAPTION_TEMPERATURE = 0.8
CAPTION_MAX_TOKENS = 1500  # 2,200 characters of caption in JSON
HASHTAGS_TEMPERATURE = 0.4
HASHTAGS_MAX_TOKENS = 400
TIMEOUT_S = 15.0
AI_UNAVAILABLE = "The AI couldn't answer just now. Try again."
_SPACES = re.compile(r"[ \t]{2,}")


class CaptionOut(BaseModel):
    """The caption prompt's structured output."""

    caption: str


class HashtagsOut(BaseModel):
    """The hashtags prompt's structured output."""

    hashtags: list[str] = Field(default_factory=list)


def _listed(items: Sequence[str]) -> str:
    return "; ".join(items) if items else "nothing specific"


def brand_values(brand: Brand) -> dict[str, str]:
    """The brand voice as prompt placeholders (trusted settings only, TR-AI-04)."""
    return {
        "business_name": brand.business_name,
        "business_description": brand.business_description or "not given",
        "tone": brand.tone,
        "emoji_policy": brand.emoji_policy,
        "do_list": _listed(brand.do_list),
        "dont_list": _listed(brand.dont_list),
    }


# ---------------------------------------------------------------- keeping answers within limits


def _drop_after(text: str, pattern: re.Pattern[str], keep: int) -> str:
    """Remove every match of ``pattern`` after the first ``keep``."""
    seen = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal seen
        seen += 1
        return match.group(0) if seen <= keep else ""

    return pattern.sub(replace, text)


def _cut(text: str, limit: int) -> str:
    """At most ``limit`` characters, cut at a line or word boundary when there is one."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    for boundary in ("\n", " "):
        at = head.rfind(boundary)
        if at >= limit // 2:
            return head[:at].rstrip()
    return head.rstrip()


def within_limits(caption: str) -> str:
    """FR-PUB-01's caption limits: 30 hashtags, 20 mentions, 2,200 characters."""
    text = _drop_after(caption.strip(), rules.HASHTAG, MAX_HASHTAGS)
    text = _drop_after(text, rules.MENTION, MAX_MENTIONS)
    text = "\n".join(_SPACES.sub(" ", line).rstrip() for line in text.splitlines())
    return _cut(text.strip(), CAPTION_MAX_CHARS)


def clean_hashtags(raw: Sequence[str], *, leave_out: set[str], count: int) -> list[str]:
    tags: list[str] = []
    for item in raw:
        tag = rules.normalize_hashtag(item)
        if tag and tag not in leave_out and tag not in tags:
            tags.append(tag)
    return tags[:count]


# ---------------------------------------------------------------- the calls


async def _quota_error(session: AsyncSession) -> ApiError:
    """§4.7's copy for used-up AI credits."""
    credits = await quota(session)
    await session.commit()
    end = credits.period_end
    return ApiError(
        "quota_exceeded",
        f"You've used all {credits.limit or 0:,} AI credits for this month. "
        f"They reset on {end.day} {end:%B}.",
    )


async def generate_caption(
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    workspace_id: uuid.UUID,
    body: CaptionRequest,
) -> CaptionSuggestion:
    """Write a caption from ``brief``, or improve ``caption`` (422 on the one the mode needs)."""
    if body.mode == "write" and not body.brief:
        raise ApiError(
            "validation_error", errors=[FieldError("brief", "Say what the post is about.")]
        )
    if body.mode == "improve" and not body.caption:
        raise ApiError(
            "validation_error", errors=[FieldError("caption", "Write a caption to improve.")]
        )
    prompt = prompts.load("caption")
    system = prompt.render(
        **brand_values(await load_brand(session)),
        max_chars=f"{CAPTION_MAX_CHARS:,}",
        max_hashtags=str(MAX_HASHTAGS),
        max_mentions=str(MAX_MENTIONS),
    )
    await session.commit()  # no transaction stays open while the model runs
    content = (
        f"BRIEF (what the post is about):\n{body.brief}"
        if body.mode == "write"
        else f"CAPTION TO IMPROVE:\n{body.caption}"
    )
    settings = get_settings()
    try:
        async with metered(sessionmaker, workspace_id=workspace_id, feature=FEATURE) as meter:
            result = await get_provider().generate_json(
                task="caption",
                schema=CaptionOut,
                system=system,
                contents=[Turn("user", content)],
                model=settings.ai_model_reply,
                max_output_tokens=CAPTION_MAX_TOKENS,
                temperature=CAPTION_TEMPERATURE,
                timeout_s=TIMEOUT_S,
            )
            meter.record(result)
            caption = within_limits(result.value.caption)
            if not caption:
                raise AIError("invalid_output", "empty caption")
    except QuotaExceeded as error:
        raise await _quota_error(session) from error
    except AIError as error:
        log.warning("caption_generation_failed", code=error.code, task="caption")
        raise ApiError("service_unavailable", AI_UNAVAILABLE) from error
    return CaptionSuggestion(caption=caption)


async def suggest_hashtags(
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    workspace_id: uuid.UUID,
    body: HashtagSuggestionRequest,
) -> HashtagSuggestion:
    """Up to ``count`` hashtags for the caption, none already in it or in ``exclude``."""
    leave_out = set(rules.hashtags_in(body.caption))
    leave_out |= {tag for tag in map(rules.normalize_hashtag, body.exclude) if tag}
    prompt = prompts.load("hashtags")
    system = prompt.render(**brand_values(await load_brand(session)), count=str(body.count))
    await session.commit()
    contents = [
        Turn("user", f"CAPTION:\n{body.caption}"),
        Turn("user", "LEAVE OUT: " + (", ".join(sorted(leave_out)) or "nothing")),
    ]
    settings = get_settings()
    try:
        async with metered(sessionmaker, workspace_id=workspace_id, feature=FEATURE) as meter:
            result = await get_provider().generate_json(
                task="hashtags",
                schema=HashtagsOut,
                system=system,
                contents=contents,
                model=settings.ai_model_reply,
                max_output_tokens=HASHTAGS_MAX_TOKENS,
                temperature=HASHTAGS_TEMPERATURE,
                timeout_s=TIMEOUT_S,
            )
            meter.record(result)
    except QuotaExceeded as error:
        raise await _quota_error(session) from error
    except AIError as error:
        log.warning("caption_generation_failed", code=error.code, task="hashtags")
        raise ApiError("service_unavailable", AI_UNAVAILABLE) from error
    return HashtagSuggestion(
        hashtags=clean_hashtags(result.value.hashtags, leave_out=leave_out, count=body.count)
    )
