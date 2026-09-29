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
SEC-10). The connected accounts are listed with what each can't do, so the answer can say so
instead of guessing (FR-AGT-06).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import require_workspace
from socialhood.models.agent import THREAD_CONTEXT_RUNS, AgentRun
from socialhood.models.connections import AccountStatus, Platform, SocialAccount
from socialhood.models.identity import Workspace
from socialhood.platforms.instagram.oauth import INSIGHTS_SCOPE
from socialhood.repositories import agent as repo
from socialhood.services.analytics.common import zone
from socialhood.services.suggestions.drafting import load_brand

STATUS_NOTES: dict[str, str] = {
    AccountStatus.NEEDS_RECONNECT.value: "needs reconnecting, so its data may be out of date",
    AccountStatus.DISCONNECTED.value: "disconnected",
    AccountStatus.ERROR.value: "has a connection error, so its data may be out of date",
}


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


def describe_account(account: SocialAccount) -> str:
    """An account in plain words with what it can't do."""
    platform = account.platform
    if platform == Platform.WHATSAPP:
        name = account.display_name or account.phone_number or "WhatsApp number"
        described = f"WhatsApp {name}"
    else:
        handle = f"@{account.username}" if account.username else account.display_name or "account"
        described = f"{platform.capitalize()} {handle}"
    notes: list[str] = []
    note = STATUS_NOTES.get(account.status)
    if note:
        notes.append(note)
    if platform == Platform.INSTAGRAM and INSIGHTS_SCOPE not in (account.scopes or []):
        notes.append("insights not granted (reach, views and saves aren't available)")
    return f"{described}: {'; '.join(notes)}" if notes else described


async def build_context(session: AsyncSession, run: AgentRun, *, now: datetime) -> AgentContext:
    """Load the context for ``run`` in its workspace's scope."""
    workspace = await session.get(Workspace, require_workspace())
    accounts = await session.scalars(
        select(SocialAccount).order_by(SocialAccount.platform, SocialAccount.created_at)
    )
    brand = await load_brand(session)
    voice = f"{brand.business_name}. Tone: {brand.tone}."
    if brand.business_description:
        voice = f"{brand.business_name}: {brand.business_description}. Tone: {brand.tone}."
    earlier = await repo.thread_history(session, run, limit=THREAD_CONTEXT_RUNS)
    return AgentContext(
        workspace_name=workspace.name if workspace else "this workspace",
        timezone=zone(workspace.timezone if workspace else "UTC"),
        now=now,
        accounts=[describe_account(a) for a in accounts.all()],
        brand_voice=voice,
        history=[Exchange(request=r.request, answer=r.answer, at=r.created_at) for r in earlier],
    )
