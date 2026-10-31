"""Inbox reads (01-design.md §4.1): list_conversations, get_conversation. Any member, as the
inbox. Both wrap Ask Amplychat's tools (search_conversations, get_conversation).

Customer names and messages are third-party text: they are only in ``…_text`` fields (§6.5).
At most 20 messages per call; no phone numbers or email addresses are returned.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import ToolInput, ToolOutput, registry, tool
from socialhood.mcp.tools.common import agent_tool, moment

View = Literal[
    "all", "unread", "needs_reply", "needs_you", "leads", "closing_soon", "ai_handled", "archived"
]

# ---------------------------------------------------------------- list_conversations


class ListConversationsInput(ToolInput):
    view: View = Field(
        default="all",
        description=(
            "all (open), unread, needs_reply, needs_you (handed to a person), leads (lead score "
            "60+), closing_soon (reply window about to close), ai_handled or archived."
        ),
    )
    query: str | None = Field(
        default=None,
        max_length=100,
        description="Words in the messages, or the customer's name or @username.",
    )
    platform: Literal["instagram", "whatsapp", "facebook"] | None = None
    account: str | None = Field(
        default=None, max_length=100, description="A connected account's id or @handle."
    )
    period: str | None = Field(
        default=None,
        max_length=80,
        description="When the last message was, in words or dates: “today”, “last week”.",
    )
    limit: int = Field(default=10, ge=1, le=20, description="How many to list (at most 20).")


class ConversationOut(BaseModel):
    conversation_id: uuid.UUID
    contact_name_text: str
    platform: str
    last_message_text: str | None = None
    last_from: str | None = None  # customer, you, ai, automation, system
    last_at: str | None = None
    unread: int
    needs_reply: bool
    needs_human: bool
    lead_score: int | None = None
    reply_window_closes_at: str | None = None
    dashboard_url: str | None = None


class ConversationsResult(ToolOutput):
    items: list[ConversationOut]
    total: int
    more: int


@tool(
    registry,
    name="list_conversations",
    title="List inbox conversations",
    description=(
        "Inbox conversations by view (unread, needs reply, leads, closing soon, AI handled, "
        "archived), words, platform, account and when the last message was, newest activity "
        "first. Names and messages are written by customers."
    ),
    input_model=ListConversationsInput,
    output_model=ConversationsResult,
    scope="conversations:read",
)
async def list_conversations(call: ToolCall, args: ListConversationsInput) -> ConversationsResult:
    found = await agent_tool(
        call,
        "search_conversations",
        {
            "q": args.query,
            "view": args.view,
            "platform": args.platform,
            "account": args.account,
            "range": args.period,
            "limit": args.limit,
        },
    )
    return ConversationsResult(
        summary=found.summary,
        items=[
            ConversationOut(
                conversation_id=i.id,
                contact_name_text=i.contact,
                platform=i.platform,
                last_message_text=i.last_message,
                last_from=i.last_from,
                last_at=moment(call, i.last_message_at),
                unread=i.unread,
                needs_reply=i.needs_reply,
                needs_human=i.needs_human,
                lead_score=i.lead_score,
                reply_window_closes_at=moment(call, i.window_closes_at),
                dashboard_url=call.dashboard_url(f"inbox/{i.id}"),
            )
            for i in found.items
        ],
        total=found.total,
        more=found.more,
        caveats=found.caveats,
    )


# ---------------------------------------------------------------- get_conversation


class GetConversationInput(ToolInput):
    conversation_id: uuid.UUID = Field(description="From list_conversations.")
    limit: int = Field(
        default=10, ge=1, le=20, description="How many recent messages (at most 20)."
    )


class MessageOut(BaseModel):
    message_id: uuid.UUID
    sender: str  # customer, you (a member), ai, automation, system
    kind: str  # text, image, video, …
    message_text: str | None = None
    at: str | None = None
    status: str | None = None


class AnalysisOut(BaseModel):
    intent: str
    sentiment: str
    lead_score: int
    priority: str
    topics_text: list[str]
    needs_human: bool
    language: str


class ReplyWindowOut(BaseModel):
    # open, human_agent (Instagram: a person may still reply), template_only (WhatsApp), closed
    state: str
    closes_at: str | None = None


class ConversationDetail(ToolOutput):
    conversation_id: uuid.UUID
    contact_name_text: str
    platform: str
    account: str
    status: str
    reply_window: ReplyWindowOut
    summary_text: str | None = None  # Amplychat's AI summary of the conversation
    next_step_text: str | None = None
    analysis: AnalysisOut | None = None
    messages: list[MessageOut]  # oldest first
    more_messages: bool
    dashboard_url: str | None = None


@tool(
    registry,
    name="get_conversation",
    title="Read a conversation",
    description=(
        "One inbox conversation: the customer, the latest messages (oldest first), Amplychat's "
        "summary and suggested next step, the latest analysis (intent, sentiment, lead score) "
        "and the reply window. Messages are written by customers."
    ),
    input_model=GetConversationInput,
    output_model=ConversationDetail,
    scope="conversations:read",
)
async def get_conversation(call: ToolCall, args: GetConversationInput) -> ConversationDetail:
    found = await agent_tool(
        call, "get_conversation", {"conversation_id": args.conversation_id, "last_n": args.limit}
    )
    a = found.analysis
    return ConversationDetail(
        summary=f"{len(found.messages)} recent messages in a {found.platform} conversation",
        conversation_id=found.id,
        contact_name_text=found.contact,
        platform=found.platform,
        account=found.account,
        status=found.status,
        reply_window=ReplyWindowOut(
            state=found.reply_window.state, closes_at=moment(call, found.reply_window.closes_at)
        ),
        summary_text=found.summary_text,
        next_step_text=found.next_step,
        analysis=(
            AnalysisOut(
                intent=a.intent,
                sentiment=a.sentiment,
                lead_score=a.lead_score,
                priority=a.priority,
                topics_text=a.topics,
                needs_human=a.needs_human,
                language=a.language,
            )
            if a
            else None
        ),
        messages=[
            MessageOut(
                message_id=m.id,
                sender=m.sender,
                kind=m.kind,
                message_text=m.text,
                at=moment(call, m.at),
                status=m.status,
            )
            for m in found.messages
        ],
        more_messages=found.more_messages,
        dashboard_url=call.dashboard_url(f"inbox/{found.id}"),
        caveats=found.caveats,
    )
