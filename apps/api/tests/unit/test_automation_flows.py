"""GR-03: flows. Their structure, what activation and Instagram allow, and the regression suite:
every template, with tap first and the follow nudge on and off, compiles to a flow that sends
what the current automation sends (services/automations/dry_run renders the current one)."""

from __future__ import annotations

import itertools
import uuid
from typing import Any

import pytest

from socialhood.models.automations import Automation
from socialhood.schemas.automations import AutomationTest
from socialhood.schemas.flows import (
    ActionStep,
    AiReplyStep,
    AskStep,
    BranchStep,
    FlowDefinition,
    SendStep,
)
from socialhood.services.automations import actions, dry_run, flows, render, templates

DISCLOSURE = "Sent automatically"
TAG = uuid.uuid4()


def flow(*steps: dict[str, Any], start: str | None = None) -> FlowDefinition:
    return FlowDefinition.model_validate({"start": start or steps[0]["id"], "steps": list(steps)})


def ctx(trigger: str = "dm_keyword", **kw: Any) -> flows.Context:
    return flows.Context(
        trigger=trigger,
        disclosure=None,
        fields=kw.get(
            "fields", {"city": flows.FieldSpec("text"), "mail": flows.FieldSpec("email")}
        ),
        tag_ids=frozenset({TAG}),
    )


def errors(definition: FlowDefinition, context: flows.Context) -> dict[str, str]:
    return {e.field: e.message for e in flows.activation_errors(definition, context)}


def send(id: str, text: str = "Hi", **kw: Any) -> dict[str, Any]:
    return {"type": "send", "id": id, "text": text, **kw}


# ---------------------------------------------------------------- structure


def test_a_broken_graph_names_each_step() -> None:
    broken = flow(send("a", next="b"), send("a"), send("c", next="nowhere"), start="zz")
    with pytest.raises(flows.FlowError) as raised:
        flows.graph(broken)
    assert {e.field: e.message for e in raised.value.errors} == {
        "flow.steps.1.id": flows.COPY["duplicate_id"],
        "flow.start": flows.COPY["start_missing"],
        "flow.steps.0": flows.COPY["next_missing"],
        "flow.steps.2": flows.COPY["next_missing"],
    }


def test_a_loop_is_refused() -> None:
    looping = flow(send("a", next="b"), send("b", next="c"), send("c", next="a"))
    with pytest.raises(flows.FlowError) as raised:
        flows.graph(looping)
    assert [e.field for e in raised.value.errors] == ["flow.steps.2"]


def test_branches_may_meet_again() -> None:
    joined = flow(
        {"type": "randomize", "id": "ab", "paths": [{"next": "a"}, {"next": "b"}]},
        send("a", next="end"),
        send("b", next="end"),
        {"type": "end", "id": "end"},
    )
    assert errors(joined, ctx()) == {}


def test_an_unreachable_step_blocks_activation() -> None:
    assert errors(flow(send("a"), send("b")), ctx()) == {"flow.steps.1": flows.COPY["unreachable"]}


# ---------------------------------------------------------------- steps


def test_message_rules() -> None:
    found = errors(
        flow(
            send(
                "a",
                "",
                buttons=[{"title": "Go", "url": "http://x.com"}, {"title": "Me"}],
                quick_replies=[{"title": "Yes"}],
                image_asset_id=str(uuid.uuid4()),
            )
        ),
        ctx(),
    )
    assert found == {
        "flow.steps.0.text": flows.COPY["text_missing"],
        "flow.steps.0.quick_replies": flows.COPY["buttons_and_replies"],
        "flow.steps.0.image_asset_id": flows.COPY["image_and_replies"],
        "flow.steps.0.buttons.0.url": "Use a full link that starts with https://.",
        "flow.steps.0.buttons.1.url": flows.COPY["button_link"],
    }
    long = flow(send("a", "é" * 501))
    assert "1,002" in errors(long, ctx())["flow.steps.0.text"]


