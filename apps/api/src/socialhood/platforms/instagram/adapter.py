"""Instagram adapter for connected accounts (TR-PL-01, TR-PL-11)."""

from __future__ import annotations

from datetime import date

from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import (
    AccountInsights,
    CommentPage,
    ContactProfile,
    MediaCounts,
    MediaDownload,
    MediaInsights,
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

# The User Profile API fields we read (TR-PL-06; FR-AUT-22 for the follow status).
PROFILE_FIELDS = "name,username,profile_pic,is_user_follow_business"

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
        """Instagram's User Profile API, which needs the person's consent (they messaged the
        account first). ``is_user_follow_business`` feeds the follow nudge (FR-AUT-22)."""
        body = await self.http.request(
            "GET",
            self._graph(platform_user_id),
            endpoint="user_profile",
            token=self._token(acct),
            params={"fields": PROFILE_FIELDS},
        )
        if not isinstance(body, dict):
            return None
        follows = body.get("is_user_follow_business")
        return ContactProfile(
            name=body.get("name"),
            username=body.get("username"),
            profile_picture_url=body.get("profile_pic"),
            follows_business=follows if isinstance(follows, bool) else None,
        )

    # ---- P3 (filled by T3.6/T3.7 for sending, T3.3/T3.14 for media, sync and backfill)

    async def send_message(
        self, acct: SocialAccount, recipient_ref: str, message: OutboundMessage
    ) -> SendResult:
        """One Send API call: text, text with quick replies, text with link buttons (the button
        template), one attachment by URL (image, video, audio or PDF file), or the heart sticker.

        Human Agent replies carry ``messaging_type: MESSAGE_TAG`` and ``tag: HUMAN_AGENT``
        (TR-PL-04). A failure after the request went out is ``delivery_unknown`` (TR-JOB-05).
        """
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
        else:
            content = _text_content(message)
        payload: dict[str, object] = {"recipient": {"id": recipient_ref}, "message": content}
        if message.human_agent:
            payload["messaging_type"] = "MESSAGE_TAG"
            payload["tag"] = "HUMAN_AGENT"
        return await self._send(acct, payload, endpoint="me.messages")

    async def _send(
        self, acct: SocialAccount, payload: dict[str, object], *, endpoint: str
    ) -> SendResult:
        from socialhood.platforms.outcome import for_write

        try:
            body = await self.http.request(
                "POST",
                self._graph("me/messages"),
                endpoint=endpoint,
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

    async def get_media(self, acct: SocialAccount, media_ref: str) -> PlatformMedia | None:
        from socialhood.platforms.instagram import reads

        return await reads.get_media(self.http, self._graph, self._token(acct), media_ref)

    async def list_threads(self, acct: SocialAccount, *, limit: int = 20) -> list[PlatformThread]:
        from socialhood.platforms.instagram import reads

        return await reads.list_threads(
            self.http, self._graph, self._token(acct), acct, limit=limit
        )

    # ---- P4 (T4.4): private replies and public comment replies

    async def private_reply(
        self, acct: SocialAccount, comment_ref: str, message: OutboundMessage
    ) -> SendResult:
        """Meta's private reply: the Send API addressed by ``recipient.comment_id`` (one per
        comment, within 7 days). Text, with link buttons or quick replies (a tap-first opening,
        FR-AUT-21); nothing else. Meta's docs show only ``message.text`` for private replies, so
        the runtime retries a rejected opening as text only (unverified, T0.9)."""
        if message.attachment is not None or message.sticker or message.template:
            raise PlatformError(
                "platform_rejected", message="A private reply can only carry text and link buttons"
            )
        payload: dict[str, object] = {
            "recipient": {"comment_id": _graph_id(comment_ref)},
            "message": _text_content(message),
        }
        return await self._send(acct, payload, endpoint="me.messages.private_reply")

    async def reply_to_comment(
        self, acct: SocialAccount, comment_ref: str, text: str
    ) -> str | None:
        """A public reply: ``POST /{comment_id}/replies?message=…`` (a reply to a reply lands
        under the top-level comment). Returns the new comment's id."""
        from socialhood.platforms.outcome import for_write

        if not text.strip():
            raise PlatformError("platform_rejected", message="A comment reply needs text")
        try:
            body = await self.http.request(
                "POST",
                self._graph(f"{_graph_id(comment_ref)}/replies"),
                endpoint="comment.replies",
                token=self._token(acct),
                params={"message": text},
            )
        except PlatformError as error:
            raise for_write(error) from error.__cause__
        reply_id = body.get("id") if isinstance(body, dict) else None
        return str(reply_id) if reply_id else None

    # ---- P6: comment backfill (T6.1, comments.py), moderation (T6.3, moderation.py), live counts
    # and insights (T6.5, insights.py)

    async def list_comments(
        self, acct: SocialAccount, media_ref: str, *, cursor: str | None = None
    ) -> CommentPage:
        from socialhood.platforms.instagram import comments

        return await comments.list_comments(
            self.http, self._graph, self._token(acct), acct, media_ref, cursor=cursor
        )

    async def hide_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        from socialhood.platforms.instagram import moderation

        await moderation.set_hidden(
            self.http, self._graph, self._token(acct), comment_ref, hidden=True
        )

    async def unhide_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        from socialhood.platforms.instagram import moderation

        await moderation.set_hidden(
            self.http, self._graph, self._token(acct), comment_ref, hidden=False
        )

    async def delete_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        from socialhood.platforms.instagram import moderation

        await moderation.delete(self.http, self._graph, self._token(acct), comment_ref)

    async def get_media_counts(self, acct: SocialAccount, media_ref: str) -> MediaCounts | None:
        from socialhood.platforms.instagram import insights

        return await insights.media_counts(self.http, self._graph, self._token(acct), media_ref)

    async def get_media_insights(
        self, acct: SocialAccount, media_ref: str, *, media_type: str
    ) -> MediaInsights:
        from socialhood.platforms.instagram import insights

        return await insights.media_insights(
            self.http, self._graph, self._token(acct), media_ref, media_type=media_type
        )

    async def get_account_insights(
        self, acct: SocialAccount, day: date, *, tz: str = "UTC"
    ) -> AccountInsights:
        from socialhood.platforms.instagram import insights

        return await insights.account_insights(
            self.http,
            self._graph,
            self._token(acct),
            acct,
            day,
            tz=tz,
            with_insights=Capability.ACCOUNT_INSIGHTS in self.capabilities_for(acct),
        )


# The button template's limits (Meta's Instagram Messaging docs, checked 2026-09-29; T0.9 item 10
# confirms them on a real account).
BUTTON_TEXT_MAX_CHARS = 640
MAX_BUTTONS = 3
# Quick replies (Meta's docs, checked 2026-09-29): at most 13, content_type "text"; titles past 20
# characters are cut by Instagram. Not shown on desktop.
MAX_QUICK_REPLIES = 13


def _text_content(message: OutboundMessage) -> dict[str, object]:
    """Text, text with quick replies (tap first, FR-AUT-21), or text with link buttons as
    Instagram's button template."""
    if not message.text:
        raise PlatformError(
            "platform_rejected", message="Instagram messages need text or one attachment"
        )
    if message.quick_replies:
        if message.buttons:
            raise PlatformError(
                "platform_rejected", message="Quick replies can't go with link buttons"
            )
        if len(message.quick_replies) > MAX_QUICK_REPLIES:
            raise PlatformError(
                "platform_rejected", message="Instagram allows up to 13 quick replies"
            )
        return {
            "text": message.text,
            "quick_replies": [
                {"content_type": "text", "title": reply.title, "payload": reply.payload}
                for reply in message.quick_replies
            ],
        }
    if not message.buttons:
        return {"text": message.text}
    if len(message.buttons) > MAX_BUTTONS:
        raise PlatformError("platform_rejected", message="Instagram allows up to 3 buttons")
    if len(message.text) > BUTTON_TEXT_MAX_CHARS:
        raise PlatformError(
            "platform_rejected",
            message=f"Messages with buttons can be up to {BUTTON_TEXT_MAX_CHARS} characters",
        )
    return {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "button",
                "text": message.text,
                "buttons": [
                    {"type": "web_url", "url": button.url, "title": button.title}
                    for button in message.buttons
                ],
            },
        }
    }


def _graph_id(ref: str) -> str:
    """A platform id placed in a Graph path; anything else could change the path."""
    from socialhood.platforms.instagram.reads import GRAPH_ID

    if not GRAPH_ID.match(ref):
        raise PlatformError("platform_rejected", message="Not an Instagram id")
    return ref
