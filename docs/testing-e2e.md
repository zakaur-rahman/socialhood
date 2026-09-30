# End-to-end tests (T9.4, TR-TEST-01)

A Playwright suite in `apps/web/e2e` drives the real web app, API and job worker through the flows
TR-TEST-01 names: **F-01, F-06, F-07, F-08, F-11, F-13 and F-15**. Everything runs on the sandbox
platform and fakes, so no test reaches Meta, Gemini, Dodo, Resend or a push service. Only Clerk
is real: its **development** instance, with testing tokens.

It runs every night in CI (`.github/workflows/e2e-nightly.yml`) and on demand from the Actions
tab. T9.4 is done when it is green three nights in a row.

## Run it locally

Prerequisites, once: `docker compose -f infra/docker-compose.yml up -d`, `pnpm install`,
`uv sync` in `apps/api`, and Playwright's browser:

```sh
pnpm --filter @socialhood/web exec playwright install chromium
```

Then, from the repository root:

```sh
pnpm e2e                          # build, start the stack, run everything, stop, clean up
pnpm e2e -- --grep F-15           # Playwright arguments after --
pnpm e2e --skip-build             # reuse the launcher's last web build, if nothing rebuilt .next since
pnpm e2e --keep-db                # keep socialhood_test_6 afterwards, to look at the data
```

While writing tests, keep the stack up and run Playwright on its own:

```sh
node scripts/e2e-stack.mjs --serve        # Ctrl-C stops it
cd apps/web && pnpm exec playwright test f06 --headed
```

The Clerk keys come from `apps/web/.env.local` (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`) and
`apps/api/.env` (`CLERK_SECRET_KEY`), or from the environment. Nothing else is read from those
files. A cold run takes about 5 minutes on a laptop: 2 for the web build, 3 for the tests.

## The stack (`scripts/e2e-stack.mjs`)

| Piece | Where | Notes |
|-------|-------|-------|
| API | `http://localhost:8100` | `apps/api/scripts/e2e/api.py`: the normal app plus test-only seed routes |
| Worker | one process, both lanes | `apps/api/scripts/e2e/worker.py`: the normal worker with the fake AI's replies set |
| Web | `http://localhost:3100` | a production build (`next build`, `next start`) |
| Database | `socialhood_test_6` | dropped and re-created, then migrated, at the start; dropped at the end |
| Valkey | db 5 | flushed at the start and the end |

It never touches the development stack: ports 8000 and 3000, the `socialhood` database and Valkey
db 0 are refused (`apps/api/scripts/e2e/db.py` only drops `socialhood_test_<n>` or
`socialhood_e2e*`), and it stops if 8100 or 3100 is already in use. On Windows uvicorn runs with
`--loop asyncio:SelectorEventLoop`. The API and worker start in `apps/api/scripts/e2e`, where no
`.env` file is loaded, so a local run and a CI run see the same settings:

- `SANDBOX_PLATFORM_ENABLED=true`, `AI_PROVIDER=fake`, `DODO_PROVIDER=fake`,
  `EMAIL_PROVIDER=fake`, `PUSH_PROVIDER=fake`, `APP_ENV=test`;
- `TOKEN_ENCRYPTION_KEYS`, `DODO_WEBHOOK_SECRET` and the seed token are generated for each run;
- `CLERK_ISSUER` and `CLERK_JWT_KEY` are derived from the publishable key (the Frontend API host
  and its JWKS).

Logs of every process are in `apps/web/e2e/logs/`. The report is in `apps/web/playwright-report`;
traces, videos and screenshots of failed tests in `apps/web/test-results/e2e`.

### Test-only pieces in the API process

`api.py` adds the fake Dodo's products (the fake starts with none, so checkout would fail) and
routes under `/__e2e` that need the per-run `X-E2E-Token`:

- `POST /__e2e/workspaces`: a fresh workspace owned by the signed-in user. Every test gets its
  own (the `workspace` fixture); the launcher drops the database after the run;
- `POST /__e2e/workspaces/{wid}/media-assets`: a photo in the media library without Cloudinary;
- `DELETE /__e2e/users/{clerk_user_id}`: a signed-up user's workspaces and row (F-01's cleanup).

It refuses to start unless the sandbox is on, Dodo is the fake and the app isn't in production.

`worker.py` makes the fake AI suggest `"Thanks for asking! Yes, it's in stock in every colour and
ships this week."` for every customer message, and "can't answer" for one containing
`[e2e:unknown]`.

## Auth

- Global setup gets a Clerk **testing token** (`@clerk/testing`), so sign-in and sign-up skip
  bot protection, and makes sure the dedicated user `socialhood-e2e+clerk_test@example.com`
  exists (created once through the Backend API, then reused).
