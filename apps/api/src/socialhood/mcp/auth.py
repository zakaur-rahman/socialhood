"""Bearer credentials on /mcp (C-165; 01-design.md §3): one resolver per kind of token.

``resolve_bearer`` picks the resolver whose ``prefix`` the token starts with and returns the
``McpPrincipal`` it acts as, or raises ``CredentialRefused``. Phase A has one resolver, API keys
(``shk_``). Phase C adds OAuth access tokens (``sho_``) by appending an ``OAuthResolver`` to
``RESOLVERS``; nothing else changes, because tools only ever see the principal.

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
from socialhood.mcp.principal import McpPrincipal
from socialhood.services.api_keys import KEY_PREFIX

__all__ = [
    "RESOLVERS",
    "ApiKeyResolver",
    "AuthEnv",
    "CredentialRefused",
    "CredentialResolver",
    "resolve_bearer",
]


@dataclass(frozen=True)
class AuthEnv:
    """What a resolver may use: the app's database and Valkey."""

    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis


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


RESOLVERS: tuple[CredentialResolver, ...] = (ApiKeyResolver(),)


async def resolve_bearer(
    token: str, env: AuthEnv, resolvers: Sequence[CredentialResolver] = RESOLVERS
) -> McpPrincipal:
    for resolver in resolvers:
        if token.startswith(resolver.prefix):
            return await resolver.resolve(token, env)
    raise CredentialRefused(INVALID, unknown=True)
