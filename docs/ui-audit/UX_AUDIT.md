# Social Hood v2 web app: UX and visual-hierarchy audit

Covers brief sections 2 (UI inventory), 21 (visual hierarchy) and 22 (UX quality, terminology, copy).
This audit is read-only: no code was changed.

- **Scope:** `apps/web` on `feature/ui-audit` at `99f67be`. That covers every route under
  `app/(app)`, `app/(marketing)` and `app/(auth)`, plus every component in `components/*`.
- **Method:**
  1. I read every screen's source and the shared copy in `lib/copy.ts`, `lib/*/format.ts` and
     `lib/inbox/format.ts`.
  2. I compared it with the spec (§3 flows F-01…F-19, §4 UX-SH, UX-INB, UX-SCR, UX-COPY and
     UX-A11Y), with `docs/CONFLICTS.md` (C-048, C-051, C-063, C-065, C-066, C-067), with the
     product guide and with the six mockups in `design/*/screen.png`.
  3. To check the visual hierarchy, I ran the isolated e2e stack:
     - ports 3100 and 8100, with its own database `socialhood_e2e_uxaudit` and Valkey db 7;
     - a sandbox Instagram account, seeded DMs, comments, one FAQ and one automation, and the
       fake AI;
     - a temporary, uncommitted Playwright script took 38 screenshots at 1440×900 (desktop) and
       390×844 (phone).

  Afterwards the stack was stopped, the database dropped and the script deleted. The screenshots
  were kept outside the repository. Findings marked *(seen)* were confirmed on screen; the rest
  come from code.
- **Priorities:**
  - **P0**: broken or unusable.
  - **P1**: a major UX problem.
  - **P2**: polish that users will notice.
  - **P3**: minor.

  There are **no P0 findings**: every core flow works.
- **Owner decisions:** some findings touch decisions the owner approved. Each one names the
  decision (for example "revisits C-063"), so it is the owner's call, not a defect report against
  the agreement.
- **Not covered here:** accessibility (beyond what affects hierarchy) and performance. Other
  audit sections cover them.

---

## Contents

