"""The sandbox adapter (TR-PL-07): an Instagram-like account that lives entirely in memory, so
every inbox, automation and AI feature can be developed without Meta. Enabled only when
SANDBOX_PLATFORM_ENABLED=true; production refuses to start with it on (SEC-14)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import ContactProfile, TokenGrant
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
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
