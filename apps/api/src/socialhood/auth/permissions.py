"""The permission matrix (GR-19): what each role may do, in one place.

Routes ask for a permission (``auth.deps.require_permission``), never for a role, and the web app
gets the caller's permissions from ``GET /v1/w/{wid}/permissions`` instead of keeping its own
copy. A new write route must declare one: tests/unit/test_permission_routes.py walks the OpenAPI
routes and fails for a write route that does not.

- Agents reply, tag and assign, and use Ask Social Hood.
- Admins also manage automations, knowledge and settings (integrations, webhooks, saved replies,
  business hours, segments, contact fields, templates), connect channels, publish, read the
  audit log, and invite agents.
- Owners also manage billing, members and ownership, and delete the workspace.

Every role has every permission of the roles below it, so the map is built from the tiers.
"""

from __future__ import annotations

from enum import StrEnum

from socialhood.models.identity import Role


class Permission(StrEnum):
    # Agent tier
    SELF = "self.preferences"  # the caller's own notification settings and read marks
    REPLY = "inbox.reply"  # send and schedule messages, reply to comments, AI help in a thread
    TAG = "contacts.tag"  # tag contacts, edit a contact, set a lead stage
    ASSIGN = "conversations.assign"  # change a conversation's status and assignment
    ASK = "ask.use"  # Ask Social Hood
    # Admin tier
    AUTOMATIONS_MANAGE = "automations.manage"
    KNOWLEDGE_MANAGE = "knowledge.manage"
    SETTINGS_MANAGE = "settings.manage"  # workspace, business hours, saved replies, AI, leads
    CONTACTS_MANAGE = "contacts.manage"  # tags, fields, segments and consents
    CHANNELS_MANAGE = "channels.manage"  # connect, change and disconnect social accounts
    INTEGRATIONS_MANAGE = "integrations.manage"  # webhook endpoints
    PUBLISHING_MANAGE = "publishing.manage"  # scheduled posts, hashtag groups, captions
    COMMENTS_DELETE = "comments.delete"
    AUDIT_READ = "audit.read"
    MEMBERS_READ = "members.read"
    MEMBERS_INVITE = "members.invite"  # admins invite agents, owners invite anyone
    # Owner tier
    MEMBERS_MANAGE = "members.manage"  # change a role, remove a member
    OWNERSHIP_TRANSFER = "ownership.transfer"
    BILLING_MANAGE = "billing.manage"
    WORKSPACE_DELETE = "workspace.delete"
    DEV_SANDBOX = "dev.sandbox"


_AGENT = frozenset(
    {Permission.SELF, Permission.REPLY, Permission.TAG, Permission.ASSIGN, Permission.ASK}
)
_ADMIN = _AGENT | {
    Permission.AUTOMATIONS_MANAGE,
    Permission.KNOWLEDGE_MANAGE,
    Permission.SETTINGS_MANAGE,
    Permission.CONTACTS_MANAGE,
    Permission.CHANNELS_MANAGE,
    Permission.INTEGRATIONS_MANAGE,
    Permission.PUBLISHING_MANAGE,
    Permission.COMMENTS_DELETE,
    Permission.AUDIT_READ,
    Permission.MEMBERS_READ,
    Permission.MEMBERS_INVITE,
}
_OWNER = _ADMIN | {
    Permission.MEMBERS_MANAGE,
    Permission.OWNERSHIP_TRANSFER,
    Permission.BILLING_MANAGE,
    Permission.WORKSPACE_DELETE,
    Permission.DEV_SANDBOX,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.AGENT: _AGENT,
    Role.ADMIN: frozenset(_ADMIN),
    Role.OWNER: frozenset(_OWNER),
}

# Roles an inviter may hand out: only owners make admins (decision recorded in C-105).
INVITABLE_ROLES: dict[Role, frozenset[Role]] = {
    Role.AGENT: frozenset(),
    Role.ADMIN: frozenset({Role.AGENT}),
    Role.OWNER: frozenset({Role.AGENT, Role.ADMIN}),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]


def permissions_of(role: Role) -> list[str]:
    """The role's permissions, sorted, for the web app's can() helper."""
    return sorted(p.value for p in ROLE_PERMISSIONS[role])
