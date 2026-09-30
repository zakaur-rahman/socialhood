"""Apply Clerk user events (TR-AUTH-04): profile updates and account deletion.

user.deleted deletes the workspaces the user solely owns (FR-ACC-05) and hands shared ones to
another owner. A solely owned workspace takes the same path as DELETE /v1/w/{wid}
(services/workspace_deletion): it is marked deleting at once (tokens destroyed, automations and
scheduled work stopped) and purged by the purge_workspace job, which cancels its Dodo subscription
first and keeps retrying while Dodo doesn't answer, so a failed cancel is never lost (C-052). The
user row goes at once; a deleting workspace may outlive its owner (migration 0015).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.clerk import parse_clerk_user
from socialhood.db.tenancy import workspace_scope
from socialhood.models.identity import Role, WorkspaceMember, WorkspaceStatus
from socialhood.repositories import users, workspaces
from socialhood.services import workspace_deletion

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
    now = datetime.now(UTC)
    for workspace in await workspaces.owned_by(session, user.id):
        if workspace.status != WorkspaceStatus.ACTIVE:
            continue  # already being deleted
        with workspace_scope(workspace.id):
            other_owner = await session.scalar(
                select(WorkspaceMember.user_id)
                .where(WorkspaceMember.role == Role.OWNER, WorkspaceMember.user_id != user.id)
                .order_by(WorkspaceMember.created_at)
                .limit(1)
            )
        if other_owner is None:  # solely owned (FR-ACC-05)
            await workspace_deletion.begin(
                session, workspace.id, requested_by=None, source="clerk_user_deleted", now=now
            )
        else:
            await workspaces.transfer_ownership(session, workspace.id, other_owner)
    await users.delete(session, user.id)
    return "processed"
