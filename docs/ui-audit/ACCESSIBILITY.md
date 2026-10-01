# Accessibility audit (brief §15 focus and touch, §16)

Read-only audit of `apps/web` on `feature/ui-audit` (commit `99f67be`), 1 October 2026. Nothing in
the app was changed. The standard is the spec's: **UX-A11Y-01…05** (`docs/BUILD_SPEC.html` §4.8),
**WCAG 2.2 AA**, **UX-TOK-02** (text 4.5:1, icons and control borders 3:1) and the C-018 touch-size
decision.

**Priorities.** P0: broken or unusable (WCAG A or AA failures that block use). P1: major. P2:
polish. P3: minor.

**Result.** No P0 was found. Keyboard users and screen-reader users can reach every flow that was
checked. Ten P1 findings remain.

- **Six are WCAG failures:**
  - single-letter shortcuts that can't be turned off (2.1.4, Level A);
  - weak focus indicators on text fields and on the primitives (2.4.7 and 1.4.11, two findings);
  - focus hidden behind sticky bars (2.4.11);
  - text contrast (1.4.3);
  - control-border contrast (1.4.11).
- **Four break the spec's own rules:**
  - there is no skip link in the app;
  - focus is lost after some dialogs close;
  - phone touch targets are under 40 px, including the composer's Send, which C-018 set at
    40 px;
  - the Radix primitives ignore reduced motion.

| Priority | Count | IDs |
|---|---|---|
| P0 | 0 | none |
| P1 | 10 | A11Y-001 to A11Y-010 |
| P2 | 9 | A11Y-011 to A11Y-019 |
| P3 | 5 | A11Y-020 to A11Y-024 |

## How it was checked

- **Static review.** I read the tokens (`apps/web/src/styles/globals.css`), every primitive in
  `components/ui/*`, the shell, the inbox and the composer. I also scanned all `.tsx` files for
  `outline-none` with no replacement, icon-only buttons with no name, inputs with no label,
  `aria-invalid` with no `aria-describedby`, `aria-label` on elements with no role, live regions,
  images and keyboard handlers. The scripts are kept outside the repo.
- **Real renders.** I started an isolated e2e stack from this worktree (`scripts/e2e-stack.mjs
  --serve`), using its own ports and data:
  - ports **8117** (API) and **3117** (web), set with `E2E_API_PORT` and `E2E_WEB_PORT` so it
    didn't collide with a sibling run on 8100 and 3100;
  - database `socialhood_test_17` and Valkey db 11;
  - the e2e Clerk test user, with a fresh workspace and a connected sandbox Instagram account
    (sandbox backfill plus three or four inbound DMs).

  Temporary Playwright specs (Chromium 1243) did the following:
  - visited 21 pages at **360, 375, 768, 1024, 1280 and 1536 px**, with an extra reflow check of
    15 app pages at **320** and **640 px** (640 px is 1280 px at 200% zoom);
  - ran **axe-core 4.13.0** from `node_modules/.pnpm` at 375 and 1280 px, with the tags `wcag2a`,
    `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa` and `best-practice`;
  - measured every visible interactive element;
  - tabbed through Home and a conversation;
  - opened the mobile drawer, a dialog, a popover and a menu, with and without emulated
    `prefers-reduced-motion: reduce`.

  The specs were deleted afterwards and the database was dropped. Screenshots are in a temporary
  folder outside the repo.
- **Contrast.** Contrast was computed from the token hex values with the WCAG 2.x
  relative-luminance formula. Translucent tokens (for example `white/10` or `brand/50`) were
  blended over the surface they sit on.
- **Not covered.**
  - No real screen reader (NVDA, JAWS, VoiceOver, TalkBack) and no Safari or iOS. The live-region
    findings (A11Y-016) need confirming with one.
  - No Windows forced-colours mode.
  - Clerk's hosted sign-in and sign-up forms were not audited.
  - The composer's uploads, the calendar's drag and drop, and the billing checkout were reviewed
    from the code only.

## What is already good

- `<html lang="en">` is set (`app/layout.tsx:24`). Every page has a `<main>`. The sidebar is a
  `<nav aria-label="Main">` with labelled groups (`AppSidebar.tsx:90-98`, `:243-263`).
- **Icon-only buttons are named everywhere.** The scan found no unnamed icon button, and axe
  reported no `button-name` or `link-name` violation on any page.
- **Conversation rows are links.** Each row has `aria-current`, and unread is announced through
  `role="img" aria-label="unread"` (`ConversationRow.tsx:214-258`). Arrow keys move between rows
  (`ConversationList.tsx:59-71`), and j and k work: at runtime, `j` moved to the next
  conversation.
- **The inbox's live regions follow UX-A11Y-03.** The message list is
  `role="log" aria-live="polite"` (`MessageLog.tsx:152-160`), and a newly unread conversation is
  announced once, politely (`ConversationList.tsx:92-94`, `:141-159`).
