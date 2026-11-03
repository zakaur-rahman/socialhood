"""C-174: Agency's limits, and every entitlement naming every plan."""

from __future__ import annotations

from socialhood.billing.plans import ENTITLEMENTS, PLANS, entitlement


def test_agency_has_the_owners_limits_and_no_trial() -> None:
    decided = {
        "accounts_per_platform": 10,
        "channels_total": None,
        "whatsapp": True,
        "active_automations": None,
        "scheduled_posts_monthly": None,
        "ai_credits_monthly": 12_000,
        "members": 10,
        "knowledge_characters": 50_000_000,
        "public_api": True,
        "message_history_days": None,
    }
    assert {key: entitlement("agency", key) for key in decided} == decided
    assert "full" in entitlement("agency", "ai_connections")
    assert "auto" in entitlement("agency", "ai_modes")


def test_every_entitlement_names_every_plan() -> None:
    """entitlement() falls back to Free for a missing plan, so a gap would silently cut Agency."""
    assert [key for key, values in ENTITLEMENTS.items() if set(values) != set(PLANS)] == []


def test_the_free_channel_rule_is_unchanged() -> None:
    assert entitlement("free", "channels_total") == 2
    assert entitlement("free", "whatsapp") is False
    assert entitlement("free", "accounts_per_platform") == 1
