"""Conversation assignment (GR-20): who can be assigned, the workspace's round-robin setting, and a
member's availability. The assignee on a conversation is ``schemas.inbox.Assignee``."""

from __future__ import annotations

import uuid

from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.team import RoleName


class AssigneeUpdate(RequestModel):
    """PUT …/conversations/{id}/assignee. ``user_id`` null takes the assignment away."""

    user_id: uuid.UUID | None


class Assignable(ResponseModel):
    """A member who can be given a conversation. Any member may list them (the picker), so there
    is no email here: the name is the member's, else the part of their email before the @."""

    user_id: uuid.UUID
    name: str | None
    avatar_url: str | None
    role: RoleName
    available: bool  # whether round-robin may hand them new conversations
    open_conversations: int  # open conversations they have now
    is_you: bool


class AssignmentOverview(ResponseModel):
    round_robin: bool
    members: list[Assignable]


class AssignmentSettingsPut(RequestModel):
    round_robin: bool


class AvailabilityPut(RequestModel):
    available: bool
