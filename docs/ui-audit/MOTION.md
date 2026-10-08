# Motion audit (brief §18)

Read-only audit of `apps/web` on `feature/ui-audit` (commit `99f67be`), 1 October 2026. Nothing in
the app was changed. The standard is spec §4.2 "Motion":

> A message that arrives live fades in and rises 4 px over 150 ms; history loads without
> animation. Suggestion card: 180 ms rise from 8 px. Send button: 120 ms scale-in when text
> appears. Sheets and dialogs: 200 ms. Under prefers-reduced-motion, all of these are instant.

Plus UX-SCR-03 (the automation line: 2 s per cycle, static under reduced motion), C-047 and C-065
(the refresh spinner is motion-safe).

**Priorities.** P0: broken or unusable. P1: major. P2: polish. P3: minor.

**Result.** No P0 was found. Motion is small throughout: fades, a 95% zoom and 4–40 px slides.
Nothing in the app flashes or moves in a way that could hurt.

- **Done well.** The three hand-made spec motions (live message, suggestion card, Send) and the
  two loops (automation line, Ask shimmer) are exactly as specified and honour reduced motion.
- **The gap is the primitives.** Every Radix-based overlay (dialog, alert dialog, sheet,
  popover, dropdown, select, tooltip) still animates under `prefers-reduced-motion: reduce`.
  Dialogs run at 100 ms, where the spec says 200 ms. There are no motion tokens, so durations and
  easings drift.

| Priority | Count | IDs |
|---|---|---|
| P0 | 0 | none |
| P1 | 1 | MOT-001 |
| P2 | 4 | MOT-002 to MOT-005 |
| P3 | 4 | MOT-006 to MOT-009 |

## How it was checked

- **Static.**
  - I listed every `animate-*`, `transition*`, `duration-*`, `ease-*`, `motion-safe:` and
    `motion-reduce:` class.
  - I read the enter and exit classes in `components/ui/*`.
  - I read the keyframes in `globals.css`, `tw-animate-css` (`dist/tw-animate.css`, which has no
    reduced-motion rule) and `shadcn/tailwind.css`.
  - I read sonner's stylesheet: it sets `animation: none` and `transition: none` under
    `prefers-reduced-motion`.
- **Runtime.** On the isolated e2e stack (`ACCESSIBILITY.md` › How it was checked), I read the
  computed `animation-name`, `animation-duration` and `transition-duration` of each overlay 20 to
  30 ms after opening it. I did this with `reducedMotion` emulated as `no-preference` and as
  `reduce`.

| Surface | no-preference | reduce | Expected under reduce |
|---|---|---|---|
| Mobile drawer (Sheet, `MobileNav.tsx`) | `enter 0.2s`, overlay `enter 0.1s` | `enter 0.2s`, overlay `enter 0.1s` | none |
| Notifications popover (`PopoverContent`) | – | `enter 0.1s` | none |
| Thread "More actions" menu (`DropdownMenuContent`) | – | `enter 0.1s` | none |
| New automation dialog (`DialogContent`), overlay | – | `enter 0.1s`, overlay `enter 0.1s` | none |
| Ask panel (`AskPanel.tsx`) | slide 0.2s | none (`motion-reduce:animate-none`) | none ✓ |

**CSP.** `style-src 'self' 'unsafe-inline'` (`lib/security/headers.ts:60`, accepted in
`docs/security-checklist.md`) allows inline `style` attributes and the styles sonner injects at
runtime. All keyframes live in compiled CSS, so the proposal below needs no CSP change. Keep new
keyframes and tokens in `globals.css`, and never build them at runtime.

## Inventory

### Primitives (`components/ui/*`)

