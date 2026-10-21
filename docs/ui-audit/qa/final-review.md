# UI-073: final design-system review

**Reviewing:** develop with every task merged (UI-001 to UI-079, with UI-072 as `feature/ui-qa-final`),
against the plan's definition of done (§H) and UI-044's [review gate](review-gate.md).

**Method:**
- UI-044's §D.4 checks, re-run over every non-test file in `apps/web/src` with a script
  (`review073.cjs`, kept in `design/ui-qa/coordination/`).
- Each of the gate's RG items and DS items, traced to the code and to DESIGN_SYSTEM.md.
- Every UI-ISS issue in [UI_AUDIT.md](../UI_AUDIT.md), mapped to the tasks it names.
- The 17 owner decisions, the lint guards, CI and the git history.
- The visual evidence is UI-072's [final QA](final.md).

## 1. Verdict: the programme is done

- **Issues:** all 116 UI-ISS issues are closed: 115 by merged tasks, one (UI-ISS-052) by measurement.
  None is deferred.
- **Decisions:** all 17 owner decisions are applied and recorded.
- **Guards:** the design lint, the copy lint and the token-mirror tests run in CI on every PR.
- **Checks:** every §D.4 check is at zero or an allowed case.
- **Gate items:** all 18 RG items and all 16 DS items are closed. This review closed the last few
  itself: four code fixes and 13 DESIGN_SYSTEM notes, listed in section 7.

**For the owner:** three FYIs carried from UI-072, none blocking (section 8).

## 2. The §D.4 checks, whole app

Counts are matching lines in non-test files under `apps/web/src`, after this review's fixes. They
compare with UI-044's figures on `6c42dd3`.

| Check | UI-044 | Final | Notes |
|---|---:|---:|---|
| `text-[`, `text-white`, `bg-white/`, `bg-black/` | 0 | **0** | |
| Palette utilities | 0 | **0** | now also impossible: `--color-*: initial` (C-075) |
| `ring-ring/50`, `ring-3`, focus rings as halos | 0 | **0** | |
| `transition-all`, `backdrop-blur`, `blur-` (app) | 0 | **0** | the marketing header's blur is the documented exception |
| `dark:` in app code | 0 | **0** | |
| `md:min-h-` / `md:size-` / `md:h-` touch patches | 0 | **0** | |
| shadcn aliases outside `components/ui` | 0 | **0** | the workspace URL field moved off `border-ring` (C-075) |
| `clsx` / `tailwind-merge` outside `lib/utils` | 0 | **0** | |
| `bg-{status}/10\|15` (app) | 1 | **0** | |
| `tracking-[0.12em]` / `[0.14em]` | 2 | **0** | RG-13: the marketing footer uses the system's 0.08em |
| Hex or `rgb()` outside tokens and mirrors | 17 | **0** | every mirror reads `colorValue()`; `global-error.tsx` too (this review) |
| `Loader2` / `LoaderCircle` outside Spinner | 6 | 3 | status-icon maps only, allowed (DS-14) |
| `<Spinner>` inside a Button | 4 | **0** | all use `loading` (RG-10; the last five here) |
| Hover-only meaning without `pointer-fine:` | 1 | **0** | RG-05 |
| `min-h-[60vh]`, `max-w-[1200px]`, `h-[calc(100dvh…)]` in app code | 19 | **0** | RG-14, C-074; the two left are the dialog primitives' height caps |
| `outline-none` without a replacement | 17 (allowed) | allowed only | the design lint enforces the allowed cases (DS-12) |

## 3. The RG items (UI-044 §4)

