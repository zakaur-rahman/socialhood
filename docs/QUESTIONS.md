# Questions

Decisions made while building that the spec did not settle. Each has the choice in the code;
answer to confirm or change it.

## Q-001 · Error codes beyond TR-API-03
TR-API-03 lists no code for some plain HTTP cases. Added to `errors.py`: `bad_request` 400,
`method_not_allowed` 405, `payload_too_large` 413, `service_unavailable` 503 (used by `/readyz`).
Add them to the spec's list?

## Q-002 · How `/readyz` stays private
SEC-12 says `/readyz` "is not exposed publicly". Outside local and test environments it requires
`Authorization: Bearer {METRICS_TOKEN}` and answers 404 otherwise. Render's health check uses
`/healthz`, which stays public.

## Q-003 · Which log keys count as secrets
SEC-07 redacts keys matching `token|secret|authorization|password|signature|code`. Taken
literally, `code` would also hide `status_code` and `error_code`, which logs need. The processor
redacts `code` and any `*_code` key except `status_code`, `error_code`, `platform_code` and
`http_status_code`.

## Q-004 · Python dependency audit severity
SEC-13 fails the build on high or critical findings. PyPI advisories carry no severity, so
`pip-audit` in CI fails on any known vulnerability. `pnpm audit` uses `--audit-level high`.

## Q-005 · Spec format in `docs/`
T0.1 asks for the spec as markdown. It is kept as the three HTML files in `docs/`, which are the
source of truth and are corrected in place (see CONFLICTS.md). Convert later if a markdown copy
is wanted for agents.

## Q-006 · Local development on Windows
Async psycopg (the job queue) cannot use Windows' default Proactor event loop. Migrations and the
test suite switch to the selector loop on Windows, and Procrastinate's CLI does the same, so the
worker runs. `scripts/worker.sh` targets Linux (Render); on Windows run one worker with
`uv run procrastinate --app=socialhood.jobs.app.app worker`. The API defers jobs too, so on
Windows start uvicorn with `--loop asyncio:SelectorEventLoop`. Production is unaffected.

## Q-007 · Response shapes for Me, workspaces and overview
§5.10 defines no shapes for these. The API returns `Me` (id, email, name, avatar_url,
last_workspace_id, workspaces[]), `WorkspaceSummary` (id, name, slug, timezone, role, plan),
`WorkspaceOut` (adds reply_language, status, automation_disclosure, checklist_dismissed_at,
created_at) and `Overview` (range, checklist {dismissed, completed, steps[{key, done}]}); the
metrics join `Overview` in T9.1. Add them to §5.10?

## Q-008 · Checklist steps before their data exists
FR-ACC-04 computes each step from data. Only the dismiss state has data in P1; the steps report
not done until their tables arrive: connect_account (T2.2), create_automation (T4.1),
add_knowledge (T5.x). "Choose an AI mode" needs a definition: proposed as "at least one
connected account whose `ai_mode` was changed from its default, or the AI settings saved once".

## Q-009 · Delete workspace in Settings
UX-SCR-07 puts Delete workspace in the Workspace page's danger zone, but the deletion itself
(FR-ACC-05, purge) is built in T9.6. The page leaves the danger zone out until then rather than
showing a button that does nothing.

## Q-010 · Clerk webhook uses the event store now
TR-AUTH-04 is in P1 and TR-WH-03 says webhooks are stored and processed by a job, but
`webhook_events` was planned for T2.5. It is built in P1 (migration 0003) together with
`process_webhook_event`, so the Clerk webhook follows the same path every provider will.
