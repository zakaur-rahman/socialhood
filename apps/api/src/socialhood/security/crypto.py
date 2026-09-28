"""Platform tokens encrypted at rest (SEC-03).

MultiFernet built from TOKEN_ENCRYPTION_KEYS (comma-separated, newest first): the first key
encrypts, every key decrypts, so keys can be rotated without downtime.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from socialhood.settings import ConfigurationError


class TokenCipher:
    def __init__(self, keys: list[str] | tuple[str, ...]) -> None:
        if not keys:
            raise ConfigurationError(
                "TOKEN_ENCRYPTION_KEYS is empty; platform tokens cannot be stored"
            )
        try:
            self._fernet = MultiFernet([Fernet(key.encode()) for key in keys])
        except ValueError as error:
            raise ConfigurationError(
                "TOKEN_ENCRYPTION_KEYS contains an invalid Fernet key"
            ) from error

    def encrypt(self, token: str) -> bytes:
        return self._fernet.encrypt(token.encode())

    def decrypt(self, blob: bytes) -> str:
        try:
            return self._fernet.decrypt(bytes(blob)).decode()
        except InvalidToken as error:
            raise ValueError("token cannot be decrypted with the configured keys") from error

    def rotate(self, blob: bytes) -> bytes:
        """Re-encrypt with the newest key."""
        return self._fernet.rotate(bytes(blob))


@lru_cache(maxsize=4)
def cipher_for(keys: tuple[str, ...]) -> TokenCipher:
    return TokenCipher(keys)


def new_key() -> str:
    return Fernet.generate_key().decode()
