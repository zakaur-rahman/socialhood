# Deploy: environments, domains and the first deploy (T9.5)

This is a step-by-step runbook for the owner. Steps marked **[owner account]** need the business's
own vendor accounts (§6.5: fresh accounts owned by the business, two-factor authentication on, no
v1 keys). Nothing here was deployed on the owner's behalf.

- **API and worker, Postgres, Valkey:** Render, Singapore, from [`infra/render.yaml`](../../infra/render.yaml).
- **Web:** Vercel, from `apps/web` ([`apps/web/vercel.json`](../../apps/web/vercel.json)).
- **Errors:** Sentry. **Metrics and alerts:** Grafana Cloud or Prometheus ([alerts.md](alerts.md)).

## 1. Environments

| | Staging | Production |
|---|---|---|
| Git branch | `main` (every merge) | `production` (fast-forward from `main` to release) |
| Render services | `socialhood-api-staging`, `socialhood-worker-staging` | `socialhood-api`, `socialhood-worker` |
| Render data | `socialhood-db-staging` (Postgres 18), `socialhood-kv-staging` | `socialhood-db`, `socialhood-kv` |
| Vercel | Custom environment `staging` (branch `main`) | Production (branch `production`) |
| Web domain | `staging.socialhood.com` | `app.socialhood.com` |
| API domain | `api.staging.socialhood.com` | `api.socialhood.com` |
| `APP_ENV` | `staging` | `production` (settings refuse fakes, the sandbox and DEBUG) |
| Sandbox platform | on (drills and end-to-end runs) | off (SEC-14) |
| Clerk | development instance, or a second production instance | production instance |
| Dodo | test mode (`DODO_ENVIRONMENT=test`) | live mode (`live`) |
| Meta app | the same app in development mode, or a test app | the live app |
| Sentry `environment` | `staging` | `production` |

Both stacks deploy only after CI passes (`autoDeployTrigger: checksPass`). Releasing is
`git push origin main:production`.

Domains follow OQ-3 (`app.` and `api.`). If the domain changes, change it in
`infra/render.yaml` (config groups), Vercel, and every vendor URL in section 5.

## 2. Accounts and plans [owner account]

