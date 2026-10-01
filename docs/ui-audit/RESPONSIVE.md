# Responsive layout audit (brief §17)

Read-only audit of `apps/web` on `feature/ui-audit` (commit `99f67be`), 1 October 2026. Nothing in
the app was changed. The standard is the spec's:

- **UX-SH-01…03**: the shell, the sidebar, phones and tablets, the page frame;
- **UX-INB-01**: the inbox at four widths;
- **UX-A11Y-05**: the layout holds at 200% zoom and at 360 px;
- **C-018, C-048, C-063, C-065 and C-066**;
- the definition of done, which asks for 360, 1024 and 1440 px.

WCAG 1.4.10 (reflow at 320 px) is checked too.

**Priorities.** P0: broken or unusable. P1: major. P2: polish. P3: minor.

**Result.** No P0 was found. No page is unusable at any width that was tried. The two P1s both
hit phones on the main screens:

- Home scrolls sideways (RSP-001).
- The conversation header hides the customer's name and overlaps its own controls below
  1024 px (RSP-002).

Everything else is polish: short viewports, toasts, hover-only controls on tablets, dialog
heights, the scrim, and mixed breakpoint sources.

| Priority | Count | IDs |
|---|---|---|
| P0 | 0 | none |
| P1 | 2 | RSP-001, RSP-002 |
| P2 | 7 | RSP-003 to RSP-009 |
| P3 | 4 | RSP-010 to RSP-013 |

## How it was checked

- The page sweep visited 21 pages, each at **360, 375, 768, 1024, 1280 and 1536 px**, against an
  isolated e2e stack (web on port 3117, API on 8117; see `ACCESSIBILITY.md` › How it was
  checked).
- A second pass loaded 15 app pages at **320 px** (WCAG reflow) and at **640 × 450 px** (a
  1280 × 900 window at 200% zoom).
- On each load the script:
  - measured `scrollWidth − clientWidth`;
  - listed elements that extend past the viewport and aren't inside a clipping scroller;
  - measured the touch targets;
  - took screenshots at 375, 768, 1280 and 1536 px.
- I also measured the conversation header's elements at 360–1280 px, and tabbed through
  Settings › AI at 375 × 700 px to look for focus hidden under sticky bars.
- **Not covered.** Real devices, iOS Safari's dynamic toolbar (the shell uses `dvh`, which should
  handle it), landscape phones, and data-heavy states (long names, 50 or more chips, 1,000-row
  tables). The sandbox workspace has 6 conversations and 3 posts.

## Breakpoint inventory

| Source | Breakpoint | Uses | Where |
|---|---|---|---|
| Tailwind `sm:` | 640 px | 135 | Marketing (14 files); dialog and sheet widths (`ui/dialog.tsx:64`, `sheet.tsx:65`); a few app files (automations 7, schedule 5, inbox 5, composer 4). **Not a spec width.** |
| Tailwind `md:` | 768 px | 261 | The shell switch (top bar and drawer below it, `AppShell.tsx:97`, `MobileNav.tsx:24`); phone density bumps (`size-10 md:size-8`, `h-10 md:h-9`); page padding |
| Tailwind `lg:` | 1024 px | 51 | Home cards in 3 columns (`HomeScreen.tsx:197`), Ask's thread rail (`AskPage.tsx:31`), comments grid, template gallery |
| Tailwind `xl:` | 1280 px | 25 | Settings two-column cards (C-066), the Knowledge test box sticky (`KnowledgePage.tsx:99`), automation editor right panel |
| Tailwind `2xl:` | 1536 px | 0 | none |
| Arbitrary | `min-[420px]` | 2 | Home metric tiles in 2 columns (`MetricTiles.tsx:113`, `:121`) |
| Arbitrary | `min-[1440px]` | 1 | Inbox details 300 → 320 px (`InboxShell.tsx:339`) |
| JS `useMediaQuery` | 768, 1024, 1280 | 3 | Inbox layout (`inbox-context.tsx:16-18`) |
| JS `useMediaQuery` | 1024 / 1280 | 1 | Sidebar collapse, at 1280 on inbox routes (`AppShell.tsx:73`) |
| JS `useMediaQuery` | 1440 | 2 | Inbox details open by default (`InboxShell.tsx:151`), schedule rail inline (`SchedulePage.tsx:125`) |
| JS `useMediaQuery` | 768 | 1 | Schedule agenda on phones (`SchedulePage.tsx:124`) |
| JS `matchMedia` | 48rem | 1 | Marketing phone menu closes when widened (`MobileMenu.tsx:66`) |
| Pointer | `pointer-coarse:` / `pointer-fine:` | 3 / 5 | Sidebar rows (`sidebar-styles.ts:10`, `:14`), Upgrade (`UsageCard.tsx:106`); Ask answer actions (`RunView.tsx:174`) |
| Container queries | none | 0 | |

