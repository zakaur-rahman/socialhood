"""Workspace and accounts (01-design.md §4.1): get_workspace, list_accounts."""

from __future__ import annotations

import uuid
from datetime import UTC
from typing import Literal

from pydantic import BaseModel, Field

from socialhood.billing.plans import entitlement
from socialhood.mcp.calls import DAILY_CAP, plan_cap
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import ToolInput, ToolOutput, registry, tool
from socialhood.mcp.tools.common import moment
from socialhood.models.connections import AccountStatus
from socialhood.models.identity import User
from socialhood.repositories import social_accounts
from socialhood.services.scheduled_posts import calendar, views

# ---------------------------------------------------------------- get_workspace


class GetWorkspaceInput(ToolInput):
    pass


class WorkspaceInfo(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    plan: str  # free, pro, max


class MemberInfo(BaseModel):
    user_id: uuid.UUID
    name: str | None = None
    role: str  # owner, admin, agent


class ConnectionInfo(BaseModel):
    kind: str  # api_key, oauth
    label: str
    scopes: list[str]
    # What AI apps may do here now: off, read_only, read_drafts or full (the workspace's
    # setting, capped by the plan).
    mode: str
    mode_setting: str
    plan_allows: str  # the most this plan allows


class Usage(BaseModel):
    tool_calls_today: int  # UTC day, this call included
    tool_calls_daily_limit: int | None = None


class WorkspaceResult(ToolOutput):
    workspace: WorkspaceInfo
    member: MemberInfo
    connection: ConnectionInfo
    usage: Usage
    dashboard_url: str | None = None


@tool(
    registry,
    name="get_workspace",
    title="Get workspace",
    description=(
        "The workspace this connection is for: its name, plan and time zone, the member it acts "
        "as and their role, the scopes granted, what AI apps may do here (the mode), and today's "
        "tool calls against the plan's daily limit. A good first call."
    ),
    input_model=GetWorkspaceInput,
    output_model=WorkspaceResult,
    scope="workspace:read",
    always_listed=True,
)
async def get_workspace(call: ToolCall, args: GetWorkspaceInput) -> WorkspaceResult:
    workspace, principal = call.workspace, call.principal
    user = await call.session.get(User, principal.user_id)
    try:
        raw = await call.redis.get(f"mcp-calls:{workspace.id}:{call.now.astimezone(UTC):%Y-%m-%d}")
        used = int(raw or 0)
    except Exception:
        used = 0
    caveats = []
    if call.mode.value == "off":
        caveats.append(
            "AI connections are turned off for this workspace, so no other tool can be used "
            "until an owner or admin turns them on in Amplychat, under Settings."
        )
    return WorkspaceResult(
        summary=f"Connected to {workspace.name} ({call.plan.capitalize()} plan) as "
        f"{principal.role.value}; AI apps may: {call.mode.value.replace('_', ' ')}",
        workspace=WorkspaceInfo(
            id=workspace.id, name=workspace.name, timezone=call.timezone.key, plan=call.plan
        ),
        member=MemberInfo(
            user_id=principal.user_id,
            name=user.name if user else None,
            role=principal.role.value,
        ),
        connection=ConnectionInfo(
            kind=principal.credential.value,
            label=principal.credential_label,
            scopes=sorted(principal.scopes),
            mode=call.mode.value,
            mode_setting=workspace.ai_connections_mode,
            plan_allows=plan_cap(call.plan).value,
        ),
        usage=Usage(
            tool_calls_today=used, tool_calls_daily_limit=entitlement(call.plan, DAILY_CAP)
        ),
        dashboard_url=call.dashboard_url("home"),
        caveats=caveats,
    )


# ---------------------------------------------------------------- list_accounts


class ListAccountsInput(ToolInput):
    platform: Literal["instagram", "facebook", "whatsapp", "web"] | None = Field(
        default=None, description="Only this platform's accounts."
    )


class AccountItem(BaseModel):
    id: uuid.UUID
    platform: str
    handle: str | None = None  # @username (Instagram) or the account's name
    name: str | None = None
    status: str  # active, needs_reconnect, disconnected, error
    can_publish: bool  # can take scheduled posts now
    needs_reconnect: bool
    published_last_24h: int | None = None  # publishing accounts only
    publishing_limit: int | None = None  # posts per 24 hours the platform allows
    next_free_slot: str | None = None  # the next free posting time, local and UTC


class AccountsResult(ToolOutput):
    items: list[AccountItem]


@tool(
    registry,
    name="list_accounts",
    title="List connected accounts",
    description=(
        "The workspace's connected Instagram, Facebook, WhatsApp and website chat accounts with "
        "their ids and handles, whether each can take scheduled posts now or needs "
        "reconnecting, and for publishing accounts the posts of the last 24 hours against the "
        "platform's limit. Account arguments of other tools take these ids or @handles."
    ),
    input_model=ListAccountsInput,
    output_model=AccountsResult,
    scope="workspace:read",
)
async def list_accounts(call: ToolCall, args: ListAccountsInput) -> AccountsResult:
    accounts = [
        a
        for a in await social_accounts.list_all(call.session)
        if args.platform is None or a.platform == args.platform
    ]
    today = call.now.astimezone(call.timezone).date()
    rail = await calendar.calendar(
        call.session,
        start_day=today,
        end_day=today,
        account_ids=[a.id for a in accounts],
        layers=("posts",),
        deps=call.deps,
        timezone=call.timezone.key,
        now=call.now,
    )
    publishing = {row.social_account_id: row for row in rail.accounts}
    items = []
    for a in accounts:
        row = publishing.get(a.id)
        items.append(
            AccountItem(
                id=a.id,
                platform=a.platform,
                handle=f"@{a.username}" if a.username else a.display_name,
                name=a.display_name,
                status=a.status,
                can_publish=row is not None and views.can_publish(a, call.deps),
                needs_reconnect=a.status == AccountStatus.NEEDS_RECONNECT,
                published_last_24h=row.published_24h if row else None,
                publishing_limit=row.publishing_limit if row else None,
                next_free_slot=moment(call, row.next_free_at) if row else None,
            )
        )
    noun = "account" if len(items) == 1 else "accounts"
    return AccountsResult(
        summary=f"{len(items)} connected {noun}, {sum(i.can_publish for i in items)} can publish",
        items=items,
        caveats=[] if items else ["No accounts are connected yet. Connect one in Amplychat."],
    )