| ID | Status | Closed by | Evidence |
|---|---|---|---|
| RG-01 | Closed | UI-075 | Badge for RunTrace's status, the sidebar's counts and labels; no `rounded-full` gradient pill outside Badge |
| RG-02 | Closed | UI-075; this review | Badge `media` tone. The `bg-media-scrim` uses left are scrims (an upload error, a remove button, bubble fills) or a caption strip. Two of them had `text-fg` on a photo, now `text-on-brand` |
| RG-03 | Closed | UI-075 | `cardInsetVariants`; ThenStep on CardInset, PageSkeleton on Card |
| RG-04 | Closed | UI-035, UI-075 | the step labels are on Field |
| RG-05 | Closed | UI-067 | RunView's actions show on hover only with `pointer-fine:`; the exact time is text in the run trace ("Asked"), so the list's `title` is a convenience |
| RG-06 | Closed | UI-069, UI-065 | no `text-xl` / `text-3xl` in app code; the Ask H1 is `PANE_TITLE` |
| RG-07 | Closed | UI-074 | `Sentry.captureException` in both route boundaries and `global-error.tsx` |
| RG-08 | Closed | UI-052 | no `MORE_CHIP` copy |
| RG-09 | Closed | UI-075, C-076 (DS-7) | AI actions use `soft`; the muted ghost is an allowed override |
| RG-10 | Closed | UI-075; this review | Button `loading` everywhere. The last five (AgentDraftDialog, TemplateGallery ×3, CropDialog) were converted here |
| RG-11 | Closed | UI-050, UI-051 | `duration-normal`. AutomationRow and RunView's `transition-opacity` are `motion-safe:` and fade only opacity |
| RG-12 | Closed | UI-070 | `colorValue()` and the mirror test |
| RG-13 | Closed | this review | `tracking-[0.08em]` |
| RG-14 | Closed | UI-076, UI-060 | none of the three patterns in app code |
| RG-15 | Closed | UI-033 residue | `bg-fg-disabled` only in `tokens.ts` |
| RG-16 | Folded | RG-04, RG-11 | |
| RG-17 | Closed | UI-065, D-16 | icon buttons are `rounded-lg`. The two `rounded-full` left are dots (a sentiment dot, carousel dots) |
| RG-18 | Closed (kept) | this review (DS-9) | the top-intents share bar stays hand-built, documented in §8.5 |

## 4. The DS items (UI-044 §5)

| ID | Status | Where |
|---|---|---|
| DS-1 | Recorded here | §2.1 Input: the primitive writes `text-sm max-md:text-base` |
| DS-2 | Recorded here | §8.2 Badge: the `media` tone |
| DS-3 | Already in | §2.1 Chip row: the collapsed sidebar's overlaid count |
| DS-4 | No change | §6's "jump-to-latest pill" exists (Ask's "Jump to latest") |
| DS-5 | Done | §1.12 and §1.13: the palette lock (C-075) |
| DS-6 | Recorded here | §1.1 and §6: the drawer is `canvas`, with the sidebar card on `panel` |
| DS-7 | Done | §8.2 Button: the muted ghost (C-076) |
| DS-8 | Recorded here | §8.2 Card: `CardBleed` and CardInset's `standard` and `compact` |
| DS-9 | Recorded here | §8.5: no share bar; Home's top intents stays hand-built |
| DS-10 | Recorded here | the plan's §H item 9: 437 `toHaveClass` assertions in 63 files at the end |
| DS-11 | Recorded here | §2.1 Pane title: Inbox, the Ask page, the phone top bar; the Ask panel's title is a sheet title |
| DS-12 | Recorded here | §8.3 Focus: the allowed `outline-none` cases, enforced by the design lint |
| DS-13 | Recorded here | §1.9: the marketing glows (token radial gradients, marketing only) |
| DS-14 | Recorded here | §8.2 Spinner: status-icon maps may keep `LoaderCircle`; Buttons use `loading` |
| DS-15 | Recorded, open | §8.5: the native radios' unchecked edge hasn't been measured against 3:1. Measure it when RadioGroup is built |
| DS-16 | Recorded here | §4: `rounded-[inherit]` is allowed (the design lint allows it) |

## 5. Issues and decisions

