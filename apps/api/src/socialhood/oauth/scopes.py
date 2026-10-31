"""The scopes an AI app can ask for over OAuth, and how the consent page words them (C-165
phase C; 01-design.md §3.4, §3.5).

They are the MCP tools' scopes (the API key catalogue's MCP part, plus ``conversations:read``
and ``automations:read``, which the public API had already). ``messages:send`` isn't offered:
sending waits for R2. ``workspace:read`` is always granted.

Clients also send scopes that aren't about our data: ``offline_access`` (asking for a refresh
token, which we always issue) and ChatGPT's default ``openid email profile``. Those, and any
scope we don't know, are dropped rather than refused, so a client that asks for extra still
connects with what it may have (RFC 6749 §3.3 lets the server grant less than asked).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from socialhood.mcp.http import SCOPES_SUPPORTED
from socialhood.mcp.principal import ALWAYS_GRANTED

OFFLINE_ACCESS = "offline_access"


@dataclass(frozen=True)
class ScopeGroup:
    """One line on the consent page: a checkbox for every scope in it at once."""

    id: str
    label: str
    scopes: tuple[tuple[str, str], ...]  # (scope, what it lets the app do, in plain words)


GROUPS: tuple[ScopeGroup, ...] = (
    ScopeGroup(
        "publishing",
        "Publishing",
        (
            ("posts:read", "See scheduled posts, the calendar, best times and your media library"),
            ("posts:write", "Schedule, change, reschedule and cancel posts"),
            ("media:write", "Upload or import images and videos for posts"),
        ),
    ),
    ScopeGroup(
        "inbox",
        "Inbox",
        (
            ("conversations:read", "Read your inbox conversations"),
            ("replies:draft", "Prepare replies for you to send in Amplychat (it can't send them)"),
        ),
    ),
    ScopeGroup(
        "insights",
        "Comments and analytics",
        (
            ("comments:read", "Read post comments, their topics and sentiment"),
            ("analytics:read", "Read post and account analytics"),
        ),
    ),
    ScopeGroup(
        "knowledge",
        "Knowledge",
        (
            ("knowledge:read", "Search your knowledge base"),
            ("knowledge:write", "Add notes and websites to your knowledge base"),
        ),
    ),
    ScopeGroup(
        "automations",
        "Automations",
        (
            ("automations:read", "See your automations and how they're doing"),
            ("automations:write", "Pause and resume automations"),
        ),
    ),
    ScopeGroup(
        "ask",
        "Ask Amplychat",
        (("ask", "Ask Amplychat's assistant questions (uses your plan's AI credits)"),),
    ),
)

ALWAYS_WORDS = "See the workspace, its plan and time zone, and its connected accounts"

# Every scope a token can carry, workspace:read first.
GRANTABLE: tuple[str, ...] = (
    ALWAYS_GRANTED,
    *(scope for group in GROUPS for scope, _ in group.scopes),
)
# What the authorization server metadata lists: the grantable scopes, and offline_access so
# clients ask for a refresh token (Claude does when it's listed).
AS_SCOPES_SUPPORTED: tuple[str, ...] = (*GRANTABLE, OFFLINE_ACCESS)
# When a client asks for no scope at all: what the protected resource metadata advertises.
DEFAULT_SCOPES: tuple[str, ...] = SCOPES_SUPPORTED


def requested(raw: str | None) -> list[str]:
    """The grantable scopes in a ``scope`` parameter, in catalogue order, workspace:read always
    included. None or empty asks for the default set."""
    asked = set((raw or "").split()) or set(DEFAULT_SCOPES)
    return [scope for scope in GRANTABLE if scope in asked or scope == ALWAYS_GRANTED]


def ordered(scopes: Iterable[str]) -> list[str]:
    chosen = set(scopes) | {ALWAYS_GRANTED}
    return [scope for scope in GRANTABLE if scope in chosen]


def words(scope: str) -> str:
    if scope == ALWAYS_GRANTED:
        return ALWAYS_WORDS
    for group in GROUPS:
        for name, text in group.scopes:
            if name == scope:
                return text
    return scope
