"""Cancelling a Dodo subscription whose workspace is gone (C-060).

A checkout paid after its workspace was deleted creates a live subscription that no workspace
will ever own: routing ignores it (webhooks/dodo_routing.py), so without this it would bill until
someone noticed. The Dodo webhook handler raises an alert and queues the
``cancel_orphan_subscription`` job (jobs/tasks/billing.py), which calls ``cancel_orphan``.
"""

from __future__ import annotations

from socialhood.billing.dodo import DodoClient, DodoError
from socialhood.observability.logging import get_logger

log = get_logger(__name__)


async def cancel_orphan(dodo: DodoClient, subscription_id: str) -> bool:
    """Cancel the subscription now (not at the period end). True when Dodo cancelled it; False
    when Dodo no longer has it or refuses because it already ended, which counts as done. A
    timeout, 429 or 5xx raises the DodoError, so the job tries again; so does Dodo not being
    configured, which fails the job for good (Sentry reports it)."""
    try:
        cancelled = await dodo.cancel_now(subscription_id)
    except DodoError as error:
        if error.retryable or error.status is None:
            log.warning(
                "billing_orphan_cancel_retry", subscription_id=subscription_id, status=error.status
            )
            raise
        log.info(
            "billing_orphan_nothing_to_cancel", subscription_id=subscription_id, status=error.status
        )
        return False
    log.warning(
        "billing_orphan_cancelled", subscription_id=subscription_id, status=cancelled.status
    )
    return True
