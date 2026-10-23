"""Flow runs (GR-03): an automation saved as a flow runs its steps here. One on its message
settings runs as before (runtime, answers, nudge); its flow is the same, compiled
(services/automations/flows.compile_legacy).

A flow run keeps its flow version (``flow_version``), the step it's at (``step_id``) and its state
(``flow_state``), and logs each step it reaches in automation_run_steps.

- **Entry.** The trigger is matched as before (keywords, posts, cooldown, the read-only account):
  - a DM's run goes through its first steps at once (``start_dm``): actions, branches and splits,
    then its first message, sent like any automation DM;
  - a comment's flow starts with its message (flows.activation_errors), the private reply, which
    the account's queue sends (``entry_message``);
  - an AI reply as the first step runs the AI reply as before (its instructions are the step's).
- **After a message is delivered** (``after_message``, wherever a send's result is decided): a
  message with quick replies, or a question, waits for the answer (``replying``, the run
  ``awaiting_reply``); any other goes on to its next step in the continue job.
- **An answer** (``find_answer``, then ``answer``, before keyword matching, as tap first does):
  - a tapped quick reply names the run, the step and the option (``shf:{run}:{step}:{n}``); a tap
    on a step the run has left is handled and sends nothing;
  - typed text answers the contact's newest run waiting on this account for a question, or for a
    message whose typed answers go somewhere (``on_text``);
  - a question's answer is checked (an email, a phone, or what its field takes) and saved; one that
    doesn't fit gets the retry prompt until the tries run out, then the flow goes to ``on_skip``.
  The answering message is marked ``automation_handled``: no keyword automation or AI reply runs
  on it.
- **The continue job** (``resume``, ``run_automation("flow", run_id)``) runs steps until the next
  message, a delay or the end. A branch on following the account reads it fresh from the platform
  outside any transaction. A delay schedules the job for its end. A message the 24-hour window no
  longer allows (the send pipeline refuses it) fails its step and ends the run.

Every message of a run has a stable client id (its step), so a retried job sends nothing twice;
and a run visits each step once (flows have no loops), so its step log has one row per step.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.errors import ApiError
from socialhood.models.automations import (
    Automation,
    AutomationRun,
    AutomationRunStep,
    FlowState,
    RunResult,
    StepStatus,
)
from socialhood.models.connections import SocialAccount
from socialhood.models.contacts import ContactFieldDefinition, ContactTag, Tag
from socialhood.models.inbox import Contact, Conversation, Message, MessageStatus
from socialhood.observability.logging import get_logger
from socialhood.platforms.base import OutboundButton, OutboundMessage, OutboundQuickReply
from socialhood.platforms.deps import PlatformDeps
from socialhood.realtime import events
from socialhood.repositories import automation_runs as runs
from socialhood.repositories import automations as automations_repo
from socialhood.repositories import inbox
from socialhood.repositories import ingest as rows
from socialhood.repositories import social_accounts as accounts
from socialhood.repositories.base import scoped_delete
from socialhood.schemas.flows import (
    ActionStep,
    AddTag,
    AiReplyStep,
    AskStep,
    BranchStep,
    ContactCondition,
    DelayStep,
    EndStep,
    FieldCondition,
    FlowButton,
    FollowsCondition,
    HandOff,
    LeadScoreCondition,
    LeadStageCondition,
    NotifyTeam,
    PlatformCondition,
    RandomizeStep,
    RemoveTag,
    SendStep,
    SetField,
    Step,
    TagCondition,
)
from socialhood.services import leads
from socialhood.services.automations import actions, flows, render, results
from socialhood.services.webhooks import events as webhook_events

log = get_logger(__name__)

PAYLOAD_PREFIX = "shf:"  # a flow quick reply's payload: "shf:{run_id}:{step_id}:{option}"
ANSWER_WINDOW = timedelta(days=7)  # as tap first (services/automations/answers)
MAX_STEPS = 60  # steps one pass may run (a flow has at most 50)
RETRY_COPY = {
    "email": "That doesn't look like an email address. Could you send it again?",
    "phone": "That doesn't look like a phone number. Could you send it with the country code?",
    "text": "Sorry, I didn't catch that. Could you send it again?",
}
FLOW_SOURCE = "flow"  # contacts.email_source and phone_source for an answer to a question
HAND_OFF_BODY = "An automation handed this conversation to you."
NOTIFY_BODY = "An automation flagged this conversation."


def is_flow_run(run: AutomationRun) -> bool:
    return run.flow_version is not None and run.flow_state is not None


# ---------------------------------------------------------------- payloads


def payload(run_id: uuid.UUID, step_id: str, option: int) -> str:
    return f"{PAYLOAD_PREFIX}{run_id}:{step_id}:{option}"


@dataclass(frozen=True)
class Tap:
    run_id: uuid.UUID
    step_id: str
    option: int


def parse_payload(value: str | None) -> Tap | None:
    if not value or not value.startswith(PAYLOAD_PREFIX):
        return None
    parts = value[len(PAYLOAD_PREFIX) :].split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        return None
    try:
        return Tap(uuid.UUID(parts[0]), parts[1], int(parts[2]))
    except ValueError:
        return None


# ---------------------------------------------------------------- loading


async def graph_for(session: AsyncSession, automation_id: uuid.UUID, version: int) -> flows.Graph:
    stored = (await automations_repo.flows_at(session, [(automation_id, version)]))[automation_id]
    return flows.graph(flows.parse(stored.definition))


@dataclass
class Scene:
    """What a pass over a run's steps reads and writes, loaded once."""

    run: AutomationRun
    automation: Automation
    graph: flows.Graph
    conv: Conversation
    contact: Contact
    acct: SocialAccount
    disclosure: str | None
    follows: bool | None = None  # read for this pass (``resume``)
    follows_read: bool = False
    published: list[Message] = field(default_factory=list)


