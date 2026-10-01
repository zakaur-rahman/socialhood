# UI audit: typography (brief §6)

Read-only audit of `apps/web` at `99f67be` (branch `feature/ui-audit`). No code was changed.
Companion document: [SPACING.md](SPACING.md) covers spacing, radius, borders and shadows.

**Priorities:** P0 broken or inaccessible · P1 major inconsistency · P2 polish · P3 minor.

## Summary

The type system works, but the code keeps no single list of sizes. One family (Geist) is loaded
correctly through `next/font`, and three weights (400, 500 and 600) cover almost everything.
The trouble is at the small end and in how roles are applied:

- **16 font sizes are in use** (9, 10, 11, 12, 12.8, 13, 14, 15, 16, 18, 20, 24, 30, 36, 48 and
  60 px). Six of them are arbitrary values with no paired line height.
- **The app's text leans small.** In the app (marketing and `/dev` excluded), `text-xs` (12 px) is
  used more often than `text-sm` (14 px), at 353 against 322. About 53% of sized text is 12 px or
  smaller.
- **11 px is the most important size that has no token.** It appears 86 times in 47 files as
  `text-[11px]`, for chips, eyebrow labels and captions.
- **The same role gets different sizes in different features.** Page titles are 24 or 30 px,
  card titles 14, 16 or 18 px, dialog titles 16, 18 or 20 px, form labels 12 or 14 px, table headers
  in three styles, and chips 10, 11 or 12 px.
- **Most text-entry fields will zoom on iPhone.** They use 14 px or 15 px text. The `Input`
  primitive already avoids this, but the inbox reply box, the search box and the `Textarea`
  primitive do not.

No P0 issues were found in typography.

