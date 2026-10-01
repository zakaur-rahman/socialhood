# UI implementation plan

How the 116 issues in [UI_AUDIT.md](UI_AUDIT.md) get fixed, reaching the system in
[DESIGN_SYSTEM.md](DESIGN_SYSTEM.md). Every implementing agent reads
[AGENT_CONTEXT.md](AGENT_CONTEXT.md) first.

- **Shape of the plan.** Fix at the source first: tokens (Wave 0) and the primitives in
  `components/ui/*` (Wave 1) resolve most P1s and change every call site at once. New shared
  components follow (Wave 2). Each feature area then adopts them in one sweep (Wave 3), screen-level
  UX fixes come after (Wave 4), and the palette is locked and reviewed last (Wave 5). Small P1 fixes
  in feature files run in Wave 0, in parallel, because they don't wait for anything.
- **Sizing.** Each task is one branch (`feature/ui-<group>`) and one squash-merged PR that can be
  reviewed alone. A task never edits a file another open task owns (§E).
- **Agents.** The eight roles: Design System Architect (DSA), Component Engineer, Layout &
  Responsive Engineer (Layout), UX Engineer, Accessibility Engineer (A11y), Motion Engineer, Visual
  QA, Final Design-System Reviewer (Reviewer). A role can run several instances in parallel on
  different tasks.

**Counts.** 67 tasks: 56 can start as soon as their dependencies merge; 11 wait for an owner
decision, and 5 more have a part that waits (UI-030, UI-037, UI-040, UI-051, UI-052). See "Ready
now, and blocked" below.

| Agent | Tasks | IDs |
|---|---:|---|
| Design System Architect | 6 | UI-001, UI-010, UI-018, UI-027, UI-070, UI-071 |
| Component Engineer | 25 | UI-011, UI-014, UI-015, UI-016, UI-017, UI-020–UI-026, UI-030–UI-042 |
| Layout & Responsive Engineer | 9 | UI-003, UI-004, UI-006, UI-009, UI-028, UI-056, UI-057, UI-065, UI-069 |
| UX Engineer | 15 | UI-005, UI-008, UI-050–UI-052, UI-054, UI-055, UI-058–UI-064, UI-068 |
| Accessibility Engineer | 5 | UI-002, UI-007, UI-013, UI-053, UI-066 |
| Motion Engineer | 2 | UI-012, UI-067 |
| Visual QA | 3 | UI-019, UI-043, UI-072 |
| Final Design-System Reviewer | 2 | UI-044, UI-073 |

---

## D. Tasks

**Conventions in every task.**
- **Validation "G"** = the gates: `pnpm lint`, `pnpm typecheck`, `pnpm test` and `pnpm build` at
  the repository root, all green. "E2E" = `pnpm e2e` green on an isolated stack. "VQA" =
  before-and-after screenshots at 375, 768, 1280 and 1536 px of the screens the task touches, on the
  isolated stack, with touch emulation (`hasTouch`, `isMobile`) at 375 and 768 (AGENT_CONTEXT §11).
- **Acceptance** always includes the definition of done (§H); only task-specific criteria are
  listed.
- **Issues** are UI-ISS numbers from UI_AUDIT.md; the evidence is in the source audits named there.

### D.1 Wave 0: tokens and quick P1 fixes

#### UI-001 · Token foundation
- **Priority · area · agent · branch:** P1 · Tokens · Design System Architect ·
  `feature/ui-tokens` · **ready now**
- **Issues:** 005, 012, 025, 027, 028, 029, 032, 047, 050, 058, 098 (foundation for most others).
- **Problem:** missing token layers force raw `white`/`black` utilities and opacity recipes; four
  alias utilities generate no CSS; gradient stops are hex literals; 11 px and 15 px have no tokens;
  there are no motion tokens and no reduced-motion safety net; type roles are documentation only.
- **Current:** `globals.css` is UX-TOK-01 plus C-002; `tokens.ts` mirrors it; `typeRoles` feeds
  only `/dev/tokens`.
- **Desired:** the **Add** items of DESIGN_SYSTEM §1.13, §1.9 and §7: `hover`, `pressed`, `scrim`,
  `media-scrim`, `on-brand`, `brand-strong`, the three `*-soft`; `text-2xs`, `text-md`; the three
  easings, the duration variables and `duration-fast|normal|slow` utilities; `--breakpoint-wide`;
  gradient stops as `var()` (brand ends at `brand-strong`); `bg-glow-brand` (from the existing
  radial value) and `mask-fade-x` utilities; `--primary` → `brand-strong`,
  `--primary-foreground` → `on-brand`, `--accent` → `hover`; the four `*-foreground` mappings;
  base layer: `strong, b { font-weight: 600 }`, the reduced-motion safety net,
  `scroll-padding-top: 4rem` below `md`; `--radius` commented as inert; `tokens.ts` mirrors all of
  it and exports the type-role constants (`EYEBROW` …) for import; `/dev/tokens` renders them; one
  CONFLICTS entry (the next free number) lists the additions as "open: confirm", like C-002.
- **Files:** `apps/web/src/styles/globals.css`, `styles/tokens.ts`, `styles/tokens.test.ts`,
  `app/(dev)/dev/tokens/page.tsx`, `docs/CONFLICTS.md`.
- **Depends on:** nothing.
- **Acceptance:** no visible change on any app screen except the `--primary` remap. Every
  `*-primary` use is inside `components/ui`: the switch's checked track and the checkbox fill become
  `brand-strong` (3.4:1 on panel, still above 3:1); the `link` variant's `text-primary` would fail as
  text, but both its call sites override it to `brand-fg` (verify; UI-011 fixes the variant); Badge
  and AvatarBadge defaults are unused;
  the compiled CSS contains rules for `text-popover-foreground`, `text-accent-foreground`,
  `text-secondary-foreground` and `text-card-foreground`; `tokens.test.ts` asserts that every
  `:root` alias has a `--color-*` mapping and pins the new values and gradient strings; with
  emulated reduced motion, opening a dialog, a menu and the phone drawer shows no animation.
- **Validation:** G; a Tailwind compile check of the new utilities; Playwright with
  `reducedMotion: "reduce"` on one dialog and the drawer; screenshots of `/dev/tokens` and Home at
  1280.

#### UI-002 · Text-contrast fixes
- **Priority · area · agent · branch:** P1 · Colour · Accessibility Engineer ·
  `feature/ui-contrast` · after UI-001
- **Issues:** 005 (call sites), 007, 002 (Clerk), 032 (sidebar outline fade).
- **Problem:** white on solid brand (3.63:1), 11 px group labels at 3.64:1, neutral badges at
  4.45:1, text dimmed by `opacity-80`, bubble labels at 3.46:1, Clerk's focus at 22%, and a focus
  outline that fades in from grey.
- **Current:** `bg-brand text-white` (PlatformStrip, marketing skip link); Clerk `colorPrimary`
  `#567FF8`; `text-fg-secondary/70`; `bg-white/10` badges; `opacity-80` plan card; `text-white/75`
  and `/90` in bubbles; `transition-colors` on sidebar rows.
