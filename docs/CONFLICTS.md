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

## C-031 · No follow gate: tap first and a follow nudge instead (decision, FR-AUT-21, FR-AUT-22)
The owner asked for "ask commenters who don't follow to follow or share, then send the link".
Meta's Spam Community Standard forbids "requiring users to engage (in the form of likes, shares,
follows, or any other public-facing form of engagement) to gain access to specific, exclusive
content", and shares are not visible through the API at all. Built instead, with the owner's
go-ahead: tap first (the private reply is an opening with a "Send me the link" quick reply; a tap or
any reply releases the message as a normal DM, with the real first name, image and buttons) and a
follow nudge (one more message after the message, only to people Instagram reports as not
following; never before it, never instead of it). Details:
- Answers: a quick-reply payload `shr:{run_id}` naming one of the contact's runs on that account
  answers only that run (a second tap is handled and sends nothing); anything else, including a
  payload that isn't theirs or an opening older than 7 days, is a typed reply, which releases up to
  3 waiting runs, oldest first. The answering message is `automation_handled` and no DM keyword
  automation runs on it; with nothing waiting, keyword automations run as usual. A paused
  automation's run is still released (the opening promised it).
- The fresh profile read (name and `is_user_follow_business`) happens before the run locks, so no
  network call runs under a lock; then, once per run, `confirmed_at`, `follows_business` and the
  message are written in one transaction. The released run is `sent` (or `partial` when its public
  reply failed) and then mirrors the message's send; `private_reply_message_id` points at the
  released message, the opening stays linked from the comment and the message's run.
- The nudge is queued only after the message is recorded as sent, so it always follows it; a
  failed message gets no nudge; unknown follow status gets none. Comment automations without tap
  first never nudge (nobody answered; Meta allows no follow-up). AI-reply automations ignore both
  settings. The nudge renders personal fields and ends with the disclosure line; its 300-character
  limit is on the text as typed. The opening also ends with the disclosure line, inside its
  1,000-byte limit.
- If Instagram refuses quick replies on a private reply (non-retryable `platform_rejected`), the
  opening is sent once more as text only, without taking another private-reply token; the default
  copy ("…tap the button below, or just reply here…") works either way.
- Defaults: new drafts and the comment templates start with tap first on; "Send a link to
  commenters" also starts with the nudge on. Switching a DM or blank automation to a comment trigger
  turns tap first on if it never had an opening. With tap first on, a comment automation may carry
  an image again (C-030's rule applies only without it).
- Runs still waiting after 7 days stay `awaiting_reply` in the log but are never released and are
  not counted in "Waiting now". Stats: tapped = runs answered in the period, nudged = nudges sent in
  the period.

## C-032 · Gemini SDK option names (resolved in code, T5.1)
TR-AI-03's sample passes `response_format={"text": {...}}` to `GenerateContentConfig`. The
installed google-genai (2.25.0) has no `response_format`; structured output uses
`response_mime_type="application/json"` with `response_json_schema` (or `response_schema`), and
thinking uses `ThinkingConfig(thinking_level=...)`. Every option still goes inside the config, as
TR-AI-03 requires. `EmbedContentConfig` has `task_type` and `output_dimensionality`; T0.9 item 17
confirms whether gemini-embedding-2 accepts `task_type` or needs the task written into the text.
The model ids in TR-AI-02 are to be checked against Google's list with a valid key (the configured
key was rejected on 2026-09-29).

## C-033 · The AI becomes a tool-using agent (decision, 2026-09-29)
The owner redirected the AI towards an autonomous agent (understand, plan, use tools, execute,
verify, report). After review: R1 ships a read-only agent, "Ask Social Hood" (FR-AGT-01…07,
phase PA after P7); write tools, approvals, permissions and Copilot/Supervised modes are R2;
Autonomous mode and standing instructions R3. Framework: Pydantic AI for the model-and-tool loop
only; state, approvals, permissions, credits and audit stay in Postgres. Facebook Pages stays R2.
Departures from the owner's brief, accepted: tools are thin adapters over existing services; one
analysis call instead of per-signal modules; plans are typed and conditions evaluated by code;
one action gateway decides every write; success is verified by read-back; four tables instead of
eleven; the agent package sits beside ai/, not inside it; FR-ANL-01 snapshots become MUST and
FR-ANL-02 post analytics move to R1 because comparisons at equal age need them. Design:
docs/agent-architecture.html.

## C-034 · Merging knowledge gaps (decision, replaces TR-AI-12's rule)
Measured on Postgres: "shipping to dubai" vs "shipping to uae" = 0.545 trigram similarity (not
merged), "shipping to uae" vs "shipping to usa" = 0.684 (wrongly merged). New rule: the open gap
labels (top 20) are passed to the suggestion call as data and the prompt asks the model to reuse
an exact label for the same missing fact; exact match first; trigram similarity only as a fallback
at 0.7. Needs suggest.v2 and an eval run (T5.9). To implement next.

## C-035 · P5 build decisions (analysis, summaries, reminders)
Embedding 2 aggregates several parts of one Content, so each text is its own Content; task format
"task: search result | query: …" and "title: … | text: …". closing_soon now means a reminder went
out for the current window, the window is open and no business message came after 18 h (FR-INB-14);
the reminder states the real hours left and goes to all members. needs_human is raised by
analysis and cleared only by a business reply. Summaries: last 50 messages, recomputed trigger
count, 409 when analysis is off. No skipped decision row on a quota skip (checks belong to T5.6).

