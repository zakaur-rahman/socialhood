"""Billing (T5.1, T8.1-T8.3; TR-BIL-01, 04, 05, 06, FR-BIL-01…05, F-15, §5.10 BillingState).

``billing_state`` is the UI's only source for the plan, its entitlements, usage and prices.
Usage: ``ai_credits`` is the current credit period's counter and ``scheduled_posts`` the posts
scheduled this period (both reset on the billing anchor day, ``period_end``); the capacity meters
(knowledge characters, active automations, pending scheduled messages, connected accounts per
platform) are counted live (§5.8).

The owner's actions hand over to Dodo and never change the plan (FR-BIL-02, D9): checkout
returns Dodo's hosted page, the portal its customer portal; cancel and resume set Dodo's
cancel_at_next_billing_date and mirror Dodo's answer in ``cancel_at_period_end``. The plan and
status change only when Dodo's signed webhook arrives (billing/lifecycle.py).

Prices come from Dodo's products (TR-BIL-06), cached in Valkey for an hour; a price Dodo can't
give now is left out (GET …/billing) or null (the public plan list), never guessed.

C-149: billing is optional. Without the Dodo settings (``Settings.billing_enabled`` false) nothing
here calls Dodo: the paid plans are listed as unavailable without prices, ``billing_available`` is
false, and checkout, the portal, cancel and resume answer 503 ``billing_unavailable``. Every
workspace stays on Free, and no trial can start (a trial only ever starts through a checkout).
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.ai.metering import quota
from socialhood.auth.deps import WorkspaceContext
from socialhood.billing.dodo import CheckoutParams, DodoClient, DodoError, ProductPrice
from socialhood.billing.entitlements import allows, count_channels
from socialhood.billing.plans import (
    ENTITLEMENTS,
    PAID_PLANS,
    PERIODS,
    PLAN_NAMES,
    PLANS,
    TRIAL_DAYS,
    accounts_limit,
    entitlement,
    is_available,
    offer_for_product,
    product_for,
    trial_days_for,
)
from socialhood.billing.usage import live_used, period_used
from socialhood.errors import ApiError, FieldError
from socialhood.models.billing import Plan
from socialhood.models.connections import Platform
from socialhood.models.identity import Workspace
from socialhood.observability.logging import get_logger
from socialhood.realtime import events
from socialhood.repositories import payments, social_accounts, subscriptions, workspaces
from socialhood.repositories.subscriptions import LIVE_STATUSES
from socialhood.schemas.billing import (
    BillingPrice,
    BillingState,
    CheckoutRequest,
    CheckoutSession,
    EntitlementValue,
    PaymentList,
    PaymentOut,
    PlanList,
    PlanOffer,
    PortalSession,
    UsageMeter,
)
from socialhood.security.signatures import sign_checkout_workspace
from socialhood.services.conversations import decode_cursor, encode_cursor
from socialhood.settings import Settings

log = get_logger(__name__)

PRICE_TTL_S = 3600  # TR-BIL-06: prices cached for 1 h
PRICE_FAILURE_TTL_S = 60
DODO_UNAVAILABLE = "The payment provider didn't answer. Try again in a moment."
NOT_CONFIGURED = "Payments aren't set up yet."
FREE_PLAN = "You're on the Free plan."
BILLING_OFF = "Paid plans aren't available yet."


def require_billing(settings: Settings) -> None:
    """C-149: 503 billing_unavailable while billing isn't set up on this server."""
    if not settings.billing_enabled:
        raise ApiError("billing_unavailable", BILLING_OFF)


def _value(value: Any) -> int | bool | list[str] | None:
    return list(value) if isinstance(value, tuple) else value


def entitlements_of(plan: str) -> list[EntitlementValue]:
    return [EntitlementValue(key=key, value=_value(entitlement(plan, key))) for key in ENTITLEMENTS]


# ---------------------------------------------------------------- prices (TR-BIL-06)


async def _cache(redis: Redis | None, key: str, value: str, ttl_s: int) -> None:
    if redis is None:
        return
    try:
        await redis.set(key, value, ex=ttl_s)
    except Exception:
        log.warning("dodo_price_cache_failed")


