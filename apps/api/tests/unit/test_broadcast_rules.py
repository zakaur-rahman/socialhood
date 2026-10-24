"""GR-23: template variables, the rate card and the estimate, and the plan's quota entries."""

from __future__ import annotations

from decimal import Decimal

import pytest

from socialhood.billing import plans
from socialhood.services.broadcasts import rates
from socialhood.services.broadcasts import variables as v

FIELD = {"source": "field", "field": "first_name", "fallback": None}


def test_a_field_takes_the_contacts_value() -> None:
    assert v.resolve([FIELD], {"first_name": " Asha "}) == ["Asha"]


def test_first_name_falls_back_to_there() -> None:
    assert v.resolve([FIELD], {"first_name": None}) == ["there"]
    assert v.resolve([FIELD], {}) == ["there"]


def test_a_named_fallback_is_used_for_an_empty_value() -> None:
    spec = {"source": "field", "field": "city", "fallback": "your city"}
    assert v.resolve([spec], {"city": ""}) == ["your city"]
    assert v.resolve([spec], {"city": "Pune"}) == ["Pune"]


def test_a_field_with_no_value_and_no_fallback_leaves_the_person_out() -> None:
    spec = {"source": "field", "field": "city", "fallback": None}
    assert v.resolve([spec], {"city": None}) is None
    assert v.resolve([FIELD, spec], {"first_name": "Asha"}) is None


def test_a_fixed_text_is_the_same_for_everyone() -> None:
    fixed = {"source": "fixed", "value": "31 October"}
    assert v.resolve([FIELD, fixed], {"first_name": "Asha"}) == ["Asha", "31 October"]


def test_parameters_are_cleaned_for_whatsapp() -> None:
    assert v.clean_param("line one\nline two\tend") == "line one line two end"
    assert v.clean_param("a     b") == "a b"  # four or more spaces in a row
    assert len(v.clean_param("x" * 5000)) == v.MAX_PARAM


def test_the_body_is_drawn_with_the_parameters() -> None:
    body = "Hi {{1}}, sale until {{2}}. {{3}}"
    assert v.render_body(body, ["Asha", "Friday"]) == "Hi Asha, sale until Friday. "
    assert v.render_body("No variables", []) == "No variables"


def test_the_mapping_must_fit_the_template() -> None:
    assert v.problems([FIELD], param_count=1, field_keys=set()) == []
    wrong_count = v.problems([FIELD], param_count=2, field_keys=set())
    assert len(wrong_count) == 1
    assert "2 variables" in wrong_count[0][1]
    unknown = v.problems([{"source": "field", "field": "nope"}], param_count=1, field_keys={"city"})
    assert unknown == [(1, "Choose a contact field for variable 1.")]
    custom = v.problems([{"source": "field", "field": "city"}], param_count=1, field_keys={"city"})
    assert custom == []
    empty = v.problems([{"source": "fixed", "value": "  "}], param_count=1, field_keys=set())
    assert empty == [(1, "Write the text for variable 1.")]


def test_the_estimate_is_the_rate_times_the_people() -> None:
    card = rates.RATE_CARD
    assert card.currency == "INR"
    assert card.verified is False  # typed in by hand, never claimed as read from Meta
    assert rates.estimate("marketing", 0) == Decimal("0.00")
    assert rates.estimate("marketing", 1_000) == (card.rates["marketing"] * 1_000).quantize(
        Decimal("0.01")
    )
    assert rates.estimate("utility", 100) < rates.estimate("marketing", 100)


def test_an_unknown_category_is_priced_as_marketing() -> None:
    assert rates.rate_for("something_new") == rates.RATE_CARD.rates["marketing"]


def test_rounding_goes_to_the_paisa() -> None:
    card = rates.RateCard(
        "INR", "India", "2026-01-01", "test", False, {"marketing": Decimal("0.785")}
    )
    assert rates.estimate("marketing", 1, card) == Decimal("0.79")


@pytest.mark.parametrize(("plan", "limit"), [("free", 0), ("pro", 2_500), ("max", 25_000)])
def test_the_monthly_recipients_by_plan(plan: str, limit: int) -> None:
    """PD-4, decided 2026-10-24: Pro and Max with a monthly recipient quota, not Free."""
    assert plans.entitlement(plan, "broadcast_recipients_monthly") == limit
