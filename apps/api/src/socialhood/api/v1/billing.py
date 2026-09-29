"""Billing (§2.15; TR-BIL-01…06, FR-BIL-01…07, F-15, §5.10 BillingState).

GET …/billing is the UI's only source for plan, status, entitlements, usage and prices (T5.1;
P8 adds prices). The owner's actions (checkout, portal, cancel, resume) are the P8 contract:
each keeps its ``openapi_extra`` marker until T8.2 builds it, so the tenancy suite covers it then.
None of them changes the plan: Dodo's signed webhook does (webhooks/dodo.py, TR-BIL-02).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from socialhood.api.v1.ai import pending
from socialhood.auth.deps import AnyMember, Owner, Session
from socialhood.schemas.billing import (
    BillingState,
    CheckoutRequest,
    CheckoutSession,
    PlanList,
    PortalSession,
)
from socialhood.services.billing import billing_state

router = APIRouter(prefix="/v1/w/{wid}", tags=["billing"])
public_router = APIRouter(prefix="/v1/billing", tags=["billing"])


@router.get("/billing", operation_id="get_billing")
async def get_billing(ctx: AnyMember, session: Session) -> BillingState:
    """Plan, status, entitlements, usage (AI credits, scheduled posts, knowledge characters),
    trial eligibility (TR-BIL-05) and, from T8.2, the paid plans' prices from Dodo (cached 1 h;
    empty when Dodo can't be reached)."""
    return await billing_state(session, ctx.workspace, now=datetime.now(UTC))


@router.post(
    "/billing/checkout", operation_id="create_billing_checkout", openapi_extra=pending("T8.2")
)
async def create_billing_checkout(
    body: CheckoutRequest, ctx: Owner, session: Session
) -> CheckoutSession:
    """F-15, TR-BIL-01: a Dodo hosted checkout for ``plan`` with the owner's email, returning to
    /w/{slug}/settings/billing?checkout=return, ``metadata.workspace_id`` set, and the 7-day trial
    only when eligible (TR-BIL-05). 409 conflict when the workspace already has a paid plan
    (active, trialing or on hold): the portal changes it. 422 for ``max`` until R2. 503 when Dodo
    isn't configured or doesn't answer."""
    raise NotImplementedError("T8.2")


@router.post("/billing/portal", operation_id="create_billing_portal", openapi_extra=pending("T8.2"))
async def create_billing_portal(ctx: Owner, session: Session) -> PortalSession:
    """FR-BIL-04, TR-BIL-06: a Dodo customer portal session (payment method, invoices), opened
    in a new tab. 409 conflict when the workspace has never had a Dodo customer."""
    raise NotImplementedError("T8.2")


@router.post("/billing/cancel", operation_id="cancel_billing", openapi_extra=pending("T8.2"))
async def cancel_billing(ctx: Owner, session: Session) -> BillingState:
    """FR-BIL-04, TR-BIL-06: cancel at the end of the period (Dodo's
    cancel_at_next_billing_date). The answer shows ``cancel_at_period_end: true``; the plan stays
    until the period ends (subscription.cancelled, then expired). 409 on the Free plan."""
    raise NotImplementedError("T8.2")


@router.post("/billing/resume", operation_id="resume_billing", openapi_extra=pending("T8.2"))
async def resume_billing(ctx: Owner, session: Session) -> BillingState:
    """Undo a cancellation before the period ends. 409 unless ``cancel_at_period_end``."""
    raise NotImplementedError("T8.2")


@public_router.get("/plans", operation_id="list_billing_plans", openapi_extra=pending("T8.2"))
async def list_billing_plans() -> PlanList:
    """Public, no sign-in: Free, Pro and Max (``available: false`` until R2) with their §1.7
    entitlements and Dodo prices (cached 1 h), for the /pricing page and the upgrade dialog's
    comparison. The same numbers as GET …/billing."""
    raise NotImplementedError("T8.2")