**Consistency.**
- The spec's widths are 360, 768, 1024, 1280 and 1440 px. 1440 px exists only as an arbitrary
  value and in JS.
- The 640 px `sm:` breakpoint is used inside the app (dialog widths, a few rows) although the spec
  never names it. It is harmless, but it makes a third phone/tablet split.
- The shell's top-bar switch is CSS (`md`). The sidebar collapse and the inbox layout are JS,
  with a server default of `true` (desktop) in `use-browser-state.ts:6`. The numbers are
  duplicated as string literals in five places (RSP-009).

## The shell, by width

| Width | Shell | Observed |
|---|---|---|
| < 768 | 56 px top bar (logo, title, Ask, menu); the drawer (`w-[256px]`) is closed on load and closes on navigation | Matches UX-SH-02. Focus is trapped and returned (`ACCESSIBILITY.md`). The scrim is `bg-black/10`, not `/60` (RSP-008). The page title is duplicated by the inbox's own "Inbox" header. |
| 768–1023 | Sidebar collapsed to 64 px icons with tooltips, 16 px inset | Matches. A collapsed sidebar cannot be expanded below 1024 px (`onToggleCollapsed` is undefined), by design. |
| 1024–1279 | Expanded (232 px) on every page except the inbox, which stays collapsed below 1280 (C-018) | Matches. |
| ≥ 1280 | Expanded or collapsed, remembered (`socialhood:sidebar-collapsed`) | Matches. Ctrl+[ toggles it. |

## The inbox, by width (UX-INB-01, C-063)

| Width | Expected | Observed |
|---|---|---|
| ≥ 1440 | Sidebar 232 · list 320 · thread · details 320, open by default | Matches (`conversation-1536`). |
| 1280–1439 | Sidebar 232 · list 320 · thread · details 300, collapsed by default | Matches. The view chips are cut off after "Needs you" (RSP-012). |
| 1024–1279 | Sidebar 64 · list 320 · thread; details as a sheet | Matches. The thread header holds at 1024 px (name 156 px, no overlap). |
| 768–1023 | Sidebar 64 · list 300 · thread; details as a sheet | List and thread match. **The thread header loses the contact's name** (RSP-002). |
| < 768 | One pane; back button; details full screen | Matches, with the back button and a full-width details sheet. **The header loses the name** (RSP-002). At 320 px the header's More and the composer's Send are clipped (RSP-003). |

## Page by width

"ok" means the document doesn't scroll sideways (`scrollWidth ≤ clientWidth`). A cell can say
"ok" and still have clipping inside a pane; the conversation header is the example, which is why
RSP-002 and RSP-003 are separate findings. "–" means not run at that width. Schedule's 375 px run
caught the loading skeleton; its 360 px run loaded normally.

| Page | 320 | 360 | 375 | 640 (200%) | 768 | 1024 | 1280 | 1536 | under 40 px at 375 |
|---|---|---|---|---|---|---|---|---|---|
| Home | **+179px** | **+139px** | **+124px** | ok | ok | ok | ok | ok | 2 of 19 |
| Inbox (list) | ok | ok | ok | ok | ok | ok | ok | ok | 12 of 20 |
| Conversation | ok (header and composer clipped) | ok (name hidden) | ok (name hidden) | ok, cramped | ok (name hidden) | ok | ok | ok | 8 of 18 |
| Comments | ok | ok | ok | ok | ok | ok | ok | ok | 0 of 5 |
| Post (comments) | – | ok | ok | – | ok | ok | ok | ok | 1 of 27 |
| Automations | **+3px** | ok | ok | ok | ok | ok | ok | ok | 7 of 10 |
| Automation editor | – | ok | ok | – | ok | ok | ok | ok | 18 of 29 |
| Schedule | ok | ok | (loading) | ok | ok | ok | ok | ok | (loading) |
| New post | ok | ok | ok | ok, sticky bar takes 25% | ok | ok | ok | ok | 6 of 28 |
| Knowledge | ok | ok | ok | ok | ok | ok | ok | ok | 16 of 21 |
| Ask | ok | ok | ok | ok | ok | ok | ok | ok | 0 of 11 |
| Settings › Workspace | ok | ok | ok | ok | ok | ok | ok | ok | 1 of 15 |
| Settings › Connections | ok | ok | ok | ok | ok | ok | ok | ok | 6 of 21 |
| Settings › AI | ok | ok | ok | ok, save bar over content | ok | ok | ok | ok | 5 of 20 |
| Settings › Notifications | ok | ok | ok | ok | ok | ok | ok | ok | 5 of 13 |
| Settings › Billing | ok | ok | ok | ok | ok | ok | ok | ok | 0 of 10 |
| Settings › Agent | ok | ok | ok | ok | ok | ok | ok | ok | 0 of 14 |
| Marketing `/` | – | ok | ok | – | ok | ok | ok | ok | 1 of 6 (the skip link) |
| Privacy | – | ok | ok | – | ok | ok | ok | ok | inline links only |
| Terms | – | ok | ok | – | ok | ok | ok | ok | inline links only |
| Data deletion | – | ok | ok | – | ok | ok | ok | ok | inline links and FAQ (26 × 40) |

**Fits at every width:** the Settings two-column layouts (one column below 1280 px, C-066), the
Knowledge test box (below the content below 1280 px), the automation editor's right panel (tabs
above the steps below 1280 px), the template gallery and the billing tables. Billing's payment
history doesn't overflow at 320 px.

