"""Outbound webhooks API (GR-04): the event catalogue, endpoints, test events, the delivery log and
replays. Owners and admins. The rules are in services/webhooks/."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response

from socialhood.auth.deps import Admin, Session
from socialhood.schemas.integrations import (
    DeliveryStatusName,
    WebhookDelivery,
    WebhookDeliveryList,
    WebhookEndpoint,
    WebhookEndpointCreate,
    WebhookEndpointList,
    WebhookEndpointPatch,
    WebhookEndpointWithSecret,
    WebhookEventTypeList,
)
from socialhood.security.crypto import TokenCipher, cipher_for
from socialhood.services.webhooks import endpoints as service
from socialhood.settings import get_settings

router = APIRouter(prefix="/v1/w/{wid}", tags=["integrations"])


def _cipher() -> TokenCipher:
    return cipher_for(tuple(get_settings().token_encryption_keys))


def _allow_private() -> bool:
    return get_settings().webhooks_allow_private


def _with_secret(endpoint: object, secret: str) -> WebhookEndpointWithSecret:
    out = service.endpoint_out(endpoint)  # type: ignore[arg-type]
    return WebhookEndpointWithSecret(**out.model_dump(), signing_secret=secret)


@router.get("/webhook-events", operation_id="list_webhook_events")
async def list_webhook_events(ctx: Admin) -> WebhookEventTypeList:
    """Every event an endpoint can subscribe to, with its payload version."""
    return service.catalogue()


@router.get("/webhook-endpoints", operation_id="list_webhook_endpoints")
async def list_webhook_endpoints(ctx: Admin, session: Session) -> WebhookEndpointList:
    return await service.list_endpoints(session)


@router.post("/webhook-endpoints", status_code=201, operation_id="create_webhook_endpoint")
async def create_webhook_endpoint(
    body: WebhookEndpointCreate, ctx: Admin, session: Session
) -> WebhookEndpointWithSecret:
    """Add an endpoint; its signing secret is in this response only."""
    endpoint, secret = await service.create(
        session, body, cipher=_cipher(), user_id=ctx.user.id, allow_private=_allow_private()
    )
    out = _with_secret(endpoint, secret)
    await session.commit()
    return out


@router.get("/webhook-endpoints/{endpoint_id}", operation_id="get_webhook_endpoint")
async def get_webhook_endpoint(
    endpoint_id: uuid.UUID, ctx: Admin, session: Session
) -> WebhookEndpoint:
    return await service.get(session, endpoint_id)


@router.patch("/webhook-endpoints/{endpoint_id}", operation_id="update_webhook_endpoint")
async def update_webhook_endpoint(
    endpoint_id: uuid.UUID, body: WebhookEndpointPatch, ctx: Admin, session: Session
) -> WebhookEndpoint:
    endpoint = await service.update(
        session, endpoint_id, body, allow_private=_allow_private(), now=datetime.now(UTC)
    )
    out = service.endpoint_out(endpoint)
    await session.commit()
    return out


@router.delete(
    "/webhook-endpoints/{endpoint_id}", status_code=204, operation_id="delete_webhook_endpoint"
)
async def delete_webhook_endpoint(endpoint_id: uuid.UUID, ctx: Admin, session: Session) -> Response:
    await service.delete(session, endpoint_id)
    await session.commit()
    return Response(status_code=204)


@router.post("/webhook-endpoints/{endpoint_id}/rotate-secret", operation_id="rotate_webhook_secret")
async def rotate_webhook_secret(
    endpoint_id: uuid.UUID, ctx: Admin, session: Session
) -> WebhookEndpointWithSecret:
    """A new signing secret, in this response only; the old one stops working at once."""
    endpoint, secret = await service.rotate(session, endpoint_id, cipher=_cipher())
    out = _with_secret(endpoint, secret)
    await session.commit()
    return out


@router.post(
    "/webhook-endpoints/{endpoint_id}/test",
    status_code=202,
    operation_id="send_webhook_test",
)
async def send_webhook_test(
    endpoint_id: uuid.UUID, ctx: Admin, session: Session
) -> WebhookDelivery:
    """Send a ``webhook.test`` event; its delivery shows in the log."""
    delivery = await service.send_test(session, endpoint_id, now=datetime.now(UTC))
    await session.commit()
    return delivery


@router.get("/webhook-endpoints/{endpoint_id}/deliveries", operation_id="list_webhook_deliveries")
async def list_webhook_deliveries(
    endpoint_id: uuid.UUID,
    ctx: Admin,
    session: Session,
    status: Annotated[DeliveryStatusName | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> WebhookDeliveryList:
    """The delivery log, newest first: each delivery's last attempt."""
    return await service.deliveries(session, endpoint_id, status=status, cursor=cursor, limit=limit)


@router.post(
    "/webhook-deliveries/{delivery_id}/replay",
    status_code=202,
    operation_id="replay_webhook_delivery",
)
async def replay_webhook_delivery(
    delivery_id: uuid.UUID, ctx: Admin, session: Session
) -> WebhookDelivery:
    """Send the same event again (the same webhook-id) as a new delivery."""
    delivery = await service.replay(session, delivery_id, now=datetime.now(UTC))
    await session.commit()
    return delivery
