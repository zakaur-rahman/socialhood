"""The agent eval's checks (TA.6, tests/evals/checks.py): reading numbers the way answers write
them, grounding them in the run's tool results, and the tool-choice, exact-number, citation,
card and text checks. No model and no database."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from tests.evals import checks
from tests.evals.checks import Expect

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 9, 30, 6, 30, tzinfo=UTC)  # Wed 30 Sep 2026, 12:00 IST


def values(text: str) -> list[Decimal]:
    return [n.value for n in checks.numbers(text)]


# ---------------------------------------------------------------- reading numbers


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("It reached 4,125 people", [Decimal(4125)]),
        ("₹1,23,456 in sales", [Decimal(123456)]),
        ("50% positive, 3.5 stars", [Decimal(50), Decimal("3.5")]),
        ("about 2 lakh views", [Decimal(200000)]),
        ("1.5 crore", [Decimal(15000000)]),
        ("4.1k likes", [Decimal(4100)]),
        ("१२ कमेंट और ३ स्पैम", [Decimal(12), Decimal(3)]),
        ("three negative comments, one of them spam", [Decimal(3)]),
        ("five hazaar", [Decimal(5)]),
        ("No numbers here.", []),
    ],
)
def test_numbers_are_read_as_written(text: str, expected: list[Decimal]) -> None:
    assert values(text) == expected


def test_a_number_keeps_the_precision_it_was_written_with() -> None:
    [whole, decimal, thousands] = checks.numbers("69 and 69.2 and 4.1k")
    assert (whole.precision, decimal.precision, thousands.precision) == (
        Decimal(1),
        Decimal("0.1"),
        Decimal(100),
    )
    assert checks.numbers("12%")[0].percent


def test_citations_links_handles_and_list_numbers_are_not_numbers() -> None:
    text = (
        "1. Reel of 26 Sep reached 4,125 [1][2].\n"
        "2. See maplebakery.in/menu and @maple.bakery [3, 4]\n"
        "Costs ₹999."
    )
    assert values(checks.strip_noise(text)) == [Decimal(26), Decimal(4125), Decimal(999)]


def test_dates_and_times_are_read_in_the_workspace_zone() -> None:
    found = checks.moments("21-27 Sep 2026, Oct 1 and 2026-09-30T11:30:00Z at 7:15 PM", IST)
    assert found.dates == {(9, 21), (9, 27), (10, 1), (9, 30)}
    assert found.times == {(5, 0), (7, 15)}  # 11:30 UTC is 17:00 IST
    en_dash = checks.moments("28\N{EN DASH}30 September and Sep 5th")
    assert en_dash.dates == {(9, 28), (9, 30), (9, 5)}


# ---------------------------------------------------------------- grounding


def pool(*results: object, request: str = "") -> checks.Pool:
    return checks.pool_of(results, request=request, now=NOW, timezone=IST)


def test_numbers_from_the_results_are_grounded() -> None:
    result = {
        "summary": "Found 6 needs-reply conversations",
        "total": 6,
        "items": [{"contact": "Priya Shah", "lead_score": 82}],
    }
    grounding = checks.ground(
        "6 conversations need a reply; Priya Shah's score is 82 [1].", pool(result)
    )
    assert grounding.passed
    assert grounding.checked == 2


def test_an_invented_number_is_flagged() -> None:
    grounding = checks.ground("You have 7 leads and 12 unread messages.", pool({"total": 7}))
    assert grounding.flagged == ["12"]


def test_roundings_shares_sums_and_counts_are_derived_values() -> None:
    result = {
        "positive": 4,
        "neutral": 2,
        "negative": 2,
        "positive_share": 0.5,
        "reach_diff_pct": 69.24,
        "items": [{"id": 1}, {"id": 2}, {"id": 3}],
    }
    answer = (
        "Half are positive (50%): 6 are positive or neutral, 2 more positive than negative. "
        "Reach is 69% above the median across 3 posts."
    )
    assert checks.ground(answer, pool(result)).passed
    # A sum of three is not a trivial derivation: the tools state totals themselves.
    assert checks.ground("8 analysed.", pool(result)).flagged == ["8"]


def test_sums_across_unrelated_nested_objects_are_not_derived() -> None:
    result = {"a": {"likes": 40}, "b": {"likes": 50}}
    assert checks.ground("Together 90 likes.", pool(result)).flagged == ["90"]


def test_numbers_in_the_request_and_the_clock_are_grounded() -> None:
    grounding = checks.ground(
        "Your top 5 posts as of 30 Sep 2026, 12:00.", pool({"items": []}, request="top 5 posts")
    )
    assert grounding.passed


def test_dates_and_times_must_come_from_a_result() -> None:
    result = {"period": {"label": "21-27 Sep 2026"}, "send_at": "2026-09-30T11:30:00Z"}
    assert checks.ground("Last week (21-27 Sep 2026) it goes out at 5 PM.", pool(result)).passed
    grounding = checks.ground("It goes out on 3 Oct at 9:45 AM.", pool(result))
    assert grounding.flagged == ["3 Oct", "9:45 AM"]


def test_a_failed_step_reason_counts_as_what_the_model_was_shown() -> None:
    reason = "Meera's window closes tomorrow at 7:00 AM, so the latest time is 6:55 AM."
    assert checks.ground("The latest I can prepare is 6:55 AM.", pool(reason)).passed


# ---------------------------------------------------------------- the other checks


def test_tool_choice_needs_one_acceptable_tool_and_no_forbidden_one() -> None:
    expect = {"get_post_comments", "sentiment_distribution"}
    assert checks.tool_choice(["get_latest_post", "sentiment_distribution"], expect).passed
    missing = checks.tool_choice(["get_posts"], expect)
    assert (missing.passed, missing.missing) == (False, True)
    forbidden = checks.tool_choice(["list_automations"], set(), {"list_automations"})
    assert (forbidden.passed, forbidden.forbidden) == (False, ["list_automations"])
    assert checks.tool_choice([], set(), {"list_automations"}).passed


def test_expected_numbers_match_as_people_round_them() -> None:
    answer = "Reach 4,125 (69% above the median); engagement 12.1%; 2 negative [1]."
    found = checks.exact_numbers(
        answer,
        [Expect(4125), Expect(69.24), Expect(12.12), Expect(2), Expect(9, (8,), "yesterday")],
    )
    assert found.missing == ["yesterday"]
    assert checks.exact_numbers("8 comments yesterday", [Expect(9, (8,))]).passed


def test_a_citation_number_is_not_an_expected_number() -> None:
    assert not checks.exact_numbers("See [2].", [Expect(2)]).passed


def test_every_citation_needs_an_answer_ref() -> None:
    refs = [{"kind": "post"}, {"kind": "comment"}]
    assert checks.citations("Reach 4,125 [1] and comments [1, 2].", refs).passed
    assert checks.citations("Something [3].", refs).invalid == [3]


def test_brackets_hold_only_citations() -> None:
    refs = [{"kind": "post"}] * 6
    found = checks.citations("Mostly positive [summary]; topics [1-6] and [] [2].", refs)
    assert found.stray == ["[summary]", "[1-6]", "[]"]
    assert not found.passed


def test_text_drafted_for_a_card_is_grounded_too() -> None:
    args = {"text": "Hi Kavya! Hampers start at ₹1,500.", "private": True}
    drafts = checks.drafted_texts("prepare_comment_reply", args)
    assert drafts == ["Hi Kavya! Hampers start at ₹1,500."]
    assert checks.drafted_texts("search_comments", {"q": "price 1500"}) == []
    known = pool("Diwali hampers cost ₹1,200 (small) and ₹2,500 (large).")
    grounding = checks.ground_run("I prepared the reply [1].", drafts, known)
    assert grounding.flagged == ["1,500 (drafted text)"]
    assert checks.ground_run("Done.", ["They cost ₹1,200."], known).passed


def test_card_and_text_expectations() -> None:
    cards = [{"kind": "schedule_message"}]
    assert checks.card_kind(cards, "schedule_message")
    assert not checks.card_kind(cards, "automation_draft")
    assert checks.card_kind([], None)
    missing = checks.text_expectations("Rahul's window closes soon.", [r"rahul", r"refund"])
    assert missing == [r"refund"]
