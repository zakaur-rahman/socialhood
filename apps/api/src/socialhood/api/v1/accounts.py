"""Connected accounts (FR-CON-01…06), the Instagram connect start (F-03) and sandbox tools
(TR-PL-07)."""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from socialhood.auth.deps import Admin, AnyMember, Owner, Session
from socialhood.billing.plans import current_plan
from socialhood.errors import ApiError
from socialhood.models.platform import WebhookProvider
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.platforms.instagram.webhooks import split_payload
from socialhood.platforms.sandbox.adapter import is_sandbox
from socialhood.repositories import social_accounts as accounts
from socialhood.schemas.accounts import (
    ConnectStart,
    SandboxInbound,
    SandboxInboundResult,
    SocialAccountList,
    SocialAccountOut,
    SocialAccountPatch,
)
from socialhood.services import connections as service
from socialhood.services.webhook_intake import store_and_enqueue

router = APIRouter(prefix="/v1/w/{wid}", tags=["accounts"])


def _deps(request: Request) -> PlatformDeps:
    return deps_from(request.app.state.http, request.app.state.settings)


@router.get("/social-accounts", operation_id="list_social_accounts")
async def list_social_accounts(
    request: Request, ctx: AnyMember, session: Session
) -> SocialAccountList:
    deps = _deps(request)
    items = [service.account_out(a, deps) for a in await accounts.list_all(session)]
    return SocialAccountList(items=items)


@router.post("/social-accounts/instagram/connect", operation_id="start_instagram_connect")
async def start_instagram_connect(request: Request, ctx: Admin, session: Session) -> ConnectStart:
    url = await service.start_instagram_connect(
        session,
        request.app.state.redis,
        _deps(request),
        workspace_id=ctx.workspace_id,
        slug=ctx.workspace.slug,
        user_id=ctx.user.id,
        plan=await current_plan(session),
    )
    return ConnectStart(authorize_url=url)


@router.patch("/social-accounts/{account_id}", operation_id="update_social_account")
async def update_social_account(
    request: Request, account_id: uuid.UUID, body: SocialAccountPatch, ctx: Admin, session: Session
) -> SocialAccountOut:
    acct = await service.get_or_404(session, account_id)
    acct = await service.update_account(session, acct, body, plan=await current_plan(session))
    return service.account_out(acct, _deps(request))


@router.delete(
    "/social-accounts/{account_id}", status_code=204, operation_id="disconnect_social_account"
)
async def disconnect_social_account(
    request: Request,
    account_id: uuid.UUID,
    ctx: Admin,
    session: Session,
    delete_data: Annotated[bool, Query()] = False,
) -> Response:
    acct = await service.get_or_404(session, account_id)
    await service.disconnect(session, request.app.state.redis, acct, delete_data=delete_data)
    return Response(status_code=204)


@router.post("/social-accounts/{account_id}/resubscribe", operation_id="resubscribe_social_account")
async def resubscribe_social_account(
    request: Request, account_id: uuid.UUID, ctx: Admin, session: Session
) -> SocialAccountOut:
    """Retry the webhook subscription after it failed (F-03 edge case)."""
    acct = await service.get_or_404(session, account_id)
    await service.subscribe(session, acct, _deps(request))
    await session.commit()
    await session.refresh(acct)
    return service.account_out(acct, _deps(request))


# ---------------------------------------------------------------- sandbox (dev only)


def _require_sandbox(request: Request) -> None:
    if not request.app.state.settings.sandbox_platform_enabled:
        raise ApiError("not_found")


@router.post("/dev/sandbox/accounts", status_code=201, operation_id="create_sandbox_account")
async def create_sandbox_account(
    request: Request, ctx: Owner, session: Session
) -> SocialAccountOut:
    """Connect a fake Instagram account for local development."""
    _require_sandbox(request)
    acct = await service.connect_sandbox(
        session, _deps(request), user_id=ctx.user.id, plan=await current_plan(session)
    )
    return service.account_out(acct, _deps(request))


@router.post("/dev/sandbox/inbound", operation_id="sandbox_inbound")
async def sandbox_inbound(
    request: Request, body: SandboxInbound, ctx: Owner, session: Session
) -> SandboxInboundResult:
    """Inject a fake DM or comment. It goes through the same intake as a real webhook."""
    _require_sandbox(request)
    acct = await service.get_or_404(session, body.account_id)
    if not is_sandbox(acct):
        raise ApiError("conflict", "Only sandbox accounts accept injected events.")
    payload = _sandbox_payload(acct.platform_account_id, body)
    stored = await store_and_enqueue(session, WebhookProvider.INSTAGRAM, split_payload(payload))
    return SandboxInboundResult(stored=len(stored))


def _sandbox_payload(account_ref: str, body: SandboxInbound) -> dict[str, object]:
    sender = body.from_id or f"sandbox_user_{secrets.token_hex(3)}"
    now_ms = int(time.time() * 1000)
    if body.kind == "dm":
        item: dict[str, object] = {
            "sender": {"id": sender},
            "recipient": {"id": account_ref},
            "timestamp": now_ms,
            "message": {"mid": f"sandbox_mid_{secrets.token_hex(8)}", "text": body.text},
        }
        entry: dict[str, object] = {"id": account_ref, "time": now_ms // 1000, "messaging": [item]}
    else:
        value = {
            "id": f"sandbox_comment_{secrets.token_hex(8)}",
            "text": body.text,
            "from": {"id": sender, "username": body.from_username or "sandbox_customer"},
            "media": {"id": "sandbox_media_1", "media_product_type": "FEED"},
            "timestamp": datetime.now(UTC).isoformat(),
        }
        entry = {
            "id": account_ref,
            "time": now_ms // 1000,
            "changes": [{"field": "comments", "value": value}],
        }
    return {"object": "instagram", "entry": [entry]}
