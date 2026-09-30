# Metrics and dashboards (T9.3, TR-OPS-01)

## How metrics are collected

The API exposes Prometheus text format at `GET /metrics`. It needs
`Authorization: Bearer {METRICS_TOKEN}`, compared in constant time. Without a configured token
the route returns 404; with a missing or wrong token it returns 401 (SEC-12).

The worker has no endpoint of its own. On Render a background worker takes no inbound traffic, and
the API can run several instances, so per-process scraping would not work. Instead there is one
shared registry:

1. Every process (each API instance, both worker lanes) adds its counts to an in-memory buffer.
   Recording is a dictionary update, with no I/O on the request or job path.
2. A background task folds the buffer into Valkey hashes (`metrics:<name>`) every 5 seconds, with
   `HINCRBYFLOAT` in one MULTI. The API starts it in its lifespan; the worker starts it on its
   first job. A failed flush keeps the counts for the next one.
3. `/metrics` flushes its own instance's buffer, reads the hashes, and adds gauges computed at
   scrape time from Postgres and Valkey. Any API instance serves the same totals.

Counters count up from the last Valkey restart; Prometheus's `rate()` and `increase()` treat a
restart as a counter reset, so Valkey still holds nothing that must survive one (the stack
table's "non-durable roles only"). Labels
come from code (route templates, task names, error codes, feature names), never from ids or user
input, so the number of series stays bounded (about 3 to 6 thousand at launch).

Code: `apps/api/src/socialhood/observability/` (`metrics.py` holds the registry and the counters,
`gauges.py` the scrape-time gauges, `http.py` the middleware and `/metrics`, `jobs.py` the worker
middleware). Tests: `tests/unit/test_metrics.py` and `tests/integration/test_observability.py`.

## The metrics

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `socialhood_http_requests_total` | counter | `method`, `route`, `status` | Requests by route template (`unmatched` for 404s) |
| `socialhood_http_request_duration_seconds` | histogram | `method`, `route` | Latency, 5 ms to 10 s buckets |
| `socialhood_webhook_deliveries_total` | counter | `provider`, `outcome` | Webhook POSTs: `accepted` (2xx), `signature_invalid` (401), `rejected` (other 4xx), `error` (5xx) |
| `socialhood_job_runs_total` | counter | `task`, `lane`, `status` | Job runs: `succeeded`, `retry`, `failed` (final), `aborted` |
| `socialhood_job_duration_seconds` | histogram | `task`, `lane`, `status` | Job run time, 10 ms to 10 min buckets |
| `socialhood_sends_total` | counter | `platform`, `outcome`, `code` | Outbound DMs that ended `sent` or `failed` (with the error code, including `delivery_unknown`) |
| `socialhood_platform_calls_total` | counter | `platform`, `endpoint`, `outcome` | Every platform API call by endpoint name: `ok`, `timeout`, `network`, or the mapped error code |
| `socialhood_ai_calls_total` | counter | `feature`, `model`, `outcome` | Metered AI calls: `ok`, `error`, `timeout` |
| `socialhood_ai_tokens_total` | counter | `feature`, `model`, `direction` | Input and output tokens |
| `socialhood_dispatcher_lag_seconds` | gauge | `kind` (`message`, `post`) | How late the oldest due scheduled message or post is (0 when none) |
| `socialhood_queue_ready_jobs` | gauge | `lane` | Jobs ready to run now (queue depth) |
| `socialhood_queue_scheduled_jobs` | gauge | `lane` | Jobs waiting for a later time (delays, retries) |
| `socialhood_queue_running_jobs` | gauge | `lane` | Jobs running |
| `socialhood_queue_oldest_ready_seconds` | gauge | `lane` | Age of the oldest ready job (TR-JOB-06) |
| `socialhood_sse_connections` | gauge | | Open SSE streams (Valkey clients named `sse:*`) |
| `socialhood_collector_up` | gauge | `collector` | 1 when a scrape-time gauge query worked |
| `socialhood_build_info` | gauge | `version`, `environment` | Always 1 |

Also in TR-OPS-01 but not exported yet: token-bucket waits by account and bucket (they would need
a label per account; the platform-call metric shows `platform_rate_limited` by endpoint instead),
and AI spend against `AI_DAILY_SPEND_LIMIT_USD` (the global spend guard is not built; token counts
per model are exported so spend can be derived once prices are fixed).

## Dashboard

[`infra/grafana/socialhood-overview.json`](../../infra/grafana/socialhood-overview.json), imported
as described in [alerts.md](alerts.md), section 2. Rows:

- **Customer promises:** dispatcher lag, and the webhook, send and AI failure ratios, each with its
  alert threshold in the title; webhook deliveries by outcome; send failures by code.
- **Queue and worker:** ready, running and later jobs per lane; the oldest ready job; job runs by
  status; failed jobs by task; p95 job time by task.
- **API:** requests by status; p95 latency for the top 10 routes (the SSE route is left out: its
  requests last minutes); open SSE connections.
- **Platforms and AI:** platform call errors by endpoint; AI calls by feature and outcome; AI tokens
  per hour by model; scrape health.

Every query was checked against a live Prometheus. Useful ad-hoc queries:

```promql
# API p95 by route over the last hour (SLO: 300 ms reads, 500 ms writes, TR §2.13)
histogram_quantile(0.95, sum by (route, le) (rate(socialhood_http_request_duration_seconds_bucket[1h])))
# Webhook acknowledgement p99 (SLO 500 ms)
histogram_quantile(0.99, sum by (le) (rate(socialhood_http_request_duration_seconds_bucket{route=~"/webhooks/.*",method="POST"}[1h])))
# Which platform endpoints are rate limited
sum by (endpoint) (increase(socialhood_platform_calls_total{outcome="platform_rate_limited"}[1h]))
```

Render's own dashboard adds CPU, memory, and Postgres and Key Value usage per service. Sentry adds
traces at `SENTRY_TRACES_SAMPLE_RATE` (API requests and one transaction per job).
