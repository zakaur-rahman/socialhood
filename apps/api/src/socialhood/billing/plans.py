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
    # Seats (GR-19): the owner counts, and so does every pending invitation. PD-1, decided by the
    # owner on 2026-10-24 ("for now"): Free 1, Pro 3, Max 10.
    "members": {"free": 1, "pro": 3, "max": 10},
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
    # Custom contact fields a workspace can define (GR-02). Contacts themselves are never
    # metered (PD-2). Proposed values, pending the owner's plan decisions.
    "contact_fields": {"free": 5, "pro": 50, "max": 200},
    "webhook_endpoints": {"free": 1, "pro": 5, "max": 20},  # GR-04 (C-080)
    # Google Sheets sync (GR-27): Pro and Max only (PD-6, decided 2026-10-24; webhooks stay on
    # every plan). Set free to True to open it to every plan.
    "sheets_sync": {"free": False, "pro": True, "max": True},
    # The public API, API keys and the Zapier app (GR-25, GR-26): Pro and Max only. Outbound
    # webhooks above stay on every plan. Owner decision PD-6 (2026-10-24).
    "public_api": {"free": False, "pro": True, "max": True},
    # AI connections over MCP (C-165, D2 decided 2026-10-31): every plan connects; the modes a
    # workspace may choose (models/mcp.AiConnectionsMode). Free reads and saves drafts; scheduling
    # from an AI client is part of Pro. Separate from public_api so either can change alone.
    "ai_connections": {
        "free": ("off", "read_only", "read_drafts"),
        "pro": ("off", "read_only", "read_drafts", "full"),
        "max": ("off", "read_only", "read_drafts", "full"),
    },
    # MCP tool calls a workspace may make in a UTC day, across all its AI connections (C-165, §6.1).
    "mcp_calls_daily": {"free": 100, "pro": 2000, "max": 10000},
    # Posts an AI app may schedule in a UTC day (C-165 phase B, §6.1: below Instagram's 100 API
    # posts per 24 hours per account). Free saves drafts only, so its cap is 0 scheduled posts.
    "mcp_posts_daily": {"free": 0, "pro": 25, "max": 100},
    # Files and megabytes an AI app may upload in a UTC day (§5.3).
    "mcp_uploads_daily": {"free": 20, "pro": 200, "max": 1000},
    "mcp_upload_mb_daily": {"free": 500, "pro": 10_000, "max": 50_000},
    # Steps in one automation flow (GR-13). Every plan can branch; Free is capped (PD-5, the
    # plan's recommended option, pending the owner's decision: change the numbers here, or set
    # free to Pro's to lift the cap). A flow is at most schemas.flows.MAX_STEPS whatever the plan.
    "flow_steps": {"free": 5, "pro": 50, "max": 50},
    # Pages one site crawl reads (GR-35): the plan's cap on a site source's pages. Proposed values,
    # pending the owner's plan decisions; the characters of knowledge limit still applies on top.
    "crawl_pages": {"free": 25, "pro": 250, "max": 1000},
    # Website chat widget (GR-28, PD-7 decided 2026-10-24): on every plan. Free shows "Powered by
    # Amplychat"; Pro and Max can turn it off. New widget chats a day are capped on every plan
    # to bound abuse (services/widget/chat.py); the cap counts new visitors, not messages.
    "widget_remove_branding": {"free": False, "pro": True, "max": True},
    "widget_conversations_daily": {"free": 50, "pro": 500, "max": 5000},
    # Recipients a workspace may send WhatsApp broadcasts to in a billing period (GR-23, PD-4:
    # Pro and Max, not Free; decided 2026-10-24). 0 means the plan has no broadcasts: the 402 is
    # then entitlement_required, otherwise quota_exceeded. A recipient counts when its message is
    # handed to the send queue (an attempt), failures included, skipped contacts never.
    "broadcast_recipients_monthly": {"free": 0, "pro": 2500, "max": 25000},
    # The product catalogue (GR-31, PD-8: commerce is on Pro and Max, not Free; one line to change).
    # Without it adding, changing, importing and syncing products is refused with 402
    # entitlement_required; what exists is still shown and still answers customers.
    "commerce": {"free": False, "pro": True, "max": True},
    # Products a workspace may hold, and the rows one CSV import may carry (a product with
    # variants is one product, each variant a row). Proposed values, pending the owner's plan
    # decisions: a Shopify sync stops at the product cap and says so.
    "catalogue_products": {"free": 0, "pro": 1000, "max": 20000},
    "catalogue_import_rows": {"free": 0, "pro": 500, "max": 5000},
    # Orders a workspace may create in a calendar month (GR-32; proposed, pending the owner's
    # confirmation, C-120): counted when the order is made, whatever happens to it after.
    "orders_monthly": {"free": 0, "pro": 500, "max": 5000},
    # Sequences (GR-24): sequences that can run at once, and steps in one. Proposed values, pending
    # the owner's confirmation (C-118): a template step is still a message Meta bills the business
    # for, and needs the contact's marketing consent, so the plan limits only how many there are.
    "active_sequences": {"free": 1, "pro": 10, "max": 50},
    "sequence_steps": {"free": 3, "pro": 10, "max": 20},
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
    # The composer's AI Polish: rewrites the member's own draft (C-063).
    "reply_polish": 1,
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