async def _scene(session: AsyncSession, run: AutomationRun) -> Scene | None:
    automation = await runs.get_automation(session, run.automation_id)
    if automation is None or run.flow_version is None or run.conversation_id is None:
        return None
    conv = await inbox.get_conversation(session, run.conversation_id)
    contact = await inbox.get_contact(session, conv.contact_id) if conv else None
    acct = await accounts.get(session, conv.social_account_id) if conv else None
    if conv is None or contact is None or acct is None:
        return None
    try:
        g = await graph_for(session, automation.id, run.flow_version)
    except (KeyError, flows.FlowError):
        return None
    return Scene(run, automation, g, conv, contact, acct, await actions.disclosure(session))


# ---------------------------------------------------------------- the step log


async def _log(
    session: AsyncSession,
    run: AutomationRun,
    step: Step,
    status: StepStatus,
    *,
    message_id: uuid.UUID | None = None,
    extra: dict[str, object] | None = None,
    **detail: object,
) -> AutomationRunStep:
    row = await session.scalar(
        select(AutomationRunStep).where(
            AutomationRunStep.run_id == run.id, AutomationRunStep.step_id == step.id
        )
    )
    if row is None:
        row = AutomationRunStep(
            run_id=run.id, step_id=step.id, kind=step.type, status=status, detail={}
        )
        session.add(row)
    row.status = status
    if message_id is not None:
        row.message_id = message_id
    if detail or extra:
        row.detail = {**(row.detail or {}), **(extra or {}), **detail}
    await session.flush()
    return row


async def _step_row(
    session: AsyncSession, run_id: uuid.UUID, step_id: str
) -> AutomationRunStep | None:
    return await session.scalar(
        select(AutomationRunStep).where(
            AutomationRunStep.run_id == run_id, AutomationRunStep.step_id == step_id
        )
    )


# ---------------------------------------------------------------- messages


def _text(
    step: SendStep | AskStep, contact: Contact | None, username: str | None, disclosure: str | None
) -> str:
    first_name, name = actions.personal_fields(contact, username=username)
    return render.with_disclosure(
        render.render(step.text, first_name=first_name, username=name), disclosure
    )


