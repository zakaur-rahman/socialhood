# UI-072: final visual QA, against Wave 3 and the baseline

The app at `71219cd` is develop with every UI task merged except UI-071 (docs only) and this one. It
is compared with the [Wave 3 checkpoint](wave-3.md), the [Wave 1 checkpoint](wave-1.md) and the
[baseline](baseline.md), using the same tool and passes. UI-043's method is followed, with two
additions the plan asks for:
- **320 px reflow;**
- **640 × 450**, a 1280 × 900 window at 200% zoom.

Each visible change since Wave 3 is classified:
- **intended:** named with the task that made it;
- **unintended:** filed, here with the fix made in this task.

Issue numbers are from [UI_AUDIT.md](../UI_AUDIT.md).

## Summary

**Go for UI-073.** The run found three unintended changes, all small. All three are fixed on this
branch and re-checked.

1. **The automation editor's trigger ran past its card.**
   - UI-064's longer labels ("Instagram comment keyword", "Any Instagram comment", "Instagram DM
     keyword") need about 640 px in a row.
   - The page scrolled sideways by 33 px at 768 and by 69 px at 640 × 450. At 1280 and 1536 the
     last label was clipped by its card.
   - **Fixed:** the row is now a container query (`@2xl`), so the three stack wherever the step is
     narrower than 672 px.
   - **Re-checked:** no sideways scroll at 640, 768 or 1280, and the labels sit inside the card.
2. **Post detail's title read "Photo from Yesterday"** (UI-056).
   - `formatDay` capitalises Today and Yesterday for labels on their own, and the title used it
     mid-sentence.
   - **Fixed:** the title now reads "Photo from yesterday", with a unit test.
3. **Ask's starter questions centred when they wrapped** (since UI-040, at Wave 3 too). A
   `<button>` centres its text; it now has `text-left`.

The passes:
- **axe:** 2 violations (2 nodes), the same as Wave 3, both Clerk's own "Secured by" text on
  sign-in. "Needs review" fell from 1,090 to 912.
- **Keyboard:** on all ten pages, the skip link is the first stop. Every stop matches
  `:focus-visible` and shows an indicator, and none is covered by another element. Wave 3's one gap,
  the Ask button on Home with no outline, is gone. All four overlays move focus in, keep Tab
  inside and return focus to their trigger.
- **Ctrl+K then Esc** closes the Ask panel 40 times out of 40, on Home and Inbox, settled and fast.
- **Reduced motion:** dialogs, alert dialogs, menus, the phone drawer and **the Ask panel** open and
  close without animating. The Ask panel was Wave 3's known exception (UI-067).
- **Reflow:** at 320 × 640 and 640 × 450 no main screen scrolls sideways (after fix 1). At 640 × 450
  the phone top bar sits in the page instead of sticking (`short:static`, C-073).
- **Tool:** one small change. In `ui-shots/options.ts`, 640 px now renders 450 tall, so
  `UI_SHOTS_WIDTHS=640` is the 200% zoom check.

## The run

| | |
|---|---|
| Date | 2026-10-21 |
| Code | `71219cd` on `feature/ui-qa-final`; the re-check adds the three fixes. |
| Stack | The isolated e2e stack (`scripts/e2e-stack.mjs --serve`): a production build on port 3132, the API on 8132, database `socialhood_e2e_qa_final`, Valkey db 8. It uses the same sandbox, fake AI, Dodo, email and push as before, and Clerk's development instance. |
| Browser | Chromium (Playwright 1.63.0), dark, device scale factor 1. Touch emulation runs below 1024 px. Heights are 812, 1024, 800 and 864, plus 640 at 320 and 450 at 640. The tool checks `pointer` on every shot, and all passed. |
| axe | axe-core 4.13.0, the same tags, at 375 and 1280. |
| Shots | `pnpm shots:ui` with no `--grep` at 375, 768, 1280 and 1536: 125 shots, 126 tests with sign-in setup, 10.5 min, no retries. Reflow: 320 and 640, 64 shots, 4.2 min. |
| Passes | `UI-072.check.spec.ts` (kept in `design/ui-qa/coordination/`): keyboard on ten pages, four overlays, Ctrl+K ×10 in four runs, reduced motion on five overlays, reflow at 320 × 640 and 640 × 450 on ten pages, 6 tests. |
| Data | The same seed (QA Shop, QA Reconnect) on a fresh database; the passes use fresh e2e workspaces with a sandbox account. |

