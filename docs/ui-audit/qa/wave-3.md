# UI-043 checkpoint: Wave 3 (area adoption) against Wave 1 and the baseline

The app at `6c42dd3` (UI-030 to UI-042 and the primitives follow-ups), compared with the
[Wave 1 checkpoint](wave-1.md) and the [baseline](baseline.md) by the same tool and the same
passes. Each visible change is classified as **intended** (with the task that made it) or
**unintended** (filed against the task that most likely caused it, with the screen, width, crop and
cause). "Known" marks items already routed in the coordinator's follow-up list. Issue numbers are
from [UI_AUDIT.md](../UI_AUDIT.md).

The run is at `6c42dd3`, the Wave 3 tip. Wave 4 tasks that merged into `develop` afterwards are not
in it.

## Summary

- **No-go for Wave 4 until two things are fixed** (both small, both in Wave 3 code):
  1. **Billing quota tiles overlap their own text** (UI-037, `QuotaTile` on `Meter`): at 1280 and
     768 the label collapses to zero width and the figures print over each other; at 375 the
     Knowledge tile does the same.
  2. **The AI-mode segments no longer show which one is selected** (UI-037's Tooltip on the
     segments): Settings › AI, every width.
  Wave 4's UI-059 and UI-060 rewrite Billing and the settings frame, and UI-061 and UI-062 change the
  connections cards. They need a base where these two are right. Everything else filed is minor and is
  carried by a named Wave 4 task or a small sweep fix.
- **axe:** 14 violations on 14 screen-widths (29 nodes) in the baseline → 3 (5 nodes) at Wave 1 →
  **2 (2 nodes)** now, and no new rule. The two left are Clerk's own "Secured by" on sign-in at 375 and
  1280. `target-size` and `aria-hidden-focus` are gone. "Needs review" 1,089 → 1,102 → 1,090.
- **Keyboard:** the skip link is first on every page. Every stop draws the global outline: the
  call-site halos and rings that Wave 1 listed (Home links, Schedule post links, settings tabs, the
  automations search) are gone, and no stop is under a sticky bar. All six overlays return focus to
  their trigger. **Ctrl+K then Esc closes the Ask panel 10 times in a row**, on four pages, with and
  without waiting for the open animation (UI-040 and UI-041 hold).
- **Reduced motion:** dialogs, alert dialogs, menus, the phone drawer and skeletons are still. Only
  the Ask panel still animates (known, UI-067).
- **Tool:** no change to the ui-shots tool.

## The run

| | |
|---|---|
| Date | 2026-10-14 |
| Code | `6c42dd3` (UI-041, the last Wave 3 merge) on `feature/ui-qa-wave3`; no app code changed. |
| Stack | The isolated e2e stack (`scripts/e2e-stack.mjs --serve`): a production build on port 3132, the API on 8132, database `socialhood_e2e_qa3`, Valkey db 8; the same sandbox, fake AI, Dodo, email and push as before; Clerk's development instance. |
| Browser | Chromium 1243 (Playwright 1.63.0), dark, device scale factor 1, touch emulation at 375 and 768, heights 812, 1024, 800, 864. The tool checks `pointer` per shot: all passed. |
| axe | axe-core 4.13.0, the same tags, at 375 and 1280. |
| Tool | `pnpm shots:ui`, no `--grep`, `UI_SHOTS_WIDTHS=375,768,1280,1536`: 125 shots, 126 tests including sign-in setup, 8 min 24 s, no retries. |
| Data | The same seed (QA Shop, QA Reconnect), fresh database. |

