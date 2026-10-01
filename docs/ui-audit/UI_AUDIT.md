# UI audit: synthesis

The consolidated result of the eight area audits of `apps/web`, read together with BUILD_SPEC §4
and CONFLICTS.md. Documentation only: no code was changed.

- **Baseline:** `99f67be` (branch `feature/ui-audit`), audited 2026-10-01.
- **Area audits** (details, evidence and measurements live there; this file links, it doesn't
  copy):
  [COLOR_SYSTEM.md](COLOR_SYSTEM.md) (COL-) ·
  [TYPOGRAPHY.md](TYPOGRAPHY.md) (TYP-) ·
  [SPACING.md](SPACING.md) (SPC-, RAD-, SHD-) ·
  [COMPONENT_AUDIT.md](COMPONENT_AUDIT.md) (CMP-) ·
  [ACCESSIBILITY.md](ACCESSIBILITY.md) (A11Y-) ·
  [RESPONSIVE.md](RESPONSIVE.md) (RSP-) ·
  [MOTION.md](MOTION.md) (MOT-) ·
  [UX_AUDIT.md](UX_AUDIT.md) (UX-, VH-).
- **Companion documents:** [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) (the target system),
  [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) (tasks UI-001…) and
  [AGENT_CONTEXT.md](AGENT_CONTEXT.md) (what every implementing agent reads first).

**Result.** 193 source findings consolidate into **116 canonical issues**: **0 P0, 24 P1, 67 P2,
25 P3**. **17 owner decisions** are needed (§D); 11 tasks wait on them, everything else can start.

---

## A. Executive summary

### What is good

- **The token foundation holds.** About 90% of colour usages go through tokens, no mockup colour
  leaked into code, and the only hex literals mirror tokens for consumers that can't read CSS
  variables. `tokens.ts`, `tokens.test.ts` and `/dev/tokens` come from one list. The danger trio
  (`danger`, `danger-fg`, `danger-fill`) and `brand-fg` are well designed, and UX-TOK-02's
  contrast fixes hold wherever the tokens are used.
- **Spacing is mostly on the grid.** 82% of spacing values are whole 4 px steps; page padding,
  dialogs and sheets are consistent.
- **One type family, loaded correctly, three weights.**
- **Keyboard and screen-reader basics work.** The global focus outline passes on every surface;
  Radix traps and returns focus; every icon-only button is named; conversation rows are links with
  j/k and arrow keys; the inbox's live regions follow UX-A11Y-03; axe found little.
- **The spec's own motions are exact** (live message, suggestion bar, Send) and the two loops
  honour reduced motion.
