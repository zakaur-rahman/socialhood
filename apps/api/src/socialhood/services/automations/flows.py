"""Automation flows (GR-03): checking a flow, and compiling today's automations into one. Pure:
no database, no clock.

Structure, checked on every save (a broken graph is never stored):
- step ids are unique, and ``start`` and every step a step leads to exist;
- no step leads back to an earlier one, so a run visits each step at most once.

``activation_errors`` returns every problem at once, with the field path of its step
(``flow.steps.3.text``):
- every step can be reached from the start;
- a message has its text, within Instagram's 1,000 bytes in its longest rendering with the
  disclosure line (640 characters with link buttons); https buttons; not both link buttons and
  quick replies, and no image with quick replies (they ride on the last message);
- a question has its text and a place for the answer: a custom field of a matching type, or for an
  email or phone the contact's own;
- the tags and fields a branch or an action names exist, and a set value fits its field;
- an AI reply has its instructions.

And what Instagram allows along every path from the start (``_path_errors``):
- a comment's flow starts with its first message, a private reply: text and buttons only, no
  image. Until the person answers (a quick reply, or a question), nothing more can be sent;
- whether someone follows the account can be read only once they've written (a DM trigger, or an
  answer);
- an AI reply is the first step, and ends the flow.

``compile_legacy`` turns an automation's message settings (the current editor) into the
equivalent flow: the message as a ``send``; tap first as an opening ``send`` whose quick reply (or
any typed answer) leads to the message; the follow nudge as a ``branch`` on not following, then a
``send`` with the "View profile" button. A comment automation without tap first never hears back,
so its nudge is left out, as the runtime always did (services/automations/nudge).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from pydantic import ValidationError

from socialhood.errors import FieldError
from socialhood.models.automations import Automation, AutomationAction
from socialhood.schemas.flows import (
    ActionStep,
    AddTag,
    AiReplyStep,
    AskStep,
    BranchRule,
    BranchStep,
    Condition,
    ContactCondition,
    DelayStep,
    FieldCondition,
    FlowButton,
    FlowDefinition,
    FollowsCondition,
    LeadScoreCondition,
    LeadStageCondition,
    PlatformCondition,
    QuickReply,
    RandomizeStep,
    RemoveTag,
    SendStep,
    SetField,
    Step,
    TagCondition,
)
from socialhood.services.automations import render, templates, validation

COMMENT_TRIGGERS = validation.COMMENT_TRIGGERS
NUDGE_BUTTON = "View profile"  # services/automations/actions.NUDGE_BUTTON

COPY = {
    "duplicate_id": "Another step has this id. Give each step its own.",
    "start_missing": "Choose the first step.",
    "next_missing": "This step leads to a step that doesn't exist.",
    "loop": "This step leads back to an earlier one. Flows can't loop.",
    "unreachable": "Nothing leads to this step. Connect it or delete it.",
    "text_missing": "Write the message to send.",
    "question_missing": "Write the question to ask.",
    "buttons_and_replies": "A message can have link buttons or quick replies, not both.",
    "image_and_replies": "Quick replies go on a text message. Move the image to the step before.",
    "image_in_private_reply": validation.COPY["image_in_private_reply"],
    "button_link": "Add a link, or make it the profile button.",
    "after_private_reply": (
        "Instagram allows one reply to a comment until the person answers. Add quick replies or "
        "a question before this step."
    ),
    "comment_start": "A comment's flow starts with its first message, its reply to the comment.",
    "follows_too_early": (
        "Whether someone follows you can be checked once they've written to you. Move this "
        "after a quick reply or a question."
    ),
    "ai_not_first": "An AI reply has to be the first step.",
    "ai_instructions": validation.COPY["ai_instructions_missing"],
    "answer_field": "Choose the field to save the answer to.",
    "field_missing": "That field doesn't exist any more. Choose another.",
    "field_type": "This field can't hold that kind of answer. Choose a field of the same type.",
    "tag_missing": "That tag doesn't exist any more. Choose another.",
    "value_missing": "Write the value to compare with.",
    "saved_reply_missing": "That saved reply doesn't exist any more. Choose another.",
    "saved_reply_alone": (
        "A saved reply goes on its own. Remove the image, buttons and quick replies, or write "
        "the message here instead."
    ),
    "comment_saved_reply": (
        "A comment's first message is written here, not a saved reply. Start with a message "
        "step, then use the saved reply."
    ),
}


class FlowError(Exception):
    """A broken graph; ``errors`` name the steps."""

    def __init__(self, errors: list[FieldError]) -> None:
        super().__init__("flow structure")
        self.errors = errors


# ---------------------------------------------------------------- the graph


def path(index: int, part: str | None = None) -> str:
    return f"flow.steps.{index}" + (f".{part}" if part else "")


def successors(step: Step) -> list[str | None]:
    """The steps a step can lead to, in order (None: the flow ends there)."""
    match step:
        case SendStep(quick_replies=replies) if replies:
            return [r.next for r in replies] + [step.on_text]
        case SendStep() | ActionStep() | DelayStep():
            return [step.next]
        case AskStep():
            return [step.next, step.on_skip]
        case BranchStep():
            return [r.next for r in step.rules] + [step.otherwise]
        case RandomizeStep():
            return [p.next for p in step.paths]
        case _:
            return []  # ai_reply and end


def exit_labels(step: Step, tag_names: Mapping[uuid.UUID, str] | None = None) -> list[str]:
    """Plain words for each exit of ``successors(step)``, in the same order (the preview and the
    dry run name the way a run goes at a fork)."""
    match step:
        case SendStep(quick_replies=replies) if replies:
            return [f"Taps {r.title}" for r in replies] + ["Types an answer"]
        case AskStep():
            return ["Answers", "Doesn't answer in a way that fits"]
        case BranchStep():
            return [describe_condition(r.when, tag_names) for r in step.rules] + ["Otherwise"]
        case RandomizeStep():
            return [f"Path {chr(65 + i)} ({p.weight})" for i, p in enumerate(step.paths)]
        case _:
            return ["Next"] * len(successors(step))


def describe_condition(
    when: Condition,
    tag_names: Mapping[uuid.UUID, str] | None = None,
) -> str:
    match when:
        case TagCondition():
            name = (tag_names or {}).get(when.tag_id, "a tag")
            return f"Has the tag {name}" if when.has else f"Doesn't have the tag {name}"
        case FieldCondition(op="equals"):
            return f"{when.key} is {when.value or ''}"
        case FieldCondition(op="unset"):
            return f"{when.key} is empty"
        case FieldCondition():
            return f"{when.key} is filled in"
        case ContactCondition():
            return f"{'Has' if when.known else 'Has no'} {when.has}"
        case FollowsCondition():
            return "Follows you" if when.follows else "Doesn't follow you"
        case PlatformCondition():
            return f"Is on {when.platform}"
        case LeadScoreCondition():
            return f"Lead score is {when.at_least} or more"
        case LeadStageCondition():
            stages = " or ".join(stage.replace("_", " ") for stage in when.stages)
            return f"Lead stage is {stages}"


def waits(step: Step) -> bool:
    """Whether the run waits for the person's answer after this step's message."""
    return isinstance(step, AskStep) or (isinstance(step, SendStep) and bool(step.quick_replies))


@dataclass(frozen=True)
class Graph:
    definition: FlowDefinition
    by_id: dict[str, Step]
    index: dict[str, int]

    def step(self, step_id: str) -> Step:
        return self.by_id[step_id]


def graph(definition: FlowDefinition) -> Graph:
    """The checked graph; raises FlowError when the structure is broken."""
    errors: list[FieldError] = []
    by_id: dict[str, Step] = {}
    index: dict[str, int] = {}
    for i, step in enumerate(definition.steps):
        if step.id in by_id:
            errors.append(FieldError(path(i, "id"), COPY["duplicate_id"]))
            continue
        by_id[step.id] = step
        index[step.id] = i
    if definition.start not in by_id:
        errors.append(FieldError("flow.start", COPY["start_missing"]))
    for i, step in enumerate(definition.steps):
        if any(target is not None and target not in by_id for target in successors(step)):
            errors.append(FieldError(path(i), COPY["next_missing"]))
    if not errors:
        errors += _loops(definition, by_id, index)
    if errors:
        raise FlowError(errors)
    return Graph(definition, by_id, index)


def _loops(
    definition: FlowDefinition, by_id: Mapping[str, Step], index: Mapping[str, int]
) -> list[FieldError]:
    """Each step that leads back to a step on its own path (depth first, every step)."""
    state: dict[str, Literal["open", "done"]] = {}
    looping: set[str] = set()

    def visit(step_id: str) -> None:
        state[step_id] = "open"
        for target in successors(by_id[step_id]):
            if target is None:
                continue
            if state.get(target) == "open":
                looping.add(step_id)
            elif target not in state:
                visit(target)
        state[step_id] = "done"

    for step in definition.steps:
        if step.id not in state:
            visit(step.id)
    return [
        FieldError(path(index[s]), COPY["loop"]) for s in sorted(looping, key=lambda s: index[s])
    ]


def reachable(g: Graph) -> list[str]:
    """Step ids reachable from the start, in the order a walk first meets them."""
    order: list[str] = []
    stack = [g.definition.start]
    while stack:
        step_id = stack.pop()
        if step_id in order:
            continue
        order.append(step_id)
        stack.extend(t for t in reversed(successors(g.by_id[step_id])) if t is not None)
    return order


# ---------------------------------------------------------------- activation


@dataclass(frozen=True)
class FieldSpec:
    type: str
    options: list[str] = field(default_factory=list)


def typed_value(spec: FieldSpec, raw: str) -> object:
    """A value typed into a flow (always text) as its field stores it, or ValueError."""
    from socialhood.services.contacts import field_value

    value: object = raw
    if spec.type == "number":
        try:
            value = float(raw) if any(c in raw for c in ".eE") else int(raw)
        except ValueError as error:
            raise ValueError("Enter a number.") from error
    return field_value(spec, value)


@dataclass(frozen=True)
class Context:
    """What activation checks a flow against."""

    trigger: str | None
    disclosure: str | None
    fields: Mapping[str, FieldSpec] = field(default_factory=dict)  # custom fields by key
    tag_ids: frozenset[uuid.UUID] = frozenset()
    # GR-21: the workspace's saved replies, id to body (their length is checked now; a body
    # edited later is checked by the send).
    saved_replies: Mapping[uuid.UUID, str] = field(default_factory=dict)

    @property
    def comment(self) -> bool:
        return self.trigger in COMMENT_TRIGGERS


def activation_errors(definition: FlowDefinition, ctx: Context) -> list[FieldError]:
    try:
        g = graph(definition)
    except FlowError as error:
        return error.errors
    errors: list[FieldError] = []
    reached = set(reachable(g))
    for i, step in enumerate(definition.steps):
        if step.id not in reached:
            errors.append(FieldError(path(i), COPY["unreachable"]))
            continue
        errors += _step_errors(i, step, ctx)
    start = g.by_id[definition.start]
    if ctx.comment and not isinstance(start, SendStep | AskStep | AiReplyStep):
        errors.append(FieldError("flow.start", COPY["comment_start"]))
    elif ctx.comment and isinstance(start, SendStep) and start.saved_reply_id is not None:
        errors.append(FieldError("flow.start", COPY["comment_saved_reply"]))
    found = _path_errors(g, ctx)
    errors += [
        FieldError(path(g.index[s]), found[s]) for s in sorted(found, key=lambda s: g.index[s])
    ]
    return errors


def _step_errors(i: int, step: Step, ctx: Context) -> list[FieldError]:
    match step:
        case SendStep():
            return _send_errors(i, step, ctx)
        case AskStep():
            return _ask_errors(i, step, ctx)
        case BranchStep():
            return _branch_errors(i, step, ctx)
        case ActionStep():
            return _action_errors(i, step, ctx)
        case AiReplyStep() if not step.instructions.strip():
            return [FieldError(path(i, "instructions"), COPY["ai_instructions"])]
        case _:
            return []


def _text_errors(where: str, text: str, ctx: Context, *, buttons: bool) -> list[FieldError]:
    size = validation.message_bytes(text, ctx.disclosure)
    limit = validation.INSTAGRAM_MESSAGE_BYTES
    errors = []
    if size > limit:
        errors.append(
            FieldError(
                where,
                f"Instagram allows {limit:,} bytes. With a long name"
                f"{' and the disclosure line' if ctx.disclosure else ''} this message is "
                f"{size:,}. Shorten it.",
            )
        )
    longest = render.with_disclosure(render.longest_render(text), ctx.disclosure)
    if buttons and len(longest) > validation.BUTTON_TEXT_CHARS:
        errors.append(FieldError(where, validation.COPY["button_text_long"]))
    return errors


def _saved_reply_errors(i: int, step: SendStep, ctx: Context) -> list[FieldError]:
    body = ctx.saved_replies.get(step.saved_reply_id) if step.saved_reply_id else None
    if body is None:
        return [FieldError(path(i, "saved_reply_id"), COPY["saved_reply_missing"])]
    errors = _text_errors(path(i, "saved_reply_id"), body, ctx, buttons=False)
    if step.buttons or step.quick_replies or step.image_asset_id is not None:
        errors.append(FieldError(path(i, "saved_reply_id"), COPY["saved_reply_alone"]))
    return errors


def _send_errors(i: int, step: SendStep, ctx: Context) -> list[FieldError]:
    if step.saved_reply_id is not None:
        return _saved_reply_errors(i, step, ctx)
    errors: list[FieldError] = []
    if not step.text.strip():
        errors.append(FieldError(path(i, "text"), COPY["text_missing"]))
    else:
        errors += _text_errors(path(i, "text"), step.text, ctx, buttons=bool(step.buttons))
    if step.buttons and step.quick_replies:
        errors.append(FieldError(path(i, "quick_replies"), COPY["buttons_and_replies"]))
    if step.image_asset_id is not None and step.quick_replies:
        errors.append(FieldError(path(i, "image_asset_id"), COPY["image_and_replies"]))
    for b, button in enumerate(step.buttons):
        where = path(i, f"buttons.{b}.url")
        if button.profile:
            continue
        if not button.url:
            errors.append(FieldError(where, COPY["button_link"]))
        elif not validation.is_https_url(button.url):
            errors.append(FieldError(where, validation.COPY["button_url"]))
    return errors


ANSWER_TYPES = {
    "text": {"text", "number", "date", "choice"},
    "email": {"email"},
    "phone": {"phone"},
}


def _ask_errors(i: int, step: AskStep, ctx: Context) -> list[FieldError]:
    errors: list[FieldError] = []
    if not step.text.strip():
        errors.append(FieldError(path(i, "text"), COPY["question_missing"]))
    else:
        errors += _text_errors(path(i, "text"), step.text, ctx, buttons=False)
    where = path(i, "field_key")
    if step.field_key is None:
        if step.expect == "text":
            errors.append(FieldError(where, COPY["answer_field"]))
    elif step.field_key not in ctx.fields:
        errors.append(FieldError(where, COPY["field_missing"]))
    elif ctx.fields[step.field_key].type not in ANSWER_TYPES[step.expect]:
        errors.append(FieldError(where, COPY["field_type"]))
    return errors


def _branch_errors(i: int, step: BranchStep, ctx: Context) -> list[FieldError]:
    errors: list[FieldError] = []
    for r, rule in enumerate(step.rules):
        where = path(i, f"rules.{r}.when")
        match rule.when:
            case TagCondition(tag_id=tag_id) if tag_id not in ctx.tag_ids:
                errors.append(FieldError(where, COPY["tag_missing"]))
            case FieldCondition(key=key) if key not in ctx.fields:
                errors.append(FieldError(where, COPY["field_missing"]))
            case FieldCondition(op="equals", value=value) if not (value or "").strip():
                errors.append(FieldError(where, COPY["value_missing"]))
    return errors


def _action_errors(i: int, step: ActionStep, ctx: Context) -> list[FieldError]:
    where = path(i, "action")
    match step.action:
        case AddTag(tag_id=tag_id) | RemoveTag(tag_id=tag_id) if tag_id not in ctx.tag_ids:
            return [FieldError(where, COPY["tag_missing"])]
        case SetField(key=key) if key not in ctx.fields:
            return [FieldError(where, COPY["field_missing"])]
        case SetField(key=key, value=value):
            try:
                typed_value(ctx.fields[key], value)
            except ValueError as error:
                return [FieldError(f"{where}.value", str(error))]
    return []


Window = Literal["entry", "open", "closed"]


def _path_errors(g: Graph, ctx: Context) -> dict[str, str]:
    """What Instagram allows along every path (see the module docstring), as {step id: copy}.
    ``entry``: nothing sent yet; ``open``: they've written, so messages may follow; ``closed``: a
    comment's private reply went out and they haven't answered."""
    errors: dict[str, str] = {}
    seen: set[tuple[str, Window]] = set()
    stack: list[tuple[str, Window]] = [(g.definition.start, "entry")]
    while stack:
        step_id, window = stack.pop()
        if (step_id, window) in seen:
            continue
        seen.add((step_id, window))
        step = g.by_id[step_id]
        problem, after = _allowed(step, window, ctx, g.definition.start)
        if problem is not None:
            errors.setdefault(step_id, COPY[problem])
        stack.extend((t, after) for t in successors(step) if t is not None)
    return errors


def _allowed(step: Step, window: Window, ctx: Context, start: str) -> tuple[str | None, Window]:
    """(the problem with ``step`` here or None, the window after it)."""
    match step:
        case SendStep() | AskStep():
            if window == "closed":
                return "after_private_reply", "closed"
            private = ctx.comment and window == "entry"
            if private and isinstance(step, SendStep) and step.image_asset_id is not None:
                return "image_in_private_reply", "open" if waits(step) else "closed"
            return None, "open" if waits(step) or not private else "closed"
        case AiReplyStep() if step.id != start:
            return "ai_not_first", window
        case BranchStep() if ctx.comment and window != "open":
            follows = any(isinstance(r.when, FollowsCondition) for r in step.rules)
            return ("follows_too_early" if follows else None), window
        case _:
            return None, window


# ---------------------------------------------------------------- today's automations


def compile_legacy(a: Automation) -> FlowDefinition:
    """The flow equivalent to the automation's message settings (see the module docstring)."""
    if a.action == AutomationAction.AI_REPLY:
        return FlowDefinition(
            start="reply", steps=[AiReplyStep(id="reply", instructions=a.ai_instructions or "")]
        )
    comment = a.trigger in COMMENT_TRIGGERS
    taps_first = a.confirm_first and comment and a.action == AutomationAction.SEND_MESSAGE
    message = SendStep(
        id="message",
        text=a.message_text or "",
        image_asset_id=a.message_media_asset_id,
        buttons=[
            FlowButton(title=str(b["title"]), url=str(b["url"]))
            for b in a.message_buttons or []
            if isinstance(b, dict) and b.get("title") and b.get("url")
        ],
    )
    steps: list[Step] = []
    if taps_first:
        title = (a.opening_button or "").strip() or templates.OPENING_BUTTON
        steps.append(
            SendStep(
                id="opening",
                text=a.opening_text or "",
                quick_replies=[QuickReply(title=title, next="message")],
                on_text="message",
            )
        )
    steps.append(message)
    nudges = (
        a.follow_nudge
        and a.action == AutomationAction.SEND_MESSAGE
        and bool((a.follow_nudge_text or "").strip())
        and (taps_first or not comment)
    )
    if nudges:
        message.next = "follows"
        steps += [
            BranchStep(
                id="follows",
                rules=[BranchRule(when=FollowsCondition(follows=False), next="nudge")],
            ),
            SendStep(
                id="nudge",
                text=a.follow_nudge_text or "",
                buttons=[FlowButton(title=NUDGE_BUTTON, profile=True)],
            ),
        ]
    return FlowDefinition(start=steps[0].id, steps=steps)