- **The mobile drawer meets UX-A11Y-02.** It traps focus (25 Tab presses stayed inside), closes on
  Esc and returns focus to "Open menu". The notifications popover moves focus in and returns it
  to the bell. The Ask panel returns focus through `useReturnFocus`
  (`AskPanel.tsx:77-90`).
- **Ask's live steps** are an `aria-live="polite"` list that announces new steps and labels but
  not the ticking seconds (`StepList.tsx:78-90`). Sonner's toast region is a polite live region.
- **Toggles are Radix switches** (`role="switch"` and `aria-checked`), as UX-A11Y-04 asks.
  Segmented controls use `aria-pressed` or `role="radio"`.
- **Several forms tie their errors to their fields:** `DeleteWorkspace.tsx:132`,
  `DeleteAccountDialog.tsx:161`, `RangeControl.tsx:113-127` and `HashtagGroupsDialog.tsx:212`.
- **axe found little.** Over 42 page-and-width runs it reported only `color-contrast` (10 nodes),
  `page-has-heading-one` (4), `scrollable-region-focusable` (1) and `landmark-unique` (1). The
  `aria-prohibited-attr`, `landmark-one-main` and `region` violations came from the loading
  skeleton, captured before Schedule had loaded at 375 px.
- **The spec's contrast fixes landed.** Message bubbles use the darker gradient end `#4467E6`
  (4.85:1), timestamps use `fg-secondary` (6.0:1) and failed bubbles use `danger-fill` (5.47:1).

## Contrast table

All values were computed from `globals.css:9-49`. "Over" means a translucent colour blended onto
that surface.

### Text (4.5:1 needed; 3:1 for 18.66 px bold or 24 px and larger)

| Pair | Foreground | Background | Ratio | Result | Where |
|---|---|---|---|---|---|
| fg on canvas, panel, field, raised | `#FFFFFF` | `#000`–`#2A2A2A` | 21–14.4:1 | Pass | everywhere |
| fg-secondary on canvas | `#9B9CA0` | `#000000` | 7.66:1 | Pass | |
| fg-secondary on panel | `#9B9CA0` | `#1F1F1F` | 6.01:1 | Pass | |
| fg-secondary on field | `#9B9CA0` | `#1D1D1D` | 6.15:1 | Pass | |
| fg-secondary on raised | `#9B9CA0` | `#2A2A2A` | 5.23:1 | Pass | selected rows, active segments |
| fg-secondary on raised-hover | `#9B9CA0` | `#333333` | 4.61:1 | Pass (just) | |
| fg-secondary on white/10 over panel | `#9B9CA0` | `#353535` | **4.47:1** | **Fail** | neutral badges, `BillingPage.tsx:64` |
| fg-secondary on white/10 over raised | `#9B9CA0` | `#3F3F3F` | **3.84:1** | **Fail** | "Coming soon", `PlanCards.tsx:84` (axe: 3.48:1 inside `opacity-80`) |
| fg-secondary/70 on panel | `#767679` | `#1F1F1F` | **3.64:1** | **Fail** | sidebar group labels (11 px), `AppSidebar.tsx:257` |
| fg-disabled (placeholders) on panel | `#71717A` | `#1F1F1F` | **3.41:1** | **Fail** | `globals.css:128` `::placeholder` |
| fg-disabled (placeholders) on field | `#71717A` | `#1D1D1D` | **3.49:1** | **Fail** | inbox search, composer |
| fg-disabled (placeholders) on raised | `#71717A` | `#2A2A2A` | **2.97:1** | **Fail** | the same fields when focused (`focus:bg-raised`) |
| brand-fg on panel | `#9DB5FF` | `#1F1F1F` | 8.23:1 | Pass | |
| brand-fg on raised | `#9DB5FF` | `#2A2A2A` | 7.17:1 | Pass | active tabs and segments |
| brand-fg on brand-soft over panel | `#9DB5FF` | `#272D40` | 6.83:1 | Pass | chips |
| brand as text on panel | `#567FF8` | `#1F1F1F` | 4.54:1 | Pass (just) | `link` variant |
| white on brand | `#FFFFFF` | `#567FF8` | **3.63:1** | **Fail** | active platform segment `PlatformStrip.tsx:54` (axe); marketing skip link `(marketing)/layout.tsx:25` |
| white on gradient start | `#FFFFFF` | `#20338A` | 11.04:1 | Pass | |
| white on gradient end | `#FFFFFF` | `#4467E6` | 4.85:1 | Pass | outgoing bubbles, primary buttons |
| white/75 on gradient end | `#D0D9F9` | `#4467E6` | **3.46:1** | **Fail** | "Template · …" label, `MessageBubble.tsx:103`, `:142` |
| white/90 on gradient end | `#ECF0FC` | `#4467E6` | **4.26:1** | **Fail** | "Unsupported message format", `MessageBubble.tsx:165` |
| white on shell-gradient | `#FFFFFF` | `#3352CC`–`#1C2D70` | 6.5–12.7:1 | Pass | Upgrade, logo |
| white on danger-fill | `#FFFFFF` | `#C53030` | 5.47:1 | Pass | failed bubble, delete buttons |
| danger-fg on panel | `#FCA5A5` | `#1F1F1F` | 8.68:1 | Pass | error text |
| danger as text on panel | `#EF4444` | `#1F1F1F` | **4.38:1** | **Fail** | destructive menu items, `dropdown-menu.tsx:75` (used at `post-parts.tsx:227`) |
| danger on destructive/20 over panel | `#EF4444` | `#492626` | **3.51:1** | **Fail** | destructive `Button`, `button.tsx:19` (used at `BillingPage.tsx:315`) |
| warning on panel; on warning/15 | `#FB923C` | `#1F1F1F`; `#403023` | 7.28:1; 5.57:1 | Pass | |
| success on panel; on success/15 | `#22C55E` | `#1F1F1F`; `#1F3828` | 7.23:1; 5.57:1 | Pass | |
| instagram as text on panel | `#BE185D` | `#1F1F1F` | **2.73:1** | **Fail** | "Instagram" in the thread header, `ThreadHeader.tsx:26`, `:100` (axe) |
| whatsapp as text on panel | `#16A34A` | `#1F1F1F` | 5.00:1 | Pass | `ThreadHeader.tsx:26` |
| canvas on fg (tooltip) | `#000000` | `#FFFFFF` | 21:1 | Pass | `tooltip.tsx:44` |

