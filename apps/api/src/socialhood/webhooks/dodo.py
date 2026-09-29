"""POST /webhooks/dodo (TR-BIL-02, TR-WH-01…03, SEC-04).

Fails closed: 503 without DODO_WEBHOOK_SECRET (production refuses to start without it), 401
unless the Standard Webhooks signature over the raw body verifies (security/signatures.py). A
verified event is stored once (dedupe ``dodo:{webhook-id}``) with Dodo's event time as
``occurred_at``, processing is enqueued, and the answer is 200. Nothing is applied inside the
request: services/webhook_handlers/dodo.py does that in the job (T8.3), so only a signed event can
ever change a plan.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request, Response

from socialhood.auth.deps import Session
from socialhood.errors import ApiError
from socialhood.jobs.enqueue import enqueue
from socialhood.jobs.tasks.webhooks import process_webhook_event
from socialhood.models.platform import WebhookProvider
from socialhood.observability.logging import get_logger
from socialhood.repositories import webhook_events
from socialhood.security.signatures import verify_standard_webhook
from socialhood.settings import Settings

router = APIRouter(prefix="/webhooks", include_in_schema=False)
log = get_logger(__name__)


def event_time(payload: dict[str, Any]) -> datetime | None:
    """Dodo's ``timestamp`` (ISO 8601): when the event happened, for ordering (TR-BIL-02)."""
    value = payload.get("timestamp")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


@router.post("/dodo")
async def dodo_webhook(request: Request, session: Session) -> Response:
    settings: Settings = request.app.state.settings
    configured = settings.dodo_webhook_secret
    if configured is None or not configured.get_secret_value():
        raise ApiError("service_unavailable", "Dodo webhooks are not configured.")

    raw = await request.body()
    if not verify_standard_webhook(raw, request.headers, configured.get_secret_value()):
        log.warning("webhook_signature_invalid", provider="dodo")
        raise ApiError("unauthorized")
    try:
        payload: Any = json.loads(raw)
    except ValueError as error:
        raise ApiError("bad_request") from error
    if not isinstance(payload, dict):
        raise ApiError("bad_request")

    event_id = await webhook_events.store(
        session,
        provider=WebhookProvider.DODO,
        dedupe_key=f"dodo:{request.headers['webhook-id']}",
        event_type=str(payload.get("type", "unknown")),
        payload=payload,
        occurred_at=event_time(payload),
    )
    await session.commit()
    if event_id is not None:
        await enqueue(process_webhook_event, key=f"wh:{event_id}", webhook_event_id=str(event_id))
    return Response(status_code=200)
