"""deliver_webhook(delivery_id) (GR-04): one attempt at an outbound webhook. Thin: the work is in
services/webhooks/delivery.py, which schedules the next attempt itself, so the job never retries
on its own. A delivery not visible yet (its transaction hasn't committed) is looked for again a few
times."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.runtime import runtime
from socialhood.security.crypto import cipher_for
from socialhood.services.webhooks import delivery, events


@app.task(name="deliver_webhook", queue=BULK)
async def deliver_webhook(workspace_id: str, delivery_id: str, not_found: int = 0) -> None:
    rt = runtime()
    wid, did = uuid.UUID(workspace_id), uuid.UUID(delivery_id)
    with workspace_scope(wid):
        outcome = await delivery.deliver(
            rt.sessionmaker,
            cipher_for(tuple(rt.settings.token_encryption_keys)),
            delivery_id=did,
            now=datetime.now(UTC),
            allow_private=rt.settings.webhooks_allow_private,
        )
        if outcome == "missing" and not_found < delivery.NOT_FOUND_RETRIES:
            await events.enqueue_delivery(
                did, delay_s=float(not_found + 1), not_found=not_found + 1
            )
