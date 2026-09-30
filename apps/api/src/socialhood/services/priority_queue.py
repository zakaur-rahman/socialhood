"""Home's Live Priority Queue (UX-SCR-01 redesign): the few conversations to answer first.

It is ``Overview.priority_queue`` (up to 5), computed with the rest of GET …/overview, so it
refreshes whenever Home does (on new messages, replies, analyses and suggestions; see the web's
lib/realtime/events.ts). It uses the inbox's own definitions (services/conversations.py) so the
queue agrees with the inbox chips:

- **Candidates**: open conversations with a message (archived ones never) that need you
  (``needs_human``, the "Needs you" count) or need a reply (``awaiting_reply``, the "Needs reply"
  view and Home's tile).
- **Excluded**: a needs-reply conversation whose reply window is closed: no free-form reply is
  possible any more (Instagram after 24 h, or 7 days for a person when Human Agent is enabled;
  WhatsApp after 24 h, template only). A conversation that needs you stays, whatever its window.
- **Order**: needs you first; then, in each group, the higher lead score (none last), the
  analysis priority (critical, high, medium, low, none last), the longest wait, and the id.
- **Wait**: ``waiting_since`` is when the customer's unanswered turn began, the first customer
  message after the business last wrote (``last_outbound_at``), or the customer's last message
  when that finds none. ``oldest_waiting_since`` is its minimum over every "Needs reply"
  conversation (Home's Attention badge).
- **has_pending_suggestion**: a pending suggested reply with a draft (it can answer and has
  text); a pending "can't answer" card is not a draft to review.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

from sqlalchemy import ColumnElement, and_, case, func, or_, select, true
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from socialhood.db.tenancy import require_workspace
from socialhood.models.ai import ReplySuggestion, SuggestionStatus
from socialhood.models.inbox import (
    Contact,
    Conversation,
    ConversationStatus,
    Direction,
    Message,
    MessageSource,
)
from socialhood.schemas.inbox import ContactSummary
from socialhood.schemas.workspaces import PriorityConversation
from socialhood.services.inbox_views import preview_text
from socialhood.services.reply_window import HUMAN_AGENT_WINDOW, STANDARD_WINDOW, reply_window

QUEUE_SIZE: Final = 5
PREVIEW_CHARS: Final = 140
PRIORITY_RANK: Final = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _customer(m: type[Message] | Any) -> ColumnElement[bool]:
    return and_(
        m.direction == Direction.INBOUND,
        m.source == MessageSource.CUSTOMER,
        m.deleted_at.is_(None),
    )


def waiting_since() -> ColumnElement[datetime]:
    """The start of the customer's unanswered turn, for the ``Conversation`` row in the query."""
    msg = aliased(Message)
    first_unanswered = (
        select(func.min(msg.occurred_at))
        .where(
            msg.conversation_id == Conversation.id,
            _customer(msg),
            or_(
                Conversation.last_outbound_at.is_(None),
                msg.occurred_at > Conversation.last_outbound_at,
            ),
        )
        .correlate(Conversation)
        .scalar_subquery()
    )
    return func.coalesce(first_unanswered, Conversation.last_inbound_at)


def _waiting() -> list[ColumnElement[bool]]:
    return [
        Conversation.status == ConversationStatus.OPEN,
        Conversation.last_message_at.is_not(None),
    ]


def _window_open(now: datetime, *, human_agent: bool) -> ColumnElement[bool]:
    """services/reply_window.py in SQL: a free-form reply is still possible."""
    standard = Conversation.last_inbound_at > now - STANDARD_WINDOW
    if not human_agent:
        return standard
    return or_(
        standard,
        and_(
            Conversation.platform == "instagram",
            Conversation.last_inbound_at > now - HUMAN_AGENT_WINDOW,
        ),
    )