- **Desired:** PlatformStrip's active segment `bg-brand-strong text-on-brand` (C-063's look kept
  until D-15); both skip links `bg-panel text-fg` with the focus outline (same as UI-006's);
  Clerk's `colorPrimary` mirrors `brand-strong` and its user-button trigger shows the 2 px outline;
  group labels `text-fg-secondary`; neutral badges `bg-hover`; the Max card dims its border and fill,
  not its text; bubble labels `text-on-brand`; sidebar rows `transition-[color,background-color]`.
- **Files:** `inbox/PlatformStrip.tsx` (+ test), `app/(marketing)/layout.tsx`,
  `lib/clerk-appearance.ts`, `shell/AppSidebar.tsx`, `shell/sidebar-styles.ts`,
  `shell/WorkspaceMenu.tsx`, `billing/BillingPage.tsx`, `billing/PlanCards.tsx`,
  `inbox/MessageBubble.tsx`.
- **Depends on:** UI-001.
- **Acceptance:** every pair in A11Y-005 items 1, 3, 5, 7 and 8 measures 4.5:1 or more in the
  browser; axe `color-contrast` clean on the inbox, a conversation, Billing and `/` at 375 and
  1280; Clerk's sign-in button text 4.5:1 or more; Tab to the account button shows a 3:1 indicator;
  sidebar focus appears in brand at once. Tests: `PlatformStrip.test.tsx:24, 27, 29`.
- **Validation:** G; axe at 375 and 1280 on those pages; VQA.

#### UI-003 · Home overflow on phones
- **Priority · area · agent · branch:** P1 · Layout · Layout Engineer · `feature/ui-home-overflow`
  · **ready now**
- **Issues:** 018.
- **Problem / current:** `grid gap-3 lg:grid-cols-3` with no explicit column lets a `truncate`
  caption size the track to 483 px; Home is 499 px wide on a 390 px phone.
- **Desired:** `grid grid-cols-1 gap-3 lg:grid-cols-3` (also the skeleton grid); `min-w-0` on the
  three sections; the other grids in `components/home` checked the same way.
- **Files:** `home/HomeScreen.tsx`, `home/TopPostsCard.tsx`, `home/SentimentCard.tsx`,
  `home/TopIntentsCard.tsx`.
- **Depends on:** nothing.
- **Acceptance:** `scrollWidth ≤ clientWidth` on Home at 320, 360, 375 and 768; captions end in an
  ellipsis; 1280 and 1536 unchanged.
- **Validation:** G; a Playwright overflow measurement at those widths; VQA.

#### UI-004 · The thread header on narrow widths
- **Priority · area · agent · branch:** P1 · Layout · Layout Engineer ·
  `feature/ui-thread-header` · **ready now**
- **Issues:** 019, 006, 056 (header part).
- **Problem / current:** the contact's name is the only shrinkable item and collapses to 0 px below
  1024 px; the window chip overlaps the AI menu; "Needs you" is hidden below 768 px; "Instagram" is
  2.73:1; at 320 px the More button is clipped.
- **Desired:** the name keeps a minimum width; below `md` the window chip moves to the handle line
  or shows compact; the AI pill shows as an icon below `sm` (label kept for screen readers); "Needs
  you" shows at every width (compact on phones); the platform name in `fg-secondary` beside its
  glyph; below 360 px the details toggle moves into More. C-063's layout is unchanged at 1024 px
  and up.
- **Files:** `inbox/ThreadHeader.tsx` (+ test), `inbox/ReplyWindowChip.tsx`,
  `ai/AiModeControl.tsx`.
- **Depends on:** nothing.
- **Acceptance:** with a long contact name, at least 80 px of name is visible at 320, 360, 375 and
  768, and no two header elements overlap (bounding boxes) from 320 to 1536; at 1440 with the panel
  open at least 12 characters show; "Needs you" visible on phones; the platform name 4.5:1 or more.
  Tests: `ThreadHeader.test.tsx:50–54` if the chip's classes change.
- **Validation:** G; a Playwright bounding-box check at 320–1536 with a long-named sandbox
  contact; VQA.

#### UI-005 · Stale AI-reply copy
- **Priority · area · agent · branch:** P1 · Copy · UX Engineer · `feature/ui-automation-copy` ·
  **ready now**
- **Issues:** 023.
- **Problem / current:** ThenStep says AI replies "start working when Knowledge arrives in Social
  Hood".
- **Desired:** "The AI answers from your knowledge. When the answer isn't there, it sends nothing
  and moves the conversation to Needs you.", with a link to Knowledge for owners and admins.
- **Files:** `automations/steps/ThenStep.tsx` (+ test if the string is asserted).
- **Depends on:** nothing.
- **Acceptance:** the sentence and link render in the AI-reply step; nothing else changes.
- **Validation:** G.

#### UI-006 · App shell frame
- **Priority · area · agent · branch:** P1 · Layout · Layout Engineer · `feature/ui-shell-frame` ·
  **ready now**
- **Issues:** 016, 020, 099, 114, 062 (the shell's `aside`).
- **Problem / current:** no skip link; `<main>` has no id; the nav is wrapped in an unlabelled
  `aside`; unsized text is 16 px; the inbox and Ask frames are `calc(100dvh − n)` with banners above
  them; a full-page skeleton replaces the shell while workspaces load.
- **Desired:** "Skip to content" first in AppShell (`sr-only` until focused, `bg-panel text-fg` with
  the focus outline) to `<main id="main" tabIndex={-1}>`; the wrapper becomes a `div`; `text-sm` on
  `<main>`; `<main>` is a full-height flex column, banners in flow, InboxShell and AskPage frames
  `flex-1 min-h-0`; the workspace layout renders the shell frame around its loading state.
- **Files:** `shell/AppShell.tsx`, `shell/BannerSlot.tsx`, `inbox/InboxShell.tsx`,
  `agent/AskPage.tsx` (+ test), `app/(app)/w/[slug]/layout.tsx`, `states/PageSkeleton.tsx` if
  needed.
- **Depends on:** nothing.
- **Acceptance:** the first Tab on any app page shows the skip link and Enter moves focus into
  `<main>`; with a banner showing (a reconnect-needed sandbox account), the inbox composer and the
  Ask box are fully visible at 375 × 667 and 1280 × 800 without scrolling the page; unsized text is
  14 px in the app; no layout jump when `/v1/workspaces` resolves; axe landmark rules clean. Tests:
  `AskPage.test.tsx:137`.
- **Validation:** G; a Playwright keyboard test and a banner screenshot; axe; VQA.

#### UI-007 · Focus, dialog mounting and Send size at call sites
- **Priority · area · agent · branch:** P1 · Accessibility · Accessibility Engineer ·
  `feature/ui-focus-fixes` · **ready now**
- **Issues:** 003, 013, 011 (Send).
- **Problem / current:** 13 raw fields set `outline-none` and show focus as a 1.17:1 fill change;
  the inbox composer only lightens its border; five dialogs mount only while open, losing focus and
  their exit; Send is 36 px on phones (C-018 says 40).
- **Desired:** remove `outline-none` on those fields (the global outline shows; the fill stays as
  an extra cue); the composer's wrapper shows the outline with `has-[textarea:focus-visible]:`; the
  dialogs stay mounted and are driven by `open` (or use `use-return-focus`); Send `h-10 md:h-8`.
- **Files:** `inbox/ListHeader.tsx`, `inbox/Composer.tsx`, `inbox/EmojiPicker.tsx`,
  `inbox/ScheduledList.tsx`, `inbox/TemplatePicker.tsx`, `inbox/ScheduleFields.tsx`,
  `schedule/HashtagGroupsDialog.tsx`, `schedule/ListView.tsx`, `schedule/PostingTimesDrawer.tsx`,
  `schedule/MoveToDialog.tsx`, `schedule/SchedulePage.tsx` (the MoveToDialog mount),
  `composer/MediaLibraryDialog.tsx`, `composer/PostPreview.tsx`, `automations/AutomationsPage.tsx`,
  `automations/AgentDraftDialog.tsx`.
- **Depends on:** nothing.
- **Acceptance:** each listed field shows a 3:1 focus indicator when focused by keyboard; after Esc
  on each of the five dialogs, focus is on the trigger; closing them plays the exit animation (no
  reduced motion); Send is 40 px tall at 375 px and 32 px at 1280.
- **Validation:** G; Playwright keyboard and focus-return checks; VQA of the focused states.

#### UI-008 · Scheduled-post safety and leave guards
- **Priority · area · agent · branch:** P1 · UX flow · UX Engineer · `feature/ui-post-safety` ·
  **ready now**
- **Issues:** 021, 022, 082.
- **Problem / current:** "Save as draft" unschedules a scheduled post without asking; scheduled
  posts and brand voice lose edits on in-app navigation; AI caption writing replaces the caption
  with no undo.
- **Desired:** on scheduled posts, no "Save as draft" in the bar; "Unschedule" in ⋯ with an
  AlertDialog ("It won't publish until you schedule it again."); Update schedule is the save;
  `useLeaveWarning(dirty && !autosave)` in the composer and the brand-voice form (import it from
  `settings/SaveBar.tsx`, or move it to its own file without changing SaveBar's behaviour); the
  caption tools' success toast offers Undo, restoring the previous caption exactly.
- **Files:** `composer/PostComposer.tsx`, `composer/use-post-draft.ts`,
  `composer/CaptionEditor.tsx`, `knowledge/BrandVoiceCard.tsx` (+ tests); `settings/SaveBar.tsx`
  only if the hook moves.
- **Depends on:** nothing.
- **Acceptance:** tests: a scheduled post shows no Save as draft; Unschedule calls the API only
  after confirming; a dirty scheduled post asks before a sidebar link navigates, a clean one and an
  autosaving draft don't; Undo restores the caption. E2E F-13 stays green (it leaves through the
  breadcrumb after scheduling, when the post is clean).
- **Validation:** G; E2E F-13; a manual leave through the sidebar, breadcrumb and a notification.

#### UI-009 · Sticky bars and focus not obscured
- **Priority · area · agent · branch:** P1 · Layout · Layout Engineer · `feature/ui-sticky-bars` ·
  after UI-001, UI-008
- **Issues:** 014, 031 (the save bar's blur).
- **Problem / current:** focused controls scroll under the save bar, the composer's action bar and
  the phone top bar; the bars take 25–40% of a short viewport; the save bar blurs behind a 95%
  surface.
- **Desired:** pages with a bottom bar set `scroll-padding-bottom` to the bar's height (a class or a
  CSS variable the bar sets); the bars become static at `max-height: 500px`; the save bar is opaque
  `bg-panel` without blur and with the spec's shadow; the composer's "why disabled" lines collapse to
  one line on short viewports. (Hiding the clean save bar is D-08, UI-060.)
- **Files:** `settings/SaveBar.tsx`, `composer/PostComposer.tsx` (action bar), `shell/MobileNav.tsx`,
  the settings layout if the padding lives there.
- **Depends on:** UI-001 (the top padding rule), UI-008 (PostComposer).
- **Acceptance:** tabbing forwards and backwards through Settings › AI and the post composer at
  375 × 700, every focused control is fully outside the bars' rectangles; at 640 × 450 the bars
  don't stick; the save bar's computed `backdrop-filter` is `none`.
- **Validation:** G; a Playwright focus-visibility check at 375 × 700 and 640 × 450; VQA.

#### UI-010 · Font subsets
- **Priority · area · agent · branch:** P2 · Typography · Design System Architect ·
  `feature/ui-fonts` · **ready now**
- **Issues:** 052 (D-17 option 1 assumed; option 2 would add a Devanagari fallback here).
- **Problem / current:** `subsets: ["latin"]`, so ₹ and latin-ext names fall back to the system font.
- **Desired:** `["latin", "latin-ext"]` for Geist and Geist Mono.
- **Files:** `app/layout.tsx`.
- **Depends on:** nothing.
- **Acceptance:** "₹999" on Pricing and Billing renders in Geist (Playwright font check or
  DevTools "Rendered fonts"); no layout shift added.
- **Validation:** G (build lists the extra subset); a screenshot of a ₹ price.

### D.2 Wave 1: primitives

Each Wave-1 task owns its files in `components/ui/*`; they run in parallel. They keep existing call
sites working (overrides become harmless duplicates); the area sweeps delete the overrides later.

#### UI-011 · Button primitive
- **Priority · area · agent · branch:** P1 · Components · Component Engineer · `feature/ui-button`
  · after UI-001
- **Issues:** 010, 009, 002 (button), 011 (button), 025 (button hover), 026, 044, 046, 100, 032
  (button transition).
- **Problem / current:** `default` is the failing solid brand with an invisible hover;
  `destructive` fails AA; ghost and outline hover are invisible; a 2.1:1 focus halo; no touch size;
  12.8 px `sm` text; `min()` radii; no loading state; disabled hides its reason; `transition-all`.
- **Desired:** DESIGN_SYSTEM §8.2–§8.4: `default` = primary (gradient, `on-brand`,
  `hover:brightness-110`, `active:brightness-95`); `secondary` (hover `raised-hover`); `outline`
  (`border-line-strong`, hover `bg-hover`, open `bg-pressed`); `ghost` (hover `bg-hover`, open
  `bg-pressed`); `destructive` (`danger-fill`, `on-brand`); `destructive-ghost` (`danger-fg`, hover
  `danger-soft`); `link` (`brand-fg`); sizes `xs`–`xl` and icon sizes with `pointer-coarse:` 40 px
  minimums; `sm` and `xs` text `text-xs`; small sizes `rounded-md`; no `outline-none`, no ring halo;
  named, `motion-safe` transitions; a `loading` prop. New `ui/spinner.tsx` (motion-safe spin) and
  `ui/disabled-reason.tsx` (focusable wrapper, Tooltip, `sr-only` reason).
- **Files:** `components/ui/button.tsx`, new `ui/spinner.tsx`, new `ui/disabled-reason.tsx`, new
  tests.
- **Depends on:** UI-001.
- **Acceptance:** tests per variant and size; `loading` sets `aria-busy`, disables and keeps the
  width; DisabledReason exposes its reason on keyboard focus and through `aria-describedby`; a unit
  test proves `cn(buttonVariants(), "bg-danger-fill …")` drops the gradient, so today's 12 danger
  overrides stay red until migrated; a primary and a ghost button visibly change on hover; keyboard
  focus shows the 2 px outline at 3:1 or more; with a coarse pointer every size is at least 40 px;
  with a fine pointer heights are unchanged (24/28/32/36, `xl` 40).
- **Validation:** G; Vitest; Playwright with touch emulation and on desktop; VQA of the inbox,
  Settings and Schedule.

#### UI-012 · Modal overlay primitives (Dialog, AlertDialog, Sheet)
- **Priority · area · agent · branch:** P1 · Motion · Motion Engineer ·
  `feature/ui-modal-overlays` · after UI-001
- **Issues:** 012 (modal part), 031 (scrim, shadow), 032 (timing), 041, 011 (close buttons).
- **Problem / current:** a 10% scrim with a full-viewport blur; 100 ms; no reduced-motion handling;
  no shadow on dialogs; four title styles with `leading-none`; no height limit by default; 28 px
  close buttons.
- **Desired:** overlays `bg-scrim`, no blur, fading over the panel's duration; content enters at
  `duration-slow ease-enter`, exits at `duration-fast ease-exit`; `motion-reduce:animate-none`
  (and `transition-none` on the sheet); DialogContent `max-h-[calc(100dvh-2rem)] overflow-y-auto` by
  default and a `size` prop (`sm`, `md`, `lg`, `xl` = today's widths); titles
  `text-base font-semibold` with normal leading (`size="lg"` → `text-lg`); close buttons with the
  coarse-pointer size; the spec's `shadow-xl` on dialog and sheet content until D-12; SheetContent
  `size="panel"` (full screen below `md`, fixed width above) for UI-067.
- **Files:** `components/ui/dialog.tsx`, `alert-dialog.tsx`, `sheet.tsx`, new tests.
- **Depends on:** UI-001.
- **Acceptance:** under reduced motion no dialog, alert dialog, sheet or drawer animates (computed
  `animation-name: none`); otherwise dialogs enter in 200 ms and leave in 120 ms with the scrim in
  step; the page behind is visibly dimmed and `backdrop-filter` is `none`; a 30-line dialog scrolls
  at 375 × 500; a two-line title doesn't clip; close buttons are 40 px with a coarse pointer;
  existing call-site classes still render correctly.
- **Validation:** G; Playwright with both `reducedMotion` settings; VQA.

#### UI-013 · Floating overlay primitives (Popover, DropdownMenu, Select)
- **Priority · area · agent · branch:** P1 · Accessibility · Accessibility Engineer ·
  `feature/ui-floating-overlays` · after UI-001
- **Issues:** 001, 009 (menu item), 012 (floating part), 031 (shadow), 032, 103, 011 (items,
  trigger), 030 and 002 (select trigger).
- **Problem / current:** the item highlight is 1.15:1 with the outline hidden; the destructive item
  is 4.38:1; no reduced motion; per-site widths and shadows; 28 px items; the select trigger is the
  stock transparent field.
- **Desired:** items `focus:bg-hover` plus `focus-visible:outline-2 focus-visible:-outline-offset-2
  focus-visible:outline-ring` (no `outline-hidden`); destructive items `text-danger-fg
  focus:bg-danger-soft`; items `pointer-coarse:min-h-10`; content `min-w-48 w-auto` (select keeps
  its trigger width), labels `text-xs text-fg-secondary`; motion tokens and `motion-reduce`; the
  spec's shadow in the primitive; SelectTrigger on the Input recipe (`bg-field`, `border-input`,
  the size ladder, the focus outline with `border-ring`, no `dark:` classes).
- **Files:** `components/ui/popover.tsx`, `dropdown-menu.tsx`, `select.tsx`, new tests.
- **Depends on:** UI-001.
- **Acceptance:** opening a menu and a select by keyboard, the highlighted item shows an indicator of
  3:1 or more against the surface, in Chromium and Firefox (if a browser doesn't match
  `:focus-visible` for arrow-key focus, the inset outline keys off `data-highlighted` instead);
  pointer hover shows the fill; destructive text 4.5:1 at rest and highlighted; no animation under
  reduced motion; items 40 px with a coarse pointer; typeahead, Esc and focus return unchanged.
- **Validation:** G; Playwright keyboard checks in Chromium and Firefox; axe; VQA.

#### UI-014 · Field primitives and Field
- **Priority · area · agent · branch:** P1 · Components · Component Engineer · `feature/ui-fields`
  · after UI-001
- **Issues:** 017, 030, 039, 045, 002 (fields), 004 (edges through `--input`), 011 (fields).
- **Problem / current:** Input is stock shadcn and differs from Textarea; Textarea is 14 px (iOS
  zoom); a 2.1:1 halo; the indeterminate checkbox shows a tick; Label's `leading-none`; three private
  `Field` copies with unlinked errors.
- **Desired:** Input and Textarea `bg-field`, `border-input`, `text-base md:text-sm`, the focus
  outline plus `border-ring`, `aria-invalid:border-danger`, no `dark:` classes; Input `size` on the
  ladder with coarse-pointer minimums; placeholder classes unchanged until UI-018. Checkbox:
  `border-input` edge, checked and indeterminate filled (`--primary`), a minus icon for
  indeterminate, 40 px hit area on coarse pointers. Switch: checked `bg-brand`, unchecked
  `bg-pressed` with a `border-input` edge, no `transition-all`. Label: normal leading. New
  `ui/field.tsx` (shadcn Field) with `density` and generated `id`, `aria-describedby` and
  `aria-invalid`.
- **Files:** `components/ui/input.tsx`, `textarea.tsx`, `checkbox.tsx`, `switch.tsx`, `label.tsx`,
  new `field.tsx`, new tests.
- **Depends on:** UI-001.
- **Acceptance:** Field tests (the control's `aria-describedby` lists the hint and error ids;
  `aria-invalid` set); an indeterminate checkbox reads as "mixed"; below `md` Input and Textarea
  compute to 16 px; Input and Textarea on one card look identical; temporarily setting `--input` to a
  test colour changes only input, textarea, select-trigger and checkbox edges (the switch track
  doesn't follow `--input`).
- **Validation:** G; Vitest; VQA of SourceSheet and the workspace settings form.

#### UI-015 · Segmented controls (Tabs, ToggleGroup)
- **Priority · area · agent · branch:** P1 · Components · Component Engineer ·
  `feature/ui-segmented` · after UI-001
- **Issues:** 002 (tabs, toggle group), 011 (items), 033, 034, 026 (disabled items), 032.
- **Problem / current:** the halo is the only focus cue; 32 px items; labels wrap; no size or chips
  variant; disabled items swallow pointer events; the no-op `shadow-sm`.
- **Desired:** the inset focus outline; `pointer-coarse:min-h-10`; `whitespace-nowrap`; `size`
  (`sm` = `text-xs`, `default`); active `bg-raised text-brand-fg` without the shadow; ToggleGroup
  `variant="chips"` (pill, `text-xs`, `h-7`, selected `brand-soft`/`brand-fg`/`brand-line`) and
  `type="multiple"`; disabled items work inside DisabledReason.
- **Files:** `components/ui/tabs.tsx`, `toggle-group.tsx`, new tests.
- **Depends on:** UI-001.
- **Acceptance:** keyboard focus on a segment shows an inset indicator of 3:1 or more; "30 days" on
  Home and "Action needed" in Settings › Agent stay on one line at 375; chips work single and
  multiple with correct ARIA; items 40 px with a coarse pointer.
- **Validation:** G; Vitest; Playwright keyboard checks on Home, Knowledge, the automation editor and
  Settings › Agent; VQA.

#### UI-016 · Display primitives (Skeleton, Badge, Avatar) and one tone map
- **Priority · area · agent · branch:** P2 · Components · Component Engineer ·
  `feature/ui-display` · after UI-001
- **Issues:** 035, 027 (tone map), 096, 012 (skeleton), 101 (AvatarBadge), 032 (badge transition).
- **Problem / current:** Skeleton's default is invisible on panel and always pulses; Badge is unused
  (`rounded-4xl`, `transition-all`); eight tone maps; AvatarBadge unused.
- **Desired:** Skeleton `bg-raised motion-safe:animate-pulse`; Badge with `tone`, `size`, `shape`
  (DESIGN_SYSTEM §8.2); one tone source (`lib/ui/tone.ts`) that Badge reads; `TONE_CLASS` and
  `CHIP_CLASS` re-export it so no call site changes yet; AvatarBadge draws the platform cut-out with
  `ring-2 ring-panel`.
- **Files:** `components/ui/skeleton.tsx`, `badge.tsx`, `avatar.tsx`, new `lib/ui/tone.ts`,
  `lib/inbox/format.ts` and `lib/schedule/format.ts` (re-exports only), new tests.
- **Depends on:** UI-001.
- **Acceptance:** Badge tests per tone and size; the UsageCard skeletons are visible; the inbox list
  and schedule list are pixel-identical before and after; skeletons stop pulsing under reduced
  motion.
- **Validation:** G; Vitest; VQA of the inbox and schedule lists.

#### UI-017 · Tooltip
- **Priority · area · agent · branch:** P2 · Components · Component Engineer ·
  `feature/ui-tooltip` · **blocked: D-03** (surface follows D-12)
- **Issues:** 042.
- **Problem / current:** a white tooltip in a dark-only app.
- **Desired (D-03 option 2):** `bg-overlay` (or `bg-panel` if D-12 is declined), `text-fg`, the
  floating shadow (or `shadow-xl`), a matching arrow, motion tokens. Under option 1 only the motion
  tokens change.
- **Files:** `components/ui/tooltip.tsx`.
- **Depends on:** UI-001; D-03.
- **Acceptance:** the collapsed-sidebar and citation tooltips match the popover surface;
  `fg` on the surface 15:1 or more; instant under reduced motion.
- **Validation:** G; VQA of the collapsed sidebar at 768 and an Ask citation.

#### UI-018 · Apply the token decisions (control edge, placeholder, overlay elevation)
- **Priority · area · agent · branch:** P1 · Tokens · Design System Architect ·
  `feature/ui-token-decisions` · **blocked: D-01, D-06, D-12** (each part merges when its decision
  lands)
- **Issues:** 004, 008, 031.
- **Desired:** D-01: `line-control` and `--input` → `line-control` (option 2) or only the
  checkbox, radio and switch edges (option 1). D-06: `::placeholder` → `fg-secondary`. D-12:
  `overlay`, `shadow-floating`, `shadow-overlay`, `--popover` → `overlay`, and the overlay
  primitives' content classes use the two shadows instead of `shadow-xl` and `ring-foreground/10`
  (the phone drawer stays `panel`, like the sidebar). Each decision is recorded in CONFLICTS.md and
  AGENT_CONTEXT.md in the same PR.
- **Files:** `styles/globals.css`, `styles/tokens.ts`, `styles/tokens.test.ts`, `docs/CONFLICTS.md`,
  `docs/ui-audit/AGENT_CONTEXT.md`; for D-12 also `components/ui/popover.tsx`, `dropdown-menu.tsx`,
  `select.tsx`, `dialog.tsx`, `alert-dialog.tsx`, `sheet.tsx`, `shell/MobileNav.tsx`.
- **Depends on:** UI-001; for D-01 UI-014; for D-12 UI-012 and UI-013.
- **Acceptance:** D-01: every input, select, textarea and checkbox edge measures 3:1 or more on its
  surface (Settings, SourceSheet, ListView's bulk select); D-06: placeholders 4.5:1 or more on panel,
  field and raised; D-12: a menu over a card and a dialog over a card page read as raised without
  call-site shadows.
- **Validation:** G; the contrast script and axe; VQA.

#### UI-019 · Visual QA: baseline, then the Wave 0–1 checkpoint
- **Priority · area · agent · branch:** — · QA · Visual QA · `feature/ui-qa-wave1` (report only) ·
  **baseline ready now**; checkpoint after UI-001–UI-016
- **Desired:** before the first Wave-0 merge, capture a baseline on `develop`: the screen list in
  AGENT_CONTEXT §11 at 375, 768, 1280 and 1536, plus axe at 375 and 1280, a keyboard pass and a
  reduced-motion pass. After Wave 1, repeat and compare; file each regression against the task that
  caused it.
- **Files:** a report at `docs/ui-audit/qa/wave-1.md` (screenshots stay outside the repo; link or
  attach them to the PR).
- **Depends on:** nothing for the baseline; Wave 0–1 merged for the checkpoint.
- **Acceptance:** every intended change is visible, every unintended change is filed, axe shows no
  new violations and fewer `color-contrast` nodes.
- **Validation:** the report itself, reviewed by the Reviewer.

### D.3 Wave 2: shared components

New files; they run in parallel with Wave 1 where their dependencies allow. They don't migrate call
sites (the area sweeps do), except where noted to remove a duplicate atomically.

#### UI-020 · Card
- **Priority · area · agent · branch:** P2 · Components · Component Engineer · `feature/ui-card` ·
  after UI-001
- **Issues:** 036, 049 (CardHeader), 092 (bleeds).
- **Desired:** `ui/card.tsx`: `Card` (`rounded-xl`, `bg-panel`, `border-line`; `padding`
  `standard` = `p-4`, `roomy` = `p-5 md:p-6`; `tone` `default`, `danger` (`border-l-2` danger),
  `brand`), `CardHeader` (title `text-base font-semibold`; description `text-xs` for standard,
  `text-sm` for roomy; an actions slot), `CardInset` (`rounded-lg border-line`, `p-3` or `p-4`); a
  `--card-padding` variable so children can bleed without negative margins.
- **Files:** new `components/ui/card.tsx` and test.
- **Depends on:** UI-001.
- **Acceptance:** tests for each padding and tone; a full-bleed child aligns with the card edge.
- **Validation:** G; Vitest.

#### UI-021 · Alert
- **Priority · area · agent · branch:** P2 · Components · Component Engineer · `feature/ui-alert` ·
  after UI-001, UI-011
- **Issues:** 038.
- **Desired:** `ui/alert.tsx`: `tone` (neutral, brand, success, warning, danger), `variant` `soft`
  (the tone's soft fill, no border) or `outline` (`bg-panel`, a tone edge); `rounded-lg px-4 py-2.5
  text-sm`; icon, title, description; one action slot (`Button variant="secondary" size="sm"`);
  optional dismiss (never for critical states); `role` by urgency.
- **Files:** new `components/ui/alert.tsx` and test.
- **Depends on:** UI-001, UI-011.
- **Acceptance:** tests; text 4.5:1 or more on every soft fill.
- **Validation:** G; Vitest.

#### UI-022 · Meter and Progress
- **Priority · area · agent · branch:** P2 · Components · Component Engineer · `feature/ui-meter` ·
  after UI-001
- **Issues:** 037.
- **Desired:** `ui/meter.tsx` (`role="meter"` with value text; `kind` `consumable` (warning at 80%,
  danger at 100%) or `slot` (neutral "All used" at 100%); one `meterLevel`; track `bg-raised h-1.5`;
  fill `bg-brand-gradient-decor`; a compact ring that shows its percentage) and `ui/progress.tsx`
  (`role="progressbar"`).
- **Files:** new `components/ui/meter.tsx`, `progress.tsx` and tests.
- **Depends on:** UI-001.
- **Acceptance:** threshold and role tests; the ring shows the percentage.
- **Validation:** G; Vitest.

#### UI-023 · SearchInput and ChipInput
- **Priority · area · agent · branch:** P2 · Components · Component Engineer ·
  `feature/ui-search-chip` · after UI-014
- **Issues:** 040.
- **Desired:** `ui/search-input.tsx` (Input with a leading icon, `type="search"`, Escape clears,
  a label); `ui/chip-input.tsx` (add on Enter or comma, remove, validation, maximum and counter,
  `text-base md:text-sm`, the focus outline on the wrapper); ChipListInput, KeywordInput and
  PhraseChips become thin wrappers or are replaced at their import sites, in this PR.
- **Files:** new `ui/search-input.tsx`, `ui/chip-input.tsx`; `ai/ChipListInput.tsx`,
  `automations/KeywordInput.tsx`, `settings/PhraseChips.tsx` and their tests.
- **Depends on:** UI-014.
- **Acceptance:** the three components' existing tests pass unchanged (behaviour parity) or move to
  ChipInput's tests one for one.
- **Validation:** G; Vitest.

#### UI-024 · Toaster and toast rules
- **Priority · area · agent · branch:** P2 · Components · Component Engineer ·
  `feature/ui-toasts` · after UI-001, UI-010
- **Issues:** 043.
- **Desired:** `ui/sonner.tsx` (token class names: surface, `line-strong` edge, `fg` text,
  `danger-fg` for errors; top-centre below `md`, bottom-right above); action toasts last 10 s or
  more; the 37 direct `toast.error(errorMessage(e))` calls become `toastError(e)`; an ESLint rule
  forbids the direct form.
- **Files:** new `components/ui/sonner.tsx`, `app/layout.tsx`, `lib/toast-error.ts`,
  `apps/web/eslint.config.mjs`, and the call sites (AutomationsPage, TemplateGallery,
  AgentDraftDialog, PostComposer, SchedulePage, BillingPage, AutomationEditor, InboxShell, the
  connections page, SuggestionSlot and the rest found by the lint rule).
- **Depends on:** UI-001, UI-010 (`app/layout.tsx`). Must merge before the Wave-3 sweeps of the
  areas whose files it touches.
- **Acceptance:** lint fails on a direct call; a 402 from any of those mutations shows only the
  upgrade dialog; toasts are at the top at 375 and bottom-right at 1280; action toasts stay 10 s.
- **Validation:** G; E2E F-15 (the upgrade flow); VQA of a toast at 375 and 1280.

#### UI-025 · Compact states and the workspace error boundary
- **Priority · area · agent · branch:** P2 · Components · Component Engineer ·
  `feature/ui-states` · after UI-011, UI-006
- **Issues:** 068, 102, 011 (the retry button).
- **Desired:** EmptyState and ErrorState `size="compact"` (left-aligned, `text-sm`, a small Button
  with touch sizing); ErrorState's retry with the touch size and "Go to Home" beside it; a new
  `app/(app)/w/[slug]/error.tsx` so a page crash keeps the shell.
- **Files:** `states/EmptyState.tsx`, `states/ErrorState.tsx`, new
  `app/(app)/w/[slug]/error.tsx`, tests.
- **Depends on:** UI-011, UI-006.
- **Acceptance:** a thrown render error inside a page keeps the sidebar and banners; Go to Home
  works; both compact variants render.
- **Validation:** G; Vitest; a manual crash test on the stack.

#### UI-026 · Table
- **Priority · area · agent · branch:** P2 · Components · Component Engineer · `feature/ui-table` ·
  after UI-020
- **Issues:** 051.
- **Desired:** `ui/table.tsx` (header `text-xs font-medium text-fg-secondary`, sentence case,
  `scope`; body `text-sm`, `tabular-nums` for numbers; edge cells use `--card-padding`; caption);
  SourcesCard, PaymentHistory and Ask's Markdown tables use it, in this PR (three sites).
- **Files:** new `ui/table.tsx`; `knowledge/SourcesCard.tsx`, `billing/PaymentHistory.tsx`,
  `agent/AnswerText.tsx`; tests (`AskPanel.test.tsx:319, 647` if the structure changes).
- **Depends on:** UI-020.
- **Acceptance:** the three tables share one header and body style; PaymentHistory keeps its
  caption and `scope`; no overflow at 320.
- **Validation:** G; VQA of the three tables.

#### UI-027 · Identity palette
- **Priority · area · agent · branch:** P2 · Colour · Design System Architect ·
  `feature/ui-identity-palette` · **blocked: D-13**
- **Issues:** 054, 097 (categorical series).
- **Desired:** one identity palette module (pairs per D-13) used by `avatarGradient` and the
  schedule rings and dots; initials `aria-hidden`; rings 3:1 or more on panel; tokens only if D-13
  option 2.
- **Files:** new `lib/ui/identity.ts`, `lib/inbox/format.ts`, `lib/schedule/format.ts`,
  `inbox/ContactAvatar.tsx`, `schedule/post-parts.tsx`; `styles/*` only under option 2.
- **Depends on:** UI-016; D-13.
- **Acceptance:** every stop 4.5:1 or more with white; no status colour used; ring contrast 3:1 or
  more.
- **Validation:** G; the contrast script; VQA of the inbox list and the schedule filter.

#### UI-028 · Breakpoints module
- **Priority · area · agent · branch:** P2 · Layout · Layout Engineer · `feature/ui-breakpoints` ·
  after UI-001, UI-006
- **Issues:** 059.
- **Desired:** `lib/breakpoints.ts` (`md`, `lg`, `xl`, `wide`); the literals in `inbox-context.tsx`,
  AppShell, InboxShell and SchedulePage read it; `wide:` replaces `min-[1440px]:`; each JS hook passes
  a deliberate server value, documented at the call; CSS for visibility-only switches.
- **Files:** new `lib/breakpoints.ts`, `inbox/inbox-context.tsx`, `shell/AppShell.tsx`,
  `inbox/InboxShell.tsx`, `schedule/SchedulePage.tsx`, the browser-state hook.
- **Depends on:** UI-001, UI-006.
- **Acceptance:** no width literals in media queries outside `lib/breakpoints.ts` and `globals.css`;
  `InboxShell.test.tsx` pane widths pass unchanged; no desktop flash of the schedule agenda at 375.
- **Validation:** G; a first-paint screenshot of Schedule at 375.

### D.4 Wave 3: area adoption

Each area gets two tasks, **A** (primitives and tokens; mechanical) then **B** (shared components).
Areas run in parallel; within an area A, then B, then that area's Wave-4 tasks.

**Issues the sweeps close or finish** (with the Wave 1–2 tasks that built the parts): UI-ISS-002,
004 (inset panels), 009, 010, 011, 017, 025–029, 031, 032, 034–040, 042, 047, 049, 050, 053
(selection bar), 055 (gradient roles), 092, 093, 094, 097, 100, 101, 104 (native fields through
Input and Select).

**What every A task does in its directories** (DESIGN_SYSTEM is the rule; AGENT_CONTEXT §6 the
checklist):
- delete `bg-brand-gradient text-white` from Buttons and AlertDialogActions (the `default` variant
  is the primary); move danger looks to `destructive` or `destructive-ghost`;
- delete the touch patches (`min-h-10 md:min-h-*`, `size-10 md:size-*`, `h-10 md:h-*`), choosing the
  size whose desktop height matches today's;
- delete the overlay patches (`border-line bg-panel`, `shadow-*`, per-dialog `max-h`), Skeleton
  overrides, `ring-ring/50` and bare `outline-none`;
- route raw `<input>`, `<textarea>` and `<select>` through Input, Textarea and Select (native date
  and time stay native through Input under D-04);
- replace `text-white` → `text-on-brand`, `bg-white/5` → `bg-hover`, `bg-white/10` → `bg-pressed`,
  `bg-black/N` on media → `bg-media-scrim/N`, `bg-*/10|15` → `bg-*-soft`, `text-[11px]` and smaller →
  `text-2xs`, `text-[15px]` → `text-md`, local eyebrow strings → `EYEBROW`, alias names → token
  names;
- transitions named and `motion-safe:`; hover reveals only for fine pointers; the selection-bar,
  spacing, radius and border rules where the files are touched (D-02 and D-16 parts wait).

**What every B task does:** Badge for every badge and chip, Card / CardHeader / CardInset for card
surfaces, Alert for callouts and banners, Meter and Progress for bars, Field for every label-control
pair, SearchInput, Table (if any), compact Empty and Error states, DisabledReason where a disabled
control has a reason, Tooltip for meaningful `title`s, Button `loading` for pending buttons.

**Acceptance for every area task** (besides §H): in the area's directories, `rg` finds none of:
`bg-brand-gradient` on a Button, `md:min-h-`, `border-line bg-panel` on overlay content,
`text-[`, `text-white`, `bg-white/`, `bg-black/`, `ring-ring/50`, `outline-none` without a
`focus-visible` replacement (B tasks: no hand-rolled badge, card, meter or field patterns remain);
screenshots differ from the baseline only where intended; the listed class-assertion tests are
updated deliberately. **Validation:** G; E2E; VQA of the area's screens; axe at 375 and 1280.

| Task | Area and directories | Branch | Agent | Depends on | Area specifics | Tests that change |
|---|---|---|---|---|---|---|
| UI-030 | Inbox and AI, A: `components/inbox`, `components/ai`, `lib/inbox` | `feature/ui-inbox-a` | Component | UI-002, UI-004, UI-007, UI-011–UI-016, UI-024 | Chats \| Scheduled → Tabs; PlatformStrip → ToggleGroup (active look per D-15 item 1; until then `brand-strong` filled); view chips → `variant="chips"`; the Scheduled count badge per UX-SH-01; Send as a Button (secondary while empty, primary with text; 40 px on touch) | `PlatformStrip.test.tsx:11, 18`; `ConversationRow.test.tsx:44` (keep the `row-accent` test id) |
| UI-031 | Inbox and AI, B | `feature/ui-inbox-b` | Component | UI-030, UI-020–UI-023, UI-025 | row badges and ReplyWindowChip → Badge; DetailsPanel → Card/CardInset; LeadScore → Meter; attachment progress → Progress; SuggestionCard notices → Alert; ScheduleFields, TemplatePicker → Field; EmojiPicker search → SearchInput; ScheduledList's cancel → AlertDialog (UI-ISS-105); ContactAvatar → AvatarBadge | `ThreadHeader.test.tsx:52, 54` (soft tokens) |
| UI-032 | Composer and Schedule, A: `components/composer`, `components/schedule`, `lib/schedule`, `lib/publishing` | `feature/ui-schedule-a` | Component | UI-007, UI-008, UI-009, UI-011–UI-016, UI-024 | the composer's More stays on the title row (UI-ISS-115); the calendar status edge `border-l-2`; dashed placeholders (no dotted) | `SchedulePage.test.tsx:659` |
| UI-033 | Composer and Schedule, B | `feature/ui-schedule-b` | Component | UI-032, UI-020–UI-023, UI-025, UI-026 | composer Section and PostChecklist → Card; StatusBanner → Alert; MediaTray and upload progress → Progress; ScheduleRail's publish meter → Meter; HashtagGroupsDialog, ListView, PostingTimesDrawer, MediaLibraryDialog → Field/SearchInput; ListView's select-all uses the indeterminate state | — |
| UI-034 | Automations, A: `components/automations`, `lib/automations` | `feature/ui-automations-a` | Component | UI-005, UI-007, UI-011–UI-016, UI-024 | hover-revealed row controls only for fine pointers (UI-ISS-057) | — |
| UI-035 | Automations, B | `feature/ui-automations-b` | Component | UI-034, UI-020–UI-023, UI-025 | STATUS_TONE and RESULT_TONE → Badge; editor callouts → Alert; AutomationsPage and PostsStep search → SearchInput; StatsPane keeps its chart pattern on tokens | `StepCard.test.tsx` only if StepCard moves onto Card (keep its status classes) |
| UI-036 | Settings group, A: `components/settings`, `components/billing`, `components/connections`, `components/push`, `app/(app)/w/[slug]/settings/**` | `feature/ui-settings-a` | Component | UI-002, UI-009, UI-011–UI-016, UI-024 | inset panels `border-line`; the settings tab row gets the edge fade (UI-ISS-058); the plan hero's glow → `bg-glow-brand`; the shell gradient off the plan icon; the current plan card loses its glow (UI-ISS-094) | — |
| UI-037 | Settings group, B | `feature/ui-settings-b` | Component | UI-036, UI-020–UI-023, UI-025, UI-026; **radius part: D-02** | SettingsCard → a thin wrapper over Card (keep `rounded-2xl` with a `D-02` TODO until decided); AccountCard → Card, CardInset, Badge, AvatarBadge; QuotaTile → Meter (`slot` for accounts and automations, VH-007); workspace form → Field; connections search → SearchInput; CheckoutReturn and InstallPrompt → Alert; the Agent run filters → ToggleGroup | — |
| UI-038 | Home, Comments, Knowledge, A: `components/home`, `components/comments`, `components/knowledge` | `feature/ui-dash-a` | Component | UI-003, UI-008, UI-011–UI-016, UI-024 | the tiles' and cards' focus rings; `text-[11px]` eyebrows → EYEBROW | `PostDetailPage.test.tsx:546, 549` |
| UI-039 | Home, Comments, Knowledge, B | `feature/ui-dash-b` | Component | UI-038, UI-020–UI-023, UI-025, UI-026 | MetricTile, Checklist, AccountHealth, KnowledgeGapBanner → Card or Alert; the knowledge usage meter → Meter; BrandVoiceCard and SourceSheet → Field (removes two private `Field`s); CommentsColumn filters → chips; the sentiment and intent bars stay charts on tokens | `PostDetailPage.test.tsx:137` and `CommentsPage.test.tsx:77` only if those bars become Progress |
| UI-040 | Ask, Shell, States, A: `components/agent`, `components/shell`, `components/states`, `components/workspace` | `feature/ui-ask-shell-a` | Component | UI-002, UI-006, UI-011–UI-016, UI-024, UI-025, UI-028 | Ask text → `text-md`; the Ask composer's focus recipe (radius waits for D-16); one selection bar (sidebar, Threads); UsageCard tokens; notification dots solid; the phone drawer `bg-panel`; PageFrame's header row wraps (UI-ISS-056) | `AskPanel.test.tsx:212, 642, 644, 649, 651, 653, 667`; `ActionCardView.test.tsx:89`; `AskPage.test.tsx:143` |
| UI-041 | Ask, Shell, States, B | `feature/ui-ask-shell-b` | Component | UI-040, UI-020–UI-022, UI-025 | BannerSlot → Alert; UsageCard → Meter (`role="meter"`); the Ask notices → Alert; inline empties → compact EmptyState | `AskPanel.test.tsx:575` |
| UI-042 | Public site and auth: `components/marketing`, `app/(marketing)`, `app/(auth)` | `feature/ui-public` | Component | UI-001, UI-002, UI-011 | marketing `white/N` → tokens; the CTA class on `buttonVariants`; the logo SVG in `currentColor`; `rounded-3xl` and `rounded-[10px]` retired; legal prose → `text-md`; unsubscribe success links back or resubscribes (UI-ISS-110) | — |

#### UI-043 · Visual QA: area adoption checkpoint
- **Agent · branch:** Visual QA · `feature/ui-qa-wave3` · after UI-030–UI-042.
- **Desired:** the full screen list at 375, 768, 1280 and 1536 against the baseline; axe at 375 and
  1280; keyboard and reduced-motion passes; a report at `docs/ui-audit/qa/wave-3.md` with every
  regression filed against its task.
- **Acceptance:** zero unexplained visual differences; axe violation count at or below the
  baseline with every targeted rule gone.

#### UI-044 · Design-system review gate
- **Agent · branch:** Final Design-System Reviewer · `feature/ui-review-gate` (report only) · after
  UI-043.
- **Desired:** check `develop` against DESIGN_SYSTEM.md (the `rg` checks above across the whole app,
  the primitive APIs, the decision log); list deviations as follow-up tasks; approve the start of
  Wave 4. Report at `docs/ui-audit/qa/review-gate.md`.

### D.5 Wave 4: screen-level UX and accessibility

Each task starts after its area's B task. Tasks marked **blocked** wait for their decision.

| Task | Title | P | Agent | Branch | Issues | Depends on | Problem → desired (summary) | Files | Acceptance and validation |
|---|---|---|---|---|---|---|---|---|---|
| UI-050 | AI and automation attribution | P2 | UX | `feature/ui-ai-labels` | 085 | UI-031; **blocked: D-07** | "AI Assisted" on every automated message → "Sent by AI" / "Automation · {name}"; "Auto:" → "Automation:"; neutral "Auto replies" badge; at most two badges per row | `MessageBubble.tsx`, `lib/inbox/format.ts`, `ConversationRow.tsx`, `AiModeControl.tsx` (+ tests) | Each message type shows its label; MessageBubble and ConversationRow tests updated; G, VQA |
| UI-051 | Draft bar and composer refinements | P2 | UX | `feature/ui-composer-ux` | 088, 066, 056 (composer), 067 and 107 (**D-15** items 2–3) | UI-031 | Draft Send becomes secondary while the composer has text, the bar clamps to one line on phones; Ask's Open keeps an existing draft (or asks); the toolbar wraps below 360 px; heart and header-schedule changes when D-15 lands | `SuggestionCard.tsx`, `Composer.tsx`, `EmojiPicker.tsx`, `ThreadHeader.tsx`, `lib/agent/handoff.ts`, `ThreadView.tsx` | One primary Send at a time; a typed draft survives Open; no clipping at 320; G, E2E F-07/F-08, VQA |
| UI-052 | Inbox views and filters | P2 | UX | `feature/ui-inbox-views` | 078, 079, 058 (inbox), Archived chip (**D-15** item 4) | UI-031 | Scheduled tab honours the platform filter (or hides it); counts on Needs reply and Needs you; `view` and `platform` in the URL; chips wrap from `md` with an edge fade below | `ListHeader.tsx`, `InboxShell.tsx`, `ScheduledList.tsx` | Back and refresh keep the view; Home's link applies when the inbox is mounted; G, VQA |
| UI-053 | Single-key shortcuts | P1 | A11y | `feature/ui-shortcuts` | 015 | UI-031; **blocked: D-14** | Shortcuts can be turned off (option 1: a per-device switch in a Keyboard shortcuts dialog opened from the list header and with "?") | `use-inbox-shortcuts.ts`, `InboxShell.tsx`, a new dialog (+ tests) | Off → j/k/e/u do nothing; the setting persists per device; InboxShell shortcut tests extended; G |
| UI-054 | Scheduling flows | P2 | UX | `feature/ui-schedule-flows` | 070, 083, 091 | UI-033 | Posting times and hashtag groups open in place from the composer (or via `?panel=`); the header's "Add to queue" removed or renamed; one empty state per view | `WhenSection.tsx`, `CaptionEditor.tsx`, `ScheduleRail.tsx`, `SchedulePage.tsx`, `AgendaView.tsx` | One click to each tool; one New post per screen on phones; G, E2E F-13, VQA |
| UI-055 | Comments needs-reply view | P1 | UX (with a backend change) | `feature/ui-comments-needs-reply` | 024 | UI-039; **blocked: D-11** | Option 1: API `needs_reply_count` on PostSummary and a `needs_reply` comment filter (schema, route, generated client); post cards show "n need a reply", the grid sorts by it; a Needs reply chip on post detail | API service and schema, `packages/api-client`, `CommentsPage.tsx`, `PostCard.tsx`, `CommentsColumn.tsx`, `lib/comments/format.ts` | The badge's number is findable in two clicks; API tests; G, E2E |
| UI-056 | Post detail and comment cards | P2 | Layout | `feature/ui-post-detail` | 090, 112 | UI-039 | Below 1024 px: post (compact), comments, then insights; cards show the caption's first line, spam only above 0 | `PostDetailPage.tsx`, `PostCard.tsx` | Comments above the fold on a 375 × 667 phone; `PostDetailPage.test.tsx:534`; G, VQA |
| UI-057 | Knowledge page order and test box | P2 | Layout | `feature/ui-knowledge-layout` | 089, 069 | UI-039 | Gaps, Sources, then Brand voice collapsed to a summary; a wider Source column; Test box "Add answer" opens the FAQ sheet prefilled | `KnowledgePage.tsx`, `SourcesCard.tsx`, `BrandVoiceCard.tsx`, `TestBox.tsx` | Sources visible without scrolling at 1280 × 800 on a first visit; G, VQA |
| UI-058 | Home checklist | P2 | UX | `feature/ui-home-checklist` | 084 | UI-039 | A completed checklist shows "You're all set" for one session, then hides; done rows collapse; "Show setup checklist" in the workspace menu | `Checklist.tsx`, `HomeScreen.tsx`, `shell/WorkspaceMenu.tsx` | Metrics visible at 1280 × 800 once set up; G, E2E (Home checklist), VQA |
| UI-059 | One primary per view | P2 | UX | `feature/ui-primary-hierarchy` | 087 | UI-031, UI-033, UI-035, UI-037, UI-039; **blocked: D-10** | Row and card actions secondary; one gradient primary per view region | `PriorityQueue.tsx`, `TemplateGallery.tsx`, `KnowledgeGapsCard.tsx`, `SourcesCard.tsx`, `BillingPage.tsx`, `PlanCards.tsx`, `AgendaView.tsx`, the automations empty state | A screen count of gradient buttons per view region is at most one; G, E2E F-11/F-15 (`Use template`, `Start 7-day trial` names unchanged), VQA |
| UI-060 | Settings frame | P2 | UX | `feature/ui-settings-frame` | 076, 077, 014 (clean save bar) | UI-037; **blocked: D-08** | Per D-08: drop breadcrumb and eyebrow, tab labels match titles, the save bar only when dirty, saving or failed (an inline "Saved" on autosave pages), the Agent tiles become one sentence | `SettingsPageHeader.tsx`, `settings/sections.ts`, `SaveBar.tsx`, `AiSettingsPage.tsx`, `NotificationSettingsPage.tsx`, `AgentSettingsPage.tsx`, `BillingPage.tsx` | About 100 px returned per tab; no bar on a clean page; G, VQA |
| UI-061 | Connections: errors, empty state, Auto | P2 | UX | `feature/ui-connections-ux` | 074, 108, 071 (Connections) | UI-037 | The last connect error as an inline Alert with Try again; both Connect buttons in the empty state; choosing Auto on Free opens the upgrade dialog | the connections page, `ConnectWhatsAppButton.tsx`, `AccountCard.tsx`, `lib/copy.ts` | Errors stay until dismissed; G, VQA |
| UI-062 | Connections: destructive placement and labels | P2 | UX | `feature/ui-account-actions` | 080 | UI-061; **blocked: D-09** | Disconnect visible (neutral); "Delete account and data" in a ⋯ menu for both modes; the typed-confirm dialog unchanged | `AccountCard.tsx`, `DeleteAccountDialog.tsx` (+ tests) | No red text on a healthy card; G, VQA |
| UI-063 | Upgrade and plan flows | P2 | UX | `feature/ui-upgrade-flows` | 071, 072, 073, 106 (agent "Not now") | UI-035, UI-037, UI-041, UI-042 | Every "Upgrade" opens the upgrade dialog; Pro templates say so on Free; `?plan=pro` survives sign-up and offers the trial; agents see "OK" | `UsageCard.tsx`, `AppShell.tsx`, `SourcesCard.tsx`, `TemplateGallery.tsx`, `Pricing.tsx`, `lib/resolve.ts`, `HomeScreen.tsx`, `UpgradeDialog.tsx` | One behaviour per word; G, E2E F-01/F-15, VQA |
| UI-064 | Automations: Instagram-only up front | P2 | UX | `feature/ui-automations-ig` | 081 | UI-035 | With no Instagram account, the list and gallery say "Automations work on Instagram" with Connect Instagram; trigger labels name Instagram | `AutomationsPage.tsx`, `TemplateGallery.tsx`, `WhenStep.tsx` | WhatsApp-only workspace sees the notice first; G |
| UI-065 | Child-page navigation and editor layout | P3 | Layout | `feature/ui-child-pages` | 075, 113 | UI-033, UI-035, UI-039; **blocked: D-16** items 1–2 | PageFrame's "‹ Parent" back link on the automation editor, post composer and post detail; the editor's panel after the steps below 1280 px; spec UX-SCR-03 updated by UI-071 | `PageFrame.tsx`, `AutomationEditor.tsx`, `PostComposer.tsx`, `PostDetailPage.tsx`, `apps/web/e2e/f11-keyword-automation.spec.ts`, `f13-schedule-post.spec.ts` | E2E F-11 and F-13 updated from the "Breadcrumb" landmark to the back link and green; G, VQA |
| UI-066 | Screen-reader semantics and document structure | P2 | A11y | `feature/ui-sr-semantics` | 060, 061, 062, 063, 064, 065, 116 | UI-031, UI-033, UI-035, UI-039, UI-041 | Roles for unread dots, reactions and loaders; route metadata and dynamic titles; `sr-only` h1s; Knowledge's aside labelled; FAQ headings outside `<summary>`; the message log announces new inbound only; the empty week grid focusable; `lang` on bubbles; descriptive photo alt text | `NotificationsButton.tsx`, `MessageBubble.tsx`, `MessageLog.tsx`, `PageSkeleton.tsx`, `ConversationList.tsx`, `KnowledgePage.tsx`, `PlatformStrip.tsx`, `Composer.tsx`, the six `page.tsx` files, `AutomationEditor.tsx`, `InboxShell.tsx`, `marketing/Faq.tsx`, `WeekView.tsx`, `AttachmentView.tsx` | axe clean of `aria-prohibited-attr`, `page-has-heading-one`, `landmark-unique`, `scrollable-region-focusable`; NVDA or VoiceOver check of the message log; G |
| UI-067 | Right-hand panels on Sheet | P3 | Motion | `feature/ui-panels-sheet` | 032 (panel families) | UI-012, UI-041 | AskPanel and the run detail move onto `SheetContent size="panel"`, with the standard sheet motion (fade and slide) | `AskPanel.tsx`, `AgentSettingsPage.tsx` (+ tests) | Ask panel and inbox details sheet move identically; focus return kept; `AskPanel.test.tsx:640` updated; G, VQA |
| UI-068 | Copy and terminology pass | P2 | UX | `feature/ui-copy` | 086, 105 (labels), 106, 109, 111 | every other unblocked Wave-4 task (runs last) | UX_AUDIT §5's recommended names ("Add answer", "AI draft", "Needs you", "Cancelled" …), §6 casing, spelling and punctuation, cancel labels, Ask's credit hint, object titles; a copy lint test beside `lib/copy.test.ts` | `lib/copy.ts`, `lib/*/format.ts`, the components named in UX_AUDIT §5–§6, `apps/web/e2e/*` where names change | E2E updated where accessible names change (F-06 and F-08 use the "Suggested reply" region; F-13 the "Post" heading); G, E2E |
| UI-069 | Page and pane title scale | P2 | Layout | `feature/ui-title-scale` | 048, 115 ("Inbox" twice) | UI-031, UI-041 (and UI-060 if D-08 lands first); **blocked: D-05** | Page H1 24 px everywhere, pane H1 18 px (Inbox, Ask, phone top bar); the list's h1 `sr-only` on phones | `SettingsPageHeader.tsx`, `ListHeader.tsx`, `AskPage.tsx`, `MobileNav.tsx` | One title size per role; G, VQA |

### D.6 Wave 5: lock and review

#### UI-070 · Palette lock and design lint
- **Priority · area · agent · branch:** P2 · Tokens · Design System Architect ·
  `feature/ui-palette-lock` · after UI-030–UI-042
- **Issues:** 028, 095, 097.
- **Desired:** `--color-*: initial` before our tokens (only our palette compiles); a source lint (an
  ESLint rule or a Vitest scan of class strings) that rejects `text-white`, `bg-black/`, `text-[`,
  `rounded-[`, `bg-brand-gradient` on Button, `ring-ring/50` and `outline-none` without a
  `focus-visible` replacement; `tokens.test.ts` compares the Clerk, OG-image and manifest mirrors with
  `tokens.ts`; chart colours read from one constant.
- **Files:** `styles/globals.css`, `styles/tokens.ts`, `styles/tokens.test.ts`,
  `apps/web/eslint.config.mjs` (or a new test), `lib/clerk-appearance.ts`, `marketing/og.tsx`,
  `app/manifest.ts`.
- **Acceptance:** a stray `bg-red-500` or `text-white` fails the build or the lint; mirrors drift →
  test fails.
- **Validation:** G.

#### UI-071 · Spec and decision records
- **Priority · area · agent · branch:** P2 · Docs · Design System Architect · `feature/ui-spec-sync`
  (one per decision batch) · rolling; final pass after UI-069
- **Desired:** BUILD_SPEC §4.2 (type-role table with 11 px and 15 px rows and the pane title,
  radius, elevation, motion, placeholders), UX-A11Y-01 (D-01), UX-INB-03 (focus wording), UX-SH-01
  (nav 14 px, C-048), UX-INB-07 and UX-SCR-03 (D-16); a CONFLICTS entry for each owner decision and
  for the confirmed additions; AGENT_CONTEXT and DESIGN_SYSTEM kept in step.
- **Files:** `docs/BUILD_SPEC.html`, `docs/CONFLICTS.md`, `docs/ui-audit/*.md`.
- **Acceptance:** the spec, CONFLICTS and DESIGN_SYSTEM agree on every token and rule.

#### UI-072 · Visual QA: final
- **Agent · branch:** Visual QA · `feature/ui-qa-final` · after every merged task.
- **Desired:** the full pass of UI-043 plus 320 px reflow and 640 × 450 (200% zoom) on the main
  screens; report at `docs/ui-audit/qa/final.md`.

#### UI-073 · Final design-system review
- **Agent · branch:** Final Design-System Reviewer · `feature/ui-review-final` · after UI-072.
- **Desired:** confirm §H for the programme: every UI-ISS closed or explicitly deferred with a
  reason, every decision recorded, the lint guards on, AGENT_CONTEXT current. Report at
  `docs/ui-audit/qa/final-review.md`.

### D.7 Conditional task

- **UI-029 · Calendar and time picker** (Component Engineer, `feature/ui-calendar`) exists only if the
  owner picks D-04 option 2: add shadcn Calendar and a time field, replace the 9 native date and time
  fields, update E2E F-13 (it fills "Date" and "Time" as text boxes). Not counted above.

---

## Ready now, and blocked

**Ready now (no dependencies):** UI-001, UI-003, UI-004, UI-005, UI-006, UI-007, UI-008, UI-010,
and UI-019's baseline capture.

**Ready as soon as UI-001 merges:** UI-002, UI-011, UI-012, UI-013, UI-014, UI-015, UI-016,
UI-020, UI-022; then UI-009 (with UI-008), UI-021 (with UI-011), UI-023 (with UI-014), UI-024
(with UI-010), UI-025 (with UI-011 and UI-006), UI-026 (with UI-020), UI-028 (with UI-006).

**Blocked on an owner decision:**

| Decision | Blocks | Partly blocks |
|---|---|---|
| D-01 control edge | UI-018 (part) | — |
| D-02 card radius | — | UI-037 (radius) |
| D-03 tooltip | UI-017 | — |
| D-04 date pickers | — (option 2 adds UI-029) | — |
| D-05 title size | UI-069 | — |
| D-06 placeholder | UI-018 (part) | — |
| D-07 AI labels | UI-050 | — |
| D-08 settings frame | UI-060 | — |
| D-09 Remove | UI-062 | — |
| D-10 one primary | UI-059 | — |
| D-11 comments API | UI-055 | — |
| D-12 overlay elevation | UI-018 (part) | UI-017 (surface) |
| D-13 identity palette | UI-027 | — |
| D-14 shortcuts | UI-053 | — |
| D-15 inbox refinements | — | UI-030 (item 1), UI-051 (items 2–3), UI-052 (item 4) |
| D-16 spec layouts | UI-065 | UI-040 (composer radius), sweeps (icon-button radius) |
| D-17 Devanagari | — | UI-010 (only under option 2) |

Fully blocked tasks: UI-017, UI-018, UI-027, UI-050, UI-053, UI-055, UI-059, UI-060, UI-062,
UI-065, UI-069 (11).

---

## E. Parallel execution plan

### E.1 Lanes

| Lane | Order | Notes |
|---|---|---|
| DSA | UI-001 → UI-010 → UI-018 (as D-01, D-06, D-12 land) → UI-027 (D-13) → UI-071 (each decision batch) → UI-070 | The only lane that edits `styles/*`, `/dev/tokens`, `CONFLICTS.md`, `BUILD_SPEC.html` and the synthesis docs |
| Component ×3 (Wave 1–2) | C1: UI-011 → UI-021 → UI-025 → UI-024 · C2: UI-014 → UI-023 → UI-020 → UI-026 · C3: UI-015 → UI-016 → UI-022 → UI-017 (D-03) | Each instance owns different `components/ui/*` files |
| Component ×up to 7 (Wave 3) | one instance per area: UI-030→031 · UI-032→033 · UI-034→035 · UI-036→037 · UI-038→039 · UI-040→041 · UI-042 | Directories are disjoint |
| Layout | UI-003 → UI-004 → UI-006 → UI-009 → UI-028 → (Wave 4) UI-056, UI-057, UI-069 (D-05), UI-065 (D-16) | |
| UX | UI-005 → UI-008 → (Wave 4) UI-051, UI-052, UI-054, UI-058, UI-061, UI-063, UI-064, then UI-050/059/060/062/055 as decided → UI-068 last | |
| Accessibility | UI-007 → UI-002 → UI-013 → (Wave 4) UI-066, UI-053 (D-14) | UI-007 runs while UI-001 is in review |
| Motion | UI-012 → UI-067 | Reviews motion in every Wave-1 PR |
| Visual QA | UI-019 baseline now → UI-019 checkpoint → UI-043 → UI-072 | |
| Reviewer | reviews each PR against AGENT_CONTEXT → UI-044 → UI-073 | |

### E.2 File ownership and coordination rules

1. **Shared token and spec files are serial.** `styles/globals.css`, `styles/tokens.ts`,
   `tokens.test.ts`, `/dev/tokens`, `docs/CONFLICTS.md`, `docs/BUILD_SPEC.html` and the four
   synthesis docs are edited only by DSA tasks, one at a time: UI-001 → UI-018 parts → UI-027 →
   UI-070, with UI-071 in between. (UI-009 needs no `globals.css` change: UI-001 adds the top
   padding rule.)
2. **One owner per primitive file.** Wave 1–2 owners: `button`, `spinner`, `disabled-reason` UI-011;
   `dialog`, `alert-dialog`, `sheet` UI-012; `popover`, `dropdown-menu`, `select` UI-013; `input`,
   `textarea`, `checkbox`, `switch`, `label`, `field` UI-014; `tabs`, `toggle-group` UI-015;
   `skeleton`, `badge`, `avatar` UI-016; `tooltip` UI-017; `card` UI-020; `alert` UI-021; `meter`,
   `progress` UI-022; `search-input`, `chip-input` UI-023; `sonner` UI-024; `table` UI-026. UI-018's
   D-12 part edits the overlay files only after UI-012 and UI-013 merged. From Wave 3 on, nobody edits
   `components/ui/*`; a needed change becomes a small new task for the owning role.
3. **Feature directories by wave.** Wave-0 tasks own the files they list. An area's Wave-3 task
   starts only after every earlier task touching its directories has merged (its "Depends on"
   column). Within an area: A, then B, then its Wave-4 tasks.
4. **Cross-area tasks** (UI-007, UI-024, UI-059, UI-063, UI-065, UI-066, UI-068) list their files
   and start only when no open task owns any of them; the plan places them before (UI-007, UI-024)
   or after (the rest) the area sweeps.
5. **Shared `lib` files:** `lib/inbox/format.ts`: UI-016 → UI-027 → UI-030/031 → UI-050 → UI-068.
   `lib/schedule/format.ts`: UI-016 → UI-027 → UI-032/033. `lib/copy.ts`: UI-061 → UI-068.
6. **Tests travel with their component**; e2e specs change only in UI-065, UI-068 (and UI-029).
7. **Every branch starts from the current `develop`** and rebases before merge; squash merge.

### E.3 Dependency graph

```text
WAVE 0  (start now)                                    QA: UI-019 baseline (now)
 UI-001 Tokens ──────────────┬─────────────────────────────────────────────────────────┐
 UI-003 Home overflow        │                                                         │
 UI-004 Thread header        ├──► UI-002 Contrast                                      │
 UI-005 Automation copy      ├──► UI-009 Sticky bars ◄── UI-008 Post safety            │
 UI-006 Shell frame ─────────┼──► UI-028 Breakpoints                                   │
 UI-007 Focus fixes          │                                                         │
 UI-010 Fonts ───────────────┼──► UI-024 Toasts                                        │
                             │                                                         │
WAVE 1  (each ◄── UI-001; parallel, disjoint files)                                    │
 UI-011 Button ──────┬──► UI-021 Alert     UI-025 States ◄── UI-006                    │
 UI-012 Modal ovl ───┤                                                                 │
 UI-013 Float ovl ───┼──► UI-018 Token decisions ◄── D-01, D-06, D-12 ◄────────────────┘
 UI-014 Fields ──────┼──► UI-023 Search/ChipInput
 UI-015 Segmented    │
 UI-016 Display ─────┴──► UI-027 Identity palette ◄── D-13
 UI-017 Tooltip ◄── D-03 (+D-12)
                                                       QA: UI-019 checkpoint
WAVE 2  (new files; alongside Wave 1)
 UI-020 Card ──► UI-026 Table      UI-022 Meter/Progress
                 │
WAVE 3  (areas in parallel; A ──► B; each A needs Wave 1 + UI-024 + its Wave-0 tasks;
         each B needs Wave 2)
 Inbox+AI          UI-030 ──► UI-031        (A also ◄ UI-002, UI-004, UI-007)
 Composer+Schedule UI-032 ──► UI-033        (A also ◄ UI-007, UI-008, UI-009)
 Automations       UI-034 ──► UI-035        (A also ◄ UI-005, UI-007)
 Settings group    UI-036 ──► UI-037 ◄ D-02 (radius only)
 Home+Comments+Kn  UI-038 ──► UI-039        (A also ◄ UI-003, UI-008)
 Ask+Shell+States  UI-040 ──► UI-041        (A also ◄ UI-002, UI-006, UI-025, UI-028)
 Public+auth       UI-042
                             │
                             ▼
                 UI-043 QA checkpoint ──► UI-044 Review gate
                             │
WAVE 4  (after the area's B task)
 ◄UI-031: UI-050 ◄D-07 · UI-051 (◄D-15) · UI-052 (◄D-15) · UI-053 ◄D-14
 ◄UI-033: UI-054
 ◄UI-035: UI-064
 ◄UI-037: UI-060 ◄D-08 · UI-061 ──► UI-062 ◄D-09
 ◄UI-039: UI-055 ◄D-11 · UI-056 · UI-057 · UI-058
 ◄several B tasks: UI-059 ◄D-10 · UI-063 · UI-065 ◄D-16 · UI-066 · UI-067 · UI-069 ◄D-05
 last:   UI-068 Copy and terminology
                             │
WAVE 5                       ▼
 UI-070 Palette lock ──► UI-071 Spec records (final) ──► UI-072 QA final ──► UI-073 Final review
```

---

## F. Sequential execution plan

For one agent at a time (or to see the critical path). Decision-blocked tasks slot in where their
dependencies are met once the decision lands; if a decision is late, skip the task and continue.

1. UI-019 baseline capture
2. UI-001 Token foundation
3. UI-005 Stale copy · UI-003 Home overflow · UI-004 Thread header
4. UI-007 Focus, dialogs, Send · UI-008 Post safety · UI-006 Shell frame · UI-010 Fonts
5. UI-002 Contrast · UI-009 Sticky bars
6. UI-011 Button · UI-014 Fields · UI-015 Segmented · UI-013 Floating overlays · UI-012 Modal
   overlays · UI-016 Display
7. *(D-01, D-06, D-12 →)* UI-018 · *(D-03 →)* UI-017
8. UI-019 checkpoint
9. UI-020 Card · UI-021 Alert · UI-022 Meter · UI-023 Search/Chip · UI-024 Toasts · UI-025 States ·
   UI-026 Table · UI-028 Breakpoints · *(D-13 →)* UI-027
10. UI-030 → UI-031 (Inbox) · UI-032 → UI-033 (Composer, Schedule) · UI-034 → UI-035 (Automations) ·
    UI-036 → UI-037 (Settings) · UI-038 → UI-039 (Home, Comments, Knowledge) · UI-040 → UI-041 (Ask,
    Shell) · UI-042 (Public)
11. UI-043 QA checkpoint · UI-044 Review gate
12. UI-051 · UI-052 · UI-054 · UI-056 · UI-057 · UI-058 · UI-061 · UI-063 · UI-064 · UI-066 · UI-067
13. As decided: UI-050 (D-07) · UI-053 (D-14) · UI-055 (D-11) · UI-059 (D-10) · UI-060 (D-08) ·
    UI-062 (D-09) · UI-065 (D-16) · UI-069 (D-05)
14. UI-068 Copy and terminology
15. UI-070 Palette lock · UI-071 Spec records · UI-072 QA final · UI-073 Final review

**Critical path:** UI-001 → UI-011/UI-014 → UI-020 → UI-026 → the slowest area's A and B → UI-043 →
Wave 4 → UI-068 → UI-070 → UI-073.

---

## H. Definition of done

A task is done when all of these hold.

**The brief's bar** (consistency, usability, accessibility, performance, maintainability, visual
quality; existing system → audit → inconsistency → canonical pattern → refactor → verify):

1. **Traceable.** The PR names the task ID, the UI-ISS issues it closes, and any D-xx decision it
   applies.
2. **Canonical.** It uses the tokens and primitives of DESIGN_SYSTEM.md: no hex, `rgb()`, palette
   utilities or arbitrary values in app code; no new colour, gradient, shadow, blur or animation
   without a recorded reason; no duplicate component; the component library is restyled, not
   replaced; nothing outside the task is rewritten or refactored.
3. **Accessible.** Contrast per DESIGN_SYSTEM §1.11; a visible focus indicator on everything the
   task touched; a keyboard path through it; names and states announced; instant under reduced
   motion. axe (tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) shows no new violation at
   375 and 1280 px on the touched pages, and the task's targeted rules are gone.
4. **Responsive.** No horizontal page overflow at 320, 360 and 375 px; the layout holds at 768,
   1024, 1280 and 1536 px; controls are 40 px on coarse pointers.
5. **Performant.** No new `backdrop-filter`, `transition-all` or font file (beyond `latin-ext`);
   `next build`'s route sizes don't grow beyond the new primitives.

**Our gates:**

6. `pnpm lint`, `pnpm typecheck`, `pnpm test` and `pnpm build` green at the repository root.
7. The e2e suite green: `pnpm e2e`, on an isolated stack with a unique database and Valkey db
   (AGENT_CONTEXT §11).
8. Visual QA at **375, 768, 1280 and 1536 px**: before and after screenshots of every touched
   screen, attached to the PR (touch emulation at 375 and 768).
9. **Class-assertion tests** are updated deliberately, never deleted to pass. A fresh count finds
   86 `toHaveClass` assertions in 18 test files (TYPOGRAPHY.md lists the 20 in 8 files that pin type
   and spacing; SPACING.md adds the touch-height ones). These are expected to change:

   | Test | Lines | Task |
   |---|---|---|
   | `inbox/PlatformStrip.test.tsx` | 24, 27, 29 (`bg-brand`); 11, 18 (grid) | UI-002; UI-030 |
   | `inbox/ThreadHeader.test.tsx` | 50, 52, 54 (window chip) | UI-004; UI-031 |
   | `inbox/ConversationRow.test.tsx` | 44 (selection bar) | UI-030 (keep the test id) |
   | `agent/AskPage.test.tsx` | 137 (frame height); 143 (`size-10`) | UI-006; UI-040 |
   | `agent/AskPanel.test.tsx` | 212 (`text-[15px] leading-7`); 642, 644, 649, 651, 653 (touch); 667 (composer focus and radius); 575 (notice); 640 (panel); 319, 647 (table) | UI-040; UI-040; UI-040 and D-16; UI-041; UI-067; UI-026 |
   | `agent/ActionCardView.test.tsx` | 89 (`min-h-10 md:min-h-8`) | UI-040 |
   | `comments/PostDetailPage.test.tsx` | 546, 549 (touch); 534 (layout); 137 (bar) | UI-038; UI-056; UI-039 |
   | `comments/CommentsPage.test.tsx` | 77 (bar) | UI-039 |
   | `schedule/SchedulePage.test.tsx` | 659 (`size-10`) | UI-032 |
   | `inbox/InboxShell.test.tsx` | 95–130 (pane widths) | must pass unchanged in UI-006 and UI-028 |

   E2E specs that change: F-11 and F-13 (the "Breadcrumb" landmark, UI-065), F-13 (the "Post"
   heading, UI-068), F-06 and F-08 (the "Suggested reply" region, if UI-068 renames it).
10. **Docs.** If a rule or decision changed, DESIGN_SYSTEM.md and AGENT_CONTEXT.md change in the same
    PR (by the DSA), and CONFLICTS.md records the decision.
11. **Repository rules.** A `feature/ui-*` branch from `develop`, squash-merged; no Co-Authored-By
    or Claude attribution in commits or PRs; gitleaks clean on the staged diff before each commit.
12. **Reported.** The PR lists the files changed, the commands run with their results, the
    screenshots, and any open question or deviation.
