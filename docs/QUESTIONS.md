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
not done until their tables arrive: create_automation (T4.1), add_knowledge (T5.x).
(connect_account is computed from `social_accounts` since P2.) "Choose an AI mode" needs a definition: proposed as "at least one
connected account whose `ai_mode` was changed from its default, or the AI settings saved once".

## Q-009 · Delete workspace in Settings
UX-SCR-07 puts Delete workspace in the Workspace page's danger zone, but the deletion itself
(FR-ACC-05, purge) is built in T9.6. The page leaves the danger zone out until then rather than
showing a button that does nothing.

## Q-010 · Clerk webhook uses the event store now
TR-AUTH-04 is in P1 and TR-WH-03 says webhooks are stored and processed by a job, but
`webhook_events` was planned for T2.5. It is built in P1 (migration 0003) together with
`process_webhook_event`, so the Clerk webhook follows the same path every provider will.

## Q-011 · The ops CLI never retries platform writes
TR-OPS-04 says the CLI never retries a send that ended `delivery_unknown`. A failed job row does
not record why the send failed, so the CLI cannot tell that case apart. It refuses every task in
`jobs/failed.py: PLATFORM_WRITE_TASKS` (sends, publishing, comment replies) and says so; users
retry those from the app, after checking Instagram, as TR-JOB-05 intends. Each sending task must
be added to that set when it is written (P3, P5, P6).

## Q-012 · Copy for a failed code exchange
The callback's `connect_failed` (Instagram refused the code or the token exchange) has no row in
§4.7. The page uses `platform_unavailable`'s copy, "Instagram didn't respond. Try again.", with
Try again. Add a row?

## Q-013 · Settings sections and Connect WhatsApp before they exist
Settings shows only the built sections (Connections, Workspace); AI, Notifications and Billing
join with their phases. "Connect WhatsApp" is shown disabled ("coming soon") until F-04 is built.

## Q-014 · "Delete data" on disconnect has nothing to delete yet
FR-CON-06's choice is in the dialog and the API (`?delete_data=`), but conversations (P3) and
comments (P6) do not exist yet, so the flag is only recorded in the log. The deletion joins the
disconnect when those tables arrive.

## Q-015 · When is a scheduled message "sent"?
It becomes `sent` once its message is queued. If the platform then refuses the send, the thread
shows that message as failed with Retry, but the scheduled row stays `sent`. F-10's "sent or
failed" could mean mirroring the final result, which needs a hook in `send_message`.

## Q-016 · Retry counts
FR-SMS-03 says a scheduled send is "retried up to 3 times"; the job catalogue gives send_message 5
tries. P3 uses 5.

## Q-017 · WhatsApp number registration
Meta's Cloud API onboarding registers a number with a 6-digit PIN (`POST /{phone_number_id}/
register`); F-04 leaves it out. Without it sends fail with 133010. Who sets the PIN, and where is
it kept?

## Q-018 · The "AI handled" view
Not defined in the spec. P3: the AI has replied in the conversation (a message with source
`ai_auto`) and it does not need a human.

## Q-019 · A reply from the Instagram app and unread
It clears `awaiting_reply` and `needs_human` but leaves the unread count. Should it mark the
conversation read?

## Q-020 · Which inbound attachments are copied
TR-MED-03 says each inbound attachment is copied because platform URLs expire. P3 copies images,
video, audio, files and stickers; stories are never copied (story mentions by policy; a story
reply's story is the business's own), and shared posts keep the link to someone else's post.

## Q-021 · Unsent messages
Instagram reports a message the customer unsent (`is_deleted`). P3 records it but cannot hide the
message: that needs a `deleted_at` column (a migration). Add it in P4?

## Q-022 · Contract gaps found while building the web inbox
`Message` has no `edited_at` (so no "Edited" label), `Conversation` has no `last_inbound_at`,
`POST …/scheduled-messages` declares no Idempotency-Key (TR-API-05, F-10), `MediaAssetOut` has no
MIME type, and there is no error code for Meta's Embedded Signup allowance ("WhatsApp connections
are paused…", F-04). All additive; proposed for the start of P4.

## Q-023 · Not built in P3
TR-API-07's 60 sends per minute per workspace (429), and the job catalogue's 30 s task timeout
(Procrastinate enforces none; HTTP timeouts apply). The echo race and follow-up jobs are deferred
by a few seconds rather than enqueued after commit; a transactional outbox would remove that.
