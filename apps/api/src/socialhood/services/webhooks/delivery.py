"""Delivering outbound webhooks (GR-04): the deliver_webhook job.

Each attempt signs the event (Standard Webhooks: ``webhook-id`` is the event id, the same on every
attempt and replay; ``webhook-timestamp``; ``webhook-signature`` as ``v1,<base64 HMAC-SHA256>`` of
``{id}.{timestamp}.{body}`` with the endpoint's secret) and posts it under the SSRF rules
(security/ssrf.post_json), outside any transaction. Then, with the delivery locked:

- a 2xx response delivers it, and the endpoint's failing count starts again;
- anything else (another status, a timeout, no connection, a refused address) is a failed attempt,
  kept with its status code, duration and reason. It's tried again after 1 minute, 5 minutes,
  30 minutes, 2 hours, 6 hours and 12 hours: 7 attempts over about 21 hours;
- a delivery whose attempts run out is ``failed``, and counts against its endpoint: after 5 such
  deliveries in a row with no success between, the endpoint is disabled and the owners and admins
  are told. Turning it back on starts the count again.

A delivery whose endpoint was deleted, paused or disabled fails at once without a request.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from socialhood.models.integrations import (
    DeliveryStatus,
    EndpointStatus,
    WebhookDelivery,
    WebhookEndpoint,
)
from socialhood.observability.logging import get_logger
from socialhood.security import ssrf
from socialhood.security.crypto import TokenCipher
from socialhood.security.signatures import sign_standard_webhook
from socialhood.services.webhooks import events

log = get_logger(__name__)

BACKOFF_S = (60, 300, 1800, 7200, 21600, 43200)
MAX_ATTEMPTS = len(BACKOFF_S) + 1
DISABLE_AFTER = 5  # deliveries in a row that ran out of attempts
TIMEOUT_S = 10.0
NOT_FOUND_RETRIES = 5
ENDPOINT_OFF = "The endpoint was turned off before this was sent."

Post = Callable[..., Awaitable[ssrf.Posted]]


@dataclass(frozen=True)
class Signed:
    url: str
    body: bytes
    headers: dict[str, str]


def body_of(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()


def sign(
    event_id: uuid.UUID, payload: dict[str, object], secret: str, now: datetime
) -> tuple[bytes, dict[str, str]]:
    body = body_of(payload)
    return body, {
        "webhook-id": str(event_id),
        "webhook-timestamp": str(int(now.timestamp())),
        "webhook-signature": sign_standard_webhook(str(event_id), now, body, secret),
    }


def backoff(attempts: int) -> timedelta | None:
    """The wait before the next attempt after ``attempts`` failed ones; None when they're over."""
    if attempts >= MAX_ATTEMPTS:
        return None
    return timedelta(seconds=BACKOFF_S[attempts - 1])


Outcome = Literal["missing", "done", "delivered", "retrying", "failed"]


async def deliver(
    sessionmaker: async_sessionmaker[AsyncSession],
    cipher: TokenCipher,
    *,
    delivery_id: uuid.UUID,
    now: datetime,
    allow_private: bool = False,
    post: Post = ssrf.post_json,
) -> Outcome:
    async with sessionmaker() as session:
        delivery = await session.get(WebhookDelivery, delivery_id)
        if delivery is None:
            return "missing"
        if delivery.status != DeliveryStatus.PENDING:
            return "done"
        endpoint = await session.get(WebhookEndpoint, delivery.endpoint_id)
        if endpoint is None or endpoint.status != EndpointStatus.ACTIVE:
            delivery.status = DeliveryStatus.FAILED
            delivery.error = ENDPOINT_OFF
            delivery.next_attempt_at = None
            await session.commit()
            return "failed"
        body, headers = sign(
            delivery.event_id, delivery.payload, cipher.decrypt(endpoint.secret_enc), now
        )
        url = endpoint.url

    code: int | None = None
    duration: int | None = None
    error: str | None = None
    try:
        posted = await post(url, body, headers, timeout_s=TIMEOUT_S, allow_private=allow_private)
        code, duration = posted.status, posted.duration_ms
        if not 200 <= code < 300:
            error = f"The endpoint answered {code}."
    except ssrf.FetchError as failure:
        error = failure.message

    async with sessionmaker() as session:
        delivery = await session.get(WebhookDelivery, delivery_id, with_for_update=True)
        if delivery is None or delivery.status != DeliveryStatus.PENDING:
            return "done"
        endpoint = await session.get(WebhookEndpoint, delivery.endpoint_id, with_for_update=True)
        delivery.attempts += 1
        delivery.last_attempt_at = now
        delivery.response_code, delivery.duration_ms, delivery.error = code, duration, error
        outcome: Outcome
        if error is None:
            delivery.status = DeliveryStatus.SUCCEEDED
            delivery.next_attempt_at = None
            if endpoint is not None:
                endpoint.failing_deliveries = 0
                endpoint.last_success_at = now
            outcome = "delivered"
        elif (wait := backoff(delivery.attempts)) is not None:
            delivery.next_attempt_at = now + wait
            await events.enqueue_delivery(delivery.id, delay_s=wait.total_seconds())
            outcome = "retrying"
        else:
            delivery.status = DeliveryStatus.FAILED
            delivery.next_attempt_at = None
            if endpoint is not None:
                await _count_failure(session, endpoint, now)
            outcome = "failed"
        await session.commit()
    log.info(
        "webhook_delivery",
        delivery_id=str(delivery_id),
        outcome=outcome,
        http_status=code,
        attempts=delivery.attempts,
    )
    return outcome


async def _count_failure(session: AsyncSession, endpoint: WebhookEndpoint, now: datetime) -> None:
    from socialhood.services.notifications import notify_admins

    endpoint.failing_deliveries += 1
    endpoint.last_failure_at = now
    if endpoint.failing_deliveries < DISABLE_AFTER or endpoint.status != EndpointStatus.ACTIVE:
        return
    endpoint.status = EndpointStatus.DISABLED
    endpoint.disabled_at = now
    await notify_admins(
        session,
        type="webhook_disabled",
        severity="warning",
        title="A webhook endpoint was turned off",
        body=(
            f"{endpoint.description or endpoint.url} failed {DISABLE_AFTER} deliveries in a row. "
            "Check it, then turn it back on in Settings, under Integrations."
        ),
        link="/settings/integrations",
        dedupe_key=f"webhook_disabled:{endpoint.id}:{now.date().isoformat()}",
    )


async def pending_ids(session: AsyncSession, endpoint_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(WebhookDelivery.id).where(
            WebhookDelivery.endpoint_id == endpoint_id,
            WebhookDelivery.status == DeliveryStatus.PENDING,
        )
    )
    return list(rows.all())