### Non-text: icons, control borders, focus (3:1 needed)

| Pair | Ratio | Result | Where |
|---|---|---|---|
| Focus outline brand vs canvas / panel / raised | 5.79 / 4.54 / 3.96:1 | Pass | global `:focus-visible`, `globals.css:127` |
| Focus ring `ring-ring/50` vs panel / canvas / raised | **2.10 / 2.13 / 1.98:1** | **Fail** | every primitive: `button.tsx:7`, `tabs.tsx:27`, `toggle-group.tsx:37`, `input.tsx:10`, `select.tsx:45`, `checkbox.tsx:16`, `switch.tsx:19` |
| `border-input` (white/10) vs panel / canvas | **1.34 / 1.21:1** | **Fail** | input, select, checkbox and outline-button borders |
| `border-line-strong` (white/20) vs panel | **1.92:1** | **Fail** | composer border when focused, `Composer.tsx:292` |
| Unchecked switch track (white 8%) vs panel | **1.27:1** | **Fail** | `switch.tsx:19` (`dark:data-unchecked:bg-input/80`) |
| Unchecked switch thumb vs its track | 13.0:1 | Pass | the state can be read from the thumb |
| field vs panel / canvas (input fill as boundary) | **1.02 / 1.25:1** | **Fail** | raw text fields with `border-line` |
| raised vs field (focus shown only by a fill change) | **1.17:1** | **Fail** | `focus:bg-raised` fields (A11Y-003) |
| Checked switch / unread dot (brand) vs panel | 4.54:1 | Pass | |
| fg-secondary, danger, brand icons on panel | 6.01 / 4.38 / 4.54:1 | Pass | |
| fg-disabled icon ("Not done" circle) on panel | 3.41:1 | Pass | `Checklist.tsx:84` |
| Instagram badge disc vs panel | 2.73:1 | Pass | the white glyph inside is 6.04:1 and carries the meaning |
| WhatsApp tile with white glyph | 3.30:1 | Pass for a glyph (fails if it ever holds text) | `Platforms.tsx:31`, `Hero.tsx:24` |

**Token proposal.**
- **Control borders and checkbox outlines:** use `#71717A`. It gives 3.41:1 on panel, 3.49:1 on
  field and 4.35:1 on canvas. Add it as a new `--color-line-control` token, so that `fg-disabled`
  keeps its "disabled only" meaning.
- **Placeholders:** use `fg-secondary` (5.23:1 even on raised).
- **Text on brand fills:** use the gradient, or `#3B5BD9` for a solid fill (5.70:1).

## Touch-target table (375 px, UX-A11Y-05 asks for 40 × 40)

Measured as rendered, including the `after:` hit extension on checkboxes and switches. Inline
links inside running text are exempt and are left out. WCAG 2.5.8 (24 px) holds everywhere: the
smallest target is 24 × 24 px.

