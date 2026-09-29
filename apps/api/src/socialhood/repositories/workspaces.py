"""Workspace rows. The workspace is the tenant itself, so it is not TenantScoped."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from socialhood.models.agent import AgentPolicy
from socialhood.models.ai import AiSettings
from socialhood.models.billing import Plan, Subscription, SubscriptionStatus
from socialhood.models.identity import Role, User, Workspace, WorkspaceMember


async def get(session: AsyncSession, workspace_id: uuid.UUID) -> Workspace | None:
    return await session.get(Workspace, workspace_id)


async def owned_by(session: AsyncSession, user_id: uuid.UUID) -> list[Workspace]:
    result = await session.scalars(select(Workspace).where(Workspace.owner_user_id == user_id))
    return list(result.all())


def new_workspace_rows(
    *, name: str, slug: str, owner_id: uuid.UUID, today: date
) -> tuple[Workspace, list[object]]:
    """A workspace and the rows every workspace starts with (TR-AUTH-03, FR-ACC-02, §5.5
    agent_policies)."""
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
        AgentPolicy(workspace_id=workspace.id),  # read_only, every capability off (FR-AGT-10)
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


async def trial_used_by_owner(session: AsyncSession, workspace: Workspace) -> bool:
    """TR-BIL-05: this workspace, or any workspace whose owner has its owner's email, has used a
    trial."""
    if workspace.trial_used_at is not None:
        return True
    owner = aliased(User)
    other_owner = aliased(User)
    used = await session.scalar(
        select(Workspace.id)
        .join(other_owner, other_owner.id == Workspace.owner_user_id)
        .join(owner, func.lower(owner.email) == func.lower(other_owner.email))
        .where(owner.id == workspace.owner_user_id, Workspace.trial_used_at.is_not(None))
        .limit(1)
    )
    return used is not None
