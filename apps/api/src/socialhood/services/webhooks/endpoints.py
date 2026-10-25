"""A workspace's webhook endpoints (GR-04): add, change, pause, delete, rotate the secret, send a
test event, the delivery log and replays. Owners and admins; nothing here commits.

- An endpoint's address is https (a local one is allowed only where WEBHOOKS_ALLOW_PRIVATE is on:
  development and e2e), without a user name or password, and not a private address. Where it
  resolves is checked at every delivery (security/ssrf.py).
- Its signing secret ("whsec_" and a base64 key) is shown once, when it's made or rotated, and
  stored encrypted. Rotating replaces it at once.
- The plan caps the number of endpoints (``webhook_endpoints``); the REST hooks a Zapier trigger
  subscribes (services/api_hooks.py) are endpoints too and don't count.
- A replay sends the same event (same ``webhook-id``) again as a new delivery; the endpoint must
  be on.
"""

from __future__ import annotations

import base64
import json
import secrets
import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from socialhood.billing.entitlements import quota_error
from socialhood.billing.plans import current_plan, entitlement
from socialhood.errors import ApiError, FieldError
from socialhood.models.integrations import (
    DeliveryStatus,
    EndpointStatus,
    WebhookDelivery,
    WebhookEndpoint,
)
from socialhood.schemas.integrations import WebhookDelivery as DeliveryOut
from socialhood.schemas.integrations import (
    WebhookDeliveryList,
    WebhookEndpointCreate,
    WebhookEndpointList,
    WebhookEndpointPatch,
    WebhookEventType,
    WebhookEventTypeList,
)
from socialhood.schemas.integrations import WebhookEndpoint as EndpointOut
from socialhood.security import ssrf
from socialhood.security.crypto import TokenCipher
from socialhood.services.webhooks import events

HTTPS_ONLY = "Use an address that starts with https://."
TEST_MESSAGE = "A test event from Amplychat. Your endpoint is set up."


def catalogue() -> WebhookEventTypeList:
    return WebhookEventTypeList(
        items=[
            WebhookEventType(
                type=e.name,
                version=e.version,
                description=e.description,
                emitted=e.emitted,
            )
            for e in events.EVENTS
        ]
    )


def new_secret() -> str:
    return "whsec_" + base64.b64encode(secrets.token_bytes(24)).decode()


def endpoint_out(endpoint: WebhookEndpoint) -> EndpointOut:
    return EndpointOut.model_validate(endpoint)


def _url(raw: str, *, allow_private: bool) -> str:
    try:
        url = ssrf.check_url(raw)
    except ssrf.FetchError as error:
        if allow_private and error.code == "blocked":
            return raw.strip()
        raise ApiError("validation_error", errors=[FieldError("url", error.message)]) from error
    if url.scheme != "https" and not allow_private:
        raise ApiError("validation_error", errors=[FieldError("url", HTTPS_ONLY)])
    return str(url)


async def _get(
    session: AsyncSession, endpoint_id: uuid.UUID, *, lock: bool = False
) -> WebhookEndpoint:
    endpoint = await session.get(WebhookEndpoint, endpoint_id, with_for_update=lock)
    if endpoint is None:
        raise ApiError("not_found")
    return endpoint


async def list_endpoints(session: AsyncSession) -> WebhookEndpointList:
    rows = await session.scalars(select(WebhookEndpoint).order_by(WebhookEndpoint.created_at))
    limit = entitlement(await current_plan(session), "webhook_endpoints")
    return WebhookEndpointList(items=[endpoint_out(e) for e in rows.all()], limit=limit)


async def get(session: AsyncSession, endpoint_id: uuid.UUID) -> EndpointOut:
    return endpoint_out(await _get(session, endpoint_id))


async def create(
    session: AsyncSession,
    body: WebhookEndpointCreate,
    *,
    cipher: TokenCipher,
    user_id: uuid.UUID | None,
    allow_private: bool,
) -> tuple[WebhookEndpoint, str]:
    url = _url(body.url, allow_private=allow_private)
    limit = entitlement(await current_plan(session), "webhook_endpoints")
    if limit is not None:
        count = await session.scalar(  # a Zapier REST hook (GR-26) takes no slot
            select(func.count())
            .select_from(WebhookEndpoint)
            .where(WebhookEndpoint.api_key_id.is_(None))
        )
        if (count or 0) >= limit:
            raise quota_error("webhook_endpoints", limit)
    secret = new_secret()
    endpoint = WebhookEndpoint(
        url=url,
        description=body.description or None,
        events=list(dict.fromkeys(body.events)),
        status=EndpointStatus.ACTIVE,
        secret_enc=cipher.encrypt(secret),
        failing_deliveries=0,
        created_by_user_id=user_id,
    )
    session.add(endpoint)
    await session.flush()
    await session.refresh(endpoint)
    return endpoint, secret


