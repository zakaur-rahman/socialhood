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

## C-011 · Echoes of our own sends (fixed in code)
Instagram echoes every message the account sends, ours included. An echo can arrive before the
send job has stored the platform id, and ingest stored it as a second (native_app) message; the
send job then hit the unique id. Ingest now matches an echo to our send that is being sent: a
text echo completes it (sent, with the id), an attachment part's echo changes nothing. Only a
send in `sending` can match; a queued one has not reached Instagram. TR-JOB-05's reconciliation
of `delivery_unknown` sends is unchanged.

## C-012 · Read receipts: contact or message (resolved in code)
TR-PL-01 has `mark_read(acct, platform_message_id)`; Instagram marks a conversation seen by the
contact, WhatsApp by message. The adapter method takes both: `mark_read(acct, recipient_ref, *,
message_ref=None)`, and read receipts pass the latest inbound message id.

## C-013 · AI paused "until resumed" (fixed in code)
`ai_paused_until = 'infinity'` (§5.4) reads back from asyncpg as a naive `datetime.max`, which
broke the conversation detail. The column now always reads timezone-aware.

## C-014 · Contract export needed a database URL (fixed in code)
`pnpm gen:api` imports the app, which reads settings, so it failed without apps/api/.env; the CI
contract job had no env and would have failed the same way. The script supplies placeholders;
the export never connects.

## C-015 · Meta refusals sent as HTTP 500 (fixed in code)
The profile API answers "User consent is required" (code 230) with HTTP 500, which the error map
treated as an outage and retried. Code 230 is now `platform_rejected`.

## C-016 · Idempotency keys in Valkey, not a table (decision)
TR-API-05 names an `idempotency_keys` table. P3 stores keys in Valkey (`idem:{workspace}:{user}:
{key}`, a pending marker for 60 s, the 2xx response for 24 h). If Valkey is lost, the unique
(conversation, client_id) still prevents a double send. A table can replace it with a migration
if durability is needed.

## C-017 · Real-time client (decision)
TR-FE-04 names `fetchEventSource`. The web uses its own small SSE reader through the one API client
(`parseAs: "stream"`), so every reconnect gets a fresh Clerk token from the existing middleware;
EventSource cannot send the Authorization header at all.

## C-018 · Design details that conflicted (resolved in code)
UX-INB-07's 36 px send button is 40 px on phones (UX-A11Y-05 touch targets). UX-INB-02's raw hex
hover colour uses the `field` token. At 1024–1279 px the sidebar collapses on inbox routes only
(UX-INB-01). The §4.7 errors name the account's platform, not always Instagram.

## C-019 · `needs_human` is cleared by human replies (decision)
§3 says any outbound human message clears it; F-09 says "sending any message". Human sends and
replies from the Instagram app clear it; AI and automations do not.

## C-020 · Scheduled messages run on a 30-second dispatcher (decision)
The job catalogue's cadence, needed for FR-SMS-03's "within 60 s". `send_scheduled` carries the
workspace id so it never needs a cross-workspace lookup; the stuck-claim sweeper is its own
periodic task (`sweep_stuck_scheduled`).

## C-021 · Instagram can send more than images (resolved in the spec)
FR-INB-08 allowed images only on Instagram and video and documents only on WhatsApp. Meta's
Instagram Messaging docs (checked 2026-09-29) list image (PNG, JPEG, 8 MB), video (MP4, OGG, AVI,
MOV, WEBM, 25 MB), audio (AAC, M4A, WAV, MP4, 25 MB), file (PDF, 25 MB) and the heart sticker
(`like_heart`); the WhatsApp Cloud API adds WebP stickers (512 × 512, 100 KB static, 500 KB
animated) and Office and text documents up to 100 MB, with tighter image (5 MB), video and audio
(16 MB) limits. FR-INB-08 now says so; `services/sending.py SEND_RULES` and the composer apply
these limits, and uploads for posts keep TR-MED-02's image and 90-second video rules. An
Instagram heart is stored and shown as ❤️, both ways.

## C-022 · AI-reply automations wait for the knowledge base (decision)
FR-AUT-01 offers "Reply with AI", but AI replies need knowledge and suggestions (P5). In P4 an
ai_reply automation can be drafted and tested but not activated: on Free the activate call returns
402 `entitlement_required` ("AI replies in automations are part of Pro."), on Pro 422 with field
`action` ("AI replies arrive with the knowledge base. Send a message for now."). The editor shows
the same note. P5 lifts the 422.

## C-023 · Activation rules beyond FR-AUT-02 (decision)
Checked in this order: the ai_reply entitlement (402), then every field problem in one 422, then
the `active_automations` quota (402 "Your plan includes N active automations."). Beyond FR-AUT-02:
an end time already past is refused; the account must be Instagram and not disconnected
(needs_reconnect is allowed); selected posts must belong to the automation's account; an empty
public-reply variation is flagged; nested fields are named by index (`message_buttons.0.url`,
`public_reply_texts.1`), and `missing_for_activation` uses the same names. A PUT that would leave an
active automation failing these checks is refused with the same 422, so an active automation is
always complete (the `complete_when_active` check). Activations in a workspace are serialised with
an advisory lock, so two at once cannot both pass the limit. Reply with AI counts as complete only
with instructions.

## C-024 · The message byte counter's worst case (decision)
FR-AUT-13's 1,000-byte limit is checked on the longest rendering: each personal field as a
30-character sample (Instagram usernames are at most 30 characters), or its fallback when that is
longer, plus the disclosure line. `render.longest_render` and the web's `worstCaseBytes` agree.

