"""The sandbox adapter (TR-PL-07): an Instagram-like account that lives entirely in memory, so
every inbox, automation and AI feature can be developed without Meta. Enabled only when
SANDBOX_PLATFORM_ENABLED=true; production refuses to start with it on (SEC-14)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import (
    ContactProfile,
    MediaDownload,
    OutboundMessage,
    PlatformMedia,
    PlatformThread,
    SendResult,
    TokenGrant,
)
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.events import InboundMediaRef
from socialhood.platforms.instagram.adapter import CAPABILITIES

SANDBOX_PREFIX = "sandbox_"


def is_sandbox(acct: SocialAccount) -> bool:
    return acct.platform_account_id.startswith(SANDBOX_PREFIX)


class SandboxAdapter:
    platform = "instagram"

    def __init__(self, deps: PlatformDeps) -> None:
        self.deps = deps

    def capabilities_for(self, acct: SocialAccount) -> frozenset[Capability]:
        return CAPABILITIES

    async def refresh_token(self, acct: SocialAccount) -> TokenGrant:
        return TokenGrant(f"sandbox-{secrets.token_hex(8)}", datetime.now(UTC) + timedelta(days=60))

    async def subscribe_webhooks(self, acct: SocialAccount) -> None:
        return None

    async def fetch_contact_profile(
        self, acct: SocialAccount, platform_user_id: str
    ) -> ContactProfile | None:
        short = platform_user_id[-4:]
        return ContactProfile(
            name=f"Sandbox customer {short}", username=f"customer_{short}", profile_picture_url=None
        )

    # ---- P3 (filled by T3.6/T3.7 for sending, T3.3/T3.14 for media, sync and backfill)

    async def send_message(
        self, acct: SocialAccount, recipient_ref: str, message: OutboundMessage
    ) -> SendResult:
        """A fake mid, or an injected failure (see ``sandbox.outbox``)."""
        from socialhood.platforms.sandbox import outbox

        failure = outbox.failure_for(message, "send")
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

    async def get_media(self, acct: SocialAccount, media_ref: str) -> PlatformMedia | None:
        from socialhood.platforms.sandbox import history

        return history.post(acct, media_ref)

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
        failure = outbox.failure_for(message, "private_reply")
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
