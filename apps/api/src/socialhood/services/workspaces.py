"""Workspace settings (FR-ACC-03) and the onboarding checklist (FR-ACC-04)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from zoneinfo import available_timezones

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.errors import ApiError, FieldError
from socialhood.models.identity import SLUG_PATTERN, Workspace
from socialhood.repositories import automations, social_accounts, workspaces
from socialhood.schemas.workspaces import Checklist, ChecklistKey, ChecklistStep, WorkspacePatch

_SLUG = re.compile(SLUG_PATTERN)
_LANGUAGE = re.compile(r"^(auto|[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)$")


@lru_cache
def _timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def validate_patch(patch: WorkspacePatch) -> dict[str, Any]:
    """Return the column values to write, or raise validation_error naming each bad field."""
    errors: list[FieldError] = []
    values: dict[str, Any] = {}
    fields = patch.model_fields_set

    if "name" in fields:
        if patch.name is None:
            errors.append(FieldError("name", "Enter a workspace name."))
        else:
            values["name"] = patch.name
    if "slug" in fields:
        if patch.slug is None or not _SLUG.match(patch.slug):
            errors.append(
                FieldError(
                    "slug",
                    "Use 3 to 48 lowercase letters, numbers and hyphens, "
                    "starting and ending with a letter or number.",
                )
            )
        else:
            values["slug"] = patch.slug
    if "timezone" in fields:
        if patch.timezone is None or patch.timezone not in _timezones():
            errors.append(FieldError("timezone", "Choose a timezone from the list."))
        else:
            values["timezone"] = patch.timezone
    if "reply_language" in fields:
        if patch.reply_language is None or not _LANGUAGE.match(patch.reply_language):
            errors.append(FieldError("reply_language", "Choose a language from the list."))
        else:
            values["reply_language"] = patch.reply_language
    if "automation_disclosure" in fields:
        values["automation_disclosure"] = patch.automation_disclosure or None
    if "checklist_dismissed" in fields and patch.checklist_dismissed is not None:
        values["checklist_dismissed_at"] = datetime.now(UTC) if patch.checklist_dismissed else None

    if errors:
        raise ApiError("validation_error", errors=errors)
    return values


async def update_workspace(
    session: AsyncSession, workspace: Workspace, patch: WorkspacePatch
) -> None:
    values = validate_patch(patch)
    try:
        await workspaces.update_settings(session, workspace.id, values)
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        if "uq_workspaces_slug" in str(error.orig):
            raise ApiError(
                "validation_error", errors=[FieldError("slug", "That URL is already taken.")]
            ) from error
        raise
    await session.refresh(workspace)


# Each checklist step is computed from data (FR-ACC-04). Steps whose tables arrive in later
# phases report False until then: add_knowledge and choose_ai_mode (T5.x). See docs/QUESTIONS.md
# Q-008. create_automation is done once an automation has been activated (a draft is not yet an
# automation that answers anyone; pausing or ending it later keeps the step done).
StepCheck = Callable[[AsyncSession, uuid.UUID], Awaitable[bool]]


async def _not_available_yet(session: AsyncSession, workspace_id: uuid.UUID) -> bool:
    return False


async def _account_connected(session: AsyncSession, workspace_id: uuid.UUID) -> bool:
    return await social_accounts.any_live(session)


async def _automation_created(session: AsyncSession, workspace_id: uuid.UUID) -> bool:
    return await automations.any_activated(session)


CHECKLIST: dict[ChecklistKey, StepCheck] = {
    "connect_account": _account_connected,
    "add_knowledge": _not_available_yet,
    "choose_ai_mode": _not_available_yet,
    "create_automation": _automation_created,
}


async def checklist(session: AsyncSession, workspace: Workspace) -> Checklist:
    steps = [
        ChecklistStep(key=key, done=await check(session, workspace.id))
        for key, check in CHECKLIST.items()
    ]
    return Checklist(
        dismissed=workspace.checklist_dismissed_at is not None,
        completed=sum(step.done for step in steps),
        steps=steps,
    )
