"""Write the public tool reference (01-design.md §7.3): every MCP tool, from the registry.

apps/web/src/lib/marketing/mcp-tools.json is what /developers/mcp lists, so the page can't drift
from the server. tests/unit/test_mcp_tool_reference.py fails when the file is stale.

Usage, after changing a tool: uv run python scripts/export_mcp_tools.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from socialhood.billing.plans import entitlement
from socialhood.mcp.registry import MODE_ADMITS, MODE_ORDER, ConfirmedInput
from socialhood.mcp.tools import load_tools

OUT = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "marketing" / "mcp-tools.json"


def exported() -> dict[str, Any]:
    free_modes = entitlement("free", "ai_connections")
    tools: list[dict[str, Any]] = []
    for tool in load_tools():
        # The least mode that admits the tool: Free can't choose them all.
        mode = next(m for m in MODE_ORDER if tool.access in MODE_ADMITS[m])
        tools.append(
            {
                "name": tool.name,
                "title": tool.title,
                "access": tool.access.value,
                "scope": tool.scope,
                "role": tool.min_role.value,
                "free": mode.value in free_modes,
                "preview": issubclass(tool.input_model, ConfirmedInput),
            }
        )
    return {"tools": tools}


if __name__ == "__main__":
    OUT.write_text(json.dumps(exported(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