- **No P0.** Every core flow works at every width tried; only Home overflows on phones.
- **UX strengths worth copying:** disabled buttons that say why (the composer checklist), typed
  confirmations that list what is deleted and kept, specific honest feedback, skeletons shaped
  like the content, Home's rules instead of scores, and Ask's hand-off that keeps a person in
  control ([UX_AUDIT §10](UX_AUDIT.md#10-what-already-works-well)).

### What is inconsistent

- **States are where the system breaks.** Hover is written six ways and the 58 primary CTAs have
  none; focus is drawn five ways; disabled four ways; the selected bar five ways.
- **Families are rebuilt per screen.** 58 hand-built primary buttons and five destructive styles;
  77 ad-hoc badges in 39 shapes and 8 copies of the tone map; 85 hand-written cards in 46
  signatures; 9 meters, 5 filter-chip and 4 segmented-control implementations, 6 search fields,
  3 copies of the form `Field` and 3 chip-list inputs.
- **Two design languages from two mockup sets.** The settings redesign (C-066) uses 16 px card
  corners, a 30 px title, a breadcrumb and a 0.12em eyebrow; the rest of the app uses 12 px
  corners and a 24 px title.
- **The primitives are stock shadcn with light-theme defaults:** a 10% scrim, 10% shadows, 100 ms
  dialogs, a 50% focus halo and no touch size. 55 overlay call sites and 142 control call sites
  patch them.
- **Type:** 16 font sizes, 11 px (the third most used) has no token, and one role takes different
  sizes in different features.
- **Words:** seven concepts have two to five names each ([UX_AUDIT §5](UX_AUDIT.md#5-terminology-table)).

### What needs improvement, in order

1. **Accessibility of states:** menu highlight, focus indicators, control edges, the remaining
   text-contrast failures and placeholders, reduced motion, and touch size on phones.
2. **The two main phone screens:** Home overflows and the thread header loses the contact's name.
3. **Data safety:** unscheduling without asking, lost edits, a one-tap heart, Ask overwriting a
   draft.
4. **Overlay elevation:** overlays are the same colour as the cards under them, over a scrim that
   doesn't dim.
5. **Consolidation into primitives:** a real primary and destructive Button, Badge, Card, Field,
   Meter, Alert and Table.
6. **Hierarchy:** one primary per view; the settings header that names the page four times.

**Strategy.** Fix at the source. Waves 0–2 of the plan (the tokens, the primitives in
`components/ui/*`, the new shared components and a few small call-site fixes) close or start about
half of the issues, including 22 of the 24 P1s (UI-ISS-004 and 008 also need decisions D-01 and
D-06; 015 and 024 wait for D-14 and D-11). Each feature area then adopts the primitives in one
sweep, and screen-level UX fixes follow. Nothing is redesigned: every change implements an approved
rule (the spec, WCAG 2.2 AA, a CONFLICTS decision) or is listed in §D for the owner.

**Performance.** No significant problems. The costliest effect is the full-viewport
`backdrop-blur` behind every dialog and sheet during their animation (low-end phones); it goes with
the 60% scrim. The save bar's blur re-composites on scroll for no visible effect, and the
primitives' `transition-all` animates more than needed. Adding the `latin-ext` font subset loads a
small file only when those characters appear.

---

## B. Priority rules and reconciliation

The brief's definitions are applied to every issue:

| Priority | Meaning | Applied as |
|---|---|---|
| **P0** | Broken, inaccessible or unusable | A task can't be completed, or a WCAG failure blocks it |
| **P1** | Major inconsistency or UX problem | Includes every WCAG 2.2 AA (or Level A) failure that doesn't block a task, every breach of a spec accessibility rule (UX-A11Y-01…05, UX-TOK-02), and data-safety problems |
| **P2** | Visual inconsistency | Includes duplicated implementations, hierarchy and terminology problems that don't lose data |
| **P3** | Minor refinement | Low reach or low impact |

Priority is severity. **Order of work is set by files, not priority:** a P2 in a primitive ships
in the primitive's pass if it touches the same file (see IMPLEMENTATION_PLAN §E).

### Disagreements, and the decision

| Canonical issue | Source ratings | Decision | Why |
|---|---|---|---|
| UI-ISS-001 menu and select highlight | CMP-001 **P0**; not raised by the accessibility audit | **P1** | The highlight exists (a full-row fill at 1.15:1, the same step the app uses for selected rows), Radix announces the item to screen readers, and the accessibility audit drove menus by keyboard without being blocked. It fails WCAG 1.4.11 for a state indicator, so P1 by rule. It is the first item in the floating-overlay pass (UI-013), so the rating doesn't delay it. |
| UI-ISS-031 overlays don't separate | SHD-001 P1, CMP-014 P1 · COL-010, A11Y-019, RSP-008 P2 | **P2** | Modals work: focus is trapped, Esc closes, the dialog has an edge. The problem is perception (a 10% scrim, the same surface as the cards), so a visual inconsistency. CMP-014's reduced-motion part is split out as UI-ISS-012 (P1). |
| UI-ISS-036 cards | RAD-001 P1 · CMP-020 P2 · VH-016 P3 | **P2** | Two radii and six paddings are a visual inconsistency; the radius itself is owner decision D-02. |
| UI-ISS-035 badges | CMP-013 P1 · TYP-007, RAD-004 P2 · SPC-007 P3 | **P2** | Visual inconsistency and duplication; the one contrast failure among badges (neutral on white/10) is in UI-ISS-007 (P1). |
| UI-ISS-030 two input looks | CMP-011 P1 · COL-011 P2 | **P2** | The look difference is visual. The edge that fails 3:1 is UI-ISS-004 (P1); the heights are UI-ISS-011 (P1). |
| UI-ISS-010 / UI-ISS-025 hover | COL-005 P1 (all hover) · CMP-028, COL-016 P3 | Split: **P1** primary, **P2** ghost and outline | The primary CTA is the most important control and its variant is the failing colour pair, so the primary's missing variant and hover is P1. Missing hover on ghost and outline buttons is a visual state gap (hover isn't required by WCAG). |
| UI-ISS-009 destructive | CMP-003 P1, A11Y-005 P1 · COL-008, VH-006 P2 | **P1** | The primitives' red text fails AA (3.51 and 4.38:1). |
| UI-ISS-007 sidebar group labels and other text | A11Y-005 P1 · COL-006 P2 | **P1** | A 1.4.3 failure on text shown on every app page. |
| UI-ISS-048 page and pane titles | TYP-003 P1 · VH-005 P2 · VH-016 P3 | **P2** | A visual inconsistency; the size is owner decision D-05. |
| UI-ISS-047 11 px token, arbitrary sizes | TYP-002 P1 (single source) | **P2** | No WCAG criterion sets a minimum size and the 9–10 px cases are nine badge-like elements; it is a consistency and maintainability problem. Re-rated by the rule above. |
| UI-ISS-026 disabled reason hidden | CMP-010 P1 (single source) | **P2** | Three unmitigated sites, none of which blocks a task (the controls are optional actions); the composer, the main case, already shows reasons visibly. Re-rated by the rule above. |
| UI-ISS-033 segmented controls | CMP-005 P1 · A11Y-015, CMP-018 P2 · VH-008 P2 · RSP-011 P3 | **P2** | CMP-005's P1 parts (touch size, Send at 40 px) are in UI-ISS-011. What remains is an incomplete tabs pattern that still works by Tab and Enter, plus duplicate implementations. |
| UI-ISS-012 reduced motion | MOT-001, A11Y-010 P1 · MOT-004, CMP-016 P2 · MOT-009 P3 | **P1** | One spec rule (§4.2 "Motion"), one fix location (the primitives plus a safety net); the skeleton pulse is part of it. |
| UI-ISS-013 conditional dialogs | A11Y-007 P1 · MOT-003 P2 | **P1** | Focus loss (WCAG 2.4.3, UX-A11Y-02) dominates; the missing exit animation has the same cause. |
| UI-ISS-014 / UI-ISS-077 sticky bars | A11Y-008 P1 · RSP-006 P2 · VH-017 P3 · UX-021 P2 | Split: **P1** focus obscured, **P2** always-visible save bar | Focus hidden under a bar fails WCAG 2.4.11 (AA). Whether the clean save bar shows at all is a C-066 decision (D-08). |
| UI-ISS-019 thread header | RSP-002, VH-002 P1 · UX-036 P3 | **P1** | The hidden "Needs you" chip is fixed by the same layout change. |
| UI-ISS-051 tables | TYP-010, SPC-003 P2 · CMP-033 P3 | **P2** | A visual inconsistency by the rule; low reach is reflected in its late wave. |
| UI-ISS-058 hidden scroll rows | VH-009 P2 · RSP-012, A11Y-024 P3 | **P2** | On desktop the inbox's own filters "Leads", "AI handled" and "More" are invisible at 1440 px. |
| UI-ISS-053 selection bar | RAD-007 P2 · COL-016 P3 | **P2** | Visual inconsistency on the most-seen state (the selected row and nav item). |
| UI-ISS-084 checklist | VH-010 P2 · UX-026 P3 | **P2** | It pushes Home's metrics below the fold on laptops. |
| UI-ISS-032 motion tokens, focus fade | MOT-002, MOT-005, MOT-007 P2 · MOT-008, A11Y-023 P3 | **P2** | Same fix location; the 150 ms grey focus fade is folded in. |
| UI-ISS-096 skeleton default | CMP-016 P2 · COL-020 P3 | **P3** | Only 3 of 117 skeletons are invisible; the pulse part is P1 in UI-ISS-012. |

Agreements (every other merged issue) keep the shared rating.

---

## C. Consolidated issues

Format: **ID · priority · category · title**, then problem, affected components, recommendation,
sources and the implementing task. Recommendations are summaries; the canonical rule is in
DESIGN_SYSTEM.md and the evidence in the source audits. An index from every source ID is in
[Appendix 1](#appendix-1-source-id-index).

### P1 (24)

#### UI-ISS-001 · P1 · Accessibility · Menu and select keyboard highlight is 1.15:1
- **Problem:** the highlighted item in every DropdownMenu and Select shows only as `focus:bg-accent`
  (raised on panel, 1.15:1) with the outline removed (`outline-hidden`). A keyboard user can barely
  see which item Enter will choose (WCAG 1.4.11; UX-A11Y-01).
- **Affected:** `ui/dropdown-menu.tsx` (item, checkbox and radio items, sub-trigger),
  `ui/select.tsx` (item); 14 menus with 40 items and 14 selects with 22 items.
- **Recommendation:** in the primitives, a `hover` fill plus a keyboard indicator: a 2 px inset
  brand outline on `focus-visible` (at least 3.96:1). Destructive items use `danger-fg` text with a
  `danger-soft` highlight.
- **Sources:** CMP-001 (re-rated, §B) · **Task:** UI-013

#### UI-ISS-002 · P1 · Accessibility · The primitives' focus ring is a 2.1:1 halo; focus is drawn five ways
- **Problem:** Button, Input, Select, Textarea, Checkbox, Switch, Tabs and ToggleGroup replace the
  global 2 px brand outline (4.54:1 on panel) with `ring-3 ring-ring/50` (2.10:1). Tabs and
  ToggleGroup have nothing else; on gradient buttons the 1 px brand border vanishes into the fill.
  About 15 cards and tiles copy the halo, 6 sites use `ring-2 ring-brand`, and Clerk's account
  button shows a 22% shadow.
- **Affected:** `ui/button`, `input`, `select`, `textarea`, `checkbox`, `switch`, `tabs`,
  `toggle-group`; Section, StepCard, MetricTile, PostCard, PriorityQueue, TopPostsCard, PostsStep,
  MediaTray, AutomationEditor, AutomationsPage, AutomationRow, CommentComposer, AskComposer;
  `lib/clerk-appearance.ts`.
- **Recommendation:** one recipe, the global `:focus-visible` outline (2 px brand, offset 2 px; inset
  inside clipping containers); fields also turn their border brand. Remove `outline-none` and the
  50% halo from the primitives and the per-site rings; style Clerk's user-button trigger.
- **Sources:** COL-003, RAD-002, CMP-008, A11Y-004, CMP §4 D20 · **Tasks:** UI-011, UI-013,
  UI-014, UI-015, UI-002, area sweeps

#### UI-ISS-003 · P1 · Accessibility · Raw fields and the inbox composer show focus only by a fill or border change
- **Problem:** 13 raw inputs, textareas and the native select set `outline-none` and change only
  `field → raised` (1.17:1); the inbox reply box only lightens its border (1.9:1). A focused
  composer can't be told from an unfocused one.
- **Affected:** ListHeader (search), Composer, EmojiPicker, ScheduledList, TemplatePicker,
  ScheduleFields (2), HashtagGroupsDialog (2), ListView, PostingTimesDrawer, MediaLibraryDialog (2),
  PostPreview (`<select>`).
- **Recommendation:** remove `outline-none` so the global outline shows (keep the fill as an extra
  cue); the composer's wrapper shows the outline when its textarea has visible focus. The area
  sweeps later route these fields through the primitives. Update UX-INB-03's wording.
- **Sources:** COL-003, CMP-007, A11Y-003 · **Task:** UI-007

#### UI-ISS-004 · P1 · Accessibility · Control boundaries are about 1.35:1
- **Problem:** inputs, selects, outline buttons and unchecked checkboxes are edged in white 10%:
  1.34:1 on panel, against UX-A11Y-01's 3:1. A field on a card has a 1.02:1 fill and a 1.32:1
  edge, so it has no visible shape; an unchecked checkbox is a 16 px square at 1.34:1. Inset
  panels (`bg-field/60`, `line-subtle`) are 1.0:1 fill and 1.15:1 edge.
- **Affected:** `ui/input`, `select`, `textarea`, `checkbox`, `switch` (off track), the outline
  Button; about 20 raw inputs; 9 inset panels (AccountCard, BillingPage, AiSettingsPage,
  AgentSettingsPage, workspace settings, DetailsPanel).
- **Recommendation:** add `line-control` (white 40%, 3.4–3.8:1 on every surface) and map `--input`
  to it; checkbox, radio and switch edges use it; inset panels use `border-line` or `bg-raised`.
  Whether text fields are included is owner decision **D-01**.
- **Sources:** COL-004, COL-011, RAD-003, CMP-009, A11Y-006 · **Tasks:** UI-014, UI-018, sweeps

#### UI-ISS-005 · P1 · Colour · White text on solid brand #567FF8 is 3.63:1
- **Problem:** UX-TOK-02 retired this pair for bubbles, but it is back on solid fills: the inbox's
  active platform segment (12 px), the marketing skip link, Clerk's primary button on sign-in and
  sign-up, and shadcn's `--primary` (Button default, Badge default, AvatarBadge).
- **Affected:** PlatformStrip, `app/(marketing)/layout.tsx`, `lib/clerk-appearance.ts`,
  `globals.css`, `ui/button`, `ui/badge`, `ui/avatar`.
- **Recommendation:** add `brand-strong` (#4467E6, the gradient's existing end: 4.85:1 with white)
  and use it for every solid brand fill that carries text; point `--primary` and Clerk's
  `colorPrimary` at it. `brand` becomes non-text only. Whether the segment stays filled is
  **D-15**.
- **Sources:** COL-001, CMP-006, A11Y-005 (items 1 and 8), COL-016 · **Tasks:** UI-001, UI-002

#### UI-ISS-006 · P1 · Colour · A platform colour is used as text
- **Problem:** "Instagram" in every Instagram thread's identity line is `text-instagram`, 2.73:1 on
  panel.
- **Affected:** ThreadHeader (`PLATFORM_TEXT`).
- **Recommendation:** platform names in `fg-secondary` beside the glyph or dot that carries the
  colour. Rule: platform colours are for fills and glyphs only. (Account rings: UI-ISS-054.)
- **Sources:** COL-002, A11Y-005 (item 2) · **Task:** UI-004

#### UI-ISS-007 · P1 · Colour · Other text below 4.5:1
- **Problem:** sidebar group labels ("ENGAGE", "GROW") in `fg-secondary/70`, 11 px, 3.64:1 on every
  page; neutral badges on `white/10` (4.45:1, Billing); "Coming soon" and the Max card under
  `opacity-80` (3.48:1); "Template · name" in outgoing bubbles (`white/75`, 3.46:1 at the gradient's
  light end) and "Unsupported message format" (`white/90`, 4.26:1).
- **Affected:** AppSidebar, BillingPage, PlanCards, MessageBubble.
- **Recommendation:** labels in plain `fg-secondary`; neutral badges on the `hover` fill (5.2:1);
  dim the unavailable plan's border and fill, not its text; bubble labels `on-brand` at full
  opacity.
- **Sources:** COL-006, A11Y-005 (items 3, 5, 7), TYP-006 · **Task:** UI-002

#### UI-ISS-008 · P1 · Colour · Placeholders are 3.41:1, and the spec assigns them fg-disabled
- **Problem:** the base `::placeholder` is `fg-disabled` (3.41:1 on panel, 2.97:1 on raised), and
  WCAG 1.4.3 applies to placeholder text. Raw fields (the composer's "Reply to …", inbox search,
  template, emoji and hashtag fields) use it, while the shadcn primitives use `fg-secondary`
  (6.0:1): two placeholder colours. Spec §4.2 says placeholders are `fg-disabled`.
- **Affected:** `globals.css`, raw inputs, `data-deletion`, PhraseChips.
- **Recommendation:** placeholders in `fg-secondary` through one base rule; `fg-disabled` for
  disabled controls only; amend the spec. Owner decision **D-06**.
- **Sources:** A11Y-005 (item 4), COL-011, CMP-011 · **Task:** UI-018

#### UI-ISS-009 · P1 · Components · Destructive actions fail AA in the primitives and come in five styles
- **Problem:** the `destructive` Button is red text on a 20% tint (3.51:1) and the destructive menu
  item is `#EF4444` text (4.38:1); spec §4.2 keeps `danger` for icons and borders. Because the
  variant was unusable, call sites built four more looks: solid `danger-fill` (12), ghost with
  `danger-fg` (6), outline with `border-danger/60` (1), secondary with `danger-fg` (1), and 3
  hand-made destructive menu items.
- **Affected:** `ui/button`, `ui/dropdown-menu`, `ui/badge`; BillingPage ("Cancel plan"),
  post-parts ("Delete") and about 22 call sites (listed in CMP-003,
  [COMPONENT_AUDIT.md](COMPONENT_AUDIT.md)).
- **Recommendation:** `destructive` = solid `danger-fill` with `on-brand` text (5.47:1), for the
  confirming action only; `destructive-ghost` = `danger-fg` text for row and card triggers that open
  a confirmation; the destructive menu item uses `danger-fg` with a `danger-soft` highlight. Migrate
  the call sites. (Account-card placement: UI-ISS-080.)
- **Sources:** CMP-003, COL-008, VH-006, A11Y-005 (item 6), CMP §4 D2 · **Tasks:** UI-011, UI-013,
  sweeps

#### UI-ISS-010 · P1 · Components · The primary action has no variant: 58 hand-built gradient CTAs, none with a hover
- **Problem:** Button's `default` is solid `bg-primary` (the failing pair), so every primary pastes
  `bg-brand-gradient text-white`. `cn` keeps `hover:bg-primary/80`, which paints under the gradient
  image, so no in-app CTA reacts to hover (50 Buttons, 3 AlertDialogActions, 3 raw buttons, 1
  Link).
- **Affected:** `ui/button`; 40 files with gradient Buttons (SaveBar, PostComposer, Composer,
  BillingPage, UpgradeDialog, TemplatePicker, SchedulePage, SourcesCard, …).
- **Recommendation:** redefine `default` as the primary: the gradient with `on-brand` text,
  `hover:brightness-110`, `active:brightness-95`; delete the overrides. How many primaries a view
  may show is **D-10**.
- **Sources:** CMP-002, COL-005, CMP §4 D1 · **Tasks:** UI-011, sweeps

#### UI-ISS-011 · P1 · Accessibility · Touch targets under 40 px on phones; heights patched at 142 call sites
- **Problem:** no primitive has a touch size (Button 24–36 px, Input 32 px), so call sites patch
  `min-h-10 md:min-h-{6…9}` with 13 different desktop values. Still under 40 px on phones: 112 of
  220 Buttons, 29 of 40 segment items, 38 of 40 menu items, every select item, 11 raw icon buttons
  and the dialog close buttons (UX-A11Y-05). Send is 36 px although C-018 set 40. At 375 px: inbox
  12 of 20 controls under 40 px, automation editor 18 of 29, knowledge 16 of 21. WCAG 2.5.8 (24 px)
  holds everywhere.
- **Affected:** `ui/button`, `input`, `select`, `tabs`, `toggle-group`, `dropdown-menu`, `dialog`
  and `sheet` close buttons; ErrorState's retry; the inbox list header; every feature folder.
- **Recommendation:** `pointer-coarse:` 40 px minimums inside every interactive primitive; one
  control size ladder on fine pointers (24, 28, 32, 36, 40); Send at 40 px on phones now; then
  delete the patches.
- **Sources:** SPC-001, CMP-004, CMP-005, CMP-011, CMP-024, CMP-034, A11Y-009 · **Tasks:**
  UI-007, UI-011–UI-015, sweeps

#### UI-ISS-012 · P1 · Motion · Overlay primitives and Skeleton ignore prefers-reduced-motion
- **Problem:** dialogs, alert dialogs, sheets (the phone drawer), popovers, menus, selects and
  tooltips still zoom, slide and fade under `reduce`, where the spec says instant. Skeleton pulses
  in 106 of 117 uses. Only the hand-built Ask panel and run detail opt out, and three
  reduced-motion mechanisms coexist.
- **Affected:** `ui/dialog`, `alert-dialog`, `sheet`, `popover`, `dropdown-menu`, `select`,
  `tooltip`, `skeleton`.
- **Recommendation:** `motion-reduce:animate-none` (and `transition-none` on the sheet) in the
  primitives, Skeleton `motion-safe:animate-pulse`, a `data-slot` safety net in `globals.css`; app
  code uses `motion-safe:` only.
- **Sources:** MOT-001, MOT-004, MOT-009, A11Y-010, CMP-014, CMP-016 · **Tasks:** UI-001, UI-012,
  UI-013, UI-016

#### UI-ISS-013 · P1 · Accessibility · Closing some dialogs drops focus on the page
- **Problem:** five dialogs are mounted only while open; closing unmounts them, so focus lands on
  `<body>` (four of them) and none plays an exit animation.
- **Affected:** AutomationsPage (TemplateGallery), AgentDraftDialog, ScheduledList, ListView,
  MoveToDialog (focus handled by hand, no exit).
- **Recommendation:** keep them mounted and drive `open`, or reuse `use-return-focus`.
- **Sources:** A11Y-007, MOT-003 · **Task:** UI-007

#### UI-ISS-014 · P1 · Accessibility · Focused controls are hidden under sticky bars
- **Problem:** no page sets scroll padding, so the settings save bar, the post composer's action
  bar and the 56 px phone top bar cover the focused control (WCAG 2.4.11; reproduced on Settings ›
  AI at 375 × 700). At 200% zoom or in landscape the bars take 25–40% of the viewport.
- **Affected:** SaveBar, PostComposer (action bar), MobileNav, `globals.css`.
- **Recommendation:** `scroll-padding-top` under the top bar and `scroll-padding-bottom` on pages
  with a bottom bar; bars become static on short viewports; SaveBar opaque without blur. Hiding the
  clean save bar is part of **D-08**.
- **Sources:** A11Y-008, RSP-006 · **Task:** UI-009

#### UI-ISS-015 · P1 · Accessibility · Single-letter inbox shortcuts can't be turned off (WCAG 2.1.4, Level A)
- **Problem:** j, k, e, u and / act window-wide whenever focus isn't in a text field, including on
  Send or Insert; a speech-input user saying "e" archives the conversation.
- **Affected:** `use-inbox-shortcuts.ts`, InboxShell.
- **Recommendation:** owner decision **D-14** (recommended: a per-device switch, on by default).
- **Sources:** A11Y-001 · **Task:** UI-053

#### UI-ISS-016 · P1 · Accessibility · No skip link in the app shell
- **Problem:** every app page puts 14 sidebar stops before the first control (in a conversation the
  composer is stop 42); the marketing site has a skip link, the app doesn't.
- **Affected:** AppShell.
- **Recommendation:** "Skip to content" first in AppShell and `<main id="main" tabIndex={-1}>`, in
  `brand-strong`.
- **Sources:** A11Y-002 · **Task:** UI-006

#### UI-ISS-017 · P1 · Typography · Text fields under 16 px make iOS zoom on focus
- **Problem:** iOS Safari zooms when a field below 16 px gets focus. Input avoids it
  (`text-base md:text-sm`); Textarea, the inbox composer, Ask's composer (15 px), the comment reply
  and 14 raw inputs don't. The installed iPhone PWA is supported (TR-FE-09).
- **Affected:** `ui/textarea`; inbox Composer, ListHeader, EmojiPicker, TemplatePicker,
  ScheduledList; AskComposer; CommentComposer; ChipListInput; AutomationsPage, KeywordInput,
  PostsStep; MediaLibraryDialog; HashtagGroupsDialog, ListView, PostingTimesDrawer; PhraseChips;
  data-deletion.
- **Recommendation:** every text-entry field `text-base md:text-sm`, Textarea first; route raw
  fields through the primitives.
- **Sources:** TYP-001 · **Tasks:** UI-014, sweeps

#### UI-ISS-018 · P1 · Layout · Home scrolls sideways on phones
- **Problem:** below 1024 px the insight-card grid has no explicit column, so a `truncate` caption
  sizes it to 483 px: the page is 499 px wide on a 390 px phone (+124 px at 375, +179 px at 320;
  WCAG 1.4.10).
- **Affected:** HomeScreen (`grid gap-3 lg:grid-cols-3`), TopPostsCard, SentimentCard,
  TopIntentsCard.
- **Recommendation:** `grid-cols-1 lg:grid-cols-3` and `min-w-0` on the sections; check the other
  grids.
- **Sources:** RSP-001, VH-001 · **Task:** UI-003

#### UI-ISS-019 · P1 · Layout · The thread header hides who you are talking to below 1024 px
- **Problem:** the name is the only shrinkable item; at 360–768 px it collapses to 0 px and the
  window chip overlaps the AI menu by 59–82 px; at 1440 px with the panel open it shows "Sandbox
  cu…". The "Needs you" chip is hidden below 768 px, where it matters most.
- **Affected:** ThreadHeader, ReplyWindowChip, AiModeControl.
- **Recommendation:** give the name a minimum width; below `md` move the window chip to the handle
  line (or show it compact) and the AI pill as an icon; show "Needs you" at every width. C-063's
  layout stays at 1024 px and up.
- **Sources:** RSP-002, VH-002, UX-036 · **Task:** UI-004

#### UI-ISS-020 · P1 · Layout · App banners push the inbox composer and the Ask box below the fold
- **Problem:** the inbox and Ask frames are sized from `100dvh`, but banners (credits used up,
  reconnect, payment failed, trial ending) render above them in `<main>`; the page scrolls and the
  composer sits about 50 px per banner below the viewport. (From code; the sandbox showed no
  banner.)
- **Affected:** AppShell, InboxShell, AskPage, BannerSlot.
- **Recommendation:** `<main>` as a full-height flex column; the frames `flex-1 min-h-0`.
- **Sources:** UX-004 · **Task:** UI-006

#### UI-ISS-021 · P1 · UX flow · "Save as draft" silently unschedules a scheduled post
- **Problem:** on a scheduled post the first and quietest button in the action bar unschedules it,
  with only a toast.
- **Affected:** PostComposer.
- **Recommendation:** for scheduled posts, remove it from the bar; Unschedule moves to ⋯ with a
  confirmation; Update schedule is the save.
- **Sources:** UX-002 · **Task:** UI-008

#### UI-ISS-022 · P1 · UX flow · Edits are lost when leaving inside the app
- **Problem:** scheduled posts (C-044) and brand voice don't autosave, and leaving through the
  sidebar, breadcrumb or a notification discards edits without asking. Settings already has the
  guard (`useLeaveWarning`).
- **Affected:** use-post-draft, PostComposer, BrandVoiceCard.
- **Recommendation:** `useLeaveWarning(dirty && !autosave)` in the composer and the brand-voice
  form.
- **Sources:** UX-003 · **Task:** UI-008

#### UI-ISS-023 · P1 · Copy · Stale copy says AI-reply automations don't work yet
- **Problem:** the automation editor tells Pro users AI replies "start working when Knowledge
  arrives in Social Hood"; Knowledge shipped in P5.
- **Affected:** ThenStep.
- **Recommendation:** "The AI answers from your knowledge. When the answer isn't there, it sends
  nothing and moves the conversation to Needs you.", with a link to Knowledge.
- **Sources:** UX-005 · **Task:** UI-005

#### UI-ISS-024 · P1 · UX flow · The Comments badge leads to a dead end
- **Problem:** the badge counts comments that need a reply (C-048), but the Comments page shows no
  needs-reply count, filter or list, and the API has no such field.
- **Affected:** CommentsPage, PostCard, CommentsColumn, `lib/comments/format.ts`, the posts and
  comments API.
- **Recommendation:** owner decision **D-11** (recommended: a per-post count and a Needs reply
  filter now, a cross-post list later).
- **Sources:** UX-001, VH-014 (the count) · **Task:** UI-055

### P2 (67)

#### UI-ISS-025 · P2 · Colour · Hover has no tokens: ghost and outline hover invisible, six recipes, hover equals selected
- **Problem:** ghost hover is `field/50` (1.01:1 on panel) on 101 buttons, outline hover 1.04:1;
  hover is written six ways (`white/5`, `white/10`, `raised`, `muted/50`, `color-mix`,
  `brightness`); on panel `white/5` is exactly `raised`, so a hovered row looks selected.
- **Affected:** `ui/button` (ghost, outline, secondary), ConversationRow, `sidebar-styles.ts`, about
  50 hover call sites.
- **Recommendation:** `hover` (white 5%) and `pressed` (white 10%) tokens; ghost and outline hover
  `bg-hover`, open `bg-pressed`; secondary hover `raised-hover`. Hover and selected stay apart
  through the selection bar (UI-ISS-053).
- **Sources:** COL-005, COL-016, CMP-028 · **Tasks:** UI-001, UI-011, sweeps

#### UI-ISS-026 · P2 · Components · Disabled controls hide their reason; four disabled recipes
- **Problem:** Button and ToggleGroupItem set `pointer-events-none` when disabled, so a `title`
  reason never shows and keyboard and touch users can't reach it ("Scheduling needs an open reply
  window", "Write a reply to polish", "WhatsApp isn't set up for this app yet"). Disabled is drawn
  as `opacity-50`, `opacity-60` or `raised` + `fg-disabled`.
- **Affected:** `ui/button`, `ui/toggle-group`, ThreadHeader, Composer, ConnectWhatsAppButton.
- **Recommendation:** a `DisabledReason` wrapper (focusable, Tooltip plus `sr-only` text); one rule:
  `opacity-50`, except the composers' empty Send, which keeps the spec's neutral state (UX-INB-07)
  as a Button state.
- **Sources:** CMP-010 (re-rated, §B), COL-020 · **Tasks:** UI-011, sweeps

#### UI-ISS-027 · P2 · Colour · Soft status fills aren't tokens; the tone map is copied eight times
- **Problem:** the spec names warning and danger soft fills (and `bg-warn-soft`), but only
  `brand-soft` exists; code uses `/10`, `/15`, `/20` and `/30` for one role. `TONE_CLASS` and
  `CHIP_CLASS` are identical, and six more tone maps exist.
- **Affected:** `lib/inbox/format.ts`, `lib/schedule/format.ts`, BillingPage, AccountCard,
  AutomationEditor, RunsPane, AutomationSection, MetricTile, InboxPreview; about 60 inline fills.
- **Recommendation:** `success-soft`, `warning-soft`, `danger-soft` at 15%; one tone map, owned by
  Badge.
- **Sources:** COL-007, CMP-013, CMP-022 · **Tasks:** UI-001, UI-016, sweeps

#### UI-ISS-028 · P2 · Colour · Raw white and black utilities and literal gradient stops block the light-theme swap
- **Problem:** D13 promises light mode as a token swap, but 108 `text-white`, about 80 `bg-white/N`
  and 15 `black` utilities, `--primary-foreground: #FFFFFF` and hex stops in the gradient utilities
  would not flip; the default Tailwind palette is still enabled, so drift compiles silently.
- **Affected:** about 100 files; `globals.css`.
- **Recommendation:** `on-brand`, `hover`, `pressed`, `scrim` and `media-scrim`; gradient stops as
  `var()`; migrate mechanically; then lock the palette.
- **Sources:** COL-012, COL-013 · **Tasks:** UI-001, sweeps, UI-070

#### UI-ISS-029 · P2 · Colour · The shadcn alias layer: four foreground utilities generate no CSS; two names per colour
- **Problem:** `@theme inline` omits `card-`, `popover-`, `secondary-` and `accent-foreground`, so
  their utilities output nothing (a secondary Button inside a warning banner turns orange). App code
  mixes aliases (`border-input`, `ring-ring/50`) with tokens (`border-line`, `ring-brand`).
- **Affected:** `globals.css`; `ui/dialog`, `alert-dialog`, `sheet`, `popover`, `dropdown-menu`,
  `select`, `button`; 19 alias uses in 15 app files.
- **Recommendation:** add the four mappings and test that every `:root` alias is mapped; aliases
  only inside `components/ui`, tokens everywhere else.
- **Sources:** COL-009, CMP-015, RAD-006 · **Tasks:** UI-001, sweeps

#### UI-ISS-030 · P2 · Components · Input looks different from every other field, and its overrides do nothing
- **Problem:** Input and SelectTrigger are near-transparent (`dark:bg-input/30`, `#262626` on
  panel) with a `fg-secondary` placeholder; Textarea and raw fields are `bg-field` with
  `fg-disabled`. The eight `bg-field` overrides on Input can't win against the `dark:` class
  (specificity 0,2,0).
- **Affected:** `ui/input`, `ui/select` (trigger), the outline Button; SettingsStep, ThenStep,
  connections page.
- **Recommendation:** every field on `bg-field`, no `dark:` backgrounds; drop the overrides.
- **Sources:** CMP-011 (re-rated, §B), COL-011 · **Task:** UI-014 (Select trigger: UI-013)

#### UI-ISS-031 · P2 · Colour · Overlays don't separate from the page
- **Problem:** popovers, menus, dialogs and sheets are `panel`, the same as the cards under them
  (1.00:1); Tailwind's 10% shadows are invisible on near-black; the scrim is `bg-black/10` plus a
  full-viewport blur (the spec's drawer asks 60%; the Ask panel and Clerk use 60%); the mobile
  drawer is `canvas` while the sidebar is `panel`. 55 call sites patch the primitives with
  `border-line bg-panel shadow-xl` (the border is a no-op); one popover has a double edge; the save
  bar blurs behind a 95% surface.
- **Affected:** `ui/dialog`, `alert-dialog`, `sheet`, `popover`, `dropdown-menu`, `select`;
  MobileNav; SaveBar; RangeControl; 55 overlay call sites.
- **Recommendation:** `scrim` (60%) without blur in the three modal primitives; the spec's shadow in
  the primitives; drawer on `panel`; delete the patches. A lighter `overlay` surface and dark
  elevation shadows are owner decision **D-12**.
- **Sources:** COL-010, COL-017, SHD-001, SHD-002, SHD-003, CMP-014, RAD-006, A11Y-019, RSP-008 ·
  **Tasks:** UI-012, UI-013, UI-018, sweeps

#### UI-ISS-032 · P2 · Motion · No motion tokens; dialogs at 100 ms; three enter and exit families
- **Problem:** six durations and three easings are literals; dialogs open in 100 ms (spec 200), the
  sheet's overlay finishes before its panel, the Ask panel slides without the fade the details
  sheet has; Button, Switch and Badge use `transition-all`; in the sidebar, `transition-colors`
  fades the focus outline in from grey for 150 ms; a few opacity transitions and a pulsing dot are
  unguarded.
- **Affected:** `globals.css`; `ui/button`, `switch`, `badge`, `dialog`, `alert-dialog`, `sheet`,
  `popover`, `dropdown-menu`, `select`; AskPanel, AgentSettingsPage; `sidebar-styles.ts`,
  WorkspaceMenu, AppSidebar; AutomationRow, SchedulePage, AccountCard.
- **Recommendation:** the motion tokens and mapping in DESIGN_SYSTEM §7 (fast 120, normal 150,
  slow 200; enter, exit, standard easings); name transition properties; never transition
  `outline-color`.
- **Sources:** MOT-002, MOT-005, MOT-007, MOT-008, A11Y-023, CMP-014 · **Tasks:** UI-001, UI-011,
  UI-012, UI-013, UI-002, UI-067, sweeps

#### UI-ISS-033 · P2 · Components · Four segmented-control implementations; the inbox tablist is incomplete; labels wrap
- **Problem:** ToggleGroup, Tabs, a hand-rolled `role="tablist"` in the inbox (no panels, no
  `aria-controls`, no arrow keys, 24 px tall) and PlatformStrip's `aria-pressed` group each have
  their own track, padding, size and active style. ToggleGroup items wrap their labels ("30 /
  days", "Action / needed").
- **Affected:** `ui/tabs`, `ui/toggle-group`, ListHeader, PlatformStrip, RangeControl,
  AgentSettingsPage.
- **Recommendation:** ToggleGroup for choosing a value, Tabs when the choice swaps panels (Chats |
  Scheduled); a `size="sm"`; `whitespace-nowrap` on items.
- **Sources:** CMP-005, CMP-018, A11Y-015, VH-008, RSP-011, CMP §4 D3 · **Tasks:** UI-015, UI-030

#### UI-ISS-034 · P2 · Components · Five filter-chip implementations
- **Problem:** chips that filter a list are built five ways with different borders, heights (26,
  28, 32–40 px) and hover styles.
- **Affected:** ListHeader, TemplateGallery, AnalysisChips, CommentsColumn, AccountPicker.
- **Recommendation:** `ToggleGroup variant="chips"` (single and multiple), one chip spec.
- **Sources:** CMP-019, CMP §4 D4 · **Tasks:** UI-015, sweeps

#### UI-ISS-035 · P2 · Components · Badges: the primitive is unused; 77 ad-hoc badges in three sizes and four radii
- **Problem:** `ui/badge` has no importers; badges are 10, 11 or 12 px, pill, 6 px, 8 px or 4 px,
  with six paddings and three neutral fills; two different components are exported as
  `StatusChip`; the inbox count badge is `h-4 text-[10px]` where UX-SH-01 asks `h-5 text-xs`.
- **Affected:** `ui/badge`; 39 files (ConversationRow, ReplyWindowChip, ThreadHeader, post-parts,
  SourcesCard, BillingPage, AccountCard, ListHeader, …).
- **Recommendation:** rebuild Badge with tone, size (11 px and 12 px) and shape (pill, tag); rename
  the two `StatusChip`s; migrate.
- **Sources:** CMP-013 (re-rated, §B), TYP-007, RAD-004, SPC-007, CMP §4 D6 · **Tasks:** UI-016,
  sweeps

#### UI-ISS-036 · P2 · Components · Cards: no primitive, two radii, six paddings
- **Problem:** 85 hand-written card surfaces in 46 signatures; settings, billing and connections
  cards (C-066) are `rounded-2xl p-5 md:p-6`, the rest `rounded-xl p-4` (spec: `xl`); inset panels
  are nearly as round as their parents.
- **Affected:** SettingsCard, composer Section, StepCard, MetricTile, PlanCards, AccountCard, the
  7 inset panels and about 85 surfaces.
- **Recommendation:** `ui/card` (Card, CardHeader, CardInset; standard `p-4` and roomy
  `p-5 md:p-6`; tones); inner radius = outer minus padding. The radius is owner decision **D-02**.
- **Sources:** CMP-020, RAD-001 (re-rated, §B), RAD-008, SPC-002, VH-016, CMP §4 D7 · **Tasks:**
  UI-020, sweeps

#### UI-ISS-037 · P2 · Components · Meters and progress bars: nine implementations; a full slot quota shows as an error
- **Problem:** thresholds, tracks (`raised`, `white/10`, `white/15`, `field`), heights, fills and
  roles differ; the AI-credits number is drawn two ways; Billing paints "Instagram accounts 1/1" in
  danger red though one connected account is normal; the collapsed credits ring reads as a spinner.
- **Affected:** UsageMeter, BillingPage, UsageCard, ScheduleRail, DetailsPanel, PostPanel,
  MediaTray, SourceSheet, AttachmentTray.
- **Recommendation:** `ui/meter` (usage: consumable or slot; warning at 80%, danger at 100% for
  consumables, neutral "All used" for slots) and `ui/progress` (task progress); one track and height;
  the ring shows its percentage.
- **Sources:** CMP-021, COL-013, VH-007, RSP-013, CMP §4 D5 · **Tasks:** UI-022, sweeps

#### UI-ISS-038 · P2 · Components · Alerts and callouts: no primitive, two looks, hand-rolled tinted actions
- **Problem:** 17 callouts use a borderless tint or a bordered tint with `/10` or `/15`; a "tinted
  action" button is hand-rolled four times at three heights.
- **Affected:** BannerSlot, SuggestionCard, HomeScreen, SourceSheet, StepCard, AutomationEditor,
  StatusBanner, InstallPrompt, CheckoutReturn, UpgradeAction, MediaTray.
- **Recommendation:** `ui/alert` (tone; soft or outline; UX-SH-04's `rounded-lg px-4 py-2.5`);
  actions on alerts are `secondary size="sm"` (no new variant).
- **Sources:** CMP-022, CMP §4 D8, D9 · **Tasks:** UI-021, sweeps

#### UI-ISS-039 · P2 · Components · Forms: three private Field copies, two label sizes, clipped labels, unlinked errors
- **Problem:** `Field` is defined three times (two byte-identical); labels are 14 px or 12 px;
  `Label` uses `leading-none`, which clips wrapped labels; hints and errors aren't tied to the input
  with `aria-describedby`; field stacks use five spacings.
- **Affected:** `ui/label`; workspace settings page, BrandVoiceCard, SourceSheet; ScheduleFields,
  HashtagGroupsDialog, ListView, TemplatePicker, ThenStep, CaptionEditor, MediaLibraryDialog,
  PostPreview.
- **Recommendation:** `ui/field` (Field, FieldLabel, FieldDescription, FieldError with generated
  ids); one label style per density; stack `space-y-4`.
- **Sources:** CMP-012, TYP-009, SPC-004, A11Y-011, CMP §4 D10 · **Tasks:** UI-014, sweeps

#### UI-ISS-040 · P2 · Components · Search fields and chip-list inputs are duplicated
- **Problem:** six search fields differ in height, icon inset, focus and border; three chip-list
  inputs differ only in validation and counters.
- **Affected:** connections page, AgentSettingsPage, AutomationsPage, PostsStep, ListHeader,
  EmojiPicker; ChipListInput, KeywordInput, PhraseChips.
- **Recommendation:** `SearchInput` (on Input; Escape clears) and one `ChipInput`.
- **Sources:** CMP-029, CMP §4 D11, D12 · **Tasks:** UI-023, sweeps

#### UI-ISS-041 · P2 · Components · Dialog anatomy: four title styles, clipped titles, five dialogs can't scroll
- **Problem:** titles are `text-xl semibold`, `text-base medium`, `text-lg semibold` or
  `text-base semibold`; `leading-none` crushes a wrapped title; UpgradeDialog (opened by every 402),
  ScheduledList, ListView, MoveToDialog and AttachmentView have no height limit, so on a short
  viewport their actions can sit off-screen.
- **Affected:** `ui/dialog`, `ui/sheet`; the 12 dialogs.
- **Recommendation:** primitive title `text-base font-semibold` with normal leading and a `size`
  prop (`lg` for gallery dialogs); `max-h-[calc(100dvh-2rem)] overflow-y-auto` by default.
- **Sources:** CMP-024, TYP-005, RSP-007 · **Task:** UI-012

#### UI-ISS-042 · P2 · Components · The tooltip is white on a dark app, and native `title` carries information
- **Problem:** Tooltip is `bg-foreground` (white), the only light surface in the app; about 25
  meaningful elements use `title`, which keyboard and touch users never see (delivery ticks, "AI
  Assisted", "Paused until …", account-filter avatars).
- **Affected:** `ui/tooltip`; MessageBubble, ConversationRow, AiModeControl, SuggestionCard,
  SchedulePage, Threads, AttachmentTray.
- **Recommendation:** owner decision **D-03** on the colour; move meaningful `title`s to Tooltip with
  an accessible description.
- **Sources:** CMP-026, CMP §4 D15 · **Tasks:** UI-017, sweeps

#### UI-ISS-043 · P2 · Components · Toasts: off-token, at the bottom on phones, 402 shown twice, actions vanish in 4 s
- **Problem:** sonner's own dark palette (a black box on the black canvas); `bottom-right` at every
  width (UX-SH-04 says top on phones, where the bottom toast covers Send); 37 direct
  `toast.error(errorMessage(e))` calls bypass C-051's one-message rule for 402s; Undo, Try again and
  Open toasts disappear after 4 s (WCAG 2.2.1).
- **Affected:** `app/layout.tsx`, `lib/toast-error.ts`, about 15 files with direct calls,
  InboxShell, connections page, AutomationsPage, SchedulePage, SuggestionSlot.
- **Recommendation:** `ui/sonner.tsx` on tokens, top-centre below `md`, action toasts 10 s or more;
  `toastError()` everywhere with a lint rule.
- **Sources:** COL-018, CMP-023, RSP-004, A11Y-014 · **Task:** UI-024

#### UI-ISS-044 · P2 · Components · No Button loading state; spinners behave two ways
- **Problem:** 20 pending buttons show a spinner and 18 only change their label (and width); 2 set
  `aria-busy`; 36 spinners in four sizes, 7 stop under reduced motion and 29 don't.
- **Affected:** `ui/button`; TemplateGallery, PostComposer, CropDialog, BrandVoiceCard,
  PostingTimesDrawer, DeleteWorkspace, TestBox and the "Loading…" pagers.
- **Recommendation:** `Button loading` (Spinner, `aria-busy`, disabled, width kept); one `Spinner`
  with one reduced-motion rule (DESIGN_SYSTEM §7).
- **Sources:** CMP-017, MOT-006, CMP §4 D16 · **Task:** UI-011

#### UI-ISS-045 · P2 · Components · An indeterminate checkbox shows a tick
- **Problem:** a partial selection draws a tick in an unfilled box, which reads as "all selected".
- **Affected:** `ui/checkbox`; ListView's select-all.
- **Recommendation:** a minus icon and the checked fill for `indeterminate`.
- **Sources:** CMP-027 · **Task:** UI-014

#### UI-ISS-046 · P2 · Components · Button size scale: 12.8 px text, corners change with size, an inert radius knob
- **Problem:** `sm` uses `text-[0.8rem]` (65 buttons); `xs`/`sm`/icon sizes use
  `rounded-[min(var(--radius-md),…)]` (6 px) next to 8 px; `:root --radius` is mapped to nothing.
- **Affected:** `ui/button`, `ui/select`, `globals.css`.
- **Recommendation:** `sm` and `xs` text `text-xs`; small sizes plain `rounded-md` (the spec's
  value), larger `rounded-lg`; document `--radius` as inert.
- **Sources:** TYP-008, RAD-005 · **Task:** UI-011

#### UI-ISS-047 · P2 · Typography · No 11 px or 15 px tokens; arbitrary sizes inherit their line height; 9–10 px text
- **Problem:** `text-[11px]` is used 86 times in 47 files, `text-[15px]` 7 times; arbitrary sizes
  carry no line height, so the same chip changes height with its parent (hence `leading-[18px]`
  patches); nine elements are 9–10 px.
- **Affected:** 47 files; AppSidebar, ListHeader, WorkspaceMenu, `sidebar-styles.ts`,
  AttachmentTray, post-parts, PostsStep; AnswerText, RunView, AskComposer, AskPanel, LegalPage.
- **Recommendation:** `text-2xs` (11/16) and `text-md` (15/24); 11 px floor.
- **Sources:** TYP-002 (re-rated, §B), TYP-012 · **Tasks:** UI-001, sweeps

#### UI-ISS-048 · P2 · Typography · Page titles are 24 or 30 px; pane titles 16 or 18 px
- **Problem:** Home and PageFrame titles are 24 px, Settings 30 px from `md` (C-066's mockup); the
  Inbox pane title is 18 px (spec 20), Ask 16 px, the phone top bar 16 px.
- **Affected:** SettingsPageHeader, ListHeader, AskPage, MobileNav.
- **Recommendation:** owner decision **D-05** (recommended: page 24 px, pane 18 px).
- **Sources:** TYP-003 (re-rated, §B), VH-016 · **Task:** UI-069

#### UI-ISS-049 · P2 · Typography · Card and section title hierarchy changes by feature
- **Problem:** card titles are 16 px (Home, Knowledge, Comments, Settings), 14 px (Composer,
  Automations) or 18 px (plan cards); descriptions 12 or 14 px under the same title; post detail
  mixes micro labels and a bold "Comments" at one level.
- **Affected:** home cards, knowledge cards, composer Section, PostChecklist, PostPreview,
  AccountGroup, TemplateGallery, KnowledgeGapBanner, PlanCards, PostSummaryCard, CommentsColumn.
- **Recommendation:** card title `text-base semibold`; item titles `text-sm semibold`;
  descriptions `text-xs` in dashboard cards, `text-sm` in settings and forms, built into CardHeader.
- **Sources:** TYP-004, VH-016 · **Task:** sweeps

#### UI-ISS-050 · P2 · Typography · Type roles aren't shared: the eyebrow is defined five times with three trackings
- **Problem:** the uppercase label is restated in `tokens.ts`, `settings/styles.ts` (0.12em),
  `Threads.tsx`, `PostPerformanceCard.tsx` and about 20 inline sites; `tokens.ts typeRoles` is
  documentation only; the spec's table has drifted from the code.
- **Affected:** `styles/tokens.ts`, `settings/styles.ts`, Threads, PostPerformanceCard, BillingPage,
  AgentSettingsPage and the inline sites.
- **Recommendation:** importable role constants (EYEBROW, CHIP …) in `styles/`; one tracking
  (0.08em); update the spec table with the token change.
- **Sources:** TYP-006, TYP-015 · **Tasks:** UI-001, sweeps

#### UI-ISS-051 · P2 · Components · Three table styles
- **Problem:** SourcesCard (12 px sentence-case header), PaymentHistory (11 px uppercase) and Ask's
  Markdown tables (13 px) use different headers, cell paddings and bleeds.
- **Affected:** SourcesCard, PaymentHistory, AnswerText.
- **Recommendation:** `ui/table`: header `text-xs font-medium fg-secondary`, body `text-sm`
  `tabular-nums`; edge cells align with the card padding.
- **Sources:** TYP-010, SPC-003, CMP-033, CMP §4 D19 · **Task:** UI-026

#### UI-ISS-052 · P2 · Typography · Only the latin subset is loaded, so ₹ falls back
- **Problem:** ₹ (U+20B9) and latin-ext letters in customer names render from the system font;
  prices are shown as "₹999" on Pricing and Billing.
- **Affected:** `app/layout.tsx`.
- **Recommendation:** add `latin-ext` to both fonts; Devanagari is owner decision **D-17**.
- **Sources:** TYP-011 · **Task:** UI-010

#### UI-ISS-053 · P2 · Components · The selected-state bar has five implementations
- **Problem:** a 3 px span (inbox row), a 2 px pseudo-element (sidebar), a 2 px inset shadow (Ask
  threads), `border-l-2` (calendar status) and `border-l-4` (danger card).
- **Affected:** ConversationRow, `sidebar-styles.ts`, Threads, CalendarPostCard, SettingsCard.
- **Recommendation:** one selection bar (2 px brand, leading edge, inset 8 px, rounded); status
  edges `border-l-2`.
- **Sources:** RAD-007, COL-016, SHD-005 · **Task:** sweeps

#### UI-ISS-054 · P2 · Colour · Identity colours borrow status and platform tokens; three avatar pairs fail contrast
- **Problem:** avatar fallbacks use `instagram → warning`, `whatsapp → success` and
  `danger-fill → warning` (white initial 2.26–3.84:1) and turn customers into "warning" colours;
  schedule account rings use warning, brand next to brand-fg (1.81:1 apart) and instagram (2.73:1
  against panel). The initial repeats the adjacent name, so it is treated as decorative, but it
  should still read.
- **Affected:** `lib/inbox/format.ts`, ContactAvatar, `lib/schedule/format.ts`, the schedule
  filter and cards.
- **Recommendation:** owner decision **D-13** (recommended: an identity palette built from existing
  values, each stop at least 4.5:1 with white, shared by avatars and account rings).
- **Sources:** COL-014, COL-015, COL-002 · **Task:** UI-027

#### UI-ISS-055 · P2 · Colour · Gradients outside their roles
- **Problem:** the shell gradient appears beyond the logo and Upgrade (plan hero icon, preview
  avatar, marketing CTA panel); 8 px notification dots use the gradient while the inbox's unread
  dot is solid.
- **Affected:** BillingPage, PreviewPane, FinalCta, NotificationsButton.
- **Recommendation:** the four-gradient system (DESIGN_SYSTEM §1.9): shell for logo and Upgrade
  only; marks under 12 px solid.
- **Sources:** COL-013 · **Task:** sweeps

#### UI-ISS-056 · P2 · Layout · The conversation clips at 320 px; Automations overflows by 3 px
- **Problem:** at the WCAG reflow width the inbox frame clips the header's More and the composer's
  Send; the Automations header overflows.
- **Affected:** InboxShell, ThreadHeader, Composer, PageFrame.
- **Recommendation:** let the composer toolbar wrap (or fold Polish, heart and schedule into More
  below 360 px); move the details toggle into More below 360 px; `flex-wrap` on PageFrame's header.
- **Sources:** RSP-003 · **Tasks:** UI-051, UI-040

#### UI-ISS-057 · P2 · Layout · Hover-only controls on touch tablets
- **Problem:** an automation row's bulk-select checkbox and drag handle are `opacity-0` until hover
  from 768 px; an iPad can't discover them.
- **Affected:** AutomationRow.
- **Recommendation:** hide on hover only for fine pointers (`pointer-fine:`), as RunView does.
- **Sources:** RSP-005 · **Task:** UI-034

#### UI-ISS-058 · P2 · Layout · Horizontally scrolling rows hide options with no cue
- **Problem:** the inbox view chips hide "Leads", "AI handled" and "More" at 375 and 1440 px, and
  the settings tabs cut at "Workspac…", with the scrollbar hidden.
- **Affected:** ListHeader, `settings/layout.tsx`.
- **Recommendation:** an edge-fade mask utility (the sidebar's pattern); wrap the chips onto two
  rows at 768 px and up.
- **Sources:** RSP-012, A11Y-024, VH-009 · **Tasks:** UI-001, UI-052, UI-036

#### UI-ISS-059 · P2 · Layout · Breakpoints come from three sources; JS hooks render desktop first on phones
- **Problem:** layout switches are split between CSS `md:` and `useMediaQuery`, whose server value
  is desktop; widths are literals in five places; 1440 exists only as `min-[1440px]` and in JS.
- **Affected:** `inbox-context.tsx`, AppShell, InboxShell, SchedulePage, `use-browser-state.ts`.
- **Recommendation:** one `BREAKPOINTS` module, `--breakpoint-wide: 90rem`, CSS for visibility-only
  switches, phone-first server values where safer.
- **Sources:** RSP-009 · **Task:** UI-028

#### UI-ISS-060 · P2 · Accessibility · `aria-label` on generic elements leaves state silent
- **Problem:** the notifications unread dot, message reactions and several loading containers carry
  `aria-label` without a role, so screen readers ignore them (unread isn't announced, against
  UX-A11Y-04).
- **Affected:** NotificationsButton, MessageBubble, PageSkeleton, ConversationList, KnowledgePage,
  PlatformStrip, Composer.
- **Recommendation:** `role="img"` (as ConversationRow does) or `sr-only` text; skeletons
  `role="status"` with "Loading …".
- **Sources:** A11Y-012 · **Task:** UI-066

#### UI-ISS-061 · P2 · Accessibility · Six screens are titled just "Social Hood"
- **Problem:** Home, a conversation, a post's comments, the automation editor, Settings ›
  Connections and Settings › Workspace export no metadata (WCAG 2.4.2).
- **Affected:** the six `page.tsx` files.
- **Recommendation:** server `page.tsx` with `metadata` around the client component;
  `document.title` with the contact's or automation's name for dynamic pages.
- **Sources:** A11Y-013 · **Task:** UI-066

#### UI-ISS-062 · P2 · Accessibility · Document structure: missing h1s, unlabelled asides, headings inside summary
- **Problem:** the automation editor and the phone conversation have no `<h1>`; the shell wraps the
  main nav in an unlabelled `<aside>` and Knowledge adds a second; FAQ headings sit inside
  `<summary>`.
- **Affected:** AutomationEditor, InboxShell, AppShell, KnowledgePage, `marketing/Faq.tsx`.
- **Recommendation:** `sr-only` h1s with the object's name; the shell wrapper becomes a `div`;
  label Knowledge's aside; headings outside `<summary>`.
- **Sources:** A11Y-015, A11Y-020, A11Y-021 · **Tasks:** UI-066, UI-006

#### UI-ISS-063 · P2 · Accessibility · The message log announces history and our own sends
- **Problem:** the whole scroller is a polite live region for additions, so loading older pages,
  virtualised rows and outbound sends may be read aloud (UX-A11Y-03 asks new inbound only). Needs
  a screen reader to confirm.
- **Affected:** MessageLog.
- **Recommendation:** keep `role="log"`, set `aria-live="off"`, announce live inbound messages
  through a separate polite region; verify with NVDA and VoiceOver.
- **Sources:** A11Y-016 · **Task:** UI-066

#### UI-ISS-064 · P2 · Accessibility · An empty week grid can't be scrolled by keyboard
- **Problem:** with no posts the calendar's scroller has nothing focusable (axe
  `scrollable-region-focusable`).
- **Affected:** WeekView.
- **Recommendation:** `tabIndex={0}`, a label and a focus outline on the scroller.
- **Sources:** A11Y-017 · **Task:** UI-066

#### UI-ISS-065 · P2 · Accessibility · Customer messages carry no language
- **Problem:** Hindi and Hinglish messages are read by an English voice (WCAG 3.1.2).
- **Affected:** MessageBubble.
- **Recommendation:** set `lang` on the bubble text when the analysis knows the language.
- **Sources:** A11Y-018 · **Task:** UI-066

#### UI-ISS-066 · P2 · UX flow · Ask's "Open" replaces an unsent composer draft
- **Problem:** opening a "Scheduled message" action card writes over whatever the member had typed
  in that conversation, without warning or undo.
- **Affected:** `lib/agent/handoff.ts`, ThreadView.
- **Recommendation:** keep an existing draft (put the prepared text in the schedule popover's own
  field) or ask "Replace your draft?"; at least an Undo toast.
- **Sources:** UX-009 · **Task:** UI-051

#### UI-ISS-067 · P2 · UX flow · One tap sends a heart to the customer
- **Problem:** the Instagram heart sends instantly, sits between Emoji and AI Polish and can't be
  unsent from Social Hood.
- **Affected:** Composer, EmojiPicker.
- **Recommendation:** owner decision **D-15** (recommended: move it into the emoji popover).
- **Sources:** UX-010 · **Task:** UI-051

#### UI-ISS-068 · P2 · UX flow · A page crash removes the whole app shell
- **Problem:** the only signed-in error boundary sits above the workspace layout, so a render error
  replaces the sidebar, banners and Ask with "This didn't load" and only Try again.
- **Affected:** `app/(app)/error.tsx`, ErrorState.
- **Recommendation:** an error boundary inside the workspace layout and "Go to Home" beside Try
  again.
- **Sources:** UX-011 · **Task:** UI-025

#### UI-ISS-069 · P2 · UX flow · The knowledge test's "Not in your knowledge" is a dead end
- **Problem:** the Test box names the missing answer but offers no way to add it.
- **Affected:** TestBox, KnowledgePage.
- **Recommendation:** "Add answer", opening the FAQ sheet with the question filled in.
- **Sources:** UX-012 · **Task:** UI-057

#### UI-ISS-070 · P2 · UX flow · The composer's links to posting times and hashtag groups open nothing
- **Problem:** both link to `/schedule` with neither tool open; below 1440 px they live in the
  "Drafts and queue" sheet, so the user needs two more clicks and loses the composer.
- **Affected:** WhenSection, CaptionEditor, ScheduleRail, SchedulePage.
- **Recommendation:** open the Posting times sheet and the Hashtag groups dialog in place, or link
  with `?panel=` and open them on arrival.
- **Sources:** UX-013 · **Task:** UI-054

#### UI-ISS-071 · P2 · UX flow · "Upgrade" behaves three ways
- **Problem:** some Upgrade controls open the upgrade dialog, others navigate to Billing (read-only
  for admins), and Connections' "Auto · Pro" is disabled with no path.
- **Affected:** UsageCard, AppShell (credits banner), SourcesCard, AiSettingsPage, UpgradeAction,
  AccountCard.
- **Recommendation:** "Upgrade" always opens the upgrade dialog (which has Compare plans); choosing
  Auto on Free opens it too.
- **Sources:** UX-014 · **Tasks:** UI-063, UI-061

#### UI-ISS-072 · P2 · UX flow · Free users start Pro templates and find out at activation
- **Problem:** "Use template" works the same for Pro templates on Free; the limit shows only at
  Activate.
- **Affected:** TemplateGallery.
- **Recommendation:** "Try with Pro" opening the upgrade dialog, or say "You can set it up; it runs
  on Pro" on the card.
- **Sources:** UX-022 · **Task:** UI-063

#### UI-ISS-073 · P2 · UX flow · The Pro intent from the pricing page is lost after sign-up
- **Problem:** "Start free, then try Pro" signs up and lands on Home with no trial offer.
- **Affected:** Pricing, `lib/resolve.ts`, HomeScreen.
- **Recommendation:** carry `?plan=pro` through sign-up and open the upgrade dialog, or show a
  "Start your Pro trial" card on the first Home.
- **Sources:** UX-027 · **Task:** UI-063

#### UI-ISS-074 · P2 · UX flow · Connection errors vanish in toasts
- **Problem:** Instagram and WhatsApp connect failures, several of them multi-step instructions,
  disappear after a few seconds.
- **Affected:** connections page, ConnectWhatsAppButton, `lib/copy.ts`.
- **Recommendation:** the last connect error as a dismissible inline alert with Try again; toasts
  for success only.
- **Sources:** UX-015 · **Task:** UI-061

#### UI-ISS-075 · P2 · UX flow · Child pages use three back patterns
- **Problem:** post detail has "‹ Comments", the automation editor and post composer have
  "Automations /" and "Schedule /" breadcrumbs (UX-SCR-03), settings has a non-link breadcrumb; the
  inbox's back arrow shows only on phones.
- **Affected:** PageFrame, AutomationEditor, PostComposer, PostDetailPage, SettingsPageHeader.
- **Recommendation:** owner decision **D-16** (recommended: PageFrame's "‹ Parent" link
  everywhere).
- **Sources:** UX-016 · **Task:** UI-065

#### UI-ISS-076 · P2 · Hierarchy · Settings names the page four times; tab labels don't match titles
- **Problem:** each tab stacks the underlined tab, a breadcrumb, an eyebrow and a 30 px title (about
  140 px before content); the "Agent" tab opens "Ask Social Hood" and "Agent" is also a member
  role; "Billing" opens "Billing & Usage".
- **Affected:** SettingsPageHeader, `settings/sections.ts`, AgentSettingsPage, BillingPage.
- **Recommendation:** owner decision **D-08**.
- **Sources:** VH-005, UX-017 · **Task:** UI-060

#### UI-ISS-077 · P2 · UX flow · The settings save bar is always present; two save models on one page
- **Problem:** "All changes saved" sits in a shadowed bar permanently, even on Notifications where
  everything autosaves, and covers the row being edited; on AI Rules, modes save instantly while
  takeover and phrases wait for Save.
- **Affected:** SaveBar, AiSettingsPage, NotificationSettingsPage.
- **Recommendation:** owner decision **D-08** (recommended: the bar only when dirty, saving or
  failed; an inline "Saved" on autosave pages).
- **Sources:** UX-021, VH-017 · **Task:** UI-060

#### UI-ISS-078 · P2 · UX flow · The Scheduled tab ignores the platform filter
- **Problem:** the platform segments stay selectable on the Scheduled tab but change nothing.
- **Affected:** InboxShell, ScheduledList.
- **Recommendation:** apply the platform and account filter, or hide the strip on that tab.
- **Sources:** UX-018 · **Task:** UI-052

#### UI-ISS-079 · P2 · UX flow · Inbox views: no counts, a one-item More, state not in the URL
- **Problem:** Needs reply and Needs you show no counts though the counts query exists; "More"
  holds only Archived; view, platform and search live in component state, so Back, refresh, Copy
  link and Home's `?view=` (after first mount) lose them.
- **Affected:** ListHeader, InboxShell.
- **Recommendation:** counts on the two chips; `view` and `platform` in search params; Archived as a
  chip is part of **D-15**.
- **Sources:** UX-019 · **Task:** UI-052

#### UI-ISS-080 · P2 · UX flow · Account cards: two red actions, and "Remove" understates a permanent purge
- **Problem:** a healthy connected card's loudest elements are two red text buttons with
  near-identical labels; "Remove" on disconnected and sandbox cards permanently deletes every
  conversation, comment, post and automation.
- **Affected:** AccountCard, DeleteAccountDialog.
- **Recommendation:** owner decision **D-09** (recommended: Disconnect stays visible; "Delete account
  and data" in a ⋯ menu).
- **Sources:** UX-020, VH-006 · **Task:** UI-062

#### UI-ISS-081 · P2 · UX flow · Automations are Instagram-only but don't say so up front
- **Problem:** with only WhatsApp connected, the list, empty state and gallery all invite you to
  create automations; the editor says so only after.
- **Affected:** AutomationsPage, TemplateGallery, WhenStep.
- **Recommendation:** "Automations work on Instagram. Connect Instagram" in the empty state when no
  Instagram account exists; "Instagram DM keyword" where it matters.
- **Sources:** UX-023 · **Task:** UI-064

#### UI-ISS-082 · P2 · UX flow · AI caption writing replaces the caption with no undo
- **Problem:** "Write caption" and "Improve my caption" overwrite the user's caption; the inbox's AI
  Polish offers Undo, the composer doesn't.
- **Affected:** CaptionEditor.
- **Recommendation:** Undo in the success toast (or Replace / Keep before applying).
- **Sources:** UX-024 · **Task:** UI-008

#### UI-ISS-083 · P2 · UX flow · Schedule's "Add to queue" creates an empty post
- **Problem:** the header button opens a new draft in queue mode, which isn't what the label says.
- **Affected:** SchedulePage.
- **Recommendation:** remove it (the composer's When step has Add to queue) or rename it "New post
  in the queue".
- **Sources:** UX-025 · **Task:** UI-054

#### UI-ISS-084 · P2 · Hierarchy · A completed checklist keeps Home's best spot; Dismiss is permanent
- **Problem:** "4 of 4 done" keeps a 250 px card above the metrics until dismissed, pushing the
  priority queue below the fold on a 900 px laptop; Dismiss hides it for good without a way back.
- **Affected:** Checklist, HomeScreen.
- **Recommendation:** "You're all set" for one session, then hide; collapse done rows while
  incomplete; "Show setup checklist" in the workspace menu.
- **Sources:** VH-010, UX-026 · **Task:** UI-058

#### UI-ISS-085 · P2 · Copy · AI and automation attribution labels are ambiguous
- **Problem:** "AI Assisted" appears under fixed-text automation messages and under AI auto replies
  alike; the list prefix "Auto:" means "an automation sent this" next to an "AI Auto" badge that
  means the AI mode; the green "AI Auto" badge reads as a positive status.
- **Affected:** MessageBubble, `lib/inbox/format.ts`, ConversationRow, AiModeControl.
- **Recommendation:** owner decision **D-07** (recommended: the spec's "Sent by AI" and
  "Automation · {name}"; prefix "Automation:"; a neutral "Auto replies" badge; two badges per row
  at most).
- **Sources:** UX-006, UX-007, VH-009 · **Task:** UI-050

#### UI-ISS-086 · P2 · Copy · One concept, several names
- **Problem:** adding a missing answer is "Train AI", "Teach AI", "Add to knowledge" and "Add answer"
  (the sheet says "Add an FAQ"); six more concepts have two to five names (Needs you and Escalated,
  AI draft and suggestion, conversation, chat and thread, Canceled and Cancelled …).
- **Affected:** KnowledgeGapBanner, DetailsPanel, SuggestionCard, KnowledgeGapsCard, SourceSheet and
  the files in [UX_AUDIT §5](UX_AUDIT.md#5-terminology-table).
- **Recommendation:** the "Recommended" column of UX_AUDIT §5; "Add answer" everywhere.
- **Sources:** UX-008 · **Task:** UI-068

#### UI-ISS-087 · P2 · Hierarchy · The brand gradient marks every primary, so screens show 3–7 equal primaries
- **Problem:** Home (checklist CTA, Train AI, up to five Review & Send, Upgrade), the template
  gallery (six Use template), Knowledge (header, empty state, each gap row, Save, Ask), Billing (two
  Start trial) and Schedule on phones (three New post); spec §4.1 says one accent for primary
  actions.
- **Affected:** PriorityQueue, TemplateGallery, KnowledgeGapsCard, SourcesCard, BillingPage,
  PlanCards, AgendaView.
- **Recommendation:** owner decision **D-10** (recommended: one gradient primary per view region).
- **Sources:** VH-003 · **Task:** UI-059

#### UI-ISS-088 · P2 · Hierarchy · Two Send buttons; the draft bar dominates phones
- **Problem:** while a draft shows and the member types, two gradient Sends sit 60 px apart and send
  different text; on phones the bar takes about 160 px.
- **Affected:** SuggestionCard, Composer.
- **Recommendation:** when the composer has text, the draft's Send becomes secondary (or the bar
  collapses to "AI draft ready · Insert"); on phones clamp the draft to one line.
- **Sources:** VH-004 · **Task:** UI-051

#### UI-ISS-089 · P2 · Hierarchy · Knowledge leads with a form
- **Problem:** on a first visit the seven-field brand-voice form sits above Sources; titles truncate
  at about 12 characters with spare table width.
- **Affected:** KnowledgePage, SourcesCard, BrandVoiceCard.
- **Recommendation:** gaps (when any), Sources, then Brand voice collapsed to a summary with "Set
  up"; a wider Source column.
- **Sources:** VH-011 · **Task:** UI-057

#### UI-ISS-090 · P2 · Hierarchy · Post detail buries the comments on phones
- **Problem:** below 1024 px four analysis cards come before the comment list.
- **Affected:** PostDetailPage.
- **Recommendation:** post (compact), comments, then summary, topics and performance (or tabs).
- **Sources:** VH-012 · **Task:** UI-056

#### UI-ISS-091 · P2 · Hierarchy · The Schedule page stacks empty states
- **Problem:** "Plan your posts" sits above an empty week grid; on phones it sits above a second
  empty state, so three New post buttons show.
- **Affected:** SchedulePage, AgendaView.
- **Recommendation:** one empty state; the header's New post is the only primary.
- **Sources:** VH-013 · **Task:** UI-054

### P3 (25)

| ID | Category | Problem | Affected | Recommendation | Sources | Task |
|---|---|---|---|---|---|---|
| UI-ISS-092 | Layout & spacing | Off-grid values (`3.5`, `5.5`, `11`, `px-[3px]`), 234 `mt-*` used for stacking, negative bleeds; page rhythm drifts (`mb-4` vs `mb-6`, settings `pt-5`, section gaps 16/20/24) | Feature folders, SchedulePage, SettingsPageHeader, PaymentHistory | `gap`/`space-y` on parents; half-steps inside controls only; PageFrame's rhythm everywhere | SPC-005, SPC-006 | sweeps |
| UI-ISS-093 | Borders | Divider strength varies, dashed vs dotted, border vs ring cut-outs, 7 deprecated bare `rounded`, stray radii | AgendaView, ListView, cell-extras, ContactAvatar, FinalCta, marketing primitives | Fold into the radius and border rules when touched | RAD-009 | sweeps |
| UI-ISS-094 | Elevation | The current plan card stacks border, ring and brand glow; box-shadow used for a selection bar and a crop mask without a name | PlanCards, Threads, CropDialog | Border or ring alone in the app; glows marketing-only; the crop mask as a named utility | SHD-004, SHD-005 | sweeps |
| UI-ISS-095 | Colour | Token mirrors in Clerk, the OG image, the manifest and the logo SVG have no guard | `clerk-appearance.ts`, `og.tsx`, `manifest.ts`, `layout.tsx`, marketing primitives | Read from `tokens.ts` or test them against it; logo in `currentColor` | COL-019 | UI-070 |
| UI-ISS-096 | Components | Skeleton's default `bg-muted` is invisible on panel; 114 of 117 uses override it | `ui/skeleton`; UsageCard | Default `bg-raised`; drop the overrides | CMP-016, COL-020 | UI-016 |
| UI-ISS-097 | Colour | No named chart palette; categorical colours improvised | StatsPane, SentimentBar, SentimentCard, TrendLine | Status charts on status tokens; categorical series on the identity palette; keep StatsPane's legend + numbers + table pattern | COL-021 | sweeps |
| UI-ISS-098 | Typography | Weight 700 leaks through 33 `<strong>` and one `font-bold` at 9 px | Legal pages, AppSidebar | `strong, b { font-weight: 600 }`; remove the 9 px tag | TYP-013 | UI-001 |
| UI-ISS-099 | Typography | No default body size: unsized text is 16 px unless an ancestor sets 14 | AppShell | `text-sm` on the app's `<main>` | TYP-014 | UI-006 |
| UI-ISS-100 | Components | The `link` variant uses `brand` (4.54:1, 3.96:1 on raised); 7 raw buttons copy a link style | `ui/button`; workspace page, SuggestionCard, PostsStep, PostPanel, DetailsPanel, PostPreview, RunView | `link` in `brand-fg` with touch size; migrate | CMP-031 | UI-011, sweeps |
| UI-ISS-101 | Components | Three avatar wrappers, two platform-badge cut-outs, `AvatarBadge` unused | ContactAvatar, post-parts, AccountCard, InboxPreview | One avatar on `ui/avatar` with `AvatarBadge` | CMP-032 | UI-016, sweeps |
| UI-ISS-102 | Components | Empty and error states have no compact size; 13 inline copies; ErrorState's retry is 32 px | EmptyState, ErrorState and the 13 sites | `size="compact"` | CMP-034 | UI-025 |
| UI-ISS-103 | Components | Menu widths overridden at all 14 menus (8 widths); `DropdownMenuLabel` restyled at 6 of 7 | `ui/dropdown-menu` | `min-w-48 w-auto`; label `text-xs fg-secondary` | CMP-035 | UI-013 |
| UI-ISS-104 | Components | Native date/time fields, radios and one `<select>` where UX-CMP-01 lists primitives; the timezone list has no search | RangeControl, SettingsStep, ScheduleFields, MediaLibraryDialog, PostingTimesDrawer, PostPreview, workspace page | Owner decision **D-04**; Select for the native `<select>`; Command for the timezone later | CMP-030 | D-04, sweeps |
| UI-ISS-105 | UX flow | Four confirmation patterns; six "cancel" labels; a red "Cancel" next to "Cancel message" | ScheduledList, SchedulePage, ListView, HashtagGroupsDialog, BillingPage | AlertDialog for permanent actions (inline confirm inside dialogs); "Cancel", or "Keep …" when the action is "Cancel …" | UX-029, CMP-025 | UI-031, UI-068 |
| UI-ISS-106 | Copy | Stale and roadmap copy, Title Case and "&" labels, UK/US spelling, punctuation drift, an unclear reply-language hint, "Not now" as the only button for agents | `lib/copy.ts`, AiModeDialogs, DecisionInfo, AgentSettingsPage, PlanCards, UpgradeDialog, workspace page, footer | One copy pass (UX_AUDIT §6) plus a lint test | UX-030, UX-031, UX-035, UX-038 | UI-068 |
| UI-ISS-107 | UX flow | Two scheduling entry points with two names | ThreadHeader, Composer | Owner decision **D-15** (recommended: composer only, "Schedule message") | UX-028 | UI-051 |
| UI-ISS-108 | UX flow | The connections empty state offers only Instagram | connections page | Both Connect buttons | UX-032 | UI-061 |
| UI-ISS-109 | Copy | Ask's credit cost and "Nothing is sent until you do" are only in hints | AskConversation, ActionCardView | "Uses AI credits" under the composer; visible card hint | UX-033 | UI-068 |
| UI-ISS-110 | UX flow | Unsubscribe success has no undo or direct link | UnsubscribeResult | "Resubscribe" if the API allows, or a link to Settings › Notifications | UX-034 | UI-042 |
| UI-ISS-111 | Copy | Generic titles: the composer's h1 "Post", post detail's "Photo from {date}" | PostComposer, PostDetailPage | The caption's first line, truncated; "New post" for an empty draft | UX-037 | UI-068 |
| UI-ISS-112 | Hierarchy | Comment cards can't be told apart (caption screen-reader-only, "No spam" on every card) | PostCard | Show the caption's first line; spam only above 0 | VH-014 | UI-056 |
| UI-ISS-113 | Hierarchy | Below 1280 px the automation editor shows Preview/Test/Runs/Stats above the steps (as UX-SCR-03 says) | AutomationEditor | Owner decision **D-16** (recommended: after the steps) | VH-015 | UI-065 |
| UI-ISS-114 | Layout | While workspaces load, a full-page skeleton replaces the shell, then the shell pops in | `app/(app)/w/[slug]/layout.tsx`, PageSkeleton | Render the shell frame around the loading state | RSP-010 | UI-006 |
| UI-ISS-115 | Layout | On phones the composer's More drops to its own line, and "Inbox" shows twice | PostComposer, ListHeader, MobileNav | Keep actions on the title row; the list's h1 `sr-only` on phones | RSP-011 | UI-032, UI-069 |
| UI-ISS-116 | Accessibility | Every inbound image's alt text is "Photo" | AttachmentView | "Photo from {name}, {time}" | A11Y-022 | UI-066 |

---

## D. Owner decisions needed

Each item changes an approved decision (C-0xx), the spec, or the look. The recommendation is the
architect's; nothing in this list is implemented until the owner answers. Once decided, the
Design System Architect records it in CONFLICTS.md and AGENT_CONTEXT.md, and the blocked task
starts. Items marked **non-blocking defaults** in DESIGN_SYSTEM.md (token additions with no visible
change) are only logged for confirmation, like C-002.

### D-01 · A stronger control-border token
- **Context:** UX-A11Y-01 requires control borders of 3:1; today's edge is 1.35:1 and a field on a
  card has no visible shape (UI-ISS-004).
- **Options:**
  1. Add `line-control` (white 40%) for checkbox, radio and switch edges only, and amend UX-A11Y-01
     to exempt labelled text fields (WCAG allows that when the label identifies the field).
  2. As 1, and also text inputs, selects and textareas (`--input` → `line-control`).
  3. Keep today's hairlines and accept the spec breach.
- **Recommendation: option 2.** Without it, fields on cards have no boundary at all (fill 1.02:1).
  White 40% passes on every surface (3.4–3.8:1); the solid greys the audits proposed fail on raised
  or overlay surfaces (`#71717A` 2.97:1 on raised, `#6B6B6B` 2.84:1 on overlay).
- **Impact:** visible: every input, select and checkbox edge goes from a faint hairline to a
  mid-grey line; focused fields still turn brand. The mockups use faint edges. One alias in
  `globals.css`; switch and checkbox details in the field pass. **Blocks:** UI-018 (part).

### D-02 · Card radius: `xl` or `2xl`
- **Context:** spec §4.2 says cards are `rounded-xl` and 76 cards are; C-066 built 21 settings,
  billing and connections surfaces at `rounded-2xl`, although the settings mockups themselves use
  12 px (`xl` = 0.75rem there).
- **Options:** 1. `xl` for every app card. 2. `2xl` for every card (76 surfaces and the spec
  change). 3. Keep both.
- **Recommendation: option 1.** It matches the spec, the settings mockups and 78% of cards, and is
  the smaller change. `2xl` stays for message bubbles and marketing.
- **Impact:** settings, billing and connections cards lose 4 px of corner; their inset panels
  become `rounded-lg`. **Blocks:** the radius part of UI-037.

### D-03 · Tooltip colour
- **Options:** 1. Keep the inverted white tooltip (shadcn's default, 21:1). 2. A dark tooltip like
  every other floating surface: `overlay` (or `panel`), `fg` text, a line edge and the floating
  shadow.
- **Recommendation: option 2.** It is the only light surface in a dark-only app, and the system's
  rule is one floating-surface style; `fg` on `overlay` is 15.1:1.
- **Impact:** `ui/tooltip.tsx` only (7 tooltips, plus the new DisabledReason). **Blocks:** UI-017.

### D-04 · Native date and time pickers for R1
- **Context:** UX-CMP-01 lists Calendar; 9 date and time fields use native inputs, whose pickers
  render in OS chrome. The e2e suite (F-13) fills them as text boxes.
- **Options:** 1. Accept native date and time inputs for R1, styled like Input. 2. Build Calendar
  and a time picker now.
- **Recommendation: option 1.** Native pickers are accessible, localised and touch-friendly;
  building pickers is a feature, not a consistency fix. Add Calendar when a range picker or R2
  needs it, and record the deviation from UX-CMP-01.
- **Impact:** option 1 needs no task beyond routing the fields through Input in the sweeps;
  option 2 adds a Calendar task and e2e changes. **Blocks:** nothing (option 2 would add UI-029).

### D-05 · Page-title size
- **Context:** page titles are 24 px (spec, Home, PageFrame) and 30 px from `md` on Settings
  (C-066's mockup); pane titles are 18 px (Inbox; spec says 20), 16 px (Ask) and 16 px (phone top
  bar).
- **Options:** 1. Page H1 24 px everywhere; pane H1 18 px for Inbox, Ask and the phone top bar;
  update the spec's pane title to `text-lg`. 2. A named "hero title" (30 px) on every hub page,
  including Settings.
- **Recommendation: option 1.** One anchor per page, the smallest change (one settings header, two
  pane titles).
- **Impact:** SettingsPageHeader, AskPage, MobileNav. **Blocks:** UI-069.

### D-06 · Placeholder contrast against the spec's `fg-disabled` rule
- **Context:** spec §4.2 assigns `fg-disabled` to placeholders (3.41:1 on panel); WCAG 1.4.3
  applies to placeholder text; the shadcn primitives already use `fg-secondary` (6.0:1).
- **Options:** 1. Placeholders `fg-secondary`; `fg-disabled` for disabled controls only; amend the
  spec. 2. Keep `fg-disabled` and accept the AA failure.
- **Recommendation: option 1.** Entered text (`fg`, 16.5:1) stays clearly brighter than a
  placeholder.
- **Impact:** placeholders in the composer, search, template, emoji and hashtag fields get lighter.
  **Blocks:** UI-018 (part).

### D-07 · "AI Assisted" on fixed-text automations (C-063)
- **Context:** C-063 shows "AI Assisted" under `ai_auto` and `automation` messages, so fixed-text
  automations are credited to the AI; "Auto:" (automation) sits beside "AI Auto" (AI mode).
- **Options:** 1. Keep C-063's labels. 2. The spec's wording (UX-INB-06): `ai_auto` → "Sent by AI"
  with the info button; `automation` → "Automation · {name}" with a zap icon, plus "AI" only when
  the step was an AI reply; list prefix "Automation:"; row badge "Auto replies", neutral, at most two
  badges per row.
- **Recommendation: option 2.**
- **Impact:** MessageBubble, `lib/inbox/format.ts`, ConversationRow and their tests. **Blocks:**
  UI-050.

### D-08 · The settings breadcrumb, tab labels and always-visible save bar (C-066)
- **Context:** every tab names the page four times; tab and title disagree ("Agent" opens "Ask
  Social Hood", and Agent is also a member role); the save bar shows "All changes saved" forever,
  even on pages that autosave; the Agent tab spends half the page on six "Coming later" tiles.
- **Options and recommendation per item:**
  1. Breadcrumb and eyebrow: keep / drop both / drop the breadcrumb only. **Drop both**; the tabs
     are the location.
  2. Tab labels: keep / match the titles ("Ask Social Hood", "Billing and usage", "AI rules and
     takeover"). **Match.**
  3. Save bar: always / only when dirty, saving or failed, with an inline "Saved" status on
     autosave pages. **Only when needed.**
  4. Agent capability tiles: keep six / one sentence ("Ask Social Hood can't send or change
     anything. It only prepares drafts for you."). **One sentence.**
- **Impact:** SettingsPageHeader, `settings/sections.ts`, SaveBar, AiSettingsPage,
  NotificationSettingsPage, AgentSettingsPage; about 100 px back on every tab. No e2e spec uses the
  settings breadcrumb. **Blocks:** UI-060.

### D-09 · "Remove" as a label (C-067)
- **Context:** connected cards show two red text buttons; "Remove" permanently deletes a
  disconnected or sandbox account's data.
- **Options:** 1. Keep C-067's labels and placement. 2. Disconnect stays visible as a neutral
  ghost button; one "Delete account and data" item for both modes in a ⋯ menu, opening the same
  typed-confirm dialog.
- **Recommendation: option 2.** The API is unchanged.
- **Impact:** AccountCard, DeleteAccountDialog copy. **Blocks:** UI-062.

### D-10 · The brand gradient on every primary button (VH-003)
- **Options:** 1. Any primary action gets the gradient (today). 2. At most one gradient primary per
  view region (page header, dialog footer, composer); row and card actions are secondary.
- **Recommendation: option 2.** It restores spec §4.1's "one accent … for primary actions".
- **Impact:** about 20 call sites demoted (Review & Send rows, Use template cards, Add answer rows,
  the duplicate trial CTA, extra New post buttons). **Blocks:** UI-059.

### D-11 · The Comments badge needs an API filter (UX-001)
- **Options:**
  1. Per post: `needs_reply_count` on PostSummary and a `needs_reply` filter on a post's comments;
     "n need a reply" on post cards, the grid sorted by it, a Needs reply chip on post detail.
  2. A cross-post "Needs reply" list as Comments' default view (a new list endpoint).
  3. Hide the badge until 1 or 2 ships.
- **Recommendation: option 1 now**, option 2 later if usage shows the need.
- **Impact:** API (schema, a filter, the generated client), CommentsPage, PostCard, CommentsColumn,
  `lib/comments/format.ts`. **Blocks:** UI-055.

### D-12 · Overlay elevation
- **Context:** overlays are the same `panel` as the cards beneath (1.00:1) and Tailwind's shadows
  don't show on near-black (UI-ISS-031).
- **Options:** 1. Spec only: the 60% scrim (UX-SH-02) and the spec's `shadow-xl` in the primitives.
  2. Also an `overlay` surface (`#262626`, the value shadcn's input fill already renders on panel)
  and two dark elevation shadows (floating, overlay) replacing `shadow-md`/`xl` and the 10% ring.
- **Recommendation: option 2.** Dark interfaces show elevation through lightness; it adds no hue.
- **Impact:** every overlay looks slightly lighter and lifted; tokens plus 7 primitives; toasts
  follow. Option 1 ships regardless in UI-012 and UI-013. **Blocks:** UI-018 (part), the surface of
  UI-017.

### D-13 · Identity palette for avatars and schedule accounts
- **Options:** 1. Up to four gradient pairs built only from existing brand, shell and platform-blue
  values (candidates in COLOR_SYSTEM §11.6), no status colour, each stop at least 4.5:1 with white,
  shared by avatar fallbacks and account rings. 2. Six pairs, adding two new hues (teal `#0F766E`,
  violet `#6D28D9`). 3. Keep today's six (three fail and borrow warning and success).
- **Recommendation: option 1.** Names sit next to every avatar, so four pairs are enough, and no
  new colour is introduced.
- **Impact:** inbox avatars change colour; `lib/inbox/format.ts`, `lib/schedule/format.ts`,
  ContactAvatar. **Blocks:** UI-027.

### D-14 · Single-key inbox shortcuts (FR-INB-12, WCAG 2.1.4)
- **Options:** 1. A per-device "Single-key shortcuts" switch, on by default, in a small Keyboard
  shortcuts dialog (j, k, /, e, u, Esc) opened from the inbox list header and with "?".
  2. Shortcuts only while focus is in the conversation list.
- **Recommendation: option 1.** It keeps today's behaviour, meets 2.1.4 and makes the shortcuts
  discoverable; option 2 breaks j/k in Safari, where clicking a row doesn't focus it.
- **Impact:** `use-inbox-shortcuts.ts`, InboxShell, one small dialog. **Blocks:** UI-053.

### D-15 · Inbox refinements that revisit C-063
- **Items and recommendation:**
  1. Active platform segment: filled `brand-strong` (C-063's look, now passing AA) / neutral
     `raised` with `brand-fg` like every other segmented control. **Neutral.**
  2. Heart button: keep (instant send) / move into the emoji popover ("Send a heart") / keep with a
     3-second Undo. **Emoji popover.**
  3. Header "Schedule a message" clock: keep both entry points / composer only, named "Schedule
     message". **Composer only.**
  4. Archived: behind "More" / a plain chip. **Plain chip.**
- **Impact:** PlatformStrip (and its test), Composer, EmojiPicker, ThreadHeader, ListHeader.
  **Blocks:** item 1 in UI-030, items 2–3 in UI-051, item 4 in UI-052.

### D-16 · Layouts the spec prescribes
- **Items and recommendation:**
  1. Child pages: PageFrame's "‹ Parent" link on the automation editor, post composer and post
     detail, instead of UX-SCR-03's "Automations /" text. **Back link.** The e2e specs F-11 and
     F-13 navigate through the "Breadcrumb" landmark and must be updated.
  2. Automation editor below 1280 px: side panel after the steps (or a Preview button) instead of
     above (UX-SCR-03). **After the steps.**
  3. Icon-only buttons: `rounded-lg` as built / `rounded-full` as spec §4.2 says. **`rounded-lg`**
     (31 primitive icon buttons already are; 23 raw ones change); `rounded-full` stays for things
     that are circles (avatars, dots, switches).
  4. Composer shells: `rounded-xl` as the inbox composer is built / the spec's 20 px pill
     (UX-INB-07). **`rounded-xl`**; Ask's composer moves from `2xl`.
- **Impact:** items 1–2: UI-065; items 3–4: the area sweeps (AskPanel.test's composer assertion).

### D-17 · Devanagari fallback font
- **Options:** 1. Accept the system fallback for Hindi-script messages in R1 (`latin-ext` is added
  regardless, for ₹ and accented names). 2. Add Noto Sans Devanagari through `next/font` as a
  matched fallback.
- **Recommendation: option 1** for R1; revisit if Hindi-script volume is high.
- **Impact:** option 2 adds one font file on pages that render Devanagari. **Blocks:** nothing.

---

## Appendix 1: source ID index

Every finding of the area audits maps to one or more canonical issues (the number after the arrow
is the UI-ISS number).

- **COLOR_SYSTEM:** COL-001→005 · 002→006, 054 · 003→002, 003 · 004→004 · 005→010, 025 ·
  006→007 · 007→027 · 008→009 · 009→029 · 010→031 · 011→004, 008, 030 · 012→028 ·
  013→028, 037, 055 · 014→054 · 015→054 · 016→005, 025, 053 · 017→031 · 018→043 · 019→095 ·
  020→026, 096 · 021→097
- **TYPOGRAPHY:** TYP-001→017 · 002→047 · 003→048 · 004→049 · 005→041 · 006→050, 007 · 007→035 ·
  008→046 · 009→039 · 010→051 · 011→052 · 012→047 · 013→098 · 014→099 · 015→050
- **SPACING:** SPC-001→011 · 002→036 · 003→051 · 004→039 · 005→092 · 006→092 · 007→035 ·
  RAD-001→036 · 002→002 · 003→004 · 004→035 · 005→046 · 006→029, 031 · 007→053 · 008→036 ·
  009→093 · SHD-001→031 · 002→031 · 003→031 · 004→094 · 005→053, 094
- **COMPONENT_AUDIT:** CMP-001→001 · 002→010 · 003→009 · 004→011 · 005→011, 033 · 006→005 ·
  007→003 · 008→002 · 009→004 · 010→026 · 011→008, 011, 030 · 012→039 · 013→027, 035 ·
  014→012, 031, 032 · 015→029 · 016→012, 096 · 017→044 · 018→033 · 019→034 · 020→036 · 021→037 ·
  022→027, 038 · 023→043 · 024→011, 041 · 025→105 · 026→042 · 027→045 · 028→025 · 029→040 ·
  030→104 · 031→100 · 032→101 · 033→051 · 034→011, 102 · 035→103
- **ACCESSIBILITY:** A11Y-001→015 · 002→016 · 003→003 · 004→002 · 005→005, 006, 007, 008, 009 ·
  006→004 · 007→013 · 008→014 · 009→011 · 010→012 · 011→039 · 012→060 · 013→061 · 014→043 ·
  015→033, 062 · 016→063 · 017→064 · 018→065 · 019→031 · 020→062 · 021→062 · 022→116 · 023→032 ·
  024→058
- **RESPONSIVE:** RSP-001→018 · 002→019 · 003→056 · 004→043 · 005→057 · 006→014 · 007→041 ·
  008→031 · 009→059 · 010→114 · 011→033, 115 · 012→058 · 013→037
- **MOTION:** MOT-001→012 · 002→032 · 003→013 · 004→012 · 005→032 · 006→044 · 007→032 · 008→032 ·
  009→012
- **UX_AUDIT:** UX-001→024 · 002→021 · 003→022 · 004→020 · 005→023 · 006→085 · 007→085 · 008→086 ·
  009→066 · 010→067 · 011→068 · 012→069 · 013→070 · 014→071 · 015→074 · 016→075 · 017→076 ·
  018→078 · 019→079 · 020→080 · 021→077 · 022→072 · 023→081 · 024→082 · 025→083 · 026→084 ·
  027→073 · 028→107 · 029→105 · 030→106 · 031→106 · 032→108 · 033→109 · 034→110 · 035→106 ·
  036→019 · 037→111 · 038→106 · VH-001→018 · 002→019 · 003→087 · 004→088 · 005→076 · 006→009, 080 ·
  007→037 · 008→033 · 009→058, 085 · 010→084 · 011→089 · 012→090 · 013→091 · 014→112, 024 ·
  015→113 · 016→036, 048, 049 · 017→077

## Appendix 2: corrections made to the area audits

Two factual errors were found while verifying and are fixed in place:

- **COLOR_SYSTEM.md §3.1 and COL-005** said 54 default-variant Buttons add
  `bg-brand-gradient text-white`. 54 Buttons use the default variant: 50 add the gradient and 4
  add `bg-danger-fill` (as COMPONENT_AUDIT CMP-002 says; re-counted from the JSX).
- **RESPONSIVE.md RSP-001** cited `HomeScreen.tsx:197` for the insight-card grid; it is line 193
  (line 116 is the loading skeleton's grid). UX_AUDIT VH-001 had it right.
