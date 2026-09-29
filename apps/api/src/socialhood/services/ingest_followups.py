"""Follow-ups of an ingested message (T3.3; TR-PL-06, TR-MED-03): the contact's profile and a
copy of each inbound attachment in our storage.

Both read what they need, call out without holding a database connection, then write in a short
transaction and publish after commit. Retryable platform errors propagate so the job retries
(TR-JOB-04); anything else is logged and dropped, since the message itself is already stored.

The profile also says whether the person follows the account (``is_user_follow_business``,
FR-AUT-22): it is cached with the rest (24 h) and kept on the contact with the time it was read
(``follows_business``, ``follows_checked_at``). ``follow_status`` reads it fresh, bypassing the
cache, for the automation runtime (tap first and the follow nudge, FR-AUT-21, FR-AUT-22).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.db.tenancy import workspace_scope
from socialhood.media.cloudinary import Cloudinary, CloudinaryError, in_workspace, workspace_folder
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.media import AssetPurpose, MediaAsset, ResourceType
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import ContactProfile
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.events import InboundMediaRef
from socialhood.platforms.registry import adapter_for
from socialhood.realtime.events import commit_and_publish, queue_conversation, queue_message
from socialhood.repositories import inbox
from socialhood.repositories import ingest as rows
from socialhood.repositories import social_accounts as accounts
from socialhood.services.ingest import COPYABLE

log = get_logger(__name__)

PROFILE_CACHE_TTL_S = 24 * 3600  # TR-PL-06
RESOURCE_TYPES = frozenset(ResourceType)


def profile_cache_key(social_account_id: uuid.UUID, platform_user_id: str) -> str:
    """Disconnecting an account deletes ``profile:{account_id}:*`` (services/connections.py)."""
    return f"profile:{social_account_id}:{platform_user_id}"


def _live(acct: SocialAccount | None) -> SocialAccount | None:
    return acct if acct is not None and acct.status != AccountStatus.DISCONNECTED else None


# ---------------------------------------------------------------- contact profiles


async def refresh_contact_profile(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
    now: datetime | None = None,
) -> bool:
    """Fill the contact's name, username, picture and follow status (from the 24 h cache when
    there); True when the contact was updated."""
    now = now or datetime.now(UTC)
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            contact = await inbox.get_contact(session, contact_id)
            acct = (
                _live(await accounts.get(session, contact.social_account_id)) if contact else None
            )
        if contact is None or acct is None:
            return False
        read = await _cached(redis, acct, contact.platform_user_id)
        if read is None:
            read = await _fetch(redis, deps, acct, contact.platform_user_id, now=now)
        await _store(sessionmaker, redis, contact_id, read, now=now)
    return True


async def follow_status(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    contact_id: uuid.UUID,
    now: datetime | None = None,
) -> bool | None:
    """Whether the contact follows the account now (FR-AUT-22), read fresh from the platform:
    the cache is bypassed, then refreshed, and the contact's name, picture and follow status are
    updated. None when the profile is refused, unavailable or silent on it. Never raises for a
    platform error: nothing an automation sends waits on this. Runs in the workspace's scope."""
    now = now or datetime.now(UTC)
    async with sessionmaker() as session:
        contact = await inbox.get_contact(session, contact_id)
        acct = _live(await accounts.get(session, contact.social_account_id)) if contact else None
    if contact is None or acct is None:
        return None
    try:
        read = await _fetch(redis, deps, acct, contact.platform_user_id, now=now)
    except PlatformError as error:  # a temporary error: unknown this time, nothing stored
        log.warning(
            "follow_status_unavailable",
            account_id=str(acct.id),
            error_code=error.code,
            platform_code=error.platform_code,
        )
        return None
    await _store(sessionmaker, redis, contact_id, read, now=now)
    return read.profile.follows_business if read.profile is not None else None


@dataclass(frozen=True)
class _Read:
    profile: ContactProfile | None  # None: refused
    fetched_at: datetime | None  # when the platform said it (a cached read is older)


async def _store(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    contact_id: uuid.UUID,
    read: _Read,
    *,
    now: datetime,
) -> None:
    async with sessionmaker() as session:
        contact = await inbox.get_contact(session, contact_id)
        if contact is None:
            return
        profile = read.profile
        if profile is not None:
            contact.display_name = profile.name or contact.display_name
            contact.username = profile.username or contact.username
            contact.profile_picture_url = profile.profile_picture_url or contact.profile_picture_url
            if profile.follows_business is not None:
                contact.follows_business = profile.follows_business
                contact.follows_checked_at = read.fetched_at or contact.follows_checked_at
        # Also after a refusal, so the next message does not ask again for a week.
        contact.profile_fetched_at = now
        await session.flush()
        for conv in await rows.conversations_for_contact(session, contact.id):
            await queue_conversation(session, conv, now=now, contact=contact)
        await commit_and_publish(session, redis)


async def _cached(redis: Redis, acct: SocialAccount, platform_user_id: str) -> _Read | None:
    try:
        cached = await redis.get(profile_cache_key(acct.id, platform_user_id))
    except Exception:  # a cache is never worth failing over
        cached = None
    if not cached:
        return None
    data: dict[str, Any] = json.loads(cached)
    follows = data.get("follows_business")
    fetched_at = data.get("fetched_at")
    return _Read(
        ContactProfile(
            name=data.get("name"),
            username=data.get("username"),
            profile_picture_url=data.get("profile_picture_url"),
            follows_business=follows if isinstance(follows, bool) else None,
        ),
        datetime.fromisoformat(fetched_at) if isinstance(fetched_at, str) else None,
    )