def _buttons(buttons: list[FlowButton], account_username: str | None) -> tuple[OutboundButton, ...]:
    out = []
    for button in buttons:
        if button.profile:
            if account_username:
                out.append(
                    OutboundButton(
                        title=button.title, url=actions.PROFILE_URL.format(account_username)
                    )
                )
        elif button.url:
            out.append(OutboundButton(title=button.title, url=button.url))
    return tuple(out)


def _quick_replies(step: SendStep, run_id: uuid.UUID) -> tuple[OutboundQuickReply, ...]:
    return tuple(
        OutboundQuickReply(title=q.title, payload=payload(run_id, step.id, i))
        for i, q in enumerate(step.quick_replies)
    )


def entry_message(
    g: flows.Graph,
    run: AutomationRun,
    contact: Contact | None,
    *,
    username: str | None,
    account_username: str | None,
    disclosure: str | None,
) -> tuple[OutboundMessage | None, bool]:
    """A comment flow's private reply (its first step) and whether the run then waits for the
    answer. None when the first step sends nothing."""
    step = g.step(g.definition.start)
    if not isinstance(step, SendStep | AskStep) or not step.text.strip():
        return None, False
    text = _text(step, contact, username, disclosure)
    if isinstance(step, AskStep):
        return OutboundMessage(text=text), True
    return (
        OutboundMessage(
            text=text,
            buttons=_buttons(step.buttons, account_username),
            quick_replies=_quick_replies(step, run.id),
        ),
        flows.waits(step),
    )


def start_values(automation: Automation, g: flows.Graph, *, comment: bool) -> dict[str, object]:
    """A new flow run's columns: a comment's first message waits in the queue (``sending``), a
    DM's first steps run at once (``start_dm``). A flow that starts with an AI reply runs as an
    AI reply, with only its version."""
    if isinstance(g.step(g.definition.start), AiReplyStep):
        return {"flow_version": automation.flow_version}
    return {
        "flow_version": automation.flow_version,
        "step_id": g.definition.start,
        "flow_state": FlowState.SENDING if comment else FlowState.NEXT,
    }


async def entry_logged(
    session: AsyncSession, run: AutomationRun, g: flows.Graph, message_id: uuid.UUID
) -> None:
    """The queue stored a comment flow's private reply: log its first step as sent."""
    if is_flow_run(run) and run.step_id is not None:
        await _log(session, run, g.step(run.step_id), StepStatus.SENT, message_id=message_id)


async def _send(
    session: AsyncSession,
    deps: PlatformDeps,
    scene: Scene,
    step: SendStep | AskStep,
    *,
    now: datetime,
    text: str | None = None,
    part: str | None = None,
) -> Message | None:
    """A step's message (or its retry prompt) through the send pipeline; None when refused
    (the step is then logged failed)."""
    from socialhood.services import sending  # sending → … → ingest → the runtime

    run = scene.run
    body = text if text is not None else _text(step, scene.contact, None, scene.disclosure)
    send_step = step if isinstance(step, SendStep) and text is None else None
    try:
        msg = await sending.queue_outbound(
            session,
            scene.conv,
            source="automation",
            client_id=actions.client_id_for(run.id, part or step.id),
            text=body,
            attachment_asset_ids=(
                [send_step.image_asset_id] if send_step and send_step.image_asset_id else ()
            ),
            buttons=_buttons(send_step.buttons, scene.acct.username) if send_step else (),
            quick_replies=_quick_replies(send_step, run.id) if send_step else (),
            automation_run_id=run.id,
            deps=deps,
            now=now,
        )
    except ApiError as error:
        await _log(
            session,
            run,
            step,
            StepStatus.FAILED,
            error_code=error.code,
            error=actions.api_error_reason(error),
        )
        return None
    return msg


# ---------------------------------------------------------------- conditions and actions