| Page | Control | Size (px) | Source |
|---|---|---|---|
| Inbox list | Platform segments All, Instagram | 169 × 28 | `PlatformStrip.tsx:53` (`py-1.5 text-xs`) |
| Inbox list | Chats, Scheduled tabs | 57 × 24, 84 × 24 | `ListHeader.tsx:102` (`py-1`) |
| Inbox list | View chips (All … More) | 41–93 × 26 | `ListHeader.tsx:36` (`py-1`) |
| Inbox list | Search | 351 × 38 | `ListHeader.tsx:142` |
| Conversation | AI mode menu | 117 × 32 | `AiModeControl.tsx:146` (`h-8`) |
| Conversation | Correct the analysis (pencil) | **24 × 24** | `AnalysisChips.tsx:108` (`size-6`) |
| Conversation | Suggestion: Dismiss, Draft again, Insert, Send | 36–107 × 36 | `SuggestionCard.tsx:31` (`h-9 … md:h-7`) |
| Conversation | AI Polish | 84 × 32 | `Composer.tsx:367` (`h-8`) |
| Conversation | **Send** | **40 × 36** | `Composer.tsx:412` (`h-9`). C-018 says 40 px on phones. |
| Conversation | Failed-message actions (Retry, Copy text…) | × 24 | `MessageBubble.tsx:242-271` (`size="xs"`) |
| Home | Dismiss checklist, checklist action | 87 × 28, 115 × 28 | `Checklist.tsx:66`, `:93` (`size="sm"`) |
| Automations | New automation, search, filter selects | 151 × 36, 218 × 36, 112–122 × 32 | `AutomationsPage.tsx:298`, `:319`, `:341`, `:354` |
| Automations | Row name link | 115 × 20 | `AutomationRow.tsx` |
| Automation editor | Breadcrumb, name input, tabs, trigger and match radios, keyword input, Edit | 16–32 tall | `AutomationEditor.tsx`, `steps/*` |
| Knowledge | Add knowledge, inputs, tone and emoji radios, Save, Ask | × 32 | `KnowledgePage.tsx`, `BrandVoiceCard.tsx`, `TestBox.tsx` |
| Settings | Connections filter radios, AI-mode radios, phrase "Add" | × 36 | `connections/page.tsx`, `AiSettingsPage.tsx`, `PhraseChips.tsx` |
| New post | Preview tabs Feed, Reel, Grid | 98 × 32 | `PostPreview.tsx` |
| Sidebar drawer | Upgrade (credits card) | × 32 | `UsageCard.tsx:106` (`h-6 pointer-coarse:h-8`) |

**Measured share under 40 px at 375 (all visible interactive elements):** inbox 12 of 20,
conversation 8 of 18, automations 7 of 10, automation editor 18 of 29, knowledge 16 of 21,
settings 3 to 6 per tab. The cause is systemic: the `Button` sizes are 32 px (`default`), 28 px
(`sm`), 24 px (`xs`), 32 px (`icon`), 28 px (`icon-sm`) and 24 px (`icon-xs`), with no
coarse-pointer bump (`button.tsx:22-33`). There are 225 `<Button>` uses, 69 of them `sm` and 11
`xs`. Only the sidebar rows and the Upgrade link use `pointer-coarse:`
(`sidebar-styles.ts:10`, `:14`; `UsageCard.tsx:106`).

## Findings

### A11Y-001 · P1 · Single-letter inbox shortcuts can't be turned off (WCAG 2.1.4, Level A)
- **Problem.** j, k, e, u and / act window-wide whenever focus is not in a text field: on the body,
  a button, a message action or the suggestion bar. There is no way to turn them off or remap
  them, and they don't depend on the list having focus. A speech-input user saying a word such as
  "e" archives the open conversation and moves to the next. A stray key while focus sits on "Send"
  or "Insert" does the same.
- **Evidence.**
  - `components/inbox/use-inbox-shortcuts.ts:33-63`: a `window` keydown listener whose only
    guards are modifiers, editable targets and open dialogs.
  - At runtime, `j` pressed with focus on `<body>` opened the next conversation.
- **Affected.** `use-inbox-shortcuts.ts`, `InboxShell.tsx:212-239`.
- **Recommendation.** Add a "Keyboard shortcuts" switch, on by default, in Settings or in a "?"
  shortcuts sheet, stored per device. Or apply the letters only while focus is inside the
  conversation list or thread pane. Either one satisfies 2.1.4. Keep Esc as it is.

### A11Y-002 · P1 · No skip link in the app shell
- **Problem.** Every app page puts 14 sidebar tab stops before the page's first control:
  - the workspace menu and Ask;
  - six nav links;
  - Notifications, Settings, Help and Collapse;
  - Upgrade and the account button.

  Landmarks satisfy WCAG 2.4.1 for screen-reader users, but a sighted keyboard user has no way
  to bypass the sidebar. The marketing site already has a skip link.
- **Evidence.**
  - Tab order on Home at 1280 px: stops 1–14 are in the sidebar and stop 15 is "7 days".
  - In a conversation, the composer is stop 42.
  - `AppShell.tsx:89-109` has no skip link. Compare `(marketing)/layout.tsx:23-28`.
- **Affected.** `components/shell/AppShell.tsx`.
- **Recommendation.**
  - Render `<a href="#main" class="sr-only focus:not-sr-only …">Skip to content</a>` first in
    `AppShell`.
  - Give `<main>` (`AppShell.tsx:106`) `id="main" tabIndex={-1}`.
  - Fix the marketing skip link's colours at the same time (A11Y-005).

