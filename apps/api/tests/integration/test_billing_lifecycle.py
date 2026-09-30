"""The billing lifecycle beyond single events (T8.1, T8.3; TR-BIL-03, FR-BIL-06, FR-BIL-07,
F-16): the reconcile job against Dodo, usage periods and limits across plan changes, the
downgrade's idempotence and a lower paid plan, and a deleted workspace's subscription."""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing.dodo import DodoError, DodoSubscriptionStatus
from socialhood.billing.dodo_fake import FakeDodo
from socialhood.billing.downgrade import apply_downgrade
from socialhood.db.engine import make_sessionmaker
from socialhood.db.tenancy import workspace_scope
from socialhood.errors import ApiError
from socialhood.jobs.tasks.billing import reconcile_all
from socialhood.services import workspaces as workspace_service
from socialhood.services.webhook_handlers import dodo as dodo_handler
from socialhood.settings import Settings
from tests.support.analysis import use_credits
from tests.support.api import Clerk, sign_in
from tests.support.automations import make_automation
from tests.support.billing import MAX_PRODUCT, PRO_PRODUCT, set_subscription
from tests.support.dodo import send, subscription
from tests.support.inbox import make_account

pytestmark = pytest.mark.usefixtures("queue")


@pytest.fixture(autouse=True)
def handler_settings(api_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dodo_handler, "get_settings", lambda: api_settings)


@dataclass
class Owner:
    app: FastAPI
    client: httpx.AsyncClient
    engine: AsyncEngine
    clerk: Clerk
    clerk_id: str
    wid: str
    settings: Settings

    async def sub(self) -> dict[str, Any]:
        return await self.one("SELECT * FROM subscriptions WHERE workspace_id = :w")

    async def one(self, sql: str) -> dict[str, Any]:
        [row] = await self.rows(sql)
        return row

    async def rows(self, sql: str) -> list[dict[str, Any]]:
        async with self.engine.connect() as conn:
            return [dict(r._mapping) for r in await conn.execute(text(sql), {"w": self.wid})]

    async def meters(self) -> dict[str, dict[str, Any]]:
        response = await self.client.get(
            f"/v1/w/{self.wid}/billing", headers=self.clerk.headers(self.clerk_id)
        )
        assert response.status_code == 200, response.text
        return {m["metric"]: m for m in response.json()["usage"]}

    async def notifications(self) -> list[str]:
        rows = await self.rows(
            "SELECT type FROM notifications WHERE workspace_id = :w ORDER BY created_at"
        )
        return [r["type"] for r in rows]

    async def reconcile(self, dodo: FakeDodo) -> dict[str, int]:
        return await reconcile_all(self.app.state.sessionmaker, dodo, settings=self.settings)


@pytest.fixture
async def owner(
    app: FastAPI,
    client: httpx.AsyncClient,
    clerk: Clerk,
    engine: AsyncEngine,
    redis: Redis,
    api_settings: Settings,
) -> Owner:
    clerk_id, me = await sign_in(client, clerk, email="owner@example.com")
    return Owner(app, client, engine, clerk, clerk_id, me["workspaces"][0]["id"], api_settings)


def ago(**delta: float) -> datetime:
    return datetime.now(UTC) - timedelta(**delta)


async def pro(
    owner: Owner, fake_dodo: FakeDodo, dodo_status: str = "active", **values: Any
) -> None:
    """A Pro workspace whose Dodo subscription ``sub_1`` reports ``dodo_status``."""
    fake_dodo.add_subscription(
        "sub_1",
        product_id=PRO_PRODUCT,
        status=cast(DodoSubscriptionStatus, dodo_status),
        customer_id="cus_1",
        previous_billing_date=ago(days=10),
        next_billing_date=ago(days=-20),
        cancel_at_next_billing_date=values.pop("dodo_cancel", False),
    )
    await set_subscription(
        owner.engine,
        workspace_id=owner.wid,
        **{
            "plan": "pro",
            "status": "active",
            "dodo_subscription_id": "sub_1",
            "dodo_customer_id": "cus_1",
            "dodo_product_id": PRO_PRODUCT,
            "current_period_start": ago(days=10),
            "current_period_end": ago(days=-20),
            **values,
        },
    )


