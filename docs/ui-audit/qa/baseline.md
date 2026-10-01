# UI-019 baseline: screenshots, axe, keyboard and reduced motion before Wave 0

The state of the app before any UI task merges, for the Wave 0–1 checkpoint (UI-019) and for every
task's before-and-after shots. Nothing here changes the app; issue numbers are from
[UI_AUDIT.md](../UI_AUDIT.md).

## The run

| | |
|---|---|
| Date | 2026-10-01 |
| Code | `develop` at `e330f4a` (UI audit, design system and plan; D-01 to D-17 approved, none implemented). Captured from `feature/ui-qa-shots`, which adds only the tool. |
| Stack | The isolated e2e stack (`scripts/e2e-stack.mjs --serve`): a production build (`next build`, `next start`) on port 3136, the API on 8136, database `socialhood_e2e_qa`, Valkey db 6; sandbox platform, fake AI, Dodo, email and push; Clerk's development instance. |
| Browser | Chromium 1243 (Playwright 1.63.0), dark, device scale factor 1; touch emulation at 375 and 768. Heights 812, 1024, 800, 864. |
| axe | axe-core 4.13.0 through `@axe-core/playwright` 4.13.0; tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`; at 375 and 1280. |
| Tool | `pnpm shots:ui` ([apps/web/scripts/ui-shots/README.md](../../../apps/web/scripts/ui-shots/README.md)). 125 shots in 15 min 9 s; one flaky test (toast-375: the page stayed on the app's loading skeleton, passed on retry). No shot recorded a loading warning. |
| Data | Workspace "QA Shop" (a sandbox Instagram account and its backfill, 4 knowledge sources, an active comment-to-DM automation and a draft, 5 DMs with AI drafts, 4 comments, 3 scheduled posts, a draft post) and "QA Reconnect" (an account that needs reconnecting). |

**Where the images are** (outside the repository, about 49 MB):
`C:\Users\zakau\social-auto\design\ui-qa\baseline\`

- `<screen>-<width>.png`: the 125 screenshots; `shots.json` lists each with its URL and size.
- `axe/`, `axe.json`, `axe-summary.md`: the axe results.
- `keyboard/`: the keyboard pass (`keyboard-pages.json`, `keyboard-overlays.json` and a screenshot at
  stops 1, 2, 8, 20 and every stop flagged as a problem, `*-problem.png`).
- `motion/`: the reduced-motion pass (`motion-reduce.json`, `motion-no-preference.json`).
- `reduced-motion/`: the overlay screens at 375 and 1280 under `prefers-reduced-motion: reduce`
  (`UI_SHOTS_REDUCED_MOTION=1`), with `diff-vs-baseline/index.html` (the tool's comparison).

## Screens

31 screens at four widths plus the phone drawer at 375. Full page unless marked "viewport" (an open
overlay, or the banner over the inbox). A width in **bold** means the page scrolls sideways.

| Screen | What it shows | 375 | 768 | 1280 | 1536 |
|---|---|---|---|---|---|
| home | Greeting, range, checklist (4 of 4 done), metric tiles, sentiment, top posts, the knowledge-gap banner, priority queue | **499**×2784 | 768×2016 | 1280×1390 | 1536×1451 |
| inbox-list | The conversation list with filters, no conversation open | viewport | viewport | viewport | viewport |
| conversation | A DM with its AI draft above the composer; list beside it from 768, details panel at 1536 | viewport | viewport | viewport | viewport |
| comments | The posts grid | viewport | viewport | viewport | viewport |
| post-comments | A post, its summary and its comments | 375×1763 | 768×1311 | 1280×1314 | 1536×1562 |
| automations | 7-day stats, one active automation, one draft | viewport | viewport | viewport | viewport |
| automation-editor | The active automation: steps, preview | 375×3876 | 768×3040 | 1280×2435 | 1536×2387 |
| template-gallery | Automations › New automation (dialog) | viewport | viewport | viewport | viewport |
| schedule-week | Week view (the agenda below 768) | viewport | viewport | viewport | viewport |
| schedule-month | Month view (the agenda below 768) | viewport | viewport | 1280×871 | 1536×871 |
| schedule-list | List view | viewport | viewport | viewport | viewport |
| composer | A draft post with a photo and caption: accounts, media, caption, first comment, when, checklist, preview | 375×2864 | 768×2833 | 1280×1935 | 1536×1943 |
| knowledge | Questions the AI couldn't answer, brand voice, sources, the test box | 375×1904 | 768×1594 | 1280×1452 | 1536×1356 |
| ask-panel | The Ask Social Hood panel over Home, no thread | viewport | viewport | viewport | viewport |
| ask-page | The Ask page, no thread | viewport | viewport | viewport | viewport |
| settings-connections | The connected sandbox account | 375×954 | viewport | viewport | viewport |
| settings-ai | AI mode per account (Auto locked on Free), takeover, escalation | 375×1686 | 768×1254 | 1280×874 | viewport |
| settings-workspace | Name, time zone, members, danger zone | 375×1806 | 768×1554 | 1280×1245 | 1536×1245 |
| settings-notifications | Email and push preferences | 375×1241 | 768×1061 | 1280×863 | viewport |
| settings-billing | Free plan, usage meters, plan cards, payment history | 375×3459 | 768×2213 | 1280×1793 | 1536×1761 |
| settings-agent | Ask Social Hood settings and run history | 375×1898 | 768×1255 | 1280×1143 | 1536×1143 |
| upgrade-dialog | Opened by Settings › AI's "Upgrade for Auto": the trial offer | viewport | viewport | viewport | viewport |
| menu-open | An automation row's ⋯ menu | viewport | viewport | viewport | viewport |
| dialog-open | Settings › Connections, "Disconnect @…?" | viewport | viewport | viewport | viewport |
| phone-drawer | The navigation drawer over Home | viewport | – | – | – |
| toast | Settings › AI after switching the AI mode ("@…: AI Off") | viewport | viewport | viewport | viewport |
| banner | Home of "QA Reconnect" with the reconnect banner | **499**×2322 | 768×1740 | 1280×1236 | 1536×1236 |
| banner-inbox | That workspace's conversation under the banner | viewport | viewport | viewport | viewport |
| landing | `/`, signed out, every section revealed | 375×16600 | 768×13988 | 1280×12168 | 1536×12168 |
| privacy | `/privacy`, signed out | 375×12458 | 768×8116 | 1280×7082 | 1536×7082 |
| data-deletion | `/data-deletion`, signed out | 375×2174 | 768×1568 | 1280×1354 | 1536×1354 |
| sign-in | Clerk's sign-in, signed out | viewport | viewport | viewport | viewport |

### What the shots show of known issues

These match the audit; the checkpoint should see them change as their tasks merge.

- **Home scrolls sideways at 375**: home-375 and banner-375 are 499 px wide (UI-ISS-018).
- **The thread header hides the contact at 375 and 768**: the name collapses to "@c…" and the window
  chip overlaps the AI pill (conversation, banner-inbox; UI-ISS-019).
- **A banner pushes the inbox composer below the fold** at every width (banner-inbox; UI-ISS-020,
  which the audit could only infer from code: the sandbox can now show it).
- **The toast sits bottom right at every width**, over the page at 375 (toast; UI-ISS-043).
- **The composer's ⋯ drops to its own row at 375** (composer-375; UI-ISS-115).
- **Scrolling rows hide options**: the inbox view chips end at "Needs you" at every width
  ("Leads", "AI handled", "More" off-screen) and the settings tabs cut at "Workspac…" at 375
  (UI-ISS-058).
- **Overlays sit on a blurred page** (template-gallery, upgrade-dialog, dialog-open; UI-ISS-031).
- **Two looks for destructive actions**: the account card's red "Remove" next to "Disconnect"
  (settings-connections; UI-ISS-080).
- **The automation editor shows the preview above the steps below 1280** (UI-ISS-113, D-16).

New, not in the audit:

- **The Disconnect confirmation is brand blue, not red** (dialog-open). The action carries both
  `bg-primary` (the AlertDialogAction's default variant) and the call site's `bg-danger-fill`; the
  computed background is `#567FF8` with white text (3.63:1). The audit counted the 8
  AlertDialogActions with `bg-danger-fill` as solid red (COMPONENT_AUDIT CMP-003); at least this
  one isn't. Belongs with UI-ISS-009 and UI-ISS-005 (UI-011, UI-013).
