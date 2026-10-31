"""Amplychat's OAuth 2.1 authorization server for AI app connections (C-165 phase C;
01-design.md §3.2 A2, decision D1). Login is the member's existing Clerk session, on the
dashboard's consent page; this module is everything else.

The flow, authorization code only:

1. ``start_authorization`` (``GET /oauth/authorize``) checks the request. A bad ``client_id``
   or ``redirect_uri`` is shown to the person (never redirected: the redirect URI isn't trusted
   yet). Anything else wrong goes back to the redirect URI as an OAuth error with ``state`` and
   ``iss`` (RFC 9207). PKCE with S256 is required. ``resource`` (RFC 8707) must be this
   server's /mcp when given; when left out it means /mcp, the only resource we serve. A good
   request waits in Valkey for 10 minutes under a random id, and the browser goes to the
   dashboard's consent page with that id.
2. The consent page reads it (``describe``), the member picks a workspace and what to allow,
   then ``approve`` issues a single-use code (60 seconds, hashed, bound to the client, the
   redirect URI, the PKCE challenge, the resource, the member, the workspace and the scopes) and
   sends the browser back with ``code``, ``state`` and ``iss``. ``deny`` sends back
   ``access_denied``. A request can be decided once.
3. ``exchange_code`` (``POST /oauth/token``) checks the client, the code, the redirect URI
   (exactly), the PKCE verifier and the resource, then makes the connection and its first
   tokens. A code used twice revokes the connection the first use made (RFC 6749 §4.1.2).
4. ``refresh`` rotates the refresh token. A rotated refresh token that comes back means one of
   the two copies was stolen: the connection is revoked (RFC 9700 §4.14.2).
5. ``revoke`` (``POST /oauth/revoke``, RFC 7009): an access token alone, or a refresh token and
   with it the whole connection. It always answers 200.

Errors are ``OAuthError`` with the RFC 6749 error codes; the routes (oauth/routes.py) turn
them into the JSON bodies, statuses and redirects the RFCs give.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, unquote_plus, urlencode, urlsplit, urlunsplit

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.mcp_oauth import find_code, find_token, member_role
from socialhood.auth.memberships import memberships_for
from socialhood.billing.plans import current_plan
from socialhood.db.tenancy import workspace_scope
from socialhood.mcp.calls import effective_mode
from socialhood.mcp.principal import ALWAYS_GRANTED
from socialhood.models.identity import Workspace
from socialhood.models.mcp import AiConnectionsMode
from socialhood.models.oauth import (
    ClientAuth,
    McpConnection,
    OAuthClient,
    OAuthCode,
    OAuthToken,
    RevokeReason,
    TokenKind,
)
from socialhood.oauth import clients, scopes, tokens
from socialhood.oauth.clients import ClientError, Fetcher
from socialhood.settings import Settings

PKCE_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43}$")
PKCE_VERIFIER = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
MAX_STATE_CHARS = 1000
REQUEST_KEY = "oauth-req:{}"


class OAuthError(Exception):
    """An OAuth error (RFC 6749 §4.1.2.1, §5.2). ``redirect``: where to send it, when the
    redirect URI has been checked; None means show it to the person."""

    def __init__(
        self,
        error: str,
        description: str,
        *,
        status: int = 400,
        redirect: str | None = None,
        state: str | None = None,
    ) -> None:
        super().__init__(description)
        self.error = error
        self.description = description
        self.status = status
        self.redirect = redirect
        self.state = state


# ---------------------------------------------------------------- addresses


def issuer(settings: Settings) -> str:
    """The authorization server's identifier: the API's origin, which the protected resource
    metadata names as its authorization server."""
    parts = urlsplit(settings.mcp_resource_url)
    return f"{parts.scheme}://{parts.netloc}"


def consent_url(settings: Settings, request_id: str) -> str:
    web = (settings.web_base_url or "http://localhost:3000").rstrip("/")
    return f"{web}/connect/authorize?{urlencode({'request': request_id})}"


def with_params(uri: str, params: Mapping[str, str | None]) -> str:
    """``uri`` with ``params`` added to its query (what it already has is kept)."""
    parts = urlsplit(uri)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query += [(k, v) for k, v in params.items() if v is not None]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def error_redirect(error: OAuthError, settings: Settings) -> str:
    assert error.redirect is not None
    return with_params(
        error.redirect,
        {
            "error": error.error,
            "error_description": error.description,
            "state": error.state,
            "iss": issuer(settings),
        },
    )


def normal_resource(value: str) -> str:
    """Scheme and host in lower case, no trailing slash (the spec's canonical form; it asks
    servers to accept upper case scheme and host)."""
    parts = urlsplit(value.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def check_resource(raw: str | None, settings: Settings, **redirect: Any) -> str:
    ours = settings.mcp_resource_url
    if raw is None or raw == "":
        return ours
    if normal_resource(raw) != normal_resource(ours):
        raise OAuthError(
            "invalid_target", "This server only issues tokens for its /mcp endpoint.", **redirect
        )
    return ours


# ---------------------------------------------------------------- 1. the authorization request


@dataclass(frozen=True)
class PendingRequest:
    id: str
    client_pk: str
    client_id: str
    client_name: str
    redirect_uri: str
    state: str | None
    code_challenge: str
    resource: str
    scopes: list[str]


async def load_client(
    session: AsyncSession, client_id: str, now: datetime, *, fetch: Fetcher | None = None
) -> OAuthClient:
    client: OAuthClient | None
    try:
        if clients.is_cimd_client_id(client_id):
            client = await clients.cimd_client(session, client_id, now, fetch=fetch)
        else:
            client = await clients.find_client(session, client_id)
    except ClientError as error:
        raise OAuthError("invalid_client", error.description) from error
    if client is None:
        raise OAuthError("invalid_client", "This app isn't registered with Amplychat.")
    if client.blocked_at is not None:
        raise OAuthError("invalid_client", "This app can't connect to Amplychat.")
    return client


async def start_authorization(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    params: Mapping[str, str],
    now: datetime,
    *,
    fetch: Fetcher | None = None,
) -> str:
    """Check an authorization request; the consent page's URL for it."""
    client_id = params.get("client_id") or ""
    if not client_id:
        raise OAuthError("invalid_request", "client_id is missing.")
    client = await load_client(session, client_id, now, fetch=fetch)
    redirect_uri = params.get("redirect_uri") or ""
    if not redirect_uri:
        raise OAuthError("invalid_request", "redirect_uri is missing.")
    if not clients.redirect_matches(client.redirect_uris, redirect_uri):
        raise OAuthError(
            "invalid_request", "redirect_uri isn't one this app registered.", status=400
        )
    state = params.get("state") or None
    back: dict[str, Any] = {"redirect": redirect_uri, "state": state}
    if state is not None and len(state) > MAX_STATE_CHARS:
        raise OAuthError("invalid_request", "state is too long.", redirect=redirect_uri)
    if params.get("response_type") != "code":
        raise OAuthError(
            "unsupported_response_type", "Only response_type=code is supported.", **back
        )
    if params.get("response_mode") not in (None, "", "query"):
        raise OAuthError("invalid_request", "Only response_mode=query is supported.", **back)
    challenge = params.get("code_challenge") or ""
    if params.get("code_challenge_method") != "S256" or not PKCE_CHALLENGE.match(challenge):
        raise OAuthError(
            "invalid_request", "PKCE is required: code_challenge with method S256.", **back
        )
    resource = check_resource(params.get("resource"), settings, **back)
    request = PendingRequest(
        id=secrets.token_urlsafe(24),
        client_pk=str(client.id),
        client_id=client.client_id,
        client_name=client.client_name,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=challenge,
        resource=resource,
        scopes=scopes.requested(params.get("scope")),
    )
    await redis.set(
        REQUEST_KEY.format(request.id),
        json.dumps(asdict(request)),
        ex=int(tokens.REQUEST_TTL.total_seconds()),
    )
    await session.commit()  # a fetched client document is kept
    return consent_url(settings, request.id)


