"""The platform interface (TR-PL-01). Services never build Graph URLs and never branch on platform
names: they get an adapter and check its capabilities (TR-PL-11).

Methods arrive with the phase that needs them; P2 covers tokens, webhooks and profiles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from socialhood.models.connections import SocialAccount
from socialhood.platforms.capabilities import Capability


@dataclass(frozen=True)
class TokenGrant:
    access_token: str
    expires_at: datetime | None


@dataclass(frozen=True)
class ContactProfile:
    name: str | None
    username: str | None
    profile_picture_url: str | None


class PlatformAdapter(Protocol):
    platform: str

    def capabilities_for(self, acct: SocialAccount) -> frozenset[Capability]: ...

    async def refresh_token(self, acct: SocialAccount) -> TokenGrant: ...

    async def subscribe_webhooks(self, acct: SocialAccount) -> None: ...

    async def fetch_contact_profile(
        self, acct: SocialAccount, platform_user_id: str
    ) -> ContactProfile | None: ...
