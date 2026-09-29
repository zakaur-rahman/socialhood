"""Downgrade effects (T8.3; FR-BIL-07, F-15 "Expired").

When a workspace moves to Free: accounts in Auto move to Suggest; AI-reply automations pause;
automations over the Free limit pause, keeping the most recently updated active; connected
accounts beyond accounts_per_platform become read-only (no sending). Nothing is deleted. The
report feeds the plan_downgraded notification ("2 accounts switched from Auto to Suggest. 4
automations paused.").
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class DowngradeReport:
    accounts_to_suggest: list[uuid.UUID] = field(default_factory=list)
    automations_paused: list[uuid.UUID] = field(default_factory=list)
    accounts_read_only: list[uuid.UUID] = field(default_factory=list)


async def apply_downgrade(session: AsyncSession, *, plan: str) -> DowngradeReport:
    """Apply ``plan``'s limits to the current workspace (idempotent)."""
    raise NotImplementedError("T8.3")