**UI-ISS:** 116 issues, from the detailed entries and the P3 table in UI_AUDIT.md.
- **115 name only tasks that merged**, or the Wave 3 sweeps.
- **UI-ISS-052** (₹ falls back from Geist) names UI-010, which was dropped after measuring.
  `next/font`'s `subsets` only chooses what to preload. The built CSS still carries Geist's
  `latin-ext` face (`unicode-range … U+20AD-20C4`, which covers ₹ U+20B9), and the browser fetches
  it the first time ₹ appears. Closed by that measurement (D-17, review gate).
- **No issue is deferred.** UI-029 (the calendar) was conditional on D-04 option 2. The owner chose
  native pickers, so it was never a task.

**Owner decisions:** D-01 to D-17 were approved on 2026-10-01 (C-069). Each is applied and marked
with its task in AGENT_CONTEXT's table (C-076). D-04 is native pickers with Input's focus fix
(C-073). D-17 needs nothing built.

**CONFLICTS:** C-069 to C-076 record the decisions and every addition to the spec. BUILD_SPEC §4.2
and the named requirements match them (UI-071).

## 6. The guards and §H

- **The lint guards run in CI.** The web job's `pnpm --filter @socialhood/web test` runs:
  - `styles/design-lint.test.ts`: default colours, arbitrary text and radius, translucent rings, a
    gradient on Button, a bare `outline-none`;
  - `lib/copy-lint.test.ts`: the renamed labels;
  - `styles/tokens.test.ts`: `globals.css` against `tokens.ts`, the palette lock, the chart aliases,
    and the hex mirrors, now including `global-error.tsx`.
- **§H 1 and 11, traceable and on the rules:**
  - every task merged from a `feature/ui-*` branch by squash;
  - **0** attribution lines in develop's 94 commits since 2026-10-01;
  - gitleaks ran before each commit.
- **§H 6 and 7, the gates:** each batch ran lint, typecheck, vitest, build and e2e centrally before
  its PRs (the last one, w5b1: 1800 tests and e2e 16/16). CI ran them again on every PR.
- **§H 3 and 4, accessible and responsive:** UI-072, which found 2 axe nodes (Clerk's), a clean
  keyboard and reduced-motion pass, and no overflow at 320, 640 × 450, 768, 1280 or 1536.
- **§H 9, class assertions:** 437 in 63 files, rewritten deliberately, with no `.skip` or `.todo`
  added.
- **§H 10, docs:** DESIGN_SYSTEM, AGENT_CONTEXT, BUILD_SPEC and CONFLICTS agree (UI-071, and this
  review's DS notes).

## 7. What this review changed

Small closes, each checked by eslint, typecheck and the affected tests:

- **RG-10:** five Buttons that drew `<Spinner />` by hand now use `loading`, which keeps the label's
  width and name and sets `aria-busy`. They are in AgentDraftDialog, TemplateGallery (×3) and
  CropDialog.
- **RG-13:** the marketing footer's headings use `tracking-[0.08em]`.
- **RG-02 follow-up:** text on photos uses `on-brand`, not `fg`, in the post picker's caption strip
  and the comments thumbnail's type icon. That keeps it white in any theme (UI-ISS-028).
- **`global-error.tsx`:**
  - Its colours come from `colorValue()`. They had drifted from the tokens (`#f5f5f5` against
    `fg` `#FFFFFF`, and `#b3b3b3` against `fg-secondary` `#9B9CA0`).
  - It joins the mirror test.
- **DESIGN_SYSTEM:** the DS notes in section 4.
- **The plan:** the §H assertion count.

## 8. For the owner

Carried from [final.md](final.md), none blocking:

1. **Clerk's "Secured by" contrast.** It is the only axe violation left, on Clerk's own branding
   markup. Turn off Clerk branding (a plan setting), or target it under Clerk's `footer` element.
2. **Max's price while "Coming soon".** The public page shows "Coming soon" in place of a price, and
   the in-app card shows Dodo's price. Decide which to show.
3. **The automation trigger stacks on desktop.** UI-072's fix stacks the three triggers wherever
   the step is narrower than about 670 px, which today means every width. A row would need shorter
   labels.

Open by design: measure the native radio's edge (DS-15) when RadioGroup is built.