async def _has_tag(session: AsyncSession, contact_id: uuid.UUID, tag_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(exists().where(ContactTag.contact_id == contact_id, ContactTag.tag_id == tag_id))
        )
    )


async def _holds(session: AsyncSession, scene: Scene, rule_when: object) -> bool:
    contact = scene.contact
    match rule_when:
        case TagCondition(tag_id=tag_id, has=has):
            return await _has_tag(session, contact.id, tag_id) == has
        case FieldCondition(key=key, op=op, value=value):
            current = (contact.fields or {}).get(key)
            if op == "set":
                return current not in (None, "")
            if op == "unset":
                return current in (None, "")
            return current is not None and str(current).casefold() == (value or "").casefold()
        case ContactCondition(has=has, known=known):
            value = contact.email if has == "email" else contact.phone
            return (value is not None) == known
        case FollowsCondition(follows=follows):
            return scene.follows is not None and scene.follows == follows
        case PlatformCondition(platform=platform):
            return scene.acct.platform == platform
        case LeadScoreCondition(at_least=at_least):
            return scene.conv.lead_score is not None and scene.conv.lead_score >= at_least
        case LeadStageCondition(stages=stages):
            return contact.lead_stage in stages
    return False


def _needs_follows(step: Step) -> bool:
    return isinstance(step, BranchStep) and any(
        isinstance(rule.when, FollowsCondition) for rule in step.rules
    )


async def _act(
    session: AsyncSession, scene: Scene, step: ActionStep, now: datetime
) -> dict[str, object]:
    """Do the action; returns what to log (``skipped`` with the reason when it can't)."""
    from socialhood.services.notifications import notify_admins
    from socialhood.services.sending import UNTIL_RESUMED

    contact, run = scene.contact, scene.run
    match step.action:
        case AddTag(tag_id=tag_id):
            if await session.scalar(select(Tag.id).where(Tag.id == tag_id)) is None:
                return {"skipped": "tag_missing"}
            if not await _has_tag(session, contact.id, tag_id):
                session.add(ContactTag(contact_id=contact.id, tag_id=tag_id))
                await _tagged(session, contact, tag_id, added=True)
            return {}
        case RemoveTag(tag_id=tag_id):
            if await _has_tag(session, contact.id, tag_id):
                await session.execute(
                    scoped_delete(ContactTag).where(
                        ContactTag.contact_id == contact.id, ContactTag.tag_id == tag_id
                    )
                )
                await _tagged(session, contact, tag_id, added=False)
            return {}
        case SetField(key=key, value=raw):
            definition = await session.scalar(
                select(ContactFieldDefinition).where(ContactFieldDefinition.key == key)
            )
            if definition is None:
                return {"skipped": "field_missing"}
            first_name, username = actions.personal_fields(contact)
            try:
                value = flows.typed_value(
                    flows.FieldSpec(definition.type, list(definition.options or [])),
                    render.render(raw, first_name=first_name, username=username),
                )
            except ValueError:
                return {"skipped": "value_invalid"}
            contact.fields = {**(contact.fields or {}), key: value}
            return {"value": value}
        case NotifyTeam(note=note):
            await notify_admins(
                session,
                type="automation_alert",
                severity="info",
                title=f"{_who(contact)}: {scene.automation.name}",
                body=note.strip() or NOTIFY_BODY,
                link=f"/inbox/{scene.conv.id}",
                dedupe_key=f"automation_step:{run.id}:{step.id}",
            )
            return {}
        case HandOff():
            conv = scene.conv
            conv.needs_human = True
            conv.needs_human_reason = None
            conv.ai_paused_until = UNTIL_RESUMED  # until someone resumes the AI
            await session.flush()
            await events.queue_conversation(session, conv, now=now, contact=contact)
            await notify_admins(
                session,
                type="ai_escalated",
                severity="warning",
                title=f"{_who(contact)} needs you",
                body=HAND_OFF_BODY,
                link=f"/inbox/{conv.id}",
                dedupe_key=f"automation_step:{run.id}:{step.id}",
            )
            return {}
    return {}


