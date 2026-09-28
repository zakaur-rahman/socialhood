"""Instagram adapter for connected accounts (TR-PL-01, TR-PL-11)."""

from __future__ import annotations

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import ContactProfile, TokenGrant
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram import oauth

# Fields every connected account is subscribed to (@mentions arrive inside comments).
SUBSCRIBED_FIELDS = "messages,messaging_seen,message_reactions,message_edit,comments"

CAPABILITIES = frozenset(
    {
        Capability.DM_SEND,
        Capability.DM_ATTACHMENTS,
        Capability.READ_RECEIPTS,
        Capability.HUMAN_AGENT,
        Capability.CONVERSATION_BACKFILL,
        Capability.COMMENTS,
        Capability.PRIVATE_REPLY,
        Capability.PUBLISH,
        Capability.POST_INSIGHTS,
        Capability.ACCOUNT_INSIGHTS,
    }
)


class InstagramAdapter:
    platform = "instagram"

    def __init__(self, deps: PlatformDeps) -> None:
        self.deps = deps
        self.http = PlatformHttp(deps.http, "instagram")

    def capabilities_for(self, acct: SocialAccount) -> frozenset[Capability]:
        caps = set(CAPABILITIES)
        if oauth.INSIGHTS_SCOPE not in (acct.scopes or []):
            caps -= {Capability.POST_INSIGHTS, Capability.ACCOUNT_INSIGHTS}
        if not self.deps.settings.ig_human_agent_enabled:
            caps.discard(Capability.HUMAN_AGENT)
        return frozenset(caps)

    def _token(self, acct: SocialAccount) -> str:
        if not acct.access_token_enc:
            raise PlatformError("account_needs_reconnect", message="No token stored")
        return self.deps.cipher.decrypt(acct.access_token_enc)

    def _graph(self, path: str) -> str:
        return f"{oauth.GRAPH}/{self.deps.settings.ig_graph_version}/{path}"

    async def refresh_token(self, acct: SocialAccount) -> TokenGrant:
        grant = await oauth.refresh(self.http, self._token(acct))
        return TokenGrant(grant.access_token, grant.expires_at)

    async def subscribe_webhooks(self, acct: SocialAccount) -> None:
        body = await self.http.request(
            "POST",
            self._graph("me/subscribed_apps"),
            endpoint="me.subscribed_apps",
            token=self._token(acct),
            params={"subscribed_fields": SUBSCRIBED_FIELDS},
        )
        if not (isinstance(body, dict) and body.get("success")):
            raise PlatformError(
                "platform_rejected", message="Instagram did not confirm the subscription"
            )

    async def fetch_contact_profile(
        self, acct: SocialAccount, platform_user_id: str
    ) -> ContactProfile | None:
        body = await self.http.request(
            "GET",
            self._graph(platform_user_id),
            endpoint="user_profile",
            token=self._token(acct),
            params={"fields": "name,username,profile_pic"},
        )
        if not isinstance(body, dict):
            return None
        return ContactProfile(
            name=body.get("name"),
            username=body.get("username"),
            profile_picture_url=body.get("profile_pic"),
        )
