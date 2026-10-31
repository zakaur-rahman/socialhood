"""Who an MCP request acts for (C-165; 01-design.md §2.4, §3.3, §3.5).

A credential (an API key now, an OAuth access token from phase C) resolves to one
``McpPrincipal``: one workspace, one member with their *current* role, the credential's scopes.
Tools only ever see the principal, never the credential, so a new kind of credential changes
nothing below ``mcp/auth.py``.

The principal of a request is kept in a context variable for the duration of the HTTP request
(``mcp/http.py`` sets it after authenticating); the SDK serves the request inside that context.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from socialhood.models.identity import Role
from socialhood.models.mcp import CredentialKind

# Every principal holds it, whatever the credential says (§3.4: "always granted").
ALWAYS_GRANTED = "workspace:read"


@dataclass(frozen=True, kw_only=True)
class McpPrincipal:
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    role: Role  # the member's role now, read on every request (the role cap, §3.5)
    scopes: frozenset[str]
    credential: CredentialKind
    credential_id: uuid.UUID  # the API key's id, or (phase C) the connection's
    # What the audit and get_workspace call the credential, e.g. "API key “Codex laptop”".
    credential_label: str


@dataclass(frozen=True, kw_only=True)
class McpRequest:
    """One authenticated HTTP request to /mcp."""

    principal: McpPrincipal
    client_ip: str
    user_agent: str | None = None
    request_id: str | None = None


_current: ContextVar[McpRequest | None] = ContextVar("mcp_request", default=None)


def current_request() -> McpRequest:
    """The authenticated request being served. Raises outside one (a handler reached without the
    auth wrapper is a bug, never an anonymous call)."""
    request = _current.get()
    if request is None:
        raise RuntimeError("no authenticated MCP request in context")
    return request


@contextmanager
def request_scope(request: McpRequest) -> Iterator[None]:
    token = _current.set(request)
    try:
        yield
    finally:
        _current.reset(token)
