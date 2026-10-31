"""API keys (GR-25): the scope catalogue, a key's record and the one-time view of a new key."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from socialhood.schemas.common import RequestModel, ResponseModel

ApiScopeName = Literal[
    "contacts:read",
    "contacts:write",
    "tags:read",
    "tags:write",
    "conversations:read",
    "messages:send",
    "automations:read",
    "webhooks:subscribe",
    # C-165: the MCP server's scopes (docs/architecture/mcp/01-design.md §3.4). An AI app
    # connected with this key can use the tools these open; workspace:read is always granted.
    "posts:read",
    "posts:write",
    "media:write",
    "replies:draft",
    "comments:read",
    "analytics:read",
    "knowledge:read",
    "knowledge:write",
    "automations:write",
    "ask",
]

# The scopes only the MCP server's tools use (no /public/v1 route needs them).
MCP_ONLY_SCOPES: tuple[str, ...] = (
    "posts:read",
    "posts:write",
    "media:write",
    "replies:draft",
    "comments:read",
    "analytics:read",
    "knowledge:read",
    "knowledge:write",
    "automations:write",
    "ask",
)

# What each scope allows, in the words the key form and the docs page show.
SCOPE_DESCRIPTIONS: dict[str, str] = {
    "contacts:read": "Read contacts and their custom fields.",
    "contacts:write": "Create contacts and change their email, phone and custom fields.",
    "tags:read": "Read the workspace's tags.",
    "tags:write": "Add and remove tags on contacts.",
    "conversations:read": "Read conversations and their messages.",
    "messages:send": "Send a message in a conversation, inside the platform's reply window.",
    "automations:read": "Read automation runs.",
    "webhooks:subscribe": "Subscribe and unsubscribe REST hooks (what Zapier triggers use).",
    "posts:read": "AI apps: read scheduled posts, the calendar, best times and the media library.",
    "posts:write": "AI apps: create, change, reschedule and cancel scheduled posts.",
    "media:write": "AI apps: upload or import images and videos for posts.",
    "replies:draft": "AI apps: prepare a reply for a member to send in Amplychat (never sent).",
    "comments:read": "AI apps: read post comments, their topics and sentiment.",
    "analytics:read": "AI apps: read post and account analytics.",
    "knowledge:read": "AI apps: search the knowledge base.",
    "knowledge:write": "AI apps: add a text note or a website to the knowledge base.",
    "automations:write": "AI apps: pause and resume automations.",
    "ask": "AI apps: ask Amplychat's own assistant (uses AI credits).",
}


class ApiScope(ResponseModel):
    scope: ApiScopeName
    description: str


class ApiKeyCreate(RequestModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[ApiScopeName] = Field(min_length=1, max_length=20)


class ApiKey(ResponseModel):
    id: uuid.UUID
    name: str
    key_prefix: str  # the first characters of the key, to tell keys apart
    scopes: list[ApiScopeName]
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiKeyWithKey(ApiKey):
    """Create only: the key itself, shown this once. Only its hash is kept."""

    key: str


class ApiKeyList(ResponseModel):
    items: list[ApiKey]
    scopes: list[ApiScope]  # every scope a key can carry
    active_limit: int  # how many unrevoked keys a workspace can hold
