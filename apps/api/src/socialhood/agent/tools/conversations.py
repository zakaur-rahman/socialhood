"""Conversation and customer tools (FR-AGT-02, FR-AGT-03, TA.4; agent-architecture.html §5).

R1:
- search_conversations(q, view, platform, account, range): read; services/conversations (inbox
  search, views, filters; ``range`` is when the last message was). Capped list with how many
  more.
- get_conversation(id, last_n): read; the conversation with its latest messages, summary
  (FR-AI-03) and latest analysis (intent, sentiment, lead score), and its reply window.
- find_contact(name_or_handle) / get_customer(id): read; contacts and their analyses. Several
  matches are listed for the model to ask which one.
- draft_reply(conversation_id, instructions): draft; the suggestion drafting path (TR-AI-06,
  charges reply_suggestion); returns the text for the member, sends nothing. Its action card is
  the conversation's schedule popover with the text and no time (the card kinds of R1 have no
  "reply now" card); a closed reply window is refused before any credits are spent.

Any member (``min_role`` agent), as in the inbox.

R2: send_message(conversation_id, text): high, capability send_replies; sending.queue_outbound.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from socialhood.agent.registry import DraftResult, ToolContext, ToolResult
from socialhood.agent.tools.common import (
    FACEBOOK_NOT_CONNECTED,
    Period,
    PlatformName,
    clip,
    contact_name,
    find_account,
    handle,
    limit_field,
    more_words,
    period,
    quoted,
    ref,
    tool,
    when,
)
from socialhood.ai.metering import QuotaExceeded
from socialhood.ai.provider import AIError
from socialhood.errors import ApiError
from socialhood.models.agent import RiskTier
from socialhood.repositories import inbox, social_accounts
from socialhood.schemas.agent import ScheduleMessageAction, ScheduleMessagePrefill
from socialhood.schemas.inbox import InboxView
from socialhood.services import conversations
from socialhood.services.analysis import latest_analysis
from socialhood.services.comments.queries import CommentQuery, find_comments
from socialhood.services.reply_window import may_send, reply_window
from socialhood.services.scheduled import WINDOW_CLOSED_COPY, send_window
from socialhood.services.suggestions import drafting

VIEW_WORDS: dict[str, str] = {
    "all": "open",
    "unread": "unread",
    "needs_reply": "needs-reply",
    "leads": "lead (score 60+)",
    "closing_soon": "closing-soon",
    "ai_handled": "AI-handled",
    "archived": "archived",
}
SENDERS = {
    "customer": "customer",
    "human": "you",
    "native_app": "you",
    "ai_auto": "ai",
    "automation": "automation",
    "system": "system",
}
Sender = Literal["customer", "you", "ai", "automation", "system"]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- search_conversations


class SearchConversationsInput(_Input):
    q: str | None = Field(
        default=None,
        max_length=100,
        description="Words in the messages, or the customer's name or @username.",
    )
    view: InboxView = Field(
        default="all",
        description=(
            "all (open), unread, needs_reply, leads (lead score 60+), closing_soon (reply window "
            "about to close), ai_handled or archived."
        ),
    )
    platform: PlatformName | None = None
    account: str | None = Field(
        default=None, max_length=100, description="A connected account's @handle or id."
    )
    range: str | None = Field(
        default=None,
        max_length=80,
        description="When the last message was, as the member said it: “today”, “last week”.",
    )
    limit: int = limit_field()


class ConversationItem(BaseModel):
    id: uuid.UUID
    contact: str
    username: str | None = None
    platform: str
    last_message_at: datetime | None = None
    last_message_at_label: str | None = None
    last_message: str | None = None
    last_from: str | None = None  # customer, you, ai, automation, system
    unread: int
    needs_reply: bool
    needs_human: bool
    signal: str | None = None  # needs_you, complaint, closing_soon, lead, negative
    lead_score: int | None = None
    window_closes_at: datetime | None = None


class ConversationsResult(ToolResult):
    period: Period | None = None
    items: list[ConversationItem]
    total: int
    more: int


@tool(
    name="search_conversations",
    label="Searching your conversations",
    description=(
        "Find inbox conversations by words in the messages or the customer's name, narrowed by "
        "a view (unread, needs reply, leads, closing soon, AI handled, archived), platform, "
        "account and when the last message was. Newest activity first."
    ),
    input_model=SearchConversationsInput,
    result_model=ConversationsResult,
)
async def search_conversations(
    ctx: ToolContext, args: SearchConversationsInput
) -> ConversationsResult:
    if args.platform == "facebook":
        return ConversationsResult(
            summary="Facebook isn't connected, so there are no Facebook conversations",
            items=[],
            total=0,
            more=0,
            caveats=[FACEBOOK_NOT_CONNECTED],
        )
    acct = await find_account(ctx, args.account)
    span = period(ctx, args.range, default=None)
    filters = conversations.ListFilters(
        view=args.view,
        platform=args.platform,
        account_id=acct.id if acct else None,
        q=args.q,
        active_from=span.start if span else None,
        active_until=span.end if span else None,
    )
    page = await conversations.list_conversations(
        ctx.session,
        filters,
        cursor=None,
        limit=args.limit,
        ig_human_agent_enabled=ctx.platform.settings.ig_human_agent_enabled,
        now=ctx.now,
    )
    total = await conversations.count_conversations(ctx.session, filters, now=ctx.now)
    items = [
        ConversationItem(
            id=c.id,
            contact=c.contact.display_name
            or (f"@{c.contact.username}" if c.contact.username else "a customer"),
            username=c.contact.username,
            platform=c.platform,
            last_message_at=c.last_message_at,
            last_message_at_label=when(ctx, c.last_message_at),
            last_message=clip(c.last_message_preview, 140),
            last_from=SENDERS.get(c.last_message_source or "", c.last_message_source),
            unread=c.unread_count,
            needs_reply=c.awaiting_reply,
            needs_human=c.needs_human,
            signal=c.signal,
            lead_score=c.lead_score,
            window_closes_at=c.reply_window_closes_at,
        )
        for c in page.items
    ]
    words = f"{VIEW_WORDS[args.view]} conversation"
    summary = f"Found {more_words(total, 0, words)}"
    if args.q:
        summary += f" matching “{clip(args.q, 40)}”"
    if span:
        summary += f", last active {span.label}"
    if total > len(items):
        summary += f" ({len(items)} shown)"
    return ConversationsResult(
        summary=clip(summary, 300) or "Searched your conversations",
        period=Period.of(span) if span else None,
        items=items,
        total=total,
        more=max(total - len(items), 0),
        refs=[ref("conversation", i.id, i.contact) for i in items],
    )


# ---------------------------------------------------------------- get_conversation


class GetConversationInput(_Input):
    conversation_id: uuid.UUID
    last_n: int = Field(default=10, ge=1, le=20, description="How many recent messages.")


class MessageLine(BaseModel):
    id: uuid.UUID
    at: datetime
    at_label: str | None = None
    sender: str  # customer, you, ai, automation, system
    kind: str
    text: str | None = None
    status: str | None = None


class Analysis(BaseModel):
    intent: str
    sentiment: str
    lead_score: int
    priority: str
    topics: list[str]
    needs_human: bool
    language: str


class Window(BaseModel):
    state: str  # open, human_agent (Instagram, human replies only), template_only, closed
    closes_at: datetime | None = None
    closes_at_label: str | None = None


class ConversationResult(ToolResult):
    id: uuid.UUID
    contact_id: uuid.UUID
    contact: str
    username: str | None = None
    platform: str
    account: str
    status: str
    reply_window: Window
    summary_text: str | None = None
    next_step: str | None = None
    analysis: Analysis | None = None
    messages: list[MessageLine]  # oldest first
    more_messages: bool
    scheduled_count: int


@tool(
    name="get_conversation",
    label="Reading the conversation",
    description=(
        "One conversation: the customer, its latest messages (oldest first), the AI summary and "
        "next step, the latest analysis (intent, sentiment, lead score) and the reply window."
    ),
    input_model=GetConversationInput,
    result_model=ConversationResult,
)
async def get_conversation(ctx: ToolContext, args: GetConversationInput) -> ConversationResult:
    conv = await conversations.get_or_404(ctx.session, args.conversation_id)
    detail = await conversations.conversation_detail(
        ctx.session,
        conv,
        ig_human_agent_enabled=ctx.platform.settings.ig_human_agent_enabled,
        now=ctx.now,
    )
    page = await conversations.list_messages(ctx.session, conv, cursor=None, limit=args.last_n)
    name = detail.contact.display_name or (
        f"@{detail.contact.username}" if detail.contact.username else "a customer"
    )
    caveats = []
    if detail.summary is None:
        caveats.append("This conversation has no AI summary yet.")
    if detail.latest_analysis is None:
        caveats.append("No message in this conversation has been analysed yet.")
    latest = detail.latest_analysis
    window = detail.reply_window
    return ConversationResult(
        summary=clip(f"Read the conversation with {name}: {len(page.items)} recent messages", 300)
        or "Read the conversation",
        id=conv.id,
        contact_id=detail.contact.id,
        contact=name,
        username=detail.contact.username,
        platform=conv.platform,
        account=(
            f"@{detail.social_account.username}"
            if detail.social_account.username
            else detail.social_account.display_name or conv.platform
        ),
        status=conv.status,
        reply_window=Window(
            state=window.state,
            closes_at=window.closes_at,
            closes_at_label=when(ctx, window.closes_at),
        ),
        summary_text=detail.summary.text if detail.summary else None,
        next_step=detail.summary.next_step if detail.summary else None,
        analysis=(
            Analysis(
                intent=latest.intent,
                sentiment=latest.sentiment,
                lead_score=latest.lead_score,
                priority=latest.priority,
                topics=latest.topics,
                needs_human=latest.needs_human,
                language=latest.language,
            )
            if latest
            else None
        ),
        messages=[
            MessageLine(
                id=m.id,
                at=m.occurred_at,
                at_label=when(ctx, m.occurred_at),
                sender=SENDERS.get(m.source, m.source),
                kind=m.kind,
                text=clip(m.text),
                status=m.status,
            )
            for m in reversed(page.items)
        ],
        more_messages=page.next_cursor is not None,
        scheduled_count=detail.scheduled_count,
        refs=[ref("conversation", conv.id, name)],
        caveats=caveats,
    )


# ---------------------------------------------------------------- find_contact


class FindContactInput(_Input):
    name_or_handle: str = Field(
        min_length=1, max_length=100, description="Part of the name or @username."
    )
    limit: int = limit_field(default=5, maximum=10)


class ContactMatch(BaseModel):
    contact_id: uuid.UUID
    name: str
    username: str | None = None
    platform: str
    account: str
    conversation_id: uuid.UUID | None = None  # None: no messages yet (for example a commenter)
    last_message_at: datetime | None = None
    lead_score: int | None = None


class FindContactResult(ToolResult):
    matches: list[ContactMatch]
    total: int
    more: int


@tool(
    name="find_contact",
    label="Looking up the contact",
    description=(
        "Find customers by part of their name or @username. Several matches are listed: ask "
        "the member which one before acting on one."
    ),
    input_model=FindContactInput,
    result_model=FindContactResult,
)
async def find_contact(ctx: ToolContext, args: FindContactInput) -> FindContactResult:
    rows, total = await conversations.find_contacts(
        ctx.session, args.name_or_handle, limit=args.limit
    )
    accounts = {a.id: a for a in await social_accounts.list_all(ctx.session)}
    matches = []
    for contact, conv in rows:
        acct = accounts.get(contact.social_account_id)
        matches.append(
            ContactMatch(
                contact_id=contact.id,
                name=contact_name(contact),
                username=contact.username,
                platform=acct.platform if acct else (conv.platform if conv else "instagram"),
                account=handle(acct) if acct else "",
                conversation_id=conv.id if conv else None,
                last_message_at=conv.last_message_at if conv else None,
                lead_score=conv.lead_score if conv else None,
            )
        )
    term = clip(args.name_or_handle, 40)
    if not matches:
        summary = f"No contact matches “{term}”"
    elif total == 1:
        m = matches[0]
        summary = f"Found {m.name} on {m.platform.capitalize()} ({m.account})"
    else:
        summary = f"Found {total} contacts matching “{term}”; ask which one"
    return FindContactResult(
        summary=clip(summary, 300) or "Looked up contacts",
        matches=matches,
        total=total,
        more=max(total - len(matches), 0),
        refs=[ref("conversation", m.conversation_id, m.name) for m in matches if m.conversation_id],
    )


# ---------------------------------------------------------------- get_customer


class GetCustomerInput(_Input):
    contact_id: uuid.UUID


class CustomerComment(BaseModel):
    id: uuid.UUID
    post_id: uuid.UUID
    text: str | None = None
    at: datetime


class CustomerResult(ToolResult):
    contact_id: uuid.UUID
    name: str
    username: str | None = None
    platform: str
    account: str
    first_seen_at: datetime | None = None
    follows_business: bool | None = None
    conversation_id: uuid.UUID | None = None
    conversation_status: str | None = None
    last_message_at: datetime | None = None
    summary_text: str | None = None
    next_step: str | None = None
    analysis: Analysis | None = None
    comment_count: int
    recent_comments: list[CustomerComment]


@tool(
    name="get_customer",
    label="Reading the customer's details",
    description=(
        "A customer (contact) by id: who they are, their conversation's summary and latest "
        "analysis (intent, sentiment, lead score) and their recent comments."
    ),
    input_model=GetCustomerInput,
    result_model=CustomerResult,
)
async def get_customer(ctx: ToolContext, args: GetCustomerInput) -> CustomerResult:
    contact = await inbox.get_contact(ctx.session, args.contact_id)
    if contact is None:
        raise ApiError("not_found", "That customer wasn't found.")
    acct = await social_accounts.get(ctx.session, contact.social_account_id)
    conv = await conversations.contact_conversation(ctx.session, contact.id)
    latest = await latest_analysis(ctx.session, conv.id) if conv is not None else None
    comments = await find_comments(
        ctx.session, CommentQuery(contact_id=contact.id, spam=None), limit=3
    )
    name = contact_name(contact)
    refs = [ref("conversation", conv.id, name)] if conv else []
    refs += [
        ref("comment", r.comment.id, quoted(r.comment.text), r.comment.media_item_id)
        for r in comments.rows
    ]
    caveats = []
    if conv is None:
        caveats.append(f"{name} hasn't messaged you, so there is no conversation.")
    elif latest is None:
        caveats.append("None of their messages has been analysed yet.")
    return CustomerResult(
        summary=clip(
            f"{name}: {'a conversation' if conv else 'no conversation'}, "
            f"{comments.total} comment{'s' if comments.total != 1 else ''}",
            300,
        )
        or name,
        contact_id=contact.id,
        name=name,
        username=contact.username,
        platform=acct.platform if acct else (conv.platform if conv else "instagram"),
        account=handle(acct) if acct else "",
        first_seen_at=contact.first_seen_at or contact.created_at,
        follows_business=contact.follows_business,
        conversation_id=conv.id if conv else None,
        conversation_status=conv.status if conv else None,
        last_message_at=conv.last_message_at if conv else None,
        summary_text=conv.summary if conv else None,
        next_step=conv.summary_next_step if conv else None,
        analysis=(
            Analysis(
                intent=latest.intent,
                sentiment=latest.sentiment,
                lead_score=latest.lead_score,
                priority=latest.priority,
                topics=latest.topics,
                needs_human=latest.needs_human,
                language=latest.language,
            )
            if latest
            else None
        ),
        comment_count=comments.total,
        recent_comments=[
            CustomerComment(
                id=r.comment.id,
                post_id=r.comment.media_item_id,
                text=clip(r.comment.text, 200),
                at=r.comment.commented_at,
            )
            for r in comments.rows
        ],
        refs=refs,
        caveats=caveats,
    )


# ---------------------------------------------------------------- draft_reply


class DraftReplyInput(_Input):
    conversation_id: uuid.UUID
    instructions: str | None = Field(
        default=None,
        max_length=500,
        description="What the reply should say or do, in the member's words.",
    )


class DraftReplyResult(DraftResult):
    conversation_id: uuid.UUID
    contact: str
    can_answer: bool
    text: str | None = None  # the drafted reply; nothing is sent
    missing_info: str | None = None  # what the knowledge base lacks when it can't answer
    sources: list[str] = Field(default_factory=list)  # knowledge sources used, by title
    low_confidence: bool = False


CREDITS_USED_UP = "Your AI credits for this period are used up."
DRAFT_FAILED = "The AI couldn't draft a reply just now. Try again."


@tool(
    name="draft_reply",
    label="Drafting a reply",
    description=(
        "Draft a reply to the customer's latest message the way inbox suggestions are drafted "
        "(brand voice and knowledge base), with the member's instructions. Sends nothing: the "
        "member reviews it. Uses 2 AI credits."
    ),
    input_model=DraftReplyInput,
    result_model=DraftReplyResult,
    tier=RiskTier.DRAFT,
)
async def draft_reply(ctx: ToolContext, args: DraftReplyInput) -> DraftReplyResult:
    conv = await conversations.get_or_404(ctx.session, args.conversation_id)
    contact = await inbox.get_contact(ctx.session, conv.contact_id)
    name = contact_name(contact)
    human_agent = ctx.platform.settings.ig_human_agent_enabled and conv.platform == "instagram"
    window = reply_window(conv.platform, conv.last_inbound_at, human_agent=human_agent, now=ctx.now)
    if not may_send(window, "human"):
        raise ApiError(
            "reply_window_closed",
            f"{name}'s reply window is closed. {WINDOW_CLOSED_COPY.get(conv.platform, '')}".strip(),
        )
    target = await conversations.latest_customer_message(ctx.session, conv.id)
    if target is None:
        raise ApiError("conflict", f"{name} hasn't sent a message to reply to yet.")
    lines = await drafting.conversation_lines(ctx.session, target)
    request = drafting.DraftRequest(
        workspace_id=ctx.workspace_id,
        feature="reply_suggestion",
        platform=conv.platform,
        lines=lines,
        query=await drafting.retrieval_query(ctx.session, target),
        ref_type="agent_run",
        ref_id=ctx.run_id,
        language=await drafting.message_language(ctx.session, target.id),
        instructions=args.instructions,
        quotable=[line.text for line in lines],
    )
    brand = await drafting.load_brand(ctx.session)
    try:
        draft = await drafting.draft(ctx.sessionmaker, request, brand=brand)
    except QuotaExceeded as error:
        raise ApiError("quota_exceeded", CREDITS_USED_UP) from error
    except AIError as error:
        raise ApiError("service_unavailable", DRAFT_FAILED) from error

    allowed = send_window(
        conv, human_agent_enabled=ctx.platform.settings.ig_human_agent_enabled, now=ctx.now
    )
    sources = list(
        dict.fromkeys(c.source_title for c in draft.chunks if c.chunk_id in draft.used_chunk_ids)
    )
    if draft.can_answer and draft.reply:
        note = "Nothing is sent: review it, then schedule it or paste it into the reply box."
        summary = f"Drafted a reply to {name}"
    else:
        note = f"The AI couldn't draft this from your knowledge: {draft.missing_info}."
        summary = f"Couldn't draft a reply to {name} from your knowledge"
    caveats = []
    if window.state == "open" and window.closes_at is not None:
        caveats.append(f"{name}'s reply window closes {when(ctx, window.closes_at)}.")
    elif window.state == "human_agent":
        caveats.append(
            f"The 24-hour window has passed; a person can still reply with the Human Agent tag "
            f"until {when(ctx, window.closes_at)}."
        )
    return DraftReplyResult(
        summary=clip(summary, 300) or "Drafted a reply",
        conversation_id=conv.id,
        contact=name,
        can_answer=draft.can_answer,
        text=draft.reply,
        missing_info=draft.missing_info,
        sources=sources,
        low_confidence=draft.confidence < 0.6,
        refs=[ref("conversation", conv.id, name)],
        caveats=caveats,
        action_card=ScheduleMessageAction(
            kind="schedule_message",
            label="Schedule this reply",
            route=f"inbox/{conv.id}?schedule=1",
            note=clip(note, 200),
            prefill=ScheduleMessagePrefill(
                conversation_id=conv.id,
                text=draft.reply or "",
                send_at=None,
                window_closes_at=allowed.latest if allowed else None,
            ),
        ),
    )
