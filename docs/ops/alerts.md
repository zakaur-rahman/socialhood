# Alerts (T9.3)

T9.3 asks for four alerts: dispatcher lag over 2 minutes, webhook failures over 1%, send failures
over 5%, and AI errors over 5%. It is done when a forced failure triggers its alert. This page
covers where the alerts live, how to set them up, how to force each failure in staging, and the
results recorded so far.

## 1. Where alerts live

| Source | What it alerts on | Defined in |
|---|---|---|
| Prometheus rules (Grafana Cloud or Prometheus) | The four T9.3 alerts, plus worker down, interactive backlog (TR-JOB-06), failed jobs, API 5xx, and scrape health | [`infra/prometheus/alerts.yml`](../../infra/prometheus/alerts.yml) |
| Sentry, API project | Errors in the API and the worker (with `job`, `lane` and `workspace_id` tags); the worker's log alerts: webhook health (TR-WH-08) and failed work (TR-OPS-04) | Code, plus the rules in section 4 |
| Sentry, web project | Browser and server errors in the web app | Code, plus the rules in section 4 |

| Alert | Rule | Severity |
|---|---|---|
| `DispatcherLag` | `max by (kind) (socialhood_dispatcher_lag_seconds) > 120` for 1 min | critical |
| `WebhookFailures` | non-accepted ÷ all webhook POSTs over 5 min > 1% for 5 min, per provider, with at least 10 deliveries | critical |
| `SendFailures` | failed ÷ all sends over 15 min > 5% for 5 min, per platform, with at least 10 sends | critical |
| `AIErrors` | non-ok ÷ all AI calls over 15 min > 5% for 5 min, with at least 10 calls | critical |
| `WorkerDown` | no `ping` job run in 10 min, for 5 min | critical |
| `MetricsScrapeDown` | `up{job="socialhood-api"} == 0` for 5 min | critical |
| `InteractiveQueueBacklog` | oldest ready interactive job > 30 s for 2 min | warning |
| `FailedJobs` | more than 20 failed jobs in an hour | warning |
| `ApiServerErrors` | 5xx > 1% over 10 min, with at least 50 requests | warning |
| `MetricsCollectorFailing` | a scrape-time gauge query failing for 10 min | warning |

What each metric means, and how the worker's counts reach `/metrics` through Valkey, is in
[dashboards.md](dashboards.md). What to do when an alert fires is in [runbook.md](runbook.md).

## 2. Grafana Cloud setup [owner account]

Grafana Cloud's free tier (10k series, 14 days) covers launch. Any Prometheus 2.x or 3.x also
works, using [`infra/prometheus/prometheus.yml`](../../infra/prometheus/prometheus.yml).

1. Create a Grafana Cloud stack in the Singapore region.
2. **Scrape the API:** Connections → Add new connection → **Metrics Endpoint**. Scrape job name
   `socialhood-api` (the `MetricsScrapeDown` rule matches on it), URL
   `https://api.socialhood.com/metrics`, interval 60 s, authentication **Bearer** with the
   production `METRICS_TOKEN`. Add a second job, `socialhood-api-staging`, for staging (then use
   `job=~"socialhood-api.*"` in `MetricsScrapeDown`).
3. **Load the rules** with `mimirtool` (Stack → Prometheus → details give the URL, instance id and
   an API token with `rules:write`):

   ```sh
   mimirtool rules load infra/prometheus/alerts.yml \
     --address=https://prometheus-prod-XX-prod-ap-southeast-1.grafana.net/api/prom \
     --id=<instance id> --key=<token>
   ```

   The rules then appear under Alerting → Alert rules as data-source-managed rules.
4. **Contact points:** create `owner-email` (email) and `owner-phone`. For the phone, use Grafana
   IRM's mobile app, or SMS via a PagerDuty or Opsgenie integration.
5. **Notification policy:** `severity=critical` → `owner-email` and `owner-phone`, repeat every 4 h;
   `severity=warning` → `owner-email`, repeat every 12 h.
6. **Dashboard:** Dashboards → New → Import → upload
   [`infra/grafana/socialhood-overview.json`](../../infra/grafana/socialhood-overview.json) and
   choose the Prometheus data source.

## 3. Proving the rules without a deploy

`infra/prometheus/alerts.test.yml` feeds each rule the series a forced failure produces: quiet
first, then broken. Run it after any change to the rules:

```sh
docker run --rm -v "$PWD/infra/prometheus:/rules" -w /rules --entrypoint promtool \
  prom/prometheus:latest test rules alerts.test.yml
# Windows Git Bash: prefix with MSYS_NO_PATHCONV=1 and use the full Windows path for -v
```

The `ops` GitHub workflow runs the same check when `infra/prometheus/` changes.

## 4. Sentry setup [owner account]

1. Create the projects `socialhood-api` (Python) and `socialhood-web` (Next.js). Put the DSNs in
   `SENTRY_DSN` (Render secrets groups) and `NEXT_PUBLIC_SENTRY_DSN` (Vercel). No DSN means no
   Sentry: local runs and tests send nothing.
2. **Data scrubbing:** keep Sentry's server-side scrubbing on (Settings → Security & Privacy → Data
   Scrubber, "Prevent storing of IP addresses"). The SDKs already strip headers, cookies, bodies,
   query strings, emails, tokens and message text before sending (SEC-12;
   `observability/sentry.py`, `apps/web/src/lib/sentry/scrub.ts`).
