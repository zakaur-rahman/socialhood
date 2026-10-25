# Product roadmap: what to build after the UI programme

Ideas collected on 2026-10-17 from a review of twelve SaaS directions, filtered against what Social
Hood already does. Ordered by priority: do them top to bottom unless something changes. Each item
says why, what already exists in the code, the steps, the external constraints to verify first,
and when it counts as done.

Effort: **S** about a week, **M** two to three weeks, **L** a month or more, for one developer
working with agents.

External API facts (permissions, review processes, costs) change. **Re-check each provider's
official documentation before starting an item**; the notes below are what we believed on the
date above, not guarantees.

**Status (2026-10-22):**
- Every item below, plus the gaps from the competitor analysis ([competitors.md](competitors.md),
  [competitor-manychat.md](competitor-manychat.md)), is now scheduled in
  **[roadmap/IMPLEMENTATION_PLAN.md](roadmap/IMPLEMENTATION_PLAN.md)** as tasks GR-00 to GR-37,
  with an owner track (O-1 to O-11) and decisions (PD-1 to PD-10).
- The plan sets the build order. This file keeps the why and what.
- P0 runs as the owner track while engineering builds, because every feature can be developed and
  tested with role accounts and the sandbox before App Review passes.

## What Amplychat already covers

Several of the reviewed ideas are already built. Build on these instead of starting over.

| Idea | Already in the code |
|---|---|
| Customer intelligence ("AudienceBrain") | Per-message analysis: sentiment, intent, topics, lead score (`services/analysis.py`, `models/ai.py`); Home's sentiment, top-intents and top-posts cards; conversation summaries (`services/summaries.py`); knowledge gaps |
| Lead follow-up ("LeadRecovery") | `lead_score` on conversations; the Home priority queue (`services/priority_queue.py`); "Needs you" hand-off (`services/takeover.py`); reminders before a reply window closes for leads scoring 60 or more (`services/follow_ups.py`) |
| Performance analytics | Daily account snapshots and post insights (`services/analytics/`) |
| An AI copilot ("OpsPilot") | Ask Amplychat, a read-only agent (C-033); write tools through one action gateway are planned for R2 (`docs/agent-architecture.html`) |
| Automation reliability | Idempotency keys, webhook intake and processing, retries, automation run results, agent runs |
| A shared integration layer | `platforms/base.py`'s `PlatformAdapter` protocol, implemented per platform |

Channels today: **Instagram and WhatsApp only.** `facebook` and `linkedin` exist as enum values in
`models/connections.py` with no integration behind them.

## P0: Meta business verification and App Review (blocker)

**Why first:** until the Meta app has Advanced Access, only people with a role on the app can
connect Instagram. No feature below reaches paying customers before this passes.

Three separate things, often confused:
- **Business Portfolio verification** proves the business behind the Meta Business Portfolio.
- **App Review** approves each permission for its stated use, with screencasts.
- **Advanced Access** lets the app use a permission with accounts outside its roles. It generally
  requires business verification as well as App Review.

**Steps:**
1. In the app dashboard (developers.facebook.com → the Amplychat app → App Review), note the exact
   message and the permissions it names (for example `instagram_business_manage_messages`,
   `instagram_business_manage_comments`). Request only what the product uses.
2. Choose the cheapest legitimate business identity:
   - operate as a **sole proprietor** under the owner's own name;
   - register on **Udyam** (udyamregistration.gov.in), which is free for eligible enterprises; never pay an
     intermediary for it;
   - don't incorporate, or register for GST, only for Meta, unless Meta's flow refuses everything
     else.
3. Make the public surface consistent with the business details you submit: the website names the
   business, with a contact address and email; the privacy policy, terms and data-deletion pages
   are reachable (they exist: `app/(marketing)`).
4. Meta Business Suite → Settings → Business portfolio info (or Security Center) → **Start
   verification**. Enter the real legal name and address, and upload only documents the flow lists
   as accepted. Keep everything genuine and matching.
