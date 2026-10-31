"""The MCP tool registry and the conventions every tool follows (C-165; 01-design.md §4, §6).

A tool is an ``McpTool``: a typed async handler with a Pydantic input model (its
``inputSchema``) and an output model extending ``ToolOutput`` (its ``outputSchema``; the result
is ``structuredContent`` plus a text copy). Each tool declares, in code:

- ``scope``: the one scope it needs (§3.4); ``tools/list`` shows only tools the principal's
  scopes open;
- ``access``: read, draft or write. The workspace's effective mode (its setting capped by the
  plan, D2 and D3) admits read in ``read_only``, read and draft in ``read_drafts``, all in
  ``full``; ``off`` admits nothing but the tools marked ``always_listed`` (get_workspace, which
  says the mode is off);
- ``min_role``: the least member role that may use it, as in the app (the role cap, §3.5);
- the annotations: ``readOnlyHint`` (from ``access``), ``destructiveHint``, ``idempotentHint``
  and ``openWorldHint``, always explicit booleans (Anthropic's and OpenAI's review);
- ``dedupe_window_s`` (writes): identical calls of one connection inside the window return the
  first result instead of running again (§6.2). Writes also take an ``idempotency_key``
  argument, required on their input model.

``register`` refuses a tool that breaks these at import, the MCP twin of the agent's
``ToolRegistry`` (agent/registry.py). Descriptions are prompts other AIs read: static strings,
short and factual, never with text that steers the model ("always", "you must", "ignore …") or
links to other sites; the registry refuses those (§6.5).
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import mcp_types as types
from pydantic import BaseModel, ConfigDict, Field

from socialhood.auth.deps import ROLE_RANK
from socialhood.mcp.context import ToolCall
from socialhood.models.identity import Role
from socialhood.models.mcp import AiConnectionsMode
from socialhood.schemas.api_keys import ApiScopeName

TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
DESCRIPTION_MAX_CHARS = 1000
# Words aimed at the model rather than describing the tool (01-design.md §6.5, test 2 of §8).
BANNED_PHRASES = re.compile(
    r"\b(always|you must|you should|must not|ignore|disregard|system prompt|instructions?)\b",
    re.IGNORECASE,
)
URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
OWN_HOSTS = ("amplychat.com",)

# Every scope a tool may need: the API key catalogue plus the one every principal holds.
MCP_SCOPES: frozenset[str] = frozenset({*ApiScopeName.__args__, "workspace:read"})  # type: ignore[attr-defined]


class Access(StrEnum):
    READ = "read"  # changes nothing
    DRAFT = "draft"  # prepares something a member acts on in the app; changes nothing outside
    WRITE = "write"  # changes the workspace or what it will publish


# What each effective mode admits (§6.7).
MODE_ADMITS: dict[AiConnectionsMode, frozenset[Access]] = {
    AiConnectionsMode.OFF: frozenset(),
    AiConnectionsMode.READ_ONLY: frozenset({Access.READ}),
    AiConnectionsMode.READ_DRAFTS: frozenset({Access.READ, Access.DRAFT}),
    AiConnectionsMode.FULL: frozenset({Access.READ, Access.DRAFT, Access.WRITE}),
}
MODE_ORDER: tuple[AiConnectionsMode, ...] = tuple(AiConnectionsMode)


class ToolInput(BaseModel):
    """Base of every tool's input: unknown arguments are refused, so a typo is an error the
    model can fix rather than an argument silently ignored."""

    model_config = ConfigDict(extra="forbid")


class ToolOutput(BaseModel):
    """Base of every tool's structured result. ``summary``: the result in one plain sentence;
    ``caveats``: what the data couldn't show, so the AI says so instead of guessing."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=400)
    caveats: list[str] = Field(default_factory=list)


class WriteInput(ToolInput):
    """Base of a write tool's input (phase B): the optional idempotency key (§6.2). A tool
    argument, because MCP clients can't set per-call HTTP headers."""

    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=100,
        description="Any unique string. Retrying with the same key returns the first result.",
    )


class WriteOutput(ToolOutput):
    """Base of a write tool's result: ``duplicate_of_previous_call`` is true when this is the
    stored result of an earlier identical call (an idempotency key, or the dedupe window)."""

    duplicate_of_previous_call: bool = False
    # True when nothing was changed because the call wasn't confirmed: the result shows what the
    # call would do (the resolved time, the checklist), and a call with ``confirmed: true`` does
    # it. A preview is never stored for replay.
    preview: bool = False


type Handler[I: ToolInput, O: ToolOutput] = Callable[[ToolCall, I], Awaitable[O]]


class ToolRegistryError(ValueError):
    """A tool the registry refuses: raised at import, so it fails fast."""


@dataclass(frozen=True, kw_only=True)
class McpTool[I: ToolInput, O: ToolOutput]:
    name: str
    title: str
    description: str
    input_model: type[I]
    output_model: type[O]
    scope: str
    access: Access
    handler: Handler[I, O]
    min_role: Role = Role.AGENT
    destructive: bool = False
    idempotent: bool = True
    open_world: bool = False
    always_listed: bool = False  # listed and callable whatever the mode (get_workspace)
    dedupe_window_s: int | None = None

    @property
    def read_only(self) -> bool:
        return self.access is Access.READ

    def annotations(self) -> types.ToolAnnotations:
        return types.ToolAnnotations(
            title=self.title,
            read_only_hint=self.read_only,
            destructive_hint=self.destructive,
            idempotent_hint=self.idempotent,
            open_world_hint=self.open_world,
        )

    def definition(self) -> types.Tool:
        return types.Tool(
            name=self.name,
            title=self.title,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            output_schema=self.output_model.model_json_schema(),
            annotations=self.annotations(),
        )

    def allowed_for(self, *, scopes: frozenset[str], role: Role) -> bool:
        return self.scope in scopes and ROLE_RANK[role] >= ROLE_RANK[self.min_role]

    def admitted_by(self, mode: AiConnectionsMode) -> bool:
        return self.always_listed or self.access in MODE_ADMITS[mode]