# ---------------------------------------------------------------- 2. consent


class ConsentError(Exception):
    """The consent page can't go on (the request expired or was decided; the workspace can't be
    used). ``code`` is the API's error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


EXPIRED_REQUEST = (
    "This sign-in request has expired or was already used. Start connecting again from your AI app."
)


async def pending(redis: Redis, request_id: str) -> PendingRequest:
    raw = await redis.get(REQUEST_KEY.format(request_id)) if request_id else None
    if raw is None:
        raise ConsentError("not_found", EXPIRED_REQUEST)
    return PendingRequest(**json.loads(raw))


async def _take(redis: Redis, request_id: str) -> PendingRequest:
    """The request, removed: it can be decided once."""
    raw = await redis.getdel(REQUEST_KEY.format(request_id))
    if raw is None:
        raise ConsentError("not_found", EXPIRED_REQUEST)
    return PendingRequest(**json.loads(raw))


@dataclass(frozen=True)
class WorkspaceChoice:
    id: uuid.UUID
    name: str
    plan: str
    role: str
    mode: str  # the effective AI connections mode
    can_connect: bool
    reason: str | None


async def workspace_choices(session: AsyncSession, user_id: uuid.UUID) -> list[WorkspaceChoice]:
    """The member's workspaces for the picker. Any role may connect (§3.5); a workspace whose
    AI connections are off is listed but can't be chosen."""
    out = []
    for m in await memberships_for(session, user_id):
        with workspace_scope(m.workspace_id):
            workspace = await session.get(Workspace, m.workspace_id)
            if workspace is None:
                continue
            plan = await current_plan(session)
            mode = effective_mode(workspace.ai_connections_mode, plan)
        off = mode is AiConnectionsMode.OFF
        out.append(
            WorkspaceChoice(
                id=m.workspace_id,
                name=m.name,
                plan=plan,
                role=m.role,
                mode=mode.value,
                can_connect=not off,
                reason="An owner or admin has turned AI connections off here." if off else None,
            )
        )
    return out


