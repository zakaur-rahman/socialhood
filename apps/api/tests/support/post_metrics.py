"""T6.5 rows for tests: posts of a given format and age, an Instagram account with a real encrypted
token (for respx-mocked Graph calls), a post's snapshots at their ages, and the workspace time
zone. Written through the ORM in the workspace's scope, committed, returned as ids. Snapshot rows
themselves come from tests/support/analytics.py (make_snapshot)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.db.tenancy import workspace_scope
from socialhood.models.analytics import WINDOW_AGES, SnapshotWindow
from socialhood.models.connections import SocialAccount
from socialhood.models.media import MediaItem
from socialhood.platforms.instagram import oauth
from socialhood.security.crypto import TokenCipher
from tests.support.analytics import make_snapshot
from tests.support.api import TOKEN_KEY

IG_USER = "17841400000000001"
TOKEN = "IGQVJlong-test-token"


def cipher() -> TokenCipher:
    return TokenCipher([TOKEN_KEY])


async def make_post(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    account_id: uuid.UUID | str,
    posted_at: datetime | None = None,
    media_type: str = "image",
    platform_media_id: str | None = None,
    caption: str = "Fresh out of the oven",
    like_count: int | None = None,
    comments_count: int | None = None,
) -> uuid.UUID:
    with workspace_scope(uuid.UUID(str(workspace_id))):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = MediaItem(
                social_account_id=uuid.UUID(str(account_id)),
                platform_media_id=platform_media_id or f"1810{uuid.uuid4().int % 10**13:013d}",
                media_type=media_type,
                caption=caption,
                media_url="https://scontent.cdninstagram.com/v/post.jpg",
                permalink="https://www.instagram.com/p/abc/",
                posted_at=posted_at or datetime.now(UTC) - timedelta(days=1),
                like_count=like_count,
                comments_count=comments_count,
            )
            session.add(row)
            await session.commit()
            return row.id


async def make_instagram_account(
    engine: AsyncEngine,
    workspace_id: uuid.UUID | str,
    *,
    insights: bool = True,
    platform_account_id: str = IG_USER,
    platform: str = "instagram",
    status: str = "active",
) -> uuid.UUID:
    """A connected Instagram account whose token the test deps can decrypt; with the insights
    scope unless ``insights`` is False."""
    scopes = [*oauth.BASE_SCOPES, *([oauth.INSIGHTS_SCOPE] if insights else [])]
    with workspace_scope(uuid.UUID(str(workspace_id))):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            acct = SocialAccount(
                platform=platform,
                platform_account_id=platform_account_id,
                username="maple.bakery",
                status=status,
                access_token_enc=cipher().encrypt(TOKEN),
                scopes=scopes,
                connected_at=datetime.now(UTC),
            )
            session.add(acct)
            await session.commit()
            return acct.id


async def make_windows(
    engine: AsyncEngine,
    *,
    workspace_id: uuid.UUID | str,
    post_id: uuid.UUID | str,
    posted_at: datetime,
    windows: Mapping[str, Mapping[str, int]],
    final: bool = True,
) -> None:
    """The post's snapshots, each captured at its age (``windows``: window -> metrics)."""
    for window, metrics in windows.items():
        await make_snapshot(
            engine,
            workspace_id=workspace_id,
            media_item_id=post_id,
            window=window,
            metrics=dict(metrics),
            insights_final=final,
            captured_at=posted_at + WINDOW_AGES[SnapshotWindow(window)],
        )


async def set_timezone(engine: AsyncEngine, workspace_id: uuid.UUID | str, timezone: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET timezone = :t WHERE id = :w"),
            {"t": timezone, "w": str(workspace_id)},
        )
