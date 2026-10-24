"""The visitor's side of the website chat (GR-28): open a session, send, read, give an email.

Everything here runs in the widget's workspace scope (the route sets it), in the caller's
transaction, and never commits except where it says so; the route commits with
``realtime.events.commit_and_publish``.

- **Sessions.** The widget sends its public id and the host of the page it is on. Both are
  checked (the widget exists and is enabled, its workspace is active, the host is allowed) and the
  answer is a signed visitor token for that host (security/widget_tokens.py), the widget's config
  and the visitor's history. Nothing is stored for a visitor who never writes: the contact and
  conversation are made by the first message (or the email form, when it comes first).
- **Messages in** are ordinary inbound messages through ``services/ingest.py``, so analysis,
  suggestions, Auto mode, knowledge, escalation, automations and webhooks work as on Instagram.
  The visitor's ``client_id`` makes a retry idempotent (it becomes the platform message id). A
  visitor is a contact keyed by ``visitor_id``; a new visitor's name is "Visitor" and four
  characters of their id, replaced by the name they type in the email form.
- **Messages out** are the conversation's sent outbound messages. The widget polls for them
  (``poll``): a request that waits until something changes or ``MAX_WAIT_S`` passes, and rereads
  every ``POLL_EVERY_S``. The ``version`` is a fingerprint of the visible messages. No 24-hour
  window applies (services/reply_window.py).
- **Email.** The form validates and normalises the address like a flow's question
  (services/contacts.normalize_email), sets it on the contact with source ``widget``, qualifies a
  new lead (GR-18) and tells webhooks (``contact.updated``). When the widget asks for marketing
  consent and the visitor ticks the box, a granted ``email`` consent is recorded with the exact
  words shown, the page's host and the time as evidence (as GR-14 does for flows). Unticked
  records nothing: silence is not a refusal.
- **Limits.** A new chat counts against the plan's daily cap (``widget_conversations_daily``;
  over it the visitor sees "try again later" and the owner nothing), messages go through
  services/widget/abuse.py, and the per-IP and per-visitor request limits are in the routes.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.billing.plans import current_plan, entitlement
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError, FieldError
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.contacts import ConsentChannel, ConsentSource, ConsentStatus
from socialhood.models.inbox import Contact, Conversation, Direction, Message, MessageSource
from socialhood.models.widget import EmailCapture, WidgetSettings
from socialhood.platforms.events import InboundMessage
from socialhood.realtime import events
from socialhood.repositories import inbox
from socialhood.repositories import ingest as ingest_repo
from socialhood.repositories import social_accounts as accounts
from socialhood.repositories import widget as repo
from socialhood.repositories import workspaces as workspace_repo
from socialhood.schemas.widget import (
    WidgetConfig,
    WidgetEmail,
    WidgetEmailOut,
    WidgetMessage,
    WidgetMessages,
    WidgetSession,
)
from socialhood.security import widget_tokens
from socialhood.security.widget_tokens import VisitorClaim
from socialhood.services import contacts as contacts_service
from socialhood.services import ingest, leads
from socialhood.services.webhooks import events as webhook_events
from socialhood.services.widget import abuse, origin
from socialhood.services.widget.settings import day_start
from socialhood.settings import Settings
from socialhood.webhooks.routing import RoutedAccount, resolve_account

MAX_WAIT_S = 20.0
POLL_EVERY_S = 1.5
NOT_AVAILABLE = "This chat isn't available."
WRONG_SITE = "This chat can't be used on this site."
BUSY = "We're getting a lot of chats right now. Try again in a little while."
EXPIRED = "Your chat session ended. Reload to continue."
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class Widget:
    """A widget that passed the checks for one call: its account, settings and workspace."""

    def __init__(self, acct: SocialAccount, row: WidgetSettings) -> None:
        self.acct = acct
        self.row = row


async def load(session: AsyncSession, routed: RoutedAccount, host: str | None) -> Widget:
    """The widget for ``routed``, or 404 (gone, switched off, workspace deleting) and 403 (a site
    that is not allowed). Runs in the workspace scope."""
    if not await workspace_repo.is_active(session, routed.workspace_id):
        raise ApiError("not_found", NOT_AVAILABLE)
    acct = await accounts.get(session, routed.account_id)
    if acct is None or acct.platform != "web" or acct.status != AccountStatus.ACTIVE:
        raise ApiError("not_found", NOT_AVAILABLE)
    row = await repo.get_settings(session, acct.id)
    if row is None or not row.enabled:
        raise ApiError("not_found", NOT_AVAILABLE)
    if not origin.host_allowed(host, list(row.allowed_domains or [])):
        raise ApiError("forbidden", WRONG_SITE)
    return Widget(acct, row)


async def resolve(session: AsyncSession, widget_id: str) -> RoutedAccount:
    """The one cross-workspace lookup: which workspace owns this public widget id."""
    routed = await resolve_account(session, "web", widget_id)
    if routed is None:
        raise ApiError("not_found", NOT_AVAILABLE)
    return routed


def routed_from(claim: VisitorClaim) -> RoutedAccount:
    return RoutedAccount(account_id=claim.account_id, workspace_id=claim.workspace_id)


def read_claim(token: str | None, settings: Settings) -> VisitorClaim:
    claim = widget_tokens.read_token(token or "", settings.token_encryption_keys)
    if claim is None:
        raise ApiError("unauthorized", EXPIRED)
    return claim


# ---------------------------------------------------------------- views


def author_of(msg: Message) -> str:
    if msg.direction == Direction.INBOUND:
        return "visitor"
    return "team" if msg.source == MessageSource.HUMAN else "assistant"


def message_view(msg: Message) -> WidgetMessage:
    return WidgetMessage(
        id=msg.id,
        author=author_of(msg),
        text=msg.text or "",
        created_at=msg.occurred_at,
    )


def config_of(row: WidgetSettings, *, can_remove_branding: bool, email_known: bool) -> WidgetConfig:
    return WidgetConfig(
        title=row.title,
        greeting=row.greeting,
        accent_color=row.accent_color,
        position=row.position,
        email_capture=row.email_capture,
        email_prompt=row.email_prompt,
        marketing_consent_enabled=row.marketing_consent_enabled,
        marketing_consent_text=row.marketing_consent_text,
        show_branding=row.show_branding or not can_remove_branding,
        email_known=email_known,
    )


async def _thread(
    session: AsyncSession, widget: Widget, visitor: str
) -> tuple[Contact | None, Conversation | None]:
    contact = await ingest_repo.find_contact(session, widget.acct.id, visitor)
    if contact is None:
        return None, None
    return contact, await repo.find_conversation(session, widget.acct.id, contact.id)


async def _messages(session: AsyncSession, conv: Conversation | None) -> WidgetMessages:
    if conv is None:
        return WidgetMessages(messages=[], version="0.0")
    messages = await repo.visible_messages(session, conv.id)
    return WidgetMessages(
        messages=[message_view(m) for m in messages],
        version=await repo.fingerprint(session, conv.id),
    )


# ---------------------------------------------------------------- session


async def open_session(
    session: AsyncSession,
    settings: Settings,
    *,
    widget_id: str,
    host: str,
    visitor_key: str | None,
) -> WidgetSession:
    """Check the widget and the site, then hand the visitor a token, their config and history.
    Runs outside any workspace scope: it finds the workspace and enters its scope itself."""
    clean = origin.clean_host(host)
    routed = await resolve(session, widget_id)
    with workspace_scope(routed.workspace_id):
        widget = await load(session, routed, clean)
        assert clean is not None  # host_allowed refused a missing host
        key = visitor_key if visitor_key and widget_tokens.valid_secret(visitor_key) else None
        key = key or widget_tokens.new_secret()
        visitor = widget_tokens.visitor_id(key)
        contact, conv = await _thread(session, widget, visitor)
        plan = await current_plan(session)
        can_remove = bool(entitlement(plan, "widget_remove_branding"))
        thread = await _messages(session, conv)
        bearer, expires_in = widget_tokens.issue(
            account_id=widget.acct.id,
            workspace_id=routed.workspace_id,
            visitor=visitor,
            host=clean,
            keys=settings.token_encryption_keys,
        )
        return WidgetSession(
            session_key=bearer,
            expires_in=expires_in,
            visitor_key=key,
            config=config_of(
                widget.row,
                can_remove_branding=can_remove,
                email_known=bool(contact and contact.email),
            ),
            messages=thread.messages,
            version=thread.version,
        )


# ---------------------------------------------------------------- messages in


async def send(
    session: AsyncSession,
    redis: Redis,
    claim: VisitorClaim,
    *,
    text: str,
    client_id: uuid.UUID,
    now: datetime | None = None,
) -> WidgetMessages:
    """Store the visitor's message and run the inbox pipeline on it; commits. Returns the thread
    as the visitor now sees it. A repeat of ``client_id`` stores nothing more."""
    now = now or datetime.now(UTC)
    routed = routed_from(claim)
    with workspace_scope(routed.workspace_id):
        widget = await load(session, routed, claim.host)
        contact, conv = await _thread(session, widget, claim.visitor_id)
        platform_message_id = f"w_{client_id.hex}"
        known = await inbox.find_message_by_platform_id(
            session, widget.acct.id, platform_message_id
        )
        if known is None:
            await _admit(session, widget, contact, conv, text, now=now)
            event = InboundMessage(
                account_ref=widget.acct.platform_account_id,
                occurred_at=now,
                contact_ref=claim.visitor_id,
                contact_name=(contact.display_name if contact else None)
                or visitor_name(claim.visitor_id),
                platform_message_id=platform_message_id,
                kind="text",
                text=abuse.clean_text(text),
            )
            await ingest.ingest(session, widget.acct, [event], now=now)
            await events.commit_and_publish(session, redis)
        _, conv = await _thread(session, widget, claim.visitor_id)
        return await _messages(session, conv)


def visitor_name(visitor: str) -> str:
    return f"Visitor {visitor[-4:]}"


async def _admit(
    session: AsyncSession,
    widget: Widget,
    contact: Contact | None,
    conv: Conversation | None,
    text: str,
    *,
    now: datetime,
) -> None:
    """The rules a message must pass before it is stored: the email form when it is required,
    the abuse checks and the plan's daily cap on new chats."""
    if widget.row.email_capture == EmailCapture.REQUIRED and not (contact and contact.email):
        raise ApiError(
            "validation_error",
            "Enter your email address first.",
            errors=[FieldError("email", "Enter your email address first.")],
        )
    recent = await repo.recent_visitor_texts(session, conv.id, limit=3) if conv else []
    reason = abuse.check_message(abuse.clean_text(text), recent)
    if reason is not None:
        raise ApiError("validation_error", reason, errors=[FieldError("text", reason)])
    if conv is None:
        plan = await current_plan(session)
        limit = int(entitlement(plan, "widget_conversations_daily"))
        started = await repo.count_conversations_since(session, widget.acct.id, day_start(now))
        if started >= limit:
            raise ApiError(
                "rate_limited",
                BUSY,
                headers={"Retry-After": str(_seconds_to_midnight(now))},
            )


