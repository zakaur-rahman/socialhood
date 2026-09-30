"""POST /webhooks/clerk (TR-AUTH-04, TR-WH-01…03).

Verify the svix signature over the raw body, store the event once, enqueue processing, return
200. Nothing is processed inside the request.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request, Response
from svix.webhooks import Webhook

from socialhood.auth.deps import Session
from socialhood.errors import ApiError
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.tasks.webhooks import process_webhook_event
from socialhood.models.platform import WebhookProvider
from socialhood.observability.logging import get_logger
from socialhood.repositories import webhook_events
from socialhood.settings import Settings

router = APIRouter(prefix="/webhooks", include_in_schema=False)
log = get_logger(__name__)

SVIX_HEADERS = ("svix-id", "svix-timestamp", "svix-signature")


@router.post("/clerk")
async def clerk_webhook(request: Request, session: Session) -> Response:
    settings: Settings = request.app.state.settings
    configured = settings.clerk_webhook_secret
    if configured is None or not configured.get_secret_value():
        # Fail closed: without the secret nothing can be verified (production refuses to start).
        raise ApiError("service_unavailable", "Clerk webhooks are not configured.")

    raw = await request.body()
    headers = {name: request.headers.get(name, "") for name in SVIX_HEADERS}
    secret = configured.get_secret_value()
    try:
        Webhook(secret).verify(raw, headers)  # raises on a bad or missing signature
    except Exception as error:
        # WebhookVerificationError, and what svix lets through for a malformed signature
        # (binascii.Error for bad base64, ValueError without a comma): 401, never a 500.
        log.warning("webhook_signature_invalid", provider="clerk")
        raise ApiError("unauthorized") from error
    payload: Any = json.loads(raw)
    if not isinstance(payload, dict):
        raise ApiError("bad_request")

    event_id = await webhook_events.store(
        session,
        provider=WebhookProvider.CLERK,
        dedupe_key=f"clerk:{headers['svix-id']}",
        event_type=str(payload.get("type", "unknown")),
        payload=payload,
    )
    await session.commit()
    if event_id is not None:
        await enqueue(process_webhook_event, key=f"wh:{event_id}", webhook_event_id=str(event_id))
    return Response(status_code=200)