async def oldest_waiting_since(session: AsyncSession) -> datetime | None:
    """When the longest-waiting "Needs reply" conversation's turn began (Home's Attention)."""
    ws = require_workspace()
    return await session.scalar(
        select(func.min(waiting_since())).where(
            Conversation.workspace_id == ws,
            *_waiting(),
            Conversation.awaiting_reply == true(),
        )
    )


def _clip(text: str) -> str:
    return text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1].rstrip() + "…"


async def priority_queue(
    session: AsyncSession, *, now: datetime, human_agent: bool, limit: int = QUEUE_SIZE
) -> list[PriorityConversation]:
    """Up to ``limit`` conversations to answer first (the module docstring has the rules).
    ``human_agent`` is IG_HUMAN_AGENT_ENABLED: Instagram's 7-day window for a person's reply."""
    ws = require_workspace()
    needs_you = Conversation.needs_human == true()
    draft = (
        select(ReplySuggestion.id)
        .where(
            ReplySuggestion.workspace_id == ws,
            ReplySuggestion.conversation_id == Conversation.id,
            ReplySuggestion.status == SuggestionStatus.PENDING,
            ReplySuggestion.can_answer == true(),
            func.length(func.coalesce(func.btrim(ReplySuggestion.reply_text), "")) > 0,
        )
        .correlate(Conversation)
        .exists()
    )
    waited = waiting_since().label("waiting_since")
    rank = case(
        *((Conversation.priority == name, n) for name, n in PRIORITY_RANK.items()),
        else_=len(PRIORITY_RANK),
    )
    rows = (
        await session.execute(
            select(Conversation, Contact, draft.label("draft"), waited)
            .join(Contact, Contact.id == Conversation.contact_id)
            .where(
                Conversation.workspace_id == ws,
                *_waiting(),
                or_(
                    needs_you,
                    and_(
                        Conversation.awaiting_reply == true(),
                        _window_open(now, human_agent=human_agent),
                    ),
                ),
            )
            .order_by(
                case((needs_you, 0), else_=1),
                Conversation.lead_score.desc().nulls_last(),
                rank,
                waited.asc().nulls_last(),
                Conversation.id,
            )
            .limit(limit)
        )
    ).all()
    if not rows:
        return []

    # Each conversation's newest customer message (not unsent).
    ids = [conv.id for conv, *_ in rows]
    latest = (
        await session.scalars(
            select(Message)
            .where(Message.workspace_id == ws, Message.conversation_id.in_(ids), _customer(Message))
            .order_by(Message.conversation_id, Message.occurred_at.desc(), Message.id.desc())
            .ext(distinct_on(Message.conversation_id))
        )
    ).all()
    newest = {msg.conversation_id: msg for msg in latest}

    queue: list[PriorityConversation] = []
    for conv, contact, has_draft, since in rows:
        msg = newest.get(conv.id)
        window = reply_window(
            conv.platform,
            conv.last_inbound_at,
            human_agent=human_agent and conv.platform == "instagram",
            now=now,
        )
        queue.append(
            PriorityConversation.model_validate(
                {
                    "id": conv.id,
                    "platform": conv.platform,
                    "contact": ContactSummary(
                        id=contact.id,
                        display_name=contact.display_name,
                        username=contact.username,
                        profile_picture_url=contact.profile_picture_url,
                    ),
                    "last_customer_message": (
                        _clip(preview_text(msg.kind, msg.text)) if msg is not None else None
                    ),
                    "last_customer_message_at": msg.occurred_at if msg is not None else None,
                    "waiting_since": since,
                    "needs_you": conv.needs_human,
                    "needs_human_reason": conv.needs_human_reason if conv.needs_human else None,
                    "awaiting_reply": conv.awaiting_reply,
                    "has_pending_suggestion": bool(has_draft),
                    "window_closes_at": (
                        window.closes_at if window.state in ("open", "human_agent") else None
                    ),
                    "lead_score": conv.lead_score,
                    "priority": conv.priority if conv.priority in PRIORITY_RANK else None,
                }
            )
        )
    return queue
