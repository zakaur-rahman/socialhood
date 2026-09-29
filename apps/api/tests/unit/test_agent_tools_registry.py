"""The R1 tools as registered (TR-AGT-03, FR-AGT-02, TA.4): every tool the architecture lists for
R1 exists with its tier and role bound, draft tools return action cards, inputs are strict and
capped, and the member's age phrases map to the snapshot windows (FR-ANL-01)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from socialhood.agent.registry import CURRENT_RELEASE, DraftResult, Release, registry
from socialhood.agent.tools import load_tools
from socialhood.agent.tools.analytics import snapshot_age
from socialhood.errors import ApiError
from socialhood.models.agent import RiskTier
from socialhood.models.identity import Role

READ = {
    "search_conversations",
    "get_conversation",
    "find_contact",
    "get_customer",
    "get_post_comments",
    "search_comments",
    "get_posts",
    "get_latest_post",
    "search_posts",
    "post_performance",
    "compare_posts",
    "top_posts",
    "sentiment_distribution",
    "comment_topics",
    "list_scheduled_messages",
    "list_scheduled_posts",
    "list_automations",
    "get_automation",
    "get_automation_stats",
    "test_automation",
    "search_knowledge",
    "answer_from_knowledge",
    "list_knowledge_gaps",
}
DRAFT = {"draft_reply", "prepare_comment_reply", "prepare_scheduled_message", "prepare_automation"}
ADMIN = {
    "list_scheduled_posts",
    "list_automations",
    "get_automation",
    "get_automation_stats",
    "test_automation",
    "prepare_automation",
    "search_knowledge",
    "answer_from_knowledge",
    "list_knowledge_gaps",
}


def test_every_r1_tool_is_registered_with_its_tier_and_role() -> None:
    tools = load_tools()
    assert tools is registry
    assert {spec.name for spec in tools} == READ | DRAFT
    for spec in tools:
        assert spec.release == Release.R1
        assert spec.capability is None
        assert spec.tier == (RiskTier.DRAFT if spec.name in DRAFT else RiskTier.READ)
        assert spec.min_role == (Role.ADMIN if spec.name in ADMIN else Role.AGENT), spec.name
        assert issubclass(spec.result_model, DraftResult) == (spec.name in DRAFT)
        assert spec.input_model.model_config.get("extra") == "forbid", spec.name
        assert spec.input_model.model_json_schema()["type"] == "object"  # for the planner
        assert spec.label[0].isupper()
        assert len(spec.description) <= 500


def test_members_see_every_tool_but_the_owner_and_admin_ones() -> None:
    load_tools()
    agent = {s.name for s in registry.available(release=CURRENT_RELEASE, role=Role.AGENT)}
    admin = {s.name for s in registry.available(release=CURRENT_RELEASE, role=Role.ADMIN)}
    assert agent == (READ | DRAFT) - ADMIN
    assert admin == READ | DRAFT


def test_inputs_are_strict_and_lists_are_capped() -> None:
    load_tools()
    search = registry.get("search_conversations")
    assert search is not None
    assert search.input_model.model_validate({}).limit == 10
    with pytest.raises(ValidationError):
        search.input_model.model_validate({"limit": 26})
    with pytest.raises(ValidationError):
        search.input_model.model_validate({"sql": "SELECT 1"})
    topics = registry.get("comment_topics")
    assert topics is not None
    with pytest.raises(ValidationError):
        topics.input_model.model_validate({"n": 11})


@pytest.mark.parametrize(
    ("phrase", "window", "rule"),
    [
        (None, None, False),
        ("lifetime", "lifetime", False),
        ("so far", "lifetime", False),
        ("after 24 hours", "24h", False),
        ("1 h", "1h", False),
        ("3 days", "72h", False),
        ("a week", "7d", False),
        ("1 month", "30d", True),  # a month counts as 30 days
        ("48 hours", "72h", True),  # nearest by ratio of ages
        ("36 hours", "24h", True),
        ("12 hours", "6h", True),  # a tie goes to the younger window
        ("10 days", "7d", True),
    ],
)
def test_age_phrases_map_to_snapshot_windows(
    phrase: str | None, window: str | None, rule: bool
) -> None:
    got, why = snapshot_age(phrase)
    assert got == window
    assert (why is not None) == rule


def test_an_unreadable_age_is_a_validation_error() -> None:
    with pytest.raises(ApiError) as caught:
        snapshot_age("whenever")
    assert caught.value.code == "validation_error"
    assert caught.value.errors[0].field == "at_age"