def test_questions_need_a_matching_field() -> None:
    def ask(**kw: Any) -> dict[str, Any]:
        return {"type": "ask", "id": "q", "text": "Your email?", **kw}

    assert errors(flow(ask(expect="email")), ctx()) == {}  # the contact's own email
    assert errors(flow(ask(expect="email", field_key="mail")), ctx()) == {}
    assert errors(flow(ask(expect="text")), ctx()) == {
        "flow.steps.0.field_key": flows.COPY["answer_field"]
    }
    assert errors(flow(ask(expect="phone", field_key="city")), ctx()) == {
        "flow.steps.0.field_key": flows.COPY["field_type"]
    }
    assert errors(flow(ask(field_key="gone")), ctx()) == {
        "flow.steps.0.field_key": flows.COPY["field_missing"]
    }


def test_branches_and_actions_name_tags_and_fields_that_exist() -> None:
    gone = str(uuid.uuid4())
    found = errors(
        flow(
            {
                "type": "branch",
                "id": "b",
                "rules": [
                    {"when": {"kind": "tag", "tag_id": gone}, "next": "t"},
                    {"when": {"kind": "field", "key": "nope"}, "next": "t"},
                    {"when": {"kind": "field", "key": "city", "op": "equals"}, "next": "t"},
                    {"when": {"kind": "tag", "tag_id": str(TAG)}, "next": "t"},
                ],
                "otherwise": "n",
            },
            {"type": "action", "id": "t", "action": {"kind": "add_tag", "tag_id": gone}},
            {
                "type": "action",
                "id": "n",
                "action": {"kind": "set_field", "key": "mail", "value": "not-an-email"},
            },
        ),
        ctx(),
    )
    assert found == {
        "flow.steps.0.rules.0.when": flows.COPY["tag_missing"],
        "flow.steps.0.rules.1.when": flows.COPY["field_missing"],
        "flow.steps.0.rules.2.when": flows.COPY["value_missing"],
        "flow.steps.1.action": flows.COPY["tag_missing"],
        "flow.steps.2.action.value": "Enter an email address like name@example.com.",
    }


# ---------------------------------------------------------------- what Instagram allows


def test_a_comment_gets_one_reply_until_they_answer() -> None:
    two = flow(send("a", next="b"), send("b"))
    assert errors(two, ctx("comment_keyword")) == {
        "flow.steps.1": flows.COPY["after_private_reply"]
    }
    assert errors(two, ctx("dm_keyword")) == {}
    asked = flow(
        send("a", quick_replies=[{"title": "Yes", "next": "b"}]),
        send("b", next="q"),
        {"type": "ask", "id": "q", "text": "Email?", "expect": "email", "next": "c"},
        send("c"),
    )
    assert errors(asked, ctx("comment_keyword")) == {}


def test_a_typed_answer_ending_the_flow_is_allowed() -> None:
    tapped = flow(send("a", quick_replies=[{"title": "Yes", "next": "b"}]), send("b"))
    assert errors(tapped, ctx("comment_any")) == {}


def test_a_private_reply_takes_no_image_and_no_delay() -> None:
    image = flow(send("a", image_asset_id=str(uuid.uuid4())))
    assert errors(image, ctx("comment_keyword")) == {
        "flow.steps.0": flows.COPY["image_in_private_reply"]
    }
    delayed = flow({"type": "delay", "id": "d", "seconds": 60, "next": "a"}, send("a"))
    assert errors(delayed, ctx("comment_keyword")) == {"flow.start": flows.COPY["comment_start"]}
    assert errors(delayed, ctx("dm_keyword")) == {}


