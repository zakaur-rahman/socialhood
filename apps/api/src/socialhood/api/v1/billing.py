"""GET …/billing (TR-BIL-04, §5.10 BillingState): the UI's only source for plan, entitlements and
usage. P5 serves it for the AI credit banner (FR-AI-05); checkout and prices arrive in P8.

The signature below is the P5 contract; T5.1 implements the body.
"""

from __future__ import annotations

from fastapi import APIRouter

from socialhood.api.v1.ai import pending
from socialhood.auth.deps import AnyMember, Session
from socialhood.schemas.billing import BillingState

router = APIRouter(prefix="/v1/w/{wid}", tags=["billing"])


@router.get("/billing", operation_id="get_billing", openapi_extra=pending("T5.1"))
async def get_billing(ctx: AnyMember, session: Session) -> BillingState:
    raise NotImplementedError("T5.1")
