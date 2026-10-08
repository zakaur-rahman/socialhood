# UI-019 checkpoint: Waves 0–2 against the pre-Wave-0 baseline

The app after Waves 0, 1 and 2, compared with the [baseline](baseline.md) by the same tool and the
same passes. Each visible change is classified as **intended** (with the task that made it) or
**unintended** (filed against the task that most likely caused it, with evidence). Issue numbers
are from [UI_AUDIT.md](../UI_AUDIT.md); follow-ups already routed by the coordinator are marked
"known".

## Summary

- **Go for Wave 3.** Nothing must be fixed before the area sweeps start. Four unintended app
  changes, all small, and one tool bug (fixed here). Each app change belongs to a Wave 3 task that
  touches the same files (see [Go / no-go](#go--no-go-for-wave-3)).
- **axe:** 14 violations on 14 screen-widths (29 nodes) → **3 (5 nodes)**, and no new rule.
  `color-contrast` 16 → 2 nodes (both are Clerk's own "Secured by"), `aria-hidden-focus` 8 → 0,
  `target-size` 5 → 3 (the calendar month cards, known). "Needs review" 1,089 → 1,102: axe can't
  decide on text over the new identity gradients and gradient buttons.
- **Keyboard:** a skip link is now first on every page, and Enter, then Tab, lands in `<main>`.
  All six overlays now return focus to their trigger (the baseline had two failures), menu items
  show the outline, and no focused control sits under a sticky bar. The global outline replaced
  the 50% halo on every primitive. What remains is all Wave 3: call-site halos and rings, "More
  views" clipped by its row, and the native date and time picker buttons.
- **Reduced motion:** dialogs, alert dialogs, menus, the phone drawer and skeletons are all still
  now. Only the Ask panel still animates (known, UI-067).
- **Tool fix:** touch full-page shots were being taken with a fine pointer; fixed and committed
  (below). The baseline's touch shots are barely affected; this checkpoint's show true touch
  sizes.

## The run

| | |
|---|---|
| Date | 2026-10-07 |
| Code | `develop` at `88b1080` (UI-017, the last Wave 2 merge), plus the ui-shots fix on `feature/ui-qa-wave1` (tool only; the app code is develop's). |
| Stack | The isolated e2e stack (`scripts/e2e-stack.mjs --serve`): a production build on port 3131, the API on 8131, database `socialhood_e2e_qa1`, Valkey db 7; the same sandbox, fake AI, Dodo, email and push as the baseline; Clerk's development instance. |
| Browser | Chromium 1243 (Playwright 1.63.0), dark, device scale factor 1, touch emulation at 375 and 768, the same heights as the baseline. **The pointer is now checked:** every 375 and 768 shot recorded `pointer: coarse` and every 1280 and 1536 shot `fine` (`meta/*.json`). |
| axe | axe-core 4.13.0, the same tags, at 375 and 1280. |
| Tool | `pnpm shots:ui` with the fix below: 125 shots in 7 min 48 s, no retries, no loading warnings. |
| Data | The same seed (QA Shop, QA Reconnect). |

**Where the images are** (outside the repository):
`C:\Users\zakau\social-auto\design\ui-qa\checkpoint-wave1\`

- `<screen>-<width>.png`, `axe/`, `axe.json`, `axe-summary.md`, `meta/`, `shots.json`: the run.
- `diff/index.html`: the tool's comparison against `../baseline` (before, after and diff side by
  side, most-changed first).
- `crops/bands/y<N>/<shot>-1.png`: crops cited below, before on the left and after on the right,
  starting at y = N.
- `keyboard/`, `motion/`: the keyboard and reduced-motion passes (the same JSON and screenshots
  as the baseline's).
- `probe/`: measurements behind the findings (`measure.json`, `touch-375.json`, `probe.json`,
  `axe-review.json`, `bottom.json`).
- `run1-fine-pointer/`: the first run, before the stitched capture (evidence for the tool bug).
- `stitch/`: the stitched capture checked against Playwright's `fullPage` (`stitch.json`).

### Reading the comparison

Every one of the 125 shots differs from the baseline, because the dynamic text (greeting, dates,
relative times, AI credits, the sandbox handle) differs between runs. The diff page orders shots
by how much changed. Differences that aren't code:

- **Data:** the sandbox now returns post insights, so Home's "Engagement rate" line and the post's
  Performance figures appear (home-1280: +57 px; post-comments-1280: +242 px). Comment analysis was
  still running for one post ("Analysing 0 of 4", comments-375). The seeded posts fall at 00:00 and
  01:00 UTC, outside the week view's 08:00 window, so **schedule-week's `target-size` 2 → 0 is not a
  fix**: the cards aren't on screen (the month view still fails on the same buttons).
- **Third party:** Clerk's account picture, a remote image from `img.clerk.com`, hadn't loaded in
  12 of the 23 full-page 1280 shots (a grey circle where "ET" should be), against 2 in the
  baseline. Clerk was updated in #41. This isn't app code: the tool neither stubs that host nor
  waits for lazy pictures.
- **Landing price:** the e2e launcher runs `next build` before it starts the API, so the
  landing's ISR snapshot shows "Prices couldn't be loaded" until the first hourly revalidation.
  The first run caught that; this run was taken after the revalidation and shows ₹999, as the
  baseline did. A tooling follow-up: start the API before the build, or warm `/` after an hour.
- **Capture method at 375 and 768** (see the tool fix): shots now have touch heights, and the
  landing page's feature illustrations, which the baseline's `fullPage` capture left blank at 375,
  are drawn.

## The tool fix (committed first, `2c5f80a`)

**Symptom:** touch shots showed desktop control heights. **Cause, measured:** Chromium's
beyond-viewport capture, which Playwright's `fullPage` uses, drops touch emulation. It renders the
page with `pointer: fine`, and the page stays fine afterwards. A probe block 300 px tall under
`(pointer: coarse)` captured at 100 px, and `matchMedia('(pointer: coarse)')` was `false` after
the shot, even with touch emulation forced again through CDP. Viewport captures keep it.
Playwright's own touch emulation does apply `coarse` on every app page tested (`probe/probe.json`).

The visible effect: the page's height is measured with touch sizes, but the capture lays it out
with desktop sizes, so the content ends early and the image has blank space at the bottom. Before
the fix: automation-editor-375 had 210 px of blank space instead of 16, knowledge-768 96 instead
of 24, post-comments-768 88 instead of 24, and the inputs were 36 px, not 40
(`run1-fine-pointer/`). axe at 375 also ran on that fine-pointer page.

**The fix:**

- At 375 and 768, full-page shots are **stitched from viewport captures**. The page never
  scrolls: each tile after the first moves `<body>` with a transform. Sticky bars, the landing
  page's scroll-linked effects and viewport units therefore stay in their scroll-0 state, as
  `fullPage` draws them, and fixed elements appear in the first screen only.
- Touch emulation is also forced from a second CDP session. `Emulation.setEmulatedMedia`, the
  route the brief suggested, silently ignores `pointer` and `hover` in Chromium 1243;
  `Emulation.setTouchEmulationEnabled` sets them.
- `matchMedia` is checked **before and after** every shot: `(pointer: coarse)`,
  `(any-pointer: coarse)` and `(hover: none)` must match at 375 and 768 and not at 1280 or 1536,
  or the shot fails. The result is recorded in `meta/*.json`.
- **Verified:**
  - all 63 touch shots are coarse and all 62 desktop shots fine;
  - stitched against `fullPage` at 1280, Settings › AI is identical (0 px) and the automation
    editor differs by 6 px; Home differs only in text anti-aliasing (1%), which is why 1280 and
    1536 keep `fullPage`;
  - at 375 a page without touch-sized controls matches `fullPage` to 4 px (home-375);
  - the landing page has no seams (`stitch/stitch.json`).
- **The baseline is still comparable:** before Wave 1 the pointer changed only four things
  (sidebar rows `pointer-coarse:h-10`, UsageCard's Upgrade, Ask's "Enter to ask" hint, RunView's
  hover actions). So the baseline's touch shots are close to what a touch user saw.

## Changes by screen

Changes that recur on every screen are listed once:

- **Touch sizes now show at 375 and 768:** Buttons, Select triggers, Inputs, ChipInputs,
  segments, tabs and menu items are 40 px (segments in vertical lists 44 px). Intended: UI-011,
  UI-013, UI-014, UI-015, UI-023.
- **Field edges at 40% white** (`line-control`) on inputs, textareas, select triggers, chip
  inputs, checkboxes and unchecked switches; **brighter placeholders** (`fg-secondary`). Intended:
  UI-018 (D-01, D-06) on UI-013, UI-014 and UI-023.
- **16 px text in fields below 768** (inputs, textareas, selects, chip inputs). Intended: UI-014,
  UI-013, UI-023.
- **Labels with normal leading.** Intended: UI-014.
- **Unsized text in `<main>` is 14 px, not 16:** label-plus-hint rows are about 4 px shorter.
  Intended: UI-006.
- **Contact and account avatars use the identity palette:** the baseline's green, red and orange
  avatars become the three brand-based pairs (mostly blue). Intended: UI-027 (D-13).
- **Modal scrim:** black 60% without blur. Intended: UI-012.
- **Sidebar group labels** (ENGAGE, GROW) in `fg-secondary`. Intended: UI-002.

| Screen | Change | Class | Task, evidence |
|---|---|---|---|
| home | 375: no longer scrolls sideways (499 → 375 px wide) | intended | UI-003 (`crops/bands/y0/home-375-1.png`) |
| home | "30 days" on one line, so the header is shorter (1536: 1451 → 1447 px; the data lines below add height at other widths) | intended | UI-015 |
| inbox-list | "All" platform segment `brand-strong` (axe contrast fixed at 375 and 1280) | intended | UI-002 |
| inbox-list | Filter chips, Chats and Scheduled, search: unchanged (hand-built, 24–28 px on touch) | known | UI-030 |
| conversation | 375 and 768: the header shows the contact's name, a compact "24h left" chip on the handle line, the AI pill as an icon; no overlap | intended | UI-004 (`crops/bands/y0/conversation-375-1.png`) |
| conversation | "Instagram" in `fg-secondary` beside its glyph (axe contrast fixed at 1280) | intended | UI-004, UI-002 |
| conversation | AI draft bar's Insert and Send 40 px on touch | intended | UI-011 |
| comments | No UI change (analysis progress is data) | – | – |
| post-comments | Performance's select has a control edge; comment avatars | intended | UI-013, UI-018, UI-027 |
| automations | Select triggers 40 px and 16 px with a 40% edge on touch; the raw search beside them stays 36 px, 14 px, 10% edge (`probe/measure.json`) | intended, plus known | UI-013, UI-018; the search is a raw field (UI-034) (`crops/bands/y0/automations-375-1.png`) |
| automation-editor | Inputs, textareas, selects and the keyword ChipInput on the field recipe; "AI reply" on one line; trigger lists 44 px on touch | intended | UI-014, UI-013, UI-023, UI-015 (`crops/bands/y900/automation-editor-375-1.png`, `crops/bands/y1800/automation-editor-375-1.png`) |
| automation-editor | UI-005's new AI-reply sentence isn't in any shot (the seeded automation sends "A message") | not visible | UI-005 |
| automation-editor | The preview stays above the steps below 1280 | known | D-16, UI-035 |
| template-gallery | No blur; "Use template" 40 px on touch | intended | UI-012, UI-011 |
| schedule-week, -list | Header buttons and segments 40 px at 768; "Select all" checkbox edge; account rings | intended | UI-011, UI-015, UI-018, UI-027 |
| schedule-month | **768: the calendar cards lose their post title:** the actions button is 40 × 40 in a 78 × 24 card, and the title span measures 0 px (at 1280 the button is 20 × 20 and the title gets 57 px) | **unintended** | UI-011's touch sizing on a call-site `size-5` (known follow-up; fix in UI-032) (`crops/bands/y0/schedule-month-768-1.png`, `probe/measure.json`) |
| composer | Caption and comment textareas 16 px with a 40% edge; the raw date and time fields stay 14 px with a 10% edge | intended, plus known | UI-014, UI-018; raw fields (UI-032) |
| composer | ⋯ still on its own row at 375 | known | UI-ISS-115, UI-032 |
| knowledge | Source names readable ("Shop timings", "Price list"; were "Sh…", "Pri…"); long ones still cut ("Can I return …") | intended, plus known | UI-026; UI-039 (`crops/bands/y900/knowledge-375-1.png`) |
| knowledge | Always and Never are ChipInputs | intended | UI-023 |
| knowledge | **375: the Always placeholder is clipped** ("…over ₹3,00"): 284 px of 16 px text in a 275 px field; it fitted at 14 px | **unintended** (minor) | UI-023 (16 px on phones); fix in UI-039 with a shorter placeholder (`crops/bands/y900/knowledge-375-1.png`, `probe/measure.json`) |
| ask-panel | 375: the panel now fits the phone (all four header buttons and the composer on screen; the baseline cut them off) | intended | UI-003: the panel opens over Home, whose 499 px overflow had widened the mobile layout viewport (`crops/bands/y0/ask-panel-375-1.png`) |
| ask-panel | Still animates under reduced motion | known | UI-067 |
| ask-page | Placeholder brighter | intended | UI-018 (D-06) |
| settings-connections | Select and switches on the field recipe; the account search stays raw | intended, plus known | UI-013, UI-014, UI-018; UI-036 |
| settings-connections | Disconnect beside a red Remove | known | D-09, UI-036 |
| settings-ai | Takeover "Until resumed" on one line (1280: 874 → 847 px) | intended | UI-015 |
| settings-ai | Escalation phrases on ChipInput (counter under the field) | intended | UI-023 |
| settings-ai | Save bar opaque, no blur | intended | UI-009 |
| settings-ai | "Upgrade for Auto" 40 px on touch, still 22 px at 1280 | intended, plus known | UI-011; UI-036 |
| settings-workspace | Fields and the time-zone select on the field recipe (+24–32 px) | intended | UI-014, UI-013, UI-018 |
| settings-workspace | "Say when a message is automated" with normal leading | intended | UI-014 |
| settings-workspace | **"Delete workspace" trigger now has a red border** (`border-danger/60`, text `danger-fg`): UI-011 dropped the outline variant's `dark:border-input`, so the call site's border wins. Harmless, but not the design's `destructive-ghost` (no border) | **unintended** (cosmetic) | UI-011; fix in UI-040 (`crops/bands/y800/settings-workspace-1280-1.png`, `probe/measure.json`) |
| settings-notifications | Rows about 4 px shorter (1280: 863 → 846 px) | intended | UI-006 (`crops/bands/y0/settings-notifications-1280-1.png`) |
| settings-billing | Max card dims its fill and border, not its text; "Coming soon" on `hover` (axe: 3 → 0 at 375 and 1280) | intended | UI-002 |
| settings-agent | "Action needed" on one line | intended | UI-015 |
| settings-agent | **1280: the run filter (28 px, `size="sm"`) sits beside a 40 px search** (the search's call-site `min-h-10`); the baseline row was one height | **unintended** (minor) | UI-015; fix in UI-040 by giving the search an Input size (`crops/bands/y800/settings-agent-1280-1.png`, `probe/measure.json`) |
| upgrade-dialog | No blur; buttons 40 px on touch; focus returns (keyboard) | intended | UI-012, UI-011 |
| menu-open | Highlighted item outlined; destructive item `danger-fg` | intended | UI-013 |
| menu-open | Non-modal: the row behind keeps its hover state (checkbox and grip visible at 1280), and the page isn't `aria-hidden` (axe `aria-hidden-focus` 4 → 0) | intended | UI-013 |
| menu-open | 375: with 40 px items the menu opens above its trigger | intended | UI-013 (`crops/bands/y0/menu-open-375-1.png`) |
| dialog-open | Disconnect is red: `#C53030` with white text, 5.47:1 (was brand `#567FF8`, 3.63:1) | intended | UI-012 with the `cn` fix (#29) (`crops/bands/y0/dialog-open-375-1.png`, `probe/probe.json`) |
| dialog-open | The dialog surface stays `panel` (`rgb(31,31,31)`, the call site's `bg-panel`) | known | Wave 3 overlay sweeps |
| phone-drawer | No blur; the whole drawer (Notifications to the account button) fits 812 px; the baseline pushed its lower half off screen | intended | UI-003 (the same viewport widening as the Ask panel), UI-012, UI-018 (`crops/bands/y0/phone-drawer-375-1.png`) |
| toast | 375: top centre over the top bar; 768+: bottom right; overlay surface with an edge | intended, plus known | UI-024; covering the bar is known (UX-SH-04) (`crops/bands/y0/toast-375-1.png`) |
| banner | 375: no longer 499 px wide | intended | UI-003 |
| banner-inbox | The reconnect notice replaces the composer inside the viewport at every width; header as in conversation | intended | UI-006, UI-004 (`crops/bands/y0/banner-inbox-375-1.png`) |
| landing | 1280, 1536: no visible change; 375, 768: illustrations drawn (capture method) | – | the tool fix |
| privacy, data-deletion | Bold run-in labels at weight 600, so some lines rewrap | intended | UI-001 (`strong, b { font-weight: 600 }`, C-070) |
| sign-in | Continue button `brand-strong`; "Secured by" still fails (Clerk's own text) | intended, plus known | UI-002; UI-042 |

**Not visible in any shot:**

- UI-005: the AI-reply copy.
- UI-008: the Unschedule confirm and leave guards.
- UI-016: Badge, Skeleton and Avatar primitives, unused at the call sites.
- UI-017: Tooltip.
- UI-020, UI-021, UI-022: Card, Alert, Meter (no call sites yet).
- UI-025: the error boundary.
- UI-028: breakpoints, behaviour only.

Their acceptance was checked in their own PRs.

### Unintended changes, filed

| # | Change | Filed against | Fix in | Evidence |
|---|---|---|---|---|
| 1 | Month view at 768 (touch): calendar cards lose their post title; the actions button is 40 × 40 in a 24 px card | UI-011 (touch sizing meets a call-site `size-5`) | UI-032: drop `size-5` (24 px at 1280, which also clears `target-size`) and give the card's button a touch size that fits | `crops/bands/y0/schedule-month-768-1.png`; `probe/measure.json` (`768.monthCard`) |
| 2 | Knowledge at 375: the Always placeholder is clipped at 16 px | UI-023 | UI-039: a shorter placeholder ("e.g. Free shipping over ₹3,000") | `crops/bands/y900/knowledge-375-1.png`; `probe/measure.json` (`375.knowledgeChip`) |
| 3 | Settings › Workspace: "Delete workspace" trigger shows a red border | UI-011 (the `dark:` border removed, so the call site's wins) | UI-040: `variant="destructive-ghost"`, drop the call-site classes | `crops/bands/y800/settings-workspace-1280-1.png`; `probe/measure.json` |
| 4 | Settings › Agent at 1280: a 28 px run filter beside a 40 px search | UI-015 (`size="sm"` at the call site) | UI-040: the search to an Input size (drop `min-h-10`) | `crops/bands/y800/settings-agent-1280-1.png`; `probe/measure.json` |
| 5 | (Tooling) touch full-page shots rendered with a fine pointer | UI-019 tool | fixed here (`2c5f80a`) | `run1-fine-pointer/`, `stitch/` |

The coordinator's follow-up list already routes #1, as "calendar card actions … 40×40 on touch,
overflowing the month card". #2 to #4 are new.

## axe (375 and 1280)

| Rule | Impact | Before: screen × width / nodes | After | Where (after) |
|---|---|---|---|---|
| `color-contrast` | serious | 10 / 16 | **2 / 2** | Clerk's "Secured by" on sign-in at 375 and 1280 (UI-042) |
| `aria-hidden-focus` | serious | 2 / 8 | **0 / 0** | – (menus are non-modal, UI-013) |
| `target-size` | serious | 2 / 5 | **1 / 3** | schedule-month-1280: the cards' "Actions for …" buttons, 20 × 20 (known, UI-032). The week view's 2 → 0 is data (cards off screen). |
| **Total** | | **14 / 29** | **3 / 5** | no new rule |

**Fixed:**

- inbox "All" and the conversation's "Instagram": UI-002, UI-004;
- Billing's three: UI-002;
- the Disconnect action: UI-012;
- the menu's `aria-hidden-focus`: UI-013.

**Needs review** (nodes axe couldn't decide):

| Rule | Before | After | Why |
|---|---:|---:|---|
| `color-contrast` | 1,052 | 1,065 | By axe's reason: background image 559 → 559 (the sidebar texture); gradient 171 → 183; short text 156 → 163; overlap 113 → 111; partly obscured 49 → 47; pseudo-content 2 → 0; equal ratio 2 → 2. |
| `aria-hidden-focus` | 37 | 35 | menu-open 2 → 0 (non-modal); upgrade-dialog 6 → 7 (the skip link is one more `aria-hidden` sibling, UI-006); the rest unchanged |
| `aria-valid-attr-value` | 0 | 2 | menu-open at 375 and 1280: the non-modal trigger's `aria-controls` (axe "controlsWithinPopup", undecided) |
| **Total** | **1,089** | **1,102** | |

The net +13 contrast nodes are all on landing at 375: the illustrations the stitched capture now
draws. Its count moves with what the page's effects had played when axe ran (25 such nodes on a
direct run in either pointer mode); no task touched those components. Elsewhere the changes cancel
out (+10, −10; `probe/axe-review.json`):

- **Up (+10):** initials on identity gradients (UI-027) and gradient primary Buttons (UI-011),
  which axe can't measure. Schedule's agenda at 375 (+2, +3), the list at 1280 (+3), and Home's
  queue behind the Ask panel (+2).
- **Down (−10):** conversation, banner and banner-inbox at 375 (−2 each); home and
  template-gallery at 375, and sign-in at both widths (−1 each), where UI-002 and UI-004 changed
  colours that axe can now decide.

The palette guarantees ≥ 4.5:1 for every identity stop (UI-027's contrast script), so none of the
new ones are failures.

**By screen** (violations by rule, then "needs review" nodes; before → after):

| Screen | 375 violations | 375 review | 1280 violations | 1280 review |
|---|---|---|---|---|
| home | 0 → 0 | 11 → 10 | 0 → 0 | 37 → 37 |
| inbox-list | color-contrast 1 → **0** | 8 → 8 | color-contrast 1 → **0** | 41 → 41 |
| conversation | 0 → 0 | 5 → 3 | color-contrast 2 → **0** | 44 → 44 |
| comments | 0 → 0 | 0 → 0 | 0 → 0 | 27 → 27 |
| post-comments | 0 → 0 | 3 → 3 | 0 → 0 | 30 → 30 |
| automations | 0 → 0 | 1 → 1 | 0 → 0 | 28 → 28 |
| automation-editor | 0 → 0 | 5 → 5 | 0 → 0 | 32 → 32 |
| template-gallery | 0 → 0 | 7 → 6 | 0 → 0 | 37 → 37 |
| schedule-week | 0 → 0 | 1 → 3 | target-size 2 → **0** (data) | 28 → 28 |
| schedule-month | 0 → 0 | 1 → 4 | target-size 3 → 3 | 28 → 28 |
| schedule-list | 0 → 0 | 1 → 1 | 0 → 0 | 28 → 31 |
| composer | 0 → 0 | 3 → 3 | 0 → 0 | 31 → 31 |
| knowledge | 0 → 0 | 2 → 2 | 0 → 0 | 29 → 29 |
| ask-panel | 0 → 0 | 14 → 16 | 0 → 0 | 41 → 41 |
| ask-page | 0 → 0 | 0 → 0 | 0 → 0 | 28 → 28 |
| settings-connections | 0 → 0 | 4 → 4 | 0 → 0 | 28 → 28 |
| settings-ai | 0 → 0 | 3 → 3 | 0 → 0 | 27 → 27 |
| settings-workspace | 0 → 0 | 3 → 3 | 0 → 0 | 27 → 27 |
| settings-notifications | 0 → 0 | 3 → 3 | 0 → 0 | 27 → 27 |
| settings-billing | color-contrast 3 → **0** | 9 → 9 | color-contrast 3 → **0** | 33 → 33 |
| settings-agent | 0 → 0 | 3 → 3 | 0 → 0 | 27 → 27 |
| upgrade-dialog | 0 → 0 | 9 → 10 | 0 → 0 | 35 → 36 |
| menu-open | aria-hidden-focus 4 → **0** | 3 → 2 | aria-hidden-focus 4 → **0** | 30 → 29 |
| dialog-open | color-contrast 1 → **0** | 5 → 5 | color-contrast 1 → **0** | 32 → 32 |
| phone-drawer | 0 → 0 | 34 → 34 | – | – |
| toast | 0 → 0 | 4 → 4 | 0 → 0 | 27 → 27 |
| banner | 0 → 0 | 3 → 1 | 0 → 0 | 27 → 27 |
| banner-inbox | 0 → 0 | 5 → 3 | color-contrast 2 → **0** | 36 → 36 |
| landing | 0 → 0 | 41 → 54 | 0 → 0 | 43 → 43 |
| privacy | 0 → 0 | 1 → 1 | 0 → 0 | 1 → 1 |
| data-deletion | 0 → 0 | 2 → 2 | 0 → 0 | 2 → 2 |
| sign-in | color-contrast 1 → 1 | 2 → 1 | color-contrast 1 → 1 | 2 → 1 |

axe at 375 now runs on the coarse-pointer page for full-page screens. In the baseline it ran after
the fine-pointer capture. This changes no violation (`target-size` was 0 at 375 both times).

**Touch targets at 375** (`probe/touch-375.json`): no primitive is under 40 px with a coarse
pointer. The Switch (32 × 18) and ChipInput's remove button (20 × 20) are small boxes, but their
hit areas are extended by a pseudo-element to 56 × 42 and 40 × 40. Hand-built controls under 40 px
remain for the sweeps:

- the inbox chips and the Chats and Scheduled toggle, 24–28 px (UI-030);
- the "More views" and AI mode triggers, 26 and 32 px (UI-030);
- the analysis chip's pencil, 24 px (UI-030);
- the automation name field, 28 px (UI-034);
- the raw search fields, 36–38 px.

## Keyboard (1280)

The same method as the baseline: Tab from the top, each stop's indicator and whether it's
covered; each overlay opened with Enter, 25 Tabs, then Esc. The scratch spec added three
read-only measurements: whether a stop is inside `<main>`, where Tab lands after using the skip
link, and which stops draw focus with a box-shadow only.

| Page | Stops | First stop | Skip link | Skip link, then Tab | First content stop | Problems, before → after |
|---|---:|---|---|---|---:|---|
| Home | 30 → 31 | Workspace menu → **Skip to content** | none → **yes**, 2 px outline on `brand-strong` | "7 days" (in `<main>`) | 15 → 16 (2 with the skip link) | none → none. Six links still draw focus with the 50% halo (metric tile, View all, the three top posts, Open Inbox) |
| Inbox | 36 → 37 | → Skip to content | → yes | "All" | 15 → 16 | **search field: fill only → outline** (UI-007). "More views" still clipped by the chip row (stop 27) |
| Conversation | 50 → 51 | → Skip to content | → yes | "All" | 15 → 16 | As Inbox. **Reply box: no focus → the composer wrapper's outline** (UI-007; `keyboard/conversation-tab47-problem.png` shows it; the script only sees the field) |
| Schedule | 26 → 27 | → Skip to content | → yes | "Add to queue" | 15 → 16 | none → none. The list's post links draw a solid ring, not the outline |
| Composer | 41 → 42 | → Skip to content | → yes | "Schedule" | 15 → 16 | **"Add comment automation" under the sticky bar → clear** (UI-009). **Date and time: 7 stops without focus → 2** (the native segments now show the outline, UI-007; the picker buttons inside the native fields show none). **"Feed" tab panel: none → outline** (UI-015) |
| Settings › AI | 24 → 25 | → Skip to content | → yes | "Connections" | 15 → 16 | Phrase field: shown by its wrapper → by ChipInput's wrapper outline (UI-023). The settings tabs draw a solid ring, not the outline (known, UI-036) |

- **One focus recipe on the primitives:** every Button, menu item, segment, tab and dialog
  control shows the 2 px brand outline (inset on segments and menu items). The baseline had four
  looks.
  - The 3 px 50% halo is gone from every primitive, and the 4 px box-shadow on the sidebar
    control is gone.
  - The halo and rings that remain are call-site classes: Home's links (UI-038), Schedule's post
    links (UI-032), the settings tabs (UI-036) and the automations search (UI-034).
- The sidebar's Ask button still shows focus on a wrapper the script can't attribute (visible, as
  in the baseline).
- No trap on any page.

| Overlay | Focus on open | Tab stays inside | Focus after Esc, before → after | Task |
|---|---|---|---|---|
| Disconnect (alert dialog) | Cancel | yes | trigger ✓ → trigger ✓; indicator halo → outline | UI-011 |
| Upgrade dialog | Not now | yes | **`<body>` → "Upgrade for Auto" ✓** | UI-012 (`useReturnFocus`) |
| Template gallery | "All" | yes | **`<body>` → "New automation" ✓** | UI-007 (kept mounted) |
| Automation ⋯ menu | Duplicate | yes | trigger ✓; **highlight: none → outline** | UI-013 |
| Conversation AI mode menu | first item | yes | trigger ✓; **highlight: none → outline** | UI-013 |
| Ask panel (button) | the question box | yes | Ask button ✓ (unchanged) | – |
| Ask panel (Ctrl K) | the question box | – | the row ✓ (unchanged) | – |

## Reduced motion

The same sampling as the baseline: every animation and transition while each overlay opens and
closes, under `reduce` and `no-preference` (`motion/`).

| Overlay | Under `reduce`, before → after | `no-preference` now |
|---|---|---|
| Template gallery, upgrade dialog (Dialog) | 100 ms enter and exit → **nothing** (computed `animation-name: none`) | 200 ms in, 120 ms out, scrim in step |
| Disconnect (AlertDialog) | 100 ms → **nothing** | 200 / 120 ms |
| Automation ⋯ menu | 100 ms → **nothing** | 120 ms |
| Phone drawer (Sheet, 375) | fade 100 ms, slide 200 ms → **nothing** | 200 / 120 ms |
| Ask panel | 200 ms enter and exit → **unchanged** | 200 ms |
| Toast | nothing → nothing | 200 ms on the tokens (was sonner's 400 ms) |
| Page loads (Home, Inbox, Schedule, Knowledge) | skeleton pulse keeps running → **stops** | pulses |
| Buttons and menu triggers | `transition-all` 150 ms including `outline-*` → **gone**: named colour, border and filter transitions, off under reduce | 120 ms |

- Intended: UI-012 (overlay timing and `motion-reduce`), UI-013 (menus), UI-016 (Skeleton
  `motion-safe`), UI-011 (Button transitions), UI-001 (the reduced-motion safety net on overlay
  slots and skeletons), UI-024 (toast timing).
- **Still moving under `reduce`:**
  - the Ask panel: a custom `DialogPrimitive` without a `data-slot`, so the safety net misses it
    (known, UI-067);
  - ToggleGroup items' 120 ms colour fade, which isn't motion.
- The baseline's "the Ask panel's opt-out doesn't work" stands: computed `animation-name: enter`,
  0.2 s, under `reduce` (`probe/probe.json`).

## Known gaps left for Wave 3 (expected, not regressions)

From the coordinator's follow-up list, as seen in this run:

- **Overlay surfaces:** 54 overlay call sites still pass `border-line bg-panel` (21 also
  `shadow-xl`), so most menus and dialogs stay `panel`. The Disconnect dialog measures
  `rgb(31,31,31)`, not `overlay` #262626.
- **Raw fields:** about 27 raw `<input>` and `<textarea>` elements keep `border-line`, 14 px text
  and 36–38 px heights until they move onto Input. Where they sit beside primitives, edges and
  heights don't match (`probe/measure.json`):
  - the automations search, 36 px, 10% edge, beside 40 px Select triggers with a 40% edge at 375;
  - the composer's date and time, 14 px, beside a 16 px caption;
  - the inbox and connections searches;
  - ListView's Shift-times amount.
- **Touch patches and halos at call sites:** `min-h-10 md:…`, `size-10 md:…`, `ring-3
  ring-ring/50`, `outline-none` with a ring (the settings tabs).
- **Primary and destructive looks at call sites:**
  - `bg-brand-gradient text-white` overrides (Unschedule, Publish now);
  - `bg-danger-fill` on AlertDialogActions (they now render red, but should be
    `variant="destructive"`);
  - the hand-made destructive menu items.
- **Calendar card actions:** `icon-xs` with a call-site `size-5`; `target-size` at 1280, and
  unintended #1 at 768.
- **Primitives not yet adopted:**
  - Send (DSA decision pending);
  - DisabledReason (ThreadHeader, Composer, Connect WhatsApp);
  - Badge, Card, Alert, Meter and the compact states at their call sites;
  - AvatarBadge in ContactAvatar and AccountCard.
- **Layout carry-overs:**
  - the composer's ⋯ on its own row at 375 (UI-ISS-115);
  - "More views" clipped by the inbox chip row (UI-ISS-058);
  - long Knowledge source names truncated (UI-039);
  - the editor's preview above the steps (D-16);
  - the skip link over the sidebar logo at 1280 (UI-041);
  - "Upgrade for Auto" 22 px at 1280 (UI-036).
- **Ask panel and RunDetailSheet** animate under reduced motion (UI-067).
- **Toasts:** at 375 a toast covers the top bar while shown (UX-SH-04); the action button isn't
  40 px on touch (UI-024 follow-up).
- **Clerk:** "Secured by" contrast and "Primary" badge (UI-042, UI-070).

## Go / no-go for Wave 3

**Go.** Nothing blocks the area sweeps:

- no new axe rule and no remaining app-owned contrast violation;
- every overlay returns focus;
- reduced motion holds except the Ask panel (already UI-067's).

Asks for the sweeps, in order of value:

1. **UI-032 first item:** fix the calendar card actions (unintended #1). It's the only change that
   hides content (post titles at 768 on touch) and the last app-owned axe violation.
2. **UI-040:**
   - "Delete workspace" → `destructive-ghost` (#3);
   - the Agent run search to an Input size (#4).
3. **UI-039:** a shorter Always placeholder (#2).
4. **Sweep agents:** take touch "after" shots only with the fixed tool (on `develop` once this
   branch merges). Before-shots from task folders made earlier show desktop heights in full-page
   touch shots; compare touch heights against this checkpoint, not those.
5. **Tooling (small, any time):**
   - start the e2e API before `next build`, so the landing's ISR price isn't the fallback on a
     fresh stack;
   - stub `img.clerk.com` in ui-shots (or wait for it), so the account picture is stable.
