# Agent context: read this first

Every agent implementing a UI task (UI-001… in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md))
reads this file before touching code, then the audit sections its task cites. This is the condensed
rulebook; [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) is the authority with the reasons, and
[UI_AUDIT.md](UI_AUDIT.md) holds the issues (UI-ISS-…) and the owner decisions (D-…). If this file and
DESIGN_SYSTEM.md disagree, DESIGN_SYSTEM.md wins; tell the Design System Architect so both are fixed.

---

## 1. Order of reading

1. This file, completely.
2. Your task in IMPLEMENTATION_PLAN.md (its issues, files, dependencies, acceptance).
3. The UI-ISS entries it lists in UI_AUDIT.md, and the source findings (COL-, TYP-, SPC-, RAD-,
   SHD-, CMP-, A11Y-, RSP-, MOT-, UX-, VH-) in the area audits for evidence and line numbers.
4. The DESIGN_SYSTEM.md sections your task implements.
5. For Next.js code: `apps/web/AGENTS.md` (Next 16 differs from older versions; read the guide in
   `node_modules/next/dist/docs/` before writing Next-specific code).

## 2. Product context

- **Social Hood** is a shared inbox and AI assistant for small businesses that sell through
  Instagram and WhatsApp, India-first (prices in ₹, customers writing English, Hindi and Hinglish).
  It brings DMs and comments into one inbox; drafts (Suggest) or sends (Auto) AI replies from the
  business's knowledge; runs keyword automations; schedules posts; and offers "Ask Social Hood", a
  read-only assistant that prepares drafts.