def _seconds_to_midnight(now: datetime) -> int:
    tomorrow = day_start(now) + timedelta(days=1)
    return max(60, int((tomorrow - now).total_seconds()))


# ---------------------------------------------------------------- messages out


async def poll(
    sessionmaker: async_sessionmaker[AsyncSession],
    claim: VisitorClaim,
    *,
    version: str | None,
    wait_s: float,
) -> WidgetMessages:
    """The visitor's thread, now if it differs from ``version`` and otherwise when it changes,
    for at most ``wait_s`` (the wait is capped at MAX_WAIT_S). The widget and token are checked at
    the start of the call; each pass is one cheap query on a session that is closed again before
    sleeping, so a waiting visitor holds no database connection."""
    routed = routed_from(claim)
    deadline = time.monotonic() + min(max(wait_s, 0.0), MAX_WAIT_S)
    async with sessionmaker() as session:
        with workspace_scope(routed.workspace_id):
            widget = await load(session, routed, claim.host)
            _, conv = await _thread(session, widget, claim.visitor_id)
            current = await _messages(session, conv)
    if version is None or current.version != version or time.monotonic() >= deadline:
        return current
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_EVERY_S)
        async with sessionmaker() as session:
            with workspace_scope(routed.workspace_id):
                if conv is None:
                    _, conv = await _thread(session, widget, claim.visitor_id)
                if conv is None:
                    continue
                latest = await repo.fingerprint(session, conv.id)
                if latest != version:
                    return await _messages(session, conv)
    return current


