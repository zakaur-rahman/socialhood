"""The agent eval against the real model (TA.6), opt-in: it calls Gemini for every case, so it
runs only with AGENT_EVAL=1 (and a Gemini key in .env). It seeds the test database fresh, runs
every case in cases.py and asserts the targets: tool choice at least 90%, every expected number
in the answer, no invented number.

    AGENT_EVAL=1 uv run pytest tests/evals -m agent_eval -s

``python scripts/agent_eval.py`` runs the same eval with options and a report per run.
"""

from __future__ import annotations

import os

import pydantic_ai.models
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.settings import get_settings
from tests.evals.runner import EVAL_RETRIEVAL_MIN_SIM, TARGETS, run_eval

pytestmark = [
    pytest.mark.agent_eval,
    pytest.mark.skipif(os.environ.get("AGENT_EVAL") != "1", reason="calls Gemini: AGENT_EVAL=1"),
]


async def test_the_agent_meets_its_eval_targets(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pydantic_ai.models, "ALLOW_MODEL_REQUESTS", True)
    monkeypatch.setenv("IG_HUMAN_AGENT_ENABLED", "false")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_RETRIEVAL_MIN_SIM", EVAL_RETRIEVAL_MIN_SIM)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        if settings.gemini_api_key is None:
            pytest.skip("GEMINI_API_KEY is not set")
        summary, _ = await run_eval(settings, label="pytest")
    finally:
        get_settings.cache_clear()
    reached = {name: getattr(summary, name) for name in TARGETS}
    assert all(summary.meets_targets().values()), f"targets {TARGETS}, reached {reached}"