async def _tagged(
    session: AsyncSession, contact: Contact, tag_id: uuid.UUID, *, added: bool
) -> None:
    name = await session.scalar(select(Tag.name).where(Tag.id == tag_id))
    await webhook_events.contacts_tagged(
        session, [webhook_events.TagChange(contact, tag_id, name or "", added)]
    )


async def _completed(session: AsyncSession, run: AutomationRun, before: str | None) -> None:
    """automation.run.completed (GR-04) when this call ended the run."""
    if before == FlowState.DONE or run.flow_state != FlowState.DONE:
        return
    automation = await runs.get_automation(session, run.automation_id)
    contact = await inbox.get_contact(session, run.contact_id) if run.contact_id else None
    await webhook_events.run_completed(
        session,
        run_id=run.id,
        result=run.result,
        trigger="comment" if run.trigger_comment_id else "dm",
        automation_id=run.automation_id,
        automation_name=automation.name if automation else "",
        contact=contact,
    )


def _who(contact: Contact) -> str:
    if contact.display_name:
        return contact.display_name
    return f"@{contact.username}" if contact.username else "A customer"


def _pick(paths_weights: list[int]) -> int:
    return random.choices(range(len(paths_weights)), weights=paths_weights)[0]  # noqa: S311


# ---------------------------------------------------------------- running steps


Stop = Literal["sent", "delay", "follows", "done"]


async def _advance(
    session: AsyncSession, deps: PlatformDeps, scene: Scene, *, now: datetime
) -> Stop:
    """Run the run's steps from ``step_id`` until a message is sent, a delay, a branch that
    needs the follow status (not read in this pass), or the end. Sets the run's state."""
    run, g = scene.run, scene.graph
    for _ in range(MAX_STEPS):
        step_id = run.step_id
        step = g.by_id.get(step_id) if step_id else None
        if step is None or isinstance(step, EndStep | AiReplyStep):
            if step is not None:
                await _log(session, run, step, StepStatus.DONE)
            run.flow_state = FlowState.DONE
            return "done"
        match step:
            case SendStep() | AskStep():
                msg = await _send(session, deps, scene, step, now=now)
                if msg is None:
                    run.flow_state = FlowState.DONE
                    return "done"
                await _log(session, run, step, StepStatus.SENT, message_id=msg.id)
                run.flow_state = FlowState.SENDING
                return "sent"
            case BranchStep():
                if _needs_follows(step) and not scene.follows_read:
                    run.flow_state = FlowState.NEXT
                    return "follows"
                target, taken = step.otherwise, "otherwise"
                for i, rule in enumerate(step.rules):
                    if await _holds(session, scene, rule.when):
                        target, taken = rule.next, str(i)
                        break
                await _log(session, run, step, StepStatus.DONE, rule=taken)
                run.step_id = target
            case ActionStep():
                done = await _act(session, scene, step, now)
                await _log(session, run, step, StepStatus.DONE, extra=done)
                run.step_id = step.next
            case RandomizeStep():
                chosen = _pick([p.weight for p in step.paths])
                await _log(session, run, step, StepStatus.DONE, path=chosen)
                run.step_id = step.paths[chosen].next
            case DelayStep():
                await _log(session, run, step, StepStatus.DONE, seconds=step.seconds)
                run.step_id = step.next
                if step.next is None:
                    continue
                run.flow_state = FlowState.DELAYING
                run.wait_until = now + timedelta(seconds=step.seconds)
                return "delay"
    log.warning("flow_step_limit", run_id=str(run.id))
    run.flow_state = FlowState.DONE
    return "done"


async def _after_stop(stop: Stop, run: AutomationRun, *, now: datetime) -> None:
    """Enqueue what comes next (inside the caller's transaction, like the follow nudge)."""
    from socialhood.services.automations.runtime import enqueue_run

    if stop == "follows":
        await enqueue_run("flow", run.id, run.workspace_id)
    elif stop == "delay" and run.wait_until is not None:
        delay = max(1.0, (run.wait_until - now).total_seconds())
        await enqueue_run("flow", run.id, run.workspace_id, delay_s=delay)