# ---------------------------------------------------------------- email


def _clean_name(name: str | None) -> str | None:
    cleaned = _CONTROL.sub(" ", name or "").strip()
    return cleaned[:80] or None


async def save_email(
    session: AsyncSession,
    redis: Redis,
    claim: VisitorClaim,
    body: WidgetEmail,
    *,
    now: datetime | None = None,
) -> WidgetEmailOut:
    """Identify the visitor: their email (and name) on their contact, the consent when asked and
    given. Makes the contact if the form came before the first message. Commits."""
    now = now or datetime.now(UTC)
    routed = routed_from(claim)
    with workspace_scope(routed.workspace_id):
        widget = await load(session, routed, claim.host)
        if widget.row.email_capture == EmailCapture.OFF:
            raise ApiError("not_found", NOT_AVAILABLE)
        try:
            email = contacts_service.normalize_email(body.email)
        except ValueError as error:
            raise ApiError(
                "validation_error", str(error), errors=[FieldError("email", str(error))]
            ) from error
        name = _clean_name(body.name)
        contact, created = await ingest_repo.get_or_create_contact(
            session,
            social_account_id=widget.acct.id,
            platform_user_id=claim.visitor_id,
            first_seen_at=now,
            display_name=name or visitor_name(claim.visitor_id),
        )
        changed = ["email"] if contact.email != email else []
        contact.email, contact.email_source, contact.email_verified = email, "widget", False
        if name:
            contact.display_name = name
        if created:
            await webhook_events.contact_created(session, contact, platform="web")
        await session.flush()
        if changed and not created:
            await webhook_events.contact_updated(session, contact, changed)
        await leads.on_capture(session, contact, "email")
        if widget.row.marketing_consent_enabled and body.marketing_consent:
            await contacts_service.record_consent(
                session,
                contact.id,
                channel=ConsentChannel.EMAIL,
                status=ConsentStatus.GRANTED,
                source=ConsentSource.WIDGET,
                evidence={
                    "text": widget.row.marketing_consent_text,
                    "channel": "email",
                    "email": email,
                    "widget_account_id": str(widget.acct.id),
                    "host": claim.host,
                    "at": now.isoformat(),
                },
                at=now,
            )
        await events.commit_and_publish(session, redis)
    return WidgetEmailOut(email_known=True)
