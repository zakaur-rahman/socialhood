"""Conversation starters, called ice breakers on Instagram (GR-11).

An Instagram account has up to 4 questions that show at the top of a new chat in the mobile app.
Each one is mapped to an automation on the ``ice_breaker`` trigger, or to "answer with AI". The
list is saved here and pushed to Instagram (``set_ice_breakers`` on the adapter), which replaces
whatever is there.

- A starter's payload is ``ib:{id}``. A position keeps its row (and id) when its question or
  mapping changes, so a starter already shown in someone's app keeps working; a removed position
  loses its row, and its old payload then matches nothing.
- Saving always keeps the list; a failed push is kept as the rows' ``sync_error`` (a sentence for
  the member) and ``synced_at`` stays at the last good push. Sync again to retry.
- A tap arrives as a postback (GR-01 stores its payload). ``tapped`` finds the starter it names on
  the account that received it; the DM runtime starts the mapped automation, and an AI starter
  leaves the message to the inbox AI (nothing marks it handled).
- Only Instagram accounts have starters.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.automations import Automation, IceBreaker
from socialhood.models.connections import SocialAccount
from socialhood.platforms.base import IceBreaker as PlatformIceBreaker
from socialhood.platforms.deps import PlatformDeps
from socialhood.platforms.errors import PlatformError
from socialhood.platforms.registry import adapter_for
from socialhood.repositories import automation_runs as runs
from socialhood.repositories import ice_breakers as repo

MAX_STARTERS = 4  # Instagram's limit
QUESTION_CHARS = 80
PAYLOAD_PREFIX = "ib:"
TRIGGER = "ice_breaker"

COPY = {
    "platform": "Conversation starters are for Instagram accounts.",
    "question_empty": "Write the question.",
    "question_long": "Keep the question to 80 characters.",
    "question_twice": "Each question must be different.",
    "automation_missing": "Choose an automation, or answer with AI.",
    "automation_gone": "That automation was not found. Choose it again.",
    "automation_trigger": "Choose an automation that starts from a conversation starter.",
    "automation_account": "Choose an automation that runs on this account.",
    "both": "Choose an automation or answer with AI, not both.",
    "too_many": "Instagram allows up to 4 conversation starters.",
}


@dataclass(frozen=True)
class StarterIn:
    question: str
    automation_id: uuid.UUID | None = None
    answer_with_ai: bool = False


def payload_for(starter: IceBreaker) -> str:
    return f"{PAYLOAD_PREFIX}{starter.id}"


def payload_id(payload: str | None) -> uuid.UUID | None:
    """The starter id a postback payload names, or None when it is not one of ours."""
    if not payload or not payload.startswith(PAYLOAD_PREFIX):
        return None
    try:
        return uuid.UUID(payload[len(PAYLOAD_PREFIX) :])
    except ValueError:
        return None


def is_tap(payload: str | None) -> bool:
    return payload_id(payload) is not None


async def tapped(
    session: AsyncSession, social_account_id: uuid.UUID, payload: str | None
) -> IceBreaker | None:
    """The starter a payload names, if it belongs to this account."""
    starter_id = payload_id(payload)
    if starter_id is None:
        return None
    starter = await repo.get(session, starter_id)
    if starter is None or starter.social_account_id != social_account_id:
        return None
    return starter


async def listing(session: AsyncSession, social_account_id: uuid.UUID) -> list[IceBreaker]:
    return await repo.for_account(session, social_account_id)


async def _problems(
    session: AsyncSession, acct: SocialAccount, items: Sequence[StarterIn]
) -> list[FieldError]:
    errors: list[FieldError] = []
    if acct.platform != "instagram":
        return [FieldError("account_id", COPY["platform"])]
    if len(items) > MAX_STARTERS:
        return [FieldError("items", COPY["too_many"])]
    seen: set[str] = set()
    for i, item in enumerate(items):
        question = item.question.strip()
        if not question:
            errors.append(FieldError(f"items.{i}.question", COPY["question_empty"]))
        elif len(question) > QUESTION_CHARS:
            errors.append(FieldError(f"items.{i}.question", COPY["question_long"]))
        elif question.casefold() in seen:
            errors.append(FieldError(f"items.{i}.question", COPY["question_twice"]))
        seen.add(question.casefold())
        if item.automation_id is not None and item.answer_with_ai:
            errors.append(FieldError(f"items.{i}.automation_id", COPY["both"]))
        elif item.automation_id is None and not item.answer_with_ai:
            errors.append(FieldError(f"items.{i}.automation_id", COPY["automation_missing"]))
        elif item.automation_id is not None:
            automation = await runs.get_automation(session, item.automation_id)
            errors += _automation_problem(i, automation, acct)
    return errors


def _automation_problem(
    index: int, automation: Automation | None, acct: SocialAccount
) -> list[FieldError]:
    field = f"items.{index}.automation_id"
    if automation is None:
        return [FieldError(field, COPY["automation_gone"])]
    if automation.trigger != TRIGGER:
        return [FieldError(field, COPY["automation_trigger"])]
    if automation.social_account_id != acct.id:
        return [FieldError(field, COPY["automation_account"])]
    return []


async def save(
    session: AsyncSession,
    acct: SocialAccount,
    items: Sequence[StarterIn],
    *,
    deps: PlatformDeps,
    now: datetime | None = None,
) -> tuple[list[IceBreaker], str | None]:
    """Replace the account's starters with ``items`` (in order) and push them to Instagram.
    Returns the starters and the sync error (None when the push worked)."""
    errors = await _problems(session, acct, items)
    if errors:
        raise ApiError("validation_error", errors=errors)
    existing = {s.position: s for s in await repo.for_account(session, acct.id)}
    await repo.delete_from(session, acct.id, position=len(items))
    for position, item in enumerate(items):
        row = existing.get(position)
        if row is None:
            row = IceBreaker(social_account_id=acct.id, position=position, question="")
            session.add(row)
        row.question = item.question.strip()
        row.automation_id = item.automation_id
        row.answer_with_ai = item.answer_with_ai
    await session.flush()
    return await sync(session, acct, deps=deps, now=now)


async def sync(
    session: AsyncSession,
    acct: SocialAccount,
    *,
    deps: PlatformDeps,
    now: datetime | None = None,
) -> tuple[list[IceBreaker], str | None]:
    """Push the saved starters to Instagram and record how it went on each row. Returns them and
    the error (a sentence), which an account with no starters has nowhere else to keep."""
    from socialhood.services.automations.actions import platform_error_reason
    from socialhood.services.sending import BLOCKED_STATUSES, readable_error

    now = now or datetime.now(UTC)
    rows = await repo.for_account(session, acct.id)
    error: str | None = None
    if acct.status in BLOCKED_STATUSES:
        error = readable_error("account_needs_reconnect", acct.platform, username=acct.username)
    else:
        try:
            await adapter_for(acct, deps).set_ice_breakers(
                acct, [PlatformIceBreaker(r.question, payload_for(r)) for r in rows]
            )
        except PlatformError as failure:
            error = platform_error_reason(failure, acct)
    for row in rows:
        row.sync_error = error
        if error is None:
            row.synced_at = now
    await session.flush()
    return rows, error
