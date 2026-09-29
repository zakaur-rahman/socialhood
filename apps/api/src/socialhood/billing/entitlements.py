"""Plan gates as FastAPI dependencies (T8.1; TR-BIL-04, FR-BIL-05, §2.15 "Role · gate").

- ``require_entitlement(key, value=None)``: a feature the plan must include, e.g.
  ``require_entitlement("ai_modes", "auto")`` or ``require_entitlement("ai_reply_automations")``.
  Refuses with 402 ``entitlement_required`` and ``PlanLimit(entitlement=key)``.
- ``require_capacity(key)``: a limit the workspace must be under, counted live for capacity keys
  (accounts_per_platform, active_automations, knowledge_characters, pending_scheduled_messages,
  members) or from usage_counters for period keys (scheduled_posts_monthly, ai_credits_monthly).
  Refuses with 402 ``quota_exceeded`` and ``PlanLimit(entitlement=key, limit=n)``.

Both read the plan from the workspace's subscription (billing/plans.py, never a copy) and run
after the role check. A gate that depends on the request body (the AI mode being set, whether an
automation replies with AI) is checked in the service with the same helpers, ``check_entitlement``
and ``check_capacity``, so the 402 is the same wherever it comes from.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.deps import WorkspaceContext


def require_entitlement(
    key: str, value: str | None = None
) -> Callable[..., Awaitable[WorkspaceContext]]:
    raise NotImplementedError("T8.1")


def require_capacity(key: str) -> Callable[..., Awaitable[WorkspaceContext]]:
    raise NotImplementedError("T8.1")


async def check_entitlement(session: AsyncSession, key: str, value: Any = None) -> None:
    """Raise 402 entitlement_required unless the current workspace's plan includes it."""
    raise NotImplementedError("T8.1")


async def check_capacity(session: AsyncSession, key: str, *, adding: int = 1) -> None:
    """Raise 402 quota_exceeded unless ``adding`` more fits under the plan's limit."""
    raise NotImplementedError("T8.1")