## C-025 · Automation stats and display status (decision)
UX-SCR-12's figures: the period is the workspace's calendar days ending today, oldest first; `runs`
counts every run row; `dms_sent` counts runs whose DM reached sent, delivered or read; `failures`
counts failed and partial runs; "outside window" skips are always 0 (the runtime never loads an
automation outside its window, so no run row exists). List sorts: `recent_runs` = most runs in 7
days, then latest run, then priority; `created` = newest first; the web adds "Priority" (its
default), the only order in which drag and Move up / Move down appear (and only with no status,
trigger or search filter, since `PUT …/priorities` takes the account's whole order).
`display_status` is "scheduled" before `starts_at` and "ended" once `ends_at` has passed for active
or paused automations; a draft is always a draft.

## C-026 · The Test tab (decision)
UX-SCR-12's test treats the automation under test as live, so a draft can be tried (the reason
then says it runs once activated). The other candidates are the account's active automations
inside their run window; cooldowns are ignored. Sample names default to "Priya" / "priya.shah"; an
empty string shows the fallback. The disclosure line is added to the DM, not to public replies. The
web saves pending edits before testing, because the API tests the saved automation.

## C-027 · Posts, next post and scheduled posts (decision)
PUT stores posts by scope: `selected` keeps the media items and scheduled posts given (a scheduled
post that has published keeps its media item); `next_post` keeps its link while the scope and
account are unchanged; `all` stores none. FR-AUT-18's next post is the account's first post (not a
story) published at or after the automation's latest activation; post sync and
`on_new_media_item` both call `link_next_posts`, which locks the automations so one is never
linked twice. `posts.link_scheduled_post` is ready for P7's publish step (T7.3). Any comment
cannot use All posts (the web switches it to Selected). The post picker leaves out stories and
shows synced posts only; scheduled posts join it in P7.

## C-028 · Automations and the rest of the app (decision)
Home's `create_automation` step is done once any automation has been activated, so pausing keeps
it ticked (the spec says only "create an automation"). The run-window job (every minute) pauses an
automation past `ends_at` and notifies owners and admins once per end time ("{name} ended", linking
to it). Disconnecting an account, or Meta's deauthorize, pauses its active automations (F-15);
drafts stay drafts. The disclosure line (FR-AUT-11) is set in Settings → Workspace: off by default
(null), "Sent automatically" when switched on, up to 60 characters.

## C-029 · The private-reply bucket keeps every hour under 750 (resolved in code)
TR-JOB-07's bucket with a 750-token burst would allow up to 1,500 private replies in the first hour
of a surge (750 at once, then 750 refilled), against FR-AUT-10's "never exceeds 750 private replies
in any hour". The IG_PRIVATE_REPLY bucket is a burst of 20 refilling at 730 an hour. The ETA uses
the same rate: the account's sendable queued runs (active or ended automations, not public-only,
comment inside 7 days) × 60 ÷ 730, one formula for the queue, the list and the summary. An
automation's `waiting` is all its queued runs (a paused one holds them). Resuming a paused
automation with queued runs enqueues its account's drain at once; held queues are rechecked every
10 minutes anyway.

## C-030 · Automation runtime rules (decision)
- A DM run is `sent` when handed to the send pipeline, then mirrors the send (as scheduled messages
  do, Q-015); `private_reply_message_id` holds the DM for DM runs too.
- Cooldown (FR-AUT-05) counts queued, sent, partial and escalated runs, not failed or skipped ones.
  A match on cooldown records `skipped_cooldown` and the next matching automation may answer; a
  match outside the post scope is passed over without a run; a comment already past 7 days when it
  matches records `skipped_expired`. `automation_handled` is set only when a DM was queued.
- Any-comment automations answer top-level comments only; keyword automations also answer replies
  in threads. The account's own comments (by its Instagram user id, app-scoped id or username) are
  skipped, which also skips our public replies coming back. Comment verbs other than "add" are
  ignored.
- If Instagram refuses the post fetch, the post is stored as a placeholder (posted_at = the
  comment's time) and is not offered to next-post automations. Commenter profiles are not fetched
  (the profile API needs the person to have messaged first), so `{first_name}` usually falls back in
  comment replies.
- The disclosure line goes on DMs and private replies, not on public comment replies. A private
  reply carries text and buttons, never an image, so activation refuses an image on a comment
  automation and the editor offers none (it suggests a link button). With link buttons the text is
  Instagram's button template: at most 640 characters in its longest rendering, checked at
  activation and in the editor. Public reply only needs at least one public reply.
- A paused automation holds its queued runs (they still expire); one whose run window ended still
  sends what matched inside it. The account's automations take turns in the queue. Temporary
  platform errors put a private reply back in the queue; `delivery_unknown` is never retried; a
  failed public reply is not retried. Run log errors are prefixed "Public reply: " or "DM: ".
- `contact_replied_at` (FR-AUT-16) is set on the first customer message within 24 h of an
  automation DM or private reply that reached sent, delivered or read.
- `run_automation` is deferred 1 s and retries up to 5 times while the trigger row is not yet
  visible. `matched_keyword` stores the normalised keyword.
- Messages an automation sent carry `automation {id, name}` in the conversation's messages and in
  `message.created` / `message.updated` events (the bubble says "Automation · {name}").
