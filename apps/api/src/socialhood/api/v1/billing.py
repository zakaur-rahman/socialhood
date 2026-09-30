"""Billing (§2.15; TR-BIL-01…06, FR-BIL-01…07, F-15, §5.10 BillingState).

GET …/billing is the UI's only source for plan, status, entitlements, usage and prices. The
owner's actions (checkout, portal, cancel, resume) hand over to Dodo; none of them changes the
plan: Dodo's signed webhook does (webhooks/dodo.py, TR-BIL-02). The public plan list serves
/pricing and the upgrade dialog's comparison.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request

from socialhood.api import ratelimit
from socialhood.auth.deps import AnyMember, Owner, Session
from socialhood.billing.dodo import DodoClient
from socialhood.billing.registry import get_dodo
from socialhood.schemas.billing import (
    BillingState,
    CheckoutRequest,
    CheckoutSession,
    PlanList,
    PortalSession,
)
from socialhood.services import billing as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["billing"])
public_router = APIRouter(prefix="/v1/billing", tags=["billing"])


def _dodo(request: Request) -> DodoClient:
    return get_dodo(request.app.state.http, request.app.state.settings)


async def _state(request: Request, ctx: AnyMember, session: Session) -> BillingState:
    prices = await service.plan_prices(
        request.app.state.redis, _dodo(request), request.app.state.settings
    )
    return await service.billing_state(session, ctx.workspace, now=datetime.now(UTC), prices=prices)


@router.get("/billing", operation_id="get_billing")
async def get_billing(request: Request, ctx: AnyMember, session: Session) -> BillingState:
    """Plan, status, entitlements, usage (AI credits and scheduled posts this period; knowledge
    characters, active automations, pending scheduled messages and connected accounts per
    platform counted live), trial eligibility (TR-BIL-05) and the paid plans' prices from Dodo
    (cached 1 h; a price Dodo can't give now is left out)."""
    return await _state(request, ctx, session)


@router.post("/billing/checkout", operation_id="create_billing_checkout")
async def create_billing_checkout(
    request: Request, body: CheckoutRequest, ctx: Owner, session: Session
) -> CheckoutSession:
    """F-15, TR-BIL-01: a Dodo hosted checkout for ``plan`` with the owner's email, returning to
    /w/{slug}/settings/billing?checkout=return, ``metadata.workspace_id`` set, and the 7-day trial
    only when eligible (TR-BIL-05). 409 conflict when the workspace already has a paid plan
    (active, trialing or on hold): the portal changes it. 422 for ``max`` until R2. 503 when Dodo
    isn't configured or doesn't answer. Nothing changes until Dodo's signed webhook arrives."""
    return await service.start_checkout(
        session, ctx, body, dodo=_dodo(request), settings=request.app.state.settings
    )


@router.post("/billing/portal", operation_id="create_billing_portal")
async def create_billing_portal(request: Request, ctx: Owner, session: Session) -> PortalSession:
    """FR-BIL-04, TR-BIL-06: a Dodo customer portal session (payment method, invoices), opened
    in a new tab. 409 conflict when the workspace has never had a Dodo customer; 503 when Dodo
    doesn't answer."""
    return await service.open_portal(
        session, ctx, dodo=_dodo(request), settings=request.app.state.settings
    )


@router.post("/billing/cancel", operation_id="cancel_billing")
async def cancel_billing(request: Request, ctx: Owner, session: Session) -> BillingState:
    """FR-BIL-04, TR-BIL-06: cancel at the end of the period (Dodo's
    cancel_at_next_billing_date). The answer shows ``cancel_at_period_end: true``; the plan stays
    until the period ends (subscription.cancelled, then Free). 409 on the Free plan; cancelling
    again answers the same."""
    await service.set_cancel(session, request.app.state.redis, cancel=True, dodo=_dodo(request))
    return await _state(request, ctx, session)


@router.post("/billing/resume", operation_id="resume_billing")
async def resume_billing(request: Request, ctx: Owner, session: Session) -> BillingState:
    """Undo a cancellation before the period ends. 409 unless ``cancel_at_period_end``, or when
    Dodo has already ended the plan."""
    await service.set_cancel(session, request.app.state.redis, cancel=False, dodo=_dodo(request))
    return await _state(request, ctx, session)


@public_router.get("/plans", operation_id="list_billing_plans", dependencies=[ratelimit.PUBLIC])
async def list_billing_plans(request: Request) -> PlanList:
    """Public, no sign-in: Free, Pro and Max (``available: false`` until R2) with their §1.7
    entitlements and Dodo prices (cached 1 h; null when Dodo can't be reached), for the /pricing
    page and the upgrade dialog's comparison. The same numbers as GET …/billing."""
    return await service.plan_list(
        request.app.state.redis, _dodo(request), request.app.state.settings
    )
