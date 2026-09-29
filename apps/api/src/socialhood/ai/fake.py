"""A deterministic AI provider for tests and for running the app without a Gemini key
(``AI_PROVIDER=fake``; TR-AI-01).

- ``generate_json`` / ``generate_text`` return what a test queued for the task with ``respond``
  (a value, a callable of the call, or an ``AIError`` to raise), else the task's default.
- ``embed`` hashes words into a bag-of-words vector and L2-normalises it, so texts sharing words
  are similar and retrieval behaves meaningfully in tests.
- Every call is recorded in ``calls`` with everything the provider was given.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from socialhood.ai.provider import AIError, AIResult, EmbedKind, M, Turn
from socialhood.models.ai import EMBED_DIM

WORD = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class FakeCall:
    task: str
    system: str
    contents: list[Turn]
    model: str
    max_output_tokens: int
    temperature: float
    timeout_s: float
    schema: type[BaseModel] | None = None


Responder = Any  # a value, a Callable[[FakeCall], value] or an AIError to raise


DEFAULTS: dict[str, dict[str, Any]] = {
    "analysis": {
        "intent": "other",
        "sentiment": "neutral",
        "sentiment_score": 0.0,
        "priority": "low",
        "lead_score": 10,
        "language": "en",
        "topics": [],
        "needs_reply": True,
        "needs_human": False,
        "needs_human_reason": None,
    },
    "suggest": {
        "can_answer": False,
        "reply": None,
        "missing_info": "the answer to this question",
        "missing_topic": "unknown topic",
        "confidence": 0.3,
        "used_source_ids": [],
    },
    "summary": {"summary": "The customer asked a question.", "next_step": None},
}


@dataclass
class FakeProvider:
    calls: list[FakeCall] = field(default_factory=list)
    embed_calls: list[tuple[list[str], EmbedKind]] = field(default_factory=list)
    _queued: dict[str, deque[Responder]] = field(default_factory=lambda: defaultdict(deque))
    model_name: str = "fake-model"
    input_tokens: int = 100
    output_tokens: int = 20

    def respond(self, task: str, *responses: Responder) -> None:
        """Queue responses for ``task``, used in order; the last one repeats."""
        self._queued[task].extend(responses)

    def calls_for(self, task: str) -> list[FakeCall]:
        return [c for c in self.calls if c.task == task]

    def _next(self, call: FakeCall) -> Any:
        queue = self._queued.get(call.task)
        if queue:
            response = queue.popleft() if len(queue) > 1 else queue[0]
        else:
            response = DEFAULTS.get(call.task, {})
        if isinstance(response, AIError):
            raise response
        if callable(response):
            response = response(call)
            if isinstance(response, AIError):
                raise response
        return response

    def _result(self, value: Any, model: str) -> AIResult[Any]:
        return AIResult(
            value=value,
            model=model or self.model_name,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            latency_ms=5,
        )

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
        call = FakeCall(
            task, system, list(contents), model, max_output_tokens, temperature, timeout_s, schema
        )
        self.calls.append(call)
        value = self._next(call)
        parsed = value if isinstance(value, schema) else schema.model_validate(value)
        return self._result(parsed, model)

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
        call = FakeCall(
            task, system, list(contents), model, max_output_tokens, temperature, timeout_s
        )
        self.calls.append(call)
        return self._result(str(self._next(call)), model)

    async def embed(self, texts: list[str], *, kind: EmbedKind) -> list[list[float]]:
        self.embed_calls.append((list(texts), kind))
        return [bag_of_words(text) for text in texts]


def bag_of_words(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Each lowercase word adds 1 to a hashed dimension; L2-normalised (zero text: a unit
    vector on dimension 0, so cosine distance stays defined)."""
    vector = [0.0] * dim
    for word in WORD.findall(text.casefold()):
        digest = hashlib.blake2b(word.encode(), digest_size=4).digest()
        vector[int.from_bytes(digest, "big") % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        vector[0] = 1.0
        return vector
    return [v / norm for v in vector]


FakeResponder = Callable[[FakeCall], Any]
