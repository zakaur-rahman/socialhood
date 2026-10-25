"""Assignment routes (GR-20): give a conversation to a member or to nobody, who can be assigned,
the round-robin setting, and a member's availability. The rules are in services/assignment.py.

Who may do what: agents take a conversation nobody has and hand on their own (403 otherwise);
owners and admins assign anyone. Any member lists who can be assigned. Admins change the
round-robin setting. Anyone sets their own availability; admins set anyone's.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from socialhood.auth.deps import AnyMember, CanAssign, CanManageSettings, CanSelf, Session
from socialhood.realtime.events import commit_and_publish
from socialhood.schemas.assignment import (
    AssigneeUpdate,
    AssignmentOverview,
    AssignmentSettingsPut,
    AvailabilityPut,
)
from socialhood.schemas.inbox import Conversation
from socialhood.services import assignment, audit
from socialhood.services import conversations as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["assignment"])


@router.put("/conversations/{conversation_id}/assignee", operation_id="assign_conversation")
async def assign_conversation(
    request: Request,
    conversation_id: uuid.UUID,
    body: AssigneeUpdate,
    ctx: CanAssign,
    session: Session,
) -> Conversation:
    """Give the conversation to a member, or to nobody (``user_id`` null). The member is told, and
    the change is in the thread, the contact's timeline and the audit log."""
    conv = await service.get_or_404(session, conversation_id)
    enabled = bool(request.app.state.settings.ig_human_agent_enabled)
    now = datetime.now(UTC)
    if await assignment.member_assign(
        session, ctx, conv, body.user_id, ig_human_agent_enabled=enabled, now=now
    ):
        await commit_and_publish(session, request.app.state.redis)
    return await service.conversation_detail(session, conv, ig_human_agent_enabled=enabled, now=now)


@router.get("/assignment", operation_id="get_assignment")
async def get_assignment(ctx: AnyMember, session: Session) -> AssignmentOverview:
    """The members who can be assigned (with their availability and open conversations) and
    whether round-robin is on."""
    return await assignment.overview(session, ctx.user.id)


@router.put("/assignment/settings", operation_id="update_assignment_settings")
async def update_assignment_settings(
    body: AssignmentSettingsPut, ctx: CanManageSettings, session: Session
) -> AssignmentOverview:
    """Turn round-robin on or off: new conversations nobody has go to the next available member."""
    await assignment.set_round_robin(session, body.round_robin)
    await audit.record(
        session, ctx, "settings.updated", "assignment_settings", round_robin=body.round_robin
    )
    out = await assignment.overview(session, ctx.user.id)
    await session.commit()
    return out


@router.put("/members/{user_id}/availability", operation_id="set_member_availability")
async def set_member_availability(
    user_id: uuid.UUID, body: AvailabilityPut, ctx: CanSelf, session: Session
) -> Response:
    """Whether round-robin may hand this member new conversations. Your own, or any member's if
    you are an owner or admin (403 otherwise)."""
    await assignment.set_available(session, ctx, user_id, body.available)
    await session.commit()
    return Response(status_code=204)
