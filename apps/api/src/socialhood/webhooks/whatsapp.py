"""GET/POST /webhooks/whatsapp (T3.12; TR-WH-01…04, SEC-04).

GET answers Meta's verification challenge with WHATSAPP_WEBHOOK_VERIFY_TOKEN. POST checks
X-Hub-Signature-256 over the raw bytes with META_APP_SECRET, splits the delivery into one event
per message and per status, stores each once, queues them and returns 200. Nothing is processed
inside the request, exactly as for Instagram.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import PlainTextResponse

from socialhood.auth.deps import Session
from socialhood.errors import ApiError
from socialhood.models.platform import WebhookProvider
from socialhood.observability.logging import get_logger
from socialhood.platforms.events import RawEvent
from socialhood.platforms.whatsapp.webhooks import split_payload
from socialhood.security.signatures import verify_hub_signature
from socialhood.services.webhook_intake import record_delivery, store_and_enqueue
from socialhood.settings import Settings

router = APIRouter(prefix="/webhooks", include_in_schema=False)
log = get_logger(__name__)


@router.get("/whatsapp")
async def verify_subscription(
    request: Request,
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    verify_token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> Response:
    settings: Settings = request.app.state.settings
    expected = (
        settings.whatsapp_webhook_verify_token.get_secret_value()
        if settings.whatsapp_webhook_verify_token
        else ""
    )
    if mode == "subscribe" and expected and hmac.compare_digest(expected, verify_token or ""):
        return PlainTextResponse(challenge or "")
    raise ApiError("forbidden")


@router.post("/whatsapp")
async def receive(request: Request, session: Session) -> Response:
    settings: Settings = request.app.state.settings
    secret = settings.meta_app_secret.get_secret_value() if settings.meta_app_secret else ""
    if not secret:
        raise ApiError("service_unavailable", "WhatsApp webhooks are not configured.")
    minute = int(time.time() // 60)
    raw = await request.body()
    if not verify_hub_signature(raw, request.headers.get("x-hub-signature-256"), secret):
        log.warning("webhook_signature_invalid", provider="whatsapp")
        await record_delivery(request.app.state.redis, "whatsapp", ok=False, minute=minute)
        raise ApiError("unauthorized")

    try:
        body = json.loads(raw)
    except ValueError:
        body = None
    if isinstance(body, dict):
        events = split_payload(body)
    else:
        # Signed but unreadable: keep it for inspection, acknowledge so Meta stops retrying.
        events = [
            RawEvent(
                f"wa:invalid:{hashlib.sha256(raw).hexdigest()[:32]}",
                "invalid",
                "",
                {"raw": raw.decode(errors="replace")[:65536]},
            )
        ]
    await store_and_enqueue(session, WebhookProvider.WHATSAPP, events)
    await record_delivery(request.app.state.redis, "whatsapp", ok=True, minute=minute)
    return Response(status_code=200)
