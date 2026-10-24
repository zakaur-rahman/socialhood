"""Facebook Pages: connect (GR-29). Start Facebook Login, list the Pages the person manages, connect
the ones they pick. The public callback is in api/v1/oauth.py; the code it parks is exchanged here,
for the member who started the connect only (X-1)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from socialhood.auth.deps import Admin, Session
from socialhood.billing.plans import current_plan
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.schemas.accounts import ConnectStart, SocialAccountList
from socialhood.schemas.facebook import (
    FacebookConnectPages,
    FacebookPageList,
    FacebookPagesRequest,
)
from socialhood.services import facebook_connect
from socialhood.services.connections import account_out

router = APIRouter(prefix="/v1/w/{wid}", tags=["facebook"])


def _deps(request: Request) -> PlatformDeps:
    return deps_from(request.app.state.http, request.app.state.settings)


@router.post("/social-accounts/facebook/connect", operation_id="start_facebook_connect")
async def start_facebook_connect(request: Request, ctx: Admin, session: Session) -> ConnectStart:
    """Facebook's authorize URL. 503 until Facebook connections are configured, 402 over
    accounts_per_platform."""
    url = await facebook_connect.start(
        session,
        request.app.state.redis,
        _deps(request),
        workspace_id=ctx.workspace_id,
        slug=ctx.workspace.slug,
        user_id=ctx.user.id,
        plan=await current_plan(session),
    )
    return ConnectStart(authorize_url=url)


@router.post("/social-accounts/facebook/pages", operation_id="list_facebook_pages")
async def list_facebook_pages(
    request: Request, body: FacebookPagesRequest, ctx: Admin, session: Session
) -> FacebookPageList:
    """The Pages the person who started the connect manages, from the nonce the OAuth callback
    redirected with. Only that member, in that workspace, can read it (403 otherwise); 404 when it
    expired (10 minutes), 502 when Facebook fails. Asking again returns the same list."""
    return await facebook_connect.list_pages(
        session,
        request.app.state.redis,
        _deps(request),
        nonce=body.nonce,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
    )


@router.post(
    "/social-accounts/facebook/connect-pages",
    status_code=201,
    operation_id="connect_facebook_pages",
)
async def connect_facebook_pages(
    request: Request, body: FacebookConnectPages, ctx: Admin, session: Session
) -> SocialAccountList:
    """Connect the picked Pages. 422 page_ids for a Page that wasn't listed or that the person
    can't answer messages for, 409 account_in_use when a Page is connected to another workspace,
    402 over accounts_per_platform (nothing is added, the nonce stays valid), 404 when it
    expired."""
    deps = _deps(request)
    accts = await facebook_connect.connect_pages(
        session,
        request.app.state.redis,
        deps,
        nonce=body.nonce,
        page_ids=list(body.page_ids),
        workspace_id=ctx.workspace_id,
        user_id=ctx.user.id,
        plan=await current_plan(session),
    )
    return SocialAccountList(items=[account_out(a, deps) for a in accts])