# ---------------------------------------------------------------- entry (DM triggers)


async def start_dm(
    session: AsyncSession,
    deps: PlatformDeps,
    automation: Automation,
    run: AutomationRun,
    msg: Message,
    *,
    now: datetime,
) -> None:
    """A DM flow's first steps, in the matching transaction (the run is recorded ``sent``; it
    follows its first message like any automation DM)."""
    msg.automation_handled = True  # FR-AUT-07: no AI reply on the trigger
    scene = await _scene(session, run)
    if scene is None:
        run.result = RunResult.FAILED
        run.error_code, run.error_message = actions.NO_MESSAGE
        run.flow_state = FlowState.DONE
        return
    stop = await _advance(session, deps, scene, now=now)
    first = await session.scalar(
        select(AutomationRunStep.message_id).where(
            AutomationRunStep.run_id == run.id, AutomationRunStep.message_id.is_not(None)
        )
    )
    run.private_reply_message_id = first  # the run log links its first message
    if stop == "done" and first is None:
        failed = await session.scalar(
            select(AutomationRunStep).where(
                AutomationRunStep.run_id == run.id,
                AutomationRunStep.status == StepStatus.FAILED,
            )
        )
        run.result = RunResult.FAILED
        if failed is not None:
            run.error_code = str(failed.detail.get("error_code") or "failed")
            run.error_message = str(failed.detail.get("error") or results.DM_FAILED)
        else:
            run.error_code, run.error_message = actions.NO_MESSAGE
    await _after_stop(stop, run, now=now)
    await _completed(session, run, FlowState.NEXT)


# ---------------------------------------------------------------- after a message


async def after_message(session: AsyncSession, run: AutomationRun, msg: Message) -> None:
    """A flow run's message was sent or failed (the run is locked)."""
    before = run.flow_state
    await _after_message(session, run, msg)
    if is_flow_run(run):
        await _completed(session, run, before)


async def _after_message(session: AsyncSession, run: AutomationRun, msg: Message) -> None:
    if not is_flow_run(run) or run.flow_state != FlowState.SENDING or run.step_id is None:
        return
    row = await _step_row(session, run.id, run.step_id)
    if row is None or row.message_id != msg.id:
        return
    g = await graph_for(session, run.automation_id, run.flow_version or 0)
    step = g.step(run.step_id)
    if msg.status == MessageStatus.FAILED:
        row.status = StepStatus.FAILED
        row.detail = {
            **(row.detail or {}),
            "error_code": msg.error_code or "failed",
            "error": msg.error_message or results.DM_FAILED,
        }
        run.flow_state = FlowState.DONE
        return
    if msg.status not in results.DELIVERED:
        return
    if flows.waits(step):
        row.status = StepStatus.WAITING
        run.flow_state = FlowState.REPLYING
        if run.result in (RunResult.SENT, RunResult.PARTIAL):
            run.result = RunResult.AWAITING_REPLY  # a comment's opening is already
        return
    row.status = StepStatus.DONE
    run.step_id = step.next if isinstance(step, SendStep) else None
    if run.step_id is None:
        run.flow_state = FlowState.DONE
        return
    run.flow_state = FlowState.NEXT
    from socialhood.services.automations.runtime import enqueue_run

    await enqueue_run("flow", run.id, run.workspace_id)


# ---------------------------------------------------------------- the continue job


ResumeOutcome = Literal["missing", "ignored", "advanced", "done"]


