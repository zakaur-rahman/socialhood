"""FR-INB-10 / TR-PL-04 reply windows, tested at their boundaries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from socialhood.services.reply_window import may_send, needs_human_agent_tag, reply_window

T0 = datetime(2026, 9, 28, 12, tzinfo=UTC)
JUST = timedelta(seconds=1)


@pytest.mark.parametrize(
    ("platform", "elapsed", "human_agent", "state"),
    [
        ("instagram", timedelta(hours=24) - JUST, False, "open"),
        ("instagram", timedelta(hours=24), False, "closed"),
        ("instagram", timedelta(hours=24), True, "human_agent"),
        ("instagram", timedelta(days=7) - JUST, True, "human_agent"),
        ("instagram", timedelta(days=7), True, "closed"),
        ("whatsapp", timedelta(hours=24) - JUST, False, "open"),
        ("whatsapp", timedelta(hours=24), True, "template_only"),
    ],
)
def test_window_state_at_the_boundaries(
    platform: str, elapsed: timedelta, human_agent: bool, state: str
) -> None:
    window = reply_window(platform, T0, human_agent=human_agent, now=T0 + elapsed)
    assert window.state == state


def test_no_inbound_message_means_no_window() -> None:
    assert reply_window("instagram", None, human_agent=True, now=T0).state == "closed"
    assert reply_window("whatsapp", None, human_agent=False, now=T0).state == "template_only"


def test_open_window_reports_when_it_closes() -> None:
    window = reply_window("instagram", T0, human_agent=False, now=T0 + timedelta(hours=5))
    assert window.closes_at == T0 + timedelta(hours=24)


def test_who_may_send_in_each_state() -> None:
    agent = reply_window("instagram", T0, human_agent=True, now=T0 + timedelta(days=2))
    assert may_send(agent, "human")
    assert needs_human_agent_tag(agent, "human")
    # AI auto replies and automations never use the Human Agent tag.
    assert not may_send(agent, "ai_auto")
    assert not may_send(agent, "automation")
    wa = reply_window("whatsapp", T0, human_agent=False, now=T0 + timedelta(days=2))
    assert may_send(wa, "template")
    assert not may_send(wa, "human")
    closed = reply_window("instagram", T0, human_agent=False, now=T0 + timedelta(days=2))
    assert not any(may_send(closed, k) for k in ("human", "ai_auto", "automation", "template"))
