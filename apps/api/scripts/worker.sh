#!/usr/bin/env bash
# Starts one worker process per lane (TR-JOB-01, TR-JOB-06) and exits if either stops, so the
# host restarts the whole service. Concurrency can be tuned per environment.
set -euo pipefail

APP="socialhood.jobs.app.app"
INTERACTIVE_CONCURRENCY="${WORKER_INTERACTIVE_CONCURRENCY:-20}"
BULK_CONCURRENCY="${WORKER_BULK_CONCURRENCY:-8}"

procrastinate --app="$APP" worker --queues=interactive --concurrency="$INTERACTIVE_CONCURRENCY" &
procrastinate --app="$APP" worker --queues=bulk --concurrency="$BULK_CONCURRENCY" &

wait -n
exit 1