| Primitive | Enter | Exit | Duration | Easing | Reduced motion |
|---|---|---|---|---|---|
| Dialog overlay (`dialog.tsx:42`) | fade | fade | 100 ms | `ease` (tw-animate default) | **not handled** |
| Dialog content (`dialog.tsx:64`) | fade + zoom from 95% | fade + zoom to 95% | 100 ms | `ease` | **not handled** |
| AlertDialog overlay and content (`alert-dialog.tsx:39`, `:61`) | fade; fade + zoom 95% | the same | 100 ms | `ease` | **not handled** |
| Sheet overlay (`sheet.tsx:40`) | fade | fade | 100 ms | `ease` | **not handled** |
| Sheet content (`sheet.tsx:65`) | fade + slide 40 px from its side | fade + slide 40 px out | 200 ms (`transition duration-200`) | `ease-in-out` | **not handled** |
| Popover (`popover.tsx:32`) | fade + zoom 95% + slide 8 px from the trigger side | fade + zoom 95% | 100 ms | `ease` | **not handled** |
| DropdownMenu and sub-menu (`dropdown-menu.tsx:45`, `:246`) | fade + zoom 95% + slide 8 px | fade + zoom 95% | 100 ms | `ease` | **not handled** |
| Select (`select.tsx:71`) | fade + zoom 95% + slide 8 px (none when item-aligned) | fade + zoom 95% | 100 ms | `ease` | **not handled** |
| Tooltip (`tooltip.tsx:44`) | fade + zoom 95% + slide 8 px, after a 300 ms delay (`app/layout.tsx:33`) | fade + zoom 95% | 150 ms (default) | `ease` | **not handled** |
| Button (`button.tsx:7`) | `transition-all`; `active:translate-y-px` press | – | 150 ms | Tailwind default `cubic-bezier(.4,0,.2,1)` | not handled |
| Input, Textarea, Select trigger, Checkbox (`input.tsx:10`, `textarea.tsx:9`, `select.tsx:45`, `checkbox.tsx:16`) | `transition-colors` | – | 150 ms | default | not handled (colour only) |
| Switch (`switch.tsx:19`, `:26`) | `transition-all`; thumb `transition-transform` | – | 150 ms | default | not handled |
| Badge (`badge.tsx:7`) | `transition-all` | – | 150 ms | default | not handled |
| Skeleton (`skeleton.tsx:7`) | `animate-pulse`, infinite | – | 2 s | `cubic-bezier(.4,0,.6,1)` | **not handled** (117 uses; 11 add `motion-reduce:animate-none`) |
| Toasts (sonner, `app/layout.tsx:34`) | slide and fade (library) | swipe or fade (library) | ~400 ms (library) | library | handled by sonner ✓ |

### The spec's motions and other app-level motion

