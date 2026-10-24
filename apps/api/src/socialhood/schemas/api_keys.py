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
]

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