async def _price(redis: Redis | None, dodo: DodoClient, product_id: str) -> ProductPrice | None:
    """The product's price, cached for an hour; a failure is remembered for a minute, so the
    public plan list can't make every visitor wait on (or hammer) Dodo while it is down."""
    key = f"dodo:price:{product_id}"
    if redis is not None:
        try:
            cached = await redis.get(key)
        except Exception:
            cached = None
        if cached:
            data = json.loads(cached)
            return ProductPrice(**data) if data else None
    try:
        price = await dodo.get_product_price(product_id)
    except DodoError as error:
        log.warning("dodo_price_unavailable", status=error.status, retryable=error.retryable)
        await _cache(redis, key, "null", PRICE_FAILURE_TTL_S)
        return None
    await _cache(redis, key, json.dumps(dataclasses.asdict(price)), PRICE_TTL_S)
    return price


async def plan_prices(
    redis: Redis | None, dodo: DodoClient, settings: Settings
) -> dict[tuple[str, str], BillingPrice]:
    """Each (plan, period) on sale and its price from the Dodo product, when Dodo gives one (none,
    and no call to Dodo, while billing is off). A plan without its monthly product has none, and a
    product that doesn't bill the way its setting says is left out, never sold as that period."""
    prices: dict[tuple[str, str], BillingPrice] = {}
    if not settings.billing_enabled:
        return prices
    for plan in PAID_PLANS:
        if not is_available(plan, settings):
            continue
        for period in PERIODS:
            product = product_for(plan, settings, period)
            price = await _price(redis, dodo, product) if product else None
            if price is None:
                continue
            if price.interval != period:
                log.warning("dodo_product_wrong_period", plan=plan, period=period)
                continue
            prices[(plan, period)] = BillingPrice(
                plan=plan,
                amount_minor=price.amount_minor,
                currency=price.currency,
                interval=price.interval,
            )
    return prices


async def plan_list(redis: Redis | None, dodo: DodoClient, settings: Settings) -> PlanList:
    """The public plan list: §1.7 entitlements, Dodo prices, the trial, and availability (a paid
    plan is unavailable while billing is off, C-149)."""
    prices = await plan_prices(redis, dodo, settings)
    on_sale = settings.billing_enabled
    return PlanList(
        items=[
            PlanOffer(
                plan=plan,
                price=prices.get((plan, "month")),
                six_month_price=prices.get((plan, "six_month")),
                trial_days=TRIAL_DAYS[plan],
                entitlements=entitlements_of(plan),
                available=plan == "free" or (on_sale and is_available(plan, settings)),
            )
            for plan in PLANS
        ]
    )


# ---------------------------------------------------------------- state