| What | Where | Motion | Duration and easing | Reduced motion | Spec |
|---|---|---|---|---|---|
| Live inbound message | `inbox/MessageBubble.tsx:127` | fade + rise 4 px (`slide-in-from-bottom-1`); history not animated (`live` prop) | 150 ms, `ease` | `motion-safe:` ✓ | ✓ matches |
| Suggestion bar | `ai/SuggestionCard.tsx:30` | fade + rise 8 px | 180 ms, `ease` | `motion-safe:` ✓ | ✓ matches |
| Send button when text appears | `inbox/Composer.tsx:414` | zoom from 95% | 120 ms, `ease` | `motion-safe:` ✓ | ✓ matches |
| Ask panel and its overlay | `agent/AskPanel.tsx:82`, `:91` | slide 40 px from the right (no fade); overlay fade | 200 ms, `ease` | `motion-reduce:animate-none` ✓ | ✓ 200 ms |
| Run detail sheet (Settings › Agent) | `agent/AgentSettingsPage.tsx:394`, `:399` | the same as the Ask panel | 200 ms | ✓ | ✓ |
| Automation gutter line (active) | `styles/globals.css:57-71` | dashed gradient moving down, infinite | 2 s linear | `@media (reduce) { animation: none }` ✓ | ✓ UX-SCR-03 |
| Ask "current step" label | `styles/globals.css:75-97`, used at `agent/StepList.tsx:86` | text shimmer, infinite | 1.6 s linear | only under `no-preference` ✓ | ✓ |
| Ask current-step dot | `agent/StepList.tsx:84` | `animate-pulse` | 2 s | `motion-safe:` ✓ | – |
| Reconnecting dot | `shell/AppSidebar.tsx:325` | `animate-ping` | 1 s | `motion-safe:` ✓ | – |
| "Publishing" card border | `lib/schedule/format.ts:31` | `animate-pulse` | 2 s | `motion-safe:` ✓ | – |
| Account "Deleting" dot | `connections/AccountCard.tsx:27` | `animate-pulse` | 2 s | **not handled** | – |
| AI credits bar fill | `shell/UsageCard.tsx:96` | width | 500 ms | `motion-safe:` ✓ | – |
| Upload progress bar and ring | `composer/MediaTray.tsx:54`, `inbox/AttachmentTray.tsx:32` | width and stroke-dashoffset | 150 ms | not handled (progress, acceptable) | – |
| Home dims while switching ranges | `home/HomeScreen.tsx:188` | opacity | 150 ms | `motion-safe:` ✓ | – |
| Ask answer actions reveal | `agent/RunView.tsx:56`, `:174` | opacity | 150 ms | `motion-safe:` ✓ | – |
| Ask steps chevron | `agent/RunView.tsx:272` | rotate 90° | 150 ms | `motion-safe:` ✓ | – |
| Ask composer focus glow | `agent/AskComposer.tsx:87` | box-shadow | 150 ms | `motion-safe:` ✓ | – |
| Sidebar rows, workspace menu, Ask card | `shell/sidebar-styles.ts:11`, `shell/WorkspaceMenu.tsx:64`, `shell/AppSidebar.tsx:219` | colours (**including outline-color**, see MOT-008) | 150 ms | `motion-safe:` ✓ | – |
| Automation row while dragging | `automations/AutomationRow.tsx:130` | opacity | 150 ms | not handled | – |
| Schedule account filter avatars | `schedule/SchedulePage.tsx:470` | opacity | 150 ms | not handled | – |
| Composer account chips | `composer/AccountPicker.tsx:70` | colours | 150 ms | not handled (colour only) | – |
| Marketing FAQ chevron | `marketing/Faq.tsx:23` | rotate 180° | 150 ms | `motion-reduce:transition-none` ✓ | – |
| Marketing links and CTAs | `marketing/SiteHeader.tsx:22`, `SiteFooter.tsx:10`, `primitives.tsx:33` | colours and filter | 150 ms | not handled (colour only) | – |
| Spinners (`Loader2` and similar) | 30 unguarded, listed in MOT-006; 7 guarded: `UnsubscribeResult.tsx:55`, `AskComposer.tsx:122`, `StepList.tsx:12`, `Threads.tsx:41`, `CheckoutReturn.tsx:73`, `HomeScreen.tsx:104`, `SaveBar.tsx:75` | `animate-spin` | 1 s linear | mixed | – |
| Skeletons | 117 `<Skeleton>` uses; `motion-reduce:animate-none` in `PlanCards.tsx:39-41`, `PaymentHistory.tsx:40`, `UsageCard.tsx:40-42`, `PushSetup.tsx:57-58`, `NotificationSettingsPage.tsx:100-101` | `animate-pulse` | 2 s | mostly not handled | Suggestion "drafting" lines use it too (`SuggestionCard.tsx:68`) |
| Marketing phone menu, FAQ answers, settings tabs, inbox panes | – | none | – | – | – |
| shadcn accordion and collapsible keyframes | `shadcn/tailwind.css`, `tw-animate-css` | imported, **unused** (no accordion in the app) | – | – | – |

### Durations and easings in use

| Duration | Where |
|---|---|
| 100 ms | every dialog, alert dialog, sheet overlay, popover, dropdown and select |
| 120 ms | Send button |
| 150 ms | live message, tooltips (default), every `transition-*` (Tailwind default) |
| 180 ms | suggestion bar |
| 200 ms | sheet content, Ask panel, run detail |
| 500 ms | AI credits bar |
| 1 s / 1.6 s / 2 s | spin and ping / shimmer / pulse and the automation line (loops) |

| Easing | Where |
|---|---|
| `ease` (`cubic-bezier(.25,.1,.25,1)`), the tw-animate default | every `animate-in` and `animate-out` except the sheet |
| `ease-in-out` (`cubic-bezier(.4,0,.2,1)`) | sheet content (`sheet.tsx:65`) |
| `cubic-bezier(.4,0,.2,1)`, the Tailwind transition default | every `transition-*` |
| `linear` | spin, shimmer, automation line |
| `cubic-bezier(.4,0,.6,1)` / `cubic-bezier(0,0,.2,1)` | pulse / ping (Tailwind) |

## Inconsistencies

1. **Dialogs are half the spec's speed.** Dialogs and alert dialogs open in 100 ms; the spec
   says 200 ms. Sheets do use 200 ms, but their overlay finishes at 100 ms, before the panel.
2. **Three families of enter and exit.**
   - Dialogs: fade with zoom 95%.
   - Sheets: fade with a 40 px slide.
   - The Ask panel and run detail: slide only, with no fade, and a 200 ms overlay.

   The Ask panel and the inbox details sheet are both right-hand panels yet move differently.