**Touch targets** are covered in `ACCESSIBILITY.md` (A11Y-009 and the touch-target table).

## Findings

### RSP-001 · P1 · Home scrolls sideways on phones (WCAG 1.4.10)
- **Problem.** Below 1024 px the three insight cards sit in a grid with no explicit column, so the
  implicit column is sized by the cards' min-content. The longest top-post caption is a
  `truncate` (nowrap) line. It doesn't shrink, the column becomes 483 px wide, and the page
  scrolls sideways.
  - The cards' right halves sit off-screen: "View all", the sentiment counts, "2 of 6 analysed".
  - So does the bottom of the page.
- **Evidence.**
  - Document overflow: +124 px at 375, +139 px at 360 and +179 px at 320. The full-page screenshot
    at 375 px is 499 px wide.
  - Offending elements: `section` "What customers asked about" (w = 483) and the top-post caption
    span (w = 389).
  - Sources: `components/home/HomeScreen.tsx:197` (`grid gap-3 lg:grid-cols-3`) and
    `components/home/TopPostsCard.tsx:59-63` (the flex row and the `truncate` caption).
- **Affected.** `HomeScreen.tsx`, `TopPostsCard.tsx`, `SentimentCard.tsx`, `TopIntentsCard.tsx`.
- **Recommendation.**
  - Use `grid grid-cols-1 gap-3 lg:grid-cols-3`. `grid-cols-1` is `minmax(0, 1fr)`, which lets
    `truncate` work.
  - Add `min-w-0` on the three `<section>`s.
  - `MetricTiles.tsx:113` already uses `grid-cols-1` and doesn't overflow.

### RSP-002 · P1 · The conversation header hides the customer's name below 1024 px and overlaps its controls
- **Problem.** The name `<h2>` truncates inside a flex row next to the `shrink-0` reply-window
  chip ("Window: 23h left"). At 360, 375 and 768 px the row is narrower than the chip, so:
  - the name collapses to **0 px**;
  - the chip spills right, **over the AI mode menu**;
  - only "@c…" is left.

  On phones and tablets, the main screen never says whom you are replying to; the composer
  placeholder carries only the first name.
- **Evidence.**
  - Measured:
    - at 360 px: name 0 px, chip 120–222 px, AI menu from 139 px (82 px overlap);
    - at 375 px: 67 px overlap;
    - at 768 px: 59 px overlap;
    - at 1024 px: name 156 px, no overlap.
  - Screenshots `conversation-375`, `conversation-768` and `thread-header-375`.
  - Source: `components/inbox/ThreadHeader.tsx:92-96`, with the chip from `ReplyWindowChip.tsx`.
- **Recommendation.**
  - Below `md`, move the chip to the second line beside the handle, or show a dot-only chip.
  - Give the name `min-w-[5rem]` and the chip `min-w-0 truncate`.
  - At 768–1023 px the list and the thread share the width, so apply the same rule there, or
    switch on the thread pane's width with a container query (`@container`).

