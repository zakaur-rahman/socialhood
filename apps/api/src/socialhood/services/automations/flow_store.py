"""Saved flows (GR-03): an automation's flow as the API shows it, saving one, going back to the
message settings, and what activation needs from a flow. Admins only; nothing here commits.

An automation's flow is either compiled from its message settings (``legacy``: every automation
until one is saved as a flow, so the two can never drift apart) or a saved version (``flow``,
automation_flows). Saving:
- refuses a broken graph (422, each step's field) and an image that isn't this workspace's image;
- keeps an active automation complete, as the definition PUT does;
- changes the current version in place until a run has started on it, then makes the next one;
- sets the automation's action from the flow (``ai_reply`` when it has an AI reply), so the AI
  entitlement and the private-reply queue see it as before.
- keeps a flow within the plan's ``flow_steps`` (402 quota_exceeded, PD-5 pending); the same check
  runs on activation, for a flow saved before a downgrade.
Going back to the settings (DELETE) keeps the saved versions for the runs that follow them.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import quota_error
from socialhood.billing.plans import entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.automations import (
    Automation,
    AutomationAction,
    AutomationFlow,
    AutomationStatus,
)
from socialhood.models.contacts import ContactFieldDefinition, Tag
from socialhood.models.media import ResourceType
from socialhood.models.replies import SavedReply
from socialhood.repositories import automations as repo
from socialhood.schemas.flows import AiReplyStep, Flow, FlowDefinition, FlowSource, SendStep
from socialhood.services.automations import definitions, flows, validation

KEEP_COMPLETE_DETAIL = definitions.KEEP_COMPLETE_DETAIL


def step_cap(plan: str) -> int | None:
    """The most steps a flow may have on ``plan`` (None: no plan cap). PD-5, pending."""
    limit = entitlement(plan, "flow_steps")
    return None if limit is None else int(limit)


def check_step_cap(definition: FlowDefinition, plan: str) -> None:
    """Raise 402 quota_exceeded when the flow has more steps than the plan allows."""
    limit = step_cap(plan)
    if limit is not None and len(definition.steps) > limit:
        raise quota_error(
            "flow_steps",
            limit,
            f"Your plan includes {limit} steps in a flow, and this one has "
            f"{len(definition.steps)}. Remove some, or upgrade to add more.",
        )


async def _context_parts(
    session: AsyncSession,
) -> tuple[dict[str, flows.FieldSpec], frozenset[uuid.UUID]]:
    fields = {
        d.key: flows.FieldSpec(d.type, list(d.options or []))
        for d in (await session.scalars(select(ContactFieldDefinition))).all()
    }
    tags = frozenset((await session.scalars(select(Tag.id))).all())
    return fields, tags


async def _saved_replies(session: AsyncSession) -> dict[uuid.UUID, str]:
    """GR-21: the workspace's saved replies, id to body."""
    rows = await session.execute(select(SavedReply.id, SavedReply.body))
    return {reply_id: body for reply_id, body in rows.all()}


async def context(
    session: AsyncSession, automation: Automation, disclosure: str | None
) -> flows.Context:
    fields, tags = await _context_parts(session)
    return flows.Context(
        trigger=automation.trigger,
        disclosure=disclosure,
        fields=fields,
        tag_ids=tags,
        saved_replies=await _saved_replies(session),
    )


async def current(
    session: AsyncSession, automation: Automation
) -> tuple[FlowDefinition, int, FlowSource]:
    """(definition, version, source): version 0 is the flow compiled from the settings."""
    if automation.flow_version is None:
        return flows.compile_legacy(automation), 0, "legacy"
    stored = (await repo.flows_at(session, [(automation.id, automation.flow_version)])).get(
        automation.id
    )
    if stored is None:  # never: the version row is kept while the automation points at it
        return flows.compile_legacy(automation), 0, "legacy"
    return flows.parse(stored.definition), stored.version, "flow"


async def view(
    session: AsyncSession, automation_id: uuid.UUID, *, disclosure: str | None, now: datetime
) -> Flow:
    automation = await definitions.get_or_404(session, automation_id)
    definition, version, source = await current(session, automation)
    found = (await problems(session, [automation], disclosure=disclosure, now=now))[automation.id]
    return Flow(
        automation_id=automation.id,
        version=version,
        source=source,
        definition=definition,
        missing_for_activation=validation.missing_fields(found),
    )


def _action_of(definition: FlowDefinition) -> AutomationAction:
    has_ai = any(isinstance(step, AiReplyStep) for step in definition.steps)
    return AutomationAction.AI_REPLY if has_ai else AutomationAction.SEND_MESSAGE