async def resume(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    run_id: uuid.UUID,
    now: datetime,
) -> ResumeOutcome:
    """``run_automation("flow", run_id)``: run the next steps (see the module docstring)."""
    from socialhood.services.automations.runtime import enqueue_run
    from socialhood.services.ingest_followups import follow_status

    follows: bool | None = None
    follows_read = False
    for _ in range(2):  # a second pass after reading the follow status
        async with sessionmaker() as session:
            run = await runs.get(session, run_id)
            if run is None:
                return "missing"
            if run.conversation_id is not None:
                await rows.lock_conversation(session, run.conversation_id)
            run = await runs.lock(session, run_id)
            if run is None or not is_flow_run(run):
                return "ignored"
            if run.flow_state == FlowState.DELAYING:
                if run.wait_until is not None and run.wait_until > now + timedelta(seconds=1):
                    await enqueue_run(
                        "flow",
                        run.id,
                        run.workspace_id,
                        delay_s=(run.wait_until - now).total_seconds(),
                    )
                    await session.commit()
                    return "ignored"
                run.flow_state = FlowState.NEXT
                run.wait_until = None
            if run.flow_state != FlowState.NEXT:
                return "ignored"
            scene = await _scene(session, run)
            if scene is None:
                run.flow_state = FlowState.DONE
                await session.commit()
                return "done"
            scene.follows, scene.follows_read = follows, follows_read
            if follows_read:
                run.follows_business = follows
            stop = await _advance(session, deps, scene, now=now)
            if stop == "follows":
                contact_id = scene.contact.id
                await session.commit()  # the steps before the branch are done
            else:
                await _after_stop(stop, run, now=now)
                await _completed(session, run, FlowState.NEXT)
                await session.flush()
                await events.commit_and_publish(session, redis)
                return "done" if stop == "done" else "advanced"
        follows = await follow_status(sessionmaker, redis, deps, contact_id=contact_id, now=now)
        follows_read = True
    return "advanced"


# ---------------------------------------------------------------- answers


@dataclass(frozen=True)
class FlowAnswer:
    """What a customer message answers: a flow run's waiting step (``option``: the quick reply
    tapped, None for typed text), or nothing more (``run_id`` None: a tap on a step the run has
    left, which is handled and sends nothing)."""

    run_id: uuid.UUID | None
    option: int | None = None


def _takes_text(step: Step) -> bool:
    return isinstance(step, AskStep) or (isinstance(step, SendStep) and step.on_text is not None)


async def find_answer(
    session: AsyncSession, msg: Message, contact_id: uuid.UUID, *, now: datetime
) -> FlowAnswer | None:
    """None when the message answers no flow run."""
    tap = parse_payload(msg.quick_reply_payload)
    if tap is not None:
        run = await runs.flow_run_of(session, tap.run_id, contact_id, msg.social_account_id)
        if run is None:
            return None
        if run.flow_state == FlowState.REPLYING and run.step_id == tap.step_id:
            return FlowAnswer(run.id, tap.option)
        return FlowAnswer(None)
    waiting = await runs.flow_waiting(
        session, contact_id, msg.social_account_id, since=now - ANSWER_WINDOW
    )
    if waiting is None or waiting.step_id is None or waiting.flow_version is None:
        return None
    g = await graph_for(session, waiting.automation_id, waiting.flow_version)
    if not _takes_text(g.step(waiting.step_id)):
        return None
    return FlowAnswer(waiting.id)


def _check(step: AskStep, text: str, spec: flows.FieldSpec | None) -> object:
    """The answer as stored, or ValueError."""
    from socialhood.services.contacts import normalize_email, normalize_phone

    text = text.strip()
    if not text:
        raise ValueError("empty")
    if spec is not None:
        return flows.typed_value(spec, text)
    if step.expect == "email":
        return normalize_email(text)
    if step.expect == "phone":
        return normalize_phone(text)
    return text


