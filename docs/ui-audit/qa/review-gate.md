# UI-044 · Design-system review gate

Reviewer: Final Design-System Reviewer. Branch `feature/ui-review-gate`, reviewing `6c42dd3` (the
Wave 3 tip: Waves 0-3, UI-001 to UI-042). Report only: no stack, no build, no screenshots. Method:
`git grep` (ripgrep was not on this machine's shell path; the patterns are the §D.4 ones) across
`apps/web/src`, test files excluded unless a row says otherwise, plus reading `components/ui/*`,
`styles/globals.css`, `styles/tokens.ts` and the call sites the greps pointed to.

## 1. Verdict: Approve Wave 4 with conditions

Wave 3 landed the system well. Every mechanical §D.4 acceptance check is at **zero** across the
whole app, not just the swept areas. There is no palette utility, no `text-[…]`, no `text-white`,
no `bg-white/N` or `bg-black/N`, no `transition-all`, no backdrop blur, no `dark:` in app code, no
shadcn alias in app code, no `cn` from anywhere but `@/lib/utils`, no call-site overlay surface or
shadow, no Skeleton colour override, no touch patch (`md:min-h-`, `md:size-`), and no `title`
standing in for a tooltip on a control. The primitives match the §8.2 API tables, `globals.css`
matches the §1 token tables, and every token is used. The 86 class-assertion tests were
rewritten deliberately (none deleted, no `.skip`/`.todo`).

What is left is the **B-task residue** (hand-built look-alikes of Badge, Card, Field and Spinner
in the Agent/Ask files and a few shell and schedule spots), 17 owner decisions of which 8 are
applied, 3 partly applied and 6 pending their Wave 4 or 5 task, and a handful of small spec edits.
None of it blocks Wave 4.

**Conditions** (all small; none needs a new Wave 4 task before Wave 4 starts):

1. Fold the RG items below into the named Wave 4/5 briefs (table in section 4). Nine attach to
   existing tasks (RG-05, 06, 08, 11, 12, 13, 14, 17, 18); seven become one new "Wave 3 residue"
   task (RG-01, 02, 03, 04, 09, 10, 15) that runs after UI-067 has touched the Agent files (E.2
   rule 3); RG-07 is its own small task.
2. RG-02 needs a Badge `media` tone (a primitive change) before the residue task, and RG-07 (error
   boundaries do not report to Sentry) is a production-visibility gap that should ship soon,
   independent of the UI programme.
3. UI-050, UI-052 and UI-065 must start from the current Wave 3 code, not the mockups, because
   they rewrite files that already carry the new primitives (MessageBubble, ListHeader, the
   editor and composer page headers).

## 2. Check tables

### 2.1 The §D.4 `rg` acceptance checks, whole app

Counts are matching lines in non-test files under `apps/web/src`. "Area" is the directory.

| Check | Hits | Where | Class |
|---|---:|---|---|
| `bg-brand-gradient` on a Button or AlertDialogAction | 0 | the only gradient on a Button is the `default` variant itself (`ui/button.tsx:19`); the 23 other `bg-brand-gradient` uses are bubbles, count badges, the sidebar Ask tile and marketing | clean |
| `md:min-h-`, `md:size-N`, `md:h-N` touch patches | 0 | `sm:min-h-8` 1 in `marketing/SiteFooter.tsx:10` (a link, marketing) | clean |
| `border-line bg-panel` / `shadow-*` / `max-h-*` on overlay content | 0 | 15 `*Content` call sites pass only widths and padding; the one `max-h-[calc(100dvh-2rem)]` pair is in `ui/dialog.tsx` and `ui/alert-dialog.tsx` | clean |
| `text-[` | 0 | | clean |
| `text-white` | 0 | (only in primitive tests asserting its absence) | clean |
| `bg-white/` | 0 | | clean |
| `bg-black/` | 0 | `src/test/overlays.ts:36` asserts its absence | clean |
| `ring-ring/50`, `ring-3`, `focus:ring`, `focus-visible:ring`, `ring-offset` as a focus halo | 0 | 2 `ring-offset-1` in `schedule/post-parts.tsx:63,98` are the avatar identity ring, not focus | clean |
| `outline-none` / `outline-hidden` without a focus replacement | 17 lines | all allowed: 6 `<main tabIndex=-1>` skip-link targets (4 marketing, `ShellFrame`, `unsubscribe` +comment); 4 Radix content roots (`ui/dialog`, `ui/alert-dialog`, `ui/popover`, `AskPanel`); 4 wrapper-draws-focus (`Composer:329`, `AskComposer:113`, `ui/chip-input:309`, `settings/workspace/page.tsx:192`); `AutomationRow:186` (replacement is `focus-visible:after:outline-2`); `AppSidebar:237` (hidden overlay button, wrapper draws it); `ui/button.tsx` (a comment) | allowed (see DS-12) |
| `transition-all`, `backdrop-blur`, `blur-` | 0 | marketing header blur is the documented exception and was not grepped here | clean |
| `dark:` | 0 | `ui/avatar.tsx:19` is a comment | clean |
| Palette utilities (`bg-red-500`, `text-white`, …) | 0 | | clean |
| Hex / `rgb()` literals outside tokens | 17 lines | `marketing/og.tsx:7-16,32,46` (10 hex + a gradient), `app/layout.tsx:20` (`themeColor`), `app/manifest.ts:17,18` | allowed mirrors per §1.12(6), **but** og.tsx is neither imported from `styles/tokens.ts` nor tested (**RG-12**) |
| Arbitrary values for text, radius, shadow, colour | 8 | 4 marketing radial gradients (`Hero:40`, `AutomationShowcase:42`, `LazyIllustration:37`, `moving-border:33`, all `var(--color-…)` stops), `rounded-[inherit]` `schedule/CalendarPostCard:55`, `tracking-[0.14em]` ×2 `marketing/SiteFooter:35,49` | marketing glows: allowed (Hero's own glow is C-068; the others need a DS line, **DS-13**); `tracking-[0.14em]`: deviation **RG-13** |
| Arbitrary layout values (`max-w-[…]`, `w-[…]`, `grid-cols-[…]`, `h-[…]`, `left-[…]`) | 89 app, 45 marketing | `max-w-[1200px]` ×10 (known UI-060), editor and inbox pane widths (known UI-065), `min-h-[60vh]` ×8 on error/empty states (**RG-14**), `WeekView:132` `h-[calc(100dvh-260px)]` (**RG-14**), the rest are one-off grids and offsets | known / allowed layout |
| shadcn alias names in app code (`border-input`, `ring-ring`, `text-destructive`, `bg-popover`, …) | 0 outside `components/ui` | | clean |
| `cn` imported from outside `@/lib/utils` | 0 | no `clsx` / `tailwind-merge` import outside `lib/utils.ts` either | clean |
| `bg-{status}/10\|15` | 1 app | `DeleteAccountDialog:130` `border-danger/30` (a border, an inset panel; folds into RG-03). Marketing `Illustrations.tsx:54,55,201` use `bg-success/15`, `bg-warning/15` | deviation (small) |
| Opacity on text tokens (`text-fg-secondary/70`) | 0 | | clean |
| `opacity-50..80` on a container with text | 4 | `MessageBubble:102` (`pending && opacity-80`, known follow-up, UI-050/068), `StatsPane:164` (chart bar column), `MediaLibraryDialog:133` (disabled tile), `SchedulePage:482` (hidden-account toggle) | known / allowed |
| Local eyebrow strings, `tracking-[0.12em]` | 0 | `EYEBROW` is imported in 27 files; the sidebar labels now use it | clean |
| Unguarded animation (no `motion-safe:`/`motion-reduce:`) in app code | 0 | `AskPanel:94` uses a bare `motion-reduce:animate-none` that loses to `data-open:animate-in` | known UI-067 |
| Hover-only controls without `pointer-fine:` | 1 | `agent/RunView.tsx:57` (a timestamp that exists only on hover or focus-within; invisible on touch) | deviation **RG-05** |
| Raw `<input>`, `<textarea>`, `<select>` | 11 | 4 radios (allowed, §8.5), 4 file inputs (`sr-only`/`hidden`), 3 composer/Ask textareas inside a wrapper that draws the field look and focus (allowed, §8.3), 1 inline title input (`AutomationEditor:251`, see RG-08). No raw `<select>` | allowed |
| Raw `<button>` | 26 files | rows, tiles, chips and menu triggers that follow the touch and focus rules ("left by design", UI-040). 3 are text links that should be `Button variant="link"` (`settings/workspace/page.tsx:230`, `ai/SuggestionCard.tsx:144`, `composer/PostPreview.tsx:266`) | allowed, plus **RG-09** |
| `title=` on a control carrying meaning | 1 | `agent/AgentSettingsPage.tsx:374` (`<time title=…>` is the only place the exact time appears) | deviation, folds into RG-05 |
| `window.confirm` | 2 | `PostComposer:537`, `settings/SaveBar:36`: the leave-page warning, allowed by C-066 | allowed |
| `Loader2` / `LoaderCircle` instead of `Spinner` | 6 | `agent/StepList:12`, `agent/Threads:45`, `billing/CheckoutReturn:60`, `(marketing)/unsubscribe/UnsubscribeResult:57`, `inbox/MessageBubble:34`, plus `HomeScreen:101` (`RefreshCw`, approved C-065). All are `motion-safe:`; the issue is the second implementation | deviation **RG-10** |
| `isPending ? <Spinner/>` inside a Button instead of `loading` | 4 | `AgentDraftDialog:156`, `AutomationEditor:272,276`, `MatchTester:84` | deviation **RG-10** |

**Per-area totals of hand-built look-alikes** (the §D.4 "B tasks" bullet; counted by pattern, so
read them as sizes, not exact figures):

| Area | Cards / insets | Badges / chips | Label + control not on Field | Spinner / loading | Notes |
|---|---:|---:|---:|---:|---|
| `agent` | 11 | 5 | 0 | 3 | UI-040 was A only for most of these files; UI-041 did Alert/Meter and the shell |
| `ai` | 3 | 0 | 0 | 0 | `AiSettingsPage:156,302`, `SuggestionCard:68,133` (a bar; may stay) |
| `automations` | 5 | 0 | 4 | 3 | `WhenStep:50`, `SettingsStep:159`, `ThenStep` select labels, `AutomationsPage:414` bulk bar |
| `composer`, `schedule` | 2 | 6 (media tags) | 0 | 0 | media-scrim labels (RG-02) |
| `connections` | 3 | 0 | 1 | 0 | `DeleteAccountDialog:130,138,158`, `AccountCard:100` |
| `inbox` | 2 | 1 | 0 | 1 | `ScheduledList:139`, `AttachmentTray:76` |
| `shell`, `states` | 3 | 3 | 0 | 0 | `AppSidebar:226,308,347`, `PageSkeleton:14`, `ShellFrame:89` (skeleton of the sidebar) |
| `home`, `comments`, `knowledge`, `settings`, `billing`, `push` | 1 | 0 | 2 | 1 | `TopIntentsCard:40` share bar; `PushSetup:113`, `NotificationSettingsPage:41` (switch rows, fine) |
| `marketing`, `(marketing)` | n/a | n/a | n/a | 1 | out of the app sweep |

### 2.2 Primitive APIs (`components/ui/*` against §8.2)

| Family | Matches DESIGN_SYSTEM? | Notes |
|---|---|---|
| Button | Yes | variants `default, secondary, outline, ghost, soft, destructive, destructive-ghost, link`; sizes `xs…xl`, `icon-xs…icon-lg`; `loading`; `data-slot`, `data-variant`, `data-size`; 40 px on `pointer-coarse:`; no `dark:`; `buttonVariants()` goes through `cn` (fixes the follow-up). `xl` has no `pointer-coarse:` rule (already 40 px). Not a deviation. |
| Spinner, DisabledReason | Yes | DisabledReason is used at all three sites the follow-ups named (`ThreadHeader`, `Composer`, `ConnectWhatsAppButton`) plus 4 more. |
| Input, Textarea, Select, Checkbox, Switch | Yes | sizes `sm, default, lg, xl`; `fieldControlClass` is shared by Textarea, SelectTrigger and ChipInput; date/time `focus-within` look (C-073); checkbox indeterminate; field edge is `--input`. Input text is `text-sm max-md:text-base`, not `text-base md:text-sm` (accepted deviation, **DS-1**). |
| Field | Yes | `Field`, `FieldLabel`, `FieldDescription`, `FieldError`, `density`. Used in 20 files. Adoption is incomplete (**RG-04**). |
| SearchInput, ChipInput | Yes | Escape clears; the Radix-overlay case is a known follow-up. |
| ToggleGroup, Tabs | Yes | `variant segmented \| chips`, `size sm \| default \| xl`. One local copy of the chip look exists: `inbox/ListHeader.tsx:46` `MORE_CHIP` copies it by hand because the More chip opens a menu (**RG-16**, small). |
| Dialog, AlertDialog, Sheet | Yes | `size sm..xl`, `size="panel"`, `data-slot`s, the exits and scrim, `100dvh − 2rem`. The Ask panel is still a custom Dialog (known UI-067). |
| Popover, DropdownMenu, Select content, Tooltip, Sonner | Yes | surface `overlay`, `ring-1 ring-line`, `shadow-floating`; tooltip arrow; toast action 10 s rule in lint. |
| Badge | Yes, with a gap | `tone neutral \| brand \| success \| warning \| danger \| count`, `size sm \| md`, `shape pill \| tag`. There is no tone for labels on photos, so 9 thumbnail labels are hand-built (**RG-02**, **DS-2**). |
| Card | Yes | `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardAction`, `CardInset`, `CardBleed`; `padding standard \| roomy`, `tone default \| danger \| brand`; radius `xl`. `CardInset` padding is `standard \| compact` (p-4, p-3), not named in the spec (**DS-8**). |
| Alert | Yes | `tone`, `variant soft \| outline`, one action slot, dismiss. |
| Meter, Progress | Yes | `kind consumable \| slot`, `role="meter"`, `role="progressbar"`. `home/TopIntentsCard.tsx:40` draws a share bar by hand because neither fits (**DS-9**). |
| Table | Yes | adopted by SourcesCard, PaymentHistory, Ask Markdown. The two `<table>` in `privacy/page.tsx` are static legal markup; `StatsPane:180` is an `sr-only` chart table. Allowed. |
| Skeleton, Avatar, EmptyState/ErrorState | Yes | no colour override at any of 114+ call sites. `PageSkeleton:14` hand-builds a card instead of using Card (**RG-03**). |

Call-site re-implementation of a primitive: **none** of colour, height, radius, focus or
elevation on Button, Input, Select, Tabs, ToggleGroup or any overlay. The only call-site class
overrides on Buttons are text colours: `text-fg-secondary` on 9 ghost Buttons (AskPage,
AskPanel, Threads ×3, BillingPage:242, Composer:400, ScheduleRail:166, ThreadHeader:89) and
`text-brand-fg` on 2 (CaptionEditor:381 "Write with AI", AnalysisChips:118 "Correct the AI"),
which are AI actions that should be `variant="soft"` per C-073 (**RG-09**, **DS-7**).

### 2.3 Owner decisions D-01 to D-17 against the code

| ID | Decision | Status | Evidence |
|---|---|---|---|
| D-01 | `line-control`, `--input` | **Applied** | `globals.css:34,180`; Checkbox/Radix edges use `border-input`; workspace slug wrapper `border-line-control` |
| D-02 | cards `rounded-xl` | **Applied** (cards) | `ui/card.tsx` `rounded-xl`; `SaveBar` is now `rounded-xl`. `PreviewPane:67` is a `rounded-2xl` mock-up phone frame, fine |
| D-03 | dark tooltip | **Applied** | `ui/tooltip.tsx:38` `bg-overlay ring-1 ring-line shadow-floating` |
| D-04 | native date/time via Input | **Applied** | `ui/input.tsx` `PICKER_TYPES`; composer fields go through ScheduleFields |
| D-05 | 24 px page H1, 18 px pane H1 | **Partly** | PageFrame, Home, Schedule, Composer 24 px; Inbox 18 px. Settings keeps `md:text-3xl` (`SettingsPageHeader:51`), Ask page H1 is `text-base` (`AskPage:51`), the editor's name input is `text-xl`; owner task UI-069 |
| D-06 | placeholders `fg-secondary` | **Applied** | `globals.css:203`; primitives use `muted-foreground` |
| D-07 | "Sent by AI" / "Automation · {name}" | **Pending** | `MessageBubble:241` still renders "AI Assisted"; `lib/inbox/format.ts:32` "Auto: "; `AiSettingsPage:138` — task UI-050 |
| D-08 | drop settings breadcrumb, eyebrow, etc. | **Pending** | `SettingsPageHeader:35,50` breadcrumb and brand eyebrow still there — UI-060 |
| D-09 | Disconnect visible; "Delete account and data" in ⋯ | **Pending** | string absent from the code — UI-062 |
| D-10 | one gradient primary per view region | **Pending** | `default` is the gradient everywhere; row and card actions not yet audited — UI-059 |
| D-11 | `needs_reply_count` on posts | **Pending** | no `needs_reply_count` / `needs_reply` comment filter in the client — UI-055 |
| D-12 | `overlay` surface, two shadows | **Applied** | tokens, every overlay primitive, SaveBar, drag preview, toast; no call-site `shadow-*` |
| D-13 | three identity pairs | **Applied** | `lib/ui/identity.ts`; ContactAvatar, AccountAvatar, schedule rings and dots read it. Known: the composer picker colours accounts by id hash and Schedule by order (UI-032/033 note) |
| D-14 | single-key shortcuts switch | **Pending** | `use-inbox-shortcuts.ts` has no setting — UI-053 |
| D-15 | neutral platform segment, heart in the emoji popover, composer-only scheduling, Archived chip | **Partly** | item 1 applied (`PlatformStrip` is a segmented ToggleGroup, `raised` + `brand-fg`); heart still a composer tool (`Composer:360`), Archived still under More (`ListHeader:34`) — UI-051/052 |
| D-16 | back link, panel after steps, icon buttons `rounded-lg`, composer `rounded-xl` | **Partly** | Button `icon-*` sizes are `rounded-lg`/`md`; inbox Composer shell `rounded-xl`; Ask composer still `rounded-2xl` with a `rounded-full` Send (`AskComposer:25,98`); raw `rounded-full` icon buttons remain in `AttachmentTray:65,76`, `SuggestionCard:233`, `AnalysisChips:33`, `PostPreview:228,238`; editor and composer still use a "Breadcrumb" nav (`AutomationEditor:245`, `PostComposer:580`) — UI-065 |
| D-17 | system Devanagari fallback; `latin-ext` | **Applied (no change)** | UI-010 was dropped after measuring (coordinator note); nothing to apply |

Applied 8 (D-01, D-02, D-03, D-04, D-06, D-12, D-13, D-17), partly 3 (D-05, D-15, D-16),
pending 6 (D-07, D-08, D-09, D-10, D-11, D-14).

Later `C-0xx` entries checked: C-070 (token foundation) is complete in `globals.css`; C-071
(D-01/06/12) and C-072 (identity) are in the code as described; C-073's five follow-ups are all
present (`soft` Button + `brand-soft-hover`, `xl` for ToggleGroup and Tabs, date/time
`focus-within`, the `short:` variant used by `sticky-bar.ts` and `MobileNav`, `shadow-crop-mask`
used by `CropDialog`). `soft` has 4 adopters (AI mode trigger, Polish, Summarize, Ask open) and 2
AI actions still on ghost (RG-09).

### 2.4 Tokens (`globals.css` against DESIGN_SYSTEM §1, §2, §7)

| Item | Result |
|---|---|
| Colour tokens (§1.1-§1.6) | All 39 present with the documented values. None missing, none misnamed. |
| Additions (§1.13) | `hover, pressed, scrim, media-scrim, on-brand, brand-strong, *-soft, text-2xs, text-md, ease-*, wide, short:, brand-soft-hover, shadow-crop-mask, shadow-floating, shadow-overlay` all present. |
| Unused tokens | **None.** Every colour token is referenced by an app utility or a primitive (checked by grep). `bg-glow-brand` has one use (BillingPage plan hero), which respects "one per view". |
| shadcn alias map (§1.10) | Matches the target column: `--primary` brand-strong, `--primary-foreground` on-brand, `--accent` hover, `--popover` overlay, `--input` line-control; the four `*-foreground` aliases are mapped. `--radius` is commented inert. |
| Motion | `--motion-*`, the three duration utilities, the reduced-motion safety net on `[data-slot$="-overlay"]`, `-content`, `skeleton` are all there. |
| Dark / light readiness (§1.12) | Items 2-5 hold (overlay states, `on-brand`, gradients as `var()`, no `dark:`). Item 1 (switch off Tailwind's default palette with `--color-*: initial`) is **not done**; it is now safe because no palette utility remains. Owner: UI-070. Item 6: `og.tsx` is not tied to `tokens.ts` (RG-12). |
| Contrast notes | Documented pairs hold. Open items already in the follow-ups: `fg-secondary` on `pressed` is 4.45:1 (neutral badges sit on `hover`; nothing in app code puts secondary text at rest on `pressed`); the decor gradient start is 1.30:1 on meters (UI-071); the Facebook ring is 2.78:1 on a raised calendar card (3.19 on panel; UI-027 FYI); the sending bubble `bg-brand/60 text-on-brand` plus `opacity-80` (`MessageBubble:101,102`) puts text on a semi-transparent brand fill, against §1.11 "never text on brand" (follow-up "unassigned"; **RG-11**). |
| Stylistic | `PostPreview:253` uses `bg-fg-disabled` for the carousel's inactive dot; `fg-disabled` is "disabled controls only" (**RG-15**). |

### 2.5 Class-assertion tests (§H)

| Check | Result |
|---|---|
| Count | 425 `toHaveClass` assertions in 61 files now, against 92 in 20 files before UI-001 (`bef8769^`). 264 of them are in the new primitives' own tests (`components/ui`), 161 in feature tests. AGENT_CONTEXT §11 and §H still say "86 in 18 files" (**DS-10**). |
| Deleted or disabled | None. No deleted test file under `apps/web/src` since UI-001 (two source files were deleted, no tests); no `it.skip`, `describe.skip`, `.only`, `.todo` in `apps/web/src`. |
| `inbox/PlatformStrip.test.tsx` (was 5, now 3 class assertions) | Rewritten deliberately for UI-030/D-15: roles `group` → `radiogroup`, `grid-cols-N` → `data-slot`/`data-size`/`flex-1`, `bg-brand` → `data-[state=on]:bg-raised`, plus a new "choosing the chosen segment again" test. Comments cite C-063/D-15. |
| `agent/AskPanel.test.tsx` (was 21, now 20) | Rewritten: `text-[15px] leading-7` → `text-md`; notice pill classes → `data-slot="alert"`/`data-tone`; `size-10`, `min-h-10 md:min-h-7` → `size-8 pointer-coarse:size-10`, `pointer-coarse:min-h-10`; composer `focus-within:ring-3` → `has-[textarea:focus-visible]:outline-brand`. One class assertion became an attribute assertion (the notice), the rest map one to one. |
| `inbox/ThreadHeader` 6→12, `ConversationRow` 6→8, `InboxShell` 5→8, `SchedulePage` 1→5 | Grew (soft tokens, selection-bar test id, pane widths, `size-10`), as §H expects. `InboxShell` pane widths pass unchanged as required. |
| Others in the §H table | `ActionCardView`, `AskPage`, `PostDetailPage`, `CommentsPage` unchanged in count; their lines were edited by UI-040/UI-038/UI-039 per the history. |

## 3. Known deviations (already routed in `ui-followups.md`) still open on `6c42dd3`

Marked "known" so the owning task closes them; they are not new RG items.

| Deviation | Evidence | Owner |
|---|---|---|
| Ask panel is a custom Dialog; bare `motion-reduce:animate-none` loses to `data-open:animate-in`; no `data-slot`; arbitrary `md:w-[420px]`; RunDetailSheet width `md:w-140` | `AskPanel.tsx:94` | UI-067 |
| UpgradeDialog focus after Esc | `components/billing` | UI-063 |
| "AI Assisted", "Auto:" labels | `MessageBubble:241`, `lib/inbox/format.ts:32`, `AiSettingsPage:138` | UI-050 |
| Settings breadcrumb, eyebrow, `md:text-3xl` | `SettingsPageHeader:35,50,51` | UI-060, UI-069 |
| Editor and composer "Breadcrumb" nav, `max-w-[1200px]` ×10 | `AutomationEditor:245`, `PostComposer:580` | UI-065, UI-060 |
| "Writes arrive in a later release", "Coming later" (roadmap copy is a rejected pattern) | `AgentSettingsPage:135,187` | UI-068 |
| `window.confirm` leave-page warning (allowed, C-066) | `PostComposer:537`, `SaveBar:36` | none |
| Sending bubble `bg-brand/60` + `opacity-80` | `MessageBubble:101,102` | UI-050 or UI-068 |
| Heart in the composer, Archived under More | `Composer:360`, `ListHeader:34` | UI-051, UI-052 |
| PlanCards `border-line-subtle bg-panel/50`, menu item weight 400, Dialog `lg`/`xl` titles `text-lg`, Clerk hover 90%, `xl` = `px-4`, secondary open state | `PlanCards:76`, `floating.ts` | UI-071 (spec to confirm) |
| `ProBadge` `text-[11px]` in TemplateGallery | no `text-[` remains anywhere | closed by UI-035 |
| Duplicate on a dirty post bypassing the leave guard, Unschedule/Publish confirm gradient overrides | fixed (`PostComposer:537`, `:831,844` default Action) | closed |
| AlertDialogAction rendering blue for a destructive action | fixed (`variant="destructive"` at 8 sites; `Button` merges the child's class) | closed |
| Skip links use `bg-brand-strong text-on-brand` | `ShellFrame:53`, `(marketing)/layout.tsx:25` | closed |
| Local eyebrow in the sidebar | uses `EYEBROW` | closed |
| `[@media(max-height:500px)]` | replaced by `short:` | closed |

## 4. New deviations: proposed follow-up tasks

Priority: P1 breaks a user-visible rule or production visibility; P2 spec drift a reviewer would
reject today; P3 tidy-up. Files are line references on `6c42dd3`.

| ID | Pri | Deviation and files | Fix | Task |
|---|---|---|---|---|
| RG-01 | P2 | Hand-built status/count badges: `agent/RunTrace.tsx:30,158` (rounded-full + `TONE_CLASS`), `agent/Threads.tsx:51` (count pill), `agent/AnswerText.tsx:80` (citation chip), `shell/AppSidebar.tsx:226` (AI micro-label), `:308` (count badge with `bg-brand-gradient`), `:347` (reconnecting pill) | `Badge` (`tone`, `count`, `shape`); keep the collapsed sidebar count's `h-4 text-2xs` as a documented Badge compound variant, or a `className` size override that the spec allows (see DS-3) | new "Wave 3 residue" (Agent files after UI-067) |
| RG-02 | P2 | Labels on photos and video are hand-built with `bg-media-scrim/N`: `composer/MediaTray.tsx:213,217,234`, `composer/MediaLibraryDialog.tsx:147,157`, `composer/PostPreview.tsx:219`, `automations/steps/PostsStep.tsx:262`, `inbox/AttachmentTray.tsx:76` | add Badge `tone="media"` (`bg-media-scrim/70 text-on-brand`, `shape="tag"`) in `ui/badge.tsx` (primitives owner), then adopt at the 9 sites | new, primitive first, then residue task |
| RG-03 | P2 | ~38 hand-built cards and inset panels (`rounded-xl|lg border border-line`): `agent/AgentSettingsPage.tsx:113,154,170,247,362`, `agent/RunTrace.tsx:122,152`, `agent/ActionCardView.tsx:105`, `agent/AnswerText.tsx:125`, `agent/AskConversation.tsx:330`, `ai/AiSettingsPage.tsx:156,302`, `automations/AutomationsPage.tsx:414` (bulk-action bar), `automations/steps/ThenStep.tsx:667`, `connections/DeleteAccountDialog.tsx:130,138`, `connections/AccountCard.tsx:100` (`bg-panel/60` on a Card), `inbox/ScheduledList.tsx:139`, `states/PageSkeleton.tsx:14` | `Card` for standalone surfaces, `CardInset` for groups inside a card, `Alert` for the bulk bar; `Card tone="danger"` for the Deleted panel; keep real rows and tiles that are buttons (`AgentSettingsPage:362`, `AskConversation:330`) as they are and document them | new "Wave 3 residue" |
| RG-04 | P2 | Label + control pairs wired by hand: `automations/steps/WhenStep.tsx:50`, `SettingsStep.tsx:159`, `ThenStep.tsx` select labels, `connections/DeleteAccountDialog.tsx:158` (typed confirm) | `Field` / `FieldLabel` / `FieldError`; `useFieldControl` already feeds Input and Select | UI-035 residue → new "Wave 3 residue" |
| RG-05 | P2 | Meaning only on hover or focus: `agent/RunView.tsx:57` (question time `opacity-0` until hover or focus-within, no `pointer-fine:`), `agent/AgentSettingsPage.tsx:374` (`<time title=…>` is the only place the exact time shows) | show the timestamp always (`text-2xs text-fg-secondary`) or behind `pointer-fine:` with a visible touch path; use `Tooltip` plus visible text instead of `title` | UI-067 (Ask files) |
| RG-06 | P2 | Typed-scale breaks: `text-xl` at `automations/AutomationEditor.tsx:262` (the page title input), `agent/AskConversation.tsx:311` (empty-state H2), `automations/StatsPane.tsx:94` (KPI); `text-3xl` at `billing/PlanCards.tsx:94` (price); `agent/AskPage.tsx:51` H1 is `text-base` (pane title is 18 px, D-05); settings H1 `md:text-3xl` (known) | `text-2xl` for page titles and KPI figures; `text-lg` for the section and pane titles; a plan price as the KPI role | UI-069 (D-05), UI-065 (editor) |
| RG-07 | P1 | The route error boundaries do not report: `app/(app)/error.tsx`, `app/(app)/w/[slug]/error.tsx` call `ErrorState onRetry={reset}` with no `Sentry.captureException`; no `global-error.tsx` exists (a root layout crash shows Next's default page). Raised in the Wave 3 notes as "small fix soon", never assigned | `captureException(error)` in a `useEffect` in both boundaries, add `global-error.tsx` using the same `ErrorState`; keep the scrub rules | new, small, not UI-visual |
| RG-08 | P3 | Second implementation of a chip: `inbox/ListHeader.tsx:46` `MORE_CHIP` copies `ui/toggle-group`'s chip classes | export the chip class (or a `ChipButton`) from `ui/toggle-group.tsx` so one place changes it | UI-052 |
| RG-09 | P3 | Ghost Buttons with a text-colour override: `text-fg-secondary` ×9 (`AskPage:40,53`, `AskPanel:104,110`, `Threads:78,98`, `BillingPage:242`, `Composer:400`, `ScheduleRail:166`, `ThreadHeader:89`) and `text-brand-fg` ×2 on AI actions (`composer/CaptionEditor.tsx:381` "Write with AI", `ai/AnalysisChips.tsx:118` "Correct the AI"). Three raw text-link buttons: `settings/workspace/page.tsx:230`, `ai/SuggestionCard.tsx:144`, `composer/PostPreview.tsx:266` | AI actions → `variant="soft"` (C-073); link buttons → `variant="link"`; the muted ghost needs a DSA decision (DS-7) | new, with the DSA |
| RG-10 | P3 | Second implementation of the spinner/loading state: `LoaderCircle` at `agent/StepList:12`, `agent/Threads:45`, `billing/CheckoutReturn:60`, `(marketing)/unsubscribe/UnsubscribeResult:57`, `inbox/MessageBubble:34`; manual `isPending ? <Spinner/>` in `AgentDraftDialog:156`, `AutomationEditor:272,276`, `MatchTester:84` | `Spinner` (inside status icon maps it is fine to keep `LoaderCircle` if DS-14 allows it); `Button loading` for the four | new "Wave 3 residue" |
| RG-11 | P3 | Motion tidy: `inbox/MessageBubble.tsx:130` `motion-safe:duration-150` (use `duration-normal`); `automations/AutomationRow.tsx:134` `transition-opacity` is unnamed; pending bubble `bg-brand/60 text-on-brand` + `opacity-80` (text on translucent brand; known follow-up) | tokens; for the pending bubble use `bg-brand-gradient` at full opacity and show "Sending" in the meta line | UI-050 |
| RG-12 | P3 | `marketing/og.tsx:6-16,32,46` writes token hex values out by hand and nothing ties them to `styles/tokens.ts`; `app/layout.tsx:20` `themeColor` has the same issue (the manifest is tested) | import `colorTokens` as `lib/clerk-appearance.ts` does, or add a test comparing them | UI-070 |
| RG-13 | P3 | `marketing/SiteFooter.tsx:35,49` uppercase headings use `tracking-[0.14em]` (the spec retired 0.12 em and allows 0.08 em for eyebrows) | `EYEBROW`, or a marketing heading constant in `styles/tokens.ts` | UI-042 residue → UI-070 |
| RG-14 | P3 | Layout rule breaks: `schedule/WeekView.tsx:132` `h-[calc(100dvh-260px)]` (§9: full-height frames are flex children); `min-h-[60vh]` ×8 on EmptyState/ErrorState `className` (`automations/layout`, `knowledge/layout`, `AgentSettingsPage:76`, `AutomationEditor:97`, `PostDetailPage:69`, `NewPost:80`, `PostComposer:130`, `SchedulePage:106`) | a `size="page"` on the state components (or `fullPage`, which ErrorState already has) instead of a per-site min-height; make the week grid a flex child | UI-066 (RSP rules) |
| RG-15 | P3 | `composer/PostPreview.tsx:253` inactive carousel dot `bg-fg-disabled` (token is for disabled controls only) | `bg-line-strong` | UI-033 residue (new) |
| RG-16 | P3 | `Select` pending wording: ThenStep/WhenStep selects use hand labels (RG-04); `automations/AutomationRow` uses `transition-opacity` without a named property (RG-11) | folded into RG-04 and RG-11 | — |
| RG-17 | P3 | Raw `rounded-full` icon buttons that D-16 turns into `rounded-lg`: `agent/AskComposer.tsx:25,125` (Send), `:98` shell `rounded-2xl`; `inbox/AttachmentTray.tsx:65,76`, `ai/SuggestionCard.tsx:233`, `ai/AnalysisChips.tsx:33`, `composer/PostPreview.tsx:228,238` | `Button size="icon-*"` (rounded-lg) or document the circles that stay; the Ask composer shell goes to `rounded-xl` | UI-065 (D-16) |
| RG-18 | P3 | Hand-rolled share bar: `home/TopIntentsCard.tsx:40` (`bg-brand-gradient-decor`, inline width) | `Progress` if a "share" kind is added (DS-9), otherwise keep and document | UI-071 decides |

RG-16 is folded into RG-04 and RG-11 and has no separate task; the ID stays so the numbers match
this review's working notes.

### Top 10 (what to read first)

1. **RG-07** error boundaries do not report to Sentry (P1; new).
2. **RG-03** about 38 hand-built cards and insets, mostly Agent/Ask, Settings AI and the Delete dialogs (P2; new residue).
3. **RG-01** hand-built badges and counts in RunTrace, Threads, AnswerText and the sidebar (P2; new residue).
4. **RG-02** nine thumbnail labels with no Badge tone to use (P2; primitive first).
5. **RG-04** label + control pairs not on Field in the automation steps and the typed-confirm dialog (P2; residue).
6. **RG-05** a hover-only timestamp and a `title`-only time in the Ask run views (P2; UI-067).
7. **RG-06** `text-xl`/`text-3xl` and an Ask H1 at 16 px against the type scale and D-05 (P2/P3; UI-069, UI-065).
8. **RG-09** nine ghost Buttons with colour overrides, two AI actions not on `soft`, three raw link buttons (P3; new with the DSA).
9. **RG-10** a second spinner implementation in six files and four manual in-button spinners (P3; residue).
10. **RG-17** `rounded-full` icon buttons and the Ask composer shell, to D-16 (P3; UI-065).

## 5. What DESIGN_SYSTEM.md itself should change (for UI-071; noted only)

| # | Change |
|---|---|
| DS-1 | §2.1 Input and §8.2 Input: the recipe is `text-sm max-md:text-base`, so `cn` cannot drop the 16 px below `md` (accepted deviation, UI-014). Say so. |
| DS-2 | §8.2 Badge: add the media tone for labels on photos and video (`media-scrim` with `on-brand`), or state what thumbnail labels use. Today `shape="tag"` is described as "thumbnail labels" with no tone to match. |
| DS-3 | §2.1 / §8.2 count badge: the collapsed sidebar's overlaid count is `h-4 min-w-4 text-2xs`; either add a Badge `size` for it or say it is an allowed local size. |
| DS-4 | §6 lists "the jump-to-latest pill" as a level-1 surface; no such component exists. Drop the mention, or add it to a task. |
| DS-5 | §1.12(1): mark the palette switch-off as **not yet done**, owner UI-070, and record that it is now safe (no palette utility remains). |
| DS-6 | §1.1 / §6: the phone drawer is `canvas` with the sidebar card on `panel` (UI-041, owner FYI). §1.1 still says the drawer is `panel`. |
| DS-7 | §8.2 Button: decide the muted ghost (`text-fg-secondary` on ghost, 9 sites) and the AI-action rule for "Write with AI" and "Correct the AI". Either a `quiet` variant or an explicit "colour override is allowed on ghost" line. |
| DS-8 | §3 / §8.2 Card: name `CardInset padding="compact"` (12 px) and `CardBleed`, and state which inset is for rows and which for form groups. |
| DS-9 | §8.2 Meter / Progress: add a "share" bar (ranked distribution, `TopIntentsCard`) or say it stays hand-built. |
| DS-10 | AGENT_CONTEXT §11 and IMPLEMENTATION_PLAN §H: "86 assertions in 18 files" is stale (425 in 61 files, 264 of them in primitive tests). |
| DS-11 | §2.1 Pane title: say which surface the Ask page and the Ask panel are (the page H1 is 16 px today; the table says 18). |
| DS-12 | §8.3 Focus: list the allowed `outline-none` cases (programmatic focus targets such as `<main>` and dialog roots, and wrapper-draws-focus patterns). Today the rule says "primitives don't remove it" and the checklist says "without a focus replacement" without naming these. |
| DS-13 | §1.9: the marketing glows (`LazyIllustration`, `AutomationShowcase`, `moving-border`) are arbitrary radial gradients built from tokens; allow them in marketing explicitly or route them through `bg-glow-brand`. |
| DS-14 | §7.4 / §8.2 Spinner: say whether status-icon maps (`StepList`, `MessageBubble`) may keep a `LoaderCircle` with `motion-safe:animate-spin`. |
| DS-15 | §8.5 RadioGroup: three native radio cards use `accent-brand`; confirm the 3:1 edge on the unchecked radio on panel (`line-control` is not applied to a native radio). |
| DS-16 | §4: `rounded-[inherit]` (CalendarPostCard) and `rounded-sm` on 4 px thumbnails are used; add "inherit" as an allowed value for a child that fills a rounded parent. |

## 6. Counts

| Measure | Count |
|---|---:|
| §D.4 acceptance checks at zero across the whole app | all 8 listed in §D.4 (gradient on a Button, `md:min-h-`, overlay patches, `text-[`, `text-white`, `bg-white/`, `bg-black/`, `ring-ring/50`) |
| §D.4 check with hits that are all allowed | 1 (`outline-none` 17 lines); hex/rgb is 17 allowed mirror lines |
| Known deviations still open | 11 (section 3), plus 6 closed |
| New deviations | 17 RG items (1 × P1, 6 × P2, 10 × P3; RG-16 folds into others) |
| Decisions applied / partly / pending | 8 / 3 / 6 |
| Tokens missing, misnamed or unused | 0 / 0 / 0 |
| Tests deleted or skipped | 0 |
| DESIGN_SYSTEM / AGENT_CONTEXT edits proposed | 16 |
