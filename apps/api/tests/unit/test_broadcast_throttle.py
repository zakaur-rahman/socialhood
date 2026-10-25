"""GR-23: pacing a broadcast to the number's daily limit, and the plan's recipients."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from socialhood.services.broadcasts import throttle

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("tier", "limit"),
    [
        ("TIER_50", 50),
        ("TIER_250", 250),
        ("TIER_1K", 1_000),
        ("TIER_10K", 10_000),
        ("TIER_100K", 100_000),
        ("TIER_UNLIMITED", None),
        (None, throttle.DEFAULT_DAILY_LIMIT),
        ("TIER_SOMETHING_NEW", throttle.DEFAULT_DAILY_LIMIT),
    ],
)
def test_a_tier_is_a_daily_limit(tier: str | None, limit: int | None) -> None:
    assert throttle.limit_for_tier(tier) == limit


def test_the_default_is_the_conservative_tier() -> None:
    assert throttle.DEFAULT_DAILY_LIMIT == 250


def test_headroom_is_left_under_the_limit() -> None:
    assert throttle.usable(1_000) == 900
    assert throttle.usable(50) == 45
    assert throttle.usable(1) == 1
    assert throttle.usable(None) is None


def test_room_is_what_is_left_of_the_usable_limit() -> None:
    assert throttle.room(1_000, 0) == 900
    assert throttle.room(1_000, 850) == 50
    assert throttle.room(1_000, 900) == 0
    assert throttle.room(1_000, 5_000) == 0  # never negative
    assert throttle.room(None, 5_000) is None


def test_a_batch_is_cut_to_every_limit() -> None:
    size = throttle.BATCH_SIZE
    assert throttle.batch_size(room_now=None, waiting=1_000, quota_left=None) == size
    assert throttle.batch_size(room_now=None, waiting=7, quota_left=None) == 7
    assert throttle.batch_size(room_now=10, waiting=1_000, quota_left=None) == 10
    assert throttle.batch_size(room_now=1_000, waiting=1_000, quota_left=3) == 3
    assert throttle.batch_size(room_now=0, waiting=1_000, quota_left=500) == 0
    assert throttle.batch_size(room_now=100, waiting=0, quota_left=100) == 0
    assert throttle.batch_size(room_now=100, waiting=100, quota_left=100, size=20) == 20


def test_a_2500_person_broadcast_takes_about_forty_minutes_at_a_high_tier() -> None:
    batches = -(-2_500 // throttle.BATCH_SIZE)
    assert batches * throttle.BATCH_EVERY <= timedelta(minutes=45)


def test_no_wait_while_there_is_room() -> None:
    recent = [NOW - timedelta(hours=1)] * 10
    assert throttle.next_room_at(recent, 250, NOW) is None
    assert throttle.next_room_at([], 250, NOW) is None
    assert throttle.next_room_at(recent, None, NOW) is None


def test_at_the_limit_a_place_frees_when_the_oldest_message_leaves_the_window() -> None:
    # 250 -> 225 usable. 225 people messaged, the oldest 23 hours ago: it leaves in an hour.
    times = [NOW - timedelta(hours=23) + timedelta(seconds=i) for i in range(225)]
    free = throttle.next_room_at(times, 250, NOW)
    assert free == times[0] + throttle.WINDOW


def test_over_the_limit_it_waits_for_enough_to_leave() -> None:
    cap = throttle.usable(50)
    assert cap == 45
    times = [NOW - timedelta(hours=1, minutes=i) for i in range(50)]  # 50 people, five over
    free = throttle.next_room_at(times, 50, NOW)
    ordered = sorted(times)
    assert free == ordered[50 - 45] + throttle.WINDOW


def test_messages_older_than_a_day_do_not_count() -> None:
    times = [NOW - timedelta(hours=30)] * 500
    assert throttle.next_room_at(times, 250, NOW) is None
