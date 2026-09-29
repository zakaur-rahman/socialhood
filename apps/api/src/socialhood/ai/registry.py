"""Which AI provider this process uses (TR-AI-01): Gemini, or the fake with ``AI_PROVIDER=fake``
(local runs without a key). Tests swap it with ``use_provider``."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from socialhood.ai.provider import AIProvider
from socialhood.settings import get_settings

_override: list[AIProvider] = []


@lru_cache
def _configured() -> AIProvider:
    settings = get_settings()
    if settings.ai_provider == "fake":
        from socialhood.ai.fake import FakeProvider

        return FakeProvider()
    from socialhood.ai.gemini import GeminiProvider

    return GeminiProvider(settings)


def get_provider() -> AIProvider:
    return _override[-1] if _override else _configured()


@contextmanager
def use_provider(provider: AIProvider) -> Iterator[AIProvider]:
    """Tests: every get_provider() in the block returns ``provider``."""
    _override.append(provider)
    try:
        yield provider
    finally:
        _override.pop()
