"""Platform-agnostic ingest (T3.2; F-06, TR-WH-06, TR-PL-12, FR-INB-09): typed inbound events
from any platform's parser become contacts, conversations and messages.

Contract (shared by the Instagram and WhatsApp handlers):
- runs inside the account's workspace scope, in the caller's transaction; never commits;
- idempotent: replaying the same events creates nothing new and triggers nothing (TR-WH-06);
- queues real-time events with ``realtime.events.queue_message`` / ``queue_conversation``;
  the caller publishes them after its commit;
- enqueues follow-ups (profile fetch, media copy) only for rows it actually created.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.connections import SocialAccount
from socialhood.platforms.events import InboundEvent


@dataclass
class IngestResult:
    created_message_ids: list[uuid.UUID] = field(default_factory=list)
    updated_message_ids: list[uuid.UUID] = field(default_factory=list)
    conversation_ids: list[uuid.UUID] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)  # reasons, for the webhook event's note


async def ingest(
    session: AsyncSession,
    acct: SocialAccount,
    events: Sequence[InboundEvent],
    *,
    now: datetime | None = None,
) -> IngestResult:
    raise NotImplementedError("T3.2")
