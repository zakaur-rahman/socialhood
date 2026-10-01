# UI audit: spacing, radius, borders and shadows (brief §7–§9)

Read-only audit of `apps/web` at `99f67be` (branch `feature/ui-audit`). No code was changed.
Companion document: [TYPOGRAPHY.md](TYPOGRAPHY.md). The method is the same: string literals in
`apps/web/src/**/*.{ts,tsx}`, tests excluded (336 source files), variants stripped, and JSX
elements parsed to map classes to roles. Counts are occurrences in source, not rendered
instances.

**Priorities:** P0 broken or inaccessible · P1 major inconsistency · P2 polish · P3 minor.

## Summary

- **Spacing is healthier than type.** 82% of the 2,257 spacing utilities sit on the 4 px grid
  (1,841). The 2 px half-steps (397, 18%) are almost all inside controls and chips, where they
  belong. A scale is already visible: 2, 4, 6, 8, 12, 16 and 24 px carry about 85% of usage.
  The drift is in a few roles:
  - outer cards use six paddings
  - tables use three cell schemes
  - control heights are patched at 79 call sites instead of living in the primitives
- **Radius splits cards in two.** 76 cards use `rounded-xl` (12 px), as the spec says, but 21 use
  `rounded-2xl` (16 px), including every settings, billing and connections card from the C-066
  redesign. Chips are pill-shaped (65) or 6 px (21). The shadcn `--radius` knob in `:root` is
  dead.
- **Borders are consistent in colour but too weak where they matter.** `border-line` (10% white)
  is used on 267 default borders.
  - **Field boundaries:** a field on a card is about 1.3:1 against the card, and the field fill
    is 1.02:1.
  - **Focus rings:** the 50% soft ring on `Tabs`, `ToggleGroup` and about 15 app components is
    2.1:1.
  - **Four focus treatments** coexist.
- **Shadows barely work on this dark UI.** Tailwind's defaults are 10% black, which is invisible
  on `#000` and faint on `#1F1F1F`. Popovers are `shadow-md` or `shadow-xl` depending on the call
  site, and dialogs have no shadow. The modal scrim is shadcn's light-mode `bg-black/10`, while
  the spec's mobile drawer asks for 60% and the Ask panel and Clerk already use 60%.

No P0 issues were found in this area. The closest are RAD-002 and RAD-003, which are
accessibility risks that the accessibility audit should confirm.

