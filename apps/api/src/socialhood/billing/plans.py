"""Plans and entitlements (§1.7, TR-BIL-04). Numbers are proposals pending OQ-1; changing one is
a one-line edit plus a deploy. None means unlimited."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

Plan = Literal["free", "pro", "max"]

ENTITLEMENTS: dict[str, dict[Plan, Any]] = {
    "accounts_per_platform": {"free": 1, "pro": 3, "max": 10},
    "members": {"free": 1, "pro": 1, "max": 10},
    "active_automations": {"free": 3, "pro": 50, "max": None},
    "ai_reply_automations": {"free": False, "pro": True, "max": True},
    "ai_modes": {
        "free": ("off", "suggest"),
        "pro": ("off", "suggest", "auto"),
        "max": ("off", "suggest", "auto"),
    },
    "ai_credits_monthly": {"free": 200, "pro": 5000, "max": 25000},
    "knowledge_characters": {"free": 200_000, "pro": 5_000_000, "max": 50_000_000},
    "scheduled_posts_monthly": {"free": 10, "pro": 300, "max": None},
    "pending_scheduled_messages": {"free": 20, "pro": 500, "max": None},
    "message_history_days": {"free": 90, "pro": None, "max": None},
}


def entitlement(plan: str, key: str) -> Any:
    values = ENTITLEMENTS[key]
    return values.get(plan, values["free"])  # type: ignore[call-overload]


async def current_plan(session: AsyncSession) -> str:
    """The current workspace's plan (the subscription row is tenant-scoped)."""
    from sqlalchemy import select

    from socialhood.models.billing import Subscription

    plan = await session.scalar(select(Subscription.plan))
    return plan or "free"
