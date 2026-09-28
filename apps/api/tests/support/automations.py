"""Automation, post and comment rows for tests (written through the ORM in the workspace's scope,
committed, returned as ids)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.automations import Automation, AutomationKeyword, AutomationPost, Comment
from socialhood.models.media import MediaItem
from socialhood.services.automations.matching import normalize


async def make_media_item(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    account_id: uuid.UUID | str,
    platform_media_id: str | None = None,
    caption: str = "New arrivals this week",
    posted_at: datetime | None = None,
) -> uuid.UUID:
    with workspace_scope(uuid.UUID(str(workspace_id))):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = MediaItem(
                social_account_id=uuid.UUID(str(account_id)),
                platform_media_id=platform_media_id or f"1810{uuid.uuid4().int % 10**12:012d}",
                media_type="image",
                caption=caption,
                media_url="https://scontent.cdninstagram.com/v/post.jpg",
                permalink="https://www.instagram.com/p/abc/",
                posted_at=posted_at or datetime.now(UTC) - timedelta(days=1),
            )
            session.add(row)
            await session.commit()
            return row.id


async def make_comment(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    account_id: uuid.UUID | str,
    media_item_id: uuid.UUID,
    text: str = "LINK please",
    author_ref: str | None = None,
    author_username: str = "curious.cat",
    commented_at: datetime | None = None,
    contact_id: uuid.UUID | None = None,
) -> uuid.UUID:
    with workspace_scope(uuid.UUID(str(workspace_id))):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = Comment(
                social_account_id=uuid.UUID(str(account_id)),
                media_item_id=media_item_id,
                contact_id=contact_id,
                platform_comment_id=f"1790{uuid.uuid4().int % 10**12:012d}",
                author_platform_user_id=author_ref or f"99{uuid.uuid4().int % 10**13:013d}",
                author_username=author_username,
                text=text,
                commented_at=commented_at or datetime.now(UTC),
            )
            session.add(row)
            await session.commit()
            return row.id


async def make_automation(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    account_id: uuid.UUID | str | None,
    keywords: tuple[str, ...] = ("link",),
    media_item_ids: tuple[uuid.UUID, ...] = (),
    **values: Any,
) -> uuid.UUID:
    """An automation (active by default, DM keyword → message) with its keywords and posts."""
    defaults: dict[str, Any] = {
        "name": "Send the link",
        "status": "active",
        "trigger": "dm_keyword",
        "match_mode": "word",
        "action": "send_message",
        "message_text": "Hi {first_name}! Here's the link",
        "activated_at": datetime.now(UTC),
    }
    with workspace_scope(uuid.UUID(str(workspace_id))):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = Automation(
                social_account_id=uuid.UUID(str(account_id)) if account_id else None,
                **{**defaults, **values},
            )
            session.add(row)
            await session.flush()
            for keyword in keywords:
                session.add(
                    AutomationKeyword(
                        automation_id=row.id,
                        keyword=keyword,
                        keyword_normalized=normalize(keyword),
                    )
                )
            for media_item_id in media_item_ids:
                session.add(AutomationPost(automation_id=row.id, media_item_id=media_item_id))
            await session.commit()
            return row.id
