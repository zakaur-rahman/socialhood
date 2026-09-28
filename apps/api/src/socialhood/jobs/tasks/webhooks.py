"""process_webhook_event (TR-WH-05): thin task, the work is in services/webhook_processing."""

from __future__ import annotations

import uuid

from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.retry import BackoffRetry
from socialhood.jobs.runtime import runtime
from socialhood.repositories.webhook_events import MAX_ATTEMPTS
from socialhood.services.webhook_processing import process_event


@app.task(
    name="process_webhook_event",
    queue=INTERACTIVE,
    retry=BackoffRetry(max_attempts=MAX_ATTEMPTS),
)
async def process_webhook_event(webhook_event_id: str) -> None:
    await process_event(runtime().sessionmaker, uuid.UUID(webhook_event_id))
