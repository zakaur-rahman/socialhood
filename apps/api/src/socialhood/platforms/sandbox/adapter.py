"""The sandbox adapter (TR-PL-07): an Instagram-like account that lives entirely in memory, so
every inbox, automation and AI feature can be developed without Meta. Enabled only when
SANDBOX_PLATFORM_ENABLED=true; production refuses to start with it on (SEC-14)."""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

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
from socialhood.platforms.facebook.adapter import CAPABILITIES as FACEBOOK_CAPABILITIES
from socialhood.platforms.instagram.adapter import CAPABILITIES
from socialhood.platforms.whatsapp.adapter import CAPABILITIES as WHATSAPP_CAPABILITIES
from socialhood.platforms.whatsapp.health import NumberHealth
from socialhood.platforms.whatsapp.templates import MessageTemplate

SANDBOX_PREFIX = "sandbox_"


def is_sandbox(acct: SocialAccount) -> bool:
    return acct.platform_account_id.startswith(SANDBOX_PREFIX)


class SandboxAdapter:
    platform = "instagram"  # a sandbox Facebook Page has acct.platform == "facebook" (GR-29)

    def __init__(self, deps: PlatformDeps) -> None:
        self.deps = deps

    def capabilities_for(self, acct: SocialAccount) -> frozenset[Capability]:
        """An Instagram-like account, a Facebook Page (GR-29) or a WhatsApp number that can send
        templates (GR-23): what the real adapters offer, with Human Agent on and without the
        settings that gate insights."""
        if acct.platform == "facebook":
            return FACEBOOK_CAPABILITIES | {Capability.HUMAN_AGENT}
        if acct.platform == "whatsapp":
            return WHATSAPP_CAPABILITIES
        return CAPABILITIES

    async def list_templates(self, acct: SocialAccount) -> list[MessageTemplate]:
        """The sandbox WhatsApp number's approved templates (platforms/sandbox/whatsapp.py)."""
        from socialhood.platforms.sandbox import whatsapp

        return whatsapp.templates()

    async def get_number_health(self, acct: SocialAccount) -> NumberHealth:
        """What ``outbox.set_number_health`` set in this process, else a rating nobody knows yet
        and the 1,000 a day tier. (Quality updates arrive as webhooks, which the worker stores.)"""
        from socialhood.platforms.sandbox import outbox

        return outbox.NUMBER_HEALTH.get(acct.platform_account_id) or NumberHealth(
            "unknown", "TIER_1K"
        )

    async def refresh_token(self, acct: SocialAccount) -> TokenGrant:
        return TokenGrant(f"sandbox-{secrets.token_hex(8)}", datetime.now(UTC) + timedelta(days=60))

    async def subscribe_webhooks(self, acct: SocialAccount) -> None:
        return None

    async def fetch_contact_profile(
        self, acct: SocialAccount, platform_user_id: str
    ) -> ContactProfile | None:
        """A made-up name; the follow status comes from ``sandbox.outbox.follows``."""
        from socialhood.platforms.sandbox import outbox

        short = platform_user_id[-4:]
        return ContactProfile(
            name=f"Sandbox customer {short}",
            username=f"customer_{short}",
            profile_picture_url=None,
            follows_business=outbox.follows(platform_user_id),
        )

    # ---- P3 (filled by T3.6/T3.7 for sending, T3.3/T3.14 for media, sync and backfill)

    async def send_message(
        self, acct: SocialAccount, recipient_ref: str, message: OutboundMessage
    ) -> SendResult:
        """A fake mid, or an injected failure (see ``sandbox.outbox``)."""
        from socialhood.platforms.sandbox import outbox

        failure = outbox.quick_reply_failure(message) or outbox.failure_for(message, "send")
        if failure is not None:
            raise failure
        return SendResult(outbox.record(acct.platform_account_id, recipient_ref, message))

    async def mark_read(
        self, acct: SocialAccount, recipient_ref: str, *, message_ref: str | None = None
    ) -> None:
        from socialhood.platforms.sandbox import outbox

        outbox.SEEN.append((acct.platform_account_id, recipient_ref))

    async def download_media(self, acct: SocialAccount, ref: InboundMediaRef) -> MediaDownload:
        from socialhood.platforms.sandbox import history

        return history.image()

    async def list_media(self, acct: SocialAccount, *, limit: int = 25) -> list[PlatformMedia]:
        from socialhood.platforms.sandbox import history

        return history.posts(acct, limit=limit)

    async def list_stories(self, acct: SocialAccount) -> list[PlatformMedia]:
        from socialhood.platforms.sandbox import history

        return history.stories(acct)

    async def get_media(self, acct: SocialAccount, media_ref: str) -> PlatformMedia | None:
        from socialhood.platforms.sandbox import history

        return history.post(acct, media_ref)

    async def set_ice_breakers(
        self, acct: SocialAccount, starters: Sequence[IceBreaker]
    ) -> list[IceBreaker]:
        """Keeps what was set, per account, and returns it (``outbox.ICE_BREAKERS``). A question
        with ``[sandbox:fail=<code>]`` fails with that code, to show a sync error."""
        from socialhood.platforms.sandbox import outbox

        for starter in starters:
            failure = outbox.failure_for_text(starter.question, "ice_breakers")
            if failure is not None:
                raise failure
        outbox.ICE_BREAKERS[acct.platform_account_id] = list(starters)
        return list(starters)

    async def list_threads(self, acct: SocialAccount, *, limit: int = 20) -> list[PlatformThread]:
        from socialhood.platforms.sandbox import history

        return history.threads(acct, limit=limit)

    # ---- P4 (T4.4): fake ids, recorded like sends, failures injectable (``sandbox.outbox``)

    async def private_reply(
        self, acct: SocialAccount, comment_ref: str, message: OutboundMessage
    ) -> SendResult:
        from socialhood.platforms.sandbox import outbox

        if message.attachment is not None or message.sticker or message.template:
            raise PlatformError(
                "platform_rejected", message="A private reply can only carry text and link buttons"
            )
        failure = outbox.quick_reply_failure(message) or outbox.failure_for(
            message, "private_reply"
        )
        if failure is not None:
            raise failure
        return SendResult(
            outbox.record_private_reply(acct.platform_account_id, comment_ref, message)
        )

    async def reply_to_comment(
        self, acct: SocialAccount, comment_ref: str, text: str
    ) -> str | None:
        from socialhood.platforms.sandbox import outbox

        failure = outbox.failure_for_text(text, "comment_reply")
        if failure is not None:
            raise failure
        return outbox.record_comment_reply(acct.platform_account_id, comment_ref, text)

    # ---- P6: comment backfill (T6.1, comments.py), moderation (T6.3, moderation.py), live counts
    # and insights (T6.5, insights.py)

    async def list_comments(
        self, acct: SocialAccount, media_ref: str, *, cursor: str | None = None
    ) -> CommentPage:
        from socialhood.platforms.sandbox import comments

        return comments.page(acct, media_ref, cursor=cursor)

    async def hide_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        from socialhood.platforms.sandbox import moderation

        moderation.set_hidden(acct, comment_ref, hidden=True)

    async def unhide_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        from socialhood.platforms.sandbox import moderation

        moderation.set_hidden(acct, comment_ref, hidden=False)

    async def delete_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        from socialhood.platforms.sandbox import moderation

        moderation.delete(acct, comment_ref)

    async def get_media_counts(self, acct: SocialAccount, media_ref: str) -> MediaCounts | None:
        from socialhood.platforms.sandbox import insights

        return insights.media_counts(acct, media_ref)

    async def get_media_insights(
        self, acct: SocialAccount, media_ref: str, *, media_type: str
    ) -> MediaInsights:
        from socialhood.platforms.sandbox import insights

        return insights.media_insights(acct, media_ref, media_type=media_type)

    async def get_account_insights(
        self, acct: SocialAccount, day: date, *, tz: str = "UTC"
    ) -> AccountInsights:
        from socialhood.platforms.sandbox import insights

        return insights.account_insights(acct, day, tz=tz)

    # ---- P7: publishing (T7.2, publishing.py)

    async def get_publishing_quota(self, acct: SocialAccount) -> PublishingQuota:
        from socialhood.platforms.sandbox import publishing

        return publishing.publishing_quota(acct)

    async def create_image_container(
        self, acct: SocialAccount, *, image_url: str, caption: str
    ) -> str:
        from socialhood.platforms.sandbox import publishing

        return publishing.create_image_container(acct, image_url=image_url, caption=caption)

    async def create_reel_container(
        self, acct: SocialAccount, *, video_url: str, caption: str, share_to_feed: bool = True
    ) -> str:
        from socialhood.platforms.sandbox import publishing

        return publishing.create_reel_container(
            acct, video_url=video_url, caption=caption, share_to_feed=share_to_feed
        )

    async def create_carousel_item(self, acct: SocialAccount, media: ContainerMedia) -> str:
        from socialhood.platforms.sandbox import publishing

        return publishing.create_carousel_item(acct, media)

    async def create_carousel_container(
        self, acct: SocialAccount, *, children: Sequence[str], caption: str
    ) -> str:
        from socialhood.platforms.sandbox import publishing

        return publishing.create_carousel_container(acct, children=children, caption=caption)

    async def get_container_status(
        self, acct: SocialAccount, container_ref: str
    ) -> ContainerStatus:
        from socialhood.platforms.sandbox import publishing

        return publishing.container_status(acct, container_ref)

    async def publish_container(self, acct: SocialAccount, container_ref: str) -> str:
        from socialhood.platforms.sandbox import publishing

        return publishing.publish_container(acct, container_ref)

    async def get_published_media(
        self, acct: SocialAccount, media_ref: str
    ) -> PlatformMedia | None:
        from socialhood.platforms.sandbox import publishing

        return publishing.published_media(acct, media_ref)

    async def find_published_media(
        self,
        acct: SocialAccount,
        container_ref: str,
        *,
        caption: str,
        published_after: datetime,
    ) -> PlatformMedia | None:
        from socialhood.platforms.sandbox import publishing

        return publishing.find_published_media(
            acct, container_ref, caption=caption, published_after=published_after
        )

    async def post_comment(self, acct: SocialAccount, media_ref: str, text: str) -> str | None:
        from socialhood.platforms.sandbox import publishing

        return publishing.post_comment(acct, media_ref, text)
