# Social Hood design system: the target

The one system the eight UI audits reconcile into. It starts from what exists (BUILD_SPEC §4,
`apps/web/src/styles/globals.css`, `components/ui/*`) and changes only what an audit found
inconsistent, inaccessible or unmaintainable. Every addition has a reason and a source.

- **Read with:** [UI_AUDIT.md](UI_AUDIT.md) (the issues and the owner decisions D-01…D-17),
  [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) (who builds what) and
  [AGENT_CONTEXT.md](AGENT_CONTEXT.md) (the condensed rules for implementing agents). Evidence and
  measurements stay in the area audits, linked by ID.
- **Theme:** dark only (D13, C-002), built so that a light theme is a token swap later (§1.12).
- **Status markers** used in every table:
  - **Keep:** exists today and stays as is.
  - **Add:** new, with no visible change (it names a value already in use, or is a utility). Logged
    for the owner's confirmation in a CONFLICTS entry, as C-002 was. Not blocking.
  - **Change:** a visible change that implements an approved rule (the spec, WCAG 2.2 AA, a
    CONFLICTS decision). Not blocking.
  - **Owner D-xx:** a visible change or a change to an approved decision. Waits for the owner (see
    UI_AUDIT §D). Until then the current value stays.

---

## 0. Principles and system rules

The spec's principles (§4.1) stand: the inbox is the product; AI sits beside the work; one accent
for what the business sends and for primary actions; say what happened; calm density (flat
surfaces, 1 px hairlines, almost no shadows, a 16 px gutter, one type family).

System rules that follow from the audits:

1. **One source per decision.** Colours, type sizes, motion and elevation are tokens in
   `globals.css`; components use the generated utilities. No hex, `rgb()`, palette utilities
   (`text-white`, `bg-black/60`, `bg-red-500`) or arbitrary values (`text-[11px]`,
   `rounded-[10px]`) in app code. Exceptions are listed (§1.12).
2. **Fix at the primitive.** A state, size or colour rule lives in `components/ui/*`, not at call
   sites. A call site that needs a different look uses a variant or prop; if none fits, the variant
   is added to the primitive (one place, reviewed), never pasted inline.
3. **One canonical component per job.** No second implementation of a family in §8.2. Product
   components compose the primitives.
4. **No visual rule without a reason.** New colours, gradients, shadows, blur or animation need a
   documented job (a spec rule, a WCAG criterion, or an owner decision). Rejected patterns are in
   AGENT_CONTEXT.md.
5. **Keep shadcn and Radix.** The library is restyled through tokens (UX-CMP-01), not replaced.
   Missing primitives are added with the shadcn CLI and restyled.

---

## 1. Colour

### 1.1 Surfaces and states

