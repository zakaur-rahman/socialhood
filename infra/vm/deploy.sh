#!/usr/bin/env bash
# Deploys one image tag of Amplychat on the VM (C-145; docs/ops/deploy-vm.md). The Production
# workflow runs it over SSH after copying infra/vm/ to /opt/amplychat; it also runs by hand:
#
#   deploy.sh <tag>        pull <tag> (a commit SHA), migrate, start, wait for health
#   deploy.sh --rollback   deploy PREVIOUS_IMAGE_TAG again
#   deploy.sh --status     show the tags and the containers
#
# The mode follows COMPOSE_PROFILES in /opt/amplychat/.env: unset = website only (caddy + web),
# "api" = the full stack. If the new tag doesn't come up healthy, the previous tag is started
# again and the script exits non-zero. Migrations are expand-only (TR-OPS-02), so the previous
# code runs on the new schema.
set -euo pipefail

app_dir="${APP_DIR:-/opt/amplychat}"
state="$app_dir/.env"
health_timeout="${HEALTH_TIMEOUT:-240}"

log() { printf '[deploy %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }
compose() { docker compose --project-directory "$app_dir" -f "$app_dir/compose.yml" "$@"; }

get_var() { { grep -E "^$1=" "$state" 2>/dev/null || true; } | tail -n 1 | cut -d= -f2-; }
set_var() {
  local tmp
  tmp="$(mktemp "$app_dir/.env.XXXXXX")"
  { grep -vE "^$1=" "$state" 2>/dev/null || true; } >"$tmp"
  printf '%s=%s\n' "$1" "$2" >>"$tmp"
  chmod 600 "$tmp"
  mv "$tmp" "$state"
}

# Every service of the active profiles except the one-shot migrate is running, and healthy where
# it has a healthcheck. Leaves the ones that aren't in $unhealthy.
unhealthy=""
wait_healthy() {
  local deadline=$((SECONDS + health_timeout)) services pending service id status
  services="$(compose config --services | grep -vx migrate)"
  while :; do
    pending=""
    for service in $services; do
      id="$(compose ps -q "$service" 2>/dev/null | head -n 1)"
      if [[ -z "$id" ]]; then
        pending+=" $service(missing)"
        continue
      fi
      status="$(docker inspect -f '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id")"
      case "$status" in
        running/healthy | running/none) ;;
        *) pending+=" $service($status)" ;;
      esac
    done
    unhealthy="$pending"
    [[ -z "$pending" ]] && return 0
    if ((SECONDS >= deadline)); then
      log "not healthy after ${health_timeout}s:$pending"
      return 1
    fi
    sleep 5
  done
}

show_failure() {
  compose ps -a || true
  local service
  # The migration's log, then each service that never got healthy ("api(running/starting)" → api).
  for service in migrate $unhealthy; do
    service="${service%%(*}"
    log "last log lines of $service:"
    compose logs --no-color --tail 40 "$service" 2>&1 || true
  done
}

# The images are private in Artifact Registry (C-147). Docker pulls with the VM's own service
# account through gcloud's credential helper, set up once here; no password is stored.
registry_login() {
  local host="${REGISTRY_HOST:-asia-southeast1-docker.pkg.dev}"
  if ! grep -q "\"$host\"" "$HOME/.docker/config.json" 2>/dev/null; then
    log "configuring Docker for $host"
    gcloud auth configure-docker "$host" --quiet >/dev/null 2>&1 || { log "gcloud auth configure-docker failed"; return 1; }
  fi
}

start() {
  # SKIP_PULL=1 uses images already on the machine (a local test of this script).
  if [[ "${SKIP_PULL:-0}" != "1" ]]; then
    registry_login || return 1
    compose pull --quiet || { log "pull failed (the VM's service account needs Artifact Registry Reader)"; return 1; }
  fi
  compose up -d --remove-orphans && sync_caddy && wait_healthy
}

# The Caddyfile is a single-file bind mount, which keeps the file the container started with: when a
# deploy replaces it (a new inode), Caddy would go on serving the old rules, and a reload reads the old
# file too. Recreate Caddy only when its copy differs from the one on disk, so a deploy that doesn't
# touch the Caddyfile has no blip.
sync_caddy() {
  local live want
  want=$(sha256sum Caddyfile | cut -d' ' -f1)
  live=$(compose exec -T caddy sha256sum /etc/caddy/Caddyfile 2>/dev/null | cut -d' ' -f1) || live=""
  [[ "$live" == "$want" ]] && return 0
  log "the Caddyfile changed: recreating caddy"
  compose up -d --no-deps --force-recreate caddy
}

main() {
  [[ -d "$app_dir" ]] || die "$app_dir does not exist"
  cd "$app_dir"
  [[ -f compose.yml && -f Caddyfile ]] || die "compose.yml or Caddyfile missing in $app_dir"

  case "${1:-}" in
    --status)
      printf 'IMAGE_TAG=%s\nPREVIOUS_IMAGE_TAG=%s\nCOMPOSE_PROFILES=%s\n' \
        "$(get_var IMAGE_TAG)" "$(get_var PREVIOUS_IMAGE_TAG)" "$(get_var COMPOSE_PROFILES)"
      compose ps
      exit 0
      ;;
    --rollback)
      set -- "$(get_var PREVIOUS_IMAGE_TAG)"
      [[ -n "$1" ]] || die "no PREVIOUS_IMAGE_TAG to roll back to"
      log "rolling back to $1"
      ;;
    "" | -*) die "usage: deploy.sh <tag> | --rollback | --status" ;;
  esac

  local tag="$1" current profiles
  [[ "$tag" =~ ^[A-Za-z0-9_.-]{1,128}$ ]] || die "not an image tag: $tag"

  # One deploy at a time.
  exec 9>"$app_dir/.deploy.lock"
  flock -n 9 || die "another deploy is running"

  [[ -f web.env ]] || die "web.env missing (copy web.env.example and fill it)"
  profiles="$(get_var COMPOSE_PROFILES)"
  if [[ ",$profiles," == *",api,"* ]]; then
    [[ -f api.env && -f postgres.env ]] || die "the full stack needs api.env and postgres.env (gen-secrets.sh)"
    log "mode: full stack"
  else
    log "mode: website only (COMPOSE_PROFILES has no 'api')"
  fi

  current="$(get_var IMAGE_TAG)"
  log "deploying $tag (running now: ${current:-nothing})"
  set_var IMAGE_TAG "$tag"

  if start; then
    if [[ -n "$current" && "$current" != "$tag" ]]; then
      set_var PREVIOUS_IMAGE_TAG "$current"
    fi
    # Images unused by any container and older than 10 days; the previous release stays for a
    # quick rollback (and the last 20 tags can be pulled again from Artifact Registry).
    docker image prune -af --filter "until=240h" >/dev/null || true
    log "deployed $tag"
    compose ps
    return 0
  fi

  log "$tag failed"
  show_failure
  if [[ -n "$current" && "$current" != "$tag" ]]; then
    log "rolling back to $current"
    set_var IMAGE_TAG "$current"
    if start; then
      log "rolled back to $current; $tag is not live"
    else
      log "rollback to $current failed too: check 'docker compose ps' and the logs"
    fi
  fi
  exit 1
}

main "$@"
