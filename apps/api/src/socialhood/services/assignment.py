"""Conversation assignment (GR-20): who has a conversation. Nothing here commits; the caller does
(the route, or the ingest and flow transactions it runs inside).

Who may assign (C-117, a decision the plan left open):
- Owners and admins assign any conversation to any member, or to nobody.
- Agents take a conversation nobody has (assign it to themselves), and release or hand on one they
  have (to anyone, or to nobody). They can't assign to others a conversation nobody has, or take
  one from a colleague; an admin does that.

Every change, whoever or whatever makes it, does the same things in one transaction:
- the conversation's ``assignee_user_id`` and ``assigned_at``, under a row lock on the conversation;
- a system note in the thread ("Sam assigned this to Priya"), which is the conversation's activity;
- an audit row (``conversation.assigned`` or ``conversation.unassigned``) that the contact's
  timeline reads, with who or what did it (a member, round-robin or an automation);
- ``conversation.updated`` for open inboxes, and ``conversation.assigned`` for webhook endpoints;
- a notification (in app, and push under the member's "needs you" switch) to the new assignee,
  unless they assigned it to themselves.

Round-robin (a workspace setting, off by default; a flow's "assign" step can also ask for it):
- a new customer message in a conversation nobody has hands it to the next *available* member in
  turn. Members are taken in the order they joined; a member with the availability switch off is
  skipped; if nobody is available the conversation stays unassigned;
- the turn is kept in ``workspaces.assignment_cursor_user_id`` and read and advanced under a row
  lock on the workspace, so two messages arriving together take different turns. The lock lasts
  until the caller's transaction ends.
Manual assignment ignores availability: a member who is away can still be given a conversation.
Removing a member clears their conversations (services/team.remove_member).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.deps import WorkspaceContext
from socialhood.auth.permissions import Permission, has_permission
from socialhood.db.tenancy import require_workspace
from socialhood.errors import ApiError
from socialhood.models.identity import Role, User, Workspace, WorkspaceMember
from socialhood.models.inbox import Contact, Conversation, ConversationStatus
from socialhood.models.notifications import NotificationType
from socialhood.realtime import events
from socialhood.repositories.base import scoped_update
from socialhood.schemas.assignment import Assignable, AssignmentOverview
from socialhood.services import audit, conversations, takeover
from socialhood.services.inbox_views import member_label
from socialhood.services.notifications import notify_user
from socialhood.services.webhooks import events as webhook_events

Via = Literal["member", "round_robin", "automation"]

AGENT_LIMIT = "Agents can take a conversation nobody has, or hand on one they have."
NOT_A_MEMBER = "That person isn't on your team."


# ---------------------------------------------------------------- pure rules


def may_assign(
    role: Role, actor_id: uuid.UUID, current: uuid.UUID | None, target: uuid.UUID | None
) -> bool:
    """Whether ``actor_id`` (with ``role``) may change ``current`` to ``target``."""
    if role in (Role.OWNER, Role.ADMIN):
        return True
    if current == actor_id:
        return True  # release it, or hand it on
    return current is None and target == actor_id  # take it


def next_in_turn(
    everyone: Sequence[uuid.UUID], available: set[uuid.UUID], last: uuid.UUID | None
) -> uuid.UUID | None:
    """The next available member after ``last`` in ``everyone`` (members in joining order),
    wrapping round. A ``last`` who has left, or is unknown, starts from the first. None when
    nobody is available."""
    if not available:
        return None
    start = everyone.index(last) + 1 if last in everyone else 0
    for step in range(len(everyone)):
        candidate = everyone[(start + step) % len(everyone)]
        if candidate in available:
            return candidate
    return None


def note_text(
    via: Via, *, actor: str, previous: str | None, target: str | None, self_assigned: bool
) -> str:
    """The system note in the thread."""
    if target is None:
        if via == "automation":
            return "An automation removed the assignee"
        who = f" {previous}" if previous else " the assignee"
        return f"{actor} removed{who} from this conversation"
    if via == "round_robin":
        return f"Assigned to {target} (round-robin)"
    if via == "automation":
        return f"An automation assigned this to {target}"
    if self_assigned:
        return f"{actor} took this conversation"
    return f"{actor} assigned this to {target}"


# ---------------------------------------------------------------- who did it


@dataclass(frozen=True)
class Actor:
    via: Via
    user_id: uuid.UUID | None = None  # the member, when a member did it
    label: str = ""  # "Sam", "Round-robin", "Automation: Welcome"
    ctx: WorkspaceContext | None = None


ROUND_ROBIN = Actor("round_robin", label="Round-robin")


def automation_actor(name: str) -> Actor:
    return Actor("automation", label=f"Automation: {name}"[:120])


# ---------------------------------------------------------------- members


async def _labels(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str | None]:
    if not ids:
        return {}
    rows = await session.execute(select(User.id, User.name, User.email).where(User.id.in_(ids)))
    return {user_id: member_label(name, email) for user_id, name, email in rows.all()}


async def _require_member(session: AsyncSession, user_id: uuid.UUID) -> WorkspaceMember:
    member = (
        await session.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == user_id))
    ).one_or_none()
    if member is None:
        raise ApiError("not_found", NOT_A_MEMBER)
    return member


@dataclass(frozen=True)
class Roster:
    """The workspace's members, to name one: label (their name, else the part of their email before
    the @), email and id, in the order they joined."""

    members: list[tuple[uuid.UUID, str, str | None]]

    def find(self, wanted: str) -> set[uuid.UUID]:
        """Everyone whose name, label or email is ``wanted`` (ignoring case). More than one means
        the name is ambiguous."""
        key = wanted.strip().casefold()
        return {
            user_id
            for user_id, label, email in self.members
            if key and key in (label.casefold(), (email or "").casefold())
        }

    @property
    def labels(self) -> list[str]:
        return [label for _, label, _ in self.members]

    def label_of(self, user_id: uuid.UUID) -> str | None:
        return next((label for found, label, _ in self.members if found == user_id), None)


async def roster(session: AsyncSession) -> Roster:
    """Who can be named in a flow's assign step or by Ask (GR-36): the workspace's members."""
    rows = (
        await session.execute(
            select(User.id, User.name, User.email)
            .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
            .order_by(WorkspaceMember.created_at, WorkspaceMember.id)
        )
    ).all()
    return Roster(
        [(user_id, member_label(name, email) or "A member", email) for user_id, name, email in rows]
    )


async def overview(session: AsyncSession, you: uuid.UUID) -> AssignmentOverview:
    """Who can be assigned, and the round-robin setting."""
    open_count = (
        select(Conversation.assignee_user_id.label("user_id"), func.count().label("n"))
        .where(
            Conversation.assignee_user_id.is_not(None),
            Conversation.status == ConversationStatus.OPEN,
        )
        .group_by(Conversation.assignee_user_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(WorkspaceMember, User, open_count.c.n)
            .join(User, User.id == WorkspaceMember.user_id)
            .outerjoin(open_count, open_count.c.user_id == WorkspaceMember.user_id)
            .order_by(WorkspaceMember.created_at, WorkspaceMember.id)
        )
    ).all()
    workspace = await session.get(Workspace, require_workspace())
    return AssignmentOverview(
        round_robin=bool(workspace and workspace.assignment_round_robin),
        members=[
            Assignable(
                user_id=user.id,
                name=member_label(user.name, user.email),
                avatar_url=user.avatar_url,
                role=Role(member.role).value,
                available=member.available_for_assignment,
                open_conversations=int(count or 0),
                is_you=user.id == you,
            )
            for member, user, count in rows
        ],
    )


async def set_round_robin(session: AsyncSession, on: bool) -> None:
    workspace = await session.get(Workspace, require_workspace())
    if workspace is None:  # pragma: no cover - the request's workspace exists
        raise ApiError("not_found", "That workspace wasn't found.")
    workspace.assignment_round_robin = on
    await session.flush()


async def set_available(
    session: AsyncSession, ctx: WorkspaceContext, user_id: uuid.UUID, available: bool
) -> None:
    """A member's availability for round-robin. Anyone sets their own; owners and admins set
    anyone's."""
    member = await _require_member(session, user_id)
    if user_id != ctx.user.id and not has_permission(ctx.role, Permission.SETTINGS_MANAGE):
        raise ApiError("forbidden")
    if member.available_for_assignment == available:
        return
    await session.execute(
        scoped_update(WorkspaceMember, id=member.id).values(available_for_assignment=available)
    )
    await audit.record(
        session, ctx, "member.availability_changed", "member", user_id, available=available
    )


