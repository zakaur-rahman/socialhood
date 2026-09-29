"""Which workspace a Dodo event belongs to (T8.3; TR-WH-05). A cross-workspace lookup before any
workspace is known, so it lives in webhooks/, where the tenant bypass is allowed (TR-TEN-04).

Order: the ``metadata.workspace_id`` the checkout set (TR-BIL-01), if that workspace exists and
isn't being deleted; else the workspace whose subscriptions.dodo_subscription_id matches; else
None (ignored).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_workspace(session: AsyncSession, payload: Mapping[str, Any]) -> uuid.UUID | None:
    raise NotImplementedError("T8.3")
