"""Plan gates (T8.1; TR-BIL-04, FR-BIL-05, FR-BIL-07, §2.15 "Role · gate", §4.7).

Every 402 comes from here, so each carries its code and the §1.7 key (errors.PlanLimit):

- ``entitlement_required``: a feature the plan lacks (``PlanLimit(entitlement=key)``, limit null),
  e.g. Auto mode ("ai_modes") or AI-reply automations ("ai_reply_automations").
- ``quota_exceeded``: a limit the workspace has reached (``PlanLimit(entitlement=key, limit=n)``):
  a capacity counted live (accounts_per_platform, active_automations, knowledge_characters,
  pending_scheduled_messages) or a monthly allowance from usage_counters (ai_credits_monthly,
  scheduled_posts_monthly; billing/usage.py has the periods).

Three forms, the same 402 whichever answers:

- FastAPI dependencies for a gate that depends only on the route: ``require_entitlement(key,
  value)`` and ``require_capacity(key, adding=n)``. Each runs the route's role check first and
  returns its WorkspaceContext.
- Service-level checks for gates that depend on the body or on rows (the AI mode being set, an
  automation's action, a knowledge source's length, which account an action uses):
  ``check_entitlement``, ``check_capacity``, ``check_credits`` and ``check_account_writable``, or
  ``entitlement_error`` / ``quota_error`` where the service counts itself (a reconnect that keeps
  its slot, an automation's own slot, a post already counted this period). Every §2.15 gate is
  one of these today, because each depends on the body or on what the service loads.
- ``credits_gate`` around a service that checks AI credits after its own refusals (a 409 for AI
  that is off stays a 409): the routes §2.15 marks "credits" whose services predate P8.

The plan is always the workspace's subscription (billing/plans.py, never a copy). Accounts beyond
the plan's accounts_per_platform (after a downgrade, FR-BIL-07) are read-only: the earliest
connected accounts of each platform keep the plan's slots; the rest refuse scheduled messages and
automation activations (``check_account_writable``).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.ai.metering import Quota, quota
from socialhood.auth.deps import Session, WorkspaceContext, require_role
from socialhood.billing.plans import current_plan, entitlement
from socialhood.billing.usage import PERIOD_KEYS, live_used, period_used
from socialhood.errors import ApiError, PlanLimit
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.identity import Role

CREDITS = "ai_credits_monthly"

# §4.7 entitlement_required: "{Feature} is part of Pro."
FEATURES = {
    "ai_modes": "Auto mode is part of Pro.",
    "ai_reply_automations": "AI replies in automations are part of Pro.",
}
# §4.7 quota_exceeded: "Your plan includes {limit} {thing}."
THINGS = {
    "active_automations": "active automations",
    "pending_scheduled_messages": "scheduled messages",
    "scheduled_posts_monthly": "scheduled posts a month",
    "knowledge_characters": "characters of knowledge",
    "members": "members",
}


# ---------------------------------------------------------------- the 402s


def entitlement_error(key: str, detail: str | None = None) -> ApiError:
    return ApiError(
        "entitlement_required",
        detail or FEATURES.get(key, "This feature is part of Pro."),
        plan_limit=PlanLimit(entitlement=key),
    )


def quota_error(key: str, limit: int | None, detail: str | None = None) -> ApiError:
    if detail is None:
        thing = THINGS.get(key, key.replace("_", " "))
        detail = f"Your plan includes {limit:,} {thing}." if limit is not None else None
    return ApiError("quota_exceeded", detail, plan_limit=PlanLimit(entitlement=key, limit=limit))


def credits_error(credits: Quota) -> ApiError:
    """§4.7: "You've used all {limit} AI credits for this month. They reset on {date}." """
    end = credits.period_end
    return quota_error(
        CREDITS,
        credits.limit,
        f"You've used all {credits.limit or 0:,} AI credits for this month. "
        f"They reset on {end.day} {end:%B}.",
    )


# ---------------------------------------------------------------- service-level checks


def allows(plan: str, key: str, value: Any = None) -> bool:
    """Whether ``plan`` includes the feature ``key`` (or ``value`` among its options)."""
    granted = entitlement(plan, key)
    if value is None:
        return bool(granted)
    return value in granted


async def check_entitlement(
    session: AsyncSession,
    key: str,
    value: Any = None,
    *,
    plan: str | None = None,
    detail: str | None = None,
) -> None:
    """Raise 402 entitlement_required unless the current workspace's plan includes it."""
    if not allows(plan or await current_plan(session), key, value):
        raise entitlement_error(key, detail)


