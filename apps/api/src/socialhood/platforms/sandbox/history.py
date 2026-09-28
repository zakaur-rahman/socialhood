"""What a sandbox account "already has" on connect (TR-PL-07, FR-CON-01): a few posts, a few
conversations with replies sent from the Instagram app, and a tiny image for inbound media.

Ids are derived from the account, so syncing or backfilling again updates rather than duplicates.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Literal

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import MediaDownload, PlatformMedia, PlatformThread
from socialhood.platforms.events import InboundMessage

# A 1x1 PNG: enough for the storage copy to have something real to upload.
PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

POSTS: tuple[tuple[Literal["image", "carousel", "reel"], str], ...] = (
    ("image", "New autumn collection is in. Which colour is your favourite?"),
    ("carousel", "Behind the scenes at the studio this week"),
    ("reel", "How we pack every order"),
)

# Each thread alternates customer, business (sent from the Instagram app), customer, ...
THREADS = (
    ("Do you have the linen shirt in medium?", "Yes! Want me to hold one for you?", "Please do"),
    ("What time do you open on Sunday?",),
    ("Loved my order, thank you!", "So glad to hear that!"),
)


def image() -> MediaDownload:
    return MediaDownload(content=PIXEL_PNG, mime_type="image/png")


def posts(acct: SocialAccount, *, limit: int, now: datetime | None = None) -> list[PlatformMedia]:
    now = now or datetime.now(UTC)
    ref = acct.platform_account_id
    items: list[PlatformMedia] = []
    for i, (media_type, caption) in enumerate(POSTS[:limit]):
        items.append(
            PlatformMedia(
                platform_media_id=f"{ref}_post_{i}",
                media_type=media_type,
                caption=caption,
                media_url=f"https://picsum.photos/seed/{ref}{i}/1080/1080",
                thumbnail_url=None,
                permalink=f"https://www.instagram.com/p/{ref}{i}/",
                posted_at=now - timedelta(days=2 * i + 1),
                like_count=40 - 10 * i,
                comments_count=3 - i,
            )
        )
    return items


def threads(
    acct: SocialAccount, *, limit: int, now: datetime | None = None
) -> list[PlatformThread]:
    now = now or datetime.now(UTC)
    ref = acct.platform_account_id
    result: list[PlatformThread] = []
    for i, lines in enumerate(THREADS[:limit]):
        contact = f"sandbox_user_{ref[-6:]}{i}"
        started = now - timedelta(days=i + 1)
        messages = tuple(
            InboundMessage(
                account_ref=ref,
                occurred_at=started + timedelta(minutes=5 * j),
                contact_ref=contact,
                contact_name=None,
                platform_message_id=f"sandbox_backfill_{ref}_{i}_{j}",
                kind="text",
                text=line,
                is_echo=j % 2 == 1,
            )
            for j, line in enumerate(lines)
        )
        result.append(
            PlatformThread(
                platform_conversation_id=f"sandbox_conversation_{ref}_{i}",
                contact_ref=contact,
                contact_username=f"customer_{contact[-4:]}",
                messages=messages,
            )
        )
    return result
