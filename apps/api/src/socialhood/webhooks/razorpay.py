"""POST /webhooks/razorpay/{token} (GR-32; TR-WH-01...03, SEC-04): payment link events from a
business's own Razorpay account.

The address is per workspace: ``token`` is random and only the workspace's payment card shows it.
Fails closed: an unknown token and a bad signature are both 401 (the answer doesn't say which),
and ``X-Razorpay-Signature`` must verify over the raw bytes with that workspace's webhook secret
(razorpay/signatures.py) before the body is read. A verified event is stored once (dedupe
``razorpay:{X-Razorpay-Event-Id}``), processing is enqueued, and the answer is 200. Nothing is
applied inside the request: services/webhook_handlers/razorpay.py does that in the job, so only a
signed event can mark an order paid. Razorpay re-sends a webhook that wasn't answered with a 2xx,
which the dedupe key absorbs.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from fastapi import APIRouter, Request, Response

from socialhood.auth.deps import Session
from socialhood.errors import ApiError
from socialhood.observability.logging import get_logger
from socialhood.platforms.events import RawEvent
from socialhood.razorpay.signatures import verify_webhook
from socialhood.security.crypto import cipher_for
from socialhood.services.webhook_intake import record_delivery, store_and_enqueue
from socialhood.webhooks.routing import razorpay_webhook_secret

router = APIRouter(prefix="/webhooks", include_in_schema=False)
log = get_logger(__name__)

TOKEN_MAX = 80
EVENT_MAX = 80


@router.post("/razorpay/{token}")
async def receive(token: str, request: Request, session: Session) -> Response:
    minute = int(time.time() // 60)
    raw = await request.body()
    secret_enc = await razorpay_webhook_secret(session, token[:TOKEN_MAX])
    secret = ""
    if secret_enc:
        cipher = cipher_for(tuple(request.app.state.settings.token_encryption_keys))
        try:
            secret = cipher.decrypt(secret_enc)
        except ValueError:
            log.warning("razorpay_secret_unreadable")
    if not verify_webhook(raw, request.headers.get("x-razorpay-signature"), secret):
        log.warning("webhook_signature_invalid", provider="razorpay")
        await record_delivery(request.app.state.redis, "razorpay", ok=False, minute=minute)
        raise ApiError("unauthorized")

    try:
        parsed: Any = json.loads(raw) if raw else {}
    except ValueError:
        parsed = None
    body = parsed if isinstance(parsed, dict) else {}
    name = str(body.get("event") or "unknown")[:EVENT_MAX]
    event_id = request.headers.get("x-razorpay-event-id") or hashlib.sha256(raw).hexdigest()
    event = RawEvent(
        f"razorpay:{event_id[:80]}",
        name if parsed is not None else "invalid",
        token[:TOKEN_MAX],
        {"event": name, "body": body},
    )
    await store_and_enqueue(session, "razorpay", [event])
    await record_delivery(request.app.state.redis, "razorpay", ok=True, minute=minute)
    return Response(status_code=200)
