"""The audit of MCP tool calls (C-165; 01-design.md §6.3): one ``mcp_tool_calls`` row per
``tools/call``, whatever the outcome.

The row says who (member, credential, client), which tool, what it was asked (a digest of the
canonical arguments plus a redacted copy: short values kept, long text cut, credentials and
idempotency keys dropped), the outcome and how long it took. Results aren't stored, so no
customer text reaches the audit; nor does the AI conversation (we never receive it).

It is written in its own transaction after the call, so a refused or failed call is recorded
too; an audit write that fails is logged and never fails the call.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.mcp.context import AuditNote
from socialhood.mcp.principal import McpPrincipal
from socialhood.models.identity import User
from socialhood.models.mcp import CallOutcome, CredentialKind, McpToolCall
from socialhood.models.team import AuditEvent
from socialhood.observability.logging import get_logger
from socialhood.services.audit import actor_label, clean_detail

log = get_logger(__name__)

VALUE_CHARS = 200
LIST_ITEMS = 20
MAX_KEYS = 30
MAX_DEPTH = 3
# Argument names never copied (their value is replaced by "[redacted]").
SECRET_KEYS = ("token", "secret", "password", "api_key", "authorization", "idempotency_key")


def digest(arguments: dict[str, Any]) -> str:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def redact(value: Any, depth: int = 0) -> Any:
    if isinstance(value, dict):
        if depth >= MAX_DEPTH:
            return "[…]"
        out: dict[str, Any] = {}
        for key, item in list(value.items())[:MAX_KEYS]:
            name = str(key)[:60]
            if any(secret in name.lower() for secret in SECRET_KEYS):
                out[name] = "[redacted]"
            else:
                out[name] = redact(item, depth + 1)
        return out
    if isinstance(value, list):
        if depth >= MAX_DEPTH:
            return "[…]"
        return [redact(item, depth + 1) for item in value[:LIST_ITEMS]]
    if isinstance(value, str):
        return value if len(value) <= VALUE_CHARS else value[: VALUE_CHARS - 1] + "…"
    if isinstance(value, bool | int | float) or value is None:
        return value
    return str(value)[:VALUE_CHARS]


@dataclass(frozen=True, kw_only=True)
class CallRecord:
    principal: McpPrincipal
    tool: str
    arguments: dict[str, Any]
    outcome: CallOutcome
    error_code: str | None
    latency_ms: int
    client_name: str | None
    client_version: str | None
    request_id: str | None


async def record(sessionmaker: async_sessionmaker[AsyncSession], call: CallRecord) -> None:
    principal = call.principal
    api_key = principal.credential is CredentialKind.API_KEY
    try:
        with workspace_scope(principal.workspace_id):
            async with sessionmaker() as session:
                session.add(
                    McpToolCall(
                        workspace_id=principal.workspace_id,
                        user_id=principal.user_id,
                        credential_kind=principal.credential.value,
                        api_key_id=principal.credential_id if api_key else None,
                        connection_id=None if api_key else principal.credential_id,
                        credential_label=principal.credential_label[:120],
                        client_name=(call.client_name or None) and call.client_name[:120],
                        client_version=(call.client_version or None) and call.client_version[:60],
                        tool=call.tool[:64],
                        arguments=redact(call.arguments),
                        arguments_digest=digest(call.arguments),
                        outcome=call.outcome.value,
                        error_code=call.error_code,
                        latency_ms=max(call.latency_ms, 0),
                        request_id=call.request_id,
                    )
                )
                await session.commit()
    except Exception as error:
        log.warning("mcp_audit_failed", tool=call.tool, error=type(error).__name__)
    log.info(
        "mcp_tool_call",
        tool=call.tool,
        outcome=call.outcome.value,
        error_code=call.error_code,
        latency_ms=call.latency_ms,
        workspace_id=str(principal.workspace_id),
        credential=principal.credential.value,
        credential_id=str(principal.credential_id),
    )


async def mirror(
    sessionmaker: async_sessionmaker[AsyncSession],
    principal: McpPrincipal,
    notes: list[AuditNote],
    *,
    client_name: str | None,
) -> None:
    """Mirror a committed write into the workspace's audit log (``audit_events``, GR-19), the
    line the Team page's Audit log shows: "Asha via Claude Code: post.created". Written after the
    change committed, in its own transaction; one that fails is logged and never fails the call.
    The detail never holds caption or message text (services/audit.clean_detail)."""
    if not notes:
        return
    try:
        with workspace_scope(principal.workspace_id):
            async with sessionmaker() as session:
                user = await session.get(User, principal.user_id)
                who = actor_label(user) if user is not None else "A member"
                via = (client_name or principal.credential_label or "an AI app")[:60]
                for note in notes:
                    session.add(
                        AuditEvent(
                            workspace_id=principal.workspace_id,
                            actor_user_id=principal.user_id,
                            actor_label=f"{who} via {via}"[:120],
                            action=note.action[:60],
                            target_type=note.target_type[:40],
                            target_id=note.target_id[:80] if note.target_id else None,
                            detail=clean_detail({**note.detail, "via": "mcp", "client": via}),
                        )
                    )
                await session.commit()
    except Exception as error:
        log.warning("mcp_audit_mirror_failed", error=type(error).__name__)
