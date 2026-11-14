"""YouTube channel adapter (TR-PL-01, TR-PL-11; C-195).

A connected channel publishes; it has no DMs and (for now) no comments. The stored credential is a
Google refresh token with no expiry (``token_expires_at`` NULL), so ``refresh_token`` has nothing to
do: ``access_token`` mints a short-lived access token for each use instead. Publishing arrives in
the next step (platforms/youtube/publishing.py); until then its methods say so.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import (
    AccountInsights,
    CollaboratorStatus,
    CommentPage,
    ContactProfile,
    ContainerMedia,
    ContainerStatus,
    IceBreaker,
    MediaCounts,
    MediaDownload,
    MediaInsights,
    OutboundMessage,
    PlatformMedia,
    PlatformThread,
    PublishExtras,
    PublishingQuota,
    SendResult,
    TokenGrant,
)
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.events import InboundMediaRef
from socialhood.platforms.youtube.oauth import SCOPE, youtube_for

CAPABILITIES = frozenset({Capability.PUBLISH, Capability.POST_INSIGHTS})
NO_MESSAGES = "YouTube channels have no direct messages"
NO_COMMENTS = "YouTube comments aren't supported yet"
NEXT_STEP = "YouTube publishing arrives in the next step"


def _unavailable(message: str) -> PlatformError:
    return PlatformError("capability_unavailable", message=message)


class YouTubeAdapter:
    platform = "youtube"

    def __init__(self, deps: PlatformDeps) -> None:
        self.deps = deps

    def capabilities_for(self, acct: SocialAccount) -> frozenset[Capability]:
        return CAPABILITIES if SCOPE in (acct.scopes or []) else frozenset()

    async def access_token(self, acct: SocialAccount) -> str:
        """A short-lived access token minted from the stored refresh token. Google's
        ``invalid_grant`` (access removed, password changed) is ``account_needs_reconnect``."""
        if acct.access_token_enc is None:
            raise PlatformError("account_needs_reconnect", message="The channel is disconnected")
        refresh = self.deps.cipher.decrypt(acct.access_token_enc)
        return await youtube_for(self.deps).access_token(refresh)

    async def refresh_token(self, acct: SocialAccount) -> TokenGrant:
        """Nothing to refresh: the stored refresh token does not expire."""
        if acct.access_token_enc is None:
            raise PlatformError("account_needs_reconnect", message="The channel is disconnected")
        return TokenGrant(self.deps.cipher.decrypt(acct.access_token_enc), None)

    async def subscribe_webhooks(self, acct: SocialAccount) -> None:
        return None  # no webhooks for a channel

    async def fetch_contact_profile(
        self, acct: SocialAccount, platform_user_id: str
    ) -> ContactProfile | None:
        return None

    async def send_message(
        self, acct: SocialAccount, recipient_ref: str, message: OutboundMessage
    ) -> SendResult:
        raise _unavailable(NO_MESSAGES)

    async def mark_read(
        self, acct: SocialAccount, recipient_ref: str, *, message_ref: str | None = None
    ) -> None:
        raise _unavailable(NO_MESSAGES)

    async def download_media(self, acct: SocialAccount, ref: InboundMediaRef) -> MediaDownload:
        raise _unavailable(NO_MESSAGES)

    async def list_media(self, acct: SocialAccount, *, limit: int = 25) -> list[PlatformMedia]:
        return []

    async def list_stories(self, acct: SocialAccount) -> list[PlatformMedia]:
        return []

    async def get_media(self, acct: SocialAccount, media_ref: str) -> PlatformMedia | None:
        return None

    async def set_ice_breakers(
        self, acct: SocialAccount, starters: Sequence[IceBreaker]
    ) -> list[IceBreaker]:
        raise _unavailable(NO_MESSAGES)

    async def list_threads(self, acct: SocialAccount, *, limit: int = 20) -> list[PlatformThread]:
        raise _unavailable(NO_MESSAGES)

    async def private_reply(
        self, acct: SocialAccount, comment_ref: str, message: OutboundMessage
    ) -> SendResult:
        raise _unavailable(NO_COMMENTS)

    async def reply_to_comment(
        self, acct: SocialAccount, comment_ref: str, text: str
    ) -> str | None:
        raise _unavailable(NO_COMMENTS)

    async def list_comments(
        self, acct: SocialAccount, media_ref: str, *, cursor: str | None = None
    ) -> CommentPage:
        raise _unavailable(NO_COMMENTS)

    async def hide_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        raise _unavailable(NO_COMMENTS)

    async def unhide_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        raise _unavailable(NO_COMMENTS)

    async def delete_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        raise _unavailable(NO_COMMENTS)

    async def get_media_counts(self, acct: SocialAccount, media_ref: str) -> MediaCounts | None:
        return None

    async def get_media_insights(
        self, acct: SocialAccount, media_ref: str, *, media_type: str
    ) -> MediaInsights:
        return MediaInsights()

    async def get_account_insights(
        self, acct: SocialAccount, day: date, *, tz: str = "UTC"
    ) -> AccountInsights:
        return AccountInsights()

    # ---- publishing: Phase 2 (platforms/youtube/publishing.py)

    async def get_publishing_quota(self, acct: SocialAccount) -> PublishingQuota:
        raise _unavailable(NEXT_STEP)

    async def create_image_container(
        self,
        acct: SocialAccount,
        *,
        image_url: str,
        caption: str,
        extras: PublishExtras | None = None,
    ) -> str:
        raise _unavailable(NEXT_STEP)

    async def create_reel_container(
        self,
        acct: SocialAccount,
        *,
        video_url: str,
        caption: str,
        share_to_feed: bool = True,
        page_reel: bool = False,
        extras: PublishExtras | None = None,
    ) -> str:
        raise _unavailable(NEXT_STEP)

    async def create_story_container(self, acct: SocialAccount, media: ContainerMedia) -> str:
        raise _unavailable(NEXT_STEP)

    async def create_carousel_item(self, acct: SocialAccount, media: ContainerMedia) -> str:
        raise _unavailable(NEXT_STEP)

    async def create_carousel_container(
        self,
        acct: SocialAccount,
        *,
        children: Sequence[str],
        caption: str,
        extras: PublishExtras | None = None,
    ) -> str:
        raise _unavailable(NEXT_STEP)

    async def list_collaborators(
        self, acct: SocialAccount, media_ref: str
    ) -> list[CollaboratorStatus]:
        return []

    async def get_container_status(
        self, acct: SocialAccount, container_ref: str
    ) -> ContainerStatus:
        raise _unavailable(NEXT_STEP)

    async def create_text_container(self, acct: SocialAccount) -> str:
        raise _unavailable(NEXT_STEP)

    async def publish_container(
        self, acct: SocialAccount, container_ref: str, *, caption: str = ""
    ) -> str:
        raise _unavailable(NEXT_STEP)

    async def get_published_media(
        self, acct: SocialAccount, media_ref: str, *, story: bool = False
    ) -> PlatformMedia | None:
        raise _unavailable(NEXT_STEP)

    async def find_published_media(
        self,
        acct: SocialAccount,
        container_ref: str,
        *,
        caption: str,
        published_after: datetime,
        story: bool = False,
    ) -> PlatformMedia | None:
        raise _unavailable(NEXT_STEP)

    async def post_comment(self, acct: SocialAccount, media_ref: str, text: str) -> str | None:
        raise _unavailable(NO_COMMENTS)
