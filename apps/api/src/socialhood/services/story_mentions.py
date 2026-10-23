"""Story mentions (GR-07): the record kept when someone mentions the account in their story, and
the Mentions list.

A mention arrives as a DM with a ``story_mention`` attachment (platforms/instagram/parse). Ingest
calls ``record`` for each new one: who, when, and the story's address on Instagram's CDN with the
time it stops working (its ``oe`` parameter, else 24 hours after the mention, the life of a story).
The media itself is never downloaded or copied; the address is kept only while it is live and is
cleared after (repositories/retention.clear_expired_mention_links, run by purge_expired). The list
gives the address only while it is live.

The automation that thanks the person runs through the DM runtime like any DM: the message kind
``story_mention`` picks the story mention triggers (services/automations/runtime).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import Contact, Message
from socialhood.platforms.instagram.parse import media_url_expiry
from socialhood.repositories import story_mentions as repo
from socialhood.schemas.stories import MentionContact, StoryMention, StoryMentionList
from socialhood.services.conversations import decode_cursor, encode_cursor

STORY_LIFETIME = timedelta(hours=24)
RECENT = timedelta(days=7)


def _story_url(msg: Message) -> str | None:
    for attachment in msg.attachments or []:
        if attachment.get("type") == "story":
            url = attachment.get("platform_url") or attachment.get("url")
            return str(url) if url else None
    return None


async def record(
    session: AsyncSession, acct: SocialAccount, contact: Contact, msg: Message, *, now: datetime
) -> bool:
    """Keep the mention in the caller's transaction; False for a message already recorded."""
    url = _story_url(msg)
    expires = media_url_expiry(url) or msg.occurred_at + STORY_LIFETIME
    live = url is not None and expires > now
    return await repo.insert_mention(
        session,
        {
            "social_account_id": acct.id,
            "contact_id": contact.id,
            "message_id": msg.id,
            "mentioned_at": msg.occurred_at,
            "media_url": url if live else None,
            "media_expires_at": expires if url is not None else None,
        },
    )


def _link(url: str | None, expires: datetime | None, now: datetime) -> dict[str, Any]:
    """The story's address only while it is live."""
    live = url is not None and (expires is None or expires > now)
    return {"link_url": url if live else None, "link_expires_at": expires if live else None}


async def list_mentions(
    session: AsyncSession,
    *,
    account_id: uuid.UUID | None,
    cursor: str | None,
    limit: int,
    now: datetime,
) -> StoryMentionList:
    rows = await repo.list_page(
        session,
        account_id=account_id,
        after=decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )
    page = rows[:limit]
    items = [
        StoryMention(
            id=row.mention.id,
            social_account_id=row.mention.social_account_id,
            mentioned_at=row.mention.mentioned_at,
            contact=MentionContact(
                id=row.contact.id,
                display_name=row.contact.display_name,
                username=row.contact.username,
                profile_picture_url=row.contact.profile_picture_url,
            ),
            conversation_id=row.conversation_id,
            **_link(row.mention.media_url, row.mention.media_expires_at, now),
        )
        for row in page
    ]
    last = page[-1].mention if page else None
    return StoryMentionList(
        items=items,
        next_cursor=(
            encode_cursor(last.mentioned_at, last.id) if len(rows) > limit and last else None
        ),
        total_7d=await repo.count_since(session, now - RECENT, account_id=account_id),
    )
