"""Automations for upcoming posts (T4.7; FR-AUT-18): link "next post" automations to the post
that appears, and scheduled-post automations to their post once it publishes (P7).

``on_new_media_item`` is called wherever a new media item is stored (post sync, and comment intake
when a comment arrives on a post we have not synced yet), in the caller's transaction.
``link_next_posts`` does the work for a whole account, so post sync calls it once after storing a
batch. ``link_scheduled_post`` is for P7's publish step (T7.3), in the same transaction that
inserts the published post's media item.

A next-post automation waits, active and without a post, for the account's first post (not a
story) published at or after its activation; that post becomes its only post. Pausing does not
unlink it; reactivating a waiting automation waits for a post after the new activation.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.automations import AutomationPost
from socialhood.models.media import MediaItem
from socialhood.observability.logging import get_logger
from socialhood.repositories import automations as repo

log = get_logger(__name__)


async def on_new_media_item(session: AsyncSession, item: MediaItem) -> None:
    await session.flush()  # the item must be visible to the lookup (sessions do not autoflush)
    await link_next_posts(session, item.social_account_id)


async def link_next_posts(session: AsyncSession, social_account_id: uuid.UUID) -> list[uuid.UUID]:
    """Link each waiting next-post automation of the account to the first post published at or
    after its activation; returns the automations linked. The automations are locked, and each
    is checked for a post after the lock, so concurrent callers link it once."""
    linked: list[uuid.UUID] = []
    for automation in await repo.lock_waiting_for_next_post(session, social_account_id):
        if automation.activated_at is None or await repo.has_posts(session, automation.id):
            continue
        item = await repo.first_post_since(session, social_account_id, automation.activated_at)
        if item is None:
            continue
        session.add(AutomationPost(automation_id=automation.id, media_item_id=item.id))
        linked.append(automation.id)
    if linked:
        await session.flush()
        log.info("next_post_linked", account_id=str(social_account_id), automations=len(linked))
    return linked


async def link_scheduled_post(
    session: AsyncSession, scheduled_post_id: uuid.UUID, item: MediaItem
) -> int:
    """A scheduled post published as ``item``: the automations of that account scoped to it now
    answer comments on the post. Returns how many links were filled."""
    await session.flush()
    rows = await repo.unlinked_scheduled_posts(session, scheduled_post_id, item.social_account_id)
    for row in rows:
        row.media_item_id = item.id
    if rows:
        await session.flush()
    return len(rows)
