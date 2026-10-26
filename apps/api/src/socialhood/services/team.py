"""Team members and invitations (GR-19). Nothing here commits; the route does.

Rules (C-106):
- Roles: owner, admin, agent. Owners invite admins or agents; admins invite agents only. Only
  owners change a role, remove a member or move ownership.
- Seats: the plan's ``members`` limit counts members plus pending invitations that haven't
  expired. Inviting past it is a 402 ``quota_exceeded`` naming ``members``.
- An invitation is one row per workspace and email while pending. Clerk sends the email and holds
  the secret link; we keep no token. A person who already has an account gets a plain email from
  us instead (Clerk refuses to invite a known address) and joins the next time they sign in.
  Expiry is 14 days; "expired" is worked out on read and a resend starts the 14 days again.
- A workspace always keeps an owner: the owner of record (``workspaces.owner_user_id``) can't be
  removed or demoted, only replaced by a transfer, which makes the old owner an admin.
- Removing a member deletes only the membership. The person's past actions (messages sent,
  automations made, audit rows) keep their user id and name. Their conversations go back to
  nobody (GR-20; services/assignment.clear_for_member).
"""

from __future__ import annotations

import html
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.deps import WorkspaceContext
from socialhood.auth.invitations import InvitationError, InvitationSender
from socialhood.auth.permissions import INVITABLE_ROLES
from socialhood.billing.entitlements import quota_error
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.identity import Role, User, WorkspaceMember
from socialhood.models.team import InvitationStatus, WorkspaceInvitation
from socialhood.notify.email import EmailError, EmailMessage
from socialhood.notify.registry import get_email_sender
from socialhood.observability.logging import get_logger
from socialhood.repositories import users, workspaces
from socialhood.repositories.base import scoped_delete, scoped_update
from socialhood.schemas.team import (
    Invitation,
    InvitationCreate,
    InvitationList,
    Member,
    MemberList,
    OwnershipTransfer,
    Seats,
)
from socialhood.services import assignment, audit
from socialhood.settings import Settings

log = get_logger(__name__)

INVITATION_DAYS = 14
ALREADY_MEMBER = "That person is already a member."
ALREADY_INVITED = "That person already has an invitation. Resend it instead."
OWNER_NEEDED = "A workspace needs an owner. Transfer ownership first."
CONFIRM_MISMATCH = "Type the workspace name exactly as it is shown to confirm."


# ---------------------------------------------------------------- pure rules


def effective_status(invitation: WorkspaceInvitation, now: datetime) -> str:
    """Stored status, except that a pending invitation past its expiry reads as expired."""
    if invitation.status == InvitationStatus.PENDING and invitation.expires_at <= now:
        return "expired"
    return invitation.status


def may_invite(inviter: Role, role: Role) -> bool:
    return role in INVITABLE_ROLES[inviter]


def seat_check(*, members: int, pending: int, limit: int | None, adding: int = 1) -> bool:
    """Whether ``adding`` more seats fit under the plan's limit (None: unlimited)."""
    return limit is None or members + pending + adding <= limit


# ---------------------------------------------------------------- seats and lists


async def _pending_count(session: AsyncSession, now: datetime) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(WorkspaceInvitation)
            .where(
                WorkspaceInvitation.status == InvitationStatus.PENDING,
                WorkspaceInvitation.expires_at > now,
            )
        )
        or 0
    )


async def seats(session: AsyncSession, now: datetime) -> Seats:
    members = int(await session.scalar(select(func.count()).select_from(WorkspaceMember)) or 0)
    limit = entitlement(await current_plan(session), "members")
    return Seats(
        members=members,
        pending_invitations=await _pending_count(session, now),
        limit=int(limit) if limit is not None else None,
    )


async def _require_seat(session: AsyncSession, now: datetime) -> None:
    current = await seats(session, now)
    if not seat_check(
        members=current.members, pending=current.pending_invitations, limit=current.limit
    ):
        limit = current.limit or 0
        noun = "member" if limit == 1 else "members"
        raise quota_error(
            "members", limit, f"Your plan includes {limit:,} {noun}, with pending invitations."
        )


async def list_members(session: AsyncSession, you: uuid.UUID, now: datetime) -> MemberList:
    rows = (
        await session.execute(
            select(WorkspaceMember, User)
            .join(User, User.id == WorkspaceMember.user_id)
            .order_by(WorkspaceMember.created_at, WorkspaceMember.id)
        )
    ).all()
    return MemberList(
        items=[
            Member(
                user_id=user.id,
                name=user.name,
                email=user.email,
                avatar_url=user.avatar_url,
                role=Role(member.role).value,
                last_seen_at=user.last_seen_at,
                joined_at=member.created_at,
                is_you=user.id == you,
            )
            for member, user in rows
        ],
        seats=await seats(session, now),
    )


