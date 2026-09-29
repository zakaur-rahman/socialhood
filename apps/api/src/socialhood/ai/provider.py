"""The AI provider interface (TR-AI-01). ``ai/gemini.py`` is the one implementation in R1; tests
use ``ai/fake.FakeProvider``.

Customer and knowledge text travel as ``contents`` (data), never inside ``system`` (TR-AI-04,
SEC-10). A provider validates structured output against the schema and retries once with the
error appended as a user turn before raising ``AIError("invalid_output")`` (TR-AI-03).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)

Role = Literal["user", "model"]
EmbedKind = Literal["document", "query"]
AIErrorCode = Literal["timeout", "invalid_output", "provider_error", "blocked", "not_configured"]


@dataclass(frozen=True)
class Turn:
    role: Role
    text: str


@dataclass(frozen=True)
class AIResult[T]:
    value: T
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class AIError(Exception):
    """A failed AI call. ``retryable`` errors (timeouts, 429s, 5xx) may be retried by the job;
    the caller refunds reserved credits either way (TR-AI-09)."""

    def __init__(self, code: AIErrorCode, message: str = "", *, retryable: bool = False) -> None:
        super().__init__(message or code)
        self.code: AIErrorCode = code
        self.retryable = retryable


class AIProvider(Protocol):
    async def generate_json(
        self,
        *,
        task: str,
        schema: type[M],
        system: str,
        contents: list[Turn],
        model: str,
        max_output_tokens: int,
        temperature: float,
        timeout_s: float,
    ) -> AIResult[M]: ...

    async def generate_text(
        self,
        *,
        task: str,
        system: str,
        contents: list[Turn],
        model: str,
        max_output_tokens: int,
        temperature: float,
        timeout_s: float,
    ) -> AIResult[str]: ...

    async def embed(self, texts: list[str], *, kind: EmbedKind) -> list[list[float]]:
        """L2-normalised vectors of ``settings.ai_embed_dim`` values, one per text."""
        ...
