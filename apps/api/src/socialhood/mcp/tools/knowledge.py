"""Knowledge and automations reads (01-design.md §4.1): search_knowledge, list_automations.
Owners and admins, as the Knowledge and Automations pages. Both wrap Ask Amplychat's tools.

Knowledge passages are the business's own sources, but a source can be a crawled web page, so
excerpts are returned as ``excerpt_text`` (third-party text).
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import ToolInput, ToolOutput, registry, tool
from socialhood.mcp.tools.common import agent_tool, moment
from socialhood.models.identity import Role
from socialhood.schemas.automations import StatusName, TriggerName
from socialhood.services.knowledge.retrieval import MAX_RESULTS

# ---------------------------------------------------------------- search_knowledge


class SearchKnowledgeInput(ToolInput):
    query: str = Field(
        min_length=1,
        max_length=500,
        description="A few words for what to look for, e.g. “opening hours”, “delivery charges”.",
    )
    limit: int = Field(
        default=5, ge=1, le=MAX_RESULTS, description=f"How many passages (at most {MAX_RESULTS})."
    )


class PassageOut(BaseModel):
    source_id: uuid.UUID
    source: str  # the source's title
    excerpt_text: str | None = None
    similarity: float  # 0 to 1


class KnowledgeResult(ToolOutput):
    passages: list[PassageOut]
    dashboard_url: str | None = None


@tool(
    registry,
    name="search_knowledge",
    title="Search the knowledge base",
    description=(
        "Passages of the business's knowledge base (FAQs, notes, website pages, files) closest "
        "to the words, most similar first, with their sources. What Amplychat's AI replies to "
        "customers from."
    ),
    input_model=SearchKnowledgeInput,
    output_model=KnowledgeResult,
    scope="knowledge:read",
    min_role=Role.ADMIN,
)
async def search_knowledge(call: ToolCall, args: SearchKnowledgeInput) -> KnowledgeResult:
    found = await agent_tool(call, "search_knowledge", {"q": args.query, "limit": args.limit})
    return KnowledgeResult(
        summary=found.summary,
        passages=[
            PassageOut(
                source_id=h.source_id,
                source=h.source,
                excerpt_text=h.excerpt,
                similarity=h.similarity,
            )
            for h in found.hits
        ],
        dashboard_url=call.dashboard_url("knowledge"),
        caveats=found.caveats,
    )


# ---------------------------------------------------------------- list_automations


class ListAutomationsInput(ToolInput):
    status: StatusName | None = None
    trigger: TriggerName | None = None
    account: str | None = Field(
        default=None, max_length=100, description="A connected account's id or @handle."
    )
    query: str | None = Field(
        default=None, max_length=100, description="Words in the name or keywords."
    )
    limit: int = Field(default=20, ge=1, le=20, description="How many to list (at most 20).")


class AutomationOut(BaseModel):
    automation_id: uuid.UUID
    name: str
    status: str  # draft, active, paused
    display_status: str  # also scheduled and ended
    trigger: str | None = None
    keywords: list[str]
    action: str | None = None
    account: str | None = None
    runs_7d: int
    last_run_at: str | None = None
    queued: int  # private replies waiting in the account's queue
    missing_for_activation: list[str]
    dashboard_url: str | None = None


class AutomationsResult(ToolOutput):
    runs_period: str
    items: list[AutomationOut]
    total: int
    more: int


@tool(
    registry,
    name="list_automations",
    title="List automations",
    description=(
        "Automations with their status, trigger, keywords, action, account and runs in the last "
        "7 days, most active first, and what a draft still needs before it can go live."
    ),
    input_model=ListAutomationsInput,
    output_model=AutomationsResult,
    scope="automations:read",
    min_role=Role.ADMIN,
)
async def list_automations(call: ToolCall, args: ListAutomationsInput) -> AutomationsResult:
    found = await agent_tool(
        call,
        "list_automations",
        {
            "status": args.status,
            "trigger": args.trigger,
            "account": args.account,
            "q": args.query,
            "limit": args.limit,
        },
    )
    return AutomationsResult(
        summary=found.summary,
        runs_period=found.runs_period,
        items=[
            AutomationOut(
                automation_id=a.id,
                name=a.name,
                status=a.status,
                display_status=a.display_status,
                trigger=a.trigger,
                keywords=a.keywords,
                action=a.action,
                account=a.account,
                runs_7d=a.runs_7d,
                last_run_at=moment(call, a.last_run_at),
                queued=a.queued,
                missing_for_activation=a.missing_for_activation,
                dashboard_url=call.dashboard_url(f"automations/{a.id}"),
            )
            for a in found.items
        ],
        total=found.total,
        more=found.more,
        caveats=found.caveats,
    )
