"""Drafting one reply (TR-AI-06; FR-SUG-02, FR-SUG-03, FR-AUT-01, TR-PL-10, TR-AI-04).

Shared by inbox suggestions (feature ``reply_suggestion``) and automations' AI replies
(``automation_ai_reply``, with the business's instructions in ``{automation_instructions}``):

1. Inside ``ai.metering.metered`` (credits reserved first; refunded if anything below fails):
   retrieve knowledge for the query (the target message plus the customer's other messages of
   the previous 10 minutes, at most 1,000 characters), number the chunks k1…k6 and call
   ``generate_json`` with the suggest prompt, AI_MODEL_REPLY, temperature 0.4, 600 tokens and a
   12 s timeout. The system prompt holds the business's brand voice only; the conversation and
   the KNOWLEDGE block are contents (data).
2. Afterwards: ``used_source_ids`` keeps only ids that were given (k1…); the confidence is
   clamped to 0…1; a reply is trimmed at a sentence boundary to the platform's text limit less
   ``reserve`` (the disclosure line); and the output filter (ai/output_filter) runs on it. A
   reply that mentions a link, email address or phone number found neither in knowledge, brand
   settings nor ``quotable`` texts becomes "can't answer" with that finding as the missing
   information, so an invented fact is never offered (FR-SUG-03).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai import output_filter, prompts
from socialhood.ai.metering import metered
from socialhood.ai.output_filter import Finding
from socialhood.ai.provider import AIResult, Turn
from socialhood.ai.registry import get_provider
from socialhood.db.tenancy import require_workspace
from socialhood.models.ai import AiSettings, KnowledgeChunk, KnowledgeSource, MessageAnalysis
from socialhood.models.identity import Workspace
from socialhood.models.inbox import Direction, Message, MessageKind
from socialhood.observability.logging import get_logger
from socialhood.services.inbox_views import preview_text
from socialhood.services.sending import TEXT_LIMITS, platform_name, text_size
from socialhood.services.suggestions.knowledge_port import RetrievedChunk, retrieve_knowledge
from socialhood.settings import get_settings

log = get_logger(__name__)

TASK = "suggest"
REPLY_TEMPERATURE = 0.4
REPLY_MAX_TOKENS = 600
REPLY_TIMEOUT_S = 12.0
CONTEXT_MESSAGES = 12
QUERY_WINDOW = timedelta(minutes=10)
QUERY_CHARS = 1000
MENTION_ROWS = 20
INSTRUCTIONS_PREFIX = "Instructions from the business for this reply: "
NOT_ANSWERED = "an answer to this message"
_SENTENCE_END = re.compile(r"[.!?।…][\"')\]]*(?=\s|$)")


class SuggestionOut(BaseModel):
    """TR-AI-06: the model's structured output."""

    can_answer: bool
    reply: str | None  # customer-facing text when can_answer
    missing_info: str | None  # for the business owner when not can_answer
    missing_topic: str | None  # 2-4 lowercase words for grouping, e.g. "shipping to uae"
    confidence: float  # 0..1, the model's own estimate
    used_source_ids: list[str]  # e.g. ["k1", "k3"]


# ---------------------------------------------------------------- brand voice (FR-KB-04)


@dataclass(frozen=True)
class Brand:
    business_name: str
    business_description: str | None = None
    tone: str = "friendly"
    emoji_policy: str = "light"
    do_list: tuple[str, ...] = ()
    dont_list: tuple[str, ...] = ()
    escalation_phrases: tuple[str, ...] = ()
    sign_off: str | None = None
    takeover_minutes: int = 120

    def texts(self) -> list[str]:
        """Brand settings as texts a reply may quote (TR-AI-07 check 13)."""
        parts = [self.business_name, self.business_description or "", self.sign_off or ""]
        return [p for p in (*parts, *self.do_list, *self.dont_list) if p]


