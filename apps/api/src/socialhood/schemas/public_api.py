"""Schemas only the public API (/public/v1, GR-25, GR-26) uses. Everything else it returns is the
app's own schema (contacts, tags, conversations, messages, automation runs)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel
from socialhood.schemas.inbox import ContactDetail, ConversationListItem, ReplyWindow


class PublicKeyInfo(ResponseModel):
    """Whose key it is and what it can do: how a tool tests a key and labels the connection."""

    workspace_id: uuid.UUID
    workspace_name: str
    key_id: uuid.UUID
    scopes: list[str]


class PublicAccount(ResponseModel):
    """A connected account: the ``account_id`` a new contact is added to."""

    id: uuid.UUID
    platform: Literal["instagram", "whatsapp"]
    display_name: str | None = None
    username: str | None = None
    phone_number: str | None = None
    status: Literal["active", "needs_reconnect", "disconnected", "error"]


class PublicAccountList(ResponseModel):
    items: list[PublicAccount]


class PublicConversation(ConversationListItem):
    """A conversation without the app's AI and suggestion detail."""

    contact: ContactDetail
    reply_window: ReplyWindow
    last_inbound_at: datetime | None = None


class PublicSendMessage(RequestModel):
    """A text message. Send the same ``client_id`` again to retry without sending twice."""

    text: str = Field(min_length=1, max_length=4096)
    client_id: uuid.UUID | None = None
