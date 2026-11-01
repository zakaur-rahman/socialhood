"""API keys (GR-25): the scope catalogue, a key's record and the one-time view of a new key.
C-167: optional expiry (30, 90 or 365 days) and an IP allowlist (IPs and CIDRs, IPv4 and IPv6)."""

from __future__ import annotations

import ipaddress
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, field_validator

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


MAX_ALLOWED_IPS = 20
IpEntry = Annotated[str, Field(min_length=1, max_length=50)]
ExpiresInDays = Literal[30, 90, 365]


def normalise_ips(values: list[str]) -> list[str]:
    """Each entry as ``ipaddress`` writes it: "203.0.113.7", "10.0.0.0/8", "2001:db8::/32". A
    single address keeps no prefix length. Repeats are dropped; the order is the member's."""
    out: list[str] = []
    for raw in values:
        entry = raw.strip()
        try:
            network = ipaddress.ip_network(entry, strict=True)
        except ValueError as error:
            if "has host bits set" in str(error):
                fixed = ipaddress.ip_network(entry, strict=False)
                raise ValueError(
                    f"{entry} isn't a network address. Did you mean {fixed}?"
                ) from None
            raise ValueError(f"{entry} isn't an IP address or a CIDR range.") from None
        text = (
            str(network.network_address)
            if network.prefixlen == network.max_prefixlen
            else str(network)
        )
        if text not in out:
            out.append(text)
    return out


class ApiKeyCreate(RequestModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[ApiScopeName] = Field(min_length=1, max_length=20)
    # C-167: leave out (or null) for a key that never expires.
    expires_in_days: ExpiresInDays | None = None
    # C-167: the addresses the key may be used from; empty for any.
    allowed_ips: list[IpEntry] = Field(default_factory=list, max_length=MAX_ALLOWED_IPS)

    @field_validator("allowed_ips")
    @classmethod
    def _ips(cls, value: list[str]) -> list[str]:
        return normalise_ips(value)


class ApiKeyUpdate(RequestModel):
    """C-167: only the name and the allowlist change after a key is made; never its scopes."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    allowed_ips: list[IpEntry] | None = Field(default=None, max_length=MAX_ALLOWED_IPS)

    @field_validator("allowed_ips")
    @classmethod
    def _ips(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else normalise_ips(value)


class ApiKey(ResponseModel):
    id: uuid.UUID
    name: str
    key_prefix: str  # the first characters of the key, to tell keys apart
    scopes: list[ApiScopeName]
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    expires_at: datetime | None = None  # C-167: null for a key that never expires
    allowed_ips: list[str] = Field(default_factory=list)  # C-167: empty means any address
    # C-167: the member who made it no longer has an account (a key from before C-167; keys of
    # members who leave are revoked). It still works on the public API, not over MCP.
    made_by_former_member: bool = False


class ApiKeyWithKey(ApiKey):
    """Create only: the key itself, shown this once. Only its hash is kept."""

    key: str


class ApiKeyList(ResponseModel):
    items: list[ApiKey]
    scopes: list[ApiScope]  # every scope a key can carry
    active_limit: int  # how many unrevoked keys a workspace can hold