- **Users:** owners, admins and agents (agents don't see Grow: Schedule, Automations, Knowledge).
  Plans: Free, Pro (7-day trial) and Max ("Coming soon").
- **Surfaces:** the app (`/w/[slug]/…`), the marketing site, Clerk sign-in. Installed as a PWA on
  phones, including iPhone.
- **Stack:** Next.js 16.3, React 19.2, Tailwind CSS 4.3 configured in CSS only (`@theme` in
  `src/styles/globals.css`; there is no `tailwind.config`), shadcn/ui v4 style `radix-nova` on the
  unified `radix-ui` package, `cva`, `cn` (shadcn's tailwind-merge replacement), sonner,
  lucide-react, tw-animate-css. Tests: Vitest and Testing Library; e2e: Playwright.
- **Specification:** `docs/BUILD_SPEC.html` §4 (UX-TOK, UX-SH, UX-INB, UX-SCR, UX-CMP, UX-COPY,
  UX-A11Y) and the decisions in `docs/CONFLICTS.md` (C-002 dark only, C-018, C-048 sidebar, C-051
  plan limits, C-063 inbox, C-065 Home, C-066 settings, C-067 account deletion).

## 3. UI principles and direction

- **The inbox is the product.** It gets the space, loads first and never waits on AI.
- **AI sits beside the work:** chips in the list and thread, drafts above the composer, decisions
  explained in place.
- **One accent:** the brand blue marks what the business sends, primary actions, selection and AI.
  Customers' content stays neutral.
- **Say what happened:** every send shows its status, every AI action says why, every limit says
  which limit and what to do. Disabled buttons say why.
- **Calm density:** flat surfaces, 1 px hairlines, almost no shadows, a 16 px gutter, one type
  family, dark only (D13).
- **Redesigns follow the owner's mockups for layout and our tokens for colour** (C-063, C-065,
  C-066). Mockup values that aren't tokens, and mockup content that isn't real, never enter code.

## 4. Tokens (quick reference)

Use the utilities (`bg-panel`, `text-fg-secondary`, `border-line` …), never raw values.
**Status:** ✓ exists · **A** added by UI-001 · **T** added by UI-018 under an owner decision
(C-071).

| Surfaces and states | Value | | Text and brand | Value | |
|---|---|---|---|---|---|
| `canvas` | `#000000` | ✓ | `fg` | `#FFFFFF` | ✓ |
| `panel` | `#1F1F1F` (cards, sidebar, panes, drawer) | ✓ | `fg-secondary` | `#9B9CA0` (meta, hints, placeholders: D-06) | ✓ |
| `field` | `#1D1D1D` (every input) | ✓ | `fg-disabled` | `#71717A` (disabled only) | ✓ |
| `raised` | `#2A2A2A` (selected, active segment, skeleton) | ✓ | `on-brand` | `#FFFFFF` on gradients and fills | A |
| `raised-hover` | `#333333` | ✓ | `brand` | `#567FF8` **non-text marks only** (incl. switch on, checkbox checked) | ✓ |
| `overlay` | `#262626` (floating surfaces, through `--popover`; D-12) | T | `brand-strong` | `#4467E6` (solid fills with text) | A |
| `hover` | white 5% | A | `brand-deep` | `#20338A` (gradient start) | ✓ |
| `pressed` | white 10% | A | `brand-fg` | `#9DB5FF` (brand text, links) | ✓ |
| `scrim` | black 60% | A | `brand-soft` / `brand-line` | brand 15% / 35% | ✓ |
| `media-scrim` | `#000` (on media only, with `/N`) | A | `shell-1` / `shell-2` | logo tile and Upgrade only | ✓ |

| Lines | Value | | Status | Value | |
|---|---|---|---|---|---|
| `line` | white 10% (edges) | ✓ | `success` / `warning` | `#22C55E` / `#FB923C` | ✓ |
| `line-subtle` | white 5% (row dividers) | ✓ | `danger` | `#EF4444` icons and borders, **never text** | ✓ |
| `line-strong` | white 20% (hover edges, outline button) | ✓ | `danger-fg` | `#FCA5A5` danger text | ✓ |
| `line-control` | white 40% (control edges, through `--input`; D-01) | T | `danger-fill` | `#C53030` destructive fill | ✓ |
| `ring` | brand (focus) | ✓ | `success-soft` / `warning-soft` / `danger-soft` | 15% fills | A |

- **Platform colours** (`instagram`, `whatsapp`) are for fills and glyphs only: never text, never
  rings.
- **Gradients:** `bg-brand-gradient` (primary buttons, outgoing bubbles, count badges),
  `bg-brand-gradient-decor` (meters and decorative tiles, never under text), `bg-shell-gradient`
  (logo and Upgrade only), `bg-glow-brand` (one per view; hero and plan hero; A). Dots and bars under
  12 px are solid. No other gradients.
- **Contrast you can rely on:** `fg-secondary` ≥ 4.6:1 on every surface token from `canvas` to
  `raised-hover`, `overlay` included (but only 4.45:1 on `pressed`, so neutral badges sit on
  `hover`); `brand-fg` ≥ 6.3:1; `on-brand` on the gradient ≥ 4.85:1; `line-control` edges
  ≥ 3.2:1 on every surface a control sits on. **Never** text on `brand` (3.63:1), `danger` as text,
  `fg-disabled` as readable text, opacity on text tokens (`fg-secondary/70`), or `opacity-*` to dim
  a container's text.

## 5. Scales

**Type** (Geist; weights 400, 500, 600 only; app default `text-sm`):

| Role | Classes | | Role | Classes |
|---|---|---|---|---|
| Page title | `text-2xl font-semibold tracking-tight` (24) | | Body | `text-sm` (14) |
| Pane title | `text-lg font-semibold` (18; D-05) | | Message | `text-sm leading-relaxed` |
| Section title | `text-lg font-semibold` (18) | | Control | `text-sm font-medium` |
| Card and dialog title | `text-base font-semibold` (16) | | Input | `text-base md:text-sm` (16 on phones) |
| Item title | `text-sm font-semibold` | | Meta, hint, error, table header | `text-xs` (12) |
| KPI | `text-2xl font-semibold tabular-nums` | | Small control (`xs`, `sm` buttons) | `text-xs font-medium` |
| Reading (Ask, legal) | `text-md` (15/24; A) | | Status badge, chip | `text-2xs font-medium` (11/16; A) |
| Count badge | `text-xs` in `h-5 min-w-5` | | Eyebrow | `EYEBROW` constant: `text-2xs font-semibold uppercase tracking-[0.08em] text-fg-secondary` |

Floor 11 px; no `text-[Npx]`; tracking −0.025em at 24 px and up, +0.08em on eyebrows only.

**Spacing** (4 px grid): 2 and 6 px only inside controls; 8 default gap; 12 control padding and row
padding; **16 the gutter** (card padding, dialogs, phone page padding, card-grid gap, field to field);
20 roomy card on phones; 24 desktop page padding and section gap. Page `p-4 md:p-6`, header to
content `mb-6`, sections `space-y-6`, card grid `gap-4`. Card padding `standard` `p-4` or `roomy`
`p-5 md:p-6`. Stacks use `gap`/`space-y` on the parent.

**Radius:** `sm` 4 (`kbd`, thumbnail labels, checkbox) · `md` 6 (small buttons, segment and menu
items, tooltips) · `lg` 8 (buttons, icon buttons, inputs, menus, alerts, inset panels, media) · `xl`
12 (**cards** (D-02), dialogs, sidebar, composer shells (D-16)) · `2xl` 16 (bubbles, marketing) ·
`full` (avatars, dots, pills, switches). Inner radius = outer minus padding. No arbitrary radii.

**Borders:** 1 px `line` for edges; `line-subtle` for row dividers; `--input` (`line-control`) for
control edges inside primitives, `border-line-control` on a hand-built field wrapper; 2 px
`brand` for selected tiles; one **selection bar** (2 px brand, leading edge, inset 8 px, rounded) for
selected rows and nav; `border-l-2` status edges; `danger` for invalid; dashed `line-strong` for
"add" slots.

**Elevation:** flat cards (no shadow); floating surfaces and modals get their elevation **from the
primitive** (D-12, C-071): `overlay` with a `ring-1 ring-line` edge plus `shadow-floating`
(popovers, menus, select options, toasts) or `shadow-overlay` (dialogs, alert dialogs, sheets);
modals over `bg-scrim`; the phone drawer stays `panel`. No call-site `bg-panel` or `shadow-*` on
overlays (they override the primitive). No backdrop blur in the app.

**Motion:** `duration-fast` 120 (hover, press, menus, popovers, tooltips, all exits), `duration-normal`
150 (live message, inline reveals), `duration-slow` 200 (dialogs, sheets, panels, suggestion bar);
`ease-enter`, `ease-exit`, `ease-standard`. Exits faster than entries. Name transition properties;
never `transition-all`; never animate `outline-color`. Reduced motion: every enter and exit instant,
loops and skeleton pulse stop, spinners stop (`motion-safe:animate-spin`). App code uses
`motion-safe:`; primitives use `motion-reduce:`.

## 6. Component rules and the adoption checklist

**Use the canonical primitive** (DESIGN_SYSTEM §8.2): Button (`default` is the primary; `secondary`,
`outline`, `ghost`, `destructive`, `destructive-ghost`, `link`; sizes `xs`–`xl`; `loading`),
DisabledReason, Spinner, Input, Textarea, Select, Checkbox, Switch, Field, SearchInput, ChipInput,
ToggleGroup (`segmented` or `chips`; single or multiple), Tabs (when the choice swaps panels),
Dialog (`size`), AlertDialog, Sheet (`size="panel"` for side panels), Popover, DropdownMenu, Tooltip,
Toaster, Badge (`tone`, `size`, `shape`), Card / CardHeader / CardInset, Alert, Meter, Progress,
Table, Skeleton, Avatar (+ AvatarBadge via ContactAvatar), EmptyState / ErrorState (`compact`).

- Never restyle a primitive at the call site (colour, height, radius, focus, shadow, surface). If a
  look is missing, ask for a variant (the primitive's owning task or the DSA); don't paste classes.
- No raw `<button>`, `<input>`, `<textarea>` or `<select>` where a primitive fits. A custom row or
  tile that must be a raw button uses the same hover, focus and touch rules.
- **States:** hover `bg-hover` (on `raised`: `bg-raised-hover`); open `bg-pressed`; focus = the
  global outline (never remove it; inset inside clipping containers; fields also `border-ring`);
  selected per DESIGN_SYSTEM §8.3; disabled `opacity-50`, with DisabledReason when there is a
  reason; loading `Button loading`; invalid `aria-invalid` plus Field's error.
- **Touch:** every interactive primitive is 40 px on coarse pointers. Don't add `min-h-10 md:…`
  patches; pick the size whose desktop height you need.
- **Destructive:** the confirming button is `destructive` (solid); a row or card trigger that opens
  the confirmation is `destructive-ghost`; permanent actions confirm in an AlertDialog (inside a
  dialog, an inline confirm); typed confirmation only for account and workspace data.
- **Primary:** `default` Button. One per view region (D-10): don't
  add new gradient buttons to rows or cards.
- **Toasts:** errors through `toastError(e)`; toasts with an action last 10 s or more.

**Adoption checklist (area sweeps, Wave 3)** — in your directories, none of these may remain:

- [ ] `bg-brand-gradient text-white` on Button or AlertDialogAction; hand-made danger buttons
- [ ] `min-h-10 md:min-h-*`, `size-10 md:size-*`, `h-10 md:h-*` touch patches
- [ ] `border-line bg-panel`, `shadow-*` or `max-h-*` on overlay content
- [ ] Skeleton colour overrides
- [ ] `ring-ring/50`, `ring-3`, `outline-none`/`outline-hidden` without a focus replacement
- [ ] raw `<input>`, `<textarea>`, `<select>` (native date and time go through Input)
- [ ] `text-white`, `bg-white/*`, `bg-black/*` (media uses `bg-media-scrim/N`), `bg-{status}/10|15`
- [ ] `text-[…]` sizes, local eyebrow strings, `tracking-[0.12em]`
- [ ] shadcn alias names in app code (`border-input`, `ring-ring`, `text-destructive`)
- [ ] `transition-all`, unguarded animation, hover-only controls for touch users
- [ ] (B tasks) hand-rolled badges, cards, callouts, meters, progress bars, label-hint-error stacks,
  search fields, tables, inline empty or error states

## 7. Accessibility rules

- WCAG 2.2 AA and UX-A11Y-01…05. Text 4.5:1 (placeholders included); control edges, focus and state
  indicators 3:1.
- One focus recipe; never hidden under a sticky bar; returned to the trigger when an overlay closes
  (keep overlays mounted, drive `open`).
- Everything works by keyboard; Radix for menus, selects, dialogs and tabs; a skip link first.
- `aria-label` on every icon-only button; `aria-label` only on elements with a role (else
  `sr-only` text or `role="img"`); state announced (unread, selected, pressed, busy, invalid).
- Every input has a visible label through Field; hints and errors linked by `aria-describedby`.
- Live regions polite; the message log announces new inbound messages only.
- One `<h1>` per page; unique, labelled landmarks; a `<title>` per route; `lang` on customer text when
  known; colour never the only cue.
- Verify: axe (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 375 and 1280, a keyboard
  pass, and a `reducedMotion: "reduce"` pass.

## 8. Responsive rules

- Breakpoints `md` 768 (top bar and drawer below), `lg` 1024, `xl` 1280, `wide` 1440. `sm` only in
  primitives and marketing. JS reads `lib/breakpoints.ts` (after UI-028); pass a deliberate server
  value to media hooks.
- Grids start at `grid-cols-1`; children that truncate get `min-w-0`; in header rows the identifying
  text keeps a minimum width and other items shrink or move first.
- Full-height frames are flex children of a full-height `<main>`, not `calc(100dvh − n)`.
- Sticky bars: scroll padding for the focused control; static on short viewports.
- Dialogs scroll within the viewport; sheets are full screen below `md`; toasts top-centre below `md`.
- Scrolling rows get an edge fade (`mask-fade-x`) and stay keyboard-reachable.
- Touch sizes through `pointer-coarse:`; hover-revealed controls hidden only for `pointer-fine:`.
- Check 375, 768, 1280, 1536 (plus 320, 360, 1024 and 640 × 450 for layout changes).

## 9. Approved and rejected patterns

**Approved (copy these):**
- Disabled buttons that say why, with the composer checklist's "Fix" links.
- Typed confirmations that list what is deleted and what is kept.
- Specific, honest feedback ("Moved to drafts. It keeps its time.").
- Skeletons shaped like the content; "—" with a hint instead of a fake zero; Home's explained rules
  (Attention, Fast) instead of scores.
- The automation stats chart: colour plus legend plus numbers plus an `sr-only` table.
- Ask's hand-off: "Prepared by Ask Social Hood. Check the message and time, then schedule."
- The global `:focus-visible` outline; Radix overlays; `useReturnFocus` for hand-built panels.
- The spec's motions (live message 150 ms rise, suggestion bar, Send scale-in), all `motion-safe`.

**Rejected (never add):**
- **Fake metrics and filler from the mockups:** "NLP Engine", "98.4% Confidence", "Accuracy 98%",
  "Engagement +14.2%", sync uptime, node ids, SOC-2 and encryption-claim cards, "Save All", "Docs &
  API", version badges, and any number the API doesn't return (C-065, C-066).
- **New gradients without a job**, gradients on small dots, the shell gradient beyond the logo and
  Upgrade, brand glows in the app.
- **Blur for decoration** (backdrop blur behind overlays or bars).
- Light-theme defaults from shadcn: the 10% scrim, 10% shadows, the 50% focus halo, `dark:` classes.
- Text on `brand` or platform colours; opacity-dimmed text; `danger` as text.
- Meaningful information only in a `title` tooltip or on hover.
- Per-call-site overrides of a primitive's colour, height, radius, focus or elevation.
- `md:` touch patches; raw controls where a primitive exists; a second implementation of a family.
- Emoji in product copy; Title Case and "&" in labels; roadmap copy ("Coming later", "arrives in a
  later release"); "Train" or "Teach" for adding knowledge.
- `window.confirm`, except the leave-page warning (C-066).

## 10. Known issues and implementation decisions

**Known issues.** UI_AUDIT.md lists 116 (0 P0, 24 P1, 67 P2, 25 P3). Until your task fixes one, don't
copy the pattern from neighbouring code: much of today's code still has hand-built primaries, the
50% focus halo, touch patches, raw fields, white/black utilities, `text-[11px]`, the 10% scrim and
per-site overlay patches.

**Decisions made by the synthesis** (binding unless the owner overrides; reasons in DESIGN_SYSTEM
§11):
- Button `default` is the primary (gradient); no separate `primary` name; `destructive` is solid and
  `destructive-ghost` is for triggers; banner actions are `secondary size="sm"` (no `tint`).
- Focus is the global outline everywhere; menus and segments use it inset.
- Touch sizes come from `pointer-coarse:` inside the primitives; desktop heights stay 24/28/32/36,
  plus `xl` 40 (settings forms).
- `brand-strong` (`#4467E6`, the gradient's end) for solid brand fills with text; `brand` is non-text.
- `hover`, `pressed`, `scrim`, `media-scrim`, `on-brand`, `*-soft`, `text-2xs`, `text-md`, motion
  tokens and `wide` are additions logged for confirmation (no visible change).
- Field is shadcn's Field; the three private copies go.
- Spinners stop under reduced motion (C-065's precedent); the suggestion bar moves to 200 ms
  (logged for confirmation).
- No `shadow-raised`, RadioGroup, Calendar, Command, info or chart colour tokens for now.

**Owner decisions.** All 17 were approved on 2026-10-01 with the recommended option (C-069). Each
applies through the task the plan names; until that task merges, the current look stays, so build
new work to the decided rule:

| ID | Topic | Status | Decision |
|---|---|---|---|
| D-01 | Control-border token `line-control` and its scope | Applied (UI-018, C-071) | Checkbox, radio, switch **and** text fields; checked boxes `brand` |
| D-02 | Card radius | Approved | `xl` everywhere |
| D-03 | Tooltip colour | Approved | Dark, like other floating surfaces |
| D-04 | Native date and time pickers in R1 | Approved | Accept native |
| D-05 | Page and pane title sizes | Approved | 24 px page, 18 px pane |
| D-06 | Placeholder colour | Applied (UI-018, C-071) | `fg-secondary` |
| D-07 | "AI Assisted" and AI/automation labels (C-063) | Approved | "Sent by AI" / "Automation · {name}" |
| D-08 | Settings breadcrumb, eyebrow, tab labels, save bar, Agent tiles (C-066) | Approved | Drop, match, only when needed, one sentence |
| D-09 | "Remove" and account-card destructive actions (C-067) | Approved | Disconnect visible; "Delete account and data" in ⋯ |
| D-10 | Gradient on every primary (VH-003) | Approved | One per view region |
| D-11 | Comments needs-reply API (UX-001) | Approved | Per-post count and filter now |
| D-12 | Overlay surface and elevation shadows | Applied (UI-018, C-071) | Adopt; the edge is a ring beside the shadow |
| D-13 | Identity palette | Approved | Up to four pairs from existing values |
| D-14 | Single-key shortcuts | Approved | A per-device switch |
| D-15 | Inbox refinements (C-063) | Approved | Neutral segment, heart in emoji popover, composer-only scheduling, Archived chip |
| D-16 | Spec-prescribed layouts (back link, editor panel, icon-button and composer radius) | Approved | Back link, panel after steps, `rounded-lg`, `rounded-xl` |
| D-17 | Devanagari fallback font | Approved | System fallback in R1 |

## 11. Working environment: renders, screens and tests

- **Never touch the owner's live stack:** ports **3000** and **8000**, the database **`socialhood`**,
  Valkey db 0.
- **Use 127.0.0.1, not localhost**, for Postgres and Valkey on this machine.
- **Renders and e2e run on the isolated e2e stack** (`docs/testing-e2e.md`), with your own ports,
  database and Valkey db. Pick values no other agent uses (the default run uses 3100, 8100,
  `socialhood_test_6` and db 5); the database name must start with `socialhood_test_` or
  `socialhood_e2e`:

  ```sh
  # bash (PowerShell: set each $env:NAME first)
  E2E_API_PORT=8131 E2E_WEB_PORT=3131 E2E_DB_NAME=socialhood_e2e_ui011 \
  E2E_REDIS_URL=redis://127.0.0.1:6379/11 pnpm e2e --serve   # keep the stack up for screenshots
  E2E_API_PORT=8131 E2E_WEB_PORT=3131 E2E_DB_NAME=socialhood_e2e_ui011 \
  E2E_REDIS_URL=redis://127.0.0.1:6379/11 pnpm e2e           # build, run the suite, clean up
  ```

  The launcher refuses busy ports and the dev database, and drops its database at the end.
- **Long commands don't run in the background through the Bash tool** (they are killed at its time
  limit). Run them in the foreground with a long timeout; to keep the stack up while you work, start
  it detached (PowerShell `Start-Process` with stdout and stderr redirected to log files) and stop it
  when done.
- **Scratch files** go in the shared scratchpad under a unique name (prefix them with your task ID).
  Temporary Playwright specs and screenshots stay out of the repository.
- **Screens for visual QA** (375, 768, 1280, 1536; touch emulation at 375 and 768): Home; the inbox
  list; a conversation with an AI draft; Comments; a post's comments; Automations; the automation
  editor; the template gallery; Schedule (week, month, list; agenda on phones); the post composer;
  Knowledge; the Ask panel and the Ask page; Settings › Connections, AI, Workspace, Notifications,
  Billing, Agent; the upgrade dialog; `/`, `/privacy`, `/data-deletion`; sign-in. Plus one open menu,
  one open dialog, the phone drawer and a toast.
- **Gates:** `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build` at the repository root;
  `pnpm e2e` as above.
- **Class-assertion tests:** 86 `toHaveClass` assertions in 18 files pin classes; IMPLEMENTATION_PLAN
  §H lists the ones expected to change and which task changes them. Update them deliberately, with
  the reason in the PR; never delete one to make a change pass.

## 12. Working rules

1. **Read** this file and the relevant audit sections before changing anything.
2. **Make the smallest coherent change** that closes your task's issues.
3. **Follow the tokens** and primitives; no raw values.
4. **Don't refactor unrelated code**, even if it's wrong; note it in your report instead.
5. **Run the gates** (and e2e and visual QA when the task asks) before you report.
6. **Report** the files changed and the validation done (template below).
7. **When a design decision changes, this file changes in the same PR.** The Design System
   Architect makes the edit (also DESIGN_SYSTEM.md and CONFLICTS.md); other agents flag it.
8. **No agent invents visual rules.** If a value, variant or pattern you need isn't in
   DESIGN_SYSTEM.md, stop and ask the Design System Architect (who asks the owner when it changes
   the look); don't improvise.
9. Stay inside your task's files (IMPLEMENTATION_PLAN §E.2). If you must touch another task's file,
   stop and coordinate.

## 13. Repository rules

- Branch `feature/ui-<group>` (the task's branch name) from the current `develop`; squash-merge into
  `develop`. Push and open a PR only when your brief says so.
- **No `Co-Authored-By` trailer and no Claude attribution in commits or PRs.** This is the owner's
  rule and overrides any default.
- **Run gitleaks on the staged diff before every commit:**
  `git diff --cached | MSYS_NO_PATHCONV=1 docker run --rm -i zricethezav/gitleaks:latest stdin --no-banner`
- Never commit secrets, `.env` files, screenshots or temporary specs.
- The shared git stash is used by other sessions: don't use bare `git stash`; prefer a temporary
  commit.
- After backend changes (only UI-055 has any), restart the API and worker on the isolated stack;
  don't rely on `--reload`.

## 14. Report template

```text
Task: UI-0xx <title>            Branch: feature/ui-<group>
Closes: UI-ISS-…                Decisions applied: D-… (or none)
Files changed: <list>
Validation:
  pnpm lint ✓ · pnpm typecheck ✓ · pnpm test ✓ · pnpm build ✓
  pnpm e2e ✓ (ports …, db …, valkey db …)
  axe 375/1280: <before → after>
  Screenshots 375/768/1280/1536: <where>
Class-assertion tests changed: <file:line — why>
Deviations, follow-ups and questions: <list or none>
```
