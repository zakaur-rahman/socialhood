"""Ask Social Hood's tools under test (TA.4): a workspace with a sandbox Instagram account, and
``call`` running one registered tool the way the executor will (the run's ToolContext, a
session in the workspace's scope, the arguments validated by the tool's input model).

Each call also checks what every R1 tool promises: its result survives the JSON round trip of a
stored step, and the tool left nothing to write in its session (FR-AGT-02).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.agent.registry import Principal, ToolContext, ToolResult
from socialhood.agent.tools import load_tools
from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.models.identity import Role
from socialhood.platforms.deps import PlatformDeps, deps_from
from socialhood.settings import Settings
from tests.support.inbox import make_account, make_workspace
from tests.support.post_metrics import set_timezone

TIMEZONE = "Asia/Kolkata"


@dataclass
class Shop:
    """A workspace, its owner and its sandbox Instagram account (@maple.bakery)."""

    engine: AsyncEngine
    deps: PlatformDeps
    wid: uuid.UUID
    owner_id: uuid.UUID
    account_id: uuid.UUID
    timezone: str = TIMEZONE
    run_id: uuid.UUID = field(default_factory=uuid.uuid4)

    async def call(
        self,
        name: str,
        args: dict[str, Any] | None = None,
        *,
        role: Role = Role.OWNER,
        now: datetime | None = None,
    ) -> Any:
        """Run tool ``name`` with ``args`` as a member with ``role``."""
        spec = load_tools().get(name)
        assert spec is not None, f"no tool {name}"
        with workspace_scope(self.wid):
            async with AsyncSession(self.engine, expire_on_commit=False) as session:
                ctx = ToolContext(
                    session=session,
                    sessionmaker=make_sessionmaker(self.engine),
                    platform=self.deps,
                    workspace_id=self.wid,
                    timezone=ZoneInfo(self.timezone),
                    now=now or datetime.now(UTC),
                    principal=Principal(user_id=self.owner_id, role=role),
                    run_id=self.run_id,
                )
                result = await spec.handler(ctx, spec.input_model.model_validate(args or {}))
                assert not session.new, "a tool added rows"
                assert not session.dirty, "a tool changed rows"
                assert not session.deleted, "a tool deleted rows"
        assert isinstance(result, spec.result_model)
        stored = spec.result_model.model_validate_json(result.model_dump_json())
        assert stored == result
        assert isinstance(result, ToolResult)
        return result

    async def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), params)]

    async def execute(self, sql: str, **params: Any) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(sql), params)


async def make_shop(engine: AsyncEngine, deps: PlatformDeps) -> Shop:
    wid = await make_workspace(engine)
    await set_timezone(engine, wid, TIMEZONE)
    account_id = await make_account(engine, wid)
    async with engine.connect() as conn:
        owner = (
            await conn.execute(
                text("SELECT owner_user_id FROM workspaces WHERE id = :w"), {"w": wid}
            )
        ).scalar_one()
    return Shop(engine, deps, wid, owner, account_id)


@asynccontextmanager
async def tool_platform(settings: Settings) -> AsyncIterator[PlatformDeps]:
    """The platform deps a run carries (the sandbox is on in the test settings)."""
    async with httpx.AsyncClient() as http:
        yield deps_from(http, settings)