async def billing_state(
    session: AsyncSession,
    workspace: Workspace,
    *,
    now: datetime,
    prices: dict[tuple[str, str], BillingPrice] | None = None,
    billing_available: bool,
    settings: Settings,
) -> BillingState:
    """The current workspace's billing state (its session's workspace scope)."""
    sub = await subscriptions.current(session)
    plan = sub.plan if sub is not None else Plan.FREE
    bought = offer_for_product(sub.dodo_product_id, settings) if sub is not None else None
    credits = await quota(session, now=now)
    posts_used, posts_limit = await period_used(
        session, "scheduled_posts_monthly", today=now.date()
    )
    posts_end = credits.period_end  # both allowances share the anchor day
    meters = [
        UsageMeter(
            metric="ai_credits",
            used=credits.used,
            limit=credits.limit,
            period_end=credits.period_end,
        ),
        UsageMeter(
            metric="scheduled_posts", used=posts_used, limit=posts_limit, period_end=posts_end
        ),
        UsageMeter(
            metric="knowledge_characters",
            used=await live_used(session, "knowledge_characters"),
            limit=entitlement(plan, "knowledge_characters"),
        ),
        UsageMeter(
            metric="active_automations",
            used=await live_used(session, "active_automations"),
            limit=entitlement(plan, "active_automations"),
        ),
        UsageMeter(
            metric="pending_scheduled_messages",
            used=await live_used(session, "pending_scheduled_messages"),
            limit=entitlement(plan, "pending_scheduled_messages"),
        ),
    ]
    whatsapp_used = await social_accounts.count_live(session, Platform.WHATSAPP)
    total = entitlement(plan, "channels_total")
    if total is not None:
        # C-172: Free counts channels in total, so the page shows "1 of 2 channels".
        meters.append(
            UsageMeter(
                metric="channels",
                used=await count_channels(session),
                limit=total,
            )
        )
    for platform in (Platform.INSTAGRAM, Platform.WHATSAPP, Platform.FACEBOOK):
        if platform == Platform.WHATSAPP and not allows(plan, "whatsapp") and not whatsapp_used:
            continue  # no WhatsApp tile where the plan has none
        if total is not None and platform != Platform.WHATSAPP:
            continue  # the "channels" tile stands for them where a total applies (Free)
        meters.append(
            UsageMeter(
                metric=f"{platform.value}_accounts",
                used=await social_accounts.count_live(session, platform),
                limit=accounts_limit(plan, platform),
            )
        )
    return BillingState(
        plan=plan,
        status=sub.status if sub is not None else "free",
        current_period_end=sub.current_period_end if sub is not None else None,
        trial_ends_at=sub.trial_ends_at if sub is not None else None,
        cancel_at_period_end=sub.cancel_at_period_end if sub is not None else False,
        grace_until=sub.grace_until if sub is not None else None,
        trial_eligible=not await workspaces.trial_used_by_owner(session, workspace),
        prices=list((prices or {}).values()),
        current_price=(prices or {}).get(bought) if bought and plan != Plan.FREE else None,
        billing_available=billing_available,
        entitlements=entitlements_of(plan),
        usage=meters,
    )


# ---------------------------------------------------------------- payment history (C-066)


async def payment_history(session: AsyncSession, *, cursor: str | None, limit: int) -> PaymentList:
    """The workspace's Dodo payments (§5.8), newest first, ``limit`` a page."""
    rows = await payments.page(
        session, before=decode_cursor(cursor) if cursor else None, limit=limit
    )
    page = rows[:limit]
    return PaymentList(
        items=[PaymentOut.model_validate(row) for row in page],
        next_cursor=(
            encode_cursor(page[-1].occurred_at, page[-1].id) if len(rows) > limit else None
        ),
    )


# ---------------------------------------------------------------- the owner's actions


def _web_base(settings: Settings) -> str:
    if not settings.web_base_url:
        raise ApiError("service_unavailable", NOT_CONFIGURED)
    return settings.web_base_url.rstrip("/")


def _billing_url(settings: Settings, workspace: Workspace) -> str:
    return f"{_web_base(settings)}/w/{workspace.slug}/settings/billing"


async def start_checkout(
    session: AsyncSession,
    ctx: WorkspaceContext,
    body: CheckoutRequest,
    *,
    dodo: DodoClient,
    settings: Settings,
) -> CheckoutSession:
    """TR-BIL-01: Dodo's hosted checkout for ``body.plan`` and ``body.period``. The return URL
    changes nothing by itself (FR-BIL-02): the plan changes with Dodo's signed webhook."""
    require_billing(settings)
    name = PLAN_NAMES.get(body.plan, body.plan.capitalize())
    if not is_available(body.plan, settings):
        raise ApiError(
            "validation_error",
            errors=[FieldError("plan", f"{name} isn't available yet.")],
        )
    if product_for(body.plan, settings, body.period) is None:
        raise ApiError(
            "validation_error",
            errors=[FieldError("period", f"{name} isn't available every 6 months yet.")],
        )
    sub = await subscriptions.current(session)
    if sub is not None and sub.plan != Plan.FREE and sub.status in LIVE_STATUSES:
        raise ApiError(
            "conflict", "This workspace already has a paid plan. Change it in Manage billing."
        )
    product = product_for(body.plan, settings, body.period)
    if product is None:
        raise ApiError("service_unavailable", NOT_CONFIGURED)
    eligible = not await workspaces.trial_used_by_owner(session, ctx.workspace)
    trial_days = trial_days_for(body.plan, body.period) if eligible else 0
    params = CheckoutParams(
        product_id=product,
        customer_email=ctx.user.email,
        customer_name=ctx.user.name,
        return_url=_billing_url(settings, ctx.workspace) + "?checkout=return",
        metadata={
            "workspace_id": str(ctx.workspace_id),
            "workspace_sig": sign_checkout_workspace(
                str(ctx.workspace_id), settings.token_encryption_keys
            ),
        },
        # Always sent: the product's own trial applies when it's left out (TR-BIL-05).
        trial_period_days=trial_days,
    )
    await session.commit()  # nothing stays open while Dodo answers
    try:
        checkout = await dodo.create_checkout(params)
    except DodoError as error:
        log.warning("dodo_checkout_failed", status=error.status, retryable=error.retryable)
        raise ApiError("service_unavailable", DODO_UNAVAILABLE) from error
    log.info("billing_checkout_started", plan=body.plan, period=body.period, trial=trial_days > 0)
    return CheckoutSession(checkout_url=checkout.checkout_url, trial=trial_days > 0)


