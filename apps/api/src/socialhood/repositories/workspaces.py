"""Workspace rows. The workspace is the tenant itself, so it is not TenantScoped."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.ai import AiSettings
from socialhood.models.billing import Plan, Subscription, SubscriptionStatus
from socialhood.models.identity import Role, Workspace, WorkspaceMember


async def get(session: AsyncSession, workspace_id: uuid.UUID) -> Workspace | None:
    return await session.get(Workspace, workspace_id)


async def owned_by(session: AsyncSession, user_id: uuid.UUID) -> list[Workspace]:
    result = await session.scalars(select(Workspace).where(Workspace.owner_user_id == user_id))
    return list(result.all())


def new_workspace_rows(
    *, name: str, slug: str, owner_id: uuid.UUID, today: date
) -> tuple[Workspace, list[object]]:
    """A workspace and the rows every workspace starts with (TR-AUTH-03, FR-ACC-02)."""
    workspace = Workspace(id=uuid.uuid4(), name=name, slug=slug, owner_user_id=owner_id)
    children: list[object] = [
        WorkspaceMember(workspace_id=workspace.id, user_id=owner_id, role=Role.OWNER),
        Subscription(
            workspace_id=workspace.id,
            plan=Plan.FREE,
            status=SubscriptionStatus.FREE,
            billing_anchor_day=min(today.day, 28),
        ),
        AiSettings(workspace_id=workspace.id),
    ]
    return workspace, children


async def update_settings(
    session: AsyncSession, workspace_id: uuid.UUID, values: dict[str, Any]
) -> None:
    if values:
        await session.execute(
            update(Workspace).where(Workspace.id == workspace_id).values(**values)
        )


async def transfer_ownership(
    session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    await session.execute(
        update(Workspace).where(Workspace.id == workspace_id).values(owner_user_id=user_id)
    )


async def delete_workspace(session: AsyncSession, workspace_id: uuid.UUID) -> None:
    """Delete a workspace; every tenant table cascades from it."""
    await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
