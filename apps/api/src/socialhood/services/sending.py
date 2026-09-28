"""The outbound pipeline's entry point (T3.6; FR-INB-06, 07, 10; TR-JOB-04, TR-JOB-05).

Contract (shared by the send endpoint, scheduled messages and, later, AI and automations):
``queue_outbound`` checks the account, capabilities, reply window and length limits, inserts the
message as ``queued``, updates the conversation, queues real-time events and enqueues
``send_message``. It runs in the caller's transaction and workspace scope and does not commit;
the caller commits with ``realtime.events.commit_and_publish``. Rule failures raise ``ApiError``
with the §4.7 codes (reply_window_closed, account_needs_reconnect, capability_unavailable,
validation_error).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.inbox import Conversation, Message
from socialhood.platforms.base import OutboundTemplate

OutboundSource = Literal["human", "ai_auto", "automation"]


async def queue_outbound(
    session: AsyncSession,
    conv: Conversation,
    *,
    source: OutboundSource,
    client_id: uuid.UUID,
    text: str | None = None,
    attachment_asset_ids: Sequence[uuid.UUID] = (),
    template: OutboundTemplate | None = None,
    sent_by_user_id: uuid.UUID | None = None,
    scheduled_message_id: uuid.UUID | None = None,
    suggestion_id: uuid.UUID | None = None,
) -> Message:
    raise NotImplementedError("T3.6")
