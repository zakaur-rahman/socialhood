"""The billing routes (T8.2; TR-BIL-01, TR-BIL-05, TR-BIL-06, FR-BIL-01…04, F-15): checkout,
the customer portal, cancel and resume, the public plan list and GET …/billing, against the
FakeDodo. None of them changes the plan (FR-BIL-02)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing.dodo import DodoError
from socialhood.billing.dodo_fake import FAKE_CHECKOUT_BASE, FAKE_PORTAL_BASE, FakeDodo
from socialhood.billing.plans import ENTITLEMENTS, entitlement
from tests.support.api import WEB, Clerk, sign_in
from tests.support.billing import PRO_PRICE_MINOR, PRO_PRODUCT, make_payment, set_subscription
from tests.support.ingest import stream


@dataclass
class Owner:
    client: httpx.AsyncClient
    engine: AsyncEngine
    clerk: Clerk
    clerk_id: str
    wid: str
    slug: str

    async def post(self, path: str, json: Any = None) -> httpx.Response:
        return await self.client.post(
            f"/v1/w/{self.wid}{path}", json=json, headers=self.clerk.headers(self.clerk_id)
        )

    async def get(self, path: str, **params: Any) -> httpx.Response:
        return await self.client.get(
            f"/v1/w/{self.wid}{path}", params=params, headers=self.clerk.headers(self.clerk_id)
        )

    async def billing(self) -> dict[str, Any]:
        response = await self.client.get(
            f"/v1/w/{self.wid}/billing", headers=self.clerk.headers(self.clerk_id)
        )
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    async def execute(self, sql: str, **params: Any) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(sql), params)


@pytest.fixture
async def owner(
    client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis
) -> Owner:
    clerk_id, me = await sign_in(client, clerk, email="owner@example.com", first_name="Asha")
    ws = me["workspaces"][0]
    return Owner(client, engine, clerk, clerk_id, ws["id"], ws["slug"])


async def paid(owner: Owner, fake_dodo: FakeDodo, **values: Any) -> None:
    fake_dodo.add_subscription("sub_1", product_id=PRO_PRODUCT, customer_id="cus_1")
    await set_subscription(
        owner.engine,
        workspace_id=owner.wid,
        **{
            "plan": "pro",
            "status": "active",
            "dodo_subscription_id": "sub_1",
            "dodo_customer_id": "cus_1",
            "current_period_end": datetime.now(UTC) + timedelta(days=20),
            **values,
        },
    )


# ---------------------------------------------------------------- checkout (TR-BIL-01, 05)


async def test_checkout_starts_the_trial_for_an_eligible_workspace(
    owner: Owner, fake_dodo: FakeDodo
) -> None:
    response = await owner.post("/billing/checkout", {"plan": "pro"})

    assert response.status_code == 200, response.text
    assert response.json()["trial"] is True
    assert response.json()["checkout_url"].startswith(FAKE_CHECKOUT_BASE)
    [params] = fake_dodo.checkouts
    assert (params.product_id, params.customer_email) == (PRO_PRODUCT, "owner@example.com")
    assert params.return_url == f"{WEB}/w/{owner.slug}/settings/billing?checkout=return"
    assert dict(params.metadata) == {"workspace_id": owner.wid}
    assert params.trial_period_days == 7
    assert (await owner.billing())["plan"] == "free"  # nothing changes until the webhook


async def test_checkout_sends_no_trial_once_one_was_used(owner: Owner, fake_dodo: FakeDodo) -> None:
    await owner.execute(
        "UPDATE workspaces SET trial_used_at = now() - interval '90 days' WHERE id = :w",
        w=owner.wid,
    )
    response = await owner.post("/billing/checkout", {"plan": "pro"})
    assert response.json()["trial"] is False
    assert fake_dodo.checkouts[0].trial_period_days == 0  # overrides the product's own trial


@pytest.mark.parametrize("status", ["active", "trialing", "on_hold"])
async def test_checkout_is_409_while_a_paid_plan_is_live(
    owner: Owner, fake_dodo: FakeDodo, status: str
) -> None:
    await paid(owner, fake_dodo, status=status)
    response = await owner.post("/billing/checkout", {"plan": "pro"})
    assert (response.status_code, response.json()["code"]) == (409, "conflict")
    assert fake_dodo.checkouts == []


async def test_checkout_after_an_expired_plan_is_allowed(owner: Owner, fake_dodo: FakeDodo) -> None:
    await paid(owner, fake_dodo, plan="free", status="expired")
    assert (await owner.post("/billing/checkout", {"plan": "pro"})).status_code == 200


async def test_max_is_422_until_r2(owner: Owner, fake_dodo: FakeDodo) -> None:
    response = await owner.post("/billing/checkout", {"plan": "max"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "plan"
    assert fake_dodo.checkouts == []


async def test_checkout_is_503_when_dodo_fails_or_isnt_set_up(
    app: FastAPI, owner: Owner, fake_dodo: FakeDodo
) -> None:
    fake_dodo.fail_next(DodoError("down", status=503, retryable=True))
    down = await owner.post("/billing/checkout", {"plan": "pro"})
    assert (down.status_code, down.json()["code"]) == (503, "service_unavailable")

    app.state.settings = app.state.settings.model_copy(update={"dodo_product_pro_monthly": None})
    missing = await owner.post("/billing/checkout", {"plan": "pro"})
    assert (missing.status_code, missing.json()["detail"]) == (503, "Payments aren't set up yet.")


async def test_only_the_owner_can_use_billing_actions(
    owner: Owner, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    admin_id, admin = await sign_in(client, clerk, email="admin@example.com")
    await owner.execute(
        "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (:w, :u, 'admin')",
        w=owner.wid,
        u=admin["id"],
    )
    for path, body in (
        ("checkout", {"plan": "pro"}),
        ("portal", None),
        ("cancel", None),
        ("resume", None),
    ):
        response = await client.post(
            f"/v1/w/{owner.wid}/billing/{path}", json=body, headers=clerk.headers(admin_id)
        )
        assert response.status_code == 403, path
    seen = await client.get(f"/v1/w/{owner.wid}/billing", headers=clerk.headers(admin_id))
    assert seen.status_code == 200  # any member reads it


# ---------------------------------------------------------------- portal (FR-BIL-04)


async def test_the_portal_needs_a_dodo_customer(owner: Owner, fake_dodo: FakeDodo) -> None:
    response = await owner.post("/billing/portal")
    assert (response.status_code, response.json()["code"]) == (409, "conflict")

    await paid(owner, fake_dodo)
    response = await owner.post("/billing/portal")
    assert response.status_code == 200, response.text
    assert response.json() == {"portal_url": FAKE_PORTAL_BASE + "cus_1"}
    name, args = fake_dodo.calls[-1]
    assert (name, args["return_url"]) == (
        "create_portal_session",
        f"{WEB}/w/{owner.slug}/settings/billing",
    )


# ---------------------------------------------------------------- cancel and resume (TR-BIL-06)


async def test_cancel_at_the_period_end_then_resume(
    owner: Owner, fake_dodo: FakeDodo, redis: Redis
) -> None:
    await paid(owner, fake_dodo)

    cancelled = await owner.post("/billing/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert (cancelled.json()["plan"], cancelled.json()["cancel_at_period_end"]) == ("pro", True)
    assert fake_dodo.subscriptions["sub_1"].cancel_at_next_billing_date is True
    again = await owner.post("/billing/cancel")
    assert again.json()["cancel_at_period_end"] is True
    assert [n for n, _ in fake_dodo.calls].count("set_cancel_at_period_end") == 1

    resumed = await owner.post("/billing/resume")
    assert (resumed.json()["plan"], resumed.json()["cancel_at_period_end"]) == ("pro", False)
    assert fake_dodo.subscriptions["sub_1"].cancel_at_next_billing_date is False
    assert (await owner.post("/billing/resume")).status_code == 409
    published = [kind for kind, _ in await stream(redis, owner.wid)]
    assert published.count("usage.updated") == 2  # every open billing page refetches


async def test_cancel_and_resume_are_409_on_free(owner: Owner, fake_dodo: FakeDodo) -> None:
    for action in ("cancel", "resume"):
        response = await owner.post(f"/billing/{action}")
        assert (response.status_code, response.json()["detail"]) == (
            409,
            "You're on the Free plan.",
        )
    assert fake_dodo.calls == []


async def test_a_dodo_refusal_is_409_and_an_outage_503(owner: Owner, fake_dodo: FakeDodo) -> None:
    await paid(owner, fake_dodo)
    fake_dodo.fail_next(DodoError("already cancelled", status=409))
    assert (await owner.post("/billing/cancel")).status_code == 409
    fake_dodo.fail_next(DodoError("down", status=502, retryable=True))
    assert (await owner.post("/billing/cancel")).status_code == 503
    assert (await owner.billing())["cancel_at_period_end"] is False


# ---------------------------------------------------------------- plans and prices (TR-BIL-06)


async def test_the_public_plan_list_has_entitlements_prices_and_the_trial(
    client: httpx.AsyncClient, fake_dodo: FakeDodo, redis: Redis
) -> None:
    response = await client.get("/v1/billing/plans")  # no sign-in

    assert response.status_code == 200, response.text
    items = {item["plan"]: item for item in response.json()["items"]}
    assert list(items) == ["free", "pro", "max"]
    assert items["free"]["price"] is None
    assert items["pro"]["price"] == {
        "plan": "pro",
        "amount_minor": PRO_PRICE_MINOR,
        "currency": "INR",
        "interval": "month",
    }
    assert (items["pro"]["trial_days"], items["pro"]["available"]) == (7, True)
    assert (items["max"]["trial_days"], items["max"]["available"]) == (0, False)
    pro = {e["key"]: e["value"] for e in items["pro"]["entitlements"]}
    assert set(pro) == set(ENTITLEMENTS)
    assert pro["active_automations"] == entitlement("pro", "active_automations")
    assert pro["ai_modes"] == ["off", "suggest", "auto"]

    # Cached for an hour: a second read doesn't ask Dodo again.
    asked = len(fake_dodo.calls)
    await client.get("/v1/billing/plans")
    assert len(fake_dodo.calls) == asked


async def test_prices_are_left_out_when_dodo_cant_give_them(
    client: httpx.AsyncClient, fake_dodo: FakeDodo, redis: Redis
) -> None:
    fake_dodo.products.clear()
    items = (await client.get("/v1/billing/plans")).json()["items"]
    assert [item["price"] for item in items] == [None, None, None]


async def test_get_billing_has_prices_and_a_meter_for_every_limit(owner: Owner) -> None:
    """Max's price shows although Max can't be bought yet (the plan list says available: false)."""
    billing = await owner.billing()

    assert {(p["plan"], p["amount_minor"]) for p in billing["prices"]} == {
        ("pro", PRO_PRICE_MINOR),
        ("max", 499900),
    }
    meters = {m["metric"]: m for m in billing["usage"]}
    assert set(meters) == {
        "ai_credits",
        "scheduled_posts",
        "knowledge_characters",
        "active_automations",
        "pending_scheduled_messages",
        "instagram_accounts",
        "whatsapp_accounts",
    }
    assert (meters["ai_credits"]["limit"], meters["scheduled_posts"]["limit"]) == (200, 10)
    assert (meters["instagram_accounts"]["used"], meters["instagram_accounts"]["limit"]) == (0, 1)
    assert meters["ai_credits"]["period_end"] == meters["scheduled_posts"]["period_end"]
    assert billing["trial_eligible"] is True


# ---------------------------------------------------------------- payment history (C-065)


async def test_payment_history_is_newest_first_with_dodos_fields_and_pages(owner: Owner) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    first = await make_payment(
        owner.engine, workspace_id=owner.wid, occurred_at=now - timedelta(days=62)
    )
    failed = await make_payment(
        owner.engine,
        workspace_id=owner.wid,
        occurred_at=now - timedelta(days=31),
        status="failed",
        invoice_url=None,
        failure_reason="The card was declined.",
    )
    latest = await make_payment(
        owner.engine,
        workspace_id=owner.wid,
        occurred_at=now - timedelta(days=1),
        amount_minor=129900,
        currency="USD",
        invoice_url="https://invoices.dodo.invalid/pay_latest",
    )

    response = await owner.get("/billing/payments")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["id"] for item in body["items"]] == [str(latest), str(failed), str(first)]
    assert body["next_cursor"] is None
    assert body["items"][0] == {
        "id": str(latest),
        "occurred_at": (now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "amount_minor": 129900,
        "currency": "USD",
        "status": "succeeded",
        "invoice_url": "https://invoices.dodo.invalid/pay_latest",
        "failure_reason": None,
    }
    assert body["items"][1]["status"] == "failed"
    assert body["items"][1]["invoice_url"] is None
    assert body["items"][1]["failure_reason"] == "The card was declined."
    assert body["items"][2]["amount_minor"] == PRO_PRICE_MINOR

    page = (await owner.get("/billing/payments", limit=2)).json()
    assert [item["id"] for item in page["items"]] == [str(latest), str(failed)]
    rest = (await owner.get("/billing/payments", limit=2, cursor=page["next_cursor"])).json()
    assert [item["id"] for item in rest["items"]] == [str(first)]
    assert rest["next_cursor"] is None
    assert (await owner.get("/billing/payments", cursor="nope")).status_code == 422
    assert (await owner.get("/billing/payments", limit=51)).status_code == 422


async def test_payment_history_is_empty_before_the_first_payment(owner: Owner) -> None:
    response = await owner.get("/billing/payments")
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.parametrize(("role", "status"), [("admin", 200), ("agent", 403)])
async def test_payment_history_is_for_owners_and_admins(
    owner: Owner, role: str, status: int
) -> None:
    await make_payment(owner.engine, workspace_id=owner.wid)
    await owner.execute(
        "UPDATE workspace_members SET role = :r WHERE workspace_id = :w", r=role, w=owner.wid
    )
    assert (await owner.get("/billing/payments")).status_code == status


async def test_payment_history_never_shows_another_workspaces_payments(
    owner: Owner, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    mine = await make_payment(owner.engine, workspace_id=owner.wid)
    other_clerk, other_me = await sign_in(client, clerk, email="other@example.com")
    other_wid = other_me["workspaces"][0]["id"]
    theirs = await make_payment(owner.engine, workspace_id=other_wid)

    listed = (await owner.get("/billing/payments")).json()["items"]
    assert [item["id"] for item in listed] == [str(mine)]
    their_list = await client.get(
        f"/v1/w/{other_wid}/billing/payments", headers=clerk.headers(other_clerk)
    )
    assert [item["id"] for item in their_list.json()["items"]] == [str(theirs)]
    # Another workspace's history is 404 to a non-member (TR-API-03), never 403.
    crossed = await client.get(
        f"/v1/w/{other_wid}/billing/payments", headers=clerk.headers(owner.clerk_id)
    )
    assert crossed.status_code == 404
