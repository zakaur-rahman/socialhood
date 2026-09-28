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
`uv run procrastinate --app=socialhood.jobs.app.app worker`. Production is unaffected.