3. **Alert rules**, all filtered to `environment:production` (make a copy for staging, email only):
   - **New or regressed issue** in either project → owner email and mobile push (the Sentry mobile
     app), immediately.
   - **Log alerts** (API project): "a new event is seen" where the tag `alert_kind` is set →
     email and push. These are the worker's webhook-health check (TR-WH-08: over 1% failed
     deliveries in 5 minutes, or an hour of silence while accounts are connected) and the
     failed-work check (TR-OPS-04: more than 20 failed events or jobs in an hour).
   - **Publishing failures** (API project): tag `job:publish_target` → email and push
     (TR-OPS-04: any `publish_target` failure other than a platform rejection).
   - **Error spike** (metric alert, API project): more than 20 errors in 5 minutes → email and push.
4. **Check each source once:** raise a test error in staging and confirm it arrives with the
   `environment`, `release` and `component` (`api` or `worker`) tags, and with no request headers,
   emails or message text.
   - API: from the staging API's Render shell,
     `uv run --no-sync python -c "import sentry_sdk; from socialhood.settings import get_settings; from socialhood.observability.sentry import init_sentry; init_sentry(get_settings(), component='api'); sentry_sdk.capture_message('staging test'); sentry_sdk.flush()"`.
   - Worker: the webhook drill below raises a `webhook_health` alert event from the worker.
   - Web: in the browser console on staging, `setTimeout(() => { throw new Error("staging test") })`.

Sentry cannot compute the Prometheus ratios, so the four T9.3 alerts live in Grafana. The webhook
failure alert also exists in Sentry through the worker's webhook-health log alert.

## 5. Forcing each failure in staging

Run these against staging only. Each drill says what to break, what fires, and how to undo it.
Record the date and result in section 6.

### Dispatcher lag (`DispatcherLag`)

1. In the staging app, schedule a message in any conversation for two minutes from now.
2. Render → `socialhood-worker-staging` → **Suspend**.
3. About four minutes after the message was due, `DispatcherLag{kind="message"}` fires
   (lag above 120 s, held for 1 minute). Staying suspended for 15 minutes also fires `WorkerDown`.
4. **Resume** the worker. The dispatcher sends the message on its next tick and the alert resolves.

### Webhook failures (`WebhookFailures`, plus the Sentry webhook-health alert)

Unsigned deliveries are rejected with 401 and counted as `signature_invalid`:

```sh
for i in $(seq 1 120); do
  curl -s -o /dev/null -w "%{http_code} " -X POST https://api.staging.socialhood.com/webhooks/instagram \
    -H "Content-Type: application/json" -d '{"object":"instagram","entry":[]}'
  sleep 5
done
```

After about six minutes `WebhookFailures{provider="instagram"}` fires; within five minutes the
worker's `check_webhook_health` also raises an `alert_kind:webhook_health` event in Sentry. This is
the launch checklist's "break the staging endpoint for 10 minutes". Stop the loop, and both clear.

### Send failures (`SendFailures`)

Staging runs with `SANDBOX_PLATFORM_ENABLED=true`, whose account fails any send containing
`[sandbox:fail=<code>]`:

1. Settings → Connections → **Add sandbox account**; create a conversation with
   `POST /v1/w/{wid}/dev/sandbox/inbound` (or the dev panel).
2. In that conversation send 12 replies within 15 minutes, 10 of them containing
   `[sandbox:fail=platform_rejected]`.
3. Five minutes later `SendFailures{platform=...}` fires. The failed bubbles show in the inbox.
   Nothing to undo; the ratio falls back as normal sends continue (or wait 15 minutes).

### AI errors (`AIErrors`)

1. Render → Env Groups → `socialhood-staging-config` → add
   `AI_MODEL_ANALYSIS=gemini-does-not-exist` → Save (the services redeploy).
2. Send 12 inbound DMs through the sandbox, from different contacts or at least 5 seconds apart
   (analysis is debounced per conversation). Each analysis call fails with a provider error.
3. Five minutes later `AIErrors` fires.
4. Delete the variable (the next Blueprint sync would also remove it). The alert resolves after
   the 15-minute window passes.

## 6. Results

### Rule tests (promtool), 30 Sep 2026

`promtool check rules`: 10 rules, success. `promtool test rules alerts.test.yml`: success. Each of
`DispatcherLag`, `WebhookFailures`, `SendFailures`, `AIErrors`, `WorkerDown` and
`InteractiveQueueBacklog` stays quiet on normal traffic and fires on its failure. The volume floor
keeps a single failed Clerk delivery from firing.

### Local end-to-end drill, 30 Sep 2026

This was a real Prometheus (`prom/prometheus:latest`, 15 s scrape and evaluation) scraping a
locally running API (`/metrics` with the bearer token) on the test database, with the rules
above. No worker was running.

| Forced failure | Alert | Pending at | Firing at |
|---|---|---|---|
| A scheduled message 3 minutes overdue, with no worker to dispatch it | `DispatcherLag{kind="message"}` | 05:25:49 UTC | by 05:28:29 (lag 363 s) |
| One unsigned `POST /webhooks/instagram` every 3 s (401 → `signature_invalid`) | `WebhookFailures{provider="instagram"}` | 05:26:34 | by 05:35:11 |
| No worker running | `WorkerDown` | 05:24:35 | by 05:30:32 |

`/metrics` returned 401 without the token. Every dashboard query parsed and returned data.
Integration tests move the send and AI metrics the same way (`tests/integration/test_observability.py`:
a sandbox send with `[sandbox:fail=platform_rejected]`, and a metered AI call that fails). The
staging drills in section 5 are still to be run by the owner once staging is deployed.

### Staging drills

| Date | Drill | Fired? | Resolved? | By |
|---|---|---|---|---|
| | Dispatcher lag | | | |
| | Webhook failures (10 minutes) | | | |
| | Send failures | | | |
| | AI errors | | | |
| | Sentry test events (API, worker, web) | | | |
