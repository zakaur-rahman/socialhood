"""The job queue (TR-JOB-01): Procrastinate on PostgreSQL, two lanes.

Workers connect directly to Postgres (DATABASE_URL_DIRECT), never through PgBouncer, because
the queue uses LISTEN/NOTIFY. Start them with scripts/worker.sh.
"""

from __future__ import annotations

import procrastinate

from socialhood.observability.logging import configure_logging
from socialhood.settings import get_settings

INTERACTIVE = "interactive"
BULK = "bulk"
LANES = (INTERACTIVE, BULK)

# Every module that declares tasks. Procrastinate imports them when a worker starts.
TASK_MODULES = [
    "socialhood.jobs.tasks.maintenance",
    "socialhood.jobs.tasks.webhooks",
    "socialhood.jobs.tasks.accounts",
    "socialhood.jobs.tasks.privacy",
    "socialhood.jobs.tasks.ingest",
    "socialhood.jobs.tasks.sync",
    "socialhood.jobs.tasks.send",
    "socialhood.jobs.tasks.scheduled",
    "socialhood.jobs.tasks.whatsapp",
    "socialhood.jobs.tasks.automations",
    "socialhood.jobs.tasks.automation_windows",
    "socialhood.jobs.tasks.analysis",
    "socialhood.jobs.tasks.suggestions",
    "socialhood.jobs.tasks.knowledge",
    "socialhood.jobs.tasks.comments",
    "socialhood.jobs.tasks.insights",
    "socialhood.jobs.tasks.publishing",
    "socialhood.jobs.tasks.agent",
    "socialhood.jobs.tasks.billing",
    "socialhood.jobs.tasks.emails",
    "socialhood.jobs.tasks.push",
    "socialhood.jobs.tasks.digests",
    "socialhood.jobs.tasks.renders",
]

configure_logging(get_settings().log_level)

app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(conninfo=get_settings().database_url_direct),
    import_paths=TASK_MODULES,
)
