"""Website chat adapter (TR-PL-01, TR-PL-11; GR-28).

The account is a workspace's widget: ``platform_account_id`` is its public widget id and a contact
is one visitor. Nothing is sent to a platform: a reply is stored as a sent message and the widget
picks it up on its next poll (services/widget/chat.py), so ``send_message`` only mints an id. The
window never closes (services/reply_window.py), there are no tokens, webhooks, posts or comments,
and a visitor has no profile to fetch.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import (
    AccountInsights,
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
    PublishingQuota,
    SendResult,
    TokenGrant,
)
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.events import InboundMediaRef

CAPABILITIES = frozenset({Capability.DM_SEND})  # text only; no read receipts or attachments yet
NO_POSTS = "The website chat has no posts"
NO_COMMENTS = "The website chat has no comments"


def _unavailable(message: str) -> PlatformError:
    return PlatformError("capability_unavailable", message=message)


class WebAdapter:
    platform = "web"

    def __init__(self, deps: PlatformDeps) -> None:
        self.deps = deps

    def capabilities_for(self, acct: SocialAccount) -> frozenset[Capability]:
        return CAPABILITIES

    async def refresh_token(self, acct: SocialAccount) -> TokenGrant:
        raise _unavailable("The website chat has no token")

    async def subscribe_webhooks(self, acct: SocialAccount) -> None:
        return None  # visitors reach us through the widget API, not a webhook

    async def fetch_contact_profile(
        self, acct: SocialAccount, platform_user_id: str
    ) -> ContactProfile | None:
        return None  # a visitor is anonymous until they give an email

    async def send_message(
        self, acct: SocialAccount, recipient_ref: str, message: OutboundMessage
    ) -> SendResult:
        """The reply is already in the conversation; the widget reads it from there. A made-up id
        keeps the (account, message id) key unique like any platform's."""
        if message.text is None or message.attachment or message.template or message.sticker:
            raise PlatformError("platform_rejected", message="The website chat takes text only")
        return SendResult(f"web_{uuid.uuid4().hex}")

    async def mark_read(
        self, acct: SocialAccount, recipient_ref: str, *, message_ref: str | None = None
    ) -> None:
        return None  # the widget does not show read receipts

    async def download_media(self, acct: SocialAccount, ref: InboundMediaRef) -> MediaDownload:
        raise _unavailable("The website chat takes text only")

    async def list_media(self, acct: SocialAccount, *, limit: int = 25) -> list[PlatformMedia]:
        return []

    async def list_stories(self, acct: SocialAccount) -> list[PlatformMedia]:
        return []

    async def get_media(self, acct: SocialAccount, media_ref: str) -> PlatformMedia | None:
        return None

    async def set_ice_breakers(
        self, acct: SocialAccount, starters: Sequence[IceBreaker]
    ) -> list[IceBreaker]:
        raise _unavailable("The website chat has no conversation starters")

    async def list_threads(self, acct: SocialAccount, *, limit: int = 20) -> list[PlatformThread]:
        return []  # nothing to backfill: conversations start in the widget

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
        raise _unavailable(NO_POSTS)

    async def get_media_insights(
        self, acct: SocialAccount, media_ref: str, *, media_type: str
    ) -> MediaInsights:
        raise _unavailable(NO_POSTS)

    async def get_account_insights(
        self, acct: SocialAccount, day: date, *, tz: str = "UTC"
    ) -> AccountInsights:
        raise _unavailable("The website chat has no account insights")

    async def get_publishing_quota(self, acct: SocialAccount) -> PublishingQuota:
        raise _unavailable(NO_POSTS)

    async def create_image_container(
        self, acct: SocialAccount, *, image_url: str, caption: str
    ) -> str:
        raise _unavailable(NO_POSTS)

    async def create_reel_container(
        self, acct: SocialAccount, *, video_url: str, caption: str, share_to_feed: bool = True
    ) -> str:
        raise _unavailable(NO_POSTS)

    async def create_carousel_item(self, acct: SocialAccount, media: ContainerMedia) -> str:
        raise _unavailable(NO_POSTS)

    async def create_carousel_container(
        self, acct: SocialAccount, *, children: Sequence[str], caption: str
    ) -> str:
        raise _unavailable(NO_POSTS)

    async def get_container_status(
        self, acct: SocialAccount, container_ref: str
    ) -> ContainerStatus:
        raise _unavailable(NO_POSTS)

    async def publish_container(self, acct: SocialAccount, container_ref: str) -> str:
        raise _unavailable(NO_POSTS)

    async def get_published_media(
        self, acct: SocialAccount, media_ref: str
    ) -> PlatformMedia | None:
        raise _unavailable(NO_POSTS)

    async def find_published_media(
        self,
        acct: SocialAccount,
        container_ref: str,
        *,
        caption: str,
        published_after: datetime,
    ) -> PlatformMedia | None:
        raise _unavailable(NO_POSTS)

    async def post_comment(self, acct: SocialAccount, media_ref: str, text: str) -> str | None:
        raise _unavailable(NO_COMMENTS)
