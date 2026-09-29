"""Push delivery (T8.6; FR-NOT-03, F-19): one notification to every device of its recipient.

``deliver`` loads the notification (in its workspace's scope), checks that its type pushes
(models/notifications.PUSH_EVENT_OF_TYPE) and that the member's switch for that event is on
(workspace_members.notification_prefs["push"]), then sends ``PushMessage(title, body,
url=/w/{slug}{link})`` to each of the user's enabled push_subscriptions. PushGone deletes the
subscription; another failure increments failure_count and disables the row at
PUSH_MAX_FAILURES; a success resets the count and sets last_used_at. ``pushed_at`` records the
attempt, so a retried job never pushes twice.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.notify.push import PushSender


async def deliver(
    sessionmaker: async_sessionmaker[AsyncSession],
    notification_id: uuid.UUID,
    *,
    sender: PushSender,
) -> int:
    """Returns the number of devices the push reached."""
    raise NotImplementedError("T8.6")
