"""The audit log (GR-19): who sent, edited or deleted what, in the workspace.

- ``record`` adds one row to the caller's session; it never commits, so the row lands with the
  change it describes (or not at all). The handler that knows the member calls it next to its
  commit (C-105).
- Rows hold ids, names and changed field names, never a message body, a secret or a token: the
  detail is filtered and cut to size here, whatever a caller passes.
- The actor's name is kept on the row, so it still reads right after the member is removed.
- Owners and admins read the log, newest first, filtered by member, action and date.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.auth.deps import WorkspaceContext
from socialhood.models.identity import User
from socialhood.models.team import AuditEvent
from socialhood.schemas.team import AuditEvent as AuditEventOut
from socialhood.schemas.team import AuditEventList

MAX_DETAIL_KEYS = 12
MAX_VALUE_CHARS = 200
# Names that never go in: message text, credentials.
_FORBIDDEN_KEYS = re.compile(r"body|text|content|token|secret|password|key|caption", re.IGNORECASE)


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return value[:MAX_VALUE_CHARS]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in list(value)[:20]]
    return str(value)[:MAX_VALUE_CHARS]


def clean_detail(detail: dict[str, Any] | None) -> dict[str, Any]:
    """Keep up to 12 small values and drop any key that could hold a message or a credential."""
    cleaned: dict[str, Any] = {}
    for key, value in (detail or {}).items():
        if _FORBIDDEN_KEYS.search(key) or len(cleaned) >= MAX_DETAIL_KEYS:
            continue
        cleaned[key[:40]] = _clean(value)
    return cleaned


def actor_label(user: User) -> str:
    return (user.name or user.email or "")[:120]


async def record(
    session: AsyncSession,
    ctx: WorkspaceContext,
    action: str,
    target_type: str,
    target_id: uuid.UUID | str | None = None,
    **detail: Any,
) -> None:
    """Add an audit row for ``ctx``'s member. The caller commits."""
    session.add(
        AuditEvent(
            workspace_id=ctx.workspace_id,
            actor_user_id=ctx.user.id,
            actor_label=actor_label(ctx.user),
            action=action[:60],
            target_type=target_type[:40],
            target_id=str(target_id)[:80] if target_id is not None else None,
            detail=clean_detail(detail),
        )
    )


async def list_events(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str | None,
    since: datetime | None,
    until: datetime | None,
    limit: int,
    offset: int,
) -> AuditEventList:
    query = (
        select(AuditEvent, User.name)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    )
    if actor_user_id is not None:
        query = query.where(AuditEvent.actor_user_id == actor_user_id)
    if action is not None:
        query = query.where(AuditEvent.action == action)
    if since is not None:
        query = query.where(AuditEvent.created_at >= since)
    if until is not None:
        query = query.where(AuditEvent.created_at < until)
    rows = (await session.execute(query.limit(limit + 1).offset(offset))).all()
    actions = list(
        await session.scalars(select(AuditEvent.action).distinct().order_by(AuditEvent.action))
    )
    return AuditEventList(
        items=[
            AuditEventOut(
                id=event.id,
                at=event.created_at,
                actor_user_id=event.actor_user_id,
                actor_name=name or event.actor_label,
                action=event.action,
                target_type=event.target_type,
                target_id=event.target_id,
                detail=event.detail,
            )
            for event, name in rows[:limit]
        ],
        has_more=len(rows) > limit,
        actions=actions,
    )