async def _fetch(
    redis: Redis, deps: PlatformDeps, acct: SocialAccount, platform_user_id: str, *, now: datetime
) -> _Read:
    """The profile from the platform, cached for a day. A refusal is a read without a profile;
    retryable errors propagate."""
    try:
        profile = await adapter_for(acct, deps).fetch_contact_profile(acct, platform_user_id)
    except PlatformError as error:
        if error.retryable:
            raise
        log.warning(
            "contact_profile_unavailable",
            account_id=str(acct.id),
            error_code=error.code,
            platform_code=error.platform_code,
        )
        return _Read(None, now)
    if profile is not None:
        cached = {**asdict(profile), "fetched_at": now.isoformat()}
        try:
            await redis.set(
                profile_cache_key(acct.id, platform_user_id),
                json.dumps(cached),
                ex=PROFILE_CACHE_TTL_S,
            )
        except Exception:
            log.warning("contact_profile_cache_failed", account_id=str(acct.id))
    return _Read(profile, now)


# ---------------------------------------------------------------- inbound media (TR-MED-03)


def _find(attachments: list[dict[str, Any]], attachment_id: str) -> int | None:
    return next((i for i, a in enumerate(attachments) if a.get("id") == attachment_id), None)


async def copy_inbound_media(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    message_id: uuid.UUID,
    attachment_id: str,
    now: datetime | None = None,
) -> bool:
    """Download one attachment through the adapter, store it under ws/{workspace}/inbound/, and
    point the attachment at the stored copy (the platform URL stays under ``platform_url``).
    True when the attachment now uses our storage."""
    now = now or datetime.now(UTC)
    storage = Cloudinary(deps.http, deps.settings)
    if not storage.configured:
        log.info(
            "inbound_media_skipped", reason="storage not configured", message_id=str(message_id)
        )
        return False
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            msg = await inbox.get_message(session, message_id)
            index = _find(msg.attachments, attachment_id) if msg else None
            acct = _live(await accounts.get(session, msg.social_account_id)) if msg else None
        if msg is None or index is None or acct is None:
            return False
        attachment = msg.attachments[index]
        if attachment.get("asset_id") or attachment.get("type") not in COPYABLE:
            return False
        ref = InboundMediaRef(
            kind=attachment["type"],
            url=attachment.get("platform_url"),
            media_id=attachment.get("media_id"),
        )
        try:
            download = await adapter_for(acct, deps).download_media(acct, ref)
        except PlatformError as error:
            if error.retryable:
                raise
            log.warning(
                "inbound_media_unavailable", message_id=str(message_id), error_code=error.code
            )
            return False
        folder = f"{workspace_folder(workspace_id, AssetPurpose.INBOUND)}/{now:%Y}/{now:%m}"
        try:
            stored = await storage.upload(
                download.content, folder=folder, public_id=attachment_id, filename=attachment_id
            )
        except httpx.HTTPError as error:
            raise PlatformError(
                "platform_unavailable", message="Storage did not respond"
            ) from error
        except CloudinaryError as error:
            log.warning("inbound_media_store_failed", message_id=str(message_id), error=str(error))
            return False
        if not in_workspace(stored.public_id, workspace_id) or stored.resource_type not in (
            RESOURCE_TYPES
        ):
            log.warning("inbound_media_unexpected_asset", message_id=str(message_id))
            return False

        async with sessionmaker() as session:
            msg = await rows.lock_message(session, message_id)
            index = _find(msg.attachments, attachment_id) if msg else None
            if msg is None or index is None or msg.attachments[index].get("asset_id"):
                return False
            asset = MediaAsset(
                public_id=stored.public_id,
                resource_type=stored.resource_type,
                purpose=AssetPurpose.INBOUND,
                format=stored.format,
                secure_url=stored.secure_url,
                bytes=stored.bytes,
                width=stored.width,
                height=stored.height,
                duration_s=stored.duration_s,
            )
            session.add(asset)
            await session.flush()
            copied = {
                "url": stored.secure_url,
                "asset_id": str(asset.id),
                "mime_type": download.mime_type,
                "size_bytes": stored.bytes,
                "width": stored.width,
                "height": stored.height,
                "duration_s": stored.duration_s,
            }
            updated = list(msg.attachments)
            updated[index] = {
                **updated[index],
                **{k: v for k, v in copied.items() if v is not None},
            }
            msg.attachments = updated
            await session.flush()
            queue_message(session, msg, created=False)
            await commit_and_publish(session, redis)
    return True


async def delete_unsent_media(
    sessionmaker: async_sessionmaker[AsyncSession],
    deps: PlatformDeps,
    *,
    workspace_id: uuid.UUID,
    asset_ids: list[uuid.UUID],
) -> int:
    """Q-021: delete our stored copies of an unsent message's media (storage, then the row).
    Returns how many were deleted; a storage failure leaves that asset for a retry."""
    storage = Cloudinary(deps.http, deps.settings)
    deleted = 0
    with workspace_scope(workspace_id):
        async with sessionmaker() as session:
            for asset in await rows.assets_by_id(session, asset_ids):
                if storage.configured and in_workspace(asset.public_id, workspace_id):
                    await storage.destroy(asset.public_id, asset.resource_type)  # type: ignore[arg-type]
                await rows.delete_asset(session, asset.id)
                await session.commit()
                deleted += 1
    return deleted
