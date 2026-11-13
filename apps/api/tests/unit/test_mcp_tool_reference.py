"""The public tool reference on /developers/mcp is a copy of the MCP registry; this test keeps it
honest (01-design.md §7.3).

apps/web/src/lib/marketing/mcp-tools.json lists every tool with its kind, scope, role, whether
Free can use it and whether it is previewed first. After changing a tool, run

    uv run python scripts/export_mcp_tools.py

to rewrite the file, then review the diff and the page's wording.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_mcp_tools.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("export_mcp_tools", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_public_tool_reference_matches_the_registry() -> None:
    script = load()
    assert json.loads(script.OUT.read_text(encoding="utf-8")) == script.exported(), (
        "An MCP tool changed: run uv run python scripts/export_mcp_tools.py to rewrite "
        "mcp-tools.json in the web app"
    )
