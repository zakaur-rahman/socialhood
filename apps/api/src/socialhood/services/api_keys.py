"""A workspace's API keys (GR-25): make, list and revoke. Owners and admins; nothing here commits.

- A key is "shk_" and 43 random characters. It is shown once, in the create response; the row
  keeps its SHA-256 (the key is long and random, so a plain hash is enough) and its first
  twelve characters, so a member can tell keys apart in the list.
- Keys carry scopes (schemas/api_keys.py). A key never gains scopes: make another.
- Public API access is Business and Agency (C-172, C-174; the ``public_api`` entitlement):
  making a key on Free or Creator is 402. Listing and revoking stay open, so a workspace that
  downgraded can still clean up.
- Revoking sets ``revoked_at`` and deletes the REST hooks the key subscribed (services/
  api_hooks.py): a key that is off sends nothing. Revoking again changes nothing.
- A workspace holds at most ``ACTIVE_LIMIT`` unrevoked keys.
- A key's Activity is its latest tool calls over /mcp, from the MCP audit (``mcp_tool_calls``,
  kept 90 days): tool, outcome and time, never arguments or results.

C-167:
- A key may expire (``expires_in_days``: 30, 90 or 365; never by default) and may be limited to
  a list of IPs and CIDRs. The name and that list can be edited later (``update``); scopes can't.
- When a member leaves (removed, or their account deleted), every unrevoked key they made in
  that workspace is revoked in the same transaction (``revoke_for_member``), one audit row each.
  Moving ownership revokes nothing.
- A key found in a public GitHub repository is revoked too (services/secret_scanning.py).
- Revocations and edits write ``api_key.revoked`` / ``api_key.updated`` audit rows; a revocation
  nobody clicked says why (``reason``).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.deps import WorkspaceContext
from socialhood.billing.entitlements import check_entitlement
from socialhood.db.tenancy import require_workspace
from socialhood.errors import ApiError
from socialhood.models.api_keys import ApiKey
from socialhood.models.identity import Workspace
from socialhood.models.integrations import WebhookEndpoint
from socialhood.models.mcp import McpToolCall
from socialhood.models.notifications import NotificationType, Severity
from socialhood.repositories import workspaces
from socialhood.repositories.base import scoped_delete
from socialhood.schemas.ai_connections import AiConnectionCall
from socialhood.schemas.api_keys import (
    SCOPE_DESCRIPTIONS,
    ApiKeyCreate,
    ApiKeyList,
    ApiKeyUpdate,
    ApiKeyWithKey,
    ApiScope,
)
from socialhood.schemas.api_keys import ApiKey as ApiKeyOut
from socialhood.services import audit, notifications

KEY_PREFIX = "shk_"
PREFIX_CHARS = 12  # shown in the list: "shk_" and eight characters
ACTIVE_LIMIT = 20
ACTIVITY = 50  # the latest tool calls a key's Activity shows, as for a connected app
REVOKED = "That API key has been revoked."
# What the audit log says about a revocation nobody clicked.
REASON_REMOVED = "revoked: the member who made it was removed from the workspace"
REASON_ACCOUNT_DELETED = "revoked: the member who made it deleted their account"
REASON_LEAKED = "revoked: found in a public GitHub repository"
EXPIRY_NOTICE = timedelta(days=7)  # owners and admins are told this long before a key expires
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def generate_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def looks_like_key(value: str) -> bool:
    """Cheap shape check before any database work."""
    return value.startswith(KEY_PREFIX) and 20 <= len(value) <= 100


def key_out(key: ApiKey) -> ApiKeyOut:
    out = ApiKeyOut.model_validate(key)
    out.made_by_former_member = key.created_by_user_id is None
    return out


def scope_catalogue() -> list[ApiScope]:
    return [ApiScope(scope=s, description=d) for s, d in SCOPE_DESCRIPTIONS.items()]


async def list_keys(session: AsyncSession) -> ApiKeyList:
    rows = await session.scalars(select(ApiKey).order_by(ApiKey.created_at.desc(), ApiKey.id))
    return ApiKeyList(
        items=[key_out(k) for k in rows.all()],
        scopes=scope_catalogue(),
        active_limit=ACTIVE_LIMIT,
    )


async def create(
    session: AsyncSession, body: ApiKeyCreate, *, user_id: uuid.UUID | None, now: datetime
) -> ApiKeyWithKey:
    await check_entitlement(session, "public_api")
    # Two creations at once would both count 19 and leave 21.
    await workspaces.lock_limit(session, "api_keys", require_workspace())
    active = await session.scalar(
        select(func.count()).select_from(ApiKey).where(ApiKey.revoked_at.is_(None))
    )
    if (active or 0) >= ACTIVE_LIMIT:
        raise ApiError(
            "conflict", f"You can have up to {ACTIVE_LIMIT} active API keys. Revoke one first."
        )
    key = generate_key()
    row = ApiKey(
        name=body.name,
        key_prefix=key[:PREFIX_CHARS],
        key_hash=hash_key(key),
        scopes=list(dict.fromkeys(body.scopes)),
        created_by_user_id=user_id,
        allowed_ips=body.allowed_ips,
        expires_at=now + timedelta(days=body.expires_in_days) if body.expires_in_days else None,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return ApiKeyWithKey(**key_out(row).model_dump(), key=key)


async def _locked(session: AsyncSession, key_id: uuid.UUID) -> ApiKey:
    row = await session.get(ApiKey, key_id, with_for_update=True)
    if row is None:
        raise ApiError("not_found", "That API key wasn't found.")
    return row


async def activity(session: AsyncSession, key_id: uuid.UUID) -> list[AiConnectionCall]:
    """The key's latest tool calls over /mcp (tool, outcome and time), revoked keys included;
    404 for a key that isn't this workspace's."""
    if await session.get(ApiKey, key_id) is None:
        raise ApiError("not_found", "That API key wasn't found.")
    rows = await session.scalars(
        select(McpToolCall)
        .where(McpToolCall.api_key_id == key_id)
        .order_by(McpToolCall.created_at.desc())
        .limit(ACTIVITY)
    )
    return [AiConnectionCall.model_validate(row) for row in rows.all()]


async def update(
    session: AsyncSession, ctx: WorkspaceContext, key_id: uuid.UUID, body: ApiKeyUpdate
) -> ApiKeyOut:
    """Rename a key or change its allowlist (an empty list allows any address). A revoked key
    can't be edited (409)."""
    row = await _locked(session, key_id)
    if row.revoked_at is not None:
        raise ApiError("conflict", REVOKED)
    changed: list[str] = []
    if body.name is not None and body.name != row.name:
        row.name = body.name
        changed.append("name")
    if body.allowed_ips is not None and body.allowed_ips != list(row.allowed_ips):
        row.allowed_ips = body.allowed_ips
        changed.append("allowed_ips")
    if changed:
        await audit.record(
            session,
            ctx,
            "api_key.updated",
            "api_key",
            row.id,
            name=row.name,
            prefix=row.key_prefix,
            fields=changed,
            allowed_ips=list(row.allowed_ips),
        )
        await session.flush()
        await session.refresh(row)
    return key_out(row)