5. App Review: for each permission, write the use case and record a screencast of the real flow on
   the production URL (connect Instagram, receive a DM, reply, comment automation).
6. When approved, switch the app to Live and test with an account that has no role on the app.

**Done when:** an Instagram account with no role on the app can connect and use the inbox and
automations in production.

## Parity and growth: the competitor gaps (added 2026-10-22)

These gaps recur across Manychat, the Instagram DM tools, the Indian WhatsApp platforms,
omnichannel inboxes and social suites. Detail, design and order are in the implementation plan.

| Item | Tasks | Size |
|---|---|---|
| Webhook coverage: postbacks, referrals, opt-ins, Live comments | GR-01 | S–M |
| Contacts: tags, fields, consent, CSV export; a contacts page | GR-02, GR-17 | M + M |
| Flow engine and editor: branching, data capture, actions, delays, A/B | GR-03, GR-13, GR-14, GR-16 | L + L + M + S |
| Outbound webhooks and events | GR-04 | M |
| New triggers: story replies, story mentions, entry links and QR codes, click-to-DM and click-to-WhatsApp ads, Live comments, ice breakers, welcome and default replies | GR-06 to GR-12 | S each, mostly |
| Link click tracking and flow analytics | GR-15 | M |
| Team: members and roles, assignment, saved replies, business hours | GR-19 to GR-22 | M, M, S, S |
| WhatsApp broadcasts and sequences | GR-23, GR-24 | L + M |
| Public API, Zapier and Make, Google Sheets | GR-25 to GR-27 | M, M, S–M |
| Website chat widget | GR-28 | L |
| Facebook publishing and best posting times (with P4) | GR-29, GR-30 | L + M |
| Commerce: product catalogue, payment requests and orders, WhatsApp catalogue | GR-31 to GR-33 | M–L, L, M |
| Website crawl into knowledge | GR-35 | S–M |
| Go-to-market pages (switch from Manychat, comparisons) | GR-37 | S |

The existing items map to tasks: P1 → GR-05, P2 → GR-18, P3 → GR-34, P4 → GR-29, P5 → GR-36.

## P1: Activity and reliability page (S)

**Why:** automations fail silently from the customer's point of view: an expired token, a missing
permission, a closed reply window. We already record these; customers just can't see them. This
builds trust and cuts support for little effort.

**Exists:** automation run results (`services/automations/results.py`), webhook processing and
failures, `SocialAccount.status` and `last_error`, agent runs, notifications.

**Steps:**
1. API: one read endpoint, `GET /workspaces/{wid}/activity`, merging automation runs, sends, failed
   webhooks processed for this workspace, and account status changes, newest first and paged.
   Tenant-filtered, with no raw payloads.
2. Plain-language reasons: map known error codes (token expired, permission missing, window
   closed, rate limited) to one sentence and one action each ("Reconnect Instagram").
3. Web: an **Activity** page in Settings or the main nav, with filters (failures only, by
   automation, by account) and a Retry action where retrying is safe and idempotent.
4. Alerts: when an automation fails N times in an hour, or an account needs reconnecting, send an
   in-app and push notification (the notifications service exists) with a deep link.
5. Tests: API tests for tenancy and paging; e2e for a failed run showing its reason and the
   reconnect link.

**Done when:** a broken automation is visible to the customer within minutes, with the reason and
the one action that fixes it.

## P2: Leads view (M)

**Why:** conversations already carry a lead score and intent, but there's no place to work leads
as a pipeline. "12 people asked about pricing this week; 5 haven't had a follow-up" is a sales
outcome customers pay for.

**Exists:** `lead_score` (0–100) per message and conversation, intents, the priority queue,
"Needs you", follow-up reminders before the reply window closes.

**Steps:**
1. Data: add a lead stage to conversations (`new`, `qualified`, `follow_up`, `won`, `lost`), plus
   `stage_changed_at` and an optional value. Expand-only migration; backfill `new` for conversations
   whose lead score is 60 or more.