3. **Some dialogs have no exit at all.** Dialogs mounted conditionally (`{open ? <Dialog open/> : null}`)
   vanish without an exit animation while the others fade out (MOT-003).
4. **Three easings for the same job.** `ease`, `ease-in-out` and Tailwind's default curve all
   serve enters and exits, and there are no tokens.
5. **Three reduced-motion mechanisms.** `motion-safe:` prefixes (most app code),
   `motion-reduce:animate-none` (the Ask panel, billing and push skeletons) and `@media` inside
   `@utility` (globals). The primitives have none.
6. **Spinners.** 30 spin always; 7 stop under reduced motion. Skeletons pulse in 106 places and
   stop in 11.
7. **`transition-all`.** The Button and Switch primitives use `transition-all`, which also
   animates layout properties and box-shadow (the focus ring fades in). Most app code uses
   `transition-colors`.

## Proposed motion system

It is built from what exists and keeps three of the spec's four numbers exactly. The only change
is the suggestion bar: 180 ms becomes 200 ms. Record that in `docs/CONFLICTS.md` if it is
adopted.

### Tokens (`globals.css`)

```css
@theme {
  /* Easing: Tailwind's own curves, named for their job. */
  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1); /* state changes: colour, opacity, toggles */
  --ease-enter: cubic-bezier(0, 0, 0.2, 1);      /* decelerate: things arriving */
  --ease-exit: cubic-bezier(0.4, 0, 1, 1);       /* accelerate: things leaving */
}

:root {
  --motion-fast: 120ms;   /* micro: hover, press, toggles, menus, popovers, selects, tooltips, Send scale-in, every exit */
  --motion-normal: 150ms; /* content arriving in place: live message, inline reveals, chevrons */
  --motion-slow: 200ms;   /* surfaces: dialogs, alert dialogs, sheets, the drawer, the Ask panel, the suggestion bar */
}

@utility duration-fast { --tw-duration: var(--motion-fast); transition-duration: var(--motion-fast); }
@utility duration-normal { --tw-duration: var(--motion-normal); transition-duration: var(--motion-normal); }
@utility duration-slow { --tw-duration: var(--motion-slow); transition-duration: var(--motion-slow); }
```

`tw-animate-css` reads `--tw-duration` and `--tw-ease`, so `duration-slow ease-enter` works for
both `transition-*` and `animate-in`. Progress fills (500 ms) and ambient loops (1–2 s) stay
outside the scale on purpose: they aren't responses to an action.

### Mapping

| Role | Duration | Easing (enter / exit) | Distance | Today |
|---|---|---|---|---|
| Hover, press, colour, toggles | fast 120 | standard | – | 150 (default) |
| Tooltip | fast 120 (after a 300 ms delay) | enter / exit | 4 px | 150 |
| Popover, dropdown, select | fast 120 | enter / exit | 4 px + zoom 97% | 100 |
| Send scale-in | fast 120 | enter | zoom 95% | 120 ✓ |
| Live message | normal 150 | enter | 4 px | 150 ✓ |
| Inline reveal (Ask steps, chevrons) | normal 150 | standard | – | 150 |
| Suggestion bar | slow 200 | enter | 8 px | 180 |
| Dialog, alert dialog | slow 200 in, fast 120 out | enter / exit | zoom 95% + fade | 100 |
| Sheet, drawer, Ask panel, run detail | slow 200 in, fast 120 out | enter / exit | 40 px + fade (overlay fades over the same duration) | 200 ease-in-out; Ask has no fade |
| Toasts | sonner default | sonner | – | library ✓ |
| Progress (credits bar, uploads) | 500 / 150 | standard | – | 500 / 150 |
| Ambient loops (shimmer, line, pulse, ping) | 1–2 s | linear / pulse | – | ✓ |

**Rules.**
- Exits are faster than entries.
- Overlays fade over the same duration as their panel.
- One slide distance per surface type.
- No `transition-all`: name the properties.
- Never transition `outline-color` on focus.

### Reduced-motion policy

Under `prefers-reduced-motion: reduce`:

- **Every enter and exit is instant.** That covers the overlays above, the live message, the
  suggestion bar and Send (the last three already are).
