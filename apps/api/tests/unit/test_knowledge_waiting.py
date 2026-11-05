"""The waiting-for-approval count goes only to roles that can approve what it counts."""

from __future__ import annotations

from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.identity import Role
from socialhood.services.knowledge.sources import waiting_count


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def scalar(self, statement: Any) -> int:
        self.statements.append(statement)
        return 3


@pytest.mark.parametrize("role", [Role.ADMIN, Role.OWNER])
async def test_roles_that_manage_knowledge_get_the_count(role: Role) -> None:
    session = FakeSession()
    assert await waiting_count(cast(AsyncSession, session), role) == 3
    [statement] = session.statements
    assert "knowledge_sources.status" in str(statement)


async def test_an_agent_gets_zero_without_a_query() -> None:
    session = FakeSession()
    assert await waiting_count(cast(AsyncSession, session), Role.AGENT) == 0
    assert session.statements == []
