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

from socialhood.billing.dodo import DodoClient, DodoError
from socialhood.errors import ApiError, FieldError
from socialhood.models.identity import SLUG_PATTERN, Workspace
from socialhood.observability.logging import get_logger
from socialhood.repositories import (
    automations,
    knowledge,
    social_accounts,
    subscriptions,
    workspaces,
)
from socialhood.schemas.workspaces import Checklist, ChecklistKey, ChecklistStep, WorkspacePatch

log = get_logger(__name__)

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


async def cancel_dodo_subscription(session: AsyncSession, dodo: DodoClient) -> bool:
    """F-16: deleting a workspace first cancels its Dodo subscription at once (not at the period
    end), so Dodo never charges for a workspace that no longer exists. Runs in the workspace's
    scope before anything is deleted. True when Dodo cancelled one. A subscription Dodo no longer
    has, or refuses to cancel because it has already ended, counts as done; Dodo not answering
    refuses the deletion with 503, so the owner can try again.

    Callers: Clerk's user.deleted (services/clerk_sync, which deletes anyway when Dodo fails and
    logs it). TODO(T9.6): DELETE /v1/w/{wid} (FR-ACC-05, F-16, §2.15) isn't built yet; P9's T9.6
    owns workspace deletion and must call this first, before tokens are destroyed and the
    workspace is marked deleting."""
    sub = await subscriptions.current(session)
    if sub is None or not sub.dodo_subscription_id:
        return False
    try:
        cancelled = await dodo.cancel_now(sub.dodo_subscription_id)
    except DodoError as error:
        if error.retryable or error.status is None:
            log.warning("workspace_delete_dodo_unavailable", status=error.status)
            raise ApiError(
                "service_unavailable",
                "Couldn't cancel the subscription with the payment provider. Try again.",
            ) from error
        log.info("workspace_delete_dodo_nothing_to_cancel", status=error.status)
        return False
    log.info("workspace_delete_dodo_cancelled", status=cancelled.status)
    return True


# Each checklist step is computed from data (FR-ACC-04). Steps whose tables arrive in later
# phases report False until then: choose_ai_mode (T5.x). See docs/QUESTIONS.md Q-008.
# add_knowledge is done once the workspace has any knowledge source (T5.3). create_automation is
# done once an automation has been activated (a draft is not yet an automation that answers
# anyone; pausing or ending it later keeps the step done).
StepCheck = Callable[[AsyncSession, uuid.UUID], Awaitable[bool]]


async def _not_available_yet(session: AsyncSession, workspace_id: uuid.UUID) -> bool:
    return False


async def _account_connected(session: AsyncSession, workspace_id: uuid.UUID) -> bool:
    return await social_accounts.any_live(session)


async def _automation_created(session: AsyncSession, workspace_id: uuid.UUID) -> bool:
    return await automations.any_activated(session)


async def _knowledge_added(session: AsyncSession, workspace_id: uuid.UUID) -> bool:
    return await knowledge.any_source(session)


CHECKLIST: dict[ChecklistKey, StepCheck] = {
    "connect_account": _account_connected,
    "add_knowledge": _knowledge_added,
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