# ---------------------------------------------------------------- reconcile (TR-BIL-03)


async def test_reconcile_mirrors_a_hold_it_missed(owner: Owner, fake_dodo: FakeDodo) -> None:
    await pro(owner, fake_dodo, dodo_status="on_hold")
    counts = await owner.reconcile(fake_dodo)

    assert counts == {"checked": 1, "corrected": 1, "failed": 0}
    sub = await owner.sub()
    assert (sub["plan"], sub["status"]) == ("pro", "on_hold")
    assert sub["grace_until"] is not None
    assert await owner.notifications() == ["payment_problem"]
    assert (await owner.reconcile(fake_dodo))["corrected"] == 0  # nothing left to correct


async def test_reconcile_restores_a_recovered_subscription(
    owner: Owner, fake_dodo: FakeDodo
) -> None:
    await pro(owner, fake_dodo, status="on_hold", grace_until=ago(days=-2))
    await owner.reconcile(fake_dodo)
    sub = await owner.sub()
    assert (sub["status"], sub["grace_until"]) == ("active", None)


@pytest.mark.parametrize("dodo", ["on_hold", "unreachable"])
async def test_a_hold_past_its_grace_goes_to_free(
    owner: Owner, fake_dodo: FakeDodo, dodo: str
) -> None:
    await pro(owner, fake_dodo, dodo_status="on_hold", status="on_hold", grace_until=ago(hours=1))
    if dodo == "unreachable":
        fake_dodo.fail_next(DodoError("down", status=503, retryable=True))
    await owner.reconcile(fake_dodo)

    sub = await owner.sub()
    assert (sub["plan"], sub["status"], sub["grace_until"]) == ("free", "expired", None)
    assert await owner.notifications() == ["plan_downgraded"]
    assert (await owner.meters())["ai_credits"]["limit"] == 200


async def test_a_cancelled_plan_ends_with_its_period(owner: Owner, fake_dodo: FakeDodo) -> None:
    await pro(owner, fake_dodo, cancel_at_period_end=True, current_period_end=ago(hours=2))
    fake_dodo.subscriptions["sub_1"] = dataclasses.replace(
        fake_dodo.subscriptions["sub_1"], status="cancelled", next_billing_date=ago(hours=2)
    )
    await owner.reconcile(fake_dodo)
    assert ((await owner.sub())["plan"], (await owner.sub())["status"]) == ("free", "expired")


async def test_dodo_not_answering_changes_nothing(owner: Owner, fake_dodo: FakeDodo) -> None:
    await pro(owner, fake_dodo, dodo_status="expired")
    fake_dodo.fail_next(DodoError("down", status=503, retryable=True))
    assert (await owner.reconcile(fake_dodo))["corrected"] == 0
    assert (await owner.sub())["plan"] == "pro"
    await owner.reconcile(fake_dodo)  # the next run sees Dodo's answer
    assert ((await owner.sub())["plan"], (await owner.sub())["status"]) == ("free", "expired")


# ---------------------------------------------------------------- usage periods and limits


async def test_a_plan_change_moves_the_credit_period_and_its_limits(
    owner: Owner, engine: AsyncEngine
) -> None:
    """§1.7: credits reset on the subscription's billing anchor day (Free: the workspace's
    creation day). Upgrading starts Dodo's period with Pro's limits; the downgrade goes back to
    the creation day's period, which keeps what it had used, with Free's limits."""
    today = datetime.now(UTC).date()
    await use_credits(engine, uuid.UUID(owner.wid), 150, now=datetime.now(UTC))
    assert (await owner.meters())["ai_credits"]["used"] == 150

    started = ago(days=10)
    row = await send(
        owner.app,
        owner.client,
        engine,
        "subscription.active",
        subscription(owner.wid, period_start=started, period_end=started + timedelta(days=30)),
        at=ago(minutes=5),
    )
    assert row["status"] == "processed"
    assert (await owner.sub())["billing_anchor_day"] == min(started.day, 28)
    meters = await owner.meters()
    assert (meters["ai_credits"]["used"], meters["ai_credits"]["limit"]) == (0, 5000)
    assert meters["scheduled_posts"]["limit"] == 300
    assert date.fromisoformat(meters["ai_credits"]["period_end"]) > today

    await send(
        owner.app,
        owner.client,
        engine,
        "subscription.expired",
        subscription(owner.wid, status="expired"),
    )
    assert (await owner.sub())["billing_anchor_day"] == min(today.day, 28)
    meters = await owner.meters()
    assert (meters["ai_credits"]["used"], meters["ai_credits"]["limit"]) == (150, 200)
    assert meters["scheduled_posts"]["limit"] == 10


