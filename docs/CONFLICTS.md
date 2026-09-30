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
