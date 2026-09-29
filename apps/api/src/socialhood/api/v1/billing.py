"""GET …/billing (T5.1; TR-BIL-04, §5.10 BillingState): the UI's only source for plan,
entitlements and usage. P5 serves it for the AI credit banner (FR-AI-05); checkout, the portal and
prices arrive in P8.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from socialhood.auth.deps import AnyMember, Session
from socialhood.schemas.billing import BillingState
from socialhood.services.billing import billing_state

router = APIRouter(prefix="/v1/w/{wid}", tags=["billing"])


@router.get("/billing", operation_id="get_billing")
async def get_billing(ctx: AnyMember, session: Session) -> BillingState:
    """Plan, status, entitlements, usage (AI credits, scheduled posts, knowledge characters) and
    trial eligibility (TR-BIL-05). Prices are empty until P8."""
    return await billing_state(session, ctx.workspace, now=datetime.now(UTC))
