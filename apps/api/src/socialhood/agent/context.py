"""Memory for a run (TR-AGT-02, TA.2; agent-architecture.html §4 Memory).

No separate vector memory: what the agent knows comes from what Social Hood already stores.

- Business: the knowledge base through the search_knowledge tool; the brand voice (ai_settings)
  in the system prompt as trusted settings.
- Customer: the contact, conversation summary (FR-AI-03), latest analysis and lead score through
  get_customer and get_conversation.
- Conversation: the Ask panel thread; the last THREAD_CONTEXT_RUNS exchanges of the thread are
  passed to the model as data (never as instructions).
- Task: agent_runs and agent_steps; the orchestrator reloads them to resume.

Customer and member text always travels as data, never inside the system prompt (TR-AI-04,
SEC-10). ``build_context`` is the interface; TA.2 implements it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.agent import AgentRun


@dataclass(frozen=True, kw_only=True)
class Exchange:
    """One earlier run of the thread."""

    request: str
    answer: str | None  # None when it didn't finish with an answer
    at: datetime


@dataclass(frozen=True, kw_only=True)
class AgentContext:
    """What the planner knows before the first tool call."""

    workspace_name: str
    timezone: ZoneInfo
    now: datetime  # the run's clock: every relative time resolves against it (FR-AGT-05)
    # The connected accounts in plain words, with what each can't do ("Instagram @maple.bakery:
    # insights not granted"), so the answer can say so (FR-AGT-06).
    accounts: list[str] = field(default_factory=list)
    brand_voice: str | None = None  # from ai_settings: trusted settings, not customer text
    history: list[Exchange] = field(default_factory=list)  # oldest first, at most 6


async def build_context(session: AsyncSession, run: AgentRun, *, now: datetime) -> AgentContext:
    """Load the context for ``run`` in its workspace's scope."""
    raise NotImplementedError("TA.2")