1. **Render:** a workspace on the Pro plan or higher (autoscaling, and 7 days of point-in-time
   recovery instead of Hobby's 3; see [backup.md](backup.md)). Connect the GitHub repository.
2. **Vercel:** Pro (Hobby forbids commercial use, §6.4). Import the repository.
3. **Sentry:** Team plan. Create two projects: `socialhood-api` (Python; the API and the worker
   share it, split by the `component` tag) and `socialhood-web` (Next.js). Copy both DSNs. Create
   an auth token with `project:releases` and `org:read` for source maps.
4. **Grafana Cloud** (free tier is enough at launch) or your own Prometheus: [alerts.md](alerts.md).
5. **Domain and DNS:** the company domain, with DNS you can edit.

## 3. Render: create both stacks [owner account]

1. In `infra/render.yaml`, check the domains in the two `*-config` groups (section 1). Commit.
2. Render → **New → Blueprint** → choose the repository → **Blueprint file path**
   `infra/render.yaml` → Apply. Render creates the project `socialhood` with the `production` and
   `staging` environments, both databases, both Key Value instances, the two config groups and the
   four services. The first deploys fail at startup until step 4 is done; that is expected
   (production settings list every missing variable).
3. Plans in the file (check current prices on render.com/pricing before applying):

   | Resource | Production | Staging |
   |---|---|---|
   | API | `1c-2g`, autoscale 1 to 3 at 70% CPU or 80% memory | `0.5c-512mb`, 1 instance |
   | Worker | `1c-2g`, 1 instance (both lanes) | `0.5c-512mb` |
   | Postgres 18 | `1c-4g`, 50 GB | `0.5c-1g`, 10 GB |
   | Key Value | `256mb`, `noeviction` | `256mb` |

   Scaling: add API instances freely (metrics, SSE and rate limits are shared through Valkey). Add
   worker instances when `socialhood_queue_oldest_ready_seconds{lane="interactive"}` stays above
   a few seconds; periodic jobs still run once (TR-JOB-02). Raise
   `WORKER_INTERACTIVE_CONCURRENCY` / `WORKER_BULK_CONCURRENCY` in the config group before adding
   instances.
4. **Secrets group, per environment.** Render cannot keep secrets in a Blueprint-managed group, so
   create them by hand: **Env Groups → New** `socialhood-production-secrets` (and
   `socialhood-staging-secrets`), fill in every variable marked "secrets group" in section 4, then
   open each of the two services of that environment → **Environment → Link environment group**.
   After the next Blueprint sync, check both groups are still linked.
5. Generate the random values locally:

   ```sh
   # METRICS_TOKEN, IG_WEBHOOK_VERIFY_TOKEN, WHATSAPP_WEBHOOK_VERIFY_TOKEN (one each)
   openssl rand -hex 32
   # TOKEN_ENCRYPTION_KEYS (a Fernet key; keep old keys after it, comma-separated, when rotating)
   cd apps/api && uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   # VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY
   npx web-push generate-vapid-keys
   ```

   Staging and production get different values for every secret.
6. **Custom domains:** `socialhood-api` → Settings → Custom Domains → `api.socialhood.com`; add the
   CNAME Render shows to your DNS. Render issues the TLS certificate. Same for
   `api.staging.socialhood.com` on the staging API.
7. **Deploy** each service again (Manual Deploy → Deploy latest commit). The API's pre-deploy
   command runs `alembic upgrade head`, which also creates the `vector`, `pg_trgm` and `pgcrypto`
   extensions and the job queue's tables. Then check:

   ```sh
   curl https://api.socialhood.com/healthz                       # {"status":"ok"}
   curl -H "Authorization: Bearer $METRICS_TOKEN" https://api.socialhood.com/readyz
   curl -o /dev/null -w "%{http_code}\n" https://api.socialhood.com/metrics   # 401 (launch checklist)
   ```

   The worker's log shows both lanes starting and a `ping` job every minute.

Migrations run only in the API's pre-deploy. Both services deploy from the same commit, so a new
worker can start a minute before the API's migration finishes: keep every migration expand-only
(TR-OPS-02; add nullable columns, drop in a later release) and it never matters. If a pre-deploy
fails, Render keeps the previous API version running; the worker may already be on the new code,
which expand-only migrations also make safe.

## 4. Environment variables

Every setting in `apps/api/src/socialhood/settings.py` and every web variable. "Link" means
`infra/render.yaml` wires it from the database or Key Value; "config" means the Blueprint's
`socialhood-<env>-config` group; "secrets" means the hand-made `socialhood-<env>-secrets` group.
API and worker read the same variables.

### API and worker (Render)

| Variable | Where | Secret | Production value / notes |
|---|---|---|---|
| `APP_ENV` | config | no | `production` / `staging` |
| `PYTHON_VERSION` | config | no | `3.13.14` |
| `API_BASE_URL` · `WEB_BASE_URL` | config | no | `https://api.socialhood.com` · `https://app.socialhood.com` |
| `CORS_ALLOWED_ORIGINS` | config | no | the web origin, exact |
| `DATABASE_URL` | link | yes | Render's `postgresql://…`; the API adds the asyncpg driver itself |
| `DATABASE_URL_DIRECT` | link | yes | same database, direct (the queue's LISTEN/NOTIFY, migrations) |
| `REDIS_URL` | link | yes | Key Value, private network |
| `BULK_CONCURRENCY_PER_WORKSPACE` | config | no | `4` |
| `LOG_LEVEL` | config | no | `INFO` (DEBUG refused in production) |
| `SENTRY_DSN` | secrets | no* | `socialhood-api` project DSN; unset = no Sentry |
| `SENTRY_TRACES_SAMPLE_RATE` | config | no | `0.1` (staging `0.5`) |
| `SENTRY_RELEASE` | automatic | no | defaults to Render's `RENDER_GIT_COMMIT` |
| `METRICS_TOKEN` | secrets | yes | random; guards `/metrics` and `/readyz` |
| `CLERK_SECRET_KEY` | secrets | yes | Clerk → API keys |
| `CLERK_JWT_KEY` | secrets | no* | Clerk → API keys → PEM public key (one line, `\n` allowed) |
| `CLERK_ISSUER` | secrets | no* | Clerk Frontend API URL, e.g. `https://clerk.socialhood.com` |
| `CLERK_AUTHORIZED_PARTIES` | config | no | the web origin |
| `CLERK_WEBHOOK_SECRET` | secrets | yes | Clerk → Webhooks → signing secret (`whsec_…`) |
| `TOKEN_ENCRYPTION_KEYS` | secrets | yes | Fernet keys, newest first |
| `IG_APP_ID` · `IG_APP_SECRET` | secrets | secret: yes | Meta app → Instagram → API setup with Instagram login |
| `IG_REDIRECT_URI` | config | no | `https://api.socialhood.com/v1/oauth/instagram/callback` |
| `IG_WEBHOOK_VERIFY_TOKEN` | secrets | yes | random; also typed into Meta's webhook form |
| `IG_GRAPH_VERSION` · `META_GRAPH_VERSION` | config | no | `v25.0` |
| `IG_REQUEST_INSIGHTS_SCOPE` · `IG_HUMAN_AGENT_ENABLED` | config | no | `false` until Meta approves |
| `META_APP_ID` · `META_APP_SECRET` | secrets | secret: yes | Meta app → Settings → Basic |
| `WHATSAPP_CONFIG_ID` | secrets | no* | Embedded Signup configuration id |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | secrets | yes | random; also typed into Meta |
| `GEMINI_API_KEY` | secrets | yes | paid, billing-enabled key (§6.4) |
| `AI_PROVIDER` | default | no | `gemini`; never `fake` outside local |
| `AI_MODEL_ANALYSIS` · `AI_MODEL_REPLY` · `AI_MODEL_REPLY_COMPLEX` · `AI_MODEL_EMBED` · `AI_MODEL_AGENT` · `AI_EMBED_DIM` · `AI_THINKING_LEVELS` | default | no | defaults in settings.py; set in config only to override |
| `AI_DAILY_SPEND_LIMIT_USD` | config | no | `100` (staging `10`) |
| `AI_RETRIEVAL_MIN_SIM` · `AUTO_MIN_CONFIDENCE` | default | no | `0.60` · `0.75`, tuned by eval |
| `CLOUDINARY_CLOUD_NAME` · `CLOUDINARY_API_KEY` | secrets | no* | Cloudinary console |
| `CLOUDINARY_API_SECRET` | secrets | yes | Cloudinary console |
| `DODO_API_KEY` · `DODO_WEBHOOK_SECRET` | secrets | yes | Dodo dashboard (live keys in production) |
| `DODO_ENVIRONMENT` | config | no | `live` / `test` |
| `DODO_PRODUCT_PRO_MONTHLY` · `DODO_PRODUCT_MAX_MONTHLY` | secrets | no* | product ids (Max in R2) |
| `DODO_PROVIDER` · `EMAIL_PROVIDER` · `PUSH_PROVIDER` | default | no | real providers; `fake` refused in production |
| `RESEND_API_KEY` | secrets | yes | Resend → API keys (sending access, one domain) |
| `EMAIL_FROM` | config | no | `Social Hood <hello@socialhood.com>` |
| `VAPID_PUBLIC_KEY` | secrets | no | from `web-push generate-vapid-keys` |
| `VAPID_PRIVATE_KEY` | secrets | yes | same pair |
| `VAPID_SUBJECT` | config | no | `mailto:support@socialhood.com` |
| `SANDBOX_PLATFORM_ENABLED` | config | no | `false` (production refuses `true`) |
| `CLIENT_IP_HEADER` | config | no | `x-forwarded-for` (required in production; see "Client IP" below) |
| `RATE_LIMITS_ENABLED` | default | no | `true` (production refuses `false`) |
| `WORKER_INTERACTIVE_CONCURRENCY` · `WORKER_BULK_CONCURRENCY` | config | no | `20` · `8` (worker only) |

\* Not secret, but specific to one vendor account and environment, so it lives with the secrets.

**Client IP (per-IP rate limits).** Render documents only `X-Forwarded-For` for the caller's
address (render.com/articles/how-render-handles-ddos-attacks); `True-Client-IP` and
`CF-Connecting-IP` are Cloudflare headers Render does not promise to pass. A client can send its
own `X-Forwarded-For`, which stays on the left, so its first entry is never used. With
`CLIENT_IP_HEADER=x-forwarded-for` the API reads the list from the right and takes the first
entry that is not a proxy: Cloudflare's published ranges and the private ranges Render's load
balancers use (`apps/api/src/socialhood/security/client_ip.py`; update `CLOUDFLARE_RANGES` there
if https://www.cloudflare.com/ips/ changes). The start command's `--proxy-headers
--forwarded-allow-ips="*"` only gives the app the https scheme; the address uvicorn derives from
the header's first entry is not used for anything. `--no-server-header` drops `server: uvicorn`
(SEC-11).

### Web (Vercel → Settings → Environment Variables, per environment)

| Variable | Secret | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | no | `https://api.socialhood.com` (staging: `https://api.staging.socialhood.com`) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | no | Clerk → API keys |
| `CLERK_SECRET_KEY` | yes (Sensitive) | same instance as the API's |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` · `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | no | `/sign-in` · `/sign-up` |
| `NEXT_PUBLIC_META_APP_ID` · `NEXT_PUBLIC_WHATSAPP_CONFIG_ID` | no | same values as the API's `META_APP_ID`, `WHATSAPP_CONFIG_ID` |
| `NEXT_PUBLIC_SENTRY_DSN` | no | `socialhood-web` project DSN; unset = no Sentry |
| `NEXT_PUBLIC_SENTRY_ENVIRONMENT` | no | `production` / `staging` |
| `NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE` | no | `0.1` |
| `SENTRY_AUTH_TOKEN` | yes (Sensitive, build only) | uploads source maps; unset = no upload |
| `SENTRY_ORG` · `SENTRY_PROJECT` | no (build only) | your org slug, `socialhood-web` |
| `NEXT_PUBLIC_ENABLE_SW` | no | leave unset (the service worker is on in production builds) |

The VAPID public key reaches the browser from the API (`GET /v1/push/config`, C-049), so the web
app has no VAPID variable.

## 5. Vercel [owner account]

1. **Add New → Project** → the repository → **Root Directory** `apps/web`. Framework, install
   and build commands come from `apps/web/vercel.json` (`pnpm install --frozen-lockfile`,
   `pnpm build`); keep "Include files outside the root directory" on (the workspace packages).
   Node.js 24.
2. Functions region: `sin1` (Singapore, next to the API; set in `vercel.json`).
3. **Settings → Git:** production branch `production`. **Settings → Environments → Create
   environment** `staging`, tracking branch `main` (Pro plan). Pull requests get preview
   deployments; point previews at the staging API.
4. Environment variables from section 4, separately for Production and staging.
5. **Domains:** `app.socialhood.com` → Production; `staging.socialhood.com` → staging. Add the
   records Vercel shows (CNAME `cname.vercel-dns.com`, or A for an apex).
6. Deploy, then open the site and sign in.
7. Security headers and the CSP are in `next.config.ts` (SEC-11). The CSP's `connect-src` must
   allow the Sentry ingest host from your DSN (for example `https://*.ingest.us.sentry.io`), or
   browser errors never arrive.

## 6. Vendor URLs to set per environment [owner account]

Replace `{API}` and `{WEB}` with the environment's domains.

| Vendor | Setting | Value |
|---|---|---|
| Meta (Instagram login) | Valid OAuth redirect URI | `{API}/v1/oauth/instagram/callback` |
| Meta (Instagram) | Webhook callback URL · verify token | `{API}/webhooks/instagram` · `IG_WEBHOOK_VERIFY_TOKEN`; fields `messages`, `messaging_seen`, `message_reactions`, `message_edit`, `comments` (the API re-subscribes accounts to these every 6 hours) |
| Meta (WhatsApp) | Webhook callback URL · verify token | `{API}/webhooks/whatsapp` · `WHATSAPP_WEBHOOK_VERIFY_TOKEN` |
| Meta | Deauthorize callback URL | `{API}/webhooks/meta/deauthorize` |
| Meta | Data deletion request URL | `{API}/webhooks/meta/data-deletion` |
| Meta | Privacy policy, terms, app domains | `{WEB}` pages; app domain = the web domain |
| Meta (WhatsApp Embedded Signup) | Allowed domains for the JS SDK | `{WEB}` |
| Clerk | Domain (production instance) | the company domain; add Clerk's DNS records (Frontend API, accounts, email DKIM) |
| Clerk | Allowed origins / redirect URLs | `{WEB}` |
| Clerk | Webhook endpoint | `{API}/webhooks/clerk`, events `user.updated` and `user.deleted` (copy the signing secret) |
| Clerk | Google OAuth | your own Google OAuth client in production |
| Dodo | Webhook endpoint | `{API}/webhooks/dodo` (copy the secret) |
| Dodo | Products | the Pro (and later Max) monthly products; ids into the secrets group |
| Dodo | Return URL | built by the API from `WEB_BASE_URL` (`/w/{slug}/settings/billing`) |
| Resend | Sending domain | verify the `EMAIL_FROM` domain: SPF, DKIM and DMARC records |
| Cloudinary | nothing per environment | one cloud per environment is simplest |
| Sentry | Allowed domains (web project) | `{WEB}` |

## 7. First-deploy checklist

Staging first, then production. Tick each line.

- [ ] Staging and production stacks created from `infra/render.yaml`; plans checked.
- [ ] Both secrets groups created, filled and linked to both services of their environment.
- [ ] `api.` and `app.` domains (and the staging pair) resolve, with TLS.
- [ ] API pre-deploy ran `alembic upgrade head`; `/healthz` is `{"status":"ok"}`; `/readyz` with
      the token is `ready`.
- [ ] `/metrics` returns 401 without the token and metrics with it (launch checklist).
- [ ] No `server` header: `curl -sI https://api.staging.socialhood.com/healthz | grep -i ^server`
      shows nothing (or only Cloudflare's `server: cloudflare`).
- [ ] The per-IP limit keys on the real client, not on a forged `X-Forwarded-For`: from one
      machine, 61 requests to `/v1/billing/plans`, each with a different forged header, and the
      61st is 429:

      ```sh
      for i in $(seq 1 61); do
        curl -s -o /dev/null -w "%{http_code}\n" -H "X-Forwarded-For: 198.51.100.$i" \
          https://api.staging.socialhood.com/v1/billing/plans
      done | sort | uniq -c    # 60 × 200 and 1 × 429
      ```

      If every request is 200, Render's `X-Forwarded-For` doesn't have the layout described
      under "Client IP" (section 4): fix `security/client_ip.py` before launch.
- [ ] Worker log shows both lanes and the `ping` job every minute.
- [ ] Vercel production and staging deploy; sign-in works; the web talks to the right API.
- [ ] Sentry: a test error from each of API, worker and web arrives, tagged with the environment
      and release, with no headers, emails or message text ([alerts.md](alerts.md), section 4).
- [ ] Grafana Cloud scrapes `/metrics`; the dashboard is imported; alert rules loaded.
- [ ] Every alert drill in [alerts.md](alerts.md) fired in staging and resolved.
- [ ] Vendor URLs in section 6 set for staging; Meta's test webhook deliveries succeed.
- [ ] Staging runs a full F-13 against a test Instagram account (T9.5).
- [ ] Point-in-time recovery shows on the production database; restore rehearsed
      ([backup.md](backup.md)).
- [ ] Production settings validation passes (the API starts); `SANDBOX_PLATFORM_ENABLED=false`.
- [ ] Vendor URLs set for production; App switched to Live mode (§6.4).

## 8. Everyday releases

1. Merge to `main`: CI runs, then staging deploys (API migrates first).
2. Check staging: the dashboard, Sentry, a quick run of the main flows.
3. `git push origin main:production`: production deploys the same commit after CI.
4. Watch the dashboard and Sentry for 15 minutes. To roll back, Render → the service → Events →
   pick the previous deploy → **Rollback** (and the same in Vercel). Migrations are expand-only,
   so the previous code runs on the new schema.

If the Python build fails on Render's native uv support, use `pip install uv && uv sync --locked
--no-dev` as the build command (uv then stays on the path for the start commands).
