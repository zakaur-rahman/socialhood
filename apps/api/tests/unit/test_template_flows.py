"""GR-16: the templates that carry a flow. Each is a valid graph within the Free plan's step cap
(PD-5, pending), asks only for what the user must fill in (the link), and has plain copy."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from socialhood.billing.plans import entitlement
from socialhood.schemas.flows import (
    ActionStep,
    AskStep,
    FlowDefinition,
    NotifyTeam,
    SendStep,
)
from socialhood.services.automations import flows, templates, validation
from socialhood.services.automations.validation import AccountInfo, Definition

FLOW_TEMPLATES = [t for t in templates.TEMPLATES if t.flow is not None]
KEYS = ["story_giveaway", "lead_magnet", "price_by_option", "call_request", "entry_link_coupon"]
NOW = datetime(2026, 10, 24, tzinfo=UTC)


def context(template: templates.Template) -> flows.Context:
    return flows.Context(trigger=template.trigger, disclosure="Sent automatically")


def flow_of(template: templates.Template) -> FlowDefinition:
    assert template.flow is not None
    return template.flow


def link_fields(definition: FlowDefinition) -> list[str]:
    return [
        f"flow.steps.{i}.buttons.{b}.url"
        for i, step in enumerate(definition.steps)
        if isinstance(step, SendStep)
        for b in range(len(step.buttons))
    ]


def test_the_v2_templates_are_in_the_gallery() -> None:
    assert [t.key for t in FLOW_TEMPLATES] == KEYS
    summaries = {t.key: t for t in templates.gallery().items}
    assert {k: summaries[k].steps for k in KEYS} == {
        "story_giveaway": 2,
        "lead_magnet": 2,
        "price_by_option": 4,
        "call_request": 2,
        "entry_link_coupon": 1,
    }
    # The older templates are single messages.
    assert summaries["send_link"].steps == 0


@pytest.mark.parametrize("template", FLOW_TEMPLATES, ids=lambda t: t.key)
def test_each_flow_template_validates_and_builds(template: templates.Template) -> None:
    definition = flow_of(template)
    # It round-trips through the stored JSON, as the create route saves it.
    assert FlowDefinition.model_validate(definition.model_dump(mode="json")) == definition
    graph = flows.graph(definition)
    assert set(flows.reachable(graph)) == {s.id for s in definition.steps}
    assert len({s.id for s in definition.steps}) == len(definition.steps)


@pytest.mark.parametrize("template", FLOW_TEMPLATES, ids=lambda t: t.key)
def test_each_flow_template_needs_only_its_link(template: templates.Template) -> None:
    definition = flow_of(template)
    found = [e.field for e in flows.activation_errors(definition, context(template))]
    assert sorted(found) == sorted(link_fields(definition))


@pytest.mark.parametrize("template", FLOW_TEMPLATES, ids=lambda t: t.key)
def test_each_flow_template_activates_once_the_link_is_filled(
    template: templates.Template,
) -> None:
    definition = flow_of(template)
    filled = definition.model_copy(deep=True)
    for step in filled.steps:
        if isinstance(step, SendStep):
            for button in step.buttons:
                button.url = "https://example.com/offer"
    assert flows.activation_errors(filled, context(template)) == []
    # The rest of the automation: only an account is chosen, and a post for a comment trigger
    # that needs one (these use "all posts" with a keyword).
    d = Definition(
        social_account_id=uuid.uuid4(),
        account=AccountInfo(platform="instagram", status="active"),
        trigger=template.trigger,
        keywords=list(template.keywords),
        post_scope=template.post_scope,
        posts=[],
        action=template.action,
        message_text=None,
        message_buttons=[],
        public_reply_texts=list(template.public_reply_texts),
        starts_at=None,
        ends_at=None,
        uses_flow=True,
    )
    assert validation.activation_errors(d, disclosure=None, now=NOW) == []


@pytest.mark.parametrize("template", FLOW_TEMPLATES, ids=lambda t: t.key)
def test_each_flow_template_fits_the_free_plan_step_cap(template: templates.Template) -> None:
    cap = entitlement("free", "flow_steps")
    assert cap is not None
    assert len(flow_of(template).steps) <= int(cap)  # PD-5, pending


def test_the_questions_save_to_the_contact_and_the_team_is_told() -> None:
    lead = flow_of(templates.BY_KEY["lead_magnet"])
    ask = lead.steps[0]
    assert isinstance(ask, AskStep)
    assert (ask.expect, ask.field_key) == ("email", None)
    call = flow_of(templates.BY_KEY["call_request"])
    phone, notify = call.steps
    assert isinstance(phone, AskStep)
    assert (phone.expect, phone.field_key) == ("phone", None)
    assert isinstance(notify, ActionStep)
    assert isinstance(notify.action, NotifyTeam)


def test_price_by_option_has_a_price_for_every_quick_reply() -> None:
    first, *prices = flow_of(templates.BY_KEY["price_by_option"]).steps
    assert isinstance(first, SendStep)
    assert [q.next for q in first.quick_replies] == [p.id for p in prices]
    assert all(len(q.title) <= 20 for q in first.quick_replies)


def messages(definition: FlowDefinition) -> list[str]:
    out = []
    for step in definition.steps:
        if isinstance(step, SendStep):
            out.append(step.text)
        elif isinstance(step, AskStep):
            out += [step.text, step.retry_text, step.confirm_text]
        elif isinstance(step, ActionStep) and isinstance(step.action, NotifyTeam):
            out.append(step.action.note)
    return [m for m in out if m]


@pytest.mark.parametrize("template", FLOW_TEMPLATES, ids=lambda t: t.key)
def test_template_copy_is_plain(template: templates.Template) -> None:
    texts = [template.name, template.outcome, *messages(flow_of(template))]
    for text in texts:
        assert "please" not in text.casefold()
        assert "\N{SINGLE RIGHT-POINTING ANGLE QUOTATION MARK}" not in text
    # Sentence case: only the first word of a name or outcome is capitalised.
    for text in (template.name, template.outcome):
        assert text[0].isupper()
        words = [w for w in text.split()[1:] if w.isalpha() and not w.isupper()]
        assert not any(w[0].isupper() for w in words)