def test_following_is_known_once_they_have_written() -> None:
    check = {
        "type": "branch",
        "id": "f",
        "rules": [{"when": {"kind": "follows_business", "follows": False}, "next": "n"}],
    }
    early = flow(check, send("n"))
    assert errors(early, ctx("comment_keyword")) == {
        "flow.start": flows.COPY["comment_start"],
        "flow.steps.0": flows.COPY["follows_too_early"],
    }
    assert errors(early, ctx("dm_keyword")) == {}


def test_an_ai_reply_comes_first() -> None:
    later = flow(send("a", next="ai"), {"type": "ai_reply", "id": "ai", "instructions": "Help"})
    assert errors(later, ctx()) == {"flow.steps.1": flows.COPY["ai_not_first"]}
    tagged_first = flow(
        {
            "type": "action",
            "id": "t",
            "action": {"kind": "add_tag", "tag_id": str(TAG)},
            "next": "ai",
        },
        {"type": "ai_reply", "id": "ai", "instructions": ""},
    )
    assert errors(tagged_first, ctx("dm_keyword")) == {
        "flow.steps.1.instructions": flows.COPY["ai_instructions"],
        "flow.steps.1": flows.COPY["ai_not_first"],
    }


# ---------------------------------------------------------------- the regression suite


def automation(template: templates.Template, **overrides: Any) -> Automation:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": template.name,
        "status": "active",
        "social_account_id": uuid.uuid4(),
        "trigger": template.trigger,
        "match_mode": "word",
        "action": template.action,
        "message_text": template.message_text,
        "message_buttons": [
            {"title": b.title, "url": "https://shop.in/x"} for b in template.message_buttons
        ],
        "message_media_asset_id": None,
        "ai_instructions": template.ai_instructions,
        "public_reply_texts": list(template.public_reply_texts),
        "post_scope": template.post_scope,
        "surge_order": "oldest_first",
        "cooldown_hours": template.cooldown_hours,
        "confirm_first": template.confirm_first,
        "opening_text": templates.OPENING_TEXT,
        "opening_button": templates.OPENING_BUTTON,
        "follow_nudge": template.follow_nudge,
        "follow_nudge_text": templates.FOLLOW_NUDGE_TEXT,
    }
    values.update(overrides)
    return Automation(**values)


def variants() -> list[tuple[str, Automation]]:
    found = []
    for template in templates.TEMPLATES:
        if template.flow is not None:  # GR-16: saved as a flow, not compiled from settings
            continue
        if template.trigger == "comment_any":
            triggers: tuple[str, ...] = ("comment_any",)
        elif template.trigger in ("story_reply", "story_mention"):
            triggers = (template.trigger, "dm_keyword")  # GR-06, GR-07: DM triggers
        else:
            triggers = ("dm_keyword", "comment_keyword")
        for trigger, tap, nudge in itertools.product(triggers, (True, False), (True, False)):
            name = f"{template.key}-{trigger}-tap{int(tap)}-nudge{int(nudge)}"
            found.append(
                (name, automation(template, trigger=trigger, confirm_first=tap, follow_nudge=nudge))
            )
    return found


def rendered(step: SendStep) -> str:
    text = render.render(
        step.text, first_name=dry_run.SAMPLE_FIRST_NAME, username=dry_run.SAMPLE_USERNAME
    )
    return render.with_disclosure(text, DISCLOSURE)


