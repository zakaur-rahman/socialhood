# Production on one GCP VM (C-145)

This runbook covers the production plan: everything runs on one Google Cloud VM with Docker
Compose. The owner and the coordinator follow it step by step. It replaces the Render and Vercel
plan in [deploy.md](deploy.md). That file still holds the variable reference (section 4) and the
vendor URLs (section 6), and they apply here unchanged.

**The VM:** GCP project `amplychat`, instance `amplychat-prod`, e2-standard-2 (2 vCPU, 8 GB RAM,
2 GB swap), `asia-southeast1-b` (Singapore), Ubuntu 24.04, 50 GB SSD, static IP `34.126.136.162`,
Docker with Compose v2, app folder `/opt/amplychat` owned by `ubuntu`.

**Domains:** `amplychat.com` serves the website and the app (canonical, C-142). `www.amplychat.com`
308-redirects to it. `api.amplychat.com` serves the API, webhooks, OAuth callbacks and the website
chat widget.

## 1. What runs where

```
Internet ──80/443──► caddy ──► web:3000          (Next.js standalone)
                         └──► api:8000          (FastAPI, uvicorn)
                    worker  (two Procrastinate lanes, scripts/worker.sh)
                    migrate (one-shot: alembic upgrade head, before api and worker start)
                    postgres (pgvector/pgvector:pg18)   valkey (valkey/valkey:8)
```

| Piece | Where it is in the repository | On the VM |
|---|---|---|
| API image (API, worker and migrations) | `apps/api/Dockerfile` | `ghcr.io/zakaur-rahman/amplychat-api:<sha>` |
| Web image | `apps/web/Dockerfile` (`NEXT_OUTPUT=standalone`, `next.config.ts`) | `ghcr.io/zakaur-rahman/amplychat-web:<sha>` |
| Services | `infra/vm/compose.yml` (project `amplychat`) | `/opt/amplychat/compose.yml` |
| HTTPS, redirects, proxy | `infra/vm/Caddyfile` | `/opt/amplychat/Caddyfile` |
| Deploy, rollback | `infra/vm/deploy.sh` | `/opt/amplychat/deploy.sh` |
| Nightly backup | `infra/vm/backup.sh` | `/opt/amplychat/backup.sh` + a systemd timer |
| Env templates, secret generator | `infra/vm/*.env.example`, `infra/vm/gen-secrets.sh` | same names |
| Pipeline | `.github/workflows/production.yml` | |

**Files that exist only on the VM.** They are never committed and never printed:

| File | Holds | Made by |
|---|---|---|
| `/opt/amplychat/.env` | `IMAGE_TAG`, `PREVIOUS_IMAGE_TAG`, `COMPOSE_PROFILES` | `deploy.sh` (tags); you (`COMPOSE_PROFILES`) |
| `/opt/amplychat/web.env` | `CLERK_SECRET_KEY` | you, from `web.env.example` |
| `/opt/amplychat/api.env` | every API and worker setting | `gen-secrets.sh`, then you paste the vendor keys |
| `/opt/amplychat/postgres.env` | `POSTGRES_PASSWORD` (the same one as in `api.env`'s URLs) | `gen-secrets.sh` |

**Two modes**, chosen by `COMPOSE_PROFILES` in `/opt/amplychat/.env`:

- **Website only** (unset): only `caddy` and `web` run. `api.amplychat.com` answers a plain
  `503 Service unavailable` from Caddy. This is the first deploy (section 5). The API needs vendor
  keys that don't exist yet.
- **Full stack** (`COMPOSE_PROFILES=api`): `postgres`, `valkey`, `migrate`, `api` and `worker` run
  as well (section 6).

**How a deploy works.** A push to `main` runs CI. When CI passes, the Production workflow builds
both images and pushes them to GHCR as `:<commit sha>` and `:latest`. It then waits for the
owner's approval in the `production` environment. After approval it copies `infra/vm/` (the
compose file, the Caddyfile and the scripts, never the env files) to `/opt/amplychat` over SSH and
runs `deploy.sh <sha>`. The script:

