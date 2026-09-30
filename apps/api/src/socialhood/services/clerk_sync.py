"""Apply Clerk user events (TR-AUTH-04): profile updates and account deletion.

user.deleted deletes the workspaces the user solely owns (FR-ACC-05) and hands shared ones to
another owner. Each workspace's Dodo subscription is cancelled at once before it is deleted (F-16,
services/workspaces.cancel_dodo_subscription); when Dodo doesn't answer, the workspace is deleted
anyway (the person asked to leave) and the failure is logged at error level with the Dodo
subscription id, for cancelling by hand (C-052).
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.clerk import parse_clerk_user
from socialhood.billing.dodo import DodoClient
from socialhood.billing.registry import get_dodo
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.models.identity import Role, WorkspaceMember
from socialhood.observability.logging import get_logger
from socialhood.repositories import subscriptions, users, workspaces
from socialhood.services import workspaces as workspace_service

log = get_logger(__name__)

Outcome = Literal["processed", "ignored"]


def dodo_client() -> DodoClient:
    """The worker's (Clerk events are processed by the worker); tests swap it with use_dodo."""
    from socialhood.jobs.runtime import runtime

    rt = runtime()
    return get_dodo(rt.http, rt.settings)


async def apply_event(session: AsyncSession, payload: dict[str, Any]) -> Outcome:
    event_type = payload.get("type")
    data = payload.get("data") or {}
    if event_type == "user.updated":
        return await _updated(session, data)
    if event_type == "user.deleted":
        return await _deleted(session, data)
    return "ignored"  # user.created is handled on first sign-in (TR-AUTH-03)


async def _updated(session: AsyncSession, data: dict[str, Any]) -> Outcome:
    profile = parse_clerk_user(data)
    if await users.get_by_clerk_id(session, profile.id) is None:
        return "ignored"  # never signed in to Social Hood
    await users.update_profile(
        session,
        profile.id,
        email=profile.email if profile.email_verified else None,
        name=profile.name,
        avatar_url=profile.image_url,
    )
    return "processed"


async def _deleted(session: AsyncSession, data: dict[str, Any]) -> Outcome:
    clerk_id = data.get("id")
    user = await users.get_by_clerk_id(session, str(clerk_id)) if clerk_id else None
    if user is None:
        return "ignored"
    for workspace in await workspaces.owned_by(session, user.id):
        with workspace_scope(workspace.id):
            other_owner = await session.scalar(
                select(WorkspaceMember.user_id)
                .where(WorkspaceMember.role == Role.OWNER, WorkspaceMember.user_id != user.id)
                .order_by(WorkspaceMember.created_at)
                .limit(1)
            )
            if other_owner is None:
                await _cancel_billing(session, workspace.id)
        if other_owner is None:
            await workspaces.delete_workspace(session, workspace.id)  # solely owned (FR-ACC-05)
        else:
            await workspaces.transfer_ownership(session, workspace.id, other_owner)
    await users.delete(session, user.id)
    return "processed"


async def _cancel_billing(session: AsyncSession, workspace_id: uuid.UUID) -> None:
    """F-16, in the workspace's scope: cancel its Dodo subscription before it is deleted. Dodo not
    answering doesn't stop the deletion; it is logged for cancelling by hand."""
    sub = await subscriptions.current(session)
    if sub is None or not sub.dodo_subscription_id:
        return
    try:
        await workspace_service.cancel_dodo_subscription(session, dodo_client())
    except ApiError:
        log.error(
            "clerk_user_deleted_dodo_cancel_failed",
            workspace_id=str(workspace_id),
            dodo_subscription_id=sub.dodo_subscription_id,
        )
