"""Automations for upcoming posts (T4.7; FR-AUT-18): link "next post" automations to the post
that appears, and scheduled-post automations to their post once it publishes (P7).

``on_new_media_item`` is called wherever a new media item is stored (post sync, and comment intake
when a comment arrives on a post we have not synced yet), in the caller's transaction.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.media import MediaItem


async def on_new_media_item(session: AsyncSession, item: MediaItem) -> None:
    return None  # T4.7
