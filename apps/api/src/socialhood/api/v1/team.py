"""Team routes (GR-19): the caller's permissions, members, invitations, ownership and the audit
log. The rules are in services/team.py and services/audit.py, the matrix in auth/permissions.py.

Any member reads their own permissions. Owners and admins read the member list, invitations and
the audit log, and invite (admins invite agents only). Owners change roles, remove members and
transfer ownership.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from socialhood.auth.deps import (
    AnyMember,
    CanInviteMembers,
    CanManageMembers,
    CanReadAudit,
    CanReadMembers,
    CanTransferOwnership,
    Session,
)
from socialhood.auth.invitations import get_invitation_sender
from socialhood.auth.permissions import permissions_of
from socialhood.models.identity import Role
from socialhood.schemas.team import (
    AuditEventList,
    Invitation,
    InvitationCreate,
    InvitationList,
    MemberList,
    MemberRolePatch,
    OwnershipTransfer,
    WorkspacePermissions,
)
from socialhood.services import audit
from socialhood.services import team as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["team"])


@router.get("/permissions", operation_id="get_workspace_permissions")
async def get_workspace_permissions(ctx: AnyMember) -> WorkspacePermissions:
    """The caller's role and permissions here; the web app hides what they can't do from it."""
    return WorkspacePermissions(role=ctx.role.value, permissions=permissions_of(ctx.role))


@router.get("/members", operation_id="list_members")
async def list_members(ctx: CanReadMembers, session: Session) -> MemberList:
    """Members with role and last active, and the seats the plan allows."""
    return await service.list_members(session, ctx.user.id, datetime.now(UTC))


@router.patch("/members/{user_id}", operation_id="update_member_role")
async def update_member_role(
    user_id: uuid.UUID, body: MemberRolePatch, ctx: CanManageMembers, session: Session
) -> MemberList:
    """Admin or agent. 409 for the owner of record: transfer ownership instead."""
    await service.change_role(session, ctx, user_id, Role(body.role))
    await session.commit()
    return await service.list_members(session, ctx.user.id, datetime.now(UTC))


@router.delete("/members/{user_id}", status_code=204, operation_id="remove_member")
async def remove_member(user_id: uuid.UUID, ctx: CanManageMembers, session: Session) -> Response:
    """Their past messages and changes stay attributed to them."""
    await service.remove_member(session, ctx, user_id)
    await session.commit()
    return Response(status_code=204)


@router.post("/ownership-transfer", operation_id="transfer_ownership")
async def transfer_ownership(
    body: OwnershipTransfer, ctx: CanTransferOwnership, session: Session
) -> MemberList:
    """Make another member the owner; the caller becomes an admin. Needs the workspace name."""
    await service.transfer_ownership(session, ctx, body)
    await session.commit()
    return await service.list_members(session, ctx.user.id, datetime.now(UTC))


@router.get("/invitations", operation_id="list_invitations")
async def list_invitations(ctx: CanReadMembers, session: Session) -> InvitationList:
    """Pending invitations, with the ones past their expiry marked expired."""
    return await service.list_invitations(session, datetime.now(UTC))


@router.post("/invitations", status_code=201, operation_id="create_invitation")
async def create_invitation(
    request: Request, body: InvitationCreate, ctx: CanInviteMembers, session: Session
) -> Invitation:
    """Invite by email. 402 when the plan's seats (members and pending invitations) are full;
    409 for a member or an open invitation; 403 when an admin invites an admin."""
    settings = request.app.state.settings
    out = await service.invite(
        session,
        ctx,
        body,
        sender=get_invitation_sender(request.app.state.http, settings),
        http=request.app.state.http,
        settings=settings,
        now=datetime.now(UTC),
    )
    await session.commit()
    return out


@router.post("/invitations/{invitation_id}/resend", operation_id="resend_invitation")
async def resend_invitation(
    request: Request, invitation_id: uuid.UUID, ctx: CanInviteMembers, session: Session
) -> Invitation:
    settings = request.app.state.settings
    out = await service.resend(
        session,
        ctx,
        invitation_id,
        sender=get_invitation_sender(request.app.state.http, settings),
        http=request.app.state.http,
        settings=settings,
        now=datetime.now(UTC),
    )
    await session.commit()
    return out


@router.delete("/invitations/{invitation_id}", status_code=204, operation_id="revoke_invitation")
async def revoke_invitation(
    request: Request, invitation_id: uuid.UUID, ctx: CanInviteMembers, session: Session
) -> Response:
    await service.revoke(
        session,
        ctx,
        invitation_id,
        sender=get_invitation_sender(request.app.state.http, request.app.state.settings),
    )
    await session.commit()
    return Response(status_code=204)


@router.get("/audit-events", operation_id="list_audit_events")
async def list_audit_events(
    ctx: CanReadAudit,
    session: Session,
    member: Annotated[uuid.UUID | None, Query()] = None,
    action: Annotated[str | None, Query(max_length=60)] = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> AuditEventList:
    """Who sent, edited or deleted what, newest first. ``until`` is exclusive."""
    return await audit.list_events(
        session,
        actor_user_id=member,
        action=action,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
