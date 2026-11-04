"""C-174: every plan and billing period at checkout and in webhooks, Agency's limits, what the
dashboard reads back, and allowances that reset monthly on a plan billed every six months."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.ai.metering import quota
from socialhood.billing.dodo_fake import FakeDodo
from socialhood.billing.plans import PLANS, entitlement, offer_for_product
from socialhood.billing.usage import period_used
from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.tasks.billing import reconcile_all
from socialhood.models.billing import UsageMetric
from socialhood.repositories import usage
from socialhood.services.webhook_handlers import dodo as dodo_handler
from socialhood.settings import Settings
from tests.support.api import Clerk, sign_in
from tests.support.billing import MAX_PRODUCT, PRO_PRODUCT, set_subscription
from tests.support.dodo import checkout_metadata, send, subscription

pytestmark = pytest.mark.usefixtures("queue")

PRO_SIX = "pdt_test_pro_six"
MAX_SIX = "pdt_test_max_six"
AGENCY_MONTH = "pdt_test_agency_month"
AGENCY_SIX = "pdt_test_agency_six"
NEW_PRODUCTS = {
    "dodo_product_pro_six_month": PRO_SIX,
    "dodo_product_max_six_month": MAX_SIX,
    "dodo_product_agency_monthly": AGENCY_MONTH,
    "dodo_product_agency_six_month": AGENCY_SIX,
}
EVERY_OFFER = [
    ("pro", "month", PRO_PRODUCT),
    ("pro", "six_month", PRO_SIX),
    ("max", "month", MAX_PRODUCT),
    ("max", "six_month", MAX_SIX),
    ("agency", "month", AGENCY_MONTH),
    ("agency", "six_month", AGENCY_SIX),
]


@dataclass
class Owner:
    app: FastAPI
    client: httpx.AsyncClient
    engine: AsyncEngine
    clerk: Clerk
    clerk_id: str
    wid: str

    async def checkout(self, **body: str) -> httpx.Response:
        return await self.client.post(
            f"/v1/w/{self.wid}/billing/checkout",
            json=body,
            headers=self.clerk.headers(self.clerk_id),
        )

    async def billing(self) -> dict[str, Any]:
        response = await self.client.get(
            f"/v1/w/{self.wid}/billing", headers=self.clerk.headers(self.clerk_id)
        )
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    async def sub(self) -> dict[str, Any]:
        async with self.engine.connect() as conn:
            row = await conn.execute(
                text("SELECT * FROM subscriptions WHERE workspace_id = :w"), {"w": self.wid}
            )
            return dict(row.one()._mapping)

    async def send(self, event: str, product: str, **values: Any) -> dict[str, Any]:
        data = subscription(self.wid, product_id=product, **values)
        return await send(self.app, self.client, self.engine, event, data)


@pytest.fixture
async def owner(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis
) -> Owner:
    clerk_id, me = await sign_in(client, clerk, email="owner@example.com", first_name="Asha")
    return Owner(app, client, engine, clerk, clerk_id, me["workspaces"][0]["id"])


@pytest.fixture
def on_sale(
    app: FastAPI,
    api_settings: Settings,
    fake_dodo: FakeDodo,
    redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> Settings:
    """Every product set, priced as the owner decided (monthly already in the fake, in rupees)."""
    settings = api_settings.model_copy(update=NEW_PRODUCTS)
    app.state.settings = settings
    monkeypatch.setattr(dodo_handler, "get_settings", lambda: settings)
    fake_dodo.add_product(PRO_SIX, amount_minor=8100, currency="USD", interval="six_month")
    fake_dodo.add_product(MAX_SIX, amount_minor=15300, currency="USD", interval="six_month")
    fake_dodo.add_product(AGENCY_MONTH, amount_minor=7000, currency="USD")
    fake_dodo.add_product(AGENCY_SIX, amount_minor=31500, currency="USD", interval="six_month")
    return settings


def only(**update: str | None) -> Callable[[FastAPI, Settings], None]:
    def apply(app: FastAPI, settings: Settings) -> None:
        app.state.settings = settings.model_copy(update=update)

    return apply


# ---------------------------------------------------------------- checkout


@pytest.mark.parametrize(("plan", "period", "product"), EVERY_OFFER)
async def test_checkout_sells_each_plan_and_period_with_a_trial_on_monthly_creator_only(
    owner: Owner, on_sale: Settings, fake_dodo: FakeDodo, plan: str, period: str, product: str
) -> None:
    response = await owner.checkout(plan=plan, period=period)

    assert response.status_code == 200, response.text
    wants_trial = (plan, period) == ("pro", "month")
    assert response.json()["trial"] is wants_trial
    [params] = fake_dodo.checkouts
    assert params.product_id == product
    assert params.trial_period_days == (7 if wants_trial else 0)
    assert dict(params.metadata) == checkout_metadata(owner.wid)


async def test_checkout_period_defaults_to_monthly_and_rejects_anything_else(
    owner: Owner, on_sale: Settings, fake_dodo: FakeDodo
) -> None:
    assert (await owner.checkout(plan="max")).status_code == 200
    assert fake_dodo.checkouts[0].product_id == MAX_PRODUCT
    assert (await owner.checkout(plan="pro", period="year")).status_code == 422
    assert (await owner.checkout(plan="free")).status_code == 422


@pytest.mark.parametrize("plan", ["pro", "max"])
async def test_six_month_is_refused_until_its_product_is_set_and_monthly_still_sells(
    owner: Owner, fake_dodo: FakeDodo, plan: str
) -> None:
    """Production today: only the existing values are set."""
    response = await owner.checkout(plan=plan, period="six_month")
    assert response.status_code == 422
    [error] = response.json()["errors"]
    assert error["field"] == "period"
    assert "isn't available every 6 months yet" in error["message"]
    assert fake_dodo.checkouts == []
    assert (await owner.checkout(plan=plan, period="month")).status_code == 200


@pytest.mark.parametrize("period", ["month", "six_month"])
async def test_agency_is_refused_until_its_monthly_product_is_set(
    app: FastAPI, api_settings: Settings, owner: Owner, fake_dodo: FakeDodo, period: str
) -> None:
    only(dodo_product_agency_six_month=AGENCY_SIX)(
        app, api_settings
    )  # six-month alone isn't a sale
    response = await owner.checkout(plan="agency", period=period)
    assert response.status_code == 422
    [error] = response.json()["errors"]
    assert (error["field"], error["message"]) == ("plan", "Agency isn't available yet.")
    assert fake_dodo.checkouts == []


async def test_no_trial_on_monthly_creator_once_one_was_used(
    owner: Owner, on_sale: Settings, fake_dodo: FakeDodo
) -> None:
    async with owner.engine.begin() as conn:
        await conn.execute(
            text("UPDATE workspaces SET trial_used_at = now() WHERE id = :w"), {"w": owner.wid}
        )
    assert (await owner.checkout(plan="pro")).json()["trial"] is False
    assert fake_dodo.checkouts[0].trial_period_days == 0


async def test_checkout_is_still_refused_for_a_paid_workspace(
    owner: Owner, on_sale: Settings, fake_dodo: FakeDodo
) -> None:
    await owner.send("subscription.active", PRO_SIX)
    response = await owner.checkout(plan="agency", period="six_month")
    assert response.status_code == 409
    assert fake_dodo.checkouts == []


# ---------------------------------------------------------------- webhooks


@pytest.mark.parametrize(("plan", "period", "product"), EVERY_OFFER)
async def test_a_webhook_maps_every_product_to_its_plan(
    owner: Owner, on_sale: Settings, plan: str, period: str, product: str
) -> None:
    assert offer_for_product(product, on_sale) == (plan, period)
    stored = await owner.send("subscription.active", product)
    assert stored["status"] == "processed"
    sub = await owner.sub()
    assert (sub["plan"], sub["status"], sub["dodo_product_id"]) == (plan, "active", product)
    assert (await owner.billing())["plan"] == plan


async def test_a_product_we_dont_sell_grants_nothing(owner: Owner, on_sale: Settings) -> None:
    stored = await owner.send("subscription.active", "pdt_unknown")
    assert stored["status"] == "ignored"
    assert (await owner.sub())["plan"] == "free"


async def test_agency_down_to_business_is_a_downgrade_and_up_is_not(
    owner: Owner, on_sale: Settings
) -> None:
    await owner.send(
        "subscription.active", MAX_PRODUCT, created_at=datetime.now(UTC) - timedelta(minutes=9)
    )
    await owner.send("subscription.plan_changed", AGENCY_SIX)
    assert (await owner.sub())["plan"] == "agency"
    await owner.send("subscription.plan_changed", MAX_PRODUCT)
    assert (await owner.sub())["plan"] == "max"
    async with owner.engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT type FROM notifications WHERE workspace_id = :w ORDER BY created_at"),
            {"w": owner.wid},
        )
        assert [row[0] for row in rows] == ["plan_activated", "plan_activated", "plan_downgraded"]


async def test_reconcile_picks_up_a_move_to_six_month_on_the_same_plan(
    owner: Owner, on_sale: Settings, fake_dodo: FakeDodo
) -> None:
    await owner.send("subscription.active", PRO_PRODUCT, subscription_id="sub_1")
    fake_dodo.add_subscription("sub_1", product_id=PRO_SIX, customer_id="cus_test_1")
    await reconcile_all(owner.app.state.sessionmaker, fake_dodo, settings=on_sale)
    sub = await owner.sub()
    assert (sub["plan"], sub["dodo_product_id"]) == ("pro", PRO_SIX)


# ---------------------------------------------------------------- prices


async def test_the_plan_list_has_each_period_once_its_product_is_on_sale(
    client: httpx.AsyncClient, on_sale: Settings
) -> None:
    items = {i["plan"]: i for i in (await client.get("/v1/billing/plans")).json()["items"]}
    assert list(items) == list(PLANS)
    assert items["pro"]["six_month_price"] == {
        "plan": "pro",
        "amount_minor": 8100,
        "currency": "USD",
        "interval": "six_month",
    }
    assert items["max"]["six_month_price"]["amount_minor"] == 15300
    assert items["agency"]["available"] is True
    assert items["agency"]["trial_days"] == 0
    assert items["agency"]["price"]["amount_minor"] == 7000
    assert items["agency"]["six_month_price"]["amount_minor"] == 31500


async def test_with_only_todays_settings_nothing_new_is_on_sale(
    client: httpx.AsyncClient, fake_dodo: FakeDodo, redis: Redis
) -> None:
    """What production does with none of the new values set."""
    items = {i["plan"]: i for i in (await client.get("/v1/billing/plans")).json()["items"]}
    assert {plan: i["available"] for plan, i in items.items()} == {
        "free": True,
        "pro": True,
        "max": True,
        "agency": False,
    }
    assert [i["six_month_price"] for i in items.values()] == [None] * 4
    assert items["agency"]["price"] is None
    assert items["pro"]["price"]["interval"] == "month"
    asked = {call[1]["product_id"] for call in fake_dodo.calls if call[0] == "get_product_price"}
    assert asked == {PRO_PRODUCT, MAX_PRODUCT}


async def test_a_product_that_doesnt_bill_as_its_setting_says_is_not_offered(
    client: httpx.AsyncClient, on_sale: Settings, fake_dodo: FakeDodo
) -> None:
    fake_dodo.add_product(PRO_SIX, amount_minor=1500, currency="USD")  # monthly, in the wrong slot
    items = {i["plan"]: i for i in (await client.get("/v1/billing/plans")).json()["items"]}
    assert items["pro"]["six_month_price"] is None


async def test_six_month_alone_doesnt_price_a_plan_thats_not_on_sale(
    app: FastAPI,
    api_settings: Settings,
    client: httpx.AsyncClient,
    fake_dodo: FakeDodo,
    redis: Redis,
) -> None:
    only(dodo_product_agency_six_month=AGENCY_SIX)(app, api_settings)
    fake_dodo.add_product(AGENCY_SIX, amount_minor=31500, currency="USD", interval="six_month")
    items = {i["plan"]: i for i in (await client.get("/v1/billing/plans")).json()["items"]}
    assert (items["agency"]["available"], items["agency"]["six_month_price"]) == (False, None)


@pytest.mark.parametrize(
    ("product", "amount", "interval"),
    [(PRO_SIX, 8100, "six_month"), (PRO_PRODUCT, 99900, "month"), (AGENCY_SIX, 31500, "six_month")],
)
async def test_the_current_plan_shows_the_price_of_what_was_bought(
    owner: Owner, on_sale: Settings, product: str, amount: int, interval: str
) -> None:
    await owner.send("subscription.active", product)
    current = (await owner.billing())["current_price"]
    assert (current["amount_minor"], current["interval"]) == (amount, interval)


async def test_free_has_no_current_price(owner: Owner, on_sale: Settings) -> None:
    assert (await owner.billing())["current_price"] is None


# ---------------------------------------------------------------- allowances reset monthly


def _same_day_months_later(start: date, months: int, anchor: int) -> date:
    return usage._add_months(start, months, anchor)


@pytest.mark.parametrize("product", [PRO_SIX, AGENCY_SIX])
async def test_credits_and_posts_reset_monthly_on_a_six_month_plan_with_no_dodo_event(
    owner: Owner, on_sale: Settings, fake_dodo: FakeDodo, product: str
) -> None:
    start = datetime.now(UTC)
    await owner.send(
        "subscription.active",
        product,
        period_start=start,
        period_end=start + timedelta(days=182),
    )
    before = await owner.sub()
    assert before["current_period_end"] > start + timedelta(days=180)
    plan = before["plan"]
    anchor = before["billing_anchor_day"]
    assert anchor == min(start.day, 28)
    wid = uuid.UUID(owner.wid)
    first, _ = usage.period_for(anchor, start.date())
    credit_limit = entitlement(plan, "ai_credits_monthly")
    post_limit = entitlement(plan, "scheduled_posts_monthly")

    # Dodo stays silent from here: nothing is delivered, and nothing asks it.
    fake_dodo.calls.clear()
    for month in range(1, 6):  # the five resets inside the six months already paid
        period_start = _same_day_months_later(first, month - 1, anchor)
        last_day = _same_day_months_later(first, month, anchor) - timedelta(days=1)
        next_start = _same_day_months_later(first, month, anchor)
        at = datetime(last_day.year, last_day.month, last_day.day, 12, tzinfo=UTC)
        await use_credits_in_period(owner.engine, wid, at, used=150)
        with workspace_scope(wid):
            async with AsyncSession(owner.engine, expire_on_commit=False) as session:
                # Still the same month: what was used stays.
                credits = await quota(session, now=at)
                assert (credits.used, credits.limit) == (150, credit_limit)
                assert credits.period_end == next_start
                assert usage.period_for(anchor, last_day)[0] == period_start
                await period_used(session, "scheduled_posts_monthly", today=last_day)
                reserved = await usage.reserve(
                    session,
                    period_start=period_start,
                    cost=4,
                    metric=UsageMetric.SCHEDULED_POSTS,
                )
                assert reserved == 4

                # A day later: a new month's allowance, at 0, with the plan's limits.
                reset_at = datetime(next_start.year, next_start.month, next_start.day, tzinfo=UTC)
                credits = await quota(session, now=reset_at)
                assert (credits.used, credits.limit) == (0, credit_limit)
                assert credits.period_end == _same_day_months_later(first, month + 1, anchor)
                assert await period_used(session, "scheduled_posts_monthly", today=next_start) == (
                    0,
                    post_limit,
                )
                await session.commit()
        after = await owner.sub()
        assert (after["plan"], after["status"]) == (plan, "active")
        assert after["current_period_end"] == before["current_period_end"]
        assert after["billing_anchor_day"] == anchor

    assert fake_dodo.calls == []


async def use_credits_in_period(
    engine: AsyncEngine, wid: uuid.UUID, at: datetime, used: int
) -> None:
    """Set the credits used in the period containing ``at`` only."""
    with workspace_scope(wid):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            credits = await quota(session, now=at)
            await session.commit()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE usage_counters SET used = :u WHERE workspace_id = :w"
                " AND metric = 'ai_credits' AND period_end = :end"
            ),
            {"u": used, "w": wid, "end": credits.period_end},
        )


async def test_the_reconcile_job_leaves_a_six_month_plan_alone_between_payments(
    owner: Owner, on_sale: Settings, fake_dodo: FakeDodo
) -> None:
    start = datetime.now(UTC)
    end = start + timedelta(days=182)
    await owner.send(
        "subscription.active",
        AGENCY_SIX,
        subscription_id="sub_1",
        period_start=start,
        period_end=end,
    )
    fake_dodo.add_subscription(
        "sub_1",
        product_id=AGENCY_SIX,
        customer_id="cus_test_1",
        previous_billing_date=start,
        next_billing_date=end,
    )
    before = await owner.sub()
    await reconcile_all(owner.app.state.sessionmaker, fake_dodo, settings=on_sale)
    after = await owner.sub()
    assert (after["plan"], after["status"]) == ("agency", "active")
    assert after["current_period_end"] == before["current_period_end"]
    assert after["billing_anchor_day"] == before["billing_anchor_day"]


async def test_the_usage_meter_resets_on_the_anchor_not_at_the_end_of_the_six_months(
    owner: Owner, on_sale: Settings
) -> None:
    """The usage page's "Resets on …" is the meter's period_end (lib/billing/plan.ts)."""
    start = datetime.now(UTC)
    await owner.send(
        "subscription.active", PRO_SIX, period_start=start, period_end=start + timedelta(days=182)
    )
    billing = await owner.billing()
    meters = {m["metric"]: m for m in billing["usage"]}
    end = date.fromisoformat(meters["ai_credits"]["period_end"])
    assert end - start.date() <= timedelta(days=31)
    assert meters["scheduled_posts"]["period_end"] == meters["ai_credits"]["period_end"]
    assert datetime.fromisoformat(billing["current_period_end"]) > start + timedelta(days=180)


async def test_set_subscription_keeps_working_with_agency(owner: Owner) -> None:
    """The check constraint (migration 0057) accepts the new key."""
    await set_subscription(owner.engine, workspace_id=owner.wid, plan="agency", status="active")
    meters = {m["metric"]: m for m in (await owner.billing())["usage"]}
    assert meters["ai_credits"]["limit"] == 12_000
    assert meters["scheduled_posts"]["limit"] is None
    assert meters["active_automations"]["limit"] is None
    assert meters["instagram_accounts"]["limit"] == 10
    assert "channels" not in meters
