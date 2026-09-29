"""Me, workspace and overview shapes (§5.10 has none for these; see docs/QUESTIONS.md Q-007)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

RoleName = Literal["owner", "admin", "agent"]
PlanName = Literal["free", "pro", "max"]


class WorkspaceSummary(ResponseModel):
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    role: RoleName
    plan: PlanName


class Me(ResponseModel):
    id: uuid.UUID
    email: str
    name: str | None = None
    avatar_url: str | None = None
    last_workspace_id: uuid.UUID | None = None
    workspaces: list[WorkspaceSummary]


class WorkspaceList(ResponseModel):
    items: list[WorkspaceSummary]
    next_cursor: str | None = None


class WorkspaceOut(ResponseModel):
    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    reply_language: str
    status: Literal["active", "deleting"]
    role: RoleName
    plan: PlanName
    automation_disclosure: str | None = None
    checklist_dismissed_at: datetime | None = None
    created_at: datetime


class WorkspacePatch(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    slug: str | None = Field(default=None, min_length=3, max_length=48)
    timezone: str | None = Field(default=None, max_length=64)
    reply_language: str | None = Field(default=None, max_length=35)
    automation_disclosure: str | None = Field(default=None, max_length=60)
    checklist_dismissed: bool | None = None


ChecklistKey = Literal["connect_account", "add_knowledge", "choose_ai_mode", "create_automation"]


class ChecklistStep(ResponseModel):
    key: ChecklistKey
    done: bool


class Checklist(ResponseModel):
    dismissed: bool
    completed: int
    steps: list[ChecklistStep]


class Overview(ResponseModel):
    range: Literal["7d", "30d"]
    checklist: Checklist
    knowledge_gaps_open: int = 0  # FR-KB-06: Home's "Questions the AI couldn't answer" (T5.10)
