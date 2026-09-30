#!/usr/bin/env bash
# Starts one worker process per lane (TR-JOB-01, TR-JOB-06) and exits if either stops, so the
# host restarts the whole service. Concurrency can be tuned per environment.
#
# Shutdown (docs/ops/runbook.md, "Deploys and running jobs"): on SIGTERM or SIGINT each lane gets
# one SIGTERM, takes no new job and finishes the ones it is running, and this script waits for
# both. Render kills what is left after the service's maxShutdownDelaySeconds (60 s);
# recover_stalled_jobs settles those jobs. Each lane runs in its own session (setsid), so a signal
# sent to the whole process group reaches it once, from here: a second SIGTERM would kill a
# Procrastinate worker at once.
set -euo pipefail

APP="socialhood.jobs.app.app"
INTERACTIVE_CONCURRENCY="${WORKER_INTERACTIVE_CONCURRENCY:-20}"
BULK_CONCURRENCY="${WORKER_BULK_CONCURRENCY:-8}"
SETSID="$(command -v setsid || true)"

interactive=""
bulk=""

stop_lanes() {
  trap '' TERM INT
  for pid in $interactive $bulk; do
    kill -TERM "$pid" 2>/dev/null || true
  done
  wait || true
}

trap 'stop_lanes; exit 0' TERM INT

$SETSID procrastinate --app="$APP" worker --queues=interactive --concurrency="$INTERACTIVE_CONCURRENCY" &
interactive=$!
$SETSID procrastinate --app="$APP" worker --queues=bulk --concurrency="$BULK_CONCURRENCY" &
bulk=$!

# One lane stopped on its own: stop the other one the same way, then exit so Render restarts both.
wait -n || true
stop_lanes
exit 1
