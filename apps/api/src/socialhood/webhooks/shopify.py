"""POST /webhooks/shopify (GR-31; TR-WH-01…03, SEC-04): product and app events from a connected
Shopify store, and the privacy topics a listed app must answer.

Fails closed: 503 without SHOPIFY_API_SECRET, 401 unless ``X-Shopify-Hmac-Sha256`` verifies over
the raw bytes (security: shopify/signatures.py). A verified event is stored once (dedupe
``shopify:{X-Shopify-Webhook-Id}``) with its topic and store, processing is enqueued, and the
answer is 200. Nothing is applied inside the request: services/webhook_handlers/shopify.py does
that in the job, so only a signed event can change the catalogue. Shopify re-sends a webhook
that wasn't answered with a 2xx, which the dedupe key absorbs.
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
from socialhood.services.webhook_intake import record_delivery, store_and_enqueue
from socialhood.shopify.client import normalize_shop
from socialhood.shopify.registry import webhook_secret
from socialhood.shopify.signatures import verify_webhook

router = APIRouter(prefix="/webhooks", include_in_schema=False)
log = get_logger(__name__)

TOPIC_MAX = 80


@router.post("/shopify")
async def receive(request: Request, session: Session) -> Response:
    secret = webhook_secret(request.app.state.settings)
    if not secret:
        raise ApiError("service_unavailable", "Shopify webhooks are not configured.")
    minute = int(time.time() // 60)
    raw = await request.body()
    if not verify_webhook(raw, request.headers.get("x-shopify-hmac-sha256"), secret):
        log.warning("webhook_signature_invalid", provider="shopify")
        await record_delivery(request.app.state.redis, "shopify", ok=False, minute=minute)
        raise ApiError("unauthorized")

    topic = (request.headers.get("x-shopify-topic") or "unknown")[:TOPIC_MAX]
    shop = normalize_shop(request.headers.get("x-shopify-shop-domain") or "") or ""
    webhook_id = request.headers.get("x-shopify-webhook-id") or hashlib.sha256(raw).hexdigest()
    try:
        parsed: Any = json.loads(raw) if raw else {}
    except ValueError:
        parsed = None
    body = parsed if isinstance(parsed, dict) else {}
    event = RawEvent(
        f"shopify:{webhook_id[:80]}",
        topic if parsed is not None else "invalid",
        shop,
        {"topic": topic, "shop": shop, "body": body},
    )
    await store_and_enqueue(session, "shopify", [event])
    await record_delivery(request.app.state.redis, "shopify", ok=True, minute=minute)
    return Response(status_code=200)
