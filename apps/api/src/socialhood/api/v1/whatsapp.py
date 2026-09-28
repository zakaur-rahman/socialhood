"""WhatsApp connect and templates (T3.12; F-04, FR-CON-02, FR-INB-10)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from socialhood.auth.deps import Admin, AnyMember, Session
from socialhood.billing.plans import current_plan
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.schemas.accounts import SocialAccountOut
from socialhood.schemas.whatsapp import EmbeddedSignup, WhatsAppTemplateList
from socialhood.services import whatsapp_connect, whatsapp_templates
from socialhood.services.connections import account_out, get_or_404

router = APIRouter(prefix="/v1/w/{wid}", tags=["whatsapp"])


def _deps(request: Request) -> PlatformDeps:
    return deps_from(request.app.state.http, request.app.state.settings)


@router.post(
    "/social-accounts/whatsapp/embedded-signup",
    status_code=201,
    operation_id="complete_whatsapp_signup",
)
async def complete_whatsapp_signup(
    request: Request, body: EmbeddedSignup, ctx: Admin, session: Session
) -> SocialAccountOut:
    """Finish Embedded Signup: store the number and subscribe to its webhooks. 409
    account_in_use when the number is connected to another workspace."""
    deps = _deps(request)
    acct = await whatsapp_connect.complete_signup(
        session, deps, signup=body, user_id=ctx.user.id, plan=await current_plan(session)
    )
    return account_out(acct, deps)


@router.get(
    "/social-accounts/{account_id}/templates",
    operation_id="list_whatsapp_templates",
)
async def list_whatsapp_templates(
    request: Request, account_id: uuid.UUID, ctx: AnyMember, session: Session
) -> WhatsAppTemplateList:
    """Approved message templates for the template picker (sends outside the 24 h window)."""
    acct = await get_or_404(session, account_id)
    items = await whatsapp_templates.approved_templates(
        session, request.app.state.redis, _deps(request), acct
    )
    return WhatsAppTemplateList(items=items)