async def check_credits(session: AsyncSession, cost: int, *, now: datetime | None = None) -> Quota:
    """Raise 402 quota_exceeded unless ``cost`` AI credits are left this period. The metering
    (ai/metering.py) still reserves them atomically when the model runs."""
    credits = await quota(session, now=now)
    if not credits.allows(cost):
        raise credits_error(credits)
    return credits


async def check_capacity(
    session: AsyncSession,
    key: str,
    *,
    adding: int = 1,
    plan: str | None = None,
    detail: str | None = None,
) -> None:
    """Raise 402 quota_exceeded unless ``adding`` more fits under the plan's limit."""
    if key == CREDITS:
        await check_credits(session, adding)
        return
    if key in PERIOD_KEYS:
        used, limit = await period_used(session, key, today=datetime.now(UTC).date())
    else:
        limit = entitlement(plan or await current_plan(session), key)
        used = 0 if limit is None else await live_used(session, key)
    if limit is not None and used + adding > limit:
        raise quota_error(key, int(limit), detail)


# ---------------------------------------------------------------- read-only accounts (FR-BIL-07)


def _noun(limit: int, platform: str) -> str:
    return f"{limit} {platform.capitalize()} account{'' if limit == 1 else 's'}"


async def read_only_accounts(session: AsyncSession, *, plan: str | None = None) -> set[uuid.UUID]:
    """Connected accounts beyond the plan's accounts_per_platform: each platform's earliest
    connected accounts keep the plan's slots."""
    limit = entitlement(plan or await current_plan(session), "accounts_per_platform")
    if limit is None:
        return set()
    rows = (
        await session.execute(
            select(SocialAccount.id, SocialAccount.platform)
            .where(SocialAccount.status != AccountStatus.DISCONNECTED)
            .order_by(
                SocialAccount.connected_at.asc().nulls_last(),
                SocialAccount.created_at,
                SocialAccount.id,
            )
        )
    ).all()
    seen: dict[str, int] = {}
    extra: set[uuid.UUID] = set()
    for account_id, platform in rows:
        seen[platform] = seen.get(platform, 0) + 1
        if seen[platform] > limit:
            extra.add(account_id)
    return extra


async def check_account_writable(
    session: AsyncSession, account: SocialAccount, *, plan: str | None = None
) -> None:
    """402 quota_exceeded when ``account`` is read-only on this plan (FR-BIL-07): it can be read
    and disconnected, not used to send or publish."""
    plan = plan or await current_plan(session)
    if account.id not in await read_only_accounts(session, plan=plan):
        return
    limit = int(entitlement(plan, "accounts_per_platform"))
    name = f"@{account.username}" if account.username else "This account"
    raise quota_error(
        "accounts_per_platform",
        limit,
        f"Your plan includes {_noun(limit, account.platform)}. {name} is read-only until you "
        "upgrade or disconnect another.",
    )


@asynccontextmanager
async def credits_gate(session: AsyncSession) -> AsyncIterator[None]:
    """Around a service whose own credits check comes after its other checks (a 409 for AI
    that's off stays a 409): a quota_exceeded it raises leaves as the §4.7 credits 402 with the
    plan's limit (PlanLimit ai_credits_monthly). Other errors pass through unchanged."""
    try:
        yield
    except ApiError as error:
        if error.code != "quota_exceeded" or error.plan_limit is not None:
            raise
        raise credits_error(await quota(session)) from error


# ---------------------------------------------------------------- FastAPI dependencies


Dependency = Callable[..., Awaitable[WorkspaceContext]]


def require_entitlement(key: str, value: Any = None, *, role: Role = Role.ADMIN) -> Dependency:
    """A route gate: 402 entitlement_required unless the plan includes ``key`` (or ``value``
    among its options), after the ``role`` check."""

    role_check = require_role(role)

    async def dependency(
        session: Session,
        ctx: WorkspaceContext = Depends(role_check),  # noqa: B008 (a closure: no Annotated)
    ) -> WorkspaceContext:
        await check_entitlement(session, key, value)
        return ctx

    return dependency


def require_capacity(key: str, *, adding: int = 1, role: Role = Role.ADMIN) -> Dependency:
    """A route gate: 402 quota_exceeded unless ``adding`` more of ``key`` fits (for
    ai_credits_monthly, ``adding`` is the feature's credit cost), after the ``role`` check."""

    role_check = require_role(role)

    async def dependency(
        session: Session,
        ctx: WorkspaceContext = Depends(role_check),  # noqa: B008 (a closure: no Annotated)
    ) -> WorkspaceContext:
        await check_capacity(session, key, adding=adding)
        return ctx

    return dependency