@pytest.mark.parametrize(("name", "a"), variants(), ids=[n for n, _ in variants()])
def test_every_template_compiles_to_a_flow_that_sends_the_same(name: str, a: Automation) -> None:
    kind = "comment" if a.trigger in flows.COMMENT_TRIGGERS else "dm"
    legacy = dry_run._rendered(a, AutomationTest(kind=kind, text="link"), DISCLOSURE)
    g = flows.graph(flows.compile_legacy(a))
    # The path where they tap the opening and don't follow the account: every message shows.
    steps = list(flows.walk(g, choose=[0, 0]))

    if a.action == "ai_reply":
        assert steps == [AiReplyStep(id="reply", instructions=a.ai_instructions or "")]
        return
    sends = [s for s in steps if isinstance(s, SendStep)]
    expected = [legacy.opening, legacy.message, legacy.nudge]
    assert [rendered(s) for s in sends] == [t for t in expected if t is not None]

    first = sends[0]
    if actions.opens_first(a):
        assert [(q.title, q.next) for q in first.quick_replies] == [(a.opening_button, "message")]
        assert first.on_text == "message"  # a typed answer releases it too (FR-AUT-21)
    else:
        assert first.quick_replies == []
    message = g.step("message")
    assert isinstance(message, SendStep)
    assert [(b.title, b.url) for b in message.buttons] == [
        (b.title, b.url) for b in actions.buttons(a)
    ]
    if legacy.nudge is not None:
        branch = g.step("follows")
        assert isinstance(branch, BranchStep)
        assert branch.rules[0].when.model_dump() == {"kind": "follows_business", "follows": False}
        assert branch.otherwise is None  # followers get nothing more
        nudge = g.step("nudge")
        assert isinstance(nudge, SendStep)
        assert [(b.title, b.profile) for b in nudge.buttons] == [(actions.NUDGE_BUTTON, True)]
    # An active template's flow activates as it is.
    assert flows.activation_errors(g.definition, ctx(a.trigger or "", fields={})) == []


def test_a_message_with_an_image_keeps_it() -> None:
    asset = uuid.uuid4()
    a = automation(templates.BY_KEY["catalogue_by_dm"], message_media_asset_id=asset)
    message = flows.graph(flows.compile_legacy(a)).step("message")
    assert isinstance(message, SendStep)
    assert message.image_asset_id == asset


def test_an_incomplete_draft_still_compiles() -> None:
    draft = Automation(
        id=uuid.uuid4(),
        name="Untitled automation",
        trigger=None,
        action=None,
        message_text=None,
        message_buttons=[],
        confirm_first=True,
        opening_text=None,
        opening_button=None,
        follow_nudge=False,
    )
    definition = flows.compile_legacy(draft)
    assert definition.start == "message"
    assert [s.id for s in definition.steps] == ["message"]


def test_step_types_parse_from_json() -> None:
    parsed = flows.parse(
        {
            "start": "q",
            "steps": [
                {"type": "ask", "id": "q", "text": "Email?", "expect": "email", "next": "t"},
                {"type": "action", "id": "t", "action": {"kind": "hand_off"}},
            ],
        }
    )
    assert isinstance(parsed.steps[0], AskStep)
    assert isinstance(parsed.steps[1], ActionStep)
    assert flows.try_parse({"start": "x", "steps": [{"type": "nope", "id": "x"}]}) is None


def test_a_flow_described_step_by_step() -> None:
    described = flows.describe(
        flow(
            send("hello", "Hi!", quick_replies=[{"title": "Yes", "next": "q"}]),
            {"type": "ask", "id": "q", "text": "City?", "field_key": "city", "next": "wait"},
            {"type": "delay", "id": "wait", "seconds": 600, "next": "t"},
            {"type": "action", "id": "t", "action": {"kind": "hand_off"}},
        )
    )
    assert described == [
        "hello: send “Hi!” with quick replies Yes",
        "q: ask for text: “City?”, saved to city",
        "wait: wait 10 minutes",
        "t: hand off",
    ]


# ---------------------------------------------------------------- story triggers (GR-06, GR-07)


@pytest.mark.parametrize("trigger", ["story_reply", "story_mention"])
def test_a_story_trigger_is_a_dm_trigger_for_flows(trigger: str) -> None:
    """A story reply or mention is a DM: the flow may start with a branch or a delay, which a
    comment's flow may not, and it can be answered like any DM."""
    assert ctx(trigger).comment is False
    delayed = flow({"type": "delay", "id": "d", "seconds": 60, "next": "a"}, send("a"))
    assert errors(delayed, ctx(trigger)) == {}