1. writes `IMAGE_TAG`;
2. pulls the images;
3. runs `up -d`, which first runs `migrate` and starts `api` and `worker` only after it succeeds;
4. waits for every container to be running and healthy;
5. records the previous tag;
6. removes images that are unused and more than 10 days old.

If anything fails, it starts the previous tag again and the workflow fails. Migrations are
expand-only (TR-OPS-02), so the previous code runs on the new schema.

**Memory** (limits in `compose.yml`; the VM has 8 GB plus 2 GB swap): postgres 2 GB
(`shared_buffers` 384 MB, tuned for about 1.5 GB), worker 1.5 GB, api 1 GB, web 768 MB, valkey
320 MB (256 MB data, `noeviction`), caddy 256 MB, migrate 512 MB while it runs. That totals about
5.9 GB.

## 2. One-time VM setup [owner + coordinator]

Run these once, as `ubuntu` on the VM (`gcloud compute ssh amplychat-prod --zone asia-southeast1-b`).

1. **Docker without sudo** (the deploy logs in as `ubuntu`):
   `sudo usermod -aG docker ubuntu`, then log out and back in. Check with `docker ps`.
   `ls -ld /opt/amplychat` should show the folder is owned by `ubuntu`.
2. **Firewall** (GCP → VPC network → Firewall, or the commands below). Allow only 22, 80 and 443
   inbound. Delete the default RDP rule. Keep ICMP if you like.

   ```sh
   gcloud compute firewall-rules list --project amplychat
   gcloud compute firewall-rules delete default-allow-rdp --project amplychat
   ```

   Docker publishes ports past `ufw`, so the GCP firewall is the boundary. Compose publishes only
   Caddy's 80 and 443; Postgres and Valkey are on an internal network with no published port.
3. **Automatic security updates:**

   ```sh
   sudo apt-get update && sudo apt-get install -y unattended-upgrades
   sudo dpkg-reconfigure -plow unattended-upgrades     # answer Yes
   ```

   For automatic reboots after kernel updates, set `Unattended-Upgrade::Automatic-Reboot "true";`
   and a quiet `Automatic-Reboot-Time "21:30";` (03:00 IST) in
   `/etc/apt/apt.conf.d/50unattended-upgrades`. Containers come back on their own
   (`restart: unless-stopped`).
4. **Check the basics:** `free -h` (8 GB plus 2 GB swap), `df -h /` (50 GB), `docker compose version`.
   Check `gcloud --version` too. Google's Ubuntu images ship the Cloud CLI as a snap; it is needed
   only for the off-site backup copy (section 7).

## 3. DNS [owner account]

At the domain's DNS host, use DNS-only records. If the DNS is on Cloudflare, use a grey cloud,
not the proxy. Caddy gets the certificates itself, and the API reads the client address that
Caddy sees.

| Type | Name | Value |
|---|---|---|
| A | `amplychat.com` (`@`) | `34.126.136.162` |
| A | `www` | `34.126.136.162` |
| A | `api` | `34.126.136.162` |

- Delete any old A, AAAA or CNAME records on these names, such as Vercel's or Render's. Add no
  AAAA record: the VM has no IPv6.
- Optional: a CAA record `0 issue "letsencrypt.org"` and `0 issue "sectigo.com"` (ZeroSSL's
  fallback).
- **Clerk production DNS:** Clerk → the production instance → Domains. Add every CNAME it lists
  (Frontend API `clerk`, Account Portal `accounts`, email `clkmail` and the two `clk._domainkey`
  records). Wait until Clerk shows them verified. The live publishable key encodes
  `clerk.amplychat.com`, so sign-in and the site's Clerk script need these records.
- **Resend:** the SPF, DKIM and DMARC records for sending as `support@amplychat.com`
  ([deploy.md](deploy.md), section 6).

