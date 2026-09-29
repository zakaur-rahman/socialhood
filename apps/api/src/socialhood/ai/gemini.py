"""The Gemini provider (TR-AI-02, TR-AI-03): google-genai's async client, every generation option
inside GenerateContentConfig, the lowest thinking level each model accepts, structured output
validated with the schema (one retry with the error appended), embeddings with the task written
into the text and L2-normalised.

- Options: ``system_instruction``, ``temperature``, ``max_output_tokens``, the JSON schema and the
  thinking level all go in ``GenerateContentConfig`` on every call; v1 lost every prompt by passing
  them at the top level (TR-AI-03). The installed SDK has no ``response_format``: structured output
  is ``response_mime_type="application/json"`` with ``response_json_schema`` (C-032).
- Thinking: Gemini 3 models cannot turn it off and bill it as output, so each call uses the lowest
  level the model accepts: "minimal" for Flash-Lite, "low" otherwise (Flash rejects minimal).
  ``AI_THINKING_LEVELS`` (JSON, model id to level) overrides it per model.
- Structured output is never trusted: the text is validated with the schema; on failure the call
  is repeated once with the invalid answer and the validation error appended, then
  ``AIError("invalid_output")``.
- Errors: a timeout (``timeout_s`` around the call) is ``AIError("timeout", retryable=True)``;
  HTTP 429 and 5xx are retryable ``provider_error``s, other 4xx are not; a blocked prompt or
  answer is ``blocked``; a missing key is ``not_configured``. The SDK's own retries stay off (its
  default), so the job's retry policy is the only one.
- Embeddings (gemini-embedding-2 has no ``task_type``): the task goes into the text in the format of
  Google's Embedding 2 guide, "task: search result | query: …" for queries and "title: … | text: …"
  for documents (a chunk's "[{source title}] " prefix becomes the title). Each text is its own
  ``Content``: several parts in one Content come back as one aggregated embedding. Batches of 100,
  ``output_dimensionality`` from ``AI_EMBED_DIM``, every vector L2-normalised (TR-AI-08).
"""

from __future__ import annotations

import asyncio
import math
import re
import time
from typing import Any

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from socialhood.ai.provider import AIError, AIResult, EmbedKind, M, Turn
from socialhood.observability.logging import get_logger
from socialhood.settings import Settings

log = get_logger(__name__)

EMBED_BATCH = 100  # TR-AI-08
EMBED_TIMEOUT_S = 30.0
RETRYABLE_STATUS = frozenset({408, 429})
BLOCKED_FINISH = frozenset({"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"})
TITLED_CHUNK = re.compile(r"\A\[([^\]\n]{1,200})\] (.*)\Z", re.DOTALL)
RETRY_PROMPT = (
    "Your previous answer did not match the required JSON schema: {error}\n"
    "Answer again with only JSON that matches the schema."
)


def thinking_level(model: str, overrides: dict[str, str]) -> str:
    """The lowest thinking level ``model`` accepts (TR-AI-03), unless configured."""
    if model in overrides:
        return overrides[model]
    return "minimal" if "flash-lite" in model else "low"


def embed_prompt(text: str, kind: EmbedKind) -> str:
    """Embedding 2's task format: asymmetric retrieval, "search result" (RETRIEVAL_QUERY)."""
    if kind == "query":
        return f"task: search result | query: {text}"
    match = TITLED_CHUNK.match(text)
    if match:
        return f"title: {match.group(1)} | text: {match.group(2)}"
    return f"title: none | text: {text}"


def l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values))
    return [v / norm for v in values] if norm else values


def _contents(turns: list[Turn]) -> list[types.Content]:
    return [types.Content(role=t.role, parts=[types.Part.from_text(text=t.text)]) for t in turns]


def _schema_error(error: ValidationError | ValueError) -> str:
    if isinstance(error, ValidationError):
        problems = [
            f"{'.'.join(str(p) for p in e['loc']) or 'answer'}: {e['msg']}"
            for e in error.errors()[:5]
        ]
        return "; ".join(problems)
    return str(error)[:300]


