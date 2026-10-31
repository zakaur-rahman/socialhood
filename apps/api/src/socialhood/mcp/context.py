"""What a tool handler receives (C-165): ``ToolCall``, one per ``tools/call``.

The session is in the principal's workspace scope (TR-TEN-02), so every query a handler or a
service makes is filtered to that workspace and another workspace's ids are "not found". A read
tool's session is rolled back; a write tool's is committed by the pipeline (mcp/calls.py) after
the handler returns, never by the handler.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.agent.registry import Principal, ToolContext
from socialhood.mcp.principal import McpPrincipal
from socialhood.models.identity import Workspace
from socialhood.models.mcp import AiConnectionsMode
from socialhood.platforms.deps import PlatformDeps
from socialhood.settings import Settings


@dataclass(frozen=True)
class AuditNote:
    """One line for the workspace's audit log (``audit_events``, GR-19) that a write tool asks for;
    the pipeline writes it after the commit (mcp/audit.py ``mirror``)."""

    action: str  # e.g. post.created
    target_type: str
    target_id: str | None
    detail: dict[str, Any]


@dataclass(kw_only=True)
class ToolCall:
    principal: McpPrincipal
    session: AsyncSession
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    settings: Settings
    deps: PlatformDeps  # the agent's visuals are off for MCP (they're for the web's Ask panel)
    workspace: Workspace
    plan: str
    mode: AiConnectionsMode  # the effective mode: the workspace's, capped by the plan
    now: datetime  # UTC; every relative time in this call resolves against it
    timezone: ZoneInfo  # the workspace's
    call_id: uuid.UUID = field(default_factory=uuid.uuid4)
    client_name: str | None = None  # the AI app (clientInfo, else the User-Agent)
    # Work for after the commit (an enqueue that needs the committed row), run by the pipeline in
    # order; a failing one is logged and never fails the call.
    after_commit: list[Callable[[], Awaitable[None]]] = field(default_factory=list)
    audit_notes: list[AuditNote] = field(default_factory=list)

    def note(
        self, action: str, target_type: str, target_id: uuid.UUID | str | None = None, **detail: Any
    ) -> None:
        """Ask for an ``audit_events`` line once the call has committed."""
        self.audit_notes.append(
            AuditNote(
                action, target_type, str(target_id) if target_id is not None else None, detail
            )
        )

    def agent_context(self) -> ToolContext:
        """The context Ask Amplychat's tools take (agent/registry.py), for the MCP principal:
        their handlers are the one definition of what an AI reads (01-design.md §2.4)."""
        return ToolContext(
            session=self.session,
            sessionmaker=self.sessionmaker,
            platform=self.deps,
            workspace_id=self.workspace.id,
            timezone=self.timezone,
            now=self.now,
            principal=Principal(user_id=self.principal.user_id, role=self.principal.role),
            run_id=self.call_id,
        )

    def dashboard_url(self, path: str) -> str | None:
        """A link into the app for this workspace, e.g. ``schedule/<id>``; None without
        WEB_BASE_URL."""
        base = (self.settings.web_base_url or "").rstrip("/")
        if not base:
            return None
        return f"{base}/w/{self.workspace.slug}/{path.lstrip('/')}"
