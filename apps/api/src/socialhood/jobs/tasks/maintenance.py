"""Maintenance tasks. ``ping`` proves the periodic scheduler and both lanes work end to end."""

from __future__ import annotations

from socialhood.jobs.app import INTERACTIVE, app
from socialhood.observability.logging import get_logger

log = get_logger(__name__)


@app.periodic(cron="* * * * *", periodic_id="ping")
@app.task(name="ping", queue=INTERACTIVE, queueing_lock="ping")
async def ping(timestamp: int) -> None:
    log.info("ping", tick=timestamp)
