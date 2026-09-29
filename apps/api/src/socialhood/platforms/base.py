"""The platform interface (TR-PL-01). Services never build Graph URLs and never branch on platform
names: they get an adapter and check its capabilities (TR-PL-11).

Methods arrive with the phase that needs them: P2 tokens, webhooks and profiles; P3 sending,
read receipts, media download, and the post and conversation lists used by sync and backfill;
P4 link buttons, private replies, public comment replies and single posts for comment intake;
P6 comment backfill and moderation, live counts and insights.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Literal, Protocol

from socialhood.models.connections import SocialAccount
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.events import InboundComment, InboundMediaRef, InboundMessage


@dataclass(frozen=True)
class TokenGrant:
    access_token: str
    expires_at: datetime | None


@dataclass(frozen=True)
class ContactProfile:
    name: str | None
    username: str | None
    profile_picture_url: str | None
    follows_business: bool | None = None  # Instagram's is_user_follow_business (FR-AUT-22)


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
class OutboundQuickReply:
    """A quick reply (tap first, FR-AUT-21): Instagram's quick_replies, content_type text.
    Not shown on desktop, so a typed reply must work too."""

    title: str  # up to 20 characters
    payload: str  # comes back as message.quick_reply.payload


@dataclass(frozen=True, kw_only=True)
class OutboundMessage:
    """One platform send: text, one attachment, a built-in sticker (Instagram's heart) or
    (WhatsApp) a template."""

    text: str | None = None
    attachment: OutboundAttachment | None = None
    template: OutboundTemplate | None = None
    sticker: Literal["like_heart"] | None = None
    buttons: tuple[OutboundButton, ...] = ()  # with text: sent as one button-template message
    quick_replies: tuple[OutboundQuickReply, ...] = ()  # with text, not with buttons
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


@dataclass(frozen=True, kw_only=True)
class PlatformComment(InboundComment):
    """A comment read from the platform for backfill (FR-CMT-01). It has the webhook event's
    fields, so it goes through the same intake (F-12), plus what only a read returns."""

    like_count: int = 0
    hidden: bool = False


@dataclass(frozen=True)
class CommentPage:
    """One page of a post's comments, replies included (their ``parent_id`` set)."""

    comments: tuple[PlatformComment, ...]
    next_cursor: str | None = None  # None on the last page


@dataclass(frozen=True, kw_only=True)
class MediaCounts:
    """A post's live counts (the 1 h and 6 h snapshots, FR-ANL-01; refreshing like_count and
    comments_count on media_items). None: the platform did not say."""

    like_count: int | None = None
    comments_count: int | None = None


def _known(values: dict[str, int | None]) -> dict[str, int]:
    return {name: value for name, value in values.items() if value is not None}


@dataclass(frozen=True, kw_only=True)
class MediaInsights:
    """A post's lifetime insights at the moment of the call (FR-ANL-01). Field names are the
    PostMetric keys of ``post_metric_snapshots.metrics``; None: not given for this media type or
    not available yet."""

    reach: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None
    total_interactions: int | None = None
    profile_visits: int | None = None
    follows: int | None = None

    def metrics(self) -> dict[str, int]:
        """The known values, as stored in a snapshot's ``metrics``."""
        return _known(asdict(self))


@dataclass(frozen=True, kw_only=True)
class AccountInsights:
    """One day of an account's metrics (FR-ANL-01). ``followers_count`` is read from the account
    fields and is known without the insights scope; the rest are the AccountMetric keys of
    ``account_daily_metrics.metrics`` and stay None without it."""

    followers_count: int | None = None
    reach: int | None = None
    views: int | None = None
    accounts_engaged: int | None = None
    total_interactions: int | None = None
    follows: int | None = None
    unfollows: int | None = None
    profile_links_taps: int | None = None

    def metrics(self) -> dict[str, int]:
        """The known insight values, as stored in ``account_daily_metrics.metrics``."""
        values = asdict(self)
        values.pop("followers_count")
        return _known(values)


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

    # ---- P6: comment backfill (T6.1), moderation (T6.2 auto-hide, T6.3 actions), live counts and
    # insights (T6.5). Accounts without comments or posts raise capability_unavailable.

    async def list_comments(
        self, acct: SocialAccount, media_ref: str, *, cursor: str | None = None
    ) -> CommentPage:
        """One page of a post's comments for the backfill on connect (FR-CMT-01: 25 recent posts,
        up to 200 comments each). Pass the previous page's ``next_cursor`` for the next."""
        ...

    async def hide_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        """Hide a comment on the account's post (FR-CMT-04, FR-CMT-05 auto-hide)."""
        ...

    async def unhide_comment(self, acct: SocialAccount, comment_ref: str) -> None: ...

    async def delete_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        """Delete a comment on the account's post. Already deleted counts as done."""
        ...

    async def get_media_counts(self, acct: SocialAccount, media_ref: str) -> MediaCounts | None:
        """A post's live like and comment counts; None when the post no longer exists."""
        ...

    async def get_media_insights(
        self, acct: SocialAccount, media_ref: str, *, media_type: str
    ) -> MediaInsights:
        """A post's insights now (needs Capability.POST_INSIGHTS). ``media_type`` is the stored
        MediaType: Instagram's valid metrics differ between Reels, feed posts and carousels."""
        ...

    async def get_account_insights(
        self, acct: SocialAccount, day: date, *, tz: str = "UTC"
    ) -> AccountInsights:
        """The account's followers now and its insights for ``day``, a date in the IANA time
        zone ``tz`` (the workspace's). Insights need Capability.ACCOUNT_INSIGHTS; without it only
        ``followers_count`` is filled."""
        ...
