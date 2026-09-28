"""What adapters need from the process: the shared HTTP client, the token cipher and settings."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from socialhood.security.crypto import TokenCipher
from socialhood.settings import Settings


@dataclass(frozen=True)
class PlatformDeps:
    http: httpx.AsyncClient
    cipher: TokenCipher
    settings: Settings


def deps_from(http: httpx.AsyncClient, settings: Settings) -> PlatformDeps:
    from socialhood.security.crypto import cipher_for

    return PlatformDeps(
        http=http, cipher=cipher_for(tuple(settings.token_encryption_keys)), settings=settings
    )