async def _image_errors(session: AsyncSession, definition: FlowDefinition) -> list[FieldError]:
    errors = []
    for i, step in enumerate(definition.steps):
        if not isinstance(step, SendStep) or step.image_asset_id is None:
            continue
        asset = await repo.get_asset(session, step.image_asset_id)
        where = flows.path(i, "image_asset_id")
        if asset is None:
            errors.append(FieldError(where, "The image wasn't found. Attach it again."))
        elif asset.resource_type != ResourceType.IMAGE:
            errors.append(FieldError(where, "Attach an image."))
    return errors


async def save(
    session: AsyncSession,
    automation_id: uuid.UUID,
    definition: FlowDefinition,
    *,
    user_id: uuid.UUID,
    plan: str,
    disclosure: str | None,
    now: datetime,
) -> Automation:
    automation = await definitions.get_or_404(session, automation_id, for_update=True)
    try:
        flows.graph(definition)
    except flows.FlowError as error:
        raise ApiError("validation_error", errors=error.errors) from error
    check_step_cap(definition, plan)
    if errors := await _image_errors(session, definition):
        raise ApiError("validation_error", errors=errors)
    if automation.status == AutomationStatus.ACTIVE:
        stored = await definitions.stored_definition(session, automation)
        found = validation.activation_errors(
            replace(stored, uses_flow=True), disclosure=disclosure, now=now
        )
        found += flows.activation_errors(definition, await context(session, automation, disclosure))
        if found:
            raise ApiError("validation_error", KEEP_COMPLETE_DETAIL, errors=found)

    data = definition.model_dump(mode="json")
    version = automation.flow_version
    reusable = version is not None and not await repo.runs_on_flow(session, automation.id, version)
    row = (
        (await repo.flows_at(session, [(automation.id, version)])).get(automation.id)
        if (reusable and version is not None)
        else None
    )
    if row is not None:
        row.definition = data
        row.created_by_user_id = user_id
    else:
        version = await repo.latest_flow_version(session, automation.id) + 1
        session.add(
            AutomationFlow(
                automation_id=automation.id,
                version=version,
                definition=data,
                created_by_user_id=user_id,
            )
        )
    automation.flow_version = version
    automation.action = _action_of(definition)
    start = next(s for s in definition.steps if s.id == definition.start)
    if isinstance(start, AiReplyStep):  # the AI reply reads them from the automation (T5.8)
        automation.ai_instructions = start.instructions
    await session.flush()
    return automation


async def use_settings(
    session: AsyncSession, automation_id: uuid.UUID, *, disclosure: str | None, now: datetime
) -> Automation:
    """Back to the flow compiled from the message settings (the action stays the flow's). An
    active automation must be complete on its settings first (422)."""
    automation = await definitions.get_or_404(session, automation_id, for_update=True)
    if automation.flow_version is None:
        return automation
    automation.flow_version = None
    if automation.status == AutomationStatus.ACTIVE:
        stored = await definitions.stored_definition(session, automation)
        found = validation.activation_errors(stored, disclosure=disclosure, now=now)
        if found:
            raise ApiError("validation_error", KEEP_COMPLETE_DETAIL, errors=found)
    await session.flush()
    return automation


async def problems(
    session: AsyncSession,
    automations: Sequence[Automation],
    *,
    disclosure: str | None,
    now: datetime,
    definitions_by_id: dict[uuid.UUID, validation.Definition] | None = None,
) -> dict[uuid.UUID, list[FieldError]]:
    """What each automation still needs to activate: the settings' checks, and for one saved as
    a flow, the flow's own (services/automations/flows)."""
    flowing = [(a.id, a.flow_version) for a in automations if a.flow_version is not None]
    stored = await repo.flows_at(session, flowing)
    parts = await _context_parts(session) if flowing else ({}, frozenset())
    replies = await _saved_replies(session) if flowing else {}
    out: dict[uuid.UUID, list[FieldError]] = {}
    for a in automations:
        d = (definitions_by_id or {}).get(a.id) or await definitions.stored_definition(session, a)
        uses_flow = a.flow_version is not None
        errors = validation.activation_errors(
            replace(d, uses_flow=uses_flow), disclosure=disclosure, now=now
        )
        row = stored.get(a.id)
        if uses_flow and row is not None:
            ctx = flows.Context(
                trigger=a.trigger,
                disclosure=disclosure,
                fields=parts[0],
                tag_ids=parts[1],
                saved_replies=replies,
            )
            errors += flows.activation_errors(flows.parse(row.definition), ctx)
        out[a.id] = errors
    return out