async def clear_for_member(session: AsyncSession, user_id: uuid.UUID) -> int:
    """A removed member's conversations go back to nobody; returns how many. The conversations
    keep their history (the notes say who had them)."""
    result = await session.execute(
        scoped_update(Conversation, assignee_user_id=user_id).values(
            assignee_user_id=None, assigned_at=None
        )
    )
    return int(getattr(result, "rowcount", 0) or 0)


# ---------------------------------------------------------------- round-robin


async def pick_round_robin(session: AsyncSession) -> uuid.UUID | None:
    """The next available member in turn, and the turn moves on. Holds the workspace row until
    the transaction ends."""
    workspace = (
        await session.scalars(
            select(Workspace)
            .where(Workspace.id == require_workspace())
            .with_for_update(key_share=True)  # NO KEY UPDATE: ingest holds KEY SHARE
            .execution_options(populate_existing=True)
        )
    ).one()
    rows = (
        await session.execute(
            select(WorkspaceMember.user_id, WorkspaceMember.available_for_assignment).order_by(
                WorkspaceMember.created_at, WorkspaceMember.id
            )
        )
    ).all()
    chosen = next_in_turn(
        [user_id for user_id, _ in rows],
        {user_id for user_id, available in rows if available},
        workspace.assignment_cursor_user_id,
    )
    if chosen is not None:
        workspace.assignment_cursor_user_id = chosen
        await session.flush()
    return chosen


