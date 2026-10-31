"""AI app connections (C-165 phase C): the consent page's request, and Settings, Connected AI
apps."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

ModeName = Literal["off", "read_only", "read_drafts", "full"]


# ---------------------------------------------------------------- the consent page


class ConnectClient(ResponseModel):
    name: str
    # Shown only for a metadata-document client whose logo is on the document's own host.
    logo_url: str | None = None
    # The host that serves the client's metadata document (it proved it speaks for the
    # client); None for a client that registered itself (its name isn't checked).
    verified_host: str | None = None
    redirect_host: str  # where the browser goes back to
    loopback: bool  # an app on this computer (Claude Code, Codex): the spec's warning applies


class ConnectScope(ResponseModel):
    scope: str
    description: str


class ConnectScopeGroup(ResponseModel):
    id: str
    label: str
    scopes: list[ConnectScope]


class ConnectWorkspace(ResponseModel):
    id: uuid.UUID
    name: str
    plan: str
    role: Literal["owner", "admin", "agent"]
    mode: ModeName
    can_connect: bool
    reason: str | None = None


class ConnectMember(ResponseModel):
    email: str
    name: str | None = None


class ConnectRequest(ResponseModel):
    client: ConnectClient
    always: str  # what every connection may do (workspace:read)
    groups: list[ConnectScopeGroup]  # only what the app asked for
    member: ConnectMember
    workspaces: list[ConnectWorkspace]


class ConnectApproval(RequestModel):
    workspace_id: uuid.UUID
    scopes: list[str] = Field(default_factory=list, max_length=30)


class ConnectRedirect(ResponseModel):
    redirect_to: str


# ---------------------------------------------------------------- Settings


class AiConnectionCall(ResponseModel):
    id: uuid.UUID
    tool: str
    outcome: Literal["ok", "error", "refused"]
    error_code: str | None = None
    created_at: datetime


class AiConnectionMember(ResponseModel):
    id: uuid.UUID
    name: str | None = None
    email: str


class AiConnection(ResponseModel):
    id: uuid.UUID
    client_name: str
    verified_host: str | None = None
    redirect_host: str
    member: AiConnectionMember
    is_yours: bool
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime
    calls_7d: int
    recent_calls: list[AiConnectionCall]


class AiConnectionList(ResponseModel):
    items: list[AiConnection]
    # Owners and admins see and revoke everyone's; other members see their own.
    can_manage_all: bool


class AiConnectionActivity(ResponseModel):
    items: list[AiConnectionCall]


class AiConnectionsRevoked(ResponseModel):
    revoked: int
