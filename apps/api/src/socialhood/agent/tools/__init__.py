"""The agent's tools (FR-AGT-02, FR-AGT-03, TR-AGT-03, TA.4; agent-architecture.html §5, §6): thin
typed adapters over existing services, one module per area. Each module registers its
``ToolSpec``s on ``agent.registry.registry`` when imported; ``load_tools`` imports them all.

Rules for every tool:
- Call services, which call repositories (tenancy): never model-written SQL, never a platform API.
- The session is in the run's workspace scope, so another workspace's ids resolve to nothing and
  the tool says so ("not found"), never an error that reveals the row exists.
- Results extend ``ToolResult``: a plain-words ``summary``, ``refs`` for citations, ``caveats``
  for data that isn't available (FR-AGT-06); lists capped and saying how many more exist; numbers
  from services with their time range and sample size (FR-AGT-04).
- Times arrive resolved (agent/timeparse.py) and results echo the range they used (FR-AGT-05).
- Read tools change nothing; draft tools return a ``DraftResult`` with an action card and change
  nothing either (FR-AGT-02, FR-AGT-03). Write tools are R2 and go through the gateway.
- The principal's role bounds each tool (``min_role``): automations, knowledge and publishing
  tools are for owners and admins, as in the UI.
"""

from __future__ import annotations

from importlib import import_module

from socialhood.agent.registry import ToolRegistry, registry

TOOL_MODULES = (
    "socialhood.agent.tools.conversations",
    "socialhood.agent.tools.comments",
    "socialhood.agent.tools.posts",
    "socialhood.agent.tools.analytics",
    "socialhood.agent.tools.scheduling",
    "socialhood.agent.tools.automations",
    "socialhood.agent.tools.knowledge",
)


def load_tools() -> ToolRegistry:
    """Import every tool module (each registers its tools once) and return the registry."""
    for module in TOOL_MODULES:
        import_module(module)
    return registry
