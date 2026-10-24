# Implementation plan: competitor parity and growth (GR)

Written 2026-10-22. This turns the [competitor analysis](../competitors.md) (with the
[Manychat comparison](../competitor-manychat.md)) and the [product roadmap](../product-roadmap.md)
into tasks.

It is grounded in the code as of develop `0bcc67c`:
- **Contacts:** `Contact` in `models/inbox.py`.
- **Automations:** the flat `Automation` in `models/automations.py`.
- **Instagram webhooks:** `platforms/instagram/parse.py` and `SUBSCRIBED_FIELDS` in
  `platforms/instagram/adapter.py`.
- **Plans:** entitlements in `billing/plans.py`.
- **Jobs:** in `jobs/tasks/`.

**Why it can start now:** Meta verification and App Review will take weeks, because the business
isn't registered yet. **Engineering doesn't have to wait.**
- In Development mode, every feature works for accounts with a role on the Meta app (yours and
  your test accounts).
- The sandbox platform covers e2e.
- Only real customers wait for App Review.
- So this plan runs two tracks in parallel: the **owner track** (section B) and the **build track**
  (section D).

**Sizes** (one developer with agents, as in the roadmap): **S** about a week, **M** two to three
weeks, **L** a month or more.

---

## A. Principles

1. **One App Review for the whole plan.**
   - Section F lists every permission and webhook field the plan needs. All Instagram and WhatsApp
     features in waves 1 to 4 reuse the five Instagram permissions we already request, plus
     WhatsApp's.
   - Submit once, after wave 2, with a screencast per feature (GR-00 prepares them).
   - Facebook Pages (wave 5) is a second, smaller submission.
2. **Only what the official APIs allow** (BUILD_SPEC §1.5).
   - Every task names the platform rule it depends on.
   - Anything marked *verify* is checked against Meta's current docs before the task starts.
   - Follow-to-DM, TikTok and cold DMs are out (section I).
3. **The owner's rules carry over:**
   - backend, API, tests and the generated client with every feature, with no mock-only UI;
   - expand-only migrations;
   - tenant filtering on every query;
   - idempotency on every external side effect;
   - pages fill the width and follow DESIGN_SYSTEM.md (with the design and copy lints in CI);
   - feature branches squash-merged into develop, merge commits into main;
   - no Claude attribution.
4. **Ask Social Hood gets a read tool for every new data source.** It's part of each task's
   definition of done, not a separate task.
5. **Ship small, behind entitlements.** Each feature gets an entitlement key in `billing/plans.py`.
   The values per plan are owner decisions (section C), and the code reads them.

---

## B. Owner track (in parallel, starting now)