## C-036 · P5 build decisions (knowledge)
Long FAQs split with "Q: …\nA: " repeated; headings are hard chunk boundaries; the "[title] "
prefix doesn't count toward 1,200. Character use: FAQ = question + answer, note = body, page or file
= extracted text; a page or file that would pass the limit fails during ingestion; shortening is
allowed over the limit. An edited source is unsearchable for the seconds it re-ingests. SSRF: every
resolved address must be public; shared 100.64/10, reserved and multicast blocked; 15 s covers the
whole fetch. An answered gap never reopens (a new one opens); a punctuation-only label records
nothing. Knowledge uploads: PDF, DOCX, TXT, MD up to 10 MB.

## C-037 · P5 build decisions (suggestions and Auto)
No analysis for a message fails check 6 (Auto never sends blind). The output filter lets reviewed
suggestions quote the conversation, but Auto and automation replies only knowledge and brand
settings; an unknown link, email or phone makes the suggestion can_answer false. Built-in
escalation phrases (refund, chargeback, lawyer, legal notice, consumer court, police, fraud, scam,
talk to a human, manager…) match whole words. Takeover note only when Auto pauses; Resume adds a
note; native-app echoes also pause Auto. Regenerate: 409 when AI is off or after 5; gaps count once
per message; decide_auto_reply only for first generations. AI-reply automations need instructions
and re-check the plan at runtime. Not built yet: suggestion expiry, the complex-model retry.

## C-038 · P5 build decisions (web)
The escalation banner and "AI paused" show only in Auto. The first draft shows a shimmer for up to
30 s after an analysis that needs a reply. Brand voice opens as a form until a description exists.
Plan gating reads the billing entitlements. The web refetches a conversation on
conversation.updated for summary and AI state (the event carries list fields only).

## C-039 · P6 foundation decisions (contract)
comment_analyses also stores media_item_id (not in §5.6) so per-post figures read one table; its
topic may be null (no topic) and is at most 60 characters, lowercased by the writer.
post_metric_snapshots keeps the column name "window", a reserved word: raw SQL quotes it. Added
indexes media_items (social_account_id, posted_at DESC) for baselines and comments (workspace_id,
commented_at DESC) for sentiment over a date range. The comparison route is
…/analytics/posts/{id}/compare (§2.15 lists …/analytics/compare); ranges are since and until dates
in the workspace time zone, both included, defaulting to the last 30 days. Percentages are 0 to
100, engagement rate included. Comment stats: positive + neutral + negative count analysed comments
that are not spam; spam is counted apart. Filter chips: questions = pricing, product_inquiry,
shipping, order_status, support; buying = purchase, pricing. Comment actions: a public reply
answers 200 with the comment once Instagram accepts it; a private reply answers 202 with the
comment (the DM is queued); hide and unhide answer 200; delete answers 204 and keeps deleted_at.
post.updated carries a PostDetail. The adapter's get_media_insights takes the media type (Instagram's
metrics differ by format) and get_account_insights the workspace time zone.

## C-040 · P6 metrics and analytics decisions
- Post snapshots are checked every 15 minutes (the §2.9 catalogue said hourly; a 1 h window needs a
  finer tick): `snapshot_post_metrics` queues a per-account `snapshot_account_posts`; account days
  are `snapshot_account_daily` (hourly) queuing `snapshot_account_day`.
- A window is due from publish time + age for max(30 min, age ÷ 4), then skipped for good, so a late
  value is never labelled with an earlier age. Posts from before connecting get only the windows
  still ahead of them. No interpolation between snapshots (agent-architecture §6 mentioned it); the
  answer states the age used.
- Instagram media insights are lifetime totals, so the 72 h run reads its own values and marks the
  1 h, 6 h and 24 h rows insights_final; 24 h insight values are provisional until then.
- Account day D is written from 02:00 local time; the run for day D also re-reads day D−2 once.
- Baselines: the previous N posts of the same account and format (feed = image, carousel, video;
  reel); diff % and z-score only with ≥ 3 values, a positive median and spread; engagement rate needs
  reach > 0 and all four interactions. Stories are left out of analytics. A new IG_INSIGHTS bucket
  paces insight calls. "insights_granted" follows the account's granted scope.

## C-041 · P6 comment intelligence decisions
- `CommentStats.analysed` counts every comment no longer pending, including skipped ones (analysis
  off, credits used up, over the plan's post limit, empty, failed alone), so progress always ends.
- New entitlement `comment_intelligence_posts` (§1.7: Free 5 most recent posts, Pro and Max all);
  comments on older posts are skipped on Free and not re-analysed after an upgrade.
- Analysis: one account at a time (lock `cmt:{account}`, at most one bulk slot), up to 10 batches of
  50 per run, dispatched every 30 s by `dispatch_comment_analysis`; the model returns `{items}` for
  comments numbered 1–50; an invalid answer is retried in halves (at most 12 calls). Summaries are
  queued 60 s after analysis so a surge costs one summary a minute; an hourly sweep covers the 24 h
  rule.
- Webhook intake publishes comment.created and post.updated with the new total; backfill publishes
  one post.updated per post. Backfill runs from sync when stored comments trail Instagram's count.
- Manual private replies are queued human messages sent by `send_private_reply` through the shared
  IG_PRIVATE_REPLY bucket; the link on the comment makes a second one 409 ("This comment already has
  a private reply."), cleared again if Instagram definitely refuses; the 7-day limit has its own
  message. A public reply with the same text within 2 minutes is not posted twice.
