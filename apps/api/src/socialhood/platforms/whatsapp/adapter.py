"""WhatsApp adapter for connected numbers (TR-PL-01, TR-PL-11, FR-INB-08, FR-INB-10).

The account is one phone number: platform_account_id is its phone_number_id and waba_id its
WhatsApp Business Account. Calls use the business token from Embedded Signup.
"""

from __future__ import annotations

from typing import Any

from socialhood.models.connections import SocialAccount
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import (
    ContactProfile,
    MediaDownload,
    OutboundAttachment,
    OutboundMessage,
    OutboundTemplate,
    PlatformMedia,
    PlatformThread,
    SendResult,
    TokenGrant,
)
from socialhood.platforms.capabilities import Capability
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.events import InboundMediaRef
from socialhood.platforms.whatsapp.graph import WhatsAppHttp
from socialhood.platforms.whatsapp.templates import MessageTemplate, parse_template

CAPABILITIES = frozenset(
    {
        Capability.DM_SEND,
        Capability.DM_ATTACHMENTS,
        Capability.READ_RECEIPTS,
        Capability.TEMPLATES,
    }
)

# Our attachment types -> WhatsApp message types. Documents carry a filename; audio no caption.
MEDIA_TYPES = {"image": "image", "video": "video", "audio": "audio", "file": "document"}
TEMPLATE_FIELDS = "name,language,status,category,components"
TEMPLATE_PAGE = 100
TEMPLATE_MAX_PAGES = 5

log = get_logger(__name__)


def _media(attachment: OutboundAttachment, caption: str | None) -> dict[str, Any]:
    kind = MEDIA_TYPES[attachment.type]
    media: dict[str, Any] = {"link": attachment.url}
    if caption:
        if kind == "audio":
            raise PlatformError(
                "platform_rejected", message="WhatsApp audio can't carry text; send it separately"
            )
        media["caption"] = caption
    if kind == "document" and attachment.filename:
        media["filename"] = attachment.filename
    return {"type": kind, kind: media}


def _template(template: OutboundTemplate) -> dict[str, Any]:
    body: dict[str, Any] = {"name": template.name, "language": {"code": template.language}}
    if template.params:
        body["components"] = [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": value} for value in template.params],
            }
        ]
    return {"type": "template", "template": body}


def outbound_payload(to: str, message: OutboundMessage) -> dict[str, Any]:
    """The POST /{phone_number_id}/messages body for one send (text, one attachment, or a
    template). Text with an image, video or document goes as its caption."""
    if message.template is not None:
        content = _template(message.template)
    elif message.attachment is not None:
        content = _media(message.attachment, message.text)
    elif message.text:
        content = {"type": "text", "text": {"body": message.text, "preview_url": False}}
    else:
        raise PlatformError("platform_rejected", message="Nothing to send")
    return {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, **content}