| Token | Value | Role | Status |
|---|---|---|---|
| `canvas` | `#000000` | App background, thread area, marketing | Keep |
| `panel` | `#1F1F1F` | Cards, sidebar, panes, headers, composer bar; **the phone drawer** | Keep; drawer Change (COL-010), applied (C-071) |
| `field` | `#1D1D1D` | **Every** text field, select trigger and textarea; incoming bubbles; segmented tracks | Keep; Input and SelectTrigger move onto it (CMP-011) |
| `raised` | `#2A2A2A` | Selected row, active segment, secondary button, skeleton, meter track | Keep |
| `raised-hover` | `#333333` | Hover on `raised` (secondary button) | Keep |
| `overlay` | `#262626` | Popovers, menus, select content, dialogs, sheets, toasts, tooltip | **Owner D-12**, applied (C-071), through `--popover` |
| `hover` | `rgb(255 255 255 / 0.05)` | Hover fill on any surface; neutral chip fill | **Add** (today's `bg-white/5`) |
| `pressed` | `rgb(255 255 255 / 0.10)` | Pressed or open (`aria-expanded`, `data-state=open`) fill | **Add** (today's `bg-white/10`) |
| `scrim` | `rgb(0 0 0 / 0.60)` | Modal and drawer backdrop | **Add** (UX-SH-02's value; Ask panel and Clerk use it) |
| `media-scrim` | `#000000` | Overlays on photos and video only, with an opacity modifier (`bg-media-scrim/60`); stays dark in any theme | **Add** |

Elevation reads by lightness: canvas → panel → raised for in-page structure, `overlay` for things
that float (D-12). Hover is an overlay so it works on any surface; selected stays `raised` plus a
bar, so the two are told apart (§5).

### 1.2 Lines and focus

| Token | Value | Role | Status |
|---|---|---|---|
| `line` | white 10% | Card, pane and list edges; inset-panel edges | Keep |
| `line-subtle` | white 5% | Row dividers inside a card | Keep |
| `line-strong` | white 20% | Hover edge on interactive cards; dashed placeholders; outline button edge | Keep |
| `line-control` | `rgb(255 255 255 / 0.40)` | Edges that identify a control: checkbox, radio, switch; text fields and selects through `--input` | **Owner D-01**, applied (C-071) |
| `--ring` (alias) | `brand` | The focus outline | Keep |

`line-control` is white 40%, not a solid grey, because it must pass 3:1 on every surface a control
sits on: 3.66 (canvas), 3.79 (panel), 3.76 (field), 3.68 (overlay), 3.58 (raised), 3.42
(raised-hover). The solid greys proposed in the audits fail somewhere: `#71717A` is 2.97:1 on
raised, `#6B6B6B` 2.84:1 on overlay. It also belongs with the other white-alpha lines, so a light
theme swaps it with them.

### 1.3 Text

| Token | Value | Role | Status |
|---|---|---|---|
| `fg` | `#FFFFFF` | Primary text | Keep |
| `fg-secondary` | `#9B9CA0` | Secondary and meta text, timestamps, hints; **placeholders** | Keep; placeholders **Owner D-06**, applied (C-071) |
| `fg-disabled` | `#71717A` | Disabled controls only (exempt from contrast) | Keep; no placeholders (D-06, C-071) |
| `on-brand` | `#FFFFFF` | Text and icons on the brand gradient, `brand-strong`, `danger-fill`, platform fills and avatars | **Add** (replaces 108 `text-white`) |

### 1.4 Brand

| Token | Value | Role | Status |
|---|---|---|---|
| `brand` | `#567FF8` | **Non-text marks only:** focus outline, unread dot, selection bar, switch on, **checkbox checked and indeterminate** (fill and edge; the tick is a graphic, `on-brand` 3.63:1; C-071), chart series, decorative gradient end. Never behind text. | Keep (rule tightened) |
| `brand-strong` | `#4467E6` | Solid brand fills that carry text or a glyph: a filled segment, the skip link, Clerk's primary, `--primary`; the gradient's end stop | **Add** (an existing value: white on it is 4.85:1) |
| `brand-deep` | `#20338A` | Gradient start | Keep |
| `brand-fg` | `#9DB5FF` | Brand text and icons on dark: links, active segment text, AI labels | Keep |
| `brand-soft` | brand 15% | Chips, the AI pill, selected cards; the **info** tone | Keep |
| `brand-line` | brand 35% | Brand borders (active filter chip) | Keep |
| `shell-1`, `shell-2` | `#3352CC`, `#1C2D70` | The logo tile and Upgrade only (UX-SH-01) | Keep (scoped) |

### 1.5 Status

| Token | Value | Role | Status |
|---|---|---|---|
| `success`, `warning` | `#22C55E`, `#FB923C` | Text, icons, borders, dots, chart marks (7.2:1 or more on panel) | Keep |
| `danger` | `#EF4444` | Icons, borders, dots, the invalid edge. **Never text** (4.38:1) | Keep |
| `danger-fg` | `#FCA5A5` | Danger text | Keep |
| `danger-fill` | `#C53030` | Destructive button fill and failed bubble, with `on-brand` | Keep |
| `success-soft`, `warning-soft`, `danger-soft` | 15% of the base colour | Chip, banner and callout fills; the destructive menu highlight | **Add** (the majority value today; the spec already names warning and danger soft) |

There is no separate info token: the **info** tone is `brand-soft` with `brand-fg`.

### 1.6 Platform

| Token | Value | Role | Status |
|---|---|---|---|
| `instagram`, `whatsapp` | `#BE185D`, `#16A34A` | Fills and glyphs only (avatar badges, platform tiles). **Never text, never a ring.** | Keep (rule added; COL-002) |
| `facebook` | `#2563EB` | Marketing "later" tile | Keep |
| `linkedin` | `#1E40AF` | No platform use; available to the identity palette | Keep |

### 1.7 Identity palette (avatars and account colours)

Avatar fallbacks and schedule account rings use a separate identity palette, never status or
platform colours as identity. Each stop is at least 4.5:1 against `on-brand`. **Owner D-13**
(recommended: up to four pairs built from existing values, for example `brand-deep → brand-strong`,
`shell-1 → shell-2`, `linkedin → facebook`). The palette lives in one module and is shared by
ContactAvatar, AccountAvatar and the schedule filter. The initial is decorative (the name is always
beside it) and gets `aria-hidden`.

### 1.8 Charts

No new tokens. Status charts use status tokens (runs `brand`, failures `danger`; sentiment
`success`, `fg-secondary`, `danger`). Categorical series use the identity palette. Every chart keeps
the pattern from the automation stats: colour plus a legend plus numbers in text, and an `sr-only`
table or `role="img"` with a label.

### 1.9 Gradients

Four gradients, each with one job; stops reference tokens (no hex in `@utility`). No new gradients.

| Utility | Stops | Allowed on | Text on it |
|---|---|---|---|
| `bg-brand-gradient` | `brand-deep → brand-strong` | Primary buttons, outgoing bubbles, count badges | `on-brand` (4.85:1 or more) |
| `bg-brand-gradient-decor` | `brand-deep → brand` | Meters, progress fills, decorative icon tiles | Icons only, never text |
| `bg-shell-gradient` | `shell-1 → shell-2` | Logo tile and Upgrade only | `on-brand` |
| `bg-glow-brand` | radial `brand-soft → transparent` | One per view at most: the marketing hero and the plan hero | Any |

Marks under 12 px (dots, bars) are solid `brand`, never a gradient.

### 1.10 shadcn alias map

Aliases stay inside `components/ui`; app code uses the tokens.

| Alias | Today | Target | Why |
|---|---|---|---|
| `--primary` | `brand` | `brand-strong` | A text-bearing fill must pass 4.5:1 (UI-ISS-005) |
| `--primary-foreground` | literal `#FFFFFF` | `on-brand` | No literals |
| `--accent` | `raised` | `hover` | Base of the menu highlight; the same pixel on `panel` |
| `--popover` | `panel` | `overlay` | **Owner D-12**, applied (C-071) |
| `--input` | `line` | `line-control` | **Owner D-01**, applied (C-071) |
| `--card-foreground`, `--popover-foreground`, `--secondary-foreground`, `--accent-foreground` | not mapped in `@theme inline` | mapped | Their utilities generate no CSS today (COL-009) |
| `--background`, `--foreground`, `--card`, `--secondary`, `--muted`, `--muted-foreground`, `--destructive`, `--border`, `--ring` | unchanged | unchanged | |
| `--radius` | `0.5rem`, read by nothing | unchanged, commented as inert | It is in UX-TOK-01's file; Tailwind's defaults are the radius scale |

`tokens.test.ts` asserts that every alias in `:root` has a `--color-*` mapping.

### 1.11 Contrast rules and reference pairs

Text 4.5:1 (3:1 at 24 px, or 18.66 px bold); placeholders count as text. Non-text 3:1 for control
edges, focus and state indicators, and icons that carry meaning. Translucent colours are measured
composited on their real surface.

| Pair | Ratio | Use |
|---|---|---|
| `fg` on canvas / panel / field / overlay / raised | 21.0 / 16.5 / 16.9 / 15.1 / 14.4 | Primary text |
| `fg-secondary` on canvas / panel / field / overlay / raised / raised-hover | 7.66 / 6.01 / 6.15 / 5.52 / 5.23 / 4.61 | Secondary text, placeholders (D-06) |
| `brand-fg` on panel / overlay / raised / brand-soft over panel | 8.23 / 7.56 / 7.17 / 6.83 | Links, active segments, chips |
| `on-brand` on gradient start / end, `brand-strong`, `danger-fill`, `instagram` | 11.04 / 4.85 / 4.85 / 5.47 / 6.04 | Buttons, bubbles, badges |
| `danger-fg` on panel / danger-soft over panel | 8.68 / 7.42 | Errors |
| `warning`, `success` on panel / on their soft fill | 7.28, 7.23 / 5.56, 5.57 | Status text |
| `brand` focus outline on canvas / panel / field / overlay / raised / raised-hover | 5.79 / 4.54 / 4.65 / 4.17 / 3.96 / 3.48 | Focus |
| `line-control` on every surface | 3.42–3.79 | Control edges (D-01); a field draws it over its own fill (`#777777`): 3.70 on panel, 3.40 on overlay, 3.22 on raised |
| `brand` (checkbox checked, switch on) on panel / overlay / raised / raised-hover | 4.54 / 4.17 / 3.96 / 3.48 | State fills (C-071; `brand-strong` is 2.96 on raised) |

**Never:** text on `brand` (3.63:1), `danger` as text (4.38:1), `fg-disabled` as readable text
(3.41:1), platform colours as text (Instagram 2.73:1), `brand` text on `raised` (3.96:1), opacity
modifiers on text tokens (`fg-secondary/70` is 3.64:1), or `opacity-*` on a container to "dim" its
text.

### 1.12 Ready for a light theme (without building one)

1. Every colour is a token. After the area sweeps, the default palette is switched off
   (`--color-*: initial` before our tokens), so `bg-red-500` or `text-white` no longer compile.
2. States are overlays (`hover`, `pressed`, `scrim`) that a light theme redefines as black alpha.
3. Text on coloured fills uses `on-brand`, never `text-white`.
4. Gradient stops are `var()`.
5. No `dark:` variants in app code or in restyled primitives: the theme lives in the token values.
   (The `dark` custom variant from C-002 stays for library code that needs it.)
6. Allowed literals: `media-scrim` overlays on media; the hex mirrors that consumers can't read as
   variables (Clerk, the OG image, the manifest), which must read from `styles/tokens.ts` or be
   tested against it (COL-019).

A light theme would then be one block that redefines the `--color-*` values under a theme selector,
with no component edits. It is not planned for R1.

### 1.13 Token changes in one place

The non-blocking additions (UI-001):

```css
@theme {
  --color-hover: rgb(255 255 255 / 0.05);
  --color-pressed: rgb(255 255 255 / 0.10);
  --color-scrim: rgb(0 0 0 / 0.60);
  --color-media-scrim: #000000;
  --color-on-brand: #FFFFFF;
  --color-brand-strong: #4467E6;
  --color-success-soft: rgb(34 197 94 / 0.15);
  --color-warning-soft: rgb(251 146 60 / 0.15);
  --color-danger-soft: rgb(239 68 68 / 0.15);

  --text-2xs: 0.6875rem; --text-2xs--line-height: 1rem;      /* 11/16 */
  --text-md: 0.9375rem;  --text-md--line-height: 1.5rem;     /* 15/24 */

  --ease-standard: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-enter: cubic-bezier(0, 0, 0.2, 1);
  --ease-exit: cubic-bezier(0.4, 0, 1, 1);

  --breakpoint-wide: 90rem;                                   /* 1440 px */
}
```

The owner's decisions, applied by UI-018 (C-071):

```css
@theme {
  --color-line-control: rgb(255 255 255 / 0.40);              /* D-01; --input */
  --color-overlay: #262626;                                    /* D-12; --popover */
  --shadow-floating: 0 8px 24px -6px rgb(0 0 0 / 0.7);         /* D-12 */
  --shadow-overlay: 0 24px 64px -12px rgb(0 0 0 / 0.8);        /* D-12 */
}
```

The 1 px `line` edge first drafted inside the two shadows is drawn beside them, as `ring-1 ring-line`
(a sheet: its side border), so a call site's leftover `shadow-xl` replaces only the shadow (C-071).

Motion durations, the reduced-motion safety net and the base-layer rules are in §2 and §7.

---

## 2. Typography

**Family:** Geist Sans and Geist Mono through `next/font`, subsets `latin` and **`latin-ext`**
(Change, UI-ISS-052; Devanagari is D-17). **Weights:** 400, 500 and 600 only;
`strong, b { font-weight: 600 }` in the base layer. **Default size:** `text-sm` on the app's
`<main>`, so unsized text is 14 px everywhere in the app (marketing keeps its own).

### 2.1 Scale by role

| Role | Classes | Size / line height | Weight | Tracking | Use | Status |
|---|---|---|---|---|---|---|
| Display | `text-4xl sm:text-5xl lg:text-6xl leading-[1.08]` | 36 → 60 | 600 | −0.025em | Marketing hero only | Keep |
| Marketing heading | `text-3xl sm:text-4xl` | 30 → 36 | 600 | −0.025em | Marketing H2, legal H1 | Keep |
| Page title (H1) | `text-2xl` | 24/32 | 600 | −0.025em | Every app page, including Settings | **Owner D-05** for Settings |
| KPI number | `text-2xl tabular-nums` | 24/32 | 600 | −0.025em | Metric tiles, plan name | Keep |
| Pane title (H1 of a pane) | `text-lg` | 18/28 | 600 | 0 | Inbox, Ask, phone top bar | **Owner D-05** (spec says `text-xl`) |
| Section title (H2) | `text-lg` | 18/28 | 600 | 0 | Page sections ("Compare plans"), large dialogs | Keep |
| Card title | `text-base` | 16/24 | 600 | 0 | Every card and panel heading; dialog and sheet titles | Change (14 and 18 px card titles align) |
| Item title | `text-sm` | 14/20 | 600 | 0 | Row names, template names, step titles | Keep |
| Reading | `text-md` | 15/24 | 400 | 0 | Ask answers and composer, legal prose | **Add** (replaces `text-[15px]`; 24 px leading, not 28) |
| Body | `text-sm` | 14/20 | 400 | 0 | Default UI text | Keep |
| Message | `text-sm leading-relaxed` | 14/22.75 | 400 | 0 | Bubbles and composers | Keep |
| Control | `text-sm` | 14/20 | 500 | 0 | Buttons (default and up), nav, tabs, segments, labels, menu items | Keep |
| Input | `text-base md:text-sm` | 16 → 14 | 400 | 0 | **Every** text-entry field (no iOS zoom) | Change (UI-ISS-017) |
| Meta, caption, helper, error | `text-xs` | 12/16 | 400 (500 for emphasis) | 0 | Timestamps, hints, descriptions in dense cards, inline errors, table headers | Keep |
| Small control | `text-xs` | 12/16 | 500 | 0 | Button `xs` and `sm` (replaces `text-[0.8rem]`), filter chips | Change |
| Chip, status badge | `text-2xs` | 11/16 | 500 | 0 | Status and signal badges, plan badge, `kbd`, the collapsed sidebar's overlaid count | **Add** (replaces `text-[11px]` and `text-[9px]`–`[10px]`) |
| Count badge | `text-xs` in `h-5 min-w-5` | 12/16 | 500 | 0 | Unread and needs-reply counts (UX-SH-01) | Keep (the inbox's `h-4 text-[10px]` count aligns) |
| Eyebrow (micro label) | `text-2xs uppercase` | 11/16 | 600 | +0.08em | Section labels, nav group labels, table group labels | **Add** token; one tracking (0.12em retires) |
| Mono | `font-mono text-xs` | 12/16 | 400 | 0 | Traces, IDs | Keep |

### 2.2 Rules

- **Floor 11 px.** No 9 or 10 px text.
- **No arbitrary sizes.** `text-[Npx]` and `text-[0.8rem]` are replaced by the scale; arbitrary
  sizes carry no line height, which is why chips needed `leading-[18px]` patches.
- **Tracking:** −0.025em at 24 px and up; +0.08em for uppercase eyebrows only; 0 elsewhere.
- **One title rule per surface:** one H1 per page at 24 px; inside a page, 18 px sections and 16 px
  cards. Card descriptions are `text-xs` in dashboard cards and `text-sm` in settings and forms,
  built into `CardHeader` so call sites don't choose.
- **Labels** use the Control role with normal leading (`leading-none` clips wrapped labels and
  titles). Compact forms (inbox and schedule popovers) may use `text-xs` labels through Field's
  `density="compact"`, not inline overrides.
- **Shared constants.** `EYEBROW` and the other role strings are importable constants in
  `styles/` (the `typeRoles` list becomes the source, not documentation); `/dev/tokens` renders
  them. No local copies (`GROUP_LABEL`, `LABEL`, `CHIP`).

---

## 3. Spacing

Tailwind's 4 px spacing stays (`--spacing: 0.25rem`); steps are restricted by role. These are
already the most used values (SPACING.md §A.3).

| Step | px | Role |
|---|---:|---|
| `0.5` | 2 | Inside controls only: chip `py`, badge offsets |
| `1` | 4 | Icon to text in chips; title to meta line; stacked bubbles |
| `1.5` | 6 | Inside controls only: label to field, icon gap in buttons |
| `2` | 8 | Default inline gap; chip `px`; tight list stacks |
| `3` | 12 | Control `px`; row `py`; related controls; inset-panel padding (rows) |
| `4` | 16 | **The gutter:** inbox regions, card padding, dialog padding, page padding on phones, card-grid gap, field-to-field |
| `5` | 20 | Roomy card padding on phones |
| `6` | 24 | Page padding on desktop; section gap; roomy card padding on desktop |
| `8`+ | 32+ | Empty states, search-icon insets, marketing rhythm only |

| Role | Canonical | Replaces |
|---|---|---|
| Page padding | `p-4 md:p-6` (PageFrame) | Settings' `pt-5` on phones |
| Page header to content | `mb-6` | `mb-4` (Schedule) |
| Section gap | `space-y-6` / `gap-6` | 16 and 20 px page-level gaps |
| Card grid | `gap-4` (`lg:gap-6` in two-column page layouts) | `gap-3` |
| Card padding | `standard` `p-4` (data and dashboard cards); `roomy` `p-5 md:p-6` (settings, billing, forms, plan cards) | six paddings |
| Card header strip | the card's own padding | `p-5` strips on `p-4` cards |
| Inset panel | `p-3` for rows, `p-4` for form groups | |
| Form | fields `space-y-4`, label to control `space-y-1.5`, fieldsets `space-y-6` | `space-y-3`, `gap-5`, `space-y-5` |
| Table cells | edge cells align with the card padding, inner `px-3`; header `py-2`, body `py-3` | three schemes |
| Dialog and sheet | `p-4 gap-4` | (keep) |
| Chip | status `h-5 px-2`; filter `h-7 px-3` (40 px on touch) | six paddings |

Stacks use `gap`/`space-y` on the parent, not `mt-*` on children. Half-steps (`0.5`, `1.5`, `2.5`)
only inside controls. No negative-margin bleeds: Card exposes its padding for full-bleed children.

---

## 4. Radius

Tailwind's defaults, one role per step. **Nesting:** inner radius = outer radius minus the padding
between them, rounded to a step (an inset panel in an `xl` card is `rounded-lg`).

| Step | px | Roles | Status |
|---|---:|---|---|
| `rounded-none` | 0 | Sheets, full-bleed panes, tables inside cards | Keep |
| `rounded-sm` | 4 | `kbd`, inline code, thumbnail labels and counters, checkbox | Change (replaces bare `rounded` and `rounded-[4px]`) |
| `rounded-md` | 6 | Small buttons (`xs`, `sm`, `icon-xs`, `icon-sm`), segment items, menu items, tooltips, bubble tails | Change (plain `rounded-md` replaces `rounded-[min(var(--radius-md),…)]`; same 6 px) |
| `rounded-lg` | 8 | Buttons (default and up), **icon-only buttons**, inputs, selects, segmented tracks, menus and popovers, banners and alerts, inset panels, media | Keep; icon buttons **Owner D-16** |
| `rounded-xl` | 12 | **All app cards**, dialogs, the sidebar, composer shells, notice cards | Cards **Owner D-02**; composer shells **Owner D-16** |
| `rounded-2xl` | 16 | Message and Ask bubbles (with the 6 px tail corner), marketing cards | Keep |
| `rounded-full` | — | Avatars, dots, status pills and count badges, switches, things that are circles | Keep |

Retire `rounded-3xl`, `rounded-4xl` (Badge), `rounded-[10px]` and the `min()` expressions.

---

## 5. Borders

| Use | Width | Colour |
|---|---|---|
| Card, pane and list edges | 1 px | `line` |
| Row dividers inside a card | 1 px | `line-subtle` (the card's own edges stay `line`) |
| Inset panel (a group inside a card) | 1 px | `line`, or a `raised` fill; never `line-subtle` on `field/60` |
| Text field, select, checkbox, radio at rest | 1 px | `--input` = `line-control` (D-01); a checked checkbox is its `brand` fill |
| Outline button | 1 px | `line-strong` |
| Hover on an interactive card | 1 px | `line-strong` |
| Focus | 2 px outline | `ring` (brand), see §8.3; fields also turn their border `ring` |
| Selected tile | 2 px | `brand` |
| **Selection bar** (selected row, active nav item) | 2 px | `brand` on the leading edge, inset 8 px, rounded; one implementation |
| Status edge on a card (post status, danger card) | `border-l-2` | the status colour |
| Invalid | 1 px | `danger` (one name, not `destructive`) |
| Disabled | — | keep the border; the control is `opacity-50` |
| Placeholder slot ("add" tiles) | 1 px dashed | `line-strong` (no dotted) |
| Platform-badge cut-out on avatars | `ring-2` | `ring-panel` (a ring, so the glyph isn't shrunk) |

---

## 6. Elevation and shadows

On near-black, depth comes from a lighter surface, a hairline and a strong, wide shadow; Tailwind's
10% shadows don't register (SHD-002). Spec §4.1 ("almost no shadows") holds: only things that float
get one.

| Level | Surface | Edge and shadow | Use | Status |
|---|---|---|---|---|
| 0 Flat | `panel` on `canvas` | `border-line`, no shadow | Cards, panes, sidebar, bubbles | Keep (drop the no-op `shadow-sm` on bubbles and active segments) |
| 1 Floating | `overlay` | a 1 px `line` ring (`ring-1 ring-line`; the toast: a `line-strong` border) plus `shadow-floating`, a dark drop shadow | Popovers, menus, selects, tooltip, toasts, the jump-to-latest pill, drag previews, the sticky save bar | **Owner D-12**, applied (C-071) |
| 2 Overlay | `overlay` (the phone drawer: `panel`, like the sidebar) | a `line` ring (a sheet: its side border) plus `shadow-overlay`, over the `scrim` | Dialogs, alert dialogs, sheets, the phone drawer, the Ask panel, run detail | Scrim Change (UX-SH-02); surface and shadow **Owner D-12**, applied (C-071) |
| Marketing glow | — | `shadow-brand/10–25` | Marketing pages only | Keep (not in the app) |

- **No blur.** Backdrop blur is not used to separate layers in the app (it costs a full-viewport
  re-render on every animation frame and does nothing behind a 60% scrim or a 95% surface). The
  marketing site header's blur is the one exception (intentional, with a fallback).
- **Elevation belongs to the primitive.** No call-site `shadow-*` or `bg-panel` on overlay content.
- **`box-shadow` for other jobs** (the crop mask) only as a named utility in `globals.css`.

---

## 7. Motion

### 7.1 Tokens

Easings are `@theme` tokens (§1.13). Durations are variables with matching utilities, which
tw-animate-css reads too:

```css
:root { --motion-fast: 120ms; --motion-normal: 150ms; --motion-slow: 200ms; }
@utility duration-fast   { --tw-duration: var(--motion-fast);   transition-duration: var(--motion-fast); }
@utility duration-normal { --tw-duration: var(--motion-normal); transition-duration: var(--motion-normal); }
@utility duration-slow   { --tw-duration: var(--motion-slow);   transition-duration: var(--motion-slow); }
```

### 7.2 Mapping

| Role | Duration | Easing (enter / exit) | Distance | Today |
|---|---|---|---|---|
| Hover, press, colour, toggles | fast 120 | standard | — | 150 |
| Tooltip | fast 120 after a 300 ms delay | enter / exit | 4 px | 150 |
| Popover, menu, select | fast 120 | enter / exit | 4 px + zoom 97% | 100 |
| Send scale-in | fast 120 | enter | zoom 95% | 120 (spec) |
| Live inbound message | normal 150 | enter | rise 4 px | 150 (spec) |
| Inline reveal (Ask steps, chevrons) | normal 150 | standard | — | 150 |
| Suggestion bar | slow 200 | enter | rise 8 px | 180 (spec): **Change, logged for confirmation** |
| Dialog, alert dialog | slow 200 in, fast 120 out | enter / exit | fade + zoom 95% | 100 |
| Sheet, drawer, Ask panel, run detail | slow 200 in, fast 120 out | enter / exit | fade + 40 px slide; the scrim fades over the same time | 200; overlay 100; Ask has no fade |
| Toasts | sonner's own | sonner's own | — | (keep; sonner honours reduced motion) |
| Progress fills | 500 (credits), 150 (uploads) | standard | — | (keep) |
| Ambient loops (shimmer, automation line, pulse, ping) | 1–2 s | linear / pulse | — | (keep) |

### 7.3 Rules

- Exits are faster than entries; an overlay's scrim fades with its panel; one slide distance per
  surface type.
- Name the transitioned properties (`transition-[color,background-color,border-color,filter]`);
  no `transition-all`; never transition `outline-color` (the focus ring must appear at once).
- No new animation without a job (feedback for an action, or arrival of live content). No motion
  for decoration.

### 7.4 Reduced motion

Under `prefers-reduced-motion: reduce`:

- **Every enter and exit is instant**, including the overlays (today they still animate).
- **Ambient loops stop:** shimmer, the automation line, pulse, ping, the skeleton pulse.
- **Colour and opacity state changes** may keep a fast fade.
- **Spinners stop** (`motion-safe:animate-spin`); the static icon, the `aria-busy` state and the
  label still say "loading". This follows C-065 (the Home refresh spinner is motion-safe) and is a
  single rule through one `Spinner` component.

Mechanism: `motion-safe:` for anything app code adds; `motion-reduce:animate-none` (and
`transition-none` on sheets) inside the primitives; `@media` only inside `globals.css` utilities;
and one safety net in `globals.css`:

```css
@media (prefers-reduced-motion: reduce) {
  [data-slot$="-overlay"], [data-slot$="-content"], [data-slot="skeleton"] {
    animation: none !important;
    transition: none !important;
  }
}
```

---

## 8. Components

### 8.1 Rules

- A family has one canonical primitive (§8.2). Product components compose it; they don't restyle it
  with overrides of colour, height, radius, focus or elevation.
- Variants are added to the primitive when a real, repeated need exists, with a reason in the PR.
- Every primitive carries its own states (§8.3), touch size (§8.4) and reduced-motion handling.
- Restyled primitives use tokens and the shadcn aliases, never `dark:` classes.

### 8.2 Canonical primitive per family

| Family | Canonical | Variants and props | Replaces (source) | Status |
|---|---|---|---|---|
| Button | `ui/button` | `variant`: **`default` = primary** (brand gradient, `on-brand`, brightness hover), `secondary`, `outline`, `ghost`, `destructive` (solid `danger-fill`), `destructive-ghost` (`danger-fg` text, for triggers that open a confirmation), `link` (`brand-fg`) · `size`: `xs`, `sm`, `default`, `lg`, `xl`, `icon-xs`, `icon-sm`, `icon`, `icon-lg` · `loading` | 58 gradient overrides (D1), 5 destructive styles (D2), 7 raw links, label-only loading (D16) | Change |
| Disabled reason | `ui/disabled-reason` (focusable wrapper with Tooltip and `sr-only` text) | `reason` | `title` on disabled controls (CMP-010) | Add |
| Spinner | `ui/spinner` | `size` | 36 `Loader2`/`LoaderCircle` with mixed rules (MOT-006) | Add |
| Text field | `ui/input` | `size` (`sm`, `default`, `lg`, `xl`); native `type="date"`/`"time"` allowed (D-04) | 17 raw inputs; two looks (CMP-011) | Change |
| Textarea | `ui/textarea` | — | 5 raw textareas (composers may keep a wrapper, focus per §8.3) | Change |
| Select | `ui/select` | trigger `size` like Input | the native `<select>` in PostPreview | Change |
| Checkbox | `ui/checkbox` | checked, unchecked, **indeterminate** (minus icon, filled) | (CMP-027) | Change |
| Switch | `ui/switch` | — | | Keep (edge and focus Change) |
| Field | `ui/field` (shadcn Field: `Field`, `FieldLabel`, `FieldDescription`, `FieldError`) | `density`: `default`, `compact`; generates ids, `aria-describedby`, `aria-invalid` | 3 private `Field`s, hand-wired labels (D10) | Add |
| Search | `ui/search-input` (on Input) | Escape clears | 6 implementations (D11) | Add |
| Chip-list input | `ui/chip-input` | validation and counter props | ChipListInput, KeywordInput, PhraseChips (D12) | Add |
| Segmented control | `ui/toggle-group` | `variant`: `segmented`, `chips` · `type`: `single`, `multiple` · `size`: `sm`, `default` | PlatformStrip, filter chips ×5 (D3, D4) | Change |
| Tabs (swap panels) | `ui/tabs` | `size` like ToggleGroup | the inbox's hand-rolled tablist | Change |
| Dialog | `ui/dialog` | `size`: `sm`, `md`, `lg`, `xl`; title `text-base font-semibold` (`lg` dialogs `text-lg`); scrolls within `100dvh − 2rem` | 4 title styles, per-dialog `max-h` (CMP-024) | Change |
| Alert dialog | `ui/alert-dialog` | confirm uses Button `destructive` or `default` | popover confirm (ScheduledList) | Change |
| Sheet | `ui/sheet` | `side`; **`size="panel"`** (full screen below `md`, fixed width above) | AskPanel and run detail on `DialogPrimitive` (D13) | Change |
| Popover | `ui/popover` | — | per-site surface and shadow | Change |
| Dropdown menu | `ui/dropdown-menu` | item `variant="destructive"` (`danger-fg`) · content `min-w-48 w-auto` | per-site widths and labels | Change |
| Tooltip | `ui/tooltip` (level 1 surface on `rounded-md`, an arrow with the same fill and edge) | — | native `title` on meaningful elements (D15) | Change; colour **Owner D-03**, applied (UI-017; C-069) |
| Toaster | `ui/sonner` | `position` by width; action toasts last 10 s or more | bare `<Toaster>` | Add |
| Badge | `ui/badge` | `tone`: `neutral` (`hover` fill), `brand` (info), `success`, `warning`, `danger` (soft fills), `count` (brand gradient, `on-brand`) · `size`: `sm` (11 px), `md` (12 px; counts) · `shape`: `pill`, `tag` (`rounded-sm`, thumbnail labels) | 77 ad-hoc badges, 8 tone maps, two `StatusChip`s (D6) | Change |
| Card | `ui/card` (`Card`, `CardHeader`, `CardInset`) | `padding`: `standard`, `roomy` · `tone`: `default`, `danger`, `brand` · exposes its padding for bleeds | SettingsCard (becomes a thin wrapper), composer Section, 85 surfaces (D7) | Add; radius **Owner D-02** |
| Alert | `ui/alert` | `tone` · `variant`: `soft`, `outline` · one action (`Button secondary size="sm"`) | BannerSlot internals, 17 callouts, 4 tinted actions (D8, D9) | Add |
| Meter | `ui/meter` (`role="meter"`) | `kind`: `consumable` (warning at 80%, danger at 100%), `slot` (neutral "All used" at 100%) | UsageMeter, QuotaTile, UsageCard, ScheduleRail, LeadScore (D5) | Add |
| Progress | `ui/progress` (`role="progressbar"`) | — | upload and analysis bars (D5) | Add |
| Table | `ui/table` | — | SourcesCard, PaymentHistory, Ask Markdown tables (D19) | Add |
| Skeleton | `ui/skeleton` | default `bg-raised`, pulse `motion-safe` | 114 overrides | Change |
| Avatar | `ui/avatar` with `AvatarBadge`; product wrapper `ContactAvatar` | `size`, `platform` | AccountAvatar, AccountCard inline, marketing Avatar (D18) | Change |
| Empty and error states | `states/EmptyState`, `states/ErrorState` | `size`: `default`, `compact` | 13 inline versions (D17) | Change |

### 8.3 Interaction states

| State | Rule |
|---|---|
| **Hover** | Neutral controls and rows `bg-hover`; on `raised`, `bg-raised-hover`; primary `brightness-110`; destructive `danger-fill/90`; links underline. Tailwind 4's `hover:` already applies only to devices that hover. |
| **Pressed / open** | `bg-pressed` for `aria-expanded` and `data-state=open`; primary `active:brightness-95`. |
| **Focus** | One recipe: the global `:focus-visible` outline (2 px `ring`, offset 2 px). Primitives don't remove it (`outline-none`, `outline-hidden`) and don't add a ring halo. Inside clipping containers (menu items, segmented tracks, scrolling rows) the outline is inset: `focus-visible:-outline-offset-2`. Text fields also turn their border `ring`. A wrapper whose inner element takes focus (the composers) shows the outline with `has-[:focus-visible]:`. A soft halo is allowed only beside the outline, never instead of it. |
| **Selected** | Rows and nav: `bg-raised` + the selection bar, `aria-current`. Segments: `bg-raised text-brand-fg`, `aria-pressed`/`aria-selected`. Chips: `bg-brand-soft text-brand-fg border-brand-line`. Tiles: 2 px `brand` border. |
| **Disabled** | `opacity-50`. A control disabled for a reason is wrapped in `DisabledReason`. Exception: the composers' Send while empty keeps UX-INB-07's neutral look (`bg-raised text-fg-disabled`), as a Button state, not hand-rolled. |
| **Loading** | Buttons: `loading` (Spinner, `aria-busy`, disabled, width kept). Lists and cards: skeletons shaped like the content. Pages: PageSkeleton inside the shell. |
| **Invalid** | `aria-invalid` → `border-danger`; the message `text-xs text-danger-fg` linked by Field through `aria-describedby`. |
| **Success** | A toast (short title, no full stop) or an inline "Saved" status; no green field borders. |
| **Highlighted (menus, selects)** | `bg-hover` for pointer and keyboard; keyboard adds the inset outline (`focus-visible`). Destructive items `danger-fg` on `danger-soft`. |

### 8.4 Control size ladder

| Size | Fine pointer | Coarse pointer | Used by |
|---|---:|---:|---|
| `xs` | 24 px | 40 px minimum | Dense inline actions (failed-message actions) |
| `sm` | 28 px | 40 px | Card-footer actions, compact toolbars, list-header controls |
| `default` | 32 px | 40 px | Most buttons, inputs, select triggers, segment items |
| `lg` | 36 px | 40 px | Primary page actions, larger forms |
| `xl` | 40 px | 40 px | Settings forms (C-066: "controls are 40 px tall there"), the composer's Send on phones |

- **Coarse pointers get 40 px everywhere** (`pointer-coarse:min-h-10`, icon sizes
  `pointer-coarse:size-10`), inside the primitives. Not `md:`: tablets and touch laptops above
  768 px need it too, and a narrow desktop window doesn't.
- Where the visual must stay small (a chip's remove ×, a checkbox), the hit area is extended to
  40 px with a pseudo-element, as the checkbox and switch already do.
- Controls on one row share a size. Menu and select items are 40 px on coarse pointers.
- Desktop density does not change: today's 24/28/32/36 stay, `xl` formalises the settings' 40.

### 8.5 Deliberately not built

- **No `primary` variant name** next to `default`: two names for one look. `default` is the primary.
- **No `tint` button variant** for actions on coloured banners: they use `secondary size="sm"`.
- **No `shadow-raised`**: active segments are already distinct (`raised` + `brand-fg`).
- **No RadioGroup yet**: the three native radio cards pass (visible focus, labelled). Add it when a
  new radio list appears.
- **No Calendar, Command, ScrollArea or Separator yet** (D-04 for Calendar; Command when the
  timezone picker needs search).
- **No new info, chart or tint colour tokens** (§1.5, §1.8).

---

## 9. Responsive rules

- **Breakpoints:** `md` 768 (top bar and drawer below it), `lg` 1024 (sidebar expands; three-column
  dashboards), `xl` 1280 (inbox details inline; settings two columns), `wide` 1440 (inbox details
  open by default; schedule rail inline). `sm` (640) only inside primitives (dialog widths) and on
  marketing pages. JS reads the same numbers from one `BREAKPOINTS` module; `min-[1440px]:` becomes
  `wide:`.
- **Server render:** JS media hooks pass an explicit server value; phone-first where a desktop
  flash would cover content, desktop where a layout jump would be worse; documented at the call.
- **Prefer CSS** (`hidden md:flex`) when a component only changes visibility.
- **Grids and flex rows:** grids start at `grid-cols-1`; grid and flex children that truncate get
  `min-w-0`; in a header row, the identifying text (a name, a title) has a minimum width and other
  items shrink or move first. Container queries are allowed when a pane's width, not the
  viewport's, decides (the thread header).
- **Full-height frames** are flex children (`flex-1 min-h-0`) of a full-height `<main>`, not
  `calc(100dvh − n)`, so banners don't push content off-screen. `dvh` units for the shell.
- **Sticky bars:** pages set scroll padding for their sticky bars; bars become static on short
  viewports (`max-height: 500px`).
- **Overlays:** dialogs scroll within `100dvh − 2rem`; sheets and panels are full-screen below `md`;
  toasts are top-centre below `md`, bottom-right above.
- **Scrolling rows** (chips, tabs) have an edge-fade mask and stay keyboard-reachable; wrap onto two
  rows from `md` where space allows.
- **Touch:** §8.4; controls revealed on hover are hidden only for fine pointers
  (`pointer-fine:opacity-0 pointer-fine:group-hover:opacity-100`).
- **Check widths:** 375, 768, 1280 and 1536 px for every change (the brief); also 360 and 1024
  (the spec's), 320 (WCAG reflow) and 640 × 450 (200% zoom) for layout changes.

---

## 10. Accessibility rules

The bar is WCAG 2.2 AA and the spec's UX-A11Y-01…05.

1. **Contrast:** §1.11. Placeholders are text. No text on `brand` or platform colours. Opacity
   never dims text below its token.
2. **Focus:** one visible recipe (§8.3), at least 3:1 on its surface; never removed without a
   replacement; never hidden under a sticky bar; returned to the trigger when an overlay closes
   (overlays stay mounted and are driven by `open`).
3. **Keyboard:** everything works by keyboard; Radix for menus, selects, dialogs and tabs; custom
   tab sets use `Tabs`; a skip link first in the shell; single-key shortcuts can be turned off
   (D-14).
4. **Names and roles:** icon-only buttons have `aria-label`; `aria-label` only on elements with a
   role (otherwise `sr-only` text or `role="img"`); state is announced as well as shown (unread,
   selected, pressed, busy, invalid).
5. **Forms:** every input has a visible label through Field; hints and errors are linked with
   `aria-describedby`; errors are text, not colour alone.
6. **Live regions:** polite only; the message log announces new inbound messages only; toasts are
   polite; ticking timers are not announced.
7. **Touch:** 40 × 40 px on coarse pointers (§8.4); 24 px minimum everywhere.
8. **Motion:** §7.4.
9. **Structure:** one `<h1>` per page (`sr-only` when the visible title lives elsewhere); landmarks
   labelled and unique; every route sets a page `<title>`.
10. **Language:** `lang` on customer text when its language is known.
11. **Colour is never the only cue:** status chips carry text; charts carry legends, numbers and a
    table or label.
12. **Time limits:** toasts with actions last 10 s or more (or persist with a close button).
13. **Verification:** axe-core (tags `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 375
    and 1280 px, a keyboard pass, and an emulated `prefers-reduced-motion: reduce` pass.

---

## 11. How the auditors' proposals were reconciled

Where the audits proposed different values or patterns, one was chosen.

| Topic | Proposals | Chosen | Why |
|---|---|---|---|
| Control-edge colour | `#6B6B6B` (COL-004), `#71717A` (A11Y-006), white 40% or `#737373` (CMP-009), white ~33% (RAD-003) | white 40% | The only candidate at 3:1 or more on every surface, including raised and overlay; joins the white-alpha line family (§1.2) |
| Solid brand fill with text | `#4467E6` (COL-001), `#3B5BD9` (A11Y-005), the gradient (CMP-006) | `#4467E6` as `brand-strong` | Already in the system (the gradient's end), so no new colour; 4.85:1 |
| Focus recipe | solid outline or 2 px ring (COL-003), global outline (CMP-008, A11Y-004), 2 px ring with offset (A11Y-004, RAD-002) | the global outline | Already passes everywhere; deleting code beats adding a ring; one recipe for raw and primitive elements |
| Menu highlight | `brand-soft` + inset bar or outline (CMP-001) | `hover` fill + inset outline on keyboard focus | `brand-soft` on panel is only 1.21:1, so the outline carries the indicator; a brand bar would read as "selected" |
| Primary button | redefine `default` (CMP-002) vs a new `primary` variant (COL-005, VH-003) | redefine `default` | One name per look; `buttonVariants()` users (AlertDialogAction, the Link at PriorityQueue) get it for free; how many primaries per view is D-10 |
| Destructive | solid `danger-fill` + `destructive-ghost` (CMP-003), soft tint with `danger-fg` (COL-008), solid for confirmations, neutral triggers (VH-006) | solid for the confirming action, `destructive-ghost` for triggers | 12 confirmations are already solid; triggers keep a danger cue at AA; card placement is D-09 |
| Touch-size strategy | `md:` or `pointer-coarse:` (SPC-001), `pointer-coarse:` (CMP-004, A11Y-009) | `pointer-coarse:` | Tablets and touch laptops above 768 px need it; narrow mouse windows don't |
| Desktop control heights | 32/36/40 (SPC-001), keep density (A11Y-009), inputs 36 (CMP-011) | keep 24/28/32/36, add `xl` 40 | No app-wide density change; settings' 40 px becomes a named size |
| Dialog title | `text-lg semibold` (CMP-024), `text-base semibold` + `size="lg"` (TYP-005) | `text-base semibold`, `lg` for large dialogs | Matches the card-title role; 6 of 12 dialogs are already 16 px |
| Tinted banner action | a `tint` Button variant (CMP D9) | `secondary size="sm"` | No new variant or recipe; works on every tone |
| Active-segment lift | `shadow-raised` (SHD C.2) | none | Today's `shadow-sm` is a no-op; the segment already reads |
| Spinners under reduced motion | keep spinning (MOT-006), `motion-safe` (CMP-017) | `motion-safe` | C-065 already approved a motion-safe refresh spinner; one rule via `Spinner` |
| Suggestion bar | 180 ms (spec), 200 ms (MOT) | 200 ms | Joins the `slow` token; logged for confirmation |
| Avatars | six pairs incl. teal and violet (COL-014) | up to four from existing values (D-13) | No new colours; names sit beside every avatar |
| Info and chart colours | `info*` and `chart-*` aliases (COL-021) | none | Tones and charts map to existing tokens in one place; fewer names |
| Small-button radius | `rounded-lg` everywhere (RAD-005), spec `rounded-md` | `rounded-md` for small sizes | The spec's value and today's rendered 6 px; only the `min()` expression goes |
| `--radius` | delete or wire (RAD-005) | keep, commented as inert | It is in UX-TOK-01's "exactly as below" file; nothing reads it |
| Field heights | 32 (today), 36 (CMP-011), 40 (C-066) | the Button ladder, `size` prop | One ladder for every control |

---

## 12. What needs the owner

| Item | Section | Decision |
|---|---|---|
| `line-control` and its scope | §1.2, §5 | D-01 (applied, C-071) |
| Card radius | §4 | D-02 |
| Tooltip colour | §8.2 | D-03 (applied, UI-017) |
| Native date and time inputs | §8.2, §8.5 | D-04 |
| Page and pane title sizes | §2.1 | D-05 |
| Placeholder colour | §1.3 | D-06 (applied, C-071) |
| Overlay surface and elevation shadows | §1.1, §6 | D-12 (applied, C-071) |
| Identity palette | §1.7 | D-13 |
| Icon-button and composer radius | §4 | D-16 |
| Latin-ext only, or Devanagari too | §2 | D-17 |

Everything marked **Add** is logged in one CONFLICTS entry (open: confirm), like C-002, by UI-001.
Everything marked **Change** implements an approved rule and is recorded in BUILD_SPEC §4.2 by
UI-071 (the spec's type table, radius, elevation and motion lines, UX-INB-03's focus wording).
