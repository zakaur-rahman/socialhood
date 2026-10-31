"""/mcp over HTTP (C-165; 01-design.md §2.1, §2.3, §3): authentication in front of the SDK's
Streamable HTTP transport.

Every request needs ``Authorization: Bearer <credential>``:

- none: 401 with ``WWW-Authenticate: Bearer resource_metadata="<PRM URL>"`` (RFC 9728 §5.1,
  the MCP authorization spec's MUST; no ``error``, per RFC 6750 §3.1 for a request without
  credentials);
- one that doesn't authenticate: 401 with ``error="invalid_token"``, its reason and the same
  ``resource_metadata``. A token that isn't any credential of ours also counts against the
  caller's IP (``public``, 60 a minute) like the public API, so guessing keys is slow; past it,
  429 with ``Retry-After``.

Then the principal is put in context (mcp/principal.py) and the request goes to the SDK, which
serves it inside that context. Responses carry ``X-Robots-Tag: noindex`` (Caddy adds it for the
whole API host too).

The protected resource metadata (RFC 9728) is served at
``/.well-known/oauth-protected-resource/mcp`` and, as the fallback Claude probes, at
``/.well-known/oauth-protected-resource``. Its authorization server is the API's own origin,
which phase C makes answer ``/.well-known/oauth-authorization-server``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from socialhood.mcp.auth import AuthEnv, CredentialRefused, CredentialResolver, resolve_bearer
from socialhood.mcp.principal import McpRequest, request_scope
from socialhood.observability.request_id import current_request_id
from socialhood.security import ratelimit
from socialhood.settings import Settings

PRM_PATH = "/.well-known/oauth-protected-resource"
NOINDEX = (b"x-robots-tag", b"noindex, nofollow")
MISSING = "Send an Amplychat API key or access token as a Bearer token."
# What the PRM document advertises a client should ask for (§3.4): the reads and publishing.
SCOPES_SUPPORTED = (
    "workspace:read",
    "posts:read",
    "posts:write",
    "media:write",
    "conversations:read",
    "replies:draft",
    "comments:read",
    "analytics:read",
    "knowledge:read",
    "automations:read",
)


def metadata_url(settings: Settings) -> str:
    resource = urlsplit(settings.mcp_resource_url)
    return f"{resource.scheme}://{resource.netloc}{PRM_PATH}{resource.path}"


def protected_resource_metadata(settings: Settings) -> dict[str, object]:
    resource = urlsplit(settings.mcp_resource_url)
    return {
        "resource": settings.mcp_resource_url,
        "authorization_servers": [f"{resource.scheme}://{resource.netloc}"],
        "scopes_supported": list(SCOPES_SUPPORTED),
        "bearer_methods_supported": ["header"],
        "resource_name": "Amplychat",
        "resource_documentation": f"{(settings.site_url or '').rstrip('/')}/developers/mcp"
        if settings.site_url
        else None,
    }


async def prm_endpoint(request: Request) -> Response:
    settings: Settings = request.app.state.settings
    body = {k: v for k, v in protected_resource_metadata(settings).items() if v is not None}
    return JSONResponse(body, headers={"Cache-Control": "public, max-age=3600"})


def _quoted(text: str) -> str:
    return text.replace("\\", "").replace('"', "'")


class McpEndpoint:
    """The ASGI app at /mcp: authenticate, then hand over to the SDK's transport."""

    def __init__(
        self,
        transport: ASGIApp,
        *,
        settings: Settings,
        auth: AuthEnv,
        resolvers: Sequence[CredentialResolver],
    ) -> None:
        self.transport = transport
        self.settings = settings
        self.auth = auth
        self.resolvers = tuple(resolvers)
        self.metadata_url = metadata_url(settings)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive)
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        token = token.strip()
        if scheme.lower() != "bearer" or not token:
            await self._challenge(scope, receive, send, None)
            return
        try:
            principal = await resolve_bearer(token, self.auth, self.resolvers)
        except CredentialRefused as refused:
            if refused.unknown and (wait := await self._guessing(request)):
                await self._too_many(scope, receive, send, wait)
                return
            await self._challenge(scope, receive, send, refused.message)
            return
        context = McpRequest(
            principal=principal,
            client_ip=ratelimit.client_ip(request),
            user_agent=(request.headers.get("user-agent") or None),
            request_id=current_request_id.get(),
        )

        async def noindex(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []), NOINDEX]}
            await send(message)

        with request_scope(context):
            await self.transport(scope, receive, noindex)

    async def _guessing(self, request: Request) -> float:
        """Count an unknown token against the caller's IP; the seconds to wait when over."""
        if not self.settings.rate_limits_enabled:
            return 0.0
        try:
            return await ratelimit.hit(
                self.auth.redis, ratelimit.LIMITS["public"], ratelimit.client_ip(request)
            )
        except Exception:
            return 0.0

    async def _challenge(
        self, scope: Scope, receive: Receive, send: Send, reason: str | None
    ) -> None:
        parts = []
        if reason is not None:
            parts += ['error="invalid_token"', f'error_description="{_quoted(reason)}"']
        parts.append(f'resource_metadata="{self.metadata_url}"')
        body = {
            "error": "invalid_token" if reason else "unauthorized",
            "error_description": reason or MISSING,
        }
        response = Response(
            json.dumps(body),
            status_code=401,
            media_type="application/json",
            headers={
                "WWW-Authenticate": "Bearer " + ", ".join(parts),
                "X-Robots-Tag": "noindex, nofollow",
            },
        )
        await response(scope, receive, send)

    async def _too_many(self, scope: Scope, receive: Receive, send: Send, wait: float) -> None:
        response = Response(
            json.dumps({"error": "rate_limited", "error_description": "Too many requests."}),
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(max(1, math.ceil(wait)))},
        )
        await response(scope, receive, send)
