"""Plans and entitlements (§1.7, TR-BIL-04). Numbers are proposals pending OQ-1; changing one is
a one-line edit plus a deploy. None means unlimited.

Paid plans map to Dodo products by settings (TR-BIL-02: DODO_PRODUCT_PRO_MONTHLY is pro,
DODO_PRODUCT_MAX_MONTHLY max). Max can be read from Dodo but not bought until R2 (FR-BIL-01).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from socialhood.settings import Settings

Plan = Literal["free", "pro", "max"]
PLANS: tuple[Plan, ...] = ("free", "pro", "max")
PAID_PLANS: tuple[Plan, ...] = ("pro", "max")
# Plans a checkout can start (FR-BIL-01: Max in R2).
AVAILABLE: dict[Plan, bool] = {"free": True, "pro": True, "max": False}
# §1.7 trial_days: Pro's 7-day trial, once per workspace and owner email (FR-BIL-03, TR-BIL-05).
TRIAL_DAYS: dict[Plan, int] = {"free": 0, "pro": 7, "max": 0}

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
    # Posts per account whose comments are analysed: the most recent ones (T6.2).
    "comment_intelligence_posts": {"free": 5, "pro": None, "max": None},
    # Edited videos rendered per usage period (P7b, FR-PUB-23): media_renders of kind video
    # created in the period, failed ones not counted; asking for the same edit again is free.
    # Photo edits render on the fly and aren't limited (they are counted, billing/usage.py).
    "video_renders_monthly": {"free": 10, "pro": 200, "max": 1000},
}


# AI credit costs per feature (§1.7); keys match models.billing.AiFeature.
CREDIT_COSTS: dict[str, int] = {
    "message_analysis": 1,
    "reply_suggestion": 2,
    "auto_reply": 2,
    "conversation_summary": 1,
    "comment_analysis": 1,
    "post_summary": 2,
    "caption_generation": 1,
    "knowledge_test": 1,
    "automation_ai_reply": 2,
    # Each model call of an agent run (TR-AGT-02; agent-architecture §17): a typical question
    # takes 2-4. Tools that call AI charge their own feature (a draft reply is reply_suggestion).
    "agent_turn": 1,
}


def entitlement(plan: str, key: str) -> Any:
    values = ENTITLEMENTS[key]
    return values.get(plan, values["free"])  # type: ignore[call-overload]


def product_for(plan: str, settings: Settings) -> str | None:
    """The Dodo product id a paid plan is sold as (None: not configured, or Free)."""
    products = {
        "pro": settings.dodo_product_pro_monthly,
        "max": settings.dodo_product_max_monthly,
    }
    return products.get(plan) or None


def plan_for_product(product_id: str | None, settings: Settings) -> Plan | None:
    """TR-BIL-02: the plan a Dodo product id stands for; None for a product we don't sell."""
    if not product_id:
        return None
    for plan in PAID_PLANS:
        if product_for(plan, settings) == product_id:
            return plan
    return None


async def current_plan(session: AsyncSession) -> str:
    """The current workspace's plan (the subscription row is tenant-scoped)."""
    from sqlalchemy import select

    from socialhood.models.billing import Subscription

    plan = await session.scalar(select(Subscription.plan))
    return plan or "free"