async def revoke(session: AsyncSession, key_id: uuid.UUID, *, now: datetime) -> ApiKeyOut:
    row = await _locked(session, key_id)
    if row.revoked_at is None:
        row.revoked_at = now
        await session.execute(scoped_delete(WebhookEndpoint, api_key_id=row.id))
        await session.flush()
    return key_out(row)


def audit_revoked(
    session: AsyncSession, key: ApiKey, *, reason: str, label: str, **detail: str
) -> None:
    """The audit row of a revocation nobody clicked; ``label`` says who or what did it."""
    audit.record_system(
        session,
        label,
        "api_key.revoked",
        "api_key",
        key.id,
        name=key.name,
        prefix=key.key_prefix,
        reason=reason,
        **detail,
    )


async def active_keys_by(session: AsyncSession, user_id: uuid.UUID) -> Sequence[ApiKey]:
    """The unrevoked keys ``user_id`` made in the current workspace."""
    rows = await session.scalars(
        select(ApiKey)
        .where(ApiKey.created_by_user_id == user_id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at, ApiKey.id)
    )
    return rows.all()


async def active_counts_by_member(session: AsyncSession) -> dict[uuid.UUID, int]:
    """How many unrevoked keys each member made in the current workspace (the members page says
    how many a removal revokes)."""
    rows = await session.execute(
        select(ApiKey.created_by_user_id, func.count())
        .where(ApiKey.revoked_at.is_(None), ApiKey.created_by_user_id.is_not(None))
        .group_by(ApiKey.created_by_user_id)
    )
    return {user_id: int(n) for user_id, n in rows.all() if user_id is not None}


async def revoke_for_member(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    now: datetime,
    reason: str,
    ctx: WorkspaceContext | None = None,
    label: str = "Amplychat",
) -> int:
    """Revoke every unrevoked key ``user_id`` made in the current workspace, one audit row each:
    as ``ctx``'s member when a member did it (a removal), else as ``label``. Returns how many.
    The caller commits."""
    keys = await active_keys_by(session, user_id)
    for key in keys:
        await revoke(session, key.id, now=now)
        if ctx is not None:
            await audit.record(
                session,
                ctx,
                "api_key.revoked",
                "api_key",
                key.id,
                name=key.name,
                prefix=key.key_prefix,
                reason=reason,
            )
        else:
            audit_revoked(session, key, reason=reason, label=label)
    if keys:
        await session.flush()  # in this workspace's scope, where the audit rows belong
    return len(keys)


def day_label(at: datetime, timezone: str) -> str:
    """ "12 Jan 2027", in the workspace's time zone (the web list's style)."""
    try:
        local = at.astimezone(ZoneInfo(timezone))
    except (KeyError, ValueError):
        local = at
    return f"{local.day} {MONTHS[local.month - 1]} {local.year}"


async def notify_expiring(session: AsyncSession, key_id: uuid.UUID, *, now: datetime) -> bool:
    """Tell the current workspace's owners and admins that the key expires soon, once per key
    (``expiry_notified_at``; the dedupe key holds too if a run repeats). In the app only. False
    when there is nothing to say: revoked, already told, or no expiry. The caller commits."""
    row = await session.get(ApiKey, key_id, with_for_update=True)
    if (
        row is None
        or row.revoked_at is not None
        or row.expiry_notified_at is not None
        or row.expires_at is None
        or row.expires_at <= now
    ):
        return False
    workspace = await session.get(Workspace, require_workspace())
    day = day_label(row.expires_at, workspace.timezone if workspace else "UTC")
    await notifications.notify_admins(
        session,
        type=NotificationType.API_KEY_EXPIRING.value,
        severity=Severity.WARNING.value,
        title=f"API key “{row.name}” expires on {day}"[:200],
        body=(
            f"Anything using {row.key_prefix}… stops working then. Make a new key in Settings, "
            "API keys and swap it in before that day."
        ),
        link="/settings/api-keys",
        dedupe_key=f"api-key-expiring:{row.id}",
    )
    row.expiry_notified_at = now
    await session.flush()
    return True