2. Rules: set `qualified` automatically from the lead score and buying intents; let people move
   stages by hand; record every change for history.
3. "Gone cold": a scheduled job flags leads with no customer reply for N days (a workspace setting)
   that haven't been closed; notify the assignee.
4. API: list leads by stage with counts, a stage update, and conversion counts by week.
5. Web: a **Leads** page with stage columns or a list (whichever works at 375 px), the reason a
   lead was qualified, last activity, and one click to the conversation. Add a lead stage chip in
   the conversation header.
6. Ask Amplychat: add a read tool `list_leads` so questions like "who asked about pricing and
   got no reply?" work.

**Done when:** an owner can see every open lead, its stage and its last touch, and is told when
one goes cold.

## P3: Trends and a weekly report (M)

**Why:** the analysis already exists, but only as current numbers. Changes are what people act on:
"negative comments about delivery rose from 8% to 21% this week".

**Exists:** daily snapshots, per-message sentiment, intent and topics, top posts, knowledge gaps.

**Steps:**
1. Compute week-over-week changes for sentiment share, top topics, response time, handled-by-AI
   share, and post engagement at equal post age (C-033 already requires equal-age comparisons).
2. Detect notable changes with simple, explainable thresholds (for example a topic's share up by
   10 points and at least 10 messages). No black-box scores.
3. Home: a "This week" strip with up to three changes, each linking to the filtered inbox or
   comments.
4. A weekly email digest: the same changes plus the leads summary (P2). Send through the existing
   notification pipeline with an unsubscribe link (the marketing unsubscribe page exists), and use
   the workspace time zone.
5. Ask Amplychat: a `get_trends` read tool.

**Done when:** an owner who opens nothing during the week still learns, every Monday, what changed
and where to look.

## P4: Facebook Pages, Messenger and comments (M to L)

**Why:** it's the cheapest new channel. It uses the same Meta app, login, verification and review
process as Instagram, and the platform value already exists. C-033 already places Facebook Pages
in R2.

**Steps:**
1. Verify the current permissions and review requirements for Pages messaging and comment
   management in Meta's documentation (for example `pages_messaging`, `pages_manage_engagement`,
   `pages_read_engagement`), and add them to the App Review from P0.
2. Implement a `PlatformAdapter` for Facebook: connect a Page, receive Messenger and comment
   webhooks, send replies within Messenger's rules (the 24-hour window and message tags), and fetch
   posts and insights.
3. Reuse the inbox, analysis, automations (comment to DM) and the scheduler; add `facebook` to the
   platform filters, chips and identity colours.
4. e2e: a sandbox Facebook account, like the Instagram sandbox, for F-06/F-07-style flows.

**Done when:** a connected Facebook Page's messages and comments appear in the inbox and
automations work on them, under the same rules as Instagram.

## P5: Copilot write actions, R2 (L)

**Why:** the main differentiator: describe the outcome and Amplychat prepares the actions. For
example: "every time someone asks about pricing, send our price list and tell me if they want a
demo."

**Exists:** the read-only agent, Pydantic AI for the model-and-tool loop, the design in
`docs/agent-architecture.html`, and the `agent_runs` and `agent_steps` tables, with
`agent_approvals` reserved for R2.

**Steps (follow the architecture doc):**
1. **The action gateway:** one service decides every write. It checks permissions, plan limits and
   the platform's rules, and verifies success by reading back.
2. Write tools as thin adapters over existing services: `draft_reply`, `create_automation`,
   `schedule_post`, `set_lead_stage`, `add_knowledge`.
3. Approvals: every write shows exactly what will be sent, scheduled or changed. Copilot mode needs
   approval for each action; Supervised mode allows pre-approved kinds.
4. An audit trail and per-workspace limits (credits, actions per day), visible on the Activity page
   (P1).
