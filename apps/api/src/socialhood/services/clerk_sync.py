"""Apply Clerk user events (TR-AUTH-04): profile updates and account deletion."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.clerk import parse_clerk_user
from socialhood.db.tenancy import workspace_scope
from socialhood.models.identity import Role, WorkspaceMember
from socialhood.repositories import users, workspaces

Outcome = Literal["processed", "ignored"]


async def apply_event(session: AsyncSession, payload: dict[str, Any]) -> Outcome:
    event_type = payload.get("type")
    data = payload.get("data") or {}
    if event_type == "user.updated":
        return await _updated(session, data)
    if event_type == "user.deleted":
        return await _deleted(session, data)
    return "ignored"  # user.created is handled on first sign-in (TR-AUTH-03)


async def _updated(session: AsyncSession, data: dict[str, Any]) -> Outcome:
    profile = parse_clerk_user(data)
    if await users.get_by_clerk_id(session, profile.id) is None:
        return "ignored"  # never signed in to Social Hood
    await users.update_profile(
        session,
        profile.id,
        email=profile.email if profile.email_verified else None,
        name=profile.name,
        avatar_url=profile.image_url,
    )
    return "processed"


async def _deleted(session: AsyncSession, data: dict[str, Any]) -> Outcome:
    clerk_id = data.get("id")
    user = await users.get_by_clerk_id(session, str(clerk_id)) if clerk_id else None
    if user is None:
        return "ignored"
    for workspace in await workspaces.owned_by(session, user.id):
        with workspace_scope(workspace.id):
            other_owner = await session.scalar(
                select(WorkspaceMember.user_id)
                .where(WorkspaceMember.role == Role.OWNER, WorkspaceMember.user_id != user.id)
                .order_by(WorkspaceMember.created_at)
                .limit(1)
            )
        if other_owner is None:
            await workspaces.delete_workspace(session, workspace.id)  # solely owned (FR-ACC-05)
        else:
            await workspaces.transfer_ownership(session, workspace.id, other_owner)
    await users.delete(session, user.id)
    return "processed"