- `auth.setup.ts` signs that user in with a sign-in token (no password, no email code), opens
  `/app` so the API provisions it, and saves the browser state every test starts from
  (`apps/web/e2e/.auth/`, ignored by git).
- F-01 signs up a new `socialhood-e2e-signup-…+clerk_test@example.com` user through Clerk's form
  (test addresses verify with `424242`) and deletes it from Clerk and the database afterwards;
  global setup and teardown delete any such user a stopped run left behind.
- Tests call the API as the signed-in user with a fresh Clerk session token from the browser.

## What each flow checks

| Flow | Spec | Key assertions |
|------|------|----------------|
| F-01 Sign up and first run | `f01-sign-up.spec.ts` | Clerk sign-up with email code lands on `/w/{slug}/home`; the workspace is "My workspace"; the checklist shows 4 steps, 0 done, the first expanded with "Connect an account", which opens Connections |
| F-06 An inbound DM arrives | `f06-inbound-dm.spec.ts` | a sandbox DM appears live at the top with an unread dot and the sidebar count; opened, it is marked read, analysed and gets a suggestion; a busier conversation jumps to the top; a DM to the open conversation appears in the thread |
| F-07 Reply from the inbox | `f07-reply.spec.ts` | Enter sends (202, idempotency key); the bubble shows at once and moves to Sent; the list preview says "You: …"; a `[sandbox:fail=delivery_unknown]` send ends Failed with the §4.7 reason, and Retry is accepted; a conversation outside the 24-hour window shows the reason instead of the composer |
| F-08 Use a suggested reply | `f08-suggested-reply.spec.ts` | Send posts the text with `suggestion_id` and the card closes; Edit moves the text into the composer with the "Editing suggestion" chip, and the edited reply carries `suggestion_id`; Regenerate (202) leaves one draft fewer; Dismiss closes the card; "Not in your knowledge" names the gap and offers Add to knowledge; a newer customer message replaces the pending suggestion |
| F-11 Keyword automation | `f11-keyword-automation.spec.ts` | a template creates a draft and opens the editor; the preview renders the fallback name; Activate reports the missing link on its step; after autosave ("Saved") it activates; the list shows it Active with its keywords and runs; a keyword DM gets the automation's message, Sent |
| F-13 Schedule and publish | `f13-schedule-post.spec.ts` | account, library photo and caption fill the checklist and the live preview; Schedule sends the chosen UTC time and the post shows as Scheduled and in the list view; Publish now goes through the jobs to Published, and the post reaches Comments |
| F-15 Upgrade | `f15-upgrade.spec.ts` | a fourth automation on Free gets 402 and the dialog "Automation limit reached", "Free includes 3 active automations", the Pro offer and price; "Start 7-day trial" goes to the fake Dodo and back; the page waits ("Confirming your payment…") and stays Free until a `subscription.active` webhook, signed with the run's `DODO_WEBHOOK_SECRET`, arrives; then "Your Pro trial has started", the limits say 50, and the fourth automation activates |

## Writing tests

- Import `test` and `expect` from `./support/fixtures`. Fixtures: `workspace` (a fresh
  workspace), `sandbox` (the workspace plus a connected sandbox Instagram account) and `api`
  (`inbound()` for DMs and comments through the webhook intake, `activeAutomation()`,
  `mediaAsset()`, `dodoWebhook()`, `call()` for any endpoint).
- Keep tests independent: never rely on another test's data. Use `unique()` for text you look for.
- Prefer roles and labels; add a `data-testid` to the app only when nothing stable exists.
- The sandbox fails a send, private reply, comment reply or publish whose text contains
  `[sandbox:fail=<code>]` (see `platforms/sandbox/outbox.py` and `publishing.py`).
- A sandbox account backfills three posts, three conversations (one outside the reply window) and
  some comments when it connects.

## CI

`.github/workflows/e2e-nightly.yml` runs at 21:30 UTC and from "Run workflow" (optionally with a
`--grep`). It starts Postgres (pgvector) and Valkey as services, installs uv, pnpm and Chromium,
and runs the launcher. Retries: 1 in CI, 0 locally. The HTML report is uploaded every run; on a
failure, the traces, videos, screenshots and stack logs too.

Secrets it needs, both from the Clerk **development** instance:

| Secret | Value |
|--------|-------|
| `CLERK_E2E_PUBLISHABLE_KEY` | the publishable key, `pk_test_…` |
| `CLERK_E2E_SECRET_KEY` | the secret key, `sk_test_…` |

Failure traces contain the test user's short-lived session tokens for the development instance;
the artifacts are kept 7 days.
