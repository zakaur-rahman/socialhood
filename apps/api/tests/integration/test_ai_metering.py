"""T5.1: AI credit metering (TR-AI-09, FR-AI-05). Done when: an exhausted quota raises before any
call. Plus refunds on failure, usage events, one 80% and one 100% notification per period, and the
credit period from the billing anchor day."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from socialhood.ai.fake import FakeProvider
from socialhood.ai.metering import QuotaExceeded, metered, quota
from socialhood.ai.provider import AIError, Turn
from socialhood.db.tenancy import workspace_scope
from socialhood.repositories.usage import period_for
from tests.support.inbox import make_workspace

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
PERIOD = date(2026, 9, 1)  # a bare workspace has no subscription: anchor day 1, Free plan


@pytest.fixture
async def wid(engine: AsyncEngine, clean_db: None) -> uuid.UUID:
    workspace_id = await make_workspace(engine)
    async with engine.begin() as conn:  # an owner to notify
        await conn.execute(
            text(
                "INSERT INTO workspace_members (workspace_id, user_id, role)"
                " SELECT id, owner_user_id, 'owner' FROM workspaces WHERE id = :w"
            ),
            {"w": workspace_id},
        )
    return workspace_id


async def one(engine: AsyncEngine, sql: str, **params: Any) -> dict[str, Any]:
    async with engine.connect() as conn:
        return dict((await conn.execute(text(sql), params)).one()._mapping)


async def rows(engine: AsyncEngine, sql: str, **params: Any) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), params)]


async def set_used(engine: AsyncEngine, wid: uuid.UUID, used: int) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    with workspace_scope(wid):
        async with maker() as session:
            await quota(session, now=NOW)  # creates the period's counter
            await session.commit()
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE usage_counters SET used = :u WHERE workspace_id = :w"),
            {"u": used, "w": wid},
        )


async def call(fake: FakeProvider) -> None:
    result = await fake.generate_text(
        task="summary",
        system="s",
        contents=[Turn("user", "hi")],
        model="m",
        max_output_tokens=10,
        temperature=0,
        timeout_s=1,
    )
    assert result.value


async def test_a_call_reserves_its_credits_and_records_the_event(
    engine: AsyncEngine, wid: uuid.UUID, fake_ai: FakeProvider
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    ref = uuid.uuid4()
    async with metered(
        maker, workspace_id=wid, feature="reply_suggestion", ref_type="message", ref_id=ref, now=NOW
    ) as meter:
        result = await fake_ai.generate_text(
            task="summary",
            system="s",
            contents=[Turn("user", "hi")],
            model="fake-model",
            max_output_tokens=10,
            temperature=0,
            timeout_s=1,
        )
        meter.record(result)

    counter = await one(
        engine, 'SELECT used, "limit", period_start, period_end FROM usage_counters'
    )
    assert counter == {
        "used": 2,
        "limit": 200,
        "period_start": PERIOD,
        "period_end": date(2026, 10, 1),
    }
    [event] = await rows(engine, "SELECT * FROM ai_usage_events")
    assert (event["feature"], event["credits"], event["outcome"]) == ("reply_suggestion", 2, "ok")
    assert (event["model"], event["input_tokens"], event["output_tokens"]) == (
        "fake-model",
        100,
        20,
    )
    assert (event["ref_type"], event["ref_id"]) == ("message", ref)


async def test_an_exhausted_quota_raises_before_any_call(
    engine: AsyncEngine, wid: uuid.UUID, fake_ai: FakeProvider
) -> None:
    await set_used(engine, wid, 199)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    with pytest.raises(QuotaExceeded):
        async with metered(maker, workspace_id=wid, feature="reply_suggestion", now=NOW):
            await call(fake_ai)

    assert fake_ai.calls == []
    assert (await one(engine, "SELECT used FROM usage_counters"))["used"] == 199
    assert await rows(engine, "SELECT id FROM ai_usage_events") == []
    # One credit still fits.
    async with metered(maker, workspace_id=wid, feature="message_analysis", now=NOW):
        await call(fake_ai)
    assert (await one(engine, "SELECT used FROM usage_counters"))["used"] == 200


@pytest.mark.parametrize(
    ("error", "outcome"),
    [(AIError("timeout", retryable=True), "timeout"), (RuntimeError("boom"), "error")],
)
async def test_a_failed_call_refunds_its_credits(
    engine: AsyncEngine, wid: uuid.UUID, error: Exception, outcome: str
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    with pytest.raises(type(error)):
        async with metered(maker, workspace_id=wid, feature="auto_reply", now=NOW):
            raise error

    assert (await one(engine, "SELECT used FROM usage_counters"))["used"] == 0
    [event] = await rows(engine, "SELECT credits, outcome FROM ai_usage_events")
    assert event == {"credits": 0, "outcome": outcome}


async def test_80_and_100_percent_notify_once_per_period(
    engine: AsyncEngine, wid: uuid.UUID, fake_ai: FakeProvider
) -> None:
    await set_used(engine, wid, 158)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    for _ in range(3):  # 160, 162, 164: crosses 80% once
        async with metered(maker, workspace_id=wid, feature="reply_suggestion", now=NOW):
            await call(fake_ai)
    await set_used(engine, wid, 198)
    for _ in range(2):  # 200, then refused
        try:
            async with metered(maker, workspace_id=wid, feature="reply_suggestion", now=NOW):
                await call(fake_ai)
        except QuotaExceeded:
            pass

    notes = await rows(engine, "SELECT type, severity FROM notifications ORDER BY created_at")
    assert notes == [
        {"type": "ai_credits_80", "severity": "warning"},
        {"type": "ai_credits_100", "severity": "critical"},
    ]


async def test_quota_reports_what_is_left(engine: AsyncEngine, wid: uuid.UUID) -> None:
    await set_used(engine, wid, 150)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    with workspace_scope(wid):
        async with maker() as session:
            left = await quota(session, now=NOW)
    assert (left.used, left.limit, left.remaining, left.period_end) == (
        150,
        200,
        50,
        date(2026, 10, 1),
    )
    assert left.allows(50)
    assert not left.allows(51)


@pytest.mark.parametrize(
    ("anchor", "today", "period"),
    [
        (1, date(2026, 9, 29), (date(2026, 9, 1), date(2026, 10, 1))),
        (15, date(2026, 9, 14), (date(2026, 8, 15), date(2026, 9, 15))),
        (15, date(2026, 9, 15), (date(2026, 9, 15), date(2026, 10, 15))),
        (28, date(2026, 1, 5), (date(2025, 12, 28), date(2026, 1, 28))),
        (28, date(2026, 12, 30), (date(2026, 12, 28), date(2027, 1, 28))),
    ],
)
def test_the_credit_period_follows_the_anchor_day(
    anchor: int, today: date, period: tuple[date, date]
) -> None:
    assert period_for(anchor, today) == period