def _foreign_urls(text: str) -> list[str]:
    return [u for u in URL.findall(text) if not any(host in u.lower() for host in OWN_HOSTS)]


class McpRegistry:
    """The tools that exist, by name; ``visible`` is what one principal's ``tools/list`` shows."""

    def __init__(self) -> None:
        self._tools: dict[str, McpTool[Any, Any]] = {}

    def register[I: ToolInput, O: ToolOutput](self, tool: McpTool[I, O]) -> McpTool[I, O]:
        name = tool.name
        if not TOOL_NAME.fullmatch(name):
            raise ToolRegistryError(f"tool name {name!r} must be snake_case, 3-64 characters")
        if name in self._tools:
            raise ToolRegistryError(f"tool {name!r} is already registered")
        if not tool.title.strip() or not tool.description.strip():
            raise ToolRegistryError(f"tool {name!r} needs a title and a description")
        if len(tool.description) > DESCRIPTION_MAX_CHARS:
            raise ToolRegistryError(f"tool {name!r}: the description is too long")
        for text in (tool.title, tool.description, *_field_descriptions(tool.input_model)):
            if found := BANNED_PHRASES.search(text):
                raise ToolRegistryError(f"tool {name!r}: {found.group(0)!r} steers the model")
            if urls := _foreign_urls(text):
                raise ToolRegistryError(f"tool {name!r}: links to another site: {urls[0]}")
        if tool.scope not in MCP_SCOPES:
            raise ToolRegistryError(f"tool {name!r}: unknown scope {tool.scope!r}")
        if not isinstance(tool.access, Access):
            raise ToolRegistryError(f"tool {name!r} has no access level")
        if not (isinstance(tool.input_model, type) and issubclass(tool.input_model, ToolInput)):
            raise ToolRegistryError(f"tool {name!r}: the input model must extend ToolInput")
        if not (isinstance(tool.output_model, type) and issubclass(tool.output_model, ToolOutput)):
            raise ToolRegistryError(f"tool {name!r}: the output model must extend ToolOutput")
        if tool.access is Access.READ and (tool.destructive or tool.dedupe_window_s):
            raise ToolRegistryError(f"read tool {name!r} can't be destructive or deduplicated")
        if tool.access is Access.WRITE and not (
            issubclass(tool.input_model, WriteInput) and issubclass(tool.output_model, WriteOutput)
        ):
            raise ToolRegistryError(
                f"write tool {name!r}: the input must extend WriteInput, the output WriteOutput"
            )
        if tool.always_listed and tool.access is not Access.READ:
            raise ToolRegistryError(f"tool {name!r}: only a read tool can be always listed")
        if not inspect.iscoroutinefunction(tool.handler):
            raise ToolRegistryError(f"tool {name!r}: the handler must be an async function")
        self._tools[name] = tool
        return tool

    def get(self, name: str) -> McpTool[Any, Any] | None:
        return self._tools.get(name)

    def visible(
        self, *, scopes: frozenset[str], role: Role, mode: AiConnectionsMode
    ) -> list[McpTool[Any, Any]]:
        """The tools a principal may call now, by name (a deterministic ``tools/list``)."""
        return [
            tool
            for tool in self
            if tool.allowed_for(scopes=scopes, role=role) and tool.admitted_by(mode)
        ]

    def __iter__(self) -> Iterator[McpTool[Any, Any]]:
        return iter([self._tools[name] for name in sorted(self._tools)])

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools


def _field_descriptions(model: type[BaseModel]) -> list[str]:
    return [f.description for f in model.model_fields.values() if f.description]


def tool[I: ToolInput, O: ToolOutput](
    registry: McpRegistry,
    *,
    name: str,
    title: str,
    description: str,
    input_model: type[I],
    output_model: type[O],
    scope: str,
    access: Access = Access.READ,
    min_role: Role = Role.AGENT,
    destructive: bool = False,
    idempotent: bool = True,
    open_world: bool = False,
    always_listed: bool = False,
    dedupe_window_s: int | None = None,
) -> Callable[[Handler[I, O]], McpTool[I, O]]:
    """Register the decorated handler as a tool on ``registry``."""

    def register(handler: Handler[I, O]) -> McpTool[I, O]:
        return registry.register(
            McpTool(
                name=name,
                title=title,
                description=description,
                input_model=input_model,
                output_model=output_model,
                scope=scope,
                access=access,
                handler=handler,
                min_role=min_role,
                destructive=destructive,
                idempotent=idempotent,
                open_world=open_world,
                always_listed=always_listed,
                dedupe_window_s=dedupe_window_s,
            )
        )

    return register


# The server's tools; mcp/tools/* register on it (mcp.tools.load_tools()).
registry = McpRegistry()