async def approve(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    request_id: str,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    allowed: list[str],
    now: datetime,
) -> str:
    """The member allowed it: a code, and where to send the browser."""
    request = await pending(redis, request_id)
    choice = next(
        (c for c in await workspace_choices(session, user_id) if c.id == workspace_id), None
    )
    if choice is None:
        raise ConsentError("not_found", "That workspace isn't one of yours.")
    if not choice.can_connect:
        raise ConsentError("forbidden", choice.reason or "AI connections are off here.")
    granted = scopes.ordered(s for s in allowed if s in request.scopes)
    request = await _take(redis, request_id)
    code = tokens.new_token(tokens.CODE_PREFIX)
    with workspace_scope(workspace_id):
        session.add(
            OAuthCode(
                code_hash=tokens.hash_token(code),
                oauth_client_id=uuid.UUID(request.client_pk),
                user_id=user_id,
                client_name=request.client_name,
                redirect_uri=request.redirect_uri,
                code_challenge=request.code_challenge,
                resource=request.resource,
                scopes=granted,
                expires_at=now + tokens.CODE_TTL,
            )
        )
        await session.commit()
    return with_params(
        request.redirect_uri, {"code": code, "state": request.state, "iss": issuer(settings)}
    )


async def deny(redis: Redis, settings: Settings, request_id: str) -> str:
    request = await _take(redis, request_id)
    return with_params(
        request.redirect_uri,
        {
            "error": "access_denied",
            "error_description": "The member didn't allow the connection.",
            "state": request.state,
            "iss": issuer(settings),
        },
    )


# ---------------------------------------------------------------- 3 to 5. the token endpoint


def _basic(authorization: str | None) -> tuple[str, str] | None:
    scheme, _, value = (authorization or "").partition(" ")
    if scheme.lower() != "basic" or not value:
        return None
    try:
        decoded = base64.b64decode(value.strip(), validate=True).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    user, sep, password = decoded.partition(":")
    if not sep:
        return None
    return unquote_plus(user), unquote_plus(password)


INVALID_CLIENT = "Client authentication failed."


