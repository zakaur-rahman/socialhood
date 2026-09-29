"""The platform interface (TR-PL-01). Services never build Graph URLs and never branch on platform
names: they get an adapter and check its capabilities (TR-PL-11).

Methods arrive with the phase that needs them: P2 tokens, webhooks and profiles; P3 sending,
read receipts, media download, and the post and conversation lists used by sync and backfill;
P4 link buttons, private replies, public comment replies and single posts for comment intake.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

from socialhood.models.connections import SocialAccount
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.events import InboundMediaRef, InboundMessage


@dataclass(frozen=True)
class TokenGrant:
    access_token: str
    expires_at: datetime | None


@dataclass(frozen=True)
class ContactProfile:
    name: str | None
    username: str | None
    profile_picture_url: str | None


@dataclass(frozen=True, kw_only=True)
class OutboundAttachment:
    type: Literal["image", "video", "audio", "file", "sticker"]
    url: str  # a public URL the platform can fetch (our storage)
    filename: str | None = None
    mime_type: str | None = None


@dataclass(frozen=True, kw_only=True)
class OutboundTemplate:
    name: str
    language: str
    params: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class OutboundButton:
    """A link button (FR-AUT-13): Instagram's button template."""

    title: str  # up to 20 characters
    url: str  # https


@dataclass(frozen=True, kw_only=True)
class OutboundMessage:
    """One platform send: text, one attachment, a built-in sticker (Instagram's heart) or
    (WhatsApp) a template."""

    text: str | None = None
    attachment: OutboundAttachment | None = None
    template: OutboundTemplate | None = None
    sticker: Literal["like_heart"] | None = None
    buttons: tuple[OutboundButton, ...] = ()  # with text: sent as one button-template message
    human_agent: bool = False  # Instagram HUMAN_AGENT tag (TR-PL-04)


@dataclass(frozen=True)
class SendResult:
    platform_message_id: str | None


@dataclass(frozen=True)
class MediaDownload:
    content: bytes
    mime_type: str | None


@dataclass(frozen=True, kw_only=True)
class PlatformMedia:
    platform_media_id: str
    media_type: Literal["image", "video", "carousel", "reel", "story"]
    caption: str | None
    media_url: str | None
    thumbnail_url: str | None
    permalink: str | None
    posted_at: datetime
    like_count: int | None = None
    comments_count: int | None = None


@dataclass(frozen=True, kw_only=True)
class PlatformThread:
    """A conversation from the platform's history, for backfill (FR-CON-01)."""

    platform_conversation_id: str
    contact_ref: str
    contact_username: str | None
    messages: tuple[InboundMessage, ...] = field(default_factory=tuple)  # oldest first


class PlatformAdapter(Protocol):
    platform: str

    def capabilities_for(self, acct: SocialAccount) -> frozenset[Capability]: ...

    async def refresh_token(self, acct: SocialAccount) -> TokenGrant: ...

    async def subscribe_webhooks(self, acct: SocialAccount) -> None: ...

    async def fetch_contact_profile(
        self, acct: SocialAccount, platform_user_id: str
    ) -> ContactProfile | None: ...

    async def send_message(
        self, acct: SocialAccount, recipient_ref: str, message: OutboundMessage
    ) -> SendResult: ...

    async def mark_read(
        self, acct: SocialAccount, recipient_ref: str, *, message_ref: str | None = None
    ) -> None:
        """Mark the conversation seen. Instagram needs the contact (``recipient_ref``); WhatsApp
        needs the latest inbound message (``message_ref``)."""
        ...

    async def download_media(self, acct: SocialAccount, ref: InboundMediaRef) -> MediaDownload: ...

    async def list_media(self, acct: SocialAccount, *, limit: int = 25) -> list[PlatformMedia]: ...

    async def get_media(self, acct: SocialAccount, media_ref: str) -> PlatformMedia | None:
        """One of the account's posts, for a comment on a post we have not synced (F-12)."""
        ...

    async def list_threads(
        self, acct: SocialAccount, *, limit: int = 20
    ) -> list[PlatformThread]: ...

    async def private_reply(
        self, acct: SocialAccount, comment_ref: str, message: OutboundMessage
    ) -> SendResult:
        """A DM to a comment's author, addressed by the comment (Instagram: one per comment,
        within 7 days; FR-AUT-10). Text, with link buttons if any; no attachments."""
        ...

    async def reply_to_comment(
        self, acct: SocialAccount, comment_ref: str, text: str
    ) -> str | None:
        """A public reply under the comment; returns the reply's platform id."""
        ...
