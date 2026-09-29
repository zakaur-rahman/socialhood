"""The inbox read side (T3.5; FR-INB-01, 02, 04, 05; TR-PL-04; TR-API-04) and the changes a
member makes to a conversation: read, unread, archive and the AI mode override.

List: open conversations, newest activity first, or one view of them: unread (unread_count > 0),
needs reply (awaiting_reply), leads (lead score >= 60), AI handled (the AI has replied in it and
it does not need a human), or archived. Views, the platform and account filters and search all
run in SQL before the page is cut, so a busy account never pushes another's conversations off a
page. Search matches the contact's name or username (the trigram index) and message text
(search_tsv, 'simple' config, each word as a prefix, for search as you type).

Cursors are opaque base64url of the sort key and id (TR-API-04), so ties never skip rows.
"""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    ColumnElement,
    ColumnExpressionArgument,
    DateTime,
    Text,
    Uuid,
    cast,
    func,
    literal,
    literal_column,
    or_,
    select,
    true,
    tuple_,
)
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.identity import User
from socialhood.models.inbox import (
    Contact,
    Conversation,
    ConversationStatus,
    Message,
    MessageSource,
    ScheduledMessage,
    ScheduledStatus,
)
from socialhood.realtime import events
from socialhood.repositories import automation_runs, inbox, social_accounts
from socialhood.repositories import conversations as writes
from socialhood.schemas.inbox import (
    AutomationRef,
    ContactDetail,
    ConversationAccount,
    ConversationAi,
    ConversationList,
    ConversationPatch,
    ConversationSummary,
    InboxCounts,
    InboxView,
    MessageList,
)
from socialhood.schemas.inbox import Conversation as ConversationOut
from socialhood.services import read_receipts
from socialhood.services.inbox_views import LEAD_SCORE, human_agent_allowed, list_item, message_out
from socialhood.services.reply_window import reply_window

CURSOR_INVALID = "This cursor is not valid. Load the list again."

_TIMESTAMP = DateTime(timezone=True)
_UUID = Uuid()
_SIMPLE: ColumnElement[Any] = literal_column("'simple'::regconfig")
_EMPTY: ColumnElement[str] = literal_column("''")
_SPACE: ColumnElement[str] = literal_column("' '")
# The expression of ix_contacts_search_trgm, spelled the same way so the planner can use it.
CONTACT_TEXT = (
    func.coalesce(Contact.display_name, _EMPTY)
    .op("||")(_SPACE)
    .op("||")(func.coalesce(Contact.username, _EMPTY))
)


# ---------------------------------------------------------------- cursors (TR-API-04)