Check with `dig +short amplychat.com www.amplychat.com api.amplychat.com`; each should print
`34.126.136.162`. Caddy can't get certificates until all three resolve.

## 4. GitHub [owner account]

### 4.1 A deploy SSH key (only for this; not the NewsIQ key, not a personal key)

On your own computer:

```sh
ssh-keygen -t ed25519 -C amplychat-deploy -N "" -f amplychat_deploy
```

- Add `amplychat_deploy.pub` to the VM. Use Compute Engine → `amplychat-prod` → Edit → Security
  → SSH keys → Add item. Paste the line and change its comment, the last word, to `ubuntu`. The
  guest agent installs it for that user. If OS Login is on for the project, metadata keys are
  ignored. In that case, append the line to `/home/ubuntu/.ssh/authorized_keys` instead.
- The VM's host key, for `VM_KNOWN_HOSTS`:

  ```sh
  ssh-keyscan -t ed25519 34.126.136.162          # from your computer
  ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub   # on the VM: the fingerprints must match
  ```

  Compare it with `ssh-keyscan -t ed25519 34.126.136.162 | ssh-keygen -lf -`.
- After the secrets are saved, delete the private key file from your computer, or keep it only in
  a password manager. Anyone with this key controls the VM, because the `docker` group is
  equivalent to root. If it leaks, remove it from the VM and make a new one.

### 4.2 Environments (Settings → Environments)

**`production`** holds the deploy:

- Required reviewers: the owner. Deployment branches: `main`.
- Delete the old secrets `RENDER_DEPLOY_HOOK_API` and `RENDER_DEPLOY_HOOK_WORKER`.
- Add these secrets:

| Secret | Value |
|---|---|
| `VM_HOST` | `34.126.136.162` |
| `VM_USER` | `ubuntu` |
| `VM_SSH_KEY` | the whole private key file `amplychat_deploy` |
| `VM_KNOWN_HOSTS` | the `ssh-keyscan` line from 4.1 |

**`production-build`** has no reviewers. Deployment branches: `main`. It holds the web's build
values. They are **variables**, not secrets, because `NEXT_PUBLIC_*` values are public by
definition and end up in the JavaScript:

| Variable | Value | Needed for |
|---|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk production instance, `pk_live_…` | website-only and full stack |
| `NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION` · `NEXT_PUBLIC_BING_SITE_VERIFICATION` · `NEXT_PUBLIC_FACEBOOK_DOMAIN_VERIFICATION` | the `content` values ([deploy.md](deploy.md), section 4) | when you have them |
| `NEXT_PUBLIC_API_BASE_URL` | `https://api.amplychat.com` | **leave unset for website-only**; set it for the full stack |
| `NEXT_PUBLIC_META_APP_ID` · `NEXT_PUBLIC_WHATSAPP_CONFIG_ID` | the same values as the API's `META_APP_ID` and `WHATSAPP_CONFIG_ID` | full stack |
| `NEXT_PUBLIC_SENTRY_DSN` | the `socialhood-web` project DSN | optional |
| `NEXT_PUBLIC_SITE_URL` | leave unset (defaults to `https://amplychat.com`) | |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` · `_SIGN_UP_URL` · `NEXT_PUBLIC_SENTRY_ENVIRONMENT` · `NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE` | leave unset (defaults: `/sign-in`, `/sign-up`, `production`, `0.1`) | |
| `SENTRY_ORG` · `SENTRY_PROJECT` (+ secret `SENTRY_AUTH_TOKEN`) | for source-map upload | optional |

A changed build variable takes effect only with a new image: run the workflow (section 8).

**Repository variable** `PRODUCTION_DEPLOY=manual` is needed only if required reviewers aren't
available ([branching.md](branching.md), section 6).

### 4.3 Images on GHCR

The first workflow run creates two packages under the owner's account: `amplychat-api` and
`amplychat-web`. New packages start **private**. For each one, open it from the profile's
Packages tab, then Package settings → Change visibility → **Public**. The repository is public,
and public packages let the VM pull without credentials. The images hold no secrets. Each image
carries the `org.opencontainers.image.source` label, which links the package to the repository.

Until the packages are public, the deploy job's `docker compose pull` fails with "denied". Make
them public and run the workflow again.

## 5. First deploy: the website only

The goal is for `https://amplychat.com` to be live for Meta's business verification, with no API
yet ([deploy.md](deploy.md), section 5a lists what works without the API).