5. Evaluations: extend `tests/ai_eval` with write-plan cases before enabling anything. Public
   replies and campaigns stay approval-only until the evaluations and real usage justify more.

**Done when:** a user can ask for an automation in plain language, review it, approve it, and see
it run, with every step in the audit trail.

## P6: Email, Outlook first, then Gmail (L)

**Why:** many leads arrive by email. One customer history across Instagram, WhatsApp and email is
worth more than a separate AI email writer.

**Constraints to verify first:**
- **Microsoft 365 / Outlook:** Microsoft Graph with delegated `Mail.Read` and `Mail.Send`. App
  publisher verification is needed for multi-tenant apps; we don't expect a paid audit.
- **Gmail:** reading mail uses Google's **restricted** scopes. Production use of restricted scopes
  requires Google's OAuth verification **and an annual third-party security assessment (CASA),
  which is paid.** Budget for it before starting Gmail.

**Steps:**
1. Add an `email` channel through `PlatformAdapter`: OAuth connect, incremental sync (Graph delta
   queries), threads mapped to conversations, and outbound replies.
2. Reuse the analysis (intent, sentiment, lead score), summaries, suggestions and the knowledge base
   for drafted replies. Start with **drafts for approval**; automatic replies only through explicit
   rules, after P5's gateway exists.
3. Matching a customer across channels by email or phone: only on exact, verified identifiers, and
   always reversible by the user.
4. Leads (P2) and trends (P3) include email automatically once it's a channel.
5. Gmail second, after the security assessment is budgeted and passed.

**Done when:** a connected Outlook mailbox's threads appear in the inbox with analysis and drafted
replies, and leads from email show in the Leads view.

## P7: More channels, in this order

Each one is a new `PlatformAdapter`, implementing only what its official API supports.

1. **YouTube comments (M).** The YouTube Data API lists comments and allows replies under OAuth and
   quota. It fits the comments product: analysis, needs-reply and drafted replies. Check the
   current quota and verification requirements first.
2. **Google Business Profile reviews (M).** Read reviews and post owner replies, which suits local
   businesses. API access needs Google's approval; apply early.
3. **Telegram (M).** The Bot API is free and simple, and good for support and FAQ bots for
   businesses that run Telegram communities.
4. **Threads (M), optional.** It uses the same Meta stack; publishing and reply management. Add it
   if target customers ask for it.

## Not planned (revisit only with a concrete reason)

| Item | Why not now |
|---|---|
| Follow to DM, Share to DM | No generally available webhook for new followers or story shares (Oct 2026); even Manychat's follow trigger is an unreliable beta |
| Follow-gating | Against Meta's Spam Community Standard; our nudge never gates (`services/automations/nudge.py`) |
| SMS | DLT registration and per-message cost in India; low fit |
| TikTok | Its official APIs centre on posting; DMs and comment replies, our core, aren't broadly available to general apps. Re-check if that changes. |
| LinkedIn | The community management API needs approval as a LinkedIn partner. |
| X | API access is paid per tier. |
| Reddit | Commercial API use is restricted; listening-only might be possible later. |
| Pinterest, Snapchat | They don't fit a DMs-and-comments product. |
| Separate products (Webhook Guardian, AgentWatch, DocFlow and others) | They would split the effort. Their useful parts are already in P1 and P5. |

## Engineering rules for every item

- **Backend with every feature:** API, tests and the generated client together; no mock-only UI
  (the owner's rule).
- **Expand-only migrations,** tenant filtering on every query, and idempotency for every external
  side effect.
- **Store structured analysis results in Postgres.** Add retrieval or vector search only when a
  feature truly needs to search large text.
- **Pages fill the width** and are responsive at any size (the owner's rule, 2026-10-14). New pages
  follow DESIGN_SYSTEM.md and the UI programme's primitives.
- **Ask Amplychat gets a read tool** for every new data source, so the agent stays the single
  place to ask questions.
