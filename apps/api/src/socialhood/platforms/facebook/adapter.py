"""Facebook Page adapter: Messenger and Page comments (GR-29; TR-PL-01, TR-PL-11).

The account is one Page: ``platform_account_id`` is the Page id (the webhook ``entry.id``) and
the token is its Page access token, which does not expire. Calls go to ``graph.facebook.com``
with ``me`` meaning the Page. A Page can message, take attachments, mark chats seen, backfill
conversations, read, answer, hide and delete comments, send private replies and (GR-30, with the
``pages_manage_posts`` permission) publish photos, videos and text posts. With the ``read_insights``
permission (C-131) it reads a post's views, reach, clicks and shares; account insights are still
not built. A Page Story has no insights to read.

Every Meta behaviour here is unverified until a real Page confirms it (docs/verification.md):
see the CONFLICTS entry for GR-29 for the list.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

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
from socialhood.platforms.facebook import oauth
from socialhood.platforms.http import PlatformHttp
from socialhood.platforms.instagram.reads import GRAPH_ID

# Attachment types the Send API takes by URL. Messenger has no built-in sticker.
FACEBOOK_SENDABLE = frozenset({"image", "video", "audio", "file"})

# Fields every connected Page is subscribed to. The reconcile_subscriptions job re-subscribes
# connected accounts with this list (TR-WH-08).
SUBSCRIBED_FIELDS = (
    "messages,message_echoes,messaging_postbacks,messaging_referrals,message_reads,"
    "message_deliveries,message_reactions,message_edits,messaging_optins,feed"
)

CAPABILITIES = frozenset(
    {
        Capability.DM_SEND,
        Capability.DM_ATTACHMENTS,
        Capability.READ_RECEIPTS,
        Capability.CONVERSATION_BACKFILL,
        Capability.COMMENTS,
        Capability.PRIVATE_REPLY,
        Capability.PUBLISH,
        Capability.POST_INSIGHTS,
    }
)

# The button template's limits (Meta's Messenger docs; unverified for Pages until a real Page
# confirms them, like Instagram's, T0.9 item 10).
BUTTON_TEXT_MAX_CHARS = 640
MAX_BUTTONS = 3
MAX_QUICK_REPLIES = 13
NO_QUOTA = "Facebook Pages have no publishing limit to read"
NO_STORIES = "Facebook Page Stories aren't available yet"
NO_INSIGHTS = "Account insights for Facebook Pages aren't available yet"


class FacebookAdapter:
    platform = "facebook"

    def __init__(self, deps: PlatformDeps) -> None:
        self.deps = deps
        self.http = PlatformHttp(deps.http, "facebook")

    def capabilities_for(self, acct: SocialAccount) -> frozenset[Capability]:
        caps = set(CAPABILITIES)
        if oauth.PUBLISH_SCOPE not in (acct.scopes or []):
            caps.discard(Capability.PUBLISH)  # connected before GR-30: reconnect to allow it
        if oauth.INSIGHTS_SCOPE not in (acct.scopes or []):
            caps.discard(Capability.POST_INSIGHTS)  # read_insights not granted (C-131)
        if self.deps.settings.ig_human_agent_enabled:  # one Meta approval covers both (O-10)
            caps.add(Capability.HUMAN_AGENT)
        return frozenset(caps)

    def _token(self, acct: SocialAccount) -> str:
        if not acct.access_token_enc:
            raise PlatformError("account_needs_reconnect", message="No token stored")
        return self.deps.cipher.decrypt(acct.access_token_enc)

    def _graph(self, path: str) -> str:
        return f"{oauth.GRAPH}/{self.deps.settings.meta_graph_version}/{path}"

    async def refresh_token(self, acct: SocialAccount) -> TokenGrant:
        """A Page token made from a long-lived user token does not expire: nothing to refresh."""
        return TokenGrant(self._token(acct), None)

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
                "platform_rejected", message="Facebook did not confirm the subscription"
            )

    async def fetch_contact_profile(
        self, acct: SocialAccount, platform_user_id: str
    ) -> ContactProfile | None:
        from socialhood.platforms.facebook import reads

        return await reads.contact_profile(
            self.http, self._graph, self._token(acct), platform_user_id
        )

    # ---- messages

    async def send_message(
        self, acct: SocialAccount, recipient_ref: str, message: OutboundMessage
    ) -> SendResult:
        """One Send API call: text, text with quick replies, text with link buttons (the button
        template), or one attachment by URL (image, video, audio or file).

        Messages carry ``messaging_type: RESPONSE``; Human Agent replies carry ``MESSAGE_TAG``
        with ``tag: HUMAN_AGENT`` (TR-PL-04). A failure after the request went out is
        ``delivery_unknown`` (TR-JOB-05)."""
        if message.sticker is not None:
            raise PlatformError("platform_rejected", message="Messenger has no built-in stickers")
        if message.template is not None:
            raise PlatformError("platform_rejected", message="Messenger has no message templates")
        content: dict[str, object]
        if message.attachment is not None:
            if message.attachment.type not in FACEBOOK_SENDABLE:
                raise PlatformError(
                    "platform_rejected", message="Messenger can't send this kind of file"
                )
            content = {
                "attachment": {
                    "type": message.attachment.type,
                    "payload": {"url": message.attachment.url, "is_reusable": False},
                }
            }
        else:
            content = text_content(message)
        payload: dict[str, object] = {
            "recipient": {"id": recipient_ref},
            "messaging_type": "RESPONSE",
            "message": content,
        }
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

    # ---- posts and conversations

    async def list_media(self, acct: SocialAccount, *, limit: int = 25) -> list[PlatformMedia]:
        from socialhood.platforms.facebook import reads

        return await reads.list_media(self.http, self._graph, self._token(acct), limit=limit)

    async def list_stories(self, acct: SocialAccount) -> list[PlatformMedia]:
        return []  # Pages have no stories we can read

    async def get_media(self, acct: SocialAccount, media_ref: str) -> PlatformMedia | None:
        from socialhood.platforms.facebook import reads

        return await reads.get_media(self.http, self._graph, self._token(acct), media_ref)

    async def set_ice_breakers(
        self, acct: SocialAccount, starters: Sequence[IceBreaker]
    ) -> list[IceBreaker]:
        from socialhood.platforms.facebook import profile

        return await profile.set_ice_breakers(self.http, self._graph, self._token(acct), starters)

    async def list_threads(self, acct: SocialAccount, *, limit: int = 20) -> list[PlatformThread]:
        from socialhood.platforms.facebook import reads

        return await reads.list_threads(
            self.http, self._graph, self._token(acct), acct, limit=limit
        )

    # ---- comments: private replies and public replies

    async def private_reply(
        self, acct: SocialAccount, comment_ref: str, message: OutboundMessage
    ) -> SendResult:
        """Meta's private reply: the Send API addressed by ``recipient.comment_id`` (one per
        comment, within 7 days). Text, with link buttons or quick replies; nothing else, as on
        Instagram (unverified: Messenger may take more)."""
        if message.attachment is not None or message.sticker or message.template:
            raise PlatformError(
                "platform_rejected", message="A private reply can only carry text and link buttons"
            )
        payload: dict[str, object] = {
            "recipient": {"comment_id": _graph_id(comment_ref)},
            "messaging_type": "RESPONSE",
            "message": text_content(message),
        }
        return await self._send(acct, payload, endpoint="me.messages.private_reply")

    async def reply_to_comment(
        self, acct: SocialAccount, comment_ref: str, text: str
    ) -> str | None:
        """A public reply: ``POST /{comment_id}/comments?message=…``. Returns the new comment's
        id."""
        from socialhood.platforms.outcome import for_write

        if not text.strip():
            raise PlatformError("platform_rejected", message="A comment reply needs text")
        try:
            body = await self.http.request(
                "POST",
                self._graph(f"{_graph_id(comment_ref)}/comments"),
                endpoint="comment.replies",
                token=self._token(acct),
                params={"message": text},
            )
        except PlatformError as error:
            raise for_write(error) from error.__cause__
        reply_id = body.get("id") if isinstance(body, dict) else None
        return str(reply_id) if reply_id else None

    async def list_comments(
        self, acct: SocialAccount, media_ref: str, *, cursor: str | None = None
    ) -> CommentPage:
        from socialhood.platforms.facebook import comments

        return await comments.list_comments(
            self.http, self._graph, self._token(acct), acct, media_ref, cursor=cursor
        )

    async def hide_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        from socialhood.platforms.facebook import moderation

        await moderation.set_hidden(
            self.http, self._graph, self._token(acct), comment_ref, hidden=True
        )

    async def unhide_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        from socialhood.platforms.facebook import moderation

        await moderation.set_hidden(
            self.http, self._graph, self._token(acct), comment_ref, hidden=False
        )

    async def delete_comment(self, acct: SocialAccount, comment_ref: str) -> None:
        from socialhood.platforms.facebook import moderation

        await moderation.delete(self.http, self._graph, self._token(acct), comment_ref)

    # ---- counts and followers; insights and publishing arrive with GR-30

    async def get_media_counts(self, acct: SocialAccount, media_ref: str) -> MediaCounts | None:
        from socialhood.platforms.facebook import reads

        return await reads.media_counts(self.http, self._graph, self._token(acct), media_ref)

    async def get_media_insights(
        self, acct: SocialAccount, media_ref: str, *, media_type: str
    ) -> MediaInsights:
        """A Page post's views, reach, clicks and shares (needs ``read_insights``). A Page Story
        has none: Facebook gives no read API for it."""
        from socialhood.platforms.facebook import insights

        if Capability.POST_INSIGHTS not in self.capabilities_for(acct):
            raise PlatformError("capability_unavailable", message=NO_INSIGHTS)
        if media_type == "story":
            return MediaInsights()
        return await insights.media_insights(self.http, self._graph, self._token(acct), media_ref)

    async def get_account_insights(
        self, acct: SocialAccount, day: date, *, tz: str = "UTC"
    ) -> AccountInsights:
        """Only the Page's followers (no insights scope yet)."""
        from socialhood.platforms.facebook import reads

        count = await reads.followers(self.http, self._graph, self._token(acct))
        return AccountInsights(followers_count=count)

    async def get_publishing_quota(self, acct: SocialAccount) -> PublishingQuota:
        raise PlatformError("capability_unavailable", message=NO_QUOTA)

    # ---- publishing (GR-30, publishing.py): a container is a reference to what was uploaded
    # unpublished; publish_container posts it. See the module for the references.

    async def create_image_container(
        self, acct: SocialAccount, *, image_url: str, caption: str
    ) -> str:
        from socialhood.platforms.facebook import publishing

        return await publishing.create_photo(
            self.http, self._graph, self._token(acct), image_url=image_url, caption=caption
        )

    async def create_reel_container(
        self, acct: SocialAccount, *, video_url: str, caption: str, share_to_feed: bool = True
    ) -> str:
        """A Page video (not a Facebook Reel); ``share_to_feed`` has no meaning here."""
        from socialhood.platforms.facebook import publishing

        return await publishing.create_video(
            self.http, self._graph, self._token(acct), video_url=video_url, caption=caption
        )

    async def create_story_container(self, acct: SocialAccount, media: ContainerMedia) -> str:
        raise PlatformError("capability_unavailable", message=NO_STORIES)

    async def create_carousel_item(self, acct: SocialAccount, media: ContainerMedia) -> str:
        from socialhood.platforms.facebook import publishing

        return await publishing.create_child(self.http, self._graph, self._token(acct), media)

    async def create_carousel_container(
        self, acct: SocialAccount, *, children: Sequence[str], caption: str
    ) -> str:
        from socialhood.platforms.facebook import publishing

        return publishing.create_photos_parent(children)

    async def create_text_container(self, acct: SocialAccount) -> str:
        from socialhood.platforms.facebook import publishing

        return publishing.create_text()

    async def get_container_status(
        self, acct: SocialAccount, container_ref: str
    ) -> ContainerStatus:
        from socialhood.platforms.facebook import publishing

        return await publishing.container_status(
            self.http, self._graph, self._token(acct), container_ref
        )

    async def publish_container(
        self, acct: SocialAccount, container_ref: str, *, caption: str = ""
    ) -> str:
        from socialhood.platforms.facebook import publishing

        return await publishing.publish_container(
            self.http, self._graph, self._token(acct), container_ref, caption=caption
        )

    async def get_published_media(
        self, acct: SocialAccount, media_ref: str, *, story: bool = False
    ) -> PlatformMedia | None:
        from socialhood.platforms.facebook import publishing

        return await publishing.published_media(
            self.http, self._graph, self._token(acct), media_ref
        )

    async def find_published_media(
        self,
        acct: SocialAccount,
        container_ref: str,
        *,
        caption: str,
        published_after: datetime,
        story: bool = False,
    ) -> PlatformMedia | None:
        from socialhood.platforms.facebook import publishing

        return await publishing.find_published_media(
            self.http,
            self._graph,
            self._token(acct),
            caption=caption,
            published_after=published_after,
        )

    async def post_comment(self, acct: SocialAccount, media_ref: str, text: str) -> str | None:
        from socialhood.platforms.facebook import publishing

        return await publishing.post_comment(
            self.http, self._graph, self._token(acct), media_ref, text
        )


def text_content(message: OutboundMessage) -> dict[str, object]:
    """Text, text with quick replies (tap first, FR-AUT-21), or text with link buttons as
    Messenger's button template."""
    if not message.text:
        raise PlatformError(
            "platform_rejected", message="Messenger messages need text or one attachment"
        )
    if message.quick_replies:
        if message.buttons:
            raise PlatformError(
                "platform_rejected", message="Quick replies can't go with link buttons"
            )
        if len(message.quick_replies) > MAX_QUICK_REPLIES:
            raise PlatformError(
                "platform_rejected", message="Messenger allows up to 13 quick replies"
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
        raise PlatformError("platform_rejected", message="Messenger allows up to 3 buttons")
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
    if not GRAPH_ID.match(ref):
        raise PlatformError("platform_rejected", message="Not a Facebook id")
    return ref
