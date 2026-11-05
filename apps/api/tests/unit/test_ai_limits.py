"""The limits around AI calls without a database: the daily spend guard (TR-AI-13), the per-contact
limit, and the check of a flagged comment on its own before it is hidden."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from socialhood.ai import metering
from socialhood.ai.provider import AIError
from socialhood.security import ratelimit
from socialhood.services.comments import analysis as comments


class Store:
    """The Valkey calls the spend guard makes."""

    def __init__(self, spent: float = 0.0) -> None:
        self.spent = spent

    async def get(self, key: str) -> str:
        return str(self.spent)

    async def incrbyfloat(self, key: str, amount: float) -> float:
        self.spent += amount
        return self.spent

    async def expire(self, key: str, seconds: int) -> None:
        return None

    async def aclose(self) -> None:
        return None


def limit() -> Any:
    return SimpleNamespace(ai_daily_spend_limit_usd=100.0, rate_limits_enabled=True)


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> Store:
    found = Store()
    monkeypatch.setattr(metering, "make_redis", lambda settings: found)
    monkeypatch.setattr(metering, "get_settings", limit)
    return found


def test_unknown_models_count_at_the_dearest_price() -> None:
    assert metering.cost_usd("gemini-3.5-flash-lite", 1_000_000, 0) == pytest.approx(0.30)
    assert metering.cost_usd("something-new", 0, 1_000_000) == pytest.approx(7.50)


async def test_the_limit_pauses_bulk_features_first_and_twice_it_stops_every_feature(
    store: Store,
) -> None:
    store.spent = 99.0
    assert await metering._spend_paused("comment_analysis") is False
    store.spent = 100.0
    assert await metering._spend_paused("comment_analysis") is True
    assert await metering._spend_paused("post_summary") is True
    assert await metering._spend_paused("auto_reply") is False
    store.spent = 200.0
    assert await metering._spend_paused("auto_reply") is True


async def test_a_paused_spend_stops_the_call_as_used_up_credits_do(store: Store) -> None:
    store.spent = 100.0
    with pytest.raises(metering.QuotaExceeded):
        async with metering.metered(
            None,  # type: ignore[arg-type]
            workspace_id=uuid.uuid4(),
            feature="comment_analysis",
        ):
            pytest.fail("the call must not start")


async def test_spend_adds_up_and_alerts_when_it_crosses_a_level(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    alerts: list[str] = []
    monkeypatch.setattr(
        metering.log, "error", lambda event, **fields: alerts.append(fields["detail"])
    )
    store.spent = 79.999
    meter = metering.Meter("something-new", input_tokens=1_000_000, output_tokens=0)
    await metering._add_spend(meter)
    assert store.spent == pytest.approx(81.499)
    assert alerts == ["80% of the daily AI spend limit"]
    await metering._add_spend(meter)
    assert alerts == ["80% of the daily AI spend limit"]


async def test_with_the_store_down_ai_keeps_working(monkeypatch: pytest.MonkeyPatch) -> None:
    def down(settings: Any) -> Any:
        raise ConnectionError

    monkeypatch.setattr(metering, "make_redis", down)
    monkeypatch.setattr(metering, "get_settings", limit)
    assert await metering._spend_paused("comment_analysis") is False
    await metering._add_spend(metering.Meter("m", input_tokens=10))

    async def refused(*args: Any, **kwargs: Any) -> float:
        raise ConnectionError

    monkeypatch.setattr(ratelimit, "hit", refused)
    assert await metering.contact_admitted(None, uuid.uuid4(), "analysis") is True  # type: ignore[arg-type]


async def test_a_contact_is_refused_by_either_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metering, "get_settings", limit)
    waits = {"ai_contact_analysis_hour": 0.0, "ai_contact_analysis_day": 5.0}

    async def hit(redis: Any, window: Any, subject: str) -> float:
        return waits[window.name]

    monkeypatch.setattr(ratelimit, "hit", hit)
    assert await metering.contact_admitted(None, uuid.uuid4(), "analysis") is False  # type: ignore[arg-type]
    waits["ai_contact_analysis_day"] = 0.0
    assert await metering.contact_admitted(None, uuid.uuid4(), "analysis") is True  # type: ignore[arg-type]


# ---------------------------------------------------------------- hiding a comment


def reading(*, spam: bool) -> comments.CommentReading:
    return comments.CommentReading(
        id="1", sentiment="neutral", sentiment_score=0.0, intent="other", is_spam=spam
    )


def batch_of(count: int) -> tuple[Any, list[Any]]:
    items = [SimpleNamespace(id=uuid.uuid4(), hidden=False) for _ in range(count)]
    return SimpleNamespace(acct=SimpleNamespace(id=uuid.uuid4()), comments=items), items


def flagged_alone(batch: Any, read: Any, spam: list[Any]) -> Any:
    return comments._flagged_alone(
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        uuid.uuid4(),
        batch,
        read,
        spam,
        None,  # type: ignore[arg-type]
    )


async def test_only_comments_flagged_on_their_own_may_be_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch, items = batch_of(3)
    verdicts = {items[0].id: True, items[1].id: False}
    costs: list[int | None] = []

    async def call(*args: Any, cost: int | None = None) -> Any:
        costs.append(cost)
        [(_, comment)] = args[4]
        return SimpleNamespace(items=[reading(spam=verdicts[comment.id])]), "m"

    monkeypatch.setattr(comments, "_call", call)
    read = comments._Readings(by_comment={c.id: reading(spam=True) for c in items[:2]})

    assert await flagged_alone(batch, read, items[:2]) == [items[0]]
    assert read.by_comment[items[1].id].is_spam is False  # the reading alone replaces the batch's
    assert costs == [0, 0]


async def test_the_checks_are_capped_and_a_failed_one_hides_nothing_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch, items = batch_of(comments.MAX_HIDE_CHECKS + 5)
    asked: list[Any] = []

    async def call(*args: Any, cost: int | None = None) -> Any:
        asked.append(args[4])
        return SimpleNamespace(items=[reading(spam=True)]), "m"

    monkeypatch.setattr(comments, "_call", call)
    found = await flagged_alone(batch, comments._Readings(), items)
    assert len(found) == len(asked) == comments.MAX_HIDE_CHECKS

    async def failing(*args: Any, cost: int | None = None) -> Any:
        raise AIError("timeout")

    monkeypatch.setattr(comments, "_call", failing)
    assert await flagged_alone(batch, comments._Readings(), items) == []


async def test_a_comment_alone_in_its_batch_needs_no_second_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch, items = batch_of(1)

    async def call(*args: Any, cost: int | None = None) -> Any:
        pytest.fail("no second call")

    monkeypatch.setattr(comments, "_call", call)
    assert await flagged_alone(batch, comments._Readings(), items) == items
