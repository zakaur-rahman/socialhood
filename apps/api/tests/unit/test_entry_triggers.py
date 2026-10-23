"""GR-08, GR-09: the entry link and ad click triggers (pure: no database) - the order they run in,
reading a stored referral, the scope of an ad click and an entry link, activation, and the QR
code."""

from __future__ import annotations

import io
import re
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
import segno

from socialhood.schemas.entry_links import CODE_PATTERN
from socialhood.services.automations import entry, matching, validation
from socialhood.services.automations.matching import Candidate
from socialhood.services.entry_links import CODE_LENGTH, QR_BORDER, QR_SCALE, _new_code, link_url

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def candidate(trigger: Any, keywords: tuple[str, ...] = (), priority: int = 100) -> Candidate:
    return Candidate(
        id=uuid.uuid4(),
        trigger=trigger,
        match_mode="word",
        keywords=keywords,
        priority=priority,
        created_at=NOW,
    )


def test_entry_automations_answer_anything_and_run_before_keyword_ones() -> None:
    keyword = candidate("dm_keyword", ("hi",), priority=1)
    link = candidate("entry_link", priority=50)
    ad = candidate("ad_click", priority=60)
    story = candidate("story_mention")
    assert matching.matches_anything(link)
    assert matching.matches_anything(ad)
    assert matching.runtime_order([story, keyword, ad, link]) == [link, ad, keyword, story]
    found = matching.matches("hello there", [keyword, link])
    assert [m.automation_id for m in found] == [link.id]
    assert found[0].keyword == ""


def referral(**values: Any) -> dict[str, Any]:
    return {"source": "link", "ref": "spring", "at": NOW.isoformat(), **values}


def test_a_stored_link_referral_is_an_entry_with_its_time() -> None:
    parsed = entry.parse(referral())
    assert parsed is not None
    found, at = parsed
    assert (found.source, found.ref, found.trigger) == ("link", "spring", "entry_link")
    assert at == NOW


def test_a_stored_ad_referral_is_an_ad_entry() -> None:
    parsed = entry.parse(referral(source="ad", ref=None, ad_id="ad_77", ctwa_clid="c1"))
    assert parsed is not None
    assert (parsed[0].source, parsed[0].ad_id, parsed[0].trigger) == ("ad", "ad_77", "ad_click")


@pytest.mark.parametrize(
    "record",
    [None, {}, {"source": "other", "at": NOW.isoformat()}, {"source": "link", "at": "nonsense"}],
)
def test_other_referrals_are_not_entries(record: dict[str, Any] | None) -> None:
    assert entry.parse(record) is None


def automation(trigger: str, **values: Any) -> Any:
    return SimpleNamespace(
        id=values.pop("id", uuid.uuid4()),
        trigger=trigger,
        post_scope=values.pop("scope", "all"),
        ad_ids=values.pop("ads", []),
    )


def test_an_entry_link_automation_answers_only_links_that_point_at_it() -> None:
    mine = automation("entry_link")
    own = entry.Entry("link", "spring", None, mine.id)
    other = entry.Entry("link", "autumn", None, uuid.uuid4())
    assert entry.in_scope(mine, own)
    assert not entry.in_scope(mine, other)
    assert not entry.in_scope(mine, entry.Entry("ad", None, "ad_1"))


@pytest.mark.parametrize(
    ("scope", "chosen", "ad_id", "expected"),
    [
        ("all", [], "ad_1", True),
        ("selected", ["ad_1", "ad_2"], "ad_2", True),
        ("selected", ["ad_1"], "ad_9", False),
        ("selected", ["ad_1"], None, False),
    ],
)
def test_an_ad_click_answers_any_ad_or_its_chosen_ads(
    scope: str, chosen: list[str], ad_id: str | None, expected: bool
) -> None:
    ad_click = automation("ad_click", scope=scope, ads=chosen)
    assert entry.in_scope(ad_click, entry.Entry("ad", None, ad_id)) is expected


def test_an_ad_click_does_not_answer_a_link_and_other_triggers_are_unlimited() -> None:
    assert not entry.in_scope(automation("ad_click"), entry.Entry("link", "x"))
    assert entry.in_scope(automation("dm_keyword"), entry.Entry("ad", None, "ad_1"))


# ---------------------------------------------------------------- activation


def definition(**values: Any) -> validation.Definition:
    base: dict[str, Any] = {
        "social_account_id": uuid.uuid4(),
        "account": validation.AccountInfo("instagram", "active"),
        "trigger": "entry_link",
        "keywords": [],
        "post_scope": "all",
        "posts": [],
        "action": "send_message",
        "message_text": "Welcome!",
        "message_buttons": [],
        "public_reply_texts": [],
        "starts_at": None,
        "ends_at": None,
    }
    return validation.Definition(**{**base, **values})


def fields(d: validation.Definition) -> list[str]:
    return validation.missing_fields(validation.activation_errors(d, disclosure=None, now=NOW))


def test_an_entry_link_automation_needs_only_a_message() -> None:
    assert fields(definition()) == []
    assert fields(definition(message_text="")) == ["message_text"]


def test_an_ad_click_automation_answers_any_ad_or_needs_an_ad_id() -> None:
    assert fields(definition(trigger="ad_click")) == []
    assert fields(definition(trigger="ad_click", post_scope="selected")) == ["ad_ids"]
    assert fields(definition(trigger="ad_click", post_scope="selected", ad_ids=["1"])) == []
    assert fields(definition(trigger="ad_click", post_scope="next_post")) == ["post_scope"]


# ---------------------------------------------------------------- links


def test_the_link_is_the_accounts_ig_me_address_with_the_code() -> None:
    acct: Any = SimpleNamespace(username="maple.bakery", platform_account_id="178")
    assert link_url(acct, "spring") == "https://ig.me/m/maple.bakery?ref=spring"
    bare: Any = SimpleNamespace(username=None, platform_account_id="178")
    assert link_url(bare, "x1y") == "https://ig.me/m/178?ref=x1y"


def test_the_qr_code_comes_as_svg_and_png() -> None:
    code = segno.make("https://ig.me/m/maple.bakery?ref=spring", error="m")
    png, svg = io.BytesIO(), io.BytesIO()
    code.save(png, kind="png", scale=QR_SCALE, border=QR_BORDER)
    code.save(svg, kind="svg", scale=QR_SCALE, border=QR_BORDER, xmldecl=False)
    assert png.getvalue().startswith(b"\x89PNG")
    assert svg.getvalue().startswith(b"<svg")


def test_generated_codes_fit_the_codes_pattern() -> None:
    for _ in range(20):
        code = _new_code()
        assert len(code) == CODE_LENGTH
        assert re.fullmatch(CODE_PATTERN, code)