| ID | P | Finding |
|---|---|---|
| [TYP-001](#typ-001) | P1 | 29 text-entry fields use text under 16 px on phones, so iOS zooms on focus (the inbox composer is one) |
| [TYP-002](#typ-002) | P1 | 11 px has no token: 95 arbitrary sizes of 11 px or less, which inherit their line height, and 9–10 px text exists |
| [TYP-003](#typ-003) | P1 | Page and pane titles disagree: 24 px, 30 px (settings), 18 px (Inbox) and 16 px (Ask) |
| [TYP-004](#typ-004) | P2 | The card and section title hierarchy changes by feature (14, 16 or 18 px titles; 12 or 14 px descriptions) |
| [TYP-005](#typ-005) | P2 | Dialog and sheet titles come in four styles; the primitive uses `leading-none`, which crushes titles that wrap |
| [TYP-006](#typ-006) | P2 | The eyebrow (micro label) is defined five times with three trackings |
| [TYP-007](#typ-007) | P2 | Chips and badges use 10, 11 and 12 px; the `Badge` primitive has no importers; `CHIP` is duplicated |
| [TYP-008](#typ-008) | P2 | Button text is 11–15 px; `Button size="sm"` uses an off-scale `text-[0.8rem]` (12.8 px) in 65 places |
| [TYP-009](#typ-009) | P2 | Form labels are 14 px in some forms and 12 px in others; three copies of the same `Field` helper |
| [TYP-010](#typ-010) | P2 | Table headers come in three styles (12 px sentence case, 11 px uppercase, 13 px) |
| [TYP-011](#typ-011) | P2 | Only the `latin` subset is loaded: ₹ (U+20B9) falls outside it, and so do latin-ext customer names |
| [TYP-012](#typ-012) | P3 | The 15 px reading size (Ask, legal) is unofficial, and Ask's 28 px line height is loose |
| [TYP-013](#typ-013) | P3 | Weight 700 leaks in through `<strong>` (33 places) and one `font-bold` at 9 px |
| [TYP-014](#typ-014) | P3 | The app has no default body size: `<body>` is 16 px, while the spec's body is `text-sm` |
| [TYP-015](#typ-015) | P3 | The spec's type-role table and `tokens.ts` `typeRoles` are documentation only, and both have drifted |

## How this was counted

- **Scope:** `apps/web/src/**/*.{ts,tsx}`, excluding `*.test.*`, `*.spec.*` and `src/test/`. That
  is 336 source files (232 `.tsx`). The 119 test files are counted separately below.
- **Method:** small Python scripts, not committed, in three steps:
  1. **Extract.** They strip comments, pull every string literal (`"…"`, `'…'`, `` `…` ``, which
     covers `className`, `cn()`, `cva()` and class constants), split it into tokens and remove
     variant prefixes (`md:` and `data-[state=on]:`), keeping the variant for state analysis.
  2. **Classify.** Each utility is sorted with regexes into size, weight, leading, tracking and so
     on.
  3. **Map roles.** A second pass parses JSX opening tags (`<h1>`, `<Button size="sm">`,
     `<DialogTitle>` …) and their `className`, which ties sizes to elements.
- **What a count means:** occurrences in source, not rendered instances. A class inside a shared
  component counts once.
- **Tests matter here.** 20 `toHaveClass` assertions in 8 test files pin classes from this area,
  so a migration must update them:
  - `components/agent/AskPanel.test.tsx` (8), including `text-[15px] leading-7` at line 212
  - `components/inbox/MessageBubble.test.tsx` (4), including `text-5xl` at line 46
  - `components/comments/PostDetailPage.test.tsx` (3)
  - one each in `ActionCardView`, `StepCard`, `CommentsPage`, `ConversationRow` and
    `ThreadHeader`
- **Prior decisions read:**
  - `docs/BUILD_SPEC.html`: §4.1 ("one type family") and §4.2 (UX-TOK-01/02 and "Type, space,
    radius, motion").
  - `docs/CONFLICTS.md` C-002, C-048, C-051, C-063, C-065 and C-066.
  - The owner's mockups in `design/*/code.html`. The settings mockups define a scale:
    `badge-caps` 11/14, `label-md` 12/16, `body-sm` 13/18, `body-md` 14/20, `body-lg` 15/22,
    `headline-md` 18/26, `headline-lg` 24/32 and `headline-xl` 32/40. The Home mockup uses plain
    Tailwind sizes with a 24 px bold `h1`.

## 1. Fonts

| | Primary (sans) | Mono |
|---|---|---|
| Family | Geist (variable, weights 100–900) | Geist Mono (variable) |
| Loaded by | `next/font/google` in `app/layout.tsx:3,10` | `app/layout.tsx:3,11` |
| CSS variable | `--font-geist-sans` on `<html>` (`layout.tsx:24`) | `--font-geist-mono` |
| Tailwind token | `--font-sans: var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif` (`globals.css:10`) | `--font-mono: var(--font-geist-mono), ui-monospace, monospace` (`globals.css:11`) |
| Applied | `<body className="… font-sans antialiased">` (`layout.tsx:25`) | `font-mono`: 7 uses (RunTrace ×3, data-deletion ×2, `/dev/tokens` ×2) |
| Subsets | `["latin"]` only | `["latin"]` only |
| `display` | not set (`next/font` defaults to `swap`) | same |
| Fallbacks | `next/font` adds a metric-matched local fallback inside the variable, then `ui-sans-serif → system-ui → sans-serif` | `ui-monospace → monospace` |

Notes:

- **There is no secondary display face.** That matches §4.1 ("one type family").
- **The mockups' `label-code` font is JetBrains Mono.** In the settings screenshots it falls back
  to a serif (for example "v2.4.0" and "18 / 48"). Neither face was adopted, which is correct.
- **Clerk repeats the stack as a literal** (`lib/clerk-appearance.ts:26`), because Clerk cannot
  read CSS variables. That is fine, but it is a second copy to keep in sync.
- **The OG image uses `fontFamily: "sans-serif"`** (`components/marketing/og.tsx:34`), the
  renderer's default face, so the social card is not set in Geist (P3, marketing only).
- **The keyboard hint opts out of mono** with `font-sans` (`shell/sidebar-styles.ts:25`). That
  is deliberate and fine.
- **Weights:** the variable font ships every weight, and the code uses 400, 500 and 600. 700
  appears only through `<strong>` (TYP-013).

## 2. Sizes in use

### 2.1 Totals

The table covers 957 size utilities in 174 files. "Line height" is Tailwind v4's paired default,
and arbitrary sizes have none.

| Utility | px | Line height | Uses | Files | Share |
|---|---:|---|---:|---:|---:|
| `text-[9px]` | 9 | none (inherits) | 1 | 1 | 0.1% |
| `text-[10px]` | 10 | none (inherits) | 8 | 8 | 0.8% |
| `text-[11px]` | 11 | none (inherits) | **86** | **47** | 9.0% |
| `text-xs` | 12 | 16 px | **379** | 119 | 39.6% |
| `text-[0.8rem]` | 12.8 | none (inherits) | 1 (Button `sm`, rendered 65×) | 1 | 0.1% |
| `text-[13px]` | 13 | none (inherits) | 2 | 2 | 0.2% |
| `text-sm` | 14 | 20 px | **374** | 147 | 39.1% |
| `text-[15px]` | 15 | none (inherits) | 7 | 6 | 0.7% |
| `text-base` | 16 | 24 px | 40 | 38 | 4.2% |
| `text-lg` | 18 | 28 px | 13 | 10 | 1.4% |
| `text-xl` | 20 | 28 px | 11 | 9 | 1.1% |
| `text-2xl` | 24 | 32 px | 15 | 13 | 1.6% |
| `text-3xl` | 30 | 36 px | 8 | 6 | 0.8% |
| `text-4xl` | 36 | 40 px | 9 | 6 | 0.9% |
| `text-5xl` | 48 | 1 | 2 | 2 | 0.2% |
| `text-6xl` | 60 | 1 | 1 | 1 | 0.1% |

App against marketing:

- **App:** `text-xs` 353, `text-sm` 322, `text-[11px]` 78, `text-base` 29, `text-lg` 9, `text-xl`
  9, `text-2xl` 9, `text-[10px]` 7, `text-[15px]` 4, `text-[13px]` 2, `text-3xl` 2, `text-5xl` 1
  (the heart sticker), `text-[9px]` 1 and `text-[0.8rem]` 1.
- **Marketing and `/dev`:** `text-sm` 52, `text-xs` 26, `text-base` 11, `text-4xl` 9,
  `text-[11px]` 8, and 2xl, 3xl, lg, 15 px, xl, 5xl, 6xl and 10 px a few times each.
- **Responsive type** is almost absent in the app. The only cases are `md:text-sm` (Input),
  `md:text-3xl` (the settings `h1`) and marketing's `sm:`/`lg:` headings. That is fine for a
  dense app.

### 2.2 By area

Counts of each size by area:

| Area | 9 | 10 | 11 | 12 | 12.8 | 13 | 14 | 15 | 16 | 18 | 20 | 24 | 30 | 36 | 48 | 60 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| components/automations | | 1 | 15 | 64 | | | 48 | | | | 4 | 1 | | | | | 133 |
| components/marketing | | 1 | 5 | 22 | | | 33 | 2 | 11 | 4 | 1 | 1 | 3 | 6 | 1 | 1 | 91 |
| components/composer | | | 10 | 35 | | | 37 | | | 1 | 3 | 1 | | | | | 87 |
| components/schedule | | 1 | 13 | 40 | | | 26 | | 3 | | | 1 | | | | | 84 |
| components/inbox | | 2 | 9 | 43 | | | 24 | | 1 | 3 | | | | | 1 | | 83 |
| components/agent | | | 12 | 30 | | 1 | 24 | 4 | 3 | 1 | 1 | | | | | | 76 |
| components/comments | | | 4 | 33 | | | 20 | | 1 | 1 | | | | | | | 59 |
| components/home | | | 3 | 18 | | | 19 | | 5 | | | 2 | | | | | 47 |
| components/ai | | | 6 | 20 | | | 18 | | | | | | | | | | 44 |
| components/knowledge | | | 1 | 20 | | | 17 | | 5 | | | | | | | | 43 |
| components/billing | | | 2 | 14 | | | 16 | | 1 | 3 | | 1 | 1 | | | | 38 |
| components/ui | | | | 7 | 1 | | 22 | | 4 | | | | | | | | 34 |
| app/(marketing) | | | | | | | 16 | 1 | | | 1 | 4 | 3 | 3 | | | 28 |
| components/shell | 1 | 3 | 1 | 11 | | 1 | 7 | | 1 | | | 1 | | | | | 26 |
| app/(app) | | | | 6 | | | 12 | | | | | | | | | | 18 |
| components/push | | | | 3 | | | 15 | | | | | | | | | | 18 |
| components/settings | | | 1 | 3 | | | 7 | | 1 | | | 1 | 1 | | | | 14 |
| app/(dev) | | | 3 | 4 | | | 3 | | | | | 1 | | | | | 11 |
| components/connections | | | | 4 | | | 5 | | | | | | | | | | 9 |
| styles (tokens.ts) | | | 1 | 1 | | | 1 | | 1 | | 1 | 1 | | | | | 6 |
| components/states | | | | | | | 2 | | 2 | | | | | | | | 4 |
| components/workspace | | | | 1 | | | 2 | | | | | | | | | | 3 |
| app/(auth) | | | | | | | | | 1 | | | | | | | | 1 |

### 2.3 Every arbitrary size

| Size | Where | Role |
|---|---|---|
| `text-[9px]` | `shell/AppSidebar.tsx:225` | "AI" tag on the Ask tile (inside `aria-hidden`), `font-bold` |
| `text-[10px]` | `shell/AppSidebar.tsx:309` | collapsed-sidebar count badge |
| | `inbox/ListHeader.tsx:109` | Scheduled count badge |
| | `shell/WorkspaceMenu.tsx:28` | plan badge |
| | `shell/sidebar-styles.ts:25` | `KBD_CLASS` shortcut hint |
| | `inbox/AttachmentTray.tsx:69` | file name under a thumbnail |
| | `schedule/post-parts.tsx:97` | avatar initial (small avatar) |
| | `automations/steps/PostsStep.tsx:270` | thumbnail caption |
| | `marketing/InboxPreview.tsx:70` | "Live" tag |
| `text-[11px]` | 86 uses, 47 files | 35 chips or badges, 28 uppercase eyebrows, 20 captions or meta, 3 labels |
| `text-[0.8rem]` | `ui/button.tsx:26` | every `Button size="sm"` (65 call sites) |
| `text-[13px]` | `shell/AppSidebar.tsx:231` | "Ask Social Hood" tile title |
| | `agent/AnswerText.tsx:124` | tables in Ask answers |
| `text-[15px]` | `agent/AnswerText.tsx:51` | Ask answer body |
| | `agent/RunView.tsx:62` | Ask answer body |
| | `agent/AskComposer.tsx:101` | Ask input |
| | `agent/AskPanel.tsx:150` | Ask panel |
| | `marketing/legal/LegalPage.tsx:11,71` | legal prose |
| | `app/(marketing)/data-deletion/page.tsx:54` | data-deletion page prose |

## 3. Roles: what each role uses today

Spec §4.2 defines seven roles:

| Spec role | Classes |
|---|---|
| Page title | `text-2xl font-semibold tracking-tight` |
| Pane title | `text-xl font-semibold` |
| Section title | `text-base font-semibold` |
| Body | `text-sm` |
| Meta | `text-xs text-fg-secondary` |
| Micro label | `text-[11px] uppercase tracking-[0.08em] font-semibold` |
| Numbers | `tabular-nums` |

The table below maps what the code does for each brief role. Where a role uses different sizes,
the spec-conforming value is in bold.

| Role | Sizes and weights in use (count) | Where they differ |
|---|---|---|
| **Display** (marketing hero) | `text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight leading-[1.08]` (1) | — |
| **Marketing H2** | `text-3xl sm:text-4xl font-semibold tracking-tight` (5) | consistent |
| **H1, page title** | **`text-2xl semibold tight`** (PageFrame, Home, Schedule, Composer, unsubscribe, `/dev/tokens`; 9 `h1`s) | Settings `text-2xl md:text-3xl` (`SettingsPageHeader.tsx:55`); legal and data-deletion `text-3xl sm:text-4xl` (3) |
| **H1, pane title** | Inbox `text-lg` (`ListHeader.tsx:92`; spec says `text-xl`); Ask `text-base` (`AskPage.tsx:49`); mobile top bar `text-base` (`MobileNav.tsx:26`) | three sizes for one role |
| **H2, section within a page** | `text-lg semibold tight` ("Compare plans", `BillingPage.tsx:176`); `text-2xl` (plan name, `BillingPage.tsx:280`); `text-xl` (Ask empty state, `AskConversation.tsx:299`) | — |
| **H2/H3, card title** | **`text-base semibold`** (11 app `h2`s: Home, Knowledge, Comments, SettingsCard); `text-sm semibold` (Composer `Section`, `PostChecklist`, `PostPreview`, automations `AccountGroup`, `TemplateGallery`, `KnowledgeGapBanner`, `PostPerformanceCard`); `text-lg semibold` (`PlanCards.tsx:80`) | 14, 16 and 18 px |
| **Card description** | `text-xs` (6 cards in Home and Knowledge); `text-sm` (SettingsCard, Home's TopIntentsCard, Billing, marketing) | 12 against 14 px under the same title size, even within Home |
| **H3/H4, sub-heading** | `text-sm semibold` (row names, template names); `h4` is never used | — |
| **Dialog title** | primitive `text-base leading-none font-medium` (7 Dialog, 14 AlertDialog); overrides `text-xl semibold` (5), `text-lg semibold` (1), `text-base semibold` (1) | see TYP-005 |
| **Sheet title** | primitive `text-base font-medium` (2); overrides `text-base semibold` (3) | — |
| **Body** | **`text-sm`** (264 elements with no weight, 121 of them `<p>`) | Ask uses 15 px; marketing body is `text-sm`/`text-base` |
| **Message bubble** | **`text-sm leading-relaxed`** (`MessageBubble.tsx:93`) | as spec |
| **Small / meta / caption** | **`text-xs`** (298 elements with no weight) and `text-[11px]` (20 captions) | 11 against 12 px for timestamps and captions |
| **Label (form)** | `Label` primitive `text-sm font-medium leading-none` (17 bare uses); `Label text-xs` (13 uses in the inbox, schedule, composer and automations) | see TYP-009 |
| **Eyebrow / micro label** | **`text-[11px] semibold uppercase tracking-[0.08em]`** (25); `tracking-[0.12em]` (3, settings and billing); marketing `text-xs tracking-[0.14em]` (5) | see TYP-006 |
| **Button** | primitive default/lg `text-sm font-medium`; `sm` `text-[0.8rem]` (12.8 px); `xs` `text-xs`; raw `<button>`: `text-xs` (12), `text-sm` (10), `text-[11px]` (3), `text-[15px]` (1), `text-lg` (emoji, 1) | see TYP-008 |
| **Input** | `Input` `text-base md:text-sm` (24); raw `<input>` `text-sm` (14); textareas `text-sm` (16 including the primitive) or `text-[15px]` (1) | see TYP-001 |
| **Table** | header: `text-xs font-medium` sentence case (`SourcesCard.tsx:140`), `text-[11px] semibold uppercase 0.08em` (`PaymentHistory.tsx:23`) or `text-[13px] font-medium` (`AnswerText.tsx:124`); body `text-sm` or 13 px | see TYP-010 |
| **Navigation** | sidebar `text-sm font-medium` (`sidebar-styles.ts:10`); settings tabs `text-sm font-medium` (`settings/layout.tsx:32`); marketing nav `text-sm` (`SiteHeader.tsx:22`) and `text-base` (mobile menu) | consistent at 14 px in the app; the sidebar redesign (C-048) uses 14 px (`sidebar-styles.ts:4–6`), but spec UX-SH-01 still says `text-[15px]` |
| **Chip / badge** | `text-xs` + `rounded-full` (37); `text-[11px]` + `rounded-full` (21); `text-[11px]` + `rounded-md` (11); `text-[10px]` (4); `Badge` primitive `text-xs` (no importers) | see TYP-007 |
| **Count badge** | sidebar `text-xs h-5` expanded, `text-[10px] h-4` collapsed (`AppSidebar.tsx:309–310`); Scheduled `text-[10px] h-4` (`ListHeader.tsx:109`) | spec: `text-xs … min-w-5 h-5` |
| **Numbers (KPI)** | **`text-2xl semibold tabular-nums`** (Home metric tiles, spec UX-SCR-01) | `tabular-nums` is used 121 times |
| **Code / mono** | `font-mono text-[11px]` (RunTrace); `<code className="text-xs">` | — |

## 4. Weights

| Weight | Uses | Files | Most often with |
|---|---:|---:|---|
| `font-medium` (500) | 223 | 112 | `text-sm` 65, `text-xs` 63, `text-[11px]` 18, no size on the line 69 |
| `font-semibold` (600) | 171 | 101 | `text-[11px]` 35 (eyebrows and chips), `text-sm` 34, `text-base` 28, `text-2xl` 15, `text-lg` 10, `text-xl` 10 |
| `font-normal` (400) | 12 | 9 | undoing a medium set by the `Label` primitive (3) or by a parent |
| `font-bold` (700) | 1 | 1 | `text-[9px]` "AI" tag, `AppSidebar.tsx:225` |
| `<strong>` / `<b>` (700) | 33 bare + 2 with `font-semibold` | 3 | legal and data-deletion pages |

Is bold overused? No. Weight follows a three-step ladder (400 body, 500 controls and emphasis,
600 titles, names and eyebrows). There are two caveats:

- **Medium is everywhere.** `font-medium` appears 223 times against 957 size utilities (about
  23%), so medium carries less meaning. It is the default for every control, chip and label,
  and also for some body lines, such as the unread preview in `ConversationRow`. That is
  acceptable, but the proposal below fixes when to use it.
- **Weight 700 appears in two places.** It shows only through `<strong>` and the 9 px tag
  (TYP-013).

## 5. Line height and letter spacing

### 5.1 Leading (60 uses in 38 files)

Most text relies on Tailwind v4's paired line heights: 12/16, 14/20, 16/24, 18/28, 20/28 and
24/32. The explicit values:

| Value | Uses | Where | Assessment |
|---|---:|---|---|
| `leading-relaxed` (1.625) | 30 | message bubbles, composer textareas, summaries, the `Textarea` primitive, marketing prose | good for multi-line message and reading text |
| `leading-5` / `leading-4` / `leading-3` | 7 / 5 / 1 | sidebar tiles, the Ask step list, chips | used to pin chip and badge heights; fine |
| `leading-[18px]` | 2 | `ConversationRow.tsx:108`, `SuggestionCard.tsx:32` | 11 px chips at 18 px tall; fine, but should be a token |
| `leading-6` / `leading-7` | 3 / 2 | Ask composer and step list; Ask answer at **15/28** (`AnswerText.tsx:51`, `RunView.tsx:62`) | 1.87 is loose for a chat column; see TYP-012 |
| `leading-none` | 5 | `ui/dialog.tsx:133` (DialogTitle), `ui/label.tsx:15` (Label), a citation pill, the heart emoji, a count badge | **inappropriate on DialogTitle and Label**: both can wrap, and a 16 px line height clips descenders and collides lines (TYP-005, TYP-009) |
| `leading-snug` / `leading-tight` / `leading-[1.08]` | 3 / 1 / 1 | automation preview, calendar card, marketing hero | fine |

**A systemic issue.** Arbitrary sizes such as `text-[11px]`, `text-[10px]`, `text-[13px]`,
`text-[15px]` and `text-[0.8rem]` set only `font-size`. Their line height is inherited, as a
factor, from whichever ancestor last set a `text-*`. So `text-[11px]` renders at about 14.7 px
inside a `text-xs` parent, about 15.7 px inside `text-sm` and 16.5 px inside `text-base` or the
page root. The 86 uses of 11 px therefore have context-dependent heights, which is why chips
needed `leading-4`, `leading-5` and `leading-[18px]` patches (TYP-002).

### 5.2 Tracking (63 uses in 42 files)

| Value | Uses | Where | Assessment |
|---|---:|---|---|
| `tracking-tight` (−0.025em) | 28 | every heading of 24 px or more, plus one `text-base` and one `text-lg` | good; nothing small is tightened |
| `tracking-[0.08em]` | 25 | uppercase 11 px eyebrows (spec value) | good |
| `tracking-[0.12em]` | 3 | `settings/styles.ts:2` (`EYEBROW`), `BillingPage.tsx:278`, `AgentSettingsPage.tsx:114` | **drift from 0.08em**: settings eyebrows are spaced 50% wider than the inbox's (TYP-006) |
| `tracking-[0.14em]` | 5 | marketing eyebrows at `text-xs` | acceptable for marketing, but a third value |
| `tracking-wider` / `tracking-widest` | 1 / 1 | `InboxPreview.tsx:70` (10 px tag); `ui/dropdown-menu.tsx:201` (shortcut) | stray |

Uppercase appears 35 times, always on 10–12 px labels with positive tracking, which is correct.
No body text is uppercase.

## 6. Proposed type scale

The proposal builds on what is already most common: `text-xs` and `text-sm` carry about 79% of
usage, and 11 px is the clear third size. It keeps the spec's roles, adds the two missing tokens
(11 px and 15 px) and gives every arbitrary size a home. Sizes are Tailwind defaults unless
marked **new**.

| Role | Token | Size / line height | Weight | Tracking | Use |
|---|---|---|---|---|---|
| Display | `text-4xl sm:text-5xl lg:text-6xl` | 36→60 / 1.08 | 600 | −0.025em | marketing hero only |
| Marketing heading | `text-3xl sm:text-4xl` | 30/36 → 36/40 | 600 | −0.025em | marketing H2, legal H1 |
| Page title (H1) | `text-2xl` | 24/32 | 600 | −0.025em | every app page, **including Settings** (drop `md:text-3xl`), Billing hero |
| KPI number | `text-2xl tabular-nums` | 24/32 | 600 | −0.025em | metric tiles, plan name |
| Pane / section title (H2) | `text-lg` | 18/28 | 600 | 0 | Inbox and Ask pane headers, mobile top bar, "Compare plans", large dialogs (galleries, media library) |
| Card title (H2/H3) | `text-base` | 16/24 | 600 | 0 | every card and panel heading, dialog and sheet titles |
| Sub-heading / item title (H4) | `text-sm` | 14/20 | 600 | 0 | row names, template names, step titles |
| Reading (**new** `text-md`) | `text-md` | 15/24 | 400 | 0 | Ask answers, legal prose (replaces `text-[15px]`; line height 24, not 28) |
| Body (default) | `text-sm` | 14/20 | 400 | 0 | default UI text; set on the app shell (TYP-014) |
| Message | `text-sm leading-relaxed` | 14/22.75 | 400 | 0 | bubbles and composers (as spec) |
| Control text | `text-sm` | 14/20 | 500 | 0 | buttons (sm and up), nav items, tabs, segments, form labels, menu items |
| Input text | `text-base md:text-sm` | 16 → 14 | 400 | 0 | every text-entry field (TYP-001) |
| Meta / caption / helper / error | `text-xs` | 12/16 | 400 (500 to emphasise) | 0 | timestamps, hints, descriptions under titles, inline errors, table headers |
| Small control | `text-xs` | 12/16 | 500 | 0 | `Button size="xs"` and `"sm"` (replaces `text-[0.8rem]`), dense toolbar actions |
| Chip / badge / count (**new** `text-2xs`) | `text-2xs` | 11/16 | 500 | 0 | status chips, signal badges, count badges, plan badges, `kbd` |
| Eyebrow (**new** `text-2xs`) | `text-2xs uppercase` | 11/16 | 600 | +0.08em | section labels, table group labels, nav group labels |
| Mono | `font-mono text-xs` | 12/16 | 400 | 0 | traces, tokens, IDs |

The rules:

- **Floor.** Nothing below 11 px. Retire 9 and 10 px (TYP-002).
- **Weights.** Use 400, 500 and 600 only. 600 is for titles, names, eyebrows and KPI numbers;
  500 is for controls, chips and emphasis.
- **Tracking.** −0.025em for 24 px and up, +0.08em for uppercase eyebrows only, 0 everywhere
  else.
- **One title rule per surface.** A page has one H1 at 24 px. Inside a page, H2s are 18 px for
  page sections and 16 px for cards. A description under a title is `text-xs` in dense cards and
  `text-sm` in settings and forms; pick one per surface type and write it into
  `SettingsCard`/`PageFrame`.

The implementation sketch below is not applied. Adding to `@theme` changes UX-TOK-01's "exactly
as below" file, so it needs a CONFLICTS entry, as C-002 had:

```css
@theme {
  --text-2xs: 0.6875rem;  --text-2xs--line-height: 1rem;    /* 11/16: chips, eyebrows, counts */
  --text-md: 0.9375rem;   --text-md--line-height: 1.5rem;   /* 15/24: reading (Ask, legal) */
}
@layer base {
  strong, b { font-weight: 600; }                            /* TYP-013 */
}
```

Then make `styles/tokens.ts` `typeRoles` the single source that components import (one
`EYEBROW` and one `CHIP` constant), not a parallel copy (TYP-015).

**Migration map.** Counts are occurrences in source.

| Today | Becomes | Uses |
|---|---|---:|
| `text-[11px]` | `text-2xs` (drop the `leading-4`/`leading-5`/`leading-[18px]` patches where they only set 16–18 px) | 86 |
| `text-[10px]`, `text-[9px]` | `text-2xs` (the "AI" tag: `font-semibold`, or remove it) | 9 |
| `text-[0.8rem]` (Button `sm`) | `text-xs` | 1 (65 call sites) |
| `text-[13px]` | `text-sm` (sidebar Ask title) / `text-xs` (Ask tables) | 2 |
| `text-[15px]` + `leading-7` / `leading-relaxed` | `text-md` | 7 (update `AskPanel.test.tsx:212`) |
| `md:text-3xl` on the settings H1 | removed | 1 |
| `text-xl` / `text-lg` DialogTitle overrides | `text-lg` for large dialogs; default `text-base semibold` | 6 |
| `tracking-[0.12em]` | `tracking-[0.08em]` through the shared `EYEBROW` | 3 |

## 7. Findings

### TYP-001

**P1. 29 text-entry fields use text under 16 px on phones, so iOS zooms on focus.**

- **Problem:** iOS Safari zooms the page when a field whose font size is below 16 px gets focus.
  The viewport (`app/layout.tsx:20`) does not prevent this, and it should not, because
  preventing zoom harms accessibility. The `Input` primitive already uses
  `text-base md:text-sm` (`ui/input.tsx:10`). Everything else uses 14 or 15 px, including the
  product's core reply box. TR-FE-09 supports iPhone as an installed PWA (`app/layout.tsx:16`),
  so this happens on a device the product is built for.
- **Evidence:**
  - the `Textarea` primitive is `text-sm` (`ui/textarea.tsx:9`, 10 call sites in 5 files)
  - the inbox composer textarea (`inbox/Composer.tsx:309`)
  - Ask's composer at `text-[15px]` (`agent/AskComposer.tsx:101`)
  - the comment reply (`comments/CommentComposer.tsx:81`)
  - 14 raw `<input className="… text-sm">`, including the inbox search (`inbox/ListHeader.tsx:128`)
- **Affected:**
  - `ui/textarea.tsx`
  - `inbox/{Composer,ListHeader,EmojiPicker,TemplatePicker,ScheduledList}.tsx`
  - `agent/AskComposer.tsx`
  - `comments/CommentComposer.tsx`
  - `ai/ChipListInput.tsx`
  - `automations/{AutomationsPage,KeywordInput,steps/PostsStep}.tsx`
  - `composer/MediaLibraryDialog.tsx`
  - `schedule/{HashtagGroupsDialog,ListView,PostingTimesDrawer}.tsx`
  - `settings/PhraseChips.tsx`
  - `app/(marketing)/data-deletion/page.tsx`
- **Recommendation:** give every text-entry field the Input rule, `text-base md:text-sm`. Fix
  `Textarea` first. Then route the raw `<input>` and `<textarea>` elements through the primitives
  (SPACING.md SPC-001 makes the same point for heights).

### TYP-002

**P1. 11 px has no token: 95 arbitrary sizes of 11 px or less, which inherit their line height,
and 9–10 px text exists.**

- **Problem:** 11 px is the third most used size (86 uses, 47 files), but it is spelled
  `text-[11px]` everywhere.
  - **Inherited line height:** arbitrary sizes carry no line height, so their height depends on
    the parent (§5.1). Chips then need `leading-4`, `leading-5` or `leading-[18px]` patches, and
    the same chip changes height when it is moved.
  - **Text below 11 px:**
    - nine elements use 9–10 px: count badges, the plan badge, the `kbd` hint, a file name and
      a thumbnail caption
    - 10 px count badges are read at a glance: `ListHeader.tsx:109` has an `aria-label`, but
      it is still visible text
    - the 9 px "AI" tag is bold to stay legible
- **Evidence:** §2.3. Files: `shell/AppSidebar.tsx:225,309`, `inbox/ListHeader.tsx:109`,
  `shell/WorkspaceMenu.tsx:28`, `shell/sidebar-styles.ts:25`, `inbox/AttachmentTray.tsx:69`,
  `schedule/post-parts.tsx:97` and `automations/steps/PostsStep.tsx:270`.
- **Recommendation:** add `--text-2xs` (11/16) and replace every `text-[11px]`, `text-[10px]`
  and `text-[9px]`. Make 11 px the floor. A collapsed-sidebar badge fits 11/16 in its `h-4`.

### TYP-003

**P1. Page and pane titles disagree: 24 px, 30 px (settings), 18 px (Inbox) and 16 px (Ask).**

- **Problem:** moving between Home (24 px), Settings (30 px from `md`), Inbox (18 px) and Ask
  (16 px) changes the top-of-page anchor each time. The cause is two mockup sets:
  - the Home mockup uses a 24 px `h1`
  - the settings mockups use `headline-xl` at 32 px
  - each redesign followed its own mockup (C-065, C-066)
- **Evidence:**
  - `settings/SettingsPageHeader.tsx:55` (`text-2xl … md:text-3xl`)
  - `shell/PageFrame.tsx:32`, `home/HomeScreen.tsx:68`, `schedule/SchedulePage.tsx:390` and
    `composer/PostComposer.tsx:567` (`text-2xl`)
  - `inbox/ListHeader.tsx:92` (`text-lg`; spec UX-INB-03 says `text-xl`)
  - `agent/AskPage.tsx:49` (`text-base`)
- **Recommendation:** use 24 px for every page H1 and 18 px for every pane H1 (Inbox, Ask, mobile
  top bar). Update the spec's Pane title to `text-lg`. If the owner prefers the larger settings
  hero, make it a named "hero title" role used on every hub page, not on settings alone. That is
  an owner decision, since C-066 approved the mockup.

### TYP-004

**P2. The card and section title hierarchy changes by feature.**

- **Problem:** card titles are 16 px in Home, Knowledge, Comments and Settings, 14 px in the
  Composer and Automations, and 18 px in Billing's plan cards. The description under them is
  12 px in Home and Knowledge and 14 px in Settings and Billing. One page can mix all three title
  sizes: Billing has `text-2xl` (plan), `text-lg` ("Compare plans") and `text-base`
  (SettingsCard), plus `text-lg` plan names.
- **Evidence:**
  - 16 px titles: `home/{Checklist,PriorityQueue,SentimentCard,TopIntentsCard,TopPostsCard}.tsx`,
    `knowledge/{BrandVoiceCard,KnowledgeGapsCard,SourcesCard,TestBox}.tsx`,
    `settings/SettingsCard.tsx:66` and `comments/CommentsColumn.tsx:132`
  - 14 px titles: `composer/{Section,PostChecklist,PostPreview}.tsx`,
    `automations/{AccountGroup,TemplateGallery}.tsx` and `home/KnowledgeGapBanner.tsx:42`
  - 18 px titles: `billing/PlanCards.tsx:80`
- **Recommendation:** card title `text-base semibold` everywhere, with sub-cards or list items at
  `text-sm semibold`. Description `text-xs` in dense dashboard cards and `text-sm` in
  settings/forms, written into `SettingsCard` and a shared `Card` header.

### TYP-005

**P2. Dialog and sheet titles come in four styles, and the primitive's `leading-none` crushes
titles that wrap.**

- **Problem:**
  - **Primitive:** `DialogTitle` is `text-base leading-none font-medium` (`ui/dialog.tsx:133`)
    and `SheetTitle` is `text-base font-medium` (`ui/sheet.tsx:117`).
  - **Overrides:** 5 Dialogs use `text-xl semibold` (TemplateGallery ×2, AutomationSection ×2,
    MediaLibraryDialog), 1 uses `text-lg semibold` (CropDialog) and 1 uses
    `text-base semibold` (HashtagGroupsDialog). Sheets use `text-base semibold` 3 times.
  - **Unchanged:** 7 Dialogs and all 14 AlertDialogs keep the primitive's `font-medium`.
  - **Wrapping:** `leading-none` gives a two-line title (for example a long "Delete …?") a
    16 px line box on phones, where the dialog is `calc(100% - 2rem)` wide.
- **Recommendation:** primitive titles `text-base font-semibold` with default leading. Use one
  `size="lg"` variant (`text-lg`) for gallery-style dialogs. Remove the 7 Dialog and 3 Sheet
  overrides.

### TYP-006

**P2. The eyebrow (micro label) is defined five times with three trackings.**

- **Problem:** the uppercase section label is restated as:
  - `tokens.ts:50` (0.08em, documentation)
  - `settings/styles.ts:2` `EYEBROW` (**0.12em**)
  - `agent/Threads.tsx:25` `GROUP_LABEL` (0.08em)
  - `comments/PostPerformanceCard.tsx:32` `LABEL` (0.08em)
  - inline in about 20 files, two of which use 0.12em (`BillingPage.tsx:278`,
    `AgentSettingsPage.tsx:114`)

  Marketing uses `text-xs` with 0.14em (5). The sidebar group label adds
  `text-fg-secondary/70` (`AppSidebar.tsx:257`), which is about 3.6:1 on the panel, so 11 px
  text falls below 4.5:1. Flag this to the colour audit.
- **Recommendation:** one `EYEBROW` (`text-2xs font-semibold uppercase tracking-[0.08em]`)
  exported from `styles/`, used everywhere in the app. Keep a separate marketing eyebrow only if
  the owner wants one.

### TYP-007

**P2. Chips and badges use 10, 11 and 12 px; the `Badge` primitive has no importers; `CHIP` is
duplicated.**

- **Problem:**
  - **Sizes:** chips use `text-xs` + `rounded-full` (37), `text-[11px]` + `rounded-full` (21),
    `text-[11px]` + `rounded-md` (11) and `text-[10px]` (4).
  - **Primitive:** `ui/badge.tsx` (12 px, `h-5`) has no importers, so every chip is hand-rolled.
  - **Duplicated constant:** the same `CHIP` string is defined in `ai/AnalysisChips.tsx:26` and
    `comments/CommentRow.tsx:34`.
  - **Inbox:** filter chips are 12 px (`ListHeader.tsx:36`) while the signal badges in the same
    list are 11 px (`ConversationRow.tsx:108`).
  - **Count badges:** 12 px expanded and 10 px collapsed (`AppSidebar.tsx:309–310`).
- **Recommendation:**
  - status, signal, intent and count badges: `text-2xs font-medium` (11/16)
  - interactive filter chips: `text-xs` (they are controls)
  - rebuild `Badge` around these values and replace the inline copies
  - see SPACING.md RAD-004 for the radius

### TYP-008

**P2. Button text is 11–15 px, and `Button size="sm"` uses an off-scale 12.8 px.**

- **Problem:** `ui/button.tsx:26` gives `sm` `text-[0.8rem]` (12.8 px, a shadcn default). It
  sits between `xs` (12) and `default` (14) and is used by 65 buttons. Raw `<button>`s add
  12 px (12), 14 px (10), 11 px (3: `MediaTray.tsx:224`, `cell-extras.tsx:49,113`) and 15 px
  (`AskPanel.tsx:144`).
- **Recommendation:** sm and xs `text-xs`; default and lg `text-sm`. Raw buttons that are really
  chips or links should use those roles.

### TYP-009

**P2. Form labels are 14 px in some forms and 12 px in others; three copies of the same `Field`
helper.**

- **Problem:** the `Label` primitive is `text-sm font-medium leading-none` (`ui/label.tsx:15`).
  It is used bare in settings, automations, knowledge and connections, but overridden to
  `text-xs` 13 times in `inbox/ScheduleFields.tsx`, `inbox/ScheduledList.tsx`,
  `inbox/TemplatePicker.tsx`, `schedule/{HashtagGroupsDialog,ListView}.tsx`,
  `composer/MediaLibraryDialog.tsx` and `automations/steps/ThenStep.tsx`. It is set back to
  `font-normal` 3 times. `leading-none` again clips wrapped labels. The same `Field` helper
  (`space-y-1.5`, `Label`, `text-sm` error, `text-xs` hint) is copied in
  `app/(app)/w/[slug]/settings/workspace/page.tsx:421`, `knowledge/BrandVoiceCard.tsx:253` and
  `knowledge/SourceSheet.tsx:397`. Danger-coloured error and limit text is `text-xs` on 35
  lines and `text-sm` on 26.
- **Recommendation:**
  - labels `text-sm font-medium` with default leading
  - helper and error text `text-xs`
  - promote the `Field` helper to `components/ui/field.tsx` and use it in the inbox and schedule
    dialogs too

### TYP-010

**P2. Table headers come in three styles.**

- **Problem:** the three in-app tables use three header treatments:
  - `knowledge/SourcesCard.tsx:140`: 12 px medium, sentence case
  - `billing/PaymentHistory.tsx:23`: 11 px semibold uppercase 0.08em
  - `agent/AnswerText.tsx:124–128`: 13 px medium, body 13 px

  The legal tables are styled by `LegalPage` descendants.
- **Recommendation:** header `text-xs font-medium text-fg-secondary` in sentence case; body
  `text-sm` with `tabular-nums` for numbers. Ask tables can stay one step smaller at `text-xs`
  if space demands.

### TYP-011

**P2. Only the `latin` subset is loaded.**

- **Problem:**
  - **What is loaded:** `subsets: ["latin"]` (`app/layout.tsx:10–11`). Geist also publishes
    `latin-ext`, `cyrillic` and `vietnamese` subsets (Next's font data).
  - **The rupee sign:** ₹ (U+20B9) lies outside Google's `latin` unicode-range and inside
    `latin-ext`. Prices are formatted as "₹999" (`lib/copy.ts:500–517`) and shown on Pricing,
    Billing and in marketing copy. The rupee sign therefore renders from the system fallback even
    if Geist has the glyph, which is noticeable at large price sizes.
  - **Customer names:** latin-ext letters (for example Polish or Turkish characters) and
    Devanagari messages also fall back. Geist has no Devanagari at all.
- **Recommendation:**
  - add `"latin-ext"` to both fonts (a small extra file, loaded only when those characters
    appear)
  - check a ₹ price in the browser
  - for Hindi-script messages, accept the system fallback, or add a matched Devanagari fallback
    (for example Noto Sans Devanagari through `next/font`) after the owner decides

### TYP-012

**P3. The 15 px reading size is unofficial, and Ask's 28 px line height is loose.**

- **Problem:** Ask answers are `text-[15px] leading-7` (15/28, factor 1.87) in
  `AnswerText.tsx:51` and `RunView.tsx:62`. Legal prose is `text-[15px] leading-relaxed`
  (15/24.4). The mockups' `body-lg` is 15/22. It is one role, with two line heights and no
  token, and a test pins it (`AskPanel.test.tsx:212`).
- **Recommendation:** add the `text-md` token (15/24). Use it for Ask answers, the Ask composer
  and legal prose, then update the test.

### TYP-013

**P3. Weight 700 leaks in through `<strong>` and one `font-bold`.**

- **Problem:** browsers render `<strong>` as `bolder` (700 here). There are 33 bare `<strong>`s
  in `app/(marketing)/{privacy,terms,data-deletion}/page.tsx`. `AppSidebar.tsx:225` uses
  `font-bold` on 9 px text. The rest of the product tops out at 600.
- **Recommendation:** add `strong, b { font-weight: 600 }` in the base layer, and remove
  `font-bold` along with the 9 px tag (TYP-002).

### TYP-014

**P3. The app has no default body size.**

- **Problem:** the spec's Body is `text-sm` ("default UI text"), but nothing sets it. `<body>`
  inherits 16 px, and `AppShell`'s `<main>` (`shell/AppShell.tsx:106`) sets no size. Elements
  without their own size (96 `<p>`, 318 `<span>` and 88 `<li>` in the app) get 14 px only when
  an ancestor sets it, so a component moved into a new container can jump to 16 px. The
  `Dialog`, `Popover` and `Sheet` content primitives set `text-sm`; `AlertDialogContent`, pages
  and cards do not.
- **Recommendation:** set `text-sm` on the app shell's `<main>` (and on the mobile shell), so
  14 px is the inherited default inside the app. Marketing keeps its own.

### TYP-015

**P3. The spec's type-role table and `tokens.ts` are documentation only, and both have drifted.**

- **Problem:**
  - **Unused source:** `styles/tokens.ts:44–52` `typeRoles` feeds only the `/dev/tokens` page.
    No component imports it.
  - **Drift between spec and code:**
    - Pane title: spec `text-xl`, code `text-lg`
    - the 11 px chips have no row in the spec table
    - settings eyebrows use 0.12em
    - nav is `text-sm` (14 px, documented in `shell/sidebar-styles.ts:4–6`), while spec
      UX-SH-01 still says `text-[15px]`
  - **No guard:** nothing tests type roles the way `tokens.test.ts` tests colours.
- **Recommendation:** when adopting §6, update spec §4.2's table and `typeRoles` in one change,
  with a CONFLICTS entry. Have components import the role constants. Optionally extend
  `tokens.test.ts` to assert `--text-2xs` and `--text-md`.
