"""Push delivery (T8.6; FR-NOT-03, F-19): one notification to every device of its recipient.

``deliver`` locks the notification (in its workspace's scope; FOR UPDATE SKIP LOCKED, so a second
job for it does nothing), checks that it is marked for push and not pushed yet, that its type
pushes (models/notifications.PUSH_EVENT_OF_TYPE) and that the member's switch for that event is
still on (workspace_members.notification_prefs["push"]), then sends ``push_message`` to each of
the user's enabled push_subscriptions at once.

Per device: success resets failure_count and sets last_used_at; PushGone (404 or 410) deletes the
subscription (TR-FE-09); any other failure adds one to failure_count, and PUSH_MAX_FAILURES in a
row disable the row. ``pushed_at`` records the attempt, so a retried job never pushes twice.

Retries: when no device was reached and a failure was retryable (429, 5xx, a timeout) and the job
will run again, the gone subscriptions are deleted, nothing else is recorded, and the error is
raised for the job to retry; the next attempt sends to every device again (none got it). Once a
device is reached, or on the last attempt, the push is settled: failures are counted and
pushed_at is set. Without VAPID keys nothing is sent and no device is blamed.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.models.identity import Workspace
from socialhood.models.notifications import (
    PUSH_EVENT_OF_TYPE,
    PUSH_MAX_FAILURES,
    Notification,
    NotificationChannel,
)
from socialhood.notify import preferences
from socialhood.notify.push import (
    PushError,
    PushGone,
    PushMessage,
    PushNotConfigured,
    PushSender,
    PushTarget,
)
from socialhood.observability.logging import get_logger
from socialhood.repositories import push_subscriptions as devices

log = get_logger(__name__)

TITLE_CHARS = 80
BODY_CHARS = 240
_CONVERSATION_LINK = re.compile(r"^/inbox/([0-9a-fA-F-]{36})")


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def push_message(notification: Notification, slug: str) -> PushMessage:
    """What the service worker shows: the notification's title and body, and on tap its link in
    the workspace (``/w/{slug}/inbox/{id}`` opens the conversation). The tag groups a device's
    notifications per conversation (or per type otherwise), so a newer one replaces an older one.
    Titles and bodies are clipped, which keeps the payload far under 3,000 bytes."""
    link = notification.link or "/home"
    if not link.startswith("/"):
        link = "/" + link
    match = _CONVERSATION_LINK.match(link)
    tag = f"conversation:{match.group(1)}" if match else f"{notification.type}:{slug}"
    urgency: Literal["high", "normal"] = (
        "high" if notification.severity in ("warning", "critical") else "normal"
    )
    return PushMessage(
        title=_clip(notification.title, TITLE_CHARS),
        body=_clip(notification.body, BODY_CHARS),
        url=f"/w/{slug}{link}",
        tag=tag,
        urgency=urgency,
    )


async def _lock(session: AsyncSession, notification_id: uuid.UUID) -> Notification | None:
    return (
        await session.scalars(
            select(Notification)
            .where(Notification.id == notification_id)
            .with_for_update(skip_locked=True)
        )
    ).one_or_none()


async def _wanted(session: AsyncSession, notification: Notification) -> bool:
    event = PUSH_EVENT_OF_TYPE.get(notification.type)
    if event is None or NotificationChannel.PUSH not in (notification.channels or []):
        return False
    member = await preferences.member(session, notification.user_id)
    return member is not None and preferences.pushes(member.notification_prefs, event)


async def deliver(
    sessionmaker: async_sessionmaker[AsyncSession],
    notification_id: uuid.UUID,
    *,
    sender: PushSender,
    will_retry: Callable[[PushError], bool] | None = None,
    now: datetime | None = None,
) -> int:
    """Returns the number of devices the push reached."""
    async with sessionmaker() as session:
        notification = await _lock(session, notification_id)
        if notification is None or notification.pushed_at is not None:
            return 0
        at = now or datetime.now(UTC)
        targets = await devices.enabled_for_user(session, notification.user_id)
        if not targets or not await _wanted(session, notification):
            notification.pushed_at = at
            await session.commit()
            return 0
        workspace = await session.get(Workspace, notification.workspace_id)
        message = push_message(notification, workspace.slug if workspace else "")

        async def one(target: PushTarget) -> PushError | None:
            try:
                await sender.send(target, message)
            except PushError as error:
                return error
            return None

        outcomes = await asyncio.gather(
            *(one(PushTarget(endpoint=d.endpoint, p256dh=d.p256dh, auth=d.auth)) for d in targets)
        )
        results = list(zip((d.id for d in targets), outcomes, strict=True))
        reached = [device for device, error in results if error is None]
        gone = [device for device, error in results if isinstance(error, PushGone)]
        failed = [
            (device, error)
            for device, error in results
            if error is not None and not isinstance(error, PushGone)
        ]
        await devices.delete_gone(session, gone)

        if any(isinstance(error, PushNotConfigured) for _, error in failed):
            notification.pushed_at = at  # no keys: nothing can be sent, no device is at fault
            await session.commit()
            log.warning("push_not_configured", notification_id=str(notification_id))
            return 0

        retryable = [error for _, error in failed if error.retryable]
        if not reached and retryable and will_retry is not None and will_retry(retryable[0]):
            await session.commit()  # the deletions only; the push is sent again
            log.info("push_retry", notification_id=str(notification_id), devices=len(failed))
            raise retryable[0]

        await devices.record_success(session, reached, at)
        disabled = await devices.record_failure(
            session, [device for device, _ in failed], at, disable_at=PUSH_MAX_FAILURES
        )
        notification.pushed_at = at
        await session.commit()
    log.info(
        "push_delivered",
        notification_id=str(notification_id),
        type=notification.type,
        reached=len(reached),
        gone=len(gone),
        failed=len(failed),
        disabled=len(disabled),
    )
    return len(reached)