### A11Y-003 · P1 · Text fields that show focus only by a 1.17:1 fill change (WCAG 2.4.7, 1.4.11)
- **Problem.** Many raw `<input>` and `<textarea>` fields set `outline-none`, which overrides the
  global brand outline. They then rely on `focus:bg-raised` alone: field `#1D1D1D` turns to raised
  `#2A2A2A`, a 1.17:1 change. The inbox composer, the most-used field in the app, also lightens its
  border from white/10 to white/20 (1.34:1 to 1.92:1), and that is all.
- **Evidence.**
  - At runtime, the focused search and composer both had `outline: none` and `box-shadow: none`.
    In a screenshot, the focused composer can't be told apart from the unfocused one.
  - Files:
    - inbox: `ListHeader.tsx:142`, `Composer.tsx:292`, `:309`, `EmojiPicker.tsx:101`,
      `ScheduledList.tsx:227`, `TemplatePicker.tsx:117`;
    - schedule: `HashtagGroupsDialog.tsx:219`, `:247`, `ListView.tsx:326`,
      `PostingTimesDrawer.tsx:275`;
    - composer: `MediaLibraryDialog.tsx:88`, `:101`, `PostPreview.tsx:139`;
    - automations: `AutomationsPage.tsx:319` (its `ring-ring/50` is too faint; see A11Y-004).
- **Recommendation.**
  - Remove `outline-none` from these fields so the global outline shows, or add
    `focus-visible:ring-2 focus-visible:ring-brand`.
  - On the composer, use `focus-within:ring-2 focus-within:ring-brand` on the wrapper, as
    `ChipListInput.tsx:104`, `PhraseChips.tsx:71` and the workspace slug field already do.

### A11Y-004 · P1 · The primitives' focus ring is a 2.1:1 halo
- **Problem.** The `Button`, `Input`, `Select`, `Checkbox`, `Switch`, `Tabs` and `ToggleGroup`
  primitives replace the global outline with `focus-visible:ring-3 ring-ring/50`. That is brand at
  50% alpha: 2.10:1 on panel, 2.13:1 on canvas and 1.98:1 on raised.
  - Button, Input, Select, Checkbox and Switch also add a 1 px brand border. On gradient buttons
    that border vanishes into the fill, which leaves only the faint halo.
  - Tabs and ToggleGroup triggers get no border, so their only indicator is the 2:1 halo. These
    are the segmented controls on Settings, Knowledge and the automation editor.
  - Clerk's account button shows focus as a 0.88 px brand shadow at 22% alpha.
- **Evidence.**
  - Sources: `button.tsx:7`, `tabs.tsx:27`, `toggle-group.tsx:37`, `input.tsx:10`,
    `select.tsx:45`, `checkbox.tsx:16`, `switch.tsx:19`.
  - The runtime tab log records "Open user menu" with `outline: none` and
    `box-shadow: rgba(86,127,248,0.22) 0 0 0 0.88px`.
  - In a screenshot of the suggestion bar's focused Send, the ring is barely distinguishable.
- **Affected.** All primitives, and `lib/clerk-appearance.ts`.
- **Recommendation.**
  - Standardise one indicator:
    `focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand`, the
    global rule (4.54:1 on panel). Or use
    `focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 ring-offset-<surface>`.
  - Remove `outline-none` from the primitives.
  - For Clerk, add `appearance.elements.userButtonTrigger` focus styles.

### A11Y-005 · P1 · Text that fails 4.5:1 (WCAG 1.4.3, UX-TOK-02)
- **Problem and evidence.** These are the failing rows of the contrast table. axe confirmed the
  first, second and fifth at runtime.
  1. Active platform segment: white on `#567FF8` at 12 px, **3.63:1** (`PlatformStrip.tsx:54`).
     This is the exact v1 failure UX-TOK-02 fixed for bubbles.
  2. "Instagram" in the thread identity line: `#BE185D` on panel, **2.73:1**
     (`ThreadHeader.tsx:26`, `:100`).
  3. Sidebar group labels "ENGAGE" and "GROW": 11 px, **3.64:1** (`AppSidebar.tsx:257`).
  4. Placeholders: `fg-disabled`, **3.41–2.97:1** (`globals.css:128`). This affects the composer
     ("Reply to …"), the inbox search and the template, emoji and hashtag fields. The spec assigns
     `fg-disabled` to placeholders, so this is a spec conflict too.
  5. Billing "Coming soon" badge and the Max card under `opacity-80`: **3.48:1 and 4.27:1**
     (`PlanCards.tsx:73`, `:84`). Neutral badges are **4.47:1** (`BillingPage.tsx:64`).
  6. Destructive `Button` text, **3.51:1** (`button.tsx:19`, used for "Cancel subscription" at
     `BillingPage.tsx:315`). Destructive menu items, **4.38:1** (`dropdown-menu.tsx:75`, Delete at
     `post-parts.tsx:227`).
  7. "Template · name" label in outgoing bubbles, **3.46:1** (`MessageBubble.tsx:103`, `:142`).
     "Unsupported message format", **4.26:1** (`MessageBubble.tsx:165`).
  8. The marketing skip link: white on brand, **3.63:1** (`(marketing)/layout.tsx:25`).