async def open_portal(
    session: AsyncSession, ctx: WorkspaceContext, *, dodo: DodoClient, settings: Settings
) -> PortalSession:
    """FR-BIL-04: Dodo's customer portal (payment method, invoices)."""
    require_billing(settings)
    sub = await subscriptions.current(session)
    if sub is None or not sub.dodo_customer_id:
        raise ApiError("conflict", "There's no billing account yet. Upgrade to create one.")
    return_url = _billing_url(settings, ctx.workspace)
    customer_id = sub.dodo_customer_id
    await session.commit()
    try:
        link = await dodo.create_portal_session(customer_id, return_url=return_url)
    except DodoError as error:
        log.warning("dodo_portal_failed", status=error.status, retryable=error.retryable)
        raise ApiError("service_unavailable", DODO_UNAVAILABLE) from error
    return PortalSession(portal_url=link)


async def set_cancel(
    session: AsyncSession, redis: Redis, *, cancel: bool, dodo: DodoClient, settings: Settings
) -> None:
    """FR-BIL-04, TR-BIL-06: cancel at the end of the period, or resume before it. 409 on the
    Free plan, or (resume) when nothing is cancelled. The plan itself stays until Dodo ends it."""
    require_billing(settings)
    sub = await subscriptions.current(session)
    if (
        sub is None
        or sub.plan == Plan.FREE
        or sub.status not in LIVE_STATUSES
        or not sub.dodo_subscription_id
    ):
        raise ApiError("conflict", FREE_PLAN)
    if sub.cancel_at_period_end == cancel:
        if cancel:
            return  # already cancelling: the same answer again
        raise ApiError("conflict", "The plan isn't cancelled.")
    subscription_id = sub.dodo_subscription_id
    await session.commit()
    try:
        snapshot = await dodo.set_cancel_at_period_end(subscription_id, cancel)
    except DodoError as error:
        log.warning("dodo_cancel_failed", status=error.status, cancel=cancel)
        if error.retryable or error.status is None:
            raise ApiError("service_unavailable", DODO_UNAVAILABLE) from error
        raise ApiError("conflict", "Dodo refused the change; the plan may have ended.") from error
    sub = await subscriptions.current(session, for_update=True)
    if sub is not None and sub.dodo_subscription_id == snapshot.subscription_id:
        sub.cancel_at_period_end = snapshot.cancel_at_next_billing_date
        await _queue_billing_changed(session)
    await events.commit_and_publish(session, redis)
    log.info("billing_cancel_set", cancel=cancel)


async def _queue_billing_changed(session: AsyncSession) -> None:
    """usage.updated, on which every open billing page refetches (C-049)."""
    credits = await quota(session)
    sub = await subscriptions.current(session)
    if sub is None:
        return
    events.queue(
        session,
        sub.workspace_id,
        "usage.updated",
        {
            "metric": "ai_credits",
            "used": credits.used,
            "limit": credits.limit,
            "period_end": credits.period_end.isoformat(),
        },
    )
