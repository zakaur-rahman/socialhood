"""Billing state (T5.1; TR-BIL-04, TR-BIL-05, FR-AI-05, §5.10 BillingState): the UI's only source
for the plan, its entitlements and usage. P5 serves it for the AI credit banner and the knowledge
limit; prices come from Dodo in P8 (TR-BIL-06), so they are empty until then.

Usage: ``ai_credits`` is the current credit period's counter (it resets on the billing anchor day,
``period_end``); ``scheduled_posts`` counts the posts scheduled this period (T7.1, each post once
per period); ``knowledge_characters`` is counted live from the knowledge sources (§5.8: capacity
limits are not stored).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.ai.metering import quota
from socialhood.billing.plans import ENTITLEMENTS, entitlement
from socialhood.models.ai import KnowledgeSource
from socialhood.models.billing import Subscription, UsageMetric
from socialhood.models.identity import Workspace
from socialhood.repositories import usage, workspaces
from socialhood.schemas.billing import BillingState, EntitlementValue, UsageMeter


def _value(value: Any) -> int | bool | list[str] | None:
    return list(value) if isinstance(value, tuple) else value


async def billing_state(
    session: AsyncSession, workspace: Workspace, *, now: datetime
) -> BillingState:
    """The current workspace's billing state (its session's workspace scope)."""
    sub = await session.scalar(select(Subscription))
    plan = sub.plan if sub is not None else "free"
    credits = await quota(session, now=now)
    posts_limit = entitlement(plan, "scheduled_posts_monthly")
    posts_start, posts_end = await usage.ensure_counter(
        session, today=now.date(), limit=posts_limit, metric=UsageMetric.SCHEDULED_POSTS
    )
    posts = await usage.counter(session, posts_start, metric=UsageMetric.SCHEDULED_POSTS)
    characters = await session.scalar(
        select(func.coalesce(func.sum(KnowledgeSource.char_count), 0))
    )
    return BillingState(
        plan=plan,
        status=sub.status if sub is not None else "free",
        current_period_end=sub.current_period_end if sub is not None else None,
        trial_ends_at=sub.trial_ends_at if sub is not None else None,
        cancel_at_period_end=sub.cancel_at_period_end if sub is not None else False,
        grace_until=sub.grace_until if sub is not None else None,
        trial_eligible=not await workspaces.trial_used_by_owner(session, workspace),
        prices=[],
        entitlements=[
            EntitlementValue(key=key, value=_value(entitlement(plan, key))) for key in ENTITLEMENTS
        ],
        usage=[
            UsageMeter(
                metric="ai_credits",
                used=credits.used,
                limit=credits.limit,
                period_end=credits.period_end,
            ),
            UsageMeter(
                metric="scheduled_posts",
                used=posts.used if posts else 0,
                limit=posts.limit if posts else posts_limit,
                period_end=posts_end,
            ),
            UsageMeter(
                metric="knowledge_characters",
                used=int(characters or 0),
                limit=entitlement(plan, "knowledge_characters"),
            ),
        ],
    )
