"""What the MCP tool modules share (C-165).

- ``agent_tool``: run one of Ask Amplychat's tools (agent/tools/*) for the MCP principal. Those
  handlers are already built for a model to read (compact, capped, numbers from services), so the
  MCP tools that wrap them only rename and reshape fields: one definition of what an AI sees
  (01-design.md §2.4). Their own role bound (``min_role``) still applies.
- ``moment``: a stored time as both the workspace's local time and UTC, so a wrong time-zone
  guess is visible (§2.5).
- Field names: customer-written text is in fields ending in ``_text`` (mcp/results.py).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from socialhood.agent.tools import load_tools as load_agent_tools
from socialhood.errors import ApiError, FieldError
from socialhood.mcp.context import ToolCall

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


async def agent_tool(call: ToolCall, name: str, arguments: dict[str, Any]) -> Any:
    """The result of Ask Amplychat's tool ``name`` with ``arguments`` (None values dropped)."""
    spec = load_agent_tools().get(name)
    if spec is None:  # pragma: no cover - a renamed agent tool is caught by the tests
        raise RuntimeError(f"no agent tool {name}")
    try:
        args = spec.input_model.model_validate(
            {k: v for k, v in arguments.items() if v is not None}
        )
    except ValidationError as error:
        raise ApiError(
            "validation_error",
            "Some arguments aren't valid. Fix them and try again.",
            errors=[
                FieldError(".".join(str(p) for p in e["loc"]), e["msg"])
                for e in error.errors(include_url=False)
            ],
        ) from error
    return await spec.handler(call.agent_context(), args)


def clock(at: datetime) -> str:
    hour = at.hour % 12 or 12
    return f"{hour}:{at.minute:02d} {'am' if at.hour < 12 else 'pm'}"


def moment(call: ToolCall, at: datetime | None) -> str | None:
    """ "Fri 7 Nov 2026, 6:00 pm Asia/Kolkata (12:30 UTC)"."""
    if at is None:
        return None
    local = at.astimezone(call.timezone)
    utc = at.astimezone(UTC)
    day = f"{DAYS[local.weekday()]} {local.day} {MONTHS[local.month - 1]} {local.year}"
    return f"{day}, {clock(local)} {call.timezone.key} ({utc.hour:02d}:{utc.minute:02d} UTC)"