- **Recommendation.**
  - Active segment: `bg-brand-gradient`, or a solid `#3B5BD9` (5.70:1).
  - Platform names: `text-fg-secondary` with a coloured dot, or a lighter pink such as `#F472B6`.
  - Group labels: plain `text-fg-secondary`.
  - Placeholders: `fg-secondary`. Record the change in `docs/CONFLICTS.md`.
  - Dim the unavailable plan card's border and background instead of its text.
  - Destructive text: `danger-fg`.
  - Bubble labels: `text-white`.

### A11Y-006 · P1 · Control boundaries are close to invisible (WCAG 1.4.11, UX-A11Y-01)
- **Problem.** Inputs, selects, outline buttons and unchecked checkboxes draw their edge with
  `border-input` (white/10): 1.34:1 on panel and 1.21:1 on canvas. Their fill (`dark:bg-input/30`,
  about 3% white) adds nothing. An unchecked checkbox is a 16 px square at 1.34:1. An unchecked
  switch's track is white 8%, 1.27:1. In the Automations screenshot at 375 px, the "Active"
  switch shows as a lone white dot.
- **Evidence.** `input.tsx:10`, `select.tsx:45`, `checkbox.tsx:16`, `switch.tsx:19`,
  `button.tsx:13` (outline variant), and raw fields with `border-line`. See the non-text table.
- **Recommendation.**
  - Add `--color-line-control: #71717A` (3.41:1 or better on every surface) and use it for
    `--input`, so that `border-input` becomes visible.
  - For the unchecked switch track, use `bg-[#52525B]` with a `#71717A` border, or that token.
  - Keep `line` for decorative dividers.

### A11Y-007 · P1 · Focus is lost when conditionally-mounted dialogs close (UX-A11Y-02, WCAG 2.4.3)
- **Problem.** Some dialogs are rendered as `{open ? <Dialog open …/> : null}`. Closing one
  unmounts it, and Radix can't hand focus back, so it falls to `<body>`. The next Tab then starts
  at the top of the page.
- **Evidence.**
  - At runtime: Automations → New automation → Esc, and focus ended on `BODY`.
  - Same pattern in:
    - `AutomationsPage.tsx:398-409` (TemplateGallery);
    - `AgentDraftDialog.tsx:72`;
    - `ScheduledList.tsx:209`;
    - `schedule/ListView.tsx:305`.
  - The pattern is handled correctly in `MoveToDialog.tsx:70-74` and the Ask panel
    (`useReturnFocus`).
- **Recommendation.** Keep the `Dialog` mounted and drive `open`, or reuse
  `components/agent/use-return-focus.ts` for these four. This also restores their exit animation
  (MOT-003).

### A11Y-008 · P1 · Focused controls hidden under sticky bars (WCAG 2.4.11, AA)
- **Problem.** No page sets `scroll-padding`. The settings save bar, the post composer's action
  bar and the 56 px mobile top bar are sticky, so the browser scrolls a focused control into view
  underneath them.
- **Evidence.**
  - Settings › AI at 375 × 700 px: tabbing reached "Upgrade for Auto" at y = 628 px, entirely
    covered by the save bar (`SaveBar.tsx:69`, `sticky bottom-0`), on 3 Tab presses.
  - The same risk applies to `MobileNav.tsx:24` (`sticky top-0 h-14`) when tabbing backwards,
    and to the post composer's sticky action bar (`PostComposer.tsx:703`).
- **Recommendation.**
  - Set `html { scroll-padding-top: 4rem }` below 768 px.
  - Set `scroll-padding-bottom` on pages with a bottom bar. A class on the page wrapper works, or
    `scroll-margin-bottom` on form controls.
  - On phones, hide the save bar while it is clean ("All changes saved").

### A11Y-009 · P1 · Touch targets under 40 px on phones (UX-A11Y-05, C-018)
- **Problem.** See the touch-target table. The Button primitive has no phone size. Inbox chips,
  tabs and segments are 24–28 px tall. C-018 ruled that the composer's Send is 40 px on phones;
  it is 36 px (`Composer.tsx:412`, `h-9 md:h-8`). The analysis pencil is 24 × 24 px
  (`AnalysisChips.tsx:108`).
- **Evidence.** The 375 px measurements above, and `button.tsx:22-33`.
- **Recommendation.**
  - Add `pointer-coarse:min-h-10` to the Button size variants, and `pointer-coarse:min-w-10` to
    the icon sizes.
  - Give chips, tabs and segment items `pointer-coarse:py-2.5`, as `sidebar-styles.ts` does.
  - Make Send `h-10 md:h-8`.
  - Desktop density stays as it is.

### A11Y-010 · P1 · Reduced motion is not honoured by any Radix primitive
- **Problem.** The sheet (mobile drawer, inbox details, knowledge and posting-times sheets),
  dialog, alert dialog, popover, dropdown, select and tooltip still animate under
  `prefers-reduced-motion: reduce`. The spec says these become instant.
