"""Drafts and knowledge writes (01-design.md §4.1): draft_reply and add_knowledge.

- ``draft_reply`` saves a reply as the conversation's pending suggestion. The inbox shows it like
  any suggestion (a member reads it, edits it and sends it, or dismisses it). **It never sends**:
  there is no send tool in R1, so a customer's message cannot make an AI app message another
  customer (§6.5). The reply window is checked as in the inbox, so a draft that could not be sent
  is refused with the window's own words.
- ``add_knowledge`` adds a note or an FAQ through the knowledge service, counting toward the
  plan's characters of knowledge (402 past it). Ingestion runs in the background after the
  commit.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field

from socialhood.agent.tools.common import contact_name
from socialhood.errors import ApiError, FieldError
from socialhood.mcp.context import ToolCall
from socialhood.mcp.registry import Access, WriteInput, WriteOutput, registry, tool
from socialhood.mcp.tools.common import agent_tool, moment
from socialhood.models.identity import Role
from socialhood.repositories import inbox
from socialhood.schemas.knowledge import KnowledgeSourceCreate
from socialhood.services import conversations
from socialhood.services.knowledge import sources
from socialhood.services.reply_window import may_send, reply_window
from socialhood.services.scheduled import WINDOW_CLOSED_COPY
from socialhood.services.suggestions import service as suggestions

# ---------------------------------------------------------------- draft_reply


class DraftReplyInput(WriteInput):
    conversation_id: uuid.UUID
    text: str | None = Field(
        default=None,
        max_length=4000,
        description="The reply to save, written for the customer. Omit it with use_knowledge to "
        "have Amplychat write one.",
    )
    use_knowledge: bool = Field(
        default=False,
        description="Have Amplychat draft the reply from the knowledge base and brand voice "
        "(uses 2 AI credits).",
    )


class DraftReplyResult(WriteOutput):
    conversation_id: uuid.UUID
    saved: bool  # false when Amplychat couldn't draft one from the knowledge
    draft_id: uuid.UUID | None = None
    reply: str | None = None  # the saved draft
    sent: bool = False  # always false: nothing is sent
    window: str | None = None  # when the reply window closes
    missing_info: str | None = None
    dashboard_url: str | None = None


@tool(
    registry,
    name="draft_reply",
    title="Save a draft reply",
    description=(
        "Save a reply as the draft of an inbox conversation, answering the customer's latest "
        "message. A member opens the conversation in Amplychat, reads it, edits it and sends it. "
        "Nothing is sent to the customer. Either send the reply's text, or ask Amplychat to draft "
        "one from the knowledge base. Refused when the 24-hour reply window has closed."
    ),
    input_model=DraftReplyInput,
    output_model=DraftReplyResult,
    scope="replies:draft",
    access=Access.DRAFT,
)
async def draft_reply(call: ToolCall, args: DraftReplyInput) -> DraftReplyResult:
    if (args.text is None) == (not args.use_knowledge):
        raise ApiError(
            "validation_error",
            errors=[FieldError("text", "Send either text or use_knowledge: true, not both.")],
        )
    conv = await conversations.get_or_404(call.session, args.conversation_id)
    contact = await inbox.get_contact(call.session, conv.contact_id)
    name = contact_name(contact)
    human_agent = call.settings.ig_human_agent_enabled and conv.platform in (
        "instagram",
        "facebook",
    )
    window = reply_window(
        conv.platform, conv.last_inbound_at, human_agent=human_agent, now=call.now
    )
    if not may_send(window, "human"):
        raise ApiError(
            "reply_window_closed",
            f"{name}'s reply window is closed. {WINDOW_CLOSED_COPY.get(conv.platform, '')}".strip(),
        )
    target = await conversations.latest_customer_message(call.session, conv.id)
    if target is None:
        raise ApiError("conflict", f"{name} hasn't sent a message to reply to yet.")
    url = call.dashboard_url(f"inbox/{conv.id}")
    closes = moment(call, window.closes_at) if window.closes_at else None
    text = args.text
    if text is None:
        found = await agent_tool(call, "draft_reply", {"conversation_id": conv.id})
        if not found.can_answer or not found.text:
            return DraftReplyResult(
                summary=f"Couldn't draft a reply to {name} from the knowledge base",
                conversation_id=conv.id,
                saved=False,
                missing_info=found.missing_info,
                window=closes,
                dashboard_url=url,
            )
        text = found.text
    if not text.strip():
        raise ApiError("validation_error", errors=[FieldError("text", "The reply can't be empty.")])
    row = await suggestions.save_draft(call.session, conv, target, text.strip(), source="mcp")
    call.note("reply.drafted", "conversation", conv.id, suggestion_id=str(row.id))
    return DraftReplyResult(
        summary=f"Saved a draft reply to {name}. It is not sent: a member sends it in Amplychat",
        conversation_id=conv.id,
        saved=True,
        draft_id=row.id,
        reply=row.reply_text,
        window=closes,
        dashboard_url=url,
    )


# ---------------------------------------------------------------- add_knowledge


class AddKnowledgeInput(WriteInput):
    type: Literal["text", "faq"] = Field(
        description="text: a note with a title; faq: a customer question and its answer."
    )
    title: str | None = Field(default=None, min_length=1, max_length=120, description="For text.")
    question: str | None = Field(default=None, min_length=1, max_length=500, description="For faq.")
    body: str = Field(
        min_length=1,
        max_length=20000,
        description="The note's text, or the faq's answer. At most 20,000 characters.",
    )


class AddKnowledgeResult(WriteOutput):
    source_id: uuid.UUID
    type: str
    title: str
    status: str  # pending: it is being read into the knowledge base
    characters: int
    characters_used: int
    characters_limit: int | None = None
    dashboard_url: str | None = None


@tool(
    registry,
    name="add_knowledge",
    title="Add to the knowledge base",
    description=(
        "Add a note (title and text) or an FAQ (question and answer) to the knowledge base that "
        "Amplychat's AI replies from. It counts toward the plan's characters of knowledge. It "
        "shows under Knowledge in Amplychat, where it can be edited or removed. It is read in "
        "the background and is searchable within a minute."
    ),
    input_model=AddKnowledgeInput,
    output_model=AddKnowledgeResult,
    scope="knowledge:write",
    access=Access.WRITE,
    min_role=Role.ADMIN,
    dedupe_window_s=600,
)
async def add_knowledge(call: ToolCall, args: AddKnowledgeInput) -> AddKnowledgeResult:
    body = KnowledgeSourceCreate(
        type=args.type, title=args.title, question=args.question, body=args.body
    )
    source = await sources.create(call.session, body, user_id=call.principal.user_id)
    call.note("knowledge.created", "knowledge_source", source.id, type=args.type)

    async def ingest() -> None:
        await sources.enqueue_ingest(source)

    call.after_commit.append(ingest)
    used = await sources.usage(call.session)
    return AddKnowledgeResult(
        summary=f"Added “{source.title}” to the knowledge base",
        source_id=source.id,
        type=source.type,
        title=source.title,
        status=source.status,
        characters=source.char_count,
        characters_used=used.characters_used,
        characters_limit=used.characters_limit,
        dashboard_url=call.dashboard_url("knowledge"),
    )
