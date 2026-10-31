"""The MCP server's tools (C-165; 01-design.md §4.1), one module per area. Each module registers
its tools on ``mcp.registry.registry`` when imported; ``load_tools`` imports them all.

Rules for every tool (the registry checks what it can):
- a thin adapter: validate, resolve friendly ids, call the services (or Ask Amplychat's tools,
  agent/tools/*, which already shape results for a model), shape a compact result;
- never business logic of its own, never SQL that bypasses tenancy (the session is in the
  connection's workspace scope);
- customer-written text only in fields ending in ``_text``;
- lists capped (20 by default) and saying how many more there are;
- times echoed in the workspace's zone and UTC.

Phase A ships the read tools; phase B adds the writes and media uploads.
"""

from __future__ import annotations

from importlib import import_module

from socialhood.mcp.registry import McpRegistry, registry

TOOL_MODULES = (
    "socialhood.mcp.tools.workspace",
    "socialhood.mcp.tools.posts",
    "socialhood.mcp.tools.media",
    "socialhood.mcp.tools.inbox",
    "socialhood.mcp.tools.insights",
    "socialhood.mcp.tools.knowledge",
)


def load_tools() -> McpRegistry:
    for module in TOOL_MODULES:
        import_module(module)
    return registry
