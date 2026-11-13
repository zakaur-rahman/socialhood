"""A member's notification preferences (FR-NOT-03, FR-NOT-04, F-19, UX-SCR-07; T8.6, T8.7):
``workspace_members.notification_prefs``, one per membership (C-049).

The stored shape is models/identity.DEFAULT_NOTIFICATION_PREFS: the weekly digest switch, the
switch for emails about what AI apps changed (01-design.md §6.7), and one push switch per
PushEvent. ``normalize`` reads any stored value as that shape, a missing or malformed key taking
its default (on), so a row written before a switch existed still reads whole. In-app
notifications are always on (FR-NOT-01) and the account and billing emails are not optional
(FR-NOT-02), so neither has a switch.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.models.identity import DEFAULT_NOTIFICATION_PREFS, WorkspaceMember
from socialhood.models.notifications import EMAIL_SWITCH_OF_TYPE, PushEvent

DIGEST = "email_digest"
AI_CHANGES = "email_ai_changes"
PUSH = "push"


def _switch(raw: Mapping[str, Any], key: str) -> bool:
    value = raw.get(key)
    return value if isinstance(value, bool) else bool(DEFAULT_NOTIFICATION_PREFS[key])


def normalize(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """The full preferences shape from a stored value; unknown keys are dropped."""
    raw = raw if isinstance(raw, Mapping) else {}
    push_raw = raw.get(PUSH)
    push_raw = push_raw if isinstance(push_raw, Mapping) else {}
    defaults: Mapping[str, bool] = DEFAULT_NOTIFICATION_PREFS[PUSH]
    return {
        DIGEST: _switch(raw, DIGEST),
        AI_CHANGES: _switch(raw, AI_CHANGES),
        PUSH: {
            event.value: (
                push_raw[event.value]
                if isinstance(push_raw.get(event.value), bool)
                else bool(defaults[event.value])
            )
            for event in PushEvent
        },
    }


def pushes(prefs: Mapping[str, Any] | None, event: PushEvent | str) -> bool:
    """Whether the member's switch for this push event is on."""
    return bool(normalize(prefs)[PUSH][PushEvent(event).value])


def wants_digest(prefs: Mapping[str, Any] | None) -> bool:
    return bool(normalize(prefs)[DIGEST])


def emails(prefs: Mapping[str, Any] | None, type: str) -> bool:
    """Whether the member gets this notification type's email: yes, unless the type has a
    switch (EMAIL_SWITCH_OF_TYPE) and theirs is off."""
    switch = EMAIL_SWITCH_OF_TYPE.get(type)
    return switch is None or bool(normalize(prefs)[switch])


async def member(session: AsyncSession, user_id: uuid.UUID) -> WorkspaceMember | None:
    """The user's membership in the current workspace."""
    return (
        await session.scalars(select(WorkspaceMember).where(WorkspaceMember.user_id == user_id))
    ).one_or_none()


async def load(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any] | None:
    """The member's preferences in the current workspace; None when not a member."""
    row = await member(session, user_id)
    return normalize(row.notification_prefs) if row is not None else None


async def save(
    session: AsyncSession, user_id: uuid.UUID, prefs: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Replace the member's preferences (the whole object); None when not a member. The caller
    commits."""
    row = await member(session, user_id)
    if row is None:
        return None
    row.notification_prefs = normalize(prefs)  # a new dict, so the change is flushed
    await session.flush()
    return normalize(row.notification_prefs)


async def turn_off_digest(session: AsyncSession, user_id: uuid.UUID) -> bool:
    """The digest's one-click unsubscribe; False when not a member. Idempotent; the push
    switches are left as they are. The caller commits."""
    row = await member(session, user_id)
    if row is None:
        return False
    prefs = normalize(row.notification_prefs)
    if prefs[DIGEST]:
        row.notification_prefs = {**prefs, DIGEST: False}
        await session.flush()
    return True