- **Ambient loops stop.** That covers shimmer, the automation line, pulse and ping (already
  done), plus skeleton pulse (not yet).
- **Colour and opacity state changes** may keep a fast fade.
- **Spinners keep spinning.** They are the only progress feedback in a button and are small and
  essential. Remove `motion-safe:` from the seven guarded ones, so every spinner behaves the same.
  Or put both behaviours behind one `<Spinner>` component.

Do it at the source, in the primitives (`motion-reduce:animate-none motion-reduce:transition-none`
on each overlay and content, and on `Skeleton`). Add one safety net in `globals.css`:

```css
@media (prefers-reduced-motion: reduce) {
  [data-slot$="-overlay"], [data-slot$="-content"], [data-slot="skeleton"] {
    animation: none !important;
    transition: none !important;
  }
}
```

The primitives already tag their parts with `data-slot`: dialog-, sheet-, alert-dialog-,
popover-, dropdown-menu-, select- and tooltip-content, and the matching overlays. With
`animation: none`, Radix's `Presence` unmounts exits immediately, so nothing lingers.

## Findings

### MOT-001 · P1 · Overlays animate under reduced motion (spec §4.2)
- **Problem.** None of the Radix primitives honour `prefers-reduced-motion`, so dialogs, alert
  dialogs, sheets (the phone drawer, the inbox details on phones and tablets, the knowledge and
  posting-times sheets), popovers, menus, selects and tooltips still zoom, slide and fade.
  `tw-animate-css` has no reduced-motion rule of its own. Only the hand-built Ask panel and run
  detail opt out.
- **Evidence.**
  - Runtime under emulated reduce: drawer `enter 0.2s`, overlay `enter 0.1s`; popover, dropdown
    and dialog `enter 0.1s`. See the table under "How it was checked".
  - Sources: `ui/dialog.tsx:42`, `:64`; `ui/alert-dialog.tsx:39`, `:61`; `ui/sheet.tsx:40`, `:65`;
    `ui/popover.tsx:32`; `ui/dropdown-menu.tsx:45`, `:246`; `ui/select.tsx:71`;
    `ui/tooltip.tsx:44`.
- **Recommendation.** Add `motion-reduce:animate-none` to each overlay and content class, and
  `motion-reduce:transition-none` to the sheet, matching `AskPanel.tsx:82` and `:91`. Add the
  `globals.css` safety net above. These moves are small (a 95% zoom, 8–40 px), so this is a spec
  breach rather than a WCAG AA failure (2.3.3 is AAA).

### MOT-002 · P2 · Dialog timing and enter/exit families are inconsistent
- **Problem.**
  - Dialogs and alert dialogs run at 100 ms, where the spec says 200 ms.
  - The sheet overlay (100 ms) and the sheet panel (200 ms) are out of step.
  - The Ask panel slides with no fade, while the inbox details sheet fades and slides.
  - Popovers and tooltips differ: 100 ms against 150 ms.
- **Evidence.** The primitives table; `AskPanel.tsx:91` against `sheet.tsx:65`.
- **Recommendation.** Adopt the tokens and the mapping above. Dialogs and sheets enter at
  `duration-slow ease-enter`, exit at `duration-fast ease-exit`, and their overlays fade over the
  same time. Give the Ask panel and run detail `fade-in-0` and `fade-out-0` so all right-hand
  panels match.

### MOT-003 · P2 · Conditionally-mounted dialogs have no exit animation
- **Problem.** These dialogs are mounted only while open, so closing them removes them at once,
  with no fade or zoom out:
  - the new-automation gallery (`AutomationsPage.tsx:398-409` → `TemplateGallery`);
  - `AgentDraftDialog.tsx:72`;
  - `inbox/ScheduledList.tsx:209`;
  - `schedule/ListView.tsx:305`;
  - `schedule/MoveToDialog.tsx:67`.

  The same pattern loses keyboard focus (`ACCESSIBILITY.md` A11Y-007).
- **Evidence.** Static, and the runtime focus check: focus fell to `BODY` after Esc.
- **Recommendation.** Keep them mounted and drive `open`, so Radix `Presence` can play the exit.

### MOT-004 · P2 · Skeletons pulse under reduced motion
- **Problem.** The `Skeleton` primitive always pulses. Only 11 of its 117 uses add
  `motion-reduce:animate-none`. That includes the conversation list, thread, page and Home
  skeletons, and the suggestion bar's "drafting" line, which the spec calls a shimmer.
