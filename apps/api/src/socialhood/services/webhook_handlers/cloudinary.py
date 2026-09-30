"""Cloudinary notifications (P7b, TB.2; TR-MED-05, TR-WH-05).

The workspace comes from the notification's ``public_id``: every upload lives under
``ws/{workspace_id}/`` (TR-MED-01), so no cross-workspace lookup is needed. In that workspace's
scope, TB.2 finds the render by ``batch_id`` (media_renders.batch_id, set by start_render) and,
for an ``eager`` notification, marks it ready from the entry whose ``transformation`` matches the
render's (width, height, bytes, secure_url; the transformation comes back URL-decoded, so compare
decoded) or failed with Cloudinary's reason; then publishes media_render.updated and
scheduled_post.updated for the posts whose items use it. A notification for no known render,
another notification type, or a render already final is ``ignored`` with the reason.

Until TB.2 builds that, every verified notification is stored and ignored here, so nothing is
lost: poll_render finishes renders on its own.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.platform import WebhookEvent
from socialhood.services.webhook_handlers import Outcome

_WORKSPACE = re.compile(
    r"^ws/(?P<wid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/"
)


def workspace_of(payload: Mapping[str, Any]) -> uuid.UUID | None:
    """The workspace whose folder holds the notification's asset, or None."""
    public_id = payload.get("public_id")
    if not isinstance(public_id, str):
        return None
    match = _WORKSPACE.match(public_id)
    return uuid.UUID(match["wid"]) if match else None


async def handle(session: AsyncSession, event: WebhookEvent) -> Outcome:
    workspace_id = workspace_of(event.payload)
    if workspace_id is None:
        return Outcome("ignored", "not an asset of a workspace")
    return Outcome("ignored", "render notifications are applied from TB.2", workspace_id)
