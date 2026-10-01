# Component audit: apps/web

Read-only audit of the web app's component layer, covering brief sections 2 (component parts), 12, 13, 14, 15 and 19.
No code was changed.

- **Baseline:** `99f67be` (branch `feature/ui-audit`), audited 2026-10-01.
- **Stack:** Next 16.3.6, React 19.2.8 and Tailwind 4 (4.3.3 installed).
  - Primitives are shadcn CLI 4.21.0, style `radix-nova` (components.json). They sit on the unified `radix-ui` 1.6.7 package.
  - Supporting libraries: `class-variance-authority` 0.7.1, `cn` 0.4.0 (shadcn's tailwind-merge replacement), `sonner` 2.0.8, `lucide-react` 1.48.0 and `tw-animate-css` 1.4.0.
- **Spec and decisions checked:** BUILD_SPEC §4.2 (UX-TOK-01/02), §4.3 (UX-SH-01…04), §4.4 (UX-INB-02/03/04/07), §4.6 (UX-CMP-01/02) and UX-A11Y-01…05. Also checked: CONFLICTS C-002, C-018, C-048, C-051, C-063, C-065, C-066, and the mockup `design/social_hood_settings_connections/screen.png`.
- **Priorities:**
  - **P0:** broken, inaccessible or unusable.
  - **P1:** major inconsistency, or a WCAG AA or spec failure on a common control.
  - **P2:** polish.
  - **P3:** minor.

## How the numbers were produced

Small Node scripts were used and not committed. They lived in the session scratchpad.

1. **JSX scanner.** It runs the TypeScript compiler API (`apps/web/node_modules/typescript`) over every `.tsx` under `apps/web/src`, excluding `*.test.tsx`. That is **227 files and 5,027 JSX elements**.
   - For each element it records the tag, attributes, class strings (including those inside `cn(...)` and template literals) and children text.
   - Call-site counts below exclude `components/ui/*`.
   - Where a `className` is only a variable (for example `className={ACTION}`), the constant was read by hand.
2. **Queries over that dump.** These cover:
   - raw elements and the `Button` variant × size matrix;
   - overrides on each primitive;
   - focus treatments, badge and card shape signatures, and touch-target sizing.
3. **`cn` merge test.** Feeding the real `Button` base classes plus typical overrides through `cn` showed what survives. For example, `hover:bg-primary/80` survives a `bg-brand-gradient` override.
4. **Tailwind compile check.** The project's Tailwind 4.3.3 `compile()` was run with the app's `dark` custom variant to read the generated selectors and specificity. It also confirmed which shadcn colour classes generate no CSS.
5. **WCAG contrast calculator.** Alpha tokens are composited over their real surface (panel `#1F1F1F`, field `#1D1D1D`, canvas `#000`).

---

## 1. Primitive layer (`components/ui/*`)

| Primitive | Origin | Restyled to our tokens? | Importing files | Elements in app | Notes |
|---|---|---|---|---|---|
| Button | shadcn radix-nova | No (stock) | 79 | 220 | `default` variant is never used as-is (CMP-002); `destructive` is unused (CMP-003) |
| Badge | shadcn radix-nova | No | **0** | 0 | Unused; 77 hand-rolled badges instead (CMP-013) |
| Input | shadcn radix-nova | No | 11 | 24 | Stock `bg-transparent dark:bg-input/30`, unlike Textarea (CMP-011) |
| Textarea | shadcn, edited | Yes (`bg-field`, `focus-visible:bg-raised`) | 5 | 10 | |
| Label | shadcn | No | 19 | 38 | 22 raw `<label>`; 14 are `sr-only` and fine |
| Checkbox | shadcn | No | 4 | 5 | Unchecked edge 1.35:1; indeterminate shows a tick (CMP-009, CMP-027) |
| Switch | shadcn | No | 7 | 9 | Unchecked track 1.27:1 (the thumb carries the state) |
| Select | shadcn | No | 9 | 14 | Item highlight 1.15:1 (CMP-001) |
| DropdownMenu | shadcn | No | 13 | 14 menus, 40 items | Item highlight 1.15:1 (CMP-001) |
| Popover | shadcn | No | 9 | 11 | |
| Dialog | shadcn | No | 12 | 12 | Overlay `bg-black/10`, 100 ms, no reduced motion (CMP-014) |
| AlertDialog | shadcn | No | 12 | 13 | Same as Dialog |
| Sheet | shadcn | No | 5 | 5 | Same as Dialog |
| Tooltip | shadcn | No | 6 (+ provider) | 7 | White tooltip (`bg-foreground`) on a dark-only app (CMP-026) |
| Tabs | shadcn, edited | Yes (segmented look, UX-INB-03) | 4 | 4 lists | Focus is the ring/50 halo only (CMP-008) |
| ToggleGroup | shadcn, rewritten | Yes (UX-CMP-01 segmented; single only) | 19 | 22 groups, 31 items | Focus is the ring/50 halo only (CMP-008) |
| Skeleton | shadcn | No | 47 | 117 | Default `bg-muted` (field) is invisible on panel; 114 call sites override it (CMP-016) |
| Avatar | shadcn | No | 3 | 5 (+2 wrappers) | `AvatarBadge` and `AvatarGroup` are unused (CMP-032) |

UX-CMP-01 lists **ScrollArea, Separator, Calendar, Command and Sonner** as primitives. None exists in `components/ui` (CMP-030).

**Token-mapping gaps that affect every primitive:**

- **Undefined colour classes.** `globals.css:113-121` (`@theme inline`) maps no `secondary-foreground`, `accent-foreground` or `popover-foreground`. The compile check confirms that `text-secondary-foreground` (3 uses), `text-accent-foreground` (12) and `text-popover-foreground` (7) **generate no CSS** (CMP-015).
- **Dark-variant specificity.** The `dark` custom variant (`globals.css:7`, `&:is(.dark *)`) compiles to `.dark\:bg-input\/30:is(.dark *)`, which has specificity 0,2,0. A plain call-site override such as `bg-field` (0,1,0) therefore **cannot win** against the primitives' `dark:` classes. `cn` keeps both classes (CMP-011).

---

## 2. Inventory by family

### 2.1 Buttons

**Canonical primitive: `ui/button.tsx`**

- **Variants:** `default`, `outline`, `secondary`, `ghost`, `destructive`, `link`.
- **Sizes:** `default` (h-8), `xs` (h-6), `sm` (h-7), `lg` (h-9), `icon` (8), `icon-xs` (6), `icon-sm` (7), `icon-lg` (9).

| Property | Primitive value (button.tsx line) |
|---|---|
| Height | 24 / 28 / 32 / 36 px (`:24-33`); **no 40 px size**, although UX-A11Y-05 asks for 40 px on phones |
| Padding, gap | `px-2.5 gap-1.5`; `xs` and `sm` use `gap-1` (`:24-27`) |
| Radius | `rounded-lg`; `xs` and `sm` use `rounded-[min(var(--radius-md),10/12px)]` (`:7`, `:25-26`). Spec: icon buttons `rounded-full` |
| Type | `text-sm font-medium`; `sm` uses `text-[0.8rem]`, `xs` uses `text-xs` |
| Icon | auto `size-4`; `xs` `size-3`, `sm` `size-3.5` (`:7`, `:25-26`) |
| Hover | per variant; `default` is `hover:bg-primary/80` (`:11`) |
| Focus | `focus-visible:border-ring ring-3 ring-ring/50`; the halo is 2.1:1, the 1 px brand border 4.5:1 (`:7`) |
| Active | `active:not-aria-[haspopup]:translate-y-px` |
| Disabled | `opacity-50 pointer-events-none`. The `pointer-events-none` blocks `title` tooltips (CMP-010) |
| Loading | **none**: no prop and no `aria-busy` |
| Transition | `transition-all` (not motion-safe) |

**Call sites: 220 `<Button>` in 78 files.**

| Variant / size | default | sm | xs | icon | icon-sm | icon-xs | icon-lg | Total |
|---|---|---|---|---|---|---|---|---|
| `default` | 43 | 11 | – | – | – | – | – | **54** (+1 conditional) |
| `secondary` | 38 | 18 | – | – | – | – | – | **56** |
| `ghost` | 27 | 36 | 10 | 13 | 3 | 2 | 13 | **105** (+1 computed) |
| `outline` | 1 | – | – | 1 | – | – | – | **2** |
| `link` | 2 | – | – | – | – | – | – | **2** |
| `destructive` | 0 | – | – | – | – | – | – | **0** |

**Overrides at call sites (Button only):**

- **Primary background.** `bg-brand-gradient text-white` is applied to **50 of 54** `default` Buttons and the other 4 get `bg-danger-fill`. So `default` is never rendered as defined. In total 51 Buttons carry the gradient, across 40 files.
- **Touch sizing.** 66 Buttons add `min-h-10`; others add `h-10`, `size-10` or `size-9`. These are followed by 13 different `md:`/`sm:` "desktop" heights (CMP-004).
- **Danger colours.** 7 Buttons add `text-danger-fg`, 4 add `bg-danger-fill hover:bg-danger-fill/90` and 3 add `hover:bg-danger/10`.

**Bypasses: 63 raw `<button>` in 43 files** (classified by hand from the scan).

| Kind | Count | Should be | Files (line) |
|---|---|---|---|
| Icon or glyph only | 25 | `Button variant="ghost" size="icon*"` | AskPanel:131 · AnalysisChips:105 · ChipListInput:115 · DecisionInfo:35 · SuggestionCard:192, 210 · AutomationRow:153 · KeywordInput:101 · MediaTray:243, 254, 263, 367, 375, 389 · PostPreview:210, 220 · AttachmentTray:80, 91 · EmojiPicker:78 · InstallPrompt:85 · MobileMenu:45 · PhraseChips:106 · BannerSlot:62 · AskComposer:104 · MonthView:132 |
| Filled or tinted action | 8 | `Button` (primary / tint) | inbox/Composer:406 (Send) · AskComposer:115 (Ask) · BannerSlot:51 · UpgradeAction:18 · SourceSheet:369 · MediaTray:224 · AskConversation:216 · (marketing) data-deletion/page:110 |
| Text link | 7 | `Button variant="link"` | settings/workspace/page:237 · SuggestionCard:137 · PostsStep:232 · PostPanel:74 · DetailsPanel:141 · PostPreview:252 · RunView:263 |
| Toggle, chip or segment | 11 | `ToggleGroup` / `Toggle` | ListHeader:95, 163, 176 · PlatformStrip:47 · TemplateGallery:124 · AccountPicker:62 · SchedulePage:455 · CaptionEditor:199 · RunView:140 · ThreadView:323 · AiModeControl:138 |
| Row, tile or card | 12 | Acceptable custom (share hover and focus) | AgentSettingsPage:357 · AskConversation:313 · AskPanel:144 · Threads:176 · PostsStep:248 · MediaLibraryDialog:137 · TemplatePicker:87 · AttachmentView:45 · NotificationsButton:134 · AppSidebar:158 · cell-extras:49, 113 |

**What the raw buttons do with interaction states:**

- **Hover:** 49 of 63 have one.
- **Transition:** 2 of 63 have one.
- **Active:** 2 of 63 have one.
- **Disabled:** 4 of the 14 that take `disabled` have no disabled style (ChipListInput:115, KeywordInput:101, PostsStep:248, PhraseChips:106). Composer:406 and AskComposer:115 swap classes by hand.
- **Radius:** icon-button radius has three values. Primitive icon Buttons are `rounded-lg`; raw ones are `rounded-md` (11) or `rounded-full` (12); the spec says `rounded-full`.

**Gradient CTA.** There are 58 interactive gradient CTAs:

| Where | Count |
|---|---|
| `Button` | 51 |
| `AlertDialogAction` | 3 |
| raw `<button>` | 3 |
| `Link` with `buttonVariants` (PriorityQueue:61) | 1 |

- **No hover in the app.** None of the in-app CTAs has a visible hover. The primitive's `hover:bg-primary/80` survives `cn` and paints the background colour *under* the gradient image (compile check).
- **Only the marketing CTA has one.** `marketing/primitives.tsx:36` (`CTA_CLASS.primary`) and `data-deletion/page.tsx:110` use `hover:brightness-110`.
- **Same gradient, other roles.** The gradient is also used, correctly, for count badges (ListHeader:108, AppSidebar:303), outgoing bubbles (PreviewPane:115, 158) and the PlanCards accent (PlanCards:77).

**Destructive buttons come in five styles** (CMP-003):

1. **Solid `bg-danger-fill`** override: 4 Buttons + 8 `AlertDialogAction`.
2. **`variant="destructive"`**, a red tint with `#EF4444` text: 1 (BillingPage:315).
3. **Ghost with `text-danger-fg`**: 6.
4. **Outline with `border-danger/60`**: 1 (DeleteWorkspace:99).
5. **Secondary with `text-danger-fg`**: 1 (ListView:142).

**Loading buttons** (CMP-017):

- 20 show a spinner and a label.
- 18 only change their label ("Saving…", "Loading…").
- `aria-busy` appears on 2 buttons.
- There are 36 spinning icons: `Loader2` and `LoaderCircle`, which are the same glyph under two lucide names, plus RefreshCw and CheckoutReturn's icon.
  - 7 are `motion-safe:`: SaveBar:75, HomeScreen:104, CheckoutReturn:73, AskComposer:122, Threads:41, StepList:12 and UnsubscribeResult:55.
  - The other 29 use plain `animate-spin` (almost all `Loader2`, including every spinner inside a button), so they keep spinning under reduced motion.

### 2.2 Inputs and forms

| Control | Primitive | Primitive uses | Bypasses | Bypass files (line) |
|---|---|---|---|---|
| Text input | Input | 24 (11 files) | **17** raw text-like `<input>` | ListHeader:128 (inbox search) · AutomationsPage:312 · PostsStep:208 · EmojiPicker:95 · TemplatePicker:113 · HashtagGroupsDialog:212 · ListView:320 · PostingTimesDrawer:263 (time) · ScheduleFields:87, 102 (date and time) · MediaLibraryDialog:82, 95 (date) · KeywordInput:120 · ChipListInput:134 · PhraseChips:76 · AutomationEditor:244 (inline title) · data-deletion/page:100 |
| Textarea | Textarea | 10 (5 files) | 5 raw | inbox/Composer:296 · AskComposer:91 · CommentComposer:81 · ScheduledList:221 · HashtagGroupsDialog:240 |
| Select | Select | 14 (9 files) | 1 native `<select>` | PostPreview:135 |
| Checkbox | Checkbox | 5 | 0 | |
| Radio | **none** | – | 3 native radios inside label cards | AgentDraftDialog:110 · TemplateGallery:275 · AutomationSection:224 |
| Switch | Switch | 9 | 0 | |
| Date and time | **none** (no Calendar) | – | 9 native date or time fields (4 via Input, 5 raw) | RangeControl:113, 127 · SettingsStep:223, 233 · ScheduleFields:87, 102 · MediaLibraryDialog:82, 95 · PostingTimesDrawer:263 |
| Search | **none** | – | 6 implementations (2 Input, 4 raw) | connections/page:165 · AgentSettingsPage:330 · AutomationsPage:312 · PostsStep:208 · ListHeader:128 · EmojiPicker:95 |
| Combobox | **none** (no Command) | – | Long lists use Select (timezone, workspace/page:223 `max-h-72`) | |
| Chip-list input | – | – | 3 near-copies | ChipListInput · KeywordInput · PhraseChips |
| Label | Label | 38 | 8 visible raw `<label>` | NotificationSettingsPage:41 · PushSetup:112 · ListView:116 · PostingTimesDrawer:303 · 3 radio cards · data-deletion:93 |

**Field metrics as built:**

| Metric | Values found |
|---|---|
| Height | 32 px (Input default, 10 uses) · 36 px (`h-9`, 9 uses, plus raw `py-2`) · 40 px (`min-h-10`, 8 uses) · 40 then 36 (`h-10 md:h-9`) · 40 then 32 · 44 px (marketing) |
| Background | Input is near-transparent (white 3%, from `dark:bg-input/30`). Textarea and raw fields are `bg-field`. The 8 `bg-field` overrides on Input are **no-ops** (see §1) |
| Border | `border-input` / `border-line` = white 10% → **1.35:1** against panel or field (UX-A11Y-01 asks ≥ 3:1) |
| Placeholder | Input and Textarea: `placeholder:text-muted-foreground` (#9B9CA0). Raw fields and the global rule: `fg-disabled` (#71717A, 3.5:1). Spec §4.2 says `fg-disabled` |
| Focus | Input, Select, Textarea: 1 px brand border + ring/50 halo. **10 of 17 raw fields, 2 of 5 raw textareas and the native select: background change only** (`focus:bg-raised`, 1.17:1, outline removed); the inbox reply box only lightens its border (1.91:1) (CMP-007). The 3 chip-list inputs ring their wrapper, 3 fields add their own ring, and data-deletion keeps the global outline |
| Error | Primitives: `aria-invalid:border-destructive` + ring. Raw fields: `aria-invalid:border-danger` on 4, nothing on the rest |
| Label style | `Label` default (`text-sm font-medium`) about 23 times; `Label className="text-xs text-fg-secondary"` 15 times |
| Hint and error text | Errors in `text-sm text-danger-fg` or `text-xs text-danger-fg`; hints in `text-xs text-fg-secondary`. In the Field helpers, errors and hints are **not linked** with `aria-describedby` (they rely on `role="alert"`) |
| Field wrapper | **3 private `Field` components**: settings/workspace/page.tsx:421, BrandVoiceCard.tsx:253, SourceSheet.tsx:397. The last two are byte-identical; the first adds a counter and an Info icon. Elsewhere label, field and hint are wired by hand (ScheduleFields, HashtagGroupsDialog, ListView shift dialog, TemplatePicker) |

### 2.3 Dropdowns, selects and menus

| Aspect | DropdownMenu (14 menus, 40 items) | Select (14 triggers, 22 items) |
|---|---|---|
| Trigger | Ghost icon `Button` (6) · secondary or ghost text `Button` (4) · raw chip button (ListHeader:176) · raw AI-mode pill (AiModeControl:138) · the trigger itself styled as a row (WorkspaceMenu:61) · gradient Button (SourcesCard:52) | `SelectTrigger` at **5 heights**: `h-9` (8) · `min-h-10` (3) · `h-10 md:h-9` · `h-10 md:h-8` · `size="sm"` h-7 (ListHeader:147) |
| Content surface | `bg-popover rounded-lg p-1 shadow-md ring-1 ring-foreground/10` (dropdown-menu.tsx:45). **14 of 14** call sites re-add `border-line bg-panel`; 12 of 14 add `shadow-xl` (missing on Threads:96 and WorkspaceMenu:96). Widths: 8 different (`w-40`…`w-80`), always overriding the radix-nova `w-(--radix-dropdown-menu-trigger-width)` | stock; no overrides |
| Item | `px-1.5 py-1 text-sm rounded-md` (about 28 px; 2 of 40 add `min-h-10`) | same (0 of 22 at 40 px) |
| Hover / keyboard highlight | `focus:bg-accent` (= raised #2A2A2A on panel #1F1F1F, **1.15:1**) with `outline-hidden` (CMP-001) | same |
| Selected | Radio and checkbox items: check on the right | check on the right |
| Disabled | `opacity-50` | `opacity-50` |
| Destructive item | `variant="destructive"`: `text-destructive` (#EF4444, 4.38:1) used **once** (post-parts:227). Hand-rolled `text-danger-fg focus:text-danger-fg` **3 times** (AutomationEditor:284, AutomationRow:264, PostComposer:584) | n/a |
| Separators, labels | `DropdownMenuSeparator` (11) and `DropdownMenuLabel` (7; 6 overridden to `text-xs text-fg-secondary`) | `SelectLabel` / `SelectSeparator` unused |
| Nested | `DropdownMenuSub*` exists, unused | n/a |
| Portal, z-index | Radix portal, `z-50` (same layer as dialogs, so a menu inside a dialog relies on DOM order) | same |
| Animation | `data-open:animate-in fade zoom slide`, 100 ms, **no reduced-motion handling** | same |
| Modality | Default `modal`; only ListHeader:174 is `modal={false}` (deliberate, C-063) | |

No hand-rolled menus or listboxes were found. All menus are Radix, so keyboard and typeahead behaviour is the same everywhere. The only native alternative is PostPreview:135 (`<select>`).

### 2.4 Dialogs, sheets, popovers and tooltips

| Component | Primitive defaults | Call-site reality |
|---|---|---|
| **Dialog** (12) | `max-w-sm` · `p-4 gap-4 rounded-xl bg-popover ring-1` · **no shadow** · overlay `bg-black/10 backdrop-blur-xs` · 100 ms zoom and fade · X close is `icon-sm` (28 px) at `top-2 right-2` · footer band `-mx-4 -mb-4 border-t bg-muted/50` | Widths: `sm:max-w-md` (4), `lg` (4), `3xl` (4). **All 12** re-add `border-line bg-panel`; `border-line` is a no-op without a border width. **6 of 12** add `max-h-[calc(100dvh-2rem)] overflow-y-auto`; UpgradeDialog, AttachmentView, ScheduledList, TemplatePicker, ListView and MoveToDialog do not. Titles at **4 sizes**: `text-xl font-semibold` (5) · default `text-base font-medium` (6) · `text-lg font-semibold` (1) · `text-base font-semibold` (1), plus 1 `sr-only`. 2 footers override the band (UpgradeDialog:95, BillingPage:313/328) |
| **AlertDialog** (13) | `max-w-xs` / `sm:max-w-sm` · same overlay · no close X (correct) | All 13 re-add `border-line bg-panel`; 2 widen to `md`. Confirm buttons: 8 solid danger-fill · 3 gradient · 1 `variant="destructive"`. Typed-name confirms use `AlertDialogCancel` and a plain `Button` (DeleteWorkspace, DeleteAccountDialog) |
| **Sheet** (5) | `sm:max-w-sm` · overlay `bg-black/10` · 200 ms slide (no reduced-motion handling) · X close `icon-sm` | Widths: 300 px (2), `md` (2), 256 px (MobileNav). All re-add `border-line bg-panel` |
| **Hand-rolled panels on Radix Dialog** (2) | — | AskPanel.tsx:81-89 and AgentSettingsPage.tsx:394-398 both use `DialogPrimitive` directly as a full-screen-on-phone, right-panel-on-desktop sheet, with overlay **`bg-black/60`**, **200 ms**, **`motion-reduce:animate-none`** and `shadow-xl`. These match the spec; the primitives do not. Focus trapping is still Radix's, so behaviour is fine |
| **Popover** (11) | `w-72 p-2.5 gap-2.5 rounded-lg shadow-md ring-1` | All re-add `border-line bg-panel`; **9 of 11** add `shadow-xl` (missing on CaptionEditor:382 and RangeControl:62). RangeControl:62 adds `border` on top of the ring, giving a double edge. Padding at 5 values (p-0, p-2, p-2.5, p-3, p-4) |
| **Tooltip** (7) | `bg-foreground text-background` (a **white** tooltip with black text) · arrow · provider delay 300 ms (layout.tsx:33) | Used for the collapsed sidebar, usage ring, Ask shortcut, citations and calendar cards. Elsewhere, **native `title`** is used on about 25 meaningful elements (CMP-026) |
| **Confirmation patterns** | AlertDialog | 11 AlertDialogs · 1 Popover confirm (ScheduledList:147-159, "Cancel message") · 1 inline confirm inside a dialog (HashtagGroupsDialog:96-110) · 1 `window.confirm` (SaveBar:33, deliberate per C-066) |

Focus trap and return: every overlay is Radix, so focus is trapped and Escape closes. The two hand-rolled panels use `useReturnFocus`. No overlay without a focus trap was found.

### 2.5 Cards, tables, badges, tabs, segmented controls, alerts, toasts, avatars and meters

| Family | Canonical | Implementations found | Variants and shapes in use |
|---|---|---|---|
| **Card** | none (no `Card` primitive). De facto `SettingsCard` (settings) and composer `Section` | **85** card-like surfaces (rounded, bordered, with a panel or field background), **46** distinct radius, border, background and padding signatures | Radius: `rounded-xl` 47 · `rounded-2xl` 15 · `rounded-lg` 21. Padding: p-3 (16) · p-4 (25) · p-5 (14) · p-6 (5) · `p-5 md:p-6` (4) · `p-4 md:p-5` (2). Inset panel `border-line-subtle bg-field/60` ×7. The settings and billing redesign (C-066) uses `rounded-2xl p-5 md:p-6` (SettingsCard.tsx:46, PlanCards:71, AccountCard:99); the rest follow the spec's `rounded-xl p-4` (Section.tsx:29, MetricTile:64, StepCard:16) |
| **Table** | none | 2 in-app (PaymentHistory.tsx:65, SourcesCard.tsx:137) + Markdown table (AnswerText:124) + legal prose | Headers differ: `thead border-y border-line-subtle` with a TH constant, versus `tr border-b border-line text-xs text-fg-secondary`. Cell padding `px-5 md:px-6 py-3` versus `px-3/5 py-3` |
| **Badge / pill** | `ui/badge.tsx` (**unused**) | **77** ad-hoc badge elements in **39** shape signatures. 8 tone maps: `TONE_CLASS` (lib/inbox/format.ts:70, used in 12 files) · `CHIP_CLASS` (lib/schedule/format.ts:38, **identical** copy) · BillingPage `BADGE` :63 · AccountCard `STATUS_TONE` :20 · AutomationEditor `STATUS_TONE` :75 · RunsPane `RESULT_TONE` :22 · AutomationSection `STATUS_TONE` :25 · MetricTile `BADGE_TONE` :38. Named chips: `StatusChip` **twice** under one name (SourcesCard:72 and post-parts:125), plus RunStatusChip, ReplyWindowChip, ProBadge, PlanBadge, TrendChip, DmChip, ScheduledChip, EditingSuggestionChip, Intent/Sentiment/PriorityChip | Shapes: `rounded-full` (most), `rounded-md` (ReplyWindowChip, MediaTray), `rounded` (ConversationRow:104, PlanBadge, AccountCard:123). Text: `text-xs` · `text-[11px]` · `text-[10px]`. Padding: px-1 to px-3. Neutral background: `bg-white/5` (TONE_CLASS, CHIP_CLASS, AccountCard) · `bg-white/10` (BillingPage, PlanBadge) · `bg-raised` (AutomationEditor, RunsPane, AutomationSection). Count badge: UX-SH-01 asks `h-5 min-w-5 text-xs`; ListHeader:108 is `h-4 min-w-4 text-[10px]` |
| **Tabs** | `ui/tabs` (4: SidePanel, PostPreview, ListView, PostingTimesDrawer) | + settings underline nav (settings/layout.tsx:27, a `Link` nav, which is fine) + **hand-rolled `role="tablist"`** (ListHeader:93-116) | ListHeader tabs: `p-0.5` track with border, `text-xs py-1`, active `text-fg`. Primitive: `p-1`, `text-sm min-h-8`, active `text-brand-fg` |
| **Segmented control** | `ui/toggle-group` (22 groups) | + PlatformStrip:47 (raw `aria-pressed`) + ListHeader tabs | PlatformStrip active is `bg-brand text-white` (a third active style; fails contrast, CMP-006) |
| **Filter chips** | none | 5 implementations: ListHeader `CHIP` :36-38 · TemplateGallery:124 · AnalysisChips:132 (ToggleGroup restyled, no border, `min-h-7`) · CommentsColumn:143 (ToggleGroup restyled, bordered, `min-h-10 md:min-h-8`) · AccountPicker:62 (multi-select) | Selected is always `bg-brand-soft (text-brand-fg)`; border, height and hover differ |
| **Alert / banner** | none (no Alert) | `BannerSlot` (app banners) + **17** inline callouts | Two looks: a borderless soft tint `rounded-lg px-3 py-2` (BannerSlot:41, SuggestionCard:226, HomeScreen:174, SourceSheet:364, StepCard:67) and a bordered tint `rounded-xl px-4 py-3` or `p-4` (AutomationEditor:320, 456, StatusBanner:91, 114, InstallPrompt:81, CheckoutReturn:62). The same tone uses `/10` or `/15` (danger `/10` ×8 vs `/15` ×10; warning `/10` ×4 vs `/15` ×18; success `/10` ×3 vs `/15` ×10). Spec UX-SH-04 asks `rounded-lg px-4 py-2.5` with a soft background. **Tinted action button** hand-rolled 4 times (BannerSlot:25, UpgradeAction:18, SourceSheet:369, MediaTray:367) with `md:` heights 7, 6, 7 and 7 |
| **Toast** | `sonner` `<Toaster theme="dark" position="bottom-right">` (layout.tsx:34) | 57 `toast.success`, 73 `toast.error`; the `toastError()` helper is used at 11 sites | No token styling (`toastOptions` or `classNames`), and no `ui/sonner.tsx`. The spec says "top on phones", but the toaster is bottom-right at every width. 37 direct `toast.error(errorMessage(e))` calls bypass the C-051 plan-limit filter (CMP-023) |
| **Avatar** | `ui/avatar` | 3 wrappers: `ContactAvatar` (inbox; gradient fallback, platform badge `border-2 border-panel`) · `AccountAvatar` (post-parts:84; `bg-raised` fallback, colour ring) · inline in AccountCard:104-115 (`bg-brand-soft` fallback, a different platform badge `ring-2 ring-panel -right-1 size-5`) · marketing `InboxPreview` has its own `Avatar` | `AvatarBadge`, `AvatarGroup` and `AvatarGroupCount` are unused |
| **Meter / progress** | `billing/UsageMeter` for usage; none for progress | **9** bar or ring implementations | See duplicate group D5 |
| **Charts** | none | TrendLine (SVG; StatsPane gives an `sr-only` table, which is good) · SentimentBar (`role="img"` with a label, which is good) · UsageCard collapsed ring · AttachmentTray progress ring | Acceptable for R1. No chart primitive is needed yet |

### 2.6 States (loading, empty, error)

| State | Canonical | Uses | Bypasses and gaps |
|---|---|---|---|
| Page loading | `states/PageSkeleton` | 14 | Fine |
| Block loading | `ui/skeleton` | 117 in 47 files | **114** override the background (107 `bg-raised`, 7 `bg-panel`) because the default `bg-muted` (field #1D1D1D) is invisible on panel (1.02:1). The **3** without an override (UsageCard.tsx:40-42) are invisible. `animate-pulse` ignores reduced motion; only UsageCard opts out. 2 local `RowSkeletons` (AutomationsPage:462, CommentsColumn:19) |
| Spinner | none (lucide `Loader2` / `LoaderCircle` + `animate-spin`) | 36 | Sizes 3 / 3.5 / 4 / 5; 7 of 36 are motion-safe |
| Empty | `states/EmptyState` | 37 in 27 files | No compact variant, so about 8 inline empties are hand-written (Threads:115, 162 · SummarySection:87 · PriorityQueue:112 · TopPostsCard:51 · ScheduleRail:72 · RunTrace:135 · RunView:280). Each uses `text-sm` or `text-xs` |
| Error | `states/ErrorState` | 35 | No compact variant, so 5 hand-rolled inline errors with "Try again": PaymentHistory:46 · PlanCards:49 (as a card) · PostPerformanceCard:43 · NotificationSettingsPage:105 · MediaLibraryDialog:115. ErrorState's retry is a 32 px `secondary` Button with no touch sizing (ErrorState.tsx:30), while the hand-rolled ones use `min-h-10` |
| Inline field error | none | about 40 `<p role="alert" className="text-sm or text-xs text-danger-fg">` | Two sizes; usually not linked to the field |

---

## 3. Interaction-state matrix

Legend:

- ✓ present and adequate.
- ◐ present but weak or inconsistent, with the reason given.
- ✗ missing.
- — not applicable.

Contrast figures are against the real surface.

| Component | Default | Hover | Focus-visible | Active / pressed | Selected | Disabled | Loading | Error / invalid | Success |
|---|---|---|---|---|---|---|---|---|---|
| `Button` secondary, ghost, outline | ✓ | ✓ | ◐ 1 px brand border + ring/50 halo (2.1:1) | ✓ `translate-y-px` | ✓ `aria-expanded` | ◐ `pointer-events-none` hides the `title` reason (CMP-010) | ✗ no prop | ✓ `aria-invalid` | ✗ |
| Gradient CTA (`default` + override, 58) | ✓ | **✗** (1 of 58, outside the app, has one) | ◐ as Button | ✓ | — | ✓ opacity | ✗ ad hoc (20 spinner / 18 label) | — | — |
| Destructive (5 styles) | ◐ | ◐ | ◐ | ✓ | — | ✓ | ✗ | — | — |
| Raw `<button>` (63) | ✓ | ◐ 49 of 63 | ✓ global 2 px outline (where not `outline-none`) | ✗ 2 of 63 | ◐ per site | ◐ 4 of 14 unstyled | ✗ | — | — |
| `Input` | ◐ white 3% background, 1.35:1 edge | ✗ | ✓ brand border (halo 2.1:1) | — | — | ✓ | — | ✓ | ✗ |
| Raw text input (17) | ◐ 1.35:1 edge | ✗ | **✗ 10 of 17: background change only, 1.17:1** | — | — | ◐ | — | ◐ 4 of 17 | ✗ |
| `Textarea` | ✓ | ✗ | ✓ border + `bg-raised` | — | — | ✓ | — | ✓ | ✗ |
| Raw textarea (5) | ✓ | ✗ | ◐ 2 background only; inbox composer wrapper `focus-within:border-line-strong` 1.91:1; Ask and comment composers ✓ ring | — | — | — | ◐ `aria-busy` on inbox (Polish) | ◐ | — |
| `SelectTrigger` | ◐ 1.35:1 edge | ✓ | ✓ border + halo | — | ✓ `data-placeholder` | ✓ | — | ✓ | — |
| Native `<select>` (1) | ◐ | ✗ | ✗ background only | — | — | — | — | — | — |
| `Checkbox` | **◐ unchecked edge 1.35:1** | ✗ | ✓ border + halo | — | ✓ checked; **✗ indeterminate shows a tick** | ✓ | — | ✓ | — |
| `Switch` | ◐ unchecked track 1.27:1 (white thumb carries it) | ✗ | ✓ | — | ✓ | ✓ | ✗ (saving shown elsewhere) | ✓ | — |
| Native radio card (3) | ✓ | ✓ | ✓ global outline | — | ✓ card border | — | — | — | — |
| `ToggleGroupItem` / `TabsTrigger` | ✓ | ◐ text colour only | **✗ halo only (ring/50, 2.1:1) with `outline-none`** | — | ✓ raised + brand-fg (7.2:1) | ✓ (`pointer-events-none`) | — | — | — |
| ListHeader tabs / PlatformStrip | ✓ | ✓ | ✓ global outline | — | ◐ PlatformStrip white on brand **3.63:1** | — | ◐ PlatformStrip skeleton | — | — |
| Filter chips (5 kinds) | ✓ | ◐ 3 of 5 | ◐ global or ring/50 | — | ✓ brand-soft | ◐ | — | — | — |
| `DropdownMenuItem` / `SelectItem` | ✓ | ◐ 1.15:1 | **✗ same 1.15:1 background, `outline-hidden`** | — | ✓ check icon | ✓ | — | ◐ destructive 4.38:1 | — |
| Link rows (ConversationRow, sidebar nav, MetricTile) | ✓ | ◐ `white/5` (1.15:1) | ✓ global or ring | — | ✓ `bg-raised` + brand bar | — | — | — | — |
| Dialog / Sheet close X | ✓ | ✓ | ✓ | ✓ | — | — | — | — | — |

**Missing states that matter most:**

1. Keyboard highlight in menus and selects (CMP-001).
2. Focus on raw fields (CMP-007) and on segmented and tab items (CMP-008).
3. Hover on every gradient CTA (CMP-002).
4. A `loading` state on Button (CMP-017).
5. An honest `indeterminate` on Checkbox (CMP-027).
6. A disabled-with-reason pattern (CMP-010).

---

## 4. Duplicate groups and proposed canonical

| # | Problem solved | Implementations (count) | Proposed canonical |
|---|---|---|---|
| D1 | Primary CTA | `Button` + `bg-brand-gradient text-white` (51) · `AlertDialogAction` + gradient (3) · raw gradient buttons (3) · `Link` + `buttonVariants` + gradient (1) · marketing `CTA_CLASS.primary` | **`Button variant="default"` redefined as the gradient**, with `hover:brightness-110` taken from marketing `CTA_CLASS.primary`. Delete all 58 overrides |
| D2 | Destructive action | danger-fill override (12) · `variant="destructive"` tint (1) · ghost + `text-danger-fg` (6) · outline + `border-danger/60` (1) · secondary + `text-danger-fg` (1) · menu `text-danger-fg` (3) vs `variant="destructive"` (1) | `Button variant="destructive"` = solid `bg-danger-fill text-white` (5.5:1); add `variant="destructive-ghost"` = `text-danger-fg hover:bg-danger/10`; `DropdownMenuItem variant="destructive"` → `text-danger-fg` |
| D3 | Segmented control | `ToggleGroup` (22) · `Tabs` (4, same look) · ListHeader hand-rolled `tablist` · PlatformStrip `aria-pressed` | **`ToggleGroup`** for value choice and **`Tabs`** when it swaps panels (ListHeader Chats/Scheduled swaps panels, so `Tabs`). PlatformStrip → `ToggleGroup` with a per-item tone |
| D4 | Filter chips | ListHeader `CHIP` · TemplateGallery · AnalysisChips ToggleGroup restyle · CommentsColumn ToggleGroup restyle · AccountPicker | Add `ToggleGroup variant="chips"` (single) and `type="multiple"` support. Use one chip spec: `rounded-full border text-xs`, at least 40 px on touch |
| D5 | Meter and progress bar | UsageMeter (canonical, `role="meter"`) · BillingPage `QuotaTile` (re-implements the bar, copies `FILL` at :93) · UsageCard (`role="progressbar"` for usage, own thresholds and `BAR` map, solid `bg-brand` fill, `white/10` track) · ScheduleRail:108 (`h-1`, `bg-field` track, inline 80/100% thresholds) · DetailsPanel LeadScore:180 · PostPanel AnalysisProgress:26 (flex-grow) · MediaTray:46 (`white/15` track) · SourceSheet:330 · AttachmentTray ring | **`ui/meter`** (usage with `meterLevel` thresholds; `role="meter"`) and **`ui/progress`** (task progress; `role="progressbar"`). One track (`bg-raised`), one height (`h-1.5`), one fill rule (decor gradient, warning at 80%, danger at 100%) |
| D6 | Status badge or pill | `ui/badge` (unused) · 8 tone maps (`TONE_CLASS` ≡ `CHIP_CLASS`) · 77 ad-hoc badges · two `StatusChip`s | **`Badge`** restyled with `tone` (neutral, brand, success, warning, danger; one neutral, `bg-white/5`), `size` (`sm` 11 px, `md` 12 px) and `shape` (`pill`, `tag`). Delete `CHIP_CLASS`; keep `TONE_CLASS` only as Badge's source |
| D7 | Card wrapper | SettingsCard (2xl, p-5/6) · composer Section (xl, p-4/5) · StepCard · MetricTile frame · PlanCards · AccountCard · 7 inset `bg-field/60` panels · 85 hand-written surfaces | **`ui/card`** (`Card`, `CardHeader`, `CardInset`) with `padding` (sm, md, lg) and `tone` (default, danger, brand). SettingsCard becomes a thin wrapper. The owner picks the radius (spec `xl` vs C-066 `2xl`) |
| D8 | Inline alert or callout | BannerSlot · 17 hand-written callouts (2 looks, `/10` vs `/15` tints) · KnowledgeGapBanner / AccountHealth (`border-warning/40 bg-panel`) | **`ui/alert`** with `tone` and `variant` (soft, outline); add soft tokens (`--color-success-soft` and so on) like `brand-soft` |
| D9 | Tinted action button on a coloured background | BannerSlot `actionClass` · UpgradeAction · SourceSheet:369 · MediaTray:367/375 | `Button variant="tint"` (`bg-white/10 hover:bg-white/15 text-current`) |
| D10 | Form field wrapper | 3 private `Field` components · hand-wired label + hint + error elsewhere | **`ui/field`** (shadcn Field) that sets `id`, `aria-describedby` and `aria-invalid`; one label style and one error style |
| D11 | Search input | 6 (2 Input, 4 raw) | `SearchInput` on `Input` (icon at `left-3`, `pl-9`, clear on Escape like ListHeader) |
| D12 | Chip-list input | ChipListInput · KeywordInput · PhraseChips | One `ChipInput` (they differ only in validation and counters) |
| D13 | Side panel or sheet | `Sheet` (5) · AskPanel and AgentSettingsPage on `DialogPrimitive` | Add `SheetContent size="panel"` (full screen below `md`, fixed width above, `bg-black/60`, 200 ms, motion-reduce) and move both panels onto it |
| D14 | Confirmation | AlertDialog (11) · Popover confirm (ScheduledList) · inline confirm (HashtagGroupsDialog) · `window.confirm` (SaveBar) | AlertDialog for destructive actions on a page; keep the inline confirm inside dialogs (no nested modal) and `window.confirm` for leave-page (C-066) |
| D15 | Tooltip | Radix Tooltip (7) · native `title` (about 25) | Radix `Tooltip` for anything meaningful (status ticks, badges, disabled reasons); keep `title` only for truncated text |
| D16 | Loading button | spinner + label (20) · label only (18) | `Button loading` prop (spinner, `aria-busy`, width kept) |
| D17 | Empty and error, compact | `EmptyState` / `ErrorState` · about 13 inline versions | Add `size="compact"` to both |
| D18 | Avatar + platform badge | ContactAvatar · AccountAvatar · AccountCard inline · marketing Avatar | `ContactAvatar`'s badge via `ui/avatar`'s `AvatarBadge` |
| D19 | Table | PaymentHistory · SourcesCard | `ui/table` (low priority) |
| D20 | Focus treatment | global 2 px outline · ring-3 ring/50 (primitives + 13 sites) · ring-2 ring-brand (6) · background only (13) · focus-within border (1) | **The global `:focus-visible` outline** (`2px brand, offset 2px`, 4.5–5.8:1) everywhere; primitives stop removing it |

---

## 5. Findings

Each finding gives priority, problem, evidence, affected files and recommendation. Line numbers are at `99f67be`.

### CMP-001 · P0 · Keyboard highlight in menus and selects is not visible
- **Problem:** Radix menus and selects show the active item only with `focus:bg-accent` (raised #2A2A2A) on the panel (#1F1F1F), and the outline is removed (`outline-hidden`). The difference is **1.15:1**, so a keyboard user can't see which item Enter will choose. This fails WCAG 2.4.7 and UX-A11Y-01/02.
- **Evidence:** dropdown-menu.tsx:75, 97, 141, 228 (`focus:bg-accent … outline-hidden`); select.tsx:114. The 1.15:1 figure comes from the contrast script.
- **Affected:** all 14 DropdownMenus (40 items) and 14 Selects (22 items). These include the thread More menu, AI-mode menu, automation row menus, schedule post menu and filters, and the workspace and timezone selects.
- **Recommendation:** In the primitives, make the highlight `focus:bg-brand-soft focus:text-fg` and add a visible marker: an inset 2 px `shadow-[inset_2px_0_0_var(--color-brand)]`, or `focus-visible:outline-2 outline-brand -outline-offset-2`. Use one rule for `DropdownMenuItem`, `*CheckboxItem`, `*RadioItem`, `SubTrigger` and `SelectItem`.

### CMP-002 · P1 · The primary button is hand-built 58 times and has no hover
- **Problem:**
  - The `default` variant is solid `bg-primary` (#567FF8) with white text. That pair is 3.63:1, which UX-TOK-02 retired.
  - Every primary call site instead pastes `bg-brand-gradient text-white`.
  - `cn` keeps the variant's `hover:bg-primary/80`, which paints the background colour **under** the gradient image, so no in-app CTA reacts to hover.
- **Evidence:**
  - button.tsx:11.
  - 50 of 54 `default` Buttons carry the gradient and the other 4 carry `bg-danger-fill`. That makes 0 uses of the variant as defined.
  - 58 gradient CTAs in total: 51 Button, 3 AlertDialogAction, 3 raw buttons, 1 Link.
  - The `cn` merge test shows `hover:bg-primary/80 … bg-brand-gradient` both kept.
  - Only marketing `CTA_CLASS.primary` (primitives.tsx:36) and data-deletion/page.tsx:110 use `hover:brightness-110`.
- **Affected:** 40 files. Examples: settings/SaveBar:112, PostComposer:719, Composer:523, BillingPage:230, UpgradeDialog:106/115, TemplatePicker:132, SchedulePage:402/538, SourcesCard:53, AgentDraftDialog:127, RangeControl:154.
- **Recommendation:** Redefine the variant as `default: "bg-brand-gradient text-white hover:brightness-110 active:brightness-95 motion-safe:transition-[filter]"`, then remove the 58 overrides. Use the same class for `AlertDialogAction`'s default.

### CMP-003 · P1 · Destructive actions come in five styles, and the primitive's red text fails AA
- **Problem:**
  - The `destructive` Button variant is a 20% red tint with `#EF4444` text, which gives **3.51:1**.
  - The `destructive` menu item is `#EF4444` text on panel, which gives **4.38:1**. Both fail 4.5:1 for 14 px text.
  - Spec §4.2 reserves `danger` for icons and borders, and `danger-fg` for text.
  - Because the variant is unusable, call sites invented four other looks.
- **Evidence:**
  - button.tsx:19 and dropdown-menu.tsx:75 (`data-[variant=destructive]:text-destructive`).
  - BillingPage:315 is the only `variant="destructive"`; post-parts:227 is the only destructive menu item.
  - Solid `bg-danger-fill text-white hover:bg-danger-fill/90` appears ×12: DeleteAccountDialog:181, ScheduledList:156, HashtagGroupsDialog:103, DeleteWorkspace:152, plus 8 AlertDialogActions (AutomationEditor:407, AutomationRow:282, CommentRow:245, PostComposer:812, DisconnectDialog:47, SourcesCard:238, ListView:205, SchedulePage:605).
  - Ghost with `text-danger-fg`: CommentRow:225, DeleteAccountDialog:119, DisconnectDialog:32, ScheduledList:149, SourcesCard:208, HashtagGroupsDialog:146.
  - Outline: DeleteWorkspace:99. Secondary: ListView:142.
  - Hand-rolled menu items: AutomationEditor:284, AutomationRow:264, PostComposer:584.
- **Recommendation:**
  - Make `destructive` solid `bg-danger-fill text-white hover:bg-danger-fill/90` (5.5–6.2:1).
  - Add `destructive-ghost` (`text-danger-fg hover:bg-danger/10`).
  - Make the menu item's destructive variant use `text-danger-fg` and `focus:bg-danger/15`.
  - Migrate all 25 sites.

### CMP-004 · P1 · Touch targets are patched by hand at 142 sites, and over 200 controls are still under 40 px on phones
- **Problem:** UX-A11Y-05 asks for 40 × 40 px on phones, but no primitive has a touch size.
  - **Hand patches:** call sites patch heights with `min-h-10`, `h-10` or `size-10`, followed by one of **13 different** `md:`/`sm:` desktop sizes (`md:min-h-8` ×52, `md:min-h-7` ×19, `md:min-h-9` ×15, `md:size-8` ×15, `md:h-9` ×11, `md:min-h-0` ×7, …).
  - **Unpatched controls:** many still miss 40 px.
- **Evidence:** the scanner found:

  | Control | Under 40 px on phones |
  |---|---|
  | `Button` with no touch override | **112 of 220**, in 44 files (56 default 32 px or SuggestionCard's 36 px `ACTION`, 39 `sm` 28 px, 10 `xs` 24 px, 5 `icon`, 2 `icon-xs`) |
  | `ToggleGroupItem` / `TabsTrigger` | **29 of 40** at 32 px |
  | `DropdownMenuItem` | **38 of 40** at about 28 px |
  | `SelectItem` | **22 of 22** |
  | Raw icon buttons | **11** at 20–32 px: ChipListInput:115, KeywordInput:101, AttachmentTray:91 (`size-5`) · AnalysisChips:105, DecisionInfo:35, AttachmentTray:80 (`size-6`) · SuggestionCard:210 (`size-5`) · MonthView:132 (`size-7`) · EmojiPicker:78, PhraseChips:106, AutomationRow:153 (`size-8`) |

  - SuggestionCard's `ACTION` (`h-9`, :31) is 36 px.
  - Dialog and Sheet close X are `icon-sm` (28 px; dialog.tsx:74, sheet.tsx:76).
  - ErrorState's retry is 32 px (ErrorState.tsx:30).
  - Two strategies coexist: `md:` breakpoints (142 sites) and `pointer-coarse:` (sidebar-styles.ts:10, UsageCard:103, AskComposer, RunView).
- **Affected:** 46 files with small Buttons (the most in ThenStep, inbox/Composer, SuggestionCard, AutomationsPage, CommentRow, MessageBubble, ScheduledList, HashtagGroupsDialog and PostingTimesDrawer). It also affects all menus, selects and segmented controls.
- **Recommendation:**
  - Put the rule in the primitives once, with one strategy: `pointer-coarse:min-h-10` / `pointer-coarse:size-10`. This is better than `md:` because touch laptops and tablets above 768 px also need it.
  - Apply it to Button (all sizes), ToggleGroupItem, TabsTrigger, menu and select items, SelectTrigger, Input and the close buttons.
  - Then delete the 142 hand patches.

### CMP-005 · P1 · Inbox list header controls are hand-rolled, small and not real tabs
- **Problem:** The most-used screen's header bypasses `Tabs` and `ToggleGroup`.
  - **Chats | Scheduled** is a `role="tablist"` of buttons with no `aria-controls`, no tab panel and no arrow-key movement, so it is a broken ARIA tabs pattern. It is `text-xs py-1` (about 24 px).
  - **View chips** are about 26 px.
  - **PlatformStrip** segments are about 28 px.
  - The **Send** button is `h-9` (36 px) on phones and 32 px on desktop. C-018 fixed Send at **40 px on phones**.
- **Evidence:** ListHeader.tsx:93-116 (tablist) and :36-38, 162-172 (chips); PlatformStrip.tsx:47-56; inbox/Composer.tsx:406-412.
- **Affected:** inbox/ListHeader.tsx, inbox/PlatformStrip.tsx, inbox/Composer.tsx.
- **Recommendation:**
  - Chats | Scheduled → `Tabs`/`TabsList` (keep the count badge, at the spec's `h-5 min-w-5 text-xs`).
  - Platform → `ToggleGroup`.
  - Chips → the D4 chip variant.
  - Send → `Button` with a 40 px touch size, per C-018.

### CMP-006 · P1 · The PlatformStrip active segment fails text contrast
- **Problem:** The active platform segment is white `text-xs` on solid `bg-brand` (#567FF8), which is **3.63:1**. UX-TOK-02 replaced exactly this pair. It is also a third active-segment style; ToggleGroup and Tabs use `bg-raised text-brand-fg` (7.2:1).
- **Evidence:** PlatformStrip.tsx:54. The same pair appears on the marketing skip link, (marketing)/layout.tsx:23 (`bg-brand … text-white`, text-sm).
- **Recommendation:** Use the ToggleGroup active style. If the platform colour must show, keep it on the dot (`:60`) or use `bg-brand-gradient`, which ends at #4467E6 (4.85:1).

### CMP-007 · P1 · Thirteen raw fields show focus only as a 1.17:1 background change
- **Problem:** Raw inputs, textareas and the native select remove the outline (`outline-none`) and signal focus only with `focus:bg-raised`, a change from #1D1D1D to #2A2A2A (**1.17:1**). The inbox reply box only lightens its border to `line-strong` (**1.91:1**).
- **Evidence:**
  - ListHeader:128-142 (inbox search) · ScheduleFields.tsx:78-79 (date and time, used by the inbox schedule popover and the composer's When section) · TemplatePicker:113 · HashtagGroupsDialog:212, 240 · ListView:320 · PostingTimesDrawer:263 · ScheduledList:221 · EmojiPicker:95 · MediaLibraryDialog:82, 95 · PostPreview:135 (`<select>`).
  - inbox/Composer.tsx:292 (`focus-within:border-line-strong`).
  - By contrast, AutomationsPage:312, PostsStep:208 and CommentComposer:81 add `focus-visible:ring-3`, and ChipListInput, KeywordInput, PhraseChips and AskComposer ring their wrapper.
- **Recommendation:** Replace the raw fields with `Input`, `Textarea` and `Select` (D10, D11). Where a wrapper must take focus, use `focus-within:` with the same token as the primitives (see CMP-008).

### CMP-008 · P1 · Focus has five treatments, and the primitives' halo is below 3:1
- **Problem:**
  - **ToggleGroup and Tabs halo.** `ToggleGroupItem` and `TabsTrigger` remove the outline and show only `ring-3 ring-ring/50`. Brand at 50% is **2.1:1** against field or panel, below the 3:1 that UX-A11Y-01 and WCAG 1.4.11 ask for state indicators. Thirteen hand-styled cards and tiles copy the same halo-only ring.
  - **Five styles in total:**
    1. The global `:focus-visible` (2 px solid brand, 2 px offset): 4.54:1 on panel, 5.79:1 on canvas.
    2. ring-3 ring/50.
    3. `ring-2 ring-brand` (6 sites).
    4. Background only (CMP-007).
    5. `focus-within` border (1).
- **Evidence:**
  - Primitives: toggle-group.tsx:37 and tabs.tsx:27.
  - Halo-only call sites: Section.tsx:29, StepCard:16, MetricTile:67, PostCard, PriorityQueue, TopPostsCard, PostsStep:248, MediaTray, AutomationEditor:244, AutomationsPage:312, CommentComposer:81.
  - `ring-2 ring-brand`: settings/layout.tsx:32, settings/workspace/page.tsx:237, AgentSettingsPage:357, PaymentHistory, CalendarPostCard:44, PhraseChips:106.
  - Global rule: globals.css:127.
- **Recommendation:** Make the global outline the single focus style: primitives use `focus-visible:outline-2 focus-visible:outline-brand focus-visible:outline-offset-2` instead of `outline-none` plus ring/50. Keep the brand border on fields. Remove the per-site rings.

### CMP-009 · P1 · Control edges are below 3:1
- **Problem:** UX-A11Y-01 asks for control borders of at least 3:1.
  - `border-input` / `border-line` (white 10%) is **1.35:1** on field or panel.
  - Input's fill (white 3%) is **1.09:1**, and field vs panel is **1.02:1**.
  - An unchecked Checkbox is therefore close to invisible.
  - An unchecked Switch track is **1.27:1**; its white thumb still reads.
- **Evidence:** globals.css:110 (`--input: var(--color-line)`); input.tsx:10; checkbox.tsx:16; switch.tsx:19 (`dark:data-unchecked:bg-input/80`); select.tsx:46. Figures come from the contrast script.
- **Affected:** every Input, SelectTrigger and Checkbox, and the raw fields.
- **Recommendation:** Add a control-edge token, for example `--color-line-control: rgb(255 255 255 / 0.40)`. That is 3.77:1 on panel; #737373 gives 3.48:1. Use it for `--input` and for unchecked Checkbox and Switch. This changes the look, so it is an **owner decision**; the mockups use faint edges.

### CMP-010 · P1 · Disabled controls hide the reason they are disabled
- **Problem:** `Button` and `ToggleGroupItem` use `disabled:pointer-events-none`, so a `title` on a disabled control can never show. Keyboard and touch users can't reach it either. Several screens explain the disabled state only that way.
- **Evidence:**
  - ThreadHeader.tsx:115-121: "Scheduling needs an open reply window".
  - inbox/Composer.tsx:364-368: "Write a reply to polish".
  - ConnectWhatsAppButton.tsx:84-87: "WhatsApp isn't set up for this app yet".
  - SuggestionCard.tsx:169-173 is mitigated by the visible "No drafts left".
  - AiSettingsPage.tsx:183-188 is mitigated by ProBadge and "Upgrade for Auto".
  - The source rules are button.tsx:7 and toggle-group.tsx:37.
- **Recommendation:** Add a `DisabledReason` pattern: wrap the control in a focusable `span` with a Radix `Tooltip`, or use `aria-disabled` with visible helper text. Use it wherever a disabled control has a reason (this is also the FR-PUB-10 composer rule: "disabled buttons say why").

### CMP-011 · P1 · Input looks different from every other field, and its overrides do nothing
- **Problem:** The fields don't match each other:
  - `Input` is stock shadcn: `bg-transparent dark:bg-input/30` with a `muted-foreground` placeholder.
  - `Textarea` was restyled to the spec: `bg-field`, `focus:bg-raised`.
  - Raw fields are `bg-field` with the global `fg-disabled` placeholder.

  So an Input next to a Textarea in the same form looks different. Call sites tried `bg-field` 8 times, but `dark:bg-input/30` compiles to specificity 0,2,0 and always wins.

  Heights also vary: 32, 36 and 40 px.
- **Evidence:** input.tsx:10 vs textarea.tsx:9. The compile check output is `.dark\:bg-input\/30:is(.dark *)`. The `bg-field` overrides are at SettingsStep:163, 223, 233, ThenStep:184, 517, 743, 760 and connections/page:165 (also `border-0`).
- **Affected:** 11 files with Input, plus forms mixing Input with Textarea (SourceSheet, BrandVoiceCard, ThenStep).
- **Recommendation:**
  - Restyle Input like Textarea: `bg-field focus-visible:bg-raised`, placeholder `fg-disabled`, no `dark:` background, 40 px on touch (CMP-004) and 36 px otherwise.
  - Drop the 8 overrides.
  - Apply the same to `SelectTrigger` and the outline Button's `dark:bg-input/30`.

### CMP-012 · P2 · Forms have no shared field pattern
- **Problem:**
  - There are three private `Field` components, two of them identical.
  - Labels use two styles: `text-sm font-medium` and `text-xs text-fg-secondary` (15 times).
  - Error text uses two sizes.
  - Hints and errors are not linked to their inputs (`aria-describedby`); they rely on `role="alert"` firing once.
- **Evidence:** settings/workspace/page.tsx:421-458, BrandVoiceCard.tsx:253-279 and SourceSheet.tsx:397-423. SourceSheet:267-297 inputs set `aria-invalid` but no `aria-describedby`. The `text-xs` labels are in ThenStep:740, 757, CaptionEditor:262, ScheduleFields:84, 99, HashtagGroupsDialog:209, 229, ListView:317, 330, 347, TemplatePicker:110, ScheduledList:218, MediaLibraryDialog:79, 92 and PostPreview:132.
- **Recommendation:** Add `ui/field` (shadcn Field: `Field`, `FieldLabel`, `FieldDescription`, `FieldError`) that generates ids and `aria-describedby`. Choose one label style per density (form or compact). Replace the three copies.

### CMP-013 · P1 · Badges: the primitive is unused, there are 77 ad-hoc badges and 8 tone maps
- **Problem:** Status pills are rebuilt per screen, with three neutral backgrounds, three radii, three text sizes and duplicated tone tables. Two different components are both exported as `StatusChip`.
- **Evidence:**
  - ui/badge.tsx has 0 imports.
  - The scanner found 77 badge-like elements in 39 shape signatures.
  - The tone maps are listed in §2.5. `CHIP_CLASS` (lib/schedule/format.ts:38-44) duplicates `TONE_CLASS` (lib/inbox/format.ts:70-76).
  - The two `StatusChip`s are knowledge/SourcesCard.tsx:72 and schedule/post-parts.tsx:125.
  - The neutral backgrounds are `bg-white/5`, `bg-white/10` (BillingPage:64, PlanBadge) and `bg-raised` (AutomationEditor:76, RunsPane:27, AutomationSection:26).
- **Recommendation:**
  - Restyle `Badge` (tone × size × shape) from `TONE_CLASS`, with one neutral background.
  - Rename the two `StatusChip`s (for example `PostStatusBadge` and `SourceStatusBadge`) and build both on `Badge`.
  - Make ListHeader:108's count badge match UX-SH-01 (`h-5 min-w-5 text-xs`), as AppSidebar:310 already does.

### CMP-014 · P1 · Overlay primitives don't follow the spec, so 55 call sites patch them
- **Problem:** The primitives disagree with spec §4.2 and with each other:
  - **Scrim:** `bg-black/10` is invisible on a black app; the spec asks `bg-black/60`.
  - **Motion:** 100 ms, where the spec asks 200 ms for sheets and dialogs.
  - **Reduced motion:** none of the primitives handle it (tw-animate-css and shadcn's CSS have no rule for it); the spec says "instant".
  - **Shadow:** `shadow-md` or none, where the spec asks `shadow-xl` for popovers, menus and dialogs.

  The two hand-rolled panels follow the spec, so overlays behave differently across the app. Separately, every content call site re-adds `border-line bg-panel`; `bg-panel` is already the base and `border-line` does nothing without a border width.
- **Evidence:**
  - Primitive overlays: dialog.tsx:42, alert-dialog.tsx:39, sheet.tsx:40.
  - Primitive surfaces: dialog.tsx:64 (no shadow), dropdown-menu.tsx:45, select.tsx:71, popover.tsx:32 (`shadow-md`).
  - Hand-rolled panels: AskPanel.tsx:81-89 and AgentSettingsPage.tsx:394-398.
  - Patching call sites: 55 of them (Dialog 12, AlertDialog 13, Sheet 5, Popover 11, Dropdown 14). Missing `shadow-xl`: CaptionEditor:382, RangeControl:62, Threads:96, WorkspaceMenu:96 and all dialogs and sheets.
- **Recommendation:** In the primitives:
  - overlay `bg-black/60`;
  - `duration-200`;
  - `motion-reduce:animate-none` on overlay and content;
  - `shadow-xl` on dialog, popover, menu and select content.

  Then delete the 55 patches. Add the `panel` sheet size from D13.

### CMP-015 · P2 · Primitives use colour classes that generate no CSS
- **Problem:** `text-secondary-foreground` (3), `text-accent-foreground` (12) and `text-popover-foreground` (7) have no `@theme` token, so they output nothing. Secondary Buttons, menu items and popovers inherit their parent's text colour. For example, a secondary Button inside a `text-warning` banner turns orange.
- **Evidence:** globals.css:113-121 is the `@theme inline` block, which lacks these tokens. The compile check produced no rules for them. They are used in button.tsx:15, dropdown-menu.tsx:75, 97, 141, 201, 228, select.tsx:114, and the content classes in dialog, sheet, popover and dropdown.
- **Recommendation:** Add `--color-secondary-foreground`, `--color-accent-foreground`, `--color-popover-foreground` and `--color-card-foreground` to `@theme inline` (two lines; C-002 already allows additions).

### CMP-016 · P2 · Skeleton's default is invisible
- **Problem:** `Skeleton` uses `bg-muted` (field #1D1D1D), which is 1.02:1 against the panel it usually sits on. As a result, 114 of 117 call sites override it, and the 3 that don't are invisible. `animate-pulse` ignores reduced motion.
- **Evidence:** skeleton.tsx:7. Overrides: 107 `bg-raised` and 7 `bg-panel`. Invisible: UsageCard.tsx:40-42.
- **Recommendation:** Make the default `bg-raised motion-safe:animate-pulse`, then remove the 107 overrides.

### CMP-017 · P2 · Buttons have no loading state, and spinners ignore reduced motion
- **Problem:** Pending buttons are written two ways: a spinner plus a label (20), or a label change only (18). The label-only version changes the button's width. Only 2 buttons set `aria-busy`. Spinners come in four sizes, and only 7 of 36 are motion-safe.
- **Evidence:** spinner-plus-label examples are TemplateGallery:215, PostComposer:709 and CropDialog:169. Label-only examples are BrandVoiceCard:245, PostingTimesDrawer:203, DeleteWorkspace:152, TestBox:51 and the "Loading…" pagers (AgentSettingsPage:305, Threads:196, CommentsColumn:115, ListView:164, PaymentHistory:129). None of the `Loader2` spinners inside buttons is `motion-safe:`; SaveBar:75 is the pattern to copy.
- **Recommendation:** Add a `loading` prop to `Button`: a leading `Loader2` (`motion-safe:animate-spin`), `aria-busy`, disabled while loading and width kept. Optionally pass `loadingText`.

### CMP-018 · P2 · There are four segmented-control implementations
- **Problem:** ToggleGroup (22), Tabs (4, styled identically, which is correct), the ListHeader hand-rolled tablist and the PlatformStrip `aria-pressed` group. The last two each have their own track, padding, text size and active style.
- **Evidence:** see D3, CMP-005 and CMP-006.
- **Recommendation:** Keep ToggleGroup and Tabs only. Also expose `size` on both (`sm` = text-xs for dense headers), so call sites stop passing `text-xs`. Today 5 ToggleGroupItem call sites pass `text-xs` and 3 pass `min-h-9`.

### CMP-019 · P2 · There are five filter-chip implementations
- **Problem:** Chips that filter a list are built five ways, with different borders, heights (26 / 28 / 32–40 px) and hover styles.
- **Evidence:** ListHeader.tsx:36-38 · TemplateGallery.tsx:124-133 · AnalysisChips.tsx:125-136 · CommentsColumn.tsx:135-146 · AccountPicker.tsx:62-75.
- **Recommendation:** Add `ToggleGroup variant="chips"` (with `type="multiple"` for AccountPicker) and use one chip spec.

### CMP-020 · P2 · Cards have no primitive, and two radius and padding systems coexist
- **Problem:** There are 85 hand-written card surfaces in 46 variants. The settings and billing redesign introduced `rounded-2xl p-5 md:p-6`; the spec, and the rest of the app, use `rounded-xl p-4`. On Home, Inbox and Automations cards are xl; on Settings and Billing they are 2xl.
- **Evidence:** SettingsCard.tsx:46, PlanCards.tsx:71, AccountCard.tsx:99 and settings/connections/page.tsx:144, 162, 189 (2xl), against Section.tsx:29, MetricTile.tsx:64, StepCard.tsx:16 and PageSkeleton.tsx:14 (xl). Inset panels `rounded-xl border-line-subtle bg-field/60` appear at settings/workspace/page:273, AgentSettingsPage:154, 170, BillingPage:406, AccountCard:150 and AiSettingsPage:152, 303.
- **Recommendation:** Add `ui/card` (`Card`, `CardInset`, padding scale, tones) and record the radius decision. This needs an owner call: C-066 vs UX-TOK `rounded-xl`.

### CMP-021 · P2 · Meters and progress bars are re-implemented nine times
- **Problem:** The bars differ in several ways:
  - **Thresholds:** duplicated (`meterLevel` in UsageMeter, copied `FILL` in BillingPage, UsageCard's own tones, ScheduleRail inline).
  - **Tracks:** `bg-raised`, `bg-white/10`, `bg-white/15` and `bg-field`.
  - **Height:** `h-1` and `h-1.5`.
  - **Fill:** decor gradient or solid brand.
  - **Role:** UsageCard reports a usage meter as `role="progressbar"`.
- **Evidence:** UsageMeter.tsx:11-23, 57-67 · BillingPage.tsx:93-97, 433-443 · UsageCard.tsx:12-17, 85-98 · ScheduleRail.tsx:108-119 · DetailsPanel.tsx:180-188 · PostPanel.tsx:26-34 · MediaTray.tsx:46-54 · SourceSheet.tsx:330-336 · AttachmentTray.tsx:23.
- **Recommendation:** Add `ui/meter` and `ui/progress` (D5). BillingPage's QuotaTile and UsageCard should compose `Meter`.

### CMP-022 · P2 · Alerts and callouts have no primitive, and tones are ad hoc
- **Problem:** The 17 callouts use two looks. The same tone appears at `/10` and `/15`, and danger tints sometimes have a solid `border-danger`. A "tinted action" button is hand-rolled 4 times with three heights. There are no soft tokens for success, warning or danger (only `brand-soft`).
- **Evidence:** §2.5 alert row. BannerSlot.tsx:25-26, 41-42 · UpgradeAction.tsx:18-22 · SourceSheet.tsx:369 · MediaTray.tsx:367, 375 · AutomationEditor.tsx:320 (`border-danger bg-danger/10`) vs StepCard.tsx:67 (`bg-danger/10`, no border) vs BannerSlot (`bg-danger/15`).
- **Recommendation:** Add `ui/alert` (`tone`, `variant="soft|outline"`) and `--color-{success,warning,danger}-soft` tokens. Add the `tint` Button variant from D9.

### CMP-023 · P2 · Toasts are unstyled, bottom-right on phones, and can duplicate plan-limit messages
- **Problem:**
  - **Styling:** `Toaster` has no token styling and no `ui/sonner.tsx` wrapper.
  - **Position:** UX-SH-04 asks for bottom-right with top on phones; the code is bottom-right at every width.
  - **Plan limits:** C-051 says each 402 shows one message. `toastError()` enforces that, but 37 calls use `toast.error(errorMessage(e))` directly. Any of those mutations that can return 402 will show the upgrade dialog (the global handler) **and** a toast.
- **Evidence:**
  - Toaster: layout.tsx:34.
  - The global 402 handler: lib/api/provider.tsx:72-104.
  - `toastError` (11 sites): lib/toast-error.ts:10.
  - Direct calls, for example: AutomationsPage:183, 206, 218, 228 · TemplateGallery:49 · AgentDraftDialog:67 · PostComposer:431, 528, 539 · SchedulePage:271, 301 · BillingPage:219, 224 · AutomationEditor:203, 213, 225.
  - Four sites guard by hand with `isPlanLimitError` (connections/page:231, 278, AiModeControl:65, AiSettingsPage:117).
- **Recommendation:**
  - Add `ui/sonner.tsx` with token `classNames` (panel background, line border, danger-fg for errors) and `position` switching to `top-center` below `md`.
  - Replace direct `toast.error(errorMessage(e))` with `toastError(e)`, and add a lint rule that forbids the direct form.

### CMP-024 · P2 · Dialog anatomy is inconsistent
- **Problem:**
  - Titles appear at four sizes and weights.
  - Half the dialogs can't scroll on short phones.
  - Two footers drop the band.
  - 24 descriptions re-apply `text-fg-secondary`, which is the same as the base `text-muted-foreground`.
  - The close X is 28 px.
- **Evidence:**
  - Titles: DialogTitle `text-xl font-semibold` at TemplateGallery:117, 260, AutomationSection:209, 249 and MediaLibraryDialog:63 (5); default `text-base font-medium` at AgentDraftDialog:75, UpgradeDialog:80, ScheduledList:212, TemplatePicker:62, ListView:309 and MoveToDialog:79 (6); `text-lg font-semibold` at CropDialog:104; `text-base font-semibold` at HashtagGroupsDialog:44.
  - No `max-h`: UpgradeDialog:78, AttachmentView:54, ScheduledList:210, TemplatePicker:60, ListView:306, MoveToDialog:68.
  - Footer overrides: UpgradeDialog:95, BillingPage:313, 328.
- **Recommendation:** Bake into DialogContent `max-h-[calc(100dvh-2rem)] overflow-y-auto` and a `size` prop (`sm|md|lg|xl`). Set one title style in the primitive (`text-lg font-semibold`, or the spec's section title). Make the close button 40 px on touch.

### CMP-025 · P3 · Destructive confirmation has three in-page patterns
- **Problem:** ScheduledList confirms "Cancel message" in a Popover, which has no `alertdialog` role and closes on outside click. Everything else that deletes from a page uses AlertDialog.
- **Evidence:** ScheduledList.tsx:147-159 vs CommentRow:235, SourcesCard:229 and ListView:194. The inline confirm in HashtagGroupsDialog.tsx:96-110 is reasonable because it avoids a nested modal.
- **Recommendation:** Use AlertDialog for ScheduledList and document the rule (D14).

### CMP-026 · P2 · Native `title` tooltips carry information, and Tooltip is styled against the theme
- **Problem:**
  - About 25 meaningful elements use `title`, which is invisible to keyboard and touch users. These include delivery status ticks, the "AI Assisted" note, row badges, "Paused until …", the thread title and account-filter avatars.
  - The Radix Tooltip is a **white** bubble (`bg-foreground text-background`), while every other floating surface is `bg-panel`.
- **Evidence:** MessageBubble.tsx:220, 225 · ConversationRow.tsx:104 · AiModeControl.tsx:112 · SuggestionCard.tsx:156, 161 · SchedulePage.tsx:455 · Threads.tsx:176 · AttachmentTray.tsx:54; tooltip.tsx:44, 50.
- **Recommendation:** Restyle Tooltip to `bg-panel text-fg ring-1 ring-line shadow-xl` (or keep it inverted, if the owner prefers it, but decide). Move meaningful `title`s to `Tooltip` plus an `sr-only` or `aria-describedby` text.

### CMP-027 · P2 · An indeterminate Checkbox shows a tick
- **Problem:** Radix renders the Indicator for `"indeterminate"`, and the primitive always draws `CheckIcon`. Its fill only applies to `data-checked`. A partial selection therefore shows a white tick in an unfilled box, which reads as "all selected", and clicking it selects all.
- **Evidence:** checkbox.tsx:21-27; ListView.tsx:117-119 (select all posts).
- **Recommendation:** Render `MinusIcon` when `data-state="indeterminate"` and fill the box for that state too.

### CMP-028 · P3 · Hover tints and transitions are ad hoc
- **Problem:** Neutral hover backgrounds come at five levels:

  | Class | Uses |
  |---|---|
  | `hover:bg-white/5` | 22 |
  | `hover:bg-raised` | 13 |
  | `hover:bg-white/10` | 12 |
  | `hover:bg-white/15` | 2 |
  | `hover:bg-white/20` | 3 |

  The `raised-hover` token is used once. Primitive Buttons transition (`transition-all`, not motion-safe); raw buttons do not (2 of 63).
- **Recommendation:** Define two hover steps as tokens (`hover-subtle` = white/5 on panel rows, `hover` = raised-hover on controls) and use `motion-safe:transition-colors` across the board.

### CMP-029 · P2 · Search fields have six implementations
- **Problem:** The six differ in height (36 / 40 px), icon padding (`pl-9` / `pl-10`), focus style (ring, background only, primitive) and border (`border-0` on connections).
- **Evidence:** connections/page.tsx:164-165 · AgentSettingsPage.tsx:329-330 · AutomationsPage.tsx:308-312 · PostsStep.tsx:204-208 · ListHeader.tsx:124-142 · EmojiPicker.tsx:95.
- **Recommendation:** Add `SearchInput` (D11), with Escape to clear as in ListHeader:134-139.

### CMP-030 · P3 · Native controls are used where UX-CMP-01 lists primitives
- **Problem:** ScrollArea, Separator, Calendar, Command and a Sonner wrapper are specified but absent.
  - Dates and times use 9 native fields, whose pickers render in OS chrome.
  - There are 3 native radios with no RadioGroup.
  - There is 1 native `<select>`.
  - The long timezone list is a Select with no search.
- **Evidence:** §2.2 table; PostPreview.tsx:135; settings/workspace/page.tsx:223-226.
- **Recommendation:** Add `RadioGroup` and replace the 3 radios. Decide whether native date and time fields are accepted for R1, record it in CONFLICTS, and add `Command` for the timezone picker later. The other primitives can come in as they are needed.

### CMP-031 · P3 · Link-style buttons are mostly hand-rolled
- **Problem:** The `link` variant is used twice, while 7 raw buttons copy `text-brand-fg hover:underline`. The variant itself uses `text-primary` (#567FF8, 4.54:1 on panel); the spec says links on dark use `brand-fg` (#9DB5FF), and both variant call sites override to that.
- **Evidence:** button.tsx:20; AiSettingsPage:210 and ScheduleRail:81 (variant); raw buttons listed in §2.1.
- **Recommendation:** Make `link` use `text-brand-fg`, add the touch size, and migrate the 7.

### CMP-032 · P3 · There are three avatar wrappers and two platform-badge styles
- **Evidence:** ContactAvatar.tsx:47-58 (`-right-0.5 -bottom-0.5 border-2 border-panel`) vs AccountCard.tsx:108-115 (`-right-1 -bottom-1 size-5 ring-2 ring-panel`). The fallbacks are a gradient, `bg-brand-soft` and `bg-raised`. avatar.tsx:59 `AvatarBadge` is unused.
- **Recommendation:** Use ContactAvatar, or AccountAvatar built on it, everywhere, with its badge implemented by `AvatarBadge`.

### CMP-033 · P3 · Tables have two header styles
- **Evidence:** PaymentHistory.tsx:65-80 vs SourcesCard.tsx:137-156.
- **Recommendation:** Add `ui/table` when a third table appears. Until then, align SourcesCard to PaymentHistory, which has the caption, `scope` and the newer style.

### CMP-034 · P3 · Empty and error states have no compact size
- **Problem:** The 13 inline empties and errors are hand-written. ErrorState's retry is 32 px.
- **Evidence:** §2.6.
- **Recommendation:** Add `size="compact"` to `EmptyState` and `ErrorState` (left-aligned, `text-sm`, `Button size="sm"` with touch sizing), and migrate.

### CMP-035 · P3 · Menu content widths are overridden everywhere
- **Problem:** The radix-nova base sizes menus to the trigger's width (`w-(--radix-dropdown-menu-trigger-width)`). That is wrong for icon triggers, so all 14 menus override it with 8 different widths, and `DropdownMenuLabel` is restyled at 6 of its 7 sites.
- **Evidence:** dropdown-menu.tsx:45, 172; §2.3.
- **Recommendation:** Set the primitive to `min-w-48 w-auto` and the label to `text-xs text-fg-secondary`, then drop the per-site classes.

---

## 6. Suggested order of work

1. **Primitive pass (one PR, low risk, removes about 400 call-site classes).** This covers:
   - Button: gradient default, solid destructive, tint, link → brand-fg, `loading`, touch size.
   - Input restyle and the four missing `*-foreground` tokens.
   - Skeleton default.
   - Overlay scrim, motion, reduced motion and shadow.
   - Menu and select highlight.
   - Focus outline in Tabs and ToggleGroup.
   - Checkbox indeterminate.

   It fixes CMP-001, 002, 003, 008, 011, 014, 015, 016, 017 and 027 at the source.
2. **Inbox header and composer (CMP-004, 005, 006, 007).** These are the screens used most on phones.
3. **New shared components:** Badge tones, Meter and Progress, Card, Alert, Field and SearchInput (CMP-012, 013, 019, 020, 021, 022, 029).
4. **Sweep the call sites** to delete overrides, which a lint rule can flag (for example, `bg-brand-gradient` on `<Button>`). Then the P3s.

**Owner decisions needed:**

- the control-edge token (CMP-009);
- the card radius, `xl` vs `2xl` (CMP-020);
- the tooltip colour (CMP-026);
- native date and time pickers for R1 (CMP-030).
