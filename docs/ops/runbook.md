# Runbook

What to do when an alert fires. Alerts, dashboards and drills: [alerts.md](alerts.md) and
[dashboards.md](dashboards.md). Deploys and rollbacks: [deploy.md](deploy.md). Restores:
[backup.md](backup.md).

First steps for any alert:

1. Open the dashboard (Grafana → Social Hood overview) and Sentry, filtered to the environment.
2. Check Render: are `socialhood-api` and `socialhood-worker` live, and did a deploy just happen?
   If a deploy caused it, roll back (Render → service → Events → Rollback) and investigate after.
3. Logs are JSON with `request_id`, `workspace_id`, `user_id` and `job`; Sentry events carry the
   same ids as tags. Search Render logs by `request_id` from a Sentry event.

Failed webhook events and jobs are listed and replayed with the ops CLI, from a Render shell on the
worker (TR-OPS-04):

```sh
uv run --no-sync python -m socialhood.ops failed-events list --since 2h
uv run --no-sync python -m socialhood.ops failed-events replay --since 2h --dry-run
uv run --no-sync python -m socialhood.ops failed-jobs list --since 2h
uv run --no-sync python -m socialhood.ops failed-jobs retry --task analyze_comments --since 2h --dry-run
```

The CLI never retries a send that ended `delivery_unknown` (TR-JOB-05).

## Dispatcher lag

Scheduled messages or posts are more than 2 minutes late.

- `WorkerDown` also firing: see [Worker down](#worker-down).
- The worker is up but the interactive lane is backed up (`socialhood_queue_oldest_ready_seconds`):
  see [Queue backlog](#queue-backlog). `dispatch_due` runs on that lane.
- Otherwise look for `dispatch_due` failures in Sentry (tag `job:dispatch_due`), and at Postgres
  health in Render (locks, CPU, connections).
- Late rows go out on the next successful tick; nothing needs replaying. `sweep_stuck` returns rows
  stuck in `sending` or `publishing` for 10 minutes to their due state.

## Webhook failures

Over 1% of a provider's webhook deliveries are not 2xx. Meta disables the webhook after about an
hour of failures and unsubscribes the account (TR-WH-08), so act within minutes.

- `outcome="signature_invalid"`: the app secret changed or does not match (`IG_APP_SECRET`,
  `META_APP_SECRET`, `CLERK_WEBHOOK_SECRET`, `DODO_WEBHOOK_SECRET`), or someone is sending forged
  requests (then it is noise, but check the source).
- `outcome="error"` (5xx): the API cannot store events; check Postgres and Sentry for the
  exception.
- After a fix, `reconcile_subscriptions` re-subscribes every connected account every 6 hours. To
  heal sooner, queue it now from a worker shell:
  `uv run --no-sync procrastinate --app=socialhood.jobs.app.app defer reconcile_subscriptions '{"timestamp": 0}'`.
  `sync_media` backfills missed comments.
- If Meta already disabled the webhook, re-enable it in the Meta app dashboard (Webhooks) and check
  a test delivery.

## Send failures

Over 5% of outbound DMs failed. The dashboard's "Send failures by code" says why:

- `reply_window_closed`: customers answered outside the 24-hour window; usually product behaviour,
  not an outage.
- `account_needs_reconnect`: tokens revoked or expired; the owners were notified in the app.
- `platform_rate_limited`, `platform_unavailable`: Meta is limiting or down; check Meta's status
  page. Retries handle short outages.
- `delivery_unknown`: timeouts after the request was sent; users retry these by hand.
- Many `platform_rejected`: read the platform error in Sentry or the logs (`send_message_failed`,
  with `platform_code`).

## AI errors

Over 5% of AI calls failed (analysis, suggestions, summaries, captions, knowledge, Ask).

- Check the Gemini status page and the Google AI console for quota or billing problems.
- A model id in `AI_MODEL_*` may be wrong or retired: check the config group.
- Timeouts retry once (TR-AI-03); credits for failed calls are refunded (TR-AI-09).
- If Gemini is down for long, suggestions and auto replies stop; manual messaging keeps working.
  Nothing to replay: new messages are analysed as they arrive, and `failed-jobs retry --task
  analyze_conversation` catches up on the failed ones.

## Worker down

No `ping` job ran for 10 minutes.

- Render → `socialhood-worker` → Logs. `scripts/worker.sh` exits when either lane dies, and Render
  restarts the service; a crash loop shows the error at startup (often settings validation, which
  lists every missing variable, or the database being unreachable).
- Check `DATABASE_URL_DIRECT` reaches Postgres directly (the queue needs LISTEN/NOTIFY).
- When it is back, due work runs by itself: the dispatcher catches up, and `sweep_stuck` requeues
  webhook events still `received`.

## Queue backlog

The interactive lane's oldest ready job is older than 30 seconds (TR-JOB-06).

- `socialhood_queue_running_jobs{lane="interactive"}` at the concurrency limit: raise
  `WORKER_INTERACTIVE_CONCURRENCY` in the config group, or add a worker instance.
- A slow task: check "Job p95 duration by task" and "Platform call errors by endpoint".
- Bulk work never blocks this lane (separate process), so a bulk backlog alone is not urgent.

## Failed jobs

More than 20 jobs failed in the last hour. See which tasks in the dashboard ("Failed jobs by task")
and Sentry (tag `job`), fix the cause, then `failed-jobs retry` with `--dry-run` first.

## Billing alerts (Sentry)

- `alert_kind:billing_orphan_subscription`: Dodo reported a live subscription whose workspace was
  deleted (usually a checkout paid after the deletion). The worker cancels it at once
  (`cancel_orphan_subscription`, retried for about 25 minutes while Dodo fails). Check in Dodo's
  dashboard that it shows cancelled; if the job failed for good (Sentry, tag
  `job:cancel_orphan_subscription`), cancel it there by hand, and refund the charge if the
  customer asks.
- `alert_kind:billing_duplicate_subscription`: two checkouts completed at once; the workspace
  keeps the first. Cancel and refund the other one in Dodo's dashboard.

## API errors

Over 1% of API requests return 5xx. Sentry has each exception with the route and request id. If it
started with a deploy, roll back.

## Metrics

`MetricsScrapeDown` or `MetricsCollectorFailing`: the scrape itself is failing.

- 401: `METRICS_TOKEN` changed; update the scrape job's bearer token.
- 5xx or timeout: the API is down, or Valkey is unreachable (the registry lives there).
- `socialhood_collector_up{collector="queue"|"dispatcher"} == 0`: the gauge queries fail or time
  out (2 s limit); check Postgres. `collector="sse"` needs Valkey's `CLIENT LIST`.

Counters restart from zero when Valkey restarts; the graphs show a reset, and alerts are unaffected.