async def _invitation_out(
    session: AsyncSession, invitation: WorkspaceInvitation, now: datetime
) -> Invitation:
    inviter = (
        await session.get(User, invitation.invited_by_user_id)
        if invitation.invited_by_user_id
        else None
    )
    return Invitation(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        status=effective_status(invitation, now),
        invited_by_name=(inviter.name or inviter.email) if inviter else None,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


async def list_invitations(session: AsyncSession, now: datetime) -> InvitationList:
    """Pending and expired invitations, newest first (accepted and revoked ones are history)."""
    rows = (
        await session.scalars(
            select(WorkspaceInvitation)
            .where(WorkspaceInvitation.status == InvitationStatus.PENDING)
            .order_by(WorkspaceInvitation.created_at.desc())
        )
    ).all()
    return InvitationList(items=[await _invitation_out(session, row, now) for row in rows])


async def _get_invitation(session: AsyncSession, invitation_id: uuid.UUID) -> WorkspaceInvitation:
    invitation = await session.scalar(
        select(WorkspaceInvitation).where(WorkspaceInvitation.id == invitation_id)
    )
    if invitation is None:
        raise ApiError("not_found")
    return invitation


# ---------------------------------------------------------------- invitations


def _sign_up_url(settings: Settings) -> str | None:
    return f"{settings.web_base_url.rstrip('/')}/sign-up" if settings.web_base_url else None


async def _deliver(
    session: AsyncSession,
    ctx: WorkspaceContext,
    invitation: WorkspaceInvitation,
    *,
    sender: InvitationSender,
    http: httpx.AsyncClient,
    settings: Settings,
) -> None:
    """Clerk emails a new person; a person who already has an account gets our own email."""
    if await users.get_by_email(session, invitation.email) is None:
        try:
            invitation.clerk_invitation_id = await sender.invite(
                invitation.email,
                redirect_url=_sign_up_url(settings),
                workspace_id=str(ctx.workspace_id),
            )
        except InvitationError as error:
            log.warning("invitation_send_failed", reason=str(error))
            raise ApiError(
                "service_unavailable", "Couldn't send the invitation. Try again in a moment."
            ) from error
        return
    invitation.clerk_invitation_id = None
    inviter = ctx.user.name or ctx.user.email
    link = settings.web_base_url or ""
    text = (
        f"{inviter} invited you to join {ctx.workspace.name} on Amplychat as "
        f"{invitation.role}. Sign in to accept: {link}"
    )
    try:
        await get_email_sender(http, settings).send(
            EmailMessage(
                to=invitation.email,
                subject=f"{inviter} invited you to {ctx.workspace.name}",
                html=f"<p>{html.escape(text)}</p>",
                text=text,
                idempotency_key=f"team-invite-{invitation.id}-{int(invitation.expires_at.timestamp())}",
            )
        )
    except EmailError as error:
        # The invitation stands; they will see it when they sign in.
        log.warning("invitation_email_failed", http_status=error.status)


async def invite(
    session: AsyncSession,
    ctx: WorkspaceContext,
    body: InvitationCreate,
    *,
    sender: InvitationSender,
    http: httpx.AsyncClient,
    settings: Settings,
    now: datetime,
) -> Invitation:
    role = Role(body.role)
    if not may_invite(ctx.role, role):
        raise ApiError("forbidden", "Only owners can invite admins.")
    email = body.email.strip().lower()
    already = await session.scalar(
        select(WorkspaceMember.id)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(func.lower(User.email) == email)
    )
    if already is not None:
        raise ApiError("conflict", ALREADY_MEMBER)
    existing = await session.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.status == InvitationStatus.PENDING,
            func.lower(WorkspaceInvitation.email) == email,
        )
    )
    if existing is not None:
        if effective_status(existing, now) == "pending":
            raise ApiError("conflict", ALREADY_INVITED)
        existing.status = InvitationStatus.REVOKED  # an expired one makes way for a new one
        await session.flush()
    await _require_seat(session, now)
    invitation = WorkspaceInvitation(
        workspace_id=ctx.workspace_id,
        email=email,
        role=role.value,
        status=InvitationStatus.PENDING,
        invited_by_user_id=ctx.user.id,
        expires_at=now + timedelta(days=INVITATION_DAYS),
    )
    session.add(invitation)
    try:
        await session.flush()
    except IntegrityError as error:  # two invites for one address at once
        raise ApiError("conflict", ALREADY_INVITED) from error
    await _deliver(session, ctx, invitation, sender=sender, http=http, settings=settings)
    await audit.record(
        session, ctx, "member.invited", "invitation", invitation.id, email=email, role=role.value
    )
    await session.flush()
    return await _invitation_out(session, invitation, now)


def _may_manage(ctx: WorkspaceContext, invitation: WorkspaceInvitation) -> None:
    if not may_invite(ctx.role, Role(invitation.role)):
        raise ApiError("forbidden", "Only owners can change an admin's invitation.")