| ID | Step | When | Notes |
|---|---|---|---|
| O-1 | **Register the business:** sole proprietor, Udyam (free; never pay an intermediary) | Now | Roadmap P0 step 2 |
| O-2 | **Make the public site match the registration:** legal name, address, contact email on the site, privacy, terms and data deletion | After O-1 | The pages exist in `app/(marketing)`; GR-00 checks them |
| O-3 | **Meta Business Portfolio verification** | After O-1 and O-2 | Business Suite → Security Center → Start verification |
| O-4 | **Approve the permission list** in section F | Week 1 | GR-00 drafts it |
| O-5 | **Record the App Review screencasts** on the production URL, from GR-00's scripts | After wave 2 lands | One per permission |
| O-6 | **Submit App Review** (Instagram and WhatsApp permissions, Advanced Access) | After O-3 and O-5 | Expect rounds of feedback; GR-00 answers them |
| O-7 | **WhatsApp:** Tech Provider onboarding, Embedded Signup, a real number with display name approval | After O-3 | Memory: move off the test number |
| O-8 | **WhatsApp billing currency:** keep each business account in INR | Before 2026-12-31 | Meta stops delivering for Indian accounts not moved to INR from 2027-01-01 |
| O-9 | **Pricing:** set the Pro price in Dodo; take the plan decisions in section C | Before launch | My suggestion is ₹1,500 to ₹2,500 (competitors.md) |
| O-10 | **Later submissions:** Facebook Pages permissions (GR-29); Google OAuth verification if Sheets is native (GR-27); a Shopify app listing (GR-31) | When those waves start | |
| O-11 | **Legal check:** WhatsApp marketing consent in India (TRAI's TCCCPR rules, the DPDP Act) before broadcasts go live | Before GR-23 ships | One vendor claims DLT-style consent rules apply; confirm with a professional. **Not done (2026-10-24):** GR-23 is built and merged behind the server setting `BROADCASTS_ENABLED`, off by default; turn it on in production only after this check |

---

## C. Decisions needed

The recommended option is first. Each goes in CONFLICTS.md when taken, as the UI programme did.

| ID | Decision | Options | Needed by |
|---|---|---|---|
| PD-1 | Team seats per plan | **Decided 2026-10-24 ("for now"): Free 1, Pro 3, Max 10** (was Free 1, Pro 1, Max 10; the alternative was Pro 5) | GR-19 |
| PD-2 | Contacts metering | **Never meter contacts; flat plans** (the competitive edge) · a soft cap | GR-02 |
| PD-3 | Who pays Meta for WhatsApp template messages | **The business, directly**: each one's account carries its own payment method through Embedded Signup, with no markup and no money through us · we bill and resell. **Decided 2026-10-24: the first.** The cost shown on a broadcast is an estimate from Meta's rate card, not a charge | GR-23 |
| PD-4 | Broadcasts by plan | **Pro and Max, with a monthly recipient quota** · Max only. **Decided 2026-10-24: the first**: Pro 2,500 recipients a month, Max 25,000, none on Free (`broadcast_recipients_monthly` in `billing/plans.py`) | GR-23 |
| PD-5 | Flow branching by plan | **All plans, with a step cap on Free** (for example 5 steps) · Pro only | GR-13 |
| PD-6 | Integrations (webhooks, API, Zapier, Sheets) | **Decided 2026-10-24 ("for now"): webhooks on all plans (Free 1, Pro 5, Max 20 endpoints); Sheets, API and Zapier on Pro and Max** | GR-04 |
| PD-7 | Website chat widget | **Decided 2026-10-24 (C-111): on every plan; Free shows "Powered by Social Hood", Pro and Max can turn it off; abuse limits on all plans.** Was: Pro and Max with the link on Free · paid only | GR-28 |
| PD-8 | Commerce (catalogue, payments) | **Pro and Max** · Max only | GR-31 |
| PD-9 | Max plan contents at launch | **Team, broadcasts and higher quotas, so Max goes on sale** (today "Coming soon") · keep Max hidden | Wave 4 |
| PD-10 | Contacts across channels | **One contact per channel identity; link them by hand later** (P6 decides automatic matching) · automatic matching by phone or email now | GR-02 |

---

## D. The tasks

Each task ships with all of this, as usual:
- the API with tests and the generated client (`pnpm gen:api`);
- the web UI with unit tests;
- an e2e flow on the sandbox where a platform is involved (the sandbox adapter in
  `platforms/sandbox` must emit every new webhook);
- a `/dev` or ui-shots screen;
- an Ask read tool for new data;
- docs: the BUILD_SPEC requirement, plus CONFLICTS for additions.

### Wave 0: get ready (now)

#### GR-00 · The App Review kit · S · owner-facing
- **Why:** you'll submit once, so the kit has to be right first time and stay current as features
  land.
- **Do:**
  - the final permission list (section F), with each permission's use-case text in Meta's
    wording;
  - a step-by-step screencast script per permission;
  - test-user instructions for reviewers;
  - checks that the privacy, terms and data-deletion pages match the business details (O-2);
  - the data-deletion callback URL (this exists).
- **Output:** `docs/ops/app-review.md`. Update it at the end of every wave.

### Wave 1: foundations

These have the fewest dependencies, and later waves stand on them.

#### GR-01 · Webhook coverage: postbacks, referrals, opt-ins, Live comments · S–M
- **Why:** ice breakers, ref links, click-to-DM ads, opt-ins and Live comments all arrive on fields
  we don't subscribe to.
- **Platform:** the Instagram API with Instagram Login offers `messaging_postbacks`,
  `messaging_referral`, `messaging_optins` and `live_comments` (Meta's overview, 2026).
  Live-comment events arrive only while the broadcast runs. For outside accounts, webhooks need
  Advanced Access (after App Review). WhatsApp delivers click-to-WhatsApp ad data in a message's
  `referral` object.
- **Do:**
  - Add the four fields to `SUBSCRIBED_FIELDS`, and re-subscribe connected accounts with a one-off
    job.
  - Parse referrals, postbacks and opt-ins into typed events in `platforms/instagram/parse.py`.
    Today `referral` and `optin` fall through as `Unsupported`.
  - Parse `live_comments` as comments with `is_live`, and WhatsApp `referral` into the same
    referral event.
  - Store each conversation's entry source (`entry_source`: organic, ref link, ad, ice breaker;
    plus `entry_ref` and `entry_ad_id`), and the contact's first source.
  - Show the source in the inbox details panel.
  - The sandbox emits all of them.
- **Done when:** a referral, a postback and a Live comment from the sandbox are stored with their
  source and visible in the inbox.

#### GR-02 · Contacts foundation (backend) · M
- **Why:** lead capture, tags, segments, broadcasts, export, Sheets and Leads all need a real
  contact record. The `contacts` table exists, with one row per channel identity, but has no tags,
  fields or consent.
- **Do:**
  - **Migrations:**
    - `tags` (per workspace, with a colour from the identity palette) and `contact_tags`;
    - `contact_field_definitions` (key, label, type: text, email, phone, number, date or choice);
    - `contacts.fields` (JSONB, validated against the definitions);
    - `contacts.email` and `contacts.phone`, with `*_source` and `*_verified`;
    - `contact_consents` (channel, purpose such as marketing, source, given_at, revoked_at,
      evidence: the message or form);
    - `contacts.last_activity_at`.
  - **API:**
    - list contacts with filters (tag, field, platform, lead score, last activity, consent) and
      cursor paging;
    - get one, update tags and fields, bulk tag and untag;
    - manage field definitions and tags;
    - **CSV export** as a job that emails a signed link (the R2 "data export").
  - The contact `fields` are usable as message variables (`{first_name}` exists; add
    `{field.key}`).
  - Ask tool: `list_contacts`.
- **Done when:** contacts can be filtered by tag and field over the API, exported to CSV, and
  carry a consent history.

#### GR-03 · The flow engine (backend) · L
- **Why:** the biggest gap against every DM tool is branching, data capture and actions. Today an
  automation is one flat path, with "tap first" and the follow nudge as fixed extras.
- **Design:**
  - A versioned `automation_steps` graph per automation. Each step is a typed node:
    - `send` (text, image, link buttons, quick replies);
    - `ask` (free text, email or phone, validated, saved to a contact field);
    - `branch` (on a quick reply or button tapped, or on a condition: tag, field, follows the
      business, platform, lead score);
    - `action` (add or remove a tag, set a field, notify the team, hand to a person, later
      assign (GR-20) and call a webhook (GR-04));
    - `delay` (bounded so the send stays inside the reply window);
    - `randomize` (A/B);
    - `end`.
  - Run state is persisted in `automation_run_steps`, so a run can wait for a reply or a delay and
    resume idempotently.
  - A wait expires when the reply window does.
  - Store the definition as validated JSON with a schema version, plus a compiled graph for the
    runtime.
- **Migration:**
  - Compile every existing automation into an equivalent graph. Trigger and keywords stay as they
    are. The message becomes `send`. "Tap first" becomes `send` with a quick reply, then a `branch`,
    then `send`. The follow nudge becomes an `action` with a `send`.
  - The flat columns stay readable until a later cleanup (expand-only).
- **Runtime:**
  - `services/automations/runtime.py` executes graphs.
  - The dry-run Test tab and the Preview run the same executor with a fake sender.
  - Every step writes a result for the Activity page and analytics.
- **Rules kept:** cooldowns, run windows, the order when busy, the 7-day comment limit, the
  private-reply queue, plan entitlements, the read-only state after a downgrade.
- **Done when:** every existing automation behaves the same after the migration (a regression
  suite over all templates), and a two-branch flow with an `ask` step runs end to end on the
  sandbox.

#### GR-04 · Outbound events and webhooks · M
- **Why:** "send my leads somewhere" is the request behind Zapier, Make, Sheets and CRMs. Build one
  event pipeline that every integration sits on.
- **Do:**
  - **The events:** `contact.created`, `contact.updated`, `contact.tagged`, `lead.captured`,
    `message.received`, `conversation.assigned`, `automation.run.completed`, `broadcast.finished`.
    Each event has a version and a documented payload.
  - **Endpoints:** a workspace's endpoints get an HMAC secret.
  - **Delivery:**
    - a job with exponential retries;
    - a delivery log (status, response code, duration);
    - replay;
    - auto-disable after repeated failures, with a notification.
  - **Settings › Integrations** page: add an endpoint, see the secret once, send a test event, see
    deliveries.
  - Payloads carry no access tokens and no more personal data than the event needs.
- **Done when:** a test endpoint receives a signed `lead.captured`, and a failing endpoint shows
  its retries in the log.

#### GR-05 · Activity and reliability page · S–M · roadmap P1
- As specified in the roadmap: one feed of automation runs, sends, failed webhooks and account
  status, with plain-language reasons, one action each, and alerts.
- **Adds:** webhook deliveries (GR-04) and broadcast failures (GR-23) once those exist.

### Wave 2: triggers and ways in

These work on today's flat model; GR-03's migration later carries them into flows.

#### GR-06 · Story reply trigger · S
- **Platform:**
  - A story reply arrives as a DM with `reply_to.story`, on `messages`; we parse it already.
  - It opens the 24-hour window, so a reply is a normal DM.
  - Story *likes* don't trigger.
- **Do:**
  - Trigger `story_reply`, with a scope: any story, or a chosen story from the last 24 hours (list
    active stories from the API).
  - Match any reply or keywords, with the existing match modes.
  - An optional heart reaction.
  - The editor's "When" step gets the option, plus a story picker.
  - A template: "Reply to story → send the link".
- **Done when:** a sandbox story reply with the keyword gets the automation's DM, recorded as a
  run.

#### GR-07 · Story mention trigger · S–M
- **Platform:**
  - A mention arrives as a DM with a `story_mention` attachment; we parse it.
  - The media URL expires, so store a thumbnail only if policy allows, and otherwise just the
    mention record.
- **Do:**
  - Trigger `story_mention`, sending a thank-you or a reward.
  - A **Mentions** list (who, when, a link while it's live) under Comments or Home.
  - Count mentions in the analytics.
- **Done when:** a sandbox mention triggers the DM and shows in Mentions.

#### GR-08 · Entry links and QR codes · S · needs GR-01
- **Platform:**
  - Instagram: `ig.me/m/<username>?ref=<code>` sends a `messaging_referral` with the ref.
  - WhatsApp has no ref parameter, so use `wa.me/<number>?text=<keyword>`, a prefilled keyword the
    DM-keyword trigger catches.
- **Do:**
  - Trigger `entry_link`, where each link has a code, a name and an automation.
  - Generate a QR code (SVG and PNG) for each link.
  - Copy-link and download buttons.
  - Per-link stats: opened conversations and runs.
  - Links live under Automations › Entry links.
- **Done when:** opening the link in the sandbox starts the right automation and counts.

#### GR-09 · Ads entry: click-to-Instagram-DM and click-to-WhatsApp · S–M · needs GR-01
- **Platform:**
  - Ad clicks arrive as referrals with the ad id.
  - A click-to-WhatsApp conversation opens a 72-hour window where follow-up marketing messages are
    free (*verify* the current rule).
- **Do:**
  - Trigger `ad_click`: any ad, or chosen ad ids. The ad id can be entered, and listing ads would
    need `ads_read`, so that is optional and *verify*.
  - Attribution: "From an ad" in the inbox, the ad id on the conversation, a filter in the
    analytics.
  - Store `ctwa_clid` for a later Conversions API.
- **Done when:** a sandbox ad referral starts the ad automation and the conversation shows its
  source.

#### GR-10 · Live comments trigger · S · needs GR-01
- **Platform:**
  - Live comments arrive only during the broadcast.
  - A private reply is allowed only while it's live.
  - It needs `instagram_business_manage_comments`, which we already have.
- **Do:**
  - The comment triggers gain a "Live" scope.
  - Send private replies at once and skip any that arrive late.
  - The Live's runs show in Activity.
- **Done when:** a sandbox Live comment with the keyword gets a private reply, and one that arrives
  after the broadcast is recorded as skipped (ended).

#### GR-11 · Ice breakers (conversation starters) · S · needs GR-01
- **Platform:**
  - Up to 4 questions, set with `/messenger_profile` (`platform=instagram`, a default locale is
    required).
  - A tap arrives as a postback.
  - They don't show on desktop.
- **Do:**
  - Settings or Automations › Conversation starters: up to 4 questions, each mapped to an
    automation or "answer with AI".
  - Sync with Meta, and show its errors.
  - Trigger `ice_breaker`.
- **Done when:** the sandbox shows the starters, and a tap runs the mapped automation.

#### GR-12 · Welcome and default replies · S
- **Do:**
  - Trigger `first_message`, for a contact's first DM ever on that account.
  - Trigger `default_reply`: a DM that no automation matched, while AI mode is Off. With Suggest or
    Auto, the AI already answers.
  - Both obey cooldowns, so they can't loop.
- **Done when:** a new sandbox contact gets the welcome once, and an unmatched DM gets the default
  reply only when AI is Off.

### Wave 3: flows in the product (needs GR-03)

#### GR-13 · The flow editor · L
- **Why:** expose GR-03's engine. Use a **structured, mobile-first editor**, not a free canvas.
  Steps are a vertical list, a branch is an indented group with its own steps, and every step is a
  card with validation.
- **Do:**
  - Rebuild the "Then" part of `AutomationEditor` on the step model:
    - an "Add step" menu (Send, Ask, Branch, Action, Delay, Split, End);
    - drag to reorder within a branch;
    - each step's own fields (reusing today's DM builder, buttons and media);
    - per-step validation and activation errors;
    - "jump to step" from errors.
  - The Preview pane walks one branch at a time, with a branch picker; the Test tab runs the flow
    dry.
  - The step cap per plan comes from PD-5.
- **Done when:** a user builds "comment → ask email → branch on button → send A or B" on a 375 px
  screen and at 1280, and it runs on the sandbox.
- e2e F-11 changes from the flat editor to the flow editor.

#### GR-14 · Data capture and consent · M · needs GR-02 and GR-03
- **Do:**
  - The `ask` step types: email (validated, normalised), phone (E.164, India +91 by default) and
    free text.
  - A retry prompt on invalid input, and skip after N tries.
  - Saved to contact fields, emitting `lead.captured` (GR-04).
  - An optional **marketing consent** question, recorded in `contact_consents` with the message as
    evidence. This is required before WhatsApp broadcasts (GR-23).
  - Default copy for the question and the confirmation, through the copy lint.
- **Done when:** a captured email lands on the contact, triggers the webhook, and appears in the
  CSV export.

#### GR-15 · Link click tracking and flow analytics · M · needs GR-03
- **Why:** automations today report "sent". Competitors report clicks and conversions. Link click
  tracking is R2 in the spec.
- **Do:**
  - Tracked redirect links (`/l/<code>` on our domain) for link buttons. Record the click with run,
    step and contact, never in the URL itself.
  - An opt-out per automation.
  - **Per-step funnel:** reached, sent, delivered, read where the platform says, button taps, link
    clicks, captures.
  - The A/B split's results.
  - Shown in the editor's Stats tab and on the Activity page.
- **Done when:** a link click in the sandbox shows on the step's funnel within a minute.

#### GR-16 · Template gallery, version 2 · S · needs GR-06 to GR-14
- New templates on the new triggers and steps:
  - a giveaway (story mention, then a thank-you);
  - a lead magnet (comment, then ask for an email, then send the PDF link);
  - price please (comment, then a quick reply for the variant, then the price);
  - book a call (ask for a phone, notify the team);
  - a coupon (from an entry link).
- Update `services/automations/templates.py` and the gallery.

#### GR-38 · Visual answers in Ask (generative UI) · M · needs GR-02 · decided 2026-10-24
- **Why:** Ask Social Hood answers performance, ranking, sentiment and lead questions with long
  paragraphs. Members should see KPI cards, charts and tables instead. The design, research and
  decision are in `docs/architecture/generative-ui/` (the owner chose option C).
- **Do** (backlog VIS-01 to VIS-06 in `docs/architecture/generative-ui/10-implementation-backlog.md`):
  - **The missing data:** a read path for `account_daily_metrics` (period sums, comparable
    days, gaps), plus agent tools `compare_periods` and `metric_trend`. Today nothing can answer
    "this month vs last month".
  - **Typed visuals:** tools build them from service data, so numbers never come from the model.
    The run exposes `visuals` the way it exposes `action_cards`, behind an `agent_visuals` flag.
    No migration.
  - **The first three visuals,** drawn with our own components (`MetricTile`, `PostThumb`,
    `SentimentBar`, `Table`): a period comparison, ranked posts and a sentiment summary.
  - **Tests:** unit, integration, tenancy, roles, an e2e spec, and eval number checks.
- **Later** (VIS-07 to VIS-13): trends, lead lists, tables, progressive visuals, range
  controls, and the report page (with GR-34).
- **Not now:** OpenUI. An offline spike (VIS-14) may follow, against the gate in doc 07.
- **Done when:** "Compare my Instagram this month with last month" shows cards whose numbers
  equal the service's, and conceptual questions show no visual.

### Wave 4: contacts, team, broadcasts

#### GR-17 · The contacts page · M · needs GR-02
- **Do:**
  - **Contacts** in the main nav:
    - a list with search and filters (tag, field, platform, lead score, consent, last activity);
    - saved segments;
    - bulk tag;
    - export.
  - **A contact drawer** (also in the inbox details panel):
    - tags and fields, editable;
    - consents;
    - a timeline of conversations, comments, automation runs, captures and broadcasts received.
  - Works at 375 px as a list with a full-screen drawer.
- **Done when:** filtering by "tag = lead-magnet and has email" and exporting gives the right rows.

#### GR-18 · Leads · M · roadmap P2 · needs GR-17
- As the roadmap specifies: stages (new, qualified, follow up, won, lost) with history, automatic
  qualification from the lead score and intents, the "gone cold" job, and a Leads view.
- **Adds:** stages live on the contact, with the conversation linking to it; a captured email
  qualifies a lead; the stage is usable as a flow condition.

#### GR-19 · Team members and roles · M · needs PD-1
- **Platform:** Clerk invitations (the identity provider).
- **Do:**
  - Invite by email.
  - Accept: join the workspace with a role (owner, admin or agent; the schema has them).
  - A members page: change a role, remove a member.
  - **A permission matrix enforced in the API:**
    - agents reply, tag and assign;
    - admins also edit automations, knowledge and settings;
    - owners also handle billing, deletion and members.
  - Seat quota from `members`.
  - An audit of who sent, edited or deleted.
- **Done when:** an agent invited in e2e can reply but gets 403 on automations and billing, and the
  UI hides what the role can't do.

#### GR-20 · Assignment · M · needs GR-19
- **Do:**
  - Assign a conversation to a member, or to nobody.
  - An "Assigned to me" view and filter.
  - Optional round-robin among members marked available.
  - The assignee gets a notification (push and in-app).
  - The flow action "assign".
  - The assignee shows in the list row and header.
- **Done when:** a round-robin assignment notifies the agent, and the view shows only their
  conversations.

#### GR-21 · Saved replies · S
- **Do:**
  - Workspace snippets, with a title, shortcut and body, using `{first_name}` and the contact
    fields.
  - A `/` picker in the composer, extending the `TemplatePicker` used for WhatsApp templates.
  - Usable in flows as "send a saved reply".
- **Done when:** typing `/price` in the composer inserts the filled snippet.

#### GR-22 · Business hours and away messages · S · R2 in the spec
- **Do:**
  - Hours per workspace or account, in the workspace time zone.
  - Auto mode either only out of hours or always (a setting).
  - An away message out of hours, once per conversation per window.
  - Automations may require "inside hours" as a condition.
- **Done when:** a message at 23:00 gets the away reply once and the Auto setting is respected.

#### GR-23 · WhatsApp broadcasts · L · needs GR-02, GR-14, O-11, PD-3, PD-4 · built 2026-10-24 behind `BROADCASTS_ENABLED` (C-112)
- **Platform:**
  - Only approved templates, and only to contacts with marketing opt-in.
  - Meta prices per message by category (marketing, utility); India is billed in INR from 2026.
  - Sending limits follow the number's messaging tier and quality rating.
  - Opt-outs must be honoured.
  - Instagram has no broadcast API outside the 24-hour window, so there are no Instagram
    broadcasts.
- **Do:**
  - **A broadcast:**
    - its audience is a segment (GR-17) filtered to opted-in WhatsApp contacts;
    - a template, with each variable mapped to a contact field;
    - send now or schedule;
    - a cost estimate from Meta's rate card;
    - a preview.
  - **Throttling** to the tier, pausing automatically if the quality rating drops.
  - **Per-recipient status:** queued, sent, delivered, read, failed (with reason); and replies.
  - A STOP or "unsubscribe" reply revokes consent automatically.
  - The quota from PD-4.
  - Results in Activity and on the contact timeline.
- **Done when:** a sandbox broadcast to 3 opted-in contacts reports each status, skips the
  opted-out one, and a STOP reply revokes consent.

#### GR-24 · Sequences (multi-step follow-ups) · M · needs GR-03 and GR-23 · R3, brought forward
- **Do:**
  - A sequence is timed steps after an entry event (captured, tagged, broadcast replied).
  - WhatsApp steps outside the window use templates and need opt-in. Instagram steps run only
    while the window is open, and are otherwise skipped with a reason.
  - It stops on reply, a tag or a stage.
- **Done when:** a three-day sequence sends day 1 and day 3 to an opted-in sandbox contact and
  stops when they reply.

### Wave 5: integrations and new channels

#### GR-25 · Public API and API keys · M · needs GR-02 and PD-6
- **Do:**
  - Workspace API keys: named, scoped (read contacts, write contacts, send messages within the
    platform rules, read conversations), revocable, shown once.
  - A separate rate limit.
  - The same handlers as the app's API, under `/public/v1`.
  - A docs page generated from the OpenAPI spec.
- **Done when:** a key with read scope lists contacts and gets 403 on a write.

#### GR-26 · Zapier app, then Make · M · needs GR-04 and GR-25
- **Zapier triggers:** new contact, lead captured, tag added, new message, run completed.
- **Zapier actions:** add or remove a tag, set a field, send a message inside the window.
- Submit to the Zapier directory. Make follows, with the same building blocks.
- **Done when:** a private Zap moves captured leads to a Google Sheet.

#### GR-27 · Native Google Sheets sync · S–M · needs GR-04 and GR-14
- **Platform:** Google OAuth with a narrow scope (`drive.file`, on sheets the user picks).
  *Verify* whether Google needs app verification for it (O-10).
- **Do:** pick a sheet, map fields to columns, append a row per captured lead, retry with the
  webhook machinery.
- **Done when:** a capture appears as a row within a minute.

#### GR-28 · Website chat widget · L · PD-7 decided (C-110)
- **Why:** Spur, respond.io and Tidio have one. We already own the inbox, the knowledge-based AI,
  the analysis and realtime, so a web channel reuses all of it.
- **Do:**
  - A `web` platform in `platforms/`.
  - An embeddable script, `<script src=…/widget.js data-workspace=…>`, with a small isolated
    bundle in the brand theme.
  - Anonymous visitors, identified by email capture.
  - Conversations in the inbox with platform "Website".
  - AI modes, knowledge and escalation work as on Instagram.
  - Spam and abuse limits, and an allowed-domains list.
  - Free plans show "Powered by Social Hood".
- **Done when:** a test page's widget conversation shows in the inbox with an AI answer from
  knowledge, and a reply from the inbox reaches the widget in real time.

#### GR-29 · Facebook Pages, Messenger and comments · L · roadmap P4
- As the roadmap specifies (a `PlatformAdapter` for Facebook, inbox, comments, automations).
- **Adds:** every wave 2 to 4 trigger and step works on Messenger where Meta allows (verify each).
- It needs the second App Review submission (O-10).

#### GR-39 · Instagram Story scheduling · S–M · owner request 2026-10-24
- A "Story" post type for Instagram accounts beside image, Reel and carousel: one image or one
  video, no caption, published through the Content Publishing API (`media_type: STORIES`), scheduled,
  retried and reported like any post. After publishing it shows in the live stories the story-reply
  picker lists, with its 24 hour expiry.
- **Out of scope:** WhatsApp Status has no API; Facebook Page Stories (see GR-30).
- **Done when:** a Story scheduled from the composer publishes on the sandbox, appears in the story
  picker and says when it disappears.

#### GR-30 · Facebook publishing and best posting times · M · needs GR-29
- Publish to Pages from the composer.
- **"Best times" (R2 in the spec):** from each account's own post insights, a suggested slot per
  weekday, shown in the composer and the Posting times drawer.
- **Built as:** photos, several photos, a video and text posts through our own scheduler; best
  times from the account's own post engagement (see C-115). Page Stories are not built.

### Wave 6: commerce

#### GR-31 · Product catalogue · M–L · needs PD-8
- **Do:**
  - Products: name, price, stock, image, link and variants. Add them by hand, by CSV, or by
    **Shopify import** (a Shopify app with OAuth and product webhooks, O-10).
  - The AI answers product questions with price, stock and a link, through the knowledge pipeline
    with structured product facts.
  - A flow step "send product".
- **Done when:** asking "price of the blue kurta in M?" in the sandbox gets the right price and
  link, from Suggest or Auto.

#### GR-32 · Payment requests and order capture · L · needs GR-31
- **Platform:** payments go to the business's own account, never through us.
  - Razorpay Payment Links through their keys or OAuth (*verify* the partner route);
  - or a UPI intent link (`upi://pay?...`) with their VPA.
- **Do:**
  - An order in chat: products, quantities, address, total.
  - Send a payment link.
  - A "paid" webhook marks the order paid and emits an event.
  - An Orders list and a timeline entry.
  - The R2 "order capture and UPI payment requests".
- **Done when:** a test-mode Razorpay link marks the sandbox order paid.

#### GR-33 · WhatsApp catalogue messages · M · needs GR-31 · *verify*
- Sync products to a Meta commerce catalogue, and send product and product-list messages on
  WhatsApp.
- Check the current Commerce Manager requirements and permissions first.

### Wave 7: intelligence and AI

#### GR-34 · Trends and a weekly report · M · roadmap P3
- As the roadmap specifies. It extends the existing weekly digest (`jobs/tasks/digests.py`,
  `notify/digest.py`) rather than adding a new email.
- **Adds:** mentions, entry links, ads and capture counts, once those exist.

#### GR-35 · Website crawl into knowledge · S–M · R2 in the spec
- Today knowledge can read one page (`services/knowledge/extract.py`).
- **Add:**
  - a site crawl (sitemap first, same-domain links, a page cap per plan, robots.txt respected);
  - a scheduled re-crawl;
  - per-page sources in the knowledge list.

#### GR-36 · Copilot write actions · L · roadmap P5
- As the roadmap specifies (the action gateway, approvals, audit).
- **Adds:** the agent drafts **flows** (GR-03), **broadcast drafts** (GR-23) and **segments**
  (GR-17) for approval, never sending on its own.

#### GR-37 · Go-to-market pages · S · needs waves 2 to 4
- **Pages:** "Switch from Manychat"; comparison pages (vs Manychat, vs Interakt); feature pages
  (comment intelligence, the AI inbox, publishing); and pricing updated with the new entitlements.
- Every claim must be checkable against our own code and their public pages, as in
  competitors.md.

---

## E. Order, dependencies and lanes

```
Owner:  O-1 → O-2 → O-3 ─────────────→ O-6 (App Review)    O-7 WhatsApp  O-8 INR  O-9 pricing
                         O-4 ↑  O-5 ↑ (after wave 2)

Wave 0  GR-00 ────────────────────────────── (updated every wave)
Wave 1  GR-01  GR-02  GR-03 (L)  GR-04  GR-05
Wave 2  GR-06  GR-07  GR-12          GR-08 GR-09 GR-10 GR-11  (← GR-01)
Wave 3  GR-38 (← GR-02)  GR-13 (← GR-03)  GR-14 (← GR-02, GR-03)  GR-15 (← GR-03)  GR-16 (← waves 2–3)
Wave 4  GR-17 (← GR-02) → GR-18     GR-19 → GR-20     GR-21  GR-22     GR-23 (← GR-14, O-11) → GR-24
Wave 5  GR-25 → GR-26    GR-27 (← GR-04, GR-14)    GR-28    GR-29 → GR-30
Wave 6  GR-31 → GR-32, GR-33
Wave 7  GR-34  GR-35  GR-36 (← GR-03, GR-23)  GR-37
```

**Suggested batches,** three parallel lanes as in the UI programme:
1. **Batch 1:**
   - GR-00;
   - GR-01 with GR-06, GR-07 and GR-12 (the platform lane);
   - GR-02 (the data lane);
   - GR-03 (the engine lane, the long one).
2. **Batch 2:**
   - GR-08 to GR-11 (platform);
   - GR-04 and GR-05 (data);
   - GR-03 continues.

   **Wave 2 is done here, so the App Review screencasts can be recorded (O-5).**
3. **Batch 3:** GR-38 (visual answers in Ask, first), then GR-13, GR-14, GR-15 and GR-17.
4. **Batch 4:** GR-16, GR-18 to GR-22.
5. **Batch 5:** GR-23 and GR-24, after O-11; GR-25 to GR-27.
6. **Batch 6:** GR-28 to GR-30.
7. **Batch 7:** GR-31 to GR-33.
8. **Batch 8:** GR-34 to GR-37.

**Roughly:**
- Waves 1 to 4 are the parity core, about 3 to 4 months with three lanes.
- Waves 5 to 7 are another 3 to 4.
- App Review usually finishes while wave 3 or 4 is underway, so launch can include the parity core.

---

## F. Permissions and webhook fields for App Review

*Verify* each one against Meta's current docs in GR-00. Status: **have** means we request it
today; **add** means new.

| Feature | Permission | Webhook fields | Status |
|---|---|---|---|
| Inbox, DM automations, story replies and mentions, ice breakers, entry links, ads entry, welcome and default replies | `instagram_business_basic`, `instagram_business_manage_messages` | `messages` (have), `messaging_postbacks`, `messaging_referral`, `messaging_optins`, `messaging_seen` (have), `message_reactions` (have), `message_edit` (have) | permissions have; 3 fields add |
| Comment automations, Live comments, moderation | `instagram_business_manage_comments` | `comments` (have), `live_comments` | permission have; field add |
| Publishing | `instagram_business_content_publish` | — | have |
| Insights and best times | `instagram_business_manage_insights` | — | have |
| WhatsApp inbox, templates, broadcasts, sequences | `whatsapp_business_messaging`, `whatsapp_business_management` (+ `business_management` for Embedded Signup) | `messages` (with `referral` for click-to-WhatsApp) | have management; check messaging in GR-00 |
| Ads entry: listing ads (optional) | `ads_read` | — | add only if GR-09 lists ads |
| WhatsApp catalogue (GR-33) | `catalog_management` (*verify*) | — | add, later submission |
| Facebook Pages (GR-29, GR-30) | `pages_show_list`, `pages_messaging`, `pages_manage_engagement`, `pages_read_engagement`, `pages_manage_posts`, `read_insights` (*verify*) | `messages`, `feed` | add, second submission |

---

## G. Definition of done (every GR task)

1. The PR names the GR task, the gap it closes (competitors.md) and any decision it applies.
2. Backend, API, tests, the generated client, the web UI and its tests ship together. No mock-only
   UI.
3. The platform rule is named in code and docs. Anything marked *verify* was checked, with the doc
   link in the PR.
4. The sandbox emits the new events, and an e2e flow covers the feature.
5. Expand-only migration, with the tenant filter on every query (with tests), idempotent side
   effects, and no tokens or extra personal data in logs or outbound events.
6. The entitlement key exists in `billing/plans.py`, with values from section C. Over the limit, the
   API returns 402 and the UI shows the upgrade path.
7. **Design and copy:** DESIGN_SYSTEM primitives; the design lint and copy lint pass; the page
   fills the width and works at 320, 375, 768, 1280 and 1536 px; it is keyboard accessible, with no
   new axe violation.
8. Ask Social Hood has a read tool for any new data.
9. **Docs:** the BUILD_SPEC requirement is added or updated, CONFLICTS records additions and
   decisions, and GR-00's App Review kit is updated if a permission or flow changed.
10. **Repository rules:** a `feature/gr-*` branch from develop, squash-merged; gitleaks clean; no
    Claude attribution; the central integration run is green before the PR.

---

## H. Risks

| Risk | Mitigation |
|---|---|
| App Review takes long or rejects a permission | One submission planned in detail (GR-00); every feature works for role accounts meanwhile; features degrade cleanly when a permission is missing |
| Meta restricts accounts for automation spam | Keep the guardrails (cooldowns, run windows, the private-reply queue, no follow-gating); broadcasts throttled by quality rating; consent required |
| The flow engine migration breaks today's automations | A regression suite over every template and existing definition; compiled graphs reviewed before the flat columns stop being written; a feature flag per workspace |
| WhatsApp marketing law in India | O-11 before GR-23 ships; recorded consent with evidence; STOP honoured automatically |
| Scope creep from competitors | Only gaps that recur across several competitors are in. Single-vendor extras (Live gating, follow-to-DM, TikTok) are out until the APIs and demand say otherwise |
| Free-plan abuse of the widget or broadcasts | Rate limits, per-plan quotas, an allowed-domains list, Meta's own tier limits |

---

## I. Out of scope, and why

| Item | Why |
|---|---|
| Follow to DM | No generally available webhook for new followers; even Manychat's beta is unreliable (Oct 2026) |
| Share to DM | No documented event for "someone shared your post to their story" in the Instagram API we use; revisit if Meta adds one |
| Follow-gating | Against Meta's Spam Community Standard (our nudge never gates: `services/automations/nudge.py`) |
| Instagram broadcasts | No API to message outside the 24-hour window |
| TikTok, Telegram, SMS, native mobile apps, social listening, a free-form canvas | As in competitors.md: gated APIs, little demand here, DLT rules, the installable web app covers mobile, API limits, a structured editor covers branching |
| Email channel (roadmap P6), YouTube, Business Profile, Telegram, Threads (P7) | Unchanged in the roadmap, after this plan |

---

## J. Where each gap went

| Gap (competitors.md) | Tasks |
|---|---|
| Story reply and mention triggers | GR-06, GR-07 |
| Lead capture and contacts | GR-02, GR-14, GR-17, GR-18 |
| Team seats, assignment, saved replies | GR-19, GR-20, GR-21 |
| Broadcasts and campaigns | GR-23, GR-24 |
| Commerce | GR-31, GR-32, GR-33 |
| Ads and other ways in | GR-01, GR-08, GR-09, GR-10, GR-11, GR-12 |
| Integrations | GR-04, GR-25, GR-26, GR-27 |
| Website chat widget | GR-28 |
| Publishing networks, best times, reports | GR-29, GR-30, GR-34 |
| Branching flow builder, A/B, analytics | GR-03, GR-13, GR-15, GR-16 |
| Roadmap P1, P2, P3, P4, P5 | GR-05, GR-18, GR-34, GR-29, GR-36 |