### RSP-003 · P2 · Clipping in the conversation at 320 px (WCAG reflow width)
- **Problem.** At 320 px the inbox frame's `overflow-hidden` clips the header's More (⋮) button
  and the composer's Send button at the right edge. The spec's own minimum is 360 px, where this
  doesn't happen, but WCAG 1.4.10 tests at 320 px. Automations overflows by 3 px at 320 px (the
  "New automation" button).
- **Evidence.**
  - Screenshot `w320-inbox`.
  - Reflow pass: `automations@320` overflows by 3 px, caused by `AutomationsPage.tsx:298`.
  - Sources: `InboxShell.tsx:97` (`overflow-hidden`), `ThreadHeader.tsx:104-163`,
    `Composer.tsx:311-422`.
- **Recommendation.**
  - Let the composer toolbar wrap (`flex-wrap`), or move Polish, heart and schedule into a "More"
    menu below 360 px.
  - In the header, hide the details toggle into More below 360 px.
  - Let the page-header row wrap (`flex-wrap`) in `PageFrame.tsx:31`.

### RSP-004 · P2 · Toasts sit at the bottom on phones; the spec puts them at the top
- **Problem.** UX-SH-04 says "Toasts use sonner … at the bottom right (top on phones)". The
  Toaster is fixed at `bottom-right`. On phones, sonner stacks full width at the bottom, over the
  composer, the Send button and the sticky action bars. That is exactly where an "Archived · Undo"
  or "Message failed" toast lands.
- **Evidence.** `app/layout.tsx:34` (`<Toaster theme="dark" position="bottom-right" />`).
- **Recommendation.** Choose the position with a media query: `top-center` below 768 px. A small
  client wrapper using `useMediaQuery` works, or sonner's `mobileOffset` with a top position.

### RSP-005 · P2 · Hover-only controls on touch tablets
- **Problem.** At 768 px and wider, an automation row's bulk-select checkbox and reorder handle
  are `opacity-0` until hover. On an iPad (a coarse pointer at md widths) there is no hover, so
  bulk pause can't be discovered and the drag handle is invisible though still tappable. Keyboard
  focus does reveal them.
- **Evidence.** `components/automations/AutomationRow.tsx:142` and `:158`
  (`md:opacity-0 md:group-hover/row:opacity-100`).
- **Recommendation.** Use the pattern already in `RunView.tsx:174`:
  `pointer-fine:opacity-0 pointer-fine:group-hover/row:opacity-100`, so touch devices always see
  them.

### RSP-006 · P2 · Sticky bars take over short viewports (200% zoom, landscape)
- **Problem.** At 640 × 450 px (1280 × 900 at 200% zoom):
  - The post composer's sticky action bar (three buttons plus two lines of reasons) and the 56 px
    top bar leave about 280 px of 450 px for the form.
  - On Settings, the top bar and a save bar that only says "All changes saved" cover about
    120 px.
  - The same bars hide focused controls (`ACCESSIBILITY.md` A11Y-008).
- **Evidence.** Screenshots `zoom200-schedule_new`, `zoom200-settings_ai` and `settings-ai-375`.
  Sources: `SaveBar.tsx:69`, `PostComposer.tsx:703` (the sticky action bar), `MobileNav.tsx:24`.
- **Recommendation.**
  - Make the bars `static` when the viewport is short: `[@media(max-height:500px)]:static`.
  - Hide the save bar while it is clean on phones.
  - Collapse the composer's "why it's disabled" lines into a single line with a tooltip.

