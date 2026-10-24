"""Team members, invitations, the caller's permissions and the audit log (GR-19)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

RoleName = Literal["owner", "admin", "agent"]
InvitableRole = Literal["admin", "agent"]
InvitationStatusName = Literal["pending", "expired", "accepted", "revoked"]
Email = Annotated[str, Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]


class WorkspacePermissions(ResponseModel):
    """What the signed-in member may do here. The web app's can() reads this list; it never
    keeps a copy of the matrix."""

    role: RoleName
    permissions: list[str]


class Seats(ResponseModel):
    """Members plus pending invitations against the plan's ``members`` limit (null: unlimited)."""

    members: int
    pending_invitations: int
    limit: int | None


class Member(ResponseModel):
    user_id: uuid.UUID
    name: str | None
    email: str
    avatar_url: str | None
    role: RoleName
    last_seen_at: datetime | None
    joined_at: datetime
    is_you: bool


class MemberList(ResponseModel):
    items: list[Member]
    seats: Seats


class Invitation(ResponseModel):
    id: uuid.UUID
    email: str
    role: InvitableRole
    status: InvitationStatusName
    invited_by_name: str | None
    expires_at: datetime
    created_at: datetime


class InvitationList(ResponseModel):
    items: list[Invitation]


class InvitationCreate(RequestModel):
    """Owners invite admins or agents; admins invite agents only."""

    email: Email
    role: InvitableRole


class MemberRolePatch(RequestModel):
    """Admin or agent. Ownership moves only through the transfer route."""

    role: InvitableRole


class OwnershipTransfer(RequestModel):
    """Hand the workspace to another member. The previous owner becomes an admin. Type the
    workspace's name to confirm."""

    user_id: uuid.UUID
    confirm_name: Annotated[str, Field(min_length=1, max_length=200)]


class AuditEvent(ResponseModel):
    id: uuid.UUID
    at: datetime
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    action: str
    target_type: str
    target_id: str | None
    detail: dict[str, Any]


class AuditEventList(ResponseModel):
    items: list[AuditEvent]
    has_more: bool
    actions: list[str]  # every action the log holds, for the filter
