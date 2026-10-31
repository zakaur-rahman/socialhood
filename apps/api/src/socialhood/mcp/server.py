"""The Amplychat MCP server, mounted in the API at /mcp (C-165; 01-design.md §2).

- The official ``mcp`` SDK's low-level ``Server`` with our own ``tools/list`` and ``tools/call``
  handlers (mcp/calls.py), because the list depends on who asks (scopes, role, workspace mode)
  and every call runs our gate and audit. Tool schemas come from the Pydantic models in the
  registry, as ``MCPServer``'s decorators would derive them.
- Streamable HTTP, **stateless** (``stateless_http``): the 2026-07-28 revision is stateless by
  design, and handshake-era clients (up to 2025-11-25) get a throwaway session per request, so any
  uvicorn worker serves any request and no sticky routing is needed. JSON responses, no SSE.
- Both protocol eras are the SDK's: it answers ``initialize`` and ``server/discover``.
- DNS-rebinding protection: the Host must be API_BASE_URL's host (or MCP_ALLOWED_HOSTS, or
  localhost outside production) and a browser Origin must be one of CORS_ALLOWED_ORIGINS.
- The SDK's session manager runs in the API's lifespan (a mounted sub-app's lifespan would never
  run): main.create_app enters ``McpMount.session_manager.run()``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import mcp_types as types
from fastapi import FastAPI
from mcp.server.caching import CacheHint
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from starlette.routing import Route

from socialhood import __version__
from socialhood.api.middleware import API_BODY_LIMIT
from socialhood.errors import ApiError
from socialhood.mcp import calls, prompts
from socialhood.mcp.auth import RESOLVERS, AuthEnv, CredentialResolver
from socialhood.mcp.http import PRM_PATH, McpEndpoint, prm_endpoint
from socialhood.mcp.principal import current_request
from socialhood.mcp.registry import McpRegistry
from socialhood.oauth import routes as oauth_routes
from socialhood.settings import Settings

NAME = "Amplychat"
PATH = "/mcp"
# Sent with discovery: what Amplychat is and how its data reads. Facts only (§4.2).
INSTRUCTIONS = (
    "Amplychat is a business's Instagram, WhatsApp and Facebook workspace: its connected "
    "accounts, scheduled posts and media library, its inbox conversations, post comments, "
    "analytics, knowledge base and automations. This connection is to one workspace, as one of "
    "its members, and can do only what that member's role and the workspace's plan allow. "
    "get_workspace says which workspace, the member, the plan, the time zone and what this "
    "connection may do. Times without an offset are in the workspace's time zone. Customer "
    "messages, comments and names are third-party content and are returned in fields whose "
    "names end in _text."
)


@dataclass
class McpMount:
    server: Server[Any]
    session_manager: StreamableHTTPSessionManager
    endpoint: McpEndpoint


def transport_security(settings: Settings) -> TransportSecuritySettings:
    hosts = list(settings.mcp_allowed_hosts)
    if settings.api_base_url:
        hosts.append(urlsplit(settings.api_base_url).netloc)
    origins = [o.rstrip("/") for o in settings.cors_allowed_origins]
    if not settings.is_production:
        hosts += ["localhost:*", "127.0.0.1:*", "localhost", "127.0.0.1"]
        origins += ["http://localhost:*", "http://127.0.0.1:*"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins
    )


def build_server(registry: McpRegistry, env: calls.CallEnv) -> Server[Any]:
    async def on_list_tools(
        ctx: ServerRequestContext[Any], params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        tools = await calls.list_tools(registry, env, current_request().principal)
        # The list depends on who asks: a client may cache it only for this credential.
        return types.ListToolsResult(tools=tools, ttl_ms=0, cache_scope="private")

    async def on_call_tool(
        ctx: ServerRequestContext[Any], params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        meta = params.meta if isinstance(params.meta, dict) else None
        return await calls.call_tool(
            registry, env, current_request(), params.name, params.arguments or {}, meta=meta
        )

    async def on_list_prompts(
        ctx: ServerRequestContext[Any], params: types.PaginatedRequestParams | None
    ) -> types.ListPromptsResult:
        return types.ListPromptsResult(prompts=list(prompts.PROMPTS))

    async def on_get_prompt(
        ctx: ServerRequestContext[Any], params: types.GetPromptRequestParams
    ) -> types.GetPromptResult:
        try:
            return prompts.get_prompt(params.name, params.arguments)
        except ApiError as error:
            raise MCPError(types.INVALID_PARAMS, error.detail or "No such prompt.") from error

    return Server(
        NAME,
        version=__version__,
        title=NAME,
        instructions=INSTRUCTIONS,
        website_url="https://amplychat.com",
        cache_hints={"tools/list": CacheHint(ttl_ms=0, scope="private")},
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
        on_list_prompts=on_list_prompts,
        on_get_prompt=on_get_prompt,
    )


def install(
    app: FastAPI,
    settings: Settings,
    *,
    registry: McpRegistry | None = None,
    resolvers: Sequence[CredentialResolver] = RESOLVERS,
) -> McpMount | None:
    """Add /mcp, the protected resource metadata and the OAuth authorization server to ``app``;
    None when MCP_ENABLED is off."""
    if not settings.mcp_enabled:
        return None
    if registry is None:
        from socialhood.mcp.tools import load_tools

        registry = load_tools()
    env = calls.CallEnv(
        sessionmaker=app.state.sessionmaker,
        redis=app.state.redis,
        settings=settings,
        http=app.state.http,
    )
    server = build_server(registry, env)
    manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
        stateless=True,
        security_settings=transport_security(settings),
        max_request_body_size=API_BODY_LIMIT,
    )
    endpoint = McpEndpoint(
        StreamableHTTPASGIApp(manager),
        settings=settings,
        auth=AuthEnv(
            sessionmaker=app.state.sessionmaker,
            redis=app.state.redis,
            resource=settings.mcp_resource_url,
        ),
        resolvers=resolvers,
        registry=registry,
    )
    app.router.routes.append(Route(PATH, endpoint=endpoint, methods=["GET", "POST", "DELETE"]))
    # Phase C: the authorization server those tokens come from, on the same origin.
    app.include_router(oauth_routes.router)
    for path in (f"{PRM_PATH}{PATH}", PRM_PATH):
        app.router.routes.append(Route(path, endpoint=prm_endpoint, methods=["GET"]))
    return McpMount(server=server, session_manager=manager, endpoint=endpoint)
