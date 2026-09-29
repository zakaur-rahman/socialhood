"""The email outbox (T8.5; FR-NOT-02): queue in the caller's transaction, send in a job.

- ``queue_email`` inserts an email_deliveries row (status queued) unless one with the same
  (workspace, dedupe_key) exists, and returns its id or None. It runs in the same transaction as
  what caused it (a notification row, a digest), so an email exists exactly when its cause does.
- The caller enqueues deliver_email after commit (jobs/tasks/emails.py, key ``email:{id}``); a
  sweeper re-enqueues rows still queued after a minute, so a lost enqueue only delays an email.
- ``send_queued`` renders the template (notify/templates/), sends with the dedupe key as the
  Idempotency-Key, and records sent (provider id, sent_at), failed (after the last attempt), or
  skipped (no address, or the member turned the digest off since it was queued).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.notify.email import EmailSender
from socialhood.settings import Settings


async def queue_email(
    session: AsyncSession,
    *,
    template: str,
    to_email: str,
    dedupe_key: str,
    data: Mapping[str, Any],
    user_id: uuid.UUID | None = None,
    notification_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    raise NotImplementedError("T8.5")


async def send_queued(
    sessionmaker: async_sessionmaker[AsyncSession],
    delivery_id: uuid.UUID,
    *,
    sender: EmailSender,
    settings: Settings,
) -> str:
    """Send one queued email; returns its final status."""
    raise NotImplementedError("T8.5")
