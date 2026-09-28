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
        raise NotImplementedError("T3.6")

    async def mark_read(self, acct: SocialAccount, recipient_ref: str) -> None:
        raise NotImplementedError("T3.6")

    async def download_media(self, acct: SocialAccount, ref: InboundMediaRef) -> MediaDownload:
        raise NotImplementedError("T3.3")

    async def list_media(self, acct: SocialAccount, *, limit: int = 25) -> list[PlatformMedia]:
        raise NotImplementedError("T3.14")

    async def list_threads(self, acct: SocialAccount, *, limit: int = 20) -> list[PlatformThread]:
        raise NotImplementedError("T3.14")
