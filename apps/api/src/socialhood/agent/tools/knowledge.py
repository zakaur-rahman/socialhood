"""Knowledge tools (FR-AGT-02, TA.4; agent-architecture.html §5). Owners and admins, as in the
UI (``min_role`` admin); the brand voice reaches every run through the system prompt instead.

R1 (all read):
- search_knowledge(q): retrieval over the knowledge base (TR-AI-08, services/knowledge/retrieval;
  the query embedding isn't metered); the matching sources as knowledge_source refs.
- answer_from_knowledge(question): the Knowledge page's test box (T5.3,
  services/knowledge/answer.try_question, charges knowledge_test with the run as its ref);
  stores and sends nothing.
- list_knowledge_gaps(): questions the AI couldn't answer in the last 30 days (T5.10,
  services/knowledge/gaps), most asked first, with example messages cited by their conversation.

No writes.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent.registry import ToolContext, ToolResult
from socialhood.agent.tools.common import capped, clip, limit_field, quoted, ref, tool, when
from socialhood.ai.provider import AIError
from socialhood.errors import ApiError
from socialhood.models.identity import Role
from socialhood.repositories import workspaces
from socialhood.schemas.agent import AnswerRef
from socialhood.services.knowledge import answer, gaps, retrieval

SEARCH_FAILED = "The knowledge search didn't respond just now. Try again."


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- search_knowledge


class SearchKnowledgeInput(_Input):
    q: str = Field(min_length=1, max_length=500, description="What to look for, in plain words.")
    limit: int = limit_field(default=5, maximum=retrieval.MAX_RESULTS)


class KnowledgeHit(BaseModel):
    source_id: uuid.UUID
    source: str  # the source's title
    excerpt: str | None = None
    similarity: float  # 0..1


class KnowledgeSearchResult(ToolResult):
    hits: list[KnowledgeHit]


@tool(
    name="search_knowledge",
    label="Searching your knowledge base",
    description=(
        "The passages of the business's knowledge base (FAQs, notes, pages, files) closest to "
        "the words, most similar first, with their sources."
    ),
    input_model=SearchKnowledgeInput,
    result_model=KnowledgeSearchResult,
    min_role=Role.ADMIN,
)
async def search_knowledge(ctx: ToolContext, args: SearchKnowledgeInput) -> KnowledgeSearchResult:
    try:
        found = await retrieval.retrieve(ctx.session, args.q, limit=args.limit)
    except AIError as error:
        raise ApiError("service_unavailable", SEARCH_FAILED) from error
    hits = [
        KnowledgeHit(
            source_id=chunk.source_id,
            source=chunk.source_title,
            excerpt=clip(answer.chunk_text(chunk), 400),
            similarity=round(chunk.similarity, 3),
        )
        for chunk in found
    ]
    sources = {h.source_id: h.source for h in hits}
    caveats = [] if hits else ["Nothing in the knowledge base matches this closely enough."]
    return KnowledgeSearchResult(
        summary=clip(
            f"Found {len(hits)} passages from {len(sources)} sources about “{clip(args.q, 40)}”",
            300,
        )
        or "Searched the knowledge base",
        hits=hits,
        refs=[ref("knowledge_source", source_id, title) for source_id, title in sources.items()],
        caveats=caveats,
    )


# ---------------------------------------------------------------- answer_from_knowledge


class AnswerFromKnowledgeInput(_Input):
    question: str = Field(
        min_length=1, max_length=1000, description="A customer's question, as they'd ask it."
    )


class KnowledgeAnswerResult(ToolResult):
    can_answer: bool
    answer: str | None = None  # how the AI would answer a customer; nothing is sent
    missing_info: str | None = None  # what the knowledge base lacks
    sources: list[str] = Field(default_factory=list)


@tool(
    name="answer_from_knowledge",
    label="Trying the question on your knowledge base",
    description=(
        "How the AI would answer a customer's question from the knowledge base and brand voice "
        "(the Knowledge page's test box), or what's missing. Stores and sends nothing. Uses 1 "
        "AI credit."
    ),
    input_model=AnswerFromKnowledgeInput,
    result_model=KnowledgeAnswerResult,
    min_role=Role.ADMIN,
)
async def answer_from_knowledge(
    ctx: ToolContext, args: AnswerFromKnowledgeInput
) -> KnowledgeAnswerResult:
    workspace = await workspaces.get(ctx.session, ctx.workspace_id)
    if workspace is None:  # pragma: no cover - the run's workspace exists
        raise ApiError("not_found")
    result = await answer.try_question(
        ctx.session,
        ctx.sessionmaker,
        workspace=workspace,
        question=args.question,
        ref_type="agent_run",
        ref_id=ctx.run_id,
    )
    if result.can_answer:
        summary = f"The knowledge base answers {quoted(args.question)}"
        caveats = []
    else:
        summary = f"The knowledge base doesn't answer {quoted(args.question)}"
        caveats = [f"Missing from the knowledge base: {result.missing_info or 'this answer'}."]
    return KnowledgeAnswerResult(
        summary=clip(summary, 300) or "Tried the question",
        can_answer=result.can_answer,
        answer=result.answer,
        missing_info=result.missing_info,
        sources=[s.title for s in result.sources],
        refs=[ref("knowledge_source", s.id, s.title) for s in result.sources],
        caveats=caveats,
    )


# ---------------------------------------------------------------- list_knowledge_gaps


class ListGapsInput(_Input):
    limit: int = limit_field()


class GapExample(BaseModel):
    conversation_id: uuid.UUID
    text: str | None = None
    at: datetime


class Gap(BaseModel):
    id: uuid.UUID
    topic: str
    asked: int  # times asked
    first_asked_at: datetime
    last_asked_at: datetime
    last_asked_label: str | None = None
    examples: list[GapExample]


class GapsResult(ToolResult):
    items: list[Gap]
    total: int
    more: int


@tool(
    name="list_knowledge_gaps",
    label="Checking questions the AI couldn't answer",
    description=(
        "Questions customers asked in the last 30 days that the knowledge base couldn't "
        "answer, most asked first, with example messages."
    ),
    input_model=ListGapsInput,
    result_model=GapsResult,
    min_role=Role.ADMIN,
)
async def list_knowledge_gaps(ctx: ToolContext, args: ListGapsInput) -> GapsResult:
    found = await gaps.list_gaps(ctx.session, status="open", now=ctx.now)
    shown, more = capped(found.items, args.limit)
    items = [
        Gap(
            id=g.id,
            topic=g.topic,
            asked=g.occurrences,
            first_asked_at=g.first_seen_at,
            last_asked_at=g.last_seen_at,
            last_asked_label=when(ctx, g.last_seen_at),
            examples=[
                GapExample(
                    conversation_id=e.conversation_id, text=clip(e.text, 200), at=e.occurred_at
                )
                for e in g.examples[:2]
            ],
        )
        for g in shown
    ]
    refs: dict[uuid.UUID, AnswerRef] = {}
    for gap in items:
        for example in gap.examples:
            refs.setdefault(
                example.conversation_id,
                ref("conversation", example.conversation_id, quoted(example.text)),
            )
    top = ", ".join(f"“{g.topic}” ({g.asked})" for g in items[:3])
    total = len(found.items)
    summary = f"{total} unanswered question topics in the last 30 days" + (
        f": {top}" if top else ""
    )
    return GapsResult(
        summary=clip(summary, 300) or "Checked knowledge gaps",
        items=items,
        total=total,
        more=more,
        refs=list(refs.values()),
    )
