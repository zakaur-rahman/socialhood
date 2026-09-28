# Conflicts

Places where the spec disagreed with itself, with the platform, or with a library, and what the
code does. Resolved items say where the spec was corrected.

## C-001 · Webhook body limit (resolved in the spec)
TR-API-07 capped webhook bodies at 1 MB; TR-WH-01 and SEC-08 say 5 MB (WhatsApp payloads reach
3 MB). The code follows 5 MB. `docs/BUILD_SPEC.html` TR-API-07 now says 5 MB.

## C-002 · `globals.css` additions to §4.2 (open: confirm)
UX-TOK-01 says the tokens file is used "exactly as below". Two lines are added, both marked in
`apps/web/src/styles/globals.css`:
- `@import "shadcn/tailwind.css";`: shadcn v4 components use keyframes and `data-open:` style
  variants defined there. No colours.
- `@custom-variant dark (&:is(.dark *));` with `class="dark"` on `<html>`: the app is dark-only
  (D13), so `dark:` classes in components must not depend on the visitor's OS setting.

## C-003 · Tenant filter sample code missed count queries (resolved in the spec)
TR-TEN-02's sample listener decided whether a query touches tenant tables from
`state.all_mappers` only. For `select(func.count()).select_from(Note)` that list is empty, so the
query ran unfiltered across workspaces, and did not even raise without a workspace. Found by
`tests/integration/test_tenancy.py`. `db/tenancy.py` also scans every table in the statement; the
spec's sample now says so. Tests cover counts, subqueries, `EXISTS` and joins.

## C-004 · Library versions newer than the spec's minimums (no action)
Installed at scaffold time (September 2026): Next.js 16.3 (Turbopack by default; `middleware.ts`
is now `proxy.ts`, which TR-FE-01 already allows for), React 19.2, FastAPI 0.141, Starlette 1.7,
SQLAlchemy 2.1, Procrastinate 3.10, pytest-asyncio 1.4. All meet the stack table's minimums.

## C-005 · Clerk Core 3 and Next.js 16 (no spec change needed)
The installed `@clerk/nextjs` 7 is Clerk Core 3 (March 2026): `<ClerkProvider>` goes inside
`<body>`; `<SignedIn>`/`<SignedOut>` are replaced by `<Show when=…>`; the dark theme comes from
`@clerk/ui/themes`; appearance variables were renamed (`colorText` to `colorForeground`,
`colorInputBackground` to `colorInput`, and so on); `useAuth().getToken` throws during SSR and
offline. On Next.js 16 the middleware file is `src/proxy.ts`, which TR-FE-01 already allows.

## C-006 · Sidebar still said "Publish" (resolved in the spec)
§3.1's sidebar sentence listed "Publish" after the page was renamed Schedule. Corrected.

## C-007 · `SocialAccount` gains `sandbox` (resolved in the spec)
The Connections page must tell a TR-PL-07 sandbox account from a real one (its card is labelled,
and it accepts injected events). `SocialAccount` in §5.10 now has `sandbox: boolean`. The SEC-02
schema test forbids `token` in response properties except `token_expires_at`, which is a date.

## C-008 · Webhook processing marked events failed, then retried (fixed in code)
The first `process_event` set a failed event to `failed` and re-raised for the job to retry,
which TR-JOB-04 forbids ("never mark failed and then re-raise"), and its rollback also undid the
attempt count, so the 5-attempt cap never applied. Now: the claim is a row lock held for the
processing transaction (`processing` is never committed, so a crashed worker leaves the row
`received` for `sweep_stuck`); a failure with attempts left writes `received` with the attempt
count and error and re-raises; the last attempt writes `failed` and returns. The stale
`processing` sweep was removed because nothing can be left in that state.

## C-009 · Plan limit versus reconnecting (fixed in code)
F-03 checks `accounts_per_platform` when the connect starts. On a full plan that blocked
reconnecting the very account that needed it (F-05). The start now refuses only when no account
in the workspace needs reconnecting or has an error; the callback decides exactly once it knows
which account came back: a reconnect always passes, a new account over the limit redirects with
`?error=quota_exceeded&limit=N`, and the page shows "Your plan includes N Instagram accounts."

## C-010 · httpx logged token URLs (fixed in code)
httpx logs each request URL at INFO. Instagram's token endpoints take the app secret and tokens
as query parameters, so those values reached the logs (SEC-06). `configure_logging` now holds
the `httpx` and `httpcore` loggers at WARNING; platform calls are logged by endpoint name
(TR-PL-05). A unit test pins it.
