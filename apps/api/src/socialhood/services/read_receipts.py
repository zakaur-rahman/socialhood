"""Read receipts to the platform (T3.6, TR-PL table): when a member opens a conversation, the
read API marks it read in our database and calls ``after_marked_read``, which (once T3.6 lands)
enqueues the platform "seen" call for accounts with the read_receipts capability."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.inbox import Conversation


async def after_marked_read(session: AsyncSession, conv: Conversation) -> None:
    return None