def parse(data: object) -> FlowDefinition:
    """A stored definition (it was valid when saved)."""
    return FlowDefinition.model_validate(data)


def try_parse(data: object) -> FlowDefinition | None:
    try:
        return parse(data)
    except ValidationError:
        return None


def walk(g: Graph, choose: Sequence[int] = ()) -> Iterator[Step]:
    """The steps one run would take: at each fork the next choice in ``choose`` (an index into
    ``successors``; 0 when there are none left). For previews and tests."""
    choices = list(choose)
    step_id: str | None = g.definition.start
    while step_id is not None:
        step = g.by_id[step_id]
        yield step
        targets = successors(step)
        if not targets:
            return
        pick = choices.pop(0) if len(targets) > 1 and choices else 0
        step_id = targets[min(pick, len(targets) - 1)]


def _excerpt(text: str, limit: int = 80) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def describe(definition: FlowDefinition) -> list[str]:
    """One line per step a run can reach, in the order a walk meets them (Ask Social Hood reads
    a flow this way)."""
    try:
        g = graph(definition)
    except FlowError:
        return []
    lines = []
    for step_id in reachable(g):
        step = g.by_id[step_id]
        match step:
            case SendStep():
                line = (
                    "send a saved reply"
                    if step.saved_reply_id is not None
                    else f"send “{_excerpt(step.text)}”"
                )
                if step.quick_replies:
                    line += " with quick replies " + ", ".join(q.title for q in step.quick_replies)
                if step.buttons:
                    line += " with buttons " + ", ".join(b.title for b in step.buttons)
            case AskStep():
                line = f"ask for {step.expect}: “{_excerpt(step.text)}”"
                if step.field_key:
                    line += f", saved to {step.field_key}"
            case BranchStep():
                kinds = ", ".join(rule.when.kind for rule in step.rules)
                line = f"branch on {kinds or 'nothing'}"
            case ActionStep():
                line = step.action.kind.replace("_", " ")
            case DelayStep():
                line = f"wait {step.seconds // 60} minutes"
            case RandomizeStep():
                line = f"split {len(step.paths)} ways"
            case AiReplyStep():
                line = "AI reply"
            case _:
                line = "end"
        lines.append(f"{step.id}: {line}")
    return lines