class WhatsAppAdapter:
    platform = "whatsapp"

    def __init__(self, deps: PlatformDeps) -> None:
        self.deps = deps
        self.wa = WhatsAppHttp(deps.http, deps.settings)

    def capabilities_for(self, acct: SocialAccount) -> frozenset[Capability]:
        return CAPABILITIES

    def _token(self, acct: SocialAccount) -> str:
        if not acct.access_token_enc:
            raise PlatformError("account_needs_reconnect", message="No token stored")
        return self.deps.cipher.decrypt(acct.access_token_enc)

    async def refresh_token(self, acct: SocialAccount) -> TokenGrant:
        """Embedded Signup's business token has no refresh call. It is stored without an expiry
        unless Meta sent one, so this only runs for a token Meta said will expire: ask for a new
        signup before it does (F-05)."""
        raise PlatformError(
            "account_needs_reconnect",
            message="WhatsApp business tokens can't be refreshed; connect the number again",
        )

    async def subscribe_webhooks(self, acct: SocialAccount) -> None:
        """Subscribe our app to the number's WhatsApp Business Account (FR-CON-02)."""
        if not acct.waba_id:
            raise PlatformError("platform_rejected", message="No WhatsApp Business Account stored")
        body = await self.wa.request(
            "POST",
            f"{acct.waba_id}/subscribed_apps",
            endpoint="waba.subscribed_apps",
            token=self._token(acct),
        )
        if not (isinstance(body, dict) and body.get("success")):
            raise PlatformError(
                "platform_rejected", message="WhatsApp did not confirm the subscription"
            )

    async def fetch_contact_profile(
        self, acct: SocialAccount, platform_user_id: str
    ) -> ContactProfile | None:
        """WhatsApp has no profile lookup: the name arrives with each message
        (contacts[].profile.name) and pictures are not available. Nothing to fetch."""
        return None

    async def send_message(
        self, acct: SocialAccount, recipient_ref: str, message: OutboundMessage
    ) -> SendResult:
        """Send to a wa_id. Meta accepting the send is not delivery: failures such as a closed
        window (131047) or an unreachable number (131026) arrive later as a failed status."""
        body = await self.wa.request(
            "POST",
            f"{acct.platform_account_id}/messages",
            endpoint="messages.send",
            token=self._token(acct),
            json=outbound_payload(recipient_ref, message),
        )
        messages = body.get("messages") if isinstance(body, dict) else None
        first = messages[0] if isinstance(messages, list) and messages else {}
        wamid = first.get("id") if isinstance(first, dict) else None
        return SendResult(str(wamid) if wamid else None)

    async def mark_read(
        self, acct: SocialAccount, recipient_ref: str, *, message_ref: str | None = None
    ) -> None:
        """Mark an inbound message (and everything before it) read. WhatsApp needs the message's
        wamid, not the contact: pass it as ``message_ref``, or as ``recipient_ref`` itself."""
        wamid = message_ref or (recipient_ref if recipient_ref.startswith("wamid.") else None)
        if wamid is None:
            log.info("whatsapp_mark_read_skipped", reason="no message id")
            return
        await self.wa.request(
            "POST",
            f"{acct.platform_account_id}/messages",
            endpoint="messages.read",
            token=self._token(acct),
            json={"messaging_product": "whatsapp", "status": "read", "message_id": wamid},
        )

    async def download_media(self, acct: SocialAccount, ref: InboundMediaRef) -> MediaDownload:
        """Media id -> a URL valid for 5 minutes -> the bytes, both with the token. Call it right
        before storing the file (TR-MED-03)."""
        if not ref.media_id:
            raise PlatformError("platform_rejected", message="No WhatsApp media id")
        token = self._token(acct)
        body = await self.wa.request(
            "GET",
            ref.media_id,
            endpoint="media.url",
            token=token,
        )
        url = body.get("url") if isinstance(body, dict) else None
        if not url:
            raise PlatformError("platform_rejected", message="WhatsApp returned no media URL")
        download = await self.wa.download(str(url), token=token)
        return MediaDownload(download.content, download.mime_type or body.get("mime_type"))

    async def list_templates(self, acct: SocialAccount) -> list[MessageTemplate]:
        """Approved templates of the number's WhatsApp Business Account that the picker can
        send (see platforms/whatsapp/templates.py)."""
        if not acct.waba_id:
            raise PlatformError("platform_rejected", message="No WhatsApp Business Account stored")
        token = self._token(acct)
        found: list[MessageTemplate] = []
        after: str | None = None
        for _ in range(TEMPLATE_MAX_PAGES):
            params: dict[str, Any] = {"fields": TEMPLATE_FIELDS, "limit": TEMPLATE_PAGE}
            if after:
                params["after"] = after
            body = await self.wa.request(
                "GET",
                f"{acct.waba_id}/message_templates",
                endpoint="waba.message_templates",
                token=token,
                params=params,
            )
            if not isinstance(body, dict):
                break
            found.extend(t for t in map(parse_template, body.get("data") or []) if t)
            paging = body["paging"] if isinstance(body.get("paging"), dict) else {}
            cursors = paging["cursors"] if isinstance(paging.get("cursors"), dict) else {}
            after = cursors.get("after") if paging.get("next") else None
            if not after:
                break
        return sorted(found, key=lambda t: (t.name, t.language))

    async def list_media(self, acct: SocialAccount, *, limit: int = 25) -> list[PlatformMedia]:
        return []  # WhatsApp numbers have no posts

    async def list_threads(self, acct: SocialAccount, *, limit: int = 20) -> list[PlatformThread]:
        return []  # no history API: the inbox fills as customers write (F-04)
