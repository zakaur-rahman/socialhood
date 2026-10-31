"""Safe retries for MCP writes (C-165; 01-design.md §6.2).

The 2026-07-28 transport has no stream resumability: a broken response loses the in-flight
request and the client sends it again, so duplicate writes are expected, not rare. Two guards:

- **An explicit key** (``idempotency_key``, every write tool's argument): stored through
  services/idempotency.py (Valkey, 24 hours, per workspace and member). The same key with the
  same arguments returns the first result; with different arguments it is
  ``idempotency_conflict``. Only successful results are stored, so a refused call can be retried
  with the same key once fixed.
- **Implicit dedupe** for a tool with ``dedupe_window_s``: without a key, an identical call
  (same connection, tool and arguments) inside the window returns the first result.

Either way the replayed result has ``duplicate_of_previous_call: true``. Valkey being down never
blocks a write (both guards then let it through, as the app's own sends do).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis

from socialhood.mcp.audit import digest
from socialhood.mcp.principal import McpPrincipal
from socialhood.observability.logging import get_logger
from socialhood.services.idempotency import IdempotencyKey, fingerprint

log = get_logger(__name__)

KEY_ARGUMENT = "idempotency_key"


@dataclass
class WriteGuard:
    """One write call's guard: ``begin`` returns a stored result to replay, or None to run the
    tool; then ``complete`` (success) or ``release`` (anything else)."""

    redis: Redis
    principal: McpPrincipal
    tool: str
    arguments: dict[str, Any]  # as validated, the key included
    dedupe_window_s: int | None

    def __post_init__(self) -> None:
        body = {k: v for k, v in self.arguments.items() if k != KEY_ARGUMENT}
        key = self.arguments.get(KEY_ARGUMENT)
        self._explicit: IdempotencyKey | None = None
        if key:
            self._explicit = IdempotencyKey(
                self.redis,
                workspace_id=self.principal.workspace_id,
                user_id=self.principal.user_id,
                key=f"mcp:{key}",
                fingerprint=fingerprint("MCP", self.tool, body),
            )
        self._dedupe_name = (
            f"mcp-dedupe:{self.principal.credential_id}:{self.tool}:{digest(body)}"
            if not key and self.dedupe_window_s
            else None
        )

    async def begin(self) -> dict[str, Any] | None:
        if self._explicit is not None:
            stored = await self._explicit.begin()  # idempotency_conflict for other arguments
            return stored.body if stored is not None else None
        if self._dedupe_name is not None:
            try:
                raw = await self.redis.get(self._dedupe_name)
            except Exception:
                log.warning("mcp_dedupe_unavailable")
                return None
            return dict(json.loads(raw)) if raw else None
        return None

    async def complete(self, structured: dict[str, Any]) -> None:
        if self._explicit is not None:
            await self._explicit.complete(200, structured)
        elif self._dedupe_name is not None and self.dedupe_window_s:
            try:
                await self.redis.set(
                    self._dedupe_name, json.dumps(structured, default=str), ex=self.dedupe_window_s
                )
            except Exception:
                log.warning("mcp_dedupe_unavailable")

    async def release(self) -> None:
        if self._explicit is not None:
            await self._explicit.release()
