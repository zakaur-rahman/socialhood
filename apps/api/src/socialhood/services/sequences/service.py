"""Sequences: create, change, activate, pause, delete, and the reads for the pages (GR-24).
Nothing here commits; the routes do.

Rules (C-118):
- A sequence belongs to one connected Instagram, WhatsApp or Messenger account, starts on one
  entry event and stops on its stop rules (services/sequences/entry.py). It has 1 to 20 steps; the
  plan caps how many (``sequence_steps``) and how many sequences run at once
  (``active_sequences``), both pending the owner's confirmation.
- Steps and rules can only be changed while the sequence is a draft or paused (409 otherwise), so a
  contact in the middle of it never meets a step that changed under them. Enrolments keep their
  place: a step removed from under one ends it ("completed") when it has no step left.
- A step with a template is for WhatsApp only, and the template must be approved on the number
  now; its name, language, category and body are copied when it is saved, so the preview needs no
  call to Meta. Its variables are mapped as in a broadcast (services/broadcasts/variables).
- Another workspace's tag, broadcast or account is 404 ``not_found``.
- Activating needs a complete sequence on an account that can send, and room in the plan. Pausing
  keeps the people already in it; they carry on when it is activated again. Only a draft or paused
  sequence can be deleted, with its enrolments and history.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import quota_error
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.broadcasts import Broadcast
from socialhood.models.connections import AccountStatus, SocialAccount
from socialhood.models.contacts import LeadStage, Tag
from socialhood.models.inbox import Contact
from socialhood.models.sequences import (
    EnrolmentStatus,
    EntryType,
    Sequence,
    SequenceEnrolment,
    SequenceStatus,
    SequenceStep,
    SequenceStepRun,
    StopReason,
)
from socialhood.platforms.deps import PlatformDeps
from socialhood.repositories import sequences as repo
from socialhood.repositories import social_accounts as accounts
from socialhood.repositories.base import scoped_delete
from socialhood.schemas import sequences as schemas
from socialhood.schemas.broadcasts import VariableOut
from socialhood.services import contacts as contact_service
from socialhood.services import whatsapp_templates
from socialhood.services.automations import actions, render
from socialhood.services.broadcasts import variables as variable_rules
from socialhood.services.leads import STAGE_LABEL
from socialhood.services.saved_replies import fill
from socialhood.services.sending import text_limit_error
from socialhood.services.sequences import rules
from socialhood.services.webhooks import events

KEY_ACTIVE = "active_sequences"
KEY_STEPS = "sequence_steps"
PLATFORMS = ("instagram", "whatsapp", "facebook")
SAMPLE = "Priya"
AUTHENTICATION = "An authentication template is a one-time code. Choose a marketing or utility one."
PAUSE_TO_EDIT = "Pause the sequence to change it. People already in it carry on afterwards."
ENTRY_WORDS = {
    EntryType.CAPTURED: "A lead is captured",
    EntryType.TAGGED: "A tag is added",
    EntryType.BROADCAST_REPLIED: "Someone replies to a broadcast",
    EntryType.LEAD_STAGE: "A lead moves into a stage",
}
CAPTURE_WORDS = {"email": "an email", "phone": "a phone number", "field": "an answer"}


def _invalid(field: str, message: str) -> ApiError:
    return ApiError("validation_error", errors=[FieldError(field, message)])


def _not_found(what: str) -> ApiError:
    return ApiError("not_found", f"That {what} wasn't found.")


# ---------------------------------------------------------------- plan


async def limits(session: AsyncSession) -> tuple[int | None, int | None]:
    """(active sequences, steps per sequence) on the workspace's plan; None: no limit."""
    plan = await current_plan(session)
    active, steps = entitlement(plan, KEY_ACTIVE), entitlement(plan, KEY_STEPS)
    return (None if active is None else int(active)), (None if steps is None else int(steps))


# ---------------------------------------------------------------- resolving a body


