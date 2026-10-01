"""Meta privacy callbacks (FR-PRV-01, F-16): deauthorize and data deletion.

Both send a form field ``signed_request`` signed with an app secret. Which secret signs the
Instagram Login callbacks is a T0.9 question, so both the Instagram and Meta app secrets are tried.
The payload's ``user_id`` is the person who connected their account through Instagram (or
Facebook) Login: their accounts are found in every workspace by that id (the tenant bypass, in
webhooks/routing.py).

- Deauthorize: they removed our app. Tokens are deleted, the accounts disconnected, the owners
  told; what was stored stays.
- Data deletion: they asked Meta to delete their data. A ``data_deletion_requests`` row with a
  confirmation code is stored ``received`` and ``delete_platform_user_data`` queued; the answer
  is Meta's ``{url, confirmation_code}``, the url being the public status page. The job
  disconnects every one of those accounts and purges each (C-067: its conversations, messages,
  comments, contacts, posts, automations, files and the account itself; jobs/tasks/privacy.py
  and services/account_deletion.py). The status goes received, then processing, then completed
  once every purge has finished; failed while one is retried.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

from socialhood.auth.deps import Session
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
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
    from socialhood.jobs.tasks.privacy import enqueue_request

    await enqueue_request(code)  # a lost enqueue is re-queued by sweep_deletions
    web = (settings.web_base_url or "http://localhost:3000").rstrip("/")
    return JSONResponse({"url": f"{web}/data-deletion?code={code}", "confirmation_code": code})
