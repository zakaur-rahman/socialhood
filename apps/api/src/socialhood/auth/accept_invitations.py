"""Joining a workspace from an invitation (GR-19). Lives in auth/ because it looks across
workspaces for the signed-in person's email (TR-TEN-04 allows the bypass here).

When someone signs in, GET /v1/me calls ``accept_for_user``. If a pending, unexpired invitation
names their email, we ask Clerk for their profile and join them only when that email is verified
there: an address typed into a sign-up form and never confirmed must not open a workspace. They
join with the invited role; the invitation becomes accepted; their last workspace becomes the
new one, so they land there. A Clerk outage skips the step and the next /me tries again.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.clerk import ClerkClient, ClerkUnavailable
from socialhood.db.tenancy import tenant_bypass_scope
from socialhood.models.identity import Role, User, Workspace, WorkspaceMember, WorkspaceStatus
from socialhood.models.team import AuditEvent, InvitationStatus, WorkspaceInvitation
from socialhood.observability.logging import get_logger
from socialhood.settings import Settings

log = get_logger(__name__)


async def _pending_for(
    session: AsyncSession, email: str, now: datetime
) -> list[WorkspaceInvitation]:
    with tenant_bypass_scope():
        rows = await session.scalars(
            select(WorkspaceInvitation)
            .join(Workspace, Workspace.id == WorkspaceInvitation.workspace_id)
            .where(
                func.lower(WorkspaceInvitation.email) == email.lower(),
                WorkspaceInvitation.status == InvitationStatus.PENDING,
                WorkspaceInvitation.expires_at > now,
                Workspace.status == WorkspaceStatus.ACTIVE,
            )
            .order_by(WorkspaceInvitation.created_at)
        )
        return list(rows.all())


async def accept_for_user(
    session: AsyncSession,
    user: User,
    *,
    http: httpx.AsyncClient,
    settings: Settings,
    now: datetime | None = None,
) -> list[uuid.UUID]:
    """Join ``user`` to every workspace with a pending invitation for their email. Returns the
    workspace ids joined (empty almost always, and then costs one indexed query)."""
    now = now or datetime.now(UTC)
    if not user.email:
        return []
    invitations = await _pending_for(session, user.email, now)
    if not invitations:
        return []
    try:
        profile = await ClerkClient(http, settings).get_user(user.clerk_user_id)
    except ClerkUnavailable as error:
        log.warning("invitation_accept_skipped", reason=str(error))
        return []
    if not profile.email_verified or profile.email != user.email.lower():
        return []

    joined: list[uuid.UUID] = []
    with tenant_bypass_scope():
        for invitation in invitations:
            workspace_id = invitation.workspace_id
            already = await session.scalar(
                select(WorkspaceMember.id).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == user.id,
                )
            )
            if already is None:
                session.add(
                    WorkspaceMember(
                        workspace_id=workspace_id, user_id=user.id, role=Role(invitation.role).value
                    )
                )
                session.add(
                    AuditEvent(
                        workspace_id=workspace_id,
                        actor_user_id=user.id,
                        actor_label=(user.name or user.email)[:120],
                        action="member.joined",
                        target_type="member",
                        target_id=str(user.id),
                        detail={
                            "role": invitation.role,
                            "invited_by": str(invitation.invited_by_user_id),
                        },
                    )
                )
                joined.append(workspace_id)
            invitation.status = InvitationStatus.ACCEPTED
            invitation.accepted_at = now
            invitation.accepted_user_id = user.id
        if joined:
            user.last_workspace_id = joined[-1]
        await session.commit()
    return joined
