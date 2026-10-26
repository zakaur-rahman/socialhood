#!/usr/bin/env bash
# Creates /opt/amplychat/api.env and /opt/amplychat/postgres.env from api.env.example (C-145).
#
#   gen-secrets.sh            create both files (refuses to overwrite either)
#   gen-secrets.sh --check    list the variables still empty in api.env (names only)
#
# Fills only the [generated] values, with fresh random ones; [fixed] values are copied and
# [owner] values stay empty for the owner to paste. Files are mode 600. No value is ever printed.
# Needs bash, openssl and base64 (all on Ubuntu). APP_DIR overrides /opt/amplychat.
set -euo pipefail
umask 077

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app_dir="${APP_DIR:-/opt/amplychat}"
template="${TEMPLATE:-$here/api.env.example}"
api_env="$app_dir/api.env"
pg_env="$app_dir/postgres.env"

die() { echo "gen-secrets: $*" >&2; exit 1; }

if [[ "${1:-}" == "--check" ]]; then
  [[ -f "$api_env" ]] || die "$api_env does not exist"
  empty="$(grep -E '^[A-Z0-9_]+=$' "$api_env" | cut -d= -f1 || true)"
  if [[ -z "$empty" ]]; then
    echo "Every variable in $api_env has a value."
  else
    echo "Empty in $api_env (required ones stop the API from starting; see the tags in the file):"
    printf '%s\n' "$empty" | sed 's/^/  /'
  fi
  exit 0
fi

command -v openssl >/dev/null || die "openssl is not installed"
[[ -f "$template" ]] || die "no template at $template"
[[ -d "$app_dir" ]] || die "$app_dir does not exist"
[[ -e "$api_env" ]] && die "$api_env exists; not overwriting (move it away first to start over)"
[[ -e "$pg_env" ]] && die "$pg_env exists; not overwriting (its password is in the database)"

b64url() { base64 -w0 | tr '+/' '-_' | tr -d '='; }
hex() { openssl rand -hex "$1"; }
# A Fernet key: 32 random bytes, url-safe base64 with padding (44 characters).
fernet() { openssl rand 32 | base64 -w0 | tr '+/' '-_'; }

# VAPID: a P-256 key pair in the format of `web-push generate-vapid-keys`: the private scalar (32
# bytes) and the uncompressed public point (65 bytes), url-safe base64 without padding. The SEC1
# DER of a P-256 key is 121 bytes: the scalar at offset 7, the public point in the last 65.
vapid_der="$(openssl ecparam -name prime256v1 -genkey -noout -outform DER | base64 -w0)"
[[ "$(printf '%s' "$vapid_der" | base64 -d | wc -c)" -eq 121 ]] || die "unexpected EC key layout"
vapid_private="$(printf '%s' "$vapid_der" | base64 -d | tail -c +8 | head -c 32 | b64url)"
vapid_public="$(printf '%s' "$vapid_der" | base64 -d | tail -c 65 | b64url)"
unset vapid_der

pg_password="$(hex 24)"

tmp_api="$(mktemp "$app_dir/.api.env.XXXXXX")"
tmp_pg="$(mktemp "$app_dir/.postgres.env.XXXXXX")"
trap 'rm -f "$tmp_api" "$tmp_pg"' EXIT

generated=()
tag=""
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  if [[ -z "$line" ]]; then
    tag=""
  elif [[ "$line" =~ ^#[[:space:]]*\[(generated|owner|fixed)\] ]]; then
    tag="${BASH_REMATCH[1]}"
  fi
  if [[ "$line" =~ ^([A-Z0-9_]+)=(.*)$ ]]; then
    key="${BASH_REMATCH[1]}"
    value="${BASH_REMATCH[2]}"
    if [[ "$tag" == "generated" ]]; then
      case "$key" in
        METRICS_TOKEN | *_VERIFY_TOKEN) value="$(hex 32)" ;;
        TOKEN_ENCRYPTION_KEYS) value="$(fernet)" ;;
        VAPID_PUBLIC_KEY) value="$vapid_public" ;;
        VAPID_PRIVATE_KEY) value="$vapid_private" ;;
        DATABASE_URL | DATABASE_URL_DIRECT) value="${value//__POSTGRES_PASSWORD__/$pg_password}" ;;
        *) die "no generator for [generated] $key" ;;
      esac
      generated+=("$key")
    fi
    printf '%s=%s\n' "$key" "$value" >>"$tmp_api"
  else
    printf '%s\n' "$line" >>"$tmp_api"
  fi
done <"$template"

grep -q '__POSTGRES_PASSWORD__' "$tmp_api" && die "a database URL kept its placeholder"
printf 'POSTGRES_PASSWORD=%s\n' "$pg_password" >"$tmp_pg"
unset pg_password vapid_private

chmod 600 "$tmp_api" "$tmp_pg"
mv "$tmp_pg" "$pg_env"
mv "$tmp_api" "$api_env"
trap - EXIT

echo "Created $api_env and $pg_env (mode 600)."
echo "Generated: ${generated[*]} (and POSTGRES_PASSWORD)."
echo "Next: paste the [owner] values into $api_env, then: $0 --check"