class GeminiProvider:
    def __init__(self, settings: Settings, *, client: Any = None) -> None:
        self.settings = settings
        self._client = client

    # ---- plumbing

    def _sdk(self) -> Any:
        if self._client is None:
            key = self.settings.gemini_api_key
            if key is None or not key.get_secret_value():
                raise AIError("not_configured", "GEMINI_API_KEY is not set")
            self._client = genai.Client(api_key=key.get_secret_value())
        return self._client

    def _config(
        self,
        *,
        system: str,
        model: str,
        max_output_tokens: int,
        temperature: float,
        schema: type[BaseModel] | None,
    ) -> types.GenerateContentConfig:
        """Every option inside the config (TR-AI-03)."""
        return types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json" if schema is not None else None,
            response_json_schema=schema.model_json_schema() if schema is not None else None,
            thinking_config=types.ThinkingConfig(
                thinking_level=thinking_level(model, self.settings.ai_thinking_levels)
            ),
        )

    async def _generate(
        self,
        *,
        task: str,
        model: str,
        contents: list[Turn],
        config: types.GenerateContentConfig,
        timeout_s: float,
    ) -> types.GenerateContentResponse:
        client = self._sdk()
        try:
            response: types.GenerateContentResponse = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model, contents=_contents(contents), config=config
                ),
                timeout=timeout_s,
            )
        except TimeoutError as error:
            raise AIError(
                "timeout", f"{task}: no answer in {timeout_s} s", retryable=True
            ) from error
        except httpx.TimeoutException as error:
            raise AIError("timeout", f"{task}: {type(error).__name__}", retryable=True) from error
        except errors.APIError as error:
            raise _api_error(task, error) from error
        except httpx.TransportError as error:
            raise AIError("provider_error", f"{task}: {error}", retryable=True) from error
        _raise_if_blocked(task, response)
        return response

    # ---- AIProvider

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
        config = self._config(
            system=system,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            schema=schema,
        )
        started = time.monotonic()
        turns = list(contents)
        tokens_in = tokens_out = 0
        problem = ""
        for attempt in range(2):
            response = await self._generate(
                task=task, model=model, contents=turns, config=config, timeout_s=timeout_s
            )
            used_in, used_out = _usage(response)
            tokens_in += used_in
            tokens_out += used_out
            text = response.text or ""
            try:
                value = schema.model_validate_json(text)
            except (ValidationError, ValueError) as error:
                problem = _schema_error(error)
                log.warning("ai_invalid_output", task=task, model=model, attempt=attempt + 1)
                turns = [
                    *turns,
                    Turn("model", text or "(empty)"),
                    Turn("user", RETRY_PROMPT.format(error=problem)),
                ]
                continue
            return AIResult(
                value=value,
                model=model,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                latency_ms=_elapsed_ms(started),
            )
        raise AIError("invalid_output", f"{task}: {problem}")

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
        config = self._config(
            system=system,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            schema=None,
        )
        started = time.monotonic()
        response = await self._generate(
            task=task, model=model, contents=contents, config=config, timeout_s=timeout_s
        )
        text = (response.text or "").strip()
        if not text:
            raise AIError("invalid_output", f"{task}: empty answer")
        tokens_in, tokens_out = _usage(response)
        return AIResult(
            value=text,
            model=model,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            latency_ms=_elapsed_ms(started),
        )

    async def embed(self, texts: list[str], *, kind: EmbedKind) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            vectors.extend(await self._embed_batch(texts[start : start + EMBED_BATCH], kind))
        return vectors

    async def _embed_batch(self, texts: list[str], kind: EmbedKind) -> list[list[float]]:
        client = self._sdk()
        dim = self.settings.ai_embed_dim
        try:
            response: types.EmbedContentResponse = await asyncio.wait_for(
                client.aio.models.embed_content(
                    model=self.settings.ai_model_embed,
                    contents=[
                        types.Content(parts=[types.Part.from_text(text=embed_prompt(t, kind))])
                        for t in texts
                    ],
                    config=types.EmbedContentConfig(output_dimensionality=dim),
                ),
                timeout=EMBED_TIMEOUT_S,
            )
        except (TimeoutError, httpx.TimeoutException) as error:
            raise AIError("timeout", "embed", retryable=True) from error
        except errors.APIError as error:
            raise _api_error("embed", error) from error
        except httpx.TransportError as error:
            raise AIError("provider_error", f"embed: {error}", retryable=True) from error
        embeddings = response.embeddings or []
        values = [list(e.values or []) for e in embeddings]
        if len(values) != len(texts) or any(len(v) != dim for v in values):
            raise AIError(
                "invalid_output",
                f"embed: {len(values)} vectors for {len(texts)} texts, expected {dim} values each",
            )
        return [l2_normalize(v) for v in values]


def _api_error(task: str, error: errors.APIError) -> AIError:
    code = int(error.code or 0)
    retryable = code in RETRYABLE_STATUS or code >= 500
    return AIError("provider_error", f"{task}: HTTP {code} {error.status}", retryable=retryable)


def _raise_if_blocked(task: str, response: types.GenerateContentResponse) -> None:
    feedback = response.prompt_feedback
    if feedback is not None and feedback.block_reason is not None:
        raise AIError("blocked", f"{task}: prompt blocked ({feedback.block_reason})")
    candidates = response.candidates or []
    if candidates:
        reason = candidates[0].finish_reason
        name = getattr(reason, "value", reason)
        if name in BLOCKED_FINISH:
            raise AIError("blocked", f"{task}: answer blocked ({name})")


def _usage(response: types.GenerateContentResponse) -> tuple[int, int]:
    """Input and output tokens; thinking is billed as output (TR-AI-03)."""
    usage = response.usage_metadata
    if usage is None:
        return 0, 0
    output = (usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)
    return usage.prompt_token_count or 0, output


def _elapsed_ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)