| ID | P | Finding |
|---|---|---|
| [SPC-001](#spc-001) | P1 | Control heights live at call sites: 79 touch patches (`min-h-10 md:min-h-7…9`), 116 primitive buttons with no touch height, inputs at 32, 36 or 40 px |
| [SPC-002](#spc-002) | P2 | Outer cards use six paddings (`p-3`, `p-4`, `p-5`, `p-6`, `p-4 md:p-5`, `p-5 md:p-6`); card header strips use `p-4` or `p-5` |
| [SPC-003](#spc-003) | P2 | Table cells use three padding schemes |
| [SPC-004](#spc-004) | P2 | Form rhythm varies (`space-y-3/4/5`, `gap-4/5`), and the `Field` helper is copied three times |
| [SPC-005](#spc-005) | P3 | Off-grid values (`3.5`, `5.5`, `7`, `9`, `11`, `px-[3px]`), negative-margin bleeds, and margins used for stacking (234 `mt-*`) |
| [SPC-006](#spc-006) | P3 | Page rhythm drifts: header gap `mb-4` against `mb-6`, settings `pt-5`, section gaps of 16, 20 or 24 px |
| [SPC-007](#spc-007) | P3 | Chip padding varies (`px-2 py-0.5` against five others) |
| [RAD-001](#rad-001) | P1 | Cards are 12 px (76) or 16 px (21); the C-066 settings cards contradict the spec and their own mockups |
| [RAD-002](#rad-002) | P1 | Four focus treatments; the soft-ring-only focus (50% brand) is 2.1:1, and the inbox composer's focus border is 1.9:1 |
| [RAD-003](#rad-003) | P1 | Field and inset-panel boundaries are close to invisible: field fill 1.02:1, field border 1.32:1, inset panel 1.0:1 fill and 1.15:1 border |
| [RAD-004](#rad-004) | P2 | Chips mix `rounded-full` (65), `rounded-md` (21), `rounded-lg` (4) and 4 px (3); the `Badge` primitive is `rounded-4xl` and has no importers |
| [RAD-005](#rad-005) | P2 | Button corners change with size (8 px against 6 px); raw buttons use four radii; the `--radius` knob is dead |
| [RAD-006](#rad-006) | P2 | Two names for each border colour (shadcn aliases against tokens); `border-line` on 50 overlays is a no-op; one popover draws a double edge |
| [RAD-007](#rad-007) | P2 | The "selected" accent bar has five implementations at 2, 3 or 4 px |
| [RAD-008](#rad-008) | P3 | Nested radii ignore padding (inset panels as round as their parents) |
| [RAD-009](#rad-009) | P3 | Small border inconsistencies: divider strength, dashed against dotted, border against ring cut-outs, deprecated bare `rounded`, stray radii |
| [SHD-001](#shd-001) | P1 | The dialog, sheet and mobile-drawer scrim is `bg-black/10` (spec: 60%); the modal barely separates from the page |
| [SHD-002](#shd-002) | P2 | Tailwind shadows (10% black) do nothing visible on these surfaces; 6 `shadow-sm` are no-ops |
| [SHD-003](#shd-003) | P2 | The same role gets different elevation: popovers `md` or `xl`, selects `md`, sheets `lg`, dialogs none, panels `xl`, the save bar `2xl` |
| [SHD-004](#shd-004) | P3 | Brand glow shadows reach the app (the current plan card has border, ring and glow) |
| [SHD-005](#shd-005) | P3 | `box-shadow` used for non-elevation jobs (a selection bar, a crop mask) is undocumented |

---

## Part A: spacing (brief §7)

### A.1 Inventory

There are 2,257 spacing utilities in 182 distinct classes. Values are Tailwind steps (×4 px).
`neg.` counts negative values (`-mx-1` and so on). `arb.` counts arbitrary values: `px-[3px]`
and `pb-[calc(env(safe-area-inset-bottom)+0.75rem)]`.

| Utility | Total | 0 | px | 0.5 | 1 | 1.5 | 2 | 2.5 | 3 | 3.5 | 4 | 5 | 5.5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 14 | 16 | 20 | 24 | auto | neg. | arb. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `p` | 188 | 7 | | 1 | 8 | 4 | 16 | 1 | 38 | | 69 | 22 | | 21 | | 1 | | | | | | | | | | | |
| `px` | 350 | 6 | | | 36 | 19 | 66 | 28 | 103 | 4 | 54 | 14 | | 18 | | | | | | 1 | | | | | | | 1 |
| `py` | 262 | 2 | | 60 | 32 | 18 | 60 | 20 | 34 | 1 | 3 | 1 | | 6 | | 2 | | 2 | | 3 | 1 | 3 | 7 | 7 | | | |
| `pt` | 54 | 2 | | 4 | 7 | 1 | 8 | 2 | 13 | | 7 | 3 | | 4 | | | | | | | 1 | | 1 | 1 | | | |
| `pr` | 29 | 1 | | 1 | 5 | 5 | 5 | | 4 | | 2 | | | | | 3 | | | | 3 | | | | | | | |
| `pb` | 22 | 1 | | 1 | 3 | 1 | 1 | 1 | 2 | | 7 | 1 | | 2 | | | | | | | | 1 | | | | | 1 |
| `pl` | 48 | 1 | | | 2 | 7 | 2 | 4 | 5 | | 5 | 4 | 3 | 2 | 5 | 2 | 3 | 2 | 1 | | | | | | | | |
| `m` | 3 | | | | | | | | 2 | | | | | | | | | | | | | | | | 1 | | |
| `mx` | 49 | 1 | | 1 | | | | | | | 5 | | | | | | | | | | | | | | 31 | 11 | |
| `my` | 6 | | | | 2 | | | | | | | | | | | | | | | | | | | | | 4 | |
| `mt` | 234 | | 3 | 41 | 37 | 12 | 37 | 1 | 35 | | 28 | 12 | | 10 | | 2 | | 3 | | 2 | 6 | 1 | | | 4 | | |
| `mr` | 3 | | | 1 | 1 | | | | | | | | | | | | | | | | | | | | | 1 | |
| `mb` | 50 | | | | 9 | | 13 | | 14 | | 5 | 1 | | 4 | | | | | | 1 | | | | | | 3 | |
| `ml` | 37 | 2 | | 1 | 4 | | 1 | | | | 1 | | | | | 1 | | | | | | | | | 22 | 5 | |
| `gap` | 565 | 6 | 1 | 23 | 92 | 65 | 188 | 13 | 120 | | 37 | 6 | | 11 | | 1 | | 2 | | | | | | | | | |
| `gap-x` | 32 | | | | 1 | 1 | 10 | | 13 | | 4 | | | 2 | | 1 | | | | | | | | | | | |
| `gap-y` | 27 | | | 1 | 15 | 3 | 7 | | 1 | | | | | | | | | | | | | | | | | | |
| `space-x` | 2 | | | | | | | | | | | | | | | | | | | | | | | | | 2 | |
| `space-y` | 296 | | | 5 | 48 | 41 | 92 | 1 | 56 | | 27 | 8 | | 15 | | 1 | | 1 | | 1 | | | | | | | |
| **All** | **2257** | **29** | **4** | **140** | **302** | **177** | **506** | **71** | **440** | **5** | **254** | **72** | **3** | **95** | **5** | **14** | **3** | **10** | **1** | **11** | **8** | **5** | **8** | **8** | **58** | **26** | **2** |

Distribution:

- **Most used utilities:**

  | Utility | Uses |
  |---|---:|
  | `gap-2` | 188 |
  | `gap-3` | 120 |
  | `px-3` | 103 |
  | `gap-1` | 92 |
  | `space-y-2` | 92 |
  | `p-4` | 69 |
  | `px-2` | 66 |
  | `gap-1.5` | 65 |
  | `py-0.5` | 60 |
  | `py-2` | 60 |
  | `space-y-3` | 56 |
  | `px-4` | 54 |

- **Grid adherence:** 1,841 values are whole 4 px steps (or 0, `px`, `auto`), 397 are 2 px
  half-steps (`0.5`, `1.5`, `2.5`, `3.5`, `5.5`), 17 are odd steps (`7`, `9`, `11`, `14`) and 2
  are arbitrary.
- **Odd and arbitrary values:**
  - `3.5` (5): `settings/workspace/page.tsx`, `AskConversation`, `RunView`
  - `5.5` (3): `SuggestionCard`, `InboxPreview`
  - `7` (5): `ui/dropdown-menu.tsx` inset items
  - `9` (3): search-icon insets in `settings/connections`, `AgentSettingsPage` and `ListHeader`
  - `11` (1): `PriorityQueue`
  - `px-[3px]`: `AppSidebar.tsx:225`
  - `14`, `20` and `24` appear only in marketing section rhythm
- **Negative values (26):** mostly bleeds and icon optical alignment, for example
  `-mx-5 md:-mx-6` (`PaymentHistory.tsx:64`) and `-mx-4 -mb-4` (dialog footers).
- **Tests:** 47 spacing tokens appear in test files, mostly `toHaveClass("min-h-10",
  "md:min-h-8")` assertions in `ActionCardView`, `AskPanel` and `PostDetailPage`. Changing the
  touch-height pattern (SPC-001) means updating those tests.

### A.2 Spacing by area

**Page padding** is consistent:

| Frame | Padding | Users |
|---|---|---|
| `PageFrame` (`shell/PageFrame.tsx:22`) | `p-4 md:p-6` | Automations, Comments, Post detail, Knowledge |
| Pages with their own frame | `p-4 md:p-6` | Home (`HomeScreen.tsx:111`), Schedule (`SchedulePage.tsx:387`), Composer (`PostComposer.tsx:558`), Automation editor (`AutomationEditor.tsx:235`), `PageSkeleton` |
| Settings | `px-4 pt-4 md:px-6 md:pt-6` (tab bar, `settings/layout.tsx:21`), then `px-4 pt-5 pb-6 md:px-6 md:pt-6` (`SettingsPageHeader.tsx:67`) | all settings tabs |
| Inbox | no page padding; `px-4` gutters per region, as UX-INB-* specifies | inbox |

This matches spec §4.2 ("p-6 on desktop, p-4 on phones"). The only drift is settings' `pt-5`
on phones.

**Section spacing** (between blocks on a page):

| Gap | Where |
|---|---|
| `space-y-6` / `gap-6` (24 px) | Home, Knowledge, Automations, AI settings, Workspace, Notifications, Billing; `PageFrame` header `mb-6` |
| `space-y-4` / `gap-4` (16 px) | Comments, Post detail, Composer, Agent settings, Schedule (`mb-4` under the header) |
| `gap-5` / `space-y-5` (20 px) | Billing (`gap-5`, `mt-5`), Automations (`space-y-5`) |
| Card grids | `gap-4`, with `gap-3` on the Comments grid (`CommentsPage.tsx:25`) and `lg:gap-6` on Post detail (`PostDetailPage.tsx:24`) |

**Card padding.** There is no `Card` primitive: every card is hand-rolled. The scan found 97
card surfaces (a rounded `xl`/`2xl` element with a surface background and a border). Every
distinct padding:

| Padding | Count | Radius | Files |
|---|---:|---|---|
| children padded (header strip + body) | 27 | xl 23, 2xl 4 | `settings/connections/page.tsx:144,189`; `automations/AutomationRow.tsx:130`; `comments/{CommentsColumn:130, CommentsPage:31,66,74,86, PostCard:38}`; `composer/PostPreview.tsx:163,200,273,317`; `home/PriorityQueue.tsx:95`; `inbox/Composer.tsx:292`; `knowledge/{KnowledgeGapsCard:43, SourcesCard:110}`; `schedule/{AgendaView:55,75, HashtagGroupsDialog:92, ListView:100,157,257, MonthView:68, WeekView:106}`; marketing `Faq:17`, `InboxPreview:63` |
| `p-4` | 27 | xl 27 | `home/{MetricTile:64, Checklist:56, AccountHealth:29, KnowledgeGapBanner:36, PriorityQueue:128, SentimentCard:67, TopIntentsCard:20, TopPostsCard:38}`; `comments/{PostDetailPage:35, PostPanel:64, PostPerformanceCard:201, PostSummaryCard:59, TopicsCard:12}`; `automations/{AutomationEditor:300, AutomationsPage:446,466, TemplateGallery:197}`; `composer/{PostPreview:125, StatusBanner:102}`; `knowledge/TestBox.tsx:34`; `states/PageSkeleton.tsx:14`; inset: `settings/workspace/page.tsx:273`, `AgentSettingsPage.tsx:154`, `BillingPage.tsx:406`, `AccountCard.tsx:150`; `/dev`, legal |
| `p-5` | 14 | xl 10, 2xl 4 | `knowledge/{BrandVoiceCard:57, KnowledgePage:23}`; `automations/{StepCard:45, AutomationEditor:492}`; `billing/PlanCards.tsx:38,49`; `connections/AccountCard.tsx:99`; data-deletion ×5; legal, marketing `Trust` |
| `p-3` | 8 | xl 7, 2xl 1 | inset: `inbox/DetailsPanel.tsx:22` (`CARD`), `ai/AiSettingsPage.tsx:154`, `AgentSettingsPage.tsx:170`; `schedule/SchedulePage.tsx:647`; `automations/PreviewPane.tsx:65`; `/dev` ×2; marketing |
| `p-6` | 4 | xl 1, 2xl 3 | `automations/AutomationsPage.tsx:495`; marketing `Features`, `HowItWorks`, `Platforms` |
| `p-5 md:p-6` | 4 | 2xl 4 | `settings/SettingsCard.tsx:46`, `SettingsPageHeader.tsx:50`, `billing/BillingPage.tsx:270`, `billing/PlanCards.tsx:71` |
| `p-4 md:p-5` | 2 | xl 2 | `composer/{Section:29, PostChecklist:27}` |
| `px-4 py-3` | 2 | xl 1, 2xl 1 | `AgentSettingsPage.tsx:360` (row button), `settings/SaveBar.tsx:70` |
| `py-6` | 2 | xl 2 | empty states: `SchedulePage.tsx:535`, `HashtagGroupsDialog.tsx:87` |
| other (one each) | 6 | | `p-2` (connections list), `px-4 py-2.5` (Agent credits), `py-1.5 pr-1.5 pl-4` (Ask composer), `py-1 pr-1 pl-3` (PhraseChips), `py-3` (sidebar card), `p-6 sm:p-8` (marketing Pricing) |

Card header strips (`border-b` above a list) are `p-4` in `PriorityQueue.tsx:96` and
`CommentsColumn.tsx:131`, and `p-5` in `KnowledgeGapsCard.tsx:44` and `SourcesCard.tsx:111`.

**Form spacing:**

| Role | Values in use |
|---|---|
| Label to control | `space-y-1.5` (6 px) in the three `Field` helpers and most forms |
| Field to field | `space-y-4` or `gap-4` (most), `space-y-3` (3 forms), `gap-5` (`SourceSheet.tsx:263`), `space-y-5` (1) |
| Fieldsets | `space-y-2` (4), `space-y-3` (2), `space-y-4` (1) |
| Save row | `flex justify-end gap-2` |

**Table cells:**

| Table | Header | Body |
|---|---|---|
| `knowledge/SourcesCard.tsx:141–197` | `px-5 py-2` at the edges, `px-3 py-2` inside | `px-5 py-3` / `px-3 py-3` |
| `billing/PaymentHistory.tsx:23,89` | `px-5 py-2.5 md:px-6` | `px-5 py-3 md:px-6` |
| `agent/AnswerText.tsx:128,142` | `px-3 py-2` | `px-3 py-2` |

**Navigation items:**

| Item | Height | Padding |
|---|---|---|
| Sidebar row (`sidebar-styles.ts:10`) | `h-9`, `pointer-coarse:h-10` | `px-3 gap-3` |
| Settings tab (`settings/layout.tsx:32`) | `min-h-11` | `px-3` |
| Marketing nav (`SiteHeader.tsx:22`) | `min-h-10` | `px-3` |
| Mobile menu (`MobileMenu.tsx:68`) | `min-h-11` | `px-2` |
| `TabsTrigger` / `ToggleGroupItem` | `min-h-8` (15 call sites override it, mostly to `min-h-10 md:min-h-8`) | `px-2` / `px-2.5` |

**Buttons:**

| Source | Height | Padding |
|---|---|---|
| `Button` primitive (`ui/button.tsx:24–33`) | `xs` h-6, `sm` h-7, default h-8, `lg` h-9; icon sizes 6–9 | `px-2` / `px-2.5`, `gap-1` / `gap-1.5` |
| Call sites (162 of 225 `<Button>`s pass a `className`) | `min-h-10` (67), `md:min-h-8` (25), `size-10` (20), `md:min-h-7` (16), `md:min-h-9` (14), `md:size-8` (11), `h-10` (10), `md:h-9` (7) … | — |
| Raw `<button>` (63) | `min-h-10 md:min-h-{6,7,8,9,0}`, `size-10 sm:size-7`, `h-9 md:h-8`, `size-5`/`size-6` (chip close) | `px-1` to `px-4` |

Desktop control heights span 24, 28, 32, 36 and 40 px. On touch the codebase converges on 40 px,
but only where each call site remembers to add it (SPC-001).

**Modals and sheets** are consistent:

- `Dialog` / `AlertDialog`: `p-4 gap-4`, footers `p-4` bleeding with `-mx-4 -mb-4`
  (`ui/dialog.tsx:64,110`).
- `Sheet` header and footer: `p-4`.
- Custom panels (`AskPanel.tsx:94`): `pl-4` under `h-14` headers.
- `SourceSheet` body: `p-4 gap-5`.
- Overrides: `p-0` (2 sheets with their own sections), `p-2` (attachment lightbox) and `p-3`
  (mobile nav drawer).

**Chips:**

| Padding | Uses |
|---|---:|
| `px-2 py-0.5` | 38 |
| `px-1` | 11 |
| `px-2.5 py-0.5` | 7 |
| `px-3 py-1` | 7 |
| `px-1.5` | 7 |
| `px-1.5 py-0.5` | 4 |
| `px-2` | 3 |

### A.3 Proposed spacing scale

Keep Tailwind's 4 px spacing variable (`--spacing: 0.25rem`) and restrict the steps by role.
These are already the most-used values:

| Step | px | Role | Today |
|---|---:|---|---:|
| `0.5` | 2 | inside controls only: chip `py`, badge offsets | 140 |
| `1` | 4 | icon to text in chips; title to meta line; stacked bubbles (spec "4 px apart") | 302 |
| `1.5` | 6 | inside controls only: label to field, icon gap in buttons | 177 |
| `2` | 8 | default inline gap; chip `px`; tight list stacks | 506 |
| `3` | 12 | control `px`; row `py`; gap between related controls; inset panel padding | 440 |
| `4` | 16 | **gutter**: inbox regions, card padding, dialog and sheet padding, page padding on phones, card-grid gap, field-to-field | 254 |
| `5` | 20 | roomy card padding on phones only | 72 |
| `6` | 24 | page padding on desktop; section gap; roomy card padding on desktop | 95 |
| `8`+ | 32+ | empty states, icon insets in search fields (`pl-9`/`pl-10`) and marketing section rhythm only | 68 |

Canonical value per role:

| Role | Canonical | Replaces |
|---|---|---|
| Page padding | `p-4 md:p-6` | settings `pt-5` |
| Page header to content | `mb-6` | `mb-4` (Schedule) |
| Section gap | `space-y-6` / `gap-6` | `space-y-4`, `gap-5`, `space-y-5` at page level |
| Card grid gap | `gap-4` (`lg:gap-6` for two-column page layouts) | `gap-3` |
| Card padding, standard (data and dashboard cards) | `p-4` | `p-5` on Knowledge, StepCard and AccountCard; `p-4 md:p-5` |
| Card padding, roomy (settings, billing, forms, plan cards) | `p-5 md:p-6` | `p-6`, `p-5` on PlanCards and AccountCard |
| Card header strip | same as the card's padding (`p-4` or `p-5 md:p-6`) | `p-5` on `p-4` cards |
| Inset panel (a group inside a card) | `p-3` for rows, `p-4` for form groups | — |
| Field stack / label gap / hint gap | `space-y-4` / `space-y-1.5` / `mt-1.5` | `space-y-3`, `gap-5` |
| Table cells | edge cells align to the card padding (`px-4` or `px-5 md:px-6`), inner `px-3`; header `py-2`, body `py-3` | — |
| Control heights | `sm` 32 / default 36 / `lg` 40 desktop; **40 on touch** for all | per-call `min-h-10 md:min-h-*` |
| Chip | `px-2 py-0.5` (`h-5`) | `px-2.5`, `px-3 py-1` for status chips; filter chips may stay `px-3 py-1` |
| Dialog / sheet | `p-4 gap-4` (keep) | — |

---

## Part B: borders (brief §8)

### B.1 Radius inventory

586 radius utilities in 163 files. Pixel values are Tailwind v4 defaults; the theme overrides
none of them.

| Utility | px | Uses | Files |
|---|---:|---:|---:|
| `rounded-full` | 9999 | 173 | 84 |
| `rounded-lg` | 8 | 156 | 83 |
| `rounded-xl` | 12 | 114 | 68 |
| `rounded-md` | 6 | 67 | 44 |
| `rounded-2xl` | 16 | 35 | 21 |
| `rounded` (bare; deprecated default in v4) | 4 | 7 | 7 |
| `rounded-sm` | 4 | 4 | 3 |
| `rounded-bl-md` / `rounded-br-md` (bubble tails) | 6 | 4 / 4 | 4 / 3 |
| `rounded-none` | 0 | 3 | 3 |
| `rounded-[min(var(--radius-md),10px)]` / `…12px)]` | 6 | 3 / 2 | 2 / 1 |
| `rounded-[4px]`, `rounded-t-[4px]` | 4 | 2 / 2 | 2 / 1 |
| `rounded-b-xl`, `rounded-t-md`, `rounded-t-lg`, `rounded-l-xl` | — | 2 / 1 / 1 / 1 | |
| `rounded-3xl` | 24 | 1 | marketing `FinalCta` |
| `rounded-4xl` | 32 | 1 | `ui/badge.tsx:7` |
| `rounded-[10px]` | 10 | 1 | `marketing/primitives.tsx` |
| `rounded-[2px]`, `rounded-[inherit]` | — | 1 / 1 | tooltip arrow, calendar card |

`globals.css:111` sets `--radius: 0.5rem`, but no `--radius-*` is mapped from it, so nothing
reads it. The `rounded-[min(var(--radius-md),…)]` classes in `ui/button.tsx:25–32` resolve
against Tailwind's own `--radius-md` (6 px).

### B.2 Radius by component type

Primitives' built-in radii are counted per call site and marked "(prim)".

| Component | Radius in use (count) | Spec §4.2 | Inconsistency |
|---|---|---|---|
| Buttons | `lg` (prim) 143, `md`-equivalent 6 px (prim `xs`/`sm`/`icon-sm`) 80, `md` 20, `full` 16, `lg` 12, `xl` 2 | small buttons `md`; icon and send buttons `full` | 8 and 6 px side by side (RAD-005) |
| Inputs, selects, textareas | `lg` (prim) 47, `lg` 16, `md` 2 (`AutomationEditor.tsx:244` title, `CommentComposer.tsx:81`), `none` 1; composer shells `xl` (`inbox/Composer.tsx:292`, `PhraseChips.tsx:71`) and `2xl` (`AskComposer.tsx:87`) | `lg`; composer `rounded-[20px]` (UX-INB-07) | composers at 12 or 16 px instead of the spec's 20 px pill |
| Cards | `xl` 73, `lg` 29 (mostly inset or notice panels), `2xl` 22, `md` 3. The element heuristic counts differently from the line-based card scan in A.2, which gives 76 `xl` and 21 `2xl`. | `xl` | RAD-001 |
| Dialogs | `xl` (prim) 25 | — | consistent |
| Sheets | none (edge-attached) 5 | — | consistent |
| Dropdowns, popovers, selects | `lg` (prim) 39; tooltip `md` (prim) 7 | `lg` | consistent |
| Badges and chips | `full` 65, `md` 21, `lg` 4, 4 px 3 | `full` | RAD-004 |
| Tables | inherit the card (`xl`); Ask tables unrounded | — | fine |
| Images and media | `lg` 7, `md` 2 (audio and file rows in `AttachmentView.tsx:87,105`) | `lg` | fine |
| Avatars, dots, switches | `full` 38+ | `full` | consistent |
| Segmented controls | track `lg` (`ui/tabs.tsx:16`, `ui/toggle-group.tsx:26`, `ListHeader.tsx:93`), item `md` | as spec | consistent; two ToggleGroups override items to `full` |
| Message bubbles | `2xl` + `rounded-b{l,r}-md` tail | as spec | consistent (pinned by `MessageBubble.test.tsx`) |
| Skeletons | `full` 10, `lg` 9, `xl` 9, `2xl` 5 | match what they stand in for | fine |

### B.3 Border widths

| Width | Uses | Where |
|---|---:|---|
| `border` (1 px) | 217 | cards, inputs, chips, list frames |
| `border-b` / `border-t` | 38 / 37 | headers, footers, card header strips, dividers |
| `border-l` / `border-r` | 7 / 6 | panes (details panel, list pane) |
| `border-y` | 1 | payment table header |
| `border-0`, `border-b-0`, `border-r-0` | 5 / 2 / 2 | resets |
| `border-2` | 5 | picked media tiles (2), the crop box, the week-view drop indicator (`WeekView.tsx:280`), the avatar badge cut-out |
| `border-b-2` | 1 | settings tab underline (`settings/layout.tsx:32`) |
| `border-l-2` | 2 | calendar post card status edge, comment reply quote |
| `border-l-4` | 1 | danger `SettingsCard` (`SettingsCard.tsx:47`) |
| `divide-y` | 12 | list rows |
| `ring-1` / bare `ring` (1 px in v4) | 8 / 2 | overlay edges in primitives, the current plan card, the sidebar "AI" tag |
| `ring-2` | 20 | badge cut-outs (`ring-panel`), solid focus rings, selected thumbnails |
| `ring-3` | 31 | soft focus rings and `aria-invalid` rings |
| `border-dashed` / `border-dotted` | 6 / 2 | "add" and empty slots |

1 px is the norm. 2 px is reserved for emphasis (picked or selected tiles) and cut-outs, which is
sound.

### B.4 Border colours by state

The table covers 444 border-colour and divide-colour utilities. `* { border-color:
var(--color-line) }` in the base layer makes a bare `border` equal `border-line`.

| State | Utilities (count) |
|---|---|
| Default | `border-line` 267, `border-line-subtle` 41, `border-brand-line` 23, `divide-y` (line) 12, `border-line-strong` 10, `border-danger` 10, `border-brand` 8, `border-transparent` 8, `divide-line-subtle` 7, `divide-line` 5, `border-warning/40` 4, `border-input` 4, `border-l-{danger,brand,success}` 7, `border-success/30–40` 3, `border-border` 2, … |
| Hover | `hover:border-line-strong` 4 (settings tabs, `PostCard`, an Ask suggestion, the media picker), `hover:border-brand/60` 1 (sidebar Ask tile). Hover is otherwise signalled by a fill (`hover:bg-white/5` 25, `hover:bg-raised` 15, `hover:bg-white/10` 12). |
| Focus | `border-ring` 9 (7 `focus-visible:` in primitives, 2 `focus-within:` in `ChipListInput` and `KeywordInput`), `focus-within:border-line-strong` 1 (inbox composer), `focus-within:border-brand-line` 1 (Ask composer), `focus:bg-raised` 16 (raw inputs, fill only) |
| Active / selected | conditional strings: `border-brand` (picked media, current plan), `border-brand-line` (active filter chip `ListHeader.tsx:37`), settings tab `border-brand` |
| Invalid | `aria-invalid:border-destructive` 7 and `/50` 5 (primitives), `aria-invalid:border-danger` 4 (raw inputs): the same colour under two names |
| Disabled | `disabled:border-line` 1; otherwise `opacity-50` |

Composited contrast of each hairline against the surface it sits on. All values are computed;
WCAG 1.4.11 asks 3:1 for boundaries needed to identify a control.

| Border | On canvas `#000` | On panel `#1F1F1F` | On field `#1D1D1D` | On raised `#2A2A2A` |
|---|---:|---:|---:|---:|
| `line-subtle` (white 5%) | 1.08 | 1.15 | 1.14 | 1.17 |
| `line` (white 10%) | 1.21 | 1.34 | 1.35 | 1.36 |
| `line-strong` (white 20%) | 1.66 | 1.92 | 1.90 | 1.93 |
| `brand-line` (brand 35%) | — | 1.65 | — | — |
| `danger/40` | — | 1.68 | — | — |

Other relevant pairs:

| Pair | Contrast |
|---|---:|
| Field fill `#1D1D1D` against panel | **1.02** |
| Raised against panel | 1.15 |
| `bg-field/60` inset panel on panel (renders `#1E1E1E`) | **1.0** |
| Soft focus ring `ring-ring/50` (brand at 50%) on panel | **2.10** |
| Solid brand focus (`globals.css:127` outline, `ring-brand`) on panel / on canvas | 4.54 / 5.79 |

Assessment:

- **For decorative hairlines** (card edges, dividers, pane borders), `line` and `line-subtle` are
  right for the "calm density" principle (§4.1), and not too strong.
- **For control boundaries and focus they are too weak** (RAD-002, RAD-003).
- **`line-strong` is used only 10 times by default**, mostly for dashed placeholders, so the
  ladder has an unused step that could serve inputs.

### B.5 Proposed radius scale

These are Tailwind defaults with one role per step. The rule for nesting is: inner radius equals
outer radius minus padding, rounded to a step.

| Step | px | Roles |
|---|---:|---|
| `rounded-none` | 0 | sheets, full-bleed panes, tables inside cards |
| `rounded-sm` | 4 | `kbd`, inline code, tiny media counters and labels on thumbnails, checkbox (replaces bare `rounded`, `rounded-[4px]` and the 4 px badges) |
| `rounded-md` | 6 | small buttons (`xs`, `sm`, `icon-sm`), segmented items, menu items, tooltips, bubble tails |
| `rounded-lg` | 8 | buttons (default, `lg`), inputs, selects, segmented tracks, menus and popovers, banners, **inset panels**, media and thumbnails |
| `rounded-xl` | 12 | **all cards**, dialogs, sidebar, composer shells, notice cards |
| `rounded-2xl` | 16 | message and Ask bubbles, and the composer pill if the spec's 20 px is dropped; marketing cards |
| `rounded-full` | — | avatars, dots, chips and status pills, count badges, switches, icon-only round buttons, send button |

Retire `rounded-3xl`, `rounded-4xl`, `rounded-[10px]`, the `min(var(--radius-md),…)` arbitrary
values and the `:root --radius`. Either delete `--radius` or wire `--radius-*` to it through
`@theme inline`; the spec's "Tailwind defaults" suggests deleting it.

### B.6 Proposed border rules

| Use | Width | Colour |
|---|---|---|
| Card, pane and list edges | 1 px | `line` |
| Dividers between rows inside a card | 1 px | `line-subtle` (the card's structural edges stay `line`) |
| Inset panel | 1 px | `line` (not `line-subtle`) or a raised fill, so the group is visible |
| Input, select and textarea at rest | 1 px | a new `--color-line-input` at about white 33% (3:1 on panel), or `line-strong` plus a fill that differs from the panel (RAD-003) |
| Hover on interactive cards and inputs | 1 px | `line-strong` |
| Focus (every interactive element) | 2 px ring | solid `brand` (4.5:1), with an optional soft halo beside it, never on its own |
| Selected or active | 2 px | `brand` (tiles); 2 px bar `brand` on the leading edge (rows, nav) |
| Invalid | 1 px | `danger` (one name, not `destructive`) |
| Disabled | — | keep the border, lower opacity |
| Dashed placeholders | 1 px dashed | `line-strong` (drop dotted) |

---

## Part C: shadows (brief §9)

### C.1 Inventory and classification

There are 50 shadow utilities in 39 files, and no `box-shadow` in CSS (`globals.css` has none;
no inline `boxShadow`). Tailwind v4 values: `shadow-sm` is `0 1px 3px rgb(0 0 0/.1)…`,
`shadow-md` `0 4px 6px -1px rgb(0 0 0/.1)…`, `shadow-lg` `0 10px 15px -3px rgb(0 0 0/.1)…`,
`shadow-xl` `0 20px 25px -5px rgb(0 0 0/.1)…` and `shadow-2xl` `0 25px 50px -12px
rgb(0 0 0/.25)`.

| Class | Where | Purpose | Category |
|---|---|---|---|
| none | every card and panel; `DialogContent` and `AlertDialogContent` (`ui/dialog.tsx:64`, `ui/alert-dialog.tsx:61`: `ring-1` only); `TooltipContent` | flat surfaces; modal | none |
| `shadow-sm` | `ui/tabs.tsx:27`, `ui/toggle-group.tsx:37` (active item), `ListHeader.tsx:103` (active segment), `PlatformStrip.tsx:54` (active platform), `MessageBubble.tsx:95` (incoming bubble), `PreviewPane.tsx:171` (preview bubble) | lift of a selected segment; bubble | subtle (invisible on dark) |
| `shadow-md` | `ui/popover.tsx:32`, `ui/dropdown-menu.tsx:45`, `ui/select.tsx:71` (primitive defaults; reach the screen in 4 popovers and menus without overrides and all 14 `SelectContent`s) | menu, popover | md |
| `shadow-lg` | `ui/sheet.tsx:65` (every sheet), `ui/dropdown-menu.tsx:246` (submenu) | sheet; floating | lg |
| `shadow-lg shadow-brand/10` | `billing/PlanCards.tsx:72` (current plan) | emphasis glow | lg (glow) |
| `shadow-lg shadow-brand/25` | `marketing/primitives.tsx:36` (CTA) | marketing glow | lg (glow) |
| `shadow-xl` | 21 `PopoverContent`/`DropdownMenuContent` overrides (`AiModeControl:153`, `AnalysisChips:118`, `DecisionInfo:43`, `AutomationEditor:279,468`, `AutomationRow:245`, `ThenStep:402`, `CaptionEditor:448`, `PostComposer:579`, `inbox/Composer:334,386`, `ListHeader:186`, `ScheduledList:153`, `ThreadHeader:143`, `SourcesCard:57`, `PostingTimesDrawer:298`, `SchedulePage:488`, `cell-extras:69,124`, `post-parts:180`, `NotificationsButton:46`) | menu, popover (the spec's choice) | floating |
| `shadow-xl` | `AskPanel.tsx:91`, `AgentSettingsPage.tsx:399` (side panels over a scrim) | modal | modal |
| `shadow-xl` | `AskConversation.tsx:223` ("jump to latest" pill), `calendar-dnd.tsx:239` (drag preview) | floating control | floating |
| `shadow-2xl shadow-black/40` | `settings/SaveBar.tsx:70` (sticky save bar, `backdrop-blur`) | floating bar | floating |
| `shadow-2xl shadow-black/60` | `marketing/MobileMenu.tsx:59` | marketing dropdown | modal |
| `shadow-2xl shadow-brand/10` | `marketing/InboxPreview.tsx:63`, `marketing/Pricing.tsx:43` | marketing glow | floating (glow) |
| `shadow-[inset_2px_0_0_var(--color-brand)]` | `agent/Threads.tsx:183` | selected-row bar | not elevation |
| `shadow-[0_0_0_9999px_color-mix(…canvas 60%…)]` | `composer/CropDialog.tsx:150` | dims outside the crop box | not elevation |
| external | Sonner toasts (`theme="dark"`, `layout.tsx:34`) and Clerk modals (`colorModalBackdrop` 60%) | library defaults | floating / modal |

Scrims:

| Overlay | Scrim |
|---|---|
| `Dialog`, `AlertDialog`, `Sheet` (including the mobile nav drawer, `MobileNav.tsx:36`) | `bg-black/10 supports-backdrop-filter:backdrop-blur-xs` (`ui/dialog.tsx:42`, `ui/alert-dialog.tsx:39`, `ui/sheet.tsx:40`) |
| Ask panel, run detail | `bg-black/60` (`AskPanel.tsx:82`, `AgentSettingsPage.tsx:394`) |
| Clerk | `rgb(0 0 0 / 0.6)` (`lib/clerk-appearance.ts:24`) |
| Spec UX-SH-02 (drawer) | "over a `bg-black/60` scrim" |

What looks dated or is duplicated:

- **Brand glows** (`shadow-brand/10–25`) are a 2021-era SaaS flourish. They are fine in marketing
  but stack with a border and a ring on the in-app current plan card (SHD-004).
- **The same popover role gets two elevations** depending on whether the caller remembered the
  override (SHD-003).
- **`shadow-sm` on active segments** is a light-theme idiom that does nothing here (SHD-002).

### C.2 Proposed elevation scale for dark surfaces

On near-black, depth comes from three things: a lighter surface, a hairline edge, and a strong
and wide black shadow that darkens what is beneath. A 10% shadow does not register. The proposal
keeps spec §4.1 ("almost no shadows"): only things that float get one.

| Level | Token (proposed) | Value | Use |
|---|---|---|---|
| 0, flat | — | no shadow; `bg-panel` on canvas + `border-line` | cards, panes, sidebar, bubbles (drop the incoming bubble's `shadow-sm`) |
| 1, raised | `shadow-raised` | `inset 0 1px 0 rgb(255 255 255 / 0.06)` | active segment or tab on `bg-raised` (replaces `shadow-sm`); optional |
| 2, floating | `shadow-floating` | `0 0 0 1px var(--color-line), 0 8px 24px -6px rgb(0 0 0 / 0.7)` | popover, dropdown, select, tooltip, toasts, jump pill, drag preview, save bar |
| 3, overlay | `shadow-overlay` | `0 0 0 1px var(--color-line), 0 24px 64px -12px rgb(0 0 0 / 0.8)` + scrim `bg-black/60` | dialog, alert dialog, sheet, mobile drawer, Ask panel, run detail |
| Marketing glow | — | `shadow-brand/10–25` | marketing pages only |

Sketch, not applied. It needs a CONFLICTS entry like C-002, because UX-TOK-01 is "exactly as
below":

```css
@theme {
  --shadow-raised:   inset 0 1px 0 rgb(255 255 255 / 0.06);
  --shadow-floating: 0 0 0 1px var(--color-line), 0 8px 24px -6px rgb(0 0 0 / 0.7);
  --shadow-overlay:  0 0 0 1px var(--color-line), 0 24px 64px -12px rgb(0 0 0 / 0.8);
}
```

Then:

- put `shadow-floating` in the `Popover`, `DropdownMenu`, `Select` and `Tooltip` primitives,
  replacing their `ring-1 ring-foreground/10` and `shadow-md`/`lg`
- put `shadow-overlay` and a `bg-black/60` scrim in `Dialog`, `AlertDialog` and `Sheet`
- delete the 21 `shadow-xl` and the 50 `border-line bg-panel` call-site overrides
- update spec §4.2 "Elevation"

---

## Findings

### SPC-001

**P1. Control heights live at call sites, not in the primitives.**

- **Problem:** `Button` sizes are 24–36 px (`ui/button.tsx:24–33`) and `Input` is 32 px
  (`ui/input.tsx:10`), with no touch size. The codebase's own touch rule (40 px under `md`, or
  `pointer-coarse:` in the sidebar) is therefore re-applied by hand at each call site:
  - 79 call sites use the `min-h-10 md:min-h-{7,8,9}` pattern, and 15 more use
    `size-10 md:size-8`
  - 116 `<Button>`s pass no height and stay 24–32 px on phones
  - Inputs come in 32 (primitive), 36 (`h-9`, 7 overrides plus raw), `h-10 md:h-9`,
    `h-10 md:h-8` and `min-h-10`. The settings redesign standardised on 40 px (C-066), the rest
    did not.
  - Navigation rows are 36, 40 or 44 px.

  This is a consistency and touch-comfort problem, not a WCAG AA failure: 2.5.8 allows 24 px.
- **Evidence:** §A.2 Buttons and Navigation items. Examples: `ActionCardView.test.tsx:89` and
  `PostDetailPage.test.tsx:546` pin `min-h-10 md:min-h-8`.
- **Affected:** `components/ui/{button,input,select,tabs,toggle-group}.tsx` and every feature
  folder.
- **Recommendation:** move the touch height into the primitives (for example `default:
  "h-10 md:h-8"` or `pointer-coarse:min-h-10` in `buttonVariants`, and the same for `Input`,
  `SelectTrigger`, `TabsTrigger` and `ToggleGroupItem`). Settle on three desktop sizes (32, 36
  and 40), then delete the per-call patches and update the pinned tests.

### SPC-002

**P2. Outer cards use six paddings, and card header strips use `p-4` or `p-5`.**

- **Problem:** with no `Card` primitive, padding follows whichever mockup each feature copied.
  The Home mockup's cards are `p-5` and the implementation's are `p-4`; the settings mockups
  use 20–28 px. So:
  - Home and Comments cards are 16 px
  - Knowledge cards are 20 px
  - Settings and Billing cards are 20 → 24 px
  - the Composer's cards are 16 → 20 px
  - one Automations section is 24 px

  Card header strips differ inside one page type (`PriorityQueue.tsx:96` `p-4` against
  `KnowledgeGapsCard.tsx:44` `p-5`).
- **Evidence:** the card padding table in §A.2.
- **Recommendation:** add a `Card` primitive (or `card.tsx` with `CardHeader` and `CardBody`)
  with two densities: `standard` `p-4` and `roomy` `p-5 md:p-6`. The header uses the same
  padding as the body. Migrate the 97 card surfaces.

### SPC-003

**P2. Table cells use three padding schemes.**

- **Problem:**
  - `SourcesCard`: `px-5` edges, `px-3` inner, `py-2` / `py-3`
  - `PaymentHistory`: `px-5 md:px-6` everywhere, `py-2.5` / `py-3`, plus `-mx-5 md:-mx-6` to
    bleed
  - `AnswerText`: `px-3 py-2` everywhere

  Together with TYP-010, the three tables look unrelated.
- **Recommendation:** one table style. Edge cells align to the card padding and inner cells use
  `px-3`; header `py-2`, body `py-3`. Put it in a `ui/table.tsx`, and bleed with the card's own
  padding variable, not with hard-coded negative margins.

### SPC-004

**P2. Form rhythm varies, and the `Field` helper is copied three times.**

- **Problem:**
  - **Field stacks:** `space-y-4`, `gap-4`, `space-y-3` (3 forms), `gap-5`
    (`SourceSheet.tsx:263`) or `space-y-5`.
  - **Copied helper:** the same `Field` (`space-y-1.5` + Label + hint + error) is defined
    separately in `settings/workspace/page.tsx:421`, `knowledge/BrandVoiceCard.tsx:253` and
    `knowledge/SourceSheet.tsx:397`.
  - **Dialog forms:** those in the inbox and schedule build their own stacks.
- **Recommendation:** a shared `ui/field.tsx` (label, control, hint, error at `space-y-1.5`) and
  a form stack of `space-y-4`, with `space-y-6` between fieldsets. See TYP-009 for label sizes.

### SPC-005

**P3. Off-grid values, negative-margin bleeds, and margins used for stacking.**

- **Problem:**
  - **Off-grid values:** `3.5` (5), `5.5` (3: `SuggestionCard.tsx:70,149`, `InboxPreview.tsx:135`),
    `11` (`PriorityQueue.tsx`) and `px-[3px]` (`AppSidebar.tsx:225`). Most are optical tweaks
    that a token would absorb.
  - **Margins for stacking:** `mt-*` (234) and `mb-*` (50) do much of the vertical stacking
    that `gap` or `space-y` on the parent would make uniform (for example `mt-0.5` 41 and
    `mt-1` 37 between titles and meta lines).
  - **Negative bleeds:** `-mx-5 md:-mx-6` (`PaymentHistory.tsx:64`) duplicates the card padding.
- **Recommendation:**
  - allow half-steps only inside controls
  - use `gap`/`space-y` on parents for title-and-meta stacks (`gap-0.5` or `gap-1`)
  - replace bleeds with a `Card` that exposes its padding (SPC-002)

### SPC-006

**P3. Page rhythm drifts.**

- **Problem:**
  - **Header to content:** `mb-6` (`PageFrame.tsx:31`, Home) against `mb-4`
    (`SchedulePage.tsx:388`).
  - **Settings frame:** starts at `pt-5` on phones while every other page uses `p-4`
    (`SettingsPageHeader.tsx:67`).
  - **Page-level section gaps:** 24 px (most), 16 px (Comments, Post detail, Composer, Agent)
    and 20 px (Billing `gap-5`, Automations `space-y-5`).
- **Recommendation:** use `PageFrame` (or its classes) everywhere: `p-4 md:p-6`, header `mb-6`,
  sections `space-y-6`, card grids `gap-4`.

### SPC-007

**P3. Chip padding varies.**

- **Problem:** `px-2 py-0.5` (38) is the de facto chip. The others are `px-2.5 py-0.5` (7),
  `px-3 py-1` (7), `px-1.5` (7), `px-1` (11, thumbnail labels) and `px-1.5 py-0.5` (4). The
  heights are then fixed with `leading-*` patches (TYP-002).
- **Recommendation:** status chip `h-5 px-2` (11/16 type); filter chip `h-7 px-3` (a control);
  thumbnail label `px-1` `rounded-sm`. All three go in the rebuilt `Badge` (RAD-004).

### RAD-001

**P1. Cards are 12 px (76) or 16 px (21).**

- **Problem:**
  - **The spec:** "Cards and the sidebar `rounded-xl`" (§4.2). Home, Knowledge, Comments,
    Schedule, Automations and Composer follow it.
  - **C-066:** the settings redesign uses `rounded-2xl` for `SettingsCard`
    (`SettingsCard.tsx:46`), `SettingsPageHeader` (`:50`), `AccountCard` (`AccountCard.tsx:99`),
    `PlanCards` (`:38,49,71`), the billing hero (`BillingPage.tsx:270`), the connections list
    (`settings/connections/page.tsx:144,162,189`) and `SaveBar` (`SaveBar.tsx:70`).
  - **The mockups:** the settings mockups use `rounded-xl` cards with `xl` = 0.75rem
    (`design/social_hood_settings_*/code.html`). The Home mockup's cards are `rounded-2xl`, yet
    Home was built with `xl`. Each redesign ended up with the other mockup's radius.

  Moving from Home to Settings changes the shape of every card.
- **Recommendation:** `rounded-xl` for all app cards. Reserve `2xl` for bubbles, the composer
  pill and marketing.

### RAD-002

**P1. Four focus treatments, and the soft-ring-only focus is 2.1:1.**

- **Problem:** the four treatments are:
  1. **Global outline:** 2 px solid brand, offset 2 (`globals.css:127`); 4.54:1 on panel.
  2. **Primitive focus:** `focus-visible:border-ring` plus `ring-3 ring-ring/50` in `Button`,
     `Input`, `Select`, `Textarea`, `Checkbox`, `Switch`, `ChipListInput` and `KeywordInput`.
     The 1 px border is solid brand, which passes.
  3. **Soft ring only:** `ring-3 ring-ring/50`, about 2.1:1 against panel or field, below the
     3:1 that WCAG 1.4.11 asks of a focus indicator. It is used in:
     - `ui/tabs.tsx:27`
     - `ui/toggle-group.tsx:37` (19 importing files)
     - `AskComposer.tsx:87`
     - `AutomationEditor.tsx:253`
     - `AutomationRow.tsx:177`
     - `AutomationsPage.tsx:319`
     - `StepCard.tsx:45`
     - `PostsStep.tsx:215,254`
     - `CommentComposer.tsx:91`
     - `PostCard.tsx:38`
     - `MediaTray.tsx:206`
     - `composer/Section.tsx:29`
     - `MetricTile.tsx:70`
     - `PriorityQueue.tsx:105`
     - `TopPostsCard.tsx:45,59`
  4. **Solid `ring-2 ring-brand`:** in 8 places in settings, billing and the calendar.

  The inbox reply box is a fifth case. It shows focus only as `focus-within:border-line-strong`
  plus a lighter fill (`inbox/Composer.tsx:292`), which is 1.9:1. Its textarea is
  `outline-none` (`:309`).
- **Recommendation:** one focus token. A 2 px solid `brand` ring (or the global outline) on every
  interactive element, with the soft halo allowed only beside it. Fix `Tabs` and `ToggleGroup`
  first. Ask the accessibility audit to confirm.

### RAD-003

**P1. Field and inset-panel boundaries are close to invisible.**

- **Problem:**
  - **Fields:** a field on a card is a `#1D1D1D` fill on a `#1F1F1F` card (1.02:1) inside a
    10% white border (1.32:1 against the card). Its shape is carried by a border at less than
    half the 3:1 that WCAG 1.4.11 asks for when the boundary identifies the control.
  - **The `Input` primitive:** `bg-transparent dark:bg-input/30` (white at 3%) does not help.
  - **Inset panels:** the `bg-field/60` groups inside cards render `#1E1E1E` on `#1F1F1F`.
    Their edge is 1.15:1 (`border-line-subtle`), or 1.34:1 in `DetailsPanel.tsx:22`, so the
    grouping the redesign intended barely shows. The others are `AccountCard.tsx:150`,
    `BillingPage.tsx:406`, `AiSettingsPage.tsx:154`, `AgentSettingsPage.tsx:113,154,170,360`
    and `settings/workspace/page.tsx:273`.
- **Affected:** 63 inputs (47 primitive and 16 raw, B.2) and 9 inset panels.
- **Recommendation:**
  - give text fields a boundary at about 3:1 (white at about 33% on panel) or a clearly different
    fill (`bg-canvas`)
  - give inset panels `border-line` or `bg-raised`
  - colour belongs to the colour audit, so treat this as a joint item

### RAD-004

**P2. Chip radii are mixed.**

- **Problem:**
  - **Radii:** chips and badges use `rounded-full` (65), `rounded-md` (21: `ReplyWindowChip.tsx:14`,
    `ListHeader.tsx:95`, `PlatformStrip.tsx:47`, `MediaTray.tsx:215–234`,
    `cell-extras.tsx:54,117`, `WeekView.tsx:257,280`, `UpgradeAction.tsx:18` …), `rounded-lg`
    (4) and 4 px (3: `ConversationRow.tsx:104`, `WorkspaceMenu.tsx:26`, `AccountCard.tsx:123`).
  - **Inbox:** the reply-window chip (`ReplyWindowChip.tsx:14`, 6 px corners, 11 px text) sits
    in the same thread header as pill chips with 12 px text (`ThreadHeader.tsx:69,108`).
  - **Primitive:** `Badge` uses `rounded-4xl` (32 px, effectively a pill) and has no importers.
- **Recommendation:** status and signal chips `rounded-full`; thumbnail and `kbd` labels
  `rounded-sm`. Make `Badge` the only chip implementation (with TYP-007 and SPC-007).

### RAD-005

**P2. Button corners change with size, and the `--radius` knob is dead.**

- **Problem:**
  - **By size:** `Button` default and `lg` are `rounded-lg` (8 px). `xs`, `sm`, `icon-xs` and
    `icon-sm` use `rounded-[min(var(--radius-md),10px|12px)]`, which resolves to 6 px
    (`ui/button.tsx:25–32`). An `sm` and a default button side by side (common in card footers;
    `sm` is used 65 times) have different corners.
  - **Raw buttons:** `rounded-md` (20), `rounded-full` (16), `rounded-lg` (12) and `rounded-xl`
    (2).
  - **The dead knob:** `:root { --radius: 0.5rem }` (`globals.css:111`) is never mapped to
    `--radius-*`, so changing it does nothing.
- **Recommendation:** buttons `rounded-lg` at every size except icon-only round buttons
  (`full`). The spec's "small buttons `rounded-md`" can stay if the owner prefers, but then use
  plain `rounded-md`, not the `min()` expression. Delete or wire `--radius`.

### RAD-006

**P2. Each border colour has two names; overlay overrides are dead; one popover has a double
edge.**

- **Problem:**
  - **Two names:** primitives use shadcn aliases (`border-input`, `border-border`,
    `border-ring`, `ring-ring`, `ring-foreground/10`, `border-destructive`,
    `ring-destructive/20`). App code uses tokens (`border-line`, `ring-brand`, `border-danger`)
    and sometimes the aliases: 19 alias uses in 15 app files, for example `ring-ring/50` in
    `MetricTile.tsx`, `PostCard.tsx` and `AutomationRow.tsx`. They resolve to the same values,
    so the same intent is spelled two ways.
  - **Dead overrides:** 50 overlay call sites (Dialog 12, AlertDialog 13, Popover 11,
    DropdownMenu 14) add `border-line bg-panel`. The primitives draw their edge with
    `ring-1 ring-foreground/10` and have no border width, so `border-line` is a no-op and
    `bg-panel` equals `bg-popover`.
  - **Double edge:** `home/RangeControl.tsx:62` adds `border`, giving a 1 px border plus a
    1 px ring.
- **Recommendation:** pick the token names for app code and keep aliases only inside
  `components/ui`. Remove the no-op overrides after SHD-003.

### RAD-007

**P2. The "selected" accent bar has five implementations.**

- **Problem:**
  - `ConversationRow.tsx:68`: a 3 px `<span>`, full height, square
  - `sidebar-styles.ts:13`: 2 px `before:` pseudo-element, inset 8 px, rounded
  - `Threads.tsx:183`: a 2 px inset `box-shadow`
  - `CalendarPostCard.tsx:85`: `border-l-2` (status colour)
  - `SettingsCard.tsx:47`: `border-l-4` (danger)

  Spec UX-INB-04 described the inbox bar as `shadow-[inset_-2px_0_0_…]` (right side, 2 px);
  C-063 moved it left.
- **Recommendation:** one `SelectionBar` style: 2 px, brand, leading edge, inset 8 px, rounded.
  Status edges on cards use `border-l-2`. The danger card uses `border-l-2` too, or a tinted
  border, but not 4 px.

### RAD-008

**P3. Nested radii ignore padding.**

- **Problem:** inset panels use nearly the parent card's radius, with no allowance for the
  padding between them: `rounded-xl` (12 px) inside `rounded-2xl p-5` (`AccountCard.tsx:150`
  inside `:99`), and `rounded-xl` panels inside the `rounded-2xl p-5 md:p-6` settings cards
  (`BillingPage.tsx:406`, `settings/workspace/page.tsx:273`, `AgentSettingsPage.tsx:154,170`).
  Concentric corners look slightly off.
- **Recommendation:** inner radius = outer − padding, so an inset panel in an `xl` card is
  `rounded-lg`.

### RAD-009

**P3. Small border inconsistencies.**

- **Problem:**
  - **Row dividers:** `divide-line-subtle` in Billing, Home and Comments, `divide-line` in the
    Schedule lists (`AgendaView.tsx:75`, `ListView.tsx:157`, `HashtagGroupsDialog.tsx:92`).
  - **Empty slots:** `border-dashed` (5) against `border-dotted` (`AgendaView.tsx:102`,
    `cell-extras.tsx:54`).
  - **Platform-badge cut-out:** `border-2 border-panel` (`ContactAvatar.tsx:49`) against
    `ring-2 ring-panel` (`AccountCard.tsx:112`, `InboxPreview.tsx:45`). The border version
    shrinks the glyph.
  - **Deprecated bare `rounded`:** 7 uses of what v4 lists as a deprecated default.
  - **Stray radii:** `rounded-3xl` (`FinalCta`), `rounded-[10px]` (`marketing/primitives.tsx`).
- **Recommendation:** fold these into the B.5 and B.6 rules when the files are next touched.

### SHD-001

**P1. The modal scrim is `bg-black/10`.**

- **Problem:**
  - **The default:** `Dialog`, `AlertDialog` and `Sheet` dim the page with `bg-black/10` plus a
    `backdrop-blur-xs` (`ui/dialog.tsx:42`, `ui/alert-dialog.tsx:39`, `ui/sheet.tsx:40`). That
    is shadcn's light-theme default.
  - **The effect:** on this UI it turns the panel behind a dialog from `#1F1F1F` to `#1C1C1C`,
    a 1.03:1 change. The dialog (`#1F1F1F`, no shadow, a 10% ring) then sits on an almost
    unchanged page, and the modal state is hard to read.
  - **The spec:** UX-SH-02 asks for a `bg-black/60` scrim on the mobile drawer, which uses
    `Sheet` (`MobileNav.tsx:36`). The Ask panel, the run detail and Clerk's modals already
    use 60%.
- **Affected:** 12 Dialogs, 13 AlertDialogs, 5 Sheets (the mobile nav among them).
- **Recommendation:** `bg-black/60` in the three primitives; the blur is optional. Add
  `shadow-overlay` (C.2).

### SHD-002

**P2. Tailwind shadows do nothing visible on these surfaces.**

- **Problem:** every Tailwind shadow up to `xl` is 10% black. On a `#000` canvas a black shadow
  cannot show. On `#1F1F1F` a 10% darkening is about 1.03:1 even at the shadow's darkest point.
  So:
  - The spec's elevation ("popovers, menus and dialogs get `shadow-xl`; incoming bubbles
    `shadow-sm`", §4.2) has almost no visual effect.
  - The 6 `shadow-sm` uses (active tab, segment and platform, incoming and preview bubbles) are
    effectively no-ops.
  - The 21 `shadow-xl` overrides add little beyond the ring.
- **Recommendation:** adopt the dark elevation tokens in C.2 (floating 0.7 alpha, overlay 0.8),
  drop `shadow-sm` from bubbles and segments (or use `shadow-raised`), and update spec §4.2.

### SHD-003

**P2. The same role gets different elevation.**

- **Problem:**
  - **Popovers and menus:** `shadow-xl` where the caller overrides (21) and `shadow-md` where it
    doesn't (`CaptionEditor.tsx:382`, `RangeControl.tsx:62`, `Threads.tsx:96`,
    `WorkspaceMenu.tsx:96`, and all 14 `SelectContent`s). Submenus are `shadow-lg`.
  - **Modals:** sheets are `shadow-lg`, dialogs and alert dialogs have none, and the Ask and
    run-detail panels are `shadow-xl`.
  - **Floating bars:** the save bar is `shadow-2xl shadow-black/40`.

  Five different elevations cover two roles (floating and overlay).
- **Recommendation:** two tokens (floating, overlay) owned by the primitives. Remove every
  call-site `shadow-*` from overlays.

### SHD-004

**P3. Brand glow shadows reach the app.**

- **Problem:** the current plan card stacks `border-brand`, `ring-1 ring-brand-line` and
  `shadow-lg shadow-brand/10` (`PlanCards.tsx:71–72`): three emphasis devices on one edge. Glows
  are otherwise marketing-only (`primitives.tsx:36`, `InboxPreview.tsx:63`, `Pricing.tsx:43`).
- **Recommendation:** in the app, emphasise the current plan with `border-brand` (or the brand
  ring) alone. Keep glows to marketing.

### SHD-005

**P3. `box-shadow` used for non-elevation jobs is undocumented.**

- **Problem:** `Threads.tsx:183` draws the selection bar with an inset shadow (see RAD-007).
  `CropDialog.tsx:150` dims the area outside the crop box with a 9999 px spread. Both work, but
  they are one-offs that later readers may mistake for elevation.
- **Recommendation:** the selection bar follows RAD-007. Keep the crop mask, with a comment, or
  make it a named `@utility` in `globals.css`.
