"""The signed-in user (GET /v1/me) and their workspaces (GET /v1/workspaces)."""

from __future__ import annotations

from fastapi import APIRouter

from socialhood.auth.deps import CurrentUser, Session
from socialhood.auth.memberships import memberships_for
from socialhood.schemas.workspaces import Me, WorkspaceList, WorkspaceSummary

router = APIRouter(prefix="/v1", tags=["me"])


async def _summaries(session: Session, user: CurrentUser) -> list[WorkspaceSummary]:
    return [
        WorkspaceSummary.model_validate(
            {
                "id": m.workspace_id,
                "name": m.name,
                "slug": m.slug,
                "timezone": m.timezone,
                "role": m.role,
                "plan": m.plan,
            }
        )
        for m in await memberships_for(session, user.id)
    ]


@router.get("/me", operation_id="get_me")
async def get_me(user: CurrentUser, session: Session) -> Me:
    """The current user, provisioned on first sight (TR-AUTH-03), with their workspaces."""
    return Me(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        last_workspace_id=user.last_workspace_id,
        workspaces=await _summaries(session, user),
    )


@router.get("/workspaces", operation_id="list_workspaces")
async def list_workspaces(user: CurrentUser, session: Session) -> WorkspaceList:
    return WorkspaceList(items=await _summaries(session, user))