async def answer(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    deps: PlatformDeps,
    *,
    message_id: uuid.UUID,
    conversation_id: uuid.UUID,
    found: FlowAnswer,
    now: datetime,
) -> bool:
    """Mark the message handled and take the answer; returns whether the run moved on."""
    from socialhood.services.automations.runtime import enqueue_run

    async with sessionmaker() as session:
        # Conversation, then message, then run: the order ingest takes them in.
        conv = await rows.lock_conversation(session, conversation_id)
        msg = await rows.lock_message(session, message_id)
        if conv is None or msg is None:
            return False
        msg.automation_handled = True  # no keyword automation, no AI reply
        run = await runs.lock(session, found.run_id) if found.run_id else None
        if run is None or run.flow_state != FlowState.REPLYING or run.step_id is None:
            await session.commit()
            return False
        run.conversation_id = run.conversation_id or conv.id
        scene = await _scene(session, run)
        if scene is None:
            run.flow_state = FlowState.DONE
            await session.commit()
            return False
        step = scene.graph.step(run.step_id)
        target, moved = await _take(session, deps, scene, step, msg, found.option, now=now)
        if moved:
            if run.confirmed_at is None:
                run.confirmed_at = now
            if run.result == RunResult.AWAITING_REPLY:
                results.hand_over(run)
            run.step_id = target
            run.flow_state = FlowState.NEXT if target else FlowState.DONE
            if target:
                await enqueue_run("flow", run.id, run.workspace_id)
            await _completed(session, run, FlowState.REPLYING)
        await session.flush()
        await events.commit_and_publish(session, redis)
        log.info("flow_answered", run_id=str(run.id), step_id=step.id, moved=moved)
        return moved


async def _take(
    session: AsyncSession,
    deps: PlatformDeps,
    scene: Scene,
    step: Step,
    msg: Message,
    option: int | None,
    *,
    now: datetime,
) -> tuple[str | None, bool]:
    """(the next step, whether the run moves on) for this answer to ``step``."""
    run = scene.run
    if isinstance(step, SendStep):
        if option is not None and 0 <= option < len(step.quick_replies):
            reply = step.quick_replies[option]
            await _log(session, run, step, StepStatus.DONE, answer=reply.title, option=option)
            return reply.next, True
        await _log(session, run, step, StepStatus.DONE, answer=(msg.text or "")[:200])
        return step.on_text, True
    if not isinstance(step, AskStep):
        return None, True
    row = await _step_row(session, run.id, step.id)
    tries = int((row.detail or {}).get("tries", 0)) + 1 if row else 1
    spec = None
    if step.field_key is not None:
        definition = await session.scalar(
            select(ContactFieldDefinition).where(ContactFieldDefinition.key == step.field_key)
        )
        spec = (
            flows.FieldSpec(definition.type, list(definition.options or [])) if definition else None
        )
    try:
        value = _check(step, msg.text or "", spec)
    except ValueError:
        if tries < step.tries:
            retry = render.with_disclosure(
                step.retry_text.strip() or RETRY_COPY[step.expect], scene.disclosure
            )
            await _send(
                session, deps, scene, step, now=now, text=retry, part=f"{step.id}:retry{tries}"
            )
            await _log(session, run, step, StepStatus.WAITING, tries=tries)
            return step.id, False
        await _log(session, run, step, StepStatus.DONE, tries=tries, skipped=True)
        return step.on_skip, True
    _save_answer(scene.contact, step, value)
    await _log(session, run, step, StepStatus.DONE, tries=tries, answer=value)
    kind = "field" if step.field_key else step.expect
    await leads.on_capture(session, scene.contact, kind)  # a captured email qualifies (GR-18)
    await webhook_events.lead_captured(
        session,
        scene.contact,
        kind=kind,
        value=value,
        field_key=step.field_key,
        automation_id=scene.automation.id,
        automation_name=scene.automation.name,
        run_id=run.id,
    )
    return step.next, True


def _save_answer(contact: Contact, step: AskStep, value: object) -> None:
    if step.field_key is not None:
        contact.fields = {**(contact.fields or {}), step.field_key: value}
    elif step.expect == "email":
        contact.email, contact.email_source, contact.email_verified = (
            str(value),
            FLOW_SOURCE,
            False,
        )
    elif step.expect == "phone":
        contact.phone, contact.phone_source, contact.phone_verified = (
            str(value),
            FLOW_SOURCE,
            False,
        )