async def update(
    session: AsyncSession,
    endpoint_id: uuid.UUID,
    body: WebhookEndpointPatch,
    *,
    allow_private: bool,
    now: datetime,
) -> WebhookEndpoint:
    endpoint = await _get(session, endpoint_id, lock=True)
    if body.url is not None:
        endpoint.url = _url(body.url, allow_private=allow_private)
    if "description" in body.model_fields_set:
        endpoint.description = body.description or None
    if body.events is not None:
        endpoint.events = list(dict.fromkeys(body.events))
    if body.status == "active" and endpoint.status != EndpointStatus.ACTIVE:
        endpoint.status = EndpointStatus.ACTIVE
        endpoint.failing_deliveries = 0
        endpoint.disabled_at = None
    elif body.status == "paused":
        endpoint.status = EndpointStatus.PAUSED
    await session.flush()
    await session.refresh(endpoint)
    return endpoint


async def delete(session: AsyncSession, endpoint_id: uuid.UUID) -> None:
    await session.delete(await _get(session, endpoint_id))
    await session.flush()


async def rotate(
    session: AsyncSession, endpoint_id: uuid.UUID, *, cipher: TokenCipher
) -> tuple[WebhookEndpoint, str]:
    endpoint = await _get(session, endpoint_id, lock=True)
    secret = new_secret()
    endpoint.secret_enc = cipher.encrypt(secret)
    await session.flush()
    return endpoint, secret


def _must_be_on(endpoint: WebhookEndpoint) -> None:
    if endpoint.status != EndpointStatus.ACTIVE:
        raise ApiError("conflict", "Turn the endpoint on first.")


async def _queue(
    session: AsyncSession,
    endpoint: WebhookEndpoint,
    *,
    event_type: str,
    payload: dict[str, object],
    now: datetime,
    event_id: uuid.UUID | None = None,
    replay_of: uuid.UUID | None = None,
) -> WebhookDelivery:
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        event_id=event_id or uuid.UUID(str(payload["id"])),
        event_type=event_type,
        payload=payload,
        status=DeliveryStatus.PENDING,
        attempts=0,
        next_attempt_at=now,
        replay_of_id=replay_of,
    )
    session.add(delivery)
    await session.flush()
    await events.enqueue_delivery(delivery.id)
    await session.refresh(delivery)
    return delivery


async def send_test(session: AsyncSession, endpoint_id: uuid.UUID, *, now: datetime) -> DeliveryOut:
    endpoint = await _get(session, endpoint_id)
    _must_be_on(endpoint)
    payload = events.envelope(events.TEST_EVENT, {"message": TEST_MESSAGE}, now=now)
    delivery = await _queue(
        session, endpoint, event_type=events.TEST_EVENT, payload=payload, now=now
    )
    return DeliveryOut.model_validate(delivery)


async def replay(session: AsyncSession, delivery_id: uuid.UUID, *, now: datetime) -> DeliveryOut:
    original = await session.get(WebhookDelivery, delivery_id)
    if original is None:
        raise ApiError("not_found")
    endpoint = await _get(session, original.endpoint_id)
    _must_be_on(endpoint)
    delivery = await _queue(
        session,
        endpoint,
        event_type=original.event_type,
        payload=dict(original.payload),
        now=now,
        event_id=original.event_id,  # the same webhook-id: the receiver's idempotency key
        replay_of=original.id,
    )
    return DeliveryOut.model_validate(delivery)


def _encode(at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps([at.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at, row_id = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        return datetime.fromisoformat(at), uuid.UUID(row_id)
    except (ValueError, TypeError) as error:
        raise ApiError("bad_request", "That page link isn't valid any more.") from error


async def deliveries(
    session: AsyncSession,
    endpoint_id: uuid.UUID,
    *,
    status: str | None,
    cursor: str | None,
    limit: int,
) -> WebhookDeliveryList:
    """The endpoint's deliveries, newest first."""
    await _get(session, endpoint_id)
    query = select(WebhookDelivery).where(WebhookDelivery.endpoint_id == endpoint_id)
    if status:
        query = query.where(WebhookDelivery.status == status)
    if cursor:
        at, row_id = _decode(cursor)
        query = query.where(
            or_(
                WebhookDelivery.created_at < at,
                and_(WebhookDelivery.created_at == at, WebhookDelivery.id < row_id),
            )
        )
    rows = list(
        (
            await session.scalars(
                query.order_by(WebhookDelivery.created_at.desc(), WebhookDelivery.id.desc()).limit(
                    limit + 1
                )
            )
        ).all()
    )
    more = len(rows) > limit
    rows = rows[:limit]
    return WebhookDeliveryList(
        items=[DeliveryOut.model_validate(r) for r in rows],
        next_cursor=_encode(rows[-1].created_at, rows[-1].id) if more and rows else None,
    )