1. Check the prerequisites:
   - DNS (section 3) resolves.
   - Clerk's production DNS is verified.
   - The `production-build` variable `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is set and
     `NEXT_PUBLIC_API_BASE_URL` is **unset**.
   - The `production` secrets are set.
2. **On the VM**, make `web.env`. The workflow copies the rest of the files. For a deploy by hand
   before the first workflow run, copy `infra/vm/*` into `/opt/amplychat` first.

   ```sh
   cd /opt/amplychat
   install -m 600 /dev/null web.env
   nano web.env        # CLERK_SECRET_KEY=sk_live_…  (one line, no quotes)
   ```

   Leave `COMPOSE_PROFILES` out of `/opt/amplychat/.env`. That is website-only mode.
3. **On GitHub:** Actions → Production → Run workflow → branch `main`, tag empty. The run builds
   both images, then the owner approves `deploy-production`. On the first run, make the two
   packages public when the build finishes (section 4.3), before you approve.
4. **Check** from your computer:

   ```sh
   curl -sI https://amplychat.com | head -n 1                      # HTTP/2 200
   curl -sI https://amplychat.com/contact | head -n 1              # HTTP/2 200
   curl -sI https://www.amplychat.com/pricing | grep -i -E '^(HTTP|location)'  # 308 → https://amplychat.com/pricing
   curl -s -o /dev/null -w '%{http_code}\n' https://api.amplychat.com/healthz  # 503 (no API yet)
   curl -sI https://amplychat.com | grep -i -E 'strict-transport|content-security' # the app's headers
   ```

   On the VM, `cd /opt/amplychat && ./deploy.sh --status` shows the tag and two healthy
   containers. If a certificate is missing, read `docker compose logs caddy`. The usual cause is
   DNS not pointing at the VM yet.
5. Then follow [deploy.md](deploy.md), section 5a, "After it is live": Search Console, Bing and
   Meta domain verification.

## 6. The full stack

Do this once the vendor accounts exist (Clerk production, Meta app, Gemini, Cloudinary, Dodo live,
Resend, Sentry).

1. **Make the secrets** on the VM:

   ```sh
   cd /opt/amplychat
   ./gen-secrets.sh            # creates api.env and postgres.env (mode 600), prints names only
   nano api.env                # paste each [owner] value after its "="
   ./gen-secrets.sh --check    # lists what is still empty
   ```

   `gen-secrets.sh` fills only the **generated** values:
   - the Postgres password, which goes into `postgres.env` and both database URLs;
   - `METRICS_TOKEN`, `IG_WEBHOOK_VERIFY_TOKEN` and `WHATSAPP_WEBHOOK_VERIFY_TOKEN`
     (`openssl rand -hex 32`);
   - `TOKEN_ENCRYPTION_KEYS` (a Fernet key);
   - the VAPID key pair.

   It refuses to overwrite either file. Never regenerate `postgres.env` once the database exists.
   Its password is stored in the database volume. The **owner** values to paste are listed in
   section 10.
   `CLERK_JWT_KEY` is the PEM on one line, with literal `\n` between its lines.
2. **Web build values:** in `production-build`, set `NEXT_PUBLIC_API_BASE_URL=https://api.amplychat.com`,
   `NEXT_PUBLIC_META_APP_ID`, `NEXT_PUBLIC_WHATSAPP_CONFIG_ID` and optionally
   `NEXT_PUBLIC_SENTRY_DSN`.
3. **Turn the stack on:** `echo COMPOSE_PROFILES=api >> /opt/amplychat/.env`.
4. **Deploy:** Actions → Production → Run workflow (tag empty), then approve. The first `migrate`
   creates the `vector`, `pg_trgm` and `pgcrypto` extensions and the queue's tables. If the API
   refuses to start, `docker compose logs api` lists every missing or unsafe setting at once.
5. **Check** (the checklist in [deploy.md](deploy.md), section 7, applies with the VM in place of
   Render):

   ```sh
   curl -s https://api.amplychat.com/healthz                                  # {"status":"ok"}
   # On the VM (reads the token without printing it):
   curl -s -H "Authorization: Bearer $(grep '^METRICS_TOKEN=' /opt/amplychat/api.env | cut -d= -f2-)" \
     https://api.amplychat.com/readyz                                         # "ready"
   curl -s -o /dev/null -w '%{http_code}\n' https://api.amplychat.com/metrics # 401
   curl -sI https://api.amplychat.com/healthz | grep -i '^server'             # nothing
   docker compose logs worker | grep -i -E 'interactive|bulk|ping' | tail     # both lanes, ping job
   ```

   Then run the per-IP limit check: 61 requests with forged `X-Forwarded-For` headers, and the
   61st returns 429 ([deploy.md](deploy.md), section 7). Caddy replaces any `X-Forwarded-For` a
   client sends with the address it saw. The API reads that header from the right
   (`CLIENT_IP_HEADER=x-forwarded-for`) and trusts the forwarded scheme only from Caddy's fixed
   address `172.30.10.10` (`FORWARDED_ALLOW_IPS`).

   Also check that Caddy sees real addresses. `docker compose logs caddy | grep handled | tail -n 1`
   must show your own public IP as `remote_ip`, not a `172.x` Docker address. If it shows a Docker
   address, every visitor shares one rate-limit key; check that Docker's `userland-proxy` is not
   forcing the connections through it (`/etc/docker/daemon.json`).
6. **Vendor URLs:** set them all as in [deploy.md](deploy.md), section 6, with `{API}` =
   `https://api.amplychat.com` and `{WEB}` = `https://amplychat.com`. This covers the Meta
   webhooks (`/webhooks/instagram` and `/webhooks/whatsapp`), the OAuth redirect
   `/v1/oauth/instagram/callback`, the deauthorize and data-deletion callbacks, the Clerk webhook
   `/webhooks/clerk`, the Dodo webhook `/webhooks/dodo` and the Embedded Signup domain. Meta's form
   needs the webhook verify tokens. Read them on the VM, in your own terminal:
   `grep -E '^(IG|WHATSAPP)_WEBHOOK_VERIFY_TOKEN=' /opt/amplychat/api.env`.
7. If you made sign-ups restricted in Clerk for the website-only period, open them again.

## 7. Backups and restore

`backup.sh` writes `pg_dump` custom-format files to `/opt/amplychat/backups`. It keeps the last 7
days in `daily/` and the last 4 Sundays in `weekly/`, and deletes anything older than 30 days, as
the privacy policy promises ([backup.md](backup.md)). Each dump is checked with
`pg_restore --list` before it counts. In website-only mode the script does nothing.

**Install the timer** (once, on the VM):

```sh
sudo tee /etc/systemd/system/amplychat-backup.service >/dev/null <<'UNIT'
[Unit]
Description=Amplychat database backup
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
User=ubuntu
# Environment=BACKUP_GCS_BUCKET=amplychat-db-backups
ExecStart=/opt/amplychat/backup.sh
UNIT
sudo tee /etc/systemd/system/amplychat-backup.timer >/dev/null <<'UNIT'
[Unit]
Description=Nightly Amplychat database backup

[Timer]
OnCalendar=*-*-* 20:30:00 UTC
RandomizedDelaySec=10m
Persistent=true

[Install]
WantedBy=timers.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now amplychat-backup.timer
systemctl list-timers amplychat-backup.timer
sudo systemctl start amplychat-backup.service && journalctl -u amplychat-backup -n 20   # a first run
```

The timer runs at 20:30 UTC (02:00 IST). The cron equivalent is
`30 20 * * * /opt/amplychat/backup.sh >> /opt/amplychat/backups/backup.log 2>&1` in `ubuntu`'s
crontab.

**Off-site copy (recommended).** A VM disk lost with its backups is a total loss. Set this up:

1. Create a bucket in the same region with a 30-day delete rule:

   ```sh
   gcloud storage buckets create gs://amplychat-db-backups --project amplychat \
     --location asia-southeast1 --uniform-bucket-level-access --public-access-prevention
   printf '{"rule":[{"action":{"type":"Delete"},"condition":{"age":30}}]}' > lifecycle.json
   gcloud storage buckets update gs://amplychat-db-backups --lifecycle-file lifecycle.json
   ```

2. Let the VM's service account write to it, without delete rights:

   ```sh
   gcloud storage buckets add-iam-policy-binding gs://amplychat-db-backups \
     --member "serviceAccount:<the VM's service account>" --role roles/storage.objectCreator
   ```

3. The VM's access scopes must allow Storage writes. The default is read-only. Stop the VM, then
   Edit → Access scopes → Storage: **Read Write**, then start it.
4. Uncomment `Environment=BACKUP_GCS_BUCKET=amplychat-db-backups` in the service, run
   `sudo systemctl daemon-reload`, and run the backup once by hand.

If the snap `gcloud` is missing: `sudo snap install google-cloud-cli --classic`.

**Restore drill** (before launch, then quarterly). Restore into a scratch database next to the
live one:

```sh
cd /opt/amplychat
f=$(ls -1 backups/daily/*.dump | tail -n 1)
docker compose exec -T postgres createdb -U socialhood restore_check
docker compose exec -T postgres pg_restore -U socialhood -d restore_check --no-owner < "$f"
docker compose exec -T postgres psql -U socialhood -d restore_check -c \
  "SELECT version_num FROM alembic_version; SELECT count(*) FROM workspaces;"
docker compose exec -T postgres dropdb -U socialhood restore_check
```

Record the drill in [backup.md](backup.md).

**A real restore** replaces the live database, so take a fresh backup of the current state first:

```sh
cd /opt/amplychat
./backup.sh
docker compose stop api worker
docker compose exec -T postgres dropdb -U socialhood --force socialhood
docker compose exec -T postgres createdb -U socialhood socialhood
docker compose exec -T postgres pg_restore -U socialhood -d socialhood < backups/daily/<file>.dump
docker compose up -d
```

Afterwards, run the deletion purges again, as [backup.md](backup.md) describes ("A restore from
an export").

**What these backups don't give:** point-in-time recovery. Render's plan had 7 days of
point-in-time recovery. Here, the worst case loses the writes since the last nightly dump
(RPO 24 h). See C-145 for the follow-up: WAL archiving to the bucket.

## 8. Everyday operations

All commands run on the VM in `/opt/amplychat`. `docker compose` finds `compose.yml` and `.env`
there.

| Task | How |
|---|---|
| Release | merge `develop` → `main` ([branching.md](branching.md)); CI passes; approve the Production run |
| Redeploy main's head (for example after changing a build variable) | Actions → Production → Run workflow, tag empty |
| **Roll back** | Actions → Production → Run workflow, tag = the previous good commit SHA (no build). On the VM: `./deploy.sh --rollback` (to `PREVIOUS_IMAGE_TAG`) |
| Status | `./deploy.sh --status` · `docker compose ps` |
| Logs | `docker compose logs -f --tail 100 api` (or `worker`, `web`, `caddy`, `postgres`). Logs are JSON files rotated at 10 MB × 5 per container |
| Restart one service | `docker compose restart api` |
| Change a setting in `api.env` | edit it, then `docker compose up -d api worker` (recreates both with the new env) |
| Database shell | `docker compose exec postgres psql -U socialhood` |
| Memory | `free -h` · `docker stats --no-stream` |
| Disk | `df -h /` · `docker system df` · `du -sh /opt/amplychat/backups`. Old images are pruned on each deploy; `docker builder prune` is never needed (nothing builds here) |
| Certificates | automatic; stored in the `amplychat_caddy-data` volume. Never delete it, or Let's Encrypt rate limits apply |
| Base images (caddy, postgres, valkey) | each deploy pulls the newest of their pinned tags (`caddy:2.10-alpine`, `pgvector/pgvector:pg18`, `valkey/valkey:8`). A major version change is a code change |

**When something is wrong:**

- The site shows 502 or 503: check `docker compose ps` for an unhealthy service and
  `docker compose logs <service>`.
- Memory is low: `docker stats`. The worker's lanes (`WORKER_*_CONCURRENCY` in `api.env`) are the
  first thing to lower.
- Disk is full: `docker system df`, then `docker image prune -af` and the backups folder.

The API's `/metrics` is at `https://api.amplychat.com/metrics` with the `METRICS_TOKEN` bearer,
for Grafana Cloud ([alerts.md](alerts.md)).

## 9. Local proof (how this was tested)

The same files run on a developer machine with throwaway values. Use a folder with copies of
`compose.yml` and `Caddyfile`, plus an `.env` like this:

```
IMAGE_TAG=local
API_IMAGE=amplychat-api
WEB_IMAGE=amplychat-web
COMPOSE_PROFILES=api
HTTP_PORT=8480
HTTPS_PORT=8443
SITE_HOST=localhost
WWW_HOST=www.localhost
API_HOST=api.localhost
```

Caddy serves `localhost` names from its internal CA (`curl -k`). Set `APP_ENV=staging` in the
local `api.env`, because production refuses the empty vendor keys. Build the images locally:

```sh
docker build -t amplychat-api:local apps/api
docker build -f apps/web/Dockerfile --build-arg NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=… -t amplychat-web:local .
```

## 10. Owner-provided values (names only)

**`api.env`** (required in production):
- `SENTRY_DSN`
- `CLERK_SECRET_KEY`, `CLERK_JWT_KEY`, `CLERK_ISSUER`, `CLERK_WEBHOOK_SECRET`
- `IG_APP_ID`, `IG_APP_SECRET`, `META_APP_ID`, `META_APP_SECRET`, `WHATSAPP_CONFIG_ID`
- `GEMINI_API_KEY`
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`
- `DODO_API_KEY`, `DODO_WEBHOOK_SECRET`, `DODO_PRODUCT_PRO_MONTHLY`
- `RESEND_API_KEY`

**`api.env`** (optional; each feature stays off while empty):
- `DODO_PRODUCT_MAX_MONTHLY`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`

Razorpay has no app-wide key: each business enters its own in the app.

**`web.env`:** `CLERK_SECRET_KEY`.

**GitHub `production-build` variables:**
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `NEXT_PUBLIC_API_BASE_URL` (full stack)
- `NEXT_PUBLIC_META_APP_ID`, `NEXT_PUBLIC_WHATSAPP_CONFIG_ID`
- `NEXT_PUBLIC_SENTRY_DSN`
- `NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION`, `NEXT_PUBLIC_BING_SITE_VERIFICATION`,
  `NEXT_PUBLIC_FACEBOOK_DOMAIN_VERIFICATION`
- optional: `SENTRY_ORG`, `SENTRY_PROJECT` and the secret `SENTRY_AUTH_TOKEN`

**GitHub `production` secrets:** `VM_HOST`, `VM_USER`, `VM_SSH_KEY`, `VM_KNOWN_HOSTS`.
