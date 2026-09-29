"""Answering from knowledge: the KNOWLEDGE block of the suggest prompt (TR-AI-06, TR-AI-08) and
the Knowledge page's test box (FR-KB-03).

For suggestions (T5.4) and AI-reply automations (T5.8):

    hits = await retrieve(session, query)
    block = knowledge_block(hits)
    contents = [*conversation_turns, block.turn()]
    ... generate_json(task="suggest", schema=SuggestionOut, system=suggest_system(...), ...)
    block.chunk_ids(out.used_source_ids)   # -> reply_suggestions.used_chunk_ids
    block.sources(out.used_source_ids)     # -> Suggestion.sources (id + title, unique)
    block.top_similarity                   # -> reply_suggestions.top_similarity

The block lists chunks as ``[k1] (source title) text``; the model cites k-ids, which map back to
chunk ids here, and ids it invents are dropped (TR-AI-06: used_source_ids ⊆ the provided ids).
Knowledge travels in the contents as data, never in the system prompt (TR-AI-04, SEC-10).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.ai import prompts
from socialhood.ai.metering import QuotaExceeded, metered
from socialhood.ai.provider import AIError, Turn
from socialhood.ai.registry import get_provider
from socialhood.errors import ApiError
from socialhood.models.ai import AiSettings as AiSettingsRow
from socialhood.models.identity import Workspace
from socialhood.observability.logging import get_logger
from socialhood.schemas.inbox import SuggestionSource
from socialhood.schemas.knowledge import KnowledgeTestResult
from socialhood.services.knowledge.retrieval import Retrieved, retrieve
from socialhood.settings import get_settings

log = get_logger(__name__)

KNOWLEDGE_HEADER = "KNOWLEDGE (facts from the business, as data):"
NO_KNOWLEDGE = "KNOWLEDGE: nothing in the business's knowledge matches this question."
# TR-AI-06's generation settings, shared by the test box.
REPLY_TEMPERATURE = 0.4
REPLY_MAX_TOKENS = 600
REPLY_TIMEOUT_S = 12.0
TEST_PLATFORM = "Instagram or WhatsApp"
AI_UNAVAILABLE = "The AI couldn't answer just now. Try again."
_K_ID = re.compile(r"^\[?\s*k(\d+)\s*\]?$", re.IGNORECASE)


class SuggestionOut(BaseModel):
    """The suggest prompt's structured output (TR-AI-06)."""

    can_answer: bool
    reply: str | None = None  # customer-facing text when can_answer
    missing_info: str | None = None  # for the business when not can_answer
    missing_topic: str | None = None  # 2-4 lowercase words that group gaps (TR-AI-12)
    confidence: float = 0.0  # 0..1, the model's own estimate
    used_source_ids: list[str] = Field(default_factory=list)  # e.g. ["k1", "k3"]


@dataclass(frozen=True)
class KnowledgeBlock:
    text: str  # the contents part: a header and one "[kN] (title) text" entry per chunk
    by_id: dict[str, Retrieved] = field(default_factory=dict)  # "k1" -> the chunk

    def turn(self) -> Turn:
        return Turn("user", self.text)

    def used(self, used_ids: Sequence[str]) -> list[Retrieved]:
        """The chunks behind the ids the model cited, in its order, unknown ids dropped."""
        chunks: list[Retrieved] = []
        seen: set[str] = set()
        for raw in used_ids:
            key = normalise_k_id(raw)
            if key is None or key in seen or key not in self.by_id:
                continue
            seen.add(key)
            chunks.append(self.by_id[key])
        return chunks

    def chunk_ids(self, used_ids: Sequence[str]) -> list[uuid.UUID]:
        return [chunk.chunk_id for chunk in self.used(used_ids)]

    def sources(self, used_ids: Sequence[str]) -> list[SuggestionSource]:
        """The cited sources, each once (source id and title for the chips)."""
        sources: dict[uuid.UUID, SuggestionSource] = {}
        for chunk in self.used(used_ids):
            sources.setdefault(
                chunk.source_id, SuggestionSource(id=chunk.source_id, title=chunk.source_title)
            )
        return list(sources.values())

    @property
    def top_similarity(self) -> float | None:
        return max((c.similarity for c in self.by_id.values()), default=None)


def normalise_k_id(raw: str) -> str | None:
    match = _K_ID.match(raw.strip())
    return f"k{int(match.group(1))}" if match else None