async def load_brand(session: AsyncSession) -> Brand:
    """The workspace's AI settings; the business name falls back to the workspace's name."""
    workspace_name = await session.scalar(
        select(Workspace.name).where(Workspace.id == require_workspace())
    )
    row = await session.scalar(select(AiSettings))
    if row is None:
        return Brand(business_name=workspace_name or "the business")
    return Brand(
        business_name=row.business_name or workspace_name or "the business",
        business_description=row.business_description,
        tone=row.tone,
        emoji_policy=row.emoji_policy,
        do_list=tuple(row.do_list or ()),
        dont_list=tuple(row.dont_list or ()),
        escalation_phrases=tuple(row.escalation_phrases or ()),
        sign_off=row.sign_off,
        takeover_minutes=row.takeover_minutes,
    )


def _listed(items: Sequence[str]) -> str:
    return "; ".join(items) if items else "nothing specific"


def system_prompt(
    brand: Brand,
    *,
    platform: str,
    language: str | None,
    instructions: str | None = None,
) -> tuple[str, str]:
    """(system prompt, prompt version): suggest.v1 filled with trusted settings only."""
    prompt = prompts.load(TASK)
    text = prompt.render(
        business_name=brand.business_name,
        platform=platform_name(platform),
        business_description=brand.business_description or "not given",
        tone=brand.tone,
        emoji_policy=brand.emoji_policy,
        do_list=_listed(brand.do_list),
        dont_list=_listed(brand.dont_list),
        sign_off=brand.sign_off or "none",
        language=language or "the language of their message",
        automation_instructions=(
            f"{INSTRUCTIONS_PREFIX}{instructions.strip()}"
            if instructions and instructions.strip()
            else ""
        ),
    )
    return text, prompt.version


# ---------------------------------------------------------------- the conversation (contents)


@dataclass(frozen=True)
class Line:
    speaker: Literal["customer", "business"]
    text: str
    target: bool = False


def line_for(msg: Message, *, target: bool = False) -> Line | None:
    """A message as the model reads it; system notes and unsent messages are left out."""
    if msg.direction == Direction.SYSTEM or msg.kind == MessageKind.SYSTEM or msg.deleted_at:
        return None
    body = msg.text.strip() if msg.text and msg.text.strip() else None
    if body is None:
        body = f"[{preview_text(msg.kind, None)}]"
    speaker: Literal["customer", "business"] = (
        "customer" if msg.direction == Direction.INBOUND else "business"
    )
    return Line(speaker, body, target)


async def conversation_lines(session: AsyncSession, target: Message) -> list[Line]:
    """The last 12 messages up to and including ``target``, oldest first."""
    rows = (
        await session.scalars(
            select(Message)
            .where(
                Message.conversation_id == target.conversation_id,
                Message.direction != Direction.SYSTEM,
                Message.occurred_at <= target.occurred_at,
            )
            .order_by(Message.occurred_at.desc(), Message.id.desc())
            .limit(CONTEXT_MESSAGES + 1)
        )
    ).all()
    lines: list[Line] = []
    for msg in reversed(rows):
        if msg.id != target.id and msg.occurred_at == target.occurred_at and msg.id > target.id:
            continue  # the same instant, after the target
        line = line_for(msg, target=msg.id == target.id)
        if line is not None:
            lines.append(line)
    return lines[-CONTEXT_MESSAGES:]


async def retrieval_query(session: AsyncSession, target: Message) -> str:
    """The target plus the customer's other messages of the previous 10 minutes, oldest first,
    at most 1,000 characters (the target is kept whole when it can be)."""
    earlier = (
        await session.scalars(
            select(Message.text)
            .where(
                Message.conversation_id == target.conversation_id,
                Message.direction == Direction.INBOUND,
                Message.id != target.id,
                Message.occurred_at >= target.occurred_at - QUERY_WINDOW,
                Message.occurred_at <= target.occurred_at,
                Message.text.is_not(None),
            )
            .order_by(Message.occurred_at)
        )
    ).all()
    parts = [t.strip() for t in (*earlier, target.text or "") if t and t.strip()]
    query = "\n".join(parts)
    return query[-QUERY_CHARS:] if len(query) > QUERY_CHARS else query