def encode_cursor(at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps([at.isoformat(), str(row_id)], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        at, row_id = json.loads(raw)
        parsed = datetime.fromisoformat(at), uuid.UUID(row_id)
    except (ValueError, TypeError) as error:  # binascii and JSON errors are ValueErrors
        raise _cursor_error() from error
    if parsed[0].tzinfo is None:
        raise _cursor_error()
    return parsed


def _cursor_error() -> ApiError:
    return ApiError("validation_error", errors=[FieldError("cursor", CURSOR_INVALID)])


def _before(
    at: ColumnExpressionArgument[Any], row_id: ColumnExpressionArgument[Any], cursor: str
) -> ColumnElement[bool]:
    """Rows after the cursor in (at DESC, id DESC) order, as one row comparison (index-friendly)."""
    cursor_at, cursor_id = decode_cursor(cursor)
    return tuple_(at, row_id) < tuple_(literal(cursor_at, _TIMESTAMP), literal(cursor_id, _UUID))


# ---------------------------------------------------------------- lookups


async def get_or_404(session: AsyncSession, conversation_id: uuid.UUID) -> Conversation:
    conv = await inbox.get_conversation(session, conversation_id)
    if conv is None:
        raise ApiError("not_found")
    return conv


async def _human_agent(session: AsyncSession, conv: Conversation, *, enabled: bool) -> bool:
    acct = await social_accounts.get(session, conv.social_account_id)
    return acct is not None and human_agent_allowed(acct, ig_human_agent_enabled=enabled)


# ---------------------------------------------------------------- list (FR-INB-01)


@dataclass(frozen=True)
class ListFilters:
    view: InboxView = "all"
    platform: str | None = None
    account_id: uuid.UUID | None = None
    q: str | None = None


def _view_filter(view: InboxView) -> list[ColumnElement[bool]]:
    if view == "archived":
        return [Conversation.status == ConversationStatus.ARCHIVED]
    where = [Conversation.status == ConversationStatus.OPEN]
    if view == "unread":
        where.append(Conversation.unread_count > 0)
    elif view == "needs_reply":
        where.append(Conversation.awaiting_reply == true())
    elif view == "leads":
        where.append(Conversation.lead_score >= LEAD_SCORE)
    elif view == "ai_handled":
        where.append(Conversation.needs_human != true())
        where.append(
            select(Message.id)
            .where(
                Message.conversation_id == Conversation.id,
                Message.source == MessageSource.AI_AUTO,
            )
            .exists()
        )
    return where


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def prefix_tsquery(term: str) -> ColumnElement[Any]:
    """``term`` parsed like the indexed text (plainto_tsquery), with every word as a prefix."""
    words = cast(func.plainto_tsquery(_SIMPLE, term), Text)
    return func.to_tsquery(_SIMPLE, func.regexp_replace(words, r"'(\s|$)", r"':*\1", "g"))


def _search_filter(q: str) -> ColumnElement[bool] | None:
    term = " ".join(q.split())
    if not term:
        return None
    by_text = select(Message.conversation_id).where(
        Message.search_tsv.bool_op("@@")(prefix_tsquery(term))
    )
    matches = [Conversation.id.in_(by_text)]
    name = term.lstrip("@")
    if name:
        by_contact = select(Contact.id).where(
            CONTACT_TEXT.ilike(f"%{_escape_like(name)}%", escape="\\")
        )
        matches.append(Conversation.contact_id.in_(by_contact))
    return or_(*matches)


def _filters(filters: ListFilters) -> list[ColumnElement[bool]]:
    where = [Conversation.last_message_at.is_not(None), *_view_filter(filters.view)]
    if filters.platform is not None:
        where.append(Conversation.platform == filters.platform)
    if filters.account_id is not None:
        where.append(Conversation.social_account_id == filters.account_id)
    if filters.q:
        search = _search_filter(filters.q)
        if search is not None:
            where.append(search)
    return where


async def list_conversations(
    session: AsyncSession,
    filters: ListFilters,
    *,
    cursor: str | None,
    limit: int,
    ig_human_agent_enabled: bool,
    now: datetime,
) -> ConversationList:
    query = (
        select(Conversation, Contact)
        .join(Contact, Contact.id == Conversation.contact_id)
        .where(*_filters(filters))
        .order_by(Conversation.last_message_at.desc(), Conversation.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        query = query.where(_before(Conversation.last_message_at, Conversation.id, cursor))
    rows = (await session.execute(query)).all()
    page = rows[:limit]
    human_agent = (
        {
            acct.id
            for acct in await social_accounts.list_all(session)
            if human_agent_allowed(acct, ig_human_agent_enabled=True)
        }
        if ig_human_agent_enabled
        else set()
    )
    last = page[-1][0] if page else None
    return ConversationList(
        items=[
            list_item(conv, contact, now=now, human_agent=conv.social_account_id in human_agent)
            for conv, contact in page
        ],
        next_cursor=(
            encode_cursor(last.last_message_at, last.id)
            if last is not None and last.last_message_at is not None and len(rows) > limit
            else None
        ),
    )


async def inbox_counts(session: AsyncSession) -> InboxCounts:
    """The Inbox nav badge (unread conversations, FR-INB-04) and the view chips."""
    unread, needs_reply, needs_you = (
        await session.execute(
            select(
                func.count().filter(Conversation.unread_count > 0),
                func.count().filter(Conversation.awaiting_reply == true()),
                func.count().filter(Conversation.needs_human == true()),
            )
            .select_from(Conversation)
            .where(
                Conversation.status == ConversationStatus.OPEN,
                Conversation.last_message_at.is_not(None),
            )
        )
    ).one()
    return InboxCounts(unread=unread, needs_reply=needs_reply, needs_you=needs_you)


# ---------------------------------------------------------------- detail (§5.10, TR-PL-04)


async def conversation_detail(
    session: AsyncSession, conv: Conversation, *, ig_human_agent_enabled: bool, now: datetime
) -> ConversationOut:
    contact = await inbox.get_contact(session, conv.contact_id)
    acct = await social_accounts.get(session, conv.social_account_id)
    if contact is None or acct is None:  # pragma: no cover - foreign keys cascade
        raise ApiError("not_found")
    human_agent = human_agent_allowed(acct, ig_human_agent_enabled=ig_human_agent_enabled)
    scheduled = await session.scalar(
        select(func.count())
        .select_from(ScheduledMessage)
        .where(
            ScheduledMessage.conversation_id == conv.id,
            ScheduledMessage.status == ScheduledStatus.SCHEDULED,
        )
    )
    paused = conv.ai_paused_until if conv.ai_paused_until and conv.ai_paused_until > now else None
    return ConversationOut.model_validate(
        {
            **list_item(conv, contact, now=now, human_agent=human_agent).model_dump(),
            "contact": ContactDetail(
                id=contact.id,
                display_name=contact.display_name,
                username=contact.username,
                profile_picture_url=contact.profile_picture_url,
                first_seen_at=contact.first_seen_at or contact.created_at,
                platform_user_id=contact.platform_user_id,
            ),
            "reply_window": reply_window(
                conv.platform, conv.last_inbound_at, human_agent=human_agent, now=now
            ),
            "ai": ConversationAi(
                effective_mode=conv.ai_mode_override or acct.ai_mode,
                override=conv.ai_mode_override,
                paused_until=paused,
            ),
            "latest_analysis": None,  # P5
            "pending_suggestion": None,  # P5
            "summary": (
                ConversationSummary(
                    text=conv.summary,
                    next_step=conv.summary_next_step,
                    updated_at=conv.summary_updated_at,
                )
                if conv.summary and conv.summary_updated_at
                else None
            ),
            "social_account": ConversationAccount(
                id=acct.id,
                username=acct.username,
                display_name=acct.display_name,
                status=acct.status,
            ),
            "scheduled_count": int(scheduled or 0),
            "last_inbound_at": conv.last_inbound_at,
        }
    )


# ---------------------------------------------------------------- messages (FR-INB-02)


async def list_messages(
    session: AsyncSession, conv: Conversation, *, cursor: str | None, limit: int
) -> MessageList:
    """Newest first; ``next_cursor`` loads the page of older messages."""
    query = (
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.occurred_at.desc(), Message.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        query = query.where(_before(Message.occurred_at, Message.id, cursor))
    rows = list((await session.scalars(query)).all())
    page = rows[:limit]
    names = await _user_names(session, {m.sent_by_user_id for m in page if m.sent_by_user_id})
    automations = await automation_runs.automation_names(
        session, [m.automation_run_id for m in page if m.automation_run_id]
    )

    def automation(m: Message) -> AutomationRef | None:
        found = automations.get(m.automation_run_id) if m.automation_run_id else None
        return AutomationRef(id=found[0], name=found[1]) if found else None

    return MessageList(
        items=[
            message_out(
                m,
                sent_by_name=names.get(m.sent_by_user_id) if m.sent_by_user_id else None,
                automation=automation(m),
            )
            for m in page
        ],
        next_cursor=(
            encode_cursor(page[-1].occurred_at, page[-1].id) if len(rows) > limit else None
        ),
    )


async def _user_names(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str | None]:
    if not ids:
        return {}
    rows = await session.execute(select(User.id, User.name).where(User.id.in_(ids)))
    return {user_id: name for user_id, name in rows}


# ---------------------------------------------------------------- changes (FR-INB-04, 05)
#
# Each returns whether the conversation changed. A change is written and conversation.updated
# is queued (TR-RT-03); the caller commits with realtime.events.commit_and_publish.


async def update_conversation(
    session: AsyncSession,
    conv: Conversation,
    patch: ConversationPatch,
    *,
    ig_human_agent_enabled: bool,
    now: datetime,
) -> bool:
    """Archive or unarchive; set or clear the AI mode override (auto needs the plan's ai_modes)."""
    if patch.clear_ai_mode_override and patch.ai_mode_override is not None:
        raise ApiError(
            "validation_error",
            errors=[FieldError("clear_ai_mode_override", "Set an override or clear it, not both.")],
        )
    values: dict[str, Any] = {}
    if patch.status is not None and patch.status != conv.status:
        values["status"] = patch.status
    if patch.ai_mode_override is not None:
        if patch.ai_mode_override not in entitlement(await current_plan(session), "ai_modes"):
            raise ApiError("entitlement_required", "Auto mode is part of Pro.")
        if patch.ai_mode_override != conv.ai_mode_override:
            values["ai_mode_override"] = patch.ai_mode_override
    elif patch.clear_ai_mode_override and conv.ai_mode_override is not None:
        values["ai_mode_override"] = None
    if not values or not await writes.update(session, conv.id, **values):
        return False
    await _changed(session, conv, ig_human_agent_enabled=ig_human_agent_enabled, now=now)
    return True


async def mark_read(
    session: AsyncSession, conv: Conversation, *, ig_human_agent_enabled: bool, now: datetime
) -> bool:
    """unread_count = 0, then the platform read receipt (read_receipts, T3.6)."""
    if not await writes.mark_read(session, conv.id):
        return False
    await _changed(session, conv, ig_human_agent_enabled=ig_human_agent_enabled, now=now)
    await read_receipts.after_marked_read(session, conv)
    return True


async def mark_unread(
    session: AsyncSession, conv: Conversation, *, ig_human_agent_enabled: bool, now: datetime
) -> bool:
    """unread_count = max(1, unread_count)."""
    if not await writes.mark_unread(session, conv.id):
        return False
    await _changed(session, conv, ig_human_agent_enabled=ig_human_agent_enabled, now=now)
    return True


async def _changed(
    session: AsyncSession, conv: Conversation, *, ig_human_agent_enabled: bool, now: datetime
) -> None:
    await session.refresh(conv)
    human_agent = await _human_agent(session, conv, enabled=ig_human_agent_enabled)
    await events.queue_conversation(session, conv, now=now, human_agent=human_agent)