# ---------------------------------------------------------------- downgrade


async def test_the_downgrade_is_idempotent(owner: Owner, engine: AsyncEngine) -> None:
    account = await make_account(engine, owner.wid)
    for word in ("a", "b", "c", "d"):
        await make_automation(engine, workspace_id=owner.wid, account_id=account, keywords=(word,))
    maker = make_sessionmaker(engine)
    with workspace_scope(uuid.UUID(owner.wid)):
        async with maker() as session:
            first = await apply_downgrade(session, plan="free", now=datetime.now(UTC))
            await session.commit()
        async with maker() as session:
            again = await apply_downgrade(session, plan="free", now=datetime.now(UTC))
            await session.commit()
    assert len(first.automations_paused) == 1
    assert again.automations_paused == []
    assert not again.changed


async def test_max_to_pro_applies_the_lower_limits(owner: Owner, engine: AsyncEngine) -> None:
    for n in range(4):
        await make_account(engine, owner.wid, username=f"shop{n}")
    await send(
        owner.app,
        owner.client,
        engine,
        "subscription.active",
        subscription(owner.wid, product_id=MAX_PRODUCT),
        at=ago(minutes=10),
    )
    assert (await owner.sub())["plan"] == "max"
    await send(
        owner.app,
        owner.client,
        engine,
        "subscription.plan_changed",
        subscription(owner.wid, product_id=PRO_PRODUCT),
    )
    assert (await owner.sub())["plan"] == "pro"
    assert await owner.notifications() == ["plan_activated", "plan_downgraded"]
    [notice] = await owner.rows(
        "SELECT body FROM notifications WHERE workspace_id = :w AND type = 'plan_downgraded'"
    )
    assert notice["body"] == "1 account can no longer send."


# ---------------------------------------------------------------- workspace deletion (F-16)


async def test_deleting_a_workspace_cancels_its_dodo_subscription(
    owner: Owner, fake_dodo: FakeDodo, engine: AsyncEngine
) -> None:
    await pro(owner, fake_dodo)
    maker = make_sessionmaker(engine)
    with workspace_scope(uuid.UUID(owner.wid)):
        async with maker() as session:
            assert await workspace_service.cancel_dodo_subscription(session, fake_dodo)
    assert fake_dodo.subscriptions["sub_1"].status == "cancelled"

    with workspace_scope(uuid.UUID(owner.wid)):
        async with maker() as session:
            fake_dodo.fail_next(DodoError("gone", status=404))
            assert not await workspace_service.cancel_dodo_subscription(session, fake_dodo)
            fake_dodo.fail_next(DodoError("down", status=503, retryable=True))
            with pytest.raises(ApiError) as refused:
                await workspace_service.cancel_dodo_subscription(session, fake_dodo)
    assert refused.value.code == "service_unavailable"


async def test_a_workspace_without_a_dodo_subscription_has_nothing_to_cancel(
    owner: Owner, fake_dodo: FakeDodo, engine: AsyncEngine
) -> None:
    maker = make_sessionmaker(engine)
    with workspace_scope(uuid.UUID(owner.wid)):
        async with maker() as session:
            assert not await workspace_service.cancel_dodo_subscription(session, fake_dodo)
    assert fake_dodo.calls == []
