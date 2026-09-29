"""Billing test support (P8): every test runs with a FakeDodo (never Dodo); request ``fake_dodo``
to add subscriptions, queue failures or read the calls. Helpers sign Dodo webhook deliveries the
way Dodo does (Standard Webhooks), and factories write billing rows through the ORM in the
workspace's scope."""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from socialhood.billing.dodo_fake import FakeDodo
from socialhood.billing.registry import use_dodo
from socialhood.db.tenancy import workspace_scope
from socialhood.models.billing import Payment, Subscription
from socialhood.security.signatures import sign_standard_webhook

DODO_WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"socialhood-test-dodo-webhook-key").decode()
DODO_API_KEY = "fake-dodo-api-key-for-tests"
PRO_PRODUCT = "pdt_test_pro_monthly"
MAX_PRODUCT = "pdt_test_max_monthly"
PRO_PRICE_MINOR = 99900  # ₹999 (OQ-1 proposal)


@pytest.fixture(autouse=True)
def fake_dodo() -> Iterator[FakeDodo]:
    fake = FakeDodo()
    fake.add_product(PRO_PRODUCT, amount_minor=PRO_PRICE_MINOR, currency="INR")
    fake.add_product(MAX_PRODUCT, amount_minor=499900, currency="INR", trial_period_days=0)
    with use_dodo(fake):
        yield fake


def _wid(workspace_id: uuid.UUID | str) -> uuid.UUID:
    return uuid.UUID(str(workspace_id))


# ---------------------------------------------------------------- webhooks


def dodo_event(
    event_type: str,
    data: Mapping[str, Any],
    *,
    timestamp: datetime | None = None,
    business_id: str = "bus_test",
) -> dict[str, Any]:
    """A webhook body in Dodo's envelope: {business_id, type, timestamp, data}."""
    at = (timestamp or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
    return {"business_id": business_id, "type": event_type, "timestamp": at, "data": dict(data)}


def signed_headers(
    raw: bytes,
    *,
    msg_id: str | None = None,
    secret: str = DODO_WEBHOOK_SECRET,
    at: datetime | None = None,
) -> dict[str, str]:
    """webhook-id, webhook-timestamp and webhook-signature for ``raw``, signed now by default."""
    msg_id = msg_id or f"msg_{uuid.uuid4().hex}"
    at = at or datetime.now(UTC)
    return {
        "webhook-id": msg_id,
        "webhook-timestamp": str(int(at.timestamp())),
        "webhook-signature": sign_standard_webhook(msg_id, at, raw, secret),
        "content-type": "application/json",
    }


async def post_dodo_event(
    client: httpx.AsyncClient,
    payload: Mapping[str, Any],
    *,
    msg_id: str | None = None,
    secret: str = DODO_WEBHOOK_SECRET,
) -> httpx.Response:
    raw = json.dumps(payload).encode()
    headers = signed_headers(raw, msg_id=msg_id, secret=secret)
    return await client.post("/webhooks/dodo", content=raw, headers=headers)


# ---------------------------------------------------------------- rows


async def set_subscription(
    engine: AsyncEngine, *, workspace_id: uuid.UUID | str, **values: Any
) -> None:
    """Change the workspace's subscription row, e.g. plan="pro", status="active"."""
    with workspace_scope(_wid(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            sub = (await session.scalars(select(Subscription))).one()
            for name, value in values.items():
                setattr(sub, name, value)
            await session.commit()


async def make_payment(
    engine: AsyncEngine, *, workspace_id: uuid.UUID | str, **values: Any
) -> uuid.UUID:
    defaults: dict[str, Any] = {
        "dodo_payment_id": f"pay_{uuid.uuid4().hex[:16]}",
        "dodo_subscription_id": "sub_test",
        "status": "succeeded",
        "amount_minor": PRO_PRICE_MINOR,
        "currency": "INR",
        "occurred_at": datetime.now(UTC),
        "invoice_url": "https://invoices.dodo.invalid/pay_test",
    }
    with workspace_scope(_wid(workspace_id)):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = Payment(**{**defaults, **values})
            session.add(row)
            await session.commit()
            return row.id
