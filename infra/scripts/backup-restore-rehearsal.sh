#!/usr/bin/env bash
# Backup and restore rehearsal (T9.5, §2.13 "restore rehearsed once before launch").
#
# Dumps the local development database through the Docker Postgres container, restores the dump
# into a scratch database, checks it (migration version, extensions, row counts per table against
# the source), then drops the scratch database. The source is only read (pg_dump and SELECTs).
# Production restores use Render's point-in-time recovery instead: docs/ops/backup.md.
#
# Usage (from anywhere; Linux, macOS or Windows Git Bash):
#   infra/scripts/backup-restore-rehearsal.sh [--keep]
# Environment (defaults match infra/docker-compose.yml):
#   PG_CONTAINER=socialhood-postgres-1  SOURCE_DB=socialhood  SCRATCH_DB=socialhood_restore_check
#   PG_USER=socialhood
# --keep leaves the scratch database in place for inspection (drop it yourself afterwards).
set -euo pipefail
export MSYS_NO_PATHCONV=1 # Git Bash: pass /tmp paths to docker exec unchanged

CONTAINER="${PG_CONTAINER:-socialhood-postgres-1}"
SOURCE_DB="${SOURCE_DB:-socialhood}"
SCRATCH_DB="${SCRATCH_DB:-socialhood_restore_check}"
PG_USER="${PG_USER:-socialhood}"
DUMP="/tmp/${SCRATCH_DB}.dump"
KEEP=false
[[ "${1:-}" == "--keep" ]] && KEEP=true

# The scratch database is dropped and recreated: refuse anything that could be a real one.
if [[ "$SCRATCH_DB" != *_restore_check || "$SCRATCH_DB" == "$SOURCE_DB" ]]; then
  echo "SCRATCH_DB must end in _restore_check and differ from SOURCE_DB" >&2
  exit 2
fi

psql_in() { # psql_in <database> <sql>: unaligned, tuples only, fields split by |
  docker exec -i "$CONTAINER" psql -X -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$1" -At -F '|' -c "$2"
}

cleanup() {
  docker exec "$CONTAINER" rm -f "$DUMP" >/dev/null 2>&1 || true
  if [[ "$KEEP" == false ]]; then
    psql_in postgres "DROP DATABASE IF EXISTS \"$SCRATCH_DB\"" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

now() { date +%s; }

# Exact row counts for every table in public, in one read-only query.
COUNTS_SQL="SELECT table_name,
  (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I',
    table_schema, table_name), false, true, '')))[1]::text::bigint
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name"

echo "== Backup and restore rehearsal: $SOURCE_DB -> $SCRATCH_DB (container $CONTAINER)"
echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
docker exec "$CONTAINER" pg_dump --version

before_counts="$(psql_in "$SOURCE_DB" "$COUNTS_SQL")"
source_version="$(psql_in "$SOURCE_DB" "SELECT version_num FROM alembic_version")"

started=$(now)
docker exec "$CONTAINER" pg_dump -U "$PG_USER" -d "$SOURCE_DB" --format=custom --file="$DUMP"
dump_seconds=$(( $(now) - started ))
dump_bytes="$(docker exec "$CONTAINER" stat -c %s "$DUMP")"
after_counts="$(psql_in "$SOURCE_DB" "$COUNTS_SQL")"
echo "Dump: $dump_bytes bytes in ${dump_seconds}s"

psql_in postgres "DROP DATABASE IF EXISTS \"$SCRATCH_DB\"" >/dev/null
psql_in postgres "CREATE DATABASE \"$SCRATCH_DB\" OWNER \"$PG_USER\"" >/dev/null
started=$(now)
docker exec "$CONTAINER" pg_restore -U "$PG_USER" -d "$SCRATCH_DB" --no-owner --exit-on-error "$DUMP"
restore_seconds=$(( $(now) - started ))
echo "Restore: ${restore_seconds}s"

restored_version="$(psql_in "$SCRATCH_DB" "SELECT version_num FROM alembic_version")"
extensions="$(psql_in "$SCRATCH_DB" "SELECT string_agg(extname || ' ' || extversion, ', ' ORDER BY extname) FROM pg_extension")"
restored_counts="$(psql_in "$SCRATCH_DB" "$COUNTS_SQL")"

failures=0
echo
echo "Migration version: source $source_version, restored $restored_version"
[[ "$source_version" == "$restored_version" ]] || { echo "FAIL: migration versions differ"; failures=$((failures + 1)); }
echo "Extensions: $extensions"
for ext in vector pg_trgm pgcrypto; do
  [[ "$extensions" == *"$ext "* ]] || { echo "FAIL: extension $ext missing"; failures=$((failures + 1)); }
done

echo
echo "| Table | Source rows | Restored rows | Check |"
echo "|---|---:|---:|---|"
tables=0
total=0
live=0
while IFS='|' read -r table rows; do
  [[ -z "$table" ]] && continue
  tables=$((tables + 1))
  total=$((total + rows))
  after="$(grep -E "^${table}\|" <<<"$after_counts" | cut -d'|' -f2 || true)"
  restored="$(grep -E "^${table}\|" <<<"$restored_counts" | cut -d'|' -f2 || true)"
  if [[ "$rows" != "$after" ]]; then
    # Written while the dump ran (a local worker's queue tables): the dump holds one snapshot.
    check="changed during dump ($rows -> $after)"
    live=$((live + 1))
  elif [[ "$restored" == "$rows" ]]; then
    check="ok"
  else
    check="FAIL"
    failures=$((failures + 1))
  fi
  echo "| $table | $rows | ${restored:-missing} | $check |"
done <<<"$before_counts"

echo
echo "Tables: $tables; rows in source: $total; changed during dump: $live; failures: $failures"
echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [[ "$KEEP" == true ]]; then
  echo "Kept $SCRATCH_DB. Drop it with: docker exec $CONTAINER psql -U $PG_USER -d postgres -c 'DROP DATABASE \"$SCRATCH_DB\"'"
else
  echo "Dropped $SCRATCH_DB."
fi
if (( failures > 0 )); then
  echo "RESULT: FAILED"
  exit 1
fi
echo "RESULT: PASSED"