- **Evidence.** Measured with emulated reduce: drawer `enter 0.2s` (overlay `enter 0.1s`);
  popover, dropdown and dialog `enter 0.1s`. `tw-animate-css` has no reduced-motion rule. Full
  detail is in `MOTION.md` (MOT-001).
- **Recommendation.** Add `motion-reduce:animate-none` (and `motion-reduce:transition-none` on
  the sheet) in the primitives, as `AskPanel.tsx:82` and `:91` already do. WCAG 2.3.3 is AAA, so
  this is a spec rule and P1, not a P0.

### A11Y-011 · P2 · Field errors aren't linked to their inputs (WCAG 1.3.1, 3.3.1)
- **Problem.** These forms set `aria-invalid` and show the error as a `role="alert"` paragraph,
  but no `aria-describedby` links it. The message is announced once when it appears; returning to
  the field later reads only "invalid entry".
- **Evidence.**
  - `knowledge/SourceSheet.tsx:267-297` and its `Field` at `:397-420`.
  - `settings/workspace/page.tsx:178`, `:312` and `Field` at `:421-449` (only the slug uses
    `aria-describedby`).
  - `BrandVoiceCard.tsx:156`, `inbox/ScheduleFields.tsx:87`, `:102`, `schedule/ListView.tsx:320`
    and the activation errors in `AutomationEditor.tsx`.
- **Recommendation.** One shared `Field` (label, hint and error, with generated ids) that passes
  `aria-describedby="{id}-hint {id}-error"` to its control. `DeleteWorkspace.tsx:132-150` already
  has the shape.

### A11Y-012 · P2 · `aria-label` on elements with no role, so state is silent (UX-A11Y-04)
- **Problem.** ARIA prohibits naming a generic element, so screen readers ignore these labels:
  - the unread dot in the notifications popover (`NotificationsButton.tsx:122`, a
    `<span aria-label="unread">`), so unread notifications are not announced, against
    UX-A11Y-04;
  - message reactions (`MessageBubble.tsx:200-205`);
  - loading containers (`PageSkeleton.tsx:7-10`, flagged by axe as `aria-prohibited-attr` at
    375 px; `ConversationList.tsx:122`; `KnowledgePage.tsx:23`; `PlatformStrip.tsx:30`);
  - the schedule popover body (`Composer.tsx:493`).
- **Recommendation.**
  - Unread dot and reactions: `role="img"` (as `ConversationRow.tsx:257` does), or `sr-only` text.
  - Skeletons: `role="status"` with `sr-only` text "Loading …".

### A11Y-013 · P2 · Page titles: six screens are just "Social Hood" (WCAG 2.4.2)
- **Problem.** The client pages export no metadata, and their layouts don't either, so they fall
  back to the root default "Social Hood". This hits Home, a conversation, a post's comments, the
  automation editor, Settings › Connections and Settings › Workspace. A tab or history list can't
  tell them apart.
- **Evidence.**
  - `app/(app)/w/[slug]/home/page.tsx`, `inbox/[id]/page.tsx`, `comments/[postId]/page.tsx`,
    `automations/[id]/page.tsx`, `settings/connections/page.tsx` and
    `settings/workspace/page.tsx` are all `"use client"` with no metadata.
  - Their siblings do have one, for example `inbox/page.tsx:6`.
- **Recommendation.**
  - Move `export const metadata` into a server `page.tsx` that renders the client component.
  - For the dynamic pages, set `document.title` with the contact's or automation's name from the
    client.

### A11Y-014 · P2 · Toast actions disappear after 4 s (WCAG 2.2.1)
- **Problem.** "Undo" on archive, "Try again" on a failed connect, and "Open" or "Finish setup"
  on automations and posts all use sonner's default 4 s. Sonner pauses on hover and focus, and
  Alt+T reaches the region, but a keyboard or screen-reader user has to get there in time.
- **Evidence.** `InboxShell.tsx:187-189`, `settings/connections/page.tsx:300`,
  `AutomationsPage.tsx:194`, `:204`, `SchedulePage.tsx:300`, `SuggestionSlot.tsx:177`.
- **Recommendation.** Give action toasts `duration: 10_000` or longer (or `Infinity` with a close
  button). Archived conversations can already be restored from the Archived view; mention it.

### A11Y-015 · P2 · Two semantic patterns are incomplete
- **Problem.**
  - Chats | Scheduled is `role="tablist"` and `role="tab"` with no `tabpanel`, no
    `aria-controls` and no arrow-key roving. Both tabs are in the Tab order.
  - The automation editor has no `<h1>`: its name is an input (axe `page-has-heading-one` at 375
    and 1280 px).
  - On phones a conversation page has no `<h1>`, because the list's "Inbox" heading is not
    rendered.
- **Evidence.** `inbox/ListHeader.tsx:93-116`, `AutomationEditor.tsx`, `InboxShell.tsx:254`.
- **Recommendation.**
  - Either complete the tabs pattern (Radix `Tabs` is already wrapped in `ui/tabs.tsx`) or use
    `aria-pressed` buttons like the platform control.
  - Add an `sr-only` `<h1>` with the automation's name, and the contact's name as the phone
    thread's `h1`.

