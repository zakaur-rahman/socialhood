"""T5.1: the Gemini provider (TR-AI-02, TR-AI-03) against a mocked SDK client.

Done when: every call carries system_instruction, max_output_tokens and temperature inside
GenerateContentConfig (v1 passed them at the top level, where the SDK ignored them). Plus: schema
validation with one retry, timeouts and HTTP errors as AIErrors, blocked answers, thinking levels,
and embeddings with the task in the text, one Content per text, L2-normalised.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Any, Literal

import pytest
from google.genai import errors, types
from pydantic import BaseModel

from socialhood.ai.gemini import GeminiProvider, embed_prompt, thinking_level
from socialhood.ai.provider import AIError, Turn
from socialhood.settings import AppEnv, Settings


class Verdict(BaseModel):
    label: Literal["yes", "no"]
    score: float


def response(
    text: str,
    *,
    prompt_tokens: int = 50,
    output_tokens: int = 7,
    thoughts: int = 3,
    finish: str = "STOP",
    block: str | None = None,
) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part.from_text(text=text)]),
                finish_reason=types.FinishReason(finish),
            )
        ],
        prompt_feedback=(
            types.GenerateContentResponsePromptFeedback(block_reason=types.BlockedReason(block))
            if block
            else None
        ),
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt_tokens,
            candidates_token_count=output_tokens,
            thoughts_token_count=thoughts,
        ),
    )


@dataclass
class FakeModels:
    """``client.aio.models``: records every call and answers from a queue."""

    answers: list[Any] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    embed_calls: list[dict[str, Any]] = field(default_factory=list)
    dim: int = 768

    async def generate_content(self, **kwargs: Any) -> types.GenerateContentResponse:
        self.calls.append(kwargs)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, BaseException):
            raise answer
        if callable(answer):
            result: types.GenerateContentResponse = await answer()
            return result
        assert isinstance(answer, types.GenerateContentResponse)
        return answer

    async def embed_content(self, **kwargs: Any) -> types.EmbedContentResponse:
        self.embed_calls.append(kwargs)
        count = len(kwargs["contents"])
        return types.EmbedContentResponse(
            embeddings=[
                types.ContentEmbedding(values=[3.0, 4.0] + [0.0] * (self.dim - 2))
                for _ in range(count)
            ]
        )


@dataclass
class FakeAio:
    models: FakeModels


@dataclass
class FakeClient:
    aio: FakeAio


def provider(*answers: Any, dim: int = 768, **settings: Any) -> tuple[GeminiProvider, FakeModels]:
    models = FakeModels(answers=list(answers), dim=dim)
    config = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env=AppEnv.TEST,
        **settings,
    )
    return GeminiProvider(config, client=FakeClient(FakeAio(models))), models


def assert_options_inside_config(
    call: dict[str, Any], *, system: str, tokens: int, temp: float
) -> None:
    """TR-AI-03: nothing at the top level but model, contents and config."""
    assert set(call) == {"model", "contents", "config"}
    config = call["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.system_instruction == system
    assert config.max_output_tokens == tokens
    assert config.temperature == temp
    assert config.thinking_config is not None


async def json_call(p: GeminiProvider, **overrides: Any) -> Any:
    values: dict[str, Any] = {
        "task": "analysis",
        "schema": Verdict,
        "system": "You classify.",
        "contents": [Turn("user", "Is it free?"), Turn("model", "Yes."), Turn("user", "Sure?")],
        "model": "gemini-3.5-flash-lite",
        "max_output_tokens": 400,
        "temperature": 0.0,
        "timeout_s": 8,
    }
    return await p.generate_json(**{**values, **overrides})


async def test_every_option_is_inside_the_config() -> None:
    p, models = provider(response('{"label": "yes", "score": 0.9}'))

    result = await json_call(p)

    assert result.value == Verdict(label="yes", score=0.9)
    [call] = models.calls
    assert_options_inside_config(call, system="You classify.", tokens=400, temp=0.0)
    assert call["model"] == "gemini-3.5-flash-lite"
    config = call["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == Verdict.model_json_schema()
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    assert [(c.role, c.parts[0].text) for c in call["contents"]] == [
        ("user", "Is it free?"),
        ("model", "Yes."),
        ("user", "Sure?"),
    ]
    # Thinking is billed as output.
    assert (result.input_tokens, result.output_tokens) == (50, 10)
    assert result.model == "gemini-3.5-flash-lite"


async def test_text_calls_carry_the_options_too() -> None:
    p, models = provider(response("  Our prices start at 499.  "))

    result = await p.generate_text(
        task="summary",
        system="You summarise.",
        contents=[Turn("user", "hi")],
        model="gemini-3.8-flash",
        max_output_tokens=300,
        temperature=0.4,
        timeout_s=12,
    )

    assert result.value == "Our prices start at 499."
    [call] = models.calls
    assert_options_inside_config(call, system="You summarise.", tokens=300, temp=0.4)
    assert call["config"].response_mime_type is None
    assert call["config"].thinking_config.thinking_level == types.ThinkingLevel.LOW


async def test_invalid_output_is_retried_once_with_the_error() -> None:
    p, models = provider(
        response('{"label": "maybe", "score": 0.5}', prompt_tokens=40, output_tokens=5),
        response('{"label": "no", "score": 0.1}', prompt_tokens=60, output_tokens=6),
    )

    result = await json_call(p)

    assert result.value.label == "no"
    first, second = models.calls
    for call in (first, second):
        assert_options_inside_config(call, system="You classify.", tokens=400, temp=0.0)
    retry_turns = [(c.role, c.parts[0].text) for c in second["contents"]][3:]
    assert retry_turns[0] == ("model", '{"label": "maybe", "score": 0.5}')
    assert retry_turns[1][0] == "user"
    assert "label" in retry_turns[1][1]
    assert "did not match" in retry_turns[1][1]
    assert (result.input_tokens, result.output_tokens) == (100, 17)


async def test_output_invalid_twice_fails_the_call() -> None:
    p, models = provider(response("not json"))

    with pytest.raises(AIError) as raised:
        await json_call(p)

    assert raised.value.code == "invalid_output"
    assert not raised.value.retryable
    assert len(models.calls) == 2


async def test_a_slow_answer_is_a_retryable_timeout() -> None:
    async def slow() -> types.GenerateContentResponse:
        await asyncio.sleep(5)
        return response("{}")

    p, _ = provider(slow)

    with pytest.raises(AIError) as raised:
        await json_call(p, timeout_s=0.05)

    assert (raised.value.code, raised.value.retryable) == ("timeout", True)


@pytest.mark.parametrize(
    ("error", "retryable"),
    [
        (errors.ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED"}}), True),
        (errors.ServerError(503, {"error": {"status": "UNAVAILABLE"}}), True),
        (errors.ServerError(500, {"error": {"status": "INTERNAL"}}), True),
        (errors.ClientError(400, {"error": {"status": "INVALID_ARGUMENT"}}), False),
        (errors.ClientError(403, {"error": {"status": "PERMISSION_DENIED"}}), False),
    ],
)
async def test_http_errors(error: errors.APIError, retryable: bool) -> None:
    p, _ = provider(error)

    with pytest.raises(AIError) as raised:
        await json_call(p)

    assert (raised.value.code, raised.value.retryable) == ("provider_error", retryable)


@pytest.mark.parametrize(
    "answer",
    [response("{}", block="SAFETY"), response("", finish="PROHIBITED_CONTENT")],
)
async def test_blocked_prompts_and_answers(answer: types.GenerateContentResponse) -> None:
    p, _ = provider(answer)

    with pytest.raises(AIError) as raised:
        await json_call(p)

    assert raised.value.code == "blocked"


async def test_without_a_key_nothing_is_called() -> None:
    config = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env=AppEnv.TEST,
    )
    with pytest.raises(AIError) as raised:
        await json_call(GeminiProvider(config))
    assert raised.value.code == "not_configured"


def test_thinking_levels() -> None:
    assert thinking_level("gemini-3.5-flash-lite", {}) == "minimal"
    assert thinking_level("gemini-3.8-flash", {}) == "low"
    assert thinking_level("gemini-3.8-flash", {"gemini-3.8-flash": "medium"}) == "medium"


async def test_configured_thinking_level_reaches_the_config() -> None:
    p, models = provider(
        response('{"label": "yes", "score": 1}'),
        ai_thinking_levels={"gemini-3.5-flash-lite": "low"},
    )
    await json_call(p)
    assert models.calls[0]["config"].thinking_config.thinking_level == types.ThinkingLevel.LOW


def test_embedding_task_format() -> None:
    assert embed_prompt("do you ship?", "query") == "task: search result | query: do you ship?"
    assert (
        embed_prompt("[Shipping] Q: Dubai?\nA: Yes.", "document")
        == "title: Shipping | text: Q: Dubai?\nA: Yes."
    )
    assert embed_prompt("plain note", "document") == "title: none | text: plain note"


async def test_embeddings_one_content_per_text_in_batches_of_100() -> None:
    p, models = provider(response("{}"), dim=768, ai_model_embed="gemini-embedding-2")
    texts = [f"[FAQ {i}] answer {i}" for i in range(150)]

    vectors = await p.embed(texts, kind="document")

    assert len(vectors) == 150
    assert [len(c["contents"]) for c in models.embed_calls] == [100, 50]
    first = models.embed_calls[0]
    assert first["model"] == "gemini-embedding-2"
    assert first["config"].output_dimensionality == 768
    content = first["contents"][0]
    assert isinstance(content, types.Content)
    assert [part.text for part in content.parts] == ["title: FAQ 0 | text: answer 0"]
    assert all(math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0) for vec in vectors)
    assert vectors[0][:2] == pytest.approx([0.6, 0.8])


async def test_embeddings_of_the_wrong_size_are_refused() -> None:
    p, _ = provider(response("{}"), dim=512)

    with pytest.raises(AIError) as raised:
        await p.embed(["how much?"], kind="query")

    assert raised.value.code == "invalid_output"
