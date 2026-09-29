"""Platform-agnostic ingest (T3.2; F-06, TR-WH-06, TR-PL-12, FR-INB-05, FR-INB-09, TR-JOB-05):
typed inbound events from any platform's parser become contacts, conversations and messages.

Contract (shared by the Instagram and WhatsApp handlers):
- runs inside the account's workspace scope, in the caller's transaction; never commits;
- idempotent: replaying the same events creates nothing new and triggers nothing (TR-WH-06);
- queues real-time events with ``realtime.events.queue_message`` / ``queue_conversation``;
  the caller publishes them after its commit;
- enqueues follow-ups (profile fetch, media copy) only for rows it actually created.

What each event does:
- a message is inserted once per (account, platform message id). Inbound: the conversation gets
  the last-message fields, ``last_inbound_at``, one more unread, ``awaiting_reply`` and leaves
  the archive (FR-INB-05). An echo (sent from the platform's own app) is stored as outbound with
  source ``native_app`` (FR-INB-09) and clears ``awaiting_reply`` and ``needs_human`` (F-09); an
  echo of our own send, whose id we already stored, changes nothing. An echo of a send that timed
  out (failed, ``delivery_unknown``) with the same text within 2 minutes completes that message
  instead (TR-JOB-05). Out-of-order arrivals never move the last-message fields backwards;
- a reaction replaces the customer's reaction on the message (one per person);
- a read receipt marks the account's sent and delivered messages read up to the one read;
- an edit replaces the text and sets ``edited_at``;
- a delivery status (WhatsApp) moves an outbound message forward, never back.

A new customer message (not backfill) also sets ``contact_replied_at`` on automation runs that
DMed the contact in the 24 h before (FR-AUT-16) and enqueues ``run_automation("dm", id)`` when
the account has DM automations or a tap-first opening awaits the contact's answer (F-06 step 8,
FR-AUT-21). A tapped quick reply keeps its payload (``quick_reply_payload``).

Follow-ups are deferred by a couple of seconds: the caller commits after this returns, and a job
that finds no row (its transaction rolled back) does nothing. ``backfill=True`` (history from
FR-CON-01) leaves unread counts and the archive alone and sends one ``conversation.updated`` per
conversation instead of an event per message.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.connections import SocialAccount
from socialhood.models.inbox import (
    Contact,
    Conversation,
    ConversationStatus,
    Direction,
    Message,
    MessageKind,
    MessageSource,
    MessageStatus,
)
from socialhood.platforms.events import (
    DeliveryStatus,
    InboundComment,
    InboundEvent,
    InboundMediaRef,
    InboundMessage,
    MessageDeleted,
    MessageEdit,
    Reaction,
    ReadReceipt,
    Unsupported,
)
from socialhood.realtime.events import queue_conversation, queue_message
from socialhood.repositories import inbox
from socialhood.repositories import ingest as rows
from socialhood.services.inbox_views import UNSENT_PREVIEW, conversation_touch, preview_text

PROFILE_MAX_AGE = timedelta(days=7)
RECONCILE_WINDOW = timedelta(minutes=2)  # TR-JOB-05
FOLLOWUP_DELAY_S = 2.0
# Attachment types ingest_media copies to our storage (TR-MED-03). Stories are never copied
# (Meta's policy for story mentions; a story reply's story is the account's own and expires with
# it); shared posts keep the link to someone else's post.
COPYABLE = frozenset({"image", "video", "audio", "file", "sticker"})
STORED_TYPES = COPYABLE | {"story", "share"}
KINDS = frozenset(MessageKind)
STATUS_ORDER = {
    MessageStatus.QUEUED: 0,
    MessageStatus.SENDING: 1,
    MessageStatus.SENT: 2,
    MessageStatus.DELIVERED: 3,
    MessageStatus.READ: 4,
}


@dataclass
class IngestResult:
    created_message_ids: list[uuid.UUID] = field(default_factory=list)
    updated_message_ids: list[uuid.UUID] = field(default_factory=list)
    conversation_ids: list[uuid.UUID] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)  # reasons, for the webhook event's note

    @property
    def changed(self) -> bool:
        return bool(self.created_message_ids or self.updated_message_ids or self.conversation_ids)


async def ingest(
    session: AsyncSession,
    acct: SocialAccount,
    events: Sequence[InboundEvent],
    *,
    now: datetime | None = None,
    backfill: bool = False,
) -> IngestResult:
    run = _Ingest(session, acct, now or datetime.now(UTC), backfill)
    for event in events:
        await run.apply(event)
    await run.finish()
    return run.result


def attachment_record(ref: InboundMediaRef) -> dict[str, Any] | None:
    """The stored Attachment (§5.10) for a platform media ref. ``url`` is the platform URL until
    ingest_media re-hosts it; ``platform_url`` and ``media_id`` stay private (not in the API)."""
    if ref.kind not in STORED_TYPES or not (ref.url or ref.media_id):
        return None
    record: dict[str, Any] = {"id": uuid.uuid4().hex, "type": ref.kind, "url": ref.url or ""}
    if ref.url:
        record["platform_url"] = ref.url
    if ref.media_id:
        record["media_id"] = ref.media_id
    if ref.mime_type:
        record["mime_type"] = ref.mime_type
    if ref.filename:
        record["filename"] = ref.filename
    return record


async def _follow_scheduled(session: AsyncSession, msg: Message) -> None:
    """A send's result was decided here (echo): scheduled messages and automation runs follow."""
    # Imported here: scheduled → sending → connections → sync → ingest would be a cycle.
    from socialhood.services import scheduled
    from socialhood.services.automations import results

    await scheduled.follow_message(session, msg)
    await results.follow_message(session, msg)


