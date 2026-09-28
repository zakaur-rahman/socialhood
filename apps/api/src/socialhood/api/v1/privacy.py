"""GET /v1/data-deletion/{code}: the public status of a Meta data-deletion request (F-16)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path

from socialhood.auth.deps import Session
from socialhood.errors import ApiError
from socialhood.repositories import data_deletion
from socialhood.schemas.accounts import DataDeletionStatus

router = APIRouter(prefix="/v1", tags=["privacy"])


@router.get("/data-deletion/{code}", operation_id="get_data_deletion_status")
async def get_data_deletion_status(
    code: Annotated[str, Path(min_length=8, max_length=64)], session: Session
) -> DataDeletionStatus:
    request = await data_deletion.get_by_code(session, code)
    if request is None:
        raise ApiError("not_found")
    return DataDeletionStatus.model_validate(request)