1. [Summary: top findings](#1-summary-top-findings)
2. [UI inventory](#2-ui-inventory)
3. [Visual hierarchy, screen by screen](#3-visual-hierarchy-screen-by-screen)
4. [UX quality review](#4-ux-quality-review)
5. [Terminology table](#5-terminology-table)
6. [Copy and tone consistency](#6-copy-and-tone-consistency)
7. [Findings: UX (UX-001…)](#7-findings-ux)
8. [Findings: visual hierarchy (VH-001…)](#8-findings-visual-hierarchy)
9. [Suggested order of work](#9-suggested-order-of-work)
10. [What already works well](#10-what-already-works-well)

---

## 1. Summary: top findings

| ID | P | Finding |
|---|---|---|
| UX-001 | P1 | The sidebar's **Comments badge** counts comments that need a reply, but no screen lists or filters them. The badge leads to a dead end. |
| UX-002 | P1 | On a scheduled post, **"Save as draft" unschedules it** without asking, and it is the first button in the action bar. |
| UX-003 | P1 | **Edits to a scheduled post are silently lost** when the user leaves through the sidebar or breadcrumb. Settings has a leave guard; the composer does not. |
| UX-004 | P1 | App banners (credits used up, reconnect, payment failed, trial ending) **push the inbox and the Ask page below the fold**, because those frames are sized to `100dvh`. |
| UX-005 | P1 | Stale copy in the automation editor says AI replies "start working when Knowledge arrives in Social Hood". Knowledge already exists. |
| VH-001 | P1 | On phones, **Home is wider than the screen** (it renders 499 px wide on a 390 px viewport). *(seen)* |
| VH-002 | P1 | On phones the **thread header hides who you are talking to**: the name truncates to nothing behind the window chip and the AI pill. *(seen)* |
| UX-006/007 | P2 | AI and automation labelling is inconsistent: "AI Assisted" appears on fixed-text automation messages, and "Auto:" (automation) sits next to "AI Auto" (AI mode). |
| UX-008 | P2 | One action, adding the missing answer, has four names: **Train AI, Teach AI, Add to knowledge, Add answer**. |
| VH-003 | P2 | The **brand gradient is used for every "primary" button**, so many screens show 3 to 7 equally loud buttons. |

All 38 UX findings are in §7 and all 17 visual-hierarchy findings in §8.

---

## 2. UI inventory

The tree lists every route, the major surfaces on each, and every dialog, sheet, popover and
menu reachable from them. Role limits are noted as `[owner/admin]`.

```text
Root layout (app/layout.tsx): Clerk provider, tooltips, Sonner toasts (bottom right)
│
├── Public site (app/(marketing)): SiteHeader (logo, Features · How it works · Pricing · FAQ,
│   │   Sign in / Start free or Open app, phone MobileMenu) and SiteFooter (legal links, support)
│   ├── /                  Landing: Hero (Start free, See how it works), InboxPreview, Features,
│   │                      HowItWorks, Platforms, Trust, Pricing (Free / Pro / Max "Coming soon",
│   │                      "How AI credits work"), Faq, FinalCta
│   ├── /privacy  /terms  /refunds      LegalPage
│   ├── /data-deletion     "Delete your data" how-to, Check status form, status result
│   │                      (Request received / Deleting / Data deleted / Still deleting / Not found)
│   ├── /unsubscribe?token Unsubscribing… → You're unsubscribed / This link doesn't work /
│   │                      This link is incomplete / That didn't work (Try again)
│   └── /og.png, robots, sitemap, manifest (no UI)
│
├── Auth (app/(auth)): logo, then Clerk widgets
│   ├── /sign-in           Clerk SignIn → /app
│   └── /sign-up           Clerk SignUp → /app
│
├── /dev/tokens            Design-token page (internal, dev only)
│
└── Signed in (app/(app)): ApiProvider (global 402 → UpgradeDialog); route error boundary
    │                      (full-page "This didn't load" + Try again)
    ├── /app               Resolver: skeleton → last workspace (inbox, or home with no account);
    │                      "No workspace" empty state (Contact support); full-page error on /v1/me
    │
    └── /w/[slug]          Workspace layout: "Workspace not found" (Go to your workspace)
        │
        ├── APP SHELL (components/shell)
        │   ├── Sidebar (≥768 px; collapses below 1024 px, or 1280 px on Inbox; Ctrl/⌘ [)
        │   │   ├── Workspace menu: logo, "Social Hood" + plan badge, workspace name
        │   │   │   └── Dropdown: Workspaces (switch), Workspace settings
        │   │   ├── Ask Social Hood card (Ctrl/⌘ K) → Ask panel
        │   │   ├── Home | ENGAGE: Inbox (unread badge), Comments (needs-reply badge)
        │   │   │   | GROW [owner/admin]: Schedule, Automations, Knowledge
        │   │   ├── Notifications → popover (360 px): Mark all read, GetAlertsCard
        │   │   │   ("Get alerts on your phone"), list or "No notifications"
        │   │   ├── Settings (→ /settings/connections) · Help (mailto) · Collapse
        │   │   ├── AI credits card (meter, Upgrade → /settings/billing) [owner/admin]
        │   │   ├── "Reconnecting…" pill (event stream down > 5 s)
        │   │   └── Account card (Clerk UserButton menu, name, email)
        │   ├── Phone top bar (<768 px): logo tile, page title, Ask (sparkles), Menu
        │   │   └── Left drawer: the expanded sidebar
        │   ├── BannerSlot (above page content): Payment failed (Manage billing) [owner],
        │   │   Trial ending (View billing / Keep Pro, dismissible) [owner],
        │   │   Reconnect @x (Reconnect), AI credits used up (Upgrade)
        │   ├── Ask panel (sheet, 420 px; full screen on phones): New thread, Threads menu,
        │   │   Open the Ask page, Close, conversation (see Ask)
        │   ├── UpgradeDialog (any 402, "Upgrade for Auto"; see Billing)
        │   └── Service worker registrar, push sign-out cleanup (no UI)
        │
        ├── /home              Home (components/home)
        │   ├── Header: greeting, channels line, period, "n channels connected" pill,
        │   │   7 days | 30 days | Custom (→ Custom period popover: From, To, Apply), Refresh
        │   ├── "Couldn't refresh" warning strip (Try again)
        │   ├── Get set up checklist (4 steps, first open step expanded, Dismiss)
        │   ├── Account health (needs reconnect / error; Open Connections)
        │   ├── Metric tiles: Needs reply (→ inbox?view=needs_reply, Attention), Messages
        │   │   today, Handled by AI, Median first response (Fast)
        │   ├── Sentiment · Most commented (View all, → post) · What customers asked about
        │   ├── Knowledge-gap banner: View thread, Train AI (→ SourceSheet FAQ), Open Knowledge
        │   └── Live priority queue: rows (Review & Send / Open chat), Open Inbox (n)
        │
        ├── /inbox, /inbox/[id]   Inbox (components/inbox, components/ai)
        │   ├── List pane: platform segments (All, Instagram, WhatsApp), "Inbox",
        │   │   Chats | Scheduled, search, account select, view chips (All, Unread, Needs reply,
        │   │   Needs you, Leads, AI handled, More ▾ → Archived)
        │   │   ├── Rows: avatar + platform badge, name, time, You:/AI:/Auto: preview,
        │   │   │   unread dot, badges (Needs you, Complaint, Closing in…, Negative, Lead n/100,
        │   │   │   AI Auto)
        │   │   ├── States: skeleton rows, error, "All caught up" (Show all), "No conversations
        │   │   │   yet", "Connect an account" (no live accounts)
        │   │   └── Scheduled tab: cards (time, status, Edit → Edit scheduled message dialog,
        │   │       Cancel → confirm popover "Cancel message"), "No scheduled messages"
        │   ├── Thread pane: "Pick a conversation" (nothing selected)
        │   │   ├── Header: back (phones), avatar, name, window chip, Needs you chip (md+),
        │   │   │   handle · platform · linked account, AI mode menu ("AI: Suggest" → Account
        │   │   │   default / Off / Suggest / Auto (Pro) → AutoConfirmDialog or UpgradeDialog;
        │   │   │   "AI paused" + Resume), Schedule (md+), Details toggle, More menu (Archive /
        │   │   │   Unarchive, Mark unread, Open in Instagram/WhatsApp, Copy link)
        │   │   ├── Message log: date separators, bubbles (customer, you, AI, automation,
        │   │   │   native app, sending, failed with Retry / Choose template / Reconnect / Copy
        │   │   │   text / Discard), system notes, reactions, quick replies, attachments,
        │   │   │   "AI Assisted" meta + DecisionInfo popover ("Why the AI sent this", Should
        │   │   │   not have sent / Undo), analysis chips + Correct the AI popover
        │   │   ├── Scheduled chip ("1 scheduled · Today 18:30" → Scheduled tab)
        │   │   ├── Escalation banner ("AI didn't reply: …")
        │   │   ├── Draft bar: generating shimmer / "AI draft: …" (Draft again, Insert, Send,
        │   │   │   Dismiss, From: chips, Check this) / "Not in your knowledge" (Write reply,
        │   │   │   Add to knowledge → SourceSheet) / "Editing suggestion" chip
        │   │   └── Composer: attachment tray, text box, Attach, Emoji popover, Heart (IG) or
        │   │       Sticker (WA), AI Polish (+ Undo), Schedule popover (date, time, Schedule,
        │   │       Upgrade on 402), Send; window notices; blocked states (Reconnect, Choose
        │   │       template → TemplatePicker dialog "Send a template")
        │   └── Context panel (inline ≥1280 px, sheet below): Customer (Open in…, follows,
        │       customer since, linked account, lead score, Needs you / AI paused notes),
        │       Latest message (Teach AI → SourceSheet, intent/sentiment/priority, topics,
        │       Correct the AI), Summary (Next step, Refresh / Summarize)
        │
        ├── /comments           Posts grid (account select, cards, Show more posts; No posts yet
        │                       / Connect Instagram)
        └── /comments/[postId]  Post detail: "‹ Comments", title "Photo from {date}"
            ├── Left: Post card (caption More/Less, Open in Instagram, Likes, Comments,
            │   sentiment, "AI analysis is off … Turn it on"), Summary (Summarize / Refresh),
            │   Topics, Performance (age select, figures, Reconnect for insights, comparison)
            └── Comments: filter chips (All, Positive, Neutral, Negative, Questions, Buying
                signals, Spam, Hidden), rows (Reply / DM or View DM / Hide / Unhide / Delete
                [owner/admin] → "Delete this comment?" alert), inline composer (Send reply /
                Send DM), "prepared reply" notice from Ask
        │
        ├── /automations [owner/admin]        Automations list
        │   ├── Header: New automation → TemplateGallery dialog (category chips, cards with
        │   │   Use template, Start from blank) → "Which account?" step
        │   ├── Figures strip (Active, Runs, DMs sent, Waiting for a DM)
        │   ├── Search, Account, Status, Trigger, Sort selects
        │   ├── Account groups → rows (checkbox on hover, drag handle, Active switch, name,
        │   │   trigger, keyword chips, action badge, trend, last run, queue badge, ⋯ menu:
        │   │   Duplicate, Pause/Resume/Activate, Move up/down, Delete → confirm alert)
        │   ├── Bulk bar (n selected, Pause, Clear selection)
        │   ├── Empty: "Reply automatically" + 3 template cards + Browse all templates
        │   └── AgentDraftDialog ("Automation from Ask Social Hood", Open in editor)
        ├── /automations/new   Same page with the gallery open
        └── /automations/[id]  Editor: breadcrumb "Automations /", inline name, status pill,
            Saved / Saving… / Not saved (Retry), Activate | Pause, ⋯ (Duplicate, Delete → alert)
            ├── Queue banner (DMs waiting, Change order menu)
            ├── Steps: When (account, trigger), On these posts (All / Selected / Next post,
            │   post grid), Keywords (chips, match mode, overlap warning), Then (public reply
            │   variations, A message | AI reply (Pro), Tap first, DM builder: Insert field
            │   menu, image, link buttons; Follow nudge), Settings (summary + Edit: cooldown,
            │   run window, order when busy, disclosure)
            └── Side panel tabs: Preview (sample names), Test (match tester), Runs (result
                filter, rows → conversation), Stats
        │
        ├── /schedule [owner/admin]   Schedule
        │   ├── Header: "Times in {zone}", Add to queue, New post
        │   ├── Toolbar: Month | Week | List, ‹ range ›, Today, account avatars, Show ▾
        │   │   (Scheduled, Drafts, Published, Failed; Scheduled DMs, Free queue times),
        │   │   "Drafts and queue" (below 1440 px → right sheet)
        │   ├── Views: Week (drag, slots, DM chips), Month (+n more), List (tabs, bulk:
        │   │   Shift times dialog, Unschedule, Delete → alert), Agenda (phones)
        │   ├── Rail: Unscheduled drafts (drag; Show all drafts), Published in the last 24 h,
        │   │   Queue (Next free time, Posting times), Edit posting times → Posting times sheet,
        │   │   Hashtag groups → dialog (create, edit, inline delete confirm)
        │   ├── Post card menu: Move to… / Schedule for… dialog, Add to queue, Open, View on
        │   │   Instagram, Unschedule, Duplicate, Delete → "Delete this post?" alert
        │   └── Empty: "Plan your posts" (New post); agenda "Nothing planned for these days"
        ├── /schedule/new      Creates a draft and opens the composer
        └── /schedule/[id]     Post composer: breadcrumb "Schedule /", "Post", status pill,
            save state, ⋯ (Duplicate, Delete → alert), StatusBanner (Publishing / Published /
            Partly published / didn't publish → Edit and retry)
            ├── Accounts, Media (Add from device, Media library dialog, tray: reorder, Crop
            │   dialog, Remove), Caption (Write with AI popover, Suggest hashtags, Insert hashtag
            │   group menu → Manage hashtag groups link, per-account captions), First comment,
            │   Automation (Add comment automation → template + account dialog), When (Pick a
            │   time | Add to queue)
            ├── Checklist (Fix → field), sticky action bar (Save draft / Save as draft,
            │   Publish now → "Publish now?" alert, Schedule / Add to queue / Update schedule,
            │   "why disabled" lines)
            └── Preview tabs: Feed, Reel, Grid
        │
        ├── /knowledge [owner/admin]   Knowledge
        │   ├── Header: Add knowledge ▾ (FAQ, Note, Web page, File) → SourceSheet (create / edit)
        │   ├── Questions the AI couldn't answer (Add answer → SourceSheet, Dismiss, Show all)
        │   ├── Brand voice (form on first visit; then summary + Edit)
        │   ├── Sources table (status, characters, Edit, Delete → alert) + Knowledge used meter
        │   └── Test your knowledge (question, Ask, answer card or "Not in your knowledge")
        │
        ├── /ask                Ask Social Hood page: thread history (New thread, groups,
        │                       Run history → Settings › Agent), conversation (Welcome +
        │                       suggested questions, runs with steps, answers, citations,
        │                       action cards → Open, follow-up chips, Copy, credits), composer
        │                       (Ask / Stop), "Jump to latest", out-of-credits notice + Upgrade
        │
        └── /settings           Tabs: Connections · AI Rules & Takeover · Workspace ·
            │                   Notifications · Billing [owner/admin] · Agent; each tab:
            │                   breadcrumb, eyebrow label, title, description
            ├── /connections    Connect Instagram (OAuth redirect → ?instagram= nonce → toast),
            │                   Connect WhatsApp (Meta Embedded Signup popup), Add sandbox account
            │                   (dev); search; All · Connected · Disconnected · Sandboxes;
            │                   account cards (AI replies select, AI analysis, Hide spam
            │                   comments, Reconnect, Retry, Disconnect → alert, Disconnect and
            │                   delete data / Remove → typed-confirm dialog, "Deleting…");
            │                   AutoConfirmDialog
            ├── /ai             AI replies by account (Off | Suggest | Auto, Upgrade for Auto),
            │                   Human takeover, Escalation (built-in list, phrase chips),
            │                   SaveBar (Reset, Save); read-only card for agents
            ├── /workspace      General information (name, URL, timezone, reply language,
            │                   disclosure + preview), At a glance, SaveBar, Danger zone →
            │                   Delete workspace dialog (typed name) [owner]
            ├── /notifications  Email (Weekly digest), Push (InstallPrompt, PushSetup states:
            │                   checking / iPhone not installed / unsupported / unavailable /
            │                   blocked / off / on; Send me: 4 switches), status-only SaveBar
            ├── /billing        Plan hero (Start 7-day trial | Upgrade to Pro, Manage billing /
            │   [owner/admin]   Update payment method → Dodo portal, Resume, Cancel plan / trial
            │                   → alert), CheckoutReturn notice, Resource quotas & usage,
            │                   Compare plans (cards with trial CTA), Payment history;
            │                   agents redirected to Notifications
            └── /agent          Ask Social Hood header + AI credits, Capabilities & permissions
                                (read-only tiles, "Coming later"), Run history (search, All /
                                Answered / Action needed / Failed, pages, row → run detail sheet)
```

**Overlay count:** about 40 distinct dialogs, sheets and popovers. The most-used are the Ask panel,
UpgradeDialog, AutoConfirmDialog, SourceSheet (opened from 4 screens), the TemplateGallery and the
typed-confirm dialogs.

---

## 3. Visual hierarchy, screen by screen

Each screen is reviewed for:

- its primary action
- its secondary actions and navigation
- how it shows information, warnings, errors and metadata
- competing emphasis

The verdict links to the findings in §8 (VH) and §7 (UX).

### 3.1 App shell (sidebar, phone top bar, banners)

- **Primary action:** nothing competes inside the nav. The Ask card (brand-soft panel) and the
  credits card's gradient **Upgrade** are the two loudest items in the sidebar. For a paying user
  under 80 % the Upgrade button is hidden, which is right (C-048).
- **Navigation:** clear. The active item has a raised background and a 2 px brand bar, and the
  groups are labelled. The badges use the brand gradient: Inbox counts unread, Comments counts
  needs-reply. Both look identical but mean different things, and the Comments one leads nowhere
  (UX-001).
- **Information:** the "Reconnecting…" pill is well judged. The phone top bar shows only a
  gradient tile with no wordmark (`MobileNav.tsx:25`), so the brand is never named on phones.
- **Banners:** tone and wording are good and there is one action each. They sit *above* page
  content without the content shrinking, which breaks the full-height Inbox and Ask (UX-004).
- **Verdict:** good. See UX-001, UX-004, UX-014 and VH-016.

### 3.2 Home *(seen at 1440 and 390)*

- **Primary action:** unclear. The gradient appears on:
  - the checklist step button;
  - Train AI;
  - up to five **Review & Send** buttons in the priority queue;
  - the sidebar's Upgrade.

  The mockup gives **Review & Send** the primary role, and that is right, but here it competes
  with four other gradient buttons (VH-003).
- **Secondary actions:** View all, Open Inbox (n), the chevron on the Needs reply tile, View
  thread and Open chat. They are consistent text links and outline buttons.
- **Information:**
  - The metric tiles read well: label, 2xl figure, hint, rule badges.
  - "Attention" (amber) and "Fast" (green) are restrained.
  - "Messages today" sits under a 7- or 30-day period header, but the tile is always today.
    Its hint gives the period count, which is acceptable.
- **Competing emphasis:**
  - A **completed** checklist ("4 of 4 done", all struck through) keeps the most valuable spot
    on the page and pushes the metrics below the fold on laptops (VH-010).
  - The range control wraps "30 / days" onto two lines (VH-008).
  - The gap banner has an amber border and the account-health card has another amber border,
    so two warning-framed cards can stack.
- **Phones:** the page overflows sideways because the card grid has no `min-w-0` (VH-001).
- **Verdict:** needs work. See VH-001, VH-003, VH-008, VH-010, UX-008 and UX-026.

### 3.3 Inbox: list pane *(seen)*

- **Primary action:** opening the next conversation. The rows are clear: name, time,
  preview, unread dot and a 3 px brand bar on the selected row.
- **Secondary actions and filters:**
  - The platform segment's active "All" is a **solid brand fill**, the strongest colour in the
    pane, for a filter that rarely changes.
  - The view chips overflow the 320 px pane with no fade or arrow. At 1440 px "Leads",
    "AI handled" and "More" are cut off, and "Needs you" is half visible (VH-009).
  - The chips carry no counts, even though Home and the sidebar know them (UX-019).
- **Metadata:** each row can show up to four badges in four colours: Needs you (red), Complaint
  (red), Lead 72/100 (brand), AI Auto (green). Green "AI Auto" reads as a positive status rather
  than a mode (VH-009). The "Auto:" preview prefix is ambiguous (UX-007).
- **Verdict:** good structure; the filter row needs attention.

### 3.4 Inbox: thread, draft bar, composer *(seen at 1440 and 390)*

- **Primary action:** sending a reply. In Suggest mode the **draft bar's Send** (gradient) is the
  primary action, and the composer's Send turns gradient as soon as there is text. Two primary
  Sends can then be stacked 60 px apart, each sending something different (VH-004).
- **Header:**
  - The name is the only element that shrinks. The window chip, AI pill, schedule button, panel
    toggle and More menu are all `shrink-0`.
  - At 1440 px with the panel open the name shows as "Sandbox cu…". At 390 px it disappears and
    the window chip overlaps the handle line (VH-002).
  - The "Needs you" chip is hidden below 768 px (`ThreadHeader.tsx:69`), so the most important
    state disappears exactly where space is tight.
- **Messages:**
  - Bubbles are clean. The meta row under each bubble carries time, ticks and "AI Assisted".
  - Failed bubbles have their reason and actions always visible, which is good.
  - The analysis chips (intent, sentiment, priority, pencil) under the latest customer message
    duplicate the context panel when it is open.
- **Composer:**
  - The toolbar holds Attach, Emoji, Heart, AI Polish (outlined brand) and Schedule.
  - AI Polish is the only outlined, coloured control, so it reads as more important than Attach
    or Schedule, which is acceptable.
  - The heart sends instantly (UX-010).
- **Phones:** the draft bar takes about 160 px of an 844 px screen, wrapping Send onto its own
  line. With the header and composer, the conversation keeps about 50 % of the height.
- **Verdict:** needs work on phones. See VH-002, VH-004, UX-006, UX-007 and UX-010.

### 3.5 Inbox: context panel *(seen)*

- **Hierarchy:**
  - Three sections with uppercase micro labels: Customer, Latest message, Summary.
  - The customer card leads with a large name and a "Doesn't follow you" pill.
  - The lead score bar is clear.
  - "Teach AI" and "Open in Instagram" are small brand text links in the section headers. They
    are easy to miss, but that suits secondary actions.
  - "Correct the AI" and the pencil in the thread do the same thing with two different labels.
- **Summary:** "Summarize" is a full-width secondary button, the biggest control in the panel.
  It is fine when there is no summary; once there is one it becomes "Refresh" and stays at full
  width. A smaller ghost button would do.
- **Verdict:** good.

### 3.6 Comments grid *(seen)*

- **Primary action:** none. The cards are links, but nothing on them says which post needs
  attention: there is no caption, no needs-reply count, and "No spam" repeats on every card
  (VH-014).
- **Information:** the date and count are clear, and the 6 px sentiment bar works once
  comments are analysed.
- **Verdict:** needs work. See UX-001 and VH-014.

### 3.7 Post detail *(seen)*

- **Primary action:** replying to comments. The row actions (Reply, DM, Hide, Delete) are quiet
  ghost buttons, which is right for a list.
- **Structure:**
  - The left column stacks four cards: Post, Summary, Topics, Performance.
  - Below 1024 px they come **before** the comment list, so on phones you scroll past analysis
    to reach the work (VH-012).
- **Heading styles:**
  - On one screen the headings mix three styles: the page h1 "Photo from Today", uppercase micro
    labels (Summary, Topics, Performance) and a text-base bold "Comments" (VH-016).
  - The title "Photo from Today" does not identify the post; the caption is lower down (UX-037).
- **Verdict:** acceptable on desktop, needs work on phones.

### 3.8 Automations list *(seen)*

- **Primary action:** **New automation** (gradient, top right). Clear.
- **Information:**
  - The figures strip matches the Home tiles.
  - Rows show the switch, name, trigger, keyword chips, action badge, trend and last run.
  - The status shows as a "Draft" pill or as text ("Starts 1 Oct").
  - Active or Paused shows only through the switch, which is quiet but acceptable.
- **Empty state:** three template cards, each with a gradient **Use template**, plus the header's
  gradient New automation: four primaries (VH-003).
- **Verdict:** good.

### 3.9 Template gallery dialog *(seen)*

- Six cards, each with a **gradient Use template**, plus Start from blank (secondary). Every card
  shouts. The Pro badge on two cards is small and does not change the button (UX-022).
- **Verdict:** needs work. See VH-003 and UX-022.

### 3.10 Automation editor *(seen)*

- **Primary action:** **Activate** (gradient), or **Pause** (secondary) when active. Clear.
  The status pill, "Saved" and Activate sit together; that is good.
- **Steps:**
  - The timeline nodes and dashed active line work well.
  - The uppercase micro labels (WHEN, KEYWORDS, THEN, SETTINGS) are quiet; the bold field labels
    carry the hierarchy.
- **Side panel:** below 1280 px the Preview / Test / Runs / Stats panel is rendered **above** the
  steps, so on a laptop the first thing seen is a preview (VH-015, per spec UX-SCR-03).
- **Verdict:** good.

### 3.11 Schedule *(seen at 1440 and 390)*

- **Primary action:** **New post** (gradient), with Add to queue as secondary. Clear on desktop.
- **Information:**
  - The week grid is quiet, which is right.
  - The rail's uppercase micro labels are consistent with the rest of the app.
  - Hashtag groups is a ghost link at the bottom of the rail, and below 1440 px it lives inside
    "Drafts and queue" (UX-013).
- **Empty states:**
  - Desktop: a "Plan your posts" empty card *above* an empty calendar.
  - Phones: "Plan your posts" **and** "Nothing planned for these days", so three gradient
    **New post** buttons are on screen (VH-013).
- **Verdict:** good on desktop, needs work on phones.

### 3.12 Post composer *(seen)*

- **Primary action:** **Schedule** (gradient, right of the sticky bar), disabled with a reason
  line, which is good.
  - Save draft (ghost) and Publish now (secondary) sit at the left.
  - For a scheduled post the leftmost button becomes **"Save as draft"**, a destructive
    unschedule styled as the quietest button (UX-002).
- **Information:**
  - The checklist with Fix links is excellent.
  - Section cards repeat a title and a field label ("Caption" / "Caption", "First comment
    (optional)" / "Comment").
  - The h1 "Post" says nothing about the post (UX-037).
- **Competing emphasis:** none serious; the preview column is quiet.
- **Verdict:** good. See UX-002, UX-003 and UX-024.

### 3.13 Knowledge *(seen)*

- **Primary action:** **Add knowledge** (gradient, header). On a first visit, though, the page
  shows:
  - first, the full brand-voice form (7 fields and a Save button);
  - then Sources, with a second gradient **Add knowledge** in its empty state;
  - then the gaps card, where each row has a gradient **Add answer**;
  - and the Test box's **Ask** button.

  Up to four primaries, and the knowledge sources themselves are under the fold (VH-011).
- **Information:**
  - The status chips (Processing, Ready, Failed) and the usage meter are clear.
  - Sources truncate titles hard ("Do you shi…" at 1440 px); the table has spare width.
- **Verdict:** needs work. See VH-011 and UX-012.

### 3.14 Ask Social Hood (panel and page) *(seen)*

- **Primary action:** the question box, which is focused on open. The suggested questions are
  quiet outline rows, which is good. The header icons (New thread, Threads, Expand, Close) are
  icon-only with labels.
- **Information:** the welcome copy is long (four lines) for a side panel. "Can prepare a reply
  for you to finish" is the key promise and is buried in the middle.
- **Action cards:**
  - Each card has a secondary **Open** button.
  - The reassurance "Nothing is sent until you do" is in a tooltip only (UX-033).
- **Verdict:** good.

### 3.15 Settings: shared frame *(seen)*

- Every tab shows the page name four times: the underlined tab, the breadcrumb "Settings ›
  Connections", the eyebrow ("CHANNELS") and a 3xl h1 (VH-005).
- The h1 is larger than the h1 on every other app page (2xl).
- The cards are rounded-2xl where the rest of the app uses rounded-xl (VH-016).
- **Revisits C-066**, which put the breadcrumb in to match the mockups.

### 3.16 Settings: Connections *(seen at 1440 and 390)*

- **Primary action:** **Connect Instagram** (gradient). Connect WhatsApp is secondary and the
  sandbox action is ghost. Good.
- **Account cards:** on a healthy, connected card the loudest elements are the **two red text
  buttons** (Disconnect, plus Disconnect and delete data or Remove) (VH-006).
- **AI inner panel:** clear. Auto is shown as "Auto · Pro" but is disabled with no way to
  upgrade (UX-014).
- **Verdict:** needs work. See VH-006 and UX-020.

### 3.17 Settings: AI Rules and Takeover *(seen)*

- **Hierarchy:** the two-column layout reads well.
  - The per-account mode toggle is clear.
  - "Upgrade for Auto" is a quiet link, which is good.
  - The six built-in rules show as green check tiles. The tiles look interactive but are not,
    and they take a lot of room for read-only text.
- **Save bar:** "All changes saved" is always present even though account modes save on their
  own (UX-021, VH-017).
- **Verdict:** good.

### 3.18 Settings: Workspace *(seen)*

- **Hierarchy:** clear fields and the "At a glance" summary. The danger zone is well separated
  with a red left border and an outline danger button.
- **Issues:**
  - The sticky save bar covers the disclosure row while you scroll (VH-017).
  - The reply-language hint is unclear (UX-038).
- **Verdict:** good.

### 3.19 Settings: Notifications *(seen)*

- **Hierarchy:** clear; the switches carry their hints. The page has no actions, but it still has
  a sticky save bar reading "All changes saved" (VH-017).
- **Verdict:** good.

### 3.20 Settings: Billing *(seen)*

- **Primary action:** **Start 7-day trial**. It appears **twice** at equal weight: in the plan
  hero and in the Pro plan card (VH-003).
- **Information:**
  - The quota grid is clear.
  - But "Instagram accounts 1/1, 100 %" is painted **danger red**, with "Free includes 1 account
    per platform." in red (VH-007). It is a normal state, not an error.
  - The hero reads "Free [Free]": the plan name and the status badge say the same thing.
- **Verdict:** needs work. See VH-003, VH-007 and UX-017.

### 3.21 Settings: Agent *(seen)*

- The tab is called "Agent" but the page title is "Ask Social Hood" (UX-017).
- Six locked tiles, each saying "Off" and "Coming later", take half the page to describe features
  that don't exist (UX-030).
- The run-history filter wraps "Action / needed" onto two lines (VH-008).
- **Verdict:** needs work.

### 3.22 Upgrade dialog *(seen)*

- **Hierarchy:** clear. The title names the feature, there is one line of benefit and one line
  of price, then Not now, Compare plans and **Start 7-day trial** (gradient).
- **Verdict:** good. For agents only "Not now" remains (UX-035).

### 3.23 Public pages *(landing, data deletion, unsubscribe; seen)*

- **Landing:** one clear primary (Start free) with a secondary (See how it works).
- **Footer:** link capitalisation is mixed (UX-031).
- **Data deletion:** two-level hierarchy, good.
- **Unsubscribe:** clear states. The success state has no undo (UX-034).
- **Auth pages:** the logo is not a link back to the site.
- **Verdict:** good.

---

## 4. UX quality review

This section groups the UX problems by theme. Details and evidence are in §7.

### 4.1 Confusing interactions

- **Save as draft unschedules a scheduled post** without confirmation (UX-002).
- **A single tap on the heart** sends a heart to the customer (UX-010).
- **Opening an Ask action card replaces the conversation's unsent draft** (UX-009).
- **Write with AI and Improve my caption** replace the caption with no undo, while the inbox's
  AI Polish has one (UX-024).
- **Schedule's header "Add to queue"** creates a new, empty post instead of queueing something
  (UX-025).
- **AI Rules mixes two save models on one page:** modes save instantly; takeover and phrases
  need Save (UX-021).

### 4.2 Inconsistent navigation and unnecessary clicks

- **Child pages use three back patterns:**
  - "‹ Comments" (back link)
  - "Automations /" and "Schedule /" (breadcrumb text)
  - "Settings › Billing" (non-link breadcrumb under tabs)

  The inbox's back arrow appears only on phones (UX-016).
- **Links from the composer** ("Set posting times", "Manage hashtag groups") land on the Schedule
  page with nothing open. Below 1440 px you then need "Drafts and queue", then the tool: three
  clicks plus losing your place (UX-013).
- **The inbox's "More" chip** holds a single item, Archived (UX-019).
- **The inbox view and platform filter** are not in the URL. Back, refresh and links from Home
  (when the inbox is already mounted) don't restore or apply them (UX-019).

### 4.3 Unclear actions and labels

- **Generic titles:** the composer's h1 "Post" and post detail's "Photo from {date}" (UX-037).
- **"Save as draft"** really means unschedule (UX-002).
- **"Remove"** on a disconnected account permanently deletes all its data (UX-020).
- **"Add to queue"** in the Schedule header (UX-025).
- **"Settings → AI"** in the Auto confirmation, while the tab is called "AI Rules & Takeover"
  (UX-030).

### 4.4 Terminology across screens

There are seven or more concepts with two to five names each. The full table is in §5; the worst
cases are UX-006, UX-007, UX-008, UX-017 and UX-020.

### 4.5 Destructive actions and confirmations

Coverage is good. Every permanent delete is confirmed:

- comments, automations, posts and knowledge sources: alert dialogs;
- the workspace and account data: typed confirmation;
- scheduled messages: a popover confirm;
- hashtag groups: an inline confirm.

Gaps and inconsistencies:

- **Unconfirmed:** unscheduling a scheduled post via "Save as draft" (UX-002), and the heart
  (UX-010). Archive and Unschedule (the menu item) are reversible and say so, which is fine.
- **Four confirmation patterns and six "cancel" labels:** Cancel, Keep as is, Keep post, Keep
  them, Not now, Keep {plan}. The scheduled-message trigger itself is a red "Cancel", next to the
  popover's "Cancel message" (UX-029).
- **Destructive buttons come in four styles** (VH-006).

### 4.6 Empty, loading and error states

These are a strength. Every list has skeletons shaped like its rows, and every query has an
ErrorState with Try again. Gaps:

- **The route-level error boundary replaces the whole shell.** The sidebar disappears and the only
  way out is Try again or browser Back (UX-011).
- **Knowledge's test box "Not in your knowledge"** gives no Add answer (UX-012).
- **The Comments badge** has no matching view (UX-001).
- **The connections empty state** offers only Instagram (UX-032).
- **The Automations list** says nothing about needing Instagram (UX-023).

### 4.7 Feedback

- Toasts are specific ("Scheduled for Today 18:30", "Moved to drafts. It keeps its time."),
  which is good.
- **Connection errors are transient toasts.** Some are three sentences of instructions, for
  example `wa_no_phone_number` (UX-015).
- **The permanent "All changes saved" bar** on pages that autosave is feedback without an event
  (UX-021).
- **Thanks. Auto learns from this.** claims learning that the product doesn't promise (UX-030).

### 4.8 Dead ends

- Comments badge to the posts grid (UX-001).
- Test box "Not in your knowledge" (UX-012).
- The error boundary without a shell (UX-011).
- Connections' "Auto · Pro" disabled option with no upgrade path (UX-014).
- The unsubscribe success page with no way to undo (UX-034).
- The Agent settings page's six "Coming later" tiles (UX-030).

### 4.9 Flows that cross screens

| Flow | Path | Verdict |
|---|---|---|
| **Ask action cards** | Ask → Open → inbox schedule popover, comment reply box, or automation draft dialog | Works, and the prefill is clearly labelled ("Prepared by Ask Social Hood…"). Problems: it overwrites any unsent draft (UX-009); the panel closes with no way back to the answer except reopening it (acceptable); reassurance is only in a tooltip (UX-033). |
| **Teach AI / Train AI / Add to knowledge / Add answer** | Home banner, inbox panel, draft bar, Knowledge gaps → SourceSheet ("Add an FAQ") | Same sheet, same result, four labels (UX-008). Saving from the inbox offers "Draft again", which is good; from Home nothing follows. |
| **Upgrade** | 402 → dialog; Auto (AI page, thread menu) → dialog; sidebar Upgrade, credits banner, knowledge meter → Billing page; Connections Auto → disabled | Three behaviours for one intent (UX-014). |
| **Connect Instagram** | Connections → Instagram OAuth → back with `?instagram=` → toast | Works. Errors such as "not a professional account" vanish in a toast (UX-015). The checklist's "Choose an AI mode" also lands on Connections. |
| **Connect WhatsApp** | Connections → Meta popup → toast | Same as Instagram: long multi-step errors in toasts (UX-015). |
| **Marketing → Pro** | "Start free, then try Pro" → sign up → Home | The trial intent is lost; the user must find Settings → Billing (UX-027). |
| **Reply-window reminder** | Push → `/inbox/{id}?schedule=1` → popover open | Good. |
| **Needs reply** | Home tile → `/inbox?view=needs_reply` | Works on first load only (UX-019). |

---

## 5. Terminology table

"Where" gives the screen, and file:line for the less obvious cases.

| Concept | Variants found (where) | Recommended | Notes |
|---|---|---|---|
| Conversation the AI handed to a person | **Needs you** (chips, row badge, header, Home, push: `lib/copy.ts:562`); **Escalated** (automation run result, `lib/automations/format.ts:68`); **Handed to you:** (Home queue, `PriorityQueue.tsx:50`); "The AI handed this over" (row tooltip, `lib/inbox/format.ts:107`); "flags the conversation for you" (`ThenStep.tsx:842`); "comes to you" (`AiSettingsPage.tsx:77,296,322`); "AI didn't reply" (banner); **Escalation** (settings card) | **Needs you** for the state. The verb is "hand to you" ("The AI handed this to you: refund"). In Settings keep "Escalation phrases", explained as "send to Needs you". | The run result "Escalated" should read "Handed to you". |
| AI mode "Auto" | **Auto** (mode); **AI: Auto** (header pill); **AI Auto** (row badge, `lib/inbox/format.ts:117`); **Auto mode** (upgrade dialog, plan cards "AI Auto mode") | **Auto** (mode name); "AI: Auto" in the pill; row badge **Auto replies** | Never use "Auto" for automations (next row). |
| Message sent by an automation | **Auto:** preview prefix (`lib/inbox/format.ts:30`); **AI Assisted** (bubble meta, `MessageBubble.tsx:231`); "Sent by an automation: X" (tooltip) | **Automation:** prefix (or a zap icon); bubble meta **Automation · {name}** | Spec UX-INB-04/06 said "Auto:" and "Automation · {name}"; "Auto:" now clashes with the Auto mode. |
| Message sent by the AI on its own | **AI:** prefix; **AI Assisted** (meta); "Sent by AI: an auto reply" (tooltip); "Why the AI sent this" | **Sent by AI** (meta; spec UX-INB-06) | "Assisted" understates a fully automatic send. Revisits C-063. |
| AI-handled metric and view | **Handled by AI** (Home tile); **AI handled** (inbox chip) | **Handled by AI** in both | Small, but one is a filter for the other. |
| The AI's proposed reply | **AI draft** (bar); **Suggested reply** (aria-label, AutoConfirm copy "leaves a suggested reply"); **suggestion** ("Editing suggestion", "Dismiss suggestion"); **AI suggestions** (plan cards); "drafts left"; **Draft again** (button) / "Write a different draft" (title) | **AI draft** everywhere users see it ("Editing AI draft", "Dismiss draft"); the mode stays **Suggest** | The spec used "Suggested reply"; C-063 moved the UI to "AI draft". The aria-labels and dialogs still say "suggestion". |
| Adding a missing answer | **Train AI** (Home, `KnowledgeGapBanner.tsx:68`); **Teach AI** (panel, `DetailsPanel.tsx:152`); **Add to knowledge** (draft bar, `SuggestionCard.tsx:100`); **Add answer** (Knowledge, `KnowledgeGapsCard.tsx:72`); sheet title **Add an FAQ** | **Add answer** (verb + object, says what you will do); sheet title **Add an answer** | "Train" and "Teach" suggest model training, which doesn't happen. |
| Knowledge gap | **Questions the AI couldn't answer** (Home, Knowledge); **Not in your knowledge** (draft bar, test box); "not in knowledge" (escalation label); "knowledge gap" (product guide) | Title **Unanswered questions**; inline **Not in your knowledge** | The current title is long and appears in three places. |
| Removing an account | **Disconnect** (keeps data); **Disconnect and delete data**; **Remove** (permanently deletes a disconnected or sandbox account and all its data, `DeleteAccountDialog.tsx:63`) | **Disconnect** (keeps data) and **Delete account and data** (connected or not; the dialog says it disconnects first) | "Remove" understates a permanent purge. Revisits C-067's labels. |
| Conversation | **conversation**; **chat** ("Open chat", "Chats" tab); **thread** ("View thread" on Home; Ask uses "thread" for its own conversations) | **Conversation** for the inbox ("Open conversation", tab **Conversations**); keep **thread** for Ask only | "View thread" on Home opens an inbox conversation, while "New thread" in Ask means something else. |
| Context panel | **Details** (toggle aria-label); "customer panel" (its title tooltip, `ThreadHeader.tsx:130`); context panel (docs) | **Details** | |
| Private reply to a comment | **DM** (buttons); "Private reply to {name}" (label); "Private reply (a DM)" (Ask) | **DM** (explained once in the composer hint, as now) | Fine; keep the aria-label in line. |
| AI usage unit | **AI credits** (sidebar, billing, banners); **credits** (Ask "3 credits"); "1 AI credit" (Polish tooltip); "Uses AI credits" | **AI credits** on first mention per screen; "credits" after that | The mockups' "ops" and "queries" were already dropped (C-065, C-066). |
| AI mode setting label | **AI replies** (Connections card, AI page card title); **AI mode** (thread menu aria, Ask); "AI in this conversation" (menu label) | **AI replies** (setting) with values Off / Suggest / Auto | |
| Settings tab vs page | Tab **Agent** / page **Ask Social Hood**; tab **Billing** / page **Billing & Usage**; "Settings → AI" vs tab **AI Rules & Takeover** | Tab and title identical: **Ask Social Hood**, **Billing & usage**, **AI rules & takeover** (sentence case) | "Agent" is also a member role (`AppSidebar.tsx:51`). |
| Cancelled status | **Canceled** (Schedule, scheduled messages: `lib/schedule/format.ts:35`, `ScheduledList.tsx:39,78`); **Cancelled** (composer pill `lib/publishing/rules.ts:242`, `StatusBanner.tsx:117`, billing) | **Cancelled** (the UI uses UK spelling elsewhere: "analysed", "colour") | The same post is "Canceled" in the calendar and "Cancelled" in its composer. |
| Not yet available | **Coming soon** (Max plan); **Coming later** (Agent tiles, Platforms) | **Coming soon**, or remove (UX-030) | |
| Selected posts | **Selected posts** (editor); **Chosen posts** (Ask draft dialog, `AgentDraftDialog.tsx:23`) | **Selected posts** | |

---

## 6. Copy and tone consistency

The voice is plain, specific and friendly, as UX-COPY-01 asks, and error messages mostly follow
"what happened + what to do". The deviations:

### 6.1 Sentence case

These labels use Title Case or "&", unlike the rest of the app:

- **Review & Send** (`components/home/rules.ts:29`)
- **Open Inbox** (`PriorityQueue.tsx:107`)
- **AI Polish** (`Composer.tsx:373`)
- **AI Rules & Takeover** (`sections.ts:10`)
- **Billing & Usage** (`BillingPage.tsx:158`)
- **Resource quotas & usage** (`BillingPage.tsx:359`)
- **Capabilities & permissions** (`AgentSettingsPage.tsx`)
- Footer: **Privacy Policy, Terms of Service, Refund Policy** next to **Data deletion**
  (`lib/marketing/site.ts:63-66`)

Recommend sentence case and "and": "Review and send", "Open inbox", "AI polish" (or "Polish"),
"AI rules and takeover", "Billing and usage", "Privacy policy".

### 6.2 Spelling

The UI mixes UK and US spelling:

| UK | US |
|---|---|
| analysed, colour, Summarise (Ask follow-ups, `lib/agent/format.ts:95-96`), cancelled (billing, composer) | **Summarize** (`SummarySection.tsx:97`, `PostSummaryCard.tsx:91`), **Canceled** (Schedule, scheduled messages), "Upload canceled" |

`PostSummaryCard.tsx:19` mixes both in one sentence: "no **analysed** comments to
**summarize**". Pick UK; the product serves India-first businesses and already uses "colour" and
"analysed".

### 6.3 Button verbs

Mostly good: Send, Schedule, Connect Instagram, Add answer, Publish now. Exceptions:

- **Open** on Ask action cards; the aria-label is fine, but the visible label says nothing.
- **Show** (the Schedule filter, `SchedulePage.tsx:485`).
- **Insert** (the draft bar; fine with its tooltip).
- **Save as draft** (means unschedule).

### 6.4 Cancel labels

There are six variants for "don't do it": Cancel, Keep as is, Keep post, Keep them, Not now and
Keep {plan}. Recommend **Cancel** in all dialogs, except a "Keep …" label when the main action is
itself called "Cancel …" (billing).

### 6.5 Error message style

- Mostly correct, without apologies or exclamation marks.
- The ErrorState heading "This didn't load" is generic but acceptable.
- The generic connect failure says "Instagram didn't respond. Try again." even for errors that are
  not Instagram's (`lib/copy.ts:278-280`).
- API detail strings for 4xx are shown verbatim (`lib/copy.ts:11-13`), so their tone depends on
  the backend.

### 6.6 Punctuation

- Banners: some end with a full stop (credits) and some don't (reconnect, payment failed, trial
  ending: `lib/copy.ts:292-294, 546-547, 553-556`).
- Toasts: the same action has two toasts, "Post deleted." (`PostComposer.tsx:536`) and
  "Post deleted" (`SchedulePage.tsx:611`). "Draft saved." has one; most toasts don't.
- Recommendation: full stops in body text and banners; none in short toast titles.

### 6.7 Unclear sentences

- "Customer's language answers in whatever they wrote in." (`settings/workspace/page.tsx:250`)
- "The AI answers from your knowledge base, so AI replies start working when Knowledge arrives in
  Social Hood." (stale; UX-005)
- "Writes arrive in a later release." (roadmap language in product UI)

---

## 7. Findings: UX

Each finding gives:

- **Priority**
- **Problem**
- **Evidence:** the screen, plus file:line under `apps/web/src`
- **Files:** the files affected
- **Recommendation**

### UX-001 · P1 · The Comments badge leads to a dead end

- **Problem:** the sidebar's Comments badge counts comments from the last 7 days that are not
  spam, hidden, deleted or replied to (C-048). The Comments page shows a posts grid with no
  needs-reply count per post, no "Needs reply" or "Unanswered" filter, and no list across posts.
  The user sees "8", opens Comments, and cannot find the 8. *(seen: badge 8, four identical
  cards)*
- **Evidence:**
  - the badge: `components/shell/AppShell.tsx:84`, `components/shell/AppSidebar.tsx:85`;
  - the grid cards: `components/comments/PostCard.tsx:44-63`;
  - the filters: `lib/comments/format.ts:7-16`;
  - the API's `PostSummary` and `CommentStats` have no needs-reply field
    (`packages/api-client/schema.d.ts:3765-3778, 5129-5141`).
- **Files:** `CommentsPage.tsx`, `PostCard.tsx`, `CommentsColumn.tsx`, `lib/comments/format.ts`,
  plus the API (posts list and comment filter).
- **Recommendation:**
  1. Add a **Needs reply** filter chip (first after All) on post detail.
  2. Add an "n need a reply" pill on post cards, and sort or filter the grid by it.
  3. Better still, give Comments a cross-post "Needs reply" list as its default view and make the
     badge open it.

  Needs an API change, which is the owner's decision.

### UX-002 · P1 · "Save as draft" silently unschedules a scheduled post

- **Problem:** on a scheduled post the action bar reads Save as draft (ghost, first), Publish
  now, Update schedule. "Save as draft" unschedules the post and puts it back in drafts. There is
  no confirmation; only a toast follows. A user who wants to "save my edits" picks the first,
  quietest button and the post stops being scheduled.
- **Evidence:** `components/composer/PostComposer.tsx:451-465` (unschedule then put),
  `PostComposer.tsx:706-708` (label "Save as draft").
- **Files:** `components/composer/PostComposer.tsx`.
- **Recommendation:**
  - For scheduled posts, drop the button from the bar.
  - Put **Unschedule** in the ⋯ menu, with a confirmation ("It won't publish until you schedule
    it again").
  - Keep **Update schedule** as the save.

### UX-003 · P1 · Edits to a scheduled post are lost when leaving inside the app

- **Problem:** scheduled posts don't autosave (C-044); the header says "Unsaved changes". The
  draft hook flushes only drafts when the composer unmounts, and its `beforeunload` covers only
  reload and close. Clicking the sidebar, the "Schedule /" breadcrumb or a notification
  discards the edits without asking. Settings already has a link-capture leave guard; the
  composer doesn't use it. Brand voice (Knowledge) and the comment composers have the same gap.
- **Evidence:**
  - `components/composer/use-post-draft.ts:176-181` (flushes only when `autosave`), `:185-194` (beforeunload);
  - `PostComposer.tsx:835-836` ("Unsaved changes");
  - the guard that exists: `components/settings/SaveBar.tsx:16-44`.
- **Files:** `use-post-draft.ts`, `PostComposer.tsx`, `knowledge/BrandVoiceCard.tsx`.
- **Recommendation:** call `useLeaveWarning(dirty && !autosave)` in the composer, and when
  dirty in BrandVoiceForm.

### UX-004 · P1 · App banners push the inbox composer and the Ask box below the fold

- **Problem:** the inbox frame is `h-[calc(100dvh-32px)]` plus a 16 px top margin, and Ask is the
  same. App banners render *above* them inside `<main>` without the frame shrinking. When any
  banner shows (AI credits used up, Reconnect @x, Payment failed, Trial ending), the page
  scrolls. The composer and the Ask question box sit below the visible area by the banners'
  height (about 50 px each), and the sticky sidebar no longer lines up.
- **Evidence:** `components/shell/AppShell.tsx:106-108`, `components/inbox/InboxShell.tsx:97`,
  `components/agent/AskPage.tsx:28`. (From code; not reproduced, because the sandbox showed no
  banner.)
- **Files:** `AppShell.tsx`, `InboxShell.tsx`, `AskPage.tsx`, `BannerSlot.tsx`.
- **Recommendation:** make `<main>` a `flex h-dvh flex-col` and let the inbox and Ask frames
  `flex-1 min-h-0` instead of computing from `100dvh`. Alternatively, on full-height pages,
  render banners as a compact strip inside the frame.

### UX-005 · P1 · Stale copy says AI-reply automations don't work yet

- **Problem:** the AI reply step of the automation editor says: "The AI answers from your
  knowledge base, so AI replies start working when Knowledge arrives in Social Hood." Knowledge
  shipped in P5. This tells Pro users the feature doesn't work.
- **Evidence:** `components/automations/steps/ThenStep.tsx:841`.
- **Files:** `ThenStep.tsx`.
- **Recommendation:** "The AI answers from your knowledge. When the answer isn't there, it sends
  nothing and moves the conversation to Needs you." Add a link to Knowledge.

### UX-006 · P2 · "AI Assisted" mislabels automation and auto-reply messages

- **Problem:** every `automation` message, including fixed-text automations with no AI, shows
  "AI Assisted" under the bubble. AI auto replies, which the AI wrote and sent alone, show the
  same "AI Assisted". The team can't tell an automation from an AI auto reply at a glance, and a
  fixed message is credited to the AI.
- **Evidence:** `components/inbox/MessageBubble.tsx:105-113, 224-234`. The spec says "Sent by AI"
  and "Automation · {name}" (UX-INB-06). Revisits C-063.
- **Files:** `MessageBubble.tsx`.
- **Recommendation:**
  - `ai_auto` → "Sent by AI" with the info button.
  - `automation` → "Automation · {name}" with a zap icon, with "AI" added only when the action was
    an AI reply.

### UX-007 · P2 · "Auto" means two things in the inbox list

- **Problem:** in the list, "Auto:" before a preview means *an automation sent this*. The badge
  "AI Auto" means *the AI mode is Auto*, and the header pill says "AI: Auto". A user reasonably
  reads "Auto: Here's the link" as an AI auto reply.
- **Evidence:** `lib/inbox/format.ts:24-37` (prefix), `:116-118` (badge);
  `components/ai/AiModeControl.tsx:149`.
- **Files:** `lib/inbox/format.ts`.
- **Recommendation:** use the prefix "Automation:" (or the zap icon) and the badge "Auto replies".
  See §5.

### UX-008 · P2 · Four names for "add the missing answer to knowledge"

- **Problem:** the same action opens the same sheet from four places with four labels, and the
  sheet itself says "Add an FAQ". "Train" and "Teach" suggest model training.
- **Evidence:**
  - Home: `components/home/KnowledgeGapBanner.tsx:68` ("Train AI")
  - inbox panel: `components/inbox/DetailsPanel.tsx:152` ("Teach AI")
  - draft bar: `components/ai/SuggestionCard.tsx:100` ("Add to knowledge")
  - Knowledge: `components/knowledge/KnowledgeGapsCard.tsx:72` ("Add answer")
  - the sheet: `components/knowledge/SourceSheet.tsx:57` ("Add an FAQ")
- **Files:** the five above.
- **Recommendation:** use **Add answer** everywhere. When the sheet opens with a prefilled
  question, title it "Add an answer" with the line "Customers asked this. Your answer is used
  from now on."

### UX-009 · P2 · Ask's "Open" replaces an unsent composer draft

- **Problem:** opening a "Scheduled message" action card writes the prepared text into that
  conversation's composer draft, overwriting anything the member had typed there, with no
  warning or undo.
- **Evidence:** `lib/agent/handoff.ts:51-54`.
- **Files:** `lib/agent/handoff.ts`, `components/inbox/ThreadView.tsx`.
- **Recommendation:** if a draft exists, keep it. Put the prepared text in the schedule popover's
  own field, or ask "Replace your draft?". At least offer Undo in a toast.

### UX-010 · P2 · One tap sends a heart to the customer

- **Problem:** the Instagram composer's heart icon sends a heart sticker immediately. It sits
  between Emoji and AI Polish, and on touch screens it is easy to hit. There is no confirmation or
  undo, and you can't unsend a heart from Social Hood.
- **Evidence:** `components/inbox/Composer.tsx:204, 338-341`.
- **Files:** `Composer.tsx`.
- **Recommendation:** move the heart into the emoji popover ("Send a heart" at the top), or show
  an Undo toast and send after 3 s.

### UX-011 · P2 · A page crash removes the whole app shell

- **Problem:** the only error boundary for signed-in pages sits at `app/(app)/error.tsx`, above the
  workspace layout. A render error in any page replaces the sidebar, banners and Ask with a
  full-page "This didn't load", whose only action is Try again. There is no Home link.
- **Evidence:** `app/(app)/error.tsx:6-8`, `components/states/ErrorState.tsx:27`.
- **Files:** add `app/(app)/w/[slug]/error.tsx`; `ErrorState.tsx`.
- **Recommendation:** add an error boundary inside the workspace layout so the shell stays, and
  add "Go to Home" next to Try again.

### UX-012 · P2 · The knowledge test result "Not in your knowledge" is a dead end

- **Problem:** the Test box says "Not in your knowledge. Missing: …" with no action, although this
  is exactly where the user wants to add the answer.
- **Evidence:** `components/knowledge/TestBox.tsx:84-92`.
- **Files:** `TestBox.tsx`, `KnowledgePage.tsx`.
- **Recommendation:** add **Add answer**, opening the FAQ sheet with the tested question
  prefilled.

### UX-013 · P2 · "Set posting times" and "Manage hashtag groups" open nothing

- **Problem:** in the composer, "Set posting times" (queue mode) and "Manage hashtag groups" (the
  caption menu) link to `/schedule`. The page opens with neither tool open. Below 1440 px both
  tools live inside the "Drafts and queue" sheet, so the user needs two more clicks and loses
  the composer.
- **Evidence:**
  - `components/composer/WhenSection.tsx:93-97`;
  - `components/composer/CaptionEditor.tsx:464`;
  - the rail: `components/schedule/ScheduleRail.tsx:157-164`;
  - the drawer button: `components/schedule/SchedulePage.tsx:526-530`.
- **Files:** those above.
- **Recommendation:** open the Posting times sheet and the Hashtag groups dialog in place from
  the composer (both are self-contained), or link with `?panel=posting-times` or `?panel=hashtags`
  and open them on arrival.

### UX-014 · P2 · "Upgrade" behaves three ways

- **Problem:**
  - Some Upgrade controls open the upgrade dialog (any 402, "Upgrade for Auto", the inline
    UpgradeAction).
  - Others navigate to Settings → Billing (the sidebar credits card, the credits banner, the
    knowledge usage meter).
  - On Connections, Auto is a disabled "Auto · Pro" option with no path at all.

  The same word leads to different places, and the Billing page is read-only for admins.
- **Evidence:**
  - billing page: `components/shell/UsageCard.tsx:102-109`, `components/shell/AppShell.tsx:155`,
    `components/knowledge/SourcesCard.tsx:125`;
  - dialog: `components/ai/AiSettingsPage.tsx:210-217`, `components/billing/UpgradeAction.tsx`;
  - disabled: `components/connections/AccountCard.tsx:166-168`.
- **Files:** those above.
- **Recommendation:** "Upgrade" always opens the upgrade dialog, which already has Compare plans.
  On Connections, picking Auto on Free should open the dialog, as the thread menu and the AI page
  do.

### UX-015 · P2 · Connection errors disappear in toasts

- **Problem:** Instagram and WhatsApp connect failures are toasts that vanish after a few seconds.
  Several are instructions the user has to follow: switch to a professional account, add a phone
  number in WhatsApp Manager, pick one number in Meta's popup.
- **Evidence:**
  - `app/(app)/w/[slug]/settings/connections/page.tsx:297-302`;
  - `components/connections/ConnectWhatsAppButton.tsx:55, 64`;
  - the copy: `lib/copy.ts:179-187, 255-261`.
- **Files:** the connections page and `ConnectWhatsAppButton.tsx`.
- **Recommendation:** show the last connect error as a dismissible inline alert at the top of
  Connections, with Try again. Keep the toast for success.

### UX-016 · P2 · Back navigation differs on every child page

- **Problem:** there are three patterns:
  - post detail: a "‹ Comments" back link;
  - the automation editor and the post composer: a small "Automations /" or "Schedule /" text
    breadcrumb above the title;
  - settings: a non-link "Settings › Billing" breadcrumb under the tabs.

  The inbox thread shows a back arrow only on phones.
- **Evidence:** `components/shell/PageFrame.tsx:23-30`, `components/automations/AutomationEditor.tsx:238-243`,
  `components/composer/PostComposer.tsx:561-566`, `components/settings/SettingsPageHeader.tsx:34-48`.
- **Files:** those above.
- **Recommendation:** one pattern for child pages, the "‹ Parent" link (PageFrame's `back`), used
  by the editor, the composer and post detail. Settings needs no breadcrumb (see VH-005).

### UX-017 · P2 · Settings tab names don't match page titles; "Agent" collides with a role

- **Problem:**
  - The tab "Agent" opens a page titled "Ask Social Hood".
  - "Agent" is also a member role, shown under the user's name in the sidebar.
  - The tab "Billing" opens "Billing & Usage", and the breadcrumb (read from the tab) contradicts
    the h1 under it.
- **Evidence:** `components/settings/sections.ts:10-17`, `components/agent/AgentSettingsPage.tsx:93`,
  `components/billing/BillingPage.tsx:158`, `components/shell/AppSidebar.tsx:51`. *(seen)*
- **Files:** `sections.ts`, `AgentSettingsPage.tsx`, `BillingPage.tsx`.
- **Recommendation:** tabs **Ask Social Hood** and **Billing and usage**, and an h1 equal to the
  tab label. Revisits C-066.

### UX-018 · P2 · The inbox's Scheduled tab ignores the filters shown above it

- **Problem:** on the Scheduled tab the platform segments (All / Instagram / WhatsApp) stay
  visible and selectable. The scheduled list ignores them and shows every message. Choosing
  "WhatsApp" changes nothing.
- **Evidence:** `components/inbox/InboxShell.tsx:268-290`, `components/inbox/ScheduledList.tsx:46-52`.
- **Files:** `InboxShell.tsx`, `ScheduledList.tsx`.
- **Recommendation:** apply the platform and account filter to scheduled messages, or hide the
  strip on that tab.

### UX-019 · P2 · Inbox views: no counts, a one-item "More", state not in the URL

- **Problem:**
  1. The chips (Needs reply, Needs you) show no counts, while Home and the sidebar know them.
  2. "More" opens a menu with a single item, Archived.
  3. The view, platform and search live only in component state. Back, refresh and Copy link lose
     them, and Home's `?view=needs_reply` is read only when the inbox first mounts.
- **Evidence:** `components/inbox/ListHeader.tsx:20-30, 174-195`, `components/inbox/InboxShell.tsx:122-129`.
- **Files:** `ListHeader.tsx`, `InboxShell.tsx`.
- **Recommendation:**
  - Show counts on Needs reply and Needs you; the inbox counts query exists.
  - Make Archived a plain chip at the end.
  - Keep `view` and `platform` in the search params (`router.replace`).

### UX-020 · P2 · Disconnect, Disconnect and delete data, Remove

- **Problem:**
  - Every connected card carries two red actions with near-identical labels.
  - Disconnected and sandbox cards show **Remove**, which permanently deletes all the account's
    conversations, comments, posts and automations. "Remove" reads as "take it off this list".
- **Evidence:** `components/connections/AccountCard.tsx:223-241`,
  `components/connections/DeleteAccountDialog.tsx:54-67`. *(seen)*
- **Files:** `AccountCard.tsx`, `DeleteAccountDialog.tsx`.
- **Recommendation:**
  - Keep **Disconnect** visible (it keeps data).
  - Put **Delete account and data** (one label for both modes) in a ⋯ menu.
  - The typed-confirm dialog stays as it is.

  Revisits C-067's labels.

### UX-021 · P2 · Two save models on one page; a save bar that never saves

- **Problem:**
  - On AI Rules & Takeover, account modes save instantly (with a toast), while takeover and
    phrases wait for Save. The sticky bar reads "All changes saved" even when a mode change
    failed or is pending.
  - On Notifications, everything autosaves but a sticky save bar still says "All changes saved"
    forever.
- **Evidence:** `components/ai/AiSettingsPage.tsx:111-119, 330-339`;
  `components/push/NotificationSettingsPage.tsx:177`; `components/settings/SaveBar.tsx:88-92`.
  Revisits C-066.
- **Files:** `AiSettingsPage.tsx`, `NotificationSettingsPage.tsx`, `SaveBar.tsx`.
- **Recommendation:** on autosave pages, show a transient "Saved" by the control instead of a
  permanent bar. On the AI page, either make takeover and phrases autosave too, or exclude modes
  from the page's "All changes saved" claim.

### UX-022 · P2 · Free users can start Pro templates and find out at activation

- **Problem:** the gallery shows a small "Pro" badge on AI-reply templates, but **Use template**
  works the same for Free workspaces. The draft opens with "Replies with AI are part of Pro. Set
  it up now and activate it after upgrading.", and Activate then opens the upgrade dialog.
- **Evidence:** `components/automations/TemplateGallery.tsx:149-152, 215-223`;
  `components/automations/steps/ThenStep.tsx:821`.
- **Files:** `TemplateGallery.tsx`.
- **Recommendation:** on Free, give Pro cards the label "Try with Pro" and open the upgrade dialog,
  or at least say "You can set it up; it runs on Pro" on the card before creating.

### UX-023 · P2 · Automations are Instagram-only but never say so up front

- **Problem:** with only WhatsApp connected, the list, empty state and gallery all invite you to
  create automations, including the "DM keyword" trigger. Only inside the editor does it say
  "Connect an Instagram account to use automations".
- **Evidence:** `components/automations/AutomationsPage.tsx:151-154, 251-261`;
  `components/automations/steps/WhenStep.tsx:51-53`.
- **Files:** `AutomationsPage.tsx`, `TemplateGallery.tsx`.
- **Recommendation:** with no Instagram account, the list's empty state reads "Automations work on
  Instagram. Connect Instagram". Trigger labels say "Instagram DM keyword" where it matters.

### UX-024 · P2 · AI caption writing replaces the caption with no undo

- **Problem:** "Write caption" and "Improve my caption" replace the caption the user wrote. The
  inbox's AI Polish offers Undo; the composer doesn't.
- **Evidence:** `components/composer/CaptionEditor.tsx:353-360`.
- **Files:** `CaptionEditor.tsx`.
- **Recommendation:** add an Undo action to the success toast, or show the result for Replace or
  Keep before applying.

### UX-025 · P2 · The Schedule header's "Add to queue" creates an empty post

- **Problem:** the secondary header button "Add to queue" doesn't add anything to the queue. It
  creates a new draft and opens the composer in queue mode, which is not what the label says.
- **Evidence:** `components/schedule/SchedulePage.tsx:394-401`.
- **Files:** `SchedulePage.tsx`.
- **Recommendation:** remove it, because the composer's When step already has "Add to queue".
  Or rename it "New post in the queue".

### UX-026 · P3 · Checklist dismissal is permanent, and completion doesn't hide it

- **Problem:** "Dismiss" hides the setup checklist for good, with no confirmation and no way to
  bring it back. Meanwhile a *completed* checklist stays until dismissed (see VH-010).
- **Evidence:** `components/home/Checklist.tsx:66-68`, `components/home/HomeScreen.tsx:57-58, 181-183`.
- **Files:** `Checklist.tsx`, `HomeScreen.tsx`.
- **Recommendation:** auto-hide after all four steps are done (after one "You're set up" view).
  Make Dismiss reversible from the workspace menu ("Show setup checklist").

### UX-027 · P2 · The Pro intent from the pricing page is lost after sign-up

- **Problem:** the Pro card's CTA "Start free, then try Pro" goes to sign-up, then Home. Nothing
  offers the trial; the card's small print says to find Settings → Billing yourself.
- **Evidence:** `components/marketing/Pricing.tsx:70-80`.
- **Files:** `Pricing.tsx`, `lib/resolve.ts`, `HomeScreen.tsx`.
- **Recommendation:** carry `?plan=pro` through sign-up and open the upgrade dialog, or a
  "Start your Pro trial" card on first Home.

### UX-028 · P3 · Two scheduling entry points with two names

- **Problem:** the thread header has a clock, "Schedule a message", shown from 768 px. The
  composer toolbar has a second clock, "Schedule for later". They open the same popover.
- **Evidence:** `components/inbox/ThreadHeader.tsx:115-125`, `components/inbox/Composer.tsx:380-384`.
- **Recommendation:** keep the composer's clock only (it sits next to the text) and name it
  "Schedule message".

### UX-029 · P3 · Inconsistent confirmation patterns and cancel labels

- **Problem:**
  - Confirmations use alert dialogs (most), a popover (cancelling a scheduled message), an inline
    row (deleting a hashtag group) and typed input (account, workspace).
  - The "don't" button says Cancel, Keep as is, Keep post, Keep them, Not now or Keep {plan}.
  - Cancelling a scheduled message starts with a red **Cancel** button, ambiguous next to Edit.
- **Evidence:**
  - `components/inbox/ScheduledList.tsx:144-159, 232-234`;
  - `components/schedule/SchedulePage.tsx:604`;
  - `components/schedule/ListView.tsx:204`;
  - `components/schedule/HashtagGroupsDialog.tsx:95-117`;
  - `components/billing/BillingPage.tsx:314`.
- **Recommendation:**
  - Use alert dialogs for every permanent action; typed confirmation only for account and
    workspace data.
  - The dismiss button is **Cancel** (or "Keep …" only when the action is called "Cancel …").
  - Rename the scheduled-message trigger **Delete**, or **Cancel message**.

### UX-030 · P3 · Stale, inaccurate or roadmap copy

- **Problem:**
  - "for the takeover period in Settings → AI": the tab is "AI Rules & Takeover".
  - "Thanks. Auto learns from this.": nothing promises learning.
  - The Agent page's "Writes arrive in a later release." plus six "Off · Coming later" tiles.
  - "Coming later" vs "Coming soon".
- **Evidence:** `components/ai/AiModeDialogs.tsx:36`, `components/ai/DecisionInfo.tsx:72`,
  `components/agent/AgentSettingsPage.tsx:135, 187`, `components/billing/PlanCards.tsx:84`.
- **Recommendation:**
  - Fix the path to "Settings → AI rules and takeover".
  - "Thanks. This helps us review Auto replies."
  - Collapse the six tiles into one line, "Ask Social Hood can't send or change anything. It only
    prepares drafts for you."

### UX-031 · P3 · Casing, spelling and punctuation drift

- **Problem:** see §6: Title Case labels, UK and US spelling, banners without full stops, two
  versions of the same toast.
- **Evidence:** the file:line references in §6.1, §6.2 and §6.6.
- **Recommendation:** a short copy pass. Add a lint test, beside `lib/copy.test.ts`, that rejects
  "&" in button labels and the US "-ize" words.

### UX-032 · P3 · The connections empty state offers only Instagram

- **Problem:** with no accounts, the empty state (titled "Connect an account", with the Instagram
  glyph) has a single **Connect Instagram** button. WhatsApp-only businesses must notice the
  header button.
- **Evidence:** `app/(app)/w/[slug]/settings/connections/page.tsx:143-158`.
- **Recommendation:** show both Connect buttons in the empty state.

### UX-033 · P3 · Ask: credit cost and safety are only in hints

- **Problem:**
  - One click on a suggested question spends about 2 to 4 AI credits without saying so.
  - Action cards hide "Nothing is sent until you do" in a tooltip and screen-reader text.
- **Evidence:** `components/agent/AskConversation.tsx:313-317`, `components/agent/ActionCardView.tsx:116-129`.
- **Recommendation:** add "Uses AI credits" under the composer (and the remaining count when low).
  Show the card's hint as visible secondary text.

### UX-034 · P3 · Unsubscribe success has no undo

- **Problem:** after unsubscribing, the page says to turn the digest back on in Settings →
  Notifications. It offers only "Open Social Hood" (`/app`), with no undo or direct link.
- **Evidence:** `app/(marketing)/unsubscribe/UnsubscribeResult.tsx:61-69`, `lib/copy.ts:571-572`.
- **Recommendation:** add "Resubscribe" (the same token, if the API allows), or link to
  `/app?next=settings/notifications`.

### UX-035 · P3 · The upgrade dialog for agents offers only "Not now"

- **Problem:** an agent hitting a limit sees the explanation and "Ask an owner…", with a single
  button labelled "Not now", as if there were an option to decline.
- **Evidence:** `components/billing/UpgradeDialog.tsx:95-121`.
- **Recommendation:** label it **OK** (or Close) when no upgrade action is shown.

### UX-036 · P3 · The thread header's "Needs you" chip disappears on phones

- **Problem:** the escalation chip is hidden below 768 px, the size where it matters most because
  the details panel is a sheet you have to open.
- **Evidence:** `components/inbox/ThreadHeader.tsx:68-72`.
- **Recommendation:** show it as a compact red dot or chip on all sizes. With VH-002, move it to
  the second header row.

### UX-037 · P3 · Generic titles don't identify the object

- **Problem:** the post composer's h1 is "Post", whatever the post. Post detail is
  "{Photo|Reel} from {date}", and the caption sits lower in the side card. In browser history and
  tabs they are indistinguishable.
- **Evidence:** `components/composer/PostComposer.tsx:567`, `components/comments/PostDetailPage.tsx:84`.
- **Recommendation:** use the caption's first line, truncated, as the title, falling back to the
  current text. The composer says "New post" for an empty draft.

### UX-038 · P3 · Unclear reply-language hint

- **Problem:** "The language AI replies use. Customer's language answers in whatever they wrote
  in."
- **Evidence:** `app/(app)/w/[slug]/settings/workspace/page.tsx:250`.
- **Recommendation:** "The language AI replies are written in. Choose Customer's language to reply
  in the language the customer used."

---

## 8. Findings: visual hierarchy

### VH-001 · P1 · Home overflows sideways on phones and tablets

- **Problem:** below 1024 px the card row (Sentiment, Most commented, What customers asked about)
  is a grid without columns. Its implicit track takes the min-content width of the longest
  `truncate` caption, so the page renders wider than the viewport: 499 px on a 390 px phone.
  Captions don't truncate and the whole page scrolls sideways. *(seen)*
- **Evidence:** `components/home/HomeScreen.tsx:193` (`grid gap-3 lg:grid-cols-3`),
  `components/home/TopPostsCard.tsx:38, 63`; screenshot m01.
- **Files:** `HomeScreen.tsx`, `TopPostsCard.tsx`.
- **Recommendation:** use `grid-cols-1 lg:grid-cols-3` (Tailwind's `grid-cols-1` is
  `minmax(0,1fr)`) and `min-w-0` on the card sections. Check the other `grid` wrappers the same
  way.

### VH-002 · P1 · The thread header hides the contact's name

- **Problem:** the name is the only shrinkable element; the window chip, AI pill, schedule,
  details and More are fixed width.
  - At 1440 px with the panel open, the name shows as "Sandbox cu…".
  - At 390 px the name is gone entirely, and the window chip overlaps the handle line.

  On phones you can't see who you are replying to. *(seen)*
- **Evidence:** `components/inbox/ThreadHeader.tsx:75-103, 104-162`; screenshots d03 and m04.
- **Files:** `ThreadHeader.tsx`, `AiModeControl.tsx`.
- **Recommendation:**
  - Give the name priority: put the window chip on the second line with the handle.
  - On phones, collapse "AI: Suggest" to a sparkles icon and move Schedule into More.
  - Add `min-w-24` on the name block.

### VH-003 · P2 · The brand gradient is the default for every "primary" button

- **Problem:** there is no `primary` button variant. About 40 call sites add
  `bg-brand-gradient text-white` by hand, so every list item, card and dialog gets one. The
  gradient stops meaning "the next step". Examples *(seen)*:

  | Screen | Gradient buttons at once |
  |---|---|
  | Home | checklist CTA, Train AI, up to 5 × Review & Send, sidebar Upgrade |
  | Template gallery | 6 × Use template |
  | Automations empty state | 3 × Use template + New automation |
  | Knowledge | Add knowledge (header), Add knowledge (empty), n × Add answer, Save, Ask |
  | Billing | 2 × Start 7-day trial |
  | Schedule on phones | 3 × New post |

- **Evidence:**
  - `components/home/PriorityQueue.tsx:64-68`
  - `components/automations/TemplateGallery.tsx:215-223`
  - `components/knowledge/KnowledgeGapsCard.tsx:67`
  - `components/knowledge/SourcesCard.tsx:53, 133`
  - `components/billing/BillingPage.tsx:229-241`
  - `components/billing/PlanCards.tsx:110`
  - `components/schedule/AgendaView.tsx:59`
  - spec §4.1: "One accent, used only for what the business sends and for primary actions."
- **Files:** `components/ui/button.tsx`, plus the call sites.
- **Recommendation:**
  - Add a `variant="primary"` (the gradient) and allow **one per view**.
  - Row and card actions use `secondary` or `outline`. For example, only the first Review & Send
    row, or none, is primary; gallery cards use secondary "Use template".
  - The duplicate trial CTA in the Pro card becomes a text link when the hero already shows it.

### VH-004 · P2 · Two Send buttons; the draft bar dominates on phones

- **Problem:**
  - When the member types while a draft is showing, there are two gradient **Send** buttons
    60 px apart: the draft's and the composer's. They send different text.
  - On phones the bar wraps to three lines plus a Send row, about 160 px.
- **Evidence:** `components/ai/SuggestionCard.tsx:181`, `components/inbox/Composer.tsx:406-422`;
  screenshots d03 and m04.
- **Files:** `SuggestionCard.tsx`, `Composer.tsx`.
- **Recommendation:**
  - When the composer has text, demote the draft's Send to secondary, or collapse the bar to
    "AI draft ready · Insert".
  - On phones, clamp the draft to one line with "More", and put Draft again, Insert and Send on
    one row of icons with labels.

### VH-005 · P2 · Settings names the page four times

- **Problem:** each tab stacks the underlined tab, the breadcrumb "Settings › X", an uppercase
  eyebrow ("CHANNELS", "PLAN & USAGE") and a 2xl/3xl h1. That is about 140 px before content,
  and the h1 is bigger than any other app page's.
- **Evidence:** `app/(app)/w/[slug]/settings/layout.tsx:22-42`,
  `components/settings/SettingsPageHeader.tsx:34-55`; screenshots d21-*. Revisits C-066.
- **Files:** `SettingsPageHeader.tsx`.
- **Recommendation:** drop the breadcrumb (the tabs are the location) and the eyebrow. Keep the
  title at text-2xl, as on PageFrame, and the one-line description.

### VH-006 · P2 · Destructive actions are too loud on healthy cards, and styled four ways

- **Problem:**
  - Every connected account card ends with two red text buttons; on a healthy card they are the
    loudest elements.
  - Across the app destructive buttons use four styles:
    - solid `bg-danger-fill` (most confirmations);
    - soft `variant="destructive"` (Cancel plan, `BillingPage.tsx:315`);
    - outline danger (Delete workspace, `DeleteWorkspace.tsx:100`);
    - ghost red (`AccountCard.tsx`, `DisconnectDialog.tsx:32`).
- **Evidence:** `components/connections/AccountCard.tsx:223-241` *(seen)*; the files above.
- **Recommendation:**
  - Card-level triggers use neutral ghost or ⋯ menu items with red text inside the menu.
  - Confirmation buttons are always solid danger.
  - One `variant="danger"` in `button.tsx`.

### VH-007 · P2 · A full account quota is shown as an error

- **Problem:** Billing paints "Instagram accounts 1 / 1 · 100 %" with a red bar, a red percentage
  and red text "Free includes 1 account per platform." Having your one account connected is the
  normal state. The red teaches users to ignore red. *(seen)*
- **Evidence:** `components/billing/BillingPage.tsx:400-449`; `components/billing/UsageMeter.tsx`
  (`meterLevel`).
- **Recommendation:**
  - Slot-type limits (accounts, active automations) at 100 % show neutral "All used" with Upgrade.
  - Keep warning and danger for consumables (AI credits, scheduled posts this month).
  - Also drop the duplicate "Free" badge next to the plan name "Free" in the hero
    (`BillingPage.tsx:280-285`).

### VH-008 · P2 · Segmented controls wrap their labels

- **Problem:** `ToggleGroupItem` is `flex-1` without `whitespace-nowrap`, so in tight groups the
  labels break: "30 / days" on Home at 1440 px and on phones, and "Action / needed" in Agent's
  run history. *(seen)*
- **Evidence:** `components/ui/toggle-group.tsx:37`, `components/home/RangeControl.tsx:14, 45-58`,
  `components/agent/AgentSettingsPage.tsx` (the run filters).
- **Recommendation:** add `whitespace-nowrap` to the item, and use `flex-none px-3` where the
  group is `w-auto`.

### VH-009 · P2 · Inbox filter chips overflow invisibly; badges compete

- **Problem:**
  - At the 320 px list width the chip row scrolls sideways with no fade or arrow. "Needs you" is
    half cut and "Leads", "AI handled" and "More" are invisible.
  - Each row can carry four colour-coded badges, and the success-green "AI Auto" reads as "good"
    rather than "mode". *(seen)*
- **Evidence:** `components/inbox/ListHeader.tsx:161-196`; `lib/inbox/format.ts:96-120`;
  `components/inbox/ConversationRow.tsx:101-114`; screenshot d02.
- **Recommendation:**
  - Add an edge fade and wrap the chips onto two rows at ≥768 px.
  - Limit rows to two badges (Needs you or signal, then Lead) and show Auto as a small neutral
    icon by the time.

### VH-010 · P2 · A completed checklist keeps the best spot on Home

- **Problem:** "Get set up · 4 of 4 done", with four struck-through rows, keeps a 250 px card
  above the metric tiles until the user dismisses it. On a 900 px laptop the priority queue is
  below the fold. *(seen)*
- **Evidence:** `components/home/Checklist.tsx:52-104`, `components/home/HomeScreen.tsx:181-183`.
- **Recommendation:** when all steps are done, show a one-line "You're all set" for one session,
  then hide it (see UX-026). While incomplete, collapse the done rows into "2 of 4 done".

### VH-011 · P2 · The Knowledge page leads with a form

- **Problem:**
  - On a first visit the brand-voice form (seven fields) sits above Sources, so the knowledge
    itself, the core of the page, starts below the fold.
  - "Add knowledge" appears twice (header and the Sources empty state), and every gap row has a
    gradient **Add answer**.
  - The Sources table truncates titles to about 12 characters at 1440 px ("Do you shi…") even
    though the table has spare width. *(seen)*
- **Evidence:** `components/knowledge/KnowledgePage.tsx:70-97`, `components/knowledge/SourcesCard.tsx:53, 133, 164-171`.
- **Recommendation:**
  - Order the page: gaps (when any), Sources, Brand voice. Collapse brand voice to a summary card
    with "Set up" when empty.
  - Make the gap rows' buttons secondary.
  - Give the Source column more width (`w-1/2`).

### VH-012 · P2 · Post detail buries the comments on phones and tablets

- **Problem:** below 1024 px the left column (post, summary, topics, performance; four cards)
  comes before the comment list, where the work happens.
- **Evidence:** `components/comments/PostDetailPage.tsx:24, 88-103`.
- **Recommendation:** on small screens order the page post (compact), comments, summary, topics
  and performance. Or put Comments and Insights in tabs.

### VH-013 · P2 · The Schedule page stacks empty states

- **Problem:**
  - On desktop, a "Plan your posts" empty card sits above a full, empty week grid.
  - On phones it sits above a second empty state, "Nothing planned for these days", so three
    gradient New post buttons are visible at once. *(seen)*
- **Evidence:** `components/schedule/SchedulePage.tsx:533-543`, `components/schedule/AgendaView.tsx:54-62`.
- **Recommendation:** show one empty state. On desktop put the hint inside the grid; on phones
  keep only the agenda's. The header's New post is the only primary.

### VH-014 · P3 · Comments cards can't be told apart

- **Problem:** cards show a thumbnail, date, count, a sentiment bar and "No spam". The caption is
  screen-reader text only, and "No spam" on every card is noise. With videos and failed
  thumbnails the cards look identical. *(seen)*
- **Evidence:** `components/comments/PostCard.tsx:40-63`.
- **Recommendation:** show the caption's first line (one line, truncated). Show spam only when it
  is above 0, and a needs-reply count when it is above 0 (see UX-001).

### VH-015 · P3 · Automation editor: the panel comes before the steps below 1280 px

- **Problem:** on laptops under 1280 px wide, Preview, Test, Runs and Stats render above the
  steps, so the first screen of the editor is a preview of an empty message. This follows the
  spec (UX-SCR-03).
- **Evidence:** `components/automations/AutomationEditor.tsx:297-315`.
- **Recommendation:** below 1280 px, put the panel *after* the steps, or collapse it into a
  "Preview" button that opens a sheet.

### VH-016 · P3 · Inconsistent heading scale, radii and section labels

- **Problem:**
  - Settings uses an h1 at md:text-3xl and rounded-2xl cards. Other app pages use text-2xl and
    rounded-xl.
  - On post detail, section headings mix uppercase micro labels with a text-base bold "Comments".
  - The phone top bar shows a gradient tile without the "Social Hood" wordmark.
- **Evidence:** `components/settings/SettingsPageHeader.tsx:55`, `components/settings/SettingsCard.tsx:46`,
  `components/comments/PostSummaryCard.tsx:60` vs `components/comments/CommentsColumn.tsx:132`,
  `components/shell/MobileNav.tsx:25`.
- **Recommendation:** one h1 size and one card radius app-wide. Use micro labels for panel
  sections and bold text-base for content blocks, but not on the same level.

### VH-017 · P3 · The sticky save bar is always present and covers content

- **Problem:** on Workspace, AI and Notifications a full-width, shadowed bar reading "All changes
  saved" sits at the bottom of the screen permanently. It overlaps the row being edited
  (screenshot: the disclosure switch) and draws the eye with nothing to do.
- **Evidence:** `components/settings/SaveBar.tsx:69-70`, `components/push/NotificationSettingsPage.tsx:177`.
- **Recommendation:** show the bar only when dirty, saving or failed. When clean, show a small
  "All changes saved" status in the header (see UX-021).

---

## 9. Suggested order of work

1. **Quick fixes, under a day each:**
   - UX-005 (stale copy)
   - VH-001 (`grid-cols-1` and `min-w-0`)
   - VH-008 (`whitespace-nowrap`)
   - UX-030 and UX-031 (copy pass)
   - UX-035
   - UX-038
2. **Data-safety fixes:**
   - UX-002 (unschedule)
   - UX-003 (leave guard)
   - UX-009 (draft overwrite)
   - UX-010 (heart)
3. **Inbox:**
   - VH-002 (header)
   - UX-004 (banner height)
   - VH-004 (two Sends)
   - UX-006 and UX-007 (labels)
   - UX-018 and UX-019 (filters)
   - VH-009
4. **Comments** (UX-001, VH-014, VH-012). Needs an API field, so it is the owner's decision.
5. **System-wide consistency:**
   - VH-003 (a primary variant, one per view)
   - VH-006 (a danger variant)
   - §5 terminology
   - UX-008 (Add answer)
   - UX-014 (Upgrade)
   - UX-016 (back links)
   - VH-005, UX-017 and UX-021 (settings frame; these revisit C-066, so they need the owner's
     approval)

---

## 10. What already works well

These are worth keeping as the patterns other screens copy:

- **Disabled buttons say why.** The composer's "Schedule: Fix the 2 items in the checklist", with
  checklist Fix links that focus the field.
- **Typed confirmations** list what is deleted and what is kept (account data, workspace).
- **Specific, honest feedback:**
  - "Moved to drafts. It keeps its time."
  - "We couldn't confirm this was delivered. Check the chat in Instagram before retrying."
  - "Your reply changed while it was polished, so it was kept."
- **Real-data rules on Home.** "—" with a hint instead of zeros; Attention and Fast are explained
  rules, not scores.
- **Loading states** are skeletons shaped like the real content, with no page spinners.
- **The AI mode control** is a single per-conversation menu with "Account default · Suggest". The
  Auto confirmation lists every escalation rule.
- **Ask's hand-off** ("Prepared by Ask Social Hood. Check the message and time, then schedule.")
  puts the human in control and reuses the screens' own checks.