### RSP-007 · P2 · Some dialogs have no height limit
- **Problem.** `DialogContent` centres with `translate(-50%, -50%)` and has no `max-h` or
  overflow by default. Most dialogs add `max-h-[calc(100dvh-2rem)] overflow-y-auto`, but five
  don't. On a short viewport (landscape phone, 200% zoom) their title and actions can sit
  off-screen with no way to scroll to them:
  - `billing/UpgradeDialog.tsx:78` (the plan-limit dialog that every 402 opens);
  - `inbox/ScheduledList.tsx:210`;
  - `schedule/ListView.tsx:306`;
  - `schedule/MoveToDialog.tsx:68`;
  - `inbox/AttachmentView.tsx:54` (the image has `max-h-[80dvh]`, but its padding doesn't fit).
- **Evidence.** Static. The shared default is in `components/ui/dialog.tsx:64`.
- **Recommendation.** Put `max-h-[calc(100dvh-2rem)] overflow-y-auto` in the primitive's default
  classes, and drop the per-dialog copies.

### RSP-008 · P2 · The drawer and dialog scrim is `black/10`, not the spec's `black/60`
- **Problem.** UX-SH-02 specifies the phone drawer "over a bg-black/60 scrim". The primitives use
  `bg-black/10` with a slight blur, so the page behind the drawer, a sheet or a dialog stays
  nearly at full contrast. The Ask panel and the run detail use `/60`. Two scrims now coexist.
- **Evidence.**
  - `ui/sheet.tsx:40`, `ui/dialog.tsx:42`, `ui/alert-dialog.tsx:39`, against `AskPanel.tsx:82`
    and `AgentSettingsPage.tsx:394`.
  - Runtime: the drawer overlay's background is `oklab(0 0 0 / 0.1)`.
- **Recommendation.** One overlay class, `bg-black/60`, in all three primitives.

### RSP-009 · P2 · Breakpoints come from three sources, with literals repeated
- **Problem.**
  - Layout switches are split between CSS (`md:` for the shell) and JS `useMediaQuery` (sidebar
    collapse, inbox layout, schedule agenda and rail).
  - The JS hook returns `true` on the server (`use-browser-state.ts:6`). Any JS-driven component
    present during hydration first renders its desktop variant on a phone, then switches.
  - The widths are string literals in `inbox-context.tsx:16-18`, `AppShell.tsx:73`,
    `InboxShell.tsx:151` and `SchedulePage.tsx:124-125`.
- **Evidence.** The inventory above.
- **Recommendation.**
  - Export `BREAKPOINTS = { md: 768, lg: 1024, xl: 1280, wide: 1440 }` from one module, used by
    the hook callers.
  - Add `--breakpoint-wide: 90rem` to `@theme`, so `wide:` replaces `min-[1440px]:`.
  - Prefer CSS (`hidden md:flex`) where a component only changes visibility.
  - Pass `serverValue` deliberately where a phone-first default is safer.

### RSP-010 · P3 · Loading replaces the whole shell
- **Problem.** While `GET /v1/workspaces` loads, the workspace layout renders a full-page
  skeleton with no top bar or sidebar. When it resolves, the shell pops in and the page shifts. On
  a slow phone this was visible: the Schedule run at 375 px captured only the skeleton after
  2.5 s.
- **Evidence.** `app/(app)/w/[slug]/layout.tsx:23` and `PageSkeleton.tsx`. Screenshot
  `schedule-375`.
- **Recommendation.** Render the shell frame (top bar and sidebar skeleton) around the loading
  state.

### RSP-011 · P3 · Header rows wrap awkwardly on phones
- **Problem.**
  - In Home's range control, "30 days" wraps onto two lines inside its segment at 375 px.
  - On the new-post page, the More (⋮) menu drops to its own line under the title.
  - The inbox shows "Inbox" twice: in the top bar and in the list header.
- **Evidence.** Screenshots `home-375` and `schedule-new-375`. Sources: `RangeControl.tsx`,
  `PostComposer.tsx` (header), `ListHeader.tsx:92`.
- **Recommendation.**
  - Add `whitespace-nowrap` on the range segments, or "30d" labels below `sm`.
  - Keep the composer's actions on the title row.
  - Make the list's `<h1>` `sr-only` on phones, since the top bar already names the page.

### RSP-012 · P3 · Scrolling rows give no visual cue
- **Problem.** The inbox view chips and the settings tab row scroll sideways with the scrollbar
  hidden. The options past the edge ("Leads", "AI handled", "More"; "Workspace", "Notifications",
  "Billing", "Agent" at 375 px) look absent.
- **Evidence.** `ListHeader.tsx:161` (`[scrollbar-width:none]`), `settings/layout.tsx:22`.
  Screenshots `conversation-1280`, `inbox-375` and `settings-ai-375`.
- **Recommendation.** Add an edge mask (the `mask-image` pattern from `AppSidebar.tsx:113`).
  Below 400 px, consider a "More" chip for the views.

### RSP-013 · P3 · The collapsed credits ring reads as a loading spinner
- **Problem.** In the collapsed sidebar (768–1279 px), the AI credits meter is a 28 px ring with
  a short brand arc. At low usage it looks like a spinner.
- **Evidence.** `UsageCard.tsx:50-76`. Screenshots `inbox-768` and `schedule-768`.
- **Recommendation.** Show the percentage inside the ring, or use a short vertical bar.