async def on_inbound(
    session: AsyncSession, conv: Conversation, contact: Contact, *, now: datetime
) -> None:
    """A new customer message: with round-robin on and nobody holding the conversation, the next
    available member gets it. Runs in the ingest transaction, with the conversation locked."""
    if conv.assignee_user_id is not None:
        return
    on = await session.scalar(
        select(Workspace.assignment_round_robin).where(Workspace.id == require_workspace())
    )
    if not on:
        return
    chosen = await pick_round_robin(session)
    if chosen is not None:
        await apply(session, conv, chosen, actor=ROUND_ROBIN, now=now, contact=contact)


# ---------------------------------------------------------------- changing


async def member_assign(
    session: AsyncSession,
    ctx: WorkspaceContext,
    conv: Conversation,
    target: uuid.UUID | None,
    *,
    ig_human_agent_enabled: bool,
    now: datetime,
) -> bool:
    """A member assigns (or unassigns) a conversation; returns whether anything changed."""
    if target is not None:
        await _require_member(session, target)  # before the role check, so 404 wins (TR-TEN-03)
    conv = await lock_conversation(session, conv)
    if not may_assign(ctx.role, ctx.user.id, conv.assignee_user_id, target):
        raise ApiError("forbidden", AGENT_LIMIT)
    actor = Actor(
        "member", ctx.user.id, member_label(ctx.user.name, ctx.user.email) or "A member", ctx
    )
    human_agent = await conversations.human_agent_for(session, conv, enabled=ig_human_agent_enabled)
    return await apply(session, conv, target, actor=actor, now=now, human_agent=human_agent)


async def lock_conversation(session: AsyncSession, conv: Conversation) -> Conversation:
    """The conversation row, locked until the transaction ends and read fresh (pending changes
    are flushed first so none is lost)."""
    await session.flush()
    locked = (
        await session.scalars(
            select(Conversation)
            .where(Conversation.id == conv.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one_or_none()
    if locked is None:
        raise ApiError("not_found")
    return locked


async def apply(
    session: AsyncSession,
    conv: Conversation,
    target: uuid.UUID | None,
    *,
    actor: Actor,
    now: datetime,
    contact: Contact | None = None,
    human_agent: bool = False,
) -> bool:
    """Set the assignee and do everything that goes with it (see the module docstring). ``conv``
    is locked by the caller. Returns False when ``target`` already has it."""
    previous = conv.assignee_user_id
    if previous == target:
        return False
    contact = contact or await session.get(Contact, conv.contact_id)
    if contact is None:  # pragma: no cover - foreign keys cascade
        raise ApiError("not_found")
    conv.assignee_user_id = target
    conv.assigned_at = now if target is not None else None
    await session.flush()

    names = await _labels(session, {u for u in (previous, target) if u is not None})
    to_name = names.get(target) if target else None
    from_name = names.get(previous) if previous else None
    self_assigned = target is not None and target == actor.user_id
    await takeover.add_note(
        session,
        conv,
        note_text(
            actor.via,
            actor=actor.label,
            previous=from_name,
            target=(to_name or "a team member") if target else None,
            self_assigned=self_assigned,
        ),
        at=now,
    )
    action = "conversation.assigned" if target else "conversation.unassigned"
    detail = {
        "via": actor.via,
        "to_user_id": target,
        "to_name": to_name,
        "from_user_id": previous,
        "from_name": from_name,
        "contact_id": contact.id,
    }
    if actor.ctx is not None:
        await audit.record(session, actor.ctx, action, "conversation", conv.id, **detail)
    else:
        audit.record_system(session, actor.label, action, "conversation", conv.id, **detail)
    await events.queue_conversation(
        session, conv, now=now, contact=contact, human_agent=human_agent
    )
    await webhook_events.conversation_assigned(
        session,
        contact,
        conversation_id=conv.id,
        platform=conv.platform,
        assignee={"user_id": str(target), "name": to_name} if target else None,
        previous={"user_id": str(previous), "name": from_name} if previous else None,
        assigned_by={
            "kind": actor.via,
            "user_id": str(actor.user_id) if actor.user_id else None,
        },
    )
    if target is not None and not self_assigned:
        who = contact.display_name or (f"@{contact.username}" if contact.username else "A contact")
        await notify_user(
            session,
            target,
            type=NotificationType.CONVERSATION_ASSIGNED,
            severity="info",
            title=f"{who} was assigned to you",
            body=_notification_body(actor),
            link=f"/inbox/{conv.id}",
            dedupe_key=f"assigned:{conv.id}:{now.isoformat()}",
        )
    return True


def _notification_body(actor: Actor) -> str:
    if actor.via == "round_robin":
        return "It was your turn in the round-robin."
    if actor.via == "automation":
        return f"{actor.label.removeprefix('Automation: ')} handed it to you."
    return f"{actor.label} assigned it to you."