async def _automations(session: AsyncSession, contact: Contact, msg: Message) -> None:
    """A new customer DM: count it as a reply to recent automation DMs (FR-AUT-16) and let
    automations answer it (F-11 runtime, before the AI's analysis): a tap-first opening waiting
    for this contact (FR-AUT-21), or DM keyword automations."""
    from socialhood.services.automations import runtime

    await runtime.contact_replied(session, contact.id, at=msg.occurred_at)
    await runtime.enqueue_for_message(session, msg, contact_id=contact.id)


def _later(current: datetime | None, candidate: datetime) -> datetime:
    return candidate if current is None or candidate > current else current


class _Ingest:
    def __init__(
        self, session: AsyncSession, acct: SocialAccount, now: datetime, backfill: bool
    ) -> None:
        self.session = session
        self.acct = acct
        self.now = now
        self.backfill = backfill
        self.result = IngestResult()
        self.touched: dict[uuid.UUID, tuple[Conversation, Contact | None]] = {}
        self.profiles: dict[uuid.UUID, None] = {}  # contact ids, in order, without duplicates
        self.media: list[tuple[uuid.UUID, str]] = []  # (message id, attachment id)
        self.unsent_assets: list[str] = []  # stored copies of unsent messages' media

    async def apply(self, event: InboundEvent) -> None:
        if isinstance(event, InboundMessage):
            await self._message(event)
        elif isinstance(event, Reaction):
            await self._reaction(event)
        elif isinstance(event, ReadReceipt):
            await self._read(event)
        elif isinstance(event, MessageEdit):
            await self._edit(event)
        elif isinstance(event, MessageDeleted):
            await self._unsend(event)
        elif isinstance(event, DeliveryStatus):
            await self._status(event)
        elif isinstance(event, InboundComment):
            # Comments are taken in by services/automations/comments (F-12), not here.
            self.result.ignored.append("comments are not messages")
        elif isinstance(event, Unsupported):
            self.result.ignored.append(event.reason)
        # Sessions do not autoflush, and the next event's row locks reload from the database.
        await self.session.flush()

    # ---- messages and echoes

    async def _message(self, event: InboundMessage) -> None:
        if not event.contact_ref:
            self.result.ignored.append("message without a contact")
            return
        stored = await inbox.find_message_by_platform_id(
            self.session, self.acct.id, event.platform_message_id
        )
        if stored is not None:
            return  # a replay, or the echo of a message we sent: nothing to do
        contact, new_contact = await rows.get_or_create_contact(
            self.session,
            social_account_id=self.acct.id,
            platform_user_id=event.contact_ref,
            first_seen_at=event.occurred_at,
            display_name=event.contact_name,
        )
        conv, _ = await rows.get_or_create_conversation(
            self.session,
            social_account_id=self.acct.id,
            contact_id=contact.id,
            platform=self.acct.platform,
        )
        if event.is_echo and await self._own_send(conv, event):
            return
        if event.is_echo and event.text and await self._reconcile(conv, event):
            return
        msg = await rows.insert_message(self.session, self._values(conv, event))
        if msg is None:
            return  # stored by a concurrent worker between our check and insert
        if event.is_echo:
            self._outbound(conv, msg)
        else:
            self._inbound(conv, contact, msg, event)
            if not self.backfill:
                await _automations(self.session, contact, msg)
        self.touched[conv.id] = (conv, contact)
        self.result.created_message_ids.append(msg.id)
        if not self.backfill:
            queue_message(self.session, msg, created=True)
        if new_contact or self._profile_stale(contact):
            self.profiles[contact.id] = None
        self.media.extend((msg.id, a["id"]) for a in msg.attachments if a["type"] in COPYABLE)

    def _values(self, conv: Conversation, event: InboundMessage) -> dict[str, Any]:
        echo = event.is_echo
        records = [r for r in map(attachment_record, event.attachments) if r is not None]
        return {
            "conversation_id": conv.id,
            "social_account_id": self.acct.id,
            "direction": Direction.OUTBOUND if echo else Direction.INBOUND,
            "source": MessageSource.NATIVE_APP if echo else MessageSource.CUSTOMER,
            "kind": event.kind if event.kind in KINDS else MessageKind.UNSUPPORTED,
            "text": event.text,
            "attachments": records,
            "occurred_at": event.occurred_at,
            "platform_message_id": event.platform_message_id,
            "status": MessageStatus.SENT if echo else MessageStatus.RECEIVED,
            "sent_at": event.occurred_at if echo else None,
            "reply_to_platform_message_id": event.reply_to_id,
            "quick_reply_payload": None if echo else event.quick_reply_payload,
        }

    def _newest(self, conv: Conversation, msg: Message) -> bool:
        if conv.last_message_at is None or msg.occurred_at >= conv.last_message_at:
            for key, value in conversation_touch(msg).items():
                setattr(conv, key, value)
            return True
        return False

    def _inbound(
        self, conv: Conversation, contact: Contact, msg: Message, event: InboundMessage
    ) -> None:
        if self._newest(conv, msg):
            conv.awaiting_reply = True
        conv.last_inbound_at = _later(conv.last_inbound_at, msg.occurred_at)
        contact.last_seen_at = _later(contact.last_seen_at, msg.occurred_at)
        if event.contact_name and contact.display_name != event.contact_name:
            contact.display_name = event.contact_name
        if not self.backfill:
            conv.unread_count += 1
            if conv.status == ConversationStatus.ARCHIVED:
                conv.status = ConversationStatus.OPEN

    def _outbound(self, conv: Conversation, msg: Message) -> None:
        if self._newest(conv, msg):
            conv.awaiting_reply = False
        conv.last_outbound_at = _later(conv.last_outbound_at, msg.occurred_at)
        if not self.backfill:  # F-09: sending any message clears needs_human
            conv.needs_human = False
            conv.needs_human_reason = None
            # Q-019: replying in the Instagram app means the business has read the conversation.
            if self._newest(conv, msg):
                conv.unread_count = 0

    async def _own_send(self, conv: Conversation, event: InboundMessage) -> bool:
        """An echo of our own send that arrived before the send job stored its id. A text echo is
        the send's last part, so it proves delivery: record the id and mark it sent (the job then
        finds it done). An attachment part's echo changes nothing; the job records each part."""
        own = await rows.own_send_for_echo(
            self.session,
            conv.id,
            platform_message_id=event.platform_message_id,
            text=event.text,
            has_attachments=bool(event.attachments),
            around=event.occurred_at,
            window=RECONCILE_WINDOW,
        )
        if own is None:
            return False
        if event.text and own.platform_message_id is None and own.status == MessageStatus.SENDING:
            own.platform_message_id = event.platform_message_id
            own.status = MessageStatus.SENT
            own.sent_at = event.occurred_at
            await self.session.flush()
            queue_message(self.session, own, created=False)
            await _follow_scheduled(self.session, own)
            self.result.updated_message_ids.append(own.id)
        return True

    async def _reconcile(self, conv: Conversation, event: InboundMessage) -> bool:
        """TR-JOB-05: the echo proves a timed-out send was delivered."""
        assert event.text is not None
        pending = await rows.unknown_delivery_candidate(
            self.session,
            conv.id,
            text=event.text,
            around=event.occurred_at,
            window=RECONCILE_WINDOW,
        )
        if pending is None:
            return False
        pending.platform_message_id = event.platform_message_id
        pending.status = MessageStatus.SENT
        pending.sent_at = event.occurred_at
        pending.error_code = None
        pending.error_message = None
        await self.session.flush()
        queue_message(self.session, pending, created=False)
        await _follow_scheduled(self.session, pending)
        self.result.updated_message_ids.append(pending.id)
        return True

    def _profile_stale(self, contact: Contact) -> bool:
        fetched = contact.profile_fetched_at
        return fetched is None or self.now - fetched > PROFILE_MAX_AGE

    # ---- reactions, read receipts, edits, delivery statuses

    async def _reaction(self, event: Reaction) -> None:
        msg = await rows.lock_message_by_platform_id(
            self.session, self.acct.id, event.platform_message_id
        )
        if msg is None:
            self.result.ignored.append("reaction to a message we don't have")
            return
        current = list(msg.reactions or [])
        others = [r for r in current if r.get("by") != "customer"]
        if event.emoji is None:
            if len(others) == len(current):
                return
            msg.reactions = others
        else:
            if any(r.get("by") == "customer" and r.get("emoji") == event.emoji for r in current):
                return
            mine = {"emoji": event.emoji, "by": "customer", "at": event.occurred_at.isoformat()}
            msg.reactions = [*others, mine]
        await self._updated(msg)

    async def _read(self, event: ReadReceipt) -> None:
        found = await rows.conversation_for_contact_ref(
            self.session, self.acct.id, event.contact_ref
        )
        if found is None:
            self.result.ignored.append("read receipt from an unknown contact")
            return
        conv, _ = found
        up_to = event.occurred_at
        if event.last_read_message_id:
            target = await inbox.find_message_by_platform_id(
                self.session, self.acct.id, event.last_read_message_id
            )
            if target is not None and target.conversation_id == conv.id:
                up_to = target.occurred_at
        for msg in await rows.outbound_unread(self.session, conv.id, up_to=up_to):
            msg.status = MessageStatus.READ
            msg.read_at = event.occurred_at
            await self._updated(msg)

    async def _edit(self, event: MessageEdit) -> None:
        msg = await rows.lock_message_by_platform_id(
            self.session, self.acct.id, event.platform_message_id
        )
        if msg is None:
            self.result.ignored.append("edit of a message we don't have")
            return
        if msg.text == event.text:
            return
        msg.text = event.text
        msg.edited_at = event.occurred_at
        await self._updated(msg)
        conv = await rows.lock_conversation(self.session, msg.conversation_id)
        if conv is None or conv.last_message_at is None or msg.occurred_at < conv.last_message_at:
            return  # not the conversation's latest message: the preview stays
        conv.last_message_preview = preview_text(msg.kind, msg.text)
        self.touched.setdefault(conv.id, (conv, None))

    async def _unsend(self, event: MessageDeleted) -> None:
        """Q-021: the customer unsent a message. Its content goes (text, attachments, reactions)
        and the bubble says it was unsent; stored copies of its media are deleted."""
        msg = await rows.lock_message_by_platform_id(
            self.session, self.acct.id, event.platform_message_id
        )
        if msg is None:
            self.result.ignored.append("unsent message we don't have")
            return
        if msg.deleted_at is not None:
            return
        self.unsent_assets.extend(
            str(a["asset_id"]) for a in msg.attachments or [] if a.get("asset_id")
        )
        msg.deleted_at = event.occurred_at
        msg.text = None
        msg.attachments = []
        msg.reactions = []
        await self._updated(msg)
        conv = await rows.lock_conversation(self.session, msg.conversation_id)
        if conv is None or conv.last_message_at is None or msg.occurred_at < conv.last_message_at:
            return
        conv.last_message_preview = UNSENT_PREVIEW
        self.touched.setdefault(conv.id, (conv, None))

    async def _status(self, event: DeliveryStatus) -> None:
        msg = await rows.lock_message_by_platform_id(
            self.session, self.acct.id, event.platform_message_id
        )
        if msg is None or msg.direction != Direction.OUTBOUND:
            self.result.ignored.append("status of a message we don't have")
            return
        current = STATUS_ORDER.get(MessageStatus(msg.status), -1) if msg.status else -1
        if event.status == "failed":
            if current >= STATUS_ORDER[MessageStatus.DELIVERED] or msg.status == "failed":
                return
            msg.status = MessageStatus.FAILED
            msg.error_code = event.error_code or "platform_rejected"
        else:
            status = MessageStatus(event.status)
            if STATUS_ORDER[status] <= current:
                return
            msg.status = status
            msg.error_code = None
            msg.error_message = None
            msg.sent_at = msg.sent_at or event.occurred_at
            if status in (MessageStatus.DELIVERED, MessageStatus.READ):
                msg.delivered_at = msg.delivered_at or event.occurred_at
            if status == MessageStatus.READ:
                msg.read_at = event.occurred_at
        await self._updated(msg)

    async def _updated(self, msg: Message) -> None:
        await self.session.flush()
        queue_message(self.session, msg, created=False)
        if msg.id not in self.result.updated_message_ids:
            self.result.updated_message_ids.append(msg.id)

    # ---- after all events

    async def finish(self) -> None:
        for conv, contact in self.touched.values():
            await queue_conversation(self.session, conv, now=self.now, contact=contact)
            self.result.conversation_ids.append(conv.id)
        await self._enqueue_followups()

    async def _enqueue_followups(self) -> None:
        if not (self.profiles or self.media or self.unsent_assets):
            return
        from socialhood.jobs.enqueue import enqueue
        from socialhood.jobs.tasks.ingest import (
            delete_unsent_media,
            fetch_contact_profile,
            ingest_media,
        )

        workspace_id = str(self.acct.workspace_id)
        for contact_id in self.profiles:
            await enqueue(
                fetch_contact_profile,
                key=f"profile:{contact_id}",
                delay_s=FOLLOWUP_DELAY_S,
                workspace_id=workspace_id,
                contact_id=str(contact_id),
            )
        for message_id, attachment_id in self.media:
            await enqueue(
                ingest_media,
                key=f"media:{attachment_id}",
                delay_s=FOLLOWUP_DELAY_S,
                workspace_id=workspace_id,
                message_id=str(message_id),
                attachment_id=attachment_id,
            )
        if self.unsent_assets:
            await enqueue(
                delete_unsent_media,
                delay_s=FOLLOWUP_DELAY_S,
                workspace_id=workspace_id,
                asset_ids=list(self.unsent_assets),
            )
