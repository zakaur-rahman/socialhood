"""Tool metadata and the registry (TR-AGT-03; agent-architecture.html §5, §8).

Every tool is a typed async function with a Pydantic input model, a result model derived from
``ToolResult``, a fixed risk tier, a capability switch (writes only) and the release it ships in.
Tool modules (agent/tools/) register their specs on the module-level ``registry`` when imported;
``agent.tools.load_tools()`` imports them all. The planner exposes ``registry.available()`` to the
model and the executor looks tools up by name, so a tool the registry refused never runs.

A tool's tier is fixed in code; arguments can only raise it (a reply to more than one comment is
high, more than the policy's bulk_max is refused, §8). The model's output never changes a tier,
a capability or the policy: there are no policy tools.
"""

from __future__ import annotations

import inspect
import re
import uuid
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.auth.deps import ROLE_RANK
from socialhood.models.agent import WRITE_TIERS, AgentCapability, RiskTier
from socialhood.models.identity import Role
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.schemas.agent import ActionCard, AnswerRef

TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
SUMMARY_MAX_CHARS = 300


class Release(StrEnum):
    """Which release a tool ships in (§13). Only tools at or before ``CURRENT_RELEASE`` exist."""

    R1 = "r1"
    R2 = "r2"
    R3 = "r3"


RELEASE_ORDER: tuple[Release, ...] = (Release.R1, Release.R2, Release.R3)
CURRENT_RELEASE = Release.R1


class ToolRegistryError(ValueError):
    """A tool spec the registry refuses (TR-AGT-03): raised at import, so it fails fast."""


# ---------------------------------------------------------------- what a tool receives


@dataclass(frozen=True, kw_only=True)
class Principal:
    """Who the run acts for (§8): a request can never do more than this member could by hand."""

    user_id: uuid.UUID | None  # None for standing instructions (R3)
    role: Role


@dataclass(kw_only=True)
class ToolContext:
    """The run's dependencies (TR-AGT-02), the same object Pydantic AI carries as ``deps``.

    The session is in the workspace's scope (tenancy), so another workspace's ids never resolve.
    Every relative time in one run resolves against ``now`` in ``timezone`` (FR-AGT-05).
    """

    session: AsyncSession
    sessionmaker: async_sessionmaker[AsyncSession]  # metered AI calls take their own transactions
    platform: PlatformDeps  # account capabilities (TR-PL-11); no platform calls in R1
    workspace_id: uuid.UUID
    timezone: ZoneInfo  # the workspace's
    now: datetime  # the run's clock (UTC)
    principal: Principal
    run_id: uuid.UUID


# ---------------------------------------------------------------- what a tool returns


class ToolResult(BaseModel):
    """Base of every tool's result model: compact and capped (TR-AGT-03). Stored as the step's
    result and shown to the model; the report is written from these results only.

    Subclasses add the tool's own typed fields. A list is capped and says how many more exist
    (for example ``items`` plus ``more``). Numbers are computed by services, never by the model
    (FR-AGT-04), and carry the time range and sample size they cover.
    """

    model_config = ConfigDict(extra="forbid")

    # The result in plain words for the live steps and run history, e.g. "Found 57 negative
    # comments from the last 30 days".
    summary: str = Field(min_length=1, max_length=SUMMARY_MAX_CHARS)
    # Records the result used; the answer cites only these (FR-AGT-01).
    refs: list[AnswerRef] = Field(default_factory=list)
    # What the data couldn't show, in plain words ("Insights aren't granted for @maple.bakery",
    # "91 comments aren't analysed yet"); the answer says so instead of guessing (FR-AGT-06).
    caveats: list[str] = Field(default_factory=list)


class DraftResult(ToolResult):
    """A draft tool's result (FR-AGT-03): something for a person to act on; nothing changes. The
    card opens the existing screen pre-filled and lands in the run's ``action_cards``."""

    action_card: ActionCard


type ToolHandler[I: BaseModel, R: ToolResult] = Callable[[ToolContext, I], Awaitable[R]]


