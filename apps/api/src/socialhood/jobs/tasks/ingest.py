"""Follow-ups of an ingested message: fetch_contact_profile and ingest_media (T3.2, T3.3).

Thin tasks; the work is in services/ingest_followups.py. Both run on the interactive lane
(TR-JOB-06) and retry retryable platform errors (TR-JOB-04), 3 tries each (job catalogue).
"""

from __future__ import annotations

import uuid

from socialhood.jobs.app import INTERACTIVE, app
from socialhood.jobs.retry import PlatformRetry
from socialhood.jobs.runtime import runtime
from socialhood.platforms.deps import deps_from
from socialhood.services import ingest_followups


@app.task(name="fetch_contact_profile", queue=INTERACTIVE, retry=PlatformRetry(max_attempts=3))
async def fetch_contact_profile(workspace_id: str, contact_id: str) -> None:
    rt = runtime()
    await ingest_followups.refresh_contact_profile(
        rt.sessionmaker,
        rt.redis,
        deps_from(rt.http, rt.settings),
        workspace_id=uuid.UUID(workspace_id),
        contact_id=uuid.UUID(contact_id),
    )


@app.task(name="ingest_media", queue=INTERACTIVE, retry=PlatformRetry(max_attempts=3))
async def ingest_media(workspace_id: str, message_id: str, attachment_id: str) -> None:
    rt = runtime()
    await ingest_followups.copy_inbound_media(
        rt.sessionmaker,
        rt.redis,
        deps_from(rt.http, rt.settings),
        workspace_id=uuid.UUID(workspace_id),
        message_id=uuid.UUID(message_id),
        attachment_id=attachment_id,
    )
