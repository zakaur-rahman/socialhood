"""WhatsApp connect and templates (T3.12; F-04, FR-CON-02, FR-INB-10).

The signatures below are the P3 contract; T3.12 implements the bodies.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.schemas.accounts import SocialAccountOut
from socialhood.schemas.whatsapp import EmbeddedSignup, WhatsAppTemplateList

router = APIRouter(prefix="/v1/w/{wid}", tags=["whatsapp"])


# Stub until T3.12 lands: the tenancy suite skips x-pending routes. Delete this and the
# openapi_extra arguments when implementing.
PENDING = {"x-pending": "T3.12"}


@router.post(
    "/social-accounts/whatsapp/embedded-signup",
    status_code=201,
    operation_id="complete_whatsapp_signup",
    openapi_extra=PENDING,
)
async def complete_whatsapp_signup(
    body: EmbeddedSignup, ctx: Admin, session: Session
) -> SocialAccountOut:
    raise NotImplementedError("T3.12")


@router.get(
    "/social-accounts/{account_id}/templates",
    operation_id="list_whatsapp_templates",
    openapi_extra=PENDING,
)
async def list_whatsapp_templates(
    account_id: uuid.UUID, ctx: AnyMember, session: Session
) -> WhatsAppTemplateList:
    """Approved message templates for the template picker (sends outside the 24 h window)."""
    raise NotImplementedError("T3.12")