- **Evidence.** `ui/skeleton.tsx:7`. The guarded uses are listed in the inventory.
- **Recommendation.** Put `motion-reduce:animate-none` in the primitive and delete the per-use
  copies.

### MOT-005 · P2 · No motion tokens
- **Problem.**
  - There are six durations (100, 120, 150, 180, 200 and 500 ms) and three easings for enters
    and exits, all as literals.
  - New screens copy whatever the nearest component uses: Home took `motion-safe:transition-opacity`
    at 150 ms, the Ask panel 200 ms, menus 100 ms.
  - The spec's motion numbers appear in four separate files.
- **Evidence.** The durations and easings tables.
- **Recommendation.** Add the tokens and utilities above to `globals.css`. Use them in the
  primitives first, then in the five spec motions.

### MOT-006 · P3 · Spinners behave two ways
- **Problem.** 30 spinners always spin and 7 stop under reduced motion. A stopped `Loader2`
  still reads as "loading", but the same button behaves differently across screens.
- **Evidence.**
  - Unguarded:
    - AI: `SuggestionCard.tsx:99`, `:176`.
    - Automations: `AgentDraftDialog.tsx:132`, `AutomationEditor.tsx:266`, `:270`, `:428`,
      `MatchTester.tsx:80`, `steps/ThenStep.tsx:667`, `TemplateGallery.tsx:169`, `:221`, `:295`.
    - Comments: `CommentComposer.tsx:108`.
    - Post composer: `AutomationSection.tsx:241`, `:280`, `CaptionEditor.tsx:130`, `:413`,
      `:418`, `CropDialog.tsx:170`, `MediaLibraryDialog.tsx:185`, `MediaTray.tsx:59`,
      `PostComposer.tsx:716`, `:726`, `:833`, `StatusBanner.tsx:93`, `:121`,
      `WhenSection.tsx:102`.
    - Inbox: `inbox/Composer.tsx:372`, `DetailsPanel.tsx:151`, `MessageBubble.tsx:32`.
    - Knowledge: `SourcesCard.tsx:76`.
  - Guarded: listed in the inventory.
- **Recommendation.** One `<Spinner>` component with one rule. The policy above keeps them
  spinning.

### MOT-007 · P3 · Unguarded or over-broad transitions
- **Problem.**
  - `transition-all` on Button, Switch and Badge (`button.tsx:7`, `switch.tsx:19`, `badge.tsx:7`).
  - The press nudge `active:translate-y-px` on every button.
  - Opacity transitions with no guard: `AutomationRow.tsx:130`, `SchedulePage.tsx:470`.
  - An unguarded pulsing "Deleting" dot (`AccountCard.tsx:27`).
  - Unused accordion and collapsible keyframes, shipped through `shadcn/tailwind.css`.
- **Recommendation.**
  - Use `transition-[color,background-color,border-color,box-shadow]` in the primitives.
  - Add `motion-safe:` to the opacity transitions and the pulse.
  - Leave the keyframes; they cost little, but don't build on them without the reduced-motion
    rule.

### MOT-008 · P3 · The focus ring fades in from grey on sidebar rows
- **Problem.** In Tailwind 4, `transition-colors` includes `outline-color`. When a sidebar row
  receives focus, its brand outline animates from the text colour over 150 ms. The tab log caught
  it at `rgb(143,151,175)`. For a moment the ring is low-contrast, and it looks sluggish.
- **Evidence.** `shell/sidebar-styles.ts:11`, `shell/WorkspaceMenu.tsx:64`,
  `shell/AppSidebar.tsx:219`, and the runtime tab log (`ACCESSIBILITY.md` A11Y-023).
- **Recommendation.** Use `motion-safe:transition-[color,background-color]`.

### MOT-009 · P3 · Three ways to express reduced motion
- **Problem.** `motion-safe:` (opt-in), `motion-reduce:animate-none` (opt-out) and
  `@media (prefers-reduced-motion)` inside `@utility` are all in use. Reviewers have to check
  each pattern, and the primitives slipped through.
- **Recommendation.**
  - Default to `motion-safe:` for anything the app adds.
  - Keep `@media` only inside `globals.css` utilities.
  - Let the global safety net cover the primitives.
  - Add a short "Motion" section to the component conventions.
