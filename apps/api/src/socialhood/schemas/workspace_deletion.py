"""DELETE /v1/w/{wid}'s answer (FR-ACC-05, F-16)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from socialhood.schemas.common import ResponseModel


class WorkspaceDeletion(ResponseModel):
    id: uuid.UUID
    status: Literal["deleting"]
    deletion_requested_at: datetime
    # Every row, file and cached key is gone by then (FR-ACC-05: within 24 hours).
    purge_by: datetime
