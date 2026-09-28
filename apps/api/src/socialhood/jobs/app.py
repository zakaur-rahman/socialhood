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
]

configure_logging(get_settings().log_level)

app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(conninfo=get_settings().database_url_direct),
    import_paths=TASK_MODULES,
)
