"""Request dependencies.

The signed-in user (TR-AUTH-01…05) and the workspace in the path (TR-TEN-01, TR-TEN-05).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.clerk import ClerkClient, ClerkUnavailable, InvalidToken, verify_session_token
from socialhood.db.session import get_session
from socialhood.db.tenancy import current_workspace_id
from socialhood.errors import ApiError
from socialhood.models.identity import Role, User, Workspace, WorkspaceMember, WorkspaceStatus
from socialhood.observability.logging import get_logger
from socialhood.repositories import users
from socialhood.services.provisioning import provision_user
from socialhood.settings import Settings

LAST_SEEN_EVERY_S = 15 * 60
ROLE_RANK = {Role.AGENT: 1, Role.ADMIN: 2, Role.OWNER: 3}

log = get_logger(__name__)

Session = Annotated[AsyncSession, Depends(get_session)]


def _bearer(request: Request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError("unauthorized")
    return token.strip()


async def current_user(request: Request, session: Session) -> User:
    settings: Settings = request.app.state.settings
    try:
        clerk_id = verify_session_token(_bearer(request), settings)
    except InvalidToken as error:
        raise ApiError("unauthorized") from error

    user = await users.get_by_clerk_id(session, clerk_id)
    if user is None:
        clerk = ClerkClient(request.app.state.http, settings)
        try:
            profile = await clerk.get_user(clerk_id)
        except ClerkUnavailable as error:
            log.warning("clerk_fetch_failed", reason=str(error))
            raise ApiError(
                "service_unavailable", "Couldn't load your account. Try again in a moment."
            ) from error
        await provision_user(session, profile)
        user = await users.get_by_clerk_id(session, clerk_id)
        if user is None:  # pragma: no cover
            raise ApiError("internal")

    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    await _touch_last_seen(request, session, user)
    return user


async def _touch_last_seen(request: Request, session: AsyncSession, user: User) -> None:
    """At most one write per user per 15 minutes (TR-AUTH-05); a Valkey outage never blocks."""
    try:
        first = await request.app.state.redis.set(
            f"seen:{user.id}", "1", nx=True, ex=LAST_SEEN_EVERY_S
        )
    except Exception:
        return
    if first:
        await users.touch_last_seen(session, user.id, datetime.now(UTC))
        await session.commit()


CurrentUser = Annotated[User, Depends(current_user)]


@dataclass(frozen=True)
class WorkspaceContext:
    workspace: Workspace
    role: Role
    user: User

    @property
    def workspace_id(self) -> uuid.UUID:
        return self.workspace.id


async def workspace_ctx(
    wid: uuid.UUID, user: CurrentUser, session: Session
) -> AsyncIterator[WorkspaceContext]:
    """Load the membership for (wid, user). Anything else is 404, never 403 (TR-API-03)."""
    token = current_workspace_id.set(wid)
    try:
        member = (
            await session.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
        ).one_or_none()
        workspace = await session.get(Workspace, wid) if member is not None else None
        if member is None or workspace is None or workspace.status != WorkspaceStatus.ACTIVE:
            raise ApiError("not_found")
        structlog.contextvars.bind_contextvars(workspace_id=str(wid))
        yield WorkspaceContext(workspace=workspace, role=Role(member.role), user=user)
    finally:
        with suppress(ValueError):  # a different context (after the response) cannot reset
            current_workspace_id.reset(token)


def require_role(minimum: Role) -> Callable[..., Awaitable[WorkspaceContext]]:
    """Routes declare their minimum role now, although every R1 member is an owner (TR-TEN-05)."""

    async def dependency(
        ctx: Annotated[WorkspaceContext, Depends(workspace_ctx)],
    ) -> WorkspaceContext:
        if ROLE_RANK[ctx.role] < ROLE_RANK[minimum]:
            raise ApiError("forbidden")
        return ctx

    return dependency


AnyMember = Annotated[WorkspaceContext, Depends(workspace_ctx)]
Admin = Annotated[WorkspaceContext, Depends(require_role(Role.ADMIN))]
Owner = Annotated[WorkspaceContext, Depends(require_role(Role.OWNER))]
