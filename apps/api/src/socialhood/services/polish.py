"""AI Polish (C-063): the composer rewrites a member's own draft before it is sent.

    POST …/conversations/{id}/polish  {"text": "...", "tone": "friendly" | "professional"}

- The draft is fixed for grammar and clarity in its own language and script (English, Hindi or
  Hinglish), keeping its meaning and roughly its length (prompt ``polish.v1``). The brand voice's
  tone applies unless the request names one.
- The conversation's last 6 messages go along as context, as data (TR-AI-04). With AI analysis off
  for the account nothing of the customer's is sent (FR-PRV-02): the draft is polished alone.
- 1 credit (reply_polish, §1.7), reserved before the call and refunded when it fails (TR-AI-09):
  quota_exceeded leaves the route's credits gate as the §4.7 402; 503 when the model can't answer.
- Nothing may be added: an answer with a number (a price, date or quantity), link, email address
  or phone number the draft doesn't have, or one far longer than the draft, is refused (503,
  refunded) instead of shown.
- Nothing is stored or sent; the composer puts the text in the box, with Undo.
"""

from __future__ import annotations

import re

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai import output_filter, prompts
from socialhood.ai.metering import QuotaExceeded, metered
from socialhood.ai.provider import AIError, Turn
from socialhood.ai.registry import get_provider
from socialhood.errors import ApiError
from socialhood.models.inbox import Conversation
from socialhood.observability.logging import get_logger
from socialhood.repositories import analyses, social_accounts
from socialhood.schemas.ai import PolishRequest, PolishResult
from socialhood.services.analysis import transcript
from socialhood.services.suggestions.drafting import load_brand
from socialhood.settings import get_settings

log = get_logger(__name__)

FEATURE = "reply_polish"
CONTEXT_MESSAGES = 6
MAX_TEXT = 4096  # a message's text (SendMessage)
MAX_OUTPUT_TOKENS = 2000
TEMPERATURE = 0.3
TIMEOUT_S = 12.0
PLATFORM = {"instagram": "Instagram", "whatsapp": "WhatsApp"}
NO_CREDITS = "Your AI credits are used up until they reset."
AI_UNAVAILABLE = "The AI couldn't polish this just now. Try again."
CHANGED_DETAILS = "The AI changed details in your reply, so it wasn't used. Try again or edit it."

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# Quotation marks the model may wrap the reply in: opening -> closing (curly ones as escapes).
_QUOTES = {'"': '"', "'": "'", "\N{LEFT DOUBLE QUOTATION MARK}": "\N{RIGHT DOUBLE QUOTATION MARK}"}
_QUOTES["\N{LEFT SINGLE QUOTATION MARK}"] = "\N{RIGHT SINGLE QUOTATION MARK}"


class PolishOut(BaseModel):
    """polish.v1's structured output."""

    text: str


def numbers(text: str) -> set[str]:
    """The numbers in ``text`` without their separators ("1,299.00" -> "129900")."""
    return {re.sub(r"[.,]", "", match) for match in _NUMBER.findall(text)}


def longest_allowed(draft: str) -> int:
    """Roughly the draft's length: twice it, or 200 characters more for a short one."""
    return min(MAX_TEXT, max(2 * len(draft), len(draft) + 200))


def clean(polished: str, draft: str) -> str:
    """Trimmed, trailing spaces gone, and quotation marks the model wrapped it in removed."""
    text = "\n".join(line.rstrip() for line in polished.strip().splitlines()).strip()
    close = _QUOTES.get(text[:1])
    if close and text.endswith(close) and len(text) > 1 and draft[:1] != text[:1]:
        text = text[1:-1].strip()
    return text


def added_details(polished: str, draft: str) -> str | None:
    """What the polished text states that the draft doesn't (a number, link, email address or
    phone number), or None."""
    extra = numbers(polished) - numbers(draft)
    if extra:
        return f"number {sorted(extra)[0]}"
    finding = output_filter.check(polished, [draft], max_chars=None)
    return finding.kind if finding else None


async def polish_reply(
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    conv: Conversation,
    body: PolishRequest,
) -> PolishResult:
    brand = await load_brand(session)
    acct = await social_accounts.get(session, conv.social_account_id)
    context = None
    if acct is not None and acct.ai_analysis_enabled:
        messages = await analyses.recent_messages(session, conv.id, CONTEXT_MESSAGES)
        context = transcript(messages) if messages else None
    await session.commit()  # no transaction stays open while the model runs

    system = prompts.load("polish").render(
        business_name=brand.business_name,
        business_description=brand.business_description or "not given",
        platform=PLATFORM.get(conv.platform, conv.platform),
        tone=body.tone or brand.tone,
    )
    contents = [Turn("user", context)] if context else []
    contents.append(Turn("user", f"DRAFT:\n{body.text}"))
    settings = get_settings()
    try:
        async with metered(
            sessionmaker,
            workspace_id=conv.workspace_id,
            feature=FEATURE,
            ref_type="conversation",
            ref_id=conv.id,
        ) as meter:
            result = await get_provider().generate_json(
                task="polish",
                schema=PolishOut,
                system=system,
                contents=contents,
                model=settings.ai_model_reply,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                temperature=TEMPERATURE,
                timeout_s=TIMEOUT_S,
            )
            meter.record(result)
            text = clean(result.value.text, body.text)
            if not text or len(text) > longest_allowed(body.text):
                raise AIError("invalid_output", "empty or too long")
            added = added_details(text, body.text)
            if added is not None:
                log.warning("polish_refused", conversation_id=str(conv.id), added=added)
                raise ApiError("service_unavailable", CHANGED_DETAILS)
    except QuotaExceeded as error:
        raise ApiError("quota_exceeded", NO_CREDITS) from error
    except AIError as error:
        log.warning("polish_failed", conversation_id=str(conv.id), error_code=error.code)
        raise ApiError("service_unavailable", AI_UNAVAILABLE) from error
    return PolishResult(text=text)
