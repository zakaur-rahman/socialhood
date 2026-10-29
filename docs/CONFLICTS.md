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

## C-042 · Keyword comments are never spam (found live, 2026-09-29)
The first real comment analysis read the comments "Link" (the keyword of a comment-to-DM
automation) as spam. With auto-hide on, that would hide the very comments automations answer. A
comment that triggered an automation (any run result) is stored with is_spam false and a "spam"
intent becomes "other", decided in code after the model answers, so it is never auto-hidden.

## C-043 · P7 foundation decisions (contract)
- A draft's accounts are its scheduled_post_targets rows, `pending` from the start (§3.6 has
  Schedule create them); the dispatcher claims only pending targets of due posts that are
  scheduled or publishing. A post has one `publish_at` (§5.7), so Add to queue takes the earliest
  time that is a free posting time of every selected account within 8 weeks (FR-PUB-09 says "for
  each selected account"), else 422. A draft may keep a time (a calendar click; drawn muted);
  unschedule keeps it.
- Added to §5.7: `scheduled_posts.counted_at`, so a post counts once per billing period against
  scheduled_posts_monthly (unschedule and schedule again costs nothing). Checks: format, status,
  "schedulable" (past draft needs a time and a format), caption, override and first-comment
  lengths, asset position 0–9, at most 10 carousel children, a published target has its media id,
  posting times in whole minutes, hashtag groups with 1–30 hashtags stored lowercase without "#".
  Indexes: (workspace_id, publish_at) for the calendar, (publish_at) WHERE scheduled or publishing
  for the dispatcher, targets (social_account_id, status), assets (media_asset_id),
  automation_posts (scheduled_post_id).
- media_items.published_target_id gets a unique FK ON DELETE SET NULL (§5.6 names no FK);
  automation_posts.scheduled_post_id gets §5.6's FK ON DELETE CASCADE, so deleting a published post
  must first clear scheduled_post_id on links that already have their media item (T7.1), or the
  automation would lose its post. Migration 0011 drops the orphan references P4 could store.
  Automation PUT now checks that scheduled_post_ids are this workspace's (422
  `scheduled_post_ids`): the FK alone would accept another workspace's post.
- §5.10 ScheduledPost is extended: first_comment, published_at, thumbnail_url, asset_count,
  created and updated times; targets with platform_media_id, post_id (the media item), published_at
  and the first-comment result; linked automations; the checklist (FR-PUB-10) with `ready`.
  `assets[].id` is the media asset's id. Lists, the calendar and bulk results return
  ScheduledPostSummary (no checklist). Checklist items and 422 errors name the same fields
  (`targets.{i}`, `asset_ids.{i}`, `caption`, `first_comment`, `publish_at`).
- Lifecycle: editable (PUT, unschedule, reschedule, delete) while draft or scheduled, 409 once
  publishing; PUT on a failed or canceled post makes it a draft again (Edit and retry); PUT on a
  scheduled post (Update schedule) re-checks everything including the time; reschedule is for
  scheduled posts only; publish-now answers 202; duplicate copies without the time or automations.
  Bulk: any id not in the workspace is 404 for the whole request; the rest report `skipped`.
- Calendar: `from` and `to` are dates in the workspace time zone, both included, at most 42 days;
  layers default to all; slots are free future times only; an `accounts` block feeds the right rail
  (published in 24 h, limit, next free time). Posting times answer with the next 5 free times.
  The media library lists post uploads only. AI caption and hashtags store nothing.
- Adapter: one method per container type (image, Reel, carousel item, carousel), status, publish
  (returns the media id), get_published_media (permalink), find_published_media (a lost publish
  answer), quota, post_comment. Creating containers may be retried; publish and comment are writes
  (delivery_unknown). The 24 h limit falls back to 100 when the quota can't be read (T0.9 to
  confirm). The publish dispatcher is its own task, dispatch_due_posts (every 30 s), with
  sweep_stuck_posts, not TR-JOB-03's shared dispatch_due.
- Routes sit in api/v1/publishing.py (T7.1), api/v1/captions.py (T7.4) and api/v1/media.py (the
  library, T7.1); adapters in platforms/*/publishing.py (T7.2); jobs in jobs/tasks/publishing.py
  (T7.3), so the four tasks touch different files.

## C-044 · P7 build decisions (posts, publishing jobs, composer, calendar)
- Posts: schedule, queue and publish-now answer 422 with one field error per failing checklist item
  (same names and messages as the checklist); a draft save refuses only foreign or duplicate
  accounts and assets. The 24 h publishing limit in the checklist is 100 minus the account's other
  posts in that window (the real quota is read by the publishing job). Deleting a post never refunds
  scheduled_posts_monthly. A free posting time has no scheduled post of the account within 30
  minutes and is at least 5 minutes ahead. Hashtags are letters, digits, underscores, combining
  marks and zero-width joiners in any script, compared NFC-lowercased, so Hindi hashtags count whole
  (API and web agree).
- Publishing jobs: a carousel's parent container is created only once every child reads FINISHED;
  polls run at once, then every 60 s to poll 5, then every 5 minutes to poll 10 (about 29 minutes).
  Every poll reads the container before publishing; PUBLISHED is resolved with a lookup, never a
  second publish; three more polls then delivery_unknown. A disconnected account cancels its
  target, a reconnect-needed one fails it; failures notify ("post_failed", deduped per post and
  time). The jobs' scheduled_post.updated payload uses the posts service's projection (checklist
  included). Publish-now sets publish_at = now and enqueues publish_target per target.
- Web: the composer checks the checklist locally for instant feedback and the API's wins once saved;
  scheduled posts don't autosave (changes wait for Update schedule); calendar drags snap to 15
  minutes, published and publishing posts can't move, and "Move to…" is the keyboard alternative.

## C-045 · PA foundation decisions (Ask Social Hood)
- Framework: pydantic-ai-slim[google] 2.51 for the model-and-tool loop only (TR-AGT-02); tests
  forbid real model requests (ALLOW_MODEL_REQUESTS = False) and use FunctionModel. The agent's
  model is AI_MODEL_AGENT, else AI_MODEL_REPLY.
- Four tables (migration 0012): agent_runs, agent_steps, agent_approvals (R2), agent_policies (one
  per workspace, read_only with every capability off; backfilled and created with new
  workspaces). Every model call costs 1 credit (agent_turn); tools that call AI charge their own
  feature with the run as ref.
- The registry refuses a tool without a tier, a write without a capability switch, and any write
  in R1 (FR-AGT-02). Tiers are fixed in code; arguments can only raise them; there are no policy
  tools. Events carry ids, statuses and plain-word steps only, never answer text.

## C-046 · PA runtime and tools decisions (TA.1–TA.4)
- Tools are bound to Pydantic AI from the registry for the member's role, run one at a time on the
  run's session, and every call is a stored step (running before the handler, then succeeded or
  failed). Invalid arguments go back to the model once (ModelRetry) and never become a step; a
  failed tool makes the run partial; a transient error is retried once.
- Caps: tools are withheld on the last model turn, past the tool-call cap, one turn before the
  credit cap and with under 20 s of wall time left; past a cap or out of credits no model writes
  the answer and the run is partial with the steps' own summaries and citations.
- Citations: refs are numbered in step order and cited as [n]; cite() keeps only what the answer
  cites, renumbered by first use, expands short ranges, and drops markers that name no record and
  brackets written in place of a citation. AnswerRef.parent_id names a comment's post and a
  scheduled message's conversation, so the web opens them.
- Recovery: finished steps are replayed, not re-run; a read left running is marked interrupted.
  The sweeper (every 5 min) resumes runs untouched for 10 min without a live job, and fails
  instead past 30 min or with a write step left running.
- Visibility: threads are personal for every role; admins see every run in Settings → Agent.
- Time phrases: a time alone is its next occurrence, a day without a time is refused (the model
  asks), "last week" is the previous Monday–Sunday, "past week" the last 7 days, a month is 30
  days for ages; daylight-saving gaps move forward, repeats take the first.
- A draft reply has no "use this reply" card in R1, so draft_reply returns a schedule_message card
  with no time. prepare_scheduled_message refuses an ambiguous contact (listing matches) and a
  closed reply window; a time past the window leaves send_at empty with the latest allowed time.
- Not built in R1: engagement_trend, account_metrics, lead_metrics, above_average_posts,
  sentiment_trend and compare_sentiment (no read query in services/analytics yet).

## C-047 · PA web and evaluation decisions (TA.5, TA.6)
- Web: Ctrl/⌘ K opens the panel (inbox shortcuts are unmodified letters); pre-fills reach the
  target screen through a client hand-off store, not search params; the automation draft card
  creates a saved draft only when the member confirms "Open in editor". Follow-up chips are chosen
  in the browser from the cited kinds; no API call. While a run works the member can type and
  the send button becomes Stop.
- Evaluation (tests/evals, scripts/agent_eval.py): 120 cases in English, Hindi and Hinglish on a
  seeded workspace with a pinned clock. v1 baseline: every check passed in 113/120, tool choice
  100%, grounding 98.3%, exact numbers 98.2%. Prompt agent.v2 adds the member's role, brackets
  only for [n], dates from labels, and customer text only from results; it passed 46/48 before
  the free-tier Gemini quota ran out (500 requests a day). A full run needs about 330 requests
  (paid key, or one run a day). The acceptable tool sets are generous, so 100% tool choice
  overstates precision.

## C-048 · Sidebar redesign
- Groups: Home; Engage (Inbox, Comments); Grow (Schedule, Automations, Knowledge; owners and
  admins only, so the agent role sees no Grow heading). Width 232 px expanded, 64 px collapsed;
  Ctrl/⌘ [ toggles it (on a Mac ⌘[ may stay the browser's Back).
- The Comments badge (GET …/comments/counts, needs_reply) counts comments from the last 7 days
  (Instagram's private-reply window) that aren't spam, hidden, deleted or replied to; without the
  window the connect backfill and replies made in the Instagram app would pin it at 99+. The
  Inbox badge stays unread conversations (FR-INB-04).
- The usage card shows AI credits; Upgrade shows only to owners and admins on Free or at 80% or
  more used, never on Max. The "Reconnecting…" pill appears only after 5 s without the event
  stream (each stream closes every 30 minutes and reconnects in about 3 s).

## C-049 · P8 foundation decisions (contract)
- Notification preferences stay in `workspace_members.notification_prefs` (§5.3), not a new table:
  FR-NOT-03, F-19 and UX-SCR-07 define only the weekly digest switch and four push switches (Needs
  you, new lead, window closing, account); in-app notifications are always on (FR-NOT-01) and the
  FR-NOT-02 emails are not optional. GET and PUT …/notification-preferences use the stored shape;
  PUT sends the whole object.
- `push_subscriptions` is user-scoped (§5.3): one row per browser endpoint (unique, https only); a
  device gets the pushes of every workspace its user is in, filtered by that membership's
  switches. Added `failure_count` and `disabled_at` (5 failures in a row disable; 404 or 410
  delete, TR-FE-09). Registering an endpoint again moves it to the caller. DELETE
  /v1/me/push-subscriptions takes `?endpoint=` (no DELETE body) and only ever removes the caller's
  row (204 either way).
- The web reads the VAPID public key from GET /v1/push/config ({enabled, vapid_public_key}), not
  NEXT_PUBLIC_VAPID_PUBLIC_KEY (TR-FE-09, §2.16), so one build serves any key and push shows as
  unavailable when the API has none.
- Dodo events are logged in `webhook_events` (§5.9: provider dodo, dedupe `dodo:{webhook-id}`),
  which gains `occurred_at` (Dodo's payload `timestamp`); the ordering guard stays
  `subscriptions.last_event_at` (TR-BIL-02). POST /webhooks/dodo is built in the foundation and
  fails closed: 503 without DODO_WEBHOOK_SECRET, 401 unless the Standard Webhooks signature over the
  raw body verifies within 5 minutes, 400 for a body that isn't a JSON object; a verified event is
  stored once and processed by process_webhook_event through services/webhook_handlers/dodo.py.
- Dodo sends events TR-BIL-02's table doesn't list (checked 2026-09-30): subscription.updated,
  past_due, paused, unpaused; payment.processing and payment.cancelled; refund.* and dispute.*.
  T8.3 maps them; proposed: past_due as on_hold (grace, FR-BIL-06), paused as on_hold, unpaused as
  active, updated refreshes the period and cancel flag only, processing is a pending payment,
  cancelled a failed one, refund and dispute events are logged and ignored.
- `payments` follows §5.8 plus `dodo_subscription_id` and `failure_reason` (shown in the payment
  problem email).
- The 402 codes are the spec's two: entitlement_required and quota_exceeded (a capacity limit is
  quota_exceeded, TR-BIL-04). A 402 also carries `entitlement` (the §1.7 key) and `limit` (a number,
  or null for a missing feature) as problem extension members (`errors.PlanLimit`), so the upgrade
  dialog names the limit without parsing `detail`.
- Billing contract: POST …/billing/checkout {plan} returns {checkout_url, trial} (409 when a paid
  plan exists, 422 for max until R2); …/portal returns {portal_url}; …/cancel and …/resume return
  BillingState. Added a public GET /v1/billing/plans (plans, entitlements and Dodo prices) for
  /pricing and the upgrade dialog. No billing event type: plan and status changes publish
  usage.updated, on which the web refetches GET …/billing (F-15 already waits for it).
- Dodo client: a thin client over the shared httpx client (§2.2 "Dodo REST via httpx"), not the
  generated dodopayments SDK; signatures with the standardwebhooks package (already under svix,
  now a direct dependency). DODO_ENVIRONMENT `live` or `live_mode` selects live, anything else test.
- Email: `email_deliveries` is a transactional outbox (not in the spec), unique per (workspace,
  dedupe_key); the dedupe key is also Resend's Idempotency-Key, so one event sends one email
  (T8.5). The template is checked in code, not the database. The spec's
  deliver_email(notification_id) takes the outbox row (delivery_id, workspace_id) instead, because
  digest emails have no notification; its module is jobs/tasks/emails.py. A sweeper re-enqueues
  rows still queued after a minute.
- Emailed notification types: account_needs_reconnect, payment_problem, plan_activated,
  plan_downgraded, post_failed (FR-NOT-02 plus F-15's "We'll email you when Pro is active" and the
  downgrade). Pushed types: ai_escalated (Needs you), new_lead (new: lead score reaches 70),
  window_closing, account_needs_reconnect and account_disconnected (account). Producers pass only
  the type; services/notifications decides the channels. `notifications.channels` is checked to
  in_app, email and push, and gains `pushed_at`.
- Push: pywebpush encrypts (aes128gcm) and py_vapid signs, but the POST goes through the shared
  httpx client. The service worker's payload is {title, body, url, tag}, at most 3,000 bytes,
  where url is `/w/{slug}` + the notification's link.
- Weekly digest: `weekly_digests` (not in the spec) is unique per (workspace, week_start), the
  local Monday; it is the durable once-a-week guard that the job catalogue's
  `digest:{workspace}:{iso week}` lock only approximates.
- Unsubscribe: no table. A 66-character HMAC token naming the workspace and user, keyed from
  TOKEN_ENCRYPTION_KEYS (the newest signs, all verify; no new secret), never expiring. POST
  /v1/digest/unsubscribe?token= is public and is also the RFC 8058 List-Unsubscribe-Post target;
  there is no GET, so link scanners can't unsubscribe anyone. The email's link opens a public web
  page, /unsubscribe?token=, which posts.
- DODO_PROVIDER, EMAIL_PROVIDER and PUSH_PROVIDER (`fake` for local runs, refused in production)
  mirror AI_PROVIDER. Migration 0013 gives any workspace without a subscription row a Free one.

## C-050 · P8 billing decisions (T8.1–T8.3)
- The reconcile job is `reconcile_billing` (every 6 h): the job catalogue's reconcile_subscriptions
  is already the webhook re-subscription task (TR-WH-08).
- `credits_gate` wraps the credit routes at service level, so a service's own refusals (a 409 for
  AI that is off) come first and its credits 402 leaves with `ai_credits_monthly` and the limit.
- Read-only accounts (FR-BIL-07) are computed, not stored: each platform's earliest connected
  accounts keep the plan's slots (`read_only_accounts`), so an upgrade or a disconnect frees them
  at once. Publishing is not gated by it (scheduled_posts_monthly is the publishing gate).
- Anchor day: Dodo's period start on a paid plan, the workspace's creation day on Free; a plan
  change gives the current period's counters the new plan's limits.
- Checkout always sends the trial, 7 days when eligible (TR-BIL-05) or 0, because the Dodo product
  carries its own; 409 while a paid plan is live, 422 for Max until R2, 503 when Dodo fails.
- Cancel and resume mirror Dodo's answer (the subscription Dodo returns), not the request.
- Reconcile never makes a Free workspace paid: only a signed event grants a plan.
- Payment events write `payments` (status only moves forward) and never move
  `subscriptions.last_event_at`, so a late payment event can't hide a newer subscription event.
- A second live subscription (two checkouts at once) is logged as an alert
  (`billing_duplicate_subscription`) and ignored; someone cancels and refunds it in Dodo.
- State machine (TR-BIL-02 plus C-049's mapping): active and renewed grant (trialing inside the
  trial); plan_changed moves the plan; on_hold, past_due and paused hold with 3 days' grace;
  unpaused restores; cancelled keeps the plan to the period end; failed and expired go to Free
  with the downgrade effects. Events older than last_event_at are ignored.

## C-051 · P8 web decisions (T8.4, T8.6 web)
- Billing actions (checkout, portal, cancel, resume) are owner-only; admins get the page
  read-only; agents are redirected to Notifications.
- One global 402 handler (lib/api/provider.tsx) opens the upgrade dialog for any query or
  mutation. A screen that explains the limit inline opts out with `meta: INLINE_PLAN_LIMITS` and
  shows Upgrade beside its message; `toastError()` skips the toast for plan limits, so each 402
  shows one message.
- After "Not now" the same limit doesn't reopen the dialog for 30 s (no reopen loop).
- Checkout return polls GET …/billing every 3 s for 60 s ("Confirming your payment…") and never
  assumes success; usage.updated also refetches.
- A trial-ending banner (owners, last 3 days, dismissible) is not in the spec.
- The service worker registers only in production builds or with NEXT_PUBLIC_ENABLE_SW=1.
- The /unsubscribe page posts the token from the browser after it loads (no GET unsubscribes, so
  link scanners can't).
- Sign-out first removes this browser's push subscription (DELETE while still signed in, then
  unsubscribe), best effort, capped at 2 s.

## C-052 · P8 billing follow-ups
- FR-BIL-07 at send time: `services/sending.queue_outbound` and `retry` refuse a read-only
  account with the 402 (quota_exceeded, `accounts_per_platform`, the limit). Every sender goes
  through it: the send route, scheduled messages, AI Auto, automation DMs, tap-first answers and
  nudges. Comment replies (public and private) check too; hide, unhide and delete don't (they send
  nothing). Reading, syncing and publishing stay allowed.
- A due scheduled message on a read-only account fails like any pipeline refusal: `failed` with
  error_code quota_exceeded and the 402's reason; no notification (only expiry notifies).
- The automation runtime records a new run result, `skipped_read_only` (migration 0014; error_code
  `read_only`, the 402's reason), for the first match that isn't cooling down, and sends nothing.
  The private-reply queue holds a read-only account's queue like a reconnect-needed one (runs
  still expire after 7 days). The stats' skipped counts don't list it (contract unchanged).
- The agent run and post summary 402s now go through `credits_gate`, so they carry
  `ai_credits_monthly` and the limit, with §4.7's credits copy.
- Clerk user.deleted cancels each solely owned workspace's Dodo subscription before deleting it.
  If Dodo fails the workspace is still deleted and an error log names the Dodo subscription id;
  reconcile can't catch it (the subscriptions row goes with the workspace), so it is cancelled by
  hand. DELETE /v1/w/{wid} (FR-ACC-05) is left to T9.6 (TODO in services/workspaces.py).

## C-053 · P8 notification decisions (T8.5–T8.7)
- Producers pass only a notification type; services/notifications.py picks the channels. Email
  goes to owners and admins only (account_needs_reconnect, post_failed, payment_problem,
  plan_activated, plan_downgraded; not optional). Push switches: needs_you (ai_escalated),
  new_lead, window_closing, account (account_needs_reconnect, account_disconnected). In-app is
  always on.
- Delivery jobs are queued by an after_commit listener, so a rollback queues nothing. Emails: 5
  tries (10/20/40/80 s), a sweeper every minute, failed after 24 h queued; skipped if the member
  left or turned the digest off. Resend's Idempotency-Key is {workspace_id}:{dedupe_key}; 5xx and
  rate-limit errors retry, daily and monthly quota errors don't.
- Push: endpoints must belong to a browser push service (FCM, Mozilla, Apple, WNS) over https
  (SSRF guard); at most 10 browsers per user (least recently used dropped); 404/410 deletes the
  subscription, 5 failures in a row disable it. Payload {title, body, url, tag}: title 80 and
  body 240 characters, url /w/{slug}{link}, TTL 24 h. No push sweeper: a late push is useless.
- new_lead fires once per conversation when the lead score crosses 70, naming the intent, never
  quoting the message.
- Weekly digest: send_weekly_digests runs every 15 minutes (so UTC+05:30 gets 09:00, not 09:30);
  a workspace is due Monday from 09:00 local until the day ends, claimed by a weekly_digests row;
  it covers the previous local Monday to Sunday; a quiet week is recorded as skipped. Its numbers
  come from services/overview_stats.py, which T9.1's overview must use (reply rate per
  conversation, handled by AI, median first response per customer turn, top intents without
  other and spam, needs you, open questions from 30 days, comments without deleted ones).
- Unsubscribe: an HMAC token computed at send time and never stored; POST only (404 for a bad
  token, safe to repeat); List-Unsubscribe headers only when API_BASE_URL is set.

## C-055 · P9 Home decisions (T9.1)
- The range is 7 or 30 local days up to today in the workspace's time zone; each tile's trend
  compares with as many full days just before it (`previous`), not a rolling window.
- Every number comes from services/overview_stats.py, the weekly digest's functions (C-053), so
  Home and the digest agree; Needs reply is the inbox chip's own count.
- Handled by AI trends in a neutral colour: more or less AI is neither good nor bad news. Faster
  first responses and a higher reply rate are good (green), the opposite red.
- Sentiment bars split positive, neutral and negative; spam is counted apart, beside the bar.
- Most commented posts show each post's own sentiment split, as the Comments page does.
- Accounts needing attention (needs reconnect or error) are listed with their status.
- Response fields are strict and nullable: no data is null ("—" and a hint), never a zero or a
  fake chart.
- Switching range keeps the previous numbers on screen until the new ones arrive, never another
  workspace's; Home refetches after relevant real-time events (throttled) and every 5 minutes.

## C-056 · P9 workspace deletion decisions (T9.6; FR-ACC-05, F-16, §5.9)
- DELETE /v1/w/{wid}: owner only, the typed workspace name confirms (422 on a mismatch), 202 with
  purge_by (24 hours). Web: Settings → Workspace danger zone, owners only.
- Two steps. In the request: status deleting (who and when), tokens destroyed, accounts
  disconnected, automations paused, unstarted scheduled messages and posts cancelled, queued
  emails skipped. The API answers 404 for a workspace that isn't active.
- The owner lands in another of their workspaces, or a new personal one when it was the last.
- purge_workspace (bulk lane, lock purge:{id}) is queued after the commit and cancels Dodo first,
  at once rather than at the period end; "nothing to cancel" counts as done.
- Tenant tables are deleted from the TenantScoped registry, children first, in committed batches,
  so a new table is covered and a stopped run resumes; a run hands over after 540 s.
- Then its webhook events, Valkey keys (every key naming the workspace or its accounts) and the
  Cloudinary folder ws/{id}/.
- The subscription and workspace rows go last, only once Dodo, keys and media are done, so a
  failed cancel is retried (8 tries with backoff).
- sweep_deletions (every 15 minutes) re-queues every deleting workspace and alerts after 6 hours.
- Clerk user.deleted takes the same path; migration 0015 lets a deleting workspace outlive its
  owner and records who asked.
- purge_expired (daily 04:00 UTC): webhook events 30 days, notifications 90, AI usage 13 months,
  finished agent runs 180 days, Free message history 90 days (emptied conversations too),
  finished queue jobs 30 days.
- Idempotency keys expire in Valkey (24 hours) and R1 has no audit_logs, so neither has a rule.

## C-057 · P9 ops decisions (T9.3, T9.5)
- Sentry on the API, worker and web, a no-op without a DSN. Scrubbed: no headers, cookies,
  bodies, query strings, emails, tokens or message text; the user keeps only an id; no local
  variables; the Gemini and Pydantic AI integrations stay off.
- Only a job's final failure reaches Sentry (tagged job, lane, workspace_id), not its retries;
  error-level logs (`log.error("alert", kind=…)`) arrive as `alert_kind` events.
- /metrics serves Prometheus text behind METRICS_TOKEN (constant time; 404 unset, 401 wrong).
- The worker has no endpoint: every process buffers its counts and flushes them to a shared
  Valkey registry every 5 s, so one scrape of any API instance covers everything. Labels come
  from code (route templates, task names), never ids.
- The four T9.3 alerts (dispatcher lag, webhook, send and AI failure rates) are Prometheus rules
  for Grafana Cloud, with promtool tests, plus worker down, backlog, failed jobs, 5xx and scrape
  health; Sentry can't compute the ratios.
- Render Blueprint: one project, a production stack (branch production) and a staging stack
  (main), Singapore, deploys after CI passes. Secrets live in a hand-made group per environment,
  because a Blueprint-managed group can't hold them.
- Migrations run only in the API's pre-deploy and stay expand-only, so a worker that starts first
  is safe; DATABASE_URL accepts Render's postgresql:// string.
- SENTRY_RELEASE defaults to RENDER_GIT_COMMIT; the web is on Vercel (sin1, Node 24).
- Backups are Render's point-in-time recovery (7 days on Pro); the restore rehearsal script ran
  read-only against the dev database (49 tables and 56,827 rows matched).

## C-058 · P9 security pass decisions (T9.2)
Evidence per item: docs/security-checklist.md.
- Webhooks are not IP-limited (Meta shares IPs); their bodies stay capped at 5 MB.
- Scheduled messages and publish-now count as sends (60 a minute per workspace).
- The AI class (20 a minute) covers every model call a member can trigger: agent runs,
  summaries and hashtags as well as the spec's three.
- Public routes get 60 a minute per IP; the OAuth callback keeps the spec's 30.
- The checkout return has no public route: the billing page polls under the per-user limit.
- Limits fail open when Valkey is down, like idempotency and last-seen.
- New settings: RATE_LIMITS_ENABLED (refused false in production) and CLIENT_IP_HEADER (required
  in production; the integration pass changed Render's value, C-060).
- The web CSP is built from the build's NEXT_PUBLIC_* values (API, Clerk, Sentry);
  upgrade-insecure-requests only when the API is https.
- No per-operation 429 in the OpenAPI document: the default problem response covers it.
- X-1 (login CSRF on Instagram connect) was left as a gap for the integration pass (fixed, C-060).
- Accepted risks:
  - A-1: Instagram inbound media downloads skip the SSRF guard (Meta-signed URLs, Meta-hosted
    kinds only, 100 MB and 60 s caps); allowlist Meta's CDN hosts once live payloads confirm them.
  - A-2: WhatsApp media sends the bearer token to the URL Graph returns (trusted; no redirects).
  - A-3: the Cloudinary upload signature signs only folder and timestamp; registration enforces
    size and format, and unregistered files are never served.
  - A-4: the web CSP keeps `script-src 'unsafe-inline'` (Next.js bootstrap) and allows Meta's
    SDK app-wide (a CSP belongs to the document, and client navigations keep it).

## C-059 · P9 end-to-end suite decisions (T9.4)
- Only Clerk is real: its development instance with testing tokens, one reused test user signed
  in with a sign-in token; F-01 signs up a throwaway `+clerk_test` user and deletes it after.
- Everything else is the sandbox platform and fakes (AI, Dodo, email, push), on its own stack:
  socialhood_test_6, Valkey db 5, ports 8100 and 3100, refusing the development stack. The API
  and worker run where no .env is loaded, so local and CI runs see the same settings.
- Test-only seed routes (/__e2e, behind a per-run token) live in a separate e2e API entry that
  refuses to start unless the sandbox is on, Dodo is the fake and the app isn't production.
- A fresh workspace per test; the web is a production build (next build, next start).
- The worker's fake AI gives one fixed suggestion, and "can't answer" for `[e2e:unknown]`.
- Nightly in CI at 21:30 UTC with one retry (none locally), artifacts kept 7 days; T9.4 is done
  after three green nights. The suite found two app bugs (F-01's session wait, F-08's card
  coming back), fixed with unit tests.

## C-060 · P9 integration pass (p9/integration)
- X-1 fixed (login CSRF): the OAuth callback no longer connects. It keeps the code, encrypted,
  under a one-time nonce in Valkey (`oauth:held:{nonce}`, 10 minutes) with the state's user and
  workspace, and redirects to Connections with `?instagram={nonce}`. The page posts it to
  `POST …/social-accounts/instagram/complete` (Admin), which takes it with GETDEL and connects
  only for that user in that workspace. The code is kept rather than the token: short-lived,
  single-use and useless without the app secret.
- The complete call's answers: 404 expired or used ("That connection link expired."), 403
  someone else's, 409 account_in_use, 402 quota_exceeded, the new 422 `ig_not_professional`
  (§4.7's code) and 502 platform_error. A 402 now opens the upgrade dialog like every other 402,
  instead of the old toast. The spec's F-03 steps are updated.
- WhatsApp Embedded Signup is not affected: the code comes back to the signed-in page's own
  JavaScript and is posted with the member's bearer token.
- No connect for a workspace being deleted: the callback refuses one that isn't active, and the
  Instagram and WhatsApp connects re-read the workspace row FOR SHARE before storing an account.
- A live Dodo subscription whose workspace is missing or deleting (a checkout paid after the
  deletion) raises `alert_kind:billing_orphan_subscription` and queues
  `cancel_orphan_subscription` (bulk lane, one per subscription): cancel now, retried about 25
  minutes while Dodo fails. An event with neither our metadata nor a stored subscription is not
  ours and is left alone.
- Client IP on Render: Render documents only X-Forwarded-For, so `CLIENT_IP_HEADER` is
  `x-forwarded-for`, read from the right past Cloudflare's published ranges and private ranges
  (the rightmost untrusted hop), not `true-client-ip`. uvicorn runs with `--no-server-header`;
  its own client address (the header's first entry) is used for nothing.
- Log fields named `code` are blanked by the redaction (SEC-07); the 13 error codes are logged
  as `error_code` now, and a unit test fails on a new one.
- "Choose an AI mode" (Q-008) is done when any connected account's AI mode is Suggest or Auto,
  and links to Settings → Connections, where the mode is set; it usually ticks with the first
  account, since new accounts start in Suggest (FR-SUG-01).
- A post video's delivery version (`vc_h264,ac_aac,f_mp4`) is rendered eagerly when the video is
  registered, so Instagram's fetch doesn't wait about 20 s for an on-the-fly render (P7b spike).
  The transformation stays: posts take MP4 and MOV in any codec. Best effort; the URL still
  renders on first fetch if Cloudinary refused.
- Tests: the tenancy route walk mints a token per request (it outlived the 60 s token); the new
  route has its isolation example body.
- e2e: the stack runs with `RATE_LIMITS_ENABLED=false` (one Clerk user from three workers passes
  the per-user 300 a minute), and its user cleanup route deletes the workspace row directly
  (the deletion pass removed `repositories.workspaces.delete_workspace`).

## C-061 · WhatsApp Embedded Signup without full session info (F-04, verification item 14)
- Seen live: Meta's popup finished, the page never got a session info with both ids and showed
  "Meta didn't say which number was chosen" without calling the API. The code is what matters
  now: once FB.login returns it, the page waits at most 5 s for the session info and completes
  through the API either way, sending only the ids it got. Every `FINISH*` event counts as a
  finish (`FINISH_ONLY_WABA` names the WABA but no number). A closed dialog (no code), `CANCEL`
  and `ERROR` are unchanged. Development builds log event names, FB.login's status and whether a
  code came to the console, never the code.
- `waba_id` and `phone_number_id` are optional in the request. The API fills a missing WABA from
  Meta's documented fallback, `debug_token` read with the app token
  (`whatsapp_business_management` `target_ids`), and a missing number from
  `/{waba_id}/phone_numbers`. It takes the only one; none or several is a 422 for the owner to
  settle in Meta's popup: `wa_choose_business_account`, `wa_no_phone_number` (its copy says
  Meta's test numbers can't be connected this way) or `wa_choose_number`. Meta says the newest
  WABA is listed first; we don't guess from that. A discovered number is checked against the
  plan after the code exchange (a known one still before). The discovery path is logged
  (`whatsapp_signup_ids`: waba_source, phone_source), never a token.
- After the token, Embedded Signup and the new development script
  (`scripts/connect_whatsapp_number.py`, docs/dev-whatsapp.md) share `connect_number`: plan limit,
  active workspace (FOR SHARE), `account_in_use`, the encrypted token, `subscribed_apps` and
  registration. The script is for Meta's test number, which Embedded Signup can't connect; it
  takes the token from `WHATSAPP_DEV_TOKEN` and refuses production.

## C-062 · Jobs left running by a dead worker; small-talk replies (live testing)
- Seen live: a worker restarted during `ingest_knowledge_source` left the job `doing` and the
  source `processing` with 0 chunks for good. Every Render deploy stops the worker, and
  `scripts/worker.sh` didn't forward SIGTERM (bash exits on it, so whether the lanes could drain
  depended on how the host signals the process tree). Worse than a lost job: a dead `doing` job
  keeps its run lock, and Procrastinate
  starts no job with that lock again. The domain sweepers settle their rows (sends, scheduled
  messages, posts, agent runs, emails, webhook events) but not the job, so the conversation's
  next send (`conv:`), the re-queued publish or poll (`pub:`, `poll:`), the resumed agent run
  (`agent:`), the account's private-reply drain (`prq:`) and the conversation's next analysis
  (`analyze:`) waited behind it for ever. `post_first_comment` had no recovery at all.
- `recover_stalled_jobs` (every 2 minutes, bulk lane) takes the jobs of workers silent for 90 s
  (`get_stalled_jobs`; `prune_stalled_workers` on the same threshold) and settles each by its
  task's class in `jobs/recovery.py: RECOVERY`, one table with every task (a unit test fails for
  a task missing from it): RETRY (idempotent, and every periodic task) back to `todo` while
  under 3 attempts, else failed; SWEEPER (`send_message`, `send_private_reply`,
  `send_scheduled`, `publish_target`, `poll_container`, `run_agent`, `process_webhook_event`,
  `deliver_email`) aborted, never re-run, so the lock frees and the sweeper decides; FAIL
  (`post_first_comment`, `deliver_push`, unknown tasks) failed with `alert_kind:stalled_job`.
  A stalled job whose queueing lock another waiting job holds is aborted: that job does the
  work. `run_automation` and `drain_private_replies` are RETRY although they write to the
  platform: a run recorded per event, and replies committed `sending` before the call, make a
  re-run send nothing twice (both already re-run after any exception).
- Shutdown: `worker.sh` gives each lane one SIGTERM (each lane in its own session, since a
  second SIGTERM kills a Procrastinate worker at once) and waits. Procrastinate's
  `shutdown_graceful_timeout` stays unset: an aborted job ends `aborted`, never retried nor
  listed as failed, while one Render kills after its 60 s grace stays `doing` for the recovery.
  The heartbeat stops as soon as a worker is asked to stop, so 90 s has to exceed that 60 s plus
  the 10 s heartbeat (tested against `infra/render.yaml`), and the worker's own startup prune
  (`stalled_worker_timeout`, Procrastinate's default 30 s) uses 90 s too.
- The ops CLI no longer retries `post_first_comment`, `send_private_reply` or `deliver_push`
  (`PLATFORM_WRITE_TASKS` named two tasks that don't exist instead).
- Fixed after (fix/queued-private-replies): a member's private reply (T6.3) whose job died before
  its claim stayed `queued`, and `sweep_messages` re-queued it as `send_message`, which sent it
  as a plain DM or failed it on the closed window while the comment kept its one private reply.
  Only these are ever `queued`: an automation's private reply is stored `sending` by the drain,
  so a dead drain's reply was already the sweeper's delivery_unknown, settling its run. Now
  `messages_repo.in_flight` names the comment of a queued human message linked from
  `comments.private_reply_message_id` (looked up among the workspace's comments of the 7 days
  before it, on ix_comments_workspace_commented, so no migration), and the sweeper hands it
  back to `send_private_reply` (`private_replies.requeue`, same `send:{id}` key), never to
  `send_message`. One left `sending` still ends delivery_unknown and keeps the comment linked;
  nothing re-sends it. The job now holds a queued reply of an account read-only after a
  downgrade (FR-BIL-07), as the automations' queue does: still queued, looked at again every
  10 minutes, sent once the account may send, failed with the 7-day reason after that. A
  reconnect-needed account fails it as before (`account_needs_reconnect`, the comment freed).
- Seen live: a WhatsApp "Hi" was analysed right (greeting, neutral, lead score 10), but its
  suggestion came back `can_answer: false`, no text, gap "business information". No code forced
  it: suggest.v2 only said "use only facts from KNOWLEDGE", and the model read a greeting as a
  question about the business. suggest.v3 (`ai/prompts.py`) adds a rule: small talk (greeting,
  thanks, goodbye, "ok") is answered without knowledge, in kind, with no business fact and no
  missing topic; "Hi, what's the price?" is not small talk. The same prompt drafts automations'
  AI replies and knowledge's "Try a question", which now answer small talk too.
- Small talk in code (`services/suggestions/small_talk.py`), the net under the prompt: the whole
  text is small talk in English, Hindi or Hinglish (a phrase list: "hi", "good morning", "thank
  you so much", "kaise ho", "shukriya", "धन्यवाद", "ठीक है"…, with "sir", "ji" and punctuation
  allowed) and the analysis intent is greeting, feedback or other (or there is no analysis). The
  intent list has no thanks or goodbye (a "thanks!" is labelled feedback or other), and adding
  intents would change the enum, its check constraint and the contract, so the text decides and
  the intent can only rule out: an "ok" read as a purchase goes to the model. Emoji alone are
  left to the model (an emoji can be angry). When the model still declines small talk, the
  suggestion is a fixed reply of the same kind in the customer's language (Devanagari → Hindi;
  Hinglish words or a `hi` analysis → Hinglish; else English), e.g. "Hi! How can I help you
  today?", with confidence 0.9 and no sources, so small talk never records a knowledge gap.
- Auto: allowed. Check 11 wants knowledge only for fact intents, so a small-talk reply goes out
  when it passes everything else (confidence ≥ AUTO_MIN_CONFIDENCE, which the fixed reply's 0.9
  meets by default; no human request, no negative sentiment, the rate cap, the output filter).
  No check changed. The prompt still needs its eval run (docs/ai-eval-log.md).

## C-063 · Inbox redesign (owner-approved layout) and three small AI features
The layout and structure follow the owner's mockup; colours stay ours (tokens and theme).
- List column: a segmented platform control (All, Instagram, WhatsApp, labelled at every width)
  replaces the coloured strip; "Inbox" sits beside the Chats | Scheduled segments; the search is
  full width with the account filter beside it when a platform has several accounts. Chips: All,
  Unread, Needs reply, Needs you, Leads, AI handled; Archived is behind "More". Needs you is a new
  list view, `view=needs_you` (open conversations with `needs_human`, the test
  InboxCounts.needs_you already used); Ask Social Hood's search tool accepts it too.
- Rows: 40 px avatar with the platform badge, time on the right, "You:", "AI:" or "Auto:" before
  our own previews (AI: stays for auto replies), and small badges: "Needs you", the other signals
  (complaint, closing soon, negative), "Lead 72/100" from the lead threshold (60, the API's
  LEAD_SCORE; the mockup's 40 would not be a lead) and "AI Auto" when the AI replies on its own.
  The API's list item gains `ai_mode_override`; the row takes the account's mode when it is null.
  Rows are 68 px, or 90 px with badges, fixed so the virtualised list needs no measuring. The
  selected row has a brand bar on the left.
- Thread header: avatar, name with the window chip beside it (neutral, amber under 2 h, red
  "Window closed"), then handle · platform · our linked account (always, not only with several
  accounts). The AI mode menu ("AI: Suggest") is the only AI mode control: the details panel's
  segments are gone; its takeover pause and escalation stay there as short notes, and Resume
  stays in the menu. Scheduling (md and up), the panel toggle and the More menu follow.
- Messages: time, delivery ticks and, for `ai_auto` and `automation` messages, "AI Assisted"
  (its tooltip says an auto reply, or names the automation) sit under the bubble; the "why"
  button of an auto reply moved there too. "Sent from Instagram" stays inside the bubble; an
  unsupported message is a small card with "View in …".
- The suggestion card is a slim bar above the composer: "AI draft: …" with Insert (was Edit),
  Send, Draft again (was Regenerate) and Dismiss, the sources and "Check this" as small chips;
  the gap state reads "Not in your knowledge: …" with Add to knowledge. Still one draft; no
  quick-reply chips.
- Composer: the text box on top, a toolbar under it (attach, emoji, heart or sticker, AI Polish,
  schedule) and Send. No "knowledge" button: there is no knowledge search to open (the Knowledge
  page's test costs a credit).
- Context panel: Customer (Follows you when known, customer since, linked account, lead score
  bar, Open in Instagram or WhatsApp when there is a profile), Latest message (intent, sentiment,
  priority, the analysis's topics as they are, Teach AI, Correct the AI) and Summary (the text,
  a Next step callout, Refresh). Inline from 1280 px (300 px, 320 px from 1440 px), a sheet
  below. The header toggle collapses it; the choice is remembered per device
  (`socialhood:inbox-details`, localStorage behind try/catch); with no choice yet it starts open
  from 1440 px and collapsed below.
- AI Polish: `POST …/conversations/{id}/polish` `{text, tone?}` → `{text}` (AnyMember, AI rate
  limit, credits gate). Prompt `polish.v1`: grammar and clarity in the draft's own language and
  script (English, Hindi, Hinglish in Latin letters), same meaning and roughly the length, no new
  facts, prices or promises; the brand voice's tone unless the request names friendly or
  professional. The last 6 messages go as context, none with AI analysis off for the account
  (FR-PRV-02). An answer that adds a number, link, email address or phone number, is empty or is
  longer than twice the draft (or 200 characters more for a short one) is refused with 503 and
  refunded, never shown. Feature `reply_polish`, 1 credit; migration 0016 lets
  ai_usage_events.feature take it (its downgrade deletes those events). The composer replaces
  the text and offers Undo until the text is edited; text typed during the call is kept.
- Summary next step: prompt `summary.v2` asks for one concrete, verb-first suggestion from the
  conversation and KNOWLEDGE only, or null. KNOWLEDGE is the chunks the conversation's newest
  knowledge-backed draft used (at most 4), read from the database, so the summary stays one model
  call with no retrieval or embedding. `next_step` was already in the schema and stays null on
  older summaries.
- Teach AI (web): from the panel's latest message, and the draft bar's Add to knowledge, the
  existing SourceSheet opens in place (no trip to the Knowledge page, so no hand-off store or
  search params) as an FAQ with the customer's question; the member writes the answer. The open
  gaps are read when it is used; the gap whose examples include that message goes with the FAQ
  as `gap_id`, so saving answers it. Owners and admins only, like knowledge.
- The mobile and tablet single-pane navigation is unchanged; the panel opens as a sheet from
  the header toggle. The sidebar is unchanged.

## C-065 · Home redesign (owner-approved layout, feat/home-redesign)
- Layout from design/social_hood_home, our tokens and theme. Header: the greeting; "Overview
  across Instagram & WhatsApp" names the platforms of active accounts ("No channels connected
  yet" without any); "Last 7 days · 24–30 Sep" is the API's local days; the pill counts active
  accounts; 7 days / 30 days / Custom; Refresh refetches the overview (the spinner is
  motion-safe). A failed refresh keeps the last numbers with a notice.
- Custom range: GET …/overview?from=YYYY-MM-DD&to=YYYY-MM-DD, local days in the workspace's time
  zone, both included, at most 90 days, `to` no later than today; 422 with the field (`from`
  after `to` or over 90 days: from; in the future or missing: to; `range` with from/to: range).
  `previous` is as many days just before (`period_before`, as for 7d/30d). The response says
  `range: "custom"` and `days`. The web checks the same rules before sending and remembers the
  choice per workspace (`custom:{from}:{to}`); a stored range that no longer holds falls back to
  7 days. States (needs reply, queue, gaps) stay "now" whatever the range.
- Badges are rules, not scores: **Attention** on Needs reply when it is above 0 and the
  longest-waiting "Needs reply" conversation's unanswered turn began more than an hour ago
  (`oldest_waiting_since`: the first customer message after the business last wrote, else the
  last customer message); **Fast** when the median first response is under 5 minutes.
- Priority queue: `Overview.priority_queue` (up to 5), not a separate route, so it refreshes with
  Home and matches the Needs reply count it sits beside (services/priority_queue.py). Candidates
  are the inbox's own sets: open conversations with a message that need you (`needs_human`) or a
  reply (`awaiting_reply`). Order: needs you first; then lead score (none last), analysis
  priority (critical to low, none last), the longest wait (`waiting_since`), the id. Left out:
  archived ones always; needs-reply ones whose window is closed (no free-form reply: Instagram
  after 24 h, or 7 days for a person with Human Agent; WhatsApp after 24 h, template only). A
  needs-you conversation stays whatever its window. `has_pending_suggestion` is a pending
  suggestion that can answer and has text (a pending "can't answer" card is no draft). Row
  action: Review & Send with a draft, else Open chat; both open /inbox/{id}, where the draft
  shows. The row shows the customer's last message (not unsent), clipped to 140 characters.
- Real time: suggestion.created and suggestion.updated join the events that refetch Home
  (throttled, as before), so "AI draft ready" appears; a message or a reply was already one.
- Knowledge gaps: no migration. A gap's `example_message_ids` (newest first) already name where
  it came from, so `latest_gap` is the open gap asked most recently (30 days) with its newest
  example that still exists and isn't unsent: its text is the question, its conversation is
  View thread. A comment's gap has no example: no View thread, and the question is the topic.
  Train AI (admins, who manage knowledge) opens the FAQ sheet with that question and the gap's
  id (lib/knowledge/prefill.ts, shaped like SourceSheet's create mode so the inbox's Teach AI can
  share it); saving is POST …/knowledge-sources with `gap_id`, which answers the gap (F-17).
  Agents see the banner with View thread only.
- Engagement rate on Most commented: only from post metric snapshots captured in the range: per
  post, its latest such snapshot with reach and all four counts, (likes + comments + shares +
  saves) ÷ reach in % (the analytics definition); `top_posts_engagement` is the mean over the
  posts that have one, with how many. No snapshot, no figure.
- Dropped from the mockup: "NLP Engine", "AI Classified", "98.4% Confidence", "Overall tone",
  "Accuracy 98%", "Instagram Graph", "Engagement +14.2%" (no such values exist), the "Needs Input"
  chip on the gap banner, and the emoji in the greeting. "7 total queries" became "n messages in
  these topics" (the sum of the listed intents). Kept from before: the onboarding checklist and
  account health, which the mockup doesn't show.
- The digest's functions and numbers are unchanged; Home's additions live beside them in
  services/overview_stats.py (accounts connected, latest question, engagement) and
  services/priority_queue.py, and the digest doesn't read them (C-053).

## C-066 · Settings redesign (owner-approved layout, feat/settings-redesign)
The layout follows the owner's five settings mockups; colours stay ours (tokens and theme).
Behaviour, routes, permissions and API calls are unchanged except where listed under API.
- Shell: the tab bar stays in the settings layout with an underlined active tab and
  `aria-current`, and the same role visibility (Billing for owners and admins). AI is labelled
  "AI Rules & Takeover". Every tab starts with `SettingsPageHeader`: a breadcrumb read from the
  address (Settings › Billing), so it always names the tab the page is on, a small label, the
  title, one line of description and the page's actions. There is no top bar and no global Save.
- Cards: `SettingsCard`, a rounded panel named by its heading (a region), with an icon, section
  labels, and a red-accented danger tone. Two columns from 1280 px where the mockup has them
  (AI, Connections, Workspace, Notifications), one column below; controls are 40 px tall there.
- Save bar: sticky at the bottom of a form page (AI's takeover and phrases, Workspace). Clean:
  "All changes saved". Dirty: "Unsaved changes" with Reset and Save. Saving: a spinner, both
  buttons disabled. A failed save's error shows in the bar (field errors stay on their fields)
  instead of a toast. While dirty, leaving warns: `beforeunload` for reload, close and typed
  addresses, and a confirm for any same-origin link, caught on the window in the capture phase
  before Next's Link sees the click. Browser Back and Forward and code-driven `router.push` are
  not caught: the App Router has no way to block them.
- Things that already saved as they changed still do: account AI modes (AI page and Connections),
  the per-account switches, and the notification switches. Notifications' bar is status only
  (saving, saved, or "Last change not saved" with the reason); its failure is no longer a toast.
- Connections: a search (name, handle, number, platform) and All · Connected · Disconnected ·
  Sandboxes with counts over the accounts the search matches. Connected means not disconnected
  (needs reconnect and error count); Sandboxes overlaps the other two. Cards: avatar with the
  platform badge, name, handle, status pill; the AI settings in an inner panel; a footer with
  "Instagram API" or "WhatsApp Cloud API", "Last synced …" when the API has a time, and
  Reconnect, Retry or Disconnect. Two columns from 1280 px. The status copy stays "Needs
  reconnecting" (lib/copy is shared).
- Remove is not built: the mockup's Remove (for sandboxes and disconnected cards) needs a route
  that deletes an account row and, by cascade, its conversations, messages, comments, posts and
  automations. Adding that was not permitted in this session, so disconnected cards keep only
  Reconnect and sandboxes keep Disconnect. It is left for the owner to decide.
- AI Rules & Takeover: left, every connected account with Off, Suggest and Auto (a disconnected
  account has no mode to set: the PATCH is 409) and Human takeover (30 min, 2 h, 24 h, Until
  resumed, as today); right, the six built-in rules as a checklist and the escalation phrases as
  removable chips with an add field and "n of 20 used" (AiSettingsUpdate: 20 phrases of up to 120
  characters). On Free, Auto is disabled with the Pro badge and "Upgrade for Auto" opens the same
  upgrade dialog; a 402 still opens it. The phrases use a new `PhraseChips`; `ChipListInput` is
  unchanged (brand voice uses it). `AiModeControl` is unchanged.
- Billing & Usage: a plan hero (name, status, the trial end or renewal with the price, the
  owner's actions as before). Badges: Trial, Active, On hold (was "Payment failed"), Cancelling
  (was "Cancelled"), Free. "Resource quotas & usage" is a grid of every meter GET …/billing
  counts, now including Instagram and WhatsApp accounts, each with its percentage and, for AI
  credits and scheduled posts, the reset date. The plan comparison is the public plan list with
  the current plan highlighted and Max "Coming soon". Payment history is a table (date, amount
  and currency, status with Dodo's failure reason, Dodo's invoice link), newest first, older
  pages on demand, with an empty state.
- Agent: a header card with this period's AI credits (GET …/billing). "Capabilities &
  permissions": the read-only bounds text, "Mode: Read only", and each AgentPermissions switch
  as Off, locked, "Coming later". Run history: search and chips, both answered by the API; All,
  Answered (succeeded, partial), Action needed (awaiting_approval; none until R2) and Failed
  (failed, expired); cancelled and unfinished runs show under All. Pages of 10 with Previous and
  Next; no total (the API has no count). A row still opens the run's trace.
- Workspace: "General information" with the name's counter at 80 (the API's maximum), the URL
  with its "…/w/" prefix and the existing warning, timezone, reply language, and the disclosure
  switch with its line (counter at 60) and a preview (the message, a blank line, the line, as
  render.with_disclosure appends it). The danger zone is `DeleteWorkspace` in the danger card;
  its behaviour is unchanged. Beside them, "At a glance": plan, connected channels by platform,
  members and the created date, all read from the API.
- API: `GET /v1/w/{wid}/billing/payments` (owners and admins, like reading billing; the billing
  actions stay the owner's): the workspace's `payments` rows (id, occurred_at, amount_minor,
  currency, status, invoice_url, failure_reason), newest first by occurred_at, cursor pages of up
  to 50 (20 by default). `SocialAccountOut.last_synced_at`: the later of `media_synced_at` and
  `backfilled_at`, null when neither ran (WhatsApp). `WorkspaceOut.member_count`. `GET
  …/agent/runs` takes `status` (repeatable) and `q` (the request contains it, any case, LIKE
  wildcards taken literally). No migration; §2.15 lists the new route and filters.
- Dropped from the mockups: the top bar (Docs & API, Support, Save Changes), the Dashboard item
  and the ops meter (the sidebar is unchanged), sync uptime, environment instance and node ids,
  the upcoming connectors card, the encryption claims card, model latency and ops tier, the
  Visual Rules Matrix, "synced to cloud edge", annual billing and "save 20%", quota rollover,
  the SOC-2 and audit cards, "Download all CSV", "Auto-renew enabled" and "Encrypted Stripe
  billing", the policy version and 2FA link, screenshots, a retention label (not a setting),
  version badges, Audit Log, Save All, disclosure reach, sync health and custom slug routing.

## C-067 · Deleting a connected account's data (owner-approved, feature/account-data-deletion)
The owner approved permanently deleting one account's data, with safeguards. It fills three
gaps: Disconnect's `delete_data` deleted nothing (Q-014's TODO), Meta's data-deletion callback
removed only the token and Meta's raw events, and backup exports had no retention.
- One purge, `purge_account_data(workspace_id, account_id)` (services/account_deletion.py; bulk
  lane, key and lock `acctpurge:{id}`, RECOVERY RETRY), idempotent and resumable in committed
  batches like purge_workspace. Its tables come from the schema: every table reachable from
  social_accounts through ON DELETE CASCADE keys, which is what deleting the row would take
  (repositories/account_deletion.account_tables). Today: conversations, messages,
  message_analyses, reply_suggestions, ai_decisions, scheduled_messages, contacts, comments,
  comment_analyses, media_items, post_metric_snapshots, account_daily_metrics, automations,
  automation_keywords, automation_posts, automation_runs (the private-reply queue),
  scheduled_post_targets and posting_slots. tests/unit/test_account_purge_tables.py fails for an
  `*account_id` column without a key to social_accounts, or a key into these tables that would
  block the delete. Then the webhook payloads routed to the workspace for its platform id, its
  Valkey keys (`*{account_id}*`: rate buckets, profile and template caches) and the account row.
- Files: those its messages own (purpose `message` or `inbound`, named in its messages' or
  scheduled messages' attachments) are deleted from Cloudinary by public id (media purger
  `delete_files`), before the messages, so they can be found. A file anything else names (another
  account's message or scheduled message, a library post, a knowledge file, another account's
  automation; every foreign key to media_assets is checked) is kept, and library and knowledge
  files never count as a message's.
- Scheduled posts: when deletion starts, the account's pending targets are canceled and each
  post's status follows F-13 (a post whose only account it was becomes canceled). After the
  purge, a post left with no account that had published only there is deleted with that
  account's posts; one still scheduled or publishing is canceled; drafts stay.
- Realtime: `social_account.updated` when deletion starts (`deleting: true`), and when it ends the
  workspace's event stream is cleared (its entries can carry the account's messages) and a
  `resync` published, so every open page refetches. No new event type.
- Audit: structlog `account_data_purged` (and `account_purge_continues` for a run that hands
  over) with workspace, account, platform, requester (null for Meta) and rows per table; never
  content or confirmation codes.
- Kept: knowledge, AI settings, workspace settings, members, billing, usage counters, agent runs,
  notifications and other accounts. Plan slots count live accounts (billing/entitlements.py), so
  a deleting account stops counting at once; its active automations pause.
- API: `DELETE …/social-accounts/{id}` keeps its path and 204 and gains `confirm`. Without
  `delete_data` or `confirm` it disconnects as before. `delete_data=true&confirm=` disconnects,
  then purges. `confirm=` alone is Remove, for a disconnected or sandbox account; 409 for a live
  one ("Disconnect this account first, or use Disconnect and delete data."). One route because
  the spec gives Remove the disconnect route's path. Owners and admins (as before). `confirm` is
  the handle with or without "@" in any case, else the number with any spacing, else the name;
  422 on `confirm` otherwise. Asking again while it deletes is a 204 that re-queues the purge.
  Covered by the per-user rate limit like every signed-in route.
- `SocialAccountOut.deleting`. Migration 0017: social_accounts.deletion_requested_at and
  deletion_requested_by_user_id (SET NULL), and data_deletion_requests.status takes `failed`. An
  account being deleted can't be reconnected in that workspace until it's gone (409), since its
  row would come back and be purged; resubscribe refuses it too.
- Meta's callback (FR-PRV-01, F-16): `delete_platform_user_data` finds every account with the
  signed request's user id (app-scoped or platform id) in every workspace (tenant bypass, as
  before), disconnects each (owners told, as for deauthorize), marks it deleting, queues its
  purge and deletes Meta's raw events for it. Status: received, then processing, then completed
  when the last purge finishes (each purge settles the requests naming its account); failed while
  a purge or the job is retried, back to processing on the retry. A request with no account left
  completes at once. The job now retries with backoff; sweep_deletions re-queues requests still
  received or failed and settles finished ones, and re-queues accounts still deleting, alerting
  after 6 hours.
- Web: Settings → Connections cards get Disconnect and delete data (connected) and Remove
  (disconnected, or a sandbox), one dialog listing what is deleted and kept with the handle or
  number typed to confirm; "Deleting…" with no actions while it runs. Disconnect's checkbox is
  gone: plain Disconnect keeps the data and says so. /data-deletion shows the failed status.
- Backups: exports are kept 30 days, then deleted. No script in the repo makes or keeps exports,
  so docs/ops/backup.md makes it a required setting (one bucket, a 30-day lifecycle rule, a
  monthly check). The privacy policy states it, and that deletion covers the account's data.

## C-068 · Expressive motion and effects on the marketing site (owner decision, feature/landing-redesign)
The owner allowed the public marketing site expressive motion and decorative effects, for the
landing page's redesign with Aceternity UI's free components. DESIGN_SYSTEM §7.3 ("no motion for
decoration") and AGENT_CONTEXT's rejected patterns (gradients without a job, blur for
decoration) still hold in the app. The scope is the marketing pages only:
`apps/web/src/app/(marketing)` and `apps/web/src/components/marketing`.
- Allowed there: entrances on scroll (once), hover lifts on cards and calls to action, one
  background effect per view (the hero's Spotlight), decorative glows and gradients built from the
  brand tokens (Spotlight, Lamp, Pro's moving border, the illustrations' backdrops),
  scroll-linked movement (the product screenshot's tilt, the timeline's rail) and small loops (the
  headline's flip words, the automation beam's pulse, the moving border).
- Still required:
  - Tokens only: every colour from `globals.css` (canvas, panel, raised, line, brand, brand-fg,
    brand-deep, brand-soft, brand-line, the status and platform colours). The Aceternity components
    were adapted from their neutral, slate and cyan values.
  - Contrast: text stays on canvas or panel at AA; effects sit behind headings or beside text,
    never under body copy.
  - Reduced motion: `MotionConfig reducedMotion="user"` wraps the landing page. Every loop stops
    (flip words, beam pulse, moving border, spotlight drift, caret), scroll-linked transforms are
    overridden flat, entrances are instant and scroll reveals never hide anything. CSS animations
    are `motion-safe:` only.
  - Accessibility: decorative layers are `aria-hidden` with no pointer events; the flip-word
    headline gives screen readers its whole sentence; one h1, headings in order, a skip link,
    focus visible (inset where a container clips), 40 px touch targets.
  - Performance: the hero's text is server-rendered and still (it is the largest paint); motion's
    animation code loads after hydration (LazyMotion with domAnimation, `m` components); the
    feature illustrations load when near the screen; loops run only while on screen; only
    transforms and opacity animate (the header uses CSS transitions; no layout animations); lazy
    boxes have fixed sizes (no layout shift). No canvas, WebGL, external scripts, fonts or images:
    the CSP is unchanged.
  - Motion values: the UI audit's tokens for hover and press (120, 150 and 200 ms; enter, exit and
    standard easings), plus two marketing-only ones, `reveal` 600 ms and `expressive` 450 ms with
    an expressive ease (`components/marketing/effects/motion.ts`).
  - Honesty: illustrations and screenshots are labelled as example data. The screenshots are the
    real app on the e2e stack with sandbox data and made-up names
    (`apps/web/scripts/marketing-shots`); no testimonials, ratings, counts or logos.
- Components and dependency: installed with the shadcn CLI from Aceternity's registry
  (`@aceternity` in `components.json`), then moved from `components/ui` to
  `components/marketing/effects` and adapted (Tabler icons swapped for lucide). The one new
  dependency is `framer-motion`, the library `motion` wraps: `motion/react` re-exports it through
  a namespace import that Turbopack can't tree-shake, which bundled drag and layout projection
  (about 20 KB more, gzipped).
- The marketing header's blur stays DESIGN_SYSTEM §6's documented exception; the header now floats
  as a rounded bar after 64 px of scroll.

## C-069 · UI audit owner decisions D-01 to D-17 (owner decision, feature/ui-audit)
The owner approved the architect's recommendation for all 17 decisions in
`docs/ui-audit/UI_AUDIT.md` §D on 2026-10-01. Each one is applied by the task the implementation
plan names; until that task merges, the current look stays.
- **D-01:** `line-control` (white 40%) on checkbox, radio and switch edges **and** on text inputs,
  selects and textareas (`--input` → `line-control`). Amends UX-A11Y-01's scope note.
- **D-02:** `rounded-xl` for every app card (amends C-066's `rounded-2xl`); inset panels
  `rounded-lg`; `2xl` stays for message bubbles and marketing.
- **D-03:** a dark tooltip: the `overlay` surface, `fg` text, a `line` edge and the floating shadow.
- **D-04:** native date and time inputs for R1, styled like Input. A deviation from UX-CMP-01's
  Calendar; Calendar comes when a range picker or R2 needs it (no UI-029).
- **D-05:** page H1 24 px everywhere (amends C-066's 30 px settings title); pane H1 18 px for
  Inbox, Ask and the phone top bar; the spec's pane title becomes `text-lg`.
- **D-06:** placeholders `fg-secondary`; `fg-disabled` for disabled controls only. Amends spec
  §4.2.
- **D-07:** `ai_auto` → "Sent by AI" with the info button; `automation` → "Automation · {name}"
  with a zap icon ("AI" only when the step was an AI reply); list prefix "Automation:"; the row
  badge "Auto replies", neutral, at most two badges per row. Amends C-063, follows UX-INB-06.
- **D-08:** no settings breadcrumb or eyebrow; tab labels match the page titles ("Ask Social
  Hood", "Billing and usage", "AI rules and takeover"); the save bar shows only when dirty, saving
  or failed, with an inline "Saved" status on autosave pages; the Agent tab's six tiles become one
  sentence. Amends C-066.
- **D-09:** Disconnect stays visible as a neutral ghost button; one "Delete account and data" item
  for both modes in a ⋯ menu, opening the same typed-confirm dialog. Amends C-067's labels and
  placement; the API is unchanged.
- **D-10:** at most one gradient primary per view region (page header, dialog footer, composer);
  row and card actions are secondary.
- **D-11:** per post now: `needs_reply_count` on PostSummary and a `needs_reply` filter on a
  post's comments, with the API, the generated client and the UI in one task (UI-055). A cross-post
  list later if usage shows the need.
- **D-12:** an `overlay` surface (`#262626`) and two dark elevation shadows (floating, overlay)
  replacing `shadow-md`/`xl` and the 10% ring on floating and modal surfaces.
- **D-13:** up to four identity gradient pairs built only from existing brand, shell and
  platform-blue values, every stop 4.5:1 or more with white, no status colour; shared by avatar
  fallbacks and schedule account rings.
- **D-14:** a per-device "Single-key shortcuts" switch, on by default, in a Keyboard shortcuts
  dialog opened from the inbox list header and with "?".
- **D-15:** the active platform segment neutral (`raised` with `brand-fg`); the heart moves into
  the emoji popover ("Send a heart"); scheduling only from the composer, named "Schedule message";
  Archived as a plain chip. Amends C-063.
- **D-16:** PageFrame's "‹ Parent" back link on the automation editor, post composer and post
  detail (amends UX-SCR-03; e2e F-11 and F-13 change in UI-065); below 1280 px the editor's side
  panel comes after the steps; icon-only buttons `rounded-lg` (amends spec §4.2's `rounded-full`,
  which stays for circles); composer shells `rounded-xl` (amends UX-INB-07's pill).
- **D-17:** the system fallback for Devanagari in R1; `latin-ext` is added regardless (UI-010).

## C-070 · `globals.css` token foundation (open: confirm, feature/ui-tokens)
UX-TOK-01 says the tokens file is used "exactly as below"; C-002 added two lines. UI-001 adds the
**Add** items of `docs/ui-audit/DESIGN_SYSTEM.md` (§1.13, §1.9, §2, §7), each marked "C-070" in
`apps/web/src/styles/globals.css` and mirrored in `styles/tokens.ts`, which `/dev/tokens` renders
and `tokens.test.ts` checks against the CSS. They name values the app already draws. No owner
decision is applied here: `line-control` (D-01), the placeholder colour (D-06) and the overlay
surface and shadows (D-12) come with UI-018.
- **Colours:** `hover` (white 5%), `pressed` (white 10%), `scrim` (black 60%), `media-scrim`
  (black, on media only, with an opacity), `on-brand` (white), `brand-strong` (`#4467E6`, the
  brand gradient's existing end stop), `success-soft`, `warning-soft`, `danger-soft` (15% of the
  base colour). They replace `bg-white/5`, `bg-white/10`, `bg-black/60`, `text-white` and the
  `/10`–`/30` status fills as the area sweeps reach them.
- **Type:** `text-2xs` (11/16) and `text-md` (15/24), for `text-[11px]` and `text-[15px]`. The type
  roles are importable constants in `styles/tokens.ts` (`EYEBROW`, `CHIP`, `CARD_TITLE` …), with
  one eyebrow tracking (0.08em).
- **Motion:** `--motion-fast` 120 ms, `--motion-normal` 150 ms and `--motion-slow` 200 ms, with
  `duration-fast|normal|slow` (they set `--tw-duration`, which tw-animate-css reads), and the
  easings `ease-standard`, `ease-enter`, `ease-exit`. The primitives adopt them in their own tasks.
- **Breakpoint:** `wide` (1440 px), for today's `min-[1440px]:`.
- **Gradients:** the three gradient utilities take their stops from tokens (the same pixels; the
  brand gradient ends at `brand-strong`). `bg-glow-brand` is the plan hero's radial glow
  (`brand-soft` from the top-left corner), one per view at most; the marketing hero keeps its own
  centred glow unless UI-042 moves it onto the utility. `mask-fade-x` fades the trailing 1rem of a
  row that scrolls sideways (the sidebar's bottom fade, turned sideways); the row gets `pe-4` so its
  last item can scroll clear of the fade.
- **shadcn aliases:** `--primary` → `brand-strong` (was `brand`), `--primary-foreground` →
  `on-brand` (was a literal `#FFFFFF`), `--accent` → `hover` (was `raised`: the same pixel on
  `panel`, where every menu and select sits). `card-`, `popover-`, `secondary-` and
  `accent-foreground` get their `--color-*` mappings, so their utilities generate CSS; every
  `:root` alias is now mapped. `--radius` stays, commented as inert.
- **Base layer:** `strong, b { font-weight: 600 }` (weights stop at 600); a reduced-motion safety
  net that removes animations and transitions from `[data-slot$="-overlay"]`,
  `[data-slot$="-content"]` and `[data-slot="skeleton"]` (spec §4.2 "Motion": instant under
  reduced motion); `scroll-padding-top: 4rem` below `md`, so a control scrolled into view isn't
  hidden under the phone's sticky top bar (WCAG 2.4.11).
- **What changes on screen:**
  - The switch's checked track and the checkbox's checked fill go from `#567FF8` to `#4467E6`
    (3.4:1 on `panel`, above the 3:1 for state indicators). Every Button `default` call site paints
    its own gradient and both `link` call sites set `brand-fg`, so neither changes.
  - Bare `<strong>` on the legal pages is 600 instead of 700.
  - The now-working foreground utilities: in a highlighted menu or select item, icons and secondary
    text turn `fg` (the primitives' `focus:**:text-accent-foreground` rule applies; UI-013 redraws
    the highlight), and a `secondary` Button no longer inherits a coloured parent's text colour.
  - Under reduced motion, dialogs, alert dialogs, sheets (the phone drawer), popovers, menus,
    selects, tooltips and skeletons no longer animate.
- The spec's §4.2 text (UX-TOK-01's list, the type table, the motion line) follows in UI-071.

## C-071 · Token decisions D-01, D-06 and D-12 applied (UI-018, feature/ui-token-decisions)
UI-018 applies three of the decisions the owner approved in C-069. The values are marked "C-071"
in `apps/web/src/styles/globals.css`, mirrored in `styles/tokens.ts`, checked by `tokens.test.ts`
and shown on `/dev/tokens`. Ratios were measured in Chromium on the e2e stack at 375 and 1280 px
(before: the old values restored in the page).
- **D-01, control edges:** `line-control` (white 40%), with `--input` → `line-control`. Input,
  Textarea, SelectTrigger, SearchInput, ChipInput, the checkbox and the switch's off edge follow it.
  - A field draws its edge over its own fill, so the edge is `#777777` wherever the field sits:
    3.70:1 on panel, 3.79:1 against the field inside, 3.40:1 on overlay and 3.22:1 on raised. Before,
    it was 1.32:1 on panel.
  - An unchecked checkbox is 3.77:1 on panel and 3.66:1 on canvas (before: 1.35:1 and 1.20:1).
    Across the surfaces it ranges from 3.41:1 to 3.79:1. The switch's off edge is 4.53:1 (before:
    1.85:1).
  - **Checked checkbox: a `brand` fill (the DSA's choice).** It matches the switch's on track and
    replaces `--primary` (`brand-strong`). A checked box's edge is its fill:
    - `brand-strong` was 2.96:1 on a selected (`raised`) row and 2.60:1 on `raised-hover`;
    - `brand` is 3.96:1 and 3.48:1 there, and 4.54:1 on panel, 4.17:1 on overlay and 5.79:1 on
      canvas;
    - the tick and the indeterminate minus are graphics, `on-brand` at 3.63:1 on `brand`, where 3:1
      is needed.

    The alternative was a `line-control` edge kept on checked boxes. It measures about 3.58:1 on
    raised, but leaves the fill at 2.96:1 and puts a grey ring round a blue box. This amends C-070's
    note that the checkbox fill became `#4467E6`, and DESIGN_SYSTEM §1.4.
  - Settings › Workspace's URL field is a hand-built wrapper. Its edge moves from `border-line` to
    `border-line-control`, so every field on that page passes. The other raw fields (about 27) keep
    their own edges until the area sweeps move them onto Input.
- **D-06, placeholders:** the base `::placeholder` is `fg-secondary` (it was `fg-disabled`).
  - The primitives already used `fg-secondary`, so only raw fields change. The inbox composer and
    list search go from 3.49:1 to 6.15:1 on field, and from 2.97:1 to 5.23:1 when focused (on raised).
  - `fg-secondary` is 6.01:1 on panel, 6.15:1 on field, 5.52:1 on overlay and 5.23:1 on raised.
  - `fg-disabled` is for disabled controls only.
- **D-12, overlay surface and elevation:**
  - **Values:**
    - `overlay` is `#262626`: 1.09:1 against panel and 1.39:1 against canvas. `--popover` →
      `overlay`.
    - `shadow-floating`: `0 8px 24px -6px rgb(0 0 0 / 0.7)`.
    - `shadow-overlay`: `0 24px 64px -12px rgb(0 0 0 / 0.8)`.
  - **Where they apply:** the floating recipe (`ui/floating`, used by Popover, DropdownMenu and
    Select) and the toast use `shadow-floating`. Dialog, AlertDialog and Sheet use
    `shadow-overlay`. Together they replace `shadow-xl` and `ring-foreground/10`.
  - **A deviation from DESIGN_SYSTEM §1.13:** the 1 px `line` edge sits outside the shadow tokens.
    - Floating content and dialogs draw it as `ring-1 ring-line`, the same pixels as
      `ring-foreground/10`. A sheet keeps its side border, and the toast its `line-strong` border.
    - The reason: 21 menus and popovers still pass `shadow-xl` at the call site. With the edge
      inside the token, `cn` would replace edge and shadow together, and those menus would lose
      their outline on panel.
  - **Supporting changes:**
    - `cn` learns `shadow-floating` and `shadow-overlay` as shadow sizes. tailwind-merge read them
      as colours, because `--color-overlay` exists.
    - The phone drawer is `panel`, like the sidebar it holds (it was `canvas`). It keeps the sheet's
      overlay shadow.
  - **Text on overlay:**
    - `fg` 15.1:1, `fg-secondary` 5.52:1, `brand-fg` 7.56:1, `danger-fg` 7.97:1;
    - a highlighted menu item (`hover` over overlay, `#313131`): `fg-secondary` 4.75:1, the
      keyboard outline 3.59:1.
  - **What changes on screen now:**
    - the 14 selects' options, the toast and the one dialog without a call-site surface (the
      composer's "Unschedule this post?") move to `overlay`;
    - every dialog, alert dialog and sheet gets the overlay shadow.
  - **What waits for the area sweeps:** 54 overlay call sites still pass `border-line bg-panel`, and
    21 of them also pass `shadow-xl`. They stay on `panel` until the Wave-3 sweeps remove those
    patches (AGENT_CONTEXT §6). After that they float on `overlay` with no further token change.

## C-072 · Identity palette D-13 applied (UI-027, feature/ui-identity-palette)
UI-027 applies D-13 (C-069) in one module, `apps/web/src/lib/ui/identity.ts`, with no new token.
It replaces UX-INB-04's "six pairs" and UX-SCR-04's ring colours, which borrowed warning,
success, danger-fill, instagram and whatsapp. Ratios (WCAG, measured in Chromium on the e2e stack
at 375 and 1280 px, and checked against the token values by `identity.test.ts`):
- **Three identities, each a gradient pair for the avatar fallback and a ring and dot colour for
  accounts:** `brand-deep → brand-strong` with `brand`; `shell-1 → shell-2` with `brand-fg`;
  `linkedin → facebook` with `facebook`.
  - White on every stop: 11.04 and 4.85; 6.52 and 12.66; 8.72 and 5.17. On the oklab midpoints
    (Tailwind's `bg-linear-135` interpolates in oklab): 7.37, 9.19 and 6.72. Before, three of six
    pairs failed (2.26–3.84:1).
  - Rings on panel, their offset colour: 4.54, 8.23, 3.19 (on canvas 5.79, 10.49, 4.06). Rings
    against each other: 1.42:1 or more (oklab ΔE 8.9 or more). Before, the instagram ring was
    2.73:1 and brand next to brand-fg was the same hue.
- **Three, not four (the DSA's choice within "up to four"):** the only values in these families
  at 3:1 or more on panel are `brand-fg`, `brand`, `brand-strong` and `facebook`, and
  `brand-strong` and `facebook` are 1.07:1 apart (ΔE 3.0), so a fourth account ring would look like
  the third.
- **The schedule's AccountAvatar** fills its fallback with its account's identity gradient, so the
  ring and the avatar agree (it was `raised`). An unknown account keeps the `line-strong` ring.
- **The initial is `aria-hidden`** on every avatar fallback: the name is beside it, or on the
  button or group that holds it, so a conversation row's name no longer starts with the initial
  ("linen.lover 4m …").
- **Scope notes:** `shell-1` and `shell-2` keep the shell gradient to the logo and Upgrade; their
  values also form one identity pair. The pair `brand-deep → brand-strong` is the brand gradient's
  pair, so one in three contact avatars matches the primary button's colours.
- **Also:** the Avatar primitive's default fallback fill is `raised` (was shadcn's `muted`, the
  field colour, 1.02:1 on panel), like Skeleton.

## C-073 · Primitive follow-ups: the soft Button, a 40 px segment, date and time focus, `short:` and the crop mask (DSA, feature/ui-primitives-followups)
Five follow-ups from the Wave-3 sweeps (UI-030, UI-032), decided by the Design System Architect
and recorded in `docs/ui-audit/DESIGN_SYSTEM.md`. The values are marked "C-073" in
`apps/web/src/styles/globals.css`, mirrored in `styles/tokens.ts`, checked by `tokens.test.ts` and
shown on `/dev/tokens`. Measured in Chromium on the e2e stack at 375 and 1280 px (and 320, 360,
640, 768 and 1024 where widths matter).
- **Button `variant="soft"` (a change on screen).** The AI trigger, AI Polish and the inbox details
  toggle each pasted brand-soft classes onto a ghost Button; DESIGN_SYSTEM §8.1 adds a variant for
  a repeated need instead. `soft` is the AI pill's look (§1.4) and the selected chip's colours
  (§8.3): `bg-brand-soft text-brand-fg border-brand-line`, `brand-soft-hover` on hover and while
  its menu is open (`aria-expanded`), the global focus outline, and the primitive's disabled rule
  (`opacity-50`). It is for AI actions and for a toggle Button while it is pressed.
  - **Token (an addition):** `brand-soft-hover`, brand at 25%, the value the AI trigger's hover
    already used (`bg-brand/25`, since P5). It sits between `brand-soft` (15%) and `brand-line`
    (35%), as `raised-hover` sits above `raised`.
  - **Contrast:** `brand-fg` text 6.80:1 at rest and 5.86:1 on hover or open over panel (the
    header); 5.94:1 and 5.17:1 over the focused composer (`raised`).
  - **AI trigger:** no visible change (same pixels; the hover value is now a token).
  - **AI Polish:** it was a transparent button with a `brand-line` edge, and its own grey disabled
    look (`border-line`, `fg-disabled`). Now it has the brand-soft fill at rest, and while the
    reply is empty it is the dimmed soft button (opacity 50%), like every disabled control.
  - **Details toggle:** pressed, it also gets the `brand-line` edge, and hovering it keeps the
    brand look (it turned white 5% with white text).
- **ToggleGroup and Tabs `size="xl"` (an addition, adopted by UI-036).** C-066's 40 px settings
  controls, named on the one ladder (Input, Button and Select call 40 px `xl`; their `lg` is 36),
  not `lg` as first suggested.
  - **Segment:** 40 px tall with 14 px control text (`min-h-10 py-2.5 text-sm`). The track's
    4 px inset makes the control 48 px outside, which is what Settings › AI's takeover choice
    renders today.
  - **Side padding 8 px, not 10:** segments stretch, so this is only a minimum. Settings › AI's
    "Off | Suggest | Auto Pro" needs a 214 px inner track at 14 px with 10 px padding. Its
    narrowest track is 220 px (212 inside) on a 320 px screen, where "Auto Pro" ran 2.1 px past
    the inset (the "didn't fit at `text-sm`" from UI-030). At 8 px it fits there with 9.9 px to
    spare; at 360 px and up there is room either way.
  - **Once UI-036 adopts it:** the per-account modes go from 36 px segments at 12 px to 40 px at
    14 px (a 44 → 48 px track); the takeover choice looks the same.
  - **Lining up:** a segmented control in a row beside 40 px fields (the Connections and Agent
    filters next to their searches) uses `default`, whose track is 40 px outside, so the edges
    line up.
- **Native date and time fields show focus at every Tab stop (a change on screen; DESIGN_SYSTEM
  §8.3, WCAG 2.4.7).**
  - **The problem:** while the calendar or clock button inside the field has focus, Chromium
    leaves the field matching neither `:focus` nor `:focus-visible`, only `:focus-within`. So that
    stop had no outline and a resting field (`line-control` edge, `field` fill).
  - **The fix:** Input draws the same look from `:focus-within` for `date`, `time`,
    `datetime-local`, `month` and `week`: the 2 px `ring` outline offset 2 px, the `ring` border
    and the `raised` fill. The browser still rings the button itself.
  - **The composer's date and time:** 7 stops (3 date segments and the calendar button, 2 time
    segments and the clock button). Before, 2 showed no focus; after, none. The outline is 4.54:1
    on panel. Every native date and time field is on Input already (ScheduleFields,
    MediaLibraryDialog, RangeControl, SettingsStep, PostingTimesDrawer).
- **`short:` variant (an addition, no visible change):** `@custom-variant short (@media
  (max-height: 500px))`. It replaces `[@media(max-height:500px)]:` in `shell/sticky-bar.ts`
  (`STATIC_WHEN_SHORT`, so the settings save bar, the composer's bar and the phone top bar) and
  PostComposer's one-line reasons. At 640 × 450 the composer's bar (85 px, 18.9% of the height)
  and the top bar are static, nothing is reserved, and the reasons are one truncated line. At
  640 × 800 both stick again (85 px reserved).
- **`shadow-crop-mask` utility (an addition, the same pixels):** CropDialog's arbitrary
  `shadow-[0_0_0_9999px_…]` becomes a named `@utility` (DESIGN_SYSTEM §6: box-shadow for another
  job than elevation, named in `globals.css`). Its colour is `media-scrim` at 60% (it dims a photo,
  so it stays dark in any theme), not `canvas`, the same black today: computed
  `color(srgb 0 0 0 / 0.6) 0 0 0 9999px`. It is a utility, not a `--shadow-*` token, so elevation
  keeps its two shadows. `cn` treats it as a shadow size, like `shadow-floating`.

## C-074 · Pages fill the width (owner decision, 2026-10-14, UI-076)
On a wide screen (about 2,130 CSS px) Home and every PageFrame page sat in a centred 1200 px column
with about 465 px of empty canvas each side, next to a full-width Inbox and Ask. The owner decided:
"fill the width and responsive to any size". This amends the spec's page width (UX-SCR), and UI-071
updates DESIGN_SYSTEM and the spec.
- **No page cap:** `max-w-[1200px]` is gone from PageFrame, HomeScreen, the settings layout and
  SettingsFrame, AutomationEditor, PostDetailPage, PostComposer and PageSkeleton. Pages fill the
  space beside the sidebar with the same `p-4 md:p-6` gutters.
- **Readability limits stay inside components:** fields in settings cards are at most `max-w-2xl`;
  message bubbles keep their own maximum width. The marketing site keeps its centred layout.
- **Grids gain columns as space grows:** the comments posts grid now goes up to 5 columns at `xl`
  and 6 at `2xl`.
- **One frame:** the inbox panel is inset on all four sides (`md:m-4 md:rounded-xl md:border`), as
  the Ask page already was. It used to run into the window's right edge.
- **In the same task:**
  - Home's empty priority queue no longer says "Nothing is waiting" while conversations need a
    reply. The queue leaves out closed reply windows, so it now says so.
  - The sidebar's Ask card puts the name on its own line, so it is no longer cut to
    "Ask Social Ho…", and its subtitle is "Your AI assistant".
  - The inbox and Automations search placeholders are short ("Search", "Name or keyword"); their
    accessible names are unchanged.

## C-075 · Palette lock, design lint, chart aliases and guarded token mirrors (UI-070, feature/ui-palette-lock)
The Wave-5 lock (UI-ISS-028, UI-ISS-095, UI-ISS-097; COLOR_SYSTEM §11.6–§11.7). Nothing changes on
screen: every colour below resolves to the value it had.
- **Palette lock (no visible change):** `--color-*: initial;` opens `@theme` in `globals.css`, so
  Tailwind's default palette (`red-500`, `white`, `black` …) no longer compiles; only the tokens
  do. White and black exist only as tokens (`fg`, `on-brand`, `canvas`, `media-scrim`). The sweeps
  had already moved app code off the default palette; `tokens.test.ts` checks that the lock comes
  first.
- **Design lint (`styles/design-lint.test.ts`):** a Vitest scan of the app's source, beside the
  copy lint, that fails on a default Tailwind colour, an arbitrary text size or colour
  (`text-[`), an arbitrary radius (`rounded-[`, except `rounded-[inherit]`), the translucent
  shadcn ring (`ring-ring/50`), `bg-brand-gradient` restated on a Button, and a bare
  `outline-none` without a `focus-visible:` replacement. A bare `outline-none` stays allowed on a
  programmatic focus target (`tabIndex={-1}`: the skip link's `<main>`, a heading focused after
  navigation) and in the dialog, alert dialog and popover primitives, whose content Radix focuses
  on open. Tests, test helpers and comment lines are skipped.
- **Chart aliases (an addition, the same pixels):** `chart-positive`, `chart-neutral`,
  `chart-negative` and `chart-series-1`, aliases of `success`, `fg-secondary`, `danger` and
  `brand`. SentimentBar, SentimentCard, StatsPane (runs and failures) and TrendLine read them, so a
  chart's colours are set in one place. Categorical series (accounts, people) use the identity
  palette (C-072). Listed in `tokens.ts` (`chartAliases`), checked by `tokens.test.ts` and shown
  on `/dev/tokens`.
- **Token mirrors read `tokens.ts` (UI-ISS-095):** `colorValue()` in `styles/tokens.ts` is the one
  lookup for consumers that can't read CSS variables: Clerk (it computes shades), the OG image
  (Satori, which also gets the glow as `rgba()` from `brand-line`), the manifest and the
  viewport's theme colour. `tokens.test.ts` fails if any of them writes a hex or `rgb()` literal
  again. The logo mark already drew in `currentColor` and token classes.
- **One alias outside the primitives:** Settings › Workspace's URL field drew its focus edge and
  outline with `border-ring` and `outline-ring`; they are `border-brand` and `outline-brand`, the
  same colour, so app code uses tokens only (DESIGN_SYSTEM §1.10).

## C-076 · The spec brought in step with the audit's decisions (UI-071, feature/ui-spec-sync)
UI-071's final pass: `docs/BUILD_SPEC.html`, `DESIGN_SYSTEM.md` and `AGENT_CONTEXT.md` now say what
the code does after C-069 to C-075. No code changes.
- **§4.2 (UX-TOK-01, UX-TOK-02):**
  - The CSS block is `globals.css` as it stands, with the palette lock first.
  - The palette table is generated from `tokens.ts`: 39 tokens, the 4 chart aliases and the 4
    gradients.
  - UX-TOK-02 adds the audit's contrast fixes: `brand-strong` behind text (3.6 → 4.9:1), the
    `line-control` edge (D-01) and `fg-secondary` placeholders (D-06).
  - The type table follows `typeRoles`: the 11 px chip and eyebrow rows, the 15 px reading row, and
    the pane title at 18 px (D-05). It replaces `text-xl` and `text-[11px]`.
  - The rules are rewritten from DESIGN_SYSTEM: spacing, width (C-074), radius (D-02 cards, D-16
    icon buttons and composer shells), borders and focus (D-01), placeholders (D-06), elevation
    (D-12, replacing "`shadow-xl` on popovers"), motion (§7, with 200 ms for the suggestion bar) and
    charts (C-075).
- **UX-SH-01:** the nav row is 14 px (`text-sm`, C-048), not `text-[15px]`. Its hover is `bg-hover`,
  not `bg-white/5`. The active row has the selection bar. The count badge uses `text-on-brand`.
- **UX-SH-03:** no 1200 px cap (C-074). The inbox is inset on all four sides, as Ask is.
- **UX-INB-03:**
  - The focus wording is fixed: the 2 px outline is the cue, and `raised` is extra, never the only
    one.
  - The search is SearchInput, with the placeholder "Search" and the name "Search conversations".
  - The chips are the built set, including "Needs you" and "Handled by AI" (UI-068).
  - The segments have no shadow.
- **UX-INB-07:** the composer is one `rounded-xl` shell (D-16) with the tool row below the textarea.
  Send is a Button (`secondary` while empty, the gradient when ready), not a 36 px circle.
- **UX-SCR-03:** the back link "‹ Automations" replaces the breadcrumb, and below 1280 px the side
  panel follows the steps (D-16).
- **UX-A11Y-01:** control edges are `line-control` (D-01), placeholders `fg-secondary` (D-06), and
  focus is the 2 px brand outline on every focusable element.
- **DS-7, the muted ghost (the Design System Architect's decision, review gate RG-09):**
  - A tertiary action may be a ghost Button with `text-fg-secondary`. Ghost's hover and open
    already turn the text `fg`, so all nine call sites behave alike, and a `quiet` variant would
    only rename them.
  - It is the one text-colour override allowed on Button. AI actions use `soft` (C-073), never
    `text-brand-fg`.
- **AGENT_CONTEXT:** the decision table marks D-02, D-04, D-05, D-07 to D-11 and D-14 to D-17 as
  applied, with their tasks. The checklist names the design lint and the copy lint. The chart
  aliases, the palette lock and the resizable panes are listed.

## C-077 · Webhook coverage and entry sources (GR-01, feature/gr-01-webhook-coverage)
An addition to the spec's platform layer (§1.5, TR-PL-12), from the growth plan
(`docs/roadmap/IMPLEMENTATION_PLAN.md`).
- **Instagram subscribes to four more webhook fields:** `messaging_postbacks`,
  `messaging_referral`, `messaging_optins` and `live_comments`.
  - Meta's Instagram API overview lists all four (2026).
  - Existing accounts pick them up from the `reconcile_subscriptions` job (TR-WH-08).
  - Outside accounts receive them only with Advanced Access, after App Review.
- **Parsing, following Meta's documented shapes:**
  - An ig.me link with `?ref=` arrives as a referral event; an ad arrives as a message's `referral`
    (`source: "ADS"`, `ad_id`, `ads_context_data.ad_title`).
  - A WhatsApp message from a Click to WhatsApp ad carries `referral` (`source_type`, `source_id`,
    `headline`, and `ctwa_clid` when there is one).
  - A tapped postback keeps its payload (for GR-11's ice breakers).
  - An opt-in is parsed and kept in the stored webhook event for GR-02's consent records.
  - A Live comment is a comment with `is_live`; its id field is `comment_id`.
- **Entry source:** each new conversation records how it began: organic, an entry link (its
  ref), an ad (its id), with ice breakers added by GR-11.
  - The entry comes from the first message's referral, or a referral the contact made in the hour
    before.
  - A referral alone never starts a conversation, so the inbox shows no empty threads. It is kept
    on the contact.
  - A referral delivered up to five minutes after the first message upgrades an organic entry.
  - Conversations from before GR-01 have no entry.
  - The conversation detail returns `entry`, and the details panel shows "Started from".
- **Live comments** are stored and labelled "Live" in the comments list. Comment automations
  don't answer them yet: post scopes mean posts and Reels, and a Live's private reply works only
  while it is on air. GR-10 adds the Live scope.
- **Migration 0018** adds the columns:
  - `conversations.entry_source`, `entry_ref`, `entry_ad_id`, `entry_at` and `last_referral`;
  - `contacts.last_referral` and `first_entry_source`;
  - `comments.is_live`;
  - `messages.postback_payload`.
- **The sandbox** injects every new kind, so dev and e2e go through the real webhook path.

## C-078 · Contacts foundation: tags, custom fields, consent, export (GR-02, feature/gr-02-contacts)
An addition from the growth plan. It is backend and API only; GR-17 builds the contacts page.
- **One contact per channel identity, as before (PD-10).** No matching across Instagram and
  WhatsApp.
- **Tags:**
  - A workspace's labels, unique by name in any case, with a colour from the identity palette, so
    they never wear status colours.
  - Any member tags contacts, one at a time or up to 500 at once; admins manage the tags.
- **Custom fields:**
  - Each has a key, a label and a type: text, email, phone, number, date or choice (with options).
  - Values are stored by key on `contacts.fields` and validated by type; an unknown key is refused.
  - A key and type never change; deleting a field removes its values from every contact.
  - The number of fields is capped by a new entitlement, `contact_fields`: Free 5, Pro 50, Max
    200. Decided 2026-10-23: the owner left it to us. A few fields free, room to grow on paid
    plans.
  - **Contacts themselves are never metered (PD-2).**
- **Email and phone** on the contact, each with where it came from and whether it was verified.
  An email is lower-cased and checked for shape. A phone is stored as E.164, with a ten-digit
  Indian mobile taken as +91.
- **Consent** (`contact_consents`) is append-only: channel, purpose (marketing), granted or
  revoked, source (platform opt-in, flow, STOP reply, member, import) and evidence. The latest
  record per channel is current.
  - Instagram's `messaging_optins`, parsed in GR-01, now records consent: granted, or revoked
    when Meta reports a stop.
  - Admins record consent given elsewhere with a note, which is the evidence.
- **The list:**
  - Newest activity first, with a keyset cursor. Activity is the latest of the conversation's last
    message (every send path keeps it), the contact's own last comment (`last_activity_at`) and
    when the contact was created.
  - Filters: search on name, @username, email or phone; every chosen tag; platform; account;
    email or phone present; current marketing consent per channel; minimum lead score; activity
    range; up to five custom fields, each `key:value` (equal, ignoring case) or `key:*` (any
    value). A filter on a field the workspace doesn't have is refused.
- **Export (the R2 "data export"):** admins download the filtered contacts as CSV, streamed from
  the API, so no file of personal data is ever stored. Custom fields follow the fixed columns, and
  a cell a spreadsheet would read as a formula gets a leading quote. *Deviation from GR-02 as
  planned, which said "a job that emails a link".*
- **Ask Social Hood:** `get_customer` now includes tags, fields, whether an email and phone are
  known, and marketing consent. A new `list_contacts` lists contacts by tag, email or phone
  present, platform or minimum lead score.
- **Moved to GR-14:** contact fields as message variables (`{field.key}`), where flows first
  capture data.
- **Migration 0019:**
  - new tables `tags`, `contact_tags` (with an id, so an account's purge deletes them in batches
    with their contacts), `contact_field_definitions` and `contact_consents`;
  - on `contacts`: `fields`, `email`, `email_source`, `email_verified`, `phone`, `phone_source`,
    `phone_verified` and `last_activity_at`, backfilled from comments.

## C-079 · The flow engine (GR-03, feature/gr-03-flow-engine)
An addition from the growth plan. What an automation does after its trigger becomes a graph of
steps; the trigger, keywords, posts, public replies and run settings stay on the automation.
- **Steps** (`schemas/flows.py`, schema version 1, at most 50):
  - `send`: text, an image, link buttons (a https link, or the account's profile), or quick
    replies, each leading to its own step, with typed answers going to `on_text`;
  - `ask`: a question whose answer is checked (text, email or phone) and saved to a custom field,
    or for an email or phone to the contact; a retry prompt, then `on_skip`;
  - `branch`: the first rule that holds (a tag, a field, email or phone known, follows the
    account, platform, lead score), else `otherwise`;
  - `action`: add or remove a tag, set a field, notify the team, hand off to a person;
  - `delay` (at most 23 hours), `randomize` (A/B by weight), `ai_reply` and `end`.
- **No loops:** a run visits each step at most once. Branches may meet again.
- **What Instagram allows, checked on every path:**
  - A comment's flow starts with its message, the private reply: no image, and nothing more until
    the person answers (a quick reply or a question).
  - Whether someone follows the account is known only once they've written.
  - An AI reply is the first step and ends the flow.
- **Today's automations are compiled, not stored.** Their flow is built from the message settings
  whenever it's read (`flows.compile_legacy`), so it can never drift from the current editor:
  - tap first becomes an opening with one quick reply (or any typed answer) leading to the
    message;
  - the follow nudge becomes a branch on not following, then the nudge with "View profile";
  - a comment automation without tap first gets no nudge, as before.
  - A regression suite runs every template, with tap first and the nudge on and off, against the
    current renderer. *Deviation from GR-03 as planned, which said to store a compiled graph for
    every automation in the migration.*
- **Saved flows:** `PUT …/automations/{id}/flow` saves one, and its steps replace the message
  settings from then on (`flow_source: flow`).
  - Versions are kept in `automation_flows`. A save changes the current version until a run has
    started on it, then makes the next, so a run always follows the flow it started with.
  - The automation's action follows the flow (`ai_reply` when it has an AI reply), so the AI plan
    entitlement and the private-reply queue apply as before.
  - `DELETE …/flow` goes back to the settings.
  - Activation and an active automation's saves check the flow, with each step's field
    (`flow.steps.2.text`).
- **Runtime** (`services/automations/engine.py`), for automations saved as a flow. Automations
  on their message settings keep today's runtime, so they behave exactly as before. *Deviation
  from GR-03 as planned, which runs every automation on the graph; a later cleanup can convert
  them once the flow editor (GR-13) makes every automation a flow.*
  - A run keeps its flow version, its step and its state (sending, replying, next, delaying,
    done), and logs every step it reaches in `automation_run_steps`: its status, its message, and
    what happened (the answer, the rule or path taken, the tries, why it failed).
  - Entry is unchanged: keywords, posts, cooldowns and the read-only account. A DM's first steps
    run at once; a comment's private reply goes through the account's queue. A flow starting with
    an AI reply runs the AI reply as before.
  - A run moves on once its message is delivered. A message with quick replies, or a question,
    waits for the answer (`awaiting_reply`).
  - **Answers come before keyword matching:**
    - A tapped quick reply names its run, step and option (`shf:{run}:{step}:{n}`). A tap on a
      step the run has left is handled and sends nothing.
    - Typed text answers the contact's newest run waiting for a question, or for a message whose
      typed answers lead somewhere.
    - An email or phone answer goes to the contact (source `flow`), anything else to its custom
      field. One that doesn't fit gets the retry prompt, then `on_skip`.
  - **The continue job** (`run_automation("flow", run_id)`):
    - A branch on following reads the follow status fresh, outside any transaction.
    - A delay schedules the job for its end.
    - A message the 24-hour window no longer allows fails its step and ends the run.
  - **Actions:**
    - "Hand off" puts the conversation in Needs you and pauses the AI until it's resumed.
    - "Notify the team" is a new in-app notification, `automation_alert`.
  - Ask Social Hood's `get_automation` lists a flow's steps.
- **Migration 0020:**
  - new tables `automation_flows` and `automation_run_steps`;
  - `automations.flow_version`;
  - on `automation_runs`: `flow_version`, `step_id`, `flow_state` and `wait_until`.
  - Expand-only; nothing is rewritten.

## C-080 · Outbound events and webhooks (GR-04, feature/gr-04-outbound-webhooks)
An addition from the growth plan: one event pipeline for Zapier, Make, Sheets and CRMs to sit on.
- **The events** (`services/webhooks/events.py`, each with a version):
  - `contact.created`: a new person wrote, commented or opened an entry link;
  - `contact.updated`: email, phone or custom fields changed;
  - `contact.tagged`: a tag added or removed, only when it really changed;
  - `lead.captured`: a flow's question saved an email, phone or field (GR-03; GR-14 extends it);
  - `message.received`;
  - `automation.run.completed`: a flow run finished, or a run on its settings had its message
    sent or failed; once per run.
  - `conversation.assigned` (GR-20) and `broadcast.finished` (GR-23) are in the catalogue so
    endpoints can subscribe now, and are emitted once those exist.
  - Backfilled history emits nothing.
- **The envelope:** `{id, type, version, created_at, workspace_id, data}`.
  - A contact is its id, platform, @username and name.
  - An email or phone appears only in `lead.captured` and in `contact.updated` when it changed.
  - No access tokens.
- **Delivery** (`services/webhooks/delivery.py`, job `deliver_webhook`):
  - Signed per Standard Webhooks: `webhook-id` is the event id, the same on every attempt and
    replay, so it's the receiver's idempotency key; plus `webhook-timestamp` and
    `webhook-signature`.
  - Posted under the SSRF rules (the checked address, no redirects, 10 seconds).
  - A 2xx delivers it. Anything else is retried after 1 minute, 5 minutes, 30 minutes, 2 hours,
    6 hours and 12 hours: 7 attempts in about 21 hours.
  - The log keeps each delivery's last attempt: status code, duration and reason.
  - After 5 deliveries in a row run out of attempts, the endpoint is disabled and owners and
    admins get an in-app notification, `webhook_disabled`.
  - Finished deliveries are kept 30 days.
- **Endpoints** (`/webhook-endpoints`, owners and admins):
  - https only, checked against private addresses;
  - the signing secret (`whsec_…`) is shown once, on create and rotate, and stored encrypted
    like platform tokens (added to the key rotation);
  - pause, turn back on (which resets the failure count), test event, replay, delete.
  - The new `webhook_endpoints` plan limit is Free 1, Pro 5, Max 20. Decided 2026-10-23: the
    owner left it to us.
    - Free gets one, because sending leads to a sheet or CRM is a core early reason to stay,
      and a webhook costs almost nothing to run.
    - The pressure to upgrade comes from AI credits, contacts and broadcasts.
    - Pro covers a CRM, a sheet and a notifier; Max covers agencies.
  - `signing_secret` is allowed in responses by the schema security test for that reason.
- **`WEBHOOKS_ALLOW_PRIVATE`** lets development and e2e post to a local receiver. Production
  refuses it.
- **Web:** Settings › Integrations (owners and admins).
  - Add an endpoint with its events.
  - See the secret once, with a copy button.
  - Turn it on or off, send a test event, get a new secret, delete it.
  - Each endpoint's latest deliveries, with status, attempts, response and when, and "Send again"
    for a failed one. The log refreshes while a delivery is being tried.
- **Migration 0021:** `webhook_endpoints` and `webhook_deliveries`. Expand-only.

## C-081 · The Activity page (GR-05, feature/gr-05-activity)
Automations used to fail silently from the customer's point of view. We already recorded the
failures; now they can see them. A read model over existing tables: no migration.
- **The feed** (`GET /v1/w/{wid}/activity`, `services/activity/feed.py`), newest first, keyset
  cursor on (time, id). It merges:
  - automation runs (`automation_runs`: result, error code and reason);
  - failed flow steps (`automation_run_steps`), only when their run did not itself fail, so one
    problem is one row;
  - failed outbound sends by people and the AI (`messages`, status failed); an automation's
    failed send is shown as its run, not twice;
  - failed outbound webhook deliveries (GR-04), with the endpoint's name or host, never its URL
    query or payload;
  - accounts that need reconnecting or are in error, from `social_accounts` as they are now.
- **Filters:** failures only (on by default), type, automation, account.
  - An automation filter leaves out sends, webhooks and accounts; an account filter leaves out
    webhooks.
  - "Failures" are runs that failed, sent only half, or were skipped for the 7-day limit or a
    read-only plan.
- **Who sees it:** owners and admins, like the automations it reports on and Settings,
  Integrations. Agents get 403 on the page and the Ask tool. They can still retry a failed
  message from the inbox.
- **No raw data:** no message text, no payloads, no platform responses. Each item carries only
  a title, a reason, a code, and ids.
- **Left out on purpose:**
  - Failed inbound webhook events. They are not tenant-scoped, a failed one has no workspace
    yet, and their errors are internal.
  - Social account status history. There is none; an account shows once, at its last change.
  - Broadcast failures arrive with GR-23.
- **Reasons** (`services/activity/reasons.py`): one plain sentence and at most one action.
  - The sentence reuses `sending.readable_error`, the copy of a Failed bubble, for the codes it
    knows; a platform rejection keeps its stored reason; the rest are written there.
  - A comment run that half worked keeps its stored "Public reply: ... DM: ..." text.
  - Reconnect (`account_needs_reconnect`, `capability_unavailable`) goes to Settings,
    Connections.
  - Upgrade (`read_only`, `entitlement_required`, `quota_exceeded`) goes to Billing.
  - Check the endpoint (`endpoint_off`, `endpoint_error`, `endpoint_unreachable`) goes to
    Settings, Integrations. These webhook codes are derived from the delivery's error and
    response code.
  - Open the chat (`reply_window_closed`, `delivery_unknown`, `recipient_unavailable`,
    `platform_rejected`) goes to the conversation, when there is one.
  - Edit the automation (`nothing_to_send`, `nothing_sent`) and Open the automation (anything
    unknown) go to the automation.
  - No action: `expired` (Instagram's 7-day private reply limit), `platform_rate_limited`,
    `platform_unavailable`. Nothing the member can fix; the second and third can be retried.
- **Retry only where it is safe:**
  - A failed message with `platform_rate_limited` or `platform_unavailable` goes through the
    existing `POST /messages/{id}/retry` (one row, one client id, so it can't double-send).
  - `delivery_unknown` is not retried from here: it may have arrived, so the reason says to
    check the chat first.
  - A failed webhook delivery goes through `POST /webhook-deliveries/{id}/replay`, only while
    its endpoint is on.
  - The item says `retryable` and where (`retry.kind`, `retry.target_id`); there is no new
    write route.
- **Alerts** (`check_automation_failures`, every 10 minutes):
  - An automation with 5 or more failed or half-sent runs in the last hour notifies owners and
    admins: in app, and push under the "Needs you" switch (new type `automation_failing`).
  - It links to `/settings/activity?automation={id}`, which opens the page filtered to it.
  - One per automation per 6 hours (dedupe key).
  - Accounts needing reconnect already notify and email once per broken connection
    (`mark_needs_reconnect`); not repeated. Disabled webhook endpoints already notify
    (`webhook_disabled`).
- **Ask Social Hood:** `list_recent_failures` (owners and admins), the latest 10 failures with
  reasons, for "what's failing?".
- **Web:** Settings, Activity (owners and admins): the filters, one row per item with its
  title, badge, reason, time, and the one link or Retry button; "Show older" pages.
- **Needs checking centrally:** `apps/api/openapi.json` and `packages/api-client` need
  regenerating for `ActivityItem`, `ActivityList`, `ActivityAction` and `ActivityRetry`.

## C-082 · Story reply trigger (GR-06, feature/gr-06-07-stories)

- **A story reply is a DM.** It arrives as a message with `reply_to.story`, opens the 24-hour
  window and goes through the DM runtime. The parser keeps the story's `id` as the story
  attachment's `media_id` (private, like the other platform ids), so an automation can be scoped
  to one story. The story's address is never copied.
- **Trigger `story_reply`** (the `ck_automations_trigger` check is re-created in migration 0022):
  - the DM runtime picks the triggers a message can start by its kind (`runtime.dm_triggers`);
  - a story reply starts story reply and DM keyword automations together, keyword ones first,
    then those that answer anything, each by priority. *Deviation from the plan, which said the
    trigger is chosen by the kind alone: an account's existing DM keyword automations kept
    answering story replies before, and still do when no story reply automation takes the reply.*
  - no keywords means any reply; keywords use the existing match modes.
- **A story like does not trigger.** A like is the heart sticker on a reply to a story, which we
  store as the text "heart". Such a reply never starts a story reply automation. A reaction event
  was never a trigger.
- **Scope** reuses `post_scope`: "all" answers any story, "selected" the stories in the new
  `automations.story_ids` (text[], at most 20; not `automation_posts`, which points at synced
  posts, and stories are never synced). "Next post" is refused for a story reply.
  - *A story lasts 24 hours, so a chosen story stops matching once it expires. The automation stays
    active and idle; the editor says so and shows a chosen story that has gone as expired, with
    Remove. Nothing pauses it by itself.*
- **The story picker** is `GET /stories?account_id=` (owners and admins): Instagram's
  `/me/stories`, read on each request and not stored, newest first, with `expires_at` 24 hours
  after posting. The adapter gets `list_stories` (the sandbox lists two per account, ids
  `<account>_story_0` and `_1`; WhatsApp lists none).
- **The heart** (`automations.story_heart`): Instagram's heart sticker is queued as its own
  message just ahead of the run's message, through the send pipeline. It is not linked to the run,
  so it never changes the run's result, and a refusal only goes to the log. *No message-reaction
  call exists in the adapter; the sticker is what exists.*
- **Flows (GR-03):** a story reply is a DM trigger for flows (`flows.Context.comment` stays false),
  so a story reply automation can be saved as a flow.
- **Template** "Reply to story, send the link" (`story_reply_link`).
- **Sandbox:** `SandboxInbound` gains `story_reply`, `story_like` and `story_mention` and a
  `story_id`; the e2e helper `inbound` passes them.
- **Web:** the When step has "Instagram story reply"; its posts slot is "On these stories" (any or
  chosen, thumbnails with time left, the heart switch); its keywords are optional.
- **Unverified (T0.9):** that `reply_to.story.id` equals the id `/me/stories` lists, and the
  `/me/stories` fields.
- **Migration 0022** (shared with C-083): the trigger check, `story_ids` and `story_heart`.
  Expand-only.

## C-083 · Story mentions (GR-07, feature/gr-06-07-stories)

- **A mention is a DM** with a `story_mention` attachment. Ingest keeps a record in the new
  `story_mentions` table (who, when, the message, the story's address and when it expires).
  - The address is Instagram's CDN link. It is never downloaded or copied, and no thumbnail is
    stored: the policy question stays closed until someone asks for it.
  - Its expiry is the link's `oe` parameter, else 24 hours after the mention. A mention that
    arrives with an expired link keeps no address.
  - `purge_expired` clears the address once it has expired (`story_mention_links`); the record
    stays.
- **Trigger `story_mention`** starts only story mention automations, which answer every mention
  (no keywords). The message is a thank-you or a reward link, sent like any DM. A mention never
  answers a waiting question (a tap-first opening or a flow step). Template `thank_story_mentions`.
- **Mentions list:** `GET /story-mentions?account_id&cursor&limit` (any member), newest first,
  cursor paged, with `total_7d`. `link_url` is only given while the story is live. Web: Comments
  has a "Story mentions" button to `/comments/mentions` (who, when, View story, Open conversation).
- **Analytics:** Home's overview periods carry `story_mentions`. The weekly digest is unchanged.
- **Events:** no GR-04 event. The catalogue has none for mentions, and `message.received` already
  fires for the mention's DM. Adding `story.mentioned` can wait for someone to ask.
- **Ask Social Hood:** no new tool. `prepare_automation` accepts the story triggers.
- **Tables:** `story_mentions` is in the account purge (it references the account), the workspace
  deletion and the isolation seeds.
- **Migration 0022** is shared with C-082.

## C-084 · Entry links and QR codes (GR-08, feature/gr-08-09-entry)

- **A link** is a row in the new `entry_links` table: account, code (unique per account, 3 to 40
  letters, digits, `_` and `-`), name, and the automation it starts. The address is
  `https://ig.me/m/<username>?ref=<code>` (the account's id when it has no username). The code is
  made (8 characters, no look-alikes) unless typed, and never changes, so a printed QR code keeps
  working. Deleting the automation sets the link's automation to null; the link and its counts stay.
- **Trigger `entry_link`** (the `ck_automations_trigger` check is re-created in migration 0023):
  the automation needs nothing but a message. It starts from the DM that is the first customer
  message after a referral whose ref is one of the account's links, within one hour (GR-01's
  referral window), and only for the automation the link points at.
  - The run reads the conversation's `last_referral` (GR-01 stores a message's own referral, a
    `messaging_referral` event, or the contact's recent referral there) in
    `services/automations/entry`. A later message, an unknown ref or a referral older than an hour
    starts nothing. Cooldown, read-only and flows work as for any DM trigger.
  - Entry link and ad click automations run **before** keyword automations in the DM runtime
    (`matching.runtime_order`: entry, then keywords, then answers-anything). *A link or an ad is the
    more specific way in, so it wins over a keyword in the first message.*
  - *A referral that Meta delivers after the first message (GR-01's five-minute upgrade) is not
    seen: the run looks about a second after the message. Such a conversation is still marked as
    from the link, but its automation does not start.*
- **API** (owners and admins): `GET/POST /entry-links`, `GET/PUT/DELETE /entry-links/{id}` and
  `GET /entry-links/{id}/qr?format=svg|png` (an attachment). A link's automation must be an entry
  link automation of the same account. Stats per link: `opened_conversations` (conversations whose
  `entry_source` is link and `entry_ref` is the code) and `runs` (runs of entry link automations on
  those conversations).
- **QR codes** use `segno` (new dependency, pure Python, no further dependencies; `uv.lock`
  updated). Error correction M, 4-module quiet zone, 10 pixels per module.
- **Web:** Automations has an "Entry links" button to `/automations/entry-links`: create, edit
  (name and automation), delete, copy link, QR preview and SVG and PNG downloads, and the two
  counts. The When step has "Instagram entry link"; it has no keywords step.
- **WhatsApp:** *deviation from the plan, which said `wa.me/<number>?text=<keyword>`.* Automations
  run on Instagram accounts only (validation refuses a WhatsApp account), so a WhatsApp link would
  have no automation to start. Links are Instagram only; a WhatsApp prefilled link can come when
  WhatsApp automations do. *Unverified:* that `ig.me/m/<id>` works for an account without a
  username.
- **Unverified (Meta):** that `messaging_referral` arrives for a user opening an `ig.me` link with
  `?ref=` when a conversation already exists, and the shape of the referral for a first-time user
  (it is delivered with the first message as `message.referral` in some cases). GR-01's parsing
  covers both; only a real account settles which one Instagram sends.
- **Tables:** `entry_links` is in the account purge (it references the account), the isolation
  seeds (`link_id`, an example body for the write routes) and the account deletion seed.
- **Migration 0023** (shared with C-085): the trigger check, `automations.ad_ids` and `entry_links`.
  Expand-only.

## C-085 · Ad clicks (GR-09, feature/gr-08-09-entry)

- **Trigger `ad_click`** answers a DM that is the first customer message after an ad referral
  (GR-01: an Instagram ad's `message.referral`, or a Click to WhatsApp ad's, recorded as
  `entry_source` "ad" and `entry_ad_id`). Same timing rule, order and cooldown as C-084. No
  keywords.
- **Scope** reuses `post_scope`: "all" answers any ad, "selected" the ad ids in the new
  `automations.ad_ids` (text[], at most 20, typed by hand in the editor; "next post" is refused).
  The editor's posts slot reads "On these ads".
- **Listing ads is not built.** It would need Meta's `ads_read` permission (optional, *unverified*),
  which would add an App Review item; the plan marked it optional. Ad ids come from Ads Manager.
- **Attribution:**
  - the inbox details panel's "Started from" now reads `From an ad: "<title>"` (or "From an ad");
  - the Home overview periods carry `conversations_from_ads` and `conversations_from_links`
    (conversations that began in the period, by entry source). *The plan said "a filter in the
    analytics"; the analytics routes are post-based and have no conversation to filter, so the
    breakdown is on the overview, where conversations are counted.*
- **`ctwa_clid`** was already kept by GR-01 in `contacts.last_referral` and
  `conversations.last_referral` (the referral record), and survives the entry upgrade. Nothing is
  sent to the Conversions API yet; a later task reads it from there.
- **WhatsApp:** a Click to WhatsApp referral is stored and shows "From an ad", but WhatsApp has no
  automations, so the trigger only runs for Instagram ads (click to Instagram DM). *Unverified:*
  the 72-hour window in which follow-up marketing messages from a Click to WhatsApp conversation
  are free. No pricing or sending logic depends on it.
- **Sandbox:** a DM with `referral_source: "ad"`, `ad_id` and `ad_title` (already in GR-01's
  injector) tests it end to end.
- **Migration 0023** is shared with C-084.

## C-086 · Live comments trigger (GR-10, feature/gr-10-11-live-icebreakers)

- **The Live scope is a new column, not a post scope.** `automations.comment_surface` is `posts`
  (default, today's behaviour), `live` or `both`; comment keyword and any comment triggers use it.
  *Deviation from the plan's "a Live scope": `post_scope` has a check constraint and means which
  posts, so a Live is not one of them.*
  - A Live comment ignores `post_scope` and chosen posts; a Live-only automation is saved with
    post scope "all" and no posts, and needs no post choice to activate (even "any comment").
  - A posts-only automation passes over Live comments, and a Live-only one passes over posts.
- **Intake** no longer skips Live comments (C-077): `enqueue_for_comment` queues the run for them
  and the runtime checks the surface. Replies in a thread still start keyword automations only.
- **When the Live ended.** Instagram sends no "Live ended" event.
  - *A Live comment is "late" once it is more than 10 minutes old (`LIVE_REPLY_WINDOW`) when it is
    matched, or when the queue gets to it. Unverified (T0.9): the window, and that Instagram refuses
    a private reply after the broadcast.*
  - A late comment records a `skipped_expired` run with the code `live_ended` and the reason "The
    Live had ended". No new `RunResult`, so the result check is unchanged. Nothing is sent.
- **Priority, not a second path.** Private replies still go only through the account's queue and its
  750-an-hour bucket. Each pass takes Live-only automations first while they have runs waiting;
  each drain also skips queued Live runs older than the window. An automation on "both" is ordered
  like any other.
- **Activity (GR-05):** the code `live_ended` reads "Instagram only lets an account reply privately
  to a Live comment while the Live is on." with the title "... skipped a comment that came after
  the Live ended". The runs list label for `skipped_expired` is now "Skipped: too late to reply".
- **Flows and the AI** work as for other comment triggers (a private reply first).
- **Sandbox:** `SandboxInbound.age_seconds` makes a comment or Live comment arrive that many
  seconds old, to show a late Live comment.
- **Web:** the posts step has Posts and Reels, Live, or both; Live hides the post scope.
- **Migration 0024** (shared with C-087): `comment_surface` and its check. Expand-only; the
  downgrade drafts Live-only automations first.

## C-087 · Ice breakers (GR-11, feature/gr-10-11-live-icebreakers)

- **A table, not JSON on the account.** `ice_breakers` holds up to 4 rows per Instagram account
  (position 0 to 3, unique per account), each with the question (1 to 80 characters), the
  automation it starts or `answer_with_ai` (never both), and how the last sync went (`synced_at`,
  `sync_error`, the same on every row of the account). It is in the account purge, the workspace
  deletion and the isolation seeds.
- **Payload `ib:{id}`.** A position keeps its row, and so its id, when its question or mapping
  changes, so a starter already shown in someone's app keeps working. A removed position's old
  payload matches nothing.
- **Trigger `ice_breaker`** (the trigger check is re-created in migration 0024). The automation has
  no keywords; flows work as for any DM trigger. A postback whose payload is one of our starters
  starts ice breaker automations only, and only the one its starter maps to; it answers no waiting
  question (tap first or flow). `runtime.dm_triggers` picks this by the payload.
- **Answer with AI:** no automation starts and the message is not marked handled, so the inbox AI
  answers it as any customer message (the existing analysis and suggestion path). Nothing new to
  build there.
- **Entry source:** a conversation that begins with a tap records `ice_breaker` (C-077 had
  reserved it) with the question as its ref, unless a referral came first.
- **API** (owners and admins write, any member reads), under the account so isolation is by path:
  - `GET /social-accounts/{id}/ice-breakers` gives the list, `synced_at`, `sync_error` and
    `max_items`;
  - `PUT` replaces the whole list in order and pushes it; `POST .../sync` pushes again;
  - a push the platform refuses is not an HTTP error: the list is kept, `sync_error` is a plain
    sentence (the usual platform error copy), and `synced_at` stays at the last good push.
  - Validation is 422 per field: one target per starter, an automation of this account on the
    `ice_breaker` trigger, 80 characters, no repeated question, at most 4. WhatsApp accounts are
    refused.
- **Adapter:** `set_ice_breakers(acct, starters)` replaces the list (an empty list clears it).
  Instagram: `POST /me/messenger_profile?platform=instagram` with one default-locale
  `ice_breakers` entry, `DELETE` of the `ice_breakers` field to clear, then a `GET` to read it
  back. *Unverified (T0.9): the request shapes, that only a default locale is accepted, the
  80-character limit, and that a re-set replaces the old list.* The sandbox keeps what was set
  per account (`outbox.ICE_BREAKERS`); a question holding `[sandbox:fail=<code>]` fails the push.
  WhatsApp raises `capability_unavailable`.
- **Web:** Automations has a "Conversation starters" page (`/automations/starters`): up to four
  rows (question, then an automation or "Answer with AI"), Save, and the sync line with the
  reason and "Send to Instagram again". The When step offers "Instagram conversation starter".
  The page says the starters don't show on desktop.
- **Deviation from the plan:** the plan said "Settings or Automations"; it lives under
  Automations, beside the automations it starts.
- **Migration 0024** (shared with C-086).
## C-088 · Welcome and default replies (GR-12, feature/gr-12-welcome-default)

- **Two triggers, both DMs, no keywords:** `first_message` (a welcome) and `default_reply`. They
  use the existing DM path: `runtime.dm_triggers` lists them for an ordinary DM, `_match_dm` keeps
  them only when they apply, and `matching.runtime_order` puts them last. Flows, AI-reply actions,
  cooldowns, the read-only account check and run records work as for any DM automation.
- **First message means:** the contact has no earlier inbound customer message to this account
  (`repositories/inbox.has_earlier_inbound_dm`: earlier by time, then id, across the contact's
  conversations on the account).
  - It reads true history, so contacts who existed before the feature shipped are not welcomed on
    their next message.
  - A contact who only commented has no DM yet, so their first DM is welcomed.
  - Any earlier customer message counts, including a story reply or mention.
- **Default reply means:** an ordinary DM that no automation matched, while the conversation's
  effective AI mode is Off (`conversations.ai_mode_override`, else `social_accounts.ai_mode`, as
  the suggestions code resolves it).
  - `ai_paused_until` is not read: a pause means a person is handling it, and with Suggest or Auto
    the mode is not Off anyway.
  - *The plan's Auto is not checked against the plan's entitlement: an account on Auto without
    the entitlement gets no default reply.*
- **Order and precedence (decision):** keyword and any-reply automations go first. The welcome and
  default reply answer only a DM that none of them matched.
  - A keyword that matched but was on cooldown still counts as matched, so a repeated question
    does not get "we did not understand".
  - If both fallbacks apply (a first DM, AI off), the welcome answers and the default reply does
    not. The next DM is not a first message, so the default reply answers it.
  - Why: one automatic message per DM, and the specific answer beats the generic one.
- **Never fire on:** a story reply or mention, a postback or ice breaker tap, a quick reply tap,
  a message that answers a waiting flow step or tap-first opening, or one already handled. Our own
  echoes never run automations.
- **Loops:** each automation's `cooldown_hours` per contact applies (default 24; the default reply
  template uses 12). A welcome fires once anyway, because only a first message qualifies.
- **Web:** the When step has "First message (welcome)" and "Any other message (default reply)",
  each with a one-line explanation (the default reply says it answers only while AI is Off). Both
  hide the keywords and posts steps. Templates `welcome_new_contacts` and
  `default_reply_when_ai_off`.
- **Test tab:** treats the text as a DM for both triggers; it cannot know if the contact is new or
  AI is off, so it reports a match.
- **Ask Social Hood:** `prepare_automation` accepts both triggers; no new tool.
- **Migration 0025** (parent 0022 until re-chained): the trigger check only. Downgrade turns these
  automations into trigger-less drafts.
- **Unverified:** nothing here depends on Meta rules. Welcome messages are ordinary DMs inside the
  24-hour window opened by the customer's message.


## C-091 · The contacts page (GR-17, feature/gr-17-contacts)

GR-02 had already built the contacts list, its filters, the CSV export, tags, fields and consent
in the API. GR-17 adds what the page needed on top, and the page itself. (The coordinator
renumbers this entry if another branch took C-088.)

- **List, filters and export: reused as built.** Filters are tag (every one chosen), search, email
  or phone present, platform, account, marketing consent per channel, minimum lead score, activity
  range and up to five custom fields (`key:value` equals, `key:*` has any value). Export stays
  admin only and streams. "Tag = lead-magnet and has email" is `tag_id` plus `has_email=true`, and
  the export of it has the same rows (an integration test checks both).
- **Moving activity ranges (new).** `active_within_days` (active in the last N days) and
  `inactive_for_days` (no activity for N days or more), 1 to 3650, beside the fixed
  `active_after` and `active_before`. *A saved segment needs a range that moves; two fixed dates
  would go stale.* The page uses only the moving ones (7, 30 or 90 days active; quiet for 30 or 90).
- **Count.** `GET /contacts/count` takes the list's filters and says how many match. It feeds
  "Select all 312 that match" and the bulk cap message.
- **Saved segments (new table `contact_segments`, migration 0026).**
  - A name (1 to 60, unique in any case per workspace) and the filter as JSON, the same keys as
    the list. It stores the filter, never the people, so a segment is whoever matches now. At most
    50 per workspace.
  - `GET /contact-segments` (any member); `POST`, `PATCH /{id}` and `DELETE /{id}` for owners and
    admins. *Decided: agents use segments but do not manage them, matching tags and fields (admins
    manage, any member uses).*
  - Saving checks the filter: a tag that is not there is 404, a custom field the workspace does
    not have is 422. A tag or field deleted later does not break the segment; the list then
    refuses the field with its plain message instead of quietly widening the match.
  - The response filter is its own class, `ContactFilterOut`, so the API description keeps one
    name per direction (a model used both ways with defaults is split in two by FastAPI).
  - *Not built: a segment id on the list, count or export routes.* The page sends the segment's
    filters. Broadcasts (GR-23) will read `contact_segments.filter` through
    `services/contact_segments`.
- **Bulk tag by filter.** `POST /contacts/bulk-tags` takes `contact_ids` (up to 500) **or**
  `filter` (the same keys), not both. A filter applies to everyone it matches, up to **5,000**
  (`BULK_FILTER_CAP`). A bigger match is a 422 on `filter` that says how many matched ("That
  filter matches 7,200 contacts. Narrow it to 5,000 or fewer to tag them at once."), and nothing
  is changed. Any member may bulk tag, as before.
  - **Audit.** Every real change is still one `contact.tagged` event (GR-04, so webhooks and
    Activity see it), and one log line (`contacts_bulk_tagged`) records who, how many contacts and
    how many tags were added or removed, and whether a filter chose them. There is no audit table
    yet; the team audit arrives with GR-19.
  - `change_tags` now reads the existing pairs in one query instead of one per contact and tag, so
    5,000 contacts is a few queries.
- **Timeline.** `GET /contacts/{id}/timeline?cursor&limit` (any member, read-only, 30 per page by
  default, 100 at most). Sources that exist today: the contact's conversation (with how it began),
  comments, automation runs (the automation's name and a plain outcome, no error text), story
  mentions, consent records and tags added. Each source is read newest first by (time, id) and
  merged, so paging never repeats or skips an item. A comment shows its first 200 characters.
  - *Left out because the data does not exist yet:* captured answers (GR-14 adds them; email and
    phone have a source but no time) and broadcasts received (GR-23). Each adds a source in
    `services/contact_timeline.py`.
- **Consent filter and display.** `contact_consents` exists (GR-02), so the page filters by "agreed
  on Instagram, WhatsApp or email", shows the current state per channel in the drawer and lets
  admins record consent or withdrawal with a note.
- **Web.**
  - **Contacts** is in the main nav under Engage, for every role (it was Inbox and Comments). The
    page fills the width (no fixed maximum), a list at 375 px (each row stacks) and a table-like
    grid from 768 px. Search waits 250 ms, filters sit in a panel that is a full-screen sheet on a
    phone, then a segment bar, the count, ticked rows with a Tag action, "Select all N that match"
    when a page is ticked and more exist, and Export CSV (admins).
  - **The contact drawer** is a sheet that is full screen below 768 px and 420 px wide from there.
    It edits tags (add, remove, and admins create a tag), email, phone and custom fields (one
    Save, only what changed, the API's messages beside the value it refuses), shows consent and
    the timeline. It opens from a row, and from the inbox details panel's "View contact".
  - Tags wear the identity palette colour stored on the tag (never a status colour).
- **Tests.** Unit: filter parsing and limits (`test_contact_filters.py`); integration:
  `test_contact_segments.py` (the done-when filter and export, count, field and activity filters,
  segments CRUD and limits, bulk tag by filter and its cap, the timeline and its paging, roles,
  another workspace); tenancy: the segment routes and table in `test_isolation.py`; vitest: the
  filters and edit helpers, the page, the drawer; e2e `gr17-contacts.spec.ts`.
- **Migration 0026** (down revision 0025): `contact_segments` only. Expand-only. It references
  the workspace and users, not accounts, so the account purge is unchanged (workspace deletion
  cascades).
- **Unsure / for the coordinator:** the generated client has to be regenerated for the new routes
  and models (`ContactFilterSpec`, `ContactFilterOut`, `Segment*`, `Timeline*`, `ContactCount`,
  the changed `BulkTagsUpdate`); the web types are aliases waiting for it.


## C-090 · The flow editor (GR-13, feature/gr-13-flow-editor)

- **A tree on screen, a graph in the API.** The editor works on a vertical list; a step that forks
  (quick replies, a question that can fail, a branch, a split) has indented groups of its own
  ("arms"). `lib/automations/flow.ts` turns the tree into the stored graph (`compile`) and a stored
  graph back into a tree (`decompile`).
  - A list runs top to bottom: each step's next is the step below it.
  - **An arm that runs out carries on with the step below the step that forks**, so branches meet
    again (the engine allows it, C-079). An arm that should stop ends with an End step. An empty arm
    with nothing below the fork ends the flow.
  - A quick reply is an arm whose title is edited in the arm's header. The answer typed instead of
    a tap can do nothing, copy an option, or have its own steps.
  - A question that never gets an answer that fits can carry on or end the flow.
  - Step ids are random (`s` and six letters or digits) and stay with the step across saves, so a
    run's log keeps naming the same step.
- **Reading a flow back.** `decompile` finds where the arms of a fork meet (the earliest step
  that most of them reach). A path that stops where others carry on gets a lone End, which is
  saved with the next edit. A shape the tree can't show (paths that share steps without one place
  they meet, or steps nothing leads to; only possible through the API) is shown **read-only**
  with "Start again from one message". It still runs as saved.
- **How a non-flow automation opens (decision).** Automations and templates still create settings
  automations (C-079's compiled flow); nothing about the gallery changed.
  - The Then step shows the message as the first step, in today's fields (tap first, the follow
    nudge, buttons, image), with a "More steps" card.
  - **Adding a step turns it into a flow:** the compiled flow is read, the new step goes at the
    end, and the whole thing is saved with `PUT …/flow`. Tap first and the nudge become steps.
    Public replies stay on the automation.
  - An active automation must be paused first (the empty new step would make it incomplete).
  - "Back to one message" calls `DELETE …/flow` after a confirmation; runs underway finish.
  - *Deviation from the plan's "rebuild Then on the step model": the single message keeps its
    builder until a step is added, so nothing that works today changes. A later cleanup can make
    every automation a flow (C-079).*
- **Steps.** "Add step" offers Send, Ask, Branch, Action, Delay, Split (the engine's `randomize`)
  and End. The AI reply stays the choice above the steps (a flow with one shows it as a card, and
  it must be first). Each step reuses the builder's parts: the message field with insert-field and
  the byte count, the image upload, the link buttons. A Send can also carry the profile button.
  - Ask defaults to an email saved to the contact; text goes to a custom field. *The email check
    itself is GR-14; here Ask uses what the engine does today.*
  - Branch rules cover all six conditions (tag, field, email or phone known, follows, platform,
    lead score). Actions cover the five the engine runs. Delay is minutes or hours, up to 23.
  - Tags and fields come from `GET …/tags` and `GET …/contact-fields`.
- **Reordering.** Drag the handle (pointer events, no new dependency), or press the arrow keys on
  the focused handle, or use Move up and Move down. Order changes only within a list; to move a
  step into another group, delete and add it there. A drop marker shows where a card lands.
- **Checks on each step.** Fields show their problem once a step has been edited; a step is
  "complete", "not finished" or "needs attention". The API's refusals (a refused save, a refused
  activation: `flow.steps.N.field`) are placed on steps by index. A list at the top names each step
  with a problem and "Go to step N" focuses it; a refused activation focuses the first.
- **Preview and Test.** The Preview walks the draft one branch at a time with a picker at each
  fork (a question counts as a fork: it can fail). The Test tab asks the API:
  - `AutomationTest.choices` names the way at each fork (0 where none); the result's `flow_path`
    lists the steps one run would take, with each fork's ways and the one taken
    (`services/automations/flow_preview.py`, called from `dry_run`). Picking another way tests again.
  - A settings automation has an empty `flow_path` and the old result.
- **Step cap (pending PD-5).** The plan's recommended option: every plan can branch; Free is capped.
  - New entitlement `flow_steps`: Free 5, Pro 50, Max 50 (`billing/plans.py`; a flow is at most 50
    whatever the plan, the schema's limit). Lifting the cap is one edit.
  - Every step counts, End included. "Comment, ask for an email, branch on a button, send A or B"
    is four.
  - `PUT …/flow` over the cap is 402 `quota_exceeded` (`flow_steps`, the limit, a plain sentence);
    so is **activation** of a flow saved under a bigger plan. The editor disables Add step at the
    cap, says why, and the 402 dialog has its copy.
- **API.** No new routes or tables. `AutomationTest.choices`, `AutomationTestResult.flow_path`
  (`FlowPreviewStep`), the 402 on `PUT …/flow`, and `flows.exit_labels` / `describe_condition`.
- **Unverified:** dragging on a touch screen (the handle is `touch-action: none`; the buttons and
  keys are the fallback), and the sandbox run of the e2e (`gr13-flow-editor.spec.ts`) is written
  but was not run.

## C-089 · Visual answers in Ask (GR-38, feature/gr-38-visual-answers)

Option C of `docs/architecture/generative-ui/` (accepted 2026-10-24), backlog VIS-01 to VIS-06 and
the small items VIS-X1, X3 and X4. No migration.

- **Owner's defaults kept:** visuals in Ask only, English labels, no OpenUI, the model never writes
  a number, label or layout. A question no tool with chartable data answers shows no visual.
- **Account metrics** (VIS-01): `services/analytics/account_metrics.py`, read by
  `GET /v1/w/{wid}/analytics/account-metrics` (any member) and by the agent.
  - Query: `since`, `until` (default the last 30 days), `account_id`, `metric` (repeatable),
    `compare=previous` (the period of the same length just before).
  - Metrics: reach, views, accounts_engaged, interactions, followers, follows, unfollows,
    profile_link_taps (from `account_daily_metrics`), comments and messages_received (counted from
    their tables over the workspace's local days).
  - Sums add the days that have a reading and say how many (`days_known` of `days_total`). A gap is
    never a zero. With no reading the value is null and `unavailable` says why:
    `insights_not_granted`, `no_readings` or `no_account`.
  - Followers is the latest reading in the period, per account, then added. Not a sum.
  - The change is `(current - previous) / previous x 100`, one decimal, worked out in the service.
    Null against a previous 0 (the direction is still up or down) or an unknown side. Flat under
    0.5%.
  - *Reach, views and the other insight metrics are daily values added up, so a person reached on
    two days counts twice. Instagram has no period total for these in the data we store. The
    caveats and the web say so.*
- **Same days, not same labels:**
  - Today has no row (it is written the next morning), so the agent's periods stop yesterday and a
    caveat says so. "This month" on 23 October is 1-22 October.
  - A period still running is matched with the other one over the same number of days, cut from
    its start: 1-22 October against 1-22 September. The note says how.
  - Two finished periods of different length are `comparable: false`: totals are given, no change.
  - *The doc 05 design had one comparable-days rule; this is that rule plus the "today" cut, which
    the doc didn't foresee.*
- **Tools** (VIS-02), both read, any member:
  - `compare_periods(range, compare_to, metrics, account)`; without `compare_to` the period just
    before. The tool description says it is the only tool that compares periods.
  - `metric_trend(metric, range, account)`: a point a day up to 31 days, then a week. It returns
    first, last, lowest and highest points and the change between first and last. *It builds no
    visual yet: the trend chart is VIS-07.*
  - Prompt `agent.v3`: points the model to `compare_periods`; with visuals on, says the screen shows
    the figures so the answer needn't repeat them. Off, the prompt text is v2's apart from the
    comparison line. *The eval was not run (no key here), so v3's rate against v2's is unmeasured.*
- **Visuals** (VIS-03): `Visual` is a closed union in `schemas/agent.py`: `metric_comparison`,
  `ranked_posts`, `sentiment_summary`. Pure builders in `agent/visuals.py`.
  - Caps in the types: 8 metrics, 10 posts, 6 topics, strings clipped, a thumbnail an https URL
    under 400 characters. Each visual at most 8 KB serialised (a test builds the worst cases).
  - A build that fails or is too big drops only the visual (log `agent_visual_failed`, counter).
  - *Shapes differ from doc 05 where a simpler one did the job: a `MetricDelta` is one flat card
    (`current`, `previous`, `change_pct`, `tone`, coverage, `unavailable`) instead of two
    `MetricValue`s; there is no `account_ref` (a label instead) and no `TrendVisual` or
    `LeadListVisual` yet.*
  - `top_posts`, `sentiment_distribution`, `comment_topics` and `compare_periods` carry the visual.
    `comment_topics` runs the distribution too (one more query, only with visuals on and no
    sentiment filter) and returns it as `split`, so the numbers on screen are ones a tool returned.
  - Built only with `AGENT_VISUALS_ENABLED` on; nothing is stored with it off.
- **The run** (VIS-04): `AgentRun.visuals`, from the succeeded steps' `visual`, in step order, at most
  3, each re-checked against the current models on read (an invalid one is dropped and counted).
  - A second sentiment summary of the same scope replaces the first (it has the topics); an
    identical visual shows once.
  - `agent/report.model_view` removes `visual` from what the model reads (also on a resumed run).
    `step.result` in the run detail drops it too, so the payload isn't doubled.
  - The list endpoint includes visuals (at most 3 x 8 KB a run, 20 runs a page). *Doc 05 left list
    vs detail open; the thread view draws from the list, so it is in.* If the page weight bites,
    cap or omit it there.
- **The flag:** *a server setting `AGENT_VISUALS_ENABLED` (default off), not a per-workspace flag:
  the app has no feature-flag table, and one would need a migration. Off: `visuals` is `[]`, tools
  build none, the prompt doesn't mention them. Per-workspace rollout can come with a real flags
  table.*
- **Web** (VIS-05): `VisualView` (error boundary, Sentry tag `visual_kind`) in `RunView`'s finished
  state, between the answer with its sources and the action cards.
  - `MetricComparison` from `MetricTile`s in a container-query grid; `RankedPosts` from `Table` and
    `PostThumb`, rows link to the post; `SentimentSummary` from `SentimentBar` and its legend.
  - Customer text is text; a picture must be https; an unknown kind draws nothing.
  - One series colour is not needed yet (no chart); the rule is in DESIGN_SYSTEM 1.8.
- **Observability** (VIS-X3): log `agent_visual` (kind, bytes, build_ms), counter
  `socialhood_agent_visuals_total{kind,outcome}` with built, dropped and dropped_stored. Web render
  errors go to Sentry. A web-side counter isn't added.
- **Tests:**
  - Unit: the arithmetic and gaps, the builders and size, the projection, the prompt.
  - Integration (written, not run): the route, the tools on seeded days, the run API with the flag
    on and off, roles and other workspaces.
  - Web (written, not run): states, malicious text, the boundary and unknown kinds, the panel.
  - E2E `gr38-visual-answers.spec.ts`: the fake model calls no tools, so a seed route in the e2e API
    (`POST /__e2e/workspaces/{wid}/agent-runs`) stores a finished run whose step holds the visual
    the real service and builder make from seeded days. The launcher sets
    `AGENT_VISUALS_ENABLED=true`.
  - Eval: 9 cases (`period-compare-*`, `trend-reach-30`, `visual-*`) over a seeded `account_daily`
    series with two gap days; each visual's figures must be ones a tool returned and, where the case
    computes them from the seed, the right ones. A concept question must show none. New target:
    `visuals` 100%.
- **Checked centrally:** `apps/api/openapi.json` and `packages/api-client` (the account-metrics
  route, `AgentRun.visuals`, `Visual` and its parts, `AccountMetrics` and friends), typecheck,
  build, the integration and tenancy suites, the web tests.
- **Left for later:** VIS-07 onwards (trend chart, lead list, table, progressive visuals, range
  controls, the report page), the OpenUI spike VIS-14, VIS-X2 (quote account names in the prompt),
  localised labels.

## C-092 · Leads (GR-18, feature/gr-18-leads)

A lead is a contact. This adds a stage to the contact, the rules that move it, a gone-cold job and a
Leads view on top of GR-17's contacts list. (The coordinator renumbers this entry if another branch
took C-092.)

- **Where the stage lives.** *The roadmap (P2) put the stage on the conversation; the plan (GR-18)
  puts it on the contact, with the conversation linking to it. Decided: the contact, as the plan
  says.* A person who wrote in twice on one account still has one conversation (PD-10), and a
  commenter with no conversation can be a lead too. Cards link to the conversation when there is one.
  - Stages: `new`, `qualified`, `follow_up`, `won`, `lost`. New, qualified and follow up are open.
  - *Not built from the roadmap: the optional lead value, and a backfill of `new` for conversations
    with a score of 60 or more.* Every existing contact starts `new`, and the first analysis that
    reaches the bar qualifies it. The migration rewrites nothing.
- **Migration 0027** (down revision 0026), expand-only: `contacts.lead_stage` (default `new`),
  `lead_stage_at`, `lead_stage_reason`, `lead_cold_at`, an index on (workspace, stage); the table
  `lead_stage_changes`; `workspaces.lead_cold_days` (default 7, 1 to 90).
- **History (`lead_stage_changes`, append only).** From, to, who or what moved it (`actor_kind`:
  member, automation, rule, system), the member, the rule name (`lead_score`, `intent`,
  `email_captured`, `gone_cold`) and a reason of up to 300 characters. It references the contact,
  so an account purge removes it with the contact (the purge test snapshot lists it). Moving to the
  stage a lead is already in records nothing.
- **Rules (`services/leads.py`).**
  - *A member* moves a lead to any stage at any time, with an optional note (any role, like tagging).
    `POST /contacts/{id}/lead-stage`.
  - *Automatic qualification* only ever moves a lead out of `new`, so a lead a member or an earlier
    rule moved on is never pulled back. After each stored analysis: a lead score of 60 or more (the
    inbox's Leads line), or a buying intent (pricing, purchase) with a score of 40 or more.
    *Decided: 60, and 40 for a buying intent; both are constants, not settings.* The intent is the
    member's correction when there is one.
  - *A captured email qualifies* a new lead: `leads.on_capture(session, contact, kind)`, called by
    the flow engine's question step today. **GR-14 calls the same function** when its lead capture
    saves an email (`kind="email"`). A phone or a custom field does not qualify. An email a member
    types into the drawer does not either: it is their own note, not a signal from the customer.
  - *Gone cold* (`mark_cold_leads`, hourly at :10, bulk lane): a qualified or follow-up lead whose
    customer has not written for the workspace's `lead_cold_days`, counted from their last message
    or from the last stage change, whichever is later (so a lead a member just moved is not cold at
    once). A qualified lead moves to follow up (rule `gone_cold`); a follow-up lead stays. Both get
    `lead_cold_at`, and every member gets an in-app `lead_cold` notification with a link to the
    conversation. *The plan says "notify the assignee"; there is no assignee until GR-20, so it is
    every member for now.* A lead is cold while the flag is later than its last customer message, so
    a new message ends it with no write, and any stage change clears it. It is idempotent (a flagged
    lead is not selected again until it has written and gone quiet again), workspace-scoped (each
    workspace's own days; rows locked with `FOR UPDATE SKIP LOCKED`), and RETRY in `RECOVERY`.
  - *Won and lost* are never touched by a rule. Cold only looks at qualified and follow up.
- **Setting.** `GET` and `PATCH /leads/settings` (`cold_after_days`, 1 to 90; admins change it).
  *The plan asks for "N days (a workspace setting)" with no owner decision, so 7 is the default
  and the Leads page offers 3, 5, 7, 14, 30 and 60 to admins.*
- **API.** `GET /leads/summary` (any member): contacts per stage, open leads gone cold, and the last
  8 weeks of leads that reached qualified and won (each contact once per week and stage, weeks start
  on Monday UTC). *This is the roadmap's "conversion counts by week".* The lead list is
  `GET /contacts?stage=` (repeat for any of them), the same filter everywhere: the list, count,
  export, saved segments (`stages`) and bulk tagging. The contact list item and record gain
  `lead_stage`, `lead_stage_at`, `lead_stage_reason` and `lead_cold`.
- **History in the drawer.** A new timeline source in `services/contact_timeline.py`: "Lead stage:
  Qualified", detail "From New. By Priya. Asked for a quote." (or "Automatically." for a rule).
- **Flow condition.** `lead_stage` in the GR-03 branch conditions: `{"kind": "lead_stage",
  "stages": ["qualified", "follow_up"]}` holds when the contact is in any of them, read when the step
  runs. It needs no activation check. *The web has no list of condition options (the editor is
  GR-13's), so `AutomationEditor` is untouched; GR-13 offers the new kind next to the others.*
- **Event.** `lead.stage_changed` (version 1) in GR-04's catalogue, so the catalogue has nine events.
  The payload has the contact, `from`, `to`, `changed_by` (`kind`, `user_id`, `rule`) and `reason`.
  It is emitted by every real move.
- **Web.**
  - **Leads** is in the main nav under Engage, for every role. From 1024 px it is a board with a
    column per stage; below that it is one stage at a time with a row of stage buttons above it, so
    it works at 375 px. Each column is the contacts list filtered to its stage, so search and the
    filter sheet are GR-17's (the sheet leaves the stage control out here; on Contacts it is a
    "Lead stage" group, and each row wears its stage). A card shows the name, score, last activity,
    why the lead is where it is, a "Gone cold" chip, up to three tags, a stage control and a link to
    the conversation. Admins get "Gone cold after N days" in the page header.
  - **The contact drawer** has a Lead stage section first (stage, since when, why, a control to move
    it with an optional note); the history is in its timeline. It also opens from the inbox's
    details panel.
  - *Left for later:* a lead stage chip in the conversation header (the roadmap's step 5) and the
    Ask tool `list_leads` (step 6). The drawer is one click from the details panel.
- **Tests.** Unit: `test_leads.py` (stages, qualification rules, cold flag, history wording, request
  limits, filter, flow condition, event, recovery class). Integration: `test_leads.py` (move, no-op,
  roles, 404, history in the timeline, filter and count, segments, summary, setting, event),
  `test_lead_rules.py` (analysis qualifies, buying intent, never pulls back, the cold job: selection,
  idempotence, per-workspace days, a recent move), `test_lead_flow.py` (the branch, a captured email
  qualifies once and fires the event, a phone does not). Tenancy: the new routes, body and table in
  `test_isolation.py`; the account purge snapshot and seed. Vitest: the Leads page, the drawer's
  stage section, the contacts page's stage badge and filter, `filters.test.ts`, the nav. E2E:
  `gr18-leads.spec.ts`.
- **Unsure / for the coordinator:** regenerate the client (`LeadStageUpdate`, `LeadSummary`,
  `LeadStageCount`, `LeadWeek`, `LeadSettings`, `LeadSettingsPatch`, the new fields on
  `ContactListItem` and `ContactRecord`, `stages` on the filter models, `lead_stage` in
  `TimelineKind`, `lead.stage_changed` in the event names); the web types are aliases waiting for it.
  The hand-written web fixtures for the contact list item and record carry the new fields.

## C-093 · Saved replies (GR-21, feature/gr-21-22-replies-hours)

- **A table of snippets.** `saved_replies`: title (1 to 60), shortcut, body (1 to 1,000 characters,
  the length of an Instagram DM). The shortcut is lower case letters, digits, `-` and `_` (up to 30),
  unique per workspace; a typed `/Price` is stored and found as `price`. A workspace keeps up to 200.
- **Who:** any member reads and uses them (agents work the inbox); owners and admins create, change
  and delete (the plan said "agents read and use; admins and owners manage").
- **API:** `GET/POST /saved-replies`, `PATCH/DELETE /saved-replies/{id}`, and `POST
  /saved-replies/{id}/fill` with a `conversation_id`, which gives the text filled for that
  conversation's contact. A duplicate shortcut is 409 `conflict`; a bad one is 422 on `shortcut`.
  Another workspace's reply or conversation is 404.
- **One filler, three users** (`services/saved_replies.fill`): the composer's fill route, a flow's send
  step and the GR-22 away message all read a body the same way.
  - Variables: `{first_name}`, `{name}`, `{username}`, `{email}`, `{phone}` and the key of any custom
    field (`{city}`). `{first_name|there}` names a fallback, as in automations.
  - A field with no value, or one that does not exist, is empty; no `{braces}` are left. `{first_name}`
    with no name falls back to "there", as automations do. A custom field cannot shadow a built-in.
  - *Deviation from "reuse any existing template-variable code":* `automations/render` only knows
    `first_name` and `username` and a 40-character fallback; the saved-reply filler reuses its
    `first_name_of` and fallback word and adds the other fields, rather than widening what every
    automation message can say.
- **Composer:** typing `/` after the start of the draft, a line or a space opens a listbox of matching
  replies (exact shortcut first, then shortcuts that start with it, then title or shortcut contains);
  arrow keys move, Enter or Tab or a click inserts the filled reply in place of the `/word`, Esc
  closes. Nothing opens for a slash inside a link or a word. The list is fetched only once a slash is
  typed. *Deviation: a new inline `SavedReplyPicker` rather than extending the `TemplatePicker` dialog
  (that one is a dialog for WhatsApp templates with variables; a `/` picker has to stay under the
  caret).*
- **In flows:** a `send` step may name a saved reply (`saved_reply_id`). The step reads the reply's
  current body when it runs and fills it for the contact (so an edit reaches flows already saved), with
  the disclosure line.
  - A saved-reply step goes alone: no image, buttons or quick replies (activation error).
  - A comment flow cannot start with one (the first message is the private reply, built before the
    run); it can use one later.
  - A reply deleted after activation fails the step: the run ends with the code `saved_reply_missing`
    and the reason "The saved reply this step sends was deleted. Choose another." Activity shows it
    with "Edit the automation". A flow naming a deleted reply cannot be activated.
  - **For the flow editor (GR-13):** the `send` step option is `saved_reply_id` (a uuid) instead of
    `text`; the editor needs a picker of `GET /saved-replies` and should hide text, image, buttons and
    quick replies while it is set. The server schema and runtime are done; no editor UI was touched.
- **Web:** Settings has a "Saved replies" tab (everyone sees it; owners and admins get the add, edit
  and delete controls).
- **Migration 0028** (shared with C-094; parent 0025 until re-chained): `saved_replies` and
  `uq_saved_replies_workspace_id_shortcut`.

## C-094 · Business hours and away messages (GR-22, feature/gr-21-22-replies-hours)

- **Where the hours live.** `business_hours`: one row for the workspace (`social_account_id` null)
  and optionally one per account that replaces it. Each has `enabled`, the weekly `schedule`, the away
  message (`away_enabled`, `away_message`) and `auto_mode`. An account row with `enabled` off means
  "this account has no hours", so it is always open. No row, or a row that is off, means always open:
  nothing changes for anyone who does not set hours.
- **The week:** Monday is 0. Each day has any number of ranges ("09:00" to "17:00"; the closing time may
  be "24:00"); a day with none is closed. Times are wall-clock in the workspace time zone
  (`workspaces.timezone`), so 09:00 stays 09:00 across a daylight saving change. A range includes its
  start and not its end. Ranges cannot overlap on a day (touching is fine) or cross midnight (open
  until 02:00 is 18:00 to 24:00, then 00:00 to 02:00 the next day, and the two count as one stretch).
  Hours switched on need at least one range.
- **`is_open(hours, at)`** is pure and unit-tested at the edges: the opening minute, the closing
  minute, midnight, a zone ahead of UTC, daylight saving. `closed_since(hours, at)` is when the current
  closed window began (touching ranges merged), used for the once-per-window rule.
- **Order (decision, as recommended):** a waiting answer (flow question, tap first) goes first, then
  automations (keyword and any-reply, then the welcome and default reply of C-088), then the away
  message if none answered, then nothing else.
  - "None answered" is a DM with no match, or one whose matches were all skipped (cooldown, scope).
  - Never on a story mention, a story like, a button, quick reply or conversation starter tap, or a
    comment.
  - **Auto mode and the away message (decision, easy to change):** a conversation whose effective AI
    mode is Auto (and not paused for a takeover) gets no away message, because the AI answers or
    escalates it; any other mode gets it. The message does not mark the customer's message handled, so
    suggestions for a person still appear.
- **Once per closed window:** `conversations.away_sent_at` is compared with `closed_since`: sent when
  it is empty or older than the window's start. A second message the same night, or the next morning
  before opening, gets nothing; the next night is a new window. The send uses a client id made from the
  customer's message, so a retried job sends nothing twice, and the conversation is locked while it is
  checked.
- **Auto mode's hours (`auto_mode`):** `always` is today's behaviour. `out_of_hours` makes check 1 of
  the auto-reply policy fail (`skipped`, `mode_not_auto`, value "auto, open hours") while the account
  is open, so the suggestion waits for a person. *Kept in the existing check, not a 14th check, so
  the 13 checks and every stored decision keep their numbers.* The setting is on the hours row (the
  workspace's, or the account's own), not on the account's AI mode.
- **Automations:** `automations.hours_condition` is `inside`, `outside` or null. An automation whose
  condition does not hold passes over the message or comment, like a scope mismatch. It works for
  message-settings automations and flows (it is checked before either runs) and for comment
  triggers. An account with no hours is always inside, so an `outside` automation never runs there.
  Web: a three-way control in the existing Settings step ("Any time", "Inside business hours",
  "Outside business hours"), and the settings summary says it.
- **API:** `GET /business-hours` (workspace schedule, time zone, each account's override, `open_now`),
  `PUT /business-hours` (owners and admins), `PUT` and `DELETE /social-accounts/{id}/business-hours`
  (an account's own schedule; delete returns it to the workspace's). 422 names the field
  (`days.2.ranges.1.start`, `away_message`, `days`). Agents read.
- **Ingest:** a new DM wakes the automation runtime when an away message could apply, even if the
  account has no active automation (`business_hours.away_possible`).
- **Web:** Settings has a "Business hours" tab: a switch, a week of ranges (add, remove, several per
  day), the away message and Auto mode's hours; one card per account with "Set its own hours" and "Use
  the workspace hours". A time input cannot show 24:00, so a closing time of 00:00 is saved as
  midnight. The rows wrap at 375 px.
- **Migration 0028:** `business_hours` (with `uq_business_hours_workspace_id_social_account_id` and a
  partial unique index for the workspace's own row), `conversations.away_sent_at`,
  `automations.hours_condition`. Expand-only; the account purge and workspace deletion pick the table
  up from the schema.
- **Not built:** holidays or one-off closures, an away message per language, and an away message for
  comments (a public comment is not a conversation). All fit the same table later.

## C-095 · Data capture and consent (GR-14, feature/gr-14-15-capture-clicks)
GR-03's Ask step already checked an email or phone, retried, skipped and raised `lead.captured`
(C-079, C-080). GR-14 finishes it: the free-text cap, the consent question, a confirmation, default
copy and the editor's options. No migration, no new route.
- **Answers** (`services/automations/capture.py`):
  - An email is trimmed and lower-cased whole (GR-02's rule). A phone is E.164, a ten-digit Indian
    mobile taken as +91. *The `phonenumbers` library is not a dependency, so the small normaliser
    stays (+country code of 8 to 15 digits, Indian mobiles); other national formats without a
    country code are asked again. Adding the library later is a one-function change.*
  - Free text is trimmed and capped at 500 characters (the custom field text cap). Over the cap
    counts as an answer that doesn't fit.
- **Retry and skip (decision).** An answer that doesn't fit gets the step's retry prompt, or the
  default copy for its kind, until `tries` run out: 1 to 3, default 2. Then the flow goes to the
  step's `on_skip`. The editor's default is **carry on** to the step below; "end the flow" is the
  other choice. Nothing is saved on a skip.
- **Saved to** the contact's email or phone (source `flow`) or a custom field, as before, and
  `lead.captured` is emitted then. *GR-18's `leads.on_capture` hook is not on this base and was not
  created: the coordinator can call it from `_take` in `engine.py` after the webhook event.*
- **Consent question (`consent` on the Ask step).** After a saved answer the step sends a Yes or
  No question with two quick replies (default copy, or the step's `consent_text`) and waits.
  - A tap, or typed words (yes, yeah, sure, haan; no, nope, no thanks), is recorded in
    `contact_consents`: Yes as granted, No as revoked (an explicit refusal). Source `flow`, purpose
    marketing, channel the conversation's (Instagram or WhatsApp).
  - **Evidence:** the answer's message id and text, the question's message id and text, the
    channel, the run, automation and step, and the time (`occurred_at`).
  - Anything else is asked once more, then the flow goes on and nothing is recorded.
  - The consent is for the channel they are chatting on. A captured email gives no email-channel
    consent. Required before WhatsApp broadcasts (GR-23): not enforced here.
- **Confirmation** (`confirm_text`): sent after the answer is saved (and the consent answered).
  Blank sends nothing; the editor suggests "Thanks, I've got it."
- **Default copy** lives in `capture.py` (retry per kind, the consent question, the "need a yes or a
  no" prompt) and is mirrored as placeholders in the Ask card. The copy lint (`copy-lint.test.ts`)
  only bans old variants; the copy follows its rules (sentence case, UK spelling).
- **Step schema:** `consent`, `consent_text`, `confirm_text` added to `AskStep`, with defaults, so
  stored flows are unchanged. Activation checks all three texts against Instagram's byte limit.
- **Editor:** the Ask card has the type, the field to save to, the retry prompt, tries, the
  confirmation and an "Ask for marketing consent" switch with its question.
- **Done when:** a captured email lands on the contact, raises the webhook and shows in the CSV
  export (`tests/integration/test_data_capture.py`; the export is GR-02's).
- **Unverified:** the integration tests, vitest and `gr14-data-capture.spec.ts` are written but were
  not run.

## C-096 · Link click tracking and flow analytics (GR-15, feature/gr-14-15-capture-clicks)
- **Tracked links.** A link button in an automation's message is sent as `{base}/l/{code}`; the
  redirect records the click and answers 302 to the original address.
  - **Which domain serves it: the API's.** `GET /l/{code}` is an API route (`webhooks/links.py`,
    public, no sign-in, not in the OpenAPI schema), built on `LINK_BASE_URL` if set, else
    `API_BASE_URL`. A short domain pointed at the API and set as `LINK_BASE_URL` shortens every
    link with no code change. With neither set, buttons are sent as written. The web app's domain
    doesn't serve it.
  - **The code** is an opaque random token (96 bits, 16 characters), mapped in `tracked_links`.
    The run, step and contact are only in our database, never in the URL. One link per run, step
    and button, so a retried send reuses it.
  - **Redirect rules:**
    - the stored address must be http or https (`links.safe_target`), else 404 and no click;
    - an unknown code is 404; the route is rate limited per IP like the other public routes (60 a
      minute);
    - the response is `no-store`, `no-referrer` and `noindex`.
  - **Bots and previews (the rule, `links.is_bot`).** Not counted, but still redirected so a preview
    shows the real page:
    - a HEAD request, or no User-Agent;
    - Meta's `facebookexternalhit` and `meta-external*` (Instagram and WhatsApp previews),
      `WhatsApp/`, Slack, Telegram, Discord, X, LinkedIn, Google, Bing, Apple and other search
      crawlers, curl, wget and common script clients;
    - anything calling itself a bot, crawler, spider, scanner or preview.
    - The in-app browsers of Instagram and Facebook are people. A second click on one link within 5
      seconds counts once (a double tap or prefetch).
    - *Unverified against real Instagram traffic; the list is one constant to extend.*
  - **Where links are made:** the flow engine's sends, the legacy settings sends (DM, tap-first
    release, and the comment queue's private reply, step `message`). The profile button ("View
    profile") is never tracked. The inbox keeps showing what was actually sent, our address.
  - **Opt-out:** `automations.track_links` (default on), a switch in Settings ("Track link
    clicks"); off sends the raw link. Left out of a save, it keeps its value; a duplicate copies it.
- **Funnel** (`GET …/automations/{id}/funnel?days=7|30|90`, admins; `services/automations/funnel.py`).
  Nothing new on the send path: it reads what is recorded.
  - Per step: reached (the step log), sent, delivered and read (the status of the step's message;
    read only where the platform reports it), failed, quick reply taps, link clicks and the people
    who clicked, answers saved by a question, answers that never fitted, and "yes" to the consent
    question. Steps come in the order a walk meets them.
  - Automations still on their message settings have no step log: their `message` step is built from
    the runs' DMs and the clicks.
  - **Split results:** per path, the runs that took it and, for the steps after it, delivered, read,
    taps, link clicks and answers. A step shared by two paths counts for each run that went through.
- **Where it shows:** the editor's Stats tab (a "By step" list and a table per Split) and the
  Settings switch. The list refreshes every 30 seconds, so a click shows within a minute. *Not on the
  Activity page: that is a feed of what failed, and a click isn't one.*
- **Migration 0029:** `tracked_links`, `link_clicks` and `automations.track_links`. Expand-only.
  Both tables hang off the automation, run and contact with cascading deletes, so an account's
  purge removes them with its automations and contacts.
- **Not done / pending:** per-quick-reply tap counts (taps are per step); a retention limit on
  `link_clicks` (kept as long as the automation); the sandbox run of `gr15-link-clicks.spec.ts`.

## C-099 · Template gallery, version 2 (GR-16, feature/gr-16-templates-v2)
Five new templates on the new triggers and steps, and a saved-reply choice in the flow editor.

### Templates that carry a flow
- **Before:** a template only filled the message settings (text, link buttons, public replies),
  so it could not make a question or a quick reply. *Deviation from the plan, which only said to
  add templates: a template may now carry a flow, minimally.*
  - `Template.flow` is an optional `FlowDefinition` (`services/automations/templates.py`).
  - `definitions.create` saves it as version 1 in `automation_flows` and sets `flow_version`, so
    the draft opens as a flow (`flow_source: flow`) and the settings are not used. No migration.
  - Everything else (trigger, keywords, public replies, post scope) fills as before.
  - The older templates stay single messages and compile from their settings.
- **The gallery:** `AutomationTemplate.steps` is the number of steps a template starts with (0 for
  a single message). The card shows "2 steps" next to its trigger and action.
- **The five** (category, trigger, steps):
  - *Story giveaway* (grow, story mention, 2): thanks them and says they are in the draw, then
    when winners are announced.
  - *Lead magnet* (grow, comment keyword GUIDE, 2): the private reply asks for their email (saved
    to the contact), then sends the PDF with a link button. Public replies are on.
  - *Price by option* (sell, comment keyword PRICE, 4): the private reply has quick replies for
    Small, Medium and Large, each leading to its own price message.
  - *Call requests* (sell, DM keyword CALL, 2): asks for a phone number (saved to the contact,
    with a thank-you), then "Notify the team". *No new action was needed: `notify_team` already
    exists (C-079).*
  - *Coupon from a link* (sell, entry link, 1): sends the code with a link button. Entry links
    (GR-08) are made on their own page.
- **Names:** the older *Giveaway replies* and *Book a call* stay (comment-on-a-post giveaway and a
  booking link by DM). The new ones have their own keys (`story_giveaway`, `lead_magnet`,
  `price_by_option`, `call_request`, `entry_link_coupon`). The plan's "price please" is named
  *Price by option*: no "please" in our copy.
- **Placeholders and activation:**
  - The link is left as `https://`, so activation asks for it, as for the other templates.
  - Prices and the code are written as `[price]` and `[code]` in the message. *The activation
    rules cannot tell that a bracket is unfilled, so they do not stop activation; the copy makes
    it plain. A later check could flag square brackets.*
  - Questions are an email or a phone answer saved to the contact, so no custom field has to exist.
  - Tap first is off for these: a flow's first message is the opening itself.
- **PD-5 (pending):** every template fits the Free plan's cap of 5 steps (the largest has 4); a
  unit test reads the `flow_steps` entitlement, so it follows the decision.
- **Ask Social Hood:** `prepare_automation` no longer reports "the message" missing for a template
  that carries a flow. The tool still prefills the settings only; the draft it opens is the
  template's.
- **Tests:** `tests/unit/test_template_flows.py` (each flow validates, builds, needs only its link,
  stays in the cap, has plain copy), `tests/integration/test_template_flows_api.py` (each creates a
  flow draft that activates once filled, on Free and Pro), the gallery snapshot tests, vitest for
  the card, and `apps/web/e2e/gr16-templates-v2.spec.ts`.
- **Needs checking centrally:** `apps/api/openapi.json` and `packages/api-client` for
  `AutomationTemplate.steps`.

### The saved-reply step in the flow editor (from GR-21, C-093)
- A Send step has a choice, "Write a message" or "Send a saved reply".
  - Choosing a saved reply shows a picker over `GET /saved-replies` (titles, with the body below)
    and a link to Settings, Saved replies. The text, image, buttons and quick replies are hidden.
  - Switching to a saved reply drops the image and link buttons the message had. It is disabled
    while the message has quick replies, which would orphan their branches.
  - Switching back keeps the (now empty) text; nothing is stored for the reply.
- **Editor model:** `SendNode.saved` and `saved_reply_id`, both optional. `compile` writes a send
  with `saved_reply_id` and no text; `decompile` reads it back. A chosen source with no reply
  picked yet saves as an empty send, so it opens as "Write a message" after a reload; the step
  check still says "Choose a saved reply" while it is chosen.
- **Checks per step:** a reply must be chosen; a deleted reply is flagged; and not on a comment
  flow's first step (the API's rule, `flow.start`, now shown on the step). The API still checks
  the reply's length and "alone" on activation.
- **Preview path:** the step shows "Saved reply: <title>" instead of the text, and is titled
  "Saved reply".

## C-097 · Trends and a weekly report (GR-34, feature/gr-34-trends-report)

Roadmap P3. No migration.

- **One service, three readers.** `services/reports.py` builds the report; the report page, the
  digest email and the Home link all read it. Every number comes from `overview_stats` (Home and the
  digest) or from GR-38's account metrics. No model writes, rounds or ranks a figure.
- **Finished weeks only.** A week is Monday to Sunday in the workspace's zone and can be asked for
  once Sunday is over; every comparison is seven days against seven (DST makes a span an hour longer
  or shorter, as everywhere else). The latest week is the one before the current Monday. *Decided: no
  "this week so far". A part-week against a whole one would mislead, and GR-38's rule for a running
  period (cut the other one to the same days) would make the report's numbers differ from the
  digest's.*
- **Digest extended, not replaced.** `OverviewStats` gains story mentions, conversations from ads and
  from links, and leads qualified and won (`lead_stage_changes`, each contact once per stage). Home
  reads the first three from the same object, so the overview and the digest still agree (the test in
  `test_overview.py` now compares them, with a link conversation seeded). Home's period has no
  leads fields yet. `weekly_digests.stats` and the email's data also carry `trends` (each metric's
  week, week before and change) and `account` (reach, views, accounts engaged, interactions,
  followers, follows, unfollows, with days covered and the reason when missing). Old rows lack both
  and the template leaves the sections out.
- **Email.** Two new tables ("Against the week before", "Your Instagram account") and the button
  "See the full report" to `/w/{slug}/reports?week={Monday}`. *The old "Open Social Hood" button is
  gone; the text version still lists Home and the inbox.* Copy: "Up 18.3% on the week before (was
  120)", "Down 2.6 points ...", "Up from 0 the week before", "No data for the week before",
  "Counts 5 of 7 days".
- **Trends.** Week against the week before, and 8 weeks ending with it (oldest first). The change is
  GR-38's `change` (percent, one decimal, flat under 0.5%, a direction but no percent against 0). *A
  rate (reply rate, handled by AI) changes in percentage points, not percent of a percent.* A faster
  median first response is good news (`lower_is_better`).
- **Gaps, the same as GR-38.** A rate with nothing to divide is null. A week that ended before the
  workspace was created *and has nothing recorded* is null for every count (a workspace's earlier
  weeks aren't zeros); if rows exist (an import) the real numbers show. Account figures sum the days
  that have a reading and say how many; none gives null and the reason; followers is the latest
  reading. The report week's account figures lack Sunday if the daily job hasn't written it yet (the
  digest at 09:00 Monday often will): shown as "Counts 6 of 7 days", not as a drop.
- **Account metrics in the digest job** need the platform capabilities (insights granted or not):
  the task passes the real ones. Callers without adapters (tests) assume insights are granted, so a
  missing reading reads "no readings", not "not allowed".
- **Route.** `GET /v1/w/{wid}/reports/weekly?week=YYYY-MM-DD` (any member). `week` is a Monday that
  has finished, at most 52 weeks back; anything else is 422 on `week`. Without it, the latest week.
  The response has the week, the week before, the picker's 12 Mondays (newest first), each metric
  with its series, the account metrics (figure plus series), `account_comparison` (a GR-38
  `MetricComparisonVisual` built by the same builder, so tone, gap wording and day coverage match
  Ask), top intents, top posts, "Open right now" counts and `notes`.
- **Captures (GR-14) are not in the report.** Nothing counts them on this base; `notes` carries
  `captures_not_built` and the page says so in one line. The slot is one more `MetricDef` once a
  source exists (and a line in the digest follows from it).
- **Page** `/w/{slug}/reports?week=`: tiles (`MetricTile`) with the change and a hand-built SVG
  line under each (`SeriesChart`: one series colour `chart-series-1`, scale from 0, or 0 to 100 for
  a share, a gap breaks the line and is counted under the chart, a dot on the latest week, the
  picture labelled with every value in words). The account part is Ask's `MetricComparison` plus a
  small chart per metric. Week picker: a select of the 12 weeks and Earlier/Later buttons; the week
  is in the address. One column to 639 px, two from 640, three from 1280, no sideways scroll at 375.
- **"Shareable".** *Decided: a stable address for members of the workspace. There is no public link
  and no unsigned URL; someone outside the workspace gets the usual 404 from the API and the app's
  sign-in. A public or expiring link would be a new surface and an owner's call.*
- **Where it is linked.** The digest email, and a "Weekly report" button in Home's header. *Not in
  the main nav (the sidebar lists are snapshotted and the report is a weekly read, not a daily
  tool).* Not yet from Ask answers (VIS-13's "linked from answers"): that needs the agent session's
  code, which is another branch's.
- **Left from roadmap P3:** notable-change detection with thresholds (step 2), Home's "This week"
  strip (step 3), the Ask `get_trends` tool (step 5), and trends for sentiment share, top topics and
  post engagement at equal age (step 1 lists them). This task did the counts, rates, leads and
  account figures the plan names. The series is 8 weeks; `SERIES_WEEKS` is a constant.
- **Tests.** Unit: `test_reports.py` (week maths, DST, the 422 rules, changes in percent and points,
  gaps stay gaps, the digest extras, the comparison reuse), `test_email_templates.py` (the new
  tables and link, an old digest without them). Integration (written, not run): `test_weekly_report.py`
  (the digest and the report give the same numbers, the week before and the series, weeks before the
  workspace are gaps, story mentions/links/ads/leads in their week, account days and gaps, insights
  not granted, no account, the route, 422s, roles, other workspaces and zones),
  `test_weekly_digest.py` and `test_overview.py` updated. Vitest: `format.test.ts`,
  `SeriesChart.test.tsx`, `WeeklyReportPage.test.tsx`, the Home link. E2E:
  `gr34-weekly-report.spec.ts` (a finished week can't be seeded through the API, so it checks the
  page against the API for the same week).
- **For the coordinator:** regenerate the client (`get_weekly_report`, `WeeklyReport`, `ReportMetric`,
  `ReportAccountMetric`, `ReportPoint`, `ReportIntent`, `ReportQuestion`, `ReportPost`); the web types
  are aliases waiting for it. `test_isolation.py` needed nothing (no table, no path id). The route's
  `week` parameter is a plain date. Nothing was added to the tenancy or purge lists.

## C-098 · Website crawl into knowledge (GR-35, feature/gr-35-site-crawl)

A whole website becomes knowledge: a crawl from a start address, a weekly re-crawl that only
re-reads what changed, and each page listed under its site. It builds on the single-page web source
(T5.3) and reuses its fetch, its extractor and its ingest job.

- **A site is a source; each page is a source.** *The plan says "per-page sources in the knowledge
  list". Decided: a new type `site` (the address, the settings) whose crawled pages are sources of
  type `page` with `parent_source_id` pointing at it.* So the existing pipeline does the rest: the
  same `ingest_knowledge_source` job chunks and embeds a page, retrieval and the test box find it,
  `knowledge_characters` counts it, and deleting a site deletes its pages and chunks (ON DELETE
  CASCADE). Pages are not in the main list (`GET /knowledge-sources` leaves out anything with a
  parent) and cannot be reached as sources (404 on get, edit and delete); they live under
  `…/pages`. A page's text is stored in its source's `body` (at most 20,000 characters, the column's
  limit), and ingestion of a `page` takes it from there instead of fetching again, so the crawl is
  the only thing that touches the site.
- **Migration 0030** (after 0029), expand-only: the `type` check widened to `site` and
  `page`; `knowledge_sources.parent_source_id`; the tables `site_crawls` (one row per site: re-crawl
  setting, excluded paths, status, whether it is seeded, whether it hit the cap, the cap of that
  crawl, error, start and finish times, `next_crawl_at`) and `site_pages` (one row per address:
  status, depth, order found, title, content hash, ETag, Last-Modified, last crawled, and the page's
  source). `uq_site_pages_site_source_id_url`. Both tables are workspace-level, so an account purge
  leaves them (the purge test's kept list names them) and they are in the tenancy test's table list.
- **The crawl (`services/knowledge/crawl.py`, rules in `crawl_rules.py`).**
  - *Order.* robots.txt of the start address's site, then the sitemap addresses (the `Sitemap:`
    lines and `/sitemap.xml`; a sitemap index is followed; at most 20 files), then the start page,
    then breadth first: the shallowest queued page, then in the order found. One page at a time,
    1 s apart, or the site's `Crawl-delay` up to 10 s.
  - *What counts as the same site.* The same host, ignoring a leading `www.`; other hosts and
    sub-domains are other sites and are not followed. *The plan says "same registrable host". There
    is no public-suffix list in the stack and guessing one risks following a different business, so
    this is the stricter rule.* A redirect that ends on another site is skipped.
  - *Addresses.* Fragments, **all query strings**, default ports, a trailing slash and double slashes
    are dropped, and the host is lowercased. *The plan says "query-duplicates". Dropping the query
    is the simple rule that cannot fall into sort-order, filter and tracking-parameter traps; the
    cost is that a site whose pages differ only by `?id=` is read as one page.* Links to files that
    aren't pages (PDF, images, scripts, documents) are not followed; `rel="nofollow"` links and
    pages with a robots meta of `nofollow` are not followed; `noindex` pages are skipped and not
    stored. Depth is capped at 6 links from the start page.
  - *robots.txt.* Our group (`SocialHoodBot`) wins over `*`; the longest matching rule decides and
    Allow wins a tie; `*` and a closing `$` work. A missing file (any 4xx) allows everything; one
    that errors (5xx, timeout) or can't be reached fails the crawl with a message, as does a site
    whose robots.txt disallows the start page. *The crawl never reads a page robots.txt disallows,
    including pages found in a sitemap.*
  - *Limits.* Pages 2 MB and 15 s (the single-page fetch's), robots.txt 512 KB, a sitemap file
    5 MB, text kept per page 20,000 characters. A failed page is tried twice, then marked failed;
    the crawl goes on. The sitemap is read by pattern, not by an XML parser (nothing to expand).
- **Plan cap.** New entitlement `crawl_pages`: **Free 25, Pro 250, Max 1,000** pages for one site.
  *Proposed values, pending the owner's plan decisions (one line in `billing/plans.py`; the same
  note as `contact_fields`).* The cap is taken when a crawl is requested and stored on the crawl
  (`page_cap`); pages found past it are left out and the site says "Stopped at N pages". Pages the
  owner removed or excluded do not count; `knowledge_characters` still applies on top.
- **SSRF.** `security/ssrf.py` gains `fetch_document` (`fetch_html` is now a call to it): the same
  rules (address checks with DNS, the connection pinned to the checked address, redirects by hand and
  checked, size and time limits) for other content types, extra request headers and a 304 answer.
  *Every address the crawl touches goes through it: the start page, robots.txt, each sitemap file
  (including ones robots.txt names on another host), each page, each redirect.* A start address that
  is a private literal is refused when adding (422 on `url`); one that resolves to a private
  address fails the crawl with the usual message. Links and sitemap entries to other hosts are
  filtered out before they are ever requested. `FetchError` gains `status`.
  **`CRAWL_ALLOW_PRIVATE`** (default off, refused in production like `WEBHOOKS_ALLOW_PRIVATE`; on in
  `.env.example` and the e2e stack) lets development and e2e crawl a local fixture site.
- **Jobs.** `crawl_site(id, version)` (bulk lane, queueing lock `crawl:{id}:{version}`, run lock
  `crawl:{id}`, 3 tries, RETRY in `RECOVERY`) and `dispatch_site_recrawls` (hourly at :20, RETRY).
  - *One crawl at a time.* The site source's `version` numbers its crawls; asking for a crawl while
    one is queued or running changes nothing. A job for an older number, a finished crawl or a
    deleted site stops ("stale").
  - *Resumable and idempotent.* The queue is the `site_pages` rows, so a job that dies carries on
    where it stopped (a stalled one is re-run by recovery). A job reads pages for four minutes, then
    queues itself again for the rest, so no crawl holds a worker for long. A page is committed with
    its result in one transaction, and a page the owner removed meanwhile is left alone. The seed
    runs once per crawl.
  - *Re-crawl.* `dispatch_site_recrawls` starts a crawl for each weekly site whose `next_crawl_at`
    has come (50 at a time, workspace-scoped), and queues again a crawl that has not moved for 30
    minutes (a lost job). The setting is `weekly` (default) or `off`; `next_crawl_at` is a week after
    the last crawl finished. *The plan says "e.g. weekly, per source setting"; weekly and off are
    the two settings.*
  - *Change detection.* A page we hold is asked for with `If-None-Match` and `If-Modified-Since` when
    it has an ETag or Last-Modified (a 304 leaves it alone); otherwise its text is read and hashed
    (whitespace-insensitive), and an equal hash leaves it alone. New or changed text gives its page
    source the next version and queues the ingest job, which swaps the chunks. Unchanged pages keep
    their chunks and cost no embedding. An unchanged page whose ingest never ran, or failed (the
    knowledge limit, say), is queued again.
  - *Gone pages.* A 404 or 410 removes the page's source and chunks and keeps the row as `gone`
    (a gone page that is listed or linked again in a later crawl is read again; not twice in the
    same crawl). A page that now answers with `noindex`, a disallow, another type or another site is
    removed from knowledge the same way and shown as `skipped` with the reason.
  - *Result.* The site is `ready` (`failed` with the reason when no page could be read or the crawl
    could not start); the crawl is `done` or `failed`.
- **API** (admins only, like the rest of knowledge).
  - `POST /knowledge-sources` with `type: "site"`, `url`, optional `title`, `recrawl`
    (`weekly`/`off`); `PATCH` takes `title`, `recrawl`, `excluded_paths` (the whole list, at most 50
    paths) and `reingest` (crawl now). The address of a site can't be edited (a different site is
    a new source). A site counts no characters itself; its pages do.
  - `GET …/{id}/pages?status=&limit=&offset=` (shallowest first; default 200, at most 500);
    `DELETE …/{id}/pages/{page_id}` (the page's knowledge goes, the row stays as `removed`, and later
    crawls leave the address out); `POST …/{id}/excluded-paths` `{path}` (a path or a full address;
    pages at the path or below it go now as `excluded`, and are not requested again; taking a path
    off with `PATCH` lets the next crawl read it); `POST …/{id}/recrawl` (404 for anything that is
    not a site).
  - `KnowledgeSource` gains `site` (`SiteCrawlInfo`: status, recrawl, excluded paths, pages found,
    done, failed and skipped, the characters and chunks of the ready pages, the cap, whether it was
    cut at the cap, the error, started, finished, next crawl). `KnowledgeSourceCreate.type` gains
    `site` (not `page`).
- **Web.** The Knowledge page's Add menu gains **Website** (address, optional title, "Check for
  changes every week" on). A site is a row in Sources with a chevron that opens its pages under it:
  a summary of the crawl (found, read, failed, stopped at the cap, the next check), **Crawl now**,
  the excluded paths (add one, or take one off), and the pages as stacked rows (title, path, status,
  when it was read, the reason it failed or was skipped) with a menu per page: Remove page (asks
  first) and Exclude that path. Stacked rows and a one-column panel, so it works at 375 px. The list
  polls while the site is crawling or its pages are being built. Deleting a site says its pages go
  too.
- **Not built.** A way to bring back a removed page except deleting the site (excluding a path can be
  undone; removing a page cannot); `.xml.gz` sitemaps; JavaScript-rendered pages (only the HTML the
  server sends is read, as for a single page); a per-site page cap the owner picks below the plan's;
  a crawl history.
- **Tests.** Unit: `test_crawl_rules.py` (robots groups, longest match, wildcards, sitemap and index
  parsing, an entity bomb, address normalisation, same-site, excluded paths, links and robots meta,
  the hash), `test_crawl_fetch.py` (`fetch_document`, SSRF for robots, sitemap, link, redirect and
  start addresses, the sitemap file and cap limits, one page's outcomes, `allow_private`),
  `test_settings.py`. Integration: `test_site_crawl.py` (end to end on a fixture site, the cap,
  a better plan, resume, stale jobs, breadth first, robots/noindex/other sites, failing pages, a
  disallowed site, www redirects, re-crawl by ETag and hash, gone and returning pages, one crawl at
  a time, remove a page, exclude a path, the scheduled re-crawl and a lost job, SSRF, roles,
  tenancy, deletion, the knowledge limit). Tenancy: the new routes, body, param and tables in
  `test_isolation.py`; the account deletion test seeds a site. Vitest: `SitePages.test.tsx`. E2E:
  `gr35-site-crawl.spec.ts` (a local fixture site; `CRAWL_ALLOW_PRIVATE` in the e2e stack).
- **Unsure / for the coordinator:** regenerate the client (`SiteCrawlInfo`, `SitePage`,
  `SitePageList`, `ExcludePath`, `site`, `recrawl` and `excluded_paths` on the source models, `site`
  and `page` in the type literals, the four new operations); the web types are aliases waiting for
  it (`KnowledgeCreateType` is `KnowledgeSourceCreate["type"]`). The web calls the new paths through
  the typed client, so typecheck after regenerating. `CRAWL_ALLOW_PRIVATE` belongs in no production
  config.

## C-106 · Team members and roles (GR-19, feature/gr-19-team)

- **Permission matrix, in one place.** `auth/permissions.py` has a `Permission` enum and a
  role-to-permissions map (each role has everything below it). Routes ask for a permission with
  `require_permission` (`CanReply`, `CanManageAutomations` and the other aliases in `auth/deps.py`),
  never for a role. The old `Admin`/`Owner`/`AnyMember` aliases stay for read routes. Every write
  route under `/v1/w/{wid}` now declares a permission; the tiers are the ones the routes already had
  (agents reply, tag and assign, and use Ask; admins also automations, knowledge, settings, channels,
  publishing, contact fields, segments, webhooks, the audit log and inviting agents; owners also
  billing, members, ownership and deleting the workspace). `tests/unit/test_permission_routes.py`
  walks the app's routes and fails for a workspace write route without a permission, and for a write
  route outside a workspace that is not in its short, reasoned list.
- **The web reads the matrix from the API.** `GET /v1/w/{wid}/permissions` returns the caller's role
  and permission names; `useCan()` (`lib/permissions.ts`) answers `can(name)` and allows nothing
  while it loads. The TypeScript side holds permission names only. The existing role-based hiding
  (nav items, settings tabs, page layouts) is left as it was; the new pages and their buttons use
  `can()`.
- **Invitations.** Table `workspace_invitations` (email lower-cased, role admin or agent, invited by,
  status pending, accepted or revoked, expiry, Clerk's invitation id). No token: Clerk sends the email
  and holds the link. One pending invitation per workspace and email (a partial unique index). They
  expire after 14 days; "expired" is worked out on read, and a resend starts the 14 days again.
  *Only owners invite admins; admins invite agents* (a decision; the plan left it open). Routes:
  `POST/GET /invitations`, `POST /invitations/{id}/resend`, `DELETE /invitations/{id}`.
- **Clerk is behind an interface** (`auth/invitations.py`): the real sender calls the Backend API's
  invitations; `CLERK_INVITATIONS_PROVIDER=fake` (refused in production, set in the e2e stack) and
  `use_invitation_sender` in tests keep it in memory. A person who already has an account is not sent
  to Clerk (it refuses a known address); they get a plain email from us and join at their next sign-in.
  If Clerk fails the invitation is not created (503).
- **Accepting.** `GET /v1/me` and `GET /v1/workspaces` call `auth/accept_invitations.py`: a pending,
  unexpired invitation for the user's email joins them with the invited role, but only when Clerk says
  that email is verified (an address typed at sign-up and never confirmed must not open a workspace).
  Their last workspace becomes the new one, so `/app` lands there. A Clerk outage skips the step and
  the next call retries. No webhook is needed.
- **Members.** `GET /members` (with seats), `PATCH /members/{user_id}` (admin or agent; owners only),
  `DELETE /members/{user_id}` (owners only), `POST /ownership-transfer` (owners only, needs the
  workspace name; the old owner becomes an admin and the new one the owner of record). The owner of
  record cannot be demoted or removed (409): transfer first, so a workspace always has an owner. You
  cannot remove yourself. Removing a member deletes the membership only; their past messages,
  automations and audit rows keep their user id and name. *The inbox has no per-member assignment yet
  (GR-20), so there is nothing to clear on removal;* GR-20 adds that to `services/team.remove_member`.
- **Seats.** `members` entitlement: **Free 1, Pro 3, Max 10, decided by the owner on 2026-10-24
  ("for now")** (PD-1). Members plus unexpired pending invitations count; one more past the cap is a
  402 `quota_exceeded` naming `members`. Revoking or an expiry frees the seat.
- **Audit.** Table `audit_events` (actor, actor name at the time, action, target type and id, small
  detail JSON, time). `services/audit.record` adds a row to the caller's session, never commits, and
  drops detail keys that could hold message text or a credential (body, text, content, token, secret,
  password, key, caption) and long values. *Deviation: rows are written from the route handlers, next
  to the commit, where the member is known; the service functions do not carry the user.* Recorded:
  message sent, automation created/updated/deleted/activated/paused, knowledge source
  created/updated/deleted, settings (workspace, AI, business hours, lead settings, saved replies,
  webhook endpoints, social accounts), billing (checkout started, cancelled, resumed), members
  (invited, resent, revoked, joined, role changed, removed, ownership transferred). Not recorded yet:
  contact tags/fields/segments, comment replies, scheduled posts, plan changes that arrive by Dodo's
  webhook. `GET /audit-events` (owners and admins) filters by member, action and date, 30 a page with
  `offset` and `has_more`, and lists the actions present for the filter.
- **Web.** Settings gains Members and Audit log tabs (owners and admins). Members: list with role and
  last active, a role select, Remove (asks first), Make owner (type the workspace name), the seat
  summary, pending invitations with Resend and Revoke, and an Invite dialog (the admin role only for
  owners). Audit log: member, action and date filters, Newer and Older. Both stack at 375 px.
- **Tests.** Unit: `test_team_rules.py` (matrix, who invites whom, seat counting, invitation states,
  audit detail, the fake sender), `test_permission_routes.py`, `test_settings.py`. Integration:
  `test_team.py` (invite, accept, unverified email, existing account, expiry and resend, revoke,
  duplicates, Clerk failing, seats on Free and Pro, role changes, the owner rules, transfer, removal
  keeping attribution, 403s for agents and admins, audit writes, filters and paging, tenancy);
  tenancy: the new routes, params and tables in `test_isolation.py`; the workspace deletion test seeds
  an invitation and an audit row. Vitest: `MembersPage`, `AuditLogPage`, `permissions`, the settings
  tab lists. E2E: `gr19-team.spec.ts` (an invited agent signs up, replies' inbox opens, 403 on
  automations and billing, the UI hides them; a `plan` seed route in the e2e API).
- **Unsure / for the coordinator:** regenerate the client (`WorkspacePermissions`, `Member`,
  `MemberList`, `Seats`, `Invitation`, `InvitationList`, `InvitationCreate`, `MemberRolePatch`,
  `OwnershipTransfer`, `AuditEvent`, `AuditEventList` and the new operations); the web types are
  aliases waiting for it. Migration `0032` follows `0031`. The e2e stack
  needs `CLERK_INVITATIONS_PROVIDER=fake` (added to `scripts/e2e-stack.mjs`).

## C-103 · Native Google Sheets sync (GR-27, feature/gr-27-sheets-followups)

Roadmap P5. Migration `0031_google_sheets` (expand-only; the coordinator re-chains it).

- **Access.** Google OAuth with the narrow `drive.file` scope (plus `openid email`, only to show
  which account is connected). Offline access with `prompt=consent` so Google always returns a
  refresh credential. The credential is stored encrypted like platform tokens
  (`google_connections.credential_enc`, Fernet via `TokenCipher`) and never returned; responses carry
  no field with token, secret or password in its name.
- **Unverified (cannot be checked from here; no Google account or app was used).**
  - *Existing sheets under `drive.file`.* From Google's documentation, `drive.file` gives per-file
    access: files the app created, or files the person opened with the app through the Google
    Picker. So a link pasted into a form is **not** enough to grant access to a sheet Social Hood
    didn't make; the Sheets API answers 404 or 403. *Decided: the supported path is "Create sheet"
    (Social Hood makes the sheet and writes its header row). "Use a sheet by its link" is offered and
    works only for a sheet Google already lets the app see (one it made earlier, for example after
    disconnecting and connecting again); otherwise it says so in plain words on the field.* The
    Picker (a browser script and a Google API key) would let a person grant a sheet they already
    have; it is left for later because it can't be tested without Google.
  - *App verification (O-10).* `drive.file` is documented as a non-sensitive scope, which does not
    need Google's sensitive-scope review; the OAuth consent screen still needs the app name, logo,
    privacy policy and terms links and a verified domain, and an app in "testing" mode only lets the
    listed test users in and expires refresh credentials after 7 days. Plan on moving the consent
    screen to "In production" before real customers connect. If the Picker or a broader scope is ever
    added, the review is longer. Not confirmed with Google.
  - The real client follows Google's documented endpoints and is tested against recorded shapes with
    respx (`tests/contract/test_google_sheets_client.py`); it has never run against Google.
- **Setting up.** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
  (`<API>/v1/oauth/google/callback`), `GOOGLE_PROVIDER` (`google` or `fake`; `fake` is refused in
  production). Not required in production: without them the card says Google isn't set up.
- **Connecting.** Like Instagram's (X-1) the public callback connects nothing: it parks the code
  (encrypted) under a one-time nonce bound to the member and workspace from the state, and redirects
  to `/w/{slug}/settings/integrations?google={nonce}`; the signed-in page posts it to `…/complete`.
  Only the starter can finish it (404 expired or used, 403 someone else). A state made for another
  platform is refused at this callback. Reconnecting keeps the sheet and mapping unless the Google
  account changed.
- **API** (`/v1/w/{wid}/integrations/google-sheets`, owners and admins, Pro and Max). `GET` (status:
  connection, sheet, columns, the fields a column can hold, counts and the latest 10 rows),
  `POST /connect`, `POST /complete`, `POST /sheet` (create), `PUT /sheet` (by link), `PUT /mapping`,
  `POST /test` (a sample row now; 409 with the reason in plain words), `DELETE` (revokes at Google
  as far as Google answers, removes the connection and its waiting rows).
- **Plan: PD-6 decided 2026-10-24 ("for now").** Webhooks stay on every plan (Free 1, Pro 5, Max 20
  endpoints); Google Sheets, the public API and Zapier are Pro and Max. New entitlement
  `sheets_sync` (Free no, Pro yes, Max yes); 402 `entitlement_required` "Google Sheets sync is part of
  Pro." The card shows the plan message with a link to the plans. A workspace that drops to Free
  keeps its connection but queues no new rows.
- **Mapping.** An ordered list of `{field, header}`, at most 30. Fields: name, @username, platform,
  email, phone, automation, captured at, consent, and any custom contact field (`field:<key>`); a
  field appears once. The default is the eight fixed fields. The header row is written only to a
  sheet Social Hood made (on create and when the mapping is saved); a sheet that was already the
  person's is never overwritten.
- **Rows.** `lead.captured` also queues a `sheet_rows` row in the same transaction
  (`sheets.queue_lead`, called from `events.lead_captured`, only with a connection, a chosen sheet and
  a plan that includes Sheets sync). The `append_sheet_row` job (bulk lane, recovery class RETRY) adds
  it with `valueInputOption=RAW`, so a customer's text starting with `=` is never a formula. The row
  keeps only the custom fields the mapping uses. *A sibling table and job rather than a new
  webhook delivery kind: `webhook_deliveries` belongs to an endpoint (address, signing secret,
  failure count) and a Google row has none of those.* It reuses the webhook machinery's backoff
  (`delivery.backoff`: 1 minute, 5 minutes, 30 minutes, 2 hours, 6 hours, 12 hours; 7 attempts).
  Only Google being busy (429, 5xx, no connection) is retried; the other answers fail at once.
- **Failure reasons (plain words, stored with a code).**
  - `access_removed`: "Access was removed: reconnect Google in Settings, under Integrations." The
    connection becomes `needs_reconnect`; waiting rows fail without calling Google.
  - `sheet_gone`: "Google said the sheet was deleted. Pick or create a sheet again."
  - `sheet_refused`: "Google won't let Social Hood write to that sheet. Pick or create a sheet
    again."
  - `no_sheet`, `google_busy` (retries ran out), `google_refused`.

  Owners and admins are told once a day per reason (new notification type `sheets_failing`, in app
  only). Reconnecting sends the rows that failed with `access_removed`; creating or choosing a sheet
  sends those that failed for the sheet reasons.
  *Deviation from the plan: the failures are on the Sheets card (status, last error, latest rows),
  not in the Activity feed.* The feed's kinds are a closed list shared with the web types, and a new
  one is a change to GR-05's schema and page; left for a later pass.
- **Consent column.** The row carries the marketing consent recorded for the contact's channel when
  it is queued. A flow's consent question comes after the answer it follows, so the row for the
  first capture usually has an empty consent cell. *Limitation, not fixed.*
- **More than one row per person.** One row per capture event: a flow that asks for an email and then
  a phone adds two rows, the second with both. Updating the first row in place needs the row's
  address from Google and was left out.
- **Duplicates.** Google's append isn't idempotent: a worker killed after Google accepted a row and
  before it was recorded sends it again on recovery. Rare, accepted.
- **Retention.** Finished `sheet_rows` (they hold names, emails and phones) are deleted with the
  webhook deliveries' window by the purge job.
- **Fake Google.** `google/fake.py`, chosen by `GOOGLE_PROVIDER=fake` or `use_google` in tests
  (`tests/support/google.py`, on in every test). It sees only the sheets it made, can revoke access,
  delete a sheet and fail the next call. With a Redis client the sheets live in Redis, so the e2e API
  and worker share them; the e2e API has `GET /__e2e/google-sheets/{id}`, `POST …/{id}/delete` and
  `POST /__e2e/workspaces/{wid}/plan`.
- **Web.** A Google Sheets card at the top of Settings, Integrations: connect (or reconnect), the
  sheet (create with a name, or use a link, with the API's reason on the field), the columns (header
  field, move up and down, remove, add an unused field, save, undo), a test row, the latest rows with
  their plain reasons, and Disconnect (asks first). Free sees the plan message.
- **Tests.** Unit: `test_sheets.py`. Contract: `test_google_sheets_client.py`. Integration:
  `test_google_sheets.py` (callback and nonce, forged and foreign states, create, mapping and header,
  existing sheets, test rows, revoked access and reconnect, disconnect, plan and roles, a capture
  becoming a row, retries and the backoff, running out of attempts, a deleted sheet, consent and
  custom fields, retention). Tenancy: the four new bodies and both tables in `test_isolation.py`.
  Vitest: `GoogleSheetsCard.test.tsx`, `sheetMapping.test.ts`. E2E: `gr27-sheets-sync.spec.ts`.
- **Unsure / for the coordinator:** regenerate the client (`GoogleSheetsStatus`, `GoogleConnectStart`,
  `SheetColumnOut`, `SheetFieldOption`, `SheetRowOut`, `SheetOut`, `SheetMappingPut`,
  `SheetTestResult` and the seven operations); the web calls the new paths through the typed client.
  The plan comparison tables (`lib/billing/plan.ts`, `lib/marketing/plans.ts`) don't list Sheets sync
  yet. Add the Google OAuth client to the production config before turning this on.

## C-104 · Captures in the weekly report (GR-34 follow-up, feature/gr-27-sheets-followups)

No migration.

- **The count.** `overview_stats.captures_received`: the flow step log rows of kind `ask` whose
  `detail` has an `answer`, in the week. That is the stored source of truth: an ask step gets an
  `answer` only when the answer was accepted and saved (a question skipped after its tries has
  `skipped` instead; a send step's tap also has an `answer` and is not counted), and it is the same
  predicate the flow funnel (GR-15) counts. *Not the `lead.captured` events: those are stored only as
  deliveries to an endpoint, so a workspace without one would show zero.*
- **Dated by `updated_at`,** which is when the answer was taken (the row is created when the question
  is asked, which can be days earlier). A consent follow-up a few minutes after the answer touches the
  row again and could move a Sunday-night capture into the next week; accepted.
- **One list.** `OverviewStats.captures` (so the digest stores it in `weekly_digests.stats`) and a
  new `captures` metric ("Leads captured", a count) in the report's `COUNT_METRICS`, before leads
  qualified: the week, the week before, the change and the 8-week series like the others. The
  digest's trends table carries it automatically; `test_weekly_report.py` still compares every
  report metric with the stored digest. A week before the workspace existed with nothing in it is a
  gap, as for the other counts (`captures` joins `QUIET_KEYS`).
- **Note removed.** `ReportNote`, `WeeklyReport.notes`, `reports.NOTES` and the report page's "aren't
  counted here yet" line are gone. *The API field `notes` is removed, not emptied: it had one value
  and nothing else reads it.*
- **Tests.** `test_reports.py` (the metric and its place), `test_weekly_report.py` (a skipped, a
  tapped and a waiting step are not counted; the week, the week before, after the week; the series;
  no `notes`), `test_weekly_digest.py` (the stored stats carry `captures`), `WeeklyReportPage.test.tsx`.
- **Unsure / for the coordinator:** regenerate the client (`captures` in the metric keys, `notes`
  removed from `WeeklyReport`).

## C-105 · Template placeholders are checked at activation (GR-16 follow-up, feature/gr-27-sheets-followups)

No migration. Closes the open point in C-099: a flow template's `[price]` or `[code]` looked filled
to activation.

- **One list.** `templates.PLACEHOLDERS` maps each bracket token a template uses to what goes there
  (`[price]`: your price, `[code]`: your code). `templates.unfilled(text)` finds the tokens still in a
  text (case-insensitive, each once, in order of appearance) and `unfilled_copy(token)` words the
  error: "Replace [price] with your price." Only listed tokens count, so a user's own brackets
  ("[incl. GST]", "[1]", "[prices]", "[Shop link]") never trip it. A unit test checks that every
  bracket token the templates use is in the list.
- **Where it refuses.** Activation of a flow (`flows._text_errors`, so a send step's text, a
  question's text, retry, consent and confirm lines, and the body of a saved reply a step uses) and
  of an automation on the message settings (`message_text`, the tap-first `opening_text`, the
  `follow_nudge_text`). The error sits on that field, so the step shows it like any other activation
  error; two tokens in one text give two errors; `missing_for_activation` lists the field. Button
  titles, public replies and AI instructions are not send text and aren't checked.
- **Editor.** The step checker (`stepProblems`) marks the same texts as you type, from a mirror of
  the list (`PLACEHOLDERS` in `lib/automations/flow.ts`; the comment names the Python list to keep in
  step). The API's answer is merged as before, so a token the editor doesn't know still shows when
  activation is refused.
- **Template tests changed.** The price-by-option and coupon templates now need their price or code
  as well as their link: `test_template_flows.py` (what each holds, and that they activate once
  filled), `test_template_flows_api.py` (fields still to fill, 422 per step, filling one at a time),
  and the GR-16 e2e spec fills them.
- **Tests.** Unit `test_template_placeholders.py` (the list, the tokens found, ordinary brackets left
  alone, flows, questions, the message settings, the opening and follow line); integration
  `test_template_flows_api.py` (refused on each step, the coupon code, a message on the settings);
  vitest `flow.test.ts`, `FlowEditor.test.tsx`.

## C-107 · Copilot write actions (GR-36, feature/gr-36-copilot-writes)

The agent can propose a flow or a segment; a member approves it; only then is it saved, by the same
service the screen calls. It builds on the approval tables and routes the agent contract already
had (`agent_approvals`, `…/agent/approvals/*`) and on the flow engine (GR-03, GR-13) and segments
(GR-17).

- **The action gateway** is `services/agent_actions.py`, with the actions it knows in
  `agent/actions.py`. *`agent/gateway.py` (the R2 tier, mode and policy table) stays as it was: it
  decides what an agent may do on its own, which nothing does yet.* Proposals never execute.
  - *Propose* (from the tool, in the model's turn): the action must exist and not be an unavailable
    one; the principal's role must allow it (403 `forbidden`); the arguments are checked with the
    UI's own service validation (the flow graph, the plan step cap, tags and fields that exist,
    the segment's name and limit); then a pending approval is stored with the proposing step's
    idempotency key and the step is marked `approval`. A retried step finds its approval instead of
    adding another. Nothing in the workspace changes.
  - *Approve* (a member, `POST …/approvals/{id}/approve`): the approval row is locked and must still
    be pending and not past its time; the approver's role must allow the action; the arguments (as
    shown, or edited) are checked again; then the normal service function runs in a savepoint in
    the same transaction that marks the approval `approved` and stores its outcome. A flow is saved
    with `definitions.create`, `definitions.update` and `flow_store.save`; a segment with
    `contact_segments.create_segment`. A second approve is 409, so a write never runs twice.
  - *If the service refuses on approval* (a name taken since, a plan limit): nothing is saved, the
    approval stays pending, its `outcome` says `ok: false` and why, the trail gets `failed`, and
    the response is 200. The member can edit it (`args`) or reject it. *This differs from the
    contract's "409 when no longer pending" only for this case, which is not a state change.*
  - *Reject*: `rejected`, nothing saved. Anyone who can see the approval may reject (it changes
    nothing); 409 when decided.
  - *Expiry*: a proposal lasts **24 hours** (`APPROVAL_TTL`, already in the models; recorded here).
    `expire_agent_approvals` runs every 15 minutes, and the list and decision routes expire what is
    due first, so a stale card never approves. Expired is final: the member asks again.
- **The agent never executes on its own.** *Decided: the proposal tools are draft tier, not write
  tier, and the workspace's agent policy (mode, `create_automations` switch) does not gate
  proposing.* The policy is about what the agent may do without asking, and no tool does; a
  proposal only files a request that a member must approve, as if they had opened the screen. The
  policy stays read-only by default and its PUT stays R2. When a write tool that runs on its own is
  built, it goes through `gateway.decide` and the policy as designed.
- **Roles.** Both screens are for owners and admins (`Admin` on the automation, flow and segment
  routes), so `min_role` is admin for both actions: the proposal tools are not offered to a team
  member, and approving needs the same. A team member sees the approvals of their own runs (and can
  reject them); `can_decide` on each approval tells the web whether to enable Approve. *GR-19:*
  `agent.actions.required_role(spec)` is the one place to replace with the permission matrix
  (`automations.manage` for a flow, `contacts.manage` for a segment); callers don't change. The
  propose and approve checks both call it.
- **Audit.** Every proposal, approval, rejection, expiry, execution and refused execution is a row
  in `agent_approval_events` (who, when, what, outcome as plain facts), shown in the run trace
  (`approvals` on `GET …/agent/runs/{id}`, and "Proposed writes" in Settings → Agent's trace) and
  logged as `agent_approval`. *Kept in the agent's own tables: GR-19's general `audit_events` is
  not a dependency.* The hook is `_record` in `services/agent_actions.py`; mirror each event there.
- **Write tools** (`agent/tools/proposals.py`, admins):
  - `propose_flow`: a new automation (trigger, keywords, public replies, account) with a flow, or
    a new flow for an existing automation (`automation_id`). The model writes steps in order
    (send, ask, action, delay, branch, ai_reply, end) and names tags; the tool resolves names to
    ids and builds the typed `FlowDefinition`, chaining each step to the next unless a `goto`, a
    branch rule or a quick reply says otherwise. An unknown tag is refused with the tags the
    workspace has. Approving saves a **draft** automation (never activated); an existing
    automation keeps its status, and the card says so when it is live.
  - `propose_segment`: tags (by name, all required), platform, account, email or phone given,
    marketing consent, lead stages, score, activity and fields, as the contacts filter has them.
    The card shows the count it matches; the count is read again on approval.
  - `propose_broadcast`: **unavailable**. Registered for R2 so the model is never offered it; the
    plain reason is `agent.actions.UNAVAILABLE` ("Broadcasts aren't available yet…") and the
    gateway refuses the action with it. When GR-23 lands: add its action to `agent/actions.py`,
    register the tool in R1 and drop the entry.
  - `ToolContext` gains `step_id` and `step_key`, set by the executor, so a proposal files its
    approval against the step that made it.
- **Prompt.** `agent.v4`: the agent may propose flows and segments, must say a proposal is waiting
  for approval and what the card shows, that an approved flow is a draft that stays off, never says
  it is created, saved, live or sent, says plainly when a tool refuses, and says broadcasts can't be
  drafted yet. Eval cases (`area: writes`): the PRICE flow (English and Hinglish), the vip segment,
  an unknown tag, a team member (no tools; the answer names owners and admins), and a broadcast.
  The two earlier `prepare_automation` cases accept either tool. The eval seed gains the tags `vip`
  and `wholesale`.
- **Migration 0033** (after 0032), expand-only: `agent_approvals.idempotency_key` (unique per
  workspace), `outcome`, `executed_at`, an index on pending expiry, and the table
  `agent_approval_events`. The coordinator re-chains it.
- **API.** `GET …/agent/approvals` (`status` now also takes `all`, plus `run_id`), `POST
  …/approvals/{id}/approve` (body `args` optional) and `…/reject` are built (no longer `x-pending`).
  `AgentApproval` gains `lines`, `match_count`, `step_count`, `can_decide`, `requested_by`,
  `outcome` and `events`; `AgentRunDetail` gains `approvals`; the action cards gain
  `flow_proposal` and `segment_proposal` (`approval_id`, `title`, `lines`, and `step_count` or
  `match_count`). New schemas: `ApprovalOutcome`, `ApprovalEvent`, `ApprovalListStatus`.
- **Web.** An answer's proposal card says in plain words what will happen (the flow's steps, or the
  segment's filters and count), when it expires, and has Approve and Reject. Approve is disabled,
  with the reason, for roles that can't do it. After a decision the card shows the result and an
  Open button (the automation or the segment), or why nothing was saved. **Waiting for you** sits
  above the question box in the panel and the page, collapsed, with a count, and decides the same
  approvals. The cards read the approval from the API, so they are right after a reload. No new
  real-time event: a decision refreshes the lists, and the list refetches on focus.
- **Not built.** Editing a proposal in the web (the API takes edited `args`; the card only approves
  or rejects as shown); a real-time event when someone else decides; resuming a run after an
  approval (a run ends when it has proposed; the answer says it is waiting); proposals that change
  or delete things other than a flow and a segment.
- **Tests.** Unit: `test_agent_actions.py` (the flow built from steps, branches, quick replies,
  tags, missing parts; strict inputs; the registry; the refusals before any database; plain-words
  filters; vocabulary). Integration: `test_agent_actions.py` (propose, nothing saved, approve to a
  segment and a draft automation with its flow and keywords, tags, a change to an existing
  automation, the step cap, reject, expiry on list and on decision, a refused approval then an
  edit, idempotent proposals, roles, the run trace). Tenancy: `agent_approval_events` in
  `test_isolation.py`; the approvals routes are no longer pending. Vitest: `ProposalCardView.test.tsx`,
  `WaitingForYou.test.tsx`. E2E: `gr36-copilot-writes.spec.ts` with the seed route
  `POST /__e2e/workspaces/{wid}/agent-proposals`.
- **Unsure / for the coordinator:** regenerate the client (`FlowProposalAction`,
  `SegmentProposalAction`, `ApprovalOutcome`, `ApprovalEvent`, the new fields of `AgentApproval`
  and `AgentRunDetail.approvals`, `ApprovalListStatus`, `run_id` on the list); the web types are
  aliases waiting for it. Run `alembic check` (the model and migration
  declare the same index and unique constraint). The agent eval needs a live key; I did not run it.

## C-108 · Facebook Pages, Messenger and comments (GR-29, feature/gr-29-facebook)
A Facebook Page is a third platform: connect Pages, answer Messenger in the inbox, answer comments
on Page posts, and run the wave 2 to 4 automations on it where Messenger allows. **Every Meta
behaviour below was written from Meta's docs and none has been seen on a real Page.** Each one is
marked *unverified* and listed in `docs/verification.md` item 36. The second App Review submission
(O-10) is `docs/ops/app-review.md` section 8.

### The platform
- **Account.** `social_accounts.platform = "facebook"` (the check already allowed it).
  `platform_account_id` is the Page id (the webhook `entry.id`), `app_scoped_id` the connecting
  person's Facebook id (so Meta's deauthorize and data-deletion callbacks, which look accounts up by
  that id, find every Page they connected), `username` the Page's username, `display_name` its name.
  The Page access token is stored encrypted like every token. *Unverified:* a Page token made from a
  long-lived user token does not expire, so `token_expires_at` is null and nothing refreshes it
  (`FacebookAdapter.refresh_token` returns the token as it is).
- **Adapter** (`platforms/facebook/`): `FacebookAdapter` implements `PlatformAdapter` on
  `graph.facebook.com` (`me` is the Page). Capabilities: DM send, DM attachments, read receipts,
  conversation backfill, comments and private reply; Human Agent follows `IG_HUMAN_AGENT_ENABLED`
  (below). No templates, no heart sticker, no stories. Publishing, post insights and account
  insights raise `capability_unavailable` until GR-30; `get_account_insights` returns the Page's
  followers only. Modules mirror Instagram's: `oauth`, `webhooks` (split), `parse`, `reads`
  (posts, counts, followers, profile, threads), `comments`, `moderation`, `profile` (ice breakers).
  Messenger's message shapes go through the Instagram parser (they are the same), so only reads,
  deliveries, postbacks without an id and `feed` comments are parsed here.
- **Sandbox.** `SandboxAdapter` serves any account with a `sandbox_` id; for a Facebook one it
  reports the Page's capabilities plus Human Agent. `POST /dev/sandbox/accounts` takes an optional
  `{platform: "instagram" | "facebook"}`; `POST /dev/sandbox/inbound` on a sandbox Page builds Page
  webhook bodies (a DM, a comment as a `feed` change on the Page's first sandbox post, a referral
  with `source: SHORTLINK` or `ADS`, a postback, an opt-in) and stores them as `facebook` events.
  Live comments and the story kinds are refused there with 422 on `kind`.
- **Migration 0034** (after 0033). `webhook_events.provider` accepts `facebook`. Nothing else changes: no new
  table, so the account purge, tenancy seeds and `B_TABLES` need no change.

### Connect
- Facebook Login for Pages, in two steps so the person picks which Pages (the plan asks "pick which
  Pages"). `POST /social-accounts/facebook/connect` returns the authorize URL (state in Valkey, single
  use, 10 minutes; 503 until `META_APP_ID`, `META_APP_SECRET` and `FB_REDIRECT_URI` are set; 402 over
  `accounts_per_platform`). The public callback `GET /v1/oauth/facebook/callback` never connects
  anything (X-1, as Instagram): it parks the code, encrypted, under a one-time nonce bound to the
  member and workspace, and redirects to Connections with `?facebook=<nonce>` (errors:
  `?error=…&platform=facebook`).
- `POST …/facebook/pages {nonce}` exchanges the code, makes a long-lived user token, reads
  `/me/accounts` and keeps the Page tokens (encrypted, 10 minutes) under the same nonce; it returns
  each Page with `connected`, `can_connect` and a `problem` (a person without the MESSAGING task
  can't answer messages). Asking again returns the same list. 403 for another member or workspace,
  404 when expired, 502 when Facebook fails.
- `POST …/facebook/connect-pages {nonce, page_ids}` connects the picked Pages: the plan's limit is
  checked for all of them first (402, nothing added, the nonce stays valid), then each is upserted
  (a reconnect updates in place; 409 `account_in_use` when another workspace has it live), subscribed
  to webhooks and queued for the first sync. The nonce is spent only on success. A failed
  subscription leaves the Page in `error` with Retry, as for Instagram.
- The Instagram connect now tags the held code with its platform, so a Facebook nonce can't finish an
  Instagram connect and the reverse.
- Settings: `fb_redirect_uri`, `fb_webhook_verify_token`. They are not in the production-required
  list (Facebook is off until set).

### Messenger
- **Webhook.** `GET/POST /webhooks/facebook`, signed with `META_APP_SECRET`, verify token
  `FB_WEBHOOK_VERIFY_TOKEN`; events stored once per `fb:` key and processed by a `facebook` handler
  that routes by Page id exactly like Instagram's (messages and echoes, postbacks, referrals, reads,
  deliveries, reactions, edits, opt-ins). A delivery receipt names several messages: one event each.
  A read is a watermark, so every message we sent before it is read. *Unverified:* all payload shapes.
- **Sending** follows the Instagram pipeline: the 24-hour window, `messaging_type: RESPONSE`;
  text up to 2,000 characters (`TEXT_LIMITS`), attachments by URL up to 25 MB, quick replies (13),
  link buttons as the button template (3 buttons, 640 characters). **Message tags:** the app models
  only HUMAN_AGENT, so a Page gets the same 7-day human window as Instagram when
  `IG_HUMAN_AGENT_ENABLED` is on (Meta approves Human Agent once for the app, so there is no
  separate setting); nothing else is sent outside the 24 hours, and the existing
  `reply_window_closed` error says so with "Facebook". Meta's closed-window error for Messenger
  (10 / 2018278) maps to the same code. The send buckets are per account, so the Instagram ones are
  reused (they only pace us; Messenger's limits are higher).
- **Inbox.** Conversations have `platform: "facebook"`; the platform filter and badges include it.
  The contact's name and picture come from the Messenger profile; people have no handle.
- **Backfill** reads `/me/conversations?platform=messenger` through the Instagram thread parser.

### Comments
- Comments arrive as the `feed` field (`item: comment`, `verb: add`); edits, removals, hides and
  other items are ignored. Post ids are the Page post ids; a post we don't have is read with
  `GET /{post_id}` and stored like Instagram's. The Page's own comments are skipped. *Unverified:*
  the commenter's `from.id` may differ from the Page-scoped id their messages carry; then the
  comment's contact and the person's Messenger contact are two contacts until they write.
- Public reply `POST /{comment_id}/comments`; private reply the Send API addressed by
  `recipient.comment_id` (text, link buttons and quick replies; no attachments, as Instagram);
  hide and unhide `is_hidden`; delete (already gone counts as done). Backfill reads
  `/{post_id}/comments` with the replies expansion. The private-reply bucket (750 an hour), the
  7-day limit and one per comment are shared with Instagram.

### Automations
Every trigger and step works on a Page except what Messenger lacks, which activation refuses in plain
words (`validation.py`, `flows.py`; copy shared with the web):
- **Allowed:** DM keyword, comment keyword and any comment (with public replies and private replies,
  tap first, link buttons, tracked links), entry link (`https://m.me/<username or id>?ref=<code>`),
  ad click (a click-to-Messenger ad's `referral` with `source: ADS`), conversation starters
  (Messenger's `ice_breakers`, the same editor and `ib:{id}` payloads; a tap is a postback),
  welcome and default reply, AI replies, flows (send, quick replies, ask, branch, action, delay,
  split, saved replies), data capture, business hours, lead scoring.
- **Refused:** story reply and story mention ("Facebook Pages have no story replies or story
  mentions"), Live comments ("Live comments on Facebook aren't supported yet"), the follow message
  and a flow branch on following (Messenger doesn't say who follows a Page), the flow's profile
  button (it opens an Instagram profile), and an Ask step's marketing-consent question (there is no
  Facebook consent channel yet; adding one means a new `contact_consents.channel` value and
  contact-list column). *Deviation from "every trigger and step": these four groups are the ones
  Messenger doesn't have; the first two because Pages have no such surface, the last two because the
  data isn't there.*
- **Limits.** A message may be 2,000 characters (not 1,000 bytes) in its longest rendering;
  button-template text stays 640; public replies stay 300 (our own cap). Copy written for Instagram
  is said with "Facebook" (`validation.localize`).
- Automations created without an account still pick the workspace's only live **Instagram** account
  (`live_instagram_accounts`); with a Page and an Instagram account the member chooses.

### Other
- Ask Social Hood no longer says "Facebook isn't connected" when a Page is; the tools check for a
  connected Page (`facebook_unconnected`) and treat `facebook` as a platform name like the others.
  Analytics tools cover a Page's posts and comments; insights are absent until GR-30.
- Billing: a `facebook_accounts` usage meter (plan limit `accounts_per_platform`, per platform).
- Webhook health (`check_webhook_health`) still watches Instagram only. *Not built.*
- Marketing pages, the privacy policy and terms still say Instagram and WhatsApp; they change with
  the second App Review submission. *Not built, needs the owner's wording.*

### Web
- `FacebookGlyph`, `PlatformGlyph` and `PLATFORM_BG` (the existing `facebook` colour token);
  Connections gets **Connect Facebook** (and **Add sandbox Page** in development), a Pages dialog
  after Facebook's redirect (tick Pages; a Page that can't be connected says why; a refusal keeps the
  list), Page cards ("Facebook Pages API"), search and filter. The inbox platform strip, thread
  header, unsupported-message link, attachment rules (25 MB), contact filter, Home, Billing and the
  send-failure copy include Facebook. Comments, entry links and conversation starters list Pages and
  say Facebook; the post panel opens the post in Facebook.
- The automation editor knows the account's platform: Facebook trigger names, the story triggers
  disabled with the reason, message counters in characters out of 2,000, no follow message, and in
  flows no follows condition, profile button or consent question.
- `instagramAccounts` stays for story mentions and publishing; `automationAccounts` (Instagram and
  Facebook) is what automations, comments, entry links and starters list.

### Tests
- Unit: `test_facebook_platform.py` (splitting, every parse, send payloads, ice breakers, connect URL,
  Page list, registry, sandbox payloads), `test_facebook_automations.py` (activation rules and flow
  rules on a Page). Integration: `test_facebook_connect.py` (the whole connect, X-1, quota, expiry,
  reconnect, deauthorize), `test_facebook_messenger.py` (webhook route, intake, echo/delivery/read,
  postback, m.me, ad referral, reply, window, limits), `test_facebook_comments.py` (comment intake,
  automations on a Page, comment actions, refusals, entry links, starters, purge); tenancy bodies for
  the three new routes and the sandbox body. Vitest: `FacebookPagesDialog`, `PlatformGlyph`,
  `facebook-rules`, `steps/facebook`, `upload-facebook`, `inbox/facebook`, additions to the
  Connections page, platform strip and Billing tests. E2E: `gr29-facebook.spec.ts` on the sandbox.
- *Existing tests changed:* the automation notice's link is now "Connect an account" and says
  "Instagram and Facebook"; the empty Connections text names Facebook; `test_entry_triggers.py`'s
  account stubs carry a platform.

### Unsure / for the coordinator
- Regenerate the client: `FacebookConnectPages`, `FacebookPageList`, `FacebookPageOption`,
  `FacebookPagesRequest`, `SandboxAccountCreate`, `facebook` in the platform literals
  (`SocialAccountOut`, conversations, contacts filters, flow platform condition), the four new
  operations (`start_facebook_connect`, `list_facebook_pages`, `connect_facebook_pages`, the
  optional body of `create_sandbox_account`), then typecheck: web code calls them through the typed
  client and keys several `Record<Platform, …>` by `facebook`.
- `alembic check` for 0034 (after 0033).
- Meta's behaviour: see `docs/verification.md` item 36. The risky ones: the commenter id, whether
  private replies take buttons and quick replies, ice breakers without a Get Started button, the
  `tasks` field, and the Messenger text limit.

## C-109 · Public API and API keys (GR-25, feature/gr-25-26-api-zapier)

- **Owner decision PD-6 (decided 2026-10-24):** outbound webhooks stay on every plan (Free 1, Pro 5,
  Max 20 endpoints, GR-04); the public API, API keys and the Zapier app are **Pro and Max only**.
  It is the `public_api` entitlement in `billing/plans.py` (`free: False`), checked with
  `check_entitlement`, so the 402 is `entitlement_required` with `entitlement: "public_api"`
  ("The public API, API keys and Zapier are part of Pro."). Making a key on Free is 402. Listing
  and revoking keys stay open, so a workspace that downgraded can clean up. A key made on Pro stops
  working (402, same body) the moment the workspace is on Free again, and works again if it comes
  back. *Decided, not pending.*
- **Keys.** `api_keys` (migration 0035 (after 0034), shared with C-110's column): name (1 to 80), the first 12
  characters (`key_prefix`, `shk_` and 8 more), the SHA-256 of the whole key (`key_hash`, unique),
  scopes, `last_used_at`, `revoked_at`, who made it. A key is `shk_` and 43 random characters
  (`secrets.token_urlsafe(32)`), shown once in the create response (`ApiKeyWithKey.key`) and never
  stored or logged. *A plain SHA-256, not a slow hash: the key is 256 random bits, so there is
  nothing to guess.* A key never changes after it is made (no edit; make another); revoking sets
  `revoked_at` and is the end of it. At most 20 unrevoked keys per workspace (409 over it).
- **Scopes** (`schemas/api_keys.py`): `contacts:read`, `contacts:write`, `tags:read`, `tags:write`,
  `conversations:read`, `messages:send`, `automations:read`, `webhooks:subscribe` (C-110's REST
  hooks). The key form starts read-only (`contacts:read` ticked). A route needs exactly one scope;
  a key without it gets 403 `forbidden`, naming the scope.
- **Managing keys** (owners and admins, `/v1/w/{wid}/api-keys`): list (with the scope catalogue),
  create (201), revoke (`DELETE`, returns the key; again is a no-op). In Settings > Integrations
  below the webhook endpoints: a list (name, prefix, scopes, made, last used or revoked), a create
  dialog (name and scopes), a copy-once dialog and a revoke confirmation. A Free workspace sees
  "part of Pro" and a link to plans instead of the form. *The routes carry a TODO for GR-19: they
  move to the same `require_permission` as the webhook endpoints.*
- **Authentication** (`auth/api_key.py`): `Authorization: Bearer shk_...` on `/public/v1`. The key's
  hash finds the key (the one cross-workspace lookup, in `tenant_bypass_scope`, as `auth/` may); it
  must be unrevoked and its workspace active (401 `unauthorized` otherwise; an unknown key also
  counts against the caller's IP, 60 a minute, so guessing is slow); then the per-key limit, then
  the plan. The key's workspace becomes the request's tenant exactly as for a member, so every
  service query is scoped and a key can never reach another workspace (404 for another workspace's
  id, like the app). `last_used_at` is written at most once a minute (Valkey `SET NX`). Every
  request's log line carries `api_key_id` and `workspace_id`; the key never reaches a log.
- **Rate limit.** *New limit `api_key`: 120 requests a minute per key* (a sliding window like the
  others, `security/ratelimit.py`). Sending a message also counts against the workspace's existing
  60 sends a minute (`sends`), the same budget as the app's. 429 `rate_limited` with `Retry-After`.
  *The numbers are proposals; changing them is one line each.*
- **Routes** (`api/public.py`, all call the app's services, no forked logic):
  `GET /accounts`, `GET/POST /contacts`, `GET/PATCH /contacts/{id}`, `GET /contact-fields`,
  `GET /tags`, `POST /contacts/{id}/tags` (add and remove by id), `GET /conversations`,
  `GET /conversations/{id}`, `GET/POST /conversations/{id}/messages`, `GET /automation-runs`
  (`automation_id`, `result`), `GET /openapi.json`. Responses are the app's schemas where they fit
  (`ContactList`, `ContactRecord`, `TagList`, `MessageList`, `AutomationRunList`) and lean ones where
  the app's carry internals (`PublicConversation`: no AI analysis, suggestion or summary).
  - *Create a contact* adds a customer to a **WhatsApp** account by phone number (the app's E.164
    rules; 409 for a number already there; 422 for an Instagram account, a phone without a country
    code or an email or field that doesn't fit). Instagram contacts exist only once they message or
    comment, so they cannot be added. `contact.created` is raised like for any new contact.
  - *Custom fields set* is `PATCH /contacts/{id}` with `fields` (merge, null removes), the app's
    validation and its `contact.updated` event.
  - *Send a message* is text only, through `sending.queue_outbound` with the app's rules and errors:
    409 `reply_window_closed` outside the window, 409 for an account that needs reconnecting, 402 for
    an account the plan made read-only. The message is "human" with no sender (`sent_by` null).
    `Idempotency-Key` is optional (the app's is required): the same key and body again returns the
    first response; a derived `client_id` also stops a double send when Valkey is down.
  - `GET /contacts` gains `sort=created` (newest contact first, for polling lists) in the service
    (`services/contacts.list_contacts(sort=)`); the app's own list is unchanged.
    `queries.list_runs` takes no `automation_id` for the workspace-wide list.
  - Errors are the app's problem+json, one format.
- **The document.** The public routes are **not** in the app's OpenAPI document (it is for the
  generated web client; `problem_openapi` leaves the public routers out). `api/public_openapi.py`
  builds a separate one: only `/public/v1`, bearer security, each operation's `x-required-scope`
  (also in its description), problem responses, and the scope list. It is served without sign-in at
  `GET /public/v1/openapi.json` (60 a minute per IP) and cached on the app.
- **Docs page.** `/developers/api` in the marketing group, server-rendered from that JSON and
  revalidated hourly: how to authenticate, the scopes, then each operation (method, path, scope,
  parameters, body fields, responses, a curl line). No viewer library (nothing in `package.json`
  renders OpenAPI); `lib/marketing/public-api.ts` reads the document with zod and builds the page's
  model. When the API can't be reached the page says so. *Not added to the sitemap or footer* (the
  sitemap test lists its pages exactly); one line in `PUBLIC_PATHS` adds it.
- **Not built.** An audit log of key use beyond the access log's `api_key_id`; an IP allow list; key
  expiry; a per-key rate limit setting; the webhook event catalogue in the document (GR-04's).
- **Tests.** Unit `test_public_api.py` (hashing and shape, scope check, limit numbers, entitlement
  values, the public document: every operation has a known scope, strings bounded, no credential
  names, nothing public in the app's document). Integration `test_public_api.py` (key management and
  roles, shown once and stored as a hash, Pro/Max gating both ways, 401s, the done-when read key
  lists and is 403 on a write, each scope, each endpoint, the window and idempotency, the per-key
  and sends limits, last used, revoke, tenancy with two workspaces). Tenancy: the `api_keys` table,
  `key_id`, the create body, and `test_public_routes_hide_other_workspaces` (a workspace A key
  calls every public route with B's ids: 404 and B unchanged). Vitest: `ApiKeysSection.test.tsx`,
  `public-api.test.ts`, `ApiReference.test.tsx`. E2E: `gr25-public-api.spec.ts` (the stack gets a
  `PUT /__e2e/workspaces/{wid}/plan` seed route).
- **For the coordinator:** regenerate the client (`ApiKey`, `ApiKeyWithKey`, `ApiKeyList`,
  `ApiKeyCreate`, `ApiScope`, the three `/api-keys` operations; the public routes are not in it);
  the web types are aliases waiting for it. `alembic check` should be clean (the partial index on
  `webhook_endpoints.api_key_id` is in the model). Migration 0035 is chained on 0030; re-chain it.

## C-110 · Zapier app (GR-26, feature/gr-25-26-api-zapier)

- **Plan gate (PD-6, decided 2026-10-24, see C-109):** Zapier is Pro and Max only, because it runs on
  the public API. The REST hooks Zapier subscribes stop receiving events when the workspace is no
  longer on a plan with `public_api` (the plan is read only when a hook is among the endpoints an
  event would go to), and work again when it comes back. A member's own webhook endpoints are
  untouched: outbound webhooks stay on every plan.
- **REST hooks** (`api/public_hooks.py`, `services/api_hooks.py`, scope `webhooks:subscribe`):
  `POST /public/v1/hooks {trigger, target_url}` (201: id, trigger, address, status and the
  `signing_secret`, once), `GET /public/v1/hooks`, `DELETE /public/v1/hooks/{id}` (204).
  - *Backed by GR-04, not beside it.* A subscription is a `webhook_endpoints` row with the new
    `api_key_id` (migration 0035 (after 0034), `ON DELETE CASCADE`, partial index), described as "Zapier: new
    contact" and subscribed to one event. So delivery, Standard Webhooks signing, the retry schedule,
    the delivery log, turning an endpoint off after repeated failures (with its Activity reason and
    notification) and replays are GR-04's code, unchanged. The hooks show in Settings > Integrations
    beside the member's endpoints.
  - **Triggers to events:** `new_contact` is `contact.created`, `lead_captured` is `lead.captured`,
    `tag_added` is `contact.tagged`, `new_message` is `message.received`, `run_completed` is
    `automation.run.completed`. *"Tag added" gets removals too (one event carries `action`); the
    Zapier trigger drops them, so there is no per-endpoint filter on the server.*
  - **Rules.** The address follows the endpoint rules (https, no user name, not a private address;
    `WEBHOOKS_ALLOW_PRIVATE` allows a local one in development and e2e). Hooks do not count against
    the plan's `webhook_endpoints` (Zapier can have one per Zap); a workspace holds at most 100.
    Unsubscribing removes only a hook a key made (404 for a member's endpoint), and any key with the
    scope in the workspace may do it (Zapier unsubscribes with the connection's key, which may have
    been replaced). Revoking a key removes its hooks (C-109).
  - `GET /public/v1/me` (any valid key) returns the workspace's name, the key and its scopes: the
    Zapier connection test and its label.
- **Polling fallbacks** (Zapier uses them to test a trigger and fetch a sample; nothing new in the API
  beyond `sort=created`): new contact is `GET /contacts?sort=created`, lead captured is the same with
  `has_email=true`, tag added is `GET /contacts?tag_id=…&sort=created`, new message is `GET
  /conversations`, run completed is `GET /automation-runs`. *They are approximations of the event
  (a contact's email is not stamped with when it was captured), good enough for a sample; the real
  trigger is the hook.* Each polled item has the shape of a delivery, with an `id` per event.
- **The integration** is Zapier Platform CLI source in `integrations/zapier/` (not in the pnpm
  workspace, which lists `apps/web` and `packages/*`; no lock file, so nothing changes `pnpm-lock.yaml`).
  `package.json` (`zapier-platform-core` 16, jest and nock), `index.js`, `authentication.js` (a custom
  `api_key` field; the test call is `GET /me`, the label is the workspace's name), five hook triggers
  and two hidden ones for dropdowns (`tag`, `contact_field`), four actions (Add Tag, Remove Tag, Set
  Contact Field, Send Message), samples and output fields on each, `lib/` helpers, and jest tests in
  the CLI's pattern (`createAppTester`, nock). *Written, not installed or run.*
  - **Send Message** sends an `Idempotency-Key` from the conversation, the text and a five-minute
    window, so Zapier retrying a step does not message a customer twice; outside the 24-hour window
    the API's `reply_window_closed` text is the Zap's error.
  - **Set Contact Field** sets one custom field (empty clears it) through the same validation as the
    app.
  - Errors from the API (problem+json) become the Zap's error with the API's own words; a 401 says to
    make a new key.
- **README** (`integrations/zapier/README.md`): what it does, scopes, first run (`npm install`, `npm
  test`, `zapier validate`), pushing a private version, the manual test (captured leads to a Google
  Sheet, step by step), and the directory submission steps for the owner. The 256 px `icon.png` is
  not in the repo (resize `icon-512.png`); `zapier register` writes `.zapierapprc`.
- **Make:** *follows with the same building blocks* (the API key and scopes, the REST hooks, the
  polling lists); its own app definition is not started.
- **Not built.** Searches ("Find Contact") and "Create Contact" as Zapier actions (the API has them:
  `GET /contacts?q=`, `POST /contacts`); a per-hook event filter on the server; verifying the
  delivery signature inside the Zap (Zapier's hook URL is unguessable; the signature is there for
  other receivers).
- **Tests.** Unit `test_zapier_hooks.py` (trigger mapping, the hook routes and their scope in the
  public document, the signing secret only in the subscribe response). Integration
  `test_zapier_hooks.py` (subscribe and unsubscribe for each trigger, address rules, scope, no slot
  from the plan's endpoints, workspace isolation, a member's endpoint is never removed, revoking a key
  removes its hooks, a signed `message.received` through the real deliver step, only the trigger's
  event, retries, stopping and resuming with the plan, a member's endpoint on Free, the polling
  lists). The public tenancy walk (C-109) also calls `DELETE /hooks/{id}` with B's hook. E2E:
  `gr26-zapier.spec.ts` (subscribe a local receiver, a signed `contact.created`, the polling list,
  unsubscribe, scope, plan). Jest in `integrations/zapier/test/` (for the owner's first run).
- **Unsure / for the coordinator:** nothing to regenerate beyond C-109's (the public routes are not in
  the app's document). The jest tests and `zapier validate` have never run: expect small fixes on the
  first `npm test` (Zapier's `bundle` shapes are written from the docs). The `API_BASE_URL` default
  `https://api.socialhood.com` is a guess at the production host.

## C-111 · Website chat widget (GR-28, feature/gr-28-widget)

Decided by the owner on 2026-10-24: **PD-7**. The widget is on every plan. Free shows "Powered by
Social Hood" (a small link in the widget); Pro and Max turn it off in the widget settings. The abuse
limits below apply to all plans. *The plan's recommended option was "Pro and Max, with the link on
Free"; the owner chose to give the widget itself to every plan.* The PD table in the plan says so.

- **A `web` platform, one widget per workspace.** A widget is a `social_accounts` row of platform
  `web` (its `platform_account_id` is the public widget id, `wgt_` and 22 random characters) and a
  `widget_settings` row. One per workspace (a partial unique index), not one per site: several
  sites share it through the allowed-domains list. The first time an owner or admin opens Settings →
  Website chat, the web account is made (`GET …/widget` writes once); a disconnected one comes back
  with the same id. Visitors are contacts of that account and chats are ordinary conversations
  (platform `web`), so the inbox, filters, search, AI, analysis, leads, webhooks and the Needs you
  queue need nothing special. The account is listed with the others; Connections hides it (it is
  not a connection) and AI rules and takeover shows it like any account, so the AI mode is set
  there, not copied. Migration `0036` (after 0035): `web` in the
  platform check, `widget` in the consent source check, the unique index and `widget_settings`.
- **Adapter** (`platforms/web/adapter.py`). Capability `dm_send` only. `send_message` mints an id
  (`web_<uuid>`): the reply is already in the conversation and the widget reads it from there.
  Everything a platform with posts, comments, tokens or profiles does is `capability_unavailable`.
  Replies go through the normal send pipeline (queue, job, `sent`), so scheduled messages, AI
  replies and automations that send text work. Text limit 2,000 characters. No buttons or quick
  replies (the web has no template for them), no attachments.
- **No reply window** (`services/reply_window.py`): a page can stay open for days and nothing is
  sent through a platform that could refuse a late reply. Always `open`, so Auto mode, scheduled
  messages and automations are never blocked by a closed window. *Recorded as the plan asked.*
- **The embed and its isolation.** `<script src="https://<api>/widget.js" data-widget="wgt_…" async>`
  (`data-workspace` is accepted as an alias: the plan's name, though the value is the widget id, not
  the workspace id). The API serves three plain files from `socialhood/widget/assets/`: `loader.js`
  (2.9 KB, 1.2 KB gzipped), `frame.js` (16.2 KB, 5.1 KB) and `frame.css` (5.9 KB, 1.9 KB), about 9 KB
  over the wire in all. No framework and no build step: *not TypeScript compiled by the repo's
  toolchain*, because a new build target could not be tried here and a 16 KB script does not need
  one; they are checked with `node --check` and the e2e test. The loader adds one **iframe** from
  the API's own origin and resizes it; the chat lives inside it. *Iframe, not a shadow DOM:* a
  frame isolates scripts and CSS both ways, keeps the visitor's session out of the host page, and
  its `Content-Security-Policy` can name the sites allowed to frame it. The host page's CSP only
  needs `frame-src` for the API origin. The widget never loads the app's CSS: it has its own small
  stylesheet, its accent colour from the settings, and light and dark from `prefers-color-scheme`.
- **Allowed domains are required** (`services/widget/origin.py`). Host names without scheme or port
  (`example.com`, `*.example.com`; a pasted address is cleaned; `www.` of a bare domain is included;
  `localhost` and IPs work for testing). A new widget allows nothing, so it shows nowhere until a
  domain is added. Enforced three ways: the frame page is served only when the loader's `h`
  (`location.hostname`) is allowed and carries `frame-ancestors` naming the allowed sites, which the
  browser enforces; the session endpoint checks the same host; the visitor token carries that host and
  every call checks it again, so removing a domain or switching the widget off stops live sessions
  within one poll. *Honest limit:* the API is public, so a script outside a browser can call it with
  any host; what stops it is the rate limits and the abuse rules, not the domain list. Browser calls
  from another site are refused (`Origin` must be this server's own).
- **Visitors and tokens** (`security/widget_tokens.py`). The frame keeps a random *visitor key* in
  its own storage; the contact is keyed by `v_` and 24 hex characters of its SHA-256, so the id in
  the inbox and exports cannot read the chat. `POST /v1/widget/session` turns the key into a signed
  *session key* (6 hours; HMAC with a key derived from `TOKEN_ENCRYPTION_KEYS`, like the digest
  unsubscribe links, so no new secret and rotation works), which the frame holds in memory and sends
  as a bearer. No secret is in the page. The public routes avoid `token`, `secret` and `password` in
  field names (SEC-02), so they are `session_key` and `visitor_key`. Nothing is stored for a visitor
  who never writes; the contact and conversation are made by the first message.
- **Public API** (`/v1/widget/*`, not in the OpenAPI document): `POST /session`, `GET /messages`
  (a long poll: `version` and `wait` up to 20 s, rechecked every 1.5 s on a query that holds no
  connection while sleeping), `POST /messages` (`client_id` makes a retry idempotent), `POST /email`.
  *Real time is a long poll, not SSE or the inbox stream:* the workspace's Redis stream belongs to
  members and carries more than a visitor may see; a long poll needs nothing new, works through any
  proxy and delivers a reply within about 1.5 s of it being sent. The frame stops polling in a
  hidden tab and before the visitor has written.
- **Email and consent.** The email form is `off`, `optional` (after the first message, skippable) or
  `required` (before the first message; the API refuses a message without it). The address is
  normalised like a flow's question, set on the contact (`email_source = widget`, unverified),
  qualifies a new lead (GR-18) and fires `contact.updated`/`contact.created`. *`lead.captured` is
  not fired: it names an automation run, and there is none.* With "Ask for marketing consent" on, an
  unticked box is shown; ticked, a granted **email** consent is recorded (source `widget`, new)
  with the exact words shown, the site's host, the address and the time as evidence, as GR-14 does.
  Unticked records nothing (silence is not a refusal). Consent is for email, the channel the
  address is for.
- **Abuse limits, all plans.** Per IP a minute: 120 frame loads, 20 sessions, 40 sends, 240 polls,
  10 email forms. Per visitor: 10 sends a minute, 300 sends a day, 60 polls a minute. Message
  length 1,000 characters (the API schema allows 2,000 so the sentence comes from the rules, not a
  422 with no words). Rules (`services/widget/abuse.py`, new: the app has no DM spam detection to
  reuse; comment spam is the AI's sentiment): no control characters, at most 2 links, no run of 30
  of one character, no fourth identical message in a row. **New chats a day, by plan**
  (`widget_conversations_daily`): Free 50, Pro 500, Max 5,000; over it a visitor sees "try again in a
  little while" (429 with `Retry-After`), open chats carry on. *The numbers are proposals.*
- **Plan rules.** New entitlement `widget_remove_branding` (Free false, Pro and Max true).
  `PUT …/widget` with `show_branding: false` on Free is 402 `entitlement_required`; the choice
  stays stored across a downgrade and the visitor sees the link again (`show_branding` in the
  response is what is shown, `can_remove_branding` says whether the switch is locked).
- **Settings routes** (`GET`/`PUT /v1/w/{wid}/widget`): owners and admins. *Waiting on GR-19:* both
  should move to `require_permission` when the matrix lands (TODO in `api/v1/widget.py`).
- **Web.** Settings → Website chat (owners and admins): sites (chips), the embed code with Copy, an
  on/off switch, title, greeting, accent colour from six brand hues (`widgetAccents` in
  `styles/tokens.ts`: the widget runs on the visitor's page and needs hex values), position, a
  preview, the email form and consent, branding (locked on Free, with the upgrade dialog) and a link to
  the AI settings. One new token, `--color-web` (`#0F766E`, 5.5:1 with white), for the platform
  badge; a globe glyph; "Website" in the inbox's platform strip, the thread header, the contacts
  filter, the contact drawer and the AI settings. A website visitor has no profile elsewhere, so
  "Open in …" is hidden for them. *The theme refactor is pending: the token is one line in
  `globals.css` and `tokens.ts` to port.*
- **Not built.** Attachments, a typing indicator, read receipts and a visitor's "seen"; a page URL
  or title on the conversation (the entry source is `organic`); push or email to the visitor when
  they close the page (the email they gave could carry it later); several widgets per workspace;
  per-page rules; a custom domain for the embed; `lead.captured` for the widget form; a custom
  colour picker (only the six hues, plus an API-set colour shown as "Current colour"); minifying
  the three files.
- **Tests.** Unit: `test_widget_origin.py`, `test_widget_tokens.py`, `test_widget_abuse.py`,
  `test_web_adapter.py` (adapter, registry, window, text limit); `test_account_purge_tables.py`
  lists `widget_settings`. Integration: `test_website_widget.py` (settings and roles, the branding
  rule per plan, sessions and sites, a removed domain, the same-origin guard, expired and forged
  keys, start and receive, idempotency, email and consent, required email, spam rules, the daily
  cap, per-visitor and per-IP limits, an inbox reply reaching the widget, a waiting poll, the AI
  answer from knowledge, an escalation to Needs you, the served files and the frame policy).
  Tenancy: `tests/tenancy/test_widget_tenancy.py` (public routes across two workspaces: same
  visitor key, forged tokens, widget ids on the wrong site, deleting workspaces) and the settings
  route and `widget_settings` in `test_isolation.py`; the account deletion test seeds a row. Vitest:
  `WidgetSettingsPage.test.tsx`, `lib/widget/form.test.ts`, `PlatformGlyph.test.tsx`, a Website
  segment in `PlatformStrip.test.tsx`; the settings tab lists. E2E: `gr28-widget.spec.ts` (a test
  page served by the test on `http://localhost`, the chat to the inbox with the AI's draft, the
  reply back to the open widget, the unread badge, email, keyboard, phone width, a site not on the
  list, the settings page).
- **Unsure / for the coordinator:** regenerate the client (`WidgetSettingsOut`, `WidgetSettingsUpdate`,
  `get_widget_settings`, `update_widget_settings`, `web` in `platform` literals and `widget` in
  `ConsentSourceName`); the web types are aliases waiting for it. Migration 0036 re-chains and it
  edits the `ck_contact_consents_source` check: any other branch that recreates it must keep
  `widget`. The e2e stack needs `TOKEN_ENCRYPTION_KEYS` (it has one) and its rate limits may stay on.
  `frame-ancestors` for `localhost` allows any port over http and https.

## C-112 · WhatsApp broadcasts (GR-23, feature/gr-23-broadcasts)

- **Owner decisions (2026-10-24), recorded as decided.**
  - **PD-3, who pays Meta: the business, directly.** Each WhatsApp Business Account carries its own
    payment method (set up in Embedded Signup); no markup, no money through Social Hood. The cost on
    a broadcast is an estimate from Meta's rate card and the pages say Meta bills the account
    directly. Nothing in the product charges for a message.
  - **PD-4, plans: Pro and Max with a monthly recipient quota, none on Free.** The entitlement
    `broadcast_recipients_monthly` in `billing/plans.py`: Free 0, Pro 2,500, Max 25,000 (one line to
    change each). The 402 is the app's own: `entitlement_required` ("WhatsApp broadcasts are part of
    Pro.") on a plan with 0, `quota_exceeded` with the plan's limit and the numbers otherwise.
  - **O-11, the legal check of marketing consent in India (TRAI TCCCPR, DPDP Act): not done.** So
    GR-23 ships behind the server setting **`BROADCASTS_ENABLED`, off by default** (like GR-38's
    `AGENT_VISUALS_ENABLED`; in `.env.example` as false, on in the e2e stack and in the tests'
    fixture). Off: every broadcast route except `GET /broadcasts/availability` answers 404 "Broadcasts
    aren't available yet.", the dispatch and sweeper jobs do nothing, and the web shows nothing (the
    Automations and Activity pages hide their Broadcasts link and filter; the broadcast pages show
    one plain notice). *Turn it on in production only after O-11.*
- **A broadcast** (`broadcasts`): one approved template (marketing or utility; an authentication
  template is a one-time code and is refused) from one connected WhatsApp number to a saved segment
  (GR-17). The template's name, language, category and body are copied when it is made, so the
  preview and the estimate need no call to Meta. Each variable `{{n}}` is a contact field (first
  name, name, username, email, phone or a custom field's key) with an optional text to write when
  the person has none, or a fixed text. `first_name` falls back to "there". A field with no value
  and no fallback leaves that person out (skipped as "missing value") rather than sending a hole.
  WhatsApp's parameter rules are applied (no line breaks or tabs, no run of four spaces, at most
  1,024 characters; *unverified*). A draft can be changed (`PATCH`) and deleted; a started one can
  be paused, resumed and cancelled.
- **The audience** (`services/broadcasts/audience`). The segment's own filter, with its platform and
  number replaced by the broadcast's (*a segment saved for Instagram still means "these people, on
  this number"*), then each contact's **latest WhatsApp marketing record** decides (GR-02, latest
  `occurred_at` wins): `granted` is sent to; `revoked` is skipped as `opted_out`; no record is
  skipped as `no_consent` (not knowing is not agreeing). Skipped contacts are rows with their
  reason, counted on the page and never sent. The audience is fixed when the broadcast **starts**
  (up to 30,000 contacts; a bigger segment is refused), and each person's consent is checked again at
  their turn, so a STOP between the two still wins.
- **Preview** (`POST /broadcasts/preview`): the counts (matching, eligible, opted out, no consent,
  missing value), the cost, the quota left, the number's daily limit and how many days that means,
  the message drawn with a sample contact, and the sentences that stop it being sent. It is the same
  audience code the send uses.
- **Cost estimate** (`services/broadcasts/rates.py`): Meta's rate card as data (India, INR, per
  message by category: marketing 0.7846, utility and authentication 0.1150) with its `as_of` date
  and `verified = False`. **The figures are unverified**: typed in by hand, not read from Meta,
  and Meta revises its rates. Update `RATE_CARD` when its pricing page changes; the pages say "typed in
  by hand, not yet checked against Meta" while it is unverified. An unknown category is priced as
  marketing (the dearest). The estimate is stored on the broadcast when it starts.
- **Schedule.** `POST /broadcasts/{id}/start` with no time sends now; with `scheduled_at` (a time
  zone is required, at least a minute and at most 90 days ahead) it schedules, and the quota is
  checked then too. The minutely job `run_broadcasts` starts the ones that are due: it fixes the
  audience, and a broadcast whose number or segment is gone, or that has no one left to send to,
  becomes `failed` with the reason and tells the owners and admins. A scheduled broadcast does not
  call Meta when it starts: a template withdrawn since then fails each message with WhatsApp's own
  reason.
- **Sending and throttling** (`services/broadcasts/dispatch`, `throttle`, job `dispatch_broadcast`).
  - A batch hands up to 60 waiting people to the normal send queue (`sending.queue_outbound` with
    the template, source `broadcast`, so the send job, token bucket, retries, statuses, inbox and
    realtime all work as for any message), then the job queues itself a minute later: about 40
    minutes for 2,500 people. *Source `broadcast` is new on `messages` (migration widens the check),
    so the inbox says "Sent as part of a broadcast" and Activity words it.*
  - **Idempotent per recipient**: the message's client id is derived from the recipient's id, rows are
    locked (SKIP LOCKED) while a batch works, and the state of each recipient is the progress, so a
    retried or stalled job sends nobody twice and a lost job is picked up by the minutely sweeper.
  - **Pacing to the tier**: the number's daily limit by messaging tier (50, 250, 1,000, 10,000,
    100,000, unlimited), 90% of it usable, less the people already messaged by broadcasts in the last
    24 hours (the room is counted from `dispatched_at`; WhatsApp counts unique people in a rolling 24
    hours, *unverified*). At the limit the next batch waits until the oldest message leaves the
    window. **When the tier is not known the default is 250** (conservative), and the preview says
    so. The tier and quality come from `whatsapp_number_health`, read from the number
    (`adapter.get_number_health`: `quality_rating`, `messaging_limit_tier`; *unverified*) when it
    has not been read for 30 minutes, and from the webhook below. An unknown rating never replaces a
    known one.
  - **Pause on a quality drop**: the `phone_number_quality_update` webhook (FLAGGED, UNFLAGGED,
    UPGRADE, DOWNGRADE, ONBOARDING; *unverified*) names the WhatsApp Business Account, not the number
    (no `metadata.phone_number_id`), so it is routed by `social_accounts.waba_id`
    (`webhooks/routing.resolve_waba_accounts`) to each of its numbers connected here. FLAGGED is rating
    Low (red); UNFLAGGED is taken as Medium until the number is read again. A sending broadcast
    **pauses with a plain reason** when the rating falls to Medium or Low, when it is Low at a batch,
    or when the tier is lowered. The owners and admins get an in-app notification
    (`broadcast_paused`) and Activity shows it with a link. **The owner resumes**; resuming while the
    rating is Low is refused (409) with the reason.
  - Other pauses, each with its own sentence and code: `member` (the owner paused), `plan` (the plan no
    longer has broadcasts), `limit` (the month's recipients ran out), `account` (the number needs
    reconnecting or cannot send templates). A recipient the queue refuses for its own reason is
    marked failed with the reason and the batch carries on.
- **Per-recipient status.** Not stored twice: a recipient shows queued, sent, delivered, read,
  failed or skipped **from its message** (`repositories/broadcasts.status_expr`), so WhatsApp's
  delivery statuses (`whatsapp_status.apply_status`, which never moves a status backwards) are the
  only thing that changes it. A failure's reason is the existing mapped wording (a number that is
  not on WhatsApp is "This person can't receive messages right now."); an unmapped code shows
  WhatsApp's own reason. `replied_at` and `stopped_at` are set by ingest. The detail page has the
  counts at each stage, a progress bar, and the audience in pages of 25 with a status filter; it
  polls every 5 seconds while sending.
- **STOP** (`services/broadcasts/stop`, `inbound`). A WhatsApp text that is **only** a stop phrase
  revokes marketing consent: a `revoked` record, source `stop_reply`, evidence `{message_id, text}`.
  It is recorded even when the contact had no consent on file, and a record in the same second as a
  grant still wins (WhatsApp stamps messages to the second). The list, in one place (the module's
  docstring and `PHRASES`): English (stop, stop all, unsubscribe, unsub, opt out, optout, cancel, end,
  quit, remove me, no more messages, do not / dont message me or contact me, stop messaging me),
  Hinglish (band karo, band kar do, mat bhejo, msg mat bhejo, bhejna band karo, nahi chahiye ...)
  and Hindi (the same in Devanagari), after lower-casing, dropping punctuation, emoji and polite
  fillers (please, pls, kindly, thanks, kripya ...). The whole message must match, so "please don't
  stop the delivery" does not. *The list is the usual set, not a legal one (O-11 covers wording).* No
  confirmation message is sent back. A message within seven days after a broadcast message counts as
  a reply to it.
- **Quota rule**: a recipient counts when its message is handed to the send queue in the current
  billing period (the subscription's anchor day, as for credits), failures after that included,
  skipped contacts and hand-over failures never. Starting or scheduling a broadcast that would not
  fit is refused with the numbers; one that runs out while sending pauses (`limit`).
- **Activity (GR-05).** Failed broadcast messages are Activity's "A broadcast message to X wasn't
  sent" with the reason; a new `broadcast` kind lists paused and failed-to-start broadcasts with the
  reason and an action to open the broadcast. **Contact timeline (GR-17)**: "Received broadcast X"
  with how far it got (Sent, Delivered, Read, Couldn't be delivered).
- **Sandbox WhatsApp number** (`platforms/sandbox/whatsapp.py`). `POST /dev/sandbox/accounts?platform=whatsapp`
  connects a fake number (`sandbox_` phone number id, `sandbox_waba_` business account) whose
  adapter lists four approved templates (two marketing, one utility, one authentication), records
  template sends (a parameter containing `[sandbox:fail=<code>]` fails that send) and reports its
  tier. `POST /dev/sandbox/inbound` takes, for such a number, `dm` (a customer's WhatsApp message),
  `status` (a delivery status for the last message sent to `from_id`: `delivery_status`,
  `error_code`, `error_text`) and `quality` (`quality_event`, `tier`), as the webhook bodies Meta
  would deliver, through the real intake. The e2e stack has a seed route to put a workspace on a plan.
- **API** (owners and admins, through GR-19's automations permission for reads and
  writes): `GET /broadcasts/availability`, `GET /broadcasts`,
  `POST /broadcasts/preview`, `POST /broadcasts`, `GET|PATCH|DELETE /broadcasts/{id}`,
  `GET /broadcasts/{id}/recipients?status=&limit=&offset=`, `POST /broadcasts/{id}/start|pause|resume|cancel`.
  A number, segment or broadcast of another workspace is 404 `not_found` before any plan check.
- **Migration 0037** (after 0036), expand-only: `messages.source` accepts
  `broadcast`; tables `broadcasts`, `broadcast_recipients` (`uq_broadcast_recipients_broadcast_id_contact_id`)
  and `whatsapp_number_health` (`uq_whatsapp_number_health_social_account_id`). All three reference the
  account, so the account purge deletes them (children first); the purge test's list, the
  account-deletion seed and the tenancy test's table list and seeds include them.
- **Web.** `/w/{slug}/broadcasts` (list with the month's quota meter, a note that Meta bills the
  account directly), `/new` (the composer: number, segment, approved template, a row per variable,
  send now or schedule in the workspace's time zone, a live preview with the audience, the skipped
  and why, the sample message, the estimate and the number's daily limit, and a confirmation) and
  `/{id}` (counts, progress, the reason it paused with Resume, Pause, Cancel and Delete, the
  message and its mapping, the estimate, and the people with their status). Shown only through a
  "Broadcasts" button on Automations when the setting is on. Owners and admins. Stacked cards and
  rows, so it works at 375 px.
- **Not built.** An outbound webhook event for broadcasts (GR-04's catalogue); a STOP
  acknowledgement message; a re-engagement of people with no consent record; a template's media
  header, buttons with variables and named parameters (the same limits as the template picker);
  editing a broadcast after it started; a CSV of the results; Instagram broadcasts (no API).
- **Unverified (Meta), everything above that says so:** the rate card's figures; the messaging tier
  names and limits and that the limit is unique people in a rolling 24 hours; the quality rating and
  tier fields of the phone number; the `phone_number_quality_update` event names and its routing by
  business account; that FLAGGED means rating Low; WhatsApp's parameter rules. Only a real number
  settles them.
- **Tests.** Unit: `test_broadcast_stop.py`, `test_broadcast_throttle.py`, `test_broadcast_rules.py`
  (variables, the rate card, the plan's numbers), the purge list. Contract: `test_whatsapp_health.py`
  (the health parsers and the sandbox bodies through the real WhatsApp parsers). Integration:
  `test_broadcasts.py` (the setting off, the plan, preview, create, schedule, the sandbox broadcast
  to three with each status and the opted-out one skipped, STOP, pacing, the quality pause and resume,
  the month's recipients, Activity and the timeline, roles, the job). Tenancy: the new routes, bodies
  and tables in `test_isolation.py` (the walk turns the setting on). Vitest: `BroadcastComposer`,
  `BroadcastDetailPage`, `BroadcastsPage`, `lib/broadcasts/format`. E2E: `gr23-broadcasts.spec.ts`.
- **Unsure / for the coordinator:** regenerate the client (the new schemas, 10 operations, the
  `broadcast` message source, activity kind and timeline kind, the `platform` query on
  `create_sandbox_account`, and `status` and `quality` plus four fields on `SandboxInbound`); the web
  types are aliases waiting for it, and the web calls the paths through the typed client, so typecheck
  after regenerating. Decimal fields (`per_message`, `total`, the rate card) arrive as strings and the
  web formats them. For production the Meta app's WhatsApp webhook needs the
  `phone_number_quality_update` field subscribed (*unverified* that it is delivered to the same
  callback as `messages`). `BROADCASTS_ENABLED` belongs on in staging only until
  O-11.

## C-113 · Combined GR batch E: integration fixes between the GRs (feature/gr-batch-e)

Each GR was written on its own base, so these only showed once they were stacked. None changes a
migration: `ck_automation_runs_one_trigger` is still the 0007 definition and was never altered.

- **Widget frame policy (GR-28 against the security headers).** The outermost middleware replaced
  every response's `Content-Security-Policy` with `frame-ancestors 'none'`, which erased the widget
  frame's own list of allowed sites. The middleware now keeps the app's policy on `/widget/frame`
  when the route set one (a refusal without one still gets `'none'`); every other route keeps `'none'`.
- **Private reply length (GR-29).** `PrivateReplyCreate.text` was capped at 1,000 characters in the
  schema, so a Page's 2,000-character limit never reached the service's per-platform check. The schema
  now only bounds the body (4,096) and the service enforces the account's own limit. The OpenAPI
  `maxLength` of that body changes, so the client is regenerated.
- **A re-delivered Messenger message is `processed`, not `ignored`.** The Facebook handler gives the
  same status as Instagram's for a replay (ingest stores nothing and records no reason), so the
  GR-29 test expected the wrong status; it still asserts that nothing new is stored.
- **A Page's webhook payloads are deleted with its data.** The purge (C-067) deletes `webhook_events`
  routed to the account whatever the provider; the GR-29 test asserted they remained. Now it asserts
  none do.
- **Tests, not behaviour.** `Ws.call` merges extra headers instead of passing `headers` twice;
  `make_run` borrows a message when a seed names no trigger (the one-trigger check holds);
  the sheets `capture_email` helper picks the still-queued question when called twice in a test; a
  public-API send outside the window uses 8 days because the sandbox account has Human Agent (7 days);
  the DM keyword test sends the message the run queues; a Page test needs Pro for four active
  automations (Free includes three); the tenancy walk lists `/public/v1/me` with the other routes that
  name no id (it still must show none of B's data); Idempotency-Key needs 8 characters.

## C-114 · Instagram Story scheduling (GR-39, feature/gr-39-30-stories-fb-publishing)

- **A Story is a choice, not a shape.** One image or one video could be an image post, a Reel or a
  Story, so the composer sends `kind: "story"` (`ScheduledPostDraft.kind`, default `post`) and the
  stored `scheduled_posts.format` becomes `story` (`derive_format(..., story=True)`). Exactly one
  image or video makes a Story; two or more files are refused ("A Story is one image or one
  video."), so a Story can't be a carousel. Duplicate keeps the format.
- **No caption.** The caption and first comment stay on the draft (switching back to Post brings
  them back) but are never sent: `_caption` returns "" for a Story, the container body has none, and
  no first comment job is queued. The checklist replaces the caption, hashtag and mention checks with
  one passing line, "Stories are published without a caption".
- **Container.** `POST /{ig}/media` with `{media_type: "STORIES", image_url | video_url}`, then the
  same status polling (videos process like Reels, images are FINISHED) and `media_publish`. A lost
  publish answer is found again in `GET /me/stories` by time (`/me/media` does not list stories; a
  Story has no caption to match on), and the new Story is read back with the story fields only
  (`id,media_type,media_url,thumbnail_url,permalink,timestamp`). New adapter method
  `create_story_container`; `get_published_media` and `find_published_media` take `story`.
- **Validation.** Videos 3 to 60 seconds (refused outside, even though a Reel may run 90 s); image
  size and format as for posts; any shape passes, with a note on the media line when the file is not
  about 9:16 ("9:16 fits a Story best. Instagram may crop or add bars to this file."). A Facebook Page
  target of a Story is refused on `targets.{i}` ("can't publish Stories"). Quota: a Story is a
  scheduled post like any other (`scheduled_posts_monthly`, once per billing period, C-043) and
  counts in the 24 hour publishing limit the checklist shows.
- **Errors.** `STORY_REASONS` re-words 2207004, 2207005, 2207009, 2207026 and 2207052 for a Story
  (size, format, shape, link); every other known subcode keeps its reason from C-043 and an unknown
  one falls back to the generic reason. The processing timeout names the account's platform
  ("Instagram took too long to process the video"). The failure notification says "Your Story".
- **After publishing.** The `media_items` row has `media_type = story` (no "next post" automation
  links to it, as before). The live-stories route (`GET /stories`, the story-reply picker) reads
  Instagram, so the new Story appears there on its own; the sandbox now lists its published stories
  (24 hours) before the two seeded ones, and keeps them out of feed posts. Each published Story target
  carries `expires_at` (published time + 24 hours), which the composer's banner shows ("Disappears
  Wed 10:00").
- **Web.** A "Type" section (Post | Story) in the composer; with Story chosen the caption and first
  comment sections are hidden, the media tray stops asking for crops and checks 3 to 60 s, the
  preview becomes a 9:16 phone ("Story preview") and the format pill says Story. The List, Agenda and
  calendar show a "Story" badge, and name the post "Story" instead of "No caption yet".
- **Story insights: not built.** The insight metrics for stories exist (`STORY_METRICS`), but
  `snapshot_post_metrics` leaves stories out on purpose (the windows are 1 h to 72 h, a Story is gone
  after 24 h) and the analytics reads skip them. Fetching reach and replies needs its own early
  windows; left for a follow-up.
- **WhatsApp Status** has no API, so it is out of scope.
- **Unverified (Meta), until a real account publishes a Story:** that `media_type: STORIES` with
  `image_url` or `video_url` is accepted under Instagram Login; that images must be JPEG and at most
  8 MB; the video limits (3 to 60 seconds, 100 MB, MP4 or MOV) and that 9:16 is recommended, not
  required; whether Stories count against `content_publishing_limit`; whether `GET /{id}` takes the
  story field list and `GET /me/stories` lists a Story right after publishing; the Story-specific
  error subcodes (we know no subcode that is only for Stories, so `STORY_REASONS` re-words general
  ones); that `me/stories` timestamps allow the time match used for a lost answer.
- **Migration 0038** (after 0037), expand-only: `ck_scheduled_posts_format` accepts `story`
  (downgrade turns stories back into drafts without a format).
- **Tests.** Unit: `test_story_scheduling.py` (format, checklist, container bodies, error wording,
  the lost-answer lookup, the sandbox lifecycle and the expiry). Integration:
  `test_story_publishing.py` (kind and format, the carousel and length refusals, the Facebook Page
  refusal, the plan quota, schedule to publish to media item, the video wait, a failed Story and its
  notification, a lost answer, the live story list). Vitest: the checklist, the composer's Story
  mode, the preview. E2E: `gr39-story-scheduling.spec.ts`.
- **For the coordinator:** regenerate the client (`PostFormatName` gains `story`,
  `ScheduledPostDraft.kind`, `ScheduledPostTarget.expires_at`); the web reads `kind` and `expires_at`
  from the generated types.
- *Added in the combined batch:* the composer's choice is stored as `scheduled_posts.kind` (`post` or `story`, default `post`, in migration 0038) instead of being read from `format`. A Story draft with the wrong media has no format yet and was checked as a carousel once saved; now it keeps its Story checks, duplicating a Story copies the kind, and a check ties `format = 'story'` to `kind = 'story'`. Responses carry `kind`; the web reads it.

## C-115 · Facebook publishing and best posting times (GR-30, feature/gr-39-30-stories-fb-publishing)

- **One composer, Pages included.** A Facebook Page shows in the composer's Accounts beside
  Instagram accounts (tagged "Facebook Page"); choosing both posts to both at once (the composer
  already took up to 10 accounts; the preview gets an account switcher when the platforms differ and
  a Facebook-style preview for a Page). Pages also appear in the Schedule page's account filter and
  colours. The publish jobs, states, retries, failure reasons and notifications are the same ones
  (`services/post_publishing`); only the platform calls differ.
- **Permission.** The Page connect now asks for `pages_manage_posts` (`oauth.SCOPES`). A Page
  gets `Capability.PUBLISH` only if that scope is on the account, so a Page connected before this
  must be reconnected ("Reconnect to allow publishing", the same wording as Instagram). Sandbox Pages
  can always publish. `read_insights` is still not asked for.
- **Containers are references** (`platforms/facebook/publishing.py`): Facebook has none, so the
  adapter returns `photo:{id}` (an unpublished `POST /me/photos`), `photos:{id,id}` (the parent of 2
  to 10 photos, no call), `video:{id}` (an unpublished `POST /me/videos` with `file_url`, polled with
  `GET /{id}?fields=status`) or `text:post`; `publish_container` then posts it: photos as
  `POST /me/feed` with `attached_media`, a video with `POST /{id}` `{published: true}`, text as
  `POST /me/feed` `{message, link?}` (the first URL in the text becomes `link`). The adapter
  protocol gained `create_text_container`, and `publish_container` takes the post's `caption` (the
  jobs pass it; Instagram ignores it).
- **Our scheduler, not Meta's.** Every call publishes at once; `scheduled_publish_time` is not used,
  so Social Hood's states, retries, calendar and Activity stay the one source of truth and a Page
  post can be moved or canceled until the moment it publishes. *No good reason found to use Meta's.*
- **Formats.** The same derived formats (one photo, one video, 2 to 10 photos), plus **text**
  (`scheduled_posts.format = text`, migration 0039): no media, a caption, only when every account is
  a Page. A Page video is a normal Page video (media item type `video`, not a Reel). The checklist is
  per platform (`TargetFacts.platform`): a Page takes any photo shape (4:5 to 1.91:1 is Instagram's),
  refuses photos mixed with a video ("A Facebook post can have several photos or one video, not
  both."), has no hashtag or mention limit and no publishing limit; text for a post that also goes
  to Instagram is refused ("Add an image or video."); a Story cannot go to a Page. *Deviation:* the
  2,200 character caption limit stays for Pages too (the column check and the API schemas share it);
  Facebook allows far more, so lifting it is a later change.
- **Lost answers are not retried on a Page.** Instagram can tell from the container's `PUBLISHED`
  status that a lost publish answer went out; a Page post has no such state, so a `delivery_unknown`
  ends the target as unconfirmed ("We couldn't confirm Facebook published this post. Check ...
  before trying again.") instead of publishing again. A worker that dies between Facebook accepting
  the post and our storing it could still publish twice on the sweeper's retry (a window of
  milliseconds; no cheap fix). Reasons are mapped for Facebook error codes 200, 324, 368 and 506;
  anything else falls back to the generic reason.
- **Not built: Page Stories** (`/photo_stories`, `/video_stories`). They need their own two step
  upload, and there is no read API to list them for the story picker. The composer says Pages can't
  publish Stories. Also not built: Facebook Reels, Meta's own scheduling, post insights for Pages
  (`get_media_insights` still raises `capability_unavailable`).
- **Best times.** `GET /social-accounts/{id}/best-times` (owners and admins, like posting times;
  another workspace's account is 404) returns a suggested hour per weekday (`BestTimes`). It is
  computed in `services/scheduled_posts/best_times.py`, cached in Valkey for 6 hours per account, and
  never by an AI model. **Method:** the account's last 90 posts of the last 180 days (stories left
  out) with a known engagement (the latest snapshot's likes + comments + shares + saves, else the
  live like and comment counts, so a Page without insights works); each post is scored against the
  account's median post; posts are grouped by weekday and hour in the workspace time zone; an hour
  needs 2 posts, and a weekday gets the hour with the best median score (the earlier on a tie);
  fewer than 10 scored posts: `enough_history` false and no suggestion ("not enough history").
  `lift_percent` is how far the hour beats a typical post (null when the median is 0). The
  constants are at the top of the module.
- **Web.** The time picker shows the best time for the chosen weekday with a "Use 18:00" button (or
  the top three days to start from, before a day is chosen) and says when there is not enough
  history; the Posting times drawer lists the suggestion per weekday with an "Add" button. Both read
  the cached route.
- **Migration 0039** (after 0038), expand-only: `ck_scheduled_posts_format` accepts `text`
  (downgrade turns text posts back into drafts without a format). No new tables; the best times
  need none.
- **Unverified (Meta), until a real Page publishes:** JSON bodies on `/photos`, `/videos` and
  `/feed` (Meta's examples are form encoded, and `attached_media` is documented as a list of JSON
  strings); `file_url` on `graph.facebook.com` rather than `graph-video.facebook.com`; that an
  unpublished video is published by `POST /{id}` with `published: true`; the `status.video_status`
  values (`ready`, `processing`, `uploading`, `error`, `expired`); that `GET /{post-id}` and the video
  fields in `VIDEO_FIELDS` return a permalink (a video's is relative); the `link` field's preview
  behaviour; the error codes 200, 324, 368 and 506 and their reasons; that `pages_manage_posts` is
  enough (App Review: O-10); that a post id has `_` and a video id is a bare number (how the read
  back tells them apart); `POST /{id}/comments` for a Page's own first comment.
- **Tests.** Unit: `test_facebook_publishing.py` (the permission gate, every call body, the video
  status, errors, the read back, the per-platform checklist, the best-times arithmetic with the
  zone, the minimum bucket, too little data and a zero median); `test_facebook_platform.py` updated
  (Pages publish, no insights). Integration: `test_facebook_publishing.py` (text, photos, video,
  no limit, first comment, a refused post and its notification, a lost answer never published twice,
  a Page without the permission; the composer API per platform; the best-times route: too little
  history, the busy weekday, a Page from its counts, the time zone and the cache, 401 and 404);
  `test_facebook_connect.py` updated. Tenancy: the new route has an account id, so the walk covers
  it. Vitest: the best-times helpers and components, the Page checklist, the account picker, the
  preview, the composer. E2E: `gr30-facebook-publishing.spec.ts`.
- **For the coordinator:** regenerate the client (`BestTimes`, `BestTimeDay`, the `get_best_times`
  operation, `PostFormatName` gains `text`); the web types are aliases waiting for it. The Meta app
  needs `pages_manage_posts` added to the Facebook Login permissions for production (O-10). Roles:
  the route uses the same `Admin` dependency as posting times; there is no member-role integration
  test for it (none exists for posting times either).

## C-116 · Product catalogue (GR-31, feature/gr-31-catalogue)

Products with variants, added by hand, by CSV or from Shopify; the AI answers price, stock and link
questions from them; a flow step sends a product. **PD-8 is decided: commerce is on Pro and Max, not
Free.** *Every Shopify behaviour below was written from Shopify's documentation and none has run
against a real store: it waits for the owner's Partner account and app listing (O-10). Each one is
marked unverified and listed in `docs/verification.md` item 37.*

### Decisions
- **PD-8 in code.** `ENTITLEMENTS["commerce"]` in `billing/plans.py` (Free off, Pro and Max on; one
  line to change). Adding, changing, deleting, importing and syncing products, connecting Shopify and
  saving a flow with a product step are refused with 402 `entitlement_required` ("The product
  catalogue is part of Pro."). **Reading is never refused**: the list, a product and the Shopify
  status answer on Free, and products that exist still answer customers and run in flows after a
  downgrade (a flow's *saving* needs Pro; a saved one keeps working). Webhooks from Shopify are
  ignored on a plan without the catalogue.
- **Caps** (proposed, `billing/plans.py`; one line each): `catalogue_products` Pro 1,000, Max 20,000
  (counted live; a Shopify sync skips what doesn't fit and says so), `catalogue_import_rows` Pro 500,
  Max 5,000 lines in one CSV file (402 `quota_exceeded` before anything is read further). A file is
  at most 900,000 characters (the API's 1 MB body limit), sent as JSON text.
- **Money.** An ISO 4217 code per product and integer minor units (`services/catalogue/money.py`:
  0, 2 and 3 decimal currencies). The default currency is the connected Shopify store's, else the
  newest product's, else INR (the workspace has no currency of its own). Requests carry prices as
  text ("799.50", checked against the currency); responses give `price_minor` and the same text. The
  web formats with Intl.
- **Stock.** `null` means "not recorded", which is not 0. The AI is told "stock not recorded" and
  must say it doesn't know; a flow's message mentions stock only when it is recorded; the list says
  "Not tracked". Shopify variants whose inventory isn't tracked are stored as not recorded.
- **Where it lives in the app.** A **Products** page under **Grow**, after Knowledge (owners and
  admins, like Knowledge; a direct link from an agent explains). The Shopify card is on that page
  (`/w/{slug}/products?shopify=<nonce>` is the OAuth return), not in Integrations: it is about
  products. Without the plan the page says so and Add, Import and Connect open the upgrade dialog.
- **Permissions (GR-19).** Writes use `CanManageKnowledge` (products are what the AI may say);
  the Shopify connect, complete, sync and disconnect use `CanManageIntegrations`. Reads use `Admin`.
  No new permission.
- **No prompt version bump.** The catalogue is a `PRODUCTS` section next to `KNOWLEDGE` in the
  contents, with its own rules in its header (quote exactly as listed, only for what is listed,
  "stock not recorded" means you don't know), so `suggest.v3` and the tests that pin it are
  unchanged. The existing rule "never state a price, stock level... or link not in KNOWLEDGE" covers
  it.

### Data (migration 0040, after 0039, expand-only)
- `products` (name, description, SKU, currency, `price_minor`, `stock`, `url`, `image_asset_id`,
  `image_url`, `active`, `source` manual/csv/shopify, `external_id`, `search_text`), `product_variants`
  (title, `options` JSON up to 3, SKU, `price_minor`, `stock`, `position`, `external_id`) and
  `shopify_connections` (one per workspace, one store per workspace: unique `shop_domain`; the token
  encrypted like every platform token). Unique: SKU per workspace on products and on variants, Shopify
  id per workspace, variant title per product. `webhook_events.provider` accepts `shopify`.
- A product with variants is priced per variant; its own price and stock are only the form's default.
  A product may have up to 100 variants (the rest of a Shopify product's are counted and dropped).
- *No table references `social_accounts` or contacts, so the account purge, `seed_account` and the
  purge tables test need no change.* The tenancy walk got a seeded product, variant and store, three
  `B_TABLES` and the example bodies of the new routes.

### Routes (all `/v1/w/{wid}`, `api/v1/catalogue.py`)
`GET/POST /products`, `GET/PATCH/DELETE /products/{product_id}`, `POST /products/import/preview`,
`POST /products/import`, `GET /integrations/shopify`, `POST .../connect`, `POST .../complete`,
`POST .../sync` (202), `DELETE /integrations/shopify?keep_products=`. Public: `GET
/v1/oauth/shopify/callback` and `POST /webhooks/shopify`. A request naming another workspace's
picture or product is a 404 *before* any plan check, so the isolation walk (a Free workspace) proves
isolation. A `PATCH` replaces the variant list: a variant with its id is kept (so a flow step that
names it keeps working), one without is new, one left out is removed.

### CSV import
- **Header row** (any order and case; `name` and `price` required, other columns ignored and
  listed): `name, description, sku, variant, option1_name, option1_value, option2_name,
  option2_value, option3_name, option3_value, price, currency, stock, url, image_url, active`. The
  starter file is downloadable from the dialog; the dialog and `csv_import.py` document the rules.
- One line is a product or one variant of it; lines with the same name (ignoring case) are one
  product. **Upsert** by SKU (a product's or a variant's), else by product name and variant name; a
  match is updated, the rest created. A blank cell never clears a value; variants the file doesn't
  mention stay. A variant's SKU on a line with no variant is an error, a currency different from the
  saved product's is an error ("change it in the product first"), a SKU twice in a file is an error.
- **Preview before saving** (`POST /products/import/preview`): every line is New, Update or Left
  out with the reason (first 500 shown, the counts cover all). The import re-reads the same text, so
  the preview can't go stale. Lines with problems are skipped; the rest are saved. Semicolon and tab
  files and a byte order mark are read.

### The AI
- `services/catalogue/facts.py`: a question is matched to products by words (no embeddings): lower
  case, a plural "s" dropped, filler removed (English and the Hinglish customers write: price,
  kitna, hai...). A product matches when a question word is in its name or is its SKU; the variants
  whose title, options or SKU hold the most question words are marked "matches the question".
  Up to 3 products, 20 variants each, active products only. Candidates come from `products.search_text`
  (a lower-case column kept by the service), ranked in Python (`rank` is pure and unit tested).
- It feeds the suggest prompt (`drafting.render_contents`), the Knowledge test box and Ask Social
  Hood's answer_from_knowledge. The model cites `p1`..: the product's id is stored in
  `reply_suggestions.used_chunk_ids` (the column has no foreign key) and `top_similarity` becomes
  1.0, so **Auto mode treats a cited product as grounded** (check 11) and re-checks the reply's links
  against the product's lines (`knowledge_port.product_texts`). A reply may quote a product's link
  (the output filter's allowed texts include the lines offered); an invented link is still
  withheld. *The filter checks links, emails and phone numbers, not prices*: a wrong price is
  prevented by exact lines and the prompt rule, not by a check. *Not built:* a price check in the
  output filter (it would flag a price the customer typed, or a discount in knowledge).
- Ask: `search_products` (admin role, read) returns each product's variants with price, stock text
  and link, marking the variants the words name; it falls back to a plain text search (switched-off
  products included, labelled) and says when nothing matches. New answer-ref kind `product` (opens
  Products).
- E2E worker (`apps/api/scripts/e2e/worker.py`): the fake AI answers from the marked PRODUCTS line,
  as a faithful model would. The done-when ("price of the blue kurta in M?" gets INR 799.00 and the
  link, from Suggest or Auto) is `tests/integration/test_catalogue_ai.py` and `gr31-catalogue.spec.ts`.

### Flow step "send product"
`type: "product"` (`product_id`, optional `variant_id`, `intro` up to 300 characters, `next`). It
reads the catalogue when it runs and sends one message: the intro, then `Name - Variant`, the price
(`INR 799.00`), "In stock" or "Out of stock" only when stock is recorded, and the link. With no
variant chosen it sends the product (its price, or up to six variants with prices). Cut to 900
bytes for Instagram. The product's uploaded picture goes as the message's attachment.
- *Deviations from "name, price, image and link as the send step does":* the link is in the text, not
  a button (the text always carries it, and buttons differ per platform); a picture that is only an
  address (Shopify, CSV) can't be attached (attachments are media-library files), so the link in the
  text stands in for it. WhatsApp catalogue messages are GR-33.
- Fails with a plain reason ("The product was deleted or switched off, so nothing was sent." /
  "...variant was deleted...") like a deleted saved reply: the step is logged failed and the run ends.
- Activation checks the product exists, is on, and that the variant belongs to it; saving needs the
  plan. A product step after a comment's private reply is refused like any message. The editor adds a
  **Product** step with a product picker (read from the catalogue) and a variant picker.

### Shopify (built like GR-29 Facebook and GR-27 Sheets)
- **Off by default.** `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET` (also signs webhooks and the install
  redirect), `SHOPIFY_REDIRECT_URI`, `SHOPIFY_SCOPES` (default `read_products`), `SHOPIFY_API_VERSION`
  (default 2025-07); unset, connecting answers 503 "Shopify isn't set up on this server." and the
  webhook route 503. `SHOPIFY_PROVIDER=fake` is a built-in store (a kurta with colour and size
  variants, a scarf with untracked stock, a draft jacket) for development and the e2e stack, its
  products in Redis; refused in production.
- **Connect.** `POST .../connect {shop}` (only `*.myshopify.com` is ever called; "my-store" works)
  returns the install address with a single-use state; the public callback checks Shopify's `hmac`
  over the sorted query (not for the built-in store), parks the code under a one-time nonce bound to
  the member and workspace (X-1, as Instagram and Google) and redirects to Products with `?shopify=`;
  `POST .../complete` exchanges it, saves the connection (token encrypted), subscribes the webhooks
  and starts the first sync. A store belongs to one workspace (409 `account_in_use`).
- **Sync** (`sync_shopify_products`, bulk lane, recovery RETRY): Admin GraphQL, 50 products a page;
  each is saved by Shopify id with variants (a single "Default Title" variant is a plain product);
  a product no longer in the store is removed after a pass that read them all; a SKU another product
  uses is dropped (Shopify allows duplicates); a picture uploaded here is kept; prices are in the
  store's currency. A pass beyond the plan's products skips the rest and says so on the card.
- **Webhooks** (`products/create|update|delete`, `app/uninstalled`, and the mandatory privacy
  topics `customers/data_request`, `customers/redact`, `shop/redact`): `POST /webhooks/shopify`
  verifies `X-Shopify-Hmac-Sha256` over the raw bytes, stores the event once (`shopify:{webhook id}`)
  and a job applies it through the same save the sync uses (`services/webhook_handlers/shopify.py`).
  `app/uninstalled` marks the store "needs reconnect"; `shop/redact` deletes the store and its
  products; the customer topics change nothing (no customer data is held).
- **Disconnect** revokes the token (best effort) and removes the store and, unless asked to keep
  them, the products it made: a price no longer kept in step must not be quoted.
- **Unverified (Shopify), until a real store connects:** the install and token endpoints and the
  `hmac` rule (sorted decoded parameters, hex); that `read_products` is enough for stock (it may need
  `read_inventory`); the GraphQL fields (`products`, `variants`, `inventoryQuantity`,
  `inventoryItem.tracked`, `onlineStoreUrl`, `selectedOptions`, `shop.primaryDomain`) and API
  version; `webhookSubscriptionCreate` with these topics and how it reports an existing subscription
  (read here as an error containing "already"); the webhook payload shape (`variants[].option1..3`,
  `options[].name`, `inventory_quantity`, `inventory_management`) and headers; that a listed app
  must answer the three privacy topics this way; `DELETE /admin/api_permissions/current.json` to
  revoke; the storefront link built from `handle` (`onlineStoreUrl` when GraphQL gives it; a custom
  domain comes from `shop.primaryDomain`); whether `app/uninstalled` arrives for a custom app.

### Tests
Unit: `test_catalogue_money_csv.py` (money, header, per-line problems, grouping, currency),
`test_catalogue_facts.py` (words, ranking, the prompt lines, the output filter with a product link,
the drafting prompt, the flow message), `test_shopify.py` (store address, both signatures, both
product shapes, the mapping, the built-in store, the flow step's activation); registry test updated.
Integration: `test_catalogue.py` (plan gate, caps, money, variants by id, SKUs, search, roles, a
foreign picture, audit), `test_catalogue_import.py` (preview, import, upsert by SKU and by name and
variant, blank cells, caps), `test_catalogue_ai.py` (Suggest, Auto, an invented link, a switched off
product, the test box, `search_products`), `test_flow_product.py` (running, saving, activating),
`test_shopify.py` (connect, nonce, signatures, sync, caps, webhooks, disconnect); tenancy updated.
Vitest: `format`, `flow` (the step), `ProductsPage`, `ImportDialog`, `ShopifyCard`, the sidebar. E2E:
`gr31-catalogue.spec.ts`. *The integration, tenancy, vitest and e2e tests were written but not run
(the coordinator runs them).*

### For the coordinator
- Regenerate the client and typecheck: `ProductOut`, `VariantOut`, `VariantIn`, `ProductList`,
  `ProductCreate`, `ProductPatch`, `CatalogueLimits`, `ImportPreview`, `ImportRowOut`,
  `ImportResult`, `CsvImport`, `ShopifyStatus`, `ShopifyConnectRequest`, `ShopifyConnectStart`,
  `ShopifyConnectComplete`, `ProductStep` in the flow step union, `product` in `AnswerRefKind`, and
  the operations `list_products`, `create_product`, `get_product`, `update_product`,
  `delete_product`, `preview_product_import`, `import_products`, `get_shopify`,
  `start_shopify_connect`, `complete_shopify_connect`, `sync_shopify`, `disconnect_shopify`. The web
  types are aliases waiting for it (`lib/api/types.ts`).
- `alembic check` for 0040 (after 0039). The e2e stack gained `SHOPIFY_*` env and
  `/__e2e/shopify/sign`.
- Owner track O-10: the Shopify Partner account, the app listing, the callback and webhook
  addresses, and the three privacy webhooks' wording. `.env.example` has the new settings.
- *Fixed in the combined batch:* the Shopify callback checked the install redirect's signature
  whenever `SHOPIFY_PROVIDER` was not `fake`, even with the built-in store in use; it now asks
  `registry.is_fake` (the setting or a test override). The built-in store kept a disconnected
  store's token revoked for ever, so reconnecting failed with "Shopify didn't respond"; installing
  again now clears the revocation, as a real reinstall gives a fresh token. A one-letter store
  ("x") passed as a valid address; handles need two characters, and the connect body no longer has
  a `min_length` so the friendly message (not Pydantic's) is what the person sees. A CSV line whose
  product name differs from the stored one only by case no longer renames the product. The CSV
  starter file in the web app had rows with 11 fields under a 16-column header.

## C-117 · Conversation assignment (GR-20, feature/gr-20-24-assign-sequences)

- **Model.** `conversations.assignee_user_id` (null: nobody; `ON DELETE SET NULL`) and `assigned_at`,
  `workspace_members.available_for_assignment` (default true, per workspace membership),
  `workspaces.assignment_round_robin` (default false) and `workspaces.assignment_cursor_user_id` (the
  member who had the last turn; not a foreign key, so a removed member just restarts the turn). Migration
  `0041` (after `0040`), expand-only, one partial index for the "Assigned to me" view. No new tables.
- **Who may assign whom (a decision; the plan left it open).** Owners and admins assign any conversation
  to any member or to nobody. Agents *take* a conversation nobody has (assign it to themselves) and
  *release or hand on* one they have (to anyone, or to nobody); they cannot give a free conversation to a
  colleague or take one from a colleague (403 "Agents can take a conversation nobody has, or hand on one
  they have."). The rule is `assignment.may_assign` and is unit tested; the web menu disables what the API
  would refuse. The route stays behind GR-19's `assign` permission (`CanAssign`, agent tier). An assignee
  who is not a member of this workspace is 404 `not_found` (checked before the role rule). Assignment
  works on every plan (on Free the one member is the only choice).
- **Every change does the same things, in one transaction** (`services/assignment.apply`): the
  conversation row is locked, then `assignee_user_id` and `assigned_at` are set; a system note goes in the
  thread ("Sam assigned this to Priya", "Priya took this conversation", "Assigned to Priya
  (round-robin)", "An automation assigned this to Priya"); an audit row `conversation.assigned` or
  `conversation.unassigned` (target the conversation, detail `via` member / round_robin / automation, the
  names and ids of the new and old assignee); `conversation.updated` for open inboxes; the
  `conversation.assigned` webhook (now emitted); and a notification to the new assignee. *The note and
  the audit row are the conversation's activity:* the contact timeline (GR-17) reads the audit rows for
  the contact's conversations ("Assigned to Priya", "By Sam. From Kim.", "Round-robin", "By an
  automation"; new timeline kind `assignment`). *Deviation: audit rows from a round-robin turn or a flow
  step have no member, so `audit.record_system(label, ...)` is new; the actor name is "Round-robin" or
  "Automation: name".*
- **Round-robin** (workspace setting, off by default; `PUT /assignment/settings`, admins). With it on, a
  customer message in a conversation nobody has hands it to the next *available* member (ingest hook
  `ingest._assign`, after the broadcast hook, with the conversation already locked). Members are taken in
  the order they joined; a member whose availability is off is skipped; nobody available leaves the
  conversation unassigned. The turn is read and moved under a `FOR UPDATE` lock on the workspace row, so
  concurrent inbound messages take different turns (tested with six at once); the lock lasts until the
  ingest transaction commits. *Accepted:* a workspace being deleted at the same moment could meet it in a
  lock cycle; the job retries. Manual assignment ignores availability. The flow action can ask for a
  round-robin turn whatever the setting says.
- **Availability.** `PUT /members/{user_id}/availability` (`CanSelf`): your own, or anyone's if you can
  manage settings (403 otherwise; a stranger is 404). Audited when it changes. The switch is in the
  assignee menu (your own, for agents) and on the Members page (everyone's, for owners and admins).
- **Notification** (`conversation_assigned`, new type; `notify_user` is new in `services/notifications`).
  In app always; push when the member's **"needs you" switch is on** (*decided: no new switch, so the
  notification settings page and its tests stay as they are*; `PUSH_EVENT_OF_TYPE` maps it to `NEEDS_YOU`).
  No notification when someone assigns a conversation to themselves. Title "Priya Shah was assigned to
  you", body says who or what handed it over, link `/inbox/{id}`. Never emailed.
- **Views and filters.** `GET /conversations` gains the views `mine` (open, assigned to the caller) and
  `unassigned`, and `assignee_id`. `GET /conversations/counts` gains `mine`. Each list item carries
  `assignee` ({user_id, name, avatar_url}; the name is the member's, else the part of their email before
  the @) and `assigned_at`. The live event (`conversation.updated`) carries the same, with the name
  looked up, so an open inbox updates without a refetch. A caller that cannot look the name up still
  sends the id, and the web falls back to the members it holds.
- **Removing a member** clears their conversations (`assignment.clear_for_member`, counted in the
  `member.removed` audit detail); the note in C-106 is closed.
- **Routes** (`/v1/w/{wid}`): `PUT /conversations/{id}/assignee` (body `{user_id | null}`, returns the
  conversation), `GET /assignment` (any member: who can be assigned, with availability and open
  conversations, and the setting), `PUT /assignment/settings`, `PUT /members/{user_id}/availability`.
- **Flow action `assign`** (`schemas.flows.Assign`): `mode` member (a chosen `user_id`), round_robin or
  nobody. Activation and the draft check say "Choose who gets the conversation." or "That person isn't on
  your team any more." (`Context.member_ids`). At run time a member who has left, or nobody available,
  skips the step with `skipped: member_missing` or `nobody_available` and the flow goes on. A flow's
  assign step overrides what round-robin did for the same message (two notes, two audit rows, and the
  last assignee is notified). Its fields are in the flow editor's Action step.
- **Web.** Inbox: an "Assigned to me" chip (with the count) before Leads; the row shows the assignee's
  initials or picture (the name for screen readers); the thread header has an assignee menu (Nobody, each
  member with open conversations and "away", and the caller's own availability); the details panel has
  the same as a field. Settings, Members: a "Hand out new conversations" card (the round-robin switch and
  everyone's availability). The contact timeline shows assignments. *Limit:* the cache keeps a row in the
  "Assigned to me" list until the next fetch when another member takes it away (only the server knows who
  is asking); assigning from the app refetches the lists.
- **Not built.** Per-account or per-skill routing; assignment by workload or by business hours;
  reassigning on a member's availability change; a daily cap per member; an "unassigned" count chip.
- **Tests.** Unit: `test_assignment_rules.py` (who may assign, the turn, the note, the flow action's
  checks, the push mapping). Integration: `test_assignment.py` (the rules, the note, audit and timeline,
  the notification and its channels, the views and counts, round-robin on and off, an away member,
  nobody available, availability rights, six concurrent messages, removing a member, live events, the
  flow action in three modes, activation refusing a stranger); `test_conversations.py` counts updated.
  Tenancy: the two new routes with ids in `test_isolation.py`. Vitest: `AssigneeMenu`, `AssignmentCard`,
  `ConversationRow`, `lib/inbox/assignee`, `lib/inbox/cache`, the flow editor's assign action. E2E:
  `gr20-assignment.spec.ts`.
- **For the coordinator:** regenerate the client (`Assignee`, `Assignable`, `AssignmentOverview`,
  `AssigneeUpdate`, `AssignmentSettingsPut`, `AvailabilityPut`, `Assign` in the flow action union, the
  `mine` and `unassigned` views, `assignee_id`, `mine` on `InboxCounts`, `assignment` on `TimelineKind`
  and the four operations); the web types are aliases waiting for it. `ContactTimeline`'s icon map and
  `ListHeader`'s chips will not typecheck until then. Migration `0041` follows `0040` (GR-31).
- *Fixed in the combined batch:* picking the next member took `FOR UPDATE` on the workspace row
  while ingest already held `KEY SHARE` on it (the new conversation's foreign key), so two messages
  arriving together deadlocked; it now takes `FOR NO KEY UPDATE` (`with_for_update(key_share=True)`),
  which waits for the other turn instead. The inbox details panel's "Assigned to" group is a
  `CardInset` like the others.

## C-118 · Sequences (GR-24, feature/gr-20-24-assign-sequences)

- **What it is.** A sequence is timed messages after an entry event, on one connected account
  (Instagram, WhatsApp or Messenger). It starts when a lead is captured (GR-14), a tag is added (GR-02)
  or someone replies to a WhatsApp broadcast (GR-23), and stops on a reply, a tag or a lead stage.
  Migration `0042` (after `0041`), expand-only: `sequences`, `sequence_steps`, `sequence_enrolments`,
  `sequence_step_runs` (all reach the account by a foreign key, so the account purge deletes them; the
  purge test's list, the account-deletion seed and the tenancy tables and seeds include them).
- **Model.**
  - `sequences`: account, name, status (draft, active, paused), entry type with `entry_tag_id`,
    `entry_broadcast_id` (null: any broadcast) and `entry_capture_kind` (email, phone or field; null:
    any), the stop rules (`stop_on_reply`, `stop_tag_ids`, `stop_stages`), `allow_reentry`.
  - `sequence_steps`: position, `delay_seconds` (0 to 30 days), `delay_from` (`entry` or `previous`;
    the first step always counts from entry), a text and/or an approved WhatsApp template (name,
    language, category and body copied when saved, variables mapped as in a broadcast), and
    `respect_hours`.
  - `sequence_enrolments`: contact, `current_step`, `next_due_at`, status (active, completed,
    stopped), why it started (`entry_event`) and why it stopped (`stop_reason`, `stop_detail`).
  - `sequence_step_runs`: sent, skipped (with a code and a plain sentence) or failed, one row per
    (enrolment, step position) by a unique constraint.
- **Entry events reuse the existing points; nothing new fires them.** `webhooks.events.lead_captured`
  (a capture step saved an email, phone or answer), `webhooks.events.contacts_tagged` (every way a tag
  is added: the API, a flow step, the agent) and `webhooks.events.lead_stage_changed` (GR-18) each call
  `services/sequences/entry`, whether or not a webhook endpoint wants the event. A customer message
  calls it from `ingest` (after GR-23's broadcast hook, which now returns the broadcasts the message is
  a reply to). Only an *active* sequence on the contact's own account takes people in.
- **At most one active enrolment per contact and sequence** (a partial unique index, so two events at
  once cannot both enter them). *Added by me: `allow_reentry`, off by default.* With it off a contact who
  finished or was stopped is not taken in again (a "captured" sequence would otherwise start again at
  every answer); with it on they can enter again once the first is over. The brief said "at most once
  while active"; this is the same rule plus a setting for the case after it.
- **Stop rules.** A reply (any customer message, on by default per sequence), one of the sequence's stop
  tags being added, the lead stage becoming one of its stop stages (stages exist: GR-18, so all three are
  supported). The reply stops the contact's sequences *before* a reply to a broadcast starts the ones
  that begin on it, so a message never stops the sequence it started. A stopped enrolment keeps its
  history and says why ("They replied", "A stop tag was added: Bought", "Their lead stage changed: Won",
  "Taken out by your team"). A person can be taken out by hand
  (`POST /sequences/{id}/enrolments/{eid}/stop`).
- **Sweeper** (`jobs/tasks/sequences.run_sequences`, every minute, bulk lane, one waiting job; recovery
  class RETRY). It finds up to 100 due enrolments across workspaces (active sequences on accounts that are
  `active`; an account that needs reconnecting is not picked up at all until it works) and runs each in
  its own transaction under `FOR UPDATE SKIP LOCKED`. A step is sent **once** however the job is retried
  or two workers meet: the row lock, the message's client id (`uuid5(enrolment, step)`, so
  `queue_outbound` returns the message already queued) and the unique step run all agree. The send goes
  through the normal queue (`sending.queue_outbound`, so the token bucket, retries, statuses, the inbox
  and realtime are the ones every message uses). *Deviation: no new message source.* A sequence's
  messages are source `automation` with no run, so the inbox shows them as automation messages and the
  `messages.source` check is unchanged; Activity tells sequence sends apart through its own kind.
- **What a step sends** (`services/sequences/rules`, pure, unit tested).
  - Instagram and Messenger: the text while the 24-hour window is open; otherwise skipped, "The messaging
    window had closed" (Human Agent never applies to an automated message). A template step is refused
    at save ("Only WhatsApp has templates.").
  - WhatsApp inside the window: the text, no consent needed. Outside it: the approved template, only to a
    contact whose latest WhatsApp marketing record is a grant (GR-23's `dispatch.consent_skip`, now
    public); no record is skipped as "no consent", a withdrawal as "opted out". A text-only step outside
    the window is skipped ("has no template"). A template-only step always needs consent.
  - *WhatsApp templates are marketing messages, so they also wait on `BROADCASTS_ENABLED` (O-11, the
    legal check of marketing consent); off, such a step is skipped as "marketing_off".* Text inside the
    window is not affected. Remove the check when O-11 is done.
  - A skipped or failed step is a finished step: the sequence moves on to the next.
  - The text is filled like a saved reply (`{first_name}`, fields), with the workspace's automation
    disclosure line; a template variable with no value and no fallback skips the step ("missing_value").
- **Limits and holds.**
  - *Business hours (GR-22):* a step with `respect_hours` waits for the account's next opening (its own
    hours, else the workspace's; no hours means always open). Hours that never open look again a day later.
  - *The number's daily limit (GR-23):* template sends count with broadcasts' against the number's tier
    limit in the rolling 24 hours (`broadcasts/dispatch` now counts sequence template sends too). A
    sequence step that finds no room waits until a place frees; none is dropped.
  - *Quality:* while the number's rating is Low a template step waits 30 minutes at a time.
  - An account error at send time (needs reconnecting, can't send) holds the step 15 minutes.
  - Template sends do not use the broadcast recipient quota (that is for broadcasts).
- **Plans (a decision, pending owner confirmation; one line each in `billing/plans.py`).** Two
  entitlements: `active_sequences` (Free 1, Pro 10, Max 50) and `sequence_steps` (Free 3, Pro 10, Max
  20; whatever the plan, a sequence has at most 20 steps). Past a limit the write is 402 `quota_exceeded`
  naming the key, and the page shows the limit. Saving a draft never counts; turning one on does. *Pending
  the owner:* whether Free gets sequences at all, and the numbers. A template step is still a message
  Meta bills the business for, and needs marketing consent, so the plan limits how many sequences there
  are, not how many messages go.
- **Editing.** Steps and rules change only while the sequence is a draft or paused (409 "Pause the
  sequence to change it."); a person already in it keeps their place, and a step removed from under them
  ends it (completed) if no step is left. A sequence with people in it cannot change account. Delete is
  for a draft or paused sequence and takes its enrolments and history. A deleted start tag is shown as a
  problem on the sequence and stops it being turned on.
- **Routes** (`/v1/w/{wid}`, owners and admins through the automations permission, except the contact's
  list): `GET|POST /sequences`, `POST /sequences/preview`, `GET|PUT|DELETE /sequences/{id}`,
  `POST /sequences/{id}/activate|pause`, `GET /sequences/{id}/enrolments?status=&limit=&offset=`,
  `POST /sequences/{id}/enrolments/{eid}/stop`, and `GET /contacts/{id}/sequences` (any member). The
  preview is the steps as a sample contact ("Priya") would meet them in a straight run: when each is due
  after entry, what it would send and a plain note (a template needs consent, a text-only WhatsApp step
  after 24 hours sends nothing); nothing is saved. A tag, broadcast or account of another workspace is 404.
- **Activity and the contact (GR-05, GR-17).** Activity has a `sequence` kind: each step sent (worked),
  skipped (with the reason) or failed, with a link to the sequence; "failures only" (the default) shows
  the skips and failures. The contact's timeline has the same ("Sent step 1 of Three days", "Skipped step
  2 of ..." with the reason), and the contact drawer has a Sequences section: each sequence they are or
  were in, the step they are on and when it is due, what happened at each step, and why a stopped one
  stopped.
- **Ask.** `list_sequences` (owners and admins; read-only): each sequence's status, what starts it, steps,
  people in it, finished, stopped, what stops it, and any problem. Never a message.
- **Web: decided to put Sequences on its own page, `/w/{slug}/sequences`, linked from Automations** (a
  button beside Broadcasts) rather than a tab: it has its own list, editor and people, like Broadcasts.
  The list shows the plan's limit; the editor is a form (name and account, what starts it, the steps with
  their wait, message, WhatsApp template and variables and a business-hours switch, what stops it) with a
  live preview from the server beside it; a sequence that is on is read-only until paused; the detail
  page has the people (filter by status, why each stopped, take one out). Agents get a plain notice.
- **Not built.** Stopping on a tag *removed*, or entering on a stage; branching inside a sequence (use a
  flow); a send time of day other than business hours; a step that sends an image or buttons; sequence
  analytics (opens, replies per step); entering existing contacts in bulk; a webhook event for sequences.
  A sequence's WhatsApp text inside the window ignores consent, as every WhatsApp reply does.
- **Tests.** Unit: `test_sequence_rules.py` (what a step sends and why not, the due time, business hours,
  the bodies, the client id, the plan's numbers), the purge list and the tool registry. Integration:
  `test_sequences.py` (the done-when: a three-day sequence sends day 1 and day 3 to an opted-in sandbox
  contact and stops when they reply; completion; consent and opt-out skipped with their reasons; text
  inside the window and skipped outside it; the marketing setting off; Instagram open and closed
  windows; once at a time and re-entry; paused; stop tag, stage and reply off; a reply to a broadcast
  starting it; a capture starting it; business hours holding a step; the shared daily limit; low quality;
  a step sent once; a reconnecting account; validation, editing rules, a deleted tag, the plan's limits,
  the preview, taking a person out, Activity, the timeline and the contact's list, roles).
  Tenancy: the new routes, bodies and tables in `test_isolation.py`. Vitest: `lib/sequences/format`,
  `SequencesPage`, `SequenceForm`, `SequencePeople`, `ContactSequences`. E2E: `gr24-sequences.spec.ts`
  (a tag starts a sequence, two steps are sent by the worker, a reply stops it, the page says why; the
  editor saves a draft).
- **Unsure / for the coordinator:** regenerate the client (the `Sequence*`, `StepIn`, `StepOut`,
  `EntryRule`, `EntryOut`, `StopRules`, `StopOut`, `Enrolment*`, `ContactSequence*`, `PreviewStep`
  schemas, 11 operations, the `sequence` activity kind and timeline kind); the web types are aliases
  waiting for it, and `ContactTimeline`'s icon map will not typecheck until then. Migration `0042` follows
  `0041` (GR-20), which follows `0040` (GR-31). The e2e spec relies on the worker's minutely sweep
  running in the e2e stack (the broadcast spec relies on the same). A sequence created while
  `BROADCASTS_ENABLED` is off still saves; only its template steps are skipped.
- *Fixed in the combined batch:* a tag added through the contacts API never entered a sequence unless
  a webhook endpoint wanted `contact.tagged`, because `contacts.py` gated the call to
  `events.contacts_tagged` (which also feeds sequences) on `wanted`; the gate is gone and
  `contacts_tagged` still decides whether to emit. The web sequence form and pages read `problems`
  as possibly absent (the generated type marks defaulted response fields optional).

## C-120 · Payment requests and order capture (GR-32, feature/gr-32-33-orders-wa-catalogue)

An order made in a conversation from the catalogue, a payment link or UPI request sent in the chat,
and a paid order marked by Razorpay's signed webhook. **Payments go to the business's own account,
never through us.** *Nothing here has run against a real Razorpay account: it is built like Shopify
(C-116), with a sandbox for development and the end-to-end stack, and listed as unverified in
`docs/verification.md` item 38.* PD-8 applies: commerce is Pro and Max.

### Decisions
- **Razorpay with the business's own keys, not partner OAuth.** *Verified from Razorpay's docs
  (2026-10-25): the OAuth route is for Technology Partners and needs sign-up with Razorpay support
  before an app can be registered, so it is not available to us by default.* Each workspace saves its
  own key id and key secret (`payment_connections`, the secrets encrypted with the existing token
  encryption and never returned). If the owner later becomes a Technology Partner, OAuth can replace
  the key form without changing orders. Pending the owner: whether to apply for partner status.
- **Unset means "not configured".** With no keys, asking for a Razorpay link answers 409 "Razorpay
  isn't set up for this workspace. Add your keys in Integrations first."; with no UPI address, the same
  for UPI. `RAZORPAY_PROVIDER=fake` is a sandbox that accepts `rzp_test_` keys and hands out
  `plink_fake_<n>` links; refused in production like the other fakes. There are no app-wide Razorpay
  credentials.
- **Connect checks the keys first** (`GET /payment_links?count=1`): refused keys are a 422 "Razorpay
  doesn't accept these keys", Razorpay not answering is a 502, and nothing is saved either way. The
  business makes up a **webhook secret** (8 or more characters), enters it here and in its Razorpay
  dashboard; the card shows the webhook address and the events to turn on, and when the last signed
  event arrived.
- **Money** as in GR-31: integer minor units and ISO 4217. The total is computed on the server from the
  catalogue's prices when the order is made; the lines are a snapshot (name, variant, SKU, unit price),
  so a later price change does not alter an order. A request carries product ids and quantities, never
  a price. All lines must share one currency. Stock, when recorded, is checked (more than is left is a
  422 "Only 4 left of Cotton kurta") **but is not reduced** by an order: the catalogue's stock is a
  number the business keeps. *Not built:* reserving or reducing stock, delivery fees, tax and discounts
  (the total is the sum of the lines).
- **Status:** `draft`, `awaiting_payment`, then `paid`, `cancelled` or `expired`. Asking for payment can
  be repeated (a new link replaces the old one, which is cancelled with Razorpay as far as it answers).
  A payment that arrives for a cancelled or expired order still marks it paid, because the money has
  arrived. A paid order cannot be cancelled. A Razorpay link lasts 3 days (`LINK_TTL`).
- **UPI has no webhook.** The request is a `upi://pay?pa=<VPA>&pn=<name>&am=<amount>&cu=INR&tn=Order <n>`
  link plus the VPA in the message ("send it to shop@okbank and tell us when it's done"); only INR.
  A member marks the order paid ("Mark as paid", with an optional reference); who and when are kept on
  the order and in the audit row `order.marked_paid`. The Orders sheet, the inbox dialog and the card
  all say so.
- **Webhooks** (`POST /webhooks/razorpay/{token}`): the token is a random per-workspace part of the
  address; an unknown token and a bad signature are both 401. `X-Razorpay-Signature` is the hex
  HMAC-SHA256 of the raw body with the workspace's webhook secret, checked before the body is read. A
  verified event is stored once per `X-Razorpay-Event-Id`, then applied by the webhook job
  (`services/webhook_handlers/razorpay.py`): `payment_link.paid` marks the order paid when the amount
  paid equals the total (another amount is ignored and logged), `payment_link.expired` expires an
  order still waiting, everything else is ignored. Idempotent: an order already paid stays as it is.
- **Plans.** `commerce` (reused) gates making orders, asking for payment, marking paid and saving
  payment settings (402 `entitlement_required`, "Orders are part of Pro."); reading orders and the
  settings status is never refused. *Proposed, pending owner confirmation:* `orders_monthly` Free 0,
  Pro 500, Max 5,000, counted when the order is made (`billing/plans.py`; one line to change). A
  request naming another workspace's conversation, product or order is a 404 before any plan check.
- **Permissions.** Any member who can reply (`CanReply`) makes orders, asks for payment, marks paid and
  cancels; payment settings need `integrations.manage`. Orders are listed for every member (agents see
  the customer's address in the order they made; the settings card is for owners and admins).

### Data (migration 0043, after 0042, expand-only)
`payment_connections` (one per workspace: Razorpay key id, encrypted key secret and webhook secret, the
address token, UPI address and name, last event seen), `orders` (number per workspace, contact,
conversation, status, source, currency, `total_minor`, address JSON, note, payment method, link id and
address, reference, `paid_at`, `paid_by_user_id`, `cancelled_at`) and `order_items`; `webhook_events.
provider` accepts `razorpay`. Orders reference contacts, so they and their lines are account tables
for the purge (`orders`, `order_items` in the expected list, a seeded row in `seed_account`). The
tenancy walk got a seeded order, line and payment settings, three `B_TABLES` and the example bodies.

### Routes (all `/v1/w/{wid}`, `api/v1/orders.py`)
`GET/POST /orders`, `GET /orders/{order_id}`, `POST /orders/{order_id}/payment-request`,
`.../mark-paid`, `.../cancel`; `GET /integrations/payments`, `PUT/DELETE /integrations/payments/razorpay`,
`PUT/DELETE /integrations/payments/upi`. Public: `POST /webhooks/razorpay/{token}`. Sending the link
uses the ordinary send pipeline (reply window, takeover and read-only rules apply; a closed window is
a 409 and the order keeps its link, which can be sent again).

### Where it shows
- **Inbox:** More, **Create order** on any conversation: products, variants and quantities from the
  catalogue (an estimated total is shown while typing; the server's is what counts), the delivery
  address, a note; then Send Razorpay link or Send UPI request in the same dialog.
- **Orders page** (Engage, every member): the list with a status filter, an order sheet (lines, address,
  how it is being paid, send a link, mark paid, cancel), and for owners and admins the **Payments** card.
- **Events** `order.created` and `order.paid` through GR-04's catalogue (the address is left out of the
  payload). **Activity** (kind `order`): paid orders, and orders that expired (needs a new link). **Contact
  timeline** (kind `order`): one entry per order at its latest step ("Order #12 paid. Paid with
  Razorpay"). **Ask:** the `list_orders` tool (admin tier, read), with paid totals per currency and
  citations that open the Orders page (answer-ref kind `order`).

### Not built
- *The flow step "request payment"* (optional in the plan): a flow has no order to attach it to until a
  cart exists (the WhatsApp cart is GR-33); a payment request needs the member's chosen products and
  address, which a flow does not collect yet. Recorded as not built.
- Refunds, partial payments (a payment link is created with `accept_partial: false`), reminders,
  editing an order's lines after it is made (cancel and make a new one), a customer-facing order page.

### Tests
Unit: `test_orders.py` (the Razorpay signature, the HTTP client's request and error kinds against a mock
transport, the sandbox, the UPI link, the payment message, the timeline and Activity wording), the
purge list, the tool registry and the event catalogue (11 events). Integration: `test_orders.py` (the
plan, pricing and the snapshot, numbering and refused lines, "not configured", keys checked and stored
encrypted, **the done-when: a test-mode link marks the order paid** and a replay changes nothing,
unsigned, forged and unknown webhooks, the wrong amount, expiry then a late payment, UPI marked paid
by hand and audited, cancelling, events, timeline and Activity). Tenancy: the new routes, bodies and
tables. Vitest: `lib/orders/format`, `OrdersPage`, the sidebar and the agent route test. E2E:
`gr32-orders.spec.ts`. *The integration, tenancy, vitest and e2e tests were written but not run (the
coordinator runs them).*

### For the coordinator
- Regenerate the client and typecheck: `OrderOut`, `OrderLineOut`, `OrderList`, `OrderCreate`,
  `OrderLineIn`, `AddressIn`, `PaymentSettings`, `RazorpayConnect`, `UpiSave`, the operations
  `list_orders`, `create_order`, `get_order`, `request_order_payment`, `mark_order_paid`, `cancel_order`,
  `get_payment_settings`, `connect_razorpay`, `disconnect_razorpay`, `save_upi`, `remove_upi`, the
  `order` activity, timeline and answer-ref kinds and the two new `EventName`s. The web types are
  aliases waiting for it (`lib/api/types.ts`); `ContactTimeline`'s icon map will not typecheck until then.
- `alembic check` for 0043 (after 0042). The e2e stack gained `RAZORPAY_PROVIDER=fake`; the suite signs
  its own webhooks with the secret it types into the card. Owner track: Razorpay account(s) for a live
  test, and whether to become a Technology Partner (OAuth).

- *Fixed in the combined batch:* (1) the payment settings showed no webhook address unless
  `API_BASE_URL` was set; it now falls back to the address the request came to, as the widget snippet does.
  (2) Asking for a payment link returned 500: `updated_at` was expired by the update and read lazily
  in the response (`MissingGreenlet`); `orders.views` now refreshes it. (3) Test fixes: the Razorpay
  webhook column is `razorpay_webhook_secret_enc`; two orders in one workspace reuse one kurta (SKUs are
  unique per workspace); the Activity feed hides successes unless `failures_only=false`, and names the
  contact as `@username`. The account-deletion seed adds one catalogue connection per workspace
  (the table allows one).

## C-121 · WhatsApp catalogue messages (GR-33, feature/gr-32-33-orders-wa-catalogue)

Products copied to a Meta commerce catalogue, product and product-list messages sent from the inbox,
the flow step "send product" as a native WhatsApp message when it can be one, and a customer's cart
becoming a GR-32 order. *Nothing here has run against Meta: it is built like Facebook (GR-29) and
Shopify (GR-31), against a sandbox catalogue for sandbox WhatsApp numbers, and listed as unverified in
`docs/verification.md` item 39.* PD-8 applies: commerce is Pro and Max.

### What Meta's documentation says (read 2026-10-25) and what is unverified
Read from Meta's current pages for the Cloud API (Graph v26.0 in the examples; the app uses
`META_GRAPH_VERSION`, v25.0) and the Catalog API:
- **Product message** (`messages`, `type: interactive`): `interactive.type = product`, optional `body`
  and `footer` text, `action.catalog_id` and `action.product_retailer_id`. The retailer id must match
  an item in the catalogue or the API returns an error and nothing is sent. Free-form: only inside an
  existing chat (the 24-hour window), no template. A customer on an old WhatsApp version sees a
  failure and the business gets a delivery-failed webhook.
- **Product list**: `interactive.type = product_list`; `header` (type `text`) **required**, `body`
  required, `footer` optional; `action.catalog_id` and `action.sections[]` each with a `title` and
  `product_items[].product_retailer_id`. Up to 30 products across up to 10 sections. If at least one
  item matches the catalogue it is sent and unmatched ones are dropped with an error; if none match
  nothing is sent.
- **Order webhook**: a message with `type: order` and `order.catalog_id`, `order.text` and
  `order.product_items[]` with `product_retailer_id`, `quantity`, `item_price` and `currency` (numbers
  in Meta's examples, quoted strings in one partner's; the parser reads both).
- **Catalog Batch API**: `POST /{catalog_id}/items_batch` with `item_type` (`PRODUCT_ITEM`) and
  `requests` (up to 5,000, Meta suggests under 3,000; 28 MB), each `{method: CREATE | UPDATE | DELETE,
  data: {...}}`; `allow_upsert` defaults to true so `UPDATE` creates a missing item; `DELETE` needs only
  the identifying `id`; the answer has `handles` and `validation_status[]` (`retailer_id`, `errors`,
  `warnings`); `GET /{catalog_id}/check_batch_request_status?handle=` reports progress. The older
  `/batch` endpoint is deprecated (unavailable from API v27), so `items_batch` is used.
- **Commerce settings**: a phone number's catalogue is shown with `is_catalog_visible` on
  `POST /{phone_number_id}/whatsapp_commerce_settings` (default false); a catalogue is connected to the
  WhatsApp Business Account in WhatsApp Manager (one catalogue per business account, shared by its
  numbers, from the same Business Manager). *Not called by us:* the owner connects it in Meta's tools.
- **Unverified, in code as written** (`metacatalog/http.py`, `platforms/whatsapp/adapter.py`):
  the exact fields a commerce catalogue item requires (this sends `id`, `title`, `description`,
  `availability`, `condition`, `price` as "799.00 INR", `link`, `image_link`, `brand`); that the
  header limit is 60 and a section title 24 characters (the body's 1,024 is Meta's documented limit);
  the shape of `check_batch_request_status`; **which permission the Embedded Signup business token
  carries**: Meta's pages did not name `catalog_management` for these calls, and the token WhatsApp
  Embedded Signup issues may lack it or `business_management`, in which case connecting answers 409
  with "Meta doesn't let this number use that catalogue ..." and the owner must grant catalogue access;
  that the same token that sends messages can call the Catalog API at all (it may need a system-user
  token); and error codes (190, 200, 100, 803, 80014 are mapped to auth, not found and rate limited).
  If catalogue access can't come from the number's token, the connection will need its own token
  (a follow-up; the card and sync already read the token through one function, `token_of`).

### Decisions
- **Sync** (`services/catalogue/wa_catalogue.py`, job `sync_whatsapp_catalogue`, bulk lane, 3 tries):
  one catalogue item per variant, or per product without variants; the retailer id is our variant or
  product id. The job compares what the catalogue should hold with a hash per item
  (`catalogue_items.content_hash`) and sends only what changed (upserts via `UPDATE`) and deletes what is
  gone or switched off. Triggered 8 seconds after a product is created, changed, deleted or imported,
  after a Shopify sync, when Sync now is pressed, and by a 5-minute sweep (`sweep_whatsapp_catalogue`),
  so a missed trigger heals. Items go in batches of 200. Deletion is found by comparison, not by hooks,
  so every way a product disappears (Shopify, CSV, the API) is covered.
- **What an item needs.** Meta needs a price, a link and a picture: a product without them is not sent
  and the card lists it with the reason ("Add a link to this product. Meta needs one for every catalogue
  item."). Out of stock only when stock is recorded as 0 (stock not recorded is "in stock", the catalogue
  has no unknown). The brand is the workspace's name unless the connect request gives one. A picture
  uploaded here wins over one given as an address.
- **Per-workspace catalogue** (`catalogue_connections`, one per workspace): the catalogue id, the WhatsApp
  number it was connected through (its token makes the calls), the brand and the sync state. Connecting
  checks the catalogue with Meta first (`GET /{catalog_id}`); a catalogue Meta won't show is a 409 with
  Meta's reason in words, Meta not answering a 502, a non-WhatsApp account a 422, another workspace's
  account a 404. Reconnecting marks every item to be sent again. Disconnecting forgets the connection
  and the item records; the Meta catalogue is left as it is.
- **Sandbox.** A sandbox WhatsApp number (`sandbox_...`, which exists only where the sandbox platform is
  on) uses the built-in catalogue (`metacatalog/fake.py`); the catalogue id `missing` is refused as not
  found and `denied` as access refused; a title containing `[fail]` is refused item by item. Tests swap
  the client with `use_catalogue`. No new setting.
- **Sending** (`services/catalogue/wa_send.py`, `POST /conversations/{id}/product-message`): "Send
  product" and "Send product list" in the inbox's More menu on WhatsApp conversations. Every item must
  be in the catalogue as last synced ("... isn't in the WhatsApp catalogue yet. Wait for the sync, or
  press Sync now."), the conversation must be on the number the catalogue was connected through (409
  otherwise), the message is a free-form send (window, takeover and read-only rules of the ordinary
  send pipeline), and the typed text is the message body and what the thread shows. The message is
  stored in the new `messages.interactive` JSON column (migration 0044) and sent by
  `sending.pending_parts` as `OutboundMessage.products`; no change to message kinds.
- **Flow step "send product"**: on WhatsApp, with a catalogue connected through the conversation's number
  and every needed item synced, it sends a native message: a product message for a named variant or a
  product without variants, a product list (one section, up to 30 variants) for a product with variants
  and none named; the step's intro is the body, else the product's name. Otherwise (another platform, no
  catalogue, another number, an item not synced yet) it sends the text and link of GR-31, unchanged.
- **Cart to order.** An `order` message becomes an inbound text ("Sent an order of 3 items") and, with
  commerce on the plan and room under `orders_monthly`, a GR-32 order for that contact in that
  conversation with status `awaiting_payment`, source `whatsapp`, priced from the catalogue now (the
  price the customer saw is not trusted; if it differs, the order's note says so). Items that are gone,
  switched off, unpriced or in another currency are left out and counted in the note; stock is not
  enforced for a cart. No usable item or no plan means no order, and the message stays in the thread.
  The message text is then rewritten to name the order ("... Order #12."). Audit: `order.created` by
  "WhatsApp cart".
- **Plan.** Connecting, syncing and sending need `commerce` (PD-8). Reading the status is open to every
  member (the inbox needs to know a catalogue is connected). A downgrade stops the sync ("The catalogue is
  part of Pro, so the sync stopped."); what is in Meta stays.

### Data (migration 0044, after 0043, expand-only)
`catalogue_connections`, `catalogue_items` and a nullable `messages.interactive`. The connection
references the WhatsApp account with `ON DELETE CASCADE`, so it is an account table for the purge
(`catalogue_connections` in the expected list, a seeded row in `seed_account`). The tenancy walk got a
seeded connection and item, two `B_TABLES` and the example bodies of the two routes that name B's
resources.

### Routes
`GET/PUT/DELETE /v1/w/{wid}/integrations/whatsapp-catalogue`, `POST .../whatsapp-catalogue/sync` (202),
`POST /v1/w/{wid}/conversations/{conversation_id}/product-message` (202). The sandbox inbound gained kind
`order` (with `cart`) for development and the end-to-end stack.

### Not built
Reading Meta's catalogue back (importing from it), creating a catalogue, setting `is_catalog_visible`
or connecting the catalogue to the business account (done in Meta's tools), product messages on
Instagram or Facebook, a "catalogue" or cart request message, order status updates back to the
customer through WhatsApp's order templates, sending a product message outside the 24-hour window
(a template would be needed), and per-item sync of a single product (a pass is cheap, it compares
hashes).

### Tests
Unit: `test_wa_catalogue.py` (the item built from a variant or product, availability, the link and
picture rules, the digest, the stored message round trip, Meta's interactive payloads, the cart parsed
from an `order` webhook, the batch client's requests and error kinds, the sandbox catalogue), the
purge list and the job recovery table. Integration: `test_wa_catalogue.py` (the plan, the connect
checks, the sync sending only what changed, deletes, unsendable items with their reasons, Meta
refusing access, disconnecting, a product and a product-list message and the sandbox receiving them,
an item not synced yet, the flow step native and fallback, a cart becoming an order, a cart with
nothing orderable). Tenancy: the new routes, bodies and tables. Vitest: `WhatsAppCatalogueCard`. E2E:
`gr33-wa-catalogue.spec.ts` (connect, sync, send a product; a cart becomes an order). *The integration,
tenancy, vitest and e2e tests were written but not run (the coordinator runs them).*

### For the coordinator
- Regenerate the client and typecheck: `WaCatalogueStatus`, `WaCatalogueConnect`, `ProductMessageSend`,
  `ItemRef`, `SectionIn`, `WaCatalogueProblem`, the operations `get_whatsapp_catalogue`,
  `connect_whatsapp_catalogue`, `sync_whatsapp_catalogue`, `disconnect_whatsapp_catalogue`,
  `send_product_message`, and the `order` sandbox-inbound kind with `cart`. The web types are aliases
  waiting for it.
- `alembic check` for 0044 (after 0043). New periodic task `sweep_whatsapp_catalogue` (every 5
  minutes) and task `sync_whatsapp_catalogue`; both are in the recovery table. No new environment
  setting.
- Owner track: a real WhatsApp number with a commerce catalogue connected in WhatsApp Manager, and a
  check of which token can call the Catalog API (item 39).

- *Fixed in the combined batch:* the sync test patched a product's variants without their stock, which
  clears it and flipped Blue / L to "in stock", so two items were sent instead of one. The test now
  sends the stock too. (Test only: the sync was right to resend a changed item.)

## C-122 · Go-to-market pages (GR-37, feature/gr-37-gtm-pages)

Seven public pages: Switch from Manychat, Social Hood vs Manychat, Social Hood vs Interakt, three
feature pages (comment intelligence, the AI inbox, publishing) and Pricing. Web only: no API
change, no migration. The footer has a "Compare and learn" column, every page is in the sitemap
(`PUBLIC_PATHS`), and the landing page's pricing links to `/pricing`.

### Pages
- **Content is data.** `lib/marketing/gtm-pages.ts` holds each page (blocks, the comparison rows,
  the honesty notes, the sources); `components/marketing/GtmPageView.tsx` renders it; each route is a
  six-line `page.tsx` using `pageMetadata` (title, description, canonical, Open Graph, Twitter).
  Static pages, one h1, h2 sections, tables with row headers inside a scrolling box (the page never
  scrolls sideways), only theme tokens.
- **Screenshots, not the lazy illustrations.** The pages use the existing `SHOTS` images (the
  illustrations load on scroll in the browser only).
- **`/pricing`** reuses the landing page's `Pricing` (prices from Dodo, hourly, `revalidate = 3600`
  as a literal) with its heading as the page's h1 (`SectionHeading level`), then `PlanMatrix`.

### Pricing without drift
- **One typed module, one exported table.** `plan-table.json` is `ENTITLEMENTS` and `TRIAL_DAYS`
  exported from `billing/plans.py`. `tests/unit/test_marketing_plan_table.py` (DB-free) fails when
  plans.py and the file differ and rewrites the file with `UPDATE_PLAN_TABLE=1`. The web reads the
  file in two places: `plan-matrix.ts` (the comparison table) and the landing page's offline
  fallback (`FALLBACK_ENTITLEMENTS`, which used to be a hand-written copy). `plan-matrix.test.ts` fails
  when an entitlement in the file has no row (or an entry in `NOT_SHOWN`), so a new limit has to be
  worded before it ships. *Chosen over reading openapi.json, which carries no plan values.*
- **Plan cards** gain team members, "Public API and Zapier app", "Google Sheets sync" and "Product
  catalogue" lines (from the API's plan list as before). Broadcasts are not a card line (see below).
- **Proposed values shown as they are now:** the catalogue caps (C-116) and sequence caps (C-118) are
  in the table, with a line under it saying they may change. *If the owner changes them, change
  plans.py, refresh the file, nothing else.*
- Seats (PD-1), broadcasts (PD-4), webhooks, API, Zapier and Sheets (PD-6), widget branding (PD-7)
  and commerce (PD-8) are shown as decided in plans.py.

### What waits on the owner, and how it is worded
- **Broadcasts (O-11):** "Coming soon" with the reason (India's consent rules), in the table and on
  both comparison pages. *Not on the plan card: the web can't tell whether `BROADCASTS_ENABLED` is on.*
- **Shopify sync (O-10):** "arrives with our Shopify app listing". The catalogue itself is described
  as built.
- **Facebook and the Instagram events that need Advanced Access (C-077, C-108, C-115):** "coming
  soon" or "with Meta's approval". Story replies and mentions arrive as ordinary messages and are
  stated plainly.
- **Not claimed:** payments in chat, contact import, share-to-DM, follow triggers, TikTok, Telegram,
  SMS, email, a free-form canvas. The Switch page says so in a "what is different" section.

### Competitor claims
- Only what `docs/competitors.md` and `docs/competitor-manychat.md` record with a source (read
  2026-10-22), or what was read from the vendor's own page. A comment above every competitor cell
  names the source and date, and a test (`gtm-pages.test.tsx`) fails if one is missing. Each page
  lists its sources and when they were read.
- **Interakt's pricing page was read on 2026-10-25** (WebFetch): Starter 999 rupees (Instagram only),
  Growth 2,799 and Advanced 3,799, plus taxes; campaigns, a catalogue and unlimited agents on the
  higher plans (the page is inconsistent about agent roles, and the page says so). Checkout and
  WhatsApp Pay come only from third-party guides and are worded that way.
- **Manychat's pages refuse automated reads (403, again on 2026-10-25),** so its column stays on the
  third-party guides and says so on the page. *Prices are indicative; the owner should check
  manychat.com and interakt.shop before launch.*
- A competitor "lacks" something only as "Not found" (a test forbids "Not offered" on their side).
  No logos, no "best" or "#1" (a test checks the words).

### Tests
- vitest: `plan-matrix.test.ts`, `app/(marketing)/gtm-pages.test.tsx` (metadata, one h1, links,
  sources, the status words, the pricing page with and without the API), `app/seo.test.ts` (sitemap),
  and `plans.test.ts` / `test/plans.ts` for the new card lines.
- pytest: `tests/unit/test_marketing_plan_table.py`.
- Playwright: `e2e/gr37-gtm-pages.spec.ts` visits every page signed out, at desktop and phone width.
- *Written but not run in this session (the coordinator builds and runs the web checks).*

- *Fixed in the combined batch:* the pages said in-chat payments were "Not offered" and the plan
  table had no row for `orders_monthly` (added by GR-32). The Interakt comparison now says what we
  offer (Razorpay link to the business's own account, or UPI marked paid by hand; no WhatsApp Pay) and
  the catalogue row says WhatsApp product messages need the owner's Meta catalogue and Meta's approval
  (C-121). The plan matrix shows "Orders a month" under commerce (Pro and Max).

## C-123 · More visual answers in Ask (VIS-07 to VIS-10, VIS-12, feature/vis-07-12)

Backlog items VIS-07 (trend), VIS-08 (lead list), VIS-09 (table), VIS-10 (progressive visuals) and
VIS-12 (prepare replies for leads), on top of GR-38 (C-089). Option C still holds: the API builds
every visual from the numbers a tool returned, the model neither writes nor sees one, and
everything stays behind `AGENT_VISUALS_ENABLED` (off by default). No migration, no new route, no
new setting. Built on the combined batch G (migrations to 0044).

### What every new visual shares
- **Closed union, three new kinds:** `trend`, `lead_list`, `table` join `metric_comparison`,
  `ranked_posts` and `sentiment_summary` in `schemas/agent.py` (`Visual`), `agent/visuals.KINDS`
  and the web's `VisualView` switch. `kind` is required; an unknown kind draws nothing.
- **Caps in the types:** 92 trend points, 10 leads, 3 `reply_ids`, 10 table rows, 6 columns, 6
  cells a row. Each visual at most 8 KB (a test builds the worst case of each). A build that fails
  or is too big drops only the visual.
- **Same text answer without visuals.** Each visual repeats numbers the tool result already holds
  (its `summary`, `contacts`, `points`, `items`), so the answer reads the same with the setting
  off. The trend carries its own sentence (`summary`) as the chart's aria label and its text
  fallback.
- **Links** (`more_route`) carry a pattern in the type (`WORKSPACE_PATH`: plain workspace paths
  with an optional query, no scheme, host, `..`, `//` or fragment), checked again on the web by
  the same rule as action cards (`visualPath`).
- **The tool's role check is the visual's.** A builder runs inside the tool after the role gate
  and only from the rows the tool returns, so a visual can never show more than the tool does.
- Prompt: `VISUALS_NOTE` names the new tools so the answer doesn't copy their lists. *The prompt
  file (`agent.v4`) is unchanged, so no version bump; the eval was not run (no key here).*

### Trend (VIS-07)
- `metric_trend` builds a `trend` visual when at least one point has a reading; with none, the
  caveats say why and there is nothing to draw.
- `TrendChart`: a hand-built SVG in `text-chart-series-1` (the brand chart token), the same recipe
  as the weekly report's `SeriesChart` (scale from 0). A day or week with no reading breaks the
  line; a lone reading is a dot; nothing is drawn through a gap or in its place. Under the chart:
  latest, lowest and highest with their days (text, not the picture), and "N of M days have a
  reading". The SVG's label is the API's `summary`; an `sr-only` table lists every point, a gap as
  "No reading". The SVG scales with its column (viewBox 300 x 96, `w-full`), so 375 px and the
  panel need no special case.
- **One series only.** *Two-series trends (for example this month against last month on one
  chart) are out of scope: the categorical palette is still on a local branch, and a second hue
  without it would break the palette lock.* Revisit when it lands.
- *The scale starts at 0, so followers (1,000 plus a few) looks flat; the facts under the chart
  carry the real range. Chosen over a floating axis, which exaggerates small moves.*
- *A range of more than 92 weekly points (about 21 months) fails the build and drops the
  visual; the tool result and answer stand. The agent's default is 30 days.*

### Lead list (VIS-08)
- **Filter:** `ContactFilter.awaiting_reply` (the conversation's `awaiting_reply` flag, the one
  the inbox's "Needs reply" view uses); `list_contacts` gains `awaiting_reply: bool | None`. A
  contact with no conversation never matches `True`.
- **Order:** new `services.contacts.top_leads`: lead score highest first, no score last, then the
  latest activity, with the total that match. The cursor-paged `list_contacts` stays
  activity-ordered. With `awaiting_reply` the result also has `total`.
- **Visual:** top 10 (the tool's `limit` still goes to 25; the visual shows 10 and "+N more"
  links to `inbox?view=needs_reply`). A row has the name (customer text, drawn as text), the
  platform, the score ("No score" when none, never 0), the GR-18 lead stage and the last-activity
  words the tool already returns. A row opens the conversation; a contact who never wrote opens the
  Contacts page.
- **`contact` ref kind:** `AnswerRefKind` gains `contact`; `list_contacts` cites a contact with no
  conversation as `contact` (before, such contacts were left out of `refs`). The web opens
  `contacts` (*the Contacts page has no per-contact route, so the ref opens the list*), labels it
  "Contact", and has a follow-up for it.
- **Roles:** unchanged. `list_contacts` is for any member, as before; `awaiting_reply` shows what
  the inbox shows them.
- *Doc 05 had `ref (conversation)` on each lead row. A row holds `conversation_id` and
  `contact_id` instead, and the web builds the link, as `RankedPosts` does.*
- *The lead's cold flag (GR-18) is not shown: a lead waiting for us is not cold.*

### Table (VIS-09)
- Used only for tools whose result is a list of like rows:
  - `search_conversations` (any member): customer, platform, last message, when, lead score.
    More: `inbox` or `inbox?view=<view>`.
  - `list_orders` (owners and admins, like the tool): order, customer, status, total (the money
    text the tool already formats, right-aligned), date. More: `orders`.
- Not used for tools whose rows are nested or single records (`search_products` has variants,
  `get_*` and the knowledge tools return one thing). *The risk the backlog names is overuse; the
  rule is a tool opts in by calling `visuals.table` with its own rows.*
- Figures are right-aligned with tabular digits; text cells are clipped to 80 characters and drawn
  as text; a missing cell is a dash. The table scrolls inside its card at 375 px (`Table` with a
  scroll label), never the page. "+N more" is a link when the API gave a safe path.
- *Rows are `{cells: [...]}` in column order, not a dict by column key: smaller, and OpenAPI
  generates a plain tuple-like list.*

### Progressive visuals (VIS-10)
- `applyAgentStepEvent` (`lib/agent/cache.ts`): when a step of a tool in `VISUAL_TOOLS` succeeds
  and the run is open in this browser (it has a cached detail), the run detail is invalidated,
  debounced at 300 ms (steps that finish together share one fetch; a later step waits again).
  Events still carry no result: the set of tools is the only signal.
- `RunView` shows `run-visuals` under the working steps, so the visual appears before the answer
  is written. When the run finishes it moves to its usual place under the answer.
- `VISUAL_TOOLS` mirrors the API's tools that have a `visual` in their result. *A DB-free API test
  (`test_the_web_refetches_for_exactly_the_tools_that_can_carry_a_visual`) reads `cache.ts` and
  fails when the two differ, so a new visual tool can't ship without it.*
- *With the setting off a visual-tool step still costs one extra GET that returns `visuals: []`.
  Left as is: the web can't see the setting, and the fetch is tiny and debounced.*

### Prepare replies for these leads (VIS-12)
- The lead list shows "Prepare replies" on the latest answer (the same rule as follow-up
  questions). It asks, in the same thread, for a `draft_reply` on each of the conversations in
  `reply_ids`: the best-scored leads that have a conversation, **at most 3**, chosen by the API.
- **The request carries ids only** (no customer name or text goes into a prompt): "Prepare replies
  for these leads. Use draft_reply once for each of these conversations, one at a time, and send
  nothing: ... If a reply window is closed, skip that conversation and say so." It is shown as the
  member's question, ids included. *Cleaner would be a structured hint on the run (VIS-11's
  `AgentRunCreate.hints`); not built.*
- **Caps:** a draft is 2 credits and one tool call; a run has 10 credits and 8 tool calls
  (`RUN_CREDIT_CAP`, `MAX_TOOL_CALLS`). 3 drafts plus the turns that call them fit; 8 would not.
  *The backlog's "8 tools" is the call cap, but the credit cap binds first.* A unit test checks the
  arithmetic against both constants.
- **Never sent:** `draft_reply` is a draft-tier tool; it drafts and returns the text. Nothing in
  this path sends (a test checks no outbound message exists and that each draft is metered at 2
  credits).
- **Cards:** each draft is the existing `schedule_message` card that opens
  `inbox/<id>?schedule=1` with the text, no time. *Its label is now "Schedule a reply to <name>"
  (it was "Schedule this reply") so several cards can be told apart.* The name is customer text,
  clipped and drawn as text.
- *A lead whose reply window is closed fails its own draft with the tool's usual message and the
  others go on; the request says to skip and say so. Not pre-filtered: the contacts service
  doesn't hold the window, and a pre-check would cost one query a lead.*

### Evals and tests
- Eval: `trend-reach-30` now expects a `trend` visual holding the first and last days' readings;
  new `visual-leads-waiting` expects a `lead_list` whose scores are the seeded needs-reply
  conversations'. The visual-number check already requires every figure to be one a tool returned.
- API unit (run here): builders (gaps, summary, caps, size, links), the credit arithmetic, the
  `awaiting_reply` SQL, the orders table, the web/API tool list, kinds read back.
  `tests/unit/test_agent_visuals.py` was updated for the six kinds.
- API integration (written, not run): `tests/integration/test_agent_visuals_vis.py`: order and
  total, 10 cap, roles, the setting off, another workspace, the drafts and their credits, the
  trend from seeded days with a gap, the table, the run API with the new kinds.
- Web (written, not run): `lib/agent/vis-lib.test.ts` (layout, words, links, cache and debounce),
  `components/agent/VisualViewVis.test.tsx` (each visual, malicious text, the follow-up, the run
  while working), fixtures in `src/test/visuals.ts`.
- E2E `e2e/vis-07-12.spec.ts` (written, not run). The e2e API (`scripts/e2e/api.py`) gains `trend`
  on `/agent-runs` and `POST /__e2e/workspaces/{wid}/agent-leads`, which sets lead scores and runs
  the real `list_contacts`, `search_conversations` and (with `drafts`) `draft_reply` as steps,
  because the fake model calls no tools.
- **Checked centrally:** regenerate `apps/api/openapi.json` and `packages/api-client`
  (`TrendVisual`, `LeadListVisual`, `TableVisual`, `TrendPoint`, `LeadRow`, `TableColumn`,
  `TableRow`, `AnswerRef.kind` with `contact`, `list_contacts` is a tool not a route so no route
  change); typecheck, build, the integration and tenancy suites, vitest, the e2e spec.

### Left for later
VIS-11 (range controls), VIS-13 (the report page), VIS-14 (the OpenUI spike), VIS-X2 (quote
account names in the prompt), VIS-X4 (design-system entries for `TrendChart`, `LeadList` and
`DataTableVisual`), a two-series trend, a reply-window pre-check for the lead follow-up, and
localised labels.

## C-124 · Sequence follow-ups (GR-24, feature/followups-24-32-ask)

The four items C-118 left as "not built", on the same tables and hooks. Migration `0046` (after `0044`;
`0045` is the visuals branch's), expand-only.

- **Stop when a tag is removed.** New stop rule `stop_removed_tag_ids` (up to 20 tags) beside the
  existing `stop_tag_ids`. A removal arrives through `webhooks.events.contacts_tagged` like an addition
  (the contacts API, a flow's "remove tag" step and the agent already call it with `added=False`);
  `entry.on_tagged` now handles both. The enrolment is stopped with the new reason `tag_removed` and
  says "A tag they needed was taken off: VIP". Only the contact's *active* enrolments in sequences that
  list the tag are touched. The stop-reason check on `sequence_enrolments` is widened.
- **Start on a lead stage.** New entry type `lead_stage` with `entry_stage` (new, qualified, follow up,
  won or lost; every stage can start a sequence, "new" included). `entry.on_stage`, called by
  `webhooks.events.lead_stage_changed` (GR-18), now first stops the sequences that stop on the new
  stage and then enrols the contact in those that start on it, so a stage never stops the sequence it
  just started. The enrolment says "Lead stage: Qualified". It follows the usual rules: only an active
  sequence on the contact's own account, one active enrolment at a time, re-entry only if allowed.
  The `entry_type` check is widened; `entry_stage` has its own check.
- **Analytics** (`GET /sequences/{id}/analytics`, owners and admins, `services/sequences/analytics.py`).
  Computed on the server from the enrolments and step runs and cached in Redis for 5 minutes
  (`seqstats:<workspace>:<sequence>`; a cache outage only costs the query). Definitions:
  - entered, in it now, finished, stopped, with stopped split by reason (most first);
  - sent, skipped (split by reason code, with the sentence) and failed, from the step runs;
  - **replied** = a *sent* run followed by a customer message in the contact's conversation on the same
    account within 24 hours of the run (`window_hours` in the answer). Someone who answers two steps
    counts once for each. *My choice of window; the brief said "within the window after a step".*
  - per step: reached (the runs at that step plus the people it is next for), waiting, sent, skipped,
    failed, replied, reply rate and the share of everyone who entered, which is the funnel.
  The reply count is one `EXISTS` over `messages` (`ix_messages_thread` serves it). *Not built:* opens
  and reads, a date range, per-variable breakdowns.
- **Webhook events** `sequence.enrolled`, `sequence.step_sent`, `sequence.completed` and
  `sequence.stopped` through GR-04's catalogue (now 16 events with `order.refunded`; the catalogue test
  counts them). Payload: the contact, `sequence` (id, name), `enrolment_id`, plus the step (1-based),
  `step_count`, `sent_as` and `message_id` on a step, and `reason` and `reason_text` on a stop. `emit` is
  skipped when no endpoint wants the event. A person taken out by hand emits `sequence.stopped` with
  reason `member`. *The Zapier trigger list (GR-26) is unchanged: it has five triggers and does not
  expose `order.created` or `order.paid` either, so the sequence events are not added there.*
- **Web.** The editor offers "A lead moves into a stage" (with a stage picker) and a "One of these tags is
  taken off" group under "Stops when". The sequence page has a Numbers section (stat figures, the
  skip and stop reasons, and a `Meter` per step for the funnel) between the form and the people; it
  stays out of the way if the numbers can't load.
- **Ask.** `list_sequences` also lists the removed-tag stops ("the tag VIP being removed").
- **Tests.** Unit: `test_sequence_analytics.py` (the counts, rates and funnel from grouped numbers, the
  new entry and stop rules, the words). Integration: `test_sequence_follow_ups.py` (tag removed stops
  and leaves the others, a stage starts a sequence, validation, the numbers with a skip, a stop and a
  reply, the empty sequence, 404, the four events, the catalogue). Vitest: `SequenceNumbers`, `format`.
  E2E: `followups-sequences.spec.ts`. *Integration, vitest and e2e were written, not run.*
- **For the coordinator:** regenerate the client (`SequenceAnalytics`, `StepStats`, `ReasonCount`, the
  `lead_stage` entry type and `stage`, `removed_tag_ids` / `removed_tag_names`, `tag_removed` stop
  reason, `get_sequence_analytics`, the four `EventName`s). Migration `0046` follows `0044`; the
  coordinator re-chains it with the others.
- *Fixed in the combined batch:* a reply in the same second as the step's send now counts ("replied" compares at whole seconds, since Meta's webhook timestamps have no fractions); CI's fast runner caught it.

## C-125 · Order follow-ups (GR-32, feature/followups-24-32-ask)

Part payments, refunds, shipping, editing, status messages and the "request payment" flow step, on the
GR-32 tables. Migration `0047` (after `0046`), expand-only: `orders` gains `amount_paid_minor`,
`amount_refunded_minor`, `accept_partial`, `fulfilled_at` and `fulfilment_note`; two new tables,
`order_payments` and `order_refunds`; the status check gains `partially_paid`, `fulfilled` and
`refunded`, and the source check gains `flow`. Orders paid before it are backfilled with their one
payment. *Everything Razorpay-side below is unverified against a real account; see
`docs/verification.md` item 38.* PD-8 (commerce is Pro and Max) applies to all of it; nothing here is
pending another PD.

### Status and money
- **Statuses:** draft, awaiting payment, **partly paid**, paid, **shipped** (`fulfilled`), **refunded**,
  cancelled, expired. The money is rows, not a status: every payment is an `order_payments` row and
  every refund an `order_refunds` row, and the two totals on the order are kept equal to their sums by
  `services/orders/ledger.py`. Partly paid means some of the total is paid; paid means all of it.
  Refunded means everything paid has been given back; a part refund leaves the status as it is (the
  sheet shows "Partly refunded" and the amounts).
- **Part payments.** *Razorpay:* the payment request can set `allow_partial`, which creates the link
  with `accept_partial: true`; Razorpay's `payment_link.partially_paid` and `payment_link.paid` events
  each record the payment entity's own amount (the link's running total is only a fallback). A Razorpay
  payment is unique per order by its payment id, so a re-delivered event and the final `paid` event never
  count twice. A link that does not take part payments ignores a part (and logs it), as before. *In
  rupees only: unverified whether Razorpay allows part payments in other currencies, so the API refuses
  `allow_partial` for a non-INR order until a real account says otherwise.* *UPI:* a member records each
  payment (`POST .../mark-paid` with `amount_minor`; blank is everything left); more than is left is a
  422. Asking for payment again on a partly paid order asks for what is left (the link or UPI amount and
  the message say "Paid so far" and "Left to pay").
- **Cancelling** an order with payments is a 422 ("Refund them before you cancel it"); *a paid order was
  already final, and a partly paid one now is too.* Unpaid and expired orders behave as before.
- **Refunds** (`POST /orders/{id}/refunds`: `amount_minor` blank for everything, a required `reason`).
  Taken from the newest payments first. A Razorpay payment is refunded through the business's own keys
  (`POST /payments/{id}/refund`, normal speed, our reason in the notes); the refund is **pending** until
  Razorpay's `refund.processed` (or `refund.failed`) webhook arrives, or processed at once when
  Razorpay answers so. A UPI payment can't be sent back by us: the member pays it back themselves and
  the refund is recorded as processed at once ("paid back by you"). The refundable amount is paid,
  less processed refunds, less pending ones, so two refunds can't promise the same money; a failed
  refund frees it again. If Razorpay refuses or can't be reached on the first part the request fails
  (422 or 502) and nothing is recorded; on a later part the failed part is recorded as failed. **A
  refund made in the Razorpay dashboard** arrives as the same webhook and is recorded as "Refunded in the
  Razorpay dashboard" (ignored if it is more than was paid or the payment is unknown). The webhook card
  lists `refund.processed` and `refund.failed` to turn on.
- **Event** `order.refunded` (payload as for the other order events, plus `refund`: id, amount, reason,
  method, and `full`), emitted once when a refund becomes processed. `order.created` and `order.paid`
  also carry `amount_paid_minor` and `amount_refunded_minor`. `RAZORPAY_PROVIDER=fake` refunds
  (`rfnd_fake_<n>`, processed; `refund_status = "pending"` leaves one for the suite to finish with a
  signed `refund.processed`).
- **Shipping.** `POST /orders/{id}/fulfil` with an optional note (courier and tracking number) moves a
  paid order to `fulfilled`; shown on the order, in Activity and on the contact timeline ("Order #12
  shipped"). A shipped order can still be refunded.
- **Audit.** Every change writes a row: `order.edited` (changed parts, totals before and after, whether
  the link was cancelled), `order.marked_paid` (amount), `order.payment_requested` (method, partial),
  `order.cancelled`, `order.fulfilled`, `order.refunded` (amount, reason, methods) and
  `order.status_message` (sent or not); Razorpay-driven changes are system rows labelled "Razorpay"
  (`order.payment_recorded`, `order.refund_updated`); the flow step's rows are "Automation: name".

### Editing
- `PATCH /orders/{id}` while the order is a draft or awaiting payment (422 after that, with the status in
  words): `items` replaces the lines and re-prices them from the catalogue now (the same checks as
  making an order: switched off, no price, stock, one currency; another workspace's product is 404),
  `address` and `note` replace theirs (an empty note clears it). **A new total makes the payment link
  useless:** the old Razorpay link is cancelled (best effort) and the order goes back to a draft, unless
  the request carries `payment`, which asks for a new request straight after (and sends it). An edit that
  keeps the total leaves the link alone. The sheet's "Edit order" dialog shares the line and address
  fields with "Create order" (`OrderLinesFields`).

### Messages to the customer
- Every status change (`mark-paid`, `cancel`, `fulfil`, `refunds`) accepts an optional `notice`
  (`message`, `template_name`, `template_language`). The change is made first; the answer's `notice`
  says `{sent, reason}`, and the sheet toasts the reason when it didn't go.
  - **Inside the 24-hour window** it goes as text, the member's own words or the default ("Thanks, we've got
    your payment for order #12 (INR 1598.00).", "We've received INR 500.00 for order #12. INR 1098.00 is
    still to pay.", "Good news: order #12 is on its way. Delhivery 123", "Order #12 has been cancelled.",
    "We've refunded INR 200.00 for order #12. It can take a few days to show in your account.").
    Human Agent applies as for any member's message.
  - **Outside it on WhatsApp** only an approved *utility* template can go (an order update is not
    marketing, so marketing consent is not involved; GR-23's `approved_templates` is the source). Its
    variables are filled in this order: the customer's first name, the order number, the total, the new
    status in words; a template with more than four is refused. With no template chosen the message is
    not sent and the answer says "The 24-hour window has closed. WhatsApp only allows an approved
    template now. Choose a utility template to send this update."
  - **Outside it on Instagram or Messenger** it can't be sent, and the answer says why.
  - No conversation (the order has none) or an account that needs reconnecting also say so.
  The template picker in the sheet lists the number's approved utility templates with up to four
  variables (`OrderOut` now carries the conversation's `social_account_id` and `platform`).
  *Unverified:* that a utility template is accepted by Meta for these updates; the sandbox's
  `order_shipped` (two variables) is what the tests use.

### The flow step "request payment"
- New step type `payment` (`schemas.flows.PaymentStep`): `source` `items` (up to ten products, with a
  variant when the product has some, and a quantity) or `draft` (the conversation's latest order that is
  not paid yet: a draft, a WhatsApp cart, one awaiting payment, or one only partly paid), a `method`
  (Razorpay or UPI) and an optional `intro`. Like the product step it needs the `commerce` plan to be
  saved (402 "Asking for payment is part of Pro.") and is checked at activation: the method must be set
  up under Payments, the products exist, are switched on and have a variant chosen when they have
  variants, and `items` is not empty; it can't follow a comment's private reply. The flow editor has the
  step (`PaymentFields`).
- **At run time** (`services/orders/flow_payment.py`) the plan is checked again, a new order is made at
  the catalogue's prices *when the step runs* (source `flow`, nobody made it; the monthly cap applies),
  and the payment message goes as an automation message. Failures end the run with a plain reason in the
  step log and Activity: no plan, no unpaid order to ask for, a product gone or switched off or out of
  stock, the method not set up. A refused Razorpay key from inside a run is not written to the payment
  card (the run commits as a whole). The step's run row carries the `order_id`.

### Other places
Activity shows paid, shipped and refunded orders; the contact timeline has words for every status; Ask's
`list_orders` knows the new statuses and counts paid or shipped orders as paid; the orders page filters
by partly paid, shipped and refunded.

### Not built
Reminders for unpaid orders; refunds by the line (a refund is an amount, with a reason); automatic
restocking; shipping labels or courier tracking; delivery fees, tax and discounts; a customer-facing
order page; editing the lines of a partly paid order (refund and make a new one).

### Tests
Unit: `test_order_follow_ups.py` (what is left to pay or refund, the split of a refund over payments,
the default messages, the payment message of a part-paid order, the UPI amount, the Razorpay refund call
and statuses with a mock transport and the sandbox, the request shapes, the payment step's activation
checks). Integration: `test_order_follow_ups.py` (UPI parts and the rest, a Razorpay link taking parts
and each payment counted once, a part and then a full refund with the events and audit, the refund
rules, a pending refund finished by the webhook and a failed one freeing the money, a dashboard refund,
Razorpay failures, a UPI refund, shipping, editing and the link, status messages in and out of the
window, on WhatsApp with templates), `test_flow_payment.py` (the step's order and message, the price
read when it runs, draft mode, a plan that was left, a method not set up, saving and activating).
Tenancy: the new routes and tables in `test_isolation.py`; the purge and account-deletion lists have
the two tables. Vitest: `OrderSheet.test.tsx`, `lib/orders/format`, `lib/automations/flow`. E2E:
`followups-orders.spec.ts`. *The integration, tenancy, vitest and e2e tests were written, not run.*

### For the coordinator
- Regenerate the client: `OrderOut` (new money fields, `payments`, `refunds`, `notice`,
  `social_account_id`, `platform`), `OrderPaymentOut`, `OrderRefundOut`, `NoticeIn`, `NoticeOut`,
  `MarkPaid`, `CancelOrder`, `FulfilOrder`, `RefundCreate`, `OrderEdit`, `PaymentRequest.allow_partial`,
  `PaymentStep` / `PaymentItem` in the flow step union and `StepType`, the new statuses, `flow` order
  source, the operations `edit_order`, `fulfil_order`, `refund_order`, and the `order.refunded` and
  `sequence.*` event names. The web types are aliases waiting for it.
- `alembic check` for `0047` (after `0046`, which follows `0044`). Add the two refund events to the
  Razorpay dashboard's webhook for the live test. Owner track: a real test account to verify item 38.

## C-126 · The assign action in Ask's flow proposals (GR-36 + GR-20, feature/followups-24-32-ask)

GR-20 added the flow action `assign`; `propose_flow` could not draft it. Now it can.

- **The model's side** (`agent/tools/proposals.py`): an action step may be `assign`, with `assign_to`
  `member`, `round_robin` or `nobody` and, for a member, `member` (the member's name or email as the
  workspace lists them; never an id, like tags). `build_flow` resolves it with the workspace's roster
  (`assignment.roster`). A name is matched ignoring case against the member's name (or the part of the
  email before the @) and their email; no match is a `validation_error` that names the step and lists
  the team ("There's no team member called "X". Members of this workspace: ..."), which the model can
  correct; two members with the same name is "More than one member is called ... Use their email
  address instead."; a missing `assign_to`, a member with no name, or a member named for `nobody` or
  `round_robin` is refused with what to fix.
- **Validation is the editor's.** The gateway's `check_flow` already ran `flow_store.reference_errors`,
  which refuses an assign step whose member is not on the team ("That person isn't on your team any
  more.") or is missing ("Choose who gets the conversation."); no second rule was added. Approving
  saves a draft as for any flow.
- **Round-robin** works in a flow whatever the workspace's own setting says (C-117), but only to an
  *available* member. *Decision (the brief said "needs the workspace setting or says what to switch
  on"; the editor and the engine have no such requirement, and "same validation as the editor" won):*
  the proposal is accepted and its summary says what to switch on: "Nobody is available for assignment
  now, so the assign step would be skipped. Turn on availability for a member under Members." and/or
  "New conversations are not handed out in turn yet (Settings, Members). This step still assigns in turn
  when it runs." (`actions.assign_notes`, from `assignment.overview`.)
- **The summary** names the member ("assign to Ben Das"), "assign to the next available member" or
  "remove the assignee" (`flows.describe` takes the member names; without them it says "assign to a team
  member"), in the proposal card's lines. Ask's reading of an existing flow uses the generic wording.
- **Schema and prompts.** `ProposedStep` has `assign_to` and `member`; the tool description lists the
  actions in 500 characters (the registry test caps it). The eval set has `write-flow-assign`.
- **Tests.** Unit (`test_agent_actions.py`): resolving by name or email, in turn and nobody, every
  refusal, the stranger message listing the team, the card lines, the round-robin notes, the schema.
  Integration (`test_agent_actions.py`): a member is saved as an assign step in a draft, a stranger is
  refused before anything is stored, the round-robin notes with the setting off and nobody available.
- *Not changed:* the web proposal card shows the summary lines as they are; nothing there lists actions.


## C-127 · Theme single source and exception list (feature/theme-single-source)

Implements the theme audit (F-01 to F-17, exceptions E-01 to E-12). Visual consistency only: no
logic, API, routing, data or auth change. The guide is `docs/ui-audit/THEME.md`.

- **One source.** `styles/globals.css` is the only place a theme value is written. New
  `scripts/gen-tokens.mjs` (no dependencies; `pnpm tokens`, also `predev` and `prebuild`) parses it
  and writes `styles/tokens.generated.ts` and `.json`, both committed. `tokens.ts` keeps only the
  descriptions (name, use, swatch) and the type-role constants and reads the values from the
  generated file; `colorValue()` reads them too, and a chart alias resolves to its token. New
  `radiusValue()`. `tokens.test.ts` regenerates in memory and fails on drift, requires a `use` entry
  for every `--color-*` and none for a token that is gone, and forbids a theme literal in
  `tokens.ts`. `scripts/generate-icons.mjs` reads shell-1, shell-2 and fg from the JSON (the icons
  come out byte-identical). The brand gradient is `--gradient-brand` in `:root`, used by
  `bg-brand-gradient` and by Clerk's primary button (`var(--gradient-brand)`); the other gradients
  are variables too. Clerk's radii read `radiusValue("lg")` and `var(--radius-xl)`; the global error
  page reads `radiusValue("lg")`. DESIGN_SYSTEM §1.13 points to globals.css and is marked
  historical; §1.10 and §1.12 are updated.
- **Light mode is not built.** Dark only, as decided; THEME.md §1 lists the prerequisites.
- **Semantic names everywhere (F-03, F-04).** Hand-written code, `components/ui` included, uses the
  tokens: `bg-popover` to `bg-overlay`, `text-muted-foreground` to `text-fg-secondary`,
  `border-input` to `border-line-control`, `bg-primary` to `bg-brand-strong`, `border-border` to
  `border-line`, `bg-border` to `bg-line`, `ring-background` to `ring-canvas`, `text-foreground` to
  `text-fg`, `outline-ring`/`border-ring`/`ring-ring` to `outline-brand`/`border-brand`/`ring-brand`.
  Every mapping is the alias's own target, so no pixel moves. The `:root` aliases and `@theme inline`
  stay for `shadcn add` output, with a comment and a manifest entry; the lint bans the class names
  in all of `src`. The inert `--radius` is removed. `SavedReplyPicker` uses `FLOATING_SURFACE`.
- **F-01.** `bg-surface` (undefined, transparent) was in ActivityPage, ContactsPage, LeadsPage,
  SegmentBar and TagChip. The three cards and the table wrapper use `cardVariants()` (`panel`,
  `line` edge); the two chips use `bg-hover` (the neutral chip fill). This is a visible fix: those
  surfaces were transparent on `canvas` and are now `panel`.
- **Named shades instead of opacity modifiers (F-05).** 58 modifiers to 0. New tokens, all derived
  with `color-mix` from their base so they follow it: `media-wash` 20%, `media-chip` 70%,
  `media-heavy` 85% (media scrim: /20 to wash, /50 /60 /70 to chip, /80 /85 and `from-canvas/90` to
  heavy); `panel-glass` 50% (panel /30 /40 /50 /60 /70) and `panel-veil` 85% (the floating nav);
  `canvas-veil` 30% (canvas /20 /30 /40); `on-brand-soft` 15%, `on-brand-line` 30%,
  `on-brand-line-strong` 60%; `danger-line` 30%, `warning-line` 40%; `danger-fill-hover`;
  `fg-hover`. Exact duplicates use existing tokens: `success-soft`, `warning-soft`; `brand-soft/20`
  to `brand-soft`; `bg-raised/60` to `bg-hover`; the dialog footers' `bg-muted/50` to `bg-field`.
- **Gradients (F-06).** New `bg-glow-brand-top` (50% 55% at the top, as the hero had) used by Hero
  and LazyIllustration. AutomationShowcase's circular glow, the moving border, the lamp and the
  spotlight stay as listed marketing-effect exceptions.
- **Charts (F-07).** Legends use the `chart-*` tokens their bars use; data bars are
  `bg-chart-series-1` (TopIntentsCard was the gradient); gradients stay for meters and progress. The
  series chart axis is `stroke-line-strong` with no stroke opacity.
- **Cards (F-08).** App cards use `cardVariants` (SuggestionCard keeps its `rounded-lg` and padding).
  Marketing cards use `MARKETING_CARD`, `MARKETING_CARD_GLASS` and `MARKETING_CARD_HOVER` in
  `marketing/primitives.tsx`, static edges `line` (hover `line-strong`). Left: the PostComposer sticky
  bar (a bar that is a card only from `md`), the app chrome frames (sidebar, shell, inbox), the
  mock-UI cards inside `Illustrations.tsx`, and the Languages and Trust cards (a `canvas` fill).
- **States (F-09).** Hover on SuggestionCard's and EmojiPicker's small buttons and on the
  TemplatePicker option is `hover:bg-hover`; `disabled:opacity-30` is 50. `hover:bg-pressed` stays
  on three elements that already sit on a `hover` or tinted fill, where `hover` would be invisible:
  the Ask source chip and suggestion rows (AnswerText, AskConversation) and the download button on a
  file card inside a bubble (AttachmentView). The empty send buttons keep `disabled:opacity-100`
  (listed).
- **Inverse button (F-11).** New Button variant `inverse` (`bg-fg text-canvas hover:bg-fg-hover`)
  for Ask's stop button and the carousel arrows in PostPreview.
- **Type (F-12).** `tracking-eyebrow` and `leading-display` are theme tokens, so no arbitrary
  tracking or leading remains. SiteFooter headings use `EYEBROW`. Headings use the roles:
  `ITEM_TITLE`, `CARD_TITLE`, `SECTION_TITLE`, `PAGE_TITLE`.
- **Radius and shadow (F-13, F-14).** SiteFooter `rounded` to `rounded-sm`. The radius scale is
  written in `@theme`. New `--shadow-glow`, `-hover` and `-button` replace the 2xl, xl and lg shadows
  tinted with `shadow-brand/N`. Stale comments in `ui/floating.ts` and `lib/utils.ts` updated;
  tailwind-merge knows the new names.
- **Left as is.** F-10 (marketing border colours are now consistent through the shared constants;
  the implicit-colour borders are fine), F-15 (arbitrary sizes, not colour), F-16 (test literals, now
  listed), F-17 (emails: out of the web app and email clients can't use CSS variables; listed with
  the reason, not changed).
- **Lint and manifest.** `styles/colour-exceptions.ts` lists every intentional literal, allowed
  shade, runtime channel, token group, the shadcn layer, dark-only choice and static asset with a
  reason. `design-lint.test.ts` now also checks undefined colour tokens (built from globals.css),
  arbitrary colour/shadow/gradient values, colour literals and inline colour styles (ts, tsx, other
  css, `scripts/*.mjs`), shadcn alias class names anywhere in `src`, opacity modifiers on tokens,
  the focus names, disabled opacity, arbitrary tracking and leading, a bare `rounded` and `dark:`,
  with positive and negative self-tests, and it fails on a listed entry that is gone.
- *Deviation: the audit said a file that uses `colorValue()` may hold literals. It may not: the five
  such files are held to none by `tokens.test.ts`, and the one literal among them (the OG glow's
  `rgba(0,0,0,0)`) is a manifest entry.*
- *Deviation: the audit suggested `hover:bg-pressed` become `hover:bg-hover` everywhere; three stay,
  for the reason above.*
- *Deviation: shades are `color-mix` of a base token, not repeated rgb literals, so a base change
  carries to them. `colorValue()` therefore returns a `color-mix(...)` string for those tokens; none
  of its consumers uses one.*
- **On-screen changes** (for screenshots): the five F-01 surfaces; marketing: `panel` cards at 30, 40
  and 60 or 70% are now 50%, the sticky nav veil unchanged, static framed shots (hero, auth, the
  automation showcase) have a `line` edge, not `line-strong`, the footer headings are 11 px,
  secondary-coloured; the Hero glow is as before and the illustration cards' glow is narrower; calendar
  cells outside the month (30%) and closed hours (20% to 30%); media chips and captions at 70% where
  they were 50 or 60% (attachment tray) and 85% where 80 (media tray); the carousel arrows are solid
  white at rest; the Stop button is now a Button (a disabled Button ignores the pointer, so its tooltip does not show while it is disabled); the
  chart axis is white 20% (it was the brand colour at 20%); the Top topics bars are solid brand; the
  dialog footers are `field` (it was `field` at 50%); the sentiment card and metric comparison
  titles are semibold where they were medium; the plans heading on the billing page loses
  `tracking-tight` at 18 px.

## C-128 · Midnight palette, indigo brand and glass surfaces (feature/theme-midnight-glass)

The owner approved a preview ("Midnight + indigo + glass") that ran as an override stylesheet on
local-dev. This entry makes it real in the theme system (C-127), and the preview stylesheet is gone.

- **Palette.** The values are exactly the approved ones: canvas `#131520`, panel `#1B1E2A`, field
  `#181B26`, raised `#252937`, overlay `#222633`, lines and states as cool `214 219 255` alpha, fg
  `#F3F4F8`, fg-secondary `#A6A9BC`, brand `#6D6AF5`, brand-strong `#5550E0`, brand-deep `#2B2585`,
  brand-fg `#B5B3FF`, shell `#4B44C9` / `#231E6B`. Indigo, because the old blue sat next to Facebook
  and LinkedIn (platform fills) and next to the info and focus colours; Midnight was lifted from
  near-black to a charcoal-indigo at the owner's request. Measured: brand-strong carries white at
  5.82:1, fg-secondary is 5.4:1 or more on every surface, line-control 3.16:1 or more (3.55 on panel).
  Comments that quoted older ratios are updated.
- **Glass is tokens and utilities, not overrides.** New colours: `panel-frost` (82%), `card-glass`
  (68%), `overlay-frost` (86%), `raised-frost` (72%), `frost-outline` (45%), `line-glass` (8%); new
  shadows: `shadow-glass`, `shadow-highlight`, `shadow-button-primary`, `shadow-button-secondary`; the
  ambient light is `--gradient-ambient` on the body (base layer). The blur is in five `@utility`
  rules (`glass-pane`, `glass-card`, `glass-float`, `glass-raised`, `glass-outline`) that bundle the
  frost colour and the blur and fall back to solid under `prefers-reduced-transparency`. Chosen over
  Tailwind's `backdrop-blur-*` plus a colour class so that colour and blur can't drift apart and
  the fallback lives in one place. Every new colour has a `use` entry and appears on `/dev/tokens`.
- **Work panes are subtler than cards** (owner): 82% with a 10 px blur, because inbox and thread
  text sits on them; cards show the glass fully.
- **Where it applies.** I chose call-site utilities over making `--color-panel` itself translucent:
  `panel` is also the colour of chips, the date pill, marketing cards and `Alert`, which must stay
  solid, and a translucent token would break every `bg-panel` that sits on another surface. The work
  panes (about a dozen call sites in shell, inbox, Ask and the post composer) switched to
  `glass-pane`; `Card` / `cardVariants`, `FLOATING_SURFACE`, dialog, alert dialog, sheet, tooltip,
  sonner and `buttonVariants` (default, secondary, outline) carry the glass in their recipes.
  `CardInset` stays solid (a card on a card). The Save bar stays opaque (its test says so) and the
  marketing cards stay solid.
  *Deviation from the preview: the preview frosted every `.bg-panel` and `.bg-overlay` on the page,
  including marketing cards, small chips and the Save bar; those are now solid.*
- **Identity rings.** brand (indigo) and facebook (blue) are 1.24:1 apart in luminance; the identity
  test's floor went from 1.3 to 1.2, since the hues differ. Rings are still 3:1 on panel.
- **Icons.** `node scripts/generate-icons.mjs` was run; the PNGs use the new shell gradient.
- Tests that quoted the old classes or values were updated (card, button, floating family, sonner,
  tooltip 13:1, manifest, tone).

## C-129 · Light mode (feature/theme-midnight-glass)

Light mode with a Dark / Light / System switch. Dark stays the default and the marketing site stays dark.

- **Mechanism: `light-dark()` pairs.** Each differing colour is one declaration, `light-dark(LIGHT,
  DARK)`, in the same `@theme` entry, so the two values sit side by side and a token can't exist in one
  theme only. `<html data-theme>` sets `color-scheme` (dark, light, or both for System, which therefore
  follows the OS with no script). Chosen over a second block of overrides under a selector because that
  needs the dark values written twice to pin a subtree dark (the marketing pages), and over a `dark`
  class because `dark:` is banned. Checked that Tailwind's optimizer keeps `light-dark()` intact in
  custom properties. Needs a 2024 browser (Chrome 123, Safari 17.5, Firefox 120).
  `scripts/gen-tokens.mjs` splits the pairs (`colors`/`colorsLight`, `shadows`/`shadowsLight`);
  `themeInvariant` lists single-valued colours with reasons.
- **Choice and first paint.** Cookie `sh_theme` (dark | light | system, default dark), applied by a small
  script in `<head>`. *Deviation from the brief: no server read in the root layout.* The root layout is
  shared with the marketing pages, which are static and revalidated hourly; `cookies()` there would make
  them all dynamic. The CSP already allows inline scripts. Only a no-JS visitor differs: they get Dark.
- **Switch.** Settings → Appearance (new tab, everyone) and a Theme radio group in the workspace menu (the
  shell's account area; Clerk's own user menu can't hold a three-way control). It is the member's, per
  browser; no Save bar.
- **Palette.** Soft cool canvas `#F5F6FB`, white panels, cool ink alpha for lines and states, text
  `#14161F` / `#585C73`, the same indigo family (`brand` `#5B57EA`, `brand-fg` `#4640C8`,
  `brand-strong` and `brand-deep` unchanged, 5.82:1 with white). Status colours are darker on light so they
  read as text on their soft fills (success `#166534`, warning `#92400E`, danger-fg `#B91C1C`). Glass on
  light: panes 88%, cards 72%, floating 92% white frost with the same blurs; shadows are cool ink; the
  ambient glows are lighter (new tokens `ambient-1..3`). Every key pair is measured and held by
  `styles/contrast.test.ts`.
- **Marketing stays dark.** The layout wrapper carries `scheme-dark` and `bg-ambient`; `<html>` is pinned
  by an inline script on a first load and by `ThemePin` on a client navigation, so scrollbars, overscroll
  and portals match. Auth pages and the app follow the choice.
- **Runtime-literal consumers.** Clerk gets per-theme variables and base (component-level appearance);
  viewport `themeColor` starts dark and `ThemeSync` moves it; manifest, OG image, icons and the global
  error page stay dark; `statusBarStyle` stays black (read once by iOS). See THEME.md section 1.
- **Dark-only spots.** Shadows are pairs; the avatar edge lost `mix-blend-lighten` for a plain `line` ring;
  the grain is `--grain-opacity` (0 on light); `dark:` variant now follows `data-theme="dark"`; the
  inverse button works by token (near-black pill in light, also on photos).
- Not verified in a browser (no build or screenshots by brief): Clerk's merge of the per-component
  appearance over the provider's, and iOS status bar in light.

## C-130 · The weekly report per account, and the categorical chart palette (feature/weekly-report-accounts)

Owner: the report did not tell accounts apart and had one chart colour. Decided here, small calls:

- **`account_id` on `GET …/reports/weekly`.** Every figure, series, top intent and top post is that account's (`overview_stats` functions take an optional `account_id`); another workspace's account is 404 `not_found`. Leads and captures follow the contact's account and the automation's account. Knowledge-gap questions belong to the workspace, so an account's report returns 0 and none for them and the page hides the line. The digest is unchanged (workspace-wide).
- **Breakdown** (workspace-wide report only, additive `breakdown`, plus `accounts` for the picker and `account` when one is picked): per account messages received, people who wrote in, comments, replies sent (the reply rate's own definition), automation runs, reach and followers, each this week against last with 8 weekly points. Counts are never None except for a week before the workspace existed. Reach and followers are None with `unavailable` (`insights_not_granted`, `no_readings`) where the platform gives no insights, e.g. WhatsApp. Leads, response time and rates are not broken down by account.
- **Palette.** `--color-chart-series-2` to `-6` (orange, aqua, sky, yellow, magenta) join series 1 (brand indigo) in a fixed order, validated per theme with the data-viz checker (adjacent colour-blind separation and normal-vision floor pass in light and dark; the light yellow, aqua and magenta are under 3:1, so every chart has a legend, tooltip and table). A seventh entity folds into the neutral token. Shared pieces live in `components/charts/`.


## C-132 · Range and platform controls, report links, and the OpenUI spike (VIS-11, VIS-13, VIS-14, feature/vis-11-13-14)

The last three backlog items for Ask, on top of C-123 (branch `feature/vis-07-12`). Option C still
holds: the API builds every visual, the model neither writes nor sees one, and everything stays
behind `AGENT_VISUALS_ENABLED`. **One migration, 0045** (`agent_runs.hints`, nullable JSON,
expand-only). No new route, no new setting.

### Structured follow-ups (VIS-11)
- **`AgentRunCreate.hints`** (`RunHints`, `schemas/agent.py`): whitelisted keys and values only,
  `extra="forbid"`. Two kinds, never mixed: `range_days` (7, 30 or 90) and/or `platform` (`all`,
  `instagram`, `facebook`, `whatsapp`) repeat the question over another range or platform;
  `reply_conversation_ids` (at most 3, the same cap as the lead list) is VIS-12's "Prepare
  replies". Never free text from the screen. A follow-up needs a `thread_id` (422 without).
- **`request` is optional with hints.** The server words the member's side itself
  (`agent/hints.bubble`: "Same, for the last 90 days on Instagram", "Same, across all platforms",
  "Prepare replies for these leads") and ignores any text sent with hints, so the thread shows
  words, never ids, and the screen can't put its own words in the thread. *This fixes the gap
  C-123 recorded: the bubble no longer shows UUIDs.*
- **The planner applies the hint as if the member had asked** (`hints.instruction`): the member's
  earlier typed question (`AgentContext.last_typed`, carried as quoted data) asked again with the
  range and platform as tool arguments, same tools. Earlier follow-ups in the thread reach the
  model as their instruction, not their bubble. When the earlier question is out of the context
  window (six runs) the instruction says "your previous answer's question".
- **Stored:** `agent_runs.hints` holds the validated hints (defaults left out) and `request` the
  bubble; run responses return `hints` (null for a typed question) so the web shows what is
  chosen. *A migration was needed: the bubble must be words and the planner must still know the
  structure, and the run table had nowhere to keep it.*
- **Conversations are checked.** `reply_conversation_ids` that aren't the workspace's give 404
  `not_found`, the rule for every body that names a resource. An integration test covers it (the
  tenancy example body can hold only one resource per route, and `thread_id` already uses it).
- **Controls on the visual** (`VisualControls`, `lib/agent/controls.ts`): range chips and
  platform chips under `trend`, `metric_comparison`, and `ranked_posts` and `sentiment_summary`
  when they have a period (a single post has no range). Not on `lead_list` and `table` (their
  tools take neither). Shown on the latest answer only, like the other follow-ups. The chosen
  range comes from the visual's own period when it is 7, 30 or 90 days, the platform from the
  run's hints; none is shown as chosen otherwise. A change sends the whole selection, so one
  control keeps the other's choice. Clicking the chosen chip does nothing (no run for no change).
- **Credits, before the run.** Under the controls: "Changing this asks again. About 2 to 4 AI
  credits." (`agent_turn` is 1 credit a model call and a typical question takes 2 to 4,
  `billing/plans.py`; the same run, so the same price as typing the question). The controls turn
  off, with the reason in that line, when the plan has no AI credits, none are left (the
  composer's own message with the reset date), or fewer are left than the upper estimate (4):
  "You have 3 AI credits left this month, and a change can use up to 4." *The API only needs one
  credit to start a run; the stricter line is a choice so a change doesn't stop half way. Easy to
  loosen in `controlGate`.* The API still answers 402 `quota_exceeded` as before.
- **Retry** on a failed follow-up resends its hints, not its bubble words.

### Weekly report links (VIS-13)
- **`report` answer-ref kind** with `AnswerRef.week` (the Monday). `parent_id` is the account when
  the question was about one; `id` is derived from week and account (`uuid5`), so the same report
  is one source however often it is cited. The web opens `reports?week=<monday>[&account=<id>]`
  (`lib/agent/routes.ts`, both values re-checked there; a malformed ref opens `reports`) and
  labels it "Weekly report". Nothing in `components/reports` and no change to the page.
- **Which week matches:** the latest finished week (Monday to Sunday in the workspace's zone,
  within the report's 52 weeks) that lies wholly inside the tool's period (`report_week`, a
  function of dates only). A period with no whole finished week cites none; a running week is
  never linked, as the report page itself refuses it.
- **Tools:** `metric_trend` and `compare_periods` (the current period) cite it, for the account
  when the question named one. *There is no overview tool in the agent (Home's figures come from
  `compare_periods`); nothing else cites a report.* The label is "Weekly report, 12-18 Oct 2026"
  (with the handle for an account). It works with the visuals setting off: refs are not visuals.
- *The `?account=` parameter belongs to the report page work on `feature/ui-refresh`; until it
  lands the page shows the workspace report for the week and ignores the account.*

### The OpenUI spike (VIS-14), not shipped
- Done offline on the scratch branch `spike/openui` (`spike/openui/`), packages installed only
  there, `OPENUI_TELEMETRY_DISABLED=1`. Result and numbers:
  `docs/architecture/generative-ui/11-openui-spike-result.md` (on this branch too).
- **Decision: do not adopt; keep C.** 30 of 30 valid, 0 number errors in 521 numbers, p95 1.54 s
  as a separate call (about 0.25 s written inside the answer's own turn, an estimate); but no
  open-ended use the catalogue can't serve was found, which the gate requires.
- The Gemini key was read through the API's `Settings` (`apps/api/.env`), held in memory, never
  printed or written; about 140 calls in all.

### Tests
- API unit (run here): `tests/unit/test_agent_hints.py` (the words, the instruction, the
  whitelist, the request rules, which week a period links, the ref).
- API integration (written, not run): `test_agent_api.py` (a follow-up is worded by the server and
  keeps its hints; thread and whitelist; 404 for another workspace's conversation; 402 without
  credits), `test_agent_visuals_vis.py` (the trend and the comparison cite the week, for an
  account, none for a period without a whole week).
- Web (written, not run): `lib/agent/vis-lib.test.ts` (selection, hints, the credit gate, which
  visuals offer controls, the report path), `VisualViewVis.test.tsx` (the controls, the cost
  line, the explanation, busy). E2E `e2e/vis-11-13.spec.ts` (written, not run); the e2e seed
  (`scripts/e2e/api.py`) gains `report_week`; `vis-07-12.spec.ts` now expects the new bubble.
- **Checked centrally:** apply migration 0045; regenerate `apps/api/openapi.json` and
  `packages/api-client` (`RunHints`, `AgentRunCreate.hints` and an optional `request`,
  `AgentRun.hints`, `AnswerRef.week` and `kind` with `report`), then drop the hand-added
  `RunHints`, `AgentRun`, `AgentRunDetail`, `AgentRunCreate` and `AnswerRef` additions in
  `lib/api/types.ts`; typecheck, build, the integration and tenancy suites, vitest, the e2e specs.

### Left for later
VIS-X2 (quote account names in the prompt), VIS-X4 (design-system entries for the visuals and
their controls), a platform control on the lead list, a two-series trend, a reply-window
pre-check for the lead follow-up, and localised labels.

## C-131 · Facebook and Stories follow-ups (feature/followups-fb-stories)

What C-114 (Instagram Stories) and C-115 (Facebook publishing) recorded as "not built", built after
the owner approved it. **Every Meta behaviour below was written from Meta's docs and none has been
seen on a real Page or account.** Each is marked *unverified* and listed in `docs/verification.md`
item 50. The permission work is part of the second App Review submission (O-10,
`docs/ops/app-review.md` section 8).

### 1. A caption limit per platform
- **The numbers.** Instagram 2,200 characters (as before). A Facebook Page post 63,206 characters,
  the figure Meta's Pages documentation and Page tools give (*unverified*). They are
  `CAPTION_MAX_CHARS` and `FACEBOOK_CAPTION_MAX_CHARS` in `models/publishing.py`. The first comment
  stays at 2,200 for every platform (Instagram's; Facebook allows more, nobody asked for it).
- **Where they apply.** The columns and the request bodies hold the longest
  (`STORED_CAPTION_MAX_CHARS`; migration 0048 re-creates `ck_scheduled_posts_caption_length` and
  `ck_scheduled_post_targets_caption_override_length`), so a draft can hold a long caption. The
  checklist and the scheduling rules apply the platform's limit (`rules.caption_limit`): an account's
  own caption to its platform's; the shared caption to the strictest of the accounts that use it
  (those without their own caption). A Page-only post may be long; add an Instagram account and the
  caption fails with "Shorten the caption to 2,200 characters (now N)". The composer's counter and
  checklist (`captionLimit`, `checklist.ts`) do the same; the counter under each caption shows its
  own limit.
- **Not changed.** The AI caption writer and "improve" still work to 2,200 characters
  (`CaptionRequest`), so improving a longer Page caption is refused by the schema; hashtag
  suggestions likewise.
- **Migration 0048** (after 0047; written as 0050 after 0044, renumbered when stacked), expand-only. *Numbering:* 0046 to 0049 belong to the other
  follow-ups branch; the coordinator re-chains.

### 2. Story insights
- **Windows.** A Story is gone after 24 hours, so it has its own snapshot windows: 1 h, 6 h and 23 h
  (`STORY_WINDOWS`, new `SnapshotWindow.H23`, `ck_post_metric_snapshots_window` re-created in
  migration 0049). Feed posts and Reels never get 23 h (`ages.WINDOWS` leaves it out). A Story's
  grace ends 10 minutes before it goes down (the 23 h reading has 50 minutes), the 15 minute tick
  (`due_condition`) now includes Stories, and every `ages` function takes the post's windows
  (`windows_for(media_type)`).
- **What is read.** Every Story window reads the insights (a Story has no like or comment counts to
  read early) and is final when written (`insights_final`). The metrics: `reach`, `views`,
  `shares`, `replies`, `total_interactions`, `follows`, `profile_visits`, and from the `navigation`
  metric with `breakdown=story_navigation_action_type` the `taps_forward`, `taps_back`,
  `swipes_forward` and `exits` (`tap_forward`, `tap_back`, `swipe_forward`, `tap_exit`). The
  breakdown is asked for on its own, like `follows_and_unfollows`. A kind with no row in the
  breakdown is 0; a refused call leaves the figures unknown (never 0). Without the insights scope a
  Story gets an empty snapshot, so it is not asked for again.
- **Stored like other metrics:** `post_metric_snapshots.metrics` (new `PostMetric` keys `replies`,
  `taps_forward`, `taps_back`, `swipes_forward`, `exits`, `clicks`).
- **Shown.** The analytics reads already take any post: `PostPerformance` gains `extra_metrics`
  (`ExtraMetrics`: the Story and Page figures that `PostMetrics` does not carry, so every post's
  shared metrics and their comparisons are unchanged), and `AgeName` gains `23h`. A Story is shown
  at the latest reading it has reached and is compared only with the account's other Stories (and
  no other post with a Story); rankings (`top_posts`) and other posts' baselines still leave Stories
  out. Web: the published Story in the composer's status banner (the schedule's published view)
  shows "Reach 900 · Views 1,100 · Shares 7 · Replies 5 · at 6 h" (`story-insights`); "Comments and
  results" in the schedule menu opens the Performance card, which for a Story lists reach, views,
  shares, replies, taps forward, taps back, swipes forward and exits at 1 h, 6 h, 23 h or lifetime.
- *Unverified:* the metric names and the breakdown values; that insights can be read while the Story
  is up and for how long after it goes down; that `replies` and `navigation` are offered under
  Instagram Login.

### 3. Facebook Page post insights
- **Metrics.** `GET /{post_id}/insights?metric=post_media_view,post_total_media_view_unique,post_clicks&period=lifetime`
  gives `views`, `reach` and `clicks`; `GET /{post_id}?fields=shares` gives `shares`. Likes
  (reactions) and comments come from the live counts, as before. Meta replaced the old impressions
  metrics with these "media view" ones, so the old names are not used. A refused metric is read
  alone and left unknown (the Instagram helpers).
- **Schedule.** The same windows as Instagram posts: live counts at 1 h and 6 h, insights from 24 h,
  the 72 h run marks them final (no change to `snapshot_account_posts`; a Page now has
  `Capability.POST_INSIGHTS`).
- **Permission.** `read_insights`, asked for only with `FB_REQUEST_INSIGHTS_SCOPE` (default off, like
  `IG_REQUEST_INSIGHTS_SCOPE`); a Page connected without it has no `POST_INSIGHTS` and the
  Performance card says to reconnect. Sandbox Pages always have it. Account-level insights for Pages
  are still not built (account insights stay followers only).
- **Shown** where Instagram post metrics are: the Performance card on the post detail (reach, views,
  likes, comments, shares, saves, engagement rate, and a Page post's clicks; the wording names
  Facebook for a Page). Saves, profile visits and follows are Instagram's, so a Page shows "—".
- *Unverified:* the three metric names and `period=lifetime`; `values[0].value`; `shares.count`; how
  soon after posting the figures exist; that reactions are a fair "likes".

### 4. Facebook Reels
- **A choice, not a shape.** A Page video stays a normal video. The composer's Type section offers
  **Reel** when a Facebook Page is chosen (`kind: "reel"`, `PostKind.REEL`; migration 0050 widens
  `ck_scheduled_posts_kind`). A Reel is exactly one video of 3 to 90 seconds (*unverified limits*,
  `FACEBOOK_REEL_MIN_S`, `FACEBOOK_REEL_MAX_S`); 9:16 is only recommended, so another shape passes
  with a note ("9:16 fits a Reel best. Facebook may crop or add bars to this file."). It needs a
  Page ("Choose a Facebook Page for a Reel. Instagram already publishes a single video as a
  Reel."); with an Instagram account chosen too, the Instagram side is its usual Reel. The caption,
  hashtag and first comment rules are a normal post's. The stored `format` is `reel` (as for any
  single video).
- **Calls** (`platforms/facebook/publishing.py`): `reel:{video_id}`. Create is
  `POST /me/video_reels {upload_phase: start}` then the hosted file handed to the answer's
  `upload_url` with `Authorization: OAuth {token}` and a `file_url` header; the token is only sent
  to an https address on facebook.com. Status is `GET /{video_id}?fields=status`: FINISHED when
  `uploading_phase` is complete, ERROR when a phase failed, PUBLISHED once `publishing_phase` has
  started. Publish is `POST /me/video_reels {upload_phase: finish, video_id, video_state: PUBLISHED,
  description}`. The video id is the media id, read back as a video and stored as `reel`.
  `PlatformHttp.request` gained a `headers` argument for the upload call; `create_reel_container`
  gained `page_reel` (Instagram and the others ignore it).
- **Lost answers.** A plain Page post cannot tell a lost publish answer from one that never went
  out, so it still ends unconfirmed (C-115). A Reel's status shows the publishing phase, so after a
  lost answer the job reads the status first: PUBLISHED finds the post again
  (`find_published_media` reads the video), anything else ends unconfirmed. The check runs for every
  non-Instagram lost answer, and only a Reel or a video Story ever answers PUBLISHED. The sandbox
  does the same.
- *Deviation:* once `finish` is accepted the target is marked published, though Facebook may still
  be processing the Reel (the publishing phase); a later processing failure is not followed up.
- *Unverified:* the whole flow (`video_reels` bodies and answers, the upload host and header,
  `file_url` for a hosted file there, the phase and `status` values, `video_state`), the limits, and
  that `pages_manage_posts` covers Reels.

### 5. Facebook Page Stories
- **Same Type switch and rules as Instagram's:** one photo or one video, no caption (kept on the
  draft, never sent), no first comment, 3 to 60 second videos, any image shape (a note says who may
  crop), 24 hours (the banner says "Disappears ..."). The composer no longer disables Story for a
  Page (the old "Pages can't publish Stories" is gone). A Page has no publishing limit to check.
- **Calls:** a photo Story is an unpublished `POST /me/photos` (`storyphoto:{id}`) then
  `POST /me/photo_stories {photo_id}`; a video Story is the Reel's start and upload on
  `video_stories` (`storyvideo:{id}`), the same status, then
  `POST /me/video_stories {upload_phase: finish, video_id}`. The answer's `post_id` is stored as the
  media id (else the upload id). The target is a `story` media item, so "next post" automations
  never link to it.
- **Not readable, honestly.** Facebook has no read API for Page Stories: the permalink stays empty
  (no "View on Facebook"), the story picker's live list is empty for a Page (`list_stories` returns
  `[]`; the sandbox too), `get_published_media` returns nothing for a Story (the job keeps what it
  knows), and a Page Story has no insights (the published banner says "Facebook doesn't share
  figures for Page Stories"; its snapshots are empty). A photo Story's lost answer ends unconfirmed
  like any plain Page post; a video Story's is found through its status like a Reel's.
- *Unverified:* `photo_stories` and `video_stories` bodies and answers, the Page video Story limits
  (the Instagram ones are used), and that `pages_manage_posts` is enough.

### Shared notes
- **Migrations** 0048 (caption checks), 0049 (snapshot window 23h), 0050 (post kind reel), all
  expand-only, each with a downgrade that removes or rewrites what the old check would refuse.
- **Settings:** `FB_REQUEST_INSIGHTS_SCOPE` (default false) in `.env.example` and
  `docs/ops/deploy.md`.
- **Tests.** Unit: `test_page_caption_limit.py`, `test_story_insights.py`,
  `test_facebook_insights.py`, `test_facebook_reels_stories.py`; `test_story_scheduling.py`,
  `test_facebook_publishing.py` and `test_analytics_rules.py` updated. Contract:
  `test_story_insights.py`. Integration (written, not run): `test_facebook_reels_stories.py`, plus
  new cases in `test_metric_snapshots.py` (Stories read at 1 h, 6 h and 23 h; Page post insights; a
  Page Story), `test_analytics_api.py` (Story figures, the 23h age, Story comparison) and
  `test_story_publishing.py` (a Story may go to a Page). Vitest (written, not run):
  `checklist.test.ts`, `format.test.ts`, `PostPerformanceCard.test.tsx`, `StatusBanner.test.tsx`,
  `PostComposer.test.tsx`. E2E: `followups-fb-stories.spec.ts` (a long Page caption, a Page Reel, a
  Page Story) and `gr30-facebook-publishing.spec.ts` updated; the e2e seed can now add a video
  (`videoAsset`).
- **For the coordinator:** regenerate the client: `AgeName` gains `23h`,
  `PostPerformance.extra_metrics` and `ExtraMetrics`, `ScheduledPostDraft.kind` and
  `ScheduledPostSummary.kind` gain `reel`. The web uses the generated types for all of these
  (`ExtraMetrics` is an alias in `lib/api/types.ts`). Migrations re-chained as 0048 to 0050 after the
  other branch's 0046 to 0049. The shared lists (nav, plans, tenancy) are untouched (no new table
  or route).

## C-133 · Final batch: what the end-to-end run caught (feature/final-batch)

The final batch (VIS-07 to VIS-14, the GR-24, GR-32 and Ask follow-ups, the Facebook and Stories
follow-ups and the UI release) was written first and tested once at the end. Locally only the
checks CI doesn't run on a PR were run (e2e and the UI screenshots); CI runs the rest on the PR.
The e2e run found these in production code:

- **Conversation starters were never saved (GR-11).** `PUT` and `sync` in `api/v1/ice_breakers.py`
  didn't commit. The integration tests called the service directly, so they never saw it.
- **WhatsApp number health, first read.** The broadcast preview sends two requests at once; both
  inserted the `whatsapp_number_health` row and one failed on the unique key with a 500. The insert
  now runs in a savepoint (`services/broadcasts/health.py`).
- **Popups inside a dialog or sheet couldn't be clicked (C-128 Select upgrade).** `ModalInert`
  marked the modal's own portalled popups inert (`components/ui/modal-inert.tsx`).
- **Flow preview branch picks.** Choosing a second fork before the first one became the first
  fork's choice (`withChoice` in `automations/flow/PathView.tsx`, used by the preview and the match
  tester).
- **Flow editor at 375 px.** The "Send a saved reply" switch overflowed sideways (`size="sm"`).
- **The e2e stack** now starts the API before the web build, or the public API reference page was
  prerendered as "unavailable" and cached for an hour.
- *Not kept:* gr39's "a published story is in the live stories" check: the sandbox keeps published
  stories in the worker's memory, which the API process can't see in the e2e stack.
- *Open:* the UI shots inbox-list-1536 and conversation-1536 failed on a network error
  (`ERR_NAME_NOT_RESOLVED`); axe reports two contrast issues on sign-in.


## C-134 · Instagram collaborators, user tags, location and Reel options (FR-PUB-07, feature/fr-pub-07)

The owner approved the Instagram publishing extras of FR-PUB-07 ("user tags; collaborators;
location") and, in a second step, the Reel options. Meta's IG User Media and IG Media Collaborators
references were read on 2026-10-25; what the code relies on and what stays unverified is in
`docs/verification.md` row 51. Built on the combined branch at a1ef4f73 (migrations 0051, 0052).

### What Meta says, and where its pages disagree
- **Collaborators.** `collaborators` on `POST /{ig}/media`: Instagram usernames, feed images, Reels
  and carousels, not Stories. *Meta's pages disagree on the maximum: the publishing reference says
  up to 3, the collaborators reference up to 5. We allow 3* (`COLLABORATORS_MAX`), the stricter one.
- **Invites.** `GET /{media}/collaborators?fields=username,invite_status` returns Accepted or
  Pending, only for users who allow collaborator tagging, with the media creator's token. *Meta names
  `instagram_basic` and `pages_read_engagement` (Facebook Login); we connect with Instagram Login, so
  whether the read works at all is unverified.* A collaborator who is not returned stays Pending; a
  failed read keeps the last answer.
- **User tags.** `[{username, x, y}]`, x and y from 0 to 1 from the top left. The reference states no
  count limit; we use 20 per photo (Instagram's own limit in the app, unverified for the API). Tags go
  on single images and on the child image containers of a carousel. *The reference does not say
  whether Reels take them: we send none on Reels and the composer offers none on videos.*
- **Location.** `location_id` is the id of a Facebook Page that has a location. *The reference says
  both that carousels do not support it and lists it on the carousel container: we send it on the
  carousel container.* Finding a Page by place needs the Pages search, which for our app needs Page
  Public Metadata Access (App Review, not requested). **So there is no search: the composer takes a
  Page's numeric id or its `profile.php?id=` / `pages/…/{id}` link**, validated on save; a vanity
  link has no id in it and is refused with a plain explanation. Search waits on the review.
- **Reels (IG User Media).** 3 seconds to 15 minutes, 300 MB, `cover_url` (JPEG, 8 MB, sRGB, 9:16
  recommended), `thumb_offset` in ms (`cover_url` wins when both are set), `audio_name` (renamed
  only once), `share_to_feed`.

### Design
- **Stored per post, not per target.** `scheduled_posts.collaborators text[]` (at most 3, a check),
  `location_id`; `scheduled_post_assets.user_tags jsonb`; `scheduled_post_targets.collaborator_statuses`
  and `collaborators_checked_at`. Reel options (0052): `cover_asset_id` (an uploaded image, SET NULL),
  `cover_offset_ms`, `share_to_feed` (default true, as before), `audio_name`. A cross-post to a Page
  and Instagram sends the extras to the Instagram target only; Pages ignore them (the adapters take
  `extras` and drop it). Per-target values were not needed.
- **One value object.** `platforms.base.PublishExtras` (collaborators, location, user tags, cover
  URL, frame offset, audio name) and `ContainerMedia.user_tags` for carousel children. The adapter
  methods for images, Reels and carousel containers take `extras=`; `list_collaborators` is a new
  adapter method (Pages, the website chat and WhatsApp return nothing).
- **Where each field goes.** Image: collaborators, location, user tags. Reel: collaborators,
  location, `cover_url` or `thumb_offset`, `audio_name`, `share_to_feed`. Carousel: tags on each child
  image, collaborators and location on the parent. Stories: nothing (unchanged container).
- **Request.** `ScheduledPostDraft` gains `collaborators`, `location` (id or link), `user_tags`
  (`asset_id`, `username`, `x`, `y`), `cover_asset_id`, `cover_offset_ms`, `share_to_feed`,
  `audio_name`. Usernames are normalised (no "@", lowercase, repeats collapse). Bad input is a 422 on
  `collaborators`, `location`, `user_tags.{i}`, `asset_ids.{i}`, `cover_asset_id` or `audio_name`.
  `ScheduledPost` returns the same, `cover_url`, each asset's `user_tags`, each target's
  `collaborators` (`username`, `status`) with `collaborators_checked_at`, and `video_max_mb`.
- **Checklist.** One new key, `extras`, listed only when a post uses one (so existing posts show no new
  line). Plain-language failures: more than 3 collaborators, an invalid username, tags over 20 on a
  photo, an unreadable location, "not available on Stories", "an Instagram feature" for a Facebook-only
  post, Reel options on something that is not one video, a cover over 8 MB or not an image, a cover
  frame past the end of the video, an audio name over 100 characters. The composer computes the same
  checks locally. When the options stop applying (a Story, no Instagram account, not one video) the
  composer drops the hidden values so they cannot fail a checklist the user cannot see.
- **Errors from Meta.** A refusal that names `location`, `collaborator`, `user_tag`, `cover`,
  `thumb_offset` or `audio_name` gets a readable reason (no subcode is documented for them).
- **Invite status.** At publish every collaborator is Pending. `refresh_collaborator_invites` (periodic,
  every 15 minutes) reads each published Instagram target with collaborators, at most once an hour, for
  three days; `POST /v1/w/{wid}/scheduled-posts/{id}/collaborators/refresh` reads now (409 until the post
  has published). The published banner lists each collaborator as Pending or Accepted, when they were
  last read, a Refresh button, and "They can't be changed after publishing" (Meta has no call to
  change them). The job is in `jobs/recovery.py` and needs no new task module.
- **Sandbox.** Containers keep their extras; the sandbox refuses what Meta refuses (more than 3
  collaborators, collaborators on a Story, tags outside 0 to 1 or on a video, a location that is not a
  numeric id, a cover on a non-Reel). Invites read Pending, or Accepted for a username starting with
  "accept" or after `accept_collaborator`. The sandbox keeps its state in the worker's memory, so the
  API process (the Refresh button) cannot see an invite the worker recorded; e2e shows Pending and the
  "Checked" time, Accepted is covered in the integration and component tests.

### Reel options and limits (the owner's scope addition)
- **Length.** A single video for Instagram alone is a Reel: 3 seconds to 15 minutes (was 90 s with no
  minimum). Videos in a carousel and Facebook videos keep 90 seconds (*Meta's carousel video limits
  were not looked up: unchanged*); Stories keep 3 to 60; Facebook Reels 3 to 90. The upload
  registration limit (`POST_VIDEO`) is now 15 minutes, with the per-format rules in the checklist.
- **Size.** Meta takes 300 MB. Our upload is a signed single POST straight to Cloudinary (XMLHttpRequest,
  no chunking), and Cloudinary caps one request at 100 MB (the free plan's file limit too; larger
  files need chunked upload and a plan that allows them). *So the cap is a setting,
  `POST_VIDEO_MAX_MB`, default 100 (10 to 300), enforced when the asset is registered and in the
  checklist; the composer states the current cap from `ScheduledPost.video_max_mb`.* Above 100 MB the
  browser sends 20 MB chunks with `X-Unique-Upload-Id` and `Content-Range` (written to Cloudinary's
  documented protocol, not run). Raising the setting is an ops decision that depends on the plan.
- **Composer.** A single video for Instagram shows "Reel options": a cover (a frame in seconds, or an
  uploaded JPEG or PNG up to 8 MB; the image wins), "Also share to feed" (on by default), an audio name
  with the note that Instagram allows renaming it once. The preview shows the cover image, the audio
  name and the collaborators.

### Tags and the preview
Tags are placed in a dialog from a tile's Tag people button: tap the photo to place a tag, type the
username, drag the marker (or use the arrow keys), remove it. Positions are stored as fractions. The
preview draws the tags on the photo and shows "name and @collaborator" with a location line. Tapping the
preview itself was not used: the dialog gives a large, stable target and keyboard use.

### Not done, and pending
- Location search (needs Page Public Metadata Access; not requested).
- Tags on videos and Reels, and per-target values.
- A cover image uploaded in e2e (it needs real storage); the e2e uses the frame.
- *Pending PD-n:* none; the decisions above were scoped by the brief. The collaborator cap (3) and the
  tag cap (20) are constants in `models/publishing.py`.
- *For the coordinator:* regenerate the client (`UserTag`, `UserTagIn`, `CollaboratorResult`, the new
  `ScheduledPostDraft` and `ScheduledPost` fields, `ChecklistKey` gains `extras`, the
  `refresh_post_collaborators` operation); the web uses aliases in `lib/publishing/types.ts`.
  Migrations 0051 and 0052 are expand-only.

### Tests (written; the DB-free ones were run)
Unit: `test_instagram_extras.py` (parsing, checklist, payloads, sandbox, invite rules); the contract
test `test_instagram_publishing.py` gains payload cases; `test_publishing_rules.py` expects `extras`
only when used. Integration (not run): `test_instagram_extras.py`. Vitest (not run):
`TagDialog.test.tsx`, `InstagramExtras.test.tsx`, `StatusBanner.test.tsx`, `checklist.test.ts`,
`rules.test.ts`, `upload.test.ts`. E2E (not run): `fr-pub-07-collab-tags-location.spec.ts`.

*Fixed before the PR:* the composer checklist showed only the first passing line under the `extras` key, so with collaborators, a tag and a location set only "Collaborators: ..." was listed. `mergeChecklist` now keeps every passing `extras` line (one per option); other keys still show one. The `share_to_feed` field the generated client now marks as required is sent as `true` by the new-draft bodies (`newDraftBody`, `useCreateScheduledPost`).
Also fixed: `publish_target` set each collaborator's Pending invite after `settle`, whose `scheduled_post.updated` event is built inside it, so the live banner showed no invites until a reload. They are now set before `settle`.

- **Media-library video limit.** The upload is checked before the post format is known, so it allows
  the most any post accepts: 15 minutes (900 s), an Instagram Reel's limit. The 90-second limit for
  carousel and Facebook videos (and 60 s for Stories) is enforced when the post is saved, by the
  publishing rules. Upload message: "Posts use JPEG, PNG, WEBP or HEIC images, or MP4 or MOV video up to 15 minutes."

## C-135 · Polish A: contact names, account card colours and small leftovers (feature/polish-names-colours)

On top of the combined GR branch (migrations to 0052). **One migration, 0053** (expand-only).

### A name the team saved is never replaced
- **The rule.** `contacts.name_source` (`platform` default, or `team`) says who chose
  `display_name`; `contacts.platform_name` keeps the latest profile name the platform sent. The
  rule lives in one place, `services/contact_names.py`: a platform name is always stored in
  `platform_name` and becomes the shown name only while `name_source = platform`; an empty or
  missing name never overwrites anything.
- **Every channel.** *The owner asked about WhatsApp; the same code serves Instagram, Facebook, the
  website widget and WhatsApp, so the rule is built once for all of them.* Inbound messages
  (`ingest._inbound`), the profile follow-up (`ingest_followups._store`) and the widget's typed
  visitor name go through `apply_platform_name`; a new contact also starts with `platform_name`.
- **What counts as the team's name.** A rename (`PATCH /contacts/{id}` with `name`, in the app and
  the public API, which share `ContactPatch`) and a contact the team creates (public API
  `POST /contacts` with a name). `use_platform_name: true` hands the name back: `name_source` is
  `platform` again and `platform_name` is copied over (without one, the saved name stays shown
  until the next message brings it). *There is no contact CSV import in the product (only the
  catalogue imports files), and Ask has no write action that types a contact name, so there was
  nothing to change there.*
- **Responses.** `ContactRecord` and the inbox `ContactDetail` gain `name_source` and
  `platform_name`; the contacts list is unchanged.
- **Web.** The contact drawer has a Name field (a changed name is sent; a blanked one is not).
  When the team's name differs from the platform's, the drawer header and the inbox details panel
  show a quiet "Instagram name: Priya N." line (the platform word from the channel) with "Use this
  name". Existing contacts keep `name_source = platform` and an empty `platform_name` until their
  next message (*no backfill: older names cannot be told apart from team-typed ones*).

### Account cards in the platforms' own colours
- `PLATFORM_LOGO_BG` (`bg-instagram-logo-gradient`, `bg-facebook-logo`, `bg-whatsapp-logo`,
  `bg-web`) is used wherever a badge or tile holds the glyph alone: the account card, the AI
  settings account tile, avatar platform badges, the platform strip dot, the billing meter tiles and
  the marketing tiles. The darkened `PLATFORM_BG` stays for fills with text (contrast). DESIGN_SYSTEM
  §1.6 states the rule.

### Small leftovers
- **View on Facebook.** The post menu and the card peek in Schedule take their label from the
  platform of the account the link is from (`viewLabelOf`); the composer banner already did.
- **Sign-in contrast.** Clerk's "Secured by" line is an unnamed `<p data-variant="buttonSmall"
  data-color="inherit">` inside the footer; the `footer` element rule in `lib/clerk-appearance.ts`
  sets it to solid `fg-secondary` (both themes, since the variable follows the theme). *Not
  measured with axe here (no browser run); the selector is the one axe reported.*
- **Lead list platform control (VIS-11 leftover).** The lead list offers the platform chips only
  (`offersRange` is false for it: it is whoever is waiting now); `list_contacts` also accepts
  `facebook`.
- **VIS-X2.** Account names in the agent's system prompt are JSON-quoted on one line, at most 60
  characters (`agent/context.quoted`), so they are data. **VIS-X4.** DESIGN_SYSTEM §8.2 has the
  trend, table, lead list and controls. Both are marked in the backlog.

### Tests (written; the DB-free ones were run)
Unit: `test_contact_names.py`, `test_agent_context_names.py` (ruff, mypy and the unit and contract
suites pass). Integration (not run): `test_contact_names.py` (inbound fills and updates a platform
name, keeps a team name, a missing name never clears, rename sets team, revert works) and an assertion
in `test_public_api.py` (create sets team). Vitest (not run): `edit.test.ts`, `ContactDrawer.test.tsx`,
`PlatformGlyph.test.tsx`, `post-parts.test.ts`, `vis-lib.test.ts`, `VisualViewVis.test.tsx`, plus
class updates in `ContactAvatar`, `PlatformStrip` and `BillingPage` tests. E2E (not run):
`polish-names-colours.spec.ts`. *For the coordinator:* regenerate the client (`ContactPatch.name`,
`use_platform_name`, `ContactRecord` and `ContactDetail` `name_source` and `platform_name`); no
decision is pending an owner call (PD-n).

## C-136 Polish B: skeletons and layout shift

### Shared pieces
- `components/states/skeletons.tsx`: `SkeletonRegion` (the one `aria-busy` region with one polite
  "Loading" label), `CardSkeleton`, `RowSkeleton`, `RowCardsSkeleton`, `ListCardSkeleton`,
  `TableSkeleton` (for use inside a `CardBleed`), `ChartSkeleton`, `MetricTileSkeleton`,
  `MediaSkeleton` (a picture at its real aspect ratio). They use the real `Card`, so padding and
  radius match; colours are the existing `bg-raised` skeleton and the pulse stops under reduced motion.
- `Skeleton` is now `aria-hidden`: placeholders are invisible to assistive tech, the region announces.
- Contacts, Leads, Sequences, Broadcasts, Orders and Products use the shared pieces (a list card,
  row cards, a table with the real column count). Home, Comments grid, post detail, Schedule list,
  Knowledge and Automations already had skeletons shaped like their cards and were kept.

### No layout shift
- `PageFrame` no longer keeps the header height in React state. `--page-header-h` starts at a CSS
  value for a title-only header (3.8125rem; 4.3125rem from md) and the observer writes the
  measured value straight onto the page element, so the first paint and the measured value agree
  and nothing re-renders.
- Inbox attachments reserve their box: images and videos take the platform's `width` and `height`
  when present, otherwise a minimum box (images) or 16:9 (video) holds the place.
- Fonts: `next/font` (Geist) already self-hosts with `display: swap` and a size-adjusted fallback.
- The sidebar's collapsed state on first paint is unchanged.

### Measured
`e2e/layout-shift.spec.ts` records `layout-shift` entries (no recent input) from navigation to idle
for 27 pages on a desktop and a phone viewport, with the API slowed by 350 ms, and fails above 0.1.
It runs locally only (CI does not run e2e).

Measured on the e2e stack (Chromium, API slowed 350 ms, three contacts). Every page is at or below 0.1
on both viewports. CLS, desktop / phone:

home 0.003 / 0.002; inbox 0.0006 / 0.0004; comments 0.0006 / 0; contacts 0.0006 / 0; leads 0.0006 / 0;
orders 0.029 / 0.067; products 0.025 / 0.056; schedule 0.042 / 0; automations 0.004 / 0;
sequences 0.0006 / 0; broadcasts 0.0006 / 0; knowledge 0.0006 / 0; ask 0.002 / 0; reports 0.0006 / 0;
settings: workspace, connections, billing, ai, hours, replies, widget, appearance 0.0006 / 0 (each);
members 0.0006 / 0.026; agent 0.014 / 0.020; integrations 0.0006 / 0.004; notifications 0.005 / 0.042;
activity 0.001 / 0.004.

What the first run found on a phone (leads 0.22, agent 0.16, products 0.13, orders 0.11, members 0.11,
knowledge 0.075, automations 0.097) and the fixes:
- Leads: the stage buttons' counts arrived after the summary and widened them, so the row wrapped.
  The count's place is held (invisible "0") until it loads.
- Orders and Products: the Pro notice and the settings cards (Payments; Shopify, WhatsApp catalogue)
  grew above the list. The notice now sits inside the list card, and the settings cards come after
  the list. The table skeleton is 7 and 8 rows (the empty state is about that tall on a phone).
- Knowledge: the cards load on their own and pushed each other and the test box (below on a phone).
  They show together once sources, brand voice and questions have all answered; the test box waits too below xl.
- Members: the assignment card loaded between the list and the invitations; it is now last.
- Settings, Agent: the mode sentence is about four lines on a phone, the skeleton is now as tall; the
  mode badge and the AI credits box hold their places while they load.
- Automations: the Broadcasts button (a flag) re-wrapped the header; its place is held until the flag is known.
- `PageFrame`'s first-paint header height is 3.8125rem (4.3125rem from md), the title-only header's real height.
- The spec also logs which elements moved for a page above 0.05 (set `CLS_PAGES` / `CLS_VIEWPORT` to narrow a run).
It runs locally only (CI does not run e2e).

Still not tied to the page's data: the "gone cold" note on Leads, a Broadcasts button when the flag is
off, and a settings card that has no AI credits to show appear or disappear after load; they only show
for workspaces that have them.

## C-137 · Polish C: 404 handling and the 404 page (feature/polish-not-found)

Web only; no API, model or migration change.

**The 404 page**
- `app/not-found.tsx` answers any address no route claims, with a real 404 status and `noindex`. It
  wears the public site's frame (header, footer, always dark like the marketing pages) around
  `NotFoundPage`. Visitors get "Go to the home page", "See pricing" and "Sign in"; once Clerk says
  someone is signed in, "Open the app" replaces "Sign in".
- `app/(app)/w/[slug]/not-found.tsx` is the in-app version, inside the workspace layout so the
  sidebar stays: Go to Home, Open Inbox, Ask. A catch-all `[...rest]/page.tsx` under the workspace
  calls `notFound()` so unknown sub-addresses reach it instead of the root page. *Deviation from
  the brief:* no "search" link, because the app has no search page; Ask is the closest.
- The illustration (`components/not-found/NotFoundIllustration.tsx`) is one inline SVG from
  tokens only (`fill-*`, `stroke-*`): a short chat thread whose last message, drawn dashed with a
  "?", has drifted off. It bobs and twinkles through `nf-drift` and `nf-twinkle` in `globals.css`,
  and stays still under reduced motion. The requested path shows small under the text.
- The product name comes from nothing hard-coded in the new files; the copy never says it.
- *Known limit:* a `notFound()` thrown after a page has started streaming (the workspace pages
  under a `loading.tsx`) can still answer with status 200; the page shows the same 404 and Next adds
  `noindex` either way. The public 404 has the real status.

**Missing resources inside the app**
- `isNotFound(error)` (lib/api/errors.ts) is true for an API 404. `NotFoundState` shows "This
  {post, conversation, automation, broadcast, sequence} doesn't exist or was deleted" with a link
  back to the list. It replaces the earlier ad-hoc "Post not found" and "Automation not found"
  states (wording changed, tests updated) and is added to the conversation, broadcast and sequence
  pages, which showed the generic error. The contact drawer (`?contact=<id>`) shows the same text
  with "Back to Contacts" (it closes the drawer).
- A deleted resource and one in another workspace read the same, because the API answers 404 for
  both. Any other error keeps the error state with Try again.
- Orders, products and reports have no per-item pages, so nothing to map there.

**Tests (run in the polish-batch check: vitest and the e2e spec pass)**
- Vitest: `components/not-found/NotFound.test.tsx`, `components/states/NotFoundState.test.tsx`
  (`isNotFound` mapping included); `PostDetailPage.test.tsx` and `PostComposer.test.tsx` expect the
  new wording.
- E2E: `apps/web/e2e/not-found.spec.ts` (public 404 with status, noindex and links; app 404 in the
  shell; missing post and conversation with working back links; another workspace's contact and a
  made-up one read the same). Screenshots: `not-found-site` and `not-found-app` in ui-shots.

## C-138 · Landing page redesign and the empty illustrations (feature/landing-redesign)

Inspired by the section galleries on vibrant.design (patterns only: a "works with" strip, a connector
grid, a bento of product UI, a stats band, two-column FAQ, an oversized footer wordmark). No artwork,
copy or branding was taken from it. Web only: no API change.

### The empty feature illustrations
- **Cause.** The six pictures were client components behind `dynamic(..., { ssr: false })` and an
  in-view check (`LazyIllustration`). The server therefore sent an empty, glowing box, and anything
  that did not scroll and wait for the chunk (a full-page screenshot, a crawler, print, a slow or
  failed chunk) showed blank panels. It was not a theme-token regression: with a slow scroll in a
  real browser (dev and production build) they did fill in. I could not reproduce "empty even after
  scrolling" in my own browser runs; the markup-level cause above is what I found and fixed.
- **Fix.** `illustrations/Illustrations.tsx` is now server components, always in the markup, with
  no framer-motion: the card's own `data-reveal` entrance is the only animation, and the two pulses
  (beam, ping) are CSS under `motion-safe`. `LazyIllustration` and `Beam` are deleted. The typed-out
  draft text is plain text now. Tests: `Illustrations.test.tsx` (each picture is in
  `renderToStaticMarkup` with text and nothing hiding it) and the landing e2e spec.

### Sections, in page order
- **Hero**: headline and product shot unchanged, with a brand glow behind the shot and a "Works with"
  strip: platform glyphs we already ship (Instagram, WhatsApp, Facebook, website chat) and plain
  names for Shopify, Razorpay, Google Sheets and Zapier (no third-party logos). Facebook and Shopify
  carry a small "soon"; a link goes to Integrations.
- **Integrations** (replaces `Platforms`, which still said Messenger was "coming soon"): nine cards,
  one line and a status each. Instagram and WhatsApp "Official API"; website chat "On every plan";
  Facebook Pages and Live comments and ad replies "With Meta's approval" (C-108, C-122); Shopify
  "With our Shopify app listing" (C-116); Razorpay and UPI "Your own account" (C-120); Google Sheets
  and Zapier with the public API "Pro and Max" (C-103, C-109, C-110). *Decision:* the brief's "ads" is
  worded as "chats that start from an ad" (the messaging referral event, C-077), the only ad feature
  we have.
- **Features bento**: ten cards in a 6-column grid (4+2, 3+3, 2+2+2, 2+2+2; two columns on tablets,
  one on phones), each with a small token-only mockup and the "Illustrations with example data."
  caption. Core: AI replies, inbox hand-off, comment and DM automations, comment intelligence,
  scheduling with Reels, Stories and collaborators, Ask. Newer: analytics and the weekly report,
  catalogue with orders and payment links, sequences, team roles and assignment. Knowledge gaps,
  the website widget and notifications moved to a row of three small cards. Honesty: "Auto is part of
  Pro", commerce "Part of Pro", Shopify sync "arrives with our Shopify app listing", broadcasts "coming
  soon, once India's consent rules are checked" (O-11), collaborators on posts and Reels only (not
  Stories, C-134), round-robin "if you turn it on" (off by default), Free has 1 seat.
- **How it works, Automation showcase, Languages**: content unchanged; section padding tightened
  (`py-16 sm:py-20`, as on every section now). The automation picture is stacked on phones (the
  beam drawing needs about 30 rem).
- **Stats band** (`Stats.tsx`): "1 inbox for Instagram, WhatsApp and website chat", "3 languages",
  and the Free plan's AI credits and active automations read from `plan-table.json` (a test checks
  them). *Not shown:* any setup time, speed or customer number we can't back.
- **Social proof** (`SocialProof.tsx`, data in `lib/marketing/social-proof.ts`): typed, empty lists;
  the section renders nothing while both are empty (tested), so there is no placeholder. Quotes and
  logos need the person's or business's written permission.
- **Pricing**: component unchanged, only the section padding.
- **Trust**: same five points, in two columns on wide screens (heading left, points right).
- **FAQ**: same questions; heading, a short intro and the support address on the left (sticky on
  wide screens), the accordion on the right.
- **Final CTA and footer**: larger headline, "See pricing" next to "Start free", and three plain
  perks (Free plan with no card, the Pro trial days read from the plan table, official Meta APIs). The
  footer has an oversized decorative wordmark from `SITE_NAME` (`aria-hidden`, token colour
  `line-subtle`); it shows on every public page because the footer is shared. `Logo` now also
  reads `SITE_NAME`.

### Checks
- `tsc --noEmit`, `pnpm lint` and vitest for `components/marketing`, `app/(marketing)`, `styles`,
  `lib/marketing` pass. The design lint caught an arbitrary radius, an arbitrary text size and a
  `fill:` key; all fixed with scale classes.
- New `e2e/landing.spec.ts`: at 375, 768, 1280 and 1536 px every picture has content before any
  scroll, the sections are in order, nothing scrolls sideways and the page's layout shift is at most
  0.1. *The existing `layout-shift.spec.ts` covers the app's pages only, not `/`.*
- *Not done:* no new product screenshots (`public/marketing/*.webp` are unchanged); no Lighthouse run;
  the owner should look at the Hindi and Hinglish examples and the new copy once.

## C-139 · Rename: Social Hood becomes Amplychat (feature/rename-amplychat)

The owner renamed the product to **Amplychat** (amplychat.com). The legal entity behind it is a sole
proprietorship, **unchartd** (lowercase, as the owner writes it).

### What changed
- Every name a person can see: "Social Hood" is now "Amplychat" (capital A, rest lowercase) in web
  copy, marketing, legal pages, metadata and SEO, emails, API messages, the widget's branding line,
  the Ask prompts (`ai/prompts/agent.v1..v4.md`, edited in place: versions are not hashed and no
  test pinned their text) and test assertions. "Ask Social Hood" is "Ask Amplychat".
- Domains: `socialhood.com` is `amplychat.com` (support@ for every address, as the owner set on 2026-10-26: contact, legal and the `EMAIL_FROM` sender; api., app., clerk.;
  `.env.example` and settings defaults; the CSP and SSRF allow-lists and the error type base URL
  follow the constants). The bot user agent is `AmplychatBot` (`amplychatbot` in the robots token).
- Operator: `LEGAL.entityName` is "unchartd", so the footer reads "(c) year unchartd", the Terms say
  "between you and unchartd ("Amplychat", "we"...)" and the legal facts show "Operated by unchartd".
  The registered address, governing law, jurisdiction, effective date and grievance officer are
  still unset and still render nothing (no address, number or name was invented).
- Living docs (README, BUILD_SPEC, ops, testing, verification, security checklist, dev-whatsapp,
  product roadmap overview) use the new name. History is untouched: this file, `docs/roadmap/*`,
  QUESTIONS, ai-eval-log, the generative-UI decision records, competitor notes and the two dated
  requirement/review pages keep "Social Hood".

### Kept internal (renaming them would break running systems for no reader's benefit)
The Python package `socialhood` and its imports, the folder and repo names, Docker/compose names, DB
names (`socialhood`, `socialhood_test_*`), Alembic, `SOCIALHOOD_*` env vars, `socialhood_*` Prometheus
metrics, Valkey keys, cookie and localStorage keys, the `shk_` key prefix, `window.__socialHoodWidget`
and the widget's `socialHood: 1` postMessage tag, `@socialhood/*` package names, CI workflow names,
the Pydantic AI agent name `ask_social_hood` (trace label only), the `.test`/`.example` fake test
domains, and the file reference `knowledge/social-hood-product.md`.

### Owner to-dos
- Buy amplychat.com (and consider .in, .co, www redirect); point app., api., docs., clerk. at it.
- Trademark search for "Amplychat" in classes 9 and 42 (and India, since the business is there).
- Rename the display names in: the Meta app (and its App Review submission text), the Clerk
  application, Razorpay, Dodo Payments, and the Render and Vercel services.
- Set up email on amplychat.com (support@amplychat.com, the one mailbox; it is also the sender) with SPF, DKIM and DMARC, and
  verify the domain in Resend before the default `EMAIL_FROM` is used.
- Update Meta redirect URIs, webhook URLs, the Clerk allowed origins and the Google OAuth redirect
  when the domains move; `CORS`/`CSP` env values that name the old domain.

## C-140 · The Amplychat logo: the "amp bubble" (feature/amplychat-logo)

The owner asked for a logo for the new name (C-139) and, from ten concepts and five colour schemes
(`amplychat-logo.html` outside the repo), asked for the best one to be chosen. Chosen: **A, the
"amp bubble"**, in the existing indigo tile, with the wordmark in one colour.

- **Why this one:** a chat bubble holding three rising bars, so it says "chat" and "amplify" in one
  shape; it reads at 16 px (the favicon), where the letter, sparkle and wave concepts lost detail.
  The two-tone wordmark ("Amply" + "chat" in brand colour) was not chosen: brand colour is for
  non-text marks (globals.css), and one colour stays readable on any surface.
- **Colours:** unchanged tokens. The tile is the shell gradient (`shell-1` to `shell-2`), the bubble
  `on-brand` (`fg` in the generated icons), the bars `brand-deep`. The concepts page used a brighter
  indigo for presentation; the product keeps its existing tile so the shell does not change.
- **One shape, four places:** `LogoMark` (`components/marketing/primitives.tsx`, exporting
  `LOGO_BUBBLE_PATH` and `LOGO_BARS` on a 64-unit tile), the share image (`og.tsx`, same constants),
  `scripts/generate-icons.mjs` (the same geometry for the PNG icons) and the sidebar.
  The sidebar's `LogoMark` (`WorkspaceMenu.tsx`) was a plain gradient tile with no mark; it now renders
  the brand mark.
- **Icons regenerated:** `icon-192`, `icon-512`, `icon-maskable-512`, `badge-72` (one colour, bars cut
  out), `apple-icon`, and `favicon.ico`, which is now generated too (16, 32 and 48 px PNGs inside the
  .ico) instead of being a static binary.

## C-141 · Landing hero: the "one door" routing diagram (feature/hero-routing)

The owner asked for the hero laid out like a reference screenshot (a SaaS hero with a two-line
headline, two CTAs and a hub-and-spoke diagram of tools routed through a central logo tile, with
hairline structure and hatched side columns), "customised to what we provide". Layout and craft
only: no copy, logo or icons were taken from it. Web only: no API change.

### What the hero shows
- **Headline** (the page's one h1, `HERO_TITLE`, which the auth pages also show): "Every DM. Every
  comment. One inbox." with "One inbox." in `brand-fg` on its own line from `sm`. One-line subhead
  (`HERO_LINE`): "AI that knows your business drafts or sends the reply on Instagram, WhatsApp and your
  website, and hands the tricky ones to you." CTAs unchanged ("Start free", "See how it works") and the
  three-point trust row kept. The "Inbox, AI replies…" pill, FlipWords and the Spotlight beams are
  gone from the hero (the components stay; nothing else on the landing page used FlipWords).
- **Structure**: the text sits in a centre column with `line-subtle` side borders (from `lg`); outside
  it, `hatch-lines` (new utility in globals.css: 1 px `line-subtle` verticals every 6 px, masked to fade
  downwards). A `line-subtle` hairline divides the text from the diagram. The hub has a round glow,
  `bg-glow-brand-centre` (new gradient token, registered in tokens.ts).
- **The diagram** (`RoutingDiagram.tsx`, geometry in `routing.ts`): one coordinate system per layout;
  the SVG tracks and the HTML nodes are placed from the same numbers (nodes in percent of the box,
  sized in percent too), so endpoints line up at every width. Tracks are orthogonal with rounded
  corners (quarter arcs), `line-strong` hairlines, staggered turns so no two cross (a test checks it).
  - Sources, left: Instagram DMs ("DM" badge), Instagram comments ("Comment"), WhatsApp ("Chat"),
    Website chat ("Widget"), Facebook Pages ("soon", as in C-138: with Meta's approval). Platform
    glyphs and the `*-logo` tiles we already ship.
  - Hub: `LogoMark` on a two-ring bezel with port nubs where the tracks plug in, captioned
    "{SITE_NAME} AI". Above it, "Your knowledge" and "Your catalogue" joined by dotted tracks, under
    "Answers only from what you added" (C-122).
  - Outcomes, right: Reply in the same chat ("Reply", success tile), Needs you, for your team
    ("Hand-off", warning tile), Razorpay or UPI link ("Pro"), Lead to Google Sheets ("Lead", "Pro";
    Sheets is Pro and Max, C-103), Monday report (C-130). *Decision:* Zapier and webhooks left out to keep
    five per side; Integrations lists them right below.
  - Micro-labels: "Every message comes in" and "The right answer goes out".
- **Motion** (`effects/RoutingPulses.tsx`, the only client part): one clock (`useAnimationFrame`, runs
  only while the diagram is on screen) drives four examples of 6.4 s each: a brand pulse with the
  customer's message on a chip rides from the source into the hub, the hub and the knowledge ties light
  up, then the answer rides out to its outcome in success (reply, payment, lead) or warning (hand-off)
  and rests there; each node "breathes" (a ring swells and fades) when a packet arrives. Examples, a
  made-up shop, two in Hinglish with `lang="hi-Latn"`: DM "Is the blue kurta in M?" → "Yes, ₹1,499.
  Shall I send the link?"; WhatsApp "Haan, M wala bhej do" → "UPI link sent: ₹1,499"; comment "Mera
  order damaged aaya" → "Needs you: passed to your team"; website "Do you take bulk orders?" → "Lead
  added to Google Sheets". Only transforms and opacity move; chips ride on a full-size layer translated
  by a percentage of itself, so no layout shift.
- **Static first and reduced motion**: the server sends the whole diagram plus a still frame (the
  first example's two tracks lit at 60% and both chips in place). That frame is what visitors with
  `prefers-reduced-motion`, without JavaScript, or before the diagram scrolls into view see; the clock
  never starts under reduced motion.
- **Phones and tablets** (below `lg`): a stacked layout (`STACK`): sources in a row on top with short
  labels, vertical tracks into the hub, "Knowledge" and "Catalogue" beside it, outcomes in a row below;
  no badges or micro-labels there (no room). Capped at `max-w-md`. Nothing scrolls sideways at 375,
  768, 1280 or 1536.
- **Accessibility**: the figure has one sentence for screen readers (`ROUTING_SUMMARY`, a
  `figcaption.sr-only`); the drawing is `aria-hidden`.

### Product shot and the "Works with" strip
- The inbox screenshot moved to its own section right after the hero, `ProductShot.tsx` ("See the
  inbox" / "Where every conversation lands"), with the same `ContainerScroll` tilt and the example-data
  caption. It is no longer `loading="eager"`/high priority: the headline is the first screen's largest
  paint now.
- The "Works with" strip is removed: the diagram shows the channels, and Integrations (next but one)
  lists every tool with its status.

### Checks
- `tsc --noEmit` (after `next typegen`), `pnpm lint`, vitest for marketing, `app/(marketing)`, `app`,
  `auth` and `styles` pass. New `RoutingDiagram.test.tsx`: tracks start at their nodes and end in the
  hub, none cross, arc maths, and the nodes, 12 tracks per layout, hub, labels and still-frame chips are
  in `renderToStaticMarkup` with nothing hidden. `page.test.tsx` and `e2e/landing.spec.ts` updated for
  the new section order and h2.
- E2E `landing|GR-37|not-found`: 26 passed (layout shift ≤ 0.1 and no sideways scroll at all four
  widths). Screenshots at 375, 768, 1280 and 1536, with and without reduced motion, checked by eye.

## C-142 · Launch SEO: canonical apex, metadata, sitemap, structured data, verification tags (feature/launch-seo)

The public website goes live on Vercel first so Meta can verify the business; this pass makes it
ready for search engines and for that check.

### Canonical origin (decided)
- **`https://amplychat.com`** (the apex) is the one public origin. `www.amplychat.com` redirects
  to it (308, set in Vercel); the signed-in app is the same deployment under `/app` and `/w/…`, so
  there is no `app.` subdomain any more. `DEFAULT_SITE_URL` (`lib/marketing/site.ts`) is the apex;
  the API's production `WEB_BASE_URL`, CORS and Clerk authorized parties are the apex too (set in
  `infra/render.yaml` on feature/launch-sec, C-143; documented in `docs/ops/deploy.md`,
  `apps/api/.env.example`, BUILD_SPEC OQ-3). Leftover `socialhood.com` hosts in the production
  workflow's environment URL, the Prometheus targets and the Zapier app's default API base are now
  `api.amplychat.com` / `api.staging.amplychat.com`.
- The root layout sets `metadataBase` from the site URL, so every canonical and Open Graph URL is
  absolute on the apex (also the 404 and the app).

### Metadata
- Every public page: a unique title of at most 60 characters as shown ("… · Amplychat"), a unique
  description of 50 to 160 characters, a canonical, Open Graph and a Twitter card with `/og.png`.
  The landing title is "Amplychat · AI inbox for Instagram and WhatsApp" (`SITE_TITLE_LINE`);
  `SITE_DESCRIPTION` and eight longer descriptions (pricing, the six GTM pages, the API reference)
  were shortened. `app/public-metadata.test.ts` finds every `(marketing)` page by glob and holds
  each `PUBLIC_PATHS` entry to that, so a sitemap entry without a page fails the test.
- `noindex`: the `(app)` and `(auth)` layouts (`NO_INDEX`), unsubscribe and the 404 (unchanged).

### Sitemap, robots, llms.txt
- `PUBLIC_PATHS` adds `/developers/api` and `/security` (the page comes from C-143); the footer's
  "Compare and learn" links the API reference. Each entry has an ISO `lastModified`: the legal
  pages' "Last updated" date, the others `PAGE_UPDATED` in `site.ts` (bump it when a page's copy
  changes; a build date would claim every page changed on every deploy).
- robots.txt also disallows `/sign-up`, `/dev/` and `/api/` (`ROBOTS_DISALLOW`); a test checks no
  public path, `/apple-icon.png` or `/llms.txt` is blocked.
- `/llms.txt` (static): the product in plain words and links to every public page.

### Structured data
- Landing page: one `@graph` with `Organization` (name Amplychat, `legalName` from
  `LEGAL.entityName`, url, logo `/icons/icon-512.png`, support email, contact point; `sameAs` only
  once `SOCIAL_PROFILES` has real profiles), `WebSite`, `SoftwareApplication` (offers only when
  the plan list has a Pro price, else none) and `FAQPage` from the FAQ data.
- `BreadcrumbList` (Home, then the page) on the GTM pages, pricing, the API reference,
  data deletion and the three legal pages (from small `layout.tsx` files beside them, so the
  documents stay untouched). No ratings, reviews or counts anywhere.

### Verification tags
`NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION` (`google-site-verification`),
`NEXT_PUBLIC_BING_SITE_VERIFICATION` (`msvalidate.01`) and
`NEXT_PUBLIC_FACEBOOK_DOMAIN_VERIFICATION` (`facebook-domain-verification`), rendered only when
set (`verificationMetadata`), documented in `apps/web/.env.example` and deploy.md section 4.

### Website without the API
`next build` with `NEXT_PUBLIC_API_BASE_URL` unset passes and prerenders every public page. The
plan cards fall back to the bundled plan table and say "See pricing when you sign up"; the
"Prices couldn't be loaded just now" line is gone (it read as broken on a website-only deploy, and
the cards already say it). `/developers/api` shows "isn't available right now"; a data-deletion
status lookup says "Request not found". Clerk keys are still needed on every page (root layout and
middleware). Deploy.md section 5a covers this first deploy.

### Performance (measured from the build, not a deploy)
The landing page's LCP is the server-rendered h1 (no hero image); Geist is self-hosted by
next/font with preload and `font-display: swap`; images below the fold are lazy with `sizes`.
Client JS on public pages is about 355 to 395 KB gzipped (home 396, pricing 380, a GTM page 365,
404 354), most of it shared by the root layout: Framer Motion with React DOM (~63 KB), Sentry
(~67 KB, loaded even with no DSN) and Clerk (~46 KB). Not changed here: making Sentry and Clerk
load only in the app is a larger change than this pass.

### Owner to-dos
- Vercel domains: `amplychat.com` primary, `www` redirect, `staging.amplychat.com` (deploy.md §5).
- Google Search Console and Bing Webmaster Tools: verify `https://amplychat.com/` (tag through the
  env vars, or DNS TXT), then submit `https://amplychat.com/sitemap.xml`.
- Meta Business Manager: verify the domain (`NEXT_PUBLIC_FACEBOOK_DOMAIN_VERIFICATION`), then
  business verification with the legal name, the website and support@amplychat.com.
- Add real social profile URLs to `SOCIAL_PROFILES` once they exist.

## C-143 · Launch security pass (feature/launch-sec)

Security hardening for putting the public website live on Vercel at `https://amplychat.com`
(API on Render later). The full record, with the vendor-dashboard steps for the owner, is the
"Launch pass" section of `docs/security-checklist.md` (L-1…L-13).

### Decisions made here
- **HSTS gets `preload`** (two years, `includeSubDomains`). Sending the directive is harmless;
  submitting the domain to hstspreload.org is the owner's step, after every subdomain is on HTTPS.
- **`'unsafe-inline'` stays** on `script-src` and `style-src` only (A-4, re-checked): Next.js's
  per-page inline scripts can't be hashed, and nonces would make the public pages dynamic. A test
  now pins it to those two directives and keeps `unsafe-eval` out of production.
- **`upgrade-insecure-requests` on Vercel without an API** (`VERCEL=1` and no
  `NEXT_PUBLIC_API_BASE_URL`), so the website-only launch gets it; local production builds don't.
- **Permissions-Policy** turns off 15 features the app never uses; `autoplay` is left alone so a
  muted marketing video can still play.
- **security.txt `Expires` is computed**, 360 days ahead (RFC 9116 recommends under a year), and the
  route revalidates daily, so it never lapses between deploys. Canonical and Policy use `siteUrl()`,
  so they follow C-142's canonical origin.
- **`/security` makes no bounty and no legal safe-harbour promise.** It gives the testing rules and
  says we reply. A safe-harbour sentence is a legal commitment, so it is left to the owner (below).
- **Production settings refuse inexact origins.** `CORS_ALLOWED_ORIGINS` and
  `CLERK_AUTHORIZED_PARTIES` must be exact https origins and include `WEB_BASE_URL`'s origin;
  `API_BASE_URL` and `WEB_BASE_URL` must be https. Staging and local are unchanged.
- **`infra/render.yaml`** moves off the `socialhood.com` placeholders: web origin
  `https://amplychat.com` (with C-142), API `api.amplychat.com`, staging `staging.amplychat.com`,
  `EMAIL_FROM` `Amplychat <support@amplychat.com>` as in `.env.example`.
- **Dependencies**: `fast-uri` 3.1.8 → 3.1.9 by a lockfile-only edit (a `pnpm update` also drifted
  rolldown and others, so it wasn't used). pip-audit was clean.

### Left for other tracks
- `/security` needs a sitemap entry (`PUBLIC_PATHS` in `lib/marketing/site.ts`, SEO track, C-142)
  and a footer link (legal or SEO track).
- `docs/ops/deploy.md` still shows `app.amplychat.com` for `WEB_BASE_URL` and the Vercel domain; the
  SEO track's canonical change updates it to match `infra/render.yaml`.

### Owner decisions (recommended values)
- Safe harbour on `/security`: recommended "If you follow these rules and act in good faith, we
  won't take legal action against you for your research."
- When to submit HSTS preload: after the API and Clerk production subdomains are live on HTTPS.
- Switch from the Clerk development key to the production instance before real sign-ups.

## C-144 · Legal and trust pages for launch (feature/launch-legal)

Brief: make the public legal pages fit for Meta business verification and App Review, India's DPDP
Act 2023 and Rules, the IT Rules 2011 (SPDI), Razorpay's and Dodo Payments' site reviews, and Google's
API Services User Data Policy, for the facts today. Web only: no API change. **Not legal advice: a
lawyer must review every page before launch (launch checklist §6.4).**

### What changed
- **`LEGAL` (`apps/web/src/lib/legal.ts`).** `entityName` is `UNCHARTD`. *Decision:* the Udyam legal
  name in capitals, not "unchartd", because Meta compares the site's legal name with the registration;
  one value, used by every page, the footer ("© year UNCHARTD") and the structured data. New fields,
  each rendered only when set: `entityType` (set: "Sole proprietorship registered in India"),
  `proprietor` (set: Zakaur Rahman), `phone`, `grievanceResponseDays`, `supportResponseTime`.
  `LegalFacts` shows them in order: Operated by, Business type, Proprietor, Registered address,
  Phone, Email, Grievance officer. `grievanceDays()` defaults to 30 (the IT Rules 2011 ask for one
  month while they apply) and never says more than 90 (DPDP Rules, rule 14(3)).
- **Privacy Policy**, rewritten on the old one: the operator; Facebook Pages and website chat as
  sources; a "Data from Instagram, Facebook and WhatsApp" section (what we get, why, how long, how to
  delete: Meta Platform Terms §4); website chat visitors' data (messages, the name and email they
  give, consent records with the words shown, IP for abuse limits, a random visitor ID in local
  storage); contacts, orders and consent records; the AI disclosure (drafted by Google Gemini from the
  business's own knowledge; Auto sends without review only if the business turns it on; paid API, so
  Google doesn't use it to improve its products); a **Google user data** section with Google's Limited
  Use sentence (Sheets uses only `drive.file`, a non-sensitive scope, so the statement is not strictly
  required; it is there because Google's OAuth review looks for it, and it covers Google sign-in
  through Clerk too); the sub-processor table with a "Where" column; a second table for the services a
  business connects with its own account (Razorpay, Shopify, Google Sheets, Zapier, the API and
  webhooks) and exactly what each gets (checked in `razorpay/http.py`: name, phone, order number and
  amount; Shopify `read_products` only); retention for Pro **and Max**, and the 30-day webhook and
  Sheets delivery logs (`jobs/tasks/purge.py`); the 24-hour deletion promise (`PURGE_WITHIN`,
  `services/workspace_deletion.py`); rights with how to ask and which identifier to give (rule 14(1)),
  consent withdrawal as easy as giving it, nomination, grievances answered within `grievanceDays()`
  days (rule 14(3)), the Data Protection Board; breach notice contents (rule 7); children; transfers
  outside India.
- **Cookies.** *Decision: no banner.* We set only strictly necessary storage: Clerk's session
  cookies, the `sh_theme` theme cookie (C-129), local storage for view preferences and the widget's
  visitor ID, and the push service worker. No analytics or ad cookies and no third-party trackers
  (checked `package.json`: only Sentry, which sets no cookies). The DPDP Act has no cookie-specific
  rule, and strictly necessary storage needs no consent under the EU ePrivacy rule either, so a
  statement in the Privacy Policy is enough. Revisit if analytics or an ad pixel is ever added.
- **Terms**: the operator and proprietor; Facebook Pages "with Meta's approval" and website chat; Max
  "coming soon"; **Dodo Payments is the merchant of record** (checkout, payment, tax, invoice; its
  terms apply to the payment); a Delivery section; connected services (Razorpay, Shopify, Sheets,
  Zapier), and we never hold money a business's customers pay through its Razorpay; the business is
  the Data Fiduciary for its customers' data; "Contact and complaints".
- **Refund and Cancellation Policy** (renamed from Refund Policy, same `/refunds`): a Cancelling
  section (how, when it takes effect, no fee, deleting the workspace cancels at once), because both
  Razorpay and Dodo ask for a "refund and cancellation" policy; refunds go through Dodo as merchant of
  record; payments to businesses through their own Razorpay are theirs to refund. The refund terms
  themselves are unchanged and still OWNER REVIEW.
- **Shipping and Delivery Policy**, new, `/shipping`. *Decision: its own short page rather than only a
  Terms section*, so a payment reviewer finds it under the name they look for; Terms has a Delivery
  section that links to it. It says nothing is shipped, when access starts, what to do if a plan
  doesn't start, and that businesses' own orders ship on their terms.
- **Contact us**, new, `/contact`: "About us" (who runs it and what it is, for Razorpay's About us
  link) and "How to reach us" (email; phone once set; grievances and the reply time; the support reply
  time once set), the facts card, and links to the FAQ, pricing, data deletion, developers and privacy.
  `ContactDetails` is in `components/marketing/legal/ContactDetails.tsx`.
- **Data deletion page**: Instagram **or Facebook** (the callback serves both: `jobs/tasks/privacy.py`),
  "finishes within 24 hours", and a "Who runs Amplychat" facts card (app-review O-2 wants the legal
  name on this page too).
- **Footer and sitemap** (`lib/marketing/site.ts`, shared with the SEO track): the legal links are
  Privacy policy, Terms of service, Refund and cancellation, Shipping and delivery, Data deletion and
  Contact us, then Security (`/security`, the security track's page, C-143, at the coordinator's
  request; it resolves once the branches are combined). `/shipping` and `/contact` are in
  `PUBLIC_PATHS`; `/security` is left to the security track's sitemap entry.
- `LEGAL_DOCUMENTS.lastUpdated` is 2026-10-26 for all four documents.
- `docs/ops/app-review.md` O-2 lists `/contact` and the legal name casing.

### Requirements and where the site meets them

| Requirement | Source | Where |
|---|---|---|
| Meta: public privacy policy URL, not geoblocked | [Meta Platform Terms §4(a)](https://developers.facebook.com/terms/) | `/privacy`, linked in every footer |
| Meta: what Platform Data is processed, how, why, and how to request deletion | [Platform Terms §4(b)](https://developers.facebook.com/terms/) | `/privacy` sections 2, 4 and 10 |
| Meta: deletion available to every user; data deletion callback and status page | [Platform Terms §4(b)](https://developers.facebook.com/terms/), [data deletion callback](https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback) | `/data-deletion` (status by code), the API callback, `/privacy#deleting` |
| Meta verification: legal name, website and email match | `docs/ops/app-review.md` O-2 | `UNCHARTD` and support@amplychat.com on every legal page, the footer and `/contact`; the address once set |
| DPDP: plain-language notice, itemised data, purposes, how to withdraw consent, exercise rights and complain to the Board | DPDP Act s.5 and s.6; [DPDP Rules, rule 3](https://dpdpa.com/dpdparules/rule3.html) | `/privacy` sections 2, 3 and 11 (consent prompts in the app are the businesses' notices, not ours) |
| DPDP: publish how to make rights requests and the identifier needed | [rule 14(1)](https://dpdpa.com/dpdparules/rule14.html) | `/privacy#your-rights`, "How to ask" |
| DPDP: grievance system and response period (at most 90 days) | [rule 14(3)](https://dpdpa.com/dpdparules/rule14.html) | `/privacy#your-rights`, `/contact` (30 days by default) |
| DPDP: nomination | Act s.14, rule 14(4) | `/privacy#your-rights` |
| DPDP: contact of the person who answers questions | rule 9 | support@amplychat.com everywhere; the grievance officer once set |
| DPDP: breach intimation to each affected person and the Board | Act s.8(6), rule 7 | `/privacy#security` |
| DPDP: children (under 18) | Act s.9 | `/privacy#children`, Terms (18+) |
| DPDP: retention and erasure | Act s.8(7), rule 8 | `/privacy#retention`, `#deleting` |
| IT Rules 2011 (SPDI): privacy policy on the website; grievance officer's name and contact published; grievances answered in one month | [IT (SPDI) Rules 2011, rules 4 and 5(9)](https://www.meity.gov.in/writereaddata/files/GSR313E_10511%281%29.pdf) | `/privacy`; one month by default; **the officer's name needs `grievanceOfficer` set** |
| Razorpay: About us, Contact us, Pricing, Terms, Privacy and Refunds links | [Razorpay business website details](https://razorpay.com/docs/payments/dashboard/account-settings/business-website-details/) | `/contact` (About us and Contact us), `/pricing`, `/terms`, `/privacy`, `/refunds` |
| Razorpay: Contact us with registered name, address, phone and email; shipping and refund timelines | [Razorpay's guide](https://razorpay.com/learn/breaking-down-the-requirements-for-accepting-international-payments-through-razorpay/) | `/contact` (**phone and address need the owner**), `/shipping`, `/refunds` |
| Dodo: public pricing with the billing interval, Terms, Privacy, Refund and Cancellation, a monitored contact, linked from the footer, matching the form | [Dodo verification process](https://docs.dodopayments.com/miscellaneous/verification-process), [business verification](https://docs.dodopayments.com/guides/business-verification) | `/pricing`, `/terms`, `/privacy`, `/refunds`, `/contact`, the footer on every page |
| Google: a privacy policy that documents Google user data use; Limited Use | [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), [Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth) (`drive.file` is non-sensitive) | `/privacy#google-user-data` |

Notes on the sources: the DPDP Rules were notified in November 2025 (G.S.R. 846(E)), with most
duties starting 18 months later (about May 2027); the dpdpa.com pages are a mirror, so check the
Gazette text. The SPDI Rules apply until the DPDP Act's repeal of IT Act s.43A takes effect.
Razorpay's own page lists no shipping policy, but its guide and its reviewers ask for one. Dodo's
docs don't ask for the legal name or a merchant-of-record line on the site; we state both anyway.

### Owner decisions (unset until the owner sets them in `LEGAL`)

| Field | Recommended value | Why it matters |
|---|---|---|
| `registeredAddress` | Publish it, or a business address you can receive post at (a virtual office is fine) | Razorpay wants an address on Contact us; Meta may compare it with the Udyam record |
| `phone` | A business number you answer (a separate SIM or a virtual number) | Razorpay's Contact us check |
| `grievanceOfficer` | `{ name: "Zakaur Rahman", email: "support@amplychat.com" }` | IT Rules 2011 rule 5(9) want the name published; DPDP rule 9 a contact |
| `grievanceResponseDays` | 30 (the default) | One month satisfies both the SPDI and DPDP rules |
| `supportResponseTime` | "within 2 working days" | Shown on `/contact`; promise only what you can keep |
| `governingLaw` | "the laws of India" | Adds the Governing law section to Terms |
| `jurisdiction` | "the courts at Bettiah, Bihar" (or the district courts of Pashchim Champaran) | The same section |
| `effectiveDate` | The day the site goes live | Shown as "Effective …" |
| Refund terms | Keep the current default (no partial-period refunds, billing errors refunded within 30 days of the charge) unless you want a first-payment money-back window | Marked OWNER REVIEW in `/refunds` |

Also for the owner to confirm: the "Where" column of the privacy table. Render and Vercel are
Singapore (`docs/ops/deploy.md`, `vercel.json`); Clerk, Cloudinary, Resend and Sentry are given as the
United States and Dodo as India and where it processes payments, from the providers' defaults, not
from our account settings. Check each dashboard (Sentry's region shows in the DSN host). The shipping
page says a paid plan shows "within a few minutes" and to write after an hour; adjust if Dodo's
webhooks are slower in production.

### Checks
- `next typegen`, `tsc --noEmit`, `pnpm lint`: clean.
- Vitest `src/lib/legal.test.tsx` (new: the owner fields stay unset, the new facts render only when
  set, `grievanceDays` and `telHref`, the contact page with today's config and with every field set,
  the shipping page in the all-pages check), `src/app/seo.test.ts` (shipping metadata, the two new
  sitemap paths, the new date), `app/(marketing)`, `components/marketing` and the copy lint: all pass.
- E2E and screenshots are left to the coordinator's combined pass.

## C-145 · Production on one GCP VM with Docker Compose (feature/vm-deploy)

Brief: the owner created a VM (GCP `amplychat-prod`, e2-standard-2, Singapore, static IP
34.126.136.162) and wants Amplychat deployed there instead of the Render + Vercel plan
(`docs/ops/deploy.md`). This entry covers the deploy code, the docs and a local proof. The first
deploy on the VM is done by the coordinator with the owner.

### What changed
- **Images.** `apps/api/Dockerfile` uses Python 3.13 slim (trixie) and uv 0.9.5. It runs
  `uv sync --locked --no-dev` in a builder stage; the runtime has only the venv, `alembic.ini`,
  `migrations/` and `scripts/worker.sh`, runs as uid 10001 and has a `/healthz` HEALTHCHECK. One
  image runs the API (CMD: uvicorn as in `render.yaml`), the worker (`bash scripts/worker.sh`) and
  migrations (`alembic upgrade head`). `apps/web/Dockerfile` builds the pnpm workspace (corepack
  uses `packageManager`, `pnpm fetch` then an offline install) and runs the Next.js standalone
  `server.js` as `node` on port 3000. Every `NEXT_PUBLIC_*` in `apps/web/.env.example` is a build
  argument. The Sentry token is an optional BuildKit secret. `CLERK_SECRET_KEY` comes only at run
  time.
- **`next.config.ts`:** `output: "standalone"` with `outputFileTracingRoot` and `turbopack.root` at
  the monorepo root, **only when `NEXT_OUTPUT=standalone`** (set in the Dockerfile). *Decision:*
  `next start` in the e2e stack (`scripts/e2e-stack.mjs`) doesn't work with standalone output, and
  Vercel, `next dev` and the tests have no reason to change. So the default output is untouched.
- **`infra/vm/`:**
  - `compose.yml` (project `amplychat`): `caddy` (fixed address 172.30.10.10 on the `edge`
    network), `web`, and under the profile `api`: `postgres` (pg18 + pgvector, tuned for about
    1.5 GB, `max_connections=200`), `valkey` (no persistence, `noeviction`, 256 MB), `migrate`
    (one-shot; `api` and `worker` wait for `service_completed_successfully`), `api` and `worker`.
    Postgres and Valkey sit on an `internal` network and are never published.
  - Memory limits total about 5.9 GB. Logs are json-file, 10 MB × 5. Images are
    `ghcr.io/zakaur-rahman/amplychat-{api,web}:${IMAGE_TAG}`.
  - **Website-only mode** is `COMPOSE_PROFILES` unset (`caddy` + `web`). The `Caddyfile` turns
    the proxy error for a missing API into a plain 503 with `Retry-After`.
  - `Caddyfile`: automatic HTTPS for the three hosts (ACME email support@amplychat.com), `www` →
    apex 308, no write timeout and `flush_interval -1` for the SSE stream, 10 MB request bodies
    (the API caps at 5 MB; media goes straight to Cloudinary), zstd/gzip for text but never
    `text/event-stream`, and no `Server` header.
  - The Caddyfile also keeps a JSON access log. The log drops OAuth `code`/`state`, `token` and
    Meta's `hub.verify_token`/`hub.challenge` from query strings. Hosts come from the
    environment, so a local run uses `localhost`.
  - `api.env.example` and `web.env.example` tag every variable [fixed], [generated] or [owner].
  - `gen-secrets.sh` writes `api.env` and `postgres.env` (mode 600, never overwrites, never
    prints a value). It fills the database password into both, plus `METRICS_TOKEN`, the two
    webhook verify tokens, a Fernet key and a VAPID P-256 pair from openssl.
  - `deploy.sh` takes a tag, `--rollback` or `--status`. It locks, writes `IMAGE_TAG`, pulls,
    runs `up -d` (migrate first), waits for health, records `PREVIOUS_IMAGE_TAG` and prunes
    images unused for 10 days. When a deploy fails, it starts the previous tag again and exits 1.
  - `backup.sh`: nightly `pg_dump -Fc`, checked with `pg_restore --list`. It keeps 7 daily and 4
    weekly dumps and nothing older than 30 days, with an optional `gcloud storage cp` to
    `BACKUP_GCS_BUCKET`.
- **`.github/workflows/production.yml`** replaces the Render deploy-hook job:
  - `prepare` picks the SHA. A manual run's `tag` must be a 40-hex SHA; it skips the build and
    checks both images exist in GHCR.
  - `build` is a matrix of `api` and `web`, using Buildx with the GHA cache. It pushes `:<sha>` and
    `:latest` with `packages: write`.
  - `deploy` runs in the `production` environment (the owner's approval). It sets up SSH from
    `VM_HOST`/`VM_USER`/`VM_SSH_KEY`/`VM_KNOWN_HOSTS`, tars `infra/vm/` (never env files) into
    `/opt/amplychat` and runs `deploy.sh <sha>`.
- `infra/render.yaml` is marked superseded. Docs: the new `docs/ops/deploy-vm.md` (runbook);
  pointers at the top of `deploy.md` and `backup.md`, in `runbook.md` and in `branching.md`
  (deploy step, secrets, workflows, what deploys where). `.gitignore` ignores `*.env`.

### Decisions
- **The web build variables live in a second environment, `production-build`.** It has no
  reviewers and its deployment branch is `main`. The brief asks for GitHub *environment*
  variables. Putting them on `production` would make the build job wait for an approval too,
  which means two approvals per release. Repository variables would work but aren't
  per-environment.
- **The Postgres password is shared through a third file, `postgres.env`,** not by giving the
  postgres container all of `api.env`. Least privilege: the database container never sees the
  vendor keys. `gen-secrets.sh` writes the same password to both files.
- **`IMAGE_TAG` has no default.** `docker compose config` needs it set
  (`IMAGE_TAG=x docker compose -f infra/vm/compose.yml config`). A `latest` default would let a
  stray `docker compose up` deploy an image that was built but never approved.
- **Uvicorn's loop:** auto (uvloop on Linux), as on Render. The selector-loop flag in the e2e stack
  exists only for Windows.
- **API forwarded headers** are trusted only from Caddy's fixed address
  (`FORWARDED_ALLOW_IPS=172.30.10.10`). Rate limits keep reading `X-Forwarded-For` from the right
  (`CLIENT_IP_HEADER`). Caddy replaces any `X-Forwarded-For` a client sends, so the header holds
  exactly the client's address.
- **Worker lanes are 10/4** (staging-sized) instead of Render production's 20/8: two vCPUs shared
  with Postgres and the web.
- **One uvicorn process**, as on Render's single instance. SSE, metrics and rate limits are in
  Valkey, so `--workers 2` is a safe later step.
- **Valkey has no persistence.** It holds only non-durable data (`docs/ops/backup.md`).

### Follow-ups (not done here)
- **Privacy policy hosting facts.** `/privacy` names Render and Vercel as sub-processors in
  Singapore. With the VM, the host is Google Cloud (asia-southeast1, Singapore). The owner and
  their lawyer should update the sub-processor table and the "where we store data" sentence
  before launch.
- **Point-in-time recovery.** The nightly dumps give an RPO of 24 h, against Render's 7 days of
  point-in-time recovery (§2.13). Add WAL archiving (pgBackRest or WAL-G to the GCS bucket) when
  the API carries real data.
- **CSP `upgrade-insecure-requests`** is only added on Vercel builds or when the API URL is https.
  In website-only mode on the VM it is absent. HSTS already covers the site, so this is cosmetic.
- **No hosted staging** any more. The Render staging stack is superseded with no VM equivalent.

### Checks (local, Docker Desktop)
- `IMAGE_TAG=x docker compose -f infra/vm/compose.yml config` validates; `caddy validate` and
  `caddy fmt` pass. actionlint and shellcheck are clean; yamllint passes (one long line that
  predates this change).
- Images built locally: API 125 MB compressed (563 MB on disk), web 109 MB compressed (463 MB on
  disk).
- Full stack with a throwaway `api.env` (`APP_ENV=staging`) on ports 8480/8443, with Caddy's
  internal CA for `localhost`:
  - `/`, `/contact`, `/pricing` and `/robots.txt` return 200 through Caddy; `www` returns 308 to
    the apex; HTTP redirects to HTTPS.
  - The API's `/healthz` returns 200 and `/metrics` returns 401. API responses carry no `Server`
    header.
  - Migrations reached 0053, with the `vector`, `pg_trgm` and `pgcrypto` extensions. The worker
    started both lanes and ran `ping`.
  - 61 requests with forged `X-Forwarded-For` headers gave 60 × 200 and 1 × 429. The access log
    dropped the secret query parameters.
  - `deploy.sh` with a broken API image waited, reported, and rolled back to the good tag.
  - `backup.sh` produced a dump; retention pruning was correct; the restore drill passed.
  - Website-only mode: web returns 200 and the API host returns 503 with `Retry-After`.
- `gen-secrets.sh` output checked in the API image: the Fernet key works and the VAPID private
  key derives the public key.
- `docker stats` (idle): worker 371 MB, api 205 MB, postgres 139 MB, web 75 MB, caddy 23 MB,
  valkey 5 MB.
- Web: `next typegen`, `tsc --noEmit` and `pnpm lint` are clean.
- Everything was torn down afterwards.

## C-146 · The signed-in app on dashboard.amplychat.com (feature/dashboard-host)

Brief: the owner wants the app (`/app`, `/w/…`, sign-in, sign-up) at
`https://dashboard.amplychat.com`, with the public website staying on the apex
`https://amplychat.com` (canonical, C-142) and the API on `https://api.amplychat.com`. DNS for
`dashboard` already points at the VM. This supersedes C-142's "no `app.` subdomain" for the app.

### How it works
- **One Next.js deployment serves both hosts.** The new public build value
  `NEXT_PUBLIC_APP_URL` is the app's origin. **Unset** (local dev, e2e, CI, staging), or equal to
  the site's origin, nothing changes: one origin, relative links, no redirects.
- **Routing** (`apps/web/src/lib/hosts.ts`, called first in `src/proxy.ts`, before Clerk's guard).
  The host is the `Host` header, which Caddy passes on unchanged.
  - Site host: `/app`, `/w/…`, `/sign-in…`, `/sign-up…` and `/dev/…` go to the same path and
    query on the app host (308).
  - App host: `/` goes to `/app` (307; signed out, `/app` goes on to sign-in as before);
    `robots.txt` is `Disallow: /` (answered by the proxy); `sitemap.xml` is a 404; every other
    path that isn't an app page or a shared file goes to the same path and query on the site
    (308): marketing, legal, `/unsubscribe`, `/data-deletion`, `/llms.txt`, unknown paths. App
    responses carry `X-Robots-Tag: noindex, nofollow` on top of the `(app)`/`(auth)` layouts'
    `noindex` (checked: both set `NO_INDEX`).
  - Both: `/_next`, `/icons`, the manifest, `sw.js`, `/.well-known` (security.txt), the favicon,
    `apple-icon.png`, `og.png`. Most of them never reach the proxy (its matcher skips static files).
- **Which pages belong where.** *Decision:* the route groups decide. `(app)`, `(auth)` and `(dev)`
  are the app; `(marketing)` is the site, **including `/unsubscribe`** (it works signed out and is
  a public page linked from email) and `/data-deletion` (Meta's status link).
- **Links without hops** (`lib/marketing/site.ts`): `appOrigin()`, `appUrl(path)` (absolute on
  the app host when set, else the path) and `siteHref(path)` (absolute on the site when the app
  has its own host). Marketing CTAs (Hero, How it works, Pricing incl. the Pro sign-up, the GTM
  pages, the final CTA), the header's Sign in / Start free / Open app, the footer's Sign in and
  Start free, the 404's actions and the unsubscribe page's "Open notification settings" use
  `appUrl`. In the app: the auth pages' logo (site home), Settings › API keys' "Read the API
  reference" and the 404's home and pricing use `siteHref`. Marketing pages' links to each other
  stay relative.
- **Clerk.** The production instance is on the root domain, so Clerk shares the session across its
  subdomains ([Clerk: deploy to production](https://clerk.com/docs/guides/development/deployment/production):
  "User sessions will also be shared across the subdomains"). With two origins the middleware
  passes `authorizedParties: [site, app]` (Clerk recommends it against subdomain cookie leaks), and
  `ClerkProvider` gets `afterSignOutUrl` = the site's home and `allowedRedirectOrigins` = both
  origins. Sign-in and sign-up URLs stay relative (`/sign-in`, `/sign-up`): they are only ever
  rendered on the app host. The marketing header's "Open app" for a signed-in visitor keeps working
  on the apex because the session is shared; if it ever isn't, the visitor just sees "Sign in",
  which lands in the app already signed in.
- **Service worker and push** register from the app (Settings, the push prompt), so on the
  dashboard origin, scope `/`; the subscription is stored by endpoint in the API and doesn't
  depend on the origin. The manifest (`start_url` and `id` `/app`) is relative, so on the
  dashboard it is right. *Not changed:* installing from a marketing page on the apex would open
  `/app` there, which redirects out of scope; the install prompt lives in the app, so this was
  left alone.
- **API** (`settings.py`): `WEB_BASE_URL` stays "links into the app" and becomes the dashboard:
  the OAuth return (`api/v1/oauth.py`), the Dodo checkout and portal returns
  (`services/billing.py`), notification and digest emails (`notify/templates`), team invitations
  (`services/team.py`). New optional `SITE_BASE_URL` (property `site_url`, falling back to
  `WEB_BASE_URL`) for links to public pages: the digest's unsubscribe page (`notify/outbox.py`),
  Meta's data deletion status URL (`webhooks/meta_privacy.py`) and the chat widget's brand link
  (`widget/routes.py`). So no email link needs a redirect. The `List-Unsubscribe` header still
  points at the API.
- **Production checks** (C-143 extended): `SITE_BASE_URL` must be https when set; its origin must
  be in `CORS_ALLOWED_ORIGINS` (the site's unsubscribe, data deletion and plans calls run in the
  browser); `CLERK_AUTHORIZED_PARTIES` must still include `WEB_BASE_URL`'s origin. The site never
  sends a Clerk token to the API, so the parties list only the dashboard. Tests in
  `tests/unit/test_settings.py` and `tests/unit/test_site_links.py`.
- **Infra:** the Caddyfile adds `{$APP_HOST:dashboard.amplychat.com}` → `web:3000` (same upstream;
  compose passes `APP_HOST`). `api.env.example`: `WEB_BASE_URL=https://dashboard.amplychat.com`,
  `SITE_BASE_URL=https://amplychat.com`, CORS both, Clerk parties the dashboard. The production
  workflow and `apps/web/Dockerfile` pass `NEXT_PUBLIC_APP_URL`; `web.env.example` and
  `apps/web/.env.example` describe it. Docs: `deploy-vm.md` (domains, the DNS row, the build
  variable, the checks, the vendor step), `deploy.md` (domain rows, §4 variables, §6 vendor URLs
  with `{SITE}` and `{APP}`), `apps/api/.env.example`, security checklist L-10.

### Owner to-dos (vendor dashboards)
- **GitHub** `production-build`: set `NEXT_PUBLIC_APP_URL=https://dashboard.amplychat.com`, then
  rebuild. **VM** `api.env`: the four values above (from `api.env.example`).
- **Clerk** (production instance): if Domains → allowed subdomains is restricted, allow
  `amplychat.com` and `dashboard.amplychat.com`; no satellite domain is needed (same root domain).
  Paths: sign-in `/sign-in`, sign-up `/sign-up` on `https://dashboard.amplychat.com`; after
  sign-out `https://amplychat.com/`.
- **Meta app:** App Domains `amplychat.com` and `dashboard.amplychat.com`; Facebook Login for
  Business / Embedded Signup "Allowed domains for the JavaScript SDK"
  `https://dashboard.amplychat.com`; Valid OAuth redirect URIs stay on `api.amplychat.com`
  (`/v1/oauth/instagram/callback`, later `/v1/oauth/facebook/callback`). Privacy policy, terms and
  data deletion instructions stay `https://amplychat.com/...`.
- **Sentry** web project allowed domains: both hosts.

### Checks
- Web: `next typegen`, `tsc --noEmit`, `pnpm lint` clean. Vitest: new `src/lib/hosts.test.ts`
  (both hosts, unset = nothing moves, `appOrigin`/`appUrl`/`siteHref`) and `src/proxy.test.ts`
  (the proxy with Clerk stubbed: redirects, robots, sitemap, noindex, `authorizedParties`), the
  header test with the variable set, and `src/lib`, `app/(marketing)`, `components/marketing`,
  `not-found`, `auth`, `integrations`, the layout and SEO tests: 93 files, 897 tests pass.
- API: `ruff check`, `ruff format --check`, `mypy` clean; `tests/unit/test_settings.py` and the
  new `tests/unit/test_site_links.py` pass.
- `caddy validate` (caddy:2.10-alpine): valid, `caddy fmt` unchanged; `docker compose config` OK.
- E2E with the variable unset: `--grep "landing|GR-37|not-found"`, 26 passed.
- Two hosts locally: `next build` with `NEXT_PUBLIC_APP_URL=http://dashboard.localhost:3200` and
  `NEXT_PUBLIC_SITE_URL=http://localhost:3200`, `next start`, `curl -H Host:`. Site host: public
  pages, robots, sitemap, llms.txt, manifest, sw.js, icons, security.txt 200; `/app`, `/w/…?c=1`,
  `/sign-in`, `/sign-up?redirect_url=…` 308 to the dashboard with the query; the landing page's
  CTAs are absolute dashboard links. Dashboard host: `/` 307 → `/app`; `/sign-in` 200 with
  `X-Robots-Tag`; `/app` and `/w/…` go to sign-in when signed out; `robots.txt` is `Disallow: /`;
  `sitemap.xml` 404; `/pricing`, `/privacy`, `/data-deletion?code=…`, `/llms.txt` 308 to the site;
  manifest, sw.js, icons, og.png, security.txt 200. Two artifacts of the local run, not of the
  code: Next rewrites a redirect to a `localhost` origin onto the request's address (the
  Location read `127.0.0.1:3200`), and the signed-out guard went to Clerk's hosted page because
  that build had no `NEXT_PUBLIC_CLERK_SIGN_IN_URL` (the Dockerfile defaults it to `/sign-in`).
  The server was stopped afterwards.

## C-147 · Images in Google Artifact Registry, not GHCR (feature/artifact-registry)

The owner plans to make the repository private later and wanted the setup ready for it now. Public
GHCR packages would have kept the API image (with its full Python source) public after the
repository went private, so the images move to **Artifact Registry** before the first deploy.

- **Where:** GCP project `amplychat`, repository `amplychat` (Docker, `asia-southeast1`), images
  `api` and `web`, private. A clean-up policy keeps the 20 most recent versions and deletes the rest
  after 60 days.
- **GitHub → registry, keyless:** Workload Identity Federation (pool `github`, provider
  `github-actions`) maps GitHub's OIDC token to `github-deployer@amplychat.iam.gserviceaccount.com`
  (Artifact Registry Writer on the repository only). The provider accepts only this repository, by
  its numeric id `1399054239` (renames and transfers don't widen it), and only `refs/heads/main`.
  No Google key is stored in GitHub; `packages: write` is gone from the workflow.
- **VM → registry, no password:** the VM's default service account has Artifact Registry Reader on
  the repository (its default scopes allow pulls); `deploy.sh` sets up gcloud's Docker credential
  helper once.
- **Identifiers in the workflow, not variables:** the provider path and the service account email
  aren't secrets and change only with the project, so they sit in `production.yml`'s `env`.
- **When the repository goes private:** nothing changes for the images. On GitHub Free the
  environment approval and branch protection stop working (GitHub Pro restores them); set
  `PRODUCTION_DEPLOY=manual` meanwhile (deploy-vm.md 4.2/4.3).
- Done on 2026-10-27 with gcloud as the owner's account; the commands are in deploy-vm.md 4.3.

## C-148 · Public pages without Clerk or Sentry in their first load (feature/public-perf)

C-142 measured 355 to 395 KB of gzipped client JS on the public pages, most of it shared: React
DOM with Framer Motion, Sentry (loaded with no DSN) and Clerk. The signed-in app lives on
dashboard.amplychat.com (C-146), so the public site doesn't need either.

### Decisions made here
- **Sentry is a lazy chunk everywhere.** `lib/sentry/client.ts` is the only browser code that
  imports `@sentry/nextjs`, and only with `import()`. No DSN: nothing is downloaded. With a DSN:
  the app (`/app`, `/w/…`) starts loading it at once; a public page loads it when the browser is
  idle (at most 4 s), and an error or unhandled rejection before then loads it and is reported.
  `instrumentation-client.ts` forwards router transitions once it has loaded; `global-error.tsx`
  reports through `captureError` (loads first). The app's own error boundaries and VisualView keep
  their direct import (same module instance). Server and edge Sentry are unchanged.
- **Clerk only where it is used, when the app has its own host.** `app/(app)` and `app/(auth)`
  move under one route group, `app/(clerk)` (URLs unchanged), whose layout adds Clerk's provider
  (`components/auth/AuthProvider.tsx`) once for both, so sign-in → app keeps it mounted. The root
  layout renders `RootAuth`: with one origin (NEXT_PUBLIC_APP_URL unset: local dev, e2e, CI) it is
  Clerk's provider on every page, exactly as before; with the app on its own host `next.config.ts`
  aliases it (Turbopack `resolveAlias`) to `RootAuth.split.tsx`, which loads no Clerk. A module
  swap, not an `if`: a layout ships every client component it imports whether it renders or not
  (measured: the `if` version still shipped all three Clerk chunks).
- **"Open app" from a cookie hint.** The header and the 404 read `useSignedIn()`. With one origin
  it comes from Clerk's `useAuth`; with the app on its own host from Clerk's `__client_uat` cookie
  (plain or suffixed, > 0 = signed in), which Clerk keeps on the registrable domain, read after
  hydration. A stale hint only leads to the dashboard, which asks for sign-in. Owner check after
  deploy: signed in on the dashboard, the apex header shows "Open app".
- **CSP `upgrade-insecure-requests`** (`servedOverHttps`): sent by a production build when every
  origin it was given (API, site, app) is https and there is at least one, or on Vercel. The
  website-only VM build (no API, https site and app URLs) now sends it; a local production build
  (http origins or none) still doesn't.
- **PWA install from the dashboard only.** Browsers ignore a manifest `start_url` that isn't
  same-origin with the page linking the manifest, so an absolute dashboard `start_url` on the apex
  wouldn't work, and the relative `/app` opened the apex, which redirects out of the app's scope.
  The manifest moves from `app/manifest.ts` (Next links that from every page) to a static route,
  `app/manifest.webmanifest/route.ts` (built by `lib/pwa/manifest.ts`). With one origin the root
  layout links it (every page, as before); with the app on its own host only `app/(clerk)` pages
  do, so the public site offers no install and the dashboard installs with `start_url` `/app`.
- **Not changed:** Framer Motion (the landing's effects and the navbar use it throughout; ~22 KB),
  the root Toaster and TooltipProvider (~20 KB together). Possible next steps if needed.

### Numbers (first-load JS, gzipped, every `<script src>` of the prerendered page)

| Build | 404 | home | pricing | /compare/manychat | /privacy | /app |
|---|---|---|---|---|---|---|
| Before, app on own host, no API | 353 | 395 | 379 | 364 | 359 | 415¹ |
| After, app on own host, no API | 248 | 290 | 273 | 259 | 253 | 358 |
| After, app on own host, with API | 248 | 290 | 273 | 259 | 253 | 374 |
| After, one origin (local, e2e) | 297 | 339 | 323 | 308 | 302 | 358 |

¹ with the API set. Public pages: about −105 KB each (Sentry −56, Clerk −49 plus Clerk's
clerk-js script from its CDN, which is no longer loaded on them at all).

### Checks
`next typegen`, `tsc --noEmit`, `pnpm lint`; vitest for app, marketing, not-found, auth, sentry,
security, pwa, styles, hosts and proxy (480 passed). Builds checked: the split build has no
manifest link on home, pricing or the 404 and one on /app; the one-origin build has it on every
page and Clerk on public pages as before; the split build's headers carry
`upgrade-insecure-requests`. The e2e run (`landing|GR-37|not-found`) didn't start: the main
checkout's `apps/web/.env.local` holds Clerk live keys and the stack only runs on a development
instance; CI runs it.

## C-149 · Production without Dodo (billing off) and without Sentry (feature/optional-billing)

The owner wants the production API live before the Dodo Payments live keys exist, and there is no
Sentry project yet. `REQUIRED_IN_PRODUCTION` listed `SENTRY_DSN` and the three Dodo values, so the
API refused to start. Both are now optional, the way Google Sheets and Shopify are.

- **Billing on or off:** `Settings.billing_enabled` is true with `DODO_PROVIDER=fake` or with all of
  `DODO_API_KEY`, `DODO_WEBHOOK_SECRET` and `DODO_PRODUCT_PRO_MONTHLY` set. Production refuses a
  partial set ("billing is half configured … all or none"), so a half-configured billing can't
  run; outside production a partial set is simply off. `DODO_PROVIDER=fake` stays refused in
  production. `DODO_PRODUCT_MAX_MONTHLY` stays optional on its own (Max is R2).
- **With billing off:** checkout, the portal, cancel and resume answer **503
  `billing_unavailable`** ("Paid plans aren't available yet."), before any other check, and never
  call Dodo; so does `POST /webhooks/dodo` (nothing stored). 503 rather than 409, because it is
  the server, not the workspace's state, that can't do it, and the existing "Dodo isn't set up"
  answer was already 503 (`service_unavailable`); the new code lets the web tell it apart from an
  outage. The 6-hourly `reconcile_billing` job returns at once.
- **What the UI reads:** `GET /v1/billing/plans` keeps all three plans with their entitlements
  but marks Pro and Max `available: false` with no prices (no Dodo calls); `GET …/billing` has a
  new required `billing_available` field and no prices. The web's `canStartCheckout` (checkout
  allowed and billing open) gates every Upgrade and trial offer: the billing page says "Paid plans
  aren't available yet. Everything on Free keeps working." with no button and Pro "Coming soon /
  Not on sale yet" in the plan cards; the upgrade dialog every 402 opens names the limit and says
  the same, with "View billing" for the owner; `?plan=pro` from the pricing page offers nothing.
  The marketing pricing shows Pro as "Coming soon" with what it includes and no trial or CTA.
- **Trials:** a trial only ever starts through a Dodo checkout (and its signed webhook), so none
  can start while billing is off. `trial_eligible` keeps its meaning (the owner hasn't used one);
  the UI ignores it while `billing_available` is false. Workspaces stay on Free; limits come from
  the plan table as usual.
- **Sentry:** an empty `SENTRY_DSN` means Sentry isn't started, as before outside production; in
  production one `sentry_off` warning is logged per process. The web's Sentry was already optional.
- **Visibility:** one `billing_off` warning at startup; `/readyz` (behind `METRICS_TOKEN`) has
  `features: {"billing": "on"|"off", "sentry": "on"|"off"}`, which never makes it unready.
- **Ops:** `infra/vm/api.env.example` has a new `[optional]` tag (Sentry, Dodo, Google, Shopify).
  `gen-secrets.sh --check` lists required empty values apart from optional ones, reading the tags
  from `api.env` and from the template beside it (so an `api.env` made from the older template
  still learns them). deploy-vm.md section 6 and 10, deploy.md and the security checklist (SEC-04)
  say what is required.
- **Tests:** settings (production without Dodo and Sentry loads; each partial Dodo set refused;
  the fake and outside production), the Sentry warning, every billing route and the webhook with
  billing off, the plan list and GET …/billing, `/readyz`; web: the billing page, the upgrade
  dialog, the `?plan=pro` offer, the plan helpers and the marketing pricing card.

## C-150 · Website chat isn't a connected channel until it's live; theme kept on refresh (fix/web-chat-channel-count)

Two production bugs the owner found on the first full deploy.

- **"1 channel connected" with nothing connected.** Opening Settings → Website chat makes the
  workspace's `web` account (GR-28) as `active`, before the widget is switched on or has a website.
  The home page's count and platform line, and the checklist's "Connect an account" and "Choose an
  AI mode" steps, counted it. Now `repositories/social_accounts.counts_as_channel()` decides once:
  a `web` account counts only while its widget is **enabled** and has **at least one allowed
  website** (until then it can't receive a chat); every other platform counts as before. Used by
  `overview_stats.accounts_connected`, `any_live` and `any_live_with_ai`. Test:
  `test_a_website_chat_counts_only_when_on_with_a_website`.
- **Theme reset on every refresh.** `THEME_INIT_SCRIPT` is a template literal, so the regex's `\s`
  became a bare `s`: `/(?:^|;s*)sh_theme=…/` matched the theme cookie only when it was the first
  cookie. On localhost it usually was; in production Clerk's cookies come first, so the saved choice
  was never applied before paint. Escaped as `\s`; a test runs the script with other cookies first.

## C-151 · Legacy timezone names in the API image (fix/legacy-timezones)

In production, saving a workspace's timezone failed with "Choose a timezone from the list." for
`Asia/Calcutta`. Chrome and Brave still report India as `Asia/Calcutta` (ICU's legacy name), and the
API checks the name against `zoneinfo.available_timezones()`. The API image is
`python:3.13-slim-trixie`, whose system tzdata has 486 zones: Debian trixie moved the legacy aliases
(`Asia/Calcutta`, `US/Eastern`, `Europe/Kiev`…) into the separate `tzdata-legacy` package. Locally
(Windows) zoneinfo reads the `tzdata` Python package, which keeps them, so tests never saw it.

- The runtime stage installs `tzdata-legacy` (599 zones, aliases included), so every name a browser
  sends is accepted and `ZoneInfo()` resolves it. Names are stored as sent.
- A build step asserts `Asia/Kolkata`, `Asia/Calcutta`, `US/Eastern` and `Europe/Kiev` are known, so
  an image without the aliases can't be built again.

## C-152 · Mobile speed and contrast on the public site (feature/launch-speed)

Live Lighthouse on amplychat.com (2026-10-28): mobile performance 76 (LCP 3.6 s, TBT 440 ms),
accessibility 97 on mobile and 96 on desktop (the footer wordmark's contrast).

**Measured** on a local production build made the way the VM makes it (standalone, split hosts),
Lighthouse 12.8.2, three runs each, medians. Local numbers differ from live, and this machine is
noisy (a single run can drop 20 points), so read the trend, not the last digit. Two local artefacts
were removed from the "before" so it compares like with like: Clerk's development instance makes a
handshake redirect on every cookie-less visit (production doesn't), and the standalone trace on
Windows misses sharp's DLLs, so images went out unresized (the VM's Linux image resizes them).

| | before | after |
|---|---|---|
| Mobile performance | 81 | 84–86 |
| Mobile LCP | 4.35 s | 3.6 s |
| Mobile Speed Index | 3.0 s | 2.6–2.7 s |
| Mobile TBT | 190–590 ms | 150–320 ms |
| Mobile accessibility | 97 | 100 |
| Desktop performance | 99 | 99 |
| Desktop LCP | 0.96 s | 0.80 s |
| Desktop accessibility | 96 | 100 |
| CLS | 0 | 0 |

The goal of 90 on mobile isn't reached locally. With scripts blocked the same page scores 98 (LCP
2.3 s): what is left is React's hydration of a ~3,300-element page and the framework's own scripts,
which Lighthouse's simulation counts into LCP because headless Chrome's first frame lands after them.
The next levers are a smaller landing DOM (Features and the two hero diagrams are the biggest) and
CSS-only versions of the framer-motion effects (lamp, moving border, trace line, scroll tilts), so
motion's code leaves the first load; both change how the page looks and are left for a decision.

**What changed**

- **Proxy:** on the public site's host the proxy returns before Clerk runs. The public pages never
  ask who is signed in (C-148: no Clerk in their bundle; the header reads the `__client_uat` hint),
  so this only drops work per request and the handshake redirect a visitor with a stale session
  paid on the first byte. The app host and one-origin setups run Clerk as before.
- **No prefetch of the page being read:** the logo, the header's section links (`/#…`) and CTA links
  to `#…` don't prefetch. The logo's prefetch fetched the home page's RSC again (180 KB) and decoded
  it on the main thread during load.
- **Less to download on the landing page** (Lighthouse, mobile, transferred): scripts 307 KB → 237
  KB, prefetch fetches 45 KB → 0, fonts 74 KB → 49 KB, everything 554 KB → 409 KB. `cn`'s tailwind-merge tables, Button and Radix left the public
  bundle. HeaderAuth and the 404's actions render both link sets on the server and a small client
  switch (`SignedInSwitch`) picks one; MobileMenu gets its content and classes from the server; the
  effects use `cx` (lib/cx.ts, a plain join) where nothing overrides a class; `MARKETING_CARD*`
  moved to `marketing/classes.ts`. The toasts and the tooltip provider moved from the root layout to
  `app/(clerk)/layout.tsx`: the public pages use neither. `colorValue`/`radiusValue` moved to
  `styles/token-values.ts` (tokens.ts re-exports them), so the theme sync and the global error page
  no longer bring the token catalogue's descriptions.
- **Motion after load:** LazyMotion's features download once the page is idle after load, and the
  hero's pulses are a server-rendered still frame until then; the moving layer
  (`RoutingPulsesLive`) is imported only when the page has settled, the diagram is on screen and
  motion is allowed, and it mounts only the example that is playing.
- **Hydration and rendering:** each landing section after the hero is its own Suspense boundary, so
  React hydrates section by section with yields in between, and sections from the third on have
  `content-visibility: auto` (with a remembered intrinsic size), so their style and layout wait
  until they come near the screen.
- **Fonts and images:** Geist Mono isn't preloaded (no page shows it above the fold); images are
  offered as AVIF first; the inbox shot's `sizes` matches its real width on phones.
- **Contrast:** the footer wordmark uses `line-control` (3:1 or more on every surface by design)
  instead of `line-subtle` (1.19:1). The hero's moving chips draw their words from a pseudo-element:
  they fade in and out, so for a moment their text sat below contrast; the diagram is decorative and
  the still frame keeps real text.
- **Not done:** a modern `browserslist` would make Next's output less modern, not more (its default
  targets are Chrome 111, Safari 16.4…), and the "legacy JavaScript" Lighthouse names is Next's
  polyfill module, which it always includes; it carries no score weight.

## C-153 · Guides section and a Hinglish page (feature/launch-blog)

To rank for real searches the public site needs useful content. A **Guides** section with its
first four articles, and the product explained in Hinglish at `/hi`. Web only: no API change.

### Content model (decided)
- **Typed React modules, no MDX, no CMS.** `@next/mdx` isn't installed, and a guide's claims should
  change in the same pull request as the code behind them. Each guide is a `Guide` in
  `lib/marketing/guides/*.tsx`: slug, title (at most 48 characters, so "… · Amplychat" stays within
  60), description (50 to 160), h1, published and updated ISO dates, author (`GUIDE_AUTHOR`,
  "Amplychat team" from `SITE_NAME`), reading time, tags, an optional hero (an existing `SHOTS`
  screenshot), optional FAQ, related links, and `Body`, a component of h2/h3 sections inside the
  shared prose styles (`components/marketing/prose.ts`, moved out of `LegalPage`).
- `GUIDES` (index.ts) is newest first; the index, the article route, the sitemap, the feed and
  llms.txt read it. `guides.test.tsx` holds every guide to the metadata lengths, 900 to 1,500 words
  in the body, a reading time of words / 200 rounded, sentence-case headings, no "please", no h1 in
  a body, internal links only to pages that exist, and the JSON-LD fields.

### Routes and SEO markup
- `/guides` (index: cards with topics, byline, date and reading time; an RSS link) and
  `/guides/[slug]` (`generateStaticParams`, `dynamicParams = false`, so any other slug is a 404).
  Both use `pageMetadata`; a guide adds `og:type article` with published and modified times, author
  and tags (`pageMetadata({ article })`), and both advertise the feed (`alternates.types`).
- **Structured data:** each guide emits one `@graph` with an `Article` (headline, description, url,
  `datePublished`, `dateModified`, author an Organization "Amplychat team", publisher the full
  `Organization` with `legalName`, the share image, keywords) and a `FAQPage` when the guide has its
  own questions on the page (all four do), plus a three-level `BreadcrumbList` (Home, Guides, the
  guide; `breadcrumbTrailJsonLd`). The index has Home, Guides. *`Article` rather than `BlogPosting`:
  these are evergreen guides, not dated posts.*
- **`/guides/rss.xml`** (static route handler): RSS 2.0 with each guide's h1, link, description,
  date and topics. Descriptions only, not the full text.
- Sitemap: `/guides` and `/hi` in `PUBLIC_PATHS`; each guide is added by `sitemap.ts` with its
  `updated` date as lastmod, and `/guides` takes the newest guide's date. llms.txt has a Guides
  section and the Hinglish page. The header nav and the footer's Product column gain "Guides"
  (`NAV_LINKS`); the footer's "Compare and learn" links the Hinglish page (with `lang`).

### The four guides
How to auto-reply to Instagram DMs without sounding like a bot; WhatsApp Business API vs the app;
comment-to-DM automations; replying in Hinglish. Every product claim matches the GTM pages and the
code: Off/Suggest/Auto with Auto on Pro, answers only from knowledge with knowledge gaps, Needs you
and the pause when you reply, the brand voice settings, keyword matching as a word, exactly or
anywhere (`MatchMode`), post scope including the next post, random public replies, tap-first, the
follow invitation never a condition, the send queue, templates from the inbox when the window has
closed (`TemplatePicker`), payment requests on Pro and Max, AI Polish keeping Hinglish in Latin
letters (`polish.v1`), `hi-Latn` in the analysis, Hinglish filler words in catalogue matching,
small talk. Gated features are worded as gated: Meta's approval for connections, Live comments and
ad chats; broadcasts "built, not switched on" (O-11); WhatsApp product messages need the business's
catalogue and Meta's approval. Meta's rules stated: one private reply per comment within 7 days,
the 24-hour window, templates and opt-in, per-message template pricing with a link to Meta's page
("under Meta's current pricing" for free service replies). *The app/API coexistence on one number is
described as "Meta has started letting some businesses…" and not claimed for Amplychat.* No
numbers, customers or quotes; the one example conversation is labelled as a made-up shop.

### Hinglish page (decided)
- **`/hi` in Hinglish (Roman script)**, the way most Indian sellers type, rather than Devanagari
  Hindi. Short: hero, six feature cards, one labelled example, "what to know" (Meta's approval, the
  24-hour window, Meta's WhatsApp fees, the three languages, Free with no card), sign-up. Same
  design and tokens; `lang="hi-Latn"` on its `<main>`, links to English pages marked `lang="en"`.
- **hreflang `hi`, not `hi-Latn`**: search engines document language (and region) codes for
  hreflang, not script subtags; the content's own `lang` says `hi-Latn`. `/` and `/hi` both carry
  `en`, `hi` and `x-default` (English) alternates (`LANDING_LANGUAGES`), in their `<head>` and in
  the sitemap (`alternates.languages`); own canonicals; Open Graph locale `hi_IN` on `/hi`.
- **A native speaker should review the Hinglish copy** (and the Hinglish examples in the Hinglish
  guide) before launch.

### Checks
`next typegen`, `tsc --noEmit`, `pnpm lint`; vitest for `lib/marketing`, `components/marketing`,
`app/(marketing)`, `app/seo.test.ts`, `app/public-metadata.test.ts` (each guide's generated
metadata, static params, uniqueness) and `styles` (design lint). New `e2e/guides.spec.ts` (index,
a guide's byline and JSON-LD, the 404 for an unknown slug, hreflang both ways, the feed and the
sitemap, no sideways scroll at 375, 768 and 1280 px), run with the landing, GR-37 and not-found
specs; screenshots of `/guides`, a guide and `/hi` at 375 and 1280 when `GUIDES_SHOTS_DIR` is set.
The e2e fixtures answer `/_next/image` with a 1 px stand-in, so with `GUIDES_SHOTS_DIR` set the
spec removes that route and waits for images before each screenshot. All 34 specs in the landing,
GR-37, not-found and C-153 run passed. The guide hero loads eagerly (it sits under the header) and is
at most 16 rem wide on phones and 20 rem from `sm`, so a tall phone screenshot doesn't push the text
far down.

### Owner to-dos
- Have a native Hindi/Hinglish speaker read `/hi` and the Hinglish guide's examples.
- Read the four guides once for tone; bump a guide's `updated` date when its copy changes.
- After deploy, submit the sitemap again in Search Console so the guides are found.

## C-154 · Nightly e2e failures (fix/nightly-e2e-failures)

The first full nightly e2e (run 40712737521 on develop 1fce7680) had 3 failures and 5 flaky tests.
Two were product bugs, the rest specs that drifted or raced the sandbox's background sync.

- **F-07 (Sent, and Failed + Retry), F-08 (Insert): a reply stuck on queued.** Product bug. A
  send's 202 is the message as queued; the API reads the sender's name and stores the idempotent
  response after committing, so the worker can send and publish `message.updated` (Sent or Failed)
  before the 202 reaches the browser. The composer then wrote the queued snapshot over the newer
  copy, and nothing moved it again. Now a send's, a retry's and a product message's response go
  through `applyQueuedResponse` (lib/inbox/cache): it replaces the optimistic bubble or a copy
  still queued, never one the worker has moved on. Events replace as before. Test:
  `cache.test.ts` "upsertQueuedResponse".
- **GR-13 activation error with no step named.** Product bug. Activate was enabled while the flow's
  steps were still loading; the API's errors name steps by index, so with no steps they were placed
  nowhere and only the toast showed. Activate now waits for the steps (disabled while the flow
  loads). Test: `AutomationEditorFlow.test.tsx` "waits for the steps before it activates".
- **GR-13 build at 1280 px.** Spec: "Add step" for the second quick reply opened while the first
  menu was still closing, so `menuitem /^Send/` matched both. Items are picked from the named menu.
- **GR-34 latest week.** Spec. Connecting the sandbox account backfills conversations and comments
  one to three days back in the worker, which from midweek on lands in the latest finished week,
  between the spec reading the API and opening the page. Each pass now reads the API and then holds
  the page to it, read again until a pass sees one state. Weeks before the first with data say
  "No data before <week>" (C-129), which the spec now accepts beside "N weeks without data".
- **GR-17 drawer.** Spec. The search is debounced and the unfiltered rows stay until it answers, so
  the first row could be a backfilled contact; the spec edited that one. It now opens the row once
  the list shows only the searched contact.
- **GR-23 New broadcast.** Spec. With no broadcasts the empty state offers "New broadcast" as well
  as the header; the spec waits for the empty list and takes the header's.

## C-155 · The public site in the owner's paper-and-night design, global and for creators too (feature/site-redesign)

The owner supplied a landing-page design and decided (2026-10-29): use its layout and look for the
whole public site; the design file is for layout and visual style only, every word comes from our
own site; go global (no Hindi/Hinglish marketing, `/hi` and the Hinglish guide taken down, neutral
demo data in dollars); speak to creators and influencers as well as businesses. The signed-in app
(the `(clerk)` group, sign-in and sign-up) keeps its own theme.

**C-155 supersedes C-127 to C-129 for the public site.** The public pages are no longer pinned
dark: they render their own palette whatever theme the member chose for the app.

### Theme and tokens
- `globals.css` gains the site palette as `@theme` tokens (`paper`, `paper-deep`, `sheet`, `ink*`,
  `rule*`, `night*`, `iris*`, `site-ok/wait/stop*`, `handoff*`, `comment`, `avatar-1..6`), each the
  same in both app themes (listed in `themeInvariant`, described in `tokens.ts`).
- A `.site` block in `globals.css` names them for the stylesheet (`--paper`, `--ink`, `--night` …,
  plus the alpha shades and the site's shadows, all `color-mix` of a token) and re-points the app
  tokens a public page uses (`canvas`, `panel`, `fg`, `fg-secondary`, `line*`, `brand*`, `success`,
  `warning` …) at paper, and at night inside `.night`. So shared pieces (cards, prose, badges,
  tables, the 404 illustration) wear the site's colours with no per-page change.
- `components/site/site.css` holds the layout and components (header, footer, hero, scenes, plan
  cards, FAQ, bands), every colour a variable, all in the components layer under `.site`, so
  utilities still win and nothing reaches the app. Imported by the marketing layout and the 404.
- The head script and `ThemePin` pin `<html>` to `light` on public routes (`SITE_THEME`), for the
  browser's own parts; `theme-color` is the paper (`applySiteThemeColor`, the marketing layout's
  viewport, and `ThemeSync` on public paths). Dark/Light/System in the app are unchanged.
- Fonts: Geist, the app's font, with headings at 700 and tight tracking (h1 -0.05em). The design's
  Funnel Display and Funnel Sans were tried first; the owner found them off, compared sixteen
  families on our own hero (2026-10-29) and asked for "more modern, minimal and bold", and I chose
  Geist Bold: clean at headline sizes, the most readable body of the set, and one type across the
  site and the app. One `next/font` Geist in the root layout, preloaded again (every first view
  shows it); `components/site/fonts.ts` is gone.

### Pages
- **Landing** rebuilt in the design's order: hero (scroll-scrubbed pile of messages sorting into one
  inbox; plays by itself on phones), the facts strip, "How it works" on a night band (knowledge
  scan, wires to the cited words, the draft writing itself, a hand-off and a knowledge gap),
  comment-to-DM automation (a creator's Reel, live comments, the DM, an editable keyword), Off,
  Suggest and Auto switch over four messages plus the three setup steps, features, integrations
  with their status, security and privacy (night), pricing, FAQ, closing (night) and footer (night).
- Every scene is **server-rendered in a meaningful still state** (the sorted inbox, the finished
  draft, a few comments and a sent DM, Suggest). One client island, `LandingMotion`, loads
  `landing-motion.ts` after load and animates with transforms, opacity and classes only (CLS 0);
  with reduced motion only the switch and the keyword field work. On wide screens the hero's notes
  wait for the script (with a 3 s CSS fallback) because that scene starts scattered.
- **framer-motion is gone** from the app (only the old landing effects used it), with the old
  sections, effects, illustrations and the routing diagram.
- **Every other public page** (pricing, features/*, compare/*, switch-from-manychat, developers/api,
  guides, legal pages, contact, security, data deletion, unsubscribe, the 404) uses the new header,
  footer, type, buttons (`CtaLink` is now the site's button), kickers and bands. Narrow columns
  start at the same left edge as the page.
- **Pricing** in the design's plan cards, still from the plans API: a plan that can't be bought
  says "Coming soon" (`available: false`), Max is a line under the cards until it can be bought, and
  the outlined plan is Pro when it is on sale, Free otherwise. Free's big number is zero in Pro's
  currency, or "Free" when there is no price. The closing's "7-day trial of Pro" perk shows only
  while Pro is on sale (it was always shown).

### Wording (owner's correction: our words, the design's layout)
Everything on the public site is our existing copy placed into the design's sections. Where it
differs from today's site, and why:
- **Languages removed** (owner): the hero trust row's "English, Hindi and Hinglish", the Languages
  section, the strip's "3 languages", the FAQ "Which languages does the AI support?", the feature
  card's "in English, Hindi and Hinglish", SITE_DESCRIPTION, the share image, llms.txt, the
  sign-in panel's benefit line, the guides (one section and two bullets) and the AI inbox page.
- **Global and creators** (owner): SITE_DESCRIPTION, the share image and its alt, llms.txt, the RSS
  description and the guides index say "businesses and creators"; "small sellers in India" and
  similar became "small businesses"; "India's consent rules" became "consent rules" (feature card,
  GTM pages, plan matrix, guides); guide examples use a denim jacket, "their city" and "what's the
  price"; the WhatsApp guide's title is now "WhatsApp Business API vs app for small business".
- **Truth fixes:** Instagram's integration row no longer lists insights as included ("Post insights
  follow Meta's approval": `IG_REQUEST_INSIGHTS_SCOPE` is off in production); the closing's
  "7-day trial of Pro" shows only while Pro is on sale; the Interakt row no longer says Pro is
  "priced in rupees".
- **Rearranged, same words:** the knowledge section uses the "AI replies from your own knowledge"
  card title and the "Will the AI make things up?" answer; the modes section uses "Set up in three
  steps" as its kicker and "Let the AI draft or reply" as its heading, and the mode descriptions are
  the FAQ's answers; the strip is C-138's numbers ("1 inbox", "200 AI credits", "3 automations")
  plus "Official Meta APIs" with the footer's no-password line; the catalogue card's "Part of Pro."
  is a "Pro" chip; Max's note sits under the plan cards as "Max: …"; the automation steps keep their
  titles with shorter bodies (the keyword line became the field label "The keyword is yours"); the
  integrations intro says "Each row" for "Each card"; the hero eyebrow is SITE_TAGLINE.
- **New microcopy, kept minimal, for the scenes the design adds:** the hero captions ("Every DM.
  Every comment." / "One inbox. Example data."), the scroll hint, the inbox chips; the knowledge
  scene's four step labels (from the feature cards), the draft's states, its citations, the
  hand-off line and "Knowledge gap: bulk orders / Add an answer"; "Automation on this Reel", "DMs
  sent from this Reel", the creator's Reel caption, the DM's link and follow lines, the comment
  summary legend; the mode table's labels and outcomes and the Off description ("No drafts.
  Messages still arrive tagged with intent, sentiment and a lead score, and you reply yourself.");
  the switch's sentence "Try the switch to see what each does with the same four messages."; the
  Free card's "Available now", and "Cancel anytime." under a priced Pro without a trial.
- **Demo data:** neutral names (Maya R., Sam K., Leo M., Nina, Theo), Toronto, a linen shirt at $39,
  a denim jacket at $79 and a cotton scarf at $19, the made-up shop "Indigo Lane" and a made-up
  creator "mia.makes" whose Reel uses our own LINK keyword example. Real plan prices still come from
  the plans API.
- **Removed with the old landing:** the inbox screenshot section, the screenshot timeline and the
  footer's oversized wordmark. The "Is there a mobile app?" answer is our existing one (install
  from the browser, push notifications; on iPhone from the Home Screen, iOS 16.4 or later).

- **Comparison pages** (owner approved, 2026-10-29): to keep comparative claims truthful and not
  misleading, /switch-from-manychat, /compare/manychat and /compare/interakt now (1) show a
  trademark and no-affiliation note under the sources ("Manychat is a trademark of its owner.
  Amplychat isn't affiliated with or endorsed by Manychat. Details checked on {date}. If something
  has changed, tell us at {support email}."), built from a `competitor` field on the page data
  with the latest `checked` date of its sources (lib/marketing/competitor-note.ts); and (2) cite the
  vendor's own pages first: Manychat's help centre and product updates, Interakt's pricing page,
  all checked 2026-10-29. Claims the official pages contradicted were corrected (Manychat AI is
  in beta and answers from your knowledge, not "a paid add-on"; TikTok is unavailable in the UK
  and EU, not "open beta"; Interakt's AI is its own WhatsApp AI agents add-on, not "early, through
  a partner"), claims they didn't fully confirm were softened (comment-to-DM "the same set", Make,
  QR codes), and the third-party blogs were dropped except Kanal, kept only for Meta's rule
  against requiring a follow. Manychat's help centre blocks automated reading, so it was read
  through a search engine's copy; the pages say so. Source dates now read "29 October 2026".

### Measured
Local production build made the way the VM makes it (standalone, split hosts), Lighthouse 12.8.2,
three runs each, medians; same machine and method as C-152. Before: develop 5b246b2b.

| | before | after |
|---|---|---|
| Mobile performance | 72 | 90 |
| Mobile LCP | 3.88 s | 3.11 s |
| Mobile TBT | 501 ms | 198 ms |
| Mobile Speed Index | 4.0 s | 1.7 s |
| Mobile accessibility | 100 | 100 |
| Desktop performance | 99 | 100 |
| Desktop LCP | 0.83 s | 0.67 s |
| Accessibility, SEO, best practices (both) | 100 | 100 |
| CLS | 0 | 0 |

*C-152's `content-visibility: auto` on the lower landing sections was tried again and dropped: it
gave 93 on mobile but 96 accessibility (axe hit-tested the pricing notes against the night band
behind a skipped section). Accessibility 100 wins.*

### Checks
`next typegen`, `tsc --noEmit` and `pnpm lint` clean; the whole web vitest suite passes (275 files,
2,983 tests), including the design lint, the token tests (generated files refreshed), theme,
public metadata, SEO, guides and the rewritten landing and pricing tests (one h1, the FAQ JSON-LD
equal to the FAQ on the page, no Hindi or Hinglish, honest statuses, the C-149 states). E2E
`landing|GR-37|not-found|C-153|guides` on the e2e stack: 33 passed. The landing spec now checks the
still scenes, the script taking over, the mode switch and the keyword field, the section order, no
sideways scroll and CLS under 0.1 at 375, 768, 1280 and 1536; the guides spec checks the 308s for
/hi and the Hinglish guide. `vitest.setup.ts` stands in for the Google fonts. framer-motion is
removed from package.json and the lockfile.

### For the owner
- Read the new microcopy listed above, the creator example and the demo data.
- Still seller-only and left for you: the guides index title "Guides for Instagram and WhatsApp
  sellers" and its h1 "Sell better in the DMs"; the hero line "AI that knows your business …".
- Razorpay and UPI are the only payment rails; the page states them as facts, which reads Indian.
- The plan matrix still says "Pro has a 7-day free trial" while Pro isn't on sale (the plan's
  rule, not an offer today).
- The share image stays dark (one picture for every theme).

## C-156 · Site trust pass

The competitor review's "do now" list plus the legal items (owner, 2026-10-29), built by three
parallel agents on `feature/site-trust-legal`, `…-pages` and `…-compare`. Each adds its own
sub-section below; the coordinator merges them with a union.

### C-156 (legal)

**No lawyer has reviewed any of this.** The owner has no lawyer budget; the text follows standard
practice and was checked against the code, not against legal advice. Every page carries a "NOT
reviewed by a lawyer" code comment.

**Owner decisions applied (2026-10-29)**
- One email, `SUPPORT_EMAIL`, for support, privacy, the grievance officer and DPA requests.
- `LEGAL.grievanceOfficer` is `{ role: "Grievance Officer, UNCHARTD", email: SUPPORT_EMAIL }`: a role,
  no personal name. The type gained `role`; `legalFacts` shows "Grievance Officer, UNCHARTD
  (support@amplychat.com)".
- The full address is never published. New `LEGAL.publicLocation: "Bihar, India"`, shown as
  "Location" in the facts card (a set `registeredAddress` would replace it), and used in the
  privacy policy and the DPA. `registeredAddress` stays unset.
- `governingLaw: "the laws of India"`, so Terms now has a Governing law section; `jurisdiction`
  stays unset (no courts named).
- `effectiveDate: "2026-10-30"`, a placeholder: **the coordinator moves it to the release date.**
  Every legal page shows "Last updated …" (from `LEGAL_DOCUMENTS`) and "Effective …".
- WhatsApp fees: Terms says customers pay Meta directly through their own WhatsApp Business account
  and we add no markup.

**What changed**
- `lib/legal.ts`: the fields above; `LEGAL_DOCUMENTS` gained `subprocessors`, `cookies`, `dpa` and
  `accessibility` (all 2026-10-29); privacy and terms moved to 2026-10-29. The sitemap reads these
  dates, so the pages agent only has to add the four paths to `PUBLIC_PATHS`.
- `lib/subprocessors.ts` + `components/marketing/legal/SubprocessorTable.tsx`: **one list**
  (provider, purpose, data, location, link to its DPA or privacy page) rendered by `/subprocessors`,
  the privacy policy ("Who we share it with") and the DPA's Annex 3.
- **Privacy policy:** controller for account data, processor for the messages, contacts and profiles
  a business or creator brings (including a creator's followers), with the DPA linked; a GDPR Art. 6
  legal-basis table; "Data from Instagram, Facebook and WhatsApp" itemised per platform (from the
  parsers: story replies and mentions, stickers, reactions, referrals; WhatsApp documents,
  locations, button replies and orders) and matched to `/data-deletion`; international transfers
  (India, GCP Singapore, subprocessors mainly in the US, Gemini wherever Google has facilities; SCCs
  and the UK Addendum for EEA/UK); a retention table from the code (`jobs/tasks/purge.py`,
  `message_history_days`, `infra/vm/backup.sh`: nightly dumps, 7 daily + 4 weekly, never over 30
  days; the old "7 days of recovery history" was Render's PITR and is gone); automated decisions;
  rights split into Everyone / EEA and UK (GDPR) / California (CCPA/CPRA, no sale or sharing, GPC
  honoured) / India (DPDP Act, the existing text) / Grievances; children; the cookie section now
  points to `/cookies`; insights say "we don't ask for it today" (the scope flag is off).
- **`/subprocessors`**: the table, "Others who receive data" (Meta, Dodo once billing opens, tools a
  business connects, push services, Grafana Cloud), "Last updated" and "To be told about changes,
  email support@amplychat.com".
- **`/cookies`**: two tables read from the code (Clerk's `__client`, `__session`, `__client_uat` and
  their suffixed forms, Cloudflare's `__cf_bm`/`_cfuvid` on Clerk's domains, `sh_theme`; every
  `socialhood:*` local/session storage key, the widget's `sh_visitor_<widget>` and the service
  worker), "No tracking, so no banner", and Meta's SDK on Connect WhatsApp.
- **`/dpa`**: incorporated into the Terms on acceptance; roles; Art. 28(3) duties (instructions,
  confidentiality, security, subprocessors, assistance, breach notice within 72 hours, deletion or
  return, audits); SCCs 2021/914 Modules 2 and 3 by reference (Clause 7 docking on, Clause 9(a)
  Option 2, Clause 11 option off, Clauses 17/18: the exporter's member state, else Ireland); the UK
  Addendum B1.0 (Table 4: neither party may end it); DPDP and CCPA service-provider terms; Annexes
  1 (processing details), 2 (security measures, true to infra/vm, `security/crypto.py`, HSTS in
  `lib/security/headers.ts`, Meta signature checks, CI's pip-audit / pnpm audit / gitleaks) and 3
  (the shared list).
- **Terms**: "AI features" (modelled on Wati §11: no warranty of accuracy, the user reviews, the
  business is responsible for what Auto sends, no decisions with legal or similarly significant
  effects), the DPA incorporated with a subprocessors link, "Pro isn't on sale yet" in Plans, the
  no-markup line, Governing law.
- **`/accessibility`**: WCAG 2.2 AA as an aim, not a claim; axe and keyboard testing; known limits;
  report to `SUPPORT_EMAIL`, reply within 5 working days.
- Tests: `legal.test.tsx` (today's config, Location vs address, grievance role, all eight documents
  with dates and no placeholders, one subprocessor list on three pages, rights headings, Terms' AI
  section and DPA link, cookies) and `seo.test.ts` (metadata for the four new routes).

**Judgment calls**
- **Gemini and training.** `ai/gemini.py` and `agent/planner.py` use `genai.Client(api_key=…)` and
  `GoogleProvider(api_key=…)`: the Gemini Developer API, not Vertex AI. Google's Gemini API
  Additional Terms (effective 2026-03-23, read 2026-10-29) say Paid Services don't use prompts or
  responses to improve Google's products, log them "for a limited period" for abuse detection, and
  may store or cache them in any country with Google facilities; Unpaid Services do use them and may
  have human review. The API is "paid" only when the key's Cloud project has an active billing
  account. `infra/vm/api.env.example` asks for "a paid, billing-enabled Gemini key", so the policy
  says we use the paid service. **Owner: confirm the production key's project has billing on;
  otherwise the AI paragraph is false.** "We don't train AI models on your data" is about us and is
  true (we train none).
- **Disconnect does not delete stored data.** The brief asked for "deleted when the account is
  disconnected or a deletion is requested". The code deletes the token on disconnect but keeps
  stored data until "Disconnect and delete data", workspace deletion or a Meta deletion request, so
  the policy says exactly that, matching `/data-deletion`.
- **Dodo is not listed as a subprocessor.** As merchant of record it is a controller of payment data
  under its own policy, and billing is off (C-149). It is under "Others who receive data".
- **Subprocessor notice: 30 days by email to each workspace owner**, with an urgent-replacement
  exception, objection, and a pro-rata refund of prepaid fees if unresolved. A common market term;
  the owner must actually send those emails.
- **Audits:** written answers first; an on-site or auditor audit on 30 days' notice, once a year
  unless a breach or an authority requires it, at the customer's cost.
- **SCC options** chosen as the usual SaaS defaults (above). No Swiss addendum (not asked for).
- **CCPA section** is written though we are very likely under the CCPA's thresholds; it promises
  only what is true (no sale or sharing, GPC honoured trivially).
- **No EU/UK representative (GDPR Art. 27) is named.** We may need one if we target EU/UK users at
  scale; not claimed, not done.
- **Locations** in the subprocessor table are each provider's default region, not read from our
  dashboards (as C-144 noted). Cloudinary has no public DPA URL that resolves (two tried, both 404),
  so its privacy policy is linked.
- **Cloudflare cookie names and lifetimes** on `/cookies` come from Clerk's and Cloudflare's docs,
  not from inspecting production. Clerk can change them.
- The **proprietor's personal name** (Zakaur Rahman, C-144) is still shown in the facts card; the
  owner's "no personal name" decision was for the grievance officer only.
- The `sh_theme` cookie is set only by the app's theme switch; the public site sets no cookie of
  its own.

**For the coordinator / owner**
- Move `LEGAL.effectiveDate` to the release date.
- Pages agent: add `/subprocessors`, `/cookies`, `/dpa`, `/accessibility` to `PUBLIC_PATHS`, the
  footer and llms.txt.
- Owner: confirm Gemini billing; check each provider's region in its dashboard; if an off-site
  backup bucket is enabled, create it in asia-southeast1 so "backups in Singapore" stays true.
- `lib/whatsapp/embedded-signup.ts` initialises Meta's SDK with `autoLogAppEvents: true`, which
  lets Meta log SDK events from the Connect WhatsApp click. The cookies page says Meta's SDK "may
  tell Meta that it was used". Consider setting it to false (not changed here: not a legal file).

**Checks:** `next typegen`, `tsc --noEmit`, `pnpm lint` clean; vitest `src/lib`, `src/app`,
`src/components/marketing`, `src/styles`: 99 files, 1,189 tests pass. Builds, e2e and screenshots
are left to the coordinator.

### C-156 (pages)
The owner approved the competitor review's "do now" list (2026-10-29). This part builds the footer,
the audience pages, safety, what's new, the AI fact sheet, the creator FAQ, WhatsApp charges on
pricing and the status link. Nothing here was reviewed by a lawyer.

- **Footer** (`SiteFooter`, data in `lib/marketing/site.ts` `footerColumns`): Product, Solutions,
  Compare, Resources, and Legal and trust, on the night band; the bottom bar reads "© {year} UNCHARTD
  · Bihar, India", the official-API line and "Amplychat isn't affiliated with or endorsed by Meta.
  Instagram and WhatsApp are trademarks of Meta Platforms, Inc." No social links. "Start free" and
  the old "Compare and learn" list (`LEARN_LINKS`) are gone from the footer; the feature pages are
  still linked from the audience pages and llms.txt. The grid is the about column plus five
  columns at 1280, five columns under the about row below 1060 px, three below 900 px and two
  below 520 px.
- **"Bihar, India"** is `COMPANY_LOCATION` in `lib/marketing/site.ts`, because `lib/legal.ts` had no
  location field on this branch. *To reconcile:* if the legal agent adds one to `LEGAL`, the footer
  and /ai-info read it from there and the constant goes.
- **Status link:** `NEXT_PUBLIC_STATUS_URL` (build time; the Dockerfile, the production workflow,
  `.env.example` and `docs/ops/deploy-vm.md` carry it). Only an http(s) URL shows "Status" in the
  footer's Product column; unset, it's hidden.
- **/for-creators and /for-businesses** (`lib/marketing/solutions.ts`, `SolutionPageView`): the hero,
  "Sounds familiar?" before and after, the features with their status (Live comments "With Meta's
  approval"), the integrations with their honest statuses (businesses; the landing page's
  `INTEGRATIONS`), plans by audience size ("Just starting", "Growing", "Established") mapped to
  Free and Pro, Pro's state and price only from the plans API ("Coming soon" while billing is off),
  the FAQ with its FAQPage JSON-LD (the same objects the page renders), related pages. No
  testimonials. Story replies and mentions are listed as built (C-082, C-083), as the comparison
  pages already say. Collaborators are on posts and Reels, not Stories (C-134).
- **Answers checked against the code:** ban risk (the 750-an-hour private-reply bucket in
  `platforms/buckets.py`, the 7-day limit); password (Instagram login, Meta's sign-up window,
  encrypted tokens); robotic replies (tone, emoji level, do's and don'ts, sign-off in
  `AiSettings`); take-over (`human_takeover`: 2 hours by default, 30 minutes, 24 hours or until
  resumed; Instagram app replies count); the Free limit (3 active automations, 10 scheduled posts
  a month, 200 credits with in-app notices at 80% and 100%, and **Free deletes messages older than
  90 days**, `jobs/tasks/purge.py`, so the answer doesn't say "nothing is deleted").
- **/safety:** our per-account pacing from `platforms/buckets.py` (750 private replies an hour,
  100 a second for Instagram text, 10 for media, 80 for WhatsApp), the queue and its order,
  nothing sent twice, the 7-day and 24-hour rules, official login, what we never do (scraping,
  follow-gating, selling engagement, cold Instagram DMs, posting behind your back), what happens if
  Meta restricts an account (reconnect-needed, sends held, the owners' email, the Activity page,
  only temporary errors retried) and that no one can promise no restrictions. *Follow-gating:* flow
  branches can test "follows you" (C-031's nudge became a branch, GR-03), so the page says our
  invite and templates never gate and asks members not to build a flow that does, rather than
  claiming the product makes it impossible.
- **/changelog ("What's new"):** `lib/marketing/changelog.ts`, from develop's merged PRs #13 to
  #176 (September's pre-PR merges have no number): user-facing features only, with "With Meta's
  approval" where it applies. Left out: infrastructure, tests, the design system, dependency bumps,
  billing (off in production, C-149), broadcasts (off, `BROADCASTS_ENABLED`), Ask's charts
  (`AGENT_VISUALS_ENABLED` off) and #178 (not merged yet). The sitemap date is the newest entry's.
- **/ai-info:** what it is, who it's for and not for, channels (the integrations' statuses), plans
  from `plan-table.json` with each plan's state from the plans API, honest limits (new, App Review
  pending, insights permission not requested, Shopify listing, broadcasts soon, no certification or
  partner badge, no uptime figure), the company (UNCHARTD, Bihar, India, the support email), and
  claims to avoid. llms.txt points at it first, with /safety and /changelog. llms.txt never says
  "India" (the C-155 test), so the location stays on the page.
- **Landing FAQ:** adds "Do I have to share my Instagram password?", "Can I take over a
  conversation from the AI?" and "Can automations get my Instagram account banned?"; the WhatsApp
  fees answer now says Meta charges by message type and country, paid directly, no markup.
  Shared objects in `lib/marketing/faq.ts`, so the landing and audience pages say the same words.
- **Pricing:** a "WhatsApp message charges" band after the limits: per template message by category
  and country, the 24-hour window in plain words, "You pay Meta directly through your own
  WhatsApp Business account. Amplychat adds no markup.", separate from the plan, and a link to
  Meta's pricing page. No rates are copied (they change).
- **Header:** no "Solutions" entry. The header already holds five links and two buttons between
  901 and 1060 px, and a menu would need a client dropdown the C-155 header avoids; the footer,
  llms.txt and the sitemap link both pages.
- **Sitemap and llms.txt** list /for-creators, /for-businesses, /safety, /changelog, /ai-info and the
  other agents' /compare, /subprocessors, /cookies, /dpa and /accessibility. On this branch alone
  the public-metadata test fails for those five (no page yet); it passes once the branches combine.

**For the owner:** read the audience pages' copy and the tier descriptions; the "claims to avoid"
list; the safety page's sentence on follow branches; whether Meta's "free replies inside the
24-hour window" wording should be checked against Meta's pricing page on the day you publish.

### C-156 (compare)

Seven new comparison pages and a `/compare` hub, from the owner-approved competitor review
(2026-10-29), following the GR-37 and C-155 rules in `lib/marketing/gtm-pages.ts`: the vendor's own
pages only, each read on 2026-10-29, a source comment above every competitor cell, the `competitor`
field so the trademark and no-affiliation note renders, a balanced "Which fits you" block, no
logos and no "best". Not reviewed by a lawyer.

- **Pages:** `/compare/linkdm`, `/compare/instantdm`, `/compare/inro`, `/compare/creatorflow`
  (Instagram DM tools) and `/compare/wati`, `/compare/aisensy`, `/compare/spur` (WhatsApp
  platforms). None skipped: each vendor's own pricing and feature pages could be read with a
  plain fetch. No site was read around a block; where a read failed (see AiSensy) that page wasn't
  used for the claim.
- **Hub `/compare`:** an intro, "How we compare" (vendor sources, dates, our side checked against
  our code, "not found" ≠ lacks), cards in two groups (`COMPARE_GROUPS`: Manychat, Switch from
  Manychat, LinkDM, InstantDM, Inrō, CreatorFlow; Interakt, Wati, AiSensy, Spur) with each page's
  latest source date, and a general trademark note with the support address. Breadcrumbs JSON-LD.
  *No CollectionPage/ItemList JSON-LD: the codebase has no pattern for one, so none was invented.*
- **Breadcrumbs:** a `/compare/*` page is now Home, Compare, the page (it was Home, the page).
- **Our column** shares cells defined once at the top of the block: Instagram, WhatsApp and website
  chat in one inbox (C-111, on every plan), Facebook "built and waits on Meta's approval" (C-077),
  broadcasts "soon" (O-11), the catalogue "with Meta's approval" and Shopify "coming soon" (O-10),
  the AI answering only from documents, Q&A, products and website pages (knowledge types
  `faq/text/url/file` and the site crawl, migrations 0009 and 0030), the follow nudge that never
  gates, and Meta's WhatsApp fees paid by the business to Meta with no markup (owner, 2026-10-29).
  "Analytics" on the CreatorFlow page names only what is built: the weekly report (GR-34) and lead
  scores; link-click tracking was not claimed.
- **Sitemap and llms.txt:** the eight paths are added to `PUBLIC_PATHS` and `PAGE_UPDATED`
  (2026-10-29) so the sitemap lists them; llms.txt lists the comparisons automatically from
  `GTM_PAGES` and gets one "Compare" line for the hub. `GTM_PATHS` includes `/compare`. The footer
  (`LEARN_LINKS`) is left to the pages agent.

Sources and what was softened, per competitor (all read 2026-10-29):
- **LinkDM** — linkdm.com/pricing, linkdm.com home (features, FAQ). Prices USD: Free (1,000 DMs a
  month), Pro $19 a month or $182 a year, Platinum+ $99 a month. Broadcasts come only from a home
  banner ("Broadcasts let you send timely DMs to active contacts!"), so the cell says "Instagram DMs
  to active contacts" and no more. AI replies, a team inbox, comment analysis and post scheduling:
  not found (the DM Planner drafts DMs for posts, which isn't publishing).
- **InstantDM** — instantdm.com/pricing, instantdm.com home. Prices USD, billed yearly: Legend Pro
  $9.99, Trendsetter $24.99, Trendsetter Pro $49.99 a month; Free 500 DM automations. The AI is
  described as the pricing page does (an agent step on your own OpenAI, Claude, Gemini or DeepSeek
  key, with human takeover); "answers from a knowledge base" was not claimed. WhatsApp is listed only
  as a support channel. The per-plan marks in its table were hard to read, so plan placement is
  kept to what the plan lists name.
- **Inrō** — inro.social/pricing, inro.social home. Prices EUR: Free (100 activated contacts),
  Pro "starting at €12.99 per month", annual €1,249, Managed from €299. Live comments are marked
  differently in two places on its pricing page, so Live is left out of its cell. "Instagram content
  management" on Pro is reported as is; scheduling posts stays "not found".
- **CreatorFlow** — creatorflow.so/pricing, creatorflow.so home (first read timed out; the
  second read worked). Prices in "$" without a currency code (said on the page): Pro $15 a month or
  $12 billed yearly, Growth $30 or $24. AI replies: "not found", with its own line that you write
  every message. Its comparison table's checkmarks didn't come through, so per-plan claims follow
  the plan lists only.
- **Wati** — wati.io/pricing, wati.io home, Astra help "How to train your AI agent" (updated
  2026-06-02), Wati help "Set up an Astra AI agent for Instagram" (updated 2026-10-22). Prices INR,
  billed quarterly: Growth ₹2,699, Pro ₹5,799, Business ₹16,799 a month. The trust centre
  (trust.wati.io) returned 403 in the review and wasn't used. Whether Wati marks up Meta's fees isn't
  stated; the cell says only that template messages are charged on top from its rate card.
  "No free plan was shown" was drafted and removed (it would read as "lacks").
- **AiSensy** — aisensy.com/pricing (add-ons, billing, Meta fees) and AiSensy's own
  aisensy.com/aisensy-vs-interakt (plan prices, agents). The pricing page's plan cards didn't come
  through in two reads (the page renders them late), so the plan prices (from ₹1,500 a month; Pro
  ₹3,200 a month) come from the vendor's comparison page, which has no date; the page says so.
  Third-party price lists that disagree (₹999, ₹2,399, ₹4,999) were not used. Instagram messaging
  and comment-to-DM: not found on AiSensy's pages or by a site search. A fetch of AiSensy's `m.`
  subdomain was refused by the session's safety check as a way round the main site and was not
  retried.
- **Spur** — spurnow.com/en/pricing, spurnow.com/en/llm-info (its page for AI assistants, last
  reviewed 2026-10-07), spurnow.com home. Prices USD: AI Acquire $15 a month or $12 billed yearly
  ($144), AI Max $399 a month billed yearly; 14-day trial; llm-info says there is no free plan (the
  cell quotes that rather than marking a status). The home page FAQ still lists "AI Powered Question
  Answering (Coming Soon)" while llm-info and pricing describe AI agents on knowledge; the cell
  follows llm-info and pricing. The review notes say a Spur help article admits a markup on Meta's
  rates; that article wasn't re-read, so no markup is claimed.

Checks: `next typegen`, `tsc --noEmit`, `pnpm lint` clean; vitest for `app/(marketing)`, `app/seo`,
`app/public-metadata`, `lib/marketing`, `components/marketing` and `styles` (design lint) pass.
E2E (`gr37-gtm-pages.spec.ts`, now with the new pages, the hub and each trademark note) is left to
the coordinator.

## C-157 · Premium landing build

The owner approved the landing page audit (`docs/landing-page-audit/`, 01–07) on 2026-10-30 and asked
for a premium page using the installed design skills. The work is in two stages on
`feature/site-redesign`: stage 1 builds the design system, the shell and the Phase 1 fixes; stage 2
rebuilds the landing sections on top of it.

### C-157 (stage 1)

**Phase 1 fixes (05, LP-1.x).**
- LP-1.1, the invisible AI draft: the draft's "words appear" state is now `.ddraft-t.is-typing`, and
  the DM's typing dots are `.dm-typing`. The two had shared `.typing`, so the dots' pill background
  and inline-flex landed on the draft (1.1:1). `landing.spec.ts` now asserts that the draft's text box
  stays transparent and block-level after the scroll.
- LP-1.2, the H1: the display step (44 → 68 px) is capped by its column. `.hero-copy` is a size
  container and the hero H1 is `min(var(--fs-display), 13cqi)`; "Every comment." is about 7.3em wide.
  The hero grid is 1fr/1fr and the copy sits above the scene (z-index). Measured at 375, 768, 1280
  and 1440: each phrase's right edge is at or inside the copy column.
- LP-1.4, the phone menu: a tap outside the button and the panel closes it (one `pointerdown`
  listener, the scrim included). Tab and Shift+Tab stay inside the button and the panel while it is
  open, and Escape returns focus to the button. The menu's links are 48 px tall, and the bar's CTA is
  44 px tall below 760 px. The menu adds only Sign in, so one "Start free" shows with it open. A
  signed-in visitor gets nothing extra in it, because "Open app" is already in the bar.
  - **Judgment call:** the brief said "focus is contained", while 05 said "Tab past the last item
    closes it". Containment was built, because the open menu now has a scrim over the page.
- LP-1.3, the secondary CTA borders: `.btn-line` uses `--s-line-control`. That is #82848B on paper
  (3.42:1, 3.18 on paper-deep, 3.74 on sheet) and #6A6C76 on night (3.63, 3.34 on night-raised).
- LP-1.5, the closer: its H2 is 700 at the story tier. The max-width is 20ch, not 14ch: at 14ch the
  heading ran to four lines at 1440, and 20ch gives three.
- LP-1.6, the dimmed knowledge lines: these are now dimmed by colour (night-ink-3, 5.52:1) instead of
  opacity .5/.35.
- The hidden hero time labels have `aria-hidden` (the T7 finding in 07).
- The two nav landmarks are now named "Main" (the bar) and "Menu" (the phone panel).
- The logo's svg has `aria-hidden` and `focusable="false"`.
- Body text in `.site` (p, li, dd, blockquote, figcaption) has `text-wrap: pretty`. Every heading,
  the FAQ's h3s included, has `balance`.

**Tokens (06, LP-2.1).** The raw values are in `@theme`, and the short names on `.site` are in
`globals.css`. That reference also keeps Tailwind 4 from dropping theme variables that only `site.css`
reads; a check with Tailwind's compiler confirmed that it removes unreferenced ones. `pnpm tokens` now
also generates `spacing` and `containers`.
- Type: `--text-site-{display,h1,h2,h2-sm,h3,stat,stat-sm,title,lede,body,body-sm,label,caption,micro}`,
  each with its line height, and `--tracking-site-*`. On `.site` they are `--fs-*`, `--lh-*` and
  `--tr-*`.
- Space: the 4 px steps are `--space-1…16` on `.site`, from Tailwind's own `--spacing`. The rhythm
  tokens are `--spacing-site-{section,section-tight,head,band,gutter}` (on `.site`: `--space-section`,
  `--space-section-tight`, `--space-head`, `--space-band`, `--gutter`). The container is
  `--container-site` (1240), or `--wrap-max` on `.site`.
- Radii: `--radius-site-{xs,sm,md,lg,xl}` (6, 10, 12, 18, 22), `--r-*` on `.site`.
- Breakpoints: `--breakpoint-site-{sm,nav,md,wide}` (520, 760, 900, 1060). `SiteHeader` reads
  `site-nav` from the generated file. `site.css` has to write the numbers, because a media query can't
  read a variable, so each query names its token.
- Motion (transitions-dev's scale):
  - durations `--motion-site-{stagger,micro,quick,fast,medium,slow,very-slow,entrance}` (40, 80, 150,
    250, 350, 400, 500, 1200 ms), `--dur-*` on `.site`;
  - easings `--ease-site-out` (smooth-out) and `--ease-site-in-out`, which are `--ease` and
    `--ease-swap` on `.site`;
  - travel, scale and blur steps `--dist-*`, `--scale-*` and `--blur-*`.
- Colour:
  - ink-tertiary #686B74 → #5E616A;
  - new `site-line-control` #82848B and `night-line-control` #6A6C76;
  - the 06 §1 mark fixes: `iris-mist` #8A82EB, `site-wait-mark` #B06A00, and new `instagram-night`
    #E0559A and `web-night` #2AA597;
  - `.site` now maps the app's `line-control` to the new control edge, and `brand-strong` to
    iris-night inside `.night`;
  - `--gradient-brand` in `.site` is flat ink, so the app's primary button looks like the site's;
  - `contrast.test.ts` asserts 21 of the site's pairs (LP-4.7).
- Semantic roles: `--s-{bg,surface,surface-2,text,text-2,text-3,line,line-2,line-control,hover,link,link-hover,focus,selection,selection-fg,cta-bg,cta-fg,cta-hover}`
  are defined on `.site` and re-pointed in `.site .night` (LP-5.2 for the shared parts). The `.night`
  overrides for buttons, the kicker, the lede, links, focus and cards are gone.
- Iris now has four roles only: links, focus, selection and AI moments.
  - The primary button's hover is a lighter ink (`--s-cta-hover`), not iris.
  - The kicker, the feature icons, the step numbers and the trust icons are in ink-3 or night-ink-2.
  - The FAQ summary no longer turns iris on hover.
- `globals.css` notes that `.site` uses 700 for its headings (LP-5.5).

**System in `site.css`.** These shared parts are now on the tokens: base, the container and section
rhythm, headings, lede, links, buttons, chips, cards, header, footer, pricing, FAQ, the closer's
heading, and inner-page heads and bands.
- Two H2 tiers: `.h2` is the story tier, 32 → 52 px, 18ch. `.h2-sm` is the utility tier, 28 → 40 px,
  20ch. `UTILITY_TITLE` in `primitives.tsx` names the utility tier, and `Faq` and `Pricing` use it
  (`/pricing` keeps its H1 at the page tier).
- `.h-page` is 26ch.
- All headings are 700. Card and item titles (`--fs-title`, 20 px) stay 600, because they are a text
  role and not a heading tier (06 §2).
- `.split-head` is 1.25fr/.75fr.
- `.after-head` and the head-to-content margins use `--space-head`. `.sec-tight` is new.
- Each component writes its states once:
  - hover only under `@media (hover: hover)`;
  - active is a 1 px press;
  - one focus ring from `--s-focus`;
  - disabled for `:disabled` and `[aria-disabled="true"]`.
- `::selection` uses the palette.
- Inner-page bands are now separated by space alone: the top rule is gone, and a band that follows
  another has a 24 px top padding.
- The scene CSS (hero, strip, decide, machine, modes, features, channels, trust) is left for stage 2.
  Only the Phase 1 fixes, the accent changes and the head gaps touched it.

**Shell.**
- Header:
  - It is a plain paper bar with no blur and no rule. Once the page scrolls, `HeaderScrollState`
    (one IntersectionObserver on a sentinel) adds a soft drop (`--shadow-nav`) through
    `data-scrolled`.
  - From 760 px the links show (the tablet tier, LP-3.2). At 761–1060 px the gaps are 20 px. At 768
    px the logo, the five links, Sign in and Start free fit on one line.
  - The links are 44 px tall, with an underline on hover.
  - The phone menu has a scrim and opens like a dropdown (250 ms from 0.97, `@starting-style`). It
    closes at once.
- Footer: the hairline above the bottom row is replaced by space. The links are 44 px tall at 900 px
  or narrower and underline on hover. Everything is on the `--s-*` roles. One rule is kept where the
  closer's night band meets it.
- Pause control (WCAG 2.2.2): `components/site/MotionToggle.tsx` (server) and `motion-control.ts`
  (plain DOM, `bindMotionControl(scope)`). It is a round 44 px button with a fixed name, and
  `aria-pressed` shows the paused state. The pause and play icons swap with transitions-dev's icon
  swap. Pausing sets `data-motion-paused` on the `[data-motion-scope]` element, and `site.css` then
  pauses every CSS animation inside it. The button stays hidden with no script and with reduced
  motion. It has unit tests. Stage 2 wires it to the looping scenes.

**Other public pages.** Every public page picks up the new system through the shared classes, with no
content changed. That covers the H1 at the page tier, the bands, the cards, the buttons, the 3:1
control edges, the darker ink-3 and the footer.
- Checked at 375 and 1280: /pricing, /features/ai-inbox, /compare, /compare/interakt, /for-creators,
  /safety, /changelog, /ai-info, /guides, /privacy, /contact and a 404.
- Also at 768 and 1440: /pricing, /for-creators and /privacy.
- No page scrolls sideways.

**Skill advice I overrode or did not apply.**
- Taste (design-taste-frontend): "buttons square or fully round, not the 9–16 px soft radius". Kept
  12 px, because the owner's design file and 06 set it.
- Taste: "no violet". Iris stays (an owner decision), limited to four roles.
- Taste: "no thin rules". The footer keeps one rule between the two night bands, and the scenes and
  real tables keep theirs (`data-ui` territory).
- Impeccable craft floor: "tracking floor -0.04em". Display and page H1 use -0.04em, not 06's
  -0.045em; the H2 and H3 tracking follows 06.
- Impeccable and Taste ban kickers (eyebrows). The landing's kickers are stage 2's to delete. On the
  inner pages, `SECTION_EYEBROW` is restyled to a quiet ink-3 label and not removed, because deleting
  it would change those pages' content, which this stage doesn't own.
- transitions-dev's snippets ship their own `t-*` classes and `:root` blocks. Only its token scale and
  the icon-swap and dropdown timings were taken, under `.site` names, to keep the stylesheet small
  and avoid a global `:root` that the app would share.
- Taste wants the footer to end on the name at full width. Not done: the owner asked to subtract
  clutter.

**Left for stage 2 or later.**
- `landing-motion.ts` still writes 901 and reads `--nav-h` from `<html>` (LP-4.6).
- The closer's `.falling` loop and the hero bob.
- The footer's about line, which still names only Instagram and WhatsApp (LP-4.8).
- `MARKETING_CARD` (shared with the app's auth shell, so not re-pointed).

Checks:
- `next typegen`, `tsc --noEmit` and `pnpm lint` are clean.
- vitest passes for `components/marketing`, `components/site`, `styles` (tokens, design lint,
  contrast), `app/(marketing)`, `lib/marketing` and not-found: 418 + 98 tests.
- Screenshots were taken on a dev server on :3160 at 375, 768, 1280 and 1440.
- e2e is left to the coordinator: the updated `landing.spec.ts` and the new `site-shell.spec.ts`
  (menu, tablet links, scrolled bar).

### C-157 (og and metadata)
- **Share image redrawn on paper** (`components/marketing/og.tsx`): `paper` canvas, `ink` text, the `iris` accent only on "One inbox.", the logo tile, the H1 "Every DM. Every comment. One inbox." in Geist 700 with tight tracking, and the line "For Instagram, WhatsApp and website chat." The colours come from `styles/tokens.ts`; no hex literals.
- **Font:** Satori reads static TTF, not the variable woff2 `next/font` ships, so the Geist 700 static TTF (SIL OFL, from Google Fonts, 32 KB) is committed at `components/marketing/fonts/Geist-Bold.ttf` and read with `readFile(join(process.cwd(), ...))`. The route stays `force-static`: drawn once at build and cached. No new dependency.
- **C-129 "stays dark" exception removed:** the `og.tsx` runtime reason now says it is drawn on the site's paper (C-157); the glow's `rgba(0,0,0,0)` code exception is deleted (the gradient is gone); the stale static-asset note for `og.png` is corrected.
- **Positioning line:** one line everywhere, naming website chat and comment-to-DM. Title uses "web chat" (the title is capped at 60 characters; "website chat" gives 61). Everything else says "website chat". Judgment call, for the owner to confirm.
- **Not touched** (other agent's scope): the footer "about" line (`SiteFooter.tsx`) still says "Instagram and WhatsApp"; change it to match `app/layout.tsx`'s default description. `gtm-pages.ts` page titles (`/features/ai-inbox` is pinned by `gr37-gtm-pages.spec.ts`) were left as they are.
- **Canonical slash:** `canonical: "/"` is resolved by Next against `metadataBase`; it renders without the trailing slash and the JSON-LD ids use `/`. Left alone: both forms resolve to one page, and the metadata tests pin `"/"`.
- JSON-LD: `WebSite` and `SoftwareApplication` both take `SITE_DESCRIPTION`, so they follow the new line; a test pins it.
