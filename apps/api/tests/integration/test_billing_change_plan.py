"""C-209: moving a paid plan to another plan or period from the app, through Dodo's change-plan
API: the preview, the change itself (the plan moves only with Dodo's webhook), and every refusal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing.dodo import DodoError
from socialhood.billing.dodo_fake import FakeDodo
from socialhood.models.billing import SubscriptionStatus
from socialhood.services.webhook_handlers import dodo as dodo_handler
from socialhood.settings import Settings
from tests.support.api import Clerk, sign_in
from tests.support.billing import MAX_PRODUCT, PRO_PRICE_MINOR, PRO_PRODUCT, set_subscription
from tests.support.dodo import send, subscription

pytestmark = pytest.mark.usefixtures("queue")

SUB = "sub_test_1"
MAX_PRICE_MINOR = 499900  # tests/support/billing.py's fake Business price
PRO_SIX = "pdt_test_pro_six"


@dataclass
class Owner:
    app: FastAPI
    client: httpx.AsyncClient
    engine: AsyncEngine
    clerk: Clerk
    clerk_id: str
    wid: str

    async def post(self, path: str, **body: str) -> httpx.Response:
        return await self.client.post(
            f"/v1/w/{self.wid}/billing/{path}", json=body, headers=self.clerk.headers(self.clerk_id)
        )

    async def plan(self) -> str:
        response = await self.client.get(
            f"/v1/w/{self.wid}/billing", headers=self.clerk.headers(self.clerk_id)
        )
        assert response.status_code == 200, response.text
        plan: str = response.json()["plan"]
        return plan

    async def subscribe(self, fake: FakeDodo, product: str, **values: Any) -> None:
        """Dodo's side of a finished checkout: the subscription exists there and its webhook ran."""
        fake.add_subscription(SUB, product_id=product)
        data = subscription(self.wid, subscription_id=SUB, product_id=product, **values)
        await send(self.app, self.client, self.engine, "subscription.active", data)

    async def webhook(self, event: str, product: str) -> None:
        data = subscription(self.wid, subscription_id=SUB, product_id=product)
        await send(self.app, self.client, self.engine, event, data)


@pytest.fixture(autouse=True)
def webhook_settings(api_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """The webhook handler reads the same settings as the app (as test_billing_six_month does)."""
    monkeypatch.setattr(dodo_handler, "get_settings", lambda: api_settings)


@pytest.fixture
async def owner(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis
) -> Owner:
    clerk_id, me = await sign_in(client, clerk, email="owner@example.com", first_name="Asha")
    return Owner(app, client, engine, clerk, clerk_id, me["workspaces"][0]["id"])


def changes(fake: FakeDodo) -> list[str]:
    return [args["product_id"] for name, args in fake.calls if name == "change_plan"]


async def test_creator_previews_and_upgrades_to_business_when_dodo_confirms(
    owner: Owner, fake_dodo: FakeDodo
) -> None:
    await owner.subscribe(fake_dodo, PRO_PRODUCT)

    preview = await owner.post("change-plan/preview", plan="max")
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert (body["plan"], body["period"]) == ("max", "month")
    assert body["amount_due_minor"] == MAX_PRICE_MINOR - PRO_PRICE_MINOR
    assert (body["credit_minor"], body["currency"]) == (0, "INR")
    assert changes(fake_dodo) == []  # a preview changes nothing

    response = await owner.post("change-plan", plan="max")
    assert response.status_code == 200, response.text
    assert response.json()["plan"] == "pro"  # D9: not until Dodo's webhook says so
    assert changes(fake_dodo) == [MAX_PRODUCT]

    await owner.webhook("subscription.plan_changed", MAX_PRODUCT)
    assert await owner.plan() == "max"


async def test_business_downgrades_to_creator_with_the_difference_as_credit(
    owner: Owner, fake_dodo: FakeDodo
) -> None:
    await owner.subscribe(fake_dodo, MAX_PRODUCT)

    body = (await owner.post("change-plan/preview", plan="pro")).json()
    assert (body["amount_due_minor"], body["credit_minor"]) == (
        0,
        MAX_PRICE_MINOR - PRO_PRICE_MINOR,
    )

    assert (await owner.post("change-plan", plan="pro")).status_code == 200
    await owner.webhook("subscription.plan_changed", PRO_PRODUCT)
    assert await owner.plan() == "pro"


@pytest.mark.parametrize("path", ["change-plan", "change-plan/preview"])
async def test_free_uses_checkout_instead(owner: Owner, fake_dodo: FakeDodo, path: str) -> None:
    response = await owner.post(path, plan="max")
    assert response.status_code == 409
    assert "no paid plan to change" in response.json()["detail"]
    assert fake_dodo.calls == []


async def test_the_same_plan_and_period_is_refused(owner: Owner, fake_dodo: FakeDodo) -> None:
    await owner.subscribe(fake_dodo, PRO_PRODUCT)
    response = await owner.post("change-plan", plan="pro", period="month")
    assert response.status_code == 409
    assert response.json()["detail"] == "You're already on Creator."
    assert changes(fake_dodo) == []


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"cancel_at_period_end": True}, "Resume it first"),
        ({"status": SubscriptionStatus.ON_HOLD}, "Update your card"),
    ],
)
async def test_an_ending_or_unpaid_plan_is_refused(
    owner: Owner, fake_dodo: FakeDodo, values: dict[str, Any], message: str
) -> None:
    await owner.subscribe(fake_dodo, PRO_PRODUCT)
    await set_subscription(owner.engine, workspace_id=owner.wid, **values)
    response = await owner.post("change-plan", plan="max")
    assert response.status_code == 409
    assert message in response.json()["detail"]
    assert changes(fake_dodo) == []


async def test_six_monthly_to_monthly_is_refused_but_monthly_to_six_monthly_works(
    app: FastAPI,
    api_settings: Settings,
    owner: Owner,
    fake_dodo: FakeDodo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = api_settings.model_copy(update={"dodo_product_pro_six_month": PRO_SIX})
    app.state.settings = settings
    monkeypatch.setattr(dodo_handler, "get_settings", lambda: settings)
    fake_dodo.add_product(PRO_SIX, amount_minor=8100, currency="INR", interval="six_month")

    await owner.subscribe(fake_dodo, PRO_PRODUCT)
    assert (await owner.post("change-plan", plan="pro", period="six_month")).status_code == 200
    await owner.webhook("subscription.plan_changed", PRO_SIX)

    response = await owner.post("change-plan", plan="max", period="month")
    assert response.status_code == 409
    assert "6-monthly to monthly" in response.json()["detail"]


async def test_a_plan_not_on_sale_is_a_422(owner: Owner, fake_dodo: FakeDodo) -> None:
    await owner.subscribe(fake_dodo, PRO_PRODUCT)
    response = await owner.post("change-plan", plan="agency")
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "plan"


@pytest.mark.parametrize(
    ("error", "status", "message"),
    [
        (DodoError("pending", status=409), 409, "already in progress"),
        (DodoError("refused", status=422), 409, "couldn't make this change"),
        (DodoError("down", status=503, retryable=True), 503, "didn't answer"),
    ],
)
async def test_dodo_refusals_and_outages_leave_the_plan_as_it_was(
    owner: Owner, fake_dodo: FakeDodo, error: DodoError, status: int, message: str
) -> None:
    await owner.subscribe(fake_dodo, PRO_PRODUCT)
    fake_dodo.fail_next(error)
    response = await owner.post("change-plan", plan="max")
    assert response.status_code == status
    assert message in response.json()["detail"]
    assert await owner.plan() == "pro"
