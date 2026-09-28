"""The automation runtime (T4.4, T4.6; F-11 runtime, F-12, FR-AUT-05…10, TR-JOB-07).

Entry points:
- ``enqueue_for_message(message)`` / ``enqueue_for_comment(comment)``: called by ingest (new
  inbound DM) and the comment handler (new comment), in their transaction, after the row exists;
  they enqueue ``run_automation(kind, id)`` with key ``automation:{kind}:{id}``.
- ``run_for_message`` / ``run_for_comment``: the job bodies. Load the account's active
  automations of the trigger type inside their run window, match (services/automations/matching),
  skip on cooldown, post scope or an earlier run for the same event, insert automation_runs
  (unique per automation and event) and act. DMs send through services/sending.queue_outbound
  (source automation) and mark the trigger message ``automation_handled``. Comments queue a
  private reply (result ``queued``) and post the public reply variation; the account's
  ``drain_private_replies`` job sends queued private replies within the 750/hour bucket.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import Comment
from socialhood.models.inbox import Message


async def enqueue_for_message(session: AsyncSession, message: Message) -> None:
    return None  # T4.4


async def enqueue_for_comment(session: AsyncSession, comment: Comment) -> None:
    return None  # T4.4


async def run_for_message(workspace_id: uuid.UUID, message_id: uuid.UUID) -> None:
    raise NotImplementedError("T4.4")


async def run_for_comment(workspace_id: uuid.UUID, comment_id: uuid.UUID) -> None:
    raise NotImplementedError("T4.4")
