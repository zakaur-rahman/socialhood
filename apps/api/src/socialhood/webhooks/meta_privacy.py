"""Meta privacy callbacks (FR-PRV-01, F-16): deauthorize and data deletion.

Both send a form field ``signed_request`` signed with an app secret. Which secret signs the
Instagram Login callbacks is a T0.9 question, so both the Instagram and Meta app secrets are tried.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

from socialhood.auth.deps import Session
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.jobs.enqueue import enqueue
from socialhood.models.platform import DataDeletionRequest
from socialhood.observability.logging import get_logger
from socialhood.repositories import social_accounts as accounts
from socialhood.security.signatures import parse_signed_request
from socialhood.services.connections import mark_disconnected_by_platform
from socialhood.settings import Settings
from socialhood.webhooks.routing import accounts_for_platform_user

router = APIRouter(prefix="/webhooks/meta", include_in_schema=False)
log = get_logger(__name__)


def _secrets(settings: Settings) -> list[str]:
    return [
        s.get_secret_value()
        for s in (settings.ig_app_secret, settings.meta_app_secret)
        if s is not None
    ]


def _verified(settings: Settings, signed_request: str) -> str:
    payload = parse_signed_request(signed_request, _secrets(settings))
    if payload is None or not payload.get("user_id"):
        log.warning("signed_request_invalid")
        raise ApiError("unauthorized")
    return str(payload["user_id"])


@router.post("/deauthorize")
async def deauthorize(
    request: Request, session: Session, signed_request: Annotated[str, Form(max_length=8192)]
) -> JSONResponse:
    """The user removed our app: delete tokens, mark disconnected, tell the owners."""
    user_id = _verified(request.app.state.settings, signed_request)
    for routed in await accounts_for_platform_user(session, user_id):
        with workspace_scope(routed.workspace_id):
            acct = await accounts.get(session, routed.account_id)
            if acct is not None:
                await mark_disconnected_by_platform(session, acct)
                await session.commit()
    return JSONResponse({})


@router.post("/data-deletion")
async def data_deletion(
    request: Request, session: Session, signed_request: Annotated[str, Form(max_length=8192)]
) -> JSONResponse:
    settings: Settings = request.app.state.settings
    user_id = _verified(settings, signed_request)
    code = secrets.token_urlsafe(12)
    session.add(
        DataDeletionRequest(confirmation_code=code, platform="instagram", platform_user_id=user_id)
    )
    await session.commit()
    from socialhood.jobs.tasks.privacy import delete_platform_user_data

    await enqueue(delete_platform_user_data, key=f"deletion:{code}", confirmation_code=code)
    web = (settings.web_base_url or "http://localhost:3000").rstrip("/")
    return JSONResponse({"url": f"{web}/data-deletion?code={code}", "confirmation_code": code})
