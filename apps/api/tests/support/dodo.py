"""Dodo webhook deliveries built from the recorded test-mode objects (tests/fixtures/dodo/), and
the processing step the worker runs (P8, T8.3). Signing and posting are tests/support/billing.py's.

Every builder starts from a real Subscription or Payment object and changes only what the test
names, so the handler always reads Dodo's real shape."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from socialhood.models.platform import WebhookStatus
from socialhood.services.webhook_processing import process_event
from tests.support.billing import PRO_PRODUCT, dodo_event, post_dodo_event

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "dodo"


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


def iso(at: datetime) -> str:
    return at.astimezone(UTC).isoformat().replace("+00:00", "Z")


def subscription(
    workspace_id: uuid.UUID | str | None,
    *,
    subscription_id: str = "sub_test_1",
    product_id: str = PRO_PRODUCT,
    status: str = "active",
    created_at: datetime | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    trial_period_days: int = 0,
    cancel_at_next_billing_date: bool = False,
    customer_id: str = "cus_test_1",
    **values: Any,
) -> dict[str, Any]:
    """A subscription.* event's data: the recorded Subscription object with these values."""
    now = datetime.now(UTC)
    start = period_start or now - timedelta(minutes=1)
    data = fixture("subscription_active.json")
    data.update(
        {
            "payload_type": "Subscription",
            "subscription_id": subscription_id,
            "product_id": product_id,
            "status": status,
            "created_at": iso(created_at or start),
            "previous_billing_date": iso(start),
            "next_billing_date": iso(period_end or start + timedelta(days=30)),
            "trial_period_days": trial_period_days,
            "cancel_at_next_billing_date": cancel_at_next_billing_date,
            "metadata": {"workspace_id": str(workspace_id)} if workspace_id else {},
        }
    )
    data["customer"] = {**data["customer"], "customer_id": customer_id}
    data.update(values)
    return data


def payment(
    workspace_id: uuid.UUID | str | None,
    *,
    payment_id: str = "pay_test_1",
    subscription_id: str = "sub_test_1",
    status: str = "succeeded",
    total_amount: int = 1000,
    currency: str = "USD",
    **values: Any,
) -> dict[str, Any]:
    """A payment.* event's data: the recorded Payment object with these values."""
    data = fixture("payment_succeeded.json")
    data.update(
        {
            "payload_type": "Payment",
            "payment_id": payment_id,
            "subscription_id": subscription_id,
            "subscription_ids": [subscription_id],
            "status": status,
            "total_amount": total_amount,
            "currency": currency,
            "created_at": iso(datetime.now(UTC)),
            "metadata": {"workspace_id": str(workspace_id)} if workspace_id else {},
        }
    )
    data.update(values)
    return data


async def deliver(
    client: httpx.AsyncClient,
    event_type: str,
    data: dict[str, Any],
    *,
    at: datetime | None = None,
    msg_id: str | None = None,
) -> httpx.Response:
    """POST a signed delivery of ``event_type`` that happened ``at`` (now by default)."""
    response = await post_dodo_event(
        client, dodo_event(event_type, data, timestamp=at), msg_id=msg_id
    )
    assert response.status_code == 200, response.text
    return response


async def process_all(app: FastAPI, engine: AsyncEngine) -> list[WebhookStatus | None]:
    """Run process_webhook_event for every stored event still waiting, oldest delivery first
    (what the worker does)."""
    async with engine.connect() as conn:
        ids = (
            await conn.execute(
                text(
                    "SELECT id FROM webhook_events WHERE provider = 'dodo' AND status = 'received'"
                    " ORDER BY received_at, id"
                )
            )
        ).scalars()
        pending = list(ids)
    return [
        await process_event(app.state.sessionmaker, event_id, app.state.redis)
        for event_id in pending
    ]


async def send(
    app: FastAPI,
    client: httpx.AsyncClient,
    engine: AsyncEngine,
    event_type: str,
    data: dict[str, Any],
    *,
    at: datetime | None = None,
) -> dict[str, Any]:
    """Deliver one event, process it, and return its stored row (status, last_error)."""
    msg_id = f"msg_{uuid.uuid4().hex}"
    await deliver(client, event_type, data, at=at, msg_id=msg_id)
    await process_all(app, engine)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT status, last_error, workspace_id FROM webhook_events"
                    " WHERE dedupe_key = :k"
                ),
                {"k": f"dodo:{msg_id}"},
            )
        ).one()
    return dict(row._mapping)
