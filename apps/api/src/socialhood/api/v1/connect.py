"""The consent page's routes (C-165 phase C; 01-design.md §3.2, §3.5): the dashboard's
``/connect/authorize`` page reads the waiting authorization request and decides it, signed in
with the member's existing Clerk session.

- ``GET /v1/connect/requests/{request_id}``: which app, where it goes back to, what it asked
  for in plain words, and the member's workspaces (with whether each can connect);
- ``POST …/approve``: the workspace and what the member allowed; the answer says where to send
  the browser (the app's redirect URI with ``code``, ``state`` and ``iss``);
- ``POST …/deny``: the same with ``error=access_denied``.

A request lives 10 minutes and can be decided once. Approving needs only membership: any role
may connect, and the connection then does only what the role allows (§3.5).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request

from socialhood.auth.deps import CurrentUser, Session
from socialhood.errors import ApiError
from socialhood.models.oauth import OAuthClient
from socialhood.oauth import clients, scopes
from socialhood.oauth import service as oauth
from socialhood.oauth.service import ConsentError
from socialhood.schemas.ai_connections import (
    ConnectApproval,
    ConnectClient,
    ConnectMember,
    ConnectRedirect,
    ConnectRequest,
    ConnectScope,
    ConnectScopeGroup,
    ConnectWorkspace,
)
from socialhood.services.ai_connections import verified_host

router = APIRouter(prefix="/v1/connect", tags=["ai-connections"])


def _refused(error: ConsentError) -> ApiError:
    return ApiError(error.code, error.message)


@router.get("/requests/{request_id}", operation_id="get_connect_request")
async def get_request(
    request_id: str, request: Request, user: CurrentUser, session: Session
) -> ConnectRequest:
    try:
        waiting = await oauth.pending(request.app.state.redis, request_id)
    except ConsentError as error:
        raise _refused(error) from error
    client = await clients.find_client(session, waiting.client_id)
    if client is None or client.blocked_at is not None:
        raise ApiError("not_found", oauth.EXPIRED_REQUEST)
    asked = set(waiting.scopes)
    groups = [
        ConnectScopeGroup(
            id=group.id,
            label=group.label,
            scopes=[ConnectScope(scope=s, description=d) for s, d in group.scopes if s in asked],
        )
        for group in scopes.GROUPS
        if any(s in asked for s, _ in group.scopes)
    ]
    choices = await oauth.workspace_choices(session, user.id)
    return ConnectRequest(
        client=_client(client, waiting.redirect_uri),
        always=scopes.ALWAYS_WORDS,
        groups=groups,
        member=ConnectMember(email=user.email, name=user.name),
        workspaces=[ConnectWorkspace.model_validate(c, from_attributes=True) for c in choices],
    )


def _client(client: OAuthClient, redirect_uri: str) -> ConnectClient:
    return ConnectClient(
        name=client.client_name,
        logo_url=clients.logo_is_shown(client),
        verified_host=verified_host(client),
        redirect_host=clients.redirect_host(redirect_uri),
        loopback=clients.is_loopback(redirect_uri),
    )


@router.post("/requests/{request_id}/approve", operation_id="approve_connect_request")
async def approve(
    request_id: str,
    body: ConnectApproval,
    request: Request,
    user: CurrentUser,
    session: Session,
) -> ConnectRedirect:
    try:
        location = await oauth.approve(
            session,
            request.app.state.redis,
            request.app.state.settings,
            request_id,
            user.id,
            body.workspace_id,
            body.scopes,
            datetime.now(UTC),
        )
    except ConsentError as error:
        raise _refused(error) from error
    return ConnectRedirect(redirect_to=location)


@router.post("/requests/{request_id}/deny", operation_id="deny_connect_request")
async def deny(request_id: str, request: Request, user: CurrentUser) -> ConnectRedirect:
    try:
        location = await oauth.deny(request.app.state.redis, request.app.state.settings, request_id)
    except ConsentError as error:
        raise _refused(error) from error
    return ConnectRedirect(redirect_to=location)