class Resolved:
    """A body checked against the workspace: its account, the rows to write for the steps."""

    def __init__(self, account: SocialAccount, steps: list[dict[str, Any]]) -> None:
        self.account = account
        self.steps = steps


async def _tags_exist(session: AsyncSession, ids: list[uuid.UUID]) -> None:
    if not ids:
        return
    found = set((await session.scalars(select(Tag.id).where(Tag.id.in_(ids)))).all())
    if found != set(ids):
        raise _not_found("tag")


async def resolve(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    body: schemas.SequenceBody,
) -> Resolved:
    account = await accounts.get(session, body.social_account_id)
    if account is None:
        raise _not_found("account")
    if body.entry.tag_id is not None:
        await _tags_exist(session, [body.entry.tag_id])
    await _tags_exist(
        session, list(dict.fromkeys([*body.stop.tag_ids, *body.stop.removed_tag_ids]))
    )
    if body.entry.broadcast_id is not None and (
        await session.scalar(select(Broadcast.id).where(Broadcast.id == body.entry.broadcast_id))
        is None
    ):
        raise _not_found("broadcast")
    if account.platform not in PLATFORMS:
        raise _invalid("social_account_id", "Sequences work on Instagram, WhatsApp and Messenger.")
    if body.entry.type == "broadcast_replied" and account.platform != "whatsapp":
        raise _invalid("entry.type", "Only WhatsApp has broadcasts. Choose another start.")
    _, step_limit = await limits(session)
    if step_limit is not None and len(body.steps) > step_limit:
        raise quota_error(
            KEY_STEPS,
            step_limit,
            f"Your plan includes {step_limit} steps in a sequence, and this one has "
            f"{len(body.steps)}. Remove some, or upgrade to add more.",
        )
    approved: list[Any] = []
    if any(step.template_name for step in body.steps):
        if account.platform != "whatsapp":
            index = next(i for i, s in enumerate(body.steps) if s.template_name)
            raise _invalid(f"steps.{index}.template_name", "Only WhatsApp has templates.")
        approved = await whatsapp_templates.approved_templates(session, redis, deps, account)
    field_keys = set((await contact_service._definitions(session)).keys())
    rows = [_step_row(i, step, account, approved, field_keys) for i, step in enumerate(body.steps)]
    return Resolved(account, rows)


def _step_row(
    index: int,
    step: schemas.StepIn,
    account: SocialAccount,
    approved: list[Any],
    field_keys: set[str],
) -> dict[str, Any]:
    where = f"steps.{index}"
    text = (step.text or "").strip() or None
    if text is not None:
        problem = text_limit_error(account.platform, render.longest_render(text))
        if problem:
            raise _invalid(f"{where}.text", problem)
    row: dict[str, Any] = {
        "position": index,
        "delay_seconds": step.delay_seconds,
        "delay_from": "entry" if index == 0 else step.delay_from,
        "text": text,
        "template_name": None,
        "template_language": None,
        "template_category": None,
        "template_body": None,
        "variables": [],
        "respect_hours": step.respect_hours,
    }
    if step.template_name:
        template = next(
            (
                t
                for t in approved
                if t.name == step.template_name and t.language == step.template_language
            ),
            None,
        )
        if template is None:
            raise _invalid(
                f"{where}.template_name",
                "That template isn't approved on this number. Choose another.",
            )
        if template.category == "authentication":
            raise _invalid(f"{where}.template_name", AUTHENTICATION)
        stored = _stored_variables(step.variables)
        found = variable_rules.problems(
            stored, param_count=template.param_count, field_keys=field_keys
        )
        if found:
            raise ApiError(
                "validation_error",
                errors=[FieldError(f"{where}.variables", message) for _, message in found],
            )
        row.update(
            template_name=template.name,
            template_language=template.language,
            template_category=template.category,
            template_body=template.body,
            variables=stored,
        )
    return row


