"""DELETE /v1/w/{wid}: delete the workspace (FR-ACC-05, F-16; owner only, §2.15).

The owner confirms by typing the workspace's name (``confirm_name``, compared after trimming
spaces; a mismatch is 422 on confirm_name). The answer is 202: the workspace is already
unreachable (every route answers 404), its tokens are destroyed and its purge is queued; every row,
file and cached key is gone by ``purge_by`` (services/workspace_deletion.py).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from socialhood.auth.deps import Owner, Session
from socialhood.schemas.workspace_deletion import WorkspaceDeletion
from socialhood.services import workspace_deletion as service

router = APIRouter(prefix="/v1/w/{wid}", tags=["workspaces"])


@router.delete("", status_code=202, operation_id="delete_workspace")
async def delete_workspace(
    ctx: Owner,
    session: Session,
    confirm_name: Annotated[str, Query(min_length=1, max_length=200)],
) -> WorkspaceDeletion:
    return await service.request_deletion(
        session, ctx.workspace, ctx.user, confirm_name=confirm_name
    )
