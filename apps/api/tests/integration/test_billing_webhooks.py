"""POST /webhooks/dodo end to end (T8.3; TR-BIL-02, TR-BIL-05, FR-BIL-02, 03, 06, 07, SEC-04):
signed delivery, stored once, processed by the worker's job, applied by the state machine. One
test per Dodo event, out-of-order events ignored, unsigned events rejected, replays idempotent,
the downgrade's effects, and no way to Pro without a signed event."""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.billing.dodo_fake import FakeDodo
from socialhood.services.webhook_handlers import dodo as dodo_handler
from socialhood.settings import Settings
from tests.support.api import Clerk, sign_in
from tests.support.automations import make_automation
from tests.support.billing import MAX_PRODUCT, dodo_event, set_subscription, signed_headers
from tests.support.dodo import deliver, payment, process_all, send, subscription
from tests.support.inbox import make_account
from tests.support.ingest import stream

pytestmark = pytest.mark.usefixtures("queue")

# A well-formed Standard Webhooks secret that isn't the app's.
FORGED_SECRET = "whsec_" + base64.b64encode(b"forged-key-for-tests").decode()


@pytest.fixture(autouse=True)
def handler_settings(api_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """The worker reads its settings from the environment; here, the test app's."""
    monkeypatch.setattr(dodo_handler, "get_settings", lambda: api_settings)


@dataclass
class Owner:
    app: FastAPI
    client: httpx.AsyncClient
    engine: AsyncEngine
    clerk: Clerk
    clerk_id: str
    wid: str

    async def event(self, event_type: str, data: dict[str, Any], **kw: Any) -> dict[str, Any]:
        return await send(self.app, self.client, self.engine, event_type, data, **kw)

    async def sub(self) -> dict[str, Any]:
        return await one(
            self.engine, "SELECT * FROM subscriptions WHERE workspace_id = :w", self.wid
        )

    async def billing(self) -> dict[str, Any]:
        response = await self.client.get(
            f"/v1/w/{self.wid}/billing", headers=self.clerk.headers(self.clerk_id)
        )
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    async def notifications(self) -> list[tuple[str, str]]:
        rows = await all_rows(
            self.engine,
            "SELECT type, body FROM notifications WHERE workspace_id = :w ORDER BY created_at",
            self.wid,
        )
        return [(r["type"], r["body"]) for r in rows]


async def all_rows(engine: AsyncEngine, sql: str, wid: str) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        return [dict(r._mapping) for r in await conn.execute(text(sql), {"w": wid})]


async def one(engine: AsyncEngine, sql: str, wid: str) -> dict[str, Any]:
    [row] = await all_rows(engine, sql, wid)
    return row


@pytest.fixture
async def owner(
    app: FastAPI, client: httpx.AsyncClient, clerk: Clerk, engine: AsyncEngine, redis: Redis
) -> Owner:
    clerk_id, me = await sign_in(client, clerk, email="owner@example.com")
    return Owner(app, client, engine, clerk, clerk_id, me["workspaces"][0]["id"])


def ago(**delta: float) -> datetime:
    return datetime.now(UTC) - timedelta(**delta)


def soon(**delta: float) -> datetime:
    return datetime.now(UTC) + timedelta(**delta)


async def make_pro(owner: Owner, **values: Any) -> dict[str, Any]:
    """The workspace on Pro through a signed subscription.active (active, not a trial)."""
    row = await owner.event(
        "subscription.active", subscription(owner.wid, **values), at=ago(hours=1)
    )
    assert row["status"] == "processed", row
    return await owner.sub()


# ---------------------------------------------------------------- subscription.active


async def test_active_with_a_trial_starts_the_pro_trial(owner: Owner, redis: Redis) -> None:
    started = ago(minutes=2)
    data = subscription(
        owner.wid,
        trial_period_days=7,
        created_at=started,
        period_start=started,
        period_end=started + timedelta(days=7),
    )
    row = await owner.event("subscription.active", data)

    assert (row["status"], str(row["workspace_id"])) == ("processed", owner.wid)
    sub = await owner.sub()
    assert (sub["plan"], sub["status"]) == ("pro", "trialing")
    assert (sub["dodo_subscription_id"], sub["dodo_customer_id"]) == ("sub_test_1", "cus_test_1")
    assert abs(sub["trial_ends_at"] - (started + timedelta(days=7))) < timedelta(seconds=1)
    assert sub["billing_anchor_day"] == min(started.day, 28)
    assert sub["last_event_at"] is not None
    workspace = await one(
        owner.engine, "SELECT trial_used_at FROM workspaces WHERE id = :w", owner.wid
    )
    assert workspace["trial_used_at"] is not None  # TR-BIL-05: one trial per workspace

    billing = await owner.billing()
    assert (billing["plan"], billing["status"], billing["trial_eligible"]) == (
        "pro",
        "trialing",
        False,
    )
    credits = next(m for m in billing["usage"] if m["metric"] == "ai_credits")
    assert credits["limit"] == 5000
    assert [t for t, _ in await owner.notifications()] == ["plan_activated"]
    published = [data for kind, data in await stream(redis, owner.wid) if kind == "usage.updated"]
    assert {p["metric"] for p in published} == {"ai_credits", "scheduled_posts"}
    assert next(p for p in published if p["metric"] == "ai_credits")["limit"] == 5000


async def test_active_without_a_trial_is_active_and_keeps_the_trial(owner: Owner) -> None:
    sub = await make_pro(owner)
    assert (sub["plan"], sub["status"], sub["trial_ends_at"]) == ("pro", "active", None)
    workspace = await one(
        owner.engine, "SELECT trial_used_at FROM workspaces WHERE id = :w", owner.wid
    )
    assert workspace["trial_used_at"] is None


async def test_the_owners_other_workspaces_lose_the_trial_too(
    owner: Owner, client: httpx.AsyncClient, clerk: Clerk
) -> None:
    """TR-BIL-05: one trial per owner email, across their workspaces."""
    started = ago(minutes=1)
    await owner.event(
        "subscription.active",
        subscription(owner.wid, trial_period_days=7, created_at=started, period_start=started),
    )
    second_id, second = await sign_in(client, clerk, email="OWNER@example.com")
    response = await client.get(
        f"/v1/w/{second['workspaces'][0]['id']}/billing", headers=clerk.headers(second_id)
    )
    assert response.json()["trial_eligible"] is False


async def test_an_unknown_product_changes_nothing(owner: Owner) -> None:
    row = await owner.event("subscription.active", subscription(owner.wid, product_id="pdt_other"))
    assert row["status"] == "ignored"
    assert "not a plan we sell" in row["last_error"]
    assert (await owner.sub())["plan"] == "free"


# ---------------------------------------------------------------- renewals and plan changes


async def test_renewed_starts_the_new_period_and_clears_a_hold(owner: Owner) -> None:
    await make_pro(owner)
    await owner.event(
        "subscription.on_hold", subscription(owner.wid, status="on_hold"), at=ago(minutes=30)
    )
    assert (await owner.sub())["status"] == "on_hold"

    start, end = ago(minutes=5), soon(days=30)
    row = await owner.event(
        "subscription.renewed", subscription(owner.wid, period_start=start, period_end=end)
    )
    assert row["status"] == "processed"
    sub = await owner.sub()
    assert (sub["plan"], sub["status"], sub["grace_until"]) == ("pro", "active", None)
    assert abs(sub["current_period_end"] - end) < timedelta(seconds=1)


async def test_plan_changed_takes_the_plan_from_the_product(owner: Owner) -> None:
    await make_pro(owner)
    row = await owner.event(
        "subscription.plan_changed", subscription(owner.wid, product_id=MAX_PRODUCT)
    )
    assert row["status"] == "processed"
    assert ((await owner.sub())["plan"], (await owner.sub())["status"]) == ("max", "active")


async def test_unpaused_is_active_again(owner: Owner) -> None:
    await make_pro(owner)
    await owner.event(
        "subscription.paused", subscription(owner.wid, status="paused"), at=ago(minutes=30)
    )
    row = await owner.event("subscription.unpaused", subscription(owner.wid))
    assert row["status"] == "processed"
    sub = await owner.sub()
    assert (sub["status"], sub["grace_until"]) == ("active", None)


# ---------------------------------------------------------------- payment trouble (FR-BIL-06)


@pytest.mark.parametrize(
    "event_type", ["subscription.on_hold", "subscription.past_due", "subscription.paused"]
)
async def test_a_hold_keeps_pro_for_three_days_of_grace(owner: Owner, event_type: str) -> None:
    await make_pro(owner)
    at = ago(minutes=10)
    row = await owner.event(event_type, subscription(owner.wid, status="on_hold"), at=at)

    assert row["status"] == "processed"
    sub = await owner.sub()
    assert (sub["plan"], sub["status"]) == ("pro", "on_hold")
    assert abs(sub["grace_until"] - (at + timedelta(days=3))) < timedelta(seconds=1)
    billing = await owner.billing()
    assert billing["grace_until"] is not None
    assert [t for t, _ in await owner.notifications()] == ["plan_activated", "payment_problem"]

    # A second hold event keeps the first grace (it isn't extended).
    await owner.event(event_type, subscription(owner.wid, status="on_hold"))
    assert (await owner.sub())["grace_until"] == sub["grace_until"]


async def test_updated_refreshes_only_the_period_and_the_cancel_flag(owner: Owner) -> None:
    await make_pro(owner)
    end = soon(days=40)
    row = await owner.event(
        "subscription.updated",
        subscription(owner.wid, status="on_hold", period_end=end, cancel_at_next_billing_date=True),
    )
    assert row["status"] == "processed"
    sub = await owner.sub()
    assert (sub["plan"], sub["status"], sub["cancel_at_period_end"]) == ("pro", "active", True)
    assert abs(sub["current_period_end"] - end) < timedelta(seconds=1)


# ---------------------------------------------------------------- cancel and end


async def test_cancelled_keeps_pro_until_the_period_ends(owner: Owner) -> None:
    await make_pro(owner)
    row = await owner.event(
        "subscription.cancelled",
        subscription(owner.wid, status="cancelled", period_end=soon(days=20)),
    )
    assert row["status"] == "processed"
    sub = await owner.sub()
    assert (sub["plan"], sub["status"], sub["cancel_at_period_end"]) == ("pro", "active", True)


async def test_cancelled_at_the_period_end_goes_to_free(owner: Owner) -> None:
    await make_pro(owner)
    row = await owner.event(
        "subscription.cancelled",
        subscription(
            owner.wid, status="cancelled", period_start=ago(days=30), period_end=ago(minutes=2)
        ),
    )
    assert row["status"] == "processed"
    sub = await owner.sub()
    assert (sub["plan"], sub["status"], sub["cancel_at_period_end"]) == ("free", "expired", False)
    assert [t for t, _ in await owner.notifications()] == ["plan_activated", "plan_downgraded"]


@pytest.mark.parametrize("event_type", ["subscription.failed", "subscription.expired"])
async def test_failed_and_expired_move_to_free_with_the_downgrade(
    owner: Owner, event_type: str
) -> None:
    await make_pro(owner)
    auto = await make_account(owner.engine, owner.wid, username="maple.bakery")
    second = await make_account(owner.engine, owner.wid, username="maple.cakes")
    async with owner.engine.begin() as conn:
        await conn.execute(text("UPDATE social_accounts SET ai_mode = 'auto'"))
    ai = await make_automation(
        owner.engine,
        workspace_id=owner.wid,
        account_id=auto,
        action="ai_reply",
        keywords=("price",),
    )
    kept = [
        await make_automation(owner.engine, workspace_id=owner.wid, account_id=auto, keywords=(w,))
        for w in ("a", "b", "c", "d")
    ]
    on_second = await make_automation(
        owner.engine, workspace_id=owner.wid, account_id=second, keywords=("e",)
    )
    # "most recently updated active": a is the oldest update, so it is the one over the limit.
    async with owner.engine.begin() as conn:
        for i, automation_id in enumerate(kept):
            await conn.execute(
                text(
                    "UPDATE automations SET updated_at = now() - make_interval(hours => :h)"
                    " WHERE id = :a"
                ),
                {"h": 10 - i, "a": automation_id},
            )

    row = await owner.event(event_type, subscription(owner.wid, status=event_type.split(".")[1]))

    assert row["status"] == "processed"
    sub = await owner.sub()
    assert (sub["plan"], sub["status"]) == ("free", "expired")
    modes = await all_rows(
        owner.engine, "SELECT ai_mode FROM social_accounts WHERE workspace_id = :w", owner.wid
    )
    assert {r["ai_mode"] for r in modes} == {"suggest"}
    statuses = {
        r["id"]: r["status"]
        for r in await all_rows(
            owner.engine, "SELECT id, status FROM automations WHERE workspace_id = :w", owner.wid
        )
    }
    assert statuses[ai] == "paused"  # AI replies are Pro
    assert statuses[on_second] == "paused"  # its account is read-only on Free
    assert [statuses[a] for a in kept] == ["paused", "active", "active", "active"]
    assert await all_rows(
        owner.engine, "SELECT 1 FROM social_accounts WHERE workspace_id = :w", owner.wid
    )  # nothing deleted
    [(_, body)] = [n for n in await owner.notifications() if n[0] == "plan_downgraded"]
    assert body == (
        "2 accounts switched from Auto to Suggest. 3 automations paused. "
        "1 account can no longer send."
    )
    billing = await owner.billing()
    assert next(m for m in billing["usage"] if m["metric"] == "ai_credits")["limit"] == 200


async def test_an_ended_plan_ignores_later_holds_and_cancels(owner: Owner) -> None:
    await make_pro(owner)
    await owner.event(
        "subscription.expired", subscription(owner.wid, status="expired"), at=ago(minutes=10)
    )
    for event_type in ("subscription.on_hold", "subscription.cancelled", "subscription.updated"):
        row = await owner.event(event_type, subscription(owner.wid, status="on_hold"))
        assert (row["status"], row["last_error"]) == ("ignored", "the plan has already ended")
    assert ((await owner.sub())["plan"], (await owner.sub())["status"]) == ("free", "expired")


# ---------------------------------------------------------------- payments


async def test_payment_events_record_payments_without_changing_the_plan(owner: Owner) -> None:
    await make_pro(owner)
    await owner.event("payment.processing", payment(owner.wid, payment_id="pay_1"))
    await owner.event("payment.succeeded", payment(owner.wid, payment_id="pay_1"))
    late = await owner.event("payment.processing", payment(owner.wid, payment_id="pay_1"))
    await owner.event(
        "payment.failed",
        payment(owner.wid, payment_id="pay_2", status="failed", error_message="Card declined"),
    )
    await owner.event(
        "payment.cancelled", payment(owner.wid, payment_id="pay_3", status="cancelled")
    )

    assert late["status"] == "ignored"  # a late "processing" can't undo "succeeded"
    rows = {
        r["dodo_payment_id"]: r
        for r in await all_rows(
            owner.engine, "SELECT * FROM payments WHERE workspace_id = :w", owner.wid
        )
    }
    assert {k: v["status"] for k, v in rows.items()} == {
        "pay_1": "succeeded",
        "pay_2": "failed",
        "pay_3": "failed",
    }
    assert rows["pay_1"]["invoice_url"].startswith("https://test.dodopayments.com/invoices/")
    assert (rows["pay_1"]["amount_minor"], rows["pay_1"]["currency"]) == (1000, "USD")
    assert rows["pay_2"]["failure_reason"] == "Card declined"
    assert ((await owner.sub())["plan"], (await owner.sub())["status"]) == ("pro", "active")
    assert [t for t, _ in await owner.notifications()].count("payment_problem") == 1


async def test_a_failed_payment_and_the_hold_it_causes_notify_once(owner: Owner) -> None:
    await make_pro(owner)
    await owner.event("payment.failed", payment(owner.wid, status="failed"), at=ago(minutes=5))
    await owner.event("subscription.on_hold", subscription(owner.wid, status="on_hold"))
    assert [t for t, _ in await owner.notifications()].count("payment_problem") == 1


@pytest.mark.parametrize(
    "event_type", ["refund.succeeded", "dispute.opened", "license_key.created"]
)
async def test_refunds_disputes_and_other_events_are_logged_and_ignored(
    owner: Owner, event_type: str
) -> None:
    await make_pro(owner)
    row = await owner.event(event_type, payment(owner.wid))
    assert row["status"] == "ignored"
    assert ((await owner.sub())["plan"], (await owner.sub())["status"]) == ("pro", "active")


# ---------------------------------------------------------------- ordering, replays, signatures


async def test_an_event_older_than_the_last_one_applied_is_ignored(owner: Owner) -> None:
    await make_pro(owner)
    await owner.event(
        "subscription.expired", subscription(owner.wid, status="expired"), at=ago(minutes=5)
    )
    late = await owner.event("subscription.renewed", subscription(owner.wid), at=ago(minutes=20))

    assert (late["status"], late["last_error"]) == (
        "ignored",
        "out of order: older than the last event applied",
    )
    assert ((await owner.sub())["plan"], (await owner.sub())["status"]) == ("free", "expired")


async def test_a_replayed_delivery_is_stored_and_applied_once(owner: Owner) -> None:
    data = subscription(owner.wid)
    await deliver(owner.client, "subscription.active", data, msg_id="msg_replay")
    await deliver(owner.client, "subscription.active", data, msg_id="msg_replay")  # Dodo retries
    assert await process_all(owner.app, owner.engine) == ["processed"]
    assert await process_all(owner.app, owner.engine) == []
    async with owner.engine.connect() as conn:
        stored = await conn.scalar(text("SELECT count(*) FROM webhook_events"))
    assert stored == 1

    # The same event again under a new id changes nothing and notifies no one twice.
    before = await owner.sub()
    again = await owner.event("subscription.active", data)
    assert again["status"] == "processed"
    after = await owner.sub()
    assert {k: after[k] for k in ("plan", "status", "current_period_end")} == {
        k: before[k] for k in ("plan", "status", "current_period_end")
    }
    assert [t for t, _ in await owner.notifications()] == ["plan_activated"]


async def test_an_unsigned_event_is_refused_and_grants_nothing(owner: Owner) -> None:
    payload = dodo_event("subscription.active", subscription(owner.wid))
    raw = json.dumps(payload).encode()
    unsigned = await owner.client.post(
        "/webhooks/dodo", content=raw, headers={"content-type": "application/json"}
    )
    forged = await owner.client.post(
        "/webhooks/dodo",
        content=raw,
        headers=signed_headers(raw, secret=FORGED_SECRET),
    )
    assert (unsigned.status_code, forged.status_code) == (401, 401)
    assert await process_all(owner.app, owner.engine) == []
    assert ((await owner.sub())["plan"], (await owner.sub())["status"]) == ("free", "free")


# ---------------------------------------------------------------- routing


async def test_an_event_without_metadata_routes_by_the_stored_subscription(owner: Owner) -> None:
    await make_pro(owner)
    row = await owner.event("subscription.on_hold", subscription(None, status="on_hold"))
    assert (row["status"], str(row["workspace_id"])) == ("processed", owner.wid)


async def test_an_event_for_no_known_workspace_is_ignored(owner: Owner) -> None:
    row = await owner.event(
        "subscription.active", subscription(str(uuid.uuid4()), subscription_id="sub_x")
    )
    assert (row["status"], row["last_error"]) == ("ignored", "no workspace for this event")


async def test_a_second_subscription_cannot_replace_a_live_one(owner: Owner) -> None:
    await make_pro(owner)
    row = await owner.event(
        "subscription.active", subscription(owner.wid, subscription_id="sub_other")
    )
    assert row["status"] == "ignored"
    assert (await owner.sub())["dodo_subscription_id"] == "sub_test_1"
    other = await owner.event(
        "subscription.expired", subscription(owner.wid, subscription_id="sub_other")
    )
    assert (other["status"], other["last_error"]) == ("ignored", "not the workspace's subscription")


# ---------------------------------------------------------------- no Pro without a signed event


async def test_no_path_but_a_signed_event_grants_pro(
    owner: Owner, fake_dodo: FakeDodo, engine: AsyncEngine
) -> None:
    """Checkout, its return, cancel/resume and the reconcile job never make a Free workspace
    paid, even when Dodo has an active subscription for it."""
    headers = owner.clerk.headers(owner.clerk_id)
    base = f"/v1/w/{owner.wid}"
    checkout = await owner.client.post(
        f"{base}/billing/checkout", json={"plan": "pro"}, headers=headers
    )
    assert checkout.status_code == 200, checkout.text
    assert (await owner.billing())["plan"] == "free"  # the return page only reads this
    for action in ("cancel", "resume"):
        assert (
            await owner.client.post(f"{base}/billing/{action}", headers=headers)
        ).status_code == 409

    fake_dodo.add_subscription("sub_test_1", product_id="pdt_test_pro_monthly", status="active")
    await set_subscription(engine, workspace_id=owner.wid, dodo_subscription_id="sub_test_1")
    from socialhood.jobs.tasks.billing import reconcile_all

    counts = await reconcile_all(owner.app.state.sessionmaker, fake_dodo)
    assert counts["checked"] == 0  # only paid subscriptions are reconciled
    assert ((await owner.sub())["plan"], (await owner.sub())["status"]) == ("free", "free")