### A11Y-016 · P2 · The message log announces more than new inbound messages (UX-A11Y-03); needs a screen reader to confirm
- **Problem.** The whole scroller is `aria-live="polite" aria-relevant="additions"`. Older pages
  loading above, virtualised rows mounting while scrolling, and our own outbound sends are all DOM
  additions, so a screen reader may read history aloud while the user scrolls up. UX-A11Y-03 asks
  for new inbound messages only.
- **Evidence.** `MessageLog.tsx:152-160`. The runtime inspection shows the live region wrapping
  the entire thread.
- **Recommendation.**
  - Keep `role="log"` but set `aria-live="off"` on the scroller.
  - Announce live inbound messages through a separate `sr-only` polite region ("Message from
    Priya: …"), as `ConversationList.tsx:92` does for the list.
  - Verify with NVDA and VoiceOver.

### A11Y-017 · P2 · An empty week grid can't be scrolled by keyboard
- **Problem.** When a week has no posts, the calendar's scroll container has no focusable
  content, so a keyboard user can't scroll the hours. Chrome 130 and later make such scrollers
  focusable, but other browsers don't.
- **Evidence.** axe `scrollable-region-focusable` on Schedule at 1280 px; `WeekView.tsx:131`.
- **Recommendation.** Give the scroller `tabIndex={0}` and `aria-label="Week, 28 Sep to 4 Oct"`,
  plus a focus ring.

### A11Y-018 · P2 · Language of parts for customer messages (WCAG 3.1.2)
- **Problem.** The workspace serves Hindi and Hinglish customers (C-063: the reply language,
  Polish "in the draft's own language and script"). Bubbles carry no `lang`, so Devanagari text is
  read by an English voice.
- **Evidence.** `MessageBubble.tsx:181`: `<p>{message.text}</p>` with no `lang`.
- **Recommendation.** When the analysis or the reply language knows a message's language, set
  `lang` on the bubble's text element. This needs no API change where the language is already
  stored.

### A11Y-019 · P2 · The drawer and dialog scrim barely dims
- **Problem.** The primitives' overlay is `bg-black/10` with a light blur. The page behind a
  dialog stays at near-full contrast, which makes modal context harder to perceive for low-vision
  users. Spec UX-SH-02 says the drawer sits over `bg-black/60`. See RSP-008.
- **Evidence.** `dialog.tsx:42`, `sheet.tsx:40`, `alert-dialog.tsx:39`. The runtime drawer
  overlay is `oklab(0 0 0 / 0.1)`.
- **Recommendation.** Use `bg-black/60` in all three, as the Ask panel does
  (`AskPanel.tsx:82`).

### A11Y-020 · P3 · Landmarks: an unlabelled `<aside>` around the main navigation
- **Problem.** The shell wraps the `<nav aria-label="Main">` in an unlabelled `<aside>`. That
  makes a complementary landmark that contains only navigation. Knowledge adds a second unlabelled
  `<aside>`, flagged by axe as `landmark-unique` at 1280 px.
- **Evidence.** `AppShell.tsx:97`, `KnowledgePage.tsx:99`.
- **Recommendation.** Change the shell's wrapper to a `<div>`. Label Knowledge's
  ("Test your knowledge").

### A11Y-021 · P3 · FAQ headings inside `<summary>`
- **Problem.** `<summary>` has an implicit button role whose children are presentational in some
  screen readers, so the `<h3>`s may not be exposed as headings.
- **Evidence.** `marketing/Faq.tsx:20-21`.
- **Recommendation.** Put the heading outside, or accept it and drop the `h3`.

### A11Y-022 · P3 · Generic alt text for customer photos
- **Problem.** Every inbound image is "Photo". The lightbox title is "Photo" too.
- **Evidence.** `AttachmentView.tsx:48`, `:51`, `:55-56`.
- **Recommendation.** Use "Photo from {name}, {time}", and "Open photo from {name}" on the
  button.

### A11Y-023 · P3 · Sidebar focus outline animates in from grey
- **Problem.** `motion-safe:transition-colors` on sidebar rows includes `outline-color` in
  Tailwind 4. For the first 150 ms after Tab, the ring is grey (`rgb(143,151,175)` was captured)
  before it turns brand.
- **Evidence.** `sidebar-styles.ts:11` and the runtime tab log.
- **Recommendation.** Use `transition-[color,background-color]`.

### A11Y-024 · P3 · Horizontally scrolling rows hide options with no cue
- **Problem.** The inbox view chips hide "Leads", "AI handled" and "More" off-screen at 375 and
  1280 px, with the scrollbar hidden. The settings tabs cut off at "Workspac…" at 375 px.
  Keyboard focus does scroll them into view.
- **Evidence.** `ListHeader.tsx:161`, `settings/layout.tsx:22`.
- **Recommendation.** Add an edge fade mask, as the sidebar does (`AppSidebar.tsx:113`).
