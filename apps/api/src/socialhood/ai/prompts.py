"""Versioned system prompts (TR-AI-04): ``ai/prompts/{task}.v{n}.md`` with ``{placeholders}``.
The version string (e.g. ``analysis.v1``) is stored on every output row. Placeholders take
trusted business settings only; customer and knowledge text go in the contents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROMPTS = Path(__file__).parent / "prompts"
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
CURRENT = {"analysis": 1, "suggest": 1, "summary": 1}


@dataclass(frozen=True)
class Prompt:
    task: str
    version: str  # "analysis.v1"
    template: str

    def render(self, **values: str) -> str:
        """Fill every placeholder; a missing value is an error, an unused one is ignored."""

        def fill(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in values:
                raise KeyError(f"{self.version} needs {{{name}}}")
            return values[name]

        return PLACEHOLDER.sub(fill, self.template).strip()


@lru_cache
def load(task: str, version: int | None = None) -> Prompt:
    n = version or CURRENT[task]
    path = PROMPTS / f"{task}.v{n}.md"
    return Prompt(task=task, version=f"{task}.v{n}", template=path.read_text(encoding="utf-8"))