**Where the images are** (outside the repository):
`C:\Users\zakau\social-auto\design\ui-qa\checkpoint-wave3\`

- `<screen>-<width>.png`, `axe/`, `axe.json`, `axe-summary.md`, `meta/`, `shots.json`: the run.
- **`diff/index.html`**: the tool's comparison against `../checkpoint-wave1`.
- **`diff-baseline/index.html`**: the tool's comparison against `../baseline`.
- `crops/bands/y<N>/<shot>-1.png`: Wave 1 on the left, Wave 3 on the right, starting at y = N,
  900 px bands (800 px for the 1280 shots' first band).
- `keyboard/`: `keyboard-pages.json`, `keyboard-overlays.json`, `keyboard-ctrlk-x10.json` and
  screenshots.
- `motion/`: `motion-reduce.json`, `motion-no-preference.json`.
- `probe/probe.json`: the measurements behind findings 1 and 2.

### Reading the comparison

All 125 shots differ from Wave 1 and from the baseline, as before: dynamic text (dates, relative
times, the greeting, AI credits, the sandbox handle) differs between runs. Differences that aren't
code:

- **Data:** at 375 the comment analysis on Home read "Not analysed yet" (it showed "10 of 10" at
  1280 in the same run), so Home's sentiment card and the engagement line differ by width; the
  post-comments Performance card showed "No figures yet" (no insights synced in this run). Seeded
  posts sit at 23:00 and 00:00 UTC, so schedule times read 23:00 where Wave 1 read 00:00.
- **Third party:** Clerk's account picture (a remote image) hadn't loaded in the 1280 shots (a grey
  circle), as in Wave 1.
- **Calendar:** "6 Oct" was today in Wave 1; today is 13 Oct. The month grid shows the current month
  by date.

Method and limits of the classification: every 375 shot (all screens), ten of the 1280 shots
(Home, Inbox, Schedule month, Billing, Agent, Knowledge, Settings › AI and more), and the four public
pages were read as Wave 1 | Wave 3 bands. The 768 and 1536 shots were ranked by the diff and spot
checked (Billing 768). Wave 3 changes are class-level (primitives and tokens), so a change seen at
375 or 1280 repeats at the other widths, and findings 1 to 3 were checked at more than one width.

## Changes by screen

Changes that recur on every screen are listed once:

- **One focus outline everywhere:** the halos and rings left at call sites are gone. Intended:
  UI-030, UI-032, UI-034, UI-036, UI-038.
- **Cards, tiles, chips and pills on the primitives:** panels share Card's radius and edge; status
  pills are Badge (neutral for platforms); chip rows are taller (40 px on touch) and rounder; banners
  are Alert. Intended: UI-031, UI-033, UI-035, UI-037, UI-039, UI-041.
- **Search fields** are SearchInput: 40 px, 16 px text on phones, the 40% edge. Intended: UI-030,
  UI-035, UI-037.
- **Field labels and hints** are Field (normal leading, hint spacing). Intended: UI-033, UI-035,
  UI-037, UI-039.
- **Sidebar AI-credits card** is a Meter ("16 of 200 used", no percentage). Intended: UI-041.
- **Overlay surfaces** are `overlay` (#262626) with the floating shadow; the call sites' `bg-panel`
  and `shadow-xl` are gone. Intended: UI-032, UI-034, UI-036 to UI-041 (the overlay sweeps).

| Screen | Change | Class | Task, evidence |
|---|---|---|---|
| home | 375: header tighter ("1 channel connected" is a small neutral Badge; range control and Refresh on one row); metric tiles 105 px (were 107); sentiment legend fits on one line ("Neutral 100%", was overflowing at 1024), thin Meter tracks; Most commented bars thinner; the gap notice is an Alert with "View thread" and "Train AI" | intended | UI-038, UI-039 (`crops/bands/y0/home-375-1.png`, `y900`, `y1800`) |
| home | **Platform pills are neutral:** "Instagram" in the priority queue is a grey Badge, not a red-outlined pill | intended, owner FYI | UI-039 (`crops/bands/y1800/home-375-1.png`) |
| home | 1280: metric tiles and cards on Card; "Engagement rate" line gone (data) | intended | UI-038, UI-039 (`crops/bands/y0/home-1280-1.png`) |
| inbox-list | **The platform segment is neutral:** "All" is no longer a blue fill (D-15); the row is 40 px with a 40% edge; Chats and Scheduled are the larger `sm` tabs; search is 40 px; filter chips 40 px, rounded, and scroll with "More" reachable by keyboard | intended | UI-030 (`crops/bands/y0/inbox-list-375-1.png`, `inbox-list-1280-1.png`) |
| inbox-list | The list starts about 44 px lower at 375 (taller header) | intended | UI-030 |
| conversation | AI Polish reads as a tinted action, not a disabled one; the header's AI pill is bordered; no other change | intended | UI-031 (`crops/bands/y0/conversation-375-1.png`) |
| comments | Cards unchanged (dates are data) | – | – |
| post-comments | "Summarize" is a soft Button; Likes and Comments tiles have an edge; comment actions: **Delete is red** (destructive ghost, was grey); chips taller; Performance "No figures yet" is data | intended | UI-039 (`crops/bands/y0/post-comments-375-1.png`, `y900`) |
| automations | Stats tiles unchanged; search, Select and sort controls all 40 px (the Wave 1 36 px search is fixed); **the search placeholder is clipped at 375 ("Search by name or")** | intended, plus **unintended #5** | UI-035 (`crops/bands/y0/automations-375-1.png`) |
| automation-editor | Cards and Fields on the primitives; Active is a Badge; the sections' content shifts about 15 px | intended | UI-035 (`crops/bands/y0/automation-editor-375-1.png`) |
| template-gallery | Filter chips are rounded 40 px chips; cards on Card; overlay surface | intended | UI-035 (`crops/bands/y0/template-gallery-375-1.png`) |
| schedule-week, -list | Header, segments and the list tabs unchanged apart from tokens; post times 23:00 (data) | intended | UI-032 (`crops/bands/y0/schedule-week-375-1.png`, `schedule-list-375-1.png`) |
| schedule-month | **1280: the cards' actions are 24 px (were 20) and readable; 768 on touch: the post title is back** (Wave 1 unintended #1 fixed) | intended | UI-032 (`crops/bands/y0/schedule-month-1280-1.png`) |
| composer | **The ⋯ moves into the header line** (UI-ISS-115); sections are Cards; media tile bigger with a count; date and time 16 px with an edge and icons; checklist and preview on Card | intended | UI-032, UI-033 (`crops/bands/y0/composer-375-1.png`, `y900`, `y1800`) |
| knowledge | **The Always placeholder fits** ("e.g. Say hello first", Wave 1 unintended #2 fixed); **the status sits under the source name** so names are no longer cut to 4 characters ("Can I return or exchang…"); Meter for usage; Alert, Field, Card | intended | UI-039 (`crops/bands/y900/knowledge-375-1.png`) |
| ask-panel | The composer's focus is the global outline (was a dark 4 px ring); otherwise unchanged | intended | UI-040 (`crops/bands/y0/ask-panel-375-1.png`) |
| ask-panel | Still animates under reduced motion | known | UI-067 |
| ask-page | Same; the header shows two clock-style history icons beside the pencil (also in Wave 1; not new) | – | file with UI-067/069 (low) |
| settings-connections | Search is SearchInput inside the filter card (a nested edge); Remove and Disconnect on the destructive variants | intended | UI-036, UI-037 (`crops/bands/y0/settings-connections-375-1.png`) |
| settings-ai | **No selected state on the AI-mode segments** (Off, Suggest, Auto); the 2 h takeover segment shows it | **unintended #2** | UI-037 (`crops/bands/y0/settings-ai-375-1.png`, `settings-ai-1280-1.png`, `toast-375-1.png`, `probe/probe.json`) |
| settings-ai | Takeover on `xl` segments; escalation items on Card; "Upgrade for Auto" 40 px at 375 | intended | UI-036 |
| settings-workspace | **"Delete workspace" is a quiet destructive ghost with a red left edge on the danger Card** (Wave 1 unintended #3 fixed) | intended | UI-036, UI-037 (`crops/bands/y900/settings-workspace-375-1.png`) |
| settings-notifications | Rows on Card; no visible change otherwise | intended | UI-037 |
| settings-billing | **Quota tiles are compact Meter rows; at 1280, 768 and (Knowledge) 375 the label and figure overlap** | **unintended #1** | UI-037 (`crops/bands/y800/settings-billing-375-1.png`, `settings-billing-1280-1.png`, `probe/probe.json`) |
| settings-billing | **A full quota (Instagram accounts, 100%) is no longer red**: a blue bar and a neutral "All used" | **unintended #3** (owner to confirm) | UI-037 (`crops/bands/y1800/settings-billing-375-1.png`) |
| settings-agent | **The run filter and the search are one height** (Wave 1 unintended #4 fixed); capabilities grid on Card | intended | UI-040 (`crops/bands/y0/settings-agent-1280-1.png`) |
| upgrade-dialog | Overlay surface; buttons unchanged | intended | UI-036 |
| menu-open | Overlay surface and shadow; Delete in `danger-fg` | intended | UI-034, UI-013 |
| dialog-open | Overlay surface; the Disconnect trigger behind is tinted red; Cancel is an outline button | intended | UI-036, UI-037 |
| phone-drawer | **The drawer is `canvas`, with the sidebar card on `panel`**; Free is a tinted Badge; AI credits a Meter | intended, owner FYI | UI-041 (`crops/bands/y0/phone-drawer-375-1.png`) |
| toast | Unchanged apart from the AI-mode segments (finding #2) | – | – |
| banner | The reconnect banner has a warning icon and a smaller Reconnect button; the notice and the checklist's current step on Alert and Card | intended | UI-041 (`crops/bands/y0/banner-375-1.png`) |
| banner-inbox | **The composer's reconnect notice is an Alert with a secondary "Reconnect"** (it was the one primary action) | intended, owner to confirm | UI-041, then UI-059 (`crops/bands/y0/banner-inbox-375-1.png`) |
| sidebar (every 1280 shot) | **"Ask Social Hood" is cut to "Ask Social Ho…" by the Ctrl K chip** (it fitted in Wave 1; the label's box is 150 px) | **unintended #4** | UI-040 (`crops/bands/y0/home-1280-1.png`, `probe/probe.json`) |
| landing | 1280: the hero is 3 px shorter; buttons on tokens; no other change | intended | UI-042 (`crops/bands/y0/landing-1280-1.png`) |
| privacy, data-deletion | Legal text at `fg-secondary` with brighter bold run-ins; the e-mail link underlined; cards on Card | intended | UI-042 (`crops/bands/y0/privacy-375-1.png`, `data-deletion-375-1.png`) |
| sign-in | Continue and Clerk tokens; "Secured by" still fails (Clerk's own text) | intended, plus known | UI-042; UI-070 |

**Not visible in any shot:** the leave guards and Undo; the focus returns after a confirmed source
delete (UI-039), the Esc fix (UI-040, UI-041; covered by the keyboard pass), the ShellSkeleton
fallback (UI-041); the `ConnectWhatsAppButton` DisabledReason. Their acceptance was in their PRs.

### Unintended changes, filed

| # | Change | Filed against | Fix in | Evidence |
|---|---|---|---|---|
| 1 | Billing quota tiles: the Meter's label row collapses (label 0 px wide, 32 px tall, the figure printed over it) at 1280 (7 of 7 tiles), 768 (Knowledge) and 375 (Knowledge) | UI-037 (QuotaTile on Meter) | **before Wave 4**: give the label `min-w-0 flex-1` and let the figure wrap or truncate; check 375 to 1536 | `crops/bands/y800/settings-billing-375-1.png`, `settings-billing-1280-1.png`, `settings-billing-768.png`; `probe/probe.json` (`billingTiles`) |
| 2 | AI-mode segments show no selected state: the Tooltip trigger's `data-state="closed"` replaces the toggle item's `data-state="on"`, so `data-[state=on]:bg-raised` never applies (aria-checked is right) | UI-037 (Tooltip on the segments) | **before Wave 4**: style on `aria-checked`, or put the Tooltip on a wrapper around the item. Check ToggleGroup items elsewhere that gain a Tooltip | `probe/probe.json` (`aiModeSegments`: Suggest, `checked: true`, bg transparent; `takeoverSegments`: 2 h `on`, #2A2A2A); `crops/bands/y0/settings-ai-1280-1.png` |
| 3 | A full quota (100%) is no longer red: blue bar, neutral "All used" | UI-037 (Meter tone) | with #1; if the neutral look is intended, say so in DESIGN_SYSTEM | `crops/bands/y1800/settings-billing-375-1.png` |
| 4 | The sidebar's "Ask Social Hood" label truncates at 1280 | UI-040 (sidebar Ask button) | small fix when the shell is next touched (UI-063 edits `AppShell.tsx`): shrink the chip or the label | `crops/bands/y0/home-1280-1.png`; `probe/probe.json` (`askButton`) |
| 5 | Automations search placeholder clipped at 375 ("Search by name or") | UI-035 (SearchInput at 16 px) | UI-064 (edits `AutomationsPage.tsx`): "Search automations" | `crops/bands/y0/automations-375-1.png` |

Wave 1's four unintended changes are all fixed (month cards, Always placeholder, Delete workspace,
the Agent search), as are its tool follow-ups' items ("More views" is reachable, the composer's ⋯
row).

## axe (375 and 1280)

| Rule | Impact | Baseline: screens × widths / nodes | Wave 1 | Wave 3 | Where (Wave 3) |
|---|---|---|---|---|---|
| `color-contrast` | serious | 10 / 16 | 2 / 2 | **2 / 2** | Clerk's "Secured by" on sign-in at 375 and 1280 (known, UI-070) |
| `aria-hidden-focus` | serious | 2 / 8 | 0 / 0 | **0 / 0** | – |
| `target-size` | serious | 2 / 5 | 1 / 3 | **0 / 0** | the calendar cards' actions are 24 px (UI-032) |
| **Total** | | **14 / 29** | **3 / 5** | **2 / 2** | no new rule |

**Every targeted rule is gone** except Clerk's "Secured by" text, which is Clerk's own markup
(UI-042 changed Clerk's tokens, not that string; routed to UI-070). The plan's bar, "at or below the
baseline", is met (29 → 2 nodes).

**Needs review** (axe couldn't decide):

| Rule | Baseline | Wave 1 | Wave 3 |
|---|---:|---:|---:|
| `color-contrast` | 1,052 | 1,065 | 1,045 |
| `aria-hidden-focus` | 37 | 35 | 43 |
| `aria-valid-attr-value` | 0 | 2 | 2 |
| **Total** | **1,089** | **1,102** | **1,090** |

- `color-contrast`: by axe's reason, background image 531, gradient 182, short text 165, overlap
  111, partly obscured 49, other 5, equal ratio 2. The 1280 shots dropped by about 1 node each (the
  sidebar's labels).
- `aria-hidden-focus`: +8, all on **template-gallery** at 375 and 1280 (3 → 7 each): the open
  dialog's hidden siblings now include more focusable elements (the gallery's header actions and the
  page behind it); resting screens are clean, and the dialog traps focus (keyboard pass).
- Nothing in Wave 3 added a violation.

axe by screen (375 | 1280) is in `axe-summary.md`; both widths read 0 violations on every screen
except sign-in.

## Keyboard (1280)

The same method as Wave 1: Tab from the top, each stop's indicator and whether it's covered; each
overlay opened with Enter, 25 Tabs, then Esc. Plus **Ctrl+K, then Esc, ten times in a row**.

| Page | Stops (W1 → W3) | First stop | Skip link, then Tab | Problems |
|---|---:|---|---|---|
| Home | 31 → 32 | Skip to content | "7 days" (in `<main>`) | none. The six Home links that drew the 50% halo now draw the outline |
| Inbox | 37 → 32 | Skip to content | "All" | none. "More views" is now "More", reachable and fully visible at the end of the scrolling chip row |
| Conversation | 51 → 47 | Skip to content | "All" | none. The reply box's focus is the wrapper's outline (as in Wave 1) |
| Schedule | 27 → 28 | Skip to content | "Add to queue" | none. The post links draw the outline (they drew a solid ring) |
| Composer | 42 → 44 | Skip to content | "Schedule" | none. **The native date and time picker buttons now show a focus indicator** (they showed none): stops 35 and 38 report `focus-visible` false but draw it |
| Settings › AI | 25 → 26 | Skip to content | "Connections" | none. **The settings tabs draw the outline** (they drew a solid ring) |

- Every page: no stop with a box-shadow-only indicator (Wave 1: six on Home, the Schedule links,
  the settings tabs); no stop under a sticky bar or off screen; no trap; the skip link draws a 2 px
  outline on `brand-strong`.
- The sidebar's "Ask Social Hood" button (stop 3) still reports no indicator on the element itself:
  the focus draws on its wrapper (visible; as in Wave 1 and the baseline).

| Overlay | Focus on open | Tab stays inside | Focus after Esc |
|---|---|---|---|
| Disconnect (alert dialog) | Cancel | yes | trigger, outline |
| Upgrade dialog | Not now | yes | "Upgrade for Auto" |
| Template gallery | "All" | yes | "New automation" |
| Automation ⋯ menu | Duplicate | yes | trigger |
| Conversation AI mode menu | first item | yes | trigger |
| Ask panel (button) | the question box | yes | Ask button |
| Ask panel (Ctrl+K from the inbox list) | the question box | – | the row you were on |

**Ctrl+K, Esc ×10** (`keyboard/keyboard-ctrlk-x10.json`): on Home (waiting 400 ms between the keys),
Home (40 ms: Esc almost as soon as the panel opens), the inbox (400 ms) and Schedule (40 ms), the
panel closed on all 40 attempts. The Wave 3 bug is fixed (UI-040, UI-041).

## Reduced motion

Every animation and transition while each overlay opens and closes, under `reduce` and
`no-preference` (`motion/`).

| Overlay | Under `reduce` | `no-preference` |
|---|---|---|
| Template gallery, upgrade dialog (Dialog) | nothing (`animation-name: none`) | 200 ms in, 120 ms out |
| Disconnect (AlertDialog) | nothing | 200 / 120 ms |
| Automation ⋯ menu | nothing | 120 ms |
| Phone drawer (Sheet, 375) | nothing | 200 / 120 ms |
| Ask panel | **200 ms enter and exit, unchanged** | 200 ms |
| Toast | no animation; the AI-mode segments' 120 ms colour fade runs (a colour change, not motion) | 200 ms |
| Page loads (Home, Inbox, Schedule, Knowledge) | no skeleton pulse | pulses |

Only the Ask panel still animates (a custom `DialogPrimitive` without a `data-slot`; known,
UI-067).

## Known gaps still open (expected, not regressions)

From the coordinator's list, as seen in this run:

- **UI-067:** the Ask panel (and RunDetailSheet) animate under reduced motion.
- **UI-070:** Clerk's "Secured by" (2 nodes) and the "Primary" badge.
- **Primary and hierarchy:** gradient primaries still sit beside primaries in several views
  (UI-059).
- **UI-063:** the UpgradeDialog's focus after Esc. The keyboard pass shows it returning to the
  "Upgrade for Auto" trigger, which was UI-012's fix; the 402 route has no trigger.
- **Layout:** the Knowledge "Concise" segment wraps to its own row at 1280 (Wave 1 too); the Ask
  page header's duplicate icons.
- **Touch targets** under 40 px that Wave 3 didn't resolve and Wave 4 owns: the composer attachment
  tray's small buttons (UI-051), the calendar month day numbers (pass 2.5.8).

## Owner FYIs to confirm

1. **The phone drawer is `canvas` with the sidebar card on `panel`** (UI-041): the drawer reads
   darker than the overlays; the card reads by its fill. `crops/bands/y0/phone-drawer-375-1.png`.
2. **The skip link opens top-centre** (UI-041): over the page header, clear of the sidebar logo.
   `keyboard/home-tab1.png`.
3. **Home's platform pills are neutral** (UI-039): "Instagram" is a grey Badge; the same in the
   inbox's platform segment (UI-030, D-15). `crops/bands/y1800/home-375-1.png`.
4. Billing's quota tiles are now small Meter rows without the big number (UI-037). Confirm after
   fix #1 that this is the intended look.
5. The reconnect notice above the composer has a secondary Reconnect (UI-041).
6. Comment "Delete" is red text now (UI-039).

## Go / no-go for Wave 4

**No-go until the two fixes below land; then go.** Both are small and in Wave 3 files.

**Must fix before Wave 4** (one small task, e.g. "UI-037 follow-up"):

1. Billing quota tiles overlap (#1, with #3 if the red full state is wanted): UI-037.
2. AI-mode segments' selected state (#2): UI-037. Check the other ToggleGroups that carry a
   Tooltip.

**Wave 4 tasks will cover:**

- #5 (Automations search placeholder): UI-064.
- #4 (the sidebar's Ask label): UI-063, or a one-line fix with it.
- Reconnect emphasis in the composer notice: UI-059.
- Clerk "Secured by" and "Primary": UI-070.
- The Ask panel's reduced motion: UI-067.
- The Ask page's duplicate history icons: UI-067/UI-069.

**Asks for the Wave 4 agents:** take "after" shots with the fixed tool; compare against this
checkpoint (`checkpoint-wave3`), not Wave 1; remember the seeded dates move with the clock.