def _stored_variables(items: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        if item.source == "fixed":
            out.append({"source": "fixed", "field": None, "value": item.value, "fallback": None})
        else:
            fallback = (item.fallback or "").strip() or None
            out.append(
                {"source": "field", "field": item.field, "value": None, "fallback": fallback}
            )
    return out


# ---------------------------------------------------------------- create and change


def _apply(row: Sequence, body: schemas.SequenceBody) -> None:
    row.name = body.name
    row.social_account_id = body.social_account_id
    row.entry_type = body.entry.type
    row.entry_tag_id = body.entry.tag_id
    row.entry_broadcast_id = body.entry.broadcast_id
    row.entry_capture_kind = body.entry.capture_kind
    row.entry_stage = body.entry.stage
    row.stop_on_reply = body.stop.on_reply
    row.stop_tag_ids = list(dict.fromkeys(body.stop.tag_ids))
    row.stop_removed_tag_ids = list(dict.fromkeys(body.stop.removed_tag_ids))
    row.stop_stages = list(dict.fromkeys(body.stop.stages))
    row.allow_reentry = body.allow_reentry


async def _write_steps(
    session: AsyncSession, sequence: Sequence, steps: list[dict[str, Any]]
) -> None:
    await session.execute(scoped_delete(SequenceStep, sequence_id=sequence.id))
    session.add_all([SequenceStep(sequence_id=sequence.id, **values) for values in steps])
    await session.flush()


async def create(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    body: schemas.SequenceBody,
    *,
    user_id: uuid.UUID,
) -> schemas.Sequence:
    resolved = await resolve(session, redis, deps, body)
    row = Sequence(status=SequenceStatus.DRAFT, created_by_user_id=user_id)
    _apply(row, body)
    session.add(row)
    await session.flush()
    await _write_steps(session, row, resolved.steps)
    return await get_out(session, row.id)


async def update(
    session: AsyncSession,
    redis: Redis,
    deps: PlatformDeps,
    sequence_id: uuid.UUID,
    body: schemas.SequenceBody,
) -> schemas.Sequence:
    row = await get(session, sequence_id, lock=True)
    resolved = await resolve(session, redis, deps, body)  # a stranger's id is a 404 first
    if row.status == SequenceStatus.ACTIVE:
        raise ApiError("conflict", PAUSE_TO_EDIT)
    if row.social_account_id != body.social_account_id and await _has_enrolments(session, row.id):
        raise _invalid(
            "social_account_id", "People are already in this sequence. Make a new one for it."
        )
    _apply(row, body)
    await _write_steps(session, row, resolved.steps)
    return await get_out(session, row.id)


async def _has_enrolments(session: AsyncSession, sequence_id: uuid.UUID) -> bool:
    return (
        await session.scalar(
            select(SequenceEnrolment.id)
            .where(SequenceEnrolment.sequence_id == sequence_id)
            .limit(1)
        )
    ) is not None


async def get(session: AsyncSession, sequence_id: uuid.UUID, *, lock: bool = False) -> Sequence:
    row = await repo.get(session, sequence_id, lock=lock)
    if row is None:
        raise _not_found("sequence")
    return row


async def delete(session: AsyncSession, sequence_id: uuid.UUID) -> None:
    row = await get(session, sequence_id, lock=True)
    if row.status == SequenceStatus.ACTIVE:
        raise ApiError("conflict", "Pause the sequence before you delete it.")
    await session.execute(scoped_delete(Sequence, id=row.id))


# ---------------------------------------------------------------- activate and pause


def problems_of(row: Sequence, steps: list[SequenceStep]) -> list[str]:
    """Why the sequence can't run, in plain words (a tag or broadcast it names was deleted)."""
    found: list[str] = []
    if row.entry_type == EntryType.TAGGED and row.entry_tag_id is None:
        found.append("The tag that starts this sequence was deleted. Choose another.")
    if not steps:
        found.append("Add at least one step.")
    return found


async def activate(
    session: AsyncSession, sequence_id: uuid.UUID, *, now: datetime
) -> schemas.Sequence:
    row = await get(session, sequence_id, lock=True)
    if row.status == SequenceStatus.ACTIVE:
        return await get_out(session, row.id)
    steps = await repo.steps_of(session, row.id)
    found = problems_of(row, steps)
    if found:
        raise ApiError("validation_error", errors=[FieldError("steps", found[0])])
    account = await accounts.get(session, row.social_account_id)
    if account is None or account.status != AccountStatus.ACTIVE:
        raise ApiError("conflict", "This account needs reconnecting before the sequence can run.")
    active_limit, _ = await limits(session)
    if (
        active_limit is not None
        and await repo.active_count(session, excluding=row.id) >= active_limit
    ):
        raise quota_error(
            KEY_ACTIVE,
            active_limit,
            f"Your plan includes {active_limit} active "
            f"sequence{'' if active_limit == 1 else 's'}. Pause one, or upgrade to run more.",
        )
    row.status = SequenceStatus.ACTIVE
    row.activated_at = row.activated_at or now
    await session.flush()
    return await get_out(session, row.id)


async def pause(session: AsyncSession, sequence_id: uuid.UUID) -> schemas.Sequence:
    row = await get(session, sequence_id, lock=True)
    if row.status == SequenceStatus.ACTIVE:
        row.status = SequenceStatus.PAUSED
        await session.flush()
    return await get_out(session, row.id)


# ---------------------------------------------------------------- reads


def _account_label(acct: SocialAccount | None) -> str | None:
    if acct is None:
        return None
    return acct.display_name or (f"@{acct.username}" if acct.username else None)


async def _names(
    session: AsyncSession, tag_ids: set[uuid.UUID], broadcast_ids: set[uuid.UUID]
) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
    tags = (
        {
            i: n
            for i, n in (
                await session.execute(select(Tag.id, Tag.name).where(Tag.id.in_(tag_ids)))
            ).all()
        }
        if tag_ids
        else {}
    )
    broadcasts = (
        {
            i: n
            for i, n in (
                await session.execute(
                    select(Broadcast.id, Broadcast.name).where(Broadcast.id.in_(broadcast_ids))
                )
            ).all()
        }
        if broadcast_ids
        else {}
    )
    return tags, broadcasts


def entry_label(row: Sequence, tag_name: str | None, broadcast_name: str | None) -> str:
    base = ENTRY_WORDS.get(EntryType(row.entry_type), row.entry_type)
    if row.entry_type == EntryType.TAGGED:
        return f"{base}: {tag_name}" if tag_name else base
    if row.entry_type == EntryType.CAPTURED and row.entry_capture_kind:
        return f"{base}: {CAPTURE_WORDS[row.entry_capture_kind]}"
    if row.entry_type == EntryType.LEAD_STAGE and row.entry_stage:
        return f"{base}: {STAGE_LABEL[LeadStage(row.entry_stage)]}"
    if row.entry_type == EntryType.BROADCAST_REPLIED and broadcast_name:
        return f"{base}: {broadcast_name}"
    return base


def _step_out(step: SequenceStep) -> schemas.StepOut:
    return schemas.StepOut(
        position=step.position,
        delay_seconds=step.delay_seconds,
        delay_from=step.delay_from,
        text=step.text,
        template_name=step.template_name,
        template_language=step.template_language,
        template_category=step.template_category,
        template_body=step.template_body,
        variables=[VariableOut.model_validate(v) for v in step.variables],
        respect_hours=step.respect_hours,
    )


async def _out_many(
    session: AsyncSession, rows: list[Sequence], *, with_steps: bool
) -> list[schemas.Sequence]:
    ids = [r.id for r in rows]
    counts = await repo.enrolment_counts(session, ids)
    step_counts = await repo.step_counts(session, ids)
    steps_by: dict[uuid.UUID, list[SequenceStep]] = {}
    if with_steps:
        for r in rows:
            steps_by[r.id] = await repo.steps_of(session, r.id)
    tags, broadcasts = await _names(
        session,
        {
            t
            for r in rows
            for t in [r.entry_tag_id, *r.stop_tag_ids, *r.stop_removed_tag_ids]
            if t is not None
        },
        {r.entry_broadcast_id for r in rows if r.entry_broadcast_id is not None},
    )
    accts = {a.id: a for a in await accounts.list_all(session)}
    out: list[schemas.Sequence] = []
    for r in rows:
        acct = accts.get(r.social_account_id)
        found = counts.get(r.id, {})
        steps = steps_by.get(r.id)
        count = len(steps) if steps is not None else step_counts.get(r.id, 0)
        out.append(
            schemas.Sequence(
                id=r.id,
                name=r.name,
                status=r.status,
                social_account_id=r.social_account_id,
                account_label=_account_label(acct),
                platform=acct.platform if acct else None,
                entry=schemas.EntryOut(
                    type=r.entry_type,
                    tag_id=r.entry_tag_id,
                    tag_name=tags.get(r.entry_tag_id) if r.entry_tag_id else None,
                    broadcast_id=r.entry_broadcast_id,
                    broadcast_name=(
                        broadcasts.get(r.entry_broadcast_id) if r.entry_broadcast_id else None
                    ),
                    capture_kind=r.entry_capture_kind,
                    stage=r.entry_stage,
                    label=entry_label(
                        r,
                        tags.get(r.entry_tag_id) if r.entry_tag_id else None,
                        broadcasts.get(r.entry_broadcast_id) if r.entry_broadcast_id else None,
                    ),
                ),
                stop=schemas.StopOut(
                    on_reply=r.stop_on_reply,
                    tag_ids=list(r.stop_tag_ids),
                    tag_names=[tags[t] for t in r.stop_tag_ids if t in tags],
                    removed_tag_ids=list(r.stop_removed_tag_ids),
                    removed_tag_names=[tags[t] for t in r.stop_removed_tag_ids if t in tags],
                    stages=list(r.stop_stages),
                ),
                allow_reentry=r.allow_reentry,
                step_count=count,
                steps=[_step_out(s) for s in steps] if steps is not None else None,
                enrolments=schemas.EnrolmentCounts(
                    active=found.get(EnrolmentStatus.ACTIVE, 0),
                    completed=found.get(EnrolmentStatus.COMPLETED, 0),
                    stopped=found.get(EnrolmentStatus.STOPPED, 0),
                ),
                activated_at=r.activated_at,
                created_at=r.created_at,
                updated_at=r.updated_at,
                problems=problems_of(r, steps) if steps is not None else _quick_problems(r, count),
            )
        )
    return out


def _quick_problems(row: Sequence, step_count: int) -> list[str]:
    found: list[str] = []
    if row.entry_type == EntryType.TAGGED and row.entry_tag_id is None:
        found.append("The tag that starts this sequence was deleted. Choose another.")
    if step_count == 0:
        found.append("Add at least one step.")
    return found


async def get_out(session: AsyncSession, sequence_id: uuid.UUID) -> schemas.Sequence:
    row = await get(session, sequence_id)
    return (await _out_many(session, [row], with_steps=True))[0]


async def list_out(session: AsyncSession) -> schemas.SequenceList:
    rows = list(
        (
            await session.scalars(
                select(Sequence).order_by(Sequence.created_at.desc(), Sequence.id)
            )
        ).all()
    )
    active_limit, step_limit = await limits(session)
    return schemas.SequenceList(
        items=await _out_many(session, rows, with_steps=False),
        active=sum(1 for r in rows if r.status == SequenceStatus.ACTIVE),
        active_limit=active_limit,
        step_limit=step_limit,
    )


# ---------------------------------------------------------------- preview


async def preview(
    session: AsyncSession, redis: Redis, deps: PlatformDeps, body: schemas.SequenceBody
) -> schemas.SequencePreview:
    """The steps as a sample contact would meet them in a straight run: when each is due after
    entry, and what it would send. Nothing is saved or sent."""
    resolved = await resolve(session, redis, deps, body)
    platform = resolved.account.platform
    disclosure = await actions.disclosure(session)
    values: dict[str, str | None] = {"first_name": SAMPLE, "name": SAMPLE}
    out: list[schemas.PreviewStep] = []
    elapsed = 0
    for step in resolved.steps:
        elapsed = (
            step["delay_seconds"]
            if step["delay_from"] == "entry"
            else elapsed + step["delay_seconds"]
        )
        text = fill(step["text"], values) if step["text"] else None
        if text:
            text = render.with_disclosure(text, disclosure)
        params = (
            variable_rules.resolve(step["variables"], values) if step["template_name"] else None
        )
        sends: str = "nothing"
        note: str | None = None
        shown: str | None = None
        if platform == "whatsapp":
            # Past the 24-hour window only a template goes; inside it the text does.
            after_window = elapsed >= 24 * 3600
            if step["template_name"] and (after_window or not text):
                sends = "template"
                shown = variable_rules.render_body(step["template_body"] or "", params or [])
                note = "Sent as a template to people who agreed to WhatsApp marketing."
            elif text and not after_window:
                sends, shown = "text", text
            else:
                note = rules.REASONS["window_closed_no_template"]
        elif text:
            sends, shown = "text", text
            if elapsed >= 24 * 3600:
                note = (
                    "Skipped if the person hasn't written in the last 24 hours. "
                    f"{rules.REASONS['window_closed']}"
                )
        out.append(
            schemas.PreviewStep(
                position=step["position"],
                after_seconds=elapsed,
                sends=sends,
                text=shown,
                note=note,
            )
        )
    return schemas.SequencePreview(contact_name=SAMPLE, steps=out, problems=[])


# ---------------------------------------------------------------- enrolments


def _contact_ref(contact: Contact) -> schemas.ContactRef:
    return schemas.ContactRef(
        id=contact.id, display_name=contact.display_name, username=contact.username
    )


def _enrolment_out(
    row: SequenceEnrolment,
    contact: Contact,
    *,
    sequence_name: str | None,
    step_count: int,
    last: SequenceStepRun | None,
) -> schemas.Enrolment:
    return schemas.Enrolment(
        id=row.id,
        sequence_id=row.sequence_id,
        sequence_name=sequence_name,
        contact=_contact_ref(contact),
        status=row.status,
        next_step=row.current_step + 1 if row.status == EnrolmentStatus.ACTIVE else None,
        step_count=step_count,
        next_due_at=row.next_due_at,
        enrolled_at=row.enrolled_at,
        finished_at=row.finished_at,
        entry_event=row.entry_event,
        stop_reason=row.stop_reason,
        stop_text=rules.stop_text(row.stop_reason, row.stop_detail),
        last_run=(
            schemas.LastRun(
                position=last.position + 1,
                status=last.status,
                reason=last.reason,
                at=last.ran_at,
            )
            if last
            else None
        ),
    )


async def _last_runs(
    session: AsyncSession, enrolment_ids: list[uuid.UUID]
) -> dict[uuid.UUID, SequenceStepRun]:
    if not enrolment_ids:
        return {}
    rows = await session.scalars(
        select(SequenceStepRun)
        .where(SequenceStepRun.enrolment_id.in_(enrolment_ids))
        .order_by(SequenceStepRun.ran_at.asc(), SequenceStepRun.position.asc())
    )
    return {r.enrolment_id: r for r in rows.all()}  # the later run replaces the earlier


async def enrolments(
    session: AsyncSession,
    sequence_id: uuid.UUID,
    *,
    status: str | None,
    limit: int,
    offset: int,
) -> schemas.EnrolmentList:
    sequence = await get(session, sequence_id)
    where = [SequenceEnrolment.sequence_id == sequence_id]
    if status is not None:
        where.append(SequenceEnrolment.status == status)
    total = int(
        await session.scalar(select(func.count()).select_from(SequenceEnrolment).where(*where)) or 0
    )
    rows = (
        await session.execute(
            select(SequenceEnrolment, Contact)
            .join(Contact, Contact.id == SequenceEnrolment.contact_id)
            .where(*where)
            .order_by(SequenceEnrolment.enrolled_at.desc(), SequenceEnrolment.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    steps = (await repo.step_counts(session, [sequence_id])).get(sequence_id, 0)
    last = await _last_runs(session, [e.id for e, _ in rows])
    return schemas.EnrolmentList(
        items=[
            _enrolment_out(e, c, sequence_name=sequence.name, step_count=steps, last=last.get(e.id))
            for e, c in rows
        ],
        total=total,
        has_more=offset + len(rows) < total,
    )


def _latest(runs: list[SequenceStepRun] | None) -> SequenceStepRun | None:
    return runs[-1] if runs else None


async def contact_sequences(
    session: AsyncSession, contact_id: uuid.UUID
) -> schemas.ContactSequenceList:
    contact = await repo.contact_of(session, contact_id)
    if contact is None:
        raise _not_found("contact")
    rows = (
        await session.execute(
            select(SequenceEnrolment, Sequence.name)
            .join(Sequence, Sequence.id == SequenceEnrolment.sequence_id)
            .where(SequenceEnrolment.contact_id == contact_id)
            .order_by(SequenceEnrolment.enrolled_at.desc(), SequenceEnrolment.id)
            .limit(20)
        )
    ).all()
    counts = await repo.step_counts(session, list({e.sequence_id for e, _ in rows}))
    runs = (
        list(
            (
                await session.scalars(
                    select(SequenceStepRun)
                    .where(SequenceStepRun.enrolment_id.in_([e.id for e, _ in rows]))
                    .order_by(SequenceStepRun.ran_at, SequenceStepRun.position)
                )
            ).all()
        )
        if rows
        else []
    )
    by_enrolment: dict[uuid.UUID, list[SequenceStepRun]] = {}
    for run in runs:
        by_enrolment.setdefault(run.enrolment_id, []).append(run)
    return schemas.ContactSequenceList(
        items=[
            schemas.ContactSequence(
                enrolment=_enrolment_out(
                    e,
                    contact,
                    sequence_name=name,
                    step_count=counts.get(e.sequence_id, 0),
                    last=_latest(by_enrolment.get(e.id)),
                ),
                runs=[
                    schemas.ContactStepRun(
                        position=r.position + 1,
                        status=r.status,
                        reason=r.reason,
                        at=r.ran_at,
                    )
                    for r in by_enrolment.get(e.id, [])
                ],
            )
            for e, name in rows
        ]
    )


async def stop_enrolment(
    session: AsyncSession, sequence_id: uuid.UUID, enrolment_id: uuid.UUID, *, now: datetime
) -> schemas.Enrolment:
    """Take a contact out of a sequence by hand."""
    sequence = await get(session, sequence_id)
    row = await repo.get_enrolment(session, enrolment_id, lock=True)
    if row is None or row.sequence_id != sequence_id:
        raise _not_found("person in this sequence")
    contact = await repo.contact_of(session, row.contact_id)
    assert contact is not None  # the enrolment cascades with its contact
    if row.status == EnrolmentStatus.ACTIVE:
        row.status = EnrolmentStatus.STOPPED
        row.stop_reason = StopReason.MEMBER
        row.finished_at = now
        row.next_due_at = None
        await session.flush()
        await events.sequence_event(
            session,
            "sequence.stopped",
            contact,
            sequence_id=sequence.id,
            sequence_name=sequence.name,
            enrolment_id=row.id,
            reason=StopReason.MEMBER,
            reason_text=rules.stop_text(StopReason.MEMBER, None),
        )
    steps = (await repo.step_counts(session, [sequence_id])).get(sequence_id, 0)
    last = (await _last_runs(session, [row.id])).get(row.id)
    return _enrolment_out(row, contact, sequence_name=sequence.name, step_count=steps, last=last)
