"""The Gemini provider (TR-AI-02, TR-AI-03): google-genai's async client, every generation option
inside GenerateContentConfig, the lowest thinking level each model accepts, structured output
validated with the schema (one retry with the error appended), embeddings with the task written
into the text and L2-normalised.

The P5 foundation stub; T5.1 implements it.
"""

from __future__ import annotations

from socialhood.ai.provider import AIError, AIResult, EmbedKind, M, Turn
from socialhood.settings import Settings


class GeminiProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

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
    ) -> AIResult[M]:
        raise AIError("not_configured", "T5.1")

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
    ) -> AIResult[str]:
        raise AIError("not_configured", "T5.1")

    async def embed(self, texts: list[str], *, kind: EmbedKind) -> list[list[float]]:
        raise AIError("not_configured", "T5.1")