**Where the images are** (outside the repository):
`C:\Users\zakau\social-auto\design\ui-qa\final\`

- `<screen>-<width>.png`, `axe/`, `axe.json`, `axe-summary.md`, `meta/`, `shots.json`: the run.
- **`diff/index.html`**: the comparison against `../checkpoint-wave3`.
- **`diff-baseline/index.html`**: the comparison against `../baseline`.
- `../final-reflow/`: the 320 and 640 shots.
- `../final-recheck/`: the automation editor at 640, 768 and 1280 after fix 1.
- `passes/`:
  - `keyboard-pages.json`, `keyboard-overlays.json`, `keyboard-ctrlk-x10.json`,
    `motion-reduce.json`;
  - `reflow-320x640.json` and `reflow-640x450.json`, with a viewport picture of each page.
- `crops/`: the trigger row at 768 and 1280, before and after fix 1.

### Reading the comparison

All 125 shots differ from Wave 3 and from the baseline, as before. Dynamic text (dates, relative
times, the greeting, AI credits, the sandbox handle) changes between runs. The changes since Wave 3
are large because Wave 4 rebuilt whole screens: sign-in at 59%, Settings › Agent at 56%, Knowledge
at 46%, Home at 37%.

What doesn't come from the code:
- **Pictures:** the tool replaces remote pictures with a grey crossed tile on purpose, so post
  thumbnails and the sign-in laptop show the tile.
- **Clerk:** Clerk's development instance adds its "Development mode" strip under the sign-in card.
- **Dates:** the seeded posts and messages carry today's dates, so day labels moved from 7–13 Oct
  to 15–21 Oct.

**Method and its limits:**
- **Read as Wave 3 and final side by side:** every screen whose diff ranked highest, at 1280 and
  375. That covers Home, Inbox and the conversation, Comments and post detail, Knowledge, the
  automation editor, Schedule, Ask, the six Settings pages and sign-in. The automation editor was
  also read at 768.
- **Checked by machine rather than by eye:** the 768 and 1536 shots were checked for sideways scroll
  from their pixel widths (a full-page shot is as wide as the document) and spot-read through the
  diff ranking.
- Wave 4's changes are class-level (primitives, tokens, copy), so a change seen at 375 or 1280
  repeats at the other widths.

## Changes by screen (since Wave 3)

All intended unless marked. The task is in brackets.

- **Shell:**
  - The Ask card gives the name its own line, with "Your AI assistant" and Ctrl K beside it
    (UI-076).
  - Pages fill the width beside the sidebar, and the inbox panel is inset on all four sides
    (UI-076, C-074).
  - Pane titles are 18 px (UI-069).
- **Home:**
  - The finished checklist collapses to "You're all set" (UI-058).
  - The gap banner reads "Open conversation" and "Add answer"; the queue reads "Open inbox",
    "Review and send" and "Open conversation" (UI-068).
  - Queue row actions are secondary instead of gradient (UI-059, D-10).
- **Inbox:**
  - The view chips gain "Needs you" (UI-052) and say "Handled by AI" (UI-068).
  - The keyboard shortcuts button (UI-053).
  - "AI draft" with Draft again, Insert and Send (UI-050).
  - AI polish is the `soft` Button (UI-051, C-073).
  - The list and details panes resize. Their handles show only on hover and focus (UI-078).
- **Comments:**
  - Each post card shows "N need a reply" and the grid has a sort (UI-055, D-11).
  - The grid gains columns at `xl` and `2xl` (UI-076).
  - Post detail has a new layout with the "‹ Comments" back link (UI-056, UI-065, D-16).
  - **Unintended, fixed:** "Photo from Yesterday" (fix 2).
- **Knowledge:**
  - Gaps first, then sources as a table, then brand voice, with the test box beside them (UI-057).
- **Automations and the editor:**
  - "Instagram" in the trigger labels, plus Connect Instagram (UI-064).
  - The "‹ Automations" back link, with the side panel after the steps below 1280 (UI-065, D-16).
  - **Unintended, fixed:** the trigger row overflowed (fix 1).
- **Schedule:** the reworked flows (UI-054) and the 18 px pane title on phones (UI-069).
- **Ask page:** the 18 px pane title (UI-069).
  - **Unintended, fixed:** centred wrapped starters (fix 3).
- **Settings:**
  - Tab labels match the page titles, with no breadcrumb or eyebrow (UI-060, D-08).
  - The save bar shows only when needed (UI-060, D-08).
  - Agent's six tiles became one sentence (UI-060, D-08).
  - Connections: Disconnect stays visible, with "Delete account and data" in the ⋯ menu (UI-061,
    UI-062, D-09).
  - Billing: "Start 7-day trial" and the plan cards (UI-059, UI-063).
  - Quota tiles no longer overlap (UI-077).
  - The AI-mode segments show their selection (UI-077).
- **Sign-in and sign-up:** the split layout with the product panel (UI-079), with Clerk's standard
  card on the app theme (#107 to #109).
- **Copy everywhere:** one name per concept, sentence case and UK spelling (UI-068).

### Unintended changes, filed and fixed

| # | Screen, widths | What | Cause | Fix (this branch) |
|---|---|---|---|---|
| 1 | automation-editor: 768 and 640 (page scrolls 33 and 69 px); 1280 and 1536 (clipped in its card) | The trigger's last segment runs past the step | UI-064 lengthened the labels; the row switched on at `sm` (window width), not at the step's width | `@container` with `flex-col @2xl:flex-row` in `WhenStep.tsx`; re-shot at 640, 768 and 1280 |
| 2 | post-comments, every width | "Photo from Yesterday" | The title used `formatDay`'s standalone label mid-sentence (UI-056) | Lower-case relative days in the title, with a unit test |
| 3 | ask-page and ask-panel, 1280 | Wrapped starter questions centred | A `<button>` centres its text (since UI-040) | `text-left` on the starter button |

Not fixed, minor:
- At 375, Settings › AI's "AI replies by account" card puts the "1 connected" chip beside the title,
  so the description wraps in a narrow column. It is readable; left for UI-073 to judge.

## axe (375 and 1280)

| Rule | Impact | Baseline: screens × widths / nodes | Wave 1 | Wave 3 | Final | Where (final) |
|---|---|---|---|---|---|---|
| `color-contrast` | serious | 10 / 16 | 2 / 2 | 2 / 2 | **2 / 2** | Clerk's "Secured by" on sign-in at 375 and 1280 |
| `aria-hidden-focus` | serious | 2 / 8 | 0 / 0 | 0 / 0 | **0 / 0** | – |
| `target-size` | serious | 2 / 5 | 1 / 3 | 0 / 0 | **0 / 0** | – |
| **Total** | | **14 / 29** | **3 / 5** | **2 / 2** | **2 / 2** | no new rule |

**Every screen reads 0 violations at both widths except sign-in.** Sign-in's single node is Clerk's
branding line, internal markup with no element key (`cl-internal-…`).
- Wave 3 routed it to UI-070, which didn't change it: the lock is about our tokens.
- It goes away when Clerk's branding is turned off on a paid Clerk plan. Otherwise it could be
  targeted with a nested selector under Clerk's `footer` element. That's an owner FYI below.

**Needs review** (axe couldn't decide):

| Rule | Baseline | Wave 1 | Wave 3 | Final |
|---|---:|---:|---:|---:|
| `color-contrast` | 1,052 | 1,065 | 1,045 | 892 |
| `aria-hidden-focus` | 37 | 35 | 43 | 18 |
| `aria-valid-attr-value` | 0 | 2 | 2 | 2 |
| **Total** | **1,089** | **1,102** | **1,090** | **912** |

- **`color-contrast`**, by axe's reason: background image 463, short text 144, gradient 140,
  overlap 95, partly obscured 48, equal ratio 2. The tool's grey picture tiles account for most of
  "background image".
- **`aria-hidden-focus`:** 2 nodes on each of 9 open-modal screens. These are Radix's focus-guard
  spans around modal content, the case UI-066 established as correct. That is fewer than Wave 3's
  43; since then ModalInert (UI-066) makes the background `inert` while a modal is open.

## Keyboard (1280)

**Pages:** ten pages, Tab from a fresh load through up to 45 stops each.

| Page | First stop | Stops | Without an indicator | Covered |
|---|---|---:|---|---|
| Home | Skip to content | 27 | none | none |
| Inbox | Skip to content | 25 | none | none |
| Comments | Skip to content | 19 | none | none |
| Schedule | Skip to content | 23 | none | none |
| Automations | Skip to content | 24 | none | none |
| Knowledge | Skip to content | 17 | none | none |
| Ask | Skip to content | 23 | none | none |
| Settings › AI | Skip to content | 24 | none | none |
| Settings › Billing | Skip to content | 23 | none | none |
| Settings › Connections | Skip to content | 30 | none | none |

- Every stop matches `:focus-visible`.
- **What counts as an indicator:** a solid 2 px or wider outline, a brand ring, or an outline drawn
  by a wrapper within four levels. Examples of the wrapper case are the Ask card and the composer
  shell.
- **Covered** means the element at the stop's centre is neither the stop nor inside it. That
  includes being under a sticky bar.
- Wave 3 listed the Home Ask button with no outline; it now has one.

**Overlays:**

| Overlay | Focus moves in | Tab stays inside | Esc returns focus to the trigger |
|---|---|---|---|
| Template gallery (dialog) | ✓ | ✓ | ✓ |
| Ask panel (sheet) | ✓ | ✓ | ✓ |
| Disconnect (alert dialog) | ✓ | ✓ | ✓ |
| Workspace menu | ✓ | n/a (menu) | ✓ |

**Ctrl+K then Esc**, 10 rounds each: Home settled 10/10, Home fast 10/10, Inbox settled 10/10,
Inbox fast 10/10. "Settled" waits 350 ms for the open animation; "fast" doesn't.

## Reduced motion

With `prefers-reduced-motion: reduce`, nothing with a finite iteration count is running on open or
on close for:
- the template gallery (dialog);
- Disconnect (alert dialog);
- the workspace menu;
- **the Ask panel**;
- the phone drawer at 375.

The Ask panel, Wave 3's known exception, is fixed by UI-067 (SheetContent). Spinners and ambient
loops were checked in Wave 3 and their code is unchanged.

## Reflow

| Size | Pages | Sideways scroll | Phone top bar |
|---|---|---|---|
| 320 × 640 | 10 (and 64 tool shots at 320 and 640) | none | sticky |
| 640 × 450 (1280 × 900 at 200%) | 10 | none after fix 1 (the automation editor was +69 px) | `static`, in the page (C-073) |

**Caveat:** the tool emulates touch below 1024 px, so its 640 shots use touch-height controls. That
is stricter than a desktop at 200% zoom, which keeps a fine pointer. The check spec's 640 × 450 pass
uses the default fine pointer, and both agree.

## Known gaps still open (expected, not regressions)

- **Clerk's "Secured by" contrast** (above). It is third-party branding; see FYI 1.
- **Phone top bar plus page H1:** on phones the top bar names the section and the page repeats it as
  its H1 ("Comments" twice). This was already the case at Wave 3 and is the shell's design (UX-SH-01,
  D-05). Inbox hides its own H1 on phones (UI-069); the other pages don't.
- **Clerk's account picture** is a remote image. Before the tool's swap it sometimes hadn't loaded
  (Wave 3); now it shows the swap tile or the initials.

## Owner FYIs to confirm

1. **Clerk's "Secured by" line** fails contrast, on Clerk's own markup. Options:
   - turn off Clerk branding (a Clerk plan setting), which removes the line;
   - or target it under Clerk's `footer` element in `lib/clerk-appearance.ts`.
2. **Max's price while "Coming soon":** Billing's plan card shows Max with a monthly price. The
   e2e fake Dodo gives every product ₹999, which is why it matches Pro here. The public pricing
   page shows "Coming soon" in place of Max's price. Decide whether the in-app card should do the
   same. (`settings-billing-1280.png`)
3. **The trigger stacks on desktop too** (fix 1): at 1280 and 1536 the three triggers are now a
   column, because with the side panel beside it the step is about 560 px wide. A row would need
   shorter labels. UI-064 chose to name Instagram in each one.

## Go / no-go for UI-073

**Go.** Nothing must be fixed first: the three unintended changes are fixed on this branch and
re-checked. The axe count is at Wave 3's floor, and the keyboard, reduced-motion and reflow passes
are clean.

**For UI-073:**
- check the programme's §H against this report;
- the two FYIs above;
- the Settings › AI chip at 375.