async def message_language(session: AsyncSession, message_id: uuid.UUID) -> str | None:
    """The analysed language of the message (TR-AI-05), when there is an analysis."""
    return await session.scalar(
        select(MessageAnalysis.language)
        .where(MessageAnalysis.message_id == message_id)
        .order_by(MessageAnalysis.created_at.desc())
        .limit(1)
    )


def render_contents(lines: Sequence[Line], chunks: Sequence[RetrievedChunk]) -> str:
    """The conversation, then the KNOWLEDGE block ("[k1] (source title) text")."""
    out = ["CONVERSATION (oldest first; the message to answer is marked TARGET)"]
    for line in lines:
        who = "Customer" if line.speaker == "customer" else "Business"
        out.append(f"{who}{' [TARGET]' if line.target else ''}: {line.text}")
    out.append("")
    out.append("KNOWLEDGE")
    if not chunks:
        out.append("(none)")
    for i, chunk in enumerate(chunks, 1):
        out.append(f"[k{i}] ({chunk.source_title}) {chunk.content}")
    return "\n".join(out)


# ---------------------------------------------------------------- trimming (TR-PL-10)


def fits(text: str, platform: str, budget: int) -> bool:
    return text_size(platform, text) <= budget


def trim_reply(text: str, platform: str, *, reserve: int = 0) -> str:
    """At most the platform's limit less ``reserve``, cut after the last whole sentence that
    fits (else at the last space, else hard)."""
    limit = TEXT_LIMITS.get(platform)
    if limit is None:
        return text
    budget = max(limit.max - reserve, 0)
    if fits(text, platform, budget):
        return text
    best: str | None = None
    for match in _SENTENCE_END.finditer(text):
        cut = text[: match.end()].rstrip()
        if not fits(cut, platform, budget):
            break
        best = cut
    if best:
        return best
    prefix = ""
    for char in text:
        if not fits(prefix + char, platform, budget):
            break
        prefix += char
    space = prefix.rfind(" ")
    return (prefix[:space] if space > 0 else prefix).rstrip()


# ---------------------------------------------------------------- the call


@dataclass(frozen=True)
class DraftRequest:
    workspace_id: uuid.UUID
    feature: Literal["reply_suggestion", "automation_ai_reply"]
    platform: str
    lines: Sequence[Line]
    query: str
    ref_type: str | None = None
    ref_id: uuid.UUID | None = None
    language: str | None = None
    instructions: str | None = None  # an automation's AI instructions (FR-AUT-01)
    reserve: int = 0  # size kept free for the disclosure line (TR-PL-10)
    quotable: Sequence[str] = ()  # texts besides knowledge and brand a reply may quote


@dataclass(frozen=True)
class Draft:
    can_answer: bool
    reply: str | None
    missing_info: str | None
    missing_topic: str | None
    confidence: float
    used_chunk_ids: list[uuid.UUID]
    top_similarity: float | None
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    chunks: list[RetrievedChunk] = field(default_factory=list)
    blocked: Finding | None = None  # the output filter's finding (the reply was withheld)


async def draft(
    sessionmaker: async_sessionmaker[AsyncSession],
    request: DraftRequest,
    *,
    brand: Brand | None = None,
) -> Draft:
    """One metered draft (see the module docstring). Raises ``QuotaExceeded`` before any call
    when credits are used up, and ``AIError`` when the call fails (credits refunded)."""
    settings = get_settings()
    if brand is None:
        async with sessionmaker() as session:
            brand = await load_brand(session)
    system, version = system_prompt(
        brand,
        platform=request.platform,
        language=request.language,
        instructions=request.instructions,
    )
    async with metered(
        sessionmaker,
        workspace_id=request.workspace_id,
        feature=request.feature,
        ref_type=request.ref_type,
        ref_id=request.ref_id,
    ) as meter:
        async with sessionmaker() as session:
            chunks = await retrieve_knowledge(session, request.query)
        result: AIResult[SuggestionOut] = await get_provider().generate_json(
            task=TASK,
            schema=SuggestionOut,
            system=system,
            contents=[Turn("user", render_contents(request.lines, chunks))],
            model=settings.ai_model_reply,
            max_output_tokens=REPLY_MAX_TOKENS,
            temperature=REPLY_TEMPERATURE,
            timeout_s=REPLY_TIMEOUT_S,
        )
        meter.record(result)
    return await _finish(sessionmaker, request, brand, result, chunks, version)