- **Knowledge's source names truncate to 2–4 characters at every width** ("Sh…", "Price …", "Ca…"):
  the Sources table's name column collapses (knowledge-*). Belongs with UI-ISS-051 (tables).

## axe

63 results (32 screens at 375, 31 at 1280): **14 violations of 3 rules on 14 screen-widths, 29
nodes**. axe left **1,089 nodes "needs review"** (1,052 of them colour contrast).

| Rule | Impact | Screen × width | Nodes | What and where | Issue |
|---|---|---:|---:|---|---|
| `color-contrast` | serious | 10 | 16 | see below | UI-ISS-005, 006, 007 |
| `aria-hidden-focus` | serious | 2 | 8 | with an automation's ⋯ menu open, the page behind is `aria-hidden` (Radix's modal menu) but its controls stay focusable: the top bar or sidebar, the page header, the filters and the list | new (UI-013's area) |
| `target-size` | serious | 2 | 5 | the calendar cards' "Actions for …" buttons (`icon-xs`, under 24 px with too little spacing) in the week and month views at 1280 | UI-ISS-011 (the audit found 2.5.8 met everywhere; these fail it) |

The contrast nodes:

- "All", the inbox's active platform segment, white on solid brand (3.63:1): inbox-list at 375 and
  1280, conversation and banner-inbox at 1280 (UI-ISS-005).
- "Instagram" in the thread header, `text-instagram` (2.73:1): conversation and banner-inbox at 1280
  (UI-ISS-006; hidden at 375).
- Billing: the "Coming soon" badge on `white/10`, and the Max card's "For teams and high volume" and
  "a month" under `opacity-80`, at 375 and 1280 (UI-ISS-007).
- The Disconnect confirmation, white on `#567FF8`, at 375 and 1280 (UI-ISS-005, UI-ISS-009; see
  above).
- Sign-in: Clerk's "Secured by" footer at 375 and 1280 (Clerk's own text; the audit didn't cover
  Clerk's forms; UI-ISS-095 owns the Clerk appearance).

By screen (from `axe-summary.md`; "to review" = nodes axe couldn't decide):

| Screen | 375 px | 1280 px |
|---|---|---|
| home | 0 · 11 to review | 0 · 37 to review |
| inbox-list | **1** (color-contrast 1) · 8 | **1** (color-contrast 1) · 41 |
| conversation | 0 · 5 | **1** (color-contrast 2) · 44 |
| comments | 0 · 0 | 0 · 27 |
| post-comments | 0 · 3 | 0 · 30 |
| automations | 0 · 1 | 0 · 28 |
| automation-editor | 0 · 5 | 0 · 32 |
| template-gallery | 0 · 7 | 0 · 37 |
| schedule-week | 0 · 1 | **1** (target-size 2) · 28 |
| schedule-month | 0 · 1 | **1** (target-size 3) · 28 |
| schedule-list | 0 · 1 | 0 · 28 |
| composer | 0 · 3 | 0 · 31 |
| knowledge | 0 · 2 | 0 · 29 |
| ask-panel | 0 · 14 | 0 · 41 |
| ask-page | 0 · 0 | 0 · 28 |
| settings-connections | 0 · 4 | 0 · 28 |
| settings-ai | 0 · 3 | 0 · 27 |
| settings-workspace | 0 · 3 | 0 · 27 |
| settings-notifications | 0 · 3 | 0 · 27 |
| settings-billing | **1** (color-contrast 3) · 9 | **1** (color-contrast 3) · 33 |
| settings-agent | 0 · 3 | 0 · 27 |
| upgrade-dialog | 0 · 9 | 0 · 35 |
| menu-open | **1** (aria-hidden-focus 4) · 3 | **1** (aria-hidden-focus 4) · 30 |
| dialog-open | **1** (color-contrast 1) · 5 | **1** (color-contrast 1) · 32 |
| phone-drawer | 0 · 34 | – |
| toast | 0 · 4 | 0 · 27 |
| banner | 0 · 3 | 0 · 27 |
| banner-inbox | 0 · 5 | **1** (color-contrast 2) · 36 |
| landing | 0 · 41 | 0 · 43 |
| privacy | 0 · 1 | 0 · 1 |
| data-deletion | 0 · 2 | 0 · 2 |
| sign-in | **1** (color-contrast 1) · 2 | **1** (color-contrast 1) · 2 |

**Read axe with its blind spots.** axe's reasons for the 1,052 undecided contrast nodes:
background image 559, gradient 171, short text 156, overlap 113, partly obscured 49, other 4. The
sidebar has a background image, so axe checks none of its text: the group labels that fail at
3.64:1 (UI-ISS-007) appear only under "needs review", which is why every 1280 screen has about 27.
axe also skips placeholders (UI-ISS-008, 3.41:1). So the checkpoint's "fewer `color-contrast`
nodes" has to read both columns, and the token fixes (UI-001, UI-002, UI-018) may move nodes from
"needs review" to passing, not out of the violations. The audit's best-practice rules
(`page-has-heading-one`, `landmark-unique`, `region`) are outside these tags, and
`scrollable-region-focusable` (UI-ISS-064) didn't fire because the seeded week has posts.

## Keyboard (1280)

Tab from the top of the page, as a keyboard user arriving; each stop's focus indicator, whether
anything covers it, and screenshots (`keyboard/`).

| Page | Stops | First stop | Skip link | First content stop | Problems |
|---|---:|---|---|---:|---|
| Home | 30 | Workspace menu | none | 15 | – |
| Inbox | 36 | Workspace menu | none | 15 | search field shows focus only by a fill; "More views" (26) is clipped by the chip row, its ring cut |
| Conversation | 50 | Workspace menu | none | 15 | as Inbox; the reply box (stop 46) shows no visible focus |
| Schedule | 26 | Workspace menu | none | 15 | – |
| Composer | 41 | Workspace menu | none | 15 | "Add comment automation" (29) is focused under the sticky action bar; the date and time fields show only the native segment highlight |
| Settings › AI | 24 | Workspace menu | none | 15 | – |

- **No skip link** in the app: 14 shell stops (workspace menu, Ask, 9 nav items, collapse,
  Upgrade, user menu) come before every page's content; the reply box is stop 46 (UI-ISS-016; the
  audit counted 42 before the view chips grew). The marketing site has one.
- **Focus is drawn several ways** (UI-ISS-002): the global 2 px brand outline on the workspace
  menu, nav links, segments and filter chips; the primitives' 3 px 50% brand halo on buttons
  (`ring-3 ring-ring/50`); a 4 px solid brand box-shadow on one shell control; the settings phrase
  field by its wrapper's brand border. The sidebar's Ask button shows a ring the script couldn't
  attribute (no outline or shadow on the button itself) but it is visible (`home-tab2-problem.png`).
- **No visible focus** on the inbox search and the reply box (a fill or border change only,
  UI-ISS-003; `inbox-tab19-problem.png`, `conversation-tab46-problem.png`). Ask's question box and
  the settings phrase field show it through their wrapper's brand border, which the script can't
  see on the field itself; their screenshots show it.
- **Focus hidden under a sticky bar**: the composer's action bar covers "Add comment automation"
  when it gets focus (UI-ISS-014, `composer-tab29-problem`).
- **Menus highlight with a faint fill only** (`row-menu-open.png`; UI-ISS-001).
- No trap on any page: Tab always left the page after the last control.

Overlays, opened from the keyboard (Enter on the trigger), then 25 Tabs, then Esc:

| Overlay | Focus on open | Tab stays inside | Focus after Esc | Issue |
|---|---|---|---|---|
| Disconnect (alert dialog) | Cancel | yes | the Disconnect trigger ✓ | – |
| Upgrade dialog | Not now | yes | **`<body>`** | new: opened from a store, not a trigger (UI-ISS-013's family) |
| Template gallery | the "All" filter | yes | **`<body>`** | UI-ISS-013 |
| Automation ⋯ menu | Duplicate | yes (Tab doesn't move) | the trigger ✓ | UI-ISS-001 (highlight) |
| Conversation AI-mode menu (non-modal) | the first item | yes | the trigger ✓ | – |
| Ask panel (button) | the question box | yes | the Ask button ✓ | – |
| Ask panel (Ctrl K from a conversation row) | the question box | – | the row ✓ | – |

## Reduced motion

Every animation and transition that ran while each overlay opened and closed, sampled each frame,
under `prefers-reduced-motion: reduce` and, for comparison, `no-preference` (`motion/`).

| Overlay | Under `reduce` | Issue |
|---|---|---|
| Template gallery, upgrade dialog (Dialog) | overlay and content `enter`/`exit` keyframes, 100 ms (fade and zoom) | UI-ISS-012; 100 ms vs the spec's 200, UI-ISS-032 |
| Disconnect (AlertDialog) | the same, 100 ms | UI-ISS-012 |
| Automation ⋯ menu (DropdownMenu) | `enter`/`exit`, 100 ms | UI-ISS-012 |
| Phone drawer (Sheet, 375) | overlay fade 100 ms, panel slide 200 ms | UI-ISS-012 |
| Ask panel | overlay and panel `enter`/`exit`, 200 ms | **new**: see below |
| Toast (sonner) | nothing ✓ (400 ms slide and fade otherwise) | – |
| Page loads (Home, Inbox, Schedule, Knowledge) | the Skeleton primitive's `animate-pulse` keeps pulsing; only the few skeletons with `motion-reduce:animate-none` stop | UI-ISS-012, UI-ISS-096 |
| Buttons and menu triggers | `transition-all` 150 ms on colour, border, shadow and `outline-color`/`outline-width`/`outline-offset` as focus moves | UI-ISS-032 |

- **What still animates under reduce:** every Radix overlay (dialogs, alert dialogs, menus, the
  drawer), the Ask panel and the skeleton pulse. Only sonner's toasts and the `motion-safe:`
  transitions (Ask's composer) stop.
- **New: the Ask panel's opt-out doesn't work.** MOTION.md and UI-ISS-012 list it as honouring
  reduced motion (`motion-reduce:animate-none`), but under `reduce` its computed `animation-name`
  is `enter`, 0.2 s, for both the panel and its overlay: `data-open:animate-in` outranks
  `motion-reduce:animate-none`. UI-012 (or UI-067) should fix the order, and UI-012's safety net
  should cover it.
- The reduced-motion screenshots (`reduced-motion/`) match the baseline apart from dynamic text
  (at most 0.21% of pixels): shots are taken after motion ends, so motion is checked by the sampling
  above, not by images.

## Known gaps

- **Ask has no thread**: the e2e stack's fake AI has no answers for Ask, so the panel and the page
  show their empty states only.
- **Inner scrollers aren't expanded**: the week view opens scrolled to 08:00, so the 14:00 posts
  are only partly in the 1280 shot; the inbox, comments grid and list views are viewport shots.
- **Sticky bars in full-page shots** sit where they are in the first screen: the composer's action
  bar (375 to 1280) and the settings save bar (Settings › AI at 1280) cover the content under them.
- **Not captured**: the workspace menu, the notifications panel, selects and tooltips (a tooltip
  shows in `keyboard/home-tab2-problem.png`), the automation editor's Test, Runs and Stats tabs, the
  composer's media library and crop dialogs, sign-up, WhatsApp (the sandbox connects Instagram
  only), billing in trial, Pro or on hold, and the other banners (credits used up, payment failed,
  trial ending).
- **Dynamic text isn't frozen**: relative times, the greeting, the calendar's dates and the AI
  credits differ between runs, and the sandbox's account handle differs between stacks. Remote
  pictures are a grey placeholder; the sign-in page shows Clerk's "Development mode" ribbon.
- **Keyboard and reduced motion at 1280 only** (the drawer at 375); no screen reader, Safari or
  forced colours.

## Repeating it at the checkpoint

1. On `develop` after Wave 1, start the stack and run `pnpm shots:ui` into
   `design/ui-qa/wave-1/`.
2. `node scripts/ui-shots/compare.mjs <baseline> <wave-1>` and file each unintended change against
   its task; compare the two `axe-summary.md` files (violations and "needs review").
3. Repeat the keyboard and reduced-motion passes as above: Tab from the top at 1280 on the six
   pages recording each stop's indicator and whether it is covered; open each overlay by keyboard,
   25 Tabs, Esc, and note where focus lands; sample `document.getAnimations()` each frame while
   each overlay opens and closes under `reduce`. (The passes were scratch specs, not committed.)