@dataclass(frozen=True, kw_only=True)
class ToolSpec[I: BaseModel, R: ToolResult]:
    """One tool (TR-AGT-03, §5)."""

    name: str  # snake_case, unique: the name the model calls
    label: str  # plain words for live steps, e.g. "Looking up your latest post"
    description: str  # what the model reads when choosing tools
    input_model: type[I]  # validates the model's arguments before the handler runs
    result_model: type[R]
    tier: RiskTier
    release: Release
    # The policy switch a write needs (FR-AGT-10); None for read and draft tools.
    capability: AgentCapability | None = None
    # The least role that may do this by hand (§8): the principal's role bounds every tool.
    min_role: Role = Role.AGENT
    # R2: what the account must support (TR-PL-11), checked by the gateway.
    platform_capability: Capability | None = None
    handler: ToolHandler[I, R]


# ---------------------------------------------------------------- the registry


class ToolRegistry:
    """The tools that exist, by name. ``register`` refuses a spec that breaks TR-AGT-03."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec[Any, Any]] = {}

    def register[I: BaseModel, R: ToolResult](self, spec: ToolSpec[I, R]) -> ToolSpec[I, R]:
        """Add a tool; raise ``ToolRegistryError`` naming the first problem.

        Refused: a name that isn't snake_case or is taken; no label or description; a tier or
        release that isn't one of ours; models that aren't Pydantic (the result a ``ToolResult``,
        a draft's a ``DraftResult``); a write tier without a capability switch, or a read or draft
        tool with one; a write in R1 (FR-AGT-02: no R1 tool changes anything); a handler that
        isn't async.
        """
        name = spec.name
        if not isinstance(name, str) or not TOOL_NAME.fullmatch(name):
            raise ToolRegistryError(f"tool name {name!r} must be snake_case, 3-64 characters")
        if name in self._tools:
            raise ToolRegistryError(f"tool {name!r} is already registered")
        if not spec.label.strip() or not spec.description.strip():
            raise ToolRegistryError(f"tool {name!r} needs a label and a description")
        if not isinstance(spec.tier, RiskTier):
            raise ToolRegistryError(f"tool {name!r} has no risk tier")
        if not isinstance(spec.release, Release):
            raise ToolRegistryError(f"tool {name!r} has no release")
        if not (isinstance(spec.input_model, type) and issubclass(spec.input_model, BaseModel)):
            raise ToolRegistryError(f"tool {name!r}: the input model must be a Pydantic model")
        if not (isinstance(spec.result_model, type) and issubclass(spec.result_model, ToolResult)):
            raise ToolRegistryError(f"tool {name!r}: the result model must extend ToolResult")
        if spec.tier == RiskTier.DRAFT and not issubclass(spec.result_model, DraftResult):
            raise ToolRegistryError(
                f"draft tool {name!r}: the result model must extend DraftResult"
            )
        writes = spec.tier in WRITE_TIERS
        if writes and spec.capability is None:
            raise ToolRegistryError(f"write tool {name!r} needs a capability switch")
        if not writes and spec.capability is not None:
            raise ToolRegistryError(f"{spec.tier} tool {name!r} can't have a capability switch")
        if writes and spec.release == Release.R1:
            raise ToolRegistryError(f"write tool {name!r} can't ship in R1 (FR-AGT-02)")
        if not inspect.iscoroutinefunction(spec.handler):
            raise ToolRegistryError(f"tool {name!r}: the handler must be an async function")
        self._tools[name] = spec
        return spec

    def get(self, name: str) -> ToolSpec[Any, Any] | None:
        return self._tools.get(name)

    def available(
        self, *, release: Release = CURRENT_RELEASE, role: Role | None = None
    ) -> list[ToolSpec[Any, Any]]:
        """Tools shipped by ``release`` (and, with ``role``, that the role may use), by name."""
        shipped = RELEASE_ORDER[: RELEASE_ORDER.index(release) + 1]
        return [
            spec
            for _, spec in sorted(self._tools.items())
            if spec.release in shipped
            and (role is None or ROLE_RANK[role] >= ROLE_RANK[spec.min_role])
        ]

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __iter__(self) -> Iterator[ToolSpec[Any, Any]]:
        return iter(list(self._tools.values()))

    def __len__(self) -> int:
        return len(self._tools)


# The process's tools; agent/tools/* register on it (agent.tools.load_tools()).
registry = ToolRegistry()