async def authenticate_client(
    session: AsyncSession, form: Mapping[str, str], authorization: str | None
) -> OAuthClient:
    """The client making a token or revocation request (RFC 6749 §2.3): a public client by its
    ``client_id``, a registered confidential one by its secret, as it registered."""
    basic = _basic(authorization)
    client_id = basic[0] if basic else (form.get("client_id") or "")
    if not client_id:
        raise OAuthError("invalid_client", INVALID_CLIENT, status=401)
    client = await clients.find_client(session, client_id)
    if client is None or client.blocked_at is not None:
        raise OAuthError("invalid_client", INVALID_CLIENT, status=401)
    method = client.token_endpoint_auth_method
    if method == ClientAuth.NONE.value:
        if basic and basic[1]:
            raise OAuthError("invalid_client", INVALID_CLIENT, status=401)
        return client
    # Either way of sending the secret is accepted, whichever the client registered: some
    # clients send it in the body whatever they asked for.
    secret = basic[1] if basic else form.get("client_secret")
    if (
        not secret
        or client.client_secret_hash is None
        or not hmac.compare_digest(clients.hash_secret(secret), client.client_secret_hash)
    ):
        raise OAuthError("invalid_client", INVALID_CLIENT, status=401)
    return client


def pkce_ok(verifier: str, challenge: str) -> bool:
    if not PKCE_VERIFIER.match(verifier):
        return False
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return hmac.compare_digest(computed, challenge)


BAD_CODE = "The authorization code is invalid, expired or already used."
BAD_REFRESH = "The refresh token is invalid, expired or revoked."


def _issue(
    session: AsyncSession, connection: McpConnection, family_id: uuid.UUID, now: datetime
) -> dict[str, Any]:
    access = tokens.new_token(tokens.ACCESS_PREFIX)
    refresh = tokens.new_token(tokens.REFRESH_PREFIX)
    session.add_all(
        [
            OAuthToken(
                token_hash=tokens.hash_token(access),
                kind=TokenKind.ACCESS.value,
                connection_id=connection.id,
                family_id=family_id,
                expires_at=now + tokens.ACCESS_TTL,
            ),
            OAuthToken(
                token_hash=tokens.hash_token(refresh),
                kind=TokenKind.REFRESH.value,
                connection_id=connection.id,
                family_id=family_id,
                expires_at=connection.expires_at,
            ),
        ]
    )
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": int(tokens.ACCESS_TTL.total_seconds()),
        "refresh_token": refresh,
        "scope": " ".join(connection.scopes),
    }


def revoke_connection(
    connection: McpConnection,
    reason: RevokeReason,
    now: datetime,
    by_user_id: uuid.UUID | None = None,
) -> bool:
    """Revoke a connection (every token of it stops at once: tokens are checked against their
    connection). False when it was already revoked."""
    if connection.revoked_at is not None:
        return False
    connection.revoked_at = now
    connection.revoke_reason = reason.value
    connection.revoked_by_user_id = by_user_id
    return True


async def exchange_code(
    session: AsyncSession,
    settings: Settings,
    client: OAuthClient,
    form: Mapping[str, str],
    now: datetime,
) -> dict[str, Any]:
    code = await find_code(session, form.get("code") or "", for_update=True)
    if code is None:
        raise OAuthError("invalid_grant", BAD_CODE)
    with workspace_scope(code.workspace_id):
        if code.oauth_client_id != client.id:
            raise OAuthError("invalid_grant", BAD_CODE)
        if code.used_at is not None:
            if code.connection_id is not None:
                connection = await session.get(McpConnection, code.connection_id)
                if connection is not None:
                    revoke_connection(connection, RevokeReason.CODE_REUSE, now)
                    await session.commit()
            raise OAuthError("invalid_grant", BAD_CODE)
        if now >= code.expires_at:
            raise OAuthError("invalid_grant", BAD_CODE)
        if (form.get("redirect_uri") or "") != code.redirect_uri:
            raise OAuthError("invalid_grant", "redirect_uri doesn't match the authorization.")
        if not pkce_ok(form.get("code_verifier") or "", code.code_challenge):
            raise OAuthError("invalid_grant", "The PKCE code_verifier doesn't match.")
        resource = check_resource(form.get("resource"), settings)
        if resource != code.resource:
            raise OAuthError("invalid_target", "resource doesn't match the authorization.")
        if await member_role(session, code.workspace_id, code.user_id) is None:
            raise OAuthError("invalid_grant", "The member is no longer in the workspace.")
        code.used_at = now
        connection = McpConnection(
            workspace_id=code.workspace_id,
            user_id=code.user_id,
            oauth_client_id=client.id,
            client_name=code.client_name,
            redirect_uri=code.redirect_uri,
            scopes=list(code.scopes),
            resource=code.resource,
            expires_at=now + tokens.ABSOLUTE_LIMIT,
            last_used_at=now,
        )
        session.add(connection)
        await session.flush()
        code.connection_id = connection.id
        body = _issue(session, connection, uuid.uuid4(), now)
        client.last_used_at = now
        await session.commit()
        return body


