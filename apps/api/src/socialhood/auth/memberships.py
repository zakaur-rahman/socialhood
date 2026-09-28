"""The workspaces a user belongs to. Lives in auth/ because it reads memberships across
workspaces before any workspace is chosen (TR-TEN-04 allows the bypass here)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.models.billing import Subscription
from socialhood.models.identity import Workspace, WorkspaceMember, WorkspaceStatus


@dataclass(frozen=True)
class Membership:
    workspace_id: uuid.UUID
    name: str
    slug: str
    timezone: str
    role: str
    plan: str


async def memberships_for(session: AsyncSession, user_id: uuid.UUID) -> list[Membership]:
    statement = (
        select(
            Workspace.id,
            Workspace.name,
            Workspace.slug,
            Workspace.timezone,
            WorkspaceMember.role,
            Subscription.plan,
        )
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .outerjoin(Subscription, Subscription.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id, Workspace.status == WorkspaceStatus.ACTIVE)
        .order_by(Workspace.created_at)
    )
    with tenant_bypass_scope():
        rows = (await session.execute(statement)).all()
    return [
        Membership(
            workspace_id=row[0],
            name=row[1],
            slug=row[2],
            timezone=row[3],
            role=row[4],
            plan=row[5] or "free",
        )
        for row in rows
    ]