async def _finish(
    sessionmaker: async_sessionmaker[AsyncSession],
    request: DraftRequest,
    brand: Brand,
    result: AIResult[SuggestionOut],
    chunks: list[RetrievedChunk],
    version: str,
) -> Draft:
    out = result.value
    by_id = {f"k{i}": chunk for i, chunk in enumerate(chunks, 1)}
    unknown = [k for k in out.used_source_ids if k not in by_id]
    if unknown:
        log.warning("suggestion_unknown_source_ids", ids=unknown[:10])
    used = [by_id[k].chunk_id for k in dict.fromkeys(out.used_source_ids) if k in by_id]
    reply = (out.reply or "").strip()
    can_answer = out.can_answer and bool(reply)
    missing_info = (out.missing_info or "").strip() or None
    missing_topic = (out.missing_topic or "").strip().casefold() or None
    blocked: Finding | None = None
    if can_answer:
        reply = trim_reply(reply, request.platform, reserve=request.reserve)
        allowed = [c.content for c in chunks] + brand.texts() + list(request.quotable)
        found = output_filter.candidates(reply)
        if found:
            async with sessionmaker() as session:
                allowed += await knowledge_mentioning(session, [v for _, v in found])
        blocked = output_filter.check(reply, allowed, max_chars=None)
        if blocked is not None:
            log.info("suggestion_output_blocked", kind=blocked.kind)
            can_answer, missing_info, missing_topic = False, blocked.describe(), None
    if not can_answer:
        reply = ""
        missing_info = missing_info or NOT_ANSWERED
    return Draft(
        can_answer=can_answer,
        reply=reply or None,
        missing_info=None if can_answer else missing_info,
        missing_topic=None if can_answer else missing_topic,
        confidence=min(max(float(out.confidence), 0.0), 1.0),
        used_chunk_ids=used,
        top_similarity=max((c.similarity for c in chunks), default=None),
        model=result.model,
        prompt_version=version,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        chunks=chunks,
        blocked=blocked,
    )


async def knowledge_mentioning(session: AsyncSession, values: Sequence[str]) -> list[str]:
    """Knowledge texts (chunks of ready sources, and web-page sources' URLs) that contain any
    of ``values`` (links without their scheme, emails, phone numbers by their last 10 digits),
    for the output filter when a reply quotes something the retrieved chunks do not show."""
    content = func.lower(KnowledgeChunk.content)
    digits_only = func.regexp_replace(KnowledgeChunk.content, r"\D", "", "g")
    terms = []
    url_terms = []
    for value in values:
        digits = re.sub(r"\D", "", value)
        if "@" not in value and "." not in value and len(digits) >= output_filter.MIN_PHONE_DIGITS:
            terms.append(digits_only.contains(digits[-output_filter.PHONE_KEY_DIGITS :]))
            continue
        key = re.sub(r"(?i)^https?://", "", value.strip().rstrip(".,;:!?)")).casefold()
        key = key.removeprefix("www.").rstrip("/")
        if key:
            terms.append(content.contains(key, autoescape=True))
            url_terms.append(func.lower(KnowledgeSource.url).contains(key, autoescape=True))
    if not terms:
        return []
    texts = list(
        (
            await session.scalars(
                select(KnowledgeChunk.content)
                .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
                .where(KnowledgeSource.status == "ready", or_(*terms))
                .limit(MENTION_ROWS)
            )
        ).all()
    )
    if url_terms:
        texts += [
            u
            for u in (
                await session.scalars(
                    select(KnowledgeSource.url)
                    .where(KnowledgeSource.url.is_not(None), or_(*url_terms))
                    .limit(MENTION_ROWS)
                )
            ).all()
            if u
        ]
    return texts
