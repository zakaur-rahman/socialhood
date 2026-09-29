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
# suggest.v2: reuse KNOWN GAPS labels (C-034). comment_analysis and post_summary: TR-AI-11 (T6.2).
CURRENT = {
    "analysis": 1,
    "suggest": 2,
    "summary": 1,
    "comment_analysis": 1,
    "post_summary": 1,
    # The composer's Write with AI and Suggest hashtags (FR-PUB-02, T7.4).
    "caption": 1,
    "hashtags": 1,
    # Ask Social Hood's planner and report (TR-AGT-02, TA.2).
    "agent": 1,
}


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
