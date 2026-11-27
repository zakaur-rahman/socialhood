"""sync_shopify_products(workspace_id) (GR-31): copy the connected Shopify store's products into the
catalogue (services/catalogue/shopify.py run_sync). Bulk lane, queueing lock
``shopify-sync:{workspace}`` so a second press of Sync while one waits adds nothing, 3 tries: a
Shopify error that can pass (rate limit, outage) is retried with backoff, and the last try records
it on the store's card instead."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from procrastinate import JobContext

from socialhood.db.tenancy import workspace_scope
from socialhood.jobs.app import BULK, app
from socialhood.jobs.fairness import BulkSemaphore, run_with_bulk_slot
from socialhood.jobs.retry import BackoffRetry
from socialhood.jobs.runtime import runtime
from socialhood.security.crypto import cipher_for
from socialhood.services.catalogue import shopify
from socialhood.shopify.registry import get_shopify

SYNC_RETRY = BackoffRetry(max_attempts=3)


@app.task(name="sync_shopify_products", queue=BULK, retry=SYNC_RETRY, pass_context=True)
async def sync_shopify_products(context: JobContext, workspace_id: str) -> None:
    rt = runtime()
    will_retry = int(context.job.attempts) + 1 < SYNC_RETRY.max_attempts

    async def work() -> None:
        with workspace_scope(uuid.UUID(workspace_id)):
            await shopify.run_sync(
                rt.sessionmaker,
                get_shopify(rt.http, rt.settings, rt.redis),
                cipher_for(tuple(rt.settings.token_encryption_keys)),
                now=datetime.now(UTC),
                will_retry=will_retry,
            )

    async def requeue(delay_s: float) -> None:
        await shopify.enqueue_sync(uuid.UUID(workspace_id), delay_s=delay_s)

    semaphore = BulkSemaphore(rt.redis, rt.settings.bulk_concurrency_per_workspace)
    await run_with_bulk_slot(semaphore, workspace_id, work, requeue)
