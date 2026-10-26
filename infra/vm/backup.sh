#!/usr/bin/env bash
# Nightly database backup on the VM (C-145; docs/ops/deploy-vm.md, "Backups"). A systemd timer
# runs it once a day:
#
#   /opt/amplychat/backups/daily/socialhood-db-YYYY-MM-DD.dump    the last 7 days
#   /opt/amplychat/backups/weekly/socialhood-db-YYYY-MM-DD.dump   the last 4 Sundays
#
# pg_dump's custom format (restore with pg_restore). Each dump is checked by listing it with
# pg_restore before it replaces anything. Nothing is ever older than 30 days, as the privacy
# policy promises for backup copies (docs/ops/backup.md).
#
# Off-site copy: set BACKUP_GCS_BUCKET (a bucket name, no gs://) and each dump is also copied there
# with gcloud (the VM's service account needs write access; the bucket's lifecycle rule deletes
# objects after 30 days). APP_DIR and BACKUP_DIR override the paths.
set -euo pipefail
umask 077

app_dir="${APP_DIR:-/opt/amplychat}"
backup_dir="${BACKUP_DIR:-$app_dir/backups}"
keep_daily=7
keep_weekly=4

log() { printf '[backup %s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
compose() { docker compose --project-directory "$app_dir" -f "$app_dir/compose.yml" "$@"; }

exec 9>"$app_dir/.backup.lock"
flock -n 9 || { log "another backup is running"; exit 1; }

if [[ -z "$(compose ps -q --status running postgres 2>/dev/null)" ]]; then
  log "postgres is not running (website-only mode?): nothing to back up"
  exit 0
fi

mkdir -p "$backup_dir/daily" "$backup_dir/weekly"
name="socialhood-db-$(date -u +%F).dump"
file="$backup_dir/daily/$name"
partial="$file.partial"
trap 'rm -f "$partial"' EXIT

log "dumping to $file"
compose exec -T postgres pg_dump -U socialhood -d socialhood --format=custom --compress=6 >"$partial"
# A dump that pg_restore can't list is not a backup.
compose exec -T postgres pg_restore --list <"$partial" >/dev/null
mv "$partial" "$file"
trap - EXIT
log "done: $(du -h "$file" | cut -f1)"

# Sundays (UTC) also go to weekly/.
if [[ "$(date -u +%u)" == "7" ]]; then
  cp "$file" "$backup_dir/weekly/$name"
fi

prune() { # keep the newest $2 dumps in $1
  find "$1" -maxdepth 1 -name 'socialhood-db-*.dump' -printf '%f\n' | sort -r | tail -n +"$(($2 + 1))" |
    while read -r old; do rm -f -- "$1/$old"; done
}
prune "$backup_dir/daily" "$keep_daily"
prune "$backup_dir/weekly" "$keep_weekly"
# Belt and braces for the 30-day promise.
find "$backup_dir" -name 'socialhood-db-*.dump' -mtime +29 -delete

if [[ -n "${BACKUP_GCS_BUCKET:-}" ]]; then
  log "copying to gs://$BACKUP_GCS_BUCKET/daily/$name"
  gcloud storage cp --quiet "$file" "gs://$BACKUP_GCS_BUCKET/daily/$name"
fi
