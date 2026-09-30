"""POST /webhooks/cloudinary (P7b; TR-MED-05, TR-WH-01…03, SEC-04): Cloudinary's notification
that an eager render finished (``notification_type: eager``) or failed.

Fails closed: 503 without the Cloudinary API secret (production refuses to start without it), 401
unless ``X-Cld-Signature`` verifies over the raw body and ``X-Cld-Timestamp`` is at most 2 hours
old (security/signatures.py). A verified notification is stored once (dedupe
``cloudinary:{sha256 of the body}``, so a redelivery is a no-op), processing is enqueued, and the
answer is 200. Nothing is applied inside the request: services/webhook_handlers/cloudinary.py
finishes the render in the job (TB.2). start_render asks for these notifications only when
API_BASE_URL is set; without them (local runs), poll_render finishes renders.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from fastapi import APIRouter, Request, Response

from socialhood.auth.deps import Session
from socialhood.errors import ApiError
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.tasks.webhooks import process_webhook_event
from socialhood.models.platform import WebhookProvider
from socialhood.observability.logging import get_logger
from socialhood.repositories import webhook_events
from socialhood.security.signatures import verify_cloudinary_notification
from socialhood.settings import Settings

router = APIRouter(prefix="/webhooks", include_in_schema=False)
log = get_logger(__name__)


@router.post("/cloudinary")
async def cloudinary_webhook(request: Request, session: Session) -> Response:
    settings: Settings = request.app.state.settings
    secret = settings.cloudinary_api_secret
    if secret is None or not secret.get_secret_value():
        raise ApiError("service_unavailable", "Cloudinary notifications are not configured.")

    raw = await request.body()
    if not verify_cloudinary_notification(
        raw, request.headers, secret.get_secret_value(), now=time.time()
    ):
        log.warning("webhook_signature_invalid", provider="cloudinary")
        raise ApiError("unauthorized")
    try:
        payload: Any = json.loads(raw)
    except ValueError as error:
        raise ApiError("bad_request") from error
    if not isinstance(payload, dict):
        raise ApiError("bad_request")

    event_id = await webhook_events.store(
        session,
        provider=WebhookProvider.CLOUDINARY,
        dedupe_key=f"cloudinary:{hashlib.sha256(raw).hexdigest()}",
        event_type=str(payload.get("notification_type", "unknown")),
        payload=payload,
    )
    await session.commit()
    if event_id is not None:
        await enqueue(process_webhook_event, key=f"wh:{event_id}", webhook_event_id=str(event_id))
    return Response(status_code=200)
