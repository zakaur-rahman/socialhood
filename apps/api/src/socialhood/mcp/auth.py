"""Bearer credentials on /mcp (C-165; 01-design.md §3): one resolver per kind of token.

``resolve_bearer`` picks the resolver whose ``prefix`` the token starts with and returns the
``McpPrincipal`` it acts as, or raises ``CredentialRefused``. Two resolvers: API keys (``shk_``,
phase A) and OAuth access tokens (``sho_``, phase C). Tools only ever see the principal.

Why not the SDK's ``BearerAuthBackend``/``TokenVerifier``: the resolver needs the request (the
caller's IP for the guessing limit) and the app's database and Valkey, and the 401 must follow
RFC 6750 exactly (no ``error`` when no credential was sent). ``mcp/http.py`` does both; the
contract here is the same shape as ``TokenVerifier.verify_token``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.auth.mcp_credentials import INVALID, CredentialRefused, principal_for_api_key
from socialhood.auth.mcp_oauth import OAuthRefused, principal_for_access_token
from socialhood.mcp.principal import McpPrincipal
from socialhood.oauth.tokens import ACCESS_PREFIX
from socialhood.services.api_keys import KEY_PREFIX

__all__ = [
    "RESOLVERS",
    "ApiKeyResolver",
    "AuthEnv",
    "CredentialRefused",
    "CredentialResolver",
    "OAuthResolver",
    "resolve_bearer",
]


@dataclass(frozen=True)
class AuthEnv:
    """What a resolver may use: the app's database and Valkey, and this server's canonical
    URL (the audience an OAuth token must have been issued for, RFC 8707)."""

    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    resource: str = "http://localhost:8000/mcp"


class CredentialResolver(Protocol):
    """One kind of bearer token."""

    prefix: str  # the token's fixed start, e.g. "shk_"

    async def resolve(self, token: str, env: AuthEnv) -> McpPrincipal:
        """The principal ``token`` acts as; ``CredentialRefused`` when it doesn't authenticate
        (unknown, revoked, expired, its member gone, its workspace inactive)."""
        ...


class ApiKeyResolver:
    """Workspace API keys (GR-25) as MCP credentials, for Claude Code and Codex (§3.3)."""

    prefix = KEY_PREFIX

    async def resolve(self, token: str, env: AuthEnv) -> McpPrincipal:
        async with env.sessionmaker() as session:
            principal = await principal_for_api_key(session, env.redis, token)
            await session.commit()
            return principal


class OAuthResolver:
    """OAuth access tokens from our authorization server (socialhood/oauth), for claude.ai,
    ChatGPT and any client that signs in (§3.2). The principal's ``credential_id`` is the
    connection's id."""

    prefix = ACCESS_PREFIX

    async def resolve(self, token: str, env: AuthEnv) -> McpPrincipal:
        async with env.sessionmaker() as session:
            try:
                return await principal_for_access_token(
                    session, env.redis, token, resource=env.resource
                )
            except OAuthRefused as refused:
                raise CredentialRefused(refused.message, unknown=refused.unknown) from refused


RESOLVERS: tuple[CredentialResolver, ...] = (ApiKeyResolver(), OAuthResolver())


async def resolve_bearer(
    token: str, env: AuthEnv, resolvers: Sequence[CredentialResolver] = RESOLVERS
) -> McpPrincipal:
    for resolver in resolvers:
        if token.startswith(resolver.prefix):
            return await resolver.resolve(token, env)
    raise CredentialRefused(INVALID, unknown=True)