async def refresh(
    session: AsyncSession,
    settings: Settings,
    client: OAuthClient,
    form: Mapping[str, str],
    now: datetime,
) -> dict[str, Any]:
    token = await find_token(
        session, form.get("refresh_token") or "", TokenKind.REFRESH, for_update=True
    )
    if token is None:
        raise OAuthError("invalid_grant", BAD_REFRESH)
    with workspace_scope(token.workspace_id):
        connection = await session.get(McpConnection, token.connection_id)
        if connection is None or connection.oauth_client_id != client.id:
            raise OAuthError("invalid_grant", BAD_REFRESH)
        if token.used_at is not None:  # reuse: one of two copies was stolen
            if revoke_connection(connection, RevokeReason.REFRESH_REUSE, now):
                await session.commit()
            raise OAuthError("invalid_grant", BAD_REFRESH)
        if token.revoked_at is not None or tokens.connection_problem(connection, now):
            raise OAuthError("invalid_grant", BAD_REFRESH)
        check_resource(form.get("resource"), settings)
        asked = set((form.get("scope") or "").split()) - {
            scopes.OFFLINE_ACCESS,
            "openid",
            "email",
            "profile",
        }
        if asked - set(connection.scopes) - {ALWAYS_GRANTED}:
            raise OAuthError("invalid_scope", "A refresh can't add scopes. Connect again.")
        if await member_role(session, connection.workspace_id, connection.user_id) is None:
            raise OAuthError("invalid_grant", "The member is no longer in the workspace.")
        token.used_at = now
        connection.last_used_at = now
        client.last_used_at = now
        body = _issue(session, connection, token.family_id, now)
        await session.commit()
        return body


async def revoke(
    session: AsyncSession, client: OAuthClient, form: Mapping[str, str], now: datetime
) -> None:
    """RFC 7009. Unknown tokens and other clients' tokens are ignored (still 200)."""
    raw = form.get("token") or ""
    token = await find_token(session, raw, None)
    if token is None:
        return
    with workspace_scope(token.workspace_id):
        connection = await session.get(McpConnection, token.connection_id)
        if connection is None or connection.oauth_client_id != client.id:
            return
        if token.kind == TokenKind.REFRESH.value:
            revoke_connection(connection, RevokeReason.CLIENT, now)
        elif token.revoked_at is None:
            token.revoked_at = now
        await session.commit()


def metadata(settings: Settings) -> dict[str, Any]:
    """RFC 8414 authorization server metadata, with what the MCP clients look for (§3.1):
    S256, ``none`` auth for public clients, CIMD, and RFC 9207 ``iss``."""
    base = issuer(settings)
    auth_methods = [m.value for m in ClientAuth]
    out: dict[str, Any] = {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "revocation_endpoint": f"{base}/oauth/revoke",
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": auth_methods,
        "revocation_endpoint_auth_methods_supported": auth_methods,
        "scopes_supported": list(scopes.AS_SCOPES_SUPPORTED),
        "client_id_metadata_document_supported": True,
        "authorization_response_iss_parameter_supported": True,
    }
    if settings.site_url:
        out["service_documentation"] = f"{settings.site_url.rstrip('/')}/developers/mcp"
    return out