async def resend(
    session: AsyncSession,
    ctx: WorkspaceContext,
    invitation_id: uuid.UUID,
    *,
    sender: InvitationSender,
    http: httpx.AsyncClient,
    settings: Settings,
    now: datetime,
) -> Invitation:
    invitation = await _get_invitation(session, invitation_id)
    if invitation.status != InvitationStatus.PENDING:
        raise ApiError("conflict", "That invitation was already used or revoked.")
    _may_manage(ctx, invitation)
    if effective_status(invitation, now) == "expired":
        await _require_seat(session, now)  # an expired invitation held no seat
    if invitation.clerk_invitation_id:
        try:
            await sender.revoke(invitation.clerk_invitation_id)
        except InvitationError as error:
            log.warning("invitation_revoke_failed", reason=str(error))
    invitation.expires_at = now + timedelta(days=INVITATION_DAYS)
    await _deliver(session, ctx, invitation, sender=sender, http=http, settings=settings)
    await audit.record(session, ctx, "member.invite_resent", "invitation", invitation.id)
    await session.flush()
    return await _invitation_out(session, invitation, now)


async def revoke(
    session: AsyncSession,
    ctx: WorkspaceContext,
    invitation_id: uuid.UUID,
    *,
    sender: InvitationSender,
) -> None:
    invitation = await _get_invitation(session, invitation_id)
    if invitation.status != InvitationStatus.PENDING:
        raise ApiError("conflict", "That invitation was already used or revoked.")
    _may_manage(ctx, invitation)
    invitation.status = InvitationStatus.REVOKED
    if invitation.clerk_invitation_id:
        try:
            await sender.revoke(invitation.clerk_invitation_id)
        except InvitationError as error:
            # Our row decides who joins, so a link Clerk still holds can't add anyone.
            log.warning("invitation_revoke_failed", reason=str(error))
    await audit.record(
        session, ctx, "member.invite_revoked", "invitation", invitation.id, email=invitation.email
    )
    await session.flush()


# ---------------------------------------------------------------- members


async def _member_or_404(session: AsyncSession, user_id: uuid.UUID) -> WorkspaceMember:
    member = await session.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user_id))
    if member is None:
        raise ApiError("not_found")
    return member


async def _owner_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(WorkspaceMember.role == Role.OWNER)
        )
        or 0
    )


async def change_role(
    session: AsyncSession, ctx: WorkspaceContext, user_id: uuid.UUID, role: Role
) -> None:
    member = await _member_or_404(session, user_id)
    if member.role == role:
        return
    if member.role == Role.OWNER and (
        user_id == ctx.workspace.owner_user_id or await _owner_count(session) <= 1
    ):
        raise ApiError("conflict", OWNER_NEEDED)
    previous = member.role
    await session.execute(scoped_update(WorkspaceMember, id=member.id).values(role=role.value))
    await audit.record(
        session,
        ctx,
        "member.role_changed",
        "member",
        user_id,
        from_role=previous,
        to_role=role.value,
    )
    await session.flush()


async def remove_member(session: AsyncSession, ctx: WorkspaceContext, user_id: uuid.UUID) -> None:
    member = await _member_or_404(session, user_id)
    if user_id == ctx.user.id:
        raise ApiError("conflict", "You can't remove yourself. Ask another owner.")
    if user_id == ctx.workspace.owner_user_id or (
        member.role == Role.OWNER and await _owner_count(session) <= 1
    ):
        raise ApiError("conflict", OWNER_NEEDED)
    await session.execute(scoped_delete(WorkspaceMember, id=member.id))
    unassigned = await assignment.clear_for_member(session, user_id)
    removed = await session.get(User, user_id)
    if removed is not None and removed.last_workspace_id == ctx.workspace_id:
        # So their next sign-in lands on a workspace they still belong to.
        await users.clear_last_workspace(session, user_id)
    await audit.record(
        session,
        ctx,
        "member.removed",
        "member",
        user_id,
        name=removed.name if removed else None,
        role=member.role,
        unassigned=unassigned,
    )
    await session.flush()


async def transfer_ownership(
    session: AsyncSession, ctx: WorkspaceContext, body: OwnershipTransfer
) -> None:
    """The caller becomes an admin and ``body.user_id`` the owner of record."""
    target = await _member_or_404(session, body.user_id)  # before the name, so 404 wins (TR-TEN-03)
    if body.confirm_name.strip() != ctx.workspace.name.strip():
        raise ApiError("validation_error", errors=[FieldError("confirm_name", CONFIRM_MISMATCH)])
    if body.user_id == ctx.user.id:
        raise ApiError("conflict", "Choose another member to become the owner.")
    await session.execute(scoped_update(WorkspaceMember, id=target.id).values(role=Role.OWNER))
    await session.execute(
        scoped_update(WorkspaceMember, user_id=ctx.user.id).values(role=Role.ADMIN)
    )
    await workspaces.transfer_ownership(session, ctx.workspace_id, body.user_id)
    await audit.record(
        session,
        ctx,
        "workspace.ownership_transferred",
        "workspace",
        ctx.workspace_id,
        to_user_id=body.user_id,
    )
    await session.flush()