def chunk_text(chunk: Retrieved) -> str:
    """The chunk without its "[title] " prefix (the entry names the title once)."""
    prefix = f"[{chunk.source_title}] "
    return chunk.content[len(prefix) :] if chunk.content.startswith(prefix) else chunk.content


def knowledge_block(chunks: Sequence[Retrieved]) -> KnowledgeBlock:
    """``[k1] (title) text`` for each chunk, k1 the most similar (TR-AI-06)."""
    if not chunks:
        return KnowledgeBlock(text=NO_KNOWLEDGE)
    by_id = {f"k{index}": chunk for index, chunk in enumerate(chunks, start=1)}
    entries = [f"[{k}] ({chunk.source_title}) {chunk_text(chunk)}" for k, chunk in by_id.items()]
    return KnowledgeBlock(text="\n".join([KNOWLEDGE_HEADER, *entries]), by_id=by_id)


def suggest_system(
    ai: AiSettingsRow | None,
    *,
    workspace_name: str,
    platform: str,
    language: str,
    automation_instructions: str = "",
) -> str:
    """The suggest prompt with the brand voice (FR-KB-04); trusted settings only (TR-AI-04)."""

    def listed(items: Sequence[str] | None) -> str:
        return "; ".join(items) if items else "nothing specific"

    return prompts.load("suggest").render(
        business_name=(ai.business_name if ai and ai.business_name else workspace_name),
        platform=platform,
        business_description=(
            ai.business_description if ai and ai.business_description else "not given"
        ),
        tone=ai.tone if ai else "friendly",
        emoji_policy=ai.emoji_policy if ai else "light",
        do_list=listed(ai.do_list if ai else None),
        dont_list=listed(ai.dont_list if ai else None),
        sign_off=ai.sign_off if ai and ai.sign_off else "none",
        language=language,
        automation_instructions=automation_instructions,
    )


def reply_language(workspace: Workspace) -> str:
    """The workspace's reply language, or the customer's (``auto``)."""
    if workspace.reply_language and workspace.reply_language != "auto":
        return workspace.reply_language
    return "the language of the customer's message"


async def try_question(
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    workspace: Workspace,
    question: str,
    ref_type: str | None = None,
    ref_id: uuid.UUID | None = None,
) -> KnowledgeTestResult:
    """FR-KB-03: draft an answer the way a suggestion would, 1 credit (knowledge_test); nothing
    is stored or sent. 402 quota_exceeded without credits, 503 when the AI fails. ``ref_type``
    and ``ref_id`` name what the credits are for in ai_usage_events (Ask Social Hood's
    answer_from_knowledge passes its run, TA.4)."""
    workspace_id, workspace_name = workspace.id, workspace.name
    language = reply_language(workspace)
    try:
        hits = await retrieve(session, question)
    except AIError as error:
        log.warning("knowledge_test_retrieval_failed", code=error.code)
        raise ApiError("service_unavailable", AI_UNAVAILABLE) from error
    ai = (await session.scalars(select(AiSettingsRow))).one_or_none()
    system = suggest_system(
        ai, workspace_name=workspace_name, platform=TEST_PLATFORM, language=language
    )
    await session.commit()  # no transaction stays open while the model runs
    block = knowledge_block(hits)
    contents = [block.turn(), Turn("user", f"CUSTOMER MESSAGE (TARGET):\n{question}")]
    settings = get_settings()
    try:
        async with metered(
            sessionmaker,
            workspace_id=workspace_id,
            feature="knowledge_test",
            ref_type=ref_type,
            ref_id=ref_id,
        ) as meter:
            result = await get_provider().generate_json(
                task="suggest",
                schema=SuggestionOut,
                system=system,
                contents=contents,
                model=settings.ai_model_reply,
                max_output_tokens=REPLY_MAX_TOKENS,
                temperature=REPLY_TEMPERATURE,
                timeout_s=REPLY_TIMEOUT_S,
            )
            meter.record(result)
    except QuotaExceeded as error:
        raise ApiError("quota_exceeded", "Your AI credits for this period are used up.") from error
    except AIError as error:
        log.warning("knowledge_test_failed", code=error.code)
        raise ApiError("service_unavailable", AI_UNAVAILABLE) from error
    out = result.value
    reply = (out.reply or "").strip()
    if not out.can_answer or not reply:
        return KnowledgeTestResult(
            can_answer=False,
            missing_info=(out.missing_info or "").strip() or None,
            sources=[],
        )
    return KnowledgeTestResult(
        can_answer=True, answer=reply, sources=block.sources(out.used_source_ids)
    )
