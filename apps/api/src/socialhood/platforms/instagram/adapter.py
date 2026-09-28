"""Instagram adapter for connected accounts (TR-PL-01, TR-PL-11)."""

from __future__ import annotations

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
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram import oauth

# Attachment types the Send API takes by URL; the only sticker is the built-in heart.
INSTAGRAM_SENDABLE = frozenset({"image", "video", "audio", "file"})

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

    # ---- P3 (filled by T3.6/T3.7 for sending, T3.3/T3.14 for media, sync and backfill)

    async def send_message(
        self, acct: SocialAccount, recipient_ref: str, message: OutboundMessage
    ) -> SendResult:
        """One Send API call: text, one attachment by URL (image, video, audio or PDF file),
        or the heart sticker (Instagram has no templates).

        Human Agent replies carry ``messaging_type: MESSAGE_TAG`` and ``tag: HUMAN_AGENT``
        (TR-PL-04). A failure after the request went out is ``delivery_unknown`` (TR-JOB-05).
        """
        from socialhood.platforms.outcome import for_write

        content: dict[str, object]
        if message.sticker == "like_heart":
            content = {"attachment": {"type": "like_heart"}}
        elif message.attachment is not None:
            if message.attachment.type not in INSTAGRAM_SENDABLE:
                raise PlatformError(
                    "platform_rejected", message="Instagram can only send its heart sticker"
                )
            content = {
                "attachment": {
                    "type": message.attachment.type,
                    "payload": {"url": message.attachment.url},
                }
            }
        elif message.text:
            content = {"text": message.text}
        else:
            raise PlatformError(
                "platform_rejected", message="Instagram messages need text or one attachment"
            )
        payload: dict[str, object] = {"recipient": {"id": recipient_ref}, "message": content}
        if message.human_agent:
            payload["messaging_type"] = "MESSAGE_TAG"
            payload["tag"] = "HUMAN_AGENT"
        try:
            body = await self.http.request(
                "POST",
                self._graph("me/messages"),
                endpoint="me.messages",
                token=self._token(acct),
                json=payload,
            )
        except PlatformError as error:
            raise for_write(error) from error.__cause__
        mid = body.get("message_id") if isinstance(body, dict) else None
        return SendResult(str(mid) if mid else None)

    async def mark_read(
        self, acct: SocialAccount, recipient_ref: str, *, message_ref: str | None = None
    ) -> None:
        """Show the customer their messages were seen (sender action ``mark_seen``)."""
        await self.http.request(
            "POST",
            self._graph("me/messages"),
            endpoint="me.messages.mark_seen",
            token=self._token(acct),
            json={"recipient": {"id": recipient_ref}, "sender_action": "mark_seen"},
        )

    async def download_media(self, acct: SocialAccount, ref: InboundMediaRef) -> MediaDownload:
        from socialhood.platforms.instagram import reads

        return await reads.download(self.deps.http, ref)

    async def list_media(self, acct: SocialAccount, *, limit: int = 25) -> list[PlatformMedia]:
        from socialhood.platforms.instagram import reads

        return await reads.list_media(self.http, self._graph, self._token(acct), limit=limit)

    async def list_threads(self, acct: SocialAccount, *, limit: int = 20) -> list[PlatformThread]:
        from socialhood.platforms.instagram import reads

        return await reads.list_threads(
            self.http, self._graph, self._token(acct), acct, limit=limit
        )
